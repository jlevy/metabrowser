// The in-page half of the WebKit measurement gate (run.mjs), the same file in
// Chrome and in the app's WKWebView.
//
// Each driver injects this at document start in the main frame, after a line
// that sets `globalThis.__webkitGateConfig` to the case to run. The probe then
// watches the page load, drives the view the way a reader would (Load more,
// scrolling), and resolves `globalThis.__webkitGate.done` with one JSON-ready
// record. The driver awaits that promise and adds what only it can see: the
// renderer's memory footprint.
//
// Timing is read with performance.now() in the page, so both engines measure
// the same intervals with the same code:
//
//   - `dom`: the trigger (navigation start or a click) to the mutation that
//     mounts the content, read in a MutationObserver callback, so it includes
//     the request, JSON parsing, and building the DOM, and never waits for a
//     frame.
//   - `layout`: the same, then a forced layout of the document.
//   - `after_response`: `layout` minus the response end of the view's request
//     (Resource Timing), which takes out the server and leaves the engine's
//     work: parsing, DOM, style, and layout.
//   - `frame`: after `layout`, the next requestAnimationFrame and a task queued
//     from it, so it includes the next rendering update. This one waits for a
//     display frame, so it is quantized by the refresh rate.
//   - Scroll work: started inside a requestAnimationFrame callback and read in
//     a task queued from it, so it is the rendering update the scroll caused,
//     without waiting for vsync.
/**
 * The case to run, as run.mjs writes it: `case` and `timeoutMs` always, and the fields
 * that case's entry in run.mjs's CASES sets. Each method in `cases` below reads only its
 * own case's fields.
 * @typedef {{
 *   case: string, timeoutMs?: number,
 *   corpora: { language: string, file: string }[],
 *   corpusUrl: string, chunks: number[], mode: "single" | "split" | "blocks",
 *   resultKey: string, errorKey: string,
 *   sweepCaps: number[], rounds: { metric: number, hover: number, sweep: number }
 * }} ProbeConfig
 */
(() => {
  const gate = /**
   * @type {typeof globalThis & {
   *   __webkitGateConfig?: ProbeConfig, __webkitGate?: { done: Promise<unknown> }
   * }}
   */ (globalThis);
  const config = gate.__webkitGateConfig;
  if (!config || window.top !== window || gate.__webkitGate) {
    return;
  }

  const TIMEOUT_MS = config.timeoutMs || 120_000;
  const now = () => performance.now();
  const round = (/** @type {number | null | undefined} */ value) =>
    typeof value === "number" && Number.isFinite(value) ? Math.round(value * 10) / 10 : null;
  const delay = (/** @type {number} */ ms) => new Promise((resolve) => setTimeout(resolve, ms));

  /**
   * The next rendering update has run: a task queued from requestAnimationFrame.
   * A page that is not displayed gets no frames, so a long wait fails the sample
   * rather than hanging it.
   */
  const afterNextFrame = () =>
    new Promise((resolve, reject) => {
      const stalled = setTimeout(
        () => reject(new Error("no animation frame in 10 s: the page is not being displayed")),
        10_000,
      );
      requestAnimationFrame(() =>
        setTimeout(() => {
          clearTimeout(stalled);
          resolve(now());
        }, 0),
      );
    });

  /**
   * Time the rendering update one change causes. `change` runs at the start of
   * a frame; the task queued after it runs once that frame's style, layout,
   * and paint are done.
   */
  const frameWork = (/** @type {() => void} */ change) =>
    new Promise((resolve) =>
      requestAnimationFrame(() => {
        const started = now();
        change();
        setTimeout(() => resolve(now() - started), 0);
      }),
    );

  /** The document's load event has fired. */
  const loaded = () =>
    document.readyState === "complete"
      ? Promise.resolve()
      : new Promise((resolve) => addEventListener("load", resolve, { once: true }));

  /** Forces style and layout of the whole document. */
  const forceLayout = () => {
    void document.documentElement.getBoundingClientRect();
    return document.documentElement.scrollHeight;
  };

  /**
   * Resolves with the first truthy value of `test`, checked now and after every
   * DOM mutation, with the time of the mutation callback that produced it.
   */
  function whenDom(/** @type {() => any} */ test, timeoutMs = TIMEOUT_MS) {
    return new Promise((resolve, reject) => {
      const first = test();
      if (first) {
        resolve({ value: first, at: now() });
        return;
      }
      const observer = new MutationObserver(() => {
        const value = test();
        if (value) {
          const at = now();
          observer.disconnect();
          clearTimeout(timer);
          resolve({ value, at });
        }
      });
      observer.observe(document, { childList: true, subtree: true });
      const timer = setTimeout(() => {
        observer.disconnect();
        reject(new Error(`no matching DOM after ${timeoutMs} ms`));
      }, timeoutMs);
    });
  }

  /** Resolves once the DOM has gone `ms` without a mutation, or after 10 s regardless. */
  function quiet(/** @type {number} */ ms) {
    return new Promise((resolve) => {
      let timer = setTimeout(done, ms);
      const observer = new MutationObserver(() => {
        clearTimeout(timer);
        timer = setTimeout(done, ms);
      });
      const cap = setTimeout(done, 10_000);
      function done() {
        observer.disconnect();
        clearTimeout(timer);
        clearTimeout(cap);
        resolve(undefined);
      }
      observer.observe(document, { childList: true, subtree: true, characterData: true });
    });
  }

  /** The last request whose URL contains `fragment` and that started at or after `since`. */
  function request(/** @type {string} */ fragment, /** @type {number} */ since) {
    const entries = /** @type {PerformanceResourceTiming[]} */ (
      performance.getEntriesByType("resource")
    ).filter((entry) => entry.name.includes(fragment) && entry.startTime >= since - 1);
    const last = entries[entries.length - 1];
    return last ? { start: last.startTime, response_end: last.responseEnd } : null;
  }

  /** Smallest positive step of performance.now(), which engines coarsen differently. */
  function timerResolution() {
    let smallest = Number.POSITIVE_INFINITY;
    let previous = now();
    for (let index = 0; index < 200_000 && smallest > 0.001; index += 1) {
      const current = now();
      const step = current - previous;
      if (step > 0 && step < smallest) {
        smallest = step;
      }
      previous = current;
    }
    return Number.isFinite(smallest) ? Math.round(smallest * 1000) / 1000 : null;
  }

  /** Median interval between animation frames, which differs by engine and display. */
  async function frameInterval(/** @type {number} */ frames = 30) {
    /** @type {number[]} */
    const stamps = [];
    for (let index = 0; index <= frames; index += 1) {
      stamps.push(
        await /** @type {Promise<number>} */ (
          new Promise((resolve) => requestAnimationFrame(resolve))
        ),
      );
    }
    const steps = stamps.slice(1).map((stamp, index) => stamp - stamps[index]);
    steps.sort((a, b) => a - b);
    return round(steps[Math.floor(steps.length / 2)]);
  }

  function environment() {
    return {
      user_agent: navigator.userAgent,
      device_pixel_ratio: devicePixelRatio,
      viewport: { width: innerWidth, height: innerHeight },
      visibility: document.visibilityState,
    };
  }

  /** The nearest ancestor that scrolls vertically. */
  function scroller(/** @type {Element} */ element) {
    for (let node = element.parentElement; node; node = node.parentElement) {
      const overflow = getComputedStyle(node).overflowY;
      if ((overflow === "auto" || overflow === "scroll") && node.scrollHeight > node.clientHeight) {
        return node;
      }
    }
    return document.scrollingElement || document.documentElement;
  }

  /** A Load more control a reader could press. */
  function visibleLoadMore(/** @type {string} */ selector) {
    for (const button of /** @type {NodeListOf<HTMLButtonElement>} */ (
      document.querySelectorAll(selector)
    )) {
      if (!button.hidden && !button.closest("[hidden]") && !button.disabled) {
        return button;
      }
    }
    return null;
  }

  /** Scroll positions as fractions of the scroll range, each timed as one frame's work. */
  async function scrollWork(/** @type {Element} */ element) {
    await quiet(500);
    const range = element.scrollHeight - element.clientHeight;
    const samples = [];
    for (const fraction of [0.5, 1, 0.25, 0.75, 0]) {
      await afterNextFrame();
      const work = await frameWork(() => {
        element.scrollTop = Math.round(range * fraction);
      });
      samples.push({ to: fraction, work_ms: round(/** @type {number} */ (work)) });
    }
    return { scroll_height: element.scrollHeight, client_height: element.clientHeight, samples };
  }

  /**
   * Open a view by navigation, then press Load more until nothing is left.
   *
   * @param {{content: string, button: string, request: string,
   *          signature: (content: Element) => string,
   *          loaded: (content: Element) => number}} view
   */
  async function openAndLoad(view) {
    const opened = await whenDom(() => document.querySelector(view.content));
    forceLayout();
    const layoutAt = now();
    const frameAt = /** @type {number} */ (await afterNextFrame());
    const openRequest = request(view.request, 0);
    const open = {
      dom_ms: round(opened.at),
      layout_ms: round(layoutAt),
      frame_ms: round(frameAt),
      after_response_ms: openRequest ? round(layoutAt - openRequest.response_end) : null,
      response_end_ms: openRequest ? round(openRequest.response_end) : null,
      loaded: view.loaded(opened.value),
    };

    const clicks = [];
    for (let guard = 0; guard < 64; guard += 1) {
      const button = visibleLoadMore(view.button);
      if (!button) {
        break;
      }
      // Let the view settle first: the binary view re-breaks its lines 150 ms after
      // its first chunk, when its ResizeObserver first reports the pane width.
      await quiet(500);
      await afterNextFrame();
      const current = /** @type {Element} */ (document.querySelector(view.content));
      const before = view.signature(current);
      const loadedBefore = view.loaded(current);
      const started = now();
      button.click();
      const changed = await whenDom(() => {
        const next = document.querySelector(view.content);
        return next && view.signature(next) !== before ? next : null;
      });
      forceLayout();
      const clickLayoutAt = now();
      const clickFrameAt = /** @type {number} */ (await afterNextFrame());
      const clickRequest = request(view.request, started);
      const loadedAfter = view.loaded(changed.value);
      clicks.push({
        added: loadedAfter - loadedBefore,
        loaded: loadedAfter,
        dom_ms: round(changed.at - started),
        layout_ms: round(clickLayoutAt - started),
        frame_ms: round(clickFrameAt - started),
        after_response_ms: clickRequest ? round(clickLayoutAt - clickRequest.response_end) : null,
        response_ms: clickRequest ? round(clickRequest.response_end - started) : null,
      });
    }
    const content = /** @type {Element} */ (document.querySelector(view.content));
    return { open, clicks, content };
  }

  /**
   * Time one change as a handler and as a frame: `handler_ms`, the change's own
   * synchronous work, and `work_ms`, that and the rendering update it causes (frameWork).
   * @param {() => void} change
   */
  async function timedChange(change) {
    let handler = 0;
    const work = /** @type {number} */ (
      await frameWork(() => {
        const started = now();
        change();
        handler = now() - started;
      })
    );
    return { handler_ms: round(handler), work_ms: round(work) };
  }

  /** Nodes in a rollup tree: every folder and file, each counted once. */
  function countNodes(/** @type {Record<string, any>} */ node) {
    let total = 0;
    const stack = [node];
    while (stack.length > 0) {
      const next = /** @type {Record<string, any>} */ (stack.pop());
      total += 1;
      for (const child of Array.isArray(next.children) ? next.children : []) {
        stack.push(child);
      }
    }
    return total;
  }

  /** Characters in an element's own text nodes, without building a string. */
  const textLength = (/** @type {Element} */ element) => {
    let total = 0;
    for (const node of element.childNodes) {
      total += node.nodeType === Node.TEXT_NODE ? /** @type {Text} */ (node).length : 0;
    }
    return total;
  };

  const cases = {
    /** The source view: a plain text file opened, loaded to the end, then scrolled. */
    async source() {
      const { open, clicks, content } = await openAndLoad({
        content: ".metabrowser-source-host pre.code-block > code",
        button: ".metabrowser-source-host button.metabrowser-load-more",
        request: "/api/file",
        signature: (code) =>
          `${code.childNodes.length}|${
            document.querySelector(".metabrowser-source-truncation-warning")?.textContent ?? ""
          }`,
        loaded: textLength,
      });
      return {
        open,
        clicks,
        dom_elements: document.getElementsByTagName("*").length,
        scroll: await scrollWork(scroller(content)),
      };
    },

    /** The binary view: a file opened, loaded to the preview ceiling, then scrolled. */
    async binary() {
      const { open, clicks, content } = await openAndLoad({
        content: ".binary-bytes-content",
        button: ".binary-bytes button.metabrowser-load-more",
        request: "chunk",
        // The readout, not the block count: a re-break changes the blocks and not the bytes.
        signature: () =>
          document.querySelector(".binary-bytes .partial-notice-readout")?.textContent ?? "",
        loaded: (element) => element.querySelectorAll(".binary-bytes-block").length,
      });
      return {
        open,
        clicks,
        readout: document.querySelector(".binary-bytes .partial-notice-readout")?.textContent,
        accent_dropped: content.classList.contains("binary-bytes-plain"),
        blocks: content.querySelectorAll(".binary-bytes-block").length,
        dom_elements: document.getElementsByTagName("*").length,
        scroll: await scrollWork(scroller(content)),
      };
    },

    /**
     * The Treemap tab on a folder's view, chosen once the folder's Overview has settled:
     * timed from the click, and from the rollup's response end, to the mutation that mounts
     * the map's labels, and to the next frame. Then each metric switch's relayout and
     * repaint, and the largest family's legend hover entering and leaving, each timed as
     * its handler and as one frame's work. Last, the view's own rollup laid out with the
     * map's own modules at each of `sweepCaps` cells, the curve PAINT_MAX_CELLS
     * (treemap-map.js) is set from: the layout, paint list, hit grid, and paint that a
     * relayout runs, and the hover's marks for the largest family, as drawCellHover runs
     * them. The sweep paints with fixed colors, where the map reads each style's from a
     * probe element once and keeps it, and its labels are not drawn.
     */
    async treemap() {
      // The shell loads many modules and requests before the rollup; the default buffer of
      // 250 entries could drop the rollup's.
      performance.setResourceTimingBufferSize(5000);
      const HOST = ".folder-treemap-host";
      const tab = /** @type {HTMLElement} */ (
        (
          await whenDom(() =>
            document.querySelector('#preview-pane > .tab-bar > .tab-btn[data-tab="treemap"]'),
          )
        ).value
      );
      // The Overview's first paint, its compact map's rollup among it, before the click.
      await quiet(1000);
      await afterNextFrame();
      if (document.querySelector(`${HOST} .tm-label-cell`)) {
        throw new Error("the Treemap's labels were mounted before its tab was chosen");
      }
      // The map's module, whose inspectTreemap reads the map it mounted, as
      // tests/dom/treemap-legend-hover-chrome.mjs reads it. The Overview's compact map has
      // loaded it already, so importing it here costs the timing below nothing.
      const mapModuleUrl = () =>
        performance
          .getEntriesByType("resource")
          .map((entry) => entry.name)
          .find((name) => /\/treemap-map\.js(\?|$)/.test(name));
      const preloaded = mapModuleUrl();
      const earlyModule = preloaded ? await import(preloaded) : null;
      await afterNextFrame();
      /** @type {unknown} */
      let cellsAtMount = null;
      const started = now();
      tab.click();
      const labelled = await whenDom(() => {
        const label = document.querySelector(`${HOST} .tm-viewport .tm-label-cell`);
        if (label && earlyModule) {
          // The layout the labels belong to, to tell whether a later one replaces it.
          cellsAtMount = earlyModule.inspectTreemap(label.closest(".tm-viewport"))?.cells ?? null;
        }
        return label;
      });
      forceLayout();
      const layoutAt = now();
      const mountedViewport = /** @type {HTMLElement} */ (labelled.value.closest(".tm-viewport"));
      const boxAtMount = [mountedViewport.clientWidth, mountedViewport.clientHeight];
      const frameAt = /** @type {number} */ (await afterNextFrame());
      const boxAfterFrame = [mountedViewport.clientWidth, mountedViewport.clientHeight];
      /** Whether the map has been laid out again since its labels mounted, or null. */
      const relaidOut = () =>
        earlyModule && cellsAtMount
          ? earlyModule.inspectTreemap(mountedViewport)?.cells !== cellsAtMount
          : null;
      const relaidOutByFrame = relaidOut();
      // The Treemap's rollup, the only one that names a node budget (treemapFullRollupQuery).
      const rollups = /** @type {PerformanceResourceTiming[]} */ (
        performance.getEntriesByType("resource")
      ).filter((entry) => entry.name.includes("nodes=max") && entry.startTime >= started - 1);
      const rollup = rollups[0];
      if (!rollup) {
        throw new Error("no Resource Timing entry for the Treemap's rollup");
      }
      const open = {
        dom_ms: round(labelled.at - started),
        layout_ms: round(layoutAt - started),
        frame_ms: round(frameAt - started),
        response_end_ms: round(rollup.responseEnd - started),
        after_response_dom_ms: round(labelled.at - rollup.responseEnd),
        after_response_frame_ms: round(frameAt - rollup.responseEnd),
        rollup_requests: rollups.length,
        // A second layout in the frame after the first, as when the legend's entries wrap
        // the row above the map and its ResizeObserver lays it out again (treemap.js).
        relaid_out_by_frame: relaidOutByFrame,
        relaid_out_after: /** @type {boolean | null} */ (null),
        box_at_mount: boxAtMount,
        box_after_frame: boxAfterFrame,
        rollup: {
          transfer_bytes: rollup.transferSize || null,
          encoded_bytes: rollup.encodedBodySize || null,
          decoded_bytes: rollup.decodedBodySize || null,
        },
      };

      const legendSelector = `${HOST} .tm-legend li[data-legend-key^="family:"]`;
      await whenDom(() => document.querySelector(legendSelector));
      await quiet(500);
      open.relaid_out_after = relaidOut();
      const viewport = mountedViewport;
      const mapUrl = mapModuleUrl();
      if (!mapUrl) {
        throw new Error("no Resource Timing entry for treemap-map.js");
      }
      const mapModule = earlyModule ?? (await import(mapUrl));
      const inspect = () => {
        const reading = mapModule.inspectTreemap(viewport);
        if (!reading) {
          throw new Error("no treemap is mounted on the view's viewport");
        }
        return reading;
      };
      const mounted = inspect();
      /** @type {Record<string, number>} */
      const kinds = {};
      for (const cell of mounted.cells) {
        kinds[cell.kind] = (kinds[cell.kind] ?? 0) + 1;
      }
      const counts = {
        cells: mounted.cells.length,
        painted: mounted.cells.length - mounted.empty,
        empty: mounted.empty,
        paint_rects: mounted.paint.length,
        labels: mounted.labels.length,
        label_elements: viewport.querySelectorAll(".tm-label-cell").length,
        kinds,
        dpr: mounted.dpr,
        box: { w: viewport.clientWidth, h: viewport.clientHeight },
      };

      const chip = (/** @type {string} */ value) =>
        /** @type {HTMLElement | null} */ (
          document.querySelector(`${HOST} .tm-rollup-controls [data-chip-value="${value}"]`)
        );
      const initial = chip("size")?.getAttribute("aria-checked") === "true" ? "size" : "files";
      const other = initial === "size" ? "files" : "size";
      const switches = [];
      for (let pass = 0; pass < config.rounds.metric; pass += 1) {
        for (const to of [other, initial]) {
          await quiet(300);
          await afterNextFrame();
          // The controls draw themselves again on every change, so each click finds its chip.
          const target = chip(to);
          if (!target) {
            throw new Error(`no ${to} metric chip`);
          }
          const timed = await timedChange(() => target.click());
          if (chip(to)?.getAttribute("aria-checked") !== "true") {
            throw new Error(`the ${to} metric chip did not take its click`);
          }
          switches.push({ to, ...timed, cells: inspect().cells.length });
        }
      }

      // The family with the largest share, by the metric the map was opened with.
      const share = (/** @type {Element} */ item) =>
        Number.parseFloat(
          item.querySelector(".file-type-summary-legend-percent")?.textContent ?? "",
        ) || 0;
      const entry = [...document.querySelectorAll(legendSelector)].reduce((best, item) =>
        share(item) > share(best) ? item : best,
      );
      const key = /** @type {string} */ (/** @type {HTMLElement} */ (entry).dataset.legendKey);
      const hover = {
        key,
        label: entry.querySelector(".file-type-summary-legend-label")?.textContent ?? null,
        share: share(entry),
        marked: 0,
        mark_ops: 0,
        rounds: /** @type {Record<string, number | null>[]} */ ([]),
      };
      for (let pass = 0; pass < config.rounds.hover; pass += 1) {
        await quiet(300);
        await afterNextFrame();
        const enter = await timedChange(() => entry.dispatchEvent(new MouseEvent("mouseenter")));
        const marking = inspect();
        if (marking.marked.length === 0) {
          throw new Error(`hovering ${key} marked no cell`);
        }
        hover.marked = marking.marked.length;
        hover.mark_ops = marking.markOps.length;
        await quiet(300);
        await afterNextFrame();
        const leave = await timedChange(() => entry.dispatchEvent(new MouseEvent("mouseleave")));
        hover.rounds.push({
          enter_handler_ms: enter.handler_ms,
          enter_ms: enter.work_ms,
          leave_handler_ms: leave.handler_ms,
          leave_ms: leave.work_ms,
        });
      }

      const load = (/** @type {string} */ name) => import(new URL(name, mapUrl).href);
      const [layoutModule, paintModule, hitModule, decodeModule] = await Promise.all(
        [
          "./treemap-layout.js",
          "./treemap-paint.js",
          "./treemap-hit.js",
          "./treemap-rollup-decode.js",
        ].map(load),
      );
      const body = await (await fetch(rollup.name)).arrayBuffer();
      const node = decodeModule.decodeRollupEnvelope(
        JSON.parse(new TextDecoder().decode(body)),
      ).node;
      const includeIgnored = Boolean(
        /** @type {HTMLInputElement | null} */ (
          document.querySelector(
            `${HOST} .tm-rollup-controls input[data-chip-check="folder-rollup-ignored"]`,
          )
        )?.checked,
      );
      const fileTypes = /** @type {any} */ (globalThis).metabrowser?.fileTypes;
      if (!fileTypes) {
        throw new Error("window.metabrowser.fileTypes is unavailable");
      }
      // Looked up once per extension a layout, as the map does (cellPaletteKey in
      // treemap-map.js).
      /** @type {Map<string, string>} */
      const extensionKeys = new Map();
      const paletteKey = (/** @type {Record<string, any>} */ cell) => {
        if (cell.kind === "rest") {
          return "";
        }
        const extension = cell.ext || "(none)";
        let found = extensionKeys.get(extension);
        if (found === undefined) {
          found = /** @type {string} */ (fileTypes.distributionKeyForExtension(extension));
          extensionKeys.set(extension, found);
        }
        return found;
      };
      /** @type {Map<string, {fill: string, edge: string, alpha: number}>} */
      const styles = new Map();
      const resolve = (/** @type {string} */ style) => {
        let resolved = styles.get(style);
        if (!resolved) {
          const hue = (styles.size * 47) % 360;
          resolved = { fill: `hsl(${hue} 55% 62%)`, edge: `hsl(${hue} 55% 42%)`, alpha: 1 };
          styles.set(style, resolved);
        }
        return resolved;
      };
      const box = counts.box;
      const dpr = mounted.dpr;
      const canvas = document.createElement("canvas");
      const marks = document.createElement("canvas");
      for (const element of [canvas, marks]) {
        element.width = Math.round(box.w * dpr);
        element.height = Math.round(box.h * dpr);
      }
      const paintContext = /** @type {CanvasRenderingContext2D} */ (canvas.getContext("2d"));
      const marksContext = /** @type {CanvasRenderingContext2D} */ (marks.getContext("2d"));
      const caps = [];
      for (const cap of config.sweepCaps) {
        /** @type {Record<string, number> | null} */
        let best = null;
        /** @type {{ total: number, ops: number, apply: number } | null} */
        let bestHover = null;
        for (let pass = 0; pass < config.rounds.sweep; pass += 1) {
          await afterNextFrame();
          const begun = now();
          // The label bounds are LAYOUT_DEFAULTS', which are the full map's (treemap-map.js).
          const cells = layoutModule.layoutTree(node, box, {
            maxCells: cap,
            minCellPx: 1 / dpr,
            metric: initial,
            includeIgnored,
          });
          const laidOut = now();
          // The map looks each cell's palette key up once a layout, for its hovers
          // (paletteKeys in treemap-map.js).
          extensionKeys.clear();
          const keys = cells.map(paletteKey);
          const keyedAt = now();
          const listed = paintModule.paintList(
            cells,
            (/** @type {Record<string, any>} */ cell) => `${paletteKey(cell)}|${cell.kind}`,
            dpr,
          );
          const listedAt = now();
          hitModule.buildHitGrid(cells, box, dpr);
          const gridded = now();
          paintContext.setTransform(1, 0, 0, 1, 0, 0);
          paintContext.globalAlpha = 1;
          paintContext.fillStyle = "#fff";
          paintContext.fillRect(0, 0, canvas.width, canvas.height);
          paintModule.paintCells(paintContext, listed.rects, resolve);
          const painted = now();
          const ops = paintModule.markOps(
            cells,
            (/** @type {number} */ index) => keys[index] === key,
            dpr,
          );
          const opsAt = now();
          marksContext.setTransform(1, 0, 0, 1, 0, 0);
          marksContext.clearRect(0, 0, marks.width, marks.height);
          paintModule.applyMarkOps(marksContext, canvas, ops);
          const hovered = now();
          const timing = {
            cells: cells.length,
            layout_ms: laidOut - begun,
            keys_ms: keyedAt - laidOut,
            paint_list_ms: listedAt - keyedAt,
            hit_ms: gridded - listedAt,
            paint_ms: painted - gridded,
            total_ms: painted - begun,
            mark_ops: ops.length,
          };
          if (!best || timing.total_ms < best.total_ms) {
            best = timing;
          }
          if (!bestHover || hovered - painted < bestHover.total) {
            bestHover = {
              total: hovered - painted,
              ops: opsAt - painted,
              apply: hovered - opsAt,
            };
          }
        }
        const chosen = /** @type {Record<string, number>} */ (best);
        const marking = /** @type {{ total: number, ops: number, apply: number }} */ (bestHover);
        caps.push({
          cap,
          cells: chosen.cells,
          layout_ms: round(chosen.layout_ms),
          keys_ms: round(chosen.keys_ms),
          paint_list_ms: round(chosen.paint_list_ms),
          hit_ms: round(chosen.hit_ms),
          paint_ms: round(chosen.paint_ms),
          total_ms: round(chosen.total_ms),
          hover_ms: round(marking.total),
          // The hover's parts: the mark ops, and drawing them.
          hover_ops_ms: round(marking.ops),
          hover_apply_ms: round(marking.apply),
          mark_ops: chosen.mark_ops,
        });
      }
      for (const element of [canvas, marks]) {
        element.width = 0;
        element.height = 0;
      }
      return {
        open,
        counts,
        switches,
        hover,
        sweep: {
          nodes: countNodes(node),
          bytes: body.byteLength,
          metric: initial,
          includeIgnored,
          caps,
        },
        dom_elements: document.getElementsByTagName("*").length,
      };
    },

    /**
     * Highlight.js on an attached <code>, the method behind the 512 KiB bound:
     * highlightElement plus a forced layout of the result, per grammar.
     */
    async highlight() {
      await loaded();
      const deadline = now() + 30_000;
      while (typeof (/** @type {any} */ (globalThis).hljs) === "undefined") {
        if (now() > deadline) {
          throw new Error("highlight.js did not load");
        }
        await delay(50);
      }
      const hljs = /** @type {any} */ (globalThis).hljs;
      const samples = [];
      for (const { language, file } of config.corpora) {
        const text = await (await fetch(`/raw/${encodeURIComponent(file)}`)).text();
        const pre = document.createElement("pre");
        pre.className = "code-block";
        const code = document.createElement("code");
        code.className = `language-${language}`;
        code.textContent = text;
        pre.append(code);
        document.body.append(pre);
        forceLayout();
        await afterNextFrame();
        const started = now();
        hljs.highlightElement(code);
        forceLayout();
        const elapsed = now() - started;
        samples.push({
          language,
          file,
          characters: text.length,
          elapsed_ms: round(elapsed),
          token_spans: code.getElementsByTagName("span").length,
        });
        pre.remove();
        await delay(100);
      }
      return { samples };
    },

    /**
     * A diagnostic, not a gate case: the source view's growth sequence (2, 2, 4,
     * and 8 MiB) appended to a bare page, to separate the engine's text layout
     * from the shell. `single` appends each chunk as one text node in one
     * `white-space: pre` element, as the source view does; `split` appends the
     * same text as text nodes of at most 65,536 characters, the size the HTML
     * parser splits text into; `blocks` puts every 128 lines in a
     * `content-visibility: auto` block, as the binary view does.
     */
    async appendLayout() {
      await loaded();
      const text = await (await fetch(config.corpusUrl)).text();
      const LINE_PX = 18;
      const host = document.createElement("pre");
      host.style.cssText = `margin:0;font:13px/${LINE_PX}px ui-monospace,Menlo,monospace;white-space:pre`;
      document.body.append(host);
      const steps = [];
      let offset = 0;
      for (const size of config.chunks) {
        const newline = text.indexOf("\n", offset + size - 1);
        const end = newline < 0 ? text.length : newline + 1;
        const chunk = text.slice(offset, end);
        offset = end;
        await afterNextFrame();
        const started = now();
        if (config.mode === "blocks") {
          const lines = chunk.split("\n");
          lines.pop();
          const fragment = document.createDocumentFragment();
          for (let index = 0; index < lines.length; index += 128) {
            const slice = lines.slice(index, index + 128);
            const block = document.createElement("div");
            block.style.cssText = `content-visibility:auto;contain-intrinsic-size:auto ${slice.length * LINE_PX}px`;
            block.textContent = `${slice.join("\n")}\n`;
            fragment.append(block);
          }
          host.append(fragment);
        } else if (config.mode === "split") {
          const fragment = document.createDocumentFragment();
          for (let index = 0; index < chunk.length; index += 65_536) {
            fragment.append(document.createTextNode(chunk.slice(index, index + 65_536)));
          }
          host.append(fragment);
        } else {
          host.append(document.createTextNode(chunk));
        }
        const built = now();
        forceLayout();
        const laidOut = now();
        const frame = /** @type {number} */ (await afterNextFrame());
        steps.push({
          characters: offset,
          build_ms: round(built - started),
          layout_ms: round(laidOut - started),
          frame_ms: round(frame - started),
        });
      }
      return { mode: config.mode, steps, scroll_height: document.documentElement.scrollHeight };
    },

    /** The tallest element each engine lays out. */
    async clamp() {
      await loaded();
      const tall = document.createElement("div");
      tall.style.cssText = "position:absolute;left:0;top:0;width:1px;height:100000000px";
      document.body.append(tall);
      const bounding = tall.getBoundingClientRect().height;
      const offset = tall.offsetHeight;
      tall.remove();
      return { requested_px: 100_000_000, bounding_px: bounding, offset_px: offset };
    },

    /** A committed benchmark page that publishes its own result on window. */
    async benchmark() {
      const deadline = now() + TIMEOUT_MS;
      const global = /** @type {any} */ (globalThis);
      while (global[config.resultKey] === undefined && global[config.errorKey] === undefined) {
        if (now() > deadline) {
          throw new Error(`${config.resultKey} was not published`);
        }
        await delay(50);
      }
      if (global[config.errorKey] !== undefined) {
        throw new Error(String(global[config.errorKey]));
      }
      return global[config.resultKey];
    },
  };

  const runCase = /** @type {Record<string, () => Promise<any>>} */ (cases)[config.case];
  const done = (async () => {
    if (!runCase) {
      throw new Error(`unknown case ${config.case}`);
    }
    const before = environment();
    const result = await runCase();
    return {
      case: config.case,
      environment: {
        ...before,
        visibility_at_end: document.visibilityState,
        timer_resolution_ms: timerResolution(),
        frame_interval_ms: await frameInterval(),
      },
      result,
      chrome_js_heap_bytes: /** @type {any} */ (performance).memory?.usedJSHeapSize ?? null,
    };
  })();
  // The driver awaits `done` and reports a rejection; this only keeps it from
  // being logged as unhandled before then.
  done.catch(() => {});
  gate.__webkitGate = { done };
})();

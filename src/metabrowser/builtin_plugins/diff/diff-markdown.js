// The rendered Markdown layer of a comparison whose server names a route for it, as a
// pull request's does. Source stays hydrated by the diff's existing scheduler, so a
// refusal or a reader's Source selection has a patch ready. This module names no route:
// the comparison carries the rendered route and the snapshot route that its links open.

const CONTEXT_BLOCKS = 2;
const MARKDOWN = /\.(?:md|markdown|mdown|mkd)$/i;
// How far below the viewport a projection is requested: one viewport. A projection
// answers in 12 ms at the median and 31-33 ms at p90 of server CPU (434 real pairs), plus
// the round trip, and one `git diff` serves sixteen files. In headless Chrome, the
// production client against a simulated one-slot server (420 px files in a 900 px pane;
// earlier client in adjacent runs): at 3,000 px/s and 70 ms answers only the first
// screen's 3 of 60 files swapped from Source to Rendered in view, as before; at
// 10,000 px/s, 10-11 of 100 swapped against 51, and none was left in Source by a refusal
// against 32; at 10,000 px/s and 35 ms answers, 3 swapped against 96.
const LOOKAHEAD = "100%";
// A refused request (429: the server's one projection slot is busy, often with a load
// the reader has already scrolled past) is asked again after this, doubling to the cap.
const RETRY_MS = 100;
const RETRY_MAX_MS = 1600;
// The app's --loading-state-delay: until it passes, a Markdown file on screen at mount
// waits for its projection with Source hidden, so a ready answer paints Rendered first
// and never replaces Source in view. Past it, Source shows and Rendered replaces it.
const LOADING_DELAY_MS = 50;

/** @typedef {Parameters<MetabrowserPublicSdk["loadKpressAssets"]>[0]} KpressAssetManifest */
/** @typedef {"rendered" | "source"} Mode */
/** @typedef {{kind: "context" | "removed" | "added", html: string, source_only?: boolean}} Block */
/** @typedef {{
 *   section: HTMLElement, bar: HTMLElement, toggle: HTMLElement,
 *   source: HTMLElement, rendered: HTMLElement,
 *   progress: HTMLElement, progressLabel: HTMLElement,
 *   control: HTMLElement,
 *   id: string, mode: Mode, pending: boolean, expanded: boolean, holding: boolean,
 *   retryAt: number, retries: number,
 *   folds: Map<string, () => void>,
 *   state: "idle" | "ready" | "unavailable"
 * }} FileView */

/**
 * Keep the feature extensible by admitting file kinds here and leaving source
 * comparisons, rendering and repository reads with their existing owners.
 * @param {Record<string, unknown>} change
 */
export function supportsMarkdownChange(change) {
  if (change.availability !== "ready" && change.availability !== "deferred") {
    return false;
  }
  return (
    [change.old, change.new].some(Boolean) &&
    [change.old, change.new].every((side) => {
      if (side == null) {
        return true;
      }
      const entry = /** @type {{entry_type?: unknown, path?: unknown}} */ (side);
      return (
        entry.entry_type === "file" && typeof entry.path === "string" && MARKDOWN.test(entry.path)
      );
    })
  );
}

/** @param {unknown} value @returns {value is {version: string, status: string, blocks: Block[], source_only: boolean, assets?: KpressAssetManifest}} */
function isProjection(value) {
  if (value === null || typeof value !== "object") {
    return false;
  }
  const answer =
    /** @type {{version?: unknown, status?: unknown, blocks?: unknown, source_only?: unknown}} */ (
      value
    );
  return (
    answer.version === "markdown-diff-v1" &&
    answer.status === "ready" &&
    typeof answer.source_only === "boolean" &&
    Array.isArray(answer.blocks) &&
    answer.blocks.every(
      (block) =>
        block !== null &&
        typeof block === "object" &&
        ["context", "removed", "added"].includes(block.kind) &&
        typeof block.html === "string" &&
        (block.source_only === undefined || typeof block.source_only === "boolean"),
    )
  );
}

/**
 * Which addresses in a rendered block open a file of this comparison: those the server
 * spelled from the comparison's own snapshot route, which a page completes with a side,
 * a path in the Git path codec's wire form, and, for an image, its mode. Every other
 * local address is dropped before the shared sanitizer, which would drop it anyway.
 * @param {string | undefined} route The comparison's `snapshot_route`, when it names one.
 * @returns {(value: string, image: boolean) => boolean}
 */
export function snapshotTargets(route) {
  if (typeof route !== "string" || !route.startsWith("/") || !route.includes("?")) {
    return () => false;
  }
  return (value, image) => {
    if (!value.startsWith(`${route}&`)) {
      return false;
    }
    const query = new URLSearchParams(value.slice(route.length + 1));
    const names = [...query.keys()];
    return (
      new Set(names).size === names.length &&
      names.every((name) => ["side", "path", "mode"].includes(name)) &&
      /^(?:base|head)$/.test(query.get("side") ?? "") &&
      /^g1-[\w-]+(?:\/g1-[\w-]+)*$/.test(query.get("path") ?? "") &&
      (image ? query.get("mode") === "image" : [null, "document"].includes(query.get("mode")))
    );
  };
}

// The files a projection is asked for before the reader opens Changes: the Markdown files
// among the ones the first screen shows. The page draws files in manifest order, a file
// bar and its first rows take about 420 px, and the server hydrates the first 8 files'
// patches with the comparison, so at most 4 Markdown files of the first 8 are asked for.
// Each costs one projection in the server's worker process (12 ms at the median, 31-33
// ms at p90 of the 434 real pairs), sent one at a time after the comparison arrives.
const FIRST_SCREEN_FILES = 8;
const FIRST_SCREEN_MARKDOWN = 4;

/**
 * The IDs of the Markdown files a page asks projections for ahead of Changes.
 * @param {unknown[]} files A comparison manifest's files, in their order.
 * @returns {string[]}
 */
export function firstScreenMarkdown(files) {
  return files
    .slice(0, FIRST_SCREEN_FILES)
    .filter(
      (file) =>
        file !== null &&
        typeof file === "object" &&
        typeof (/** @type {{id?: unknown}} */ (file).id) === "string" &&
        supportsMarkdownChange(/** @type {Record<string, unknown>} */ (file)),
    )
    .slice(0, FIRST_SCREEN_MARKDOWN)
    .map((file) => String(/** @type {{id: string}} */ (file).id));
}

/** @param {string} value */
function outsideLink(value) {
  if (!/^https?:\/\//i.test(value)) {
    return false;
  }
  try {
    return new URL(value).origin !== window.location.origin;
  } catch {
    return false;
  }
}

/**
 * The shared sanitizer discards reserved application URLs. Preserve only
 * explicit snapshot addresses through it and discard other local targets
 * before the detached nodes can load any resource.
 * @param {string} html
 * @param {MetabrowserInertHtmlRuntime} inert
 * @param {HTMLTemplateElement} template
 * @param {Document} scratch
 * @param {(value: string, image: boolean) => boolean} isSnapshotTarget
 */
export function sanitizeBlock(html, inert, template, scratch, isSnapshotTarget) {
  template.innerHTML = html;
  /** @type {Map<string, string>} */
  const targets = new Map();
  for (const element of template.content.querySelectorAll("a[href], img[src]")) {
    const image = element.tagName === "IMG";
    const attribute = image ? "src" : "href";
    const value = element.getAttribute(attribute) ?? "";
    if (isSnapshotTarget(value, image)) {
      const marker = `mb-snapshot-target-${targets.size}`;
      targets.set(marker, value);
      element.setAttribute(attribute, marker);
    } else if (image || (!value.startsWith(`#${inert.ANCHOR_PREFIX}`) && !outsideLink(value))) {
      element.removeAttribute(attribute);
    }
  }
  const prose = inert.kpressProse(
    inert.sanitizeNodes(template.content.childNodes, scratch, null),
    scratch,
  );
  for (const element of prose.querySelectorAll("a[href], img[src]")) {
    const image = element.tagName === "IMG";
    const attribute = image ? "src" : "href";
    const scoped = targets.get(element.getAttribute(attribute) ?? "");
    if (scoped !== undefined) {
      element.setAttribute(attribute, scoped);
    }
  }
  return prose;
}

/**
 * One rendered block's row: its change gutter, its screen-reader label, and, when
 * its source says more than any render shows, a note that names Source.
 * @param {Block} block
 * @param {(html: string) => Node} build
 */
function blockRow(block, build) {
  const row = document.createElement("div");
  row.className = `diff-markdown-block diff-markdown-${block.kind}`;
  if (block.kind !== "context") {
    const label = document.createElement("span");
    label.className = "sr-only";
    label.textContent = block.kind === "added" ? "Added: " : "Removed: ";
    row.append(label);
  }
  if (block.source_only) {
    row.classList.add("diff-markdown-source-only");
    const note = document.createElement("p");
    note.className = "diff-markdown-note";
    note.textContent = "Source shows changes not shown here.";
    row.append(note);
  }
  row.append(build(block.html));
  return row;
}

/**
 * Keep unchanged runs around an edit readable and fold their long interiors. A folded
 * run is built only when it opens, so a long document mounts the blocks a reader sees
 * rather than all of them (review C of #349: at p90, 80% of blocks ended inside a fold).
 * A context block whose source says more never folds. Returns, for each heading id a
 * fold holds, the function that opens it.
 * @param {DocumentFragment} fragment
 * @param {Block[]} blocks
 * @param {(html: string) => Node} build
 * @returns {Map<string, () => void>}
 */
export function appendBlocks(fragment, blocks, build) {
  /** @type {Map<string, () => void>} */
  const folds = new Map();
  let index = 0;
  const foldable = (/** @type {Block} */ block) => block.kind === "context" && !block.source_only;
  while (index < blocks.length) {
    if (!foldable(blocks[index])) {
      fragment.append(blockRow(blocks[index++], build));
      continue;
    }
    const first = index;
    while (index < blocks.length && foldable(blocks[index])) {
      index += 1;
    }
    const run = blocks.slice(first, index);
    if (run.length <= 2 * CONTEXT_BLOCKS + 1) {
      fragment.append(...run.map((block) => blockRow(block, build)));
      continue;
    }
    const hidden = run.slice(CONTEXT_BLOCKS, -CONTEXT_BLOCKS);
    const details = document.createElement("details");
    details.className = "diff-markdown-context";
    const summary = document.createElement("summary");
    summary.className = "disclosure-toggle";
    summary.textContent = `${hidden.length} unchanged blocks`;
    details.append(summary);
    let mounted = false;
    const mount = () => {
      if (!mounted) {
        mounted = true;
        details.append(...hidden.map((block) => blockRow(block, build)));
      }
    };
    details.addEventListener("toggle", () => {
      if (details.open) {
        mount();
      }
    });
    const open = () => {
      mount();
      details.open = true;
    };
    for (const block of hidden) {
      for (const match of block.html.matchAll(/\sid="([^"]+)"/g)) {
        folds.set(match[1], open);
      }
    }
    fragment.append(
      ...run.slice(0, CONTEXT_BLOCKS).map((block) => blockRow(block, build)),
      details,
      ...run.slice(-CONTEXT_BLOCKS).map((block) => blockRow(block, build)),
    );
  }
  return folds;
}

/**
 * @param {KpressAssetManifest} assets
 * @returns {KpressAssetManifest}
 */
function stylesOnly(assets) {
  return {
    schema_version: "kpress-asset-manifest-v2",
    import_map: {},
    assets: assets.assets.filter(
      (asset) =>
        asset.loading === "stylesheet" &&
        /^\/kpress-static\/[\w./%-]+\.css$/.test(asset.public_url ?? ""),
    ),
  };
}

/**
 * One queue for a mounted comparison, one request at a time to match the server's one
 * projection slot. An answer that arrives after its file switched to Source or left
 * the lookahead is kept for when the reader comes back to it.
 * @param {{
 *   load: (fileId: string, signal: AbortSignal) => Promise<unknown>,
 *   controls: NonNullable<MetabrowserPublicSdk["filterControls"]>,
 *   ensureInert: () => Promise<MetabrowserInertHtmlRuntime | undefined>,
 *   loadStyles: (assets: KpressAssetManifest) => Promise<void>,
 *   mutate: (change: () => void) => void,
 *   isSnapshotTarget?: (value: string, image: boolean) => boolean,
 *   now?: () => number,
 *   later?: (callback: () => void, ms: number) => unknown,
 *   cancel?: (handle: unknown) => void
 * }} deps
 */
export function createMarkdownViews(deps) {
  const now = deps.now ?? (() => Date.now());
  const isSnapshotTarget = deps.isSnapshotTarget ?? (() => false);
  const later = deps.later ?? ((callback, ms) => setTimeout(callback, ms));
  const cancel =
    deps.cancel ??
    ((handle) => clearTimeout(/** @type {ReturnType<typeof setTimeout>} */ (handle)));
  /** @type {Map<HTMLElement, FileView>} */
  const files = new Map();
  /** @type {Map<string, FileView>} */
  const controls = new Map();
  /** @type {Set<FileView>} */
  const nearby = new Set();
  /** @type {{file: FileView, controller: AbortController} | null} */
  let active = null;
  /** @type {IntersectionObserver | null} */
  let observer = null;
  /** @type {Promise<MetabrowserInertHtmlRuntime | undefined> | undefined} */
  let inertReady;
  /** @type {Promise<void> | undefined} */
  let stylesReady;
  let disposed = false;
  let observed = false;
  let reported = false;
  /** @type {unknown} */
  let holdTimer;
  /** @type {unknown} */
  let retryTimer;
  /** @type {(() => void) | undefined} */
  let unbind;

  /** @param {FileView} file */
  function draw(file) {
    const rich = file.mode === "rendered" && file.state === "ready";
    file.source.hidden = rich || (file.holding && file.mode === "rendered" && file.expanded);
    file.rendered.hidden = !file.expanded || !rich;
    drawProgress(file);
  }

  // A file that can only show Source has no format to choose. Its chooser, its progress
  // mark and the bar's two-format layout go, so its bar lays out as any other file's, and
  // focus the chooser held returns to the file's disclosure.
  /** @param {FileView} file */
  function drawControl(file) {
    const restoreFocus = file.control.contains(document.activeElement);
    const chooser = file.state !== "unavailable";
    file.control.hidden = !chooser;
    file.progress.hidden = !chooser;
    file.bar.classList.toggle("diff-file-bar-markdown", chooser);
    file.control.innerHTML = deps.controls.groupHtml({
      key: file.source.id,
      label: "Markdown diff format",
      layout: "joined",
      options: [
        { label: "Rendered", value: "rendered" },
        { label: "Source", value: "source" },
      ],
      select: "one",
      value: file.mode,
    });
    for (const chip of file.control.querySelectorAll("button[data-chip-value]")) {
      const button = /** @type {HTMLButtonElement} */ (chip);
      const mode = button.dataset.chipValue;
      button.setAttribute("aria-controls", mode === "rendered" ? file.rendered.id : file.source.id);
      // Never seen: the chooser is hidden whenever this applies. Kept, with select()'s
      // guard, so a file that can only show Source cannot be switched to Rendered.
      button.disabled = mode === "rendered" && file.state === "unavailable";
      if (restoreFocus && chooser && mode === file.mode) {
        button.focus();
      }
    }
    if (restoreFocus && !chooser) {
      file.toggle.focus();
    }
  }

  // The progress mark sits in the file bar beside the chooser, so it never moves the
  // diff, and stays invisible until the loading-state delay passes.
  /** @param {FileView} file */
  function drawProgress(file) {
    const showing = file.pending && file.expanded && file.mode === "rendered";
    file.progress.classList.toggle("mb-delayed-loading", showing);
    file.progressLabel.textContent = showing ? "Rendering Markdown" : "";
  }

  /** @param {FileView} file */
  function interested(file) {
    return (
      nearby.has(file) &&
      file.expanded &&
      file.mode === "rendered" &&
      file.state === "idle" &&
      file.retryAt <= now()
    );
  }

  function release() {
    holdTimer = undefined;
    const held = Array.from(files.values()).filter((file) => file.holding);
    if (held.length > 0) {
      deps.mutate(() => {
        for (const file of held) {
          file.holding = false;
          draw(file);
        }
      });
    }
  }

  function pump() {
    if (disposed || !observed) {
      return;
    }
    if (active !== null) {
      // The request in flight finishes even when its file leaves the lookahead: the
      // server finishes the work regardless (a cancelled waiter does not stop its
      // load), and one slot busy with a load nobody waits for refused the next file.
      // In review C's simulation of 100 files at 10,000 px/s that was 33 of them.
      return;
    }
    const file = Array.from(nearby).find(interested);
    if (file === undefined) {
      scheduleRetry();
      return;
    }
    const controller = new AbortController();
    const { signal } = controller;
    active = { file, controller };
    void load(file, signal);
  }

  /** @param {FileView} file */
  function retryLater(file) {
    file.retryAt = now() + Math.min(RETRY_MS * 2 ** file.retries, RETRY_MAX_MS);
    file.retries += 1;
  }

  // Wake for the earliest refused file still waiting near the viewport.
  function scheduleRetry() {
    const waiting = Array.from(nearby).filter(
      (file) =>
        file.expanded && file.mode === "rendered" && file.state === "idle" && file.retryAt > now(),
    );
    if (retryTimer !== undefined || waiting.length === 0) {
      return;
    }
    const at = Math.min(...waiting.map((file) => file.retryAt));
    retryTimer = later(
      () => {
        retryTimer = undefined;
        pump();
      },
      Math.max(at - now(), 0),
    );
  }

  /** @param {FileView} file @param {AbortSignal} signal */
  async function load(file, signal) {
    let settled = false;
    try {
      file.pending = true;
      deps.mutate(() => drawProgress(file));
      const projection = await deps.load(file.id, signal);
      if (signal.aborted || disposed) {
        return;
      }
      if (!isProjection(projection)) {
        fallBack(file, true);
        return;
      }
      inertReady ??= deps.ensureInert();
      /** @type {MetabrowserInertHtmlRuntime | undefined} */
      let inert;
      try {
        inert = await inertReady;
      } catch {
        inert = undefined;
      }
      if (inert === undefined) {
        // Not kept: choosing Rendered again loads it again.
        inertReady = undefined;
        throw new Error("The untrusted Markdown sanitizer is unavailable.");
      }
      if (projection.assets !== undefined) {
        stylesReady ??= deps.loadStyles(stylesOnly(projection.assets)).catch(() => {});
        await stylesReady;
      }
      if (signal.aborted || disposed) {
        return;
      }
      const content = document.createDocumentFragment();
      const scratch = document.implementation.createHTMLDocument("");
      const template = document.createElement("template");
      const folds = appendBlocks(content, projection.blocks, (html) =>
        sanitizeBlock(html, inert, template, scratch, isSnapshotTarget),
      );
      if (projection.source_only) {
        const note = document.createElement("p");
        note.className = "diff-availability";
        note.textContent = "Source shows additional changes.";
        content.prepend(note);
      }
      settled = true;
      deps.mutate(() => {
        file.rendered.replaceChildren(content);
        file.folds = folds;
        file.state = "ready";
        file.pending = false;
        file.retries = 0;
        draw(file);
      });
    } catch (error) {
      if (!signal.aborted && !disposed) {
        if (/** @type {{status?: unknown}} */ (error)?.status === 429) {
          retryLater(file);
        } else {
          console.warn("metabrowser diff: rendered Markdown failed; showing Source", error);
          fallBack(file, false);
        }
      }
    } finally {
      if (!settled && !disposed) {
        file.pending = false;
        deps.mutate(() => drawProgress(file));
      }
      active = null;
      pump();
    }
  }

  // Source is what a file shows when it is not rendered, and nothing says so: a file
  // that can only show Source loses its chooser, and one whose render failed keeps it, so
  // choosing Rendered asks again.
  /** @param {FileView} file @param {boolean} unsupported */
  function fallBack(file, unsupported) {
    deps.mutate(() => {
      file.state = unsupported ? "unavailable" : "idle";
      file.mode = "source";
      file.holding = false;
      drawControl(file);
      draw(file);
    });
  }

  /** @param {FileView} file @param {Mode} mode */
  function select(file, mode) {
    if (disposed || file.mode === mode || (mode === "rendered" && file.state === "unavailable")) {
      return;
    }
    deps.mutate(() => {
      file.mode = mode;
      file.holding = false;
      if (mode === "rendered") {
        file.retryAt = 0;
      }
      drawControl(file);
      draw(file);
    });
    pump();
  }

  return {
    /**
     * @param {{
     *   section: HTMLElement, bar: HTMLElement, toggle: HTMLElement, source: HTMLElement,
     *   id: string
     * }} input The file's section, its bar, the bar's disclosure button, which the
     *   chooser follows and which takes focus when the chooser goes, and its Source body.
     */
    add({ section, bar, toggle, source, id }) {
      const control = document.createElement("div");
      control.className = "diff-markdown-control";
      const rendered = document.createElement("article");
      rendered.className = "kpress kpress-inert diff-markdown";
      rendered.id = `${source.id}-rendered`;
      const progress = document.createElement("span");
      progress.className = "diff-markdown-progress";
      progress.setAttribute("role", "status");
      const spinner = document.createElement("span");
      spinner.className = "spinner spinner-sm";
      spinner.setAttribute("aria-hidden", "true");
      const progressLabel = document.createElement("span");
      progressLabel.className = "sr-only";
      progress.append(spinner, progressLabel);
      /** @type {FileView} */
      const file = {
        section,
        bar,
        toggle,
        source,
        rendered,
        progress,
        progressLabel,
        id,
        control,
        mode: "rendered",
        expanded: true,
        pending: false,
        holding: true,
        retryAt: 0,
        retries: 0,
        folds: new Map(),
        state: "idle",
      };
      // A fragment link into a folded run opens that fold before the browser looks.
      rendered.addEventListener("click", (event) => {
        const origin = /** @type {{closest?: (selector: string) => Element | null}} */ (
          event.target
        );
        const href = origin?.closest?.("a[href]")?.getAttribute("href") ?? "";
        if (href.startsWith("#")) {
          file.folds.get(href.slice(1))?.();
        }
      });
      toggle.after(control, progress);
      source.before(rendered);
      files.set(section, file);
      controls.set(source.id, file);
      drawControl(file);
      draw(file);
      return {
        /** @param {boolean} expanded */
        setExpanded(expanded) {
          file.expanded = expanded;
          draw(file);
          pump();
        },
      };
    },
    /** @param {HTMLElement} container @param {Element | null} root */
    observe(container, root) {
      observed = true;
      if (files.size === 0) {
        return;
      }
      holdTimer = later(release, LOADING_DELAY_MS);
      unbind = deps.controls.bind(container, {
        onChange(key, value, selectType) {
          const file = controls.get(key);
          if (
            file !== undefined &&
            selectType === "one" &&
            (value === "source" || value === "rendered")
          ) {
            // The shared handler moves focus first. Repaint once that handler
            // returns so its focus recovery cannot find another file's chips.
            queueMicrotask(() => select(file, value));
          }
        },
      });
      observer = new IntersectionObserver(
        (entries) => {
          if (disposed) {
            return;
          }
          /** @type {FileView[]} */
          const away = [];
          for (const entry of entries) {
            const file = files.get(/** @type {HTMLElement} */ (entry.target));
            if (file !== undefined) {
              if (entry.isIntersecting) {
                nearby.add(file);
              } else {
                nearby.delete(file);
                if (file.holding) {
                  away.push(file);
                }
              }
            }
          }
          // Only the files near the first screen wait; the rest draw Source now.
          if (!reported) {
            reported = true;
            for (const file of files.values()) {
              if (file.holding && !nearby.has(file) && !away.includes(file)) {
                away.push(file);
              }
            }
          }
          if (away.length > 0) {
            deps.mutate(() => {
              for (const file of away) {
                file.holding = false;
                draw(file);
              }
            });
          }
          pump();
        },
        { root, rootMargin: `0px 0px ${LOOKAHEAD} 0px` },
      );
      for (const section of files.keys()) {
        observer.observe(section);
      }
    },
    dispose() {
      disposed = true;
      observer?.disconnect();
      active?.controller.abort();
      if (active !== null) {
        active.file.progress.classList.remove("mb-delayed-loading");
      }
      for (const handle of [holdTimer, retryTimer]) {
        if (handle !== undefined) {
          cancel(handle);
        }
      }
      unbind?.();
      unbind = undefined;
      files.clear();
      controls.clear();
      nearby.clear();
    },
  };
}

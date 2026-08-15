// The binary plugin's Bytes view: fetch, decode, paint, append, dispose.
//
// Bytes arrive base64-encoded from /api/plugin/binary/chunk and are decoded
// straight to a Uint8Array. Nothing here runs content through a text decoder;
// see byte_format.js for why.
//
// Rendering strategy, chosen by measurement (Chromium 141, software raster):
//
//   one CSS-wrapped run   1 MiB in 33,333 ms   quadratic in run length
//   pre-broken lines      1 MiB in    633 ms   proportional to line count
//   + content-visibility  1 MiB in     50 ms   16 MiB in 671 ms
//
// So lines are broken in JS, the surface uses `white-space: pre`, and the
// lines are grouped into `content-visibility: auto` blocks. Offscreen blocks
// skip layout and paint while their `contain-intrinsic-size` keeps the
// scrollbar honest, and appending a chunk costs only its own blocks rather
// than relaying out everything already mounted — which is what made repeated
// Load more degrade before.
//
// This keeps real text in the DOM, so browser find-in-page, select-all, and
// print all still cover the whole loaded file — the thing a virtualized
// window would have given up.
//
// One mount owns one container. State lives in this closure keyed per mount,
// so two mounted copies of the view never share an offset or a fingerprint.

import {
  countAccentRuns,
  DEFAULT_ACCENT_RUN_BUDGET,
  DEFAULT_CHARS_PER_LINE,
  formatByteLines,
} from "./byte_format.js";

const LOADING_TEXT = "Loading bytes…";
const EMPTY_TEXT = "This file is empty.";
const UNAVAILABLE_TEXT = "This file is no longer available.";
const UNDECODABLE_TEXT = "This file could not be decompressed.";
const FAILED_TEXT = "Could not load these bytes.";
const LOAD_MORE_LABEL = "Load more";
/**
 * Shown when the view drops the two-tone treatment. The glyphs are unchanged,
 * so this reports the one thing the reader would otherwise have to infer.
 *
 * It says "this file", not "this section": the treatment is decided for
 * everything mounted at once, so it is never on above the note and off below
 * it. Earlier wording blamed the density of non-printable bytes, which is not
 * the trigger — what costs is how often the two classes alternate, and a file
 * of mostly readable strings punctuated by field separators alternates far
 * more than its printable ratio suggests.
 */
const ACCENT_NOTE =
  "Coloring is off for this file: literal text and byte codes alternate too often to mark apart.";

/** Fallback line box when the pane cannot be measured. */
const FALLBACK_LINE_HEIGHT_PX = 18;
/**
 * Lines per render block. The block is the unit of deferred layout, so this
 * trades element count against how much work one scroll-in can trigger.
 */
const LINES_PER_BLOCK = 128;
/** Re-breaking on every resize tick would thrash; settle first. */
const RESIZE_DEBOUNCE_MS = 150;
/**
 * Bytes requested on open. Small so the file appears promptly: formatting is
 * main-thread work, and 4 MiB of it measured ~550 ms against ~145 ms here.
 */
const FIRST_CHUNK_BYTES = 1024 * 1024;
/**
 * Each Load more asks for twice the last chunk, up to this cap, so reaching
 * the ceiling takes a handful of clicks rather than dozens while no single
 * click blocks the main thread for long.
 */
const MAX_CHUNK_BYTES = 8 * 1024 * 1024;

/**
 * @typedef {object} BytesViewState
 * @property {"loading" | "ready" | "empty" | "oversize" | "undecodable" | "unavailable" | "failed"} status
 * @property {number} [bytesLoaded]
 * @property {number} [logicalSize]
 * @property {boolean} [hasMore]
 * @property {boolean} [accentDropped]
 * @property {number} [maxPreviewBytes]
 */

/**
 * Decode base64 to raw bytes without going through a text decoder.
 *
 * @param {string} value
 * @returns {Uint8Array}
 */
export function decodeBase64(value) {
  const binary = atob(value || "");
  const bytes = new Uint8Array(binary.length);
  for (let index = 0; index < binary.length; index += 1) {
    bytes[index] = binary.charCodeAt(index) & 0xff;
  }
  return bytes;
}

/**
 * @param {BytesViewState} state
 * @param {MetabrowserPublicSdk} mb
 * @returns {string}
 */
function readoutText(state, mb) {
  return `${mb.formatSize(state.bytesLoaded || 0)} / ${mb.formatSize(state.logicalSize || 0)}`;
}

/**
 * @param {string} message
 * @param {boolean} isFailure
 * @returns {string}
 */
function emptyStateHtml(message, isFailure) {
  const role = isFailure ? "alert" : "status";
  return `<div class="preview-empty" role="${role}">${message}</div>`;
}

/**
 * Build the full surface for one state. Pure, so every visible state is
 * reachable in a test without a network call.
 *
 * @param {BytesViewState} state
 * @param {MetabrowserPublicSdk} mb
 * @returns {string}
 */
export function renderChunkState(state, mb) {
  switch (state.status) {
    case "loading":
      return `<div class="preview-empty mb-delayed-loading" role="status">${LOADING_TEXT}</div>`;
    case "empty":
      return emptyStateHtml(EMPTY_TEXT, false);
    case "oversize":
      return emptyStateHtml(
        `Preview unavailable. Binary previews are limited to ${mb.formatSize(
          state.maxPreviewBytes || 0,
        )}.`,
        false,
      );
    case "undecodable":
      return emptyStateHtml(UNDECODABLE_TEXT, true);
    case "unavailable":
      return emptyStateHtml(UNAVAILABLE_TEXT, true);
    case "failed":
      return emptyStateHtml(FAILED_TEXT, true);
    default:
      break;
  }
  const note = state.accentDropped ? ACCENT_NOTE : "";
  const noteHidden = state.accentDropped ? "" : " hidden";
  const moreHidden = state.hasMore ? "" : " hidden";
  // Without the two-tone elements the surface still has to say which of the
  // two colors the unwrapped text is. Content that spends the budget is
  // overwhelmingly byte codes, so it defaults to the code color.
  const plain = state.accentDropped ? " binary-bytes-plain" : "";
  return (
    '<div class="binary-bytes">' +
    '<div class="binary-bytes-controls">' +
    `<span class="binary-bytes-readout">${readoutText(state, mb)}</span>` +
    `<button class="btn binary-bytes-more" type="button" data-position="top"${moreHidden}>${LOAD_MORE_LABEL}</button>` +
    "</div>" +
    `<div class="binary-bytes-note" role="status"${noteHidden}>${note}</div>` +
    // `no-highlight` is the shell's opt-out in highlightCode(). Without it
    // highlight.js runs over this block after the chunk mounts, rewrites the
    // byte runs into hljs token spans, and both destroys the accent markup and
    // claims these bytes are source code.
    `<pre class="code-block"><code class="binary-bytes-content no-highlight${plain}"></code></pre>` +
    // The trailing control. A reader who has scrolled to the end of the loaded
    // bytes is exactly the reader who wants the next chunk, and the header
    // control has long since scrolled away. See docs/design-system.md,
    // "Continuing partial content".
    '<div class="binary-bytes-footer">' +
    `<button class="btn binary-bytes-more" type="button" data-position="bottom"${moreHidden}>${LOAD_MORE_LABEL}</button>` +
    "</div>" +
    "</div>"
  );
}

/**
 * Columns and line box available inside the mounted surface.
 *
 * Falls back to fixed values wherever the environment cannot measure, so the
 * renderer stays usable under a container double.
 *
 * @param {Element | null} surface
 * @returns {{charsPerLine: number, lineHeightPx: number}}
 */
export function measureSurface(surface) {
  const fallback = {
    charsPerLine: DEFAULT_CHARS_PER_LINE,
    lineHeightPx: FALLBACK_LINE_HEIGHT_PX,
  };
  if (!surface || typeof document === "undefined" || typeof getComputedStyle !== "function") {
    return fallback;
  }
  const width = /** @type {HTMLElement} */ (surface).clientWidth;
  if (!width) {
    return fallback;
  }
  const probe = document.createElement("span");
  probe.setAttribute("aria-hidden", "true");
  probe.style.position = "absolute";
  probe.style.visibility = "hidden";
  probe.style.whiteSpace = "pre";
  probe.textContent = "0".repeat(100);
  surface.appendChild(probe);
  const probeWidth = probe.getBoundingClientRect().width;
  const computed = getComputedStyle(probe);
  const lineHeight = Number.parseFloat(computed.lineHeight);
  const fontSize = Number.parseFloat(computed.fontSize);
  probe.remove();
  const charWidth = probeWidth / 100;
  if (!charWidth || !Number.isFinite(charWidth)) {
    return fallback;
  }
  return {
    charsPerLine: Math.max(16, Math.floor(width / charWidth)),
    lineHeightPx:
      Number.isFinite(lineHeight) && lineHeight > 0
        ? lineHeight
        : (Number.isFinite(fontSize) ? fontSize : 12) * 1.5,
  };
}

/**
 * Mount the Bytes view into ``container``.
 *
 * @param {HTMLElement} container
 * @param {{path?: string}} ctx
 * @param {MetabrowserPublicSdk} mb
 * @param {{signal?: AbortSignal}} [options]
 * @returns {Promise<{dispose: () => void}>}
 */
export async function mountBytesView(container, ctx, mb, options) {
  /** @type {BytesViewState} */
  const state = {
    status: "loading",
    bytesLoaded: 0,
    logicalSize: 0,
    hasMore: false,
    accentDropped: false,
    maxPreviewBytes: 0,
  };
  let disposed = false;
  /** @type {string | null} */
  let fingerprint = null;
  let nextOffset = 0;
  let nextChunkBytes = FIRST_CHUNK_BYTES;
  /** @type {AbortController | null} */
  let inflight = null;
  /** Retained so a resize can re-break lines without refetching. */
  /** @type {Uint8Array[]} */
  let loaded = [];
  /**
   * Class changes across everything loaded so far, and whether the two-tone
   * treatment is still affordable. Both are view-wide: the DOM accumulates
   * across Load more, and a treatment that applied to some chunks and not
   * others would read as a rendering fault rather than a budget.
   */
  let accentRuns = 0;
  let accentEnabled = true;
  let metrics = { charsPerLine: DEFAULT_CHARS_PER_LINE, lineHeightPx: FALLBACK_LINE_HEIGHT_PX };
  /** @type {ResizeObserver | null} */
  let resizeObserver = null;
  /** @type {ReturnType<typeof setTimeout> | null} */
  let resizeTimer = null;

  const dispose = () => {
    if (disposed) {
      return;
    }
    disposed = true;
    options?.signal?.removeEventListener("abort", dispose);
    if (resizeTimer !== null) {
      clearTimeout(resizeTimer);
      resizeTimer = null;
    }
    resizeObserver?.disconnect();
    resizeObserver = null;
    inflight?.abort();
    inflight = null;
    loaded = [];
  };

  const contentEl = () => container.querySelector(".binary-bytes-content");

  /**
   * One loaded chunk as a run of `content-visibility: auto` blocks.
   *
   * The browser skips layout and paint for a block while it is offscreen, and
   * pays for it when it scrolls in — so the block, not the chunk, is the unit
   * of deferred work. A whole 4 MiB chunk in one block measured 1.8 s to
   * scroll into; at this granularity the same jump costs tens of
   * milliseconds. Each block's `contain-intrinsic-size` keeps the scrollbar
   * proportional while its layout is still skipped.
   *
   * @param {Uint8Array} bytes
   * @returns {string}
   */
  const blocksHtml = (bytes) => {
    const run = formatByteLines(bytes, mb.escapeHtml, {
      charsPerLine: metrics.charsPerLine,
      accent: accentEnabled,
    });
    /** @type {string[]} */
    const blocks = [];
    for (let index = 0; index < run.lines.length; index += LINES_PER_BLOCK) {
      const slice = run.lines.slice(index, index + LINES_PER_BLOCK);
      const height = Math.max(1, Math.round(slice.length * metrics.lineHeightPx));
      blocks.push(
        `<div class="binary-bytes-block" style="contain-intrinsic-size: auto ${height}px">` +
          slice.join("\n") +
          "</div>",
      );
    }
    return blocks.join("");
  };

  /** Every Load more control in the mounted view — currently head and foot. */
  const moreButtons = () =>
    /** @type {HTMLElement[]} */ (
      Array.from(container.querySelectorAll?.(".binary-bytes-more") ?? [])
    );

  /** @param {BytesViewState} next */
  const paint = (next) => {
    container.innerHTML = renderChunkState(next, mb);
    for (const more of moreButtons()) {
      more.hidden = !next.hasMore;
      more.addEventListener("click", onLoadMore);
    }
    metrics = measureSurface(contentEl());
  };

  const syncControls = () => {
    const readout = container.querySelector(".binary-bytes-readout");
    if (readout) {
      readout.textContent = readoutText(state, mb);
    }
    for (const more of moreButtons()) {
      more.hidden = !state.hasMore;
    }
    const note = /** @type {HTMLElement | null} */ (container.querySelector(".binary-bytes-note"));
    if (note) {
      note.textContent = state.accentDropped ? ACCENT_NOTE : "";
      note.hidden = !state.accentDropped;
    }
    contentEl()?.classList.toggle("binary-bytes-plain", state.accentDropped === true);
  };

  /**
   * Re-render every loaded chunk into the mounted surface.
   *
   * Used both when the pane width changes and when the accent is withdrawn,
   * because in each case the markup already mounted was built under an
   * assumption that no longer holds.
   */
  const renderAllLoaded = () => {
    const content = contentEl();
    if (!content) {
      return;
    }
    content.innerHTML = loaded.map(blocksHtml).join("");
  };

  /** @param {Uint8Array} bytes */
  const appendBlock = (bytes) => {
    const content = contentEl();
    if (content) {
      content.insertAdjacentHTML("beforeend", blocksHtml(bytes));
    }
  };

  /** Re-break every loaded chunk after the pane width changes. */
  const rebreak = () => {
    const content = contentEl();
    if (!content || loaded.length === 0) {
      return;
    }
    metrics = measureSurface(content);
    // The accent decision is not re-derived here: it depends on the bytes,
    // which a resize does not change.
    renderAllLoaded();
    syncControls();
  };

  const watchResize = () => {
    if (typeof ResizeObserver !== "function" || resizeObserver) {
      return;
    }
    let lastWidth = 0;
    resizeObserver = new ResizeObserver((entries) => {
      const width = entries[0]?.contentRect?.width ?? 0;
      if (disposed || !width || Math.abs(width - lastWidth) < 1) {
        return;
      }
      lastWidth = width;
      if (resizeTimer !== null) {
        clearTimeout(resizeTimer);
      }
      resizeTimer = setTimeout(() => {
        resizeTimer = null;
        if (!disposed) {
          rebreak();
        }
      }, RESIZE_DEBOUNCE_MS);
    });
    resizeObserver.observe(container);
  };

  /**
   * @param {Record<string, unknown>} data
   * @param {boolean} repaint
   */
  const applyChunk = (data, repaint) => {
    const hash = typeof data.mtime_hash === "string" ? data.mtime_hash : null;
    if (!repaint && fingerprint !== null && hash !== fingerprint) {
      // The file changed underneath us. Combining bytes from two versions
      // would silently produce a window that never existed on disk, so drop
      // what is mounted and start over.
      fingerprint = null;
      nextOffset = 0;
      nextChunkBytes = FIRST_CHUNK_BYTES;
      loaded = [];
      accentRuns = 0;
      accentEnabled = true;
      state.accentDropped = false;
      state.status = "loading";
      paint(state);
      void loadChunk(0, true);
      return;
    }
    fingerprint = hash;
    state.logicalSize = Number(data.logical_size) || 0;
    state.bytesLoaded = Number(data.next_offset) || 0;
    state.hasMore = data.has_more === true;
    nextOffset = state.bytesLoaded;

    if (state.logicalSize === 0) {
      state.status = "empty";
      paint(state);
      return;
    }

    const bytes = decodeBase64(typeof data.content_base64 === "string" ? data.content_base64 : "");
    state.status = "ready";
    if (repaint) {
      loaded = [];
      accentRuns = 0;
      accentEnabled = true;
      state.accentDropped = false;
      paint(state);
    }
    loaded.push(bytes);

    // Decide the treatment before emitting anything, against the whole view
    // rather than this chunk. Withdrawing it means re-rendering what is
    // already mounted from the retained bytes — the cost of a consistent
    // surface, paid at most once per view.
    accentRuns += countAccentRuns(bytes);
    const withdrawAccent = accentEnabled && accentRuns > DEFAULT_ACCENT_RUN_BUDGET;
    if (withdrawAccent) {
      accentEnabled = false;
      state.accentDropped = true;
      renderAllLoaded();
    } else {
      appendBlock(bytes);
    }
    syncControls();
    watchResize();
  };

  /** @param {unknown} error */
  const applyError = (error) => {
    const status =
      error && typeof error === "object" && typeof (/** @type {any} */ (error).status) === "number"
        ? /** @type {any} */ (error).status
        : 0;
    if (status === 404) {
      state.status = "unavailable";
    } else if (status === 422) {
      state.status = "undecodable";
    } else if (status === 413 || status === 416) {
      state.status = "oversize";
      const payload = /** @type {any} */ (error).payload;
      state.maxPreviewBytes = Number(payload?.max_preview_bytes) || 0;
    } else {
      state.status = "failed";
    }
    paint(state);
  };

  /**
   * @param {number} offset
   * @param {boolean} repaint
   * @returns {Promise<void>}
   */
  async function loadChunk(offset, repaint, limit = FIRST_CHUNK_BYTES) {
    if (disposed) {
      return;
    }
    const controller = new AbortController();
    inflight = controller;
    try {
      const data = await mb.fetchPluginData(
        "binary",
        "chunk",
        { path: ctx.path || "", offset: offset, limit: limit },
        { signal: controller.signal },
      );
      if (disposed) {
        return;
      }
      applyChunk(/** @type {Record<string, unknown>} */ (data), repaint);
    } catch (error) {
      if (disposed) {
        return;
      }
      applyError(error);
    } finally {
      if (inflight === controller) {
        inflight = null;
      }
    }
  }

  function onLoadMore() {
    // `nextOffset` only advances once a response lands, so without this guard
    // a second click while the first request is still open asks for the same
    // window again and appends it a second time: the same bytes appear twice
    // in the DOM, and find-in-page and select-all see the duplicate. Three
    // fast clicks measured three requests at one offset and three appends.
    // `inflight` is the request in progress, and it also covers the opening
    // load and the restart-on-change, neither of which should race a click.
    if (disposed || inflight || !state.hasMore) {
      return;
    }
    const limit = nextChunkBytes;
    nextChunkBytes = Math.min(nextChunkBytes * 2, MAX_CHUNK_BYTES);
    void loadChunk(nextOffset, false, limit);
  }

  if (options?.signal?.aborted) {
    dispose();
  } else {
    options?.signal?.addEventListener("abort", dispose, { once: true });
  }

  paint(state);
  await loadChunk(0, true);
  return { dispose };
}

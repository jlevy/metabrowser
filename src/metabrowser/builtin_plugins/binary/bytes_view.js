// The binary plugin's Bytes view: fetch, decode, paint, append, dispose.
//
// Bytes arrive base64-encoded from /api/plugin/binary/chunk and are decoded
// straight to a Uint8Array. Nothing here runs content through a text decoder;
// see byte_format.js for why.
//
// One mount owns one container. State lives in this closure keyed per mount,
// so two mounted copies of the view never share an offset or a fingerprint.

import { DEFAULT_ACCENT_RUN_BUDGET, formatByteRuns } from "./byte_format.js";

const LOADING_TEXT = "Loading bytes…";
const EMPTY_TEXT = "This file is empty.";
const UNAVAILABLE_TEXT = "This file is no longer available.";
const UNDECODABLE_TEXT = "This file could not be decompressed.";
const FAILED_TEXT = "Could not load these bytes.";
const LOAD_MORE_LABEL = "Load more";
/**
 * Shown when a chunk spends its accent budget. The glyphs are unchanged, so
 * this reports the one thing the reader would otherwise have to infer.
 */
const ACCENT_NOTE =
  "Byte highlighting is off for this section because nearly every byte is non-printable.";

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
  return (
    '<div class="binary-bytes">' +
    '<div class="binary-bytes-controls">' +
    `<span class="binary-bytes-readout">${readoutText(state, mb)}</span>` +
    `<button class="btn binary-bytes-more" type="button"${moreHidden}>${LOAD_MORE_LABEL}</button>` +
    "</div>" +
    `<div class="binary-bytes-note" role="status"${noteHidden}>${note}</div>` +
    // `no-highlight` is the shell's opt-out in highlightCode(). Without it
    // highlight.js runs over this block after the chunk mounts, rewrites the
    // byte runs into hljs token spans, and both destroys the accent markup and
    // claims these bytes are source code.
    '<pre class="code-block"><code class="binary-bytes-content no-highlight"></code></pre>' +
    "</div>"
  );
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
  /** @type {AbortController | null} */
  let inflight = null;

  const dispose = () => {
    if (disposed) {
      return;
    }
    disposed = true;
    options?.signal?.removeEventListener("abort", dispose);
    inflight?.abort();
    inflight = null;
  };

  /** @param {BytesViewState} next */
  const paint = (next) => {
    container.innerHTML = renderChunkState(next, mb);
    const more = /** @type {HTMLElement | null} */ (container.querySelector(".binary-bytes-more"));
    if (more) {
      more.hidden = !next.hasMore;
      more.addEventListener("click", onLoadMore);
    }
  };

  const syncControls = () => {
    const readout = container.querySelector(".binary-bytes-readout");
    if (readout) {
      readout.textContent = readoutText(state, mb);
    }
    const more = /** @type {HTMLElement | null} */ (container.querySelector(".binary-bytes-more"));
    if (more) {
      more.hidden = !state.hasMore;
    }
    const note = /** @type {HTMLElement | null} */ (container.querySelector(".binary-bytes-note"));
    if (note) {
      note.textContent = state.accentDropped ? ACCENT_NOTE : "";
      note.hidden = !state.accentDropped;
    }
  };

  /** @param {string} html */
  const appendBytes = (html) => {
    const content = container.querySelector(".binary-bytes-content");
    if (content) {
      content.insertAdjacentHTML("beforeend", html);
    }
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
    const run = formatByteRuns(bytes, mb.escapeHtml, DEFAULT_ACCENT_RUN_BUDGET);
    state.accentDropped = state.accentDropped === true || run.accentDropped;
    state.status = "ready";
    if (repaint) {
      paint(state);
    } else {
      syncControls();
    }
    appendBytes(run.html);
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
  async function loadChunk(offset, repaint) {
    if (disposed) {
      return;
    }
    const controller = new AbortController();
    inflight = controller;
    try {
      const data = await mb.fetchPluginData(
        "binary",
        "chunk",
        { path: ctx.path || "", offset: offset },
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
    if (disposed || !state.hasMore) {
      return;
    }
    void loadChunk(nextOffset, false);
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

// A Markdown document whose render the server refused: its source, under one line saying why.
//
// Under the untrusted profile the server renders a document in its Markdown child, under
// a deadline (src/metabrowser/diff/markdown_projection_worker.py), and answers one that
// ran past it, whose renderer stopped, whose renderer could not start, or that arrived
// while the renderer had as many other documents as it takes, with a
// `kpress_render_refused` envelope and a code. The Document view then shows the file's
// source in its place, as the Source tab draws it, under a warning notice that says why,
// rather than a render error: the document is readable, only not rendered. That is the
// Document tab of a file, and every page that embeds a document through the Markdown
// view, as the folder Overview's README does.
//
// The source is the file's first window: the one the page already holds for a file it
// shows, or the one `/api/file` answers for a document a page embeds. A window that is not
// the whole file is said in the notice, with where the rest is (the file's Source tab, or
// the file itself), rather than offering a Load more that belongs to another view.

import { renderMarkdownSource } from "./source.js";

/** @typedef {{code: string, deadlineMs: number | null}} RenderRefusal */

const REFUSED = "kpress_render_refused";

/**
 * The refusal an error from `fetchKpressRender` carries, or null for any other failure.
 *
 * @param {unknown} error
 * @returns {RenderRefusal | null}
 */
export function renderRefusal(error) {
  const payload =
    error && typeof error === "object"
      ? /** @type {{payload?: unknown}} */ (error).payload
      : undefined;
  if (!payload || typeof payload !== "object") {
    return null;
  }
  const body = /** @type {Record<string, unknown>} */ (payload);
  if (body.type !== REFUSED || typeof body.code !== "string") {
    return null;
  }
  const deadline = body.deadline_ms;
  return Object.freeze({
    code: body.code,
    deadlineMs: typeof deadline === "number" && Number.isFinite(deadline) ? deadline : null,
  });
}

/**
 * The sentence the notice says for *refusal*. The deadline and the renderer's state are
 * the refusal's (`deadlineMs`, `code`), for a test or an agent; the notice says what the
 * reader sees (docs/design-system-messages.md).
 *
 * @param {RenderRefusal} refusal
 */
export function refusalNote(refusal) {
  switch (refusal.code) {
    case "render_deadline":
      return "This document took too long to render, so its source is shown.";
    case "renderer_unavailable":
    case "renderer_busy":
      return "This document could not be rendered, so its source is shown. Reload to try again.";
    default:
      return "This document could not be rendered, so its source is shown.";
  }
}

/**
 * The text envelope the source is drawn from: *raw* when it is this file's own, which the
 * page already holds, and otherwise the first window `/api/file` answers.
 *
 * @param {string} path
 * @param {unknown} raw
 * @param {AbortSignal | undefined} signal
 * @returns {Promise<{envelope: Record<string, any>, own: boolean}>}
 */
export async function sourceWindow(path, raw, signal) {
  const held =
    raw && typeof raw === "object"
      ? /** @type {Record<string, any>} */ (raw)
      : /** @type {Record<string, any>} */ ({});
  if (held.type === "text" && typeof held.content === "string" && held.path === path) {
    return { envelope: held, own: true };
  }
  const url = new URL("/api/file", globalThis.location.origin);
  url.searchParams.set("path", path);
  const response = await fetch(url.toString(), { signal });
  if (!response.ok) {
    throw new Error(`Could not read the source of ${path}`, { cause: response.status });
  }
  const envelope = /** @type {Record<string, any>} */ (await response.json());
  if (envelope?.type !== "text" || typeof envelope.content !== "string") {
    throw new Error(`Could not read the source of ${path}: not a text file`);
  }
  return { envelope, own: false };
}

/**
 * What the notice adds when the window is not the whole file, or "".
 *
 * @param {Record<string, any>} envelope
 * @param {boolean} own
 * @param {MetabrowserPublicSdk} mb
 */
export function partialNote(envelope, own, mb) {
  // The figures the Source tab's partial notice reads (`textPreviewProgress`).
  const total = Number(envelope.size_uncompressed || envelope.logical_size || envelope.size || 0);
  const loaded = Number(envelope.bytes_read || envelope.content_bytes || 0);
  const partial =
    envelope.content_truncated === true ||
    (typeof envelope.bytes_read === "number" && total > 0 && loaded < total);
  if (!partial) {
    return "";
  }
  const shown = `Showing the first ${mb.formatSize(loaded)} of ${mb.formatSize(total)}`;
  return own ? ` ${shown}; the Source tab shows the rest.` : ` ${shown}.`;
}

/**
 * Show *ctx*'s source in *container* in place of the render the server refused.
 *
 * @param {HTMLElement} container
 * @param {{path?: string, raw?: unknown}} ctx
 * @param {RenderRefusal} refusal
 * @param {MetabrowserPublicSdk} mb
 * @param {{signal?: AbortSignal}} [options]
 * @returns {Promise<boolean>} Whether the source was placed; false once aborted.
 */
export async function mountRefusedSource(container, ctx, refusal, mb, options = {}) {
  const path = typeof ctx.path === "string" ? ctx.path : "";
  const { envelope, own } = await sourceWindow(path, ctx.raw, options.signal);
  if (options.signal?.aborted) {
    return false;
  }
  const note = refusalNote(refusal) + partialNote(envelope, own, mb);
  const link = own
    ? ""
    : ` <a class="metabrowser-render-refused-open" href="${mb.escapeHtml(mb.navigation.href({ path }))}">Open the file</a>`;
  container.classList.remove("metabrowser-kpress-host", "metabrowser-markdown-document");
  container.innerHTML =
    `<div class="notice metabrowser-render-refused" data-severity="warning" role="status" data-refusal="${mb.escapeHtml(refusal.code)}">` +
    `${mb.escapeHtml(note)}${link}</div><div class="metabrowser-render-refused-source"></div>`;
  const host = /** @type {HTMLElement | null} */ (
    container.querySelector(".metabrowser-render-refused-source")
  );
  if (host) {
    // The window alone, with nothing that says it continues: the notice says what it
    // leaves out, so no Load more here.
    const shown = { path: envelope.path ?? path, ext: envelope.ext, content: envelope.content };
    renderMarkdownSource(host, { raw: shown }, mb);
  }
  return true;
}

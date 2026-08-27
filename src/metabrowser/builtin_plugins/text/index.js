// Text built-in plugin — generic source-code / plain-text rendering.
//
// The text kind is the catch-all classifier output for files no other
// rule claims (the manifest has no [[kind]] match — the assignment
// happens in metabrowser.file_kinds.classify_file_kind's text fallback).
//
// Owns one view:
//   ("text", "source") — <pre><code class="language-X"> using the
//                        host's path-aware syntax registry
//                        hint highlight.js picks up after render.
(() => {
  const mb = window.metabrowser;
  if (!mb) {
    console.error("metabrowser text plugin: window.metabrowser missing — SDK not loaded");
    return;
  }

  /**
   * @param {HTMLElement} container
   * @param {{raw?: unknown}} ctx
   */
  function renderSource(container, ctx) {
    const data = /** @type {Record<string, unknown> & {content?: string, ext?: string}} */ (
      ctx.raw || {}
    );
    mb.perf.measure("renderText:source", () => {
      mb.renderSourceView(container, data);
    });
  }

  mb.registerView("text", "source", { render: renderSource });
})();

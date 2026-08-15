// Text built-in plugin — generic source-code / plain-text rendering.
//
// The text kind is the catch-all classifier output for files no other
// rule claims (the manifest has no [[kind]] match — the assignment
// happens in metabrowser.file_kinds.classify_file_kind's text fallback).
//
// Owns one view:
//   ("text", "source") — <pre><code class="language-X"> using
//                        mb.langForExtension(ctx.raw.ext) for the language
//                        hint highlight.js picks up after render.
(() => {
  const mb = window.metabrowser;
  if (!mb) {
    console.error("metabrowser text plugin: window.metabrowser missing — SDK not loaded");
    return;
  }

  /**
   * @param {Record<string, unknown> & {content?: string, ext?: string}} data
   * @returns {string}
   */
  function renderSourceHtml(data) {
    // Partial content is bracketed by the control that continues it: banner
    // above, the same control below. A reader who reaches the end of what
    // loaded should not have to scroll back up to ask for the rest.
    // See docs/design-system.md, "Continuing partial content".
    const truncationWarning = mb.renderTextTruncationWarning(data);
    const loadMoreFooter = mb.renderTextLoadMoreFooter(data);
    const code = mb.isLargeTextPreview(data)
      ? '<pre class="code-block"><code class="plaintext no-highlight">' +
        mb.escapeHtml(data.content || "") +
        "</code></pre>"
      : (() => {
          const lang = mb.langForExtension(data.ext || "");
          const langCls = lang ? `language-${lang}` : "plaintext";
          return (
            '<pre class="code-block"><code class="' +
            langCls +
            '">' +
            mb.escapeHtml(data.content || "") +
            "</code></pre>"
          );
        })();
    return truncationWarning + mb.wrapWithCopy(code) + loadMoreFooter;
  }

  /**
   * @param {HTMLElement} container
   * @param {{raw?: unknown}} ctx
   */
  function renderSource(container, ctx) {
    const data = /** @type {Record<string, unknown> & {content?: string, ext?: string}} */ (
      ctx.raw || {}
    );
    container.classList.add("metabrowser-source-host");
    mb.perf.measure("renderText:source", () => {
      container.innerHTML = renderSourceHtml(data);
    });
  }

  if (!mb.builtins) {
    mb.builtins = {};
  }
  mb.builtins.text = { renderSource: renderSource };

  mb.registerView("text", "source", { render: renderSource });
})();

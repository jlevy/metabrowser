// Markdown built-in plugin — renders `.md` files in the metabrowser shell.
//
// Owns two views:
//   ("markdown", "rendered") — body via KPress, with a visible error state
//   ("markdown", "source")   — raw source view; `.md` files split frontmatter
//                              vs body for syntax highlighting; other text uses
//                              a single language-marked code block
//
// Helpers used from the SDK (window.metabrowser):
//   mb.escapeHtml                — text → safe HTML
//   mb.isLargeTextPreview        — bypass syntax-highlight above 512 KiB
//   mb.wrapWithCopy              — copy-button frame around a code block
//   mb.fetchKpressRender         — KPress fragment fetch + asset loading
//   mb.perf.measure              — perf-overlay-friendly timing wrapper
(() => {
  const mb = window.metabrowser;
  if (!mb) {
    console.error("metabrowser markdown plugin: window.metabrowser missing — SDK not loaded");
    return;
  }

  function renderSourceHtml(data) {
    const truncationWarning = mb.renderTextTruncationWarning(data);
    if (mb.isLargeTextPreview(data)) {
      return (
        truncationWarning +
        mb.wrapWithCopy(
          '<pre class="code-block"><code class="plaintext no-highlight">' +
            mb.escapeHtml(data.content || "") +
            "</code></pre>",
        )
      );
    }
    // .md source: split frontmatter so each side highlights with the
    // appropriate language (yaml + markdown), matching the previous
    // shell behaviour.
    const content = data.content || "";
    if (content.startsWith("---\n") || content.startsWith("---\r\n")) {
      let fmEnd = content.indexOf("\n---\n", 4);
      if (fmEnd === -1) {
        fmEnd = content.indexOf("\n---\r\n", 4);
      }
      if (fmEnd >= 0) {
        const fmText = content.slice(4, fmEnd);
        const bodyText = content.slice(fmEnd + 5);
        return (
          truncationWarning +
          mb.wrapWithCopy(
            '<pre class="code-block"><code class="language-yaml">' +
              mb.escapeHtml("---\n" + fmText + "\n---") +
              "</code></pre>" +
              '<pre class="code-block"><code class="language-markdown">' +
              mb.escapeHtml(bodyText) +
              "</code></pre>",
          )
        );
      }
    }
    return (
      truncationWarning +
      mb.wrapWithCopy(
        '<pre class="code-block"><code class="language-markdown">' +
          mb.escapeHtml(content) +
          "</code></pre>",
      )
    );
  }

  function renderKpressDiagnosticsHtml(diagnostics) {
    if (!diagnostics?.length) {
      return "";
    }
    const rows = diagnostics
      .map((d) => {
        if (typeof d === "string") {
          return "<dt>message</dt><dd>" + mb.escapeHtml(d) + "</dd>";
        }
        const entries = [];
        if (d.type) {
          entries.push("<dt>type</dt><dd>" + mb.escapeHtml(String(d.type)) + "</dd>");
        }
        if (d.message) {
          entries.push("<dt>message</dt><dd>" + mb.escapeHtml(String(d.message)) + "</dd>");
        }
        if (d.severity) {
          entries.push("<dt>severity</dt><dd>" + mb.escapeHtml(String(d.severity)) + "</dd>");
        }
        return entries.join("");
      })
      .join("");
    return (
      '<details class="kpress-frontmatter metabrowser-kpress-diagnostics kpress-no-print">' +
      "<summary>Diagnostics</summary>" +
      "<dl>" +
      rows +
      "</dl></details>"
    );
  }

  // Inject diagnostics beside KPress's metadata details when present.
  function injectDiagnostics(container, diagnostics) {
    const html = renderKpressDiagnosticsHtml(diagnostics);
    if (!html) {
      return;
    }
    const tmp = document.createElement("div");
    tmp.innerHTML = html;
    const node = tmp.firstElementChild;
    const article = container.querySelector("article.kpress");
    if (article) {
      const metadata = article.querySelector(
        ".kpress-frontmatter:not(.metabrowser-kpress-diagnostics)",
      );
      if (metadata) {
        metadata.after(node);
      } else {
        article.prepend(node);
      }
    } else {
      container.prepend(node);
    }
  }

  function renderKpressError(err) {
    const payload = err?.payload ? err.payload : {};
    const diagnostics = payload.diagnostics || [];
    const message =
      (payload.error || "KPress render failed") +
      (payload.detail ? ": " + payload.detail : err?.message ? ": " + err.message : "");
    return (
      '<div class="metabrowser-kpress-render-error" role="alert">' +
      "<strong>KPress render failed.</strong>" +
      '<pre class="metabrowser-kpress-error-detail">' +
      mb.escapeHtml(message) +
      "</pre>" +
      renderKpressDiagnosticsHtml(diagnostics) +
      "</div>"
    );
  }

  // Plugins for other Markdown kinds reuse these renderers through the builtins
  // namespace. Built-ins discover before external plugin scripts load.
  let activeTocDispose = null;

  function disposeToc() {
    if (typeof activeTocDispose === "function") {
      try {
        activeTocDispose();
      } catch (_error) {
        // Disposal is best-effort because the document is already being replaced.
      }
      activeTocDispose = null;
    }
  }

  async function renderRendered(container, ctx) {
    disposeToc();
    container.classList.add("metabrowser-kpress-host");
    container.innerHTML = '<div class="loading"><div class="spinner"></div>Loading document…</div>';
    try {
      const rendered = await mb.fetchKpressRender(ctx, "rendered", { profile: "document" });
      container.innerHTML = rendered.html;
      injectDiagnostics(container, rendered.diagnostics || []);
      activeTocDispose = mb.kpressInitToc(container);
    } catch (err) {
      container.innerHTML = renderKpressError(err);
    }
  }

  function renderSource(container, ctx) {
    container.classList.add("metabrowser-source-host");
    mb.perf.measure("renderMarkdown:source", () => {
      container.innerHTML = renderSourceHtml(ctx.raw);
    });
  }

  if (!mb.builtins) {
    mb.builtins = {};
  }
  mb.builtins.markdown = {
    renderRendered: renderRendered,
    renderSource: renderSource,
  };

  mb.registerView("markdown", "rendered", { render: renderRendered, dispose: disposeToc });
  mb.registerView("markdown", "source", { render: renderSource });
})();

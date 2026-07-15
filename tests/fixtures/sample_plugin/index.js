// Sample plugin — exercises the JS plugin contract end-to-end.
//
// This plugin handles markdown files with a `sample:` frontmatter key.
// It contributes two views: a "card" rendering using the Mustache
// {{...}} helper, and a raw source view for completeness.

(() => {
  const mb = window.metabrowser;
  if (!mb) {
    console.error("sample plugin: window.metabrowser missing — SDK not loaded");
    return;
  }

  const CARD_TMPL = `
    <div class="mb-plugin-sample sample-card">
      <h2>{{title}}</h2>
      <p>Sample plugin loaded for path: {{path}}</p>
      {{#tags}}<span class="tag">{{.}}</span>{{/tags}}
    </div>
  `;

  mb.registerView("sample-doc", "card", {
    render(container, ctx) {
      const data = {
        title: ctx?.frontmatter?.title || "Sample",
        path: ctx?.path || "",
        tags: ctx?.frontmatter?.tags || [],
      };
      container.innerHTML = mb.render(CARD_TMPL, data);
    },
  });

  mb.registerView("sample-doc", "raw", {
    render(container, ctx) {
      const body = ctx?.body || "";
      container.innerHTML = `<pre>${mb.escapeHtml(body)}</pre>`;
    },
  });
})();

/** @param {Record<string, unknown>} data @param {MetabrowserPublicSdk} mb */
export function renderMarkdownSourceHtml(data, mb) {
  const warning = mb.renderTextTruncationWarning(data);
  const content = typeof data.content === "string" ? data.content : "";
  if (mb.isLargeTextPreview(data)) {
    return `${warning}${mb.wrapWithCopy(`<pre class="code-block"><code class="plaintext no-highlight">${mb.escapeHtml(content)}</code></pre>`)}`;
  }
  if (content.startsWith("---\n") || content.startsWith("---\r\n")) {
    let end = content.indexOf("\n---\n", 4);
    if (end === -1) {
      end = content.indexOf("\n---\r\n", 4);
    }
    if (end >= 0) {
      const frontmatter = content.slice(4, end);
      const body = content.slice(end + 5);
      return `${warning}${mb.wrapWithCopy(
        `<pre class="code-block"><code class="language-yaml">${mb.escapeHtml(`---\n${frontmatter}\n---`)}</code></pre>` +
          `<pre class="code-block"><code class="language-markdown">${mb.escapeHtml(body)}</code></pre>`,
      )}`;
    }
  }
  return `${warning}${mb.wrapWithCopy(`<pre class="code-block"><code class="language-markdown">${mb.escapeHtml(content)}</code></pre>`)}`;
}

/** @param {HTMLElement} container @param {{raw?: unknown}} ctx @param {MetabrowserPublicSdk} mb */
export function renderMarkdownSource(container, ctx, mb) {
  container.classList.add("metabrowser-source-host");
  mb.perf.measure("renderMarkdown:source", () => {
    const raw =
      ctx.raw && typeof ctx.raw === "object"
        ? /** @type {Record<string, unknown>} */ (ctx.raw)
        : {};
    container.innerHTML = renderMarkdownSourceHtml(raw, mb);
  });
}

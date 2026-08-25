/** @param {Record<string, unknown>} data @param {MetabrowserPublicSdk} mb */
export function renderMarkdownSourceHtml(data, mb) {
  const warning = mb.renderTextTruncationWarning(data);
  const footer = mb.renderTextLoadMoreFooter(data);
  const content = typeof data.content === "string" ? data.content : "";
  if (mb.isLargeTextPreview(data)) {
    return `${warning}${mb.wrapWithCopy(`<pre class="code-block"><code class="plaintext no-highlight">${mb.escapeHtml(content)}</code></pre>`)}${footer}`;
  }
  if (content.startsWith("---\n") || content.startsWith("---\r\n")) {
    const lineBreak = content.startsWith("---\r\n") ? "\r\n" : "\n";
    const closingDelimiter = `${lineBreak}---${lineBreak}`;
    const end = content.indexOf(closingDelimiter, 3 + lineBreak.length);
    if (end >= 0) {
      const frontmatterEnd = end + closingDelimiter.length;
      const frontmatter = content.slice(0, frontmatterEnd);
      const body = content.slice(frontmatterEnd);
      return `${warning}${mb.wrapWithCopy(
        `<code data-mb-copy-payload class="no-highlight" hidden>${mb.escapeHtml(content)}</code>` +
          `<pre class="code-block"><code class="language-yaml">${mb.escapeHtml(frontmatter)}</code></pre>` +
          `<pre class="code-block"><code class="language-markdown">${mb.escapeHtml(body)}</code></pre>`,
      )}${footer}`;
    }
  }
  return `${warning}${mb.wrapWithCopy(`<pre class="code-block"><code class="language-markdown">${mb.escapeHtml(content)}</code></pre>`)}${footer}`;
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

// The Markdown Source tab: the file's text in the shared source view, with its line
// numbers and #L anchors. YAML front matter is highlighted as YAML and the body as
// Markdown, as two code blocks under one gutter.

/**
 * The front matter and body of a Markdown file's text, or null when it has no
 * complete front matter block.
 *
 * @param {string} content
 * @returns {[string, string] | null}
 */
export function splitFrontMatter(content) {
  if (!content.startsWith("---\n") && !content.startsWith("---\r\n")) {
    return null;
  }
  const lineBreak = content.startsWith("---\r\n") ? "\r\n" : "\n";
  const closingDelimiter = `${lineBreak}---${lineBreak}`;
  const end = content.indexOf(closingDelimiter, 3 + lineBreak.length);
  if (end < 0) {
    return null;
  }
  const frontMatterEnd = end + closingDelimiter.length;
  return [content.slice(0, frontMatterEnd), content.slice(frontMatterEnd)];
}

/** @param {HTMLElement} container @param {{raw?: unknown}} ctx @param {MetabrowserPublicSdk} mb */
export function renderMarkdownSource(container, ctx, mb) {
  mb.perf.measure("renderMarkdown:source", () => {
    const raw =
      ctx.raw && typeof ctx.raw === "object"
        ? /** @type {Record<string, unknown>} */ (ctx.raw)
        : {};
    const split = splitFrontMatter(typeof raw.content === "string" ? raw.content : "");
    mb.renderSourceView(
      container,
      raw,
      split
        ? {
            parts: [
              { text: split[0], language: "yaml" },
              { text: split[1], language: "markdown" },
            ],
          }
        : {},
    );
  });
}

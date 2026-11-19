// The Diagram view of a `.mmd` or `.mermaid` file, which GitHub shows as one diagram.
//
// The file's text is rendered as a Markdown document holding one `mermaid` fence, so the
// file view is the Document view of that document: KPress's figure, stylesheet, and icon
// sprite, the same trust (a trusted folder's diagram is SVG in the page, an untrusted
// one's an image), and the same renderer, toolbar, and dialog (diagrams.js).

/**
 * *text* as a Markdown `mermaid` fence, its fence longer than any backtick run inside.
 *
 * @param {string} text
 * @returns {string}
 */
export function mermaidFence(text) {
  const longest = Math.max(0, ...(text.match(/`+/g) ?? []).map((run) => run.length));
  const fence = "`".repeat(Math.max(3, longest + 1));
  return `${fence}mermaid\n${text.endsWith("\n") ? text : `${text}\n`}${fence}\n`;
}

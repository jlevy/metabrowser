// Built-in Markdown view registration.

import { mermaidFence } from "./mermaid-view.js";
import { mountRenderedMarkdown } from "./rendered.js";
import { renderMarkdownSource } from "./source.js";

const mb = window.metabrowser;
if (!mb) {
  throw new Error("metabrowser markdown plugin: SDK is unavailable");
}

const mountRendered = (container, ctx, options = {}) =>
  mountRenderedMarkdown(container, ctx, mb, options);
const renderSource = (container, ctx) => renderMarkdownSource(container, ctx, mb);

mb.builtins.markdown = { mountRendered, renderSource };
// The file's Document view prints the document, so its card carries the print button.
mb.registerView("markdown", "rendered", {
  render: (container, ctx) => mountRendered(container, ctx, { printIndicator: true }),
});
mb.registerView("markdown", "source", { render: renderSource });

// A `.mmd` or `.mermaid` file: its text as a document holding one Mermaid fence.
mb.registerView("mermaid", "diagram", {
  render: (container, ctx) => mountRendered(container, ctx, { wrapSource: mermaidFence }),
});
mb.registerView("mermaid", "source", {
  render: (container, ctx) =>
    mb.renderSourceView(
      container,
      /** @type {Record<string, unknown>} */ (
        ctx.raw && typeof ctx.raw === "object" ? ctx.raw : {}
      ),
      {},
    ),
});

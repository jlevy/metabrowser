// Built-in Markdown view registration.

import { mermaidFence } from "./mermaid-view.js";
import { drawDiagrams } from "./place-rendered.js";
import { mountRenderedMarkdown } from "./rendered.js";
import { renderMarkdownSource } from "./source.js";

const mb = window.metabrowser;
if (!mb) {
  throw new Error("metabrowser markdown plugin: SDK is unavailable");
}

const mountRendered = (container, ctx, options = {}) =>
  mountRenderedMarkdown(container, ctx, mb, options);
const renderSource = (container, ctx) => renderMarkdownSource(container, ctx, mb);
// Another plugin's KPress render draws its Mermaid diagrams through this plugin's host, as
// a pull request's description and comments do: an image for each unless the caller says
// the render is trusted (`inert: false`), laid out in a frame whose policy loads nothing
// when the caller says nothing else bounds it (`isolated: true`). Null when the root holds
// no diagram.
const drawRenderDiagrams = (root, options = {}) =>
  drawDiagrams(
    root,
    mb,
    options.isolated === true ? "isolated" : options.inert === false ? "document" : "image",
  );

// What a plugin that requires this one gets from `mb.plugins.load("markdown")`.
export { drawRenderDiagrams as drawDiagrams, mountRendered, renderSource };
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

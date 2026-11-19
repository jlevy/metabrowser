// Built-in Markdown view registration.

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

// A `.mmd` or `.mermaid` file. Its view and the renderer behind it load with the first
// one opened, so a Markdown file's view does not fetch them.
/** @param {HTMLElement} container @param {MetabrowserPublicRenderContext} ctx */
const renderDiagramFile = (container, ctx) => {
  /** @type {{dispose(): void} | null} */
  let handle = null;
  let disposed = false;
  const ready = import("./mermaid-view.js").then((view) => {
    if (disposed) {
      return undefined;
    }
    const mounted = view.mountMermaidFile(container, ctx, mb);
    handle = mounted;
    return mounted.ready;
  });
  return {
    ready,
    dispose() {
      disposed = true;
      handle?.dispose();
    },
  };
};
mb.registerView("mermaid", "diagram", { render: renderDiagramFile });
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

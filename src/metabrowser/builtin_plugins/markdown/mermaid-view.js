// The Diagram view of a `.mmd` or `.mermaid` file, which GitHub shows as one diagram.
//
// The file's text goes into the figure KPress emits for a Mermaid fence, so the same
// renderer (diagrams.js), toolbar, and dialog draw it. A file view has no render that
// says whether its source is trusted, so it always draws the image a trusted folder's
// inert render draws: a standalone diagram loses only text selection by it, and its
// source is one tab away.

import { mountDiagrams } from "./diagrams.js";

/**
 * @param {HTMLElement} container
 * @param {MetabrowserPublicRenderContext} ctx
 * @param {MetabrowserPublicSdk} mb
 * @returns {{dispose(): void, ready: Promise<void>}}
 */
export function mountMermaidFile(container, ctx, mb) {
  const controller = new AbortController();
  /** @type {{dispose(): void} | null} */
  let diagrams = null;
  const figure = document.createElement("figure");
  figure.className = "kpress-diagram kpress-mermaid metabrowser-diagram-file";
  figure.dataset.kpressDiagram = "mermaid";
  figure.dataset.kpressDiagramStatus = "source";
  const pre = document.createElement("pre");
  pre.className = "kpress-diagram-source";
  const code = document.createElement("code");
  code.className = "language-mermaid";
  pre.append(code);
  figure.append(pre);
  container.replaceChildren(figure);

  async function render() {
    const raw =
      ctx.raw && typeof ctx.raw === "object"
        ? /** @type {Record<string, unknown>} */ (ctx.raw)
        : {};
    let content = typeof raw.content === "string" ? raw.content : "";
    if (raw.content_truncated === true) {
      content = await mb.fetchCompleteText(ctx, { signal: controller.signal });
    }
    if (controller.signal.aborted) {
      return;
    }
    code.textContent = content;
    const mounted = mountDiagrams(container, mb, { mode: "image" });
    diagrams = mounted;
    await mounted.ready;
  }

  const ready = render().catch((error) => {
    if (!controller.signal.aborted && !mb.errors.isAbortError(error)) {
      console.warn("metabrowser markdown: the diagram file could not be read", error);
    }
  });
  return {
    ready,
    dispose() {
      controller.abort();
      diagrams?.dispose();
      diagrams = null;
    },
  };
}

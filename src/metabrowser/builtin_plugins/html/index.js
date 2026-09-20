// HTML built-in plugin — sandboxed document preview plus shared Source.

(() => {
  const mb = window.metabrowser;
  if (!mb) {
    throw new Error("metabrowser html plugin: SDK is unavailable");
  }

  // Same token set as the /raw CSP sandbox, minus the directive name.
  // Omit allow-same-origin and allow-top-navigation: those would rejoin
  // the application origin or escape the preview.
  const PREVIEW_SANDBOX = "allow-scripts allow-popups allow-forms allow-downloads";

  /**
   * @param {string} inventoryPath
   */
  function rawDocumentUrl(inventoryPath) {
    const href = mb.navigation.href({ path: inventoryPath });
    if (!href.startsWith("/view/")) {
      throw new TypeError("html preview requires a view href");
    }
    return `/raw/${href.slice("/view/".length)}`;
  }

  /**
   * The escape hatch out of the frame: the same document as a top-level tab.
   *
   * No capability check belongs here. The server omits the Preview view when
   * active content is off, so this bar only ever exists beside a live frame,
   * and containment does not depend on it either way: the sandbox is a
   * response header on every `/raw` reply, so a top-level tab gets the same
   * opaque origin the iframe does.
   *
   * @param {Document} doc
   * @param {string} rawUrl The document URL the preview frame is showing.
   * @returns {HTMLElement}
   */
  function createFullPageBar(doc, rawUrl) {
    const bar = doc.createElement("div");
    bar.setAttribute("class", "file-html-preview-bar");
    const link = doc.createElement("a");
    link.setAttribute("class", "file-html-preview-open");
    // A plain anchor with no click handler, so middle-click, modifier-click,
    // copy-link, and the browser's status preview keep native behavior.
    link.setAttribute("href", rawUrl);
    link.setAttribute("target", "_blank");
    // The opened tab gets no `window.opener` back to the shell, and no referrer.
    link.setAttribute("rel", "noopener noreferrer");
    link.setAttribute("data-tip-text", "Open this document in its own tab, still sandboxed");
    link.textContent = "Open as full page";
    bar.replaceChildren(link);
    return bar;
  }

  /**
   * @param {HTMLElement} container
   * @param {{path?: unknown}} ctx
   * @returns {{dispose: () => void}}
   */
  function renderPreview(container, ctx) {
    if (typeof ctx?.path !== "string" || !ctx.path) {
      throw new TypeError("html preview requires a non-empty string path");
    }

    const doc = container.ownerDocument;
    // One URL for both the frame and the full-page control, so they cannot
    // come to address different documents.
    const rawUrl = rawDocumentUrl(ctx.path);
    const bar = createFullPageBar(doc, rawUrl);
    const frame = doc.createElement("iframe");
    frame.setAttribute("class", "file-html-preview");
    frame.setAttribute("sandbox", PREVIEW_SANDBOX);
    frame.setAttribute("referrerpolicy", "no-referrer");
    frame.setAttribute("title", ctx.path);
    frame.setAttribute("src", rawUrl);
    container.replaceChildren(bar, frame);

    let disposed = false;
    return {
      dispose() {
        if (disposed) {
          return;
        }
        disposed = true;
        frame.removeAttribute("src");
        frame.remove();
        bar.remove();
      },
    };
  }

  /**
   * @param {HTMLElement} container
   * @param {{raw?: unknown}} ctx
   */
  function renderSource(container, ctx) {
    const data = /** @type {Record<string, unknown> & {content?: string, ext?: string}} */ (
      ctx.raw || {}
    );
    mb.perf.measure("renderHtml:source", () => {
      mb.renderSourceView(container, data);
    });
  }

  mb.registerView("html", "preview", { render: renderPreview });
  mb.registerView("html", "source", { render: renderSource });
})();

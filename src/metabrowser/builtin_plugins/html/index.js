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
   * @param {HTMLElement} container
   * @param {{path?: unknown}} ctx
   * @returns {{dispose: () => void}}
   */
  function renderPreview(container, ctx) {
    if (typeof ctx?.path !== "string" || !ctx.path) {
      throw new TypeError("html preview requires a non-empty string path");
    }

    const frame = container.ownerDocument.createElement("iframe");
    frame.setAttribute("class", "file-html-preview");
    frame.setAttribute("sandbox", PREVIEW_SANDBOX);
    frame.setAttribute("referrerpolicy", "no-referrer");
    frame.setAttribute("title", ctx.path);
    frame.setAttribute("src", rawDocumentUrl(ctx.path));
    container.replaceChildren(frame);

    let disposed = false;
    return {
      dispose() {
        if (disposed) {
          return;
        }
        disposed = true;
        frame.removeAttribute("src");
        frame.remove();
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

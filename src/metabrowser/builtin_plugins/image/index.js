// Image built-in plugin — the raw-file preview for browser image formats.

(() => {
  const mb = window.metabrowser;
  if (!mb) {
    throw new Error("metabrowser image plugin: SDK is unavailable");
  }

  /**
   * @param {HTMLElement} container
   * @param {{path?: unknown}} ctx
   * @returns {{dispose: () => void}}
   */
  function renderImage(container, ctx) {
    if (typeof ctx?.path !== "string" || !ctx.path) {
      throw new TypeError("image preview requires a non-empty string path");
    }

    const image = container.ownerDocument.createElement("img");
    image.setAttribute("class", "file-image");
    image.setAttribute("src", `/raw?path=${encodeURIComponent(ctx.path)}`);
    image.setAttribute("alt", ctx.path);
    container.replaceChildren(image);

    let disposed = false;
    return {
      dispose() {
        if (disposed) {
          return;
        }
        disposed = true;
        image.remove();
      },
    };
  }

  mb.registerView("image", "preview", { render: renderImage });
})();

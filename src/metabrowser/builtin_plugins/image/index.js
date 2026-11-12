// Image built-in plugin — the raw-file preview for browser image formats.

(() => {
  const mb = window.metabrowser;
  if (!mb) {
    throw new Error("metabrowser image plugin: SDK is unavailable");
  }

  /**
   * The address of the image's bytes. With the envelope's `mtime_hash` as `v` it names
   * these bytes, and the server answers it immutable, so a revisit asks for nothing; an
   * edit gives the next envelope a new one.
   *
   * @param {string} path
   * @param {unknown} raw
   */
  function rawUrl(path, raw) {
    const stamp =
      raw && typeof raw === "object"
        ? /** @type {{mtime_hash?: unknown}} */ (raw).mtime_hash
        : null;
    const version = typeof stamp === "string" && stamp ? `&v=${encodeURIComponent(stamp)}` : "";
    return `/raw?path=${encodeURIComponent(path)}${version}`;
  }

  /**
   * @param {HTMLElement} container
   * @param {{path?: unknown, raw?: unknown}} ctx
   * @returns {{dispose: () => void}}
   */
  function renderImage(container, ctx) {
    if (typeof ctx?.path !== "string" || !ctx.path) {
      throw new TypeError("image preview requires a non-empty string path");
    }

    const image = container.ownerDocument.createElement("img");
    image.setAttribute("class", "file-image");
    image.setAttribute("src", rawUrl(ctx.path, ctx.raw));
    // Navigation identity stays the GitPath wire; alt is the display name.
    const route = window.MetabrowserNavigationRoute;
    const alt =
      route && typeof route.displayPath === "function"
        ? route.displayPath(ctx.path, mb.sourceKind())
        : ctx.path;
    image.setAttribute("alt", alt);
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

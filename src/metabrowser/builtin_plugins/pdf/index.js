// PDF built-in plugin: the host's own PDF viewer, and the ways to open the file outside it.
//
// The viewer is an `<embed>` of the file's `/raw` address. Every `/raw` answer carries a
// CSP sandbox, and a sandboxed document gets no PDF viewer inside an iframe, in WebKit or
// Chrome; an `<embed>` and a top-level tab do get one (measured in
// docs/project/specs/active/plan-2026-11-24-pdf-plugin-and-open-in-default-app.md). Every
// profile's page admits it: the untrusted policy's `object-src` names `/raw` alone
// (capabilities.untrusted_content_security_policy; the threat it answers is in
// docs/project/architecture/arch-threat-model.md). Only the file page mounts this view, so
// a diff or an overview never starts a viewer.
//
// Which actions show depends on what the host supports, never on which host it is:
// - Open: the host opens the file in the app its system assigns to PDF. The macOS app
//   offers it ("open-file"), intercepting the marked link; a browser never sees it.
// - Download: a copy, by the browser's rule for the type (Safari opens a PDF in Preview
//   by default) or the app's save panel.
// - Open in new tab: the browser's viewer at full size. A host that opens the file
//   outside the page has no need of it.

(() => {
  const mb = window.metabrowser;
  if (!mb) {
    throw new Error("metabrowser pdf plugin: SDK is unavailable");
  }

  /** The host action that opens a file in its system's default app. */
  const OPEN_FILE_ACTION = "open-file";
  /** The marker the macOS app intercepts; its value is the subject the path belongs to. */
  const OPEN_FILE_MARKER = "data-metabrowser-open-file";

  /**
   * The file's display path: a GitPath wire on a pinned revision decodes to its names.
   *
   * @param {string} path
   */
  function displayPath(path) {
    const route = window.MetabrowserNavigationRoute;
    return route && typeof route.displayPath === "function"
      ? route.displayPath(path, mb.sourceKind())
      : path;
  }

  /**
   * @param {Document} doc
   * @param {string} label
   * @param {Record<string, string>} attributes
   */
  function action(doc, label, attributes) {
    const link = doc.createElement("a");
    link.setAttribute("class", "pdf-action");
    for (const [name, value] of Object.entries(attributes)) {
      link.setAttribute(name, value);
    }
    link.textContent = label;
    return link;
  }

  /**
   * The bar's actions, each a plain link with no click handler, so a modifier-click,
   * copy-link, and the status preview keep the browser's own behavior.
   *
   * @param {Document} doc
   * @param {string} rawUrl
   * @param {string} name The file's base name, which a download is saved under.
   */
  function actions(doc, rawUrl, name) {
    const links = [];
    if (mb.host.supports(OPEN_FILE_ACTION)) {
      links.push(
        action(doc, "Open", {
          href: rawUrl,
          download: name,
          [OPEN_FILE_MARKER]: mb.sourceKind(),
          "data-tip-text": "Open in the app this Mac uses for PDF files",
        }),
      );
    }
    links.push(
      action(doc, "Download", {
        href: rawUrl,
        download: name,
        "data-tip-text": "Save a copy of this PDF",
      }),
    );
    if (!mb.host.supports(OPEN_FILE_ACTION)) {
      links.push(
        action(doc, "Open in new tab", {
          href: rawUrl,
          target: "_blank",
          // The new tab gets no `window.opener` back to the shell, and no referrer.
          rel: "noopener noreferrer",
          "data-tip-text": "Show this PDF in the browser's viewer, in its own tab",
        }),
      );
    }
    return links;
  }

  /**
   * @param {HTMLElement} container
   * @param {{path?: unknown}} ctx
   * @returns {{dispose: () => void}}
   */
  function renderPdf(container, ctx) {
    if (typeof ctx?.path !== "string" || !ctx.path) {
      throw new TypeError("pdf preview requires a non-empty string path");
    }

    const doc = container.ownerDocument;
    // One address for the viewer and every action, so they cannot name different files.
    const rawUrl = `/raw?path=${encodeURIComponent(ctx.path)}`;
    const shown = displayPath(ctx.path);
    const name = shown.slice(shown.lastIndexOf("/") + 1) || shown;

    const bar = doc.createElement("div");
    bar.setAttribute("class", "pdf-bar");
    bar.replaceChildren(...actions(doc, rawUrl, name));

    const body = doc.createElement("embed");
    body.setAttribute("class", "pdf-viewer");
    body.setAttribute("type", "application/pdf");
    body.setAttribute("src", rawUrl);
    body.setAttribute("aria-label", shown);
    container.replaceChildren(bar, body);

    let disposed = false;
    return {
      dispose() {
        if (disposed) {
          return;
        }
        disposed = true;
        // Dropping the address first lets the viewer release the document.
        body.removeAttribute("src");
        body.remove();
        bar.remove();
      },
    };
  }

  mb.registerView("pdf", "preview", { render: renderPdf });
})();

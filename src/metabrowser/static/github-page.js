// The view header's GitHub toggle (docs/design-system.md, "View Headers").
//
// On a page whose repository is on github.com, a file's or a folder's heading row ends in
// two marks: Metabrowser's, gray, the view the page is in, and GitHub's, a link to the
// same item's page on github.com. Every page opens in the Metabrowser view.
//
// The server writes this module inline into a page for which it found a repository
// context, as it does static/mirror-heading.js, and into no other (server.py,
// `_github_page_script`): the context is a served checkout's `origin` on github.com
// (repository_context.py) or a mirror the GitHub provider owns (cache/providers.py), so a
// plain folder, a checkout whose origin is on another host, and a repository with no
// remote carry neither the module nor the toggle.
//
// github.com refuses to be framed, so a browser cannot show the GitHub view in the page:
// its mark is a link that opens the page in a new tab, as View on GitHub does, and the
// macOS app hands it to the default browser (NavigationPolicy.decideNewWindow).
//
// tests/dom/github-page-session.js runs this file on the contexts the server derives.

(() => {
  const SITE = "https://github.com/";
  const UNRESERVED = /^[A-Za-z0-9._~-]$/;

  /** @param {ArrayLike<number>} bytes */
  function escapeBytes(bytes) {
    let text = "";
    for (const byte of Array.from(bytes)) {
      const character = String.fromCharCode(byte);
      text += UNRESERVED.test(character)
        ? character
        : `%${byte.toString(16).toUpperCase().padStart(2, "0")}`;
    }
    return text;
  }

  /** @param {string} text */
  const escapeText = (text) => escapeBytes(new TextEncoder().encode(text));

  /**
   * One segment of a path identity as its bytes: a pinned revision's `g1-` atom is its
   * base64url bytes, and a folder's identity is UTF-8 with `%XX` for a byte it escapes,
   * a literal percent among them.
   * @param {string} segment
   * @param {string} sourceKind
   */
  function segmentBytes(segment, sourceKind) {
    if (sourceKind === "git_revision" && /^g1-[A-Za-z0-9_-]+$/.test(segment)) {
      const atom = segment.slice(3).replaceAll("-", "+").replaceAll("_", "/");
      const binary = atob(atom + "=".repeat((4 - (atom.length % 4)) % 4));
      return Uint8Array.from(binary, (character) => character.charCodeAt(0));
    }
    const bytes = [];
    for (let at = 0; at < segment.length; ) {
      if (segment[at] === "%" && /^[0-9A-Fa-f]{2}$/.test(segment.slice(at + 1, at + 3))) {
        bytes.push(Number.parseInt(segment.slice(at + 1, at + 3), 16));
        at += 3;
        continue;
      }
      const character = String.fromCodePoint(/** @type {number} */ (segment.codePointAt(at)));
      bytes.push(...new TextEncoder().encode(character));
      at += character.length;
    }
    return bytes;
  }

  /**
   * The ref a page's link names, and what the link's tooltip says of it. A view that names
   * its own ref, as a revision's would, supplies it (`viewRef`). Otherwise the branch the
   * page is on, when `origin` has it (`branch_on_origin`, which the server reads from the
   * checkout's `refs/remotes/origin`; a mirror's branch is the origin's). Otherwise the
   * page's commit, which a branch not pushed may not have put on github.com either.
   *
   * @param {NonNullable<NonNullable<Window["metabrowser"]>["repository"]>} context
   * @param {boolean} onOrigin
   * @param {string} [viewRef]
   * @returns {{ref: string, note: string}}
   */
  function pageRef(context, onOrigin, viewRef) {
    if (viewRef) {
      return { ref: viewRef, note: "" };
    }
    if (context.branch && onOrigin) {
      return { ref: context.branch, note: "" };
    }
    return {
      ref: context.revision,
      note: context.branch
        ? `${context.branch} is not pushed, so this commit may not be on github.com either`
        : "",
    };
  }

  /**
   * The item's page on github.com: a folder's tree or a file's blob at `item.ref`, under
   * the served root's place in the repository. Null without a repository on github.com,
   * for which the SDK's `repository` is null.
   *
   * @param {NonNullable<Window["metabrowser"]>["repository"]} context the SDK's `repository`
   * @param {string} path the item's path identity; "" is the served root
   * @param {{folder: boolean, sourceKind: string, ref: string}} item
   * @returns {string | null}
   */
  function pageUrl(context, path, item) {
    if (!context) {
      return null;
    }
    const ref = item.ref.split("/").map(escapeText);
    const place = context.served_prefix ? context.served_prefix.split("/").map(escapeText) : [];
    const segments = path.replace(/\/+$/, "");
    const below = segments
      ? segments.split("/").map((segment) => escapeBytes(segmentBytes(segment, item.sourceKind)))
      : [];
    const repository = `${SITE}${escapeText(context.owner)}/${escapeText(context.name)}`;
    return [repository, item.folder ? "tree" : "blob", ...ref, ...place, ...below].join("/");
  }

  /**
   * The toggle: the Metabrowser mark, the current view, then the GitHub mark, a link to
   * `url`. A group of two, each with its name for a screen reader and its tooltip; `note`
   * adds what the tooltip says of the link's ref.
   * @param {Document} doc
   * @param {string} url
   * @param {string} [note]
   */
  function toggle(doc, url, note = "") {
    const group = doc.createElement("span");
    group.className = "view-header-toggle";
    group.setAttribute("role", "group");
    group.setAttribute("aria-label", "View");
    const here = doc.createElement("span");
    here.className = "view-header-toggle-option view-header-toggle-metabrowser";
    here.setAttribute("aria-current", "page");
    here.setAttribute("role", "img");
    here.setAttribute("aria-label", "Metabrowser view, shown");
    here.dataset.tipText = "Metabrowser view, shown";
    const there = doc.createElement("a");
    there.className = "view-header-toggle-option view-header-toggle-github";
    there.href = url;
    there.target = "_blank";
    there.rel = "noopener noreferrer";
    there.setAttribute("aria-label", "View on GitHub");
    there.dataset.tipText = `View on GitHub: ${url.replace("https://", "")}${note ? `. ${note}` : ""}`;
    for (const option of [here, there]) {
      const mark = doc.createElement("span");
      mark.className = "view-header-toggle-mark";
      mark.setAttribute("aria-hidden", "true");
      option.append(mark);
    }
    group.append(here, there);
    return group;
  }

  /**
   * End the committed view header's heading row with the toggle, once. The header names
   * its item (`data-path`), and a view that names its own ref its ref (`data-ref`); a page
   * with no repository on github.com gets nothing.
   * @param {Document} doc
   */
  function sync(doc) {
    const header = doc.querySelector("#preview-pane > .view-header");
    const end = header?.querySelector(".view-header-end");
    if (!(header instanceof HTMLElement) || !end || end.querySelector(".view-header-toggle")) {
      return null;
    }
    const sdk = window.metabrowser;
    const context = sdk?.repository ?? null;
    if (!context) {
      return null;
    }
    // `branch_on_origin` rides in the context the server wrote, beside what the SDK keeps.
    const onOrigin = window.METABROWSER_REPOSITORY_CONTEXT?.branch_on_origin === true;
    const { ref, note } = pageRef(context, onOrigin, header.dataset.ref);
    const url = pageUrl(context, header.dataset.path ?? "", {
      folder: header.classList.contains("folder-header"),
      sourceKind: sdk?.sourceKind() ?? "filesystem",
      ref,
    });
    if (url === null) {
      return null;
    }
    const control = toggle(doc, url, note);
    end.append(control);
    return control;
  }

  // A header is committed into the main pane as a child of it; the observer's callback
  // runs before the next frame, so the toggle is drawn with the header it ends.
  const start = () => {
    const pane = document.getElementById("preview-pane");
    if (pane) {
      new MutationObserver(() => sync(document)).observe(pane, { childList: true });
      sync(document);
    }
  };
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start, { once: true });
  } else {
    start();
  }

  window.MetabrowserGithubPage = Object.freeze({ pageRef, pageUrl, sync, toggle });
})();

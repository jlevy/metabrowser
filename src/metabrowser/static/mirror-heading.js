// What a served mirror's page adds to its headings.
//
// A page served from a mirror is headed by the repository's name, as a checkout of it
// would be called, and says where the mirror is kept. The server writes both into the
// navigation heading (`data-served-root`, `data-mirror-location`, `data-mirror-tip`)
// and writes this module inline into such a page, and into no other: a folder's page
// carries none of it, so none of it is a startup script.
//
// - `note()` is what follows the main heading's address: `mirror in <location>`. The
//   mirror is a bare Git repository and nothing is checked out, so the location is a
//   note after the address and never its start, where it would read as a folder
//   holding these files. A revision a folder's server shows of its own checkout is
//   headed the same way, and its note reads `committed revision of <location>`: the
//   server writes the words (`data-mirror-note`), and the folder there holds the
//   working tree, not these files.
//   A mirror's note names the store's directory, without the `/repository.git` every
//   store ends in: the directory's name is what tells one mirror from another. The
//   tooltip and `/api/source/status` keep the whole location, where `git -C <location>`
//   works. This file is written into a mirror's page, so it names no cache path itself.
// - `tip()` is the line the navigation heading's tooltip gains, and the tooltip of the
//   note and of the root's name: the sentence that says what the directory is, with the
//   origin and the full commit.
// - The navigation heading gets a control that copies the full commit, through the
//   SDK's owner-stamped copy delegate. A mirror's heading and a checkout's revision's
//   are the name alone, and the tooltip names the commit.
//
// tests/dom/mirror-heading-session.js runs this file on what the server served.

(() => {
  /** @param {string} text */
  function esc(text) {
    return text
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  /** The navigation heading's data attributes, which the server wrote. */
  function served() {
    const heading = /** @type {HTMLElement | null} */ (document.querySelector(".header-path"));
    return heading?.dataset ?? {};
  }

  /**
   * Where the note says a mirror is: its store's directory, which the bare repository the
   * server names stands in. A checkout's revision names the checkout's own folder, whatever
   * that folder is called.
   * @param {string} location
   * @param {boolean} mirror whether the page is a mirror, which carries no `data-mirror-note`
   */
  function shown(location, mirror) {
    return mirror ? location.replace(/\/repository\.git$/, "") : location;
  }

  /** The note after the main heading's address: where the mirror is kept. */
  function note() {
    const { mirrorLocation: location, mirrorNote: words } = served();
    return location
      ? `<span class="file-header-mirror"><span class="file-header-mirror-text">${esc(words ?? "mirror in")} ${esc(shown(location, words === undefined))}</span></span>`
      : "";
  }

  /**
   * The sentence that says what that directory is.
   * @param {string} [detail] the class of a line under a tooltip's name
   */
  function tip(detail = "tip-detail ") {
    const sentence = served().mirrorTip;
    return sentence ? `<div class="${detail}tip-mirror">${esc(sentence)}</div>` : "";
  }

  /**
   * The root's name or the note under the pointer: each says what the mirror is.
   * @param {Event} event
   */
  function described(event) {
    return event.target instanceof Element
      ? event.target.closest(".file-header-root, .file-header-mirror-text")
      : null;
  }

  // mouseenter and mouseleave do not bubble, so these listen in the capture phase, as
  // the application's own tooltip delegate does.
  document.addEventListener(
    "mouseenter",
    (event) => {
      const anchor = described(event);
      if (anchor) {
        window.MetabrowserTooltip?.show(tip(""), anchor);
      }
    },
    true,
  );
  document.addEventListener(
    "mouseleave",
    (event) => {
      if (described(event)) {
        window.MetabrowserTooltip?.hide();
      }
    },
    true,
  );

  /** Put the control that copies the full commit after the navigation heading. */
  function mountCommitCopy() {
    const heading = document.querySelector(".header-path");
    const pin = window.METABROWSER_SOURCE_PIN?.pin;
    const sdk = window.metabrowser;
    if (!heading || !pin || !sdk || heading.nextElementSibling?.classList.contains("header-copy")) {
      return;
    }
    const button = document.createElement("button");
    button.type = "button";
    button.className = "icon-btn icon-btn-reveal header-copy";
    button.dataset.mbCopy = "text";
    button.dataset.mbCopyText = pin;
    button.dataset.mbCopyLabel = "Copy commit";
    button.dataset.tipText = "Copy commit";
    button.setAttribute("aria-label", `Copy commit ${pin}`);
    button.innerHTML = sdk.icons?.copy ?? "";
    heading.after(sdk.ownDelegate(button));
  }

  // The SDK that stamps the control is a later script of the page.
  document.addEventListener("DOMContentLoaded", mountCommitCopy);

  window.MetabrowserMirrorHeading = Object.freeze({ mountCommitCopy, note, tip });
})();

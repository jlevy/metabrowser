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
//   root menu and `/api/source/status` keep the whole location, where `git -C <location>`
//   works. This file is written into a mirror's page, so it names no cache path itself.
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

  window.MetabrowserMirrorHeading = Object.freeze({ note });
})();

// The reader's choice to block the images of the web, which untrusted Markdown shows
// unless they turn it off ("Block remote images", in the Metabrowser menu).
//
// A document from an untrusted source -- a mirrored repository's README, a pull request's
// text, a folder served with --untrusted -- may show an image from an https address, as
// github.com does, fetched with no referrer. A reader who would rather their browser made
// no such request, because the author of what they are reading learns of it, turns this
// on, and every such image is its alt text inside its link instead, and the page's
// Content-Security-Policy no longer admits one (src/metabrowser/capabilities.py).
//
// The choice is one host-wide preference cookie, as the theme and the reading width are,
// so it covers every Metabrowser server on this host. Only the server reads it, from the
// page request, and the policy, the box's state, and
// `METABROWSER_SETTINGS.BLOCK_REMOTE_IMAGES` follow what it read, so a change takes effect
// as the page loads again: `choose` writes the cookie and asks for that. The exact module
// runs browserlessly in tests/dom/remote-images-session.js.
//
// Loaded on demand (`ensureAsset("settings-menu")`) when the menu opens. The server draws
// the checkbox disabled, and `mount` enables it once it is wired, so a change before then
// is not made and lost.

(() => {
  const KEY = "metabrowser.blockRemoteImages";
  // The one value that turns it on; anything else, or nothing, is off, which is also
  // what src/metabrowser/settings.py reads.
  const ON = "1";
  const OFF = "0";
  const INPUT_ID = "block-remote-images-input";

  /**
   * Make *blocked* the reader's choice, from *applied*, which the page was served with:
   * the cookie is written and the page loads again only when the choice differs, so a
   * click that changes nothing neither writes nor reloads.
   *
   * @param {boolean} blocked
   * @param {boolean} applied
   * @param {{
   *   writePreference(key: string, value: string): void,
   *   reload(): void,
   * }} dependencies
   */
  function choose(blocked, applied, dependencies) {
    if (blocked === applied) {
      return false;
    }
    dependencies.writePreference(KEY, blocked ? ON : OFF);
    dependencies.reload();
    return true;
  }

  /**
   * Wire the menu's checkbox, which the server drew ticked or not as it read the cookie,
   * to `choose`. Returns whether there is one.
   *
   * @param {Pick<Document, "getElementById">} doc
   * @param {{
   *   applied(): boolean,
   *   writePreference(key: string, value: string): void,
   *   reload(): void,
   * }} dependencies
   */
  function mount(doc, dependencies) {
    const input = /** @type {HTMLInputElement | null} */ (doc.getElementById(INPUT_ID));
    if (!input) {
      return false;
    }
    input.addEventListener("change", () => {
      choose(input.checked, dependencies.applied(), dependencies);
    });
    input.disabled = false;
    return true;
  }

  window.MetabrowserRemoteImages = Object.freeze({
    INPUT_ID,
    KEY,
    choose,
    mount,
  });

  // In the page, not in the browserless session that loads this file to run the rest.
  if (typeof document !== "undefined") {
    mount(document, {
      applied: () => window.METABROWSER_SETTINGS?.BLOCK_REMOTE_IMAGES === true,
      // As app.js writes every preference: host-only, so one choice covers every server.
      writePreference(key, value) {
        // biome-ignore lint/suspicious/noDocumentCookie: the shell's preferences are cookies.
        document.cookie = `${key}=${encodeURIComponent(value)}; path=/; max-age=31536000; samesite=lax`;
      },
      reload: () => window.location.reload(),
    });
  }
})();

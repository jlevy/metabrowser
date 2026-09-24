// A page on a pinned revision names the commit it shows on every data request.
//
// One server serves one pin at a time. POST /api/source/pin can switch it while other
// tabs still show the old one, and a restarted server can serve another commit than
// the tab it finds still open. Either tab would otherwise read the new pin's files into
// a page labelled with the old one. The server renders this module inline on a pin,
// with the commit and ref the page was rendered for, before any script can fetch. It
// wraps `fetch` so every same-origin `/api/` request except the `/api/source/` routes
// carries that commit in `x-metabrowser-pin`. The server refuses a request for a commit
// it no longer serves with `409 pin_changed` and names the commit it serves in
// `x-metabrowser-pin-changed`; the wrapper announces that as a
// `metabrowser:pin-changed` event, and the freshness row offers a reload.
//
// The commit is the token, not a counter: a counter restarts with the server, while a
// commit names exactly the content the page shows. Loads that are not `fetch` calls,
// such as an image in rendered Markdown or `/raw` in a new tab, carry no commit and are
// not refused.

(() => {
  const PIN_HEADER = "x-metabrowser-pin";
  const PIN_CHANGED_HEADER = "x-metabrowser-pin-changed";

  /**
   * Whether a request to *url* names the page's commit.
   *
   * @param {string} url
   * @param {string} base The page's own URL.
   */
  function guardedRequest(url, base) {
    let target;
    try {
      target = new URL(url, base);
    } catch {
      return false;
    }
    return (
      target.origin === new URL(base).origin &&
      target.pathname.startsWith("/api/") &&
      !target.pathname.startsWith("/api/source/")
    );
  }

  /**
   * A `fetch` that names *pin* on guarded requests and reports a refusal.
   *
   * @param {typeof fetch} fetchImpl
   * @param {string} pin The full commit ID the page shows.
   * @param {() => string} base The page's current URL, read at each call.
   * @param {(served: string) => void} onPinChanged
   * @returns {typeof fetch}
   */
  function guardFetch(fetchImpl, pin, base, onPinChanged) {
    return async (input, init) => {
      const url = typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
      if (!guardedRequest(url, base())) {
        return fetchImpl(input, init);
      }
      const headers = new Headers(
        init?.headers ?? (input instanceof Request ? input.headers : undefined),
      );
      headers.set(PIN_HEADER, pin);
      const response = await fetchImpl(input, { ...init, headers });
      const served = response.headers.get(PIN_CHANGED_HEADER);
      if (response.status === 409 && served !== null) {
        onPinChanged(served);
      }
      return response;
    };
  }

  window.MetabrowserSourcePinGuard = Object.freeze({
    PIN_CHANGED_HEADER,
    PIN_HEADER,
    guardFetch,
    guardedRequest,
  });

  const page = window.METABROWSER_SOURCE_PIN;
  if (page && typeof page.pin === "string" && typeof window.fetch === "function") {
    window.fetch = guardFetch(
      window.fetch.bind(window),
      page.pin,
      () => window.location.href,
      (served) => {
        window.dispatchEvent(
          new CustomEvent("metabrowser:pin-changed", { detail: { pin: served } }),
        );
      },
    );
  }
})();

// A page on a pinned revision names the pin it shows on every data request.
//
// One server serves one pin at a time, and POST /api/source/pin can switch it while
// other tabs still show the old one. Each of those tabs would otherwise read the new
// pin's files into a page labelled with the old one. The server renders this module
// inline on a pin, with the session generation the page was rendered for, before any
// script can fetch. It wraps `fetch` so every same-origin `/api/` request except the
// `/api/source/` routes carries that generation in `x-metabrowser-generation`. The
// server refuses a request for a generation it no longer serves with `409 pin_changed`
// and says which generation it serves in `x-metabrowser-pin-changed`; the wrapper
// announces that as a `metabrowser:pin-changed` event, and the freshness row offers a
// reload. Requests that are not `fetch` calls, such as images in rendered Markdown,
// carry no generation and are not refused.

(() => {
  const GENERATION_HEADER = "x-metabrowser-generation";
  const PIN_CHANGED_HEADER = "x-metabrowser-pin-changed";

  /**
   * Whether a request to *url* names the page's generation.
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
   * A `fetch` that names *generation* on guarded requests and reports a refusal.
   *
   * @param {typeof fetch} fetchImpl
   * @param {number} generation
   * @param {() => string} base The page's current URL, read at each call.
   * @param {(served: number) => void} onPinChanged
   * @returns {typeof fetch}
   */
  function guardFetch(fetchImpl, generation, base, onPinChanged) {
    return async (input, init) => {
      const url = typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
      if (!guardedRequest(url, base())) {
        return fetchImpl(input, init);
      }
      const headers = new Headers(
        init?.headers ?? (input instanceof Request ? input.headers : undefined),
      );
      headers.set(GENERATION_HEADER, String(generation));
      const response = await fetchImpl(input, { ...init, headers });
      const served = response.headers.get(PIN_CHANGED_HEADER);
      if (response.status === 409 && served !== null) {
        onPinChanged(Number(served));
      }
      return response;
    };
  }

  window.MetabrowserSourceGeneration = Object.freeze({
    GENERATION_HEADER,
    PIN_CHANGED_HEADER,
    guardFetch,
    guardedRequest,
  });

  const generation = window.METABROWSER_SOURCE_GENERATION;
  if (typeof generation === "number" && typeof window.fetch === "function") {
    window.fetch = guardFetch(
      window.fetch.bind(window),
      generation,
      () => window.location.href,
      (served) => {
        window.dispatchEvent(
          new CustomEvent("metabrowser:pin-changed", { detail: { generation: served } }),
        );
      },
    );
  }
})();

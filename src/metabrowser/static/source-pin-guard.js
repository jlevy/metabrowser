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
//
// Back and forward bring a page back without asking the server for it: from the
// back/forward cache as it was left, or from the HTTP cache as it was first served.
// Either can name a commit the server stopped serving after a pin switch, and such a
// page would show "Could not load files" and tooltips for the old commit until a reload.
// So on a history landing, and only then, the page asks the status route once what is
// served and reloads if it is not what the page shows; a data request refused meanwhile
// says the same sooner. A page reloads itself at most once, and a reload is not a
// history landing, so it cannot loop. A page the reader is looking at when another tab
// switches is left to the freshness row's offer: nothing changes under a reader.
//
// The alternative, `Cache-Control: no-store` on the page, keeps every pin page out of
// the back/forward cache: measured in Chrome 152, Back to a diff then took 342-630 ms
// on every landing against 8-34 ms without the header, and lost the scroll position.
// With this guard instead, in Chrome 152.0.7977.83 over ten rounds each
// (explorations/history-landing/README.md): a landing with nothing switched is restored
// from the back/forward cache 3-14 ms after Back, at its scroll position, with no
// document loaded; a landing after a switch is restored and then reloads once, with
// the diff of the served pin in the page 204-541 ms after Back. With the back/forward
// cache off the page loads from the HTTP cache (19-29 ms to pageshow) and reloads once
// only after a switch.

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

  /**
   * Whether the status route's answer says the server serves another commit than the
   * page shows, or none at all, as after a restart on a folder. An answer that is not a
   * status says nothing.
   *
   * @param {string} pin The commit the page was rendered for.
   * @param {{pin?: unknown} | null} served
   */
  function servesAnother(pin, served) {
    return (
      served !== null &&
      (typeof served.pin === "string" || served.pin === null) &&
      served.pin !== pin
    );
  }

  /**
   * What a page does on a history landing. No DOM: the glue below supplies the status
   * route, the reload, and the events.
   *
   * `loaded(type)` is the document's own navigation type, read once when the page starts;
   * `shown(persisted)` is a `pageshow`; `refused()` is a data request answered
   * `pin_changed`. A landing asks the status route once; while its answer is on the
   * way, a refusal is taken as the answer.
   *
   * @param {{status(): Promise<{pin?: unknown} | null>, reload(): void}} deps
   * @param {string} pin The commit the page was rendered for.
   */
  function createHistoryGuard(deps, pin) {
    let asking = false;
    let reloaded = false;

    function reload() {
      if (!reloaded) {
        reloaded = true;
        deps.reload();
      }
    }

    async function landed() {
      if (asking || reloaded) {
        return;
      }
      asking = true;
      let served = null;
      try {
        served = await deps.status();
      } catch {
        served = null;
      }
      asking = false;
      if (servesAnother(pin, served)) {
        reload();
      }
    }

    return Object.freeze({
      /** @param {string} navigationType */
      loaded: (navigationType) =>
        navigationType === "back_forward" ? landed() : Promise.resolve(),
      /** @param {boolean} persisted */
      shown: (persisted) => (persisted ? landed() : Promise.resolve()),
      refused() {
        if (asking) {
          reload();
        }
      },
      snapshot: () => ({ asking, reloaded }),
    });
  }

  window.MetabrowserSourcePinGuard = Object.freeze({
    PIN_CHANGED_HEADER,
    PIN_HEADER,
    createHistoryGuard,
    guardFetch,
    guardedRequest,
    servesAnother,
  });

  const page = window.METABROWSER_SOURCE_PIN;
  if (page && typeof page.pin === "string" && typeof window.fetch === "function") {
    const plainFetch = window.fetch.bind(window);
    const history = createHistoryGuard(
      {
        async status() {
          const response = await plainFetch("/api/source/status", { cache: "no-store" });
          return response.ok ? await response.json() : null;
        },
        reload: () => window.location.reload(),
      },
      page.pin,
    );
    window.fetch = guardFetch(
      plainFetch,
      page.pin,
      () => window.location.href,
      (served) => {
        history.refused();
        window.dispatchEvent(
          new CustomEvent("metabrowser:pin-changed", { detail: { pin: served } }),
        );
      },
    );
    window.addEventListener("pageshow", (event) => void history.shown(event.persisted));
    const entry = window.performance?.getEntriesByType?.("navigation")[0];
    void history.loaded(
      entry ? /** @type {PerformanceNavigationTiming} */ (entry).type : "navigate",
    );
  }
})();

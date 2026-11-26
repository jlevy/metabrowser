// A page on a pinned revision names the commit it shows on every data request.
//
// One server serves one pin at a time. POST /api/source/pin can switch it while other
// tabs still show the old one, and a restarted server can serve another commit than
// the tab it finds still open. Either tab would otherwise read the new pin's files into
// a page labelled with the old one. The server renders this module inline on a pin,
// with the commit and ref the page was rendered for, before any script can fetch. It
// wraps `fetch` so every same-origin `/api/` request except the `/api/source/` and
// `/api/event-log` routes carries that commit in `x-metabrowser-pin`. The server refuses a request for a commit
// it no longer serves with `409 pin_changed` and names the commit it serves in
// `x-metabrowser-pin-changed`; the wrapper announces that as a
// `metabrowser:pin-changed` event, and the freshness row offers a reload.
//
// The commit is the token, not a counter: a counter restarts with the server, while a
// commit names exactly the content the page shows. Loads that are not `fetch` calls,
// such as an image in rendered Markdown or `/raw` in a new tab, carry no commit and are
// not refused.
//
// A folder's server serves nothing but its folder, so a folder's page names nothing,
// with one exception. A folder that is a repository's root can show a committed revision
// of its checkout in the folder's place (static/source-ref-selector.js), so the page of
// its working tree names what it shows too, with the word `working-tree` where a pin's
// page has its commit, and is refused in the same way once a revision is served. That
// page does not carry this module inline: it arrives with the selector that can make
// the switch, after the first tree request, so a folder's first paint pays nothing for
// it (`METABROWSER_SOURCE_CHECKOUT`).
//
// Back and forward bring a page back without asking the server for it: from the
// back/forward cache as it was left, or from the HTTP cache as it was first served.
// Either can name a commit the server stopped serving after a pin switch, and such a
// page would show "Could not load files" and tooltips for the old commit until a reload.
// So on a history landing, and only then, the page asks the status route once what is
// served and reloads if it is not what the page shows; a data request refused meanwhile
// says the same sooner. A page reloads itself at most once, and a reload is not a
// history landing, so it cannot loop. A page the reader is looking at when another tab
// switches is left to the freshness row's offer: nothing changes under a reader. A page
// on a branch a refresh moved is the row's too, which follows the branch by itself.
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
//
// The page that switches the server (static/source-ref-selector.js) is left behind too,
// from the moment it asks until it has gone: its refresh of the root's tallies, half a
// second after its first rows, was refused so and showed the offer to reload on its way
// out (mb-bio7). So its guarded requests wait out the switch (`createSwitchHold`).

(() => {
  const PIN_HEADER = "x-metabrowser-pin";
  const PIN_CHANGED_HEADER = "x-metabrowser-pin-changed";
  // What the page of a checkout's working tree names: `WORKING_TREE_PIN` in
  // source_routes.py. Not hexadecimal, so it is never a commit.
  const WORKING_TREE_PIN = "working-tree";
  // How long a switch holds the page's requests at most, from the moment it asks. Measured
  // 2026-11-18 in headless Chrome 152 at a load average of 90, on the three-file checkout of
  // tests/dom/checkout-ref-selector-chrome.mjs: the pin route answered 105 to 134 ms after
  // it was asked and the new document made its first request 39 ms after that; on CI the
  // whole switch, from the click to the new page's rows, took 168 ms. 5 s is about 30 times
  // the slowest of those, for a loaded machine or a larger checkout. Too short, and a switch
  // slower than the bound sends the page's requests while it is still here: they are
  // refused and the page shows the offer to reload on its way out, as before the hold. Too
  // long, and a page whose pin route does not answer, or whose navigation the reader
  // stopped, asks the server for nothing that long.
  const SWITCH_HOLD_MS = 5000;

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
    const path = target.pathname;
    return (
      target.origin === new URL(base).origin &&
      path.startsWith("/api/") &&
      !path.startsWith("/api/source/") &&
      // The event log is about the server, whichever revision it shows: a page left on
      // an old pin still reports what it saw, and its Details still read the log
      // (`_PIN_EXEMPT_EVENT_LOG` in source_routes.py).
      path !== "/api/event-log" &&
      !path.startsWith("/api/event-log/")
    );
  }

  /**
   * A `fetch` that names *pin* on guarded requests and reports a refusal.
   *
   * @param {typeof fetch} fetchImpl
   * @param {string} pin The full commit ID the page shows, or `WORKING_TREE_PIN`.
   * @param {() => string} base The page's current URL, read at each call.
   * @param {(served: string) => void} onPinChanged
   * @param {() => Promise<void> | null} [waiting] What a guarded request waits for before
   *   it is sent: a switch the page asked for (`createSwitchHold`), or null.
   * @returns {typeof fetch}
   */
  function guardFetch(fetchImpl, pin, base, onPinChanged, waiting = () => null) {
    let selecting = false;
    return async (input, init) => {
      const url = typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
      const address = base();
      const method = init?.method ?? (input instanceof Request ? input.method : "GET");
      // Menus, the chooser, and PR/diff controls all post to this route. A second
      // control must not change the session while the first is waiting for its answer.
      if (method.toUpperCase() === "POST") {
        const target = new URL(url, address);
        if (target.origin === new URL(address).origin && target.pathname === "/api/source/pin") {
          if (selecting) {
            return Response.json(
              { code: "selection_busy", error: "Another switch is already in progress." },
              { status: 409 },
            );
          }
          selecting = true;
          try {
            return await fetchImpl(input, init);
          } finally {
            selecting = false;
          }
        }
      }
      if (!guardedRequest(url, address)) {
        return fetchImpl(input, init);
      }
      const wait = waiting();
      if (wait !== null) {
        await heldUntil(wait, init?.signal ?? (input instanceof Request ? input.signal : null));
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
   * *wait*, or a rejection with the signal's reason as soon as *signal* aborts: a request
   * given up while it is held settles then, as `fetch` would, and is never sent.
   *
   * @param {Promise<void>} wait
   * @param {AbortSignal | null | undefined} signal
   * @returns {Promise<void>}
   */
  function heldUntil(wait, signal) {
    if (!signal) {
      return wait;
    }
    return new Promise((resolve, reject) => {
      const abort = () => reject(signal.reason);
      if (signal.aborted) {
        abort();
        return;
      }
      signal.addEventListener("abort", abort, { once: true });
      void wait.then(() => {
        signal.removeEventListener("abort", abort);
        resolve();
      });
    });
  }

  /**
   * The wait a page's guarded requests take while it switches what the server serves, which
   * may serve the other subject before the page has gone. `hold(going)` starts it as the
   * page asks; *going* settles false when the page stays, which ends it at once, and true
   * when the page goes, which keeps it until the page has gone. Whatever *going* does, it
   * ends SWITCH_HOLD_MS after the ask: a pin route that does not answer, or a navigation the
   * reader stopped. `release()` ends it for a page the back/forward cache shows again;
   * `waiting()` is what a request waits for now. No DOM: the glue below supplies the timer.
   *
   * @param {(callback: () => void, ms: number) => void} setTimer
   */
  function createSwitchHold(setTimer) {
    /** @type {{wait: Promise<void>, open: () => void} | null} */
    let held = null;

    function release() {
      const ending = held;
      held = null;
      ending?.open();
    }

    /** @param {Promise<boolean>} going */
    function hold(going) {
      release();
      /** @type {() => void} */
      let open = () => {};
      /** @type {Promise<void>} */
      const wait = new Promise((resolve) => {
        open = () => resolve();
      });
      const mine = { wait, open };
      held = mine;
      // Only this hold's own end: a bound of an earlier switch, firing during this one,
      // finds another hold and leaves it.
      const ends = () => {
        if (held === mine) {
          release();
        }
      };
      setTimer(ends, SWITCH_HOLD_MS);
      void going.then((gone) => {
        if (!gone) {
          ends();
        }
      }, ends);
    }

    return Object.freeze({ hold, release, waiting: () => held?.wait ?? null });
  }

  /**
   * Whether the status route's answer says the server serves another commit than the
   * page shows, or none at all, as after a restart on a folder. An answer that is not a
   * status says nothing.
   *
   * @param {string | null} pin The commit the page was rendered for, or null for the
   *   page of a checkout's working tree, which a status names by a null pin.
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
   * @param {string | null} pin The commit the page was rendered for; null for the page
   *   of a checkout's working tree.
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

  /**
   * What this page shows, as the guard names it: its commit, null for the working tree
   * of a checkout, or `undefined` for a page with nothing to guard. Pure.
   *
   * @param {{pin?: unknown} | null | undefined} page `METABROWSER_SOURCE_PIN`.
   * @param {{working_tree?: unknown} | null | undefined} checkout `METABROWSER_SOURCE_CHECKOUT`.
   * @returns {string | null | undefined}
   */
  function shownPin(page, checkout) {
    if (page && typeof page.pin === "string") {
      return page.pin;
    }
    return checkout && checkout.working_tree === true ? null : undefined;
  }

  const switchHold = createSwitchHold((callback, ms) => void window.setTimeout(callback, ms));

  // A stale shell can mount another page from its own cached data before the next request.
  let pinChanged = false;
  window.MetabrowserSourcePinGuard = Object.freeze({
    hasChanged: () => pinChanged,
    PIN_CHANGED_HEADER,
    PIN_HEADER,
    WORKING_TREE_PIN,
    createHistoryGuard,
    createSwitchHold,
    guardFetch,
    guardedRequest,
    // A page can have several ways to change refs. Keep the first one's hold through
    // navigation so another control cannot race the switch while its request is pending.
    /** @param {Promise<boolean>} going */
    hold(going) {
      if (switchHold.waiting()) {
        return false;
      }
      switchHold.hold(going);
      return true;
    },
    servesAnother,
    shownPin,
  });

  const shown = shownPin(window.METABROWSER_SOURCE_PIN, window.METABROWSER_SOURCE_CHECKOUT);
  if (shown !== undefined && typeof window.fetch === "function") {
    const plainFetch = window.fetch.bind(window);
    const history = createHistoryGuard(
      {
        async status() {
          const response = await plainFetch("/api/source/status", { cache: "no-store" });
          return response.ok ? await response.json() : null;
        },
        reload: () => window.location.reload(),
      },
      shown,
    );
    window.fetch = guardFetch(
      plainFetch,
      shown ?? WORKING_TREE_PIN,
      () => window.location.href,
      (served) => {
        pinChanged = true;
        history.refused();
        window.dispatchEvent(
          new CustomEvent("metabrowser:pin-changed", { detail: { pin: served } }),
        );
      },
      switchHold.waiting,
    );
    window.addEventListener("pageshow", (event) => {
      if (event.persisted) {
        switchHold.release();
      }
      void history.shown(event.persisted);
    });
    const entry = window.performance?.getEntriesByType?.("navigation")[0];
    void history.loaded(
      entry ? /** @type {PerformanceNavigationTiming} */ (entry).type : "navigate",
    );
  }
})();

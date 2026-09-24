// Freshness of a served mirror: the quiet fetched label, the newer-revision offer,
// and switching the pin.
//
// A page on a pinned revision polls /api/source/status while it is visible: quickly
// while a refresh runs, slowly otherwise, and with If-None-Match so an unchanged
// answer is a 304. When the mirror is older than the server's freshness window and
// nothing is refreshing, opening or revealing the page asks for one background
// refresh; the page never waits for it. When a refresh moves the pinned ref, the
// label offers the newer commit, and accepting switches the pin and reloads the view.
// When the server serves another pin than the one the page was rendered for -- another
// tab switched it, or a data request came back `pin_changed` -- it offers a reload.
//
// Every decision lives here without a DOM: `describe` turns a status into what the
// label says and offers, and `createController` owns polling, visibility, and the
// two POST actions through injected dependencies. `mount` is the browser glue that
// supplies real fetch, timers, and paint. tests/dom/source-freshness-session.js runs
// the same functions from the command line.

(() => {
  // The status route answers from server memory and a 304 when nothing changed, so
  // polling costs one small request. One second while a refresh runs makes its end
  // visible promptly; thirty seconds otherwise bounds how late a page learns of a
  // refresh another tab started and keeps the label's age current.
  const FAST_POLL_MS = 1000;
  const SLOW_POLL_MS = 30000;
  const STATUS_ROUTE = "/api/source/status";
  const REFRESH_ROUTE = "/api/source/refresh";
  const PIN_ROUTE = "/api/source/pin";

  // Refresh outcomes that are not failures: the fetch ran, or another process's is running.
  const QUIET_OUTCOMES = new Set(["succeeded", "default_branch_unknown", "refreshing_elsewhere"]);

  /** @type {Readonly<Record<string, string>>} */
  const OUTCOME_DETAIL = Object.freeze({
    origin_unavailable: "The origin could not be read.",
    fetch_failed: "The fetch from the origin failed.",
    not_found_or_private:
      "The origin says the repository does not exist, or it is private and the credentials offered do not open it.",
    network_unreachable: "The origin's host could not be reached.",
    connection_interrupted: "The connection to the origin was interrupted.",
    tls_failed: "The secure connection to the origin failed.",
    timed_out: "The origin did not answer, or stopped sending, in time.",
    server_error: "The origin answered with a server error.",
    rate_limited: "The origin is limiting requests; try again later.",
    proxy_auth_required: "The proxy between here and the origin asked for credentials.",
    ref_case_collision:
      "The origin has branches or tags whose names differ only in letter case, which this file system cannot keep apart, so no ref moved.",
    validation_failed: "The origin's default branch did not arrive in the mirror as a commit.",
    default_branch_unknown:
      "The origin's HEAD names no branch, so the mirror keeps the default branch it had.",
    unsupported_git: "The installed Git is older than the version Metabrowser fetches with.",
    store_unavailable: "The mirror could not be opened.",
    refreshing_elsewhere: "Another Metabrowser process is refreshing this mirror.",
    cancelled: "The refresh was stopped before it finished.",
    failed: "The refresh failed.",
  });

  // What the row says about the address a page was opened at, while the server serves
  // the default branch in its place.
  /** @type {Readonly<Record<string, string>>} */
  const SELECTION_DETAIL = Object.freeze({
    pending:
      "The address this page was opened at is not in the mirror yet; it opens when the fetch brings it.",
    not_found:
      "The address this page was opened at is not on the origin, so the default branch is shown.",
    fetch_failed:
      "The address this page was opened at could not be fetched, so the default branch is shown.",
  });

  /**
   * How long ago an ISO timestamp was, the way a quiet label says it.
   *
   * @param {string | null} iso
   * @param {number} nowMs
   * @returns {string}
   */
  function relativeAge(iso, nowMs) {
    const at = iso === null ? Number.NaN : Date.parse(iso);
    if (!Number.isFinite(at)) {
      return "at an unknown time";
    }
    const seconds = Math.max(0, Math.floor((nowMs - at) / 1000));
    if (seconds < 60) {
      return "just now";
    }
    const minutes = Math.floor(seconds / 60);
    if (minutes < 60) {
      return `${minutes} min ago`;
    }
    const hours = Math.floor(minutes / 60);
    if (hours < 48) {
      return `${hours} h ago`;
    }
    return `${Math.floor(hours / 24)} d ago`;
  }

  /**
   * What the label says and offers for one status. Pure.
   *
   * @param {MetabrowserSourceStatus | null} status
   * @param {{shown: MetabrowserSourcePage | null, nowMs: number, error?: string | null}} page
   *   *shown* is the pin and ref the page was rendered for.
   * @returns {MetabrowserSourceFreshnessModel}
   */
  function describe(status, page) {
    const error = page.error ?? null;
    if (status === null || status.subject !== "git_revision" || !status.refreshable) {
      return {
        visible: false,
        tone: "quiet",
        label: "",
        detail: "",
        offer: null,
        error,
        pull: null,
      };
    }
    const age = relativeAge(status.last_fetch_at, page.nowMs);
    const outcome = status.last_outcome;
    const failed =
      outcome !== null && outcome.operation === "refresh" && !QUIET_OUTCOMES.has(outcome.outcome);
    /** @type {MetabrowserSourceFreshnessModel["tone"]} */
    let tone = status.stale ? "stale" : "quiet";
    let label = `Fetched ${age}`;
    let detail = `The mirror was last fetched from its origin ${age}.`;
    if (status.refreshing) {
      tone = "refreshing";
      label = "Refreshing…";
      detail = `Fetching from the origin. The mirror was last fetched ${age}.`;
    } else if (failed) {
      tone = "warning";
      label = `Refresh failed · fetched ${age}`;
      detail = `${OUTCOME_DETAIL[outcome.outcome] ?? OUTCOME_DETAIL.failed} The pinned revision is still served from the mirror.`;
    } else if (outcome !== null && outcome.outcome === "refreshing_elsewhere") {
      detail = `${OUTCOME_DETAIL.refreshing_elsewhere} It was last fetched here ${age}.`;
    } else if (outcome !== null && outcome.outcome === "default_branch_unknown") {
      detail = `${detail} ${OUTCOME_DETAIL.default_branch_unknown}`;
    }
    const selection = status.selection_state ?? null;
    const retrySelection = selection === "fetch_failed" && !status.refreshing;
    if (selection === "pending") {
      detail = `${detail} ${SELECTION_DETAIL.pending}`;
    } else if (selection === "not_found") {
      tone = "warning";
      label = `Address not found · fetched ${age}`;
      detail = SELECTION_DETAIL.not_found;
    } else if (retrySelection) {
      tone = "warning";
      label = `Address not fetched · fetched ${age}`;
      const why = outcome !== null ? (OUTCOME_DETAIL[outcome.outcome] ?? "") : "";
      detail = `${SELECTION_DETAIL.fetch_failed} ${why}`.trim();
    }
    /** @type {MetabrowserSourceOffer | null} */
    let offer = null;
    if (page.shown !== null && (status.pin !== page.shown.pin || status.ref !== page.shown.ref)) {
      offer = {
        kind: "reload",
        text: "The server now serves another revision",
        button: "Reload",
      };
    } else if (retrySelection) {
      offer = { kind: "retry", text: "Fetch the address again", button: "Retry" };
    } else if (
      status.ref !== null &&
      status.latest !== null &&
      status.pin !== null &&
      status.latest !== status.pin
    ) {
      offer = {
        kind: "switch",
        ref: status.ref,
        latest: status.latest,
        // "Now at", not "newer": a force-push can move a branch back.
        text: `${status.ref_name ?? status.ref} is now at ${status.latest.slice(0, 12)}`,
        button: "Switch",
      };
    } else if (status.ref !== null && status.ref_on_origin === false && !status.refreshing) {
      detail = `${detail} ${status.ref_name ?? status.ref} is no longer on the origin; its commits stay readable here.`;
    }
    // The served pull request's page is one link away from every page on its pin.
    const pull =
      typeof status.pull_request === "number"
        ? { href: `/pull/${status.pull_request}`, text: `Pull request #${status.pull_request}` }
        : null;
    return { visible: true, tone, label, detail, offer, error, pull };
  }

  /**
   * Where a page should go when a URL selection it was opened for has arrived. Pure.
   *
   * A page opened while the selection waited for its fetch shows the default branch.
   * Once the server serves the selection, that page goes to the selection's address,
   * line anchor included. A page already showing the served pin stays.
   *
   * @param {MetabrowserSourceStatus | null} status
   * @param {MetabrowserSourcePage | null} shown
   * @returns {string | null}
   */
  function selectionToOpen(status, shown) {
    if (
      status === null ||
      shown === null ||
      status.selection_state !== "found" ||
      typeof status.selection_href !== "string" ||
      !(status.selection_href.startsWith("/view/") || status.selection_href.startsWith("/pull/"))
    ) {
      return null;
    }
    return status.pin !== shown.pin || status.ref !== shown.ref ? status.selection_href : null;
  }

  /**
   * @param {unknown} value
   * @returns {value is MetabrowserSourceStatus}
   */
  function isStatus(value) {
    if (value === null || typeof value !== "object") {
      return false;
    }
    const record = /** @type {Record<string, unknown>} */ (value);
    return (
      typeof record.subject === "string" &&
      typeof record.generation === "number" &&
      typeof record.refreshable === "boolean" &&
      typeof record.refreshing === "boolean" &&
      typeof record.stale === "boolean"
    );
  }

  /**
   * The polling and action state machine for one page.
   *
   * *options.shown* is the pin and ref the page was rendered for, which the server
   * writes into a pin's page; without it the first status answered stands in. They are
   * compared rather than the session generation, which counts from 1 again in every
   * server process, so a page left open across a restart onto another pin notices.
   *
   * @param {MetabrowserSourceFreshnessDependencies} deps
   * @param {{shown?: MetabrowserSourcePage | null}} [options]
   */
  function createController(deps, options = {}) {
    /** @type {MetabrowserSourceStatus | null} */
    let status = null;
    /** @type {string | null} */
    let etag = null;
    /** @type {MetabrowserSourcePage | null} */
    let shown = options.shown ?? null;
    // What was last painted, so an unchanged status repaints nothing: a live region
    // that repaints announces again, and focus on its button would be lost.
    /** @type {string | null} */
    let painted = null;
    /** @type {unknown} */
    let timer = null;
    let polling = false;
    let disposed = false;
    // One refresh request per visible period: a stale page that cannot be refreshed
    // (its origin is gone) must not ask again on every poll.
    let refreshAskedWhileVisible = false;
    let switching = false;
    // A page goes to a selection that arrived at most once.
    let openedSelection = false;
    /** @type {string | null} */
    let error = null;

    function render() {
      const model = describe(status, { shown, nowMs: deps.now(), error });
      const key = JSON.stringify(model);
      if (key === painted) {
        return;
      }
      painted = key;
      deps.render(model);
    }

    function clearTimer() {
      if (timer !== null) {
        deps.cancel(timer);
        timer = null;
      }
    }

    function scheduleNext() {
      clearTimer();
      if (disposed || !deps.isVisible()) {
        return;
      }
      const delay = status?.refreshing ? FAST_POLL_MS : SLOW_POLL_MS;
      timer = deps.schedule(() => {
        timer = null;
        void poll();
      }, delay);
    }

    /** @param {MetabrowserSourceStatus} next */
    function accept(next) {
      status = next;
      if (shown === null && next.pin !== null) {
        shown = { pin: next.pin, ref: next.ref };
      }
      const href = selectionToOpen(next, shown);
      if (href !== null && !openedSelection) {
        openedSelection = true;
        deps.navigate(href);
      }
    }

    async function poll() {
      if (disposed || polling || !deps.isVisible()) {
        return;
      }
      polling = true;
      try {
        const response = await deps.request("GET", STATUS_ROUTE, { etag });
        if (disposed) {
          return;
        }
        if (response.status === 200 && isStatus(response.body)) {
          accept(response.body);
          etag = response.etag;
          error = null;
        } else if (response.status === 304) {
          error = null;
        } else {
          error = `Status unavailable (HTTP ${response.status})`;
        }
      } catch {
        error = "The server did not answer";
      } finally {
        polling = false;
      }
      if (disposed) {
        return;
      }
      if (status?.stale && !status.refreshing && !refreshAskedWhileVisible) {
        await requestRefresh();
        return;
      }
      render();
      scheduleNext();
    }

    async function requestRefresh() {
      if (disposed || status === null || !status.refreshable) {
        return;
      }
      refreshAskedWhileVisible = true;
      try {
        const response = await deps.request("POST", REFRESH_ROUTE, { body: {} });
        const body = /** @type {{status?: unknown} | null} */ (response.body);
        if (response.status === 202 && body !== null && isStatus(body.status)) {
          accept(body.status);
          // The envelope changed; the next poll must not be answered by a 304.
          etag = null;
          error = null;
        } else {
          error = `Refresh refused (HTTP ${response.status})`;
        }
      } catch {
        error = "The refresh request failed";
      }
      if (!disposed) {
        render();
        scheduleNext();
      }
    }

    async function acceptOffer() {
      const model = describe(status, { shown, nowMs: deps.now() });
      const offer = model.offer;
      if (disposed || switching || offer === null) {
        return;
      }
      if (offer.kind === "reload") {
        deps.reload();
        return;
      }
      if (offer.kind === "retry") {
        await requestRefresh();
        return;
      }
      switching = true;
      try {
        const response = await deps.request("POST", PIN_ROUTE, { body: { ref: offer.ref } });
        if (response.status === 200) {
          deps.reload();
          return;
        }
        const body = /** @type {{code?: unknown} | null} */ (response.body);
        const code = body !== null && typeof body.code === "string" ? body.code : "";
        error = `Could not switch (${code || `HTTP ${response.status}`})`;
      } catch {
        error = "The switch request failed";
      } finally {
        switching = false;
      }
      if (!disposed) {
        render();
      }
    }

    function onVisibilityChange() {
      if (disposed) {
        return;
      }
      if (!deps.isVisible()) {
        clearTimer();
        return;
      }
      refreshAskedWhileVisible = false;
      void poll();
    }

    function dispose() {
      disposed = true;
      clearTimer();
    }

    return Object.freeze({
      start: () => poll(),
      poll,
      requestRefresh,
      acceptOffer,
      onVisibilityChange,
      dispose,
      snapshot: () => ({
        status,
        etag,
        shown,
        timerPending: timer !== null,
        refreshAskedWhileVisible,
        error,
      }),
    });
  }

  /**
   * What a screen reader is told when the row changes: its state and offer, not the age,
   * which changes every minute and is read from the label on demand.
   *
   * @param {MetabrowserSourceFreshnessModel} model
   */
  function announcement(model) {
    if (!model.visible) {
      return "";
    }
    const parts = [];
    if (model.tone === "refreshing" || model.tone === "warning") {
      parts.push(model.label);
    }
    if (model.offer !== null) {
      parts.push(model.offer.text);
    }
    if (model.error !== null) {
      parts.push(model.error);
    }
    return parts.join(". ");
  }

  /**
   * Paint one model into the row. Browser only.
   *
   * The row itself is not a live region; one visually hidden span announces
   * {@link announcement} when it changes. Focus on the offer's button survives a repaint.
   *
   * @param {HTMLElement} element
   * @param {MetabrowserSourceFreshnessModel} model
   * @param {{refresh(): void, accept(): void}} actions
   * @param {HTMLElement} live
   */
  function paint(element, model, actions, live) {
    const announced = announcement(model);
    if (live.textContent !== announced) {
      live.textContent = announced;
    }
    element.hidden = !model.visible;
    element.dataset.tone = model.tone;
    if (!model.visible) {
      element.replaceChildren(live);
      return;
    }
    const focused = document.activeElement;
    const refocus =
      focused instanceof HTMLElement && element.contains(focused)
        ? focused.className.split(" ").find((name) => name.startsWith("source-freshness-"))
        : undefined;
    const label = document.createElement("button");
    label.type = "button";
    label.className = "source-freshness-label";
    label.textContent = model.label;
    label.dataset.tipText = `${model.detail} Click to refresh now.`;
    label.setAttribute("aria-label", `${model.label}. ${model.detail} Refresh now.`);
    label.disabled = model.tone === "refreshing";
    label.addEventListener("click", actions.refresh);
    /** @type {HTMLElement[]} */
    const children = [label];
    if (model.pull !== null) {
      const pull = document.createElement("a");
      pull.className = "source-freshness-pull";
      pull.href = model.pull.href;
      pull.textContent = model.pull.text;
      if (window.location.pathname.startsWith(model.pull.href)) {
        pull.setAttribute("aria-current", "page");
      }
      children.push(pull);
    }
    if (model.offer !== null) {
      const offer = document.createElement("span");
      offer.className = "source-freshness-offer";
      const text = document.createElement("span");
      text.textContent = model.offer.text;
      const button = document.createElement("button");
      button.type = "button";
      button.className = "btn source-freshness-accept";
      button.textContent = model.offer.button;
      button.addEventListener("click", actions.accept);
      offer.append(text, button);
      children.push(offer);
    }
    if (model.error !== null) {
      const failure = document.createElement("span");
      failure.className = "source-freshness-error";
      failure.textContent = model.error;
      children.push(failure);
    }
    element.replaceChildren(...children, live);
    if (refocus) {
      const target = element.querySelector(`.${refocus}`);
      if (target instanceof HTMLElement) {
        target.focus();
      }
    }
  }

  /**
   * Start the controller on this page with the browser's fetch, timers, and paint.
   *
   * @param {HTMLElement} element
   */
  function mount(element) {
    /** @type {ReturnType<typeof createController> | null} */
    let controller = null;
    const actions = {
      refresh: () => void controller?.requestRefresh(),
      accept: () => void controller?.acceptOffer(),
    };
    const live = document.createElement("span");
    live.className = "sr-only";
    live.setAttribute("aria-live", "polite");
    controller = createController(
      {
        async request(method, route, options) {
          /** @type {Record<string, string>} */
          const headers = {};
          if (method === "GET" && options.etag) {
            headers["if-none-match"] = options.etag;
          }
          if (method === "POST") {
            headers["content-type"] = "application/json";
          }
          const response = await fetch(route, {
            method,
            headers,
            cache: "no-store",
            body: method === "POST" ? JSON.stringify(options.body ?? {}) : undefined,
          });
          let body = null;
          if (response.status !== 304) {
            try {
              body = await response.json();
            } catch {
              body = null;
            }
          }
          return { status: response.status, etag: response.headers.get("etag"), body };
        },
        schedule: (callback, delayMs) => window.setTimeout(callback, delayMs),
        cancel: (handle) => window.clearTimeout(/** @type {number} */ (handle)),
        now: () => Date.now(),
        isVisible: () => document.visibilityState === "visible",
        render: (model) => paint(element, model, actions, live),
        reload: () => window.location.reload(),
        navigate: (href) => window.location.assign(href),
      },
      { shown: window.METABROWSER_SOURCE_PIN ?? null },
    );
    const listening = new AbortController();
    document.addEventListener("visibilitychange", controller.onVisibilityChange, {
      signal: listening.signal,
    });
    // A data request refused as pin_changed: ask the status route now, not at the next
    // slow poll, so the reload offer appears while the refusal is on screen.
    const polled = controller;
    window.addEventListener("metabrowser:pin-changed", () => void polled.poll(), {
      signal: listening.signal,
    });
    void controller.start();
    const mounted = controller;
    return Object.freeze({
      ...mounted,
      dispose() {
        listening.abort();
        mounted.dispose();
      },
    });
  }

  window.MetabrowserSourceFreshness = Object.freeze({
    FAST_POLL_MS,
    SLOW_POLL_MS,
    createController,
    describe,
    mount,
    relativeAge,
    selectionToOpen,
  });
})();

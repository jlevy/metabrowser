// Freshness of a served mirror: the quiet fetched label, following a branch to its
// new commit, and switching the pin.
//
// A page on a pinned revision polls /api/source/status while it is visible: quickly
// while a refresh runs, slowly otherwise, and with If-None-Match so an unchanged
// answer is a 304. When the mirror is older than the server's freshness window and
// nothing is refreshing, opening or revealing the page asks for one background
// refresh; the page never waits for it, and a refusal of that ask, which the reader did
// not make, says nothing. A page on one of the origin's branches also makes its own ask
// while it is visible, as often as the status says (`probe_every_s`): the server asks the
// origin where the branch is and fetches at once when it moved, so a push shows within
// seconds, and fetches the whole mirror once it is older than the window. That ask
// answers the status, so it stands in for the slow poll, and a hidden page sends none.
// A fetch nobody asked for, that one or the server's own while no page was looking, is
// quiet (`refresh_quiet`): the row says and announces nothing for it.
// A page on a branch or tag reads that ref as the mirror has it,
// as github.com shows a branch: when a refresh moves the ref, the server serves its new
// tip, and the page goes with it to the same address, by itself. Only a ref the pin does
// not follow, a pull request's head, is offered instead, and accepting switches the pin.
// When the server serves another ref than the one the page was rendered for -- another
// tab switched it, or a restart -- the row offers a reload.
//
// A repository folder that keeps a store of its checkout's origin has the row on every
// page, its working tree's too: what is fetched there is that store, never the checkout,
// and the row says so (`describe` with `checkout`). Its ref selector offers the reload.
//
// A commit the mirror lacks is an address not fetched too. The commit view hands it to
// `openMissingCommit`, which asks through the page's controller for the fetch such a
// commit waits for, waits for it to end, and then opens the commit or says, in the
// row's own words, that the origin did not have it or that the fetch could not run. A
// link in served content can send a reader to any commit's address, so a page asks for
// that fetch by itself only when something is older than the server's freshness window;
// inside it the view says the commit is not in the mirror as fetched, and offers Retry.
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
    not_found_or_private: "The repository was not found, or it is private and could not be read.",
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
    lender_missing:
      "The checkout this mirror borrows objects from is gone. Run metab again with --checkout and where it is now.",
    refreshing_elsewhere: "Another Metabrowser process is refreshing this mirror.",
    cancelled: "The refresh was stopped before it finished.",
    failed: "The refresh failed.",
  });

  // The outcomes whose words name the mirror, as a repository folder's row says them: what
  // was fetched there is the store Metabrowser keeps of the checkout's origin.
  /** @type {Readonly<Record<string, string>>} */
  const FOLDER_OUTCOME_DETAIL = Object.freeze({
    validation_failed:
      "The origin's default branch did not arrive in Metabrowser's store as a commit.",
    default_branch_unknown:
      "The origin's HEAD names no branch, so the store keeps the default branch it had.",
    store_unavailable: "Metabrowser's store of the origin could not be opened.",
    lender_missing:
      "The checkout can no longer lend its objects to Metabrowser's store of the origin.",
    refreshing_elsewhere: "Another Metabrowser process is refreshing this store.",
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
   * Whether a refresh the reader, or the page for them, is waiting on runs: any but one
   * the status calls quiet.
   *
   * @param {MetabrowserSourceStatus | null} status
   */
  function loudlyRefreshing(status) {
    return status?.refreshing === true && status.refresh_quiet !== true;
  }

  /**
   * What the label says and offers for one status. Pure.
   *
   * @param {MetabrowserSourceStatus | null} status
   * @param {{shown: MetabrowserSourcePage | null, nowMs: number, error?: string | null, checkout?: boolean}} page
   *   *shown* is the pin and ref the page was rendered for. *checkout* is whether the page
   *   is a repository folder's: what is fetched is then the store Metabrowser keeps of the
   *   checkout's origin, on every page of the folder, its working tree's too, and the row
   *   says so where a mirror's says "mirror".
   * @returns {MetabrowserSourceFreshnessModel}
   */
  function describe(status, page) {
    const error = page.error ?? null;
    const folder = page.checkout === true;
    if (status === null || !status.refreshable || (status.subject !== "git_revision" && !folder)) {
      return {
        visible: false,
        tone: "quiet",
        label: "",
        detail: "",
        offer: null,
        error,
        pull: null,
        follow: null,
      };
    }
    const age = relativeAge(status.last_fetch_at, page.nowMs);
    const outcome = status.last_outcome;
    const failed =
      outcome !== null && outcome.operation === "refresh" && !QUIET_OUTCOMES.has(outcome.outcome);
    // A fetch no reader asked for, the server's idle one or a visible page's once a
    // window, changes nothing the row says: no "Refreshing…", no disabled button, and
    // nothing announced, every minute, to a reader who pressed nothing. The mirror it is
    // fetching is no longer called stale either, since that is being seen to.
    const refreshing = loudlyRefreshing(status);
    /** @type {MetabrowserSourceFreshnessModel["tone"]} */
    let tone = status.stale && !status.refresh_quiet ? "stale" : "quiet";
    // What a failure is called: a folder's is its store's, never its checkout's.
    /** @param {string} code */
    const why = (code) =>
      (folder ? FOLDER_OUTCOME_DETAIL[code] : undefined) ??
      OUTCOME_DETAIL[code] ??
      OUTCOME_DETAIL.failed;
    let label = folder ? `Origin fetched ${age}` : `Fetched ${age}`;
    let detail = folder
      ? `Metabrowser's store of this checkout's origin was last fetched ${age}. The checkout itself is never fetched into.`
      : `The mirror was last fetched from its origin ${age}.`;
    if (refreshing) {
      tone = "refreshing";
      label = "Refreshing…";
      detail = folder
        ? `Fetching from the origin into Metabrowser's store. It was last fetched ${age}.`
        : `Fetching from the origin. The mirror was last fetched ${age}.`;
    } else if (failed) {
      tone = "warning";
      label = folder ? `Refresh failed · origin fetched ${age}` : `Refresh failed · fetched ${age}`;
      detail = folder
        ? `${why(outcome.outcome)} The origin's branches and tags are as last fetched, and the checkout is unchanged.`
        : `${why(outcome.outcome)} The pinned revision is still served from the mirror.`;
    } else if (outcome !== null && outcome.outcome === "refreshing_elsewhere") {
      detail = `${why("refreshing_elsewhere")} It was last fetched here ${age}.`;
    } else if (outcome !== null && outcome.outcome === "default_branch_unknown") {
      detail = `${detail} ${why("default_branch_unknown")}`;
    }
    const pull =
      typeof status.pull_request === "number"
        ? { href: `/pull/${status.pull_request}`, text: `Pull request #${status.pull_request}` }
        : null;
    // Not while something failed: a follow the server refused says why, with the reload
    // offer below, rather than claiming to update.
    const follow = error === null ? followTarget(status, page.shown) : null;
    if (follow !== null) {
      const name = status.ref_name ?? follow.ref;
      return {
        visible: true,
        tone: "refreshing",
        label: `Updating to ${name}…`,
        detail: `${name} is now at ${window.MetabrowserFormatters.shortCommit(follow.commit)}, and this page follows it.`,
        offer: null,
        error,
        pull,
        follow,
      };
    }
    const selection = status.selection_state ?? null;
    const retrySelection = selection === "fetch_failed" && !refreshing;
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
    // A folder's ref selector makes this offer itself, for its working tree's page too.
    if (
      !folder &&
      page.shown !== null &&
      (status.pin !== page.shown.pin || status.ref !== page.shown.ref)
    ) {
      offer = {
        kind: "reload",
        text: "The server now serves another revision",
        button: "Reload",
      };
    } else if (retrySelection) {
      offer = { kind: "retry", text: "Fetch the address again", button: "Retry" };
    } else if (
      !status.follows &&
      status.ref !== null &&
      status.latest !== null &&
      status.pin !== null &&
      status.latest !== status.pin
    ) {
      // A ref the pin does not follow, a pull request's head, moved: offer its new tip.
      offer = {
        kind: "switch",
        ref: status.ref,
        latest: status.latest,
        // "Now at", not "newer": a force-push can move a branch back. The commit follows
        // the words in the commit-ID face, as every line names one.
        text: `${status.ref_name ?? status.ref} is now at`,
        commit: window.MetabrowserFormatters.shortCommit(status.latest),
        button: "Switch",
      };
    } else if (status.ref !== null && status.ref_on_origin === false && !refreshing) {
      detail = `${detail} ${status.ref_name ?? status.ref} is no longer on the origin; its commits stay readable here.`;
    }
    // The attended pull request's page is one link away from every page on its pin.
    return { visible: true, tone, label, detail, offer, error, pull, follow: null };
  }

  /**
   * The branch or tag a page follows to a new commit, and that commit, or `null`. Pure.
   *
   * A page on a branch or tag reads that ref as the mirror has it, not one commit of it:
   * the server serves the ref's new tip itself once a fetch moves it (`follows`), and a
   * page still drawn for the commit before goes with it, to the same address. When the
   * server could not follow yet, status reports the tip as `latest`, and the page asks for
   * it. A page drawn for another ref than the one served was switched by another tab or
   * a restart, which a reload offer answers instead, and a commit or a pull request's head
   * does not move.
   *
   * @param {MetabrowserSourceStatus} status
   * @param {MetabrowserSourcePage | null} shown
   * @returns {MetabrowserSourceFollow | null}
   */
  function followTarget(status, shown) {
    if (shown === null || status.follows !== true || status.ref === null || status.pin === null) {
      return null;
    }
    if (status.ref !== shown.ref) {
      return null;
    }
    if (status.pin !== shown.pin) {
      return { ref: status.ref, commit: status.pin };
    }
    if (status.latest !== null && status.latest !== status.pin && !status.refreshing) {
      return { ref: status.ref, commit: status.latest };
    }
    return null;
  }

  // What the commit view says about a commit the mirror lacks. The states are the ones a
  // URL selection passes through, named for a commit instead of the page's address.
  /** @type {Readonly<Record<"pending" | "not_found" | "fetch_failed" | "no_mirror" | "pull_refused", string>>} */
  const MISSING_COMMIT_DETAIL = Object.freeze({
    pending: "This commit is not in the mirror yet; it opens when the fetch brings it.",
    not_found:
      "This commit is not in the mirror, and the fetch from the origin did not bring it: no branch or tag there reaches it.",
    fetch_failed: "This commit is not in the mirror, and it could not be fetched.",
    no_mirror: "This commit is not in the repository.",
    pull_refused:
      "The pull request's refresh, which brings its newer commits, was not queued: too many pull requests are being fetched; try again when one has finished.",
  });

  /**
   * What the commit view says and offers for a commit the mirror lacks. Pure.
   *
   * While a fetch it waits for runs, *page.phase* is `"fetching"`. Afterwards *status*
   * is the status then, *page.error* why the fetch could not be asked for or followed,
   * and *page.fetched* whether a fetch of the mirror's branches and tags ran for this
   * commit. Only then does the view say the origin does not offer it. When none ran --
   * the mirror was fetched inside the freshness window, or only the data beside it was
   * refreshed -- the view says only that the commit is not in the mirror as fetched.
   * *page.pullRefused* is that a full queue refused the attended pull request's refresh,
   * the only one that brings a newer head of it: the view then says so, and does not say
   * the origin lacks the commit.
   *
   * @param {MetabrowserSourceStatus | null} status
   * @param {{phase: "fetching" | "ended", nowMs: number, error?: string | null, fetched?: boolean, pullRefused?: boolean}} page
   * @returns {MetabrowserMissingCommitModel}
   */
  function describeMissingCommit(status, page) {
    if (page.phase === "fetching") {
      return {
        state: "pending",
        title: "Fetching this commit…",
        detail: MISSING_COMMIT_DETAIL.pending,
        retry: false,
      };
    }
    const error = page.error ?? null;
    if (status === null) {
      return {
        state: "fetch_failed",
        title: "Commit not fetched",
        detail: `${MISSING_COMMIT_DETAIL.fetch_failed} ${error ?? "The server did not answer."}`,
        retry: true,
      };
    }
    if (status.subject !== "git_revision" || !status.refreshable) {
      return {
        state: "not_found",
        title: "Commit not found",
        detail: MISSING_COMMIT_DETAIL.no_mirror,
        retry: false,
      };
    }
    const age = relativeAge(status.last_fetch_at, page.nowMs);
    if (error !== null) {
      return {
        state: "fetch_failed",
        title: `Commit not fetched · fetched ${age}`,
        detail: `${MISSING_COMMIT_DETAIL.fetch_failed} ${error}`,
        retry: true,
      };
    }
    const refused = page.pullRefused === true ? ` ${MISSING_COMMIT_DETAIL.pull_refused}` : "";
    if (page.fetched !== true) {
      return {
        state: "not_found",
        title: `Commit not found · fetched ${age}`,
        detail: `This commit is not in the mirror as fetched ${age}.${refused}`,
        retry: true,
      };
    }
    const outcome = status.last_outcome;
    if (
      outcome !== null &&
      outcome.operation === "refresh" &&
      !QUIET_OUTCOMES.has(outcome.outcome)
    ) {
      return {
        state: "fetch_failed",
        title: `Commit not fetched · fetched ${age}`,
        detail: `${MISSING_COMMIT_DETAIL.fetch_failed} ${OUTCOME_DETAIL[outcome.outcome] ?? OUTCOME_DETAIL.failed}`,
        retry: true,
      };
    }
    if (refused !== "") {
      // The branches and tags were fetched; the pull request's head, which may be the
      // commit, was not.
      return {
        state: "fetch_failed",
        title: `Commit not fetched · fetched ${age}`,
        detail: `${MISSING_COMMIT_DETAIL.fetch_failed}${refused}`,
        retry: true,
      };
    }
    return {
      state: "not_found",
      title: `Commit not found · fetched ${age}`,
      detail: MISSING_COMMIT_DETAIL.not_found,
      retry: true,
    };
  }

  // The commit route failed for a reason other than the commit being absent.
  /** @type {MetabrowserMissingCommitModel} */
  const COMMIT_LOAD_FAILED = Object.freeze({
    state: "failed",
    title: "Could not load this commit.",
    detail: "",
    retry: false,
  });

  /**
   * Show a commit the served mirror lacks: ask for the fetch it waits for, say so while
   * one runs, and then open the commit or say why not.
   *
   * *view.load* asks the server for the commit again: `"found"` once it has painted
   * it, `"missing"` when the server still does not have it, and `"failed"` when the
   * request failed, which is not an answer about the commit and is painted as a load
   * failure. *view.isCurrent* is false once the reader has gone elsewhere, and nothing
   * is painted after that. *options.retry* is the reader's own click, which fetches
   * however fresh the mirror is.
   *
   * @param {Pick<MetabrowserSourceFreshnessController, "fetchMissing">} controller
   * @param {MetabrowserMissingCommitView} view
   * @param {{retry?: boolean}} [options]
   * @returns {Promise<"found" | "not_found" | "fetch_failed" | "failed" | "superseded">}
   */
  async function openMissingCommit(controller, view, options = {}) {
    const ended = await controller.fetchMissing({
      retry: options.retry === true,
      waiting() {
        if (view.isCurrent()) {
          view.paint(describeMissingCommit(null, { phase: "fetching", nowMs: view.now() }));
        }
      },
    });
    if (!view.isCurrent()) {
      return "superseded";
    }
    // Asked again only when something ran that could have brought the commit, and was
    // followed to its end.
    if (ended.waited && ended.error === null) {
      const loaded = await view.load();
      if (loaded === "found") {
        return "found";
      }
      if (!view.isCurrent()) {
        return "superseded";
      }
      if (loaded === "failed") {
        view.paint(COMMIT_LOAD_FAILED);
        return "failed";
      }
    }
    const model = describeMissingCommit(ended.status, {
      phase: "ended",
      nowMs: view.now(),
      error: ended.error,
      fetched: ended.fetched,
      pullRefused: ended.pullRefused,
    });
    view.paint(model);
    return model.state === "not_found" ? "not_found" : "fetch_failed";
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
   * Whether two `/view/` addresses name the same place, a folder's trailing slash aside.
   *
   * @param {string} a
   * @param {string} b
   */
  function sameAddress(a, b) {
    const bare = (/** @type {string} */ value) =>
      value.length > "/view/".length ? value.replace(/\/$/, "") : value;
    return bare(a) === bare(b);
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
   * *options.checkout* is whether the page is a repository folder's (`describe`).
   *
   * @param {MetabrowserSourceFreshnessDependencies} deps
   * @param {{shown?: MetabrowserSourcePage | null, checkout?: boolean}} [options]
   */
  function createController(deps, options = {}) {
    const checkout = options.checkout === true;
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
    // Whether the page's own ask went out since the page was last shown: the first goes
    // with the first status, so a page opened or revealed learns of a push at once, and
    // the rest on the timer.
    let pageAskedWhileVisible = false;
    // Whether the server answers the page's own ask. One that refuses it is polled as a
    // page that sends none is, until the page is shown again.
    let pageAskAnswered = true;
    let switching = false;
    // A page follows its ref at most once: it leaves, or a refused follow says why and
    // waits for the reader's refresh rather than asking on every poll.
    let following = false;
    // Why the server refused a follow, which stays said, unlike a poll's own failure,
    // until the reader's refresh lets the page ask again.
    /** @type {string | null} */
    let followError = null;
    // A page goes to a selection that arrived at most once.
    let openedSelection = false;
    /** @type {string | null} */
    let error = null;
    // Callers waiting for the next poll or refresh request to end, or for disposal.
    /** @type {Array<() => void>} */
    let changeWaiters = [];

    function notifyChange() {
      const waiting = changeWaiters;
      changeWaiters = [];
      for (const resume of waiting) {
        resume();
      }
    }

    /** @returns {Promise<void>} */
    function nextChange() {
      return new Promise((resolve) => {
        changeWaiters.push(resolve);
      });
    }

    function render() {
      const model = describe(status, {
        shown,
        nowMs: deps.now(),
        error: error ?? followError,
        checkout,
      });
      if (model.follow !== null && !following && !disposed) {
        following = true;
        void follow(model.follow.ref);
      }
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

    /**
     * How long the page waits before its own ask, or null when it sends none: only a
     * page of a pin the server probes asks, and not one whose ask the server refused.
     *
     * @returns {number | null}
     */
    function pageAskMs() {
      const every = status?.refreshable && pageAskAnswered ? status.probe_every_s : null;
      return typeof every === "number" && every > 0 ? every * 1000 : null;
    }

    function scheduleNext() {
      clearTimer();
      if (disposed || !deps.isVisible()) {
        return;
      }
      // A poll that failed backs off to the slow interval: a server that stopped while
      // a refresh ran must not be asked every second for as long as the page is open.
      // While a refresh runs the status is polled quickly, and the asks wait for its end.
      // A quiet one is not waited for: the page keeps its own interval through it.
      const refreshing = loudlyRefreshing(status) && error === null;
      const askMs = refreshing || error !== null ? null : pageAskMs();
      const delay = askMs ?? (refreshing ? FAST_POLL_MS : SLOW_POLL_MS);
      timer = deps.schedule(() => {
        timer = null;
        void (askMs === null ? poll() : pageAsk());
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
          error = "The source's status could not be read.";
        }
      } catch {
        error = "The server did not answer.";
      } finally {
        polling = false;
      }
      if (disposed) {
        return;
      }
      if (status?.stale && !status.refreshing && !refreshAskedWhileVisible) {
        // A folder's page that shows nothing of the store asks as a page does, so the
        // fetch is quiet: nothing on the page can change when it ends.
        await ask(checkout && !status.follows ? { for: "page" } : {}, { own: true });
        return;
      }
      render();
      // The first status of a visible period: ask at once, unless the page is already
      // leaving for the commit its branch moved to. The ask is not waited for, and
      // whoever waits for this status is told first: the server can hold the ask for as
      // long as a probe takes, and a commit view waiting to ask for its own fetch, or to
      // say what it found, must not wait for that.
      if (
        error === null &&
        !status?.refreshing &&
        !following &&
        !pageAskedWhileVisible &&
        pageAskMs() !== null
      ) {
        notifyChange();
        void pageAsk();
        return;
      }
      scheduleNext();
      notifyChange();
    }

    /**
     * The page's own ask, sent only while it is visible: the server asks the origin where
     * the served branch is and fetches at once when it moved, and fetches a mirror older
     * than its freshness window. It answers the status, as a poll does, so the timer that
     * sends it is the page's poll too. The reader did not ask, so a refusal says nothing
     * and the page goes back to polling; a server that does not answer is reported as a
     * poll's is, and the slow poll finds it again.
     */
    async function pageAsk() {
      if (disposed || polling || !deps.isVisible()) {
        return;
      }
      polling = true;
      pageAskedWhileVisible = true;
      try {
        const response = await deps.request("POST", REFRESH_ROUTE, { body: { for: "page" } });
        if (disposed) {
          return;
        }
        const answer = /** @type {{status?: unknown} | null} */ (response.body);
        if (
          (response.status === 200 || response.status === 202) &&
          answer !== null &&
          isStatus(answer.status)
        ) {
          accept(answer.status);
          // The envelope may have changed; the next poll must not be answered by a 304.
          etag = null;
          error = null;
        } else {
          pageAskAnswered = false;
        }
      } catch {
        error = "The server did not answer.";
      } finally {
        polling = false;
      }
      if (disposed) {
        return;
      }
      render();
      scheduleNext();
      notifyChange();
    }

    /**
     * Ask for a refresh and take the status the server answers with. Answers what the
     * server did -- `"started"`, `"joined"`, or `"fresh"` -- or `null` when the request
     * was refused or failed. A refusal says why in the server's words when it gives them,
     * as when the queue of pull requests has no room for the attended one's refresh.
     *
     * @param {Record<string, unknown>} [body]
     * @returns {Promise<string | null>}
     */
    async function requestRefresh(body = {}) {
      following = false;
      followError = null;
      return (await ask(body, { own: false }))?.refresh ?? null;
    }

    /**
     * Go with the page's branch or tag to the commit the server serves for it now.
     *
     * Asks the pin route for the ref, which changes nothing once the server has followed
     * and serves the tip when it has not yet, naming the page's own `/view/` address, so
     * the answer says where the page is on the new commit: the same file or folder when
     * the commit has it, else the root. The page reloads in place when that is where it
     * is, which keeps its line anchor and scroll, and otherwise goes there. Any other
     * page, a pull request's or a commit's, reloads.
     *
     * @param {string} ref
     */
    async function follow(ref) {
      const view = deps.address();
      try {
        const response = await deps.request("POST", PIN_ROUTE, {
          body: view === null ? { ref } : { ref, view },
        });
        if (disposed) {
          return;
        }
        const answer = /** @type {{view_href?: unknown} | null} */ (response.body);
        if (response.status === 200) {
          const href = answer !== null ? answer.view_href : undefined;
          if (typeof href === "string" && view !== null && !sameAddress(href, view)) {
            deps.navigate(href);
          } else {
            deps.reload();
          }
          return;
        }
        followError = `Could not follow ${status?.ref_name ?? ref} to its new commit.`;
      } catch {
        if (disposed) {
          return;
        }
        followError = "The request to follow the branch failed.";
      }
      render();
    }

    /**
     * {@link requestRefresh}, answering the whole answer. *own* is the ask a stale page makes
     * by itself when it is opened or shown: as on a pull request's page, a refusal or a
     * failure of it says nothing, since the reader did not ask, and the row still offers a
     * refresh to press.
     *
     * `pullRefresh` is how a commit's fetch found the attended pull request's refresh,
     * which only that request's answer carries.
     *
     * @param {Record<string, unknown>} body
     * @param {{own: boolean}} options
     * @returns {Promise<{refresh: string, pullRefresh: string | null} | null>}
     */
    async function ask(body, options) {
      if (disposed || status === null || !status.refreshable) {
        notifyChange();
        return null;
      }
      refreshAskedWhileVisible = true;
      /** @type {{refresh: string, pullRefresh: string | null} | null} */
      let answered = null;
      try {
        const response = await deps.request("POST", REFRESH_ROUTE, { body });
        const answer =
          /** @type {{refresh?: unknown, pull_refresh?: unknown, status?: unknown, error?: unknown} | null} */ (
            response.body
          );
        if (
          (response.status === 202 || response.status === 200) &&
          answer !== null &&
          isStatus(answer.status)
        ) {
          accept(answer.status);
          // The envelope changed; the next poll must not be answered by a 304.
          etag = null;
          error = null;
          answered = {
            refresh: typeof answer.refresh === "string" ? answer.refresh : "started",
            pullRefresh: typeof answer.pull_refresh === "string" ? answer.pull_refresh : null,
          };
        } else if (!options.own) {
          const said = answer !== null && typeof answer.error === "string" ? answer.error : null;
          error = said === null ? "The refresh could not be started." : `Refresh refused: ${said}.`;
        }
      } catch {
        if (!options.own) {
          error = "The refresh request failed.";
        }
      }
      if (!disposed) {
        render();
        scheduleNext();
      }
      notifyChange();
      return answered;
    }

    /**
     * Ask for the fetch a commit the mirror lacks waits for, and answer when nothing is
     * refreshing any more: the status then, why the fetch could not be asked for or
     * followed, whether a fetch of the mirror ran (`fetched`), whether anything ran
     * that could have brought the commit (`waited`), and whether a full queue refused
     * the attended pull request's refresh (`pullRefused`).
     *
     * A page asks by itself only when something is older than the freshness window or
     * already refreshing; the server holds the mirror's fetch to the same floor, so a
     * request this code did not make cannot pass it. *options.retry* is a reader's
     * click and always fetches. The server joins a fetch of the mirror that is running
     * and answers `"fresh"` when it starts none, so a refresh of the data beside the
     * mirror is never taken for a fetch of its branches. *options.waiting* is called
     * once, when there is a refresh to wait for. The waiting rides the page's own
     * polls, so a hidden page waits until it is shown, and it ends at the first poll
     * that fails: a server that stopped is not waited for.
     *
     * @param {{retry?: boolean, waiting?: () => void}} [options]
     * @returns {Promise<MetabrowserSourceFetchEnd>}
     */
    async function fetchMissing(options = {}) {
      const retry = options.retry === true;
      // The first status may still be on its way.
      while (!disposed && status === null && error === null) {
        if (polling || !deps.isVisible()) {
          await nextChange();
        } else {
          await poll();
        }
      }
      if (disposed || status === null || !status.refreshable) {
        return { status, error, fetched: false, waited: false, pullRefused: false };
      }
      if (!retry && !status.stale && !status.refreshing) {
        return { status, error: null, fetched: false, waited: false, pullRefused: false };
      }
      const answered = await ask(retry ? { for: "commit", retry: true } : { for: "commit" }, {
        own: false,
      });
      if (disposed || answered === null || status === null) {
        return { status, error, fetched: false, waited: false, pullRefused: false };
      }
      const fetched = answered.refresh === "started" || answered.refresh === "joined";
      const pullRefused = answered.pullRefresh === "too_many";
      const waited = fetched || status.refreshing;
      if (status.refreshing) {
        options.waiting?.();
      }
      while (!disposed && status !== null && status.refreshing && error === null) {
        await nextChange();
      }
      return { status, error, fetched, waited, pullRefused };
    }

    async function acceptOffer() {
      const model = describe(status, { shown, nowMs: deps.now(), error: followError });
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
        error = "Could not switch to that commit.";
      } catch {
        error = "The switch request failed.";
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
      pageAskedWhileVisible = false;
      pageAskAnswered = true;
      void poll();
    }

    function dispose() {
      disposed = true;
      clearTimer();
      notifyChange();
    }

    return Object.freeze({
      start: () => poll(),
      poll,
      requestRefresh,
      fetchMissing,
      acceptOffer,
      onVisibilityChange,
      dispose,
      snapshot: () => ({
        status,
        etag,
        shown,
        timerPending: timer !== null,
        refreshAskedWhileVisible,
        pageAskedWhileVisible,
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
      parts.push(
        model.offer.kind === "switch"
          ? `${model.offer.text} ${model.offer.commit}`
          : model.offer.text,
      );
    }
    if (model.error !== null) {
      parts.push(model.error.replace(/\.$/, ""));
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
    label.dataset.tipText = `${model.detail} Press to refresh now.`;
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
      const here = window.location.pathname;
      if (here === model.pull.href || here.startsWith(`${model.pull.href}/`)) {
        pull.setAttribute("aria-current", "page");
      }
      children.push(pull);
    }
    if (model.offer !== null) {
      const offer = document.createElement("span");
      offer.className = "source-freshness-offer";
      const text = document.createElement("span");
      text.textContent = model.offer.text;
      if (model.offer.kind === "switch") {
        const commit = document.createElement("span");
        commit.className = "git-commit-sha";
        commit.textContent = model.offer.commit;
        text.append(" ", commit);
      }
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
    // A refresh the row shows running is a wait the event log hears of if it runs late, and
    // how it ended (static/event-reports.js, mb-9zp5). The reporter is an on-demand bundle,
    // so it is told when the wait began.
    /** @type {{handle: MetabrowserEventWait | null, ended: boolean} | null} */
    let refreshWait = null;
    /** @param {MetabrowserSourceFreshnessModel} model */
    const noteRefresh = (model) => {
      if (model.tone === "refreshing" && refreshWait === null) {
        const startedAt = performance.now();
        /** @type {{handle: MetabrowserEventWait | null, ended: boolean}} */
        const wait = { handle: null, ended: false };
        refreshWait = wait;
        window.MetabrowserAssets?.ensureAsset("event-reports").then(
          () => {
            if (!wait.ended) {
              wait.handle =
                window.metabrowser?.eventReports?.wait("source:refresh", { startedAt }) ?? null;
            }
          },
          () => {},
        );
      } else if (model.tone !== "refreshing" && refreshWait !== null) {
        refreshWait.ended = true;
        refreshWait.handle?.end(model.tone === "warning" ? "failed" : "ok");
        refreshWait = null;
      }
    };
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
        render: (model) => {
          noteRefresh(model);
          paint(element, model, actions, live);
        },
        reload: () => window.location.reload(),
        navigate: (href) => window.location.assign(href),
        address: () =>
          window.location.pathname.startsWith("/view/") ? window.location.pathname : null,
      },
      {
        shown: window.METABROWSER_SOURCE_PIN ?? null,
        checkout: Boolean(window.METABROWSER_SOURCE_CHECKOUT),
      },
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
    describeMissingCommit,
    mount,
    openMissingCommit,
    relativeAge,
    selectionToOpen,
  });
})();

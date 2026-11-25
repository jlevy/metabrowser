// The branch and tag selector of a served mirror, and of a served checkout.
//
// A page on a mirror's pin shows a compact button naming the ref it was rendered for.
// Opening it lists every one of the mirror's branches or tags from GET /api/source/refs,
// the default branch first and then newest first, with the served ref marked, narrowed
// by a filter box. The list draws only the rows near its view (`drawWindow`), so what it
// draws costs the same over ten thousand branches as over ten. Choosing a ref
// switches the served pin with POST /api/source/pin -- a same-origin JSON request
// behind the server's guard -- and names the page's own /view/ address, so the answer
// says where the page goes: the same file or folder when the new revision has it,
// else the root.
//
// A folder that is a repository's root has the same selector, on the same two routes.
// Folder mode is a superset of mirror mode: any branch or tag of the checkout is shown
// as a mirror shows one, a pinned revision read from its Git objects, and nothing is
// checked out. What a checkout adds is told by the page (`METABROWSER_SOURCE_CHECKOUT`)
// and by the listing:
//
// - a Working tree row above the refs, the live files on disk, which is what a folder
//   opens on and the only choice that is not a ref. It names the folder by its path, and
//   has no commit or age: what is on disk is not one commit. The checked-out branch is a
//   ref like any other and shows its last commit, so it is marked "checked out", not
//   "current";
// - a third list, Remotes, its remote-tracking branches, beside its own branches and
//   its tags;
// - an offer to reload when the server comes to serve something else, which a mirror's
//   freshness row makes and a checkout's page has no such row to make;
// - its origin's branches and tags from a store Metabrowser keeps beside the checkout
//   (`origin` in the listing; metabrowser/checkout_store.py). Once that store exists, the
//   Remotes list has the origin's branches as Metabrowser last fetched them, in place of
//   the checkout's own `origin/*`, and the Tags list the origin's tags; a line under the
//   list says so and when, or why the origin is not fetched. The origin's default branch
//   is first there and marked. A row there whose branch the reader's own checkout has
//   at another commit, or not at all, says so (`ownDifference`): "yours differs" where
//   the checkout's own `origin/<branch>` is not where the origin's is, which is a branch
//   the reader has not fetched since it moved, or has pushed since. An open list of a
//   checkout, once it shows Remotes or Tags, makes a visible page's own ask once
//   (`{"for": "page"}`), which fetches a store older than the server's freshness window,
//   and asks for the list again while that runs.
//
// The selector chooses the source of the Files tab. The server draws its row above the
// Files toolbar (server.py); the Pulls and Commits tabs do not follow it. Each listed ref shows its commit as the history
// does, Git's short ID in the commit-ID face, and the commit's age by the shared
// formatter (docs/design-system.md, "Age").
//
// A branch that is the head of a pull request shows it on a second line: its state's
// icon, its number, and its title, from the listing's `pulls`, which the server reads from
// what the repository's provider has cached and never fetches. The filter finds a branch
// by its pull request's number or title too, which the server does, so the list the page
// shows is the server's. While the provider is still filling its cache the listing says
// so, and an open list asks again (`PULLS_POLL_MS`) until it is full. A row with a pull
// request is taller than one without, so the window is placed by each row's own offset
// (`rowOffsets`), not by one height.
//
// Every decision lives here without a DOM: `describe` turns the selector's state into
// what it shows, and `createSelector` owns loading, filtering, stale answers, and the
// switch through injected dependencies. `mount` is the browser glue that supplies real
// fetch, timers, focus, and paint. tests/dom/source-ref-selector-session.js runs the
// same functions from the command line.

(() => {
  const REFS_ROUTE = "/api/source/refs";
  const PIN_ROUTE = "/api/source/pin";
  const REFRESH_ROUTE = "/api/source/refresh";
  const VIEW_PREFIX = "/view/";
  // A mirror keeps its origin's branches where a checkout keeps a remote's: it has no
  // branches of its own, so they are simply its branches.
  const BRANCH_PREFIX = "refs/remotes/origin/";
  const TAG_PREFIX = "refs/tags/";
  const LOCAL_BRANCH_PREFIX = "refs/heads/";
  const REMOTE_PREFIX = "refs/remotes/";
  const WORKING_TREE = "Working tree";
  const PULL_HEAD = /^refs\/pull\/([1-9][0-9]{0,9})\/head$/;
  // Typing narrows the list through the server, which reads the mirror's refs once per
  // request; waiting for a short pause in typing asks once per word, not per key.
  const FILTER_DELAY_MS = 150;
  // While the server says it is still filling its cache of pull requests, an open list asks
  // again at this interval: the answer is kept under the cache's revision, so each ask
  // reads one small file and runs no Git, and the rows gain their pull requests as the
  // pages arrive. It stops when the list closes or the server says the cache is full.
  const PULLS_POLL_MS = 3000;
  // A pull request's title is cut to what one line holds; the row's tooltip carries the
  // rest, and when more than one pull request names a branch, the others.
  const PULL_MORE_LIMIT = 5;
  // What the list says beside a filter's finds while the server has cached only some of the
  // repository's pull requests: a number or a title may match more branches than it lists.
  const PULLS_INCOMPLETE = "Some pull requests are still loading, so more branches may match.";
  // Rows drawn beyond the list's view on either side, so a scroll or a key finds the next
  // rows drawn already. The list draws the rows in its view and these, whatever the
  // listing holds, and places each by its index over a box as tall as all of them
  // (`drawWindow`). Drawing every row instead cost the same main-thread time per row
  // whatever was in view. Measured 2026-11-19 in headless Chrome 152 on an M1 Pro at a
  // load average of 17 to 19, building the rows and then laying them out: 1,301 rows took
  // 8 and 54 ms, and 10,001 took 57 and 430 ms and 320 ms more to the next frame, while
  // `content-visibility: auto` on each row made 10,001 slower, 0.8 to 1.0 s and 2.6 to
  // 2.9 s. Drawing this window instead, 32 rows at the list's 320 px, ran no task over
  // 50 ms: opening painted in a median 68 ms over 1,301 branches, and 0.25 and 0.67 s
  // over 10,001 with packed and loose refs, of which fetching the listing alone took 30
  // ms, 0.21 s, and 0.57 s; End, each ArrowDown, and a scroll to the foot each reached the
  // next frame in 30 to 34 ms (same machine, a load average of 17 to 33). Twenty rows is
  // 580 px, more than the list's tallest view, so a scroll of a whole view between two
  // frames, before its scroll event draws, still lands on rows already drawn.
  const ROWS_OVERSCAN = 20;

  /** @type {Readonly<Record<MetabrowserSourceRefKind, string>>} */
  const KIND_PLURAL = Object.freeze({
    branch: "branches",
    tag: "tags",
    remote: "remote branches",
  });
  /** @type {Readonly<Record<MetabrowserSourceRefKind, string>>} */
  const KIND_LABEL = Object.freeze({ branch: "Branches", remote: "Remotes", tag: "Tags" });
  /** The lists each subject has; the listing says the same in `kinds`.
   * @type {readonly MetabrowserSourceRefKind[]} */
  const MIRROR_KINDS = Object.freeze(["branch", "tag"]);
  /** @type {readonly MetabrowserSourceRefKind[]} */
  const CHECKOUT_KINDS = Object.freeze(["branch", "remote", "tag"]);

  /**
   * What the button says for the ref and commit a page was rendered for. Pure.
   *
   * *checkout* is whether the page is a checkout's. Its page with no pin shows the
   * working tree; its branches are its own, and a remote's keep the remote's name.
   *
   * @param {MetabrowserSourcePage | null} shown
   * @param {boolean} [checkout]
   * @returns {{kind: string, name: string}}
   */
  function shownLabel(shown, checkout = false) {
    if (shown === null) {
      return { kind: checkout ? WORKING_TREE : "Revision", name: "" };
    }
    const ref = shown.ref ?? "";
    if (checkout && ref.startsWith(LOCAL_BRANCH_PREFIX)) {
      return { kind: "Branch", name: ref.slice(LOCAL_BRANCH_PREFIX.length) };
    }
    if (checkout && ref.startsWith(REMOTE_PREFIX)) {
      return { kind: "Remote branch", name: ref.slice(REMOTE_PREFIX.length) };
    }
    if (ref.startsWith(BRANCH_PREFIX)) {
      return { kind: "Branch", name: ref.slice(BRANCH_PREFIX.length) };
    }
    if (ref.startsWith(TAG_PREFIX)) {
      return { kind: "Tag", name: ref.slice(TAG_PREFIX.length) };
    }
    const pull = PULL_HEAD.exec(ref);
    if (pull !== null) {
      return { kind: "Pull request", name: `#${pull[1]}` };
    }
    // As every row names a commit (`shortCommit`).
    return { kind: "Commit", name: window.MetabrowserFormatters.shortCommit(shown.pin) };
  }

  /**
   * @param {unknown} value
   * @returns {value is MetabrowserSourceRefListing}
   */
  function isListing(value) {
    if (value === null || typeof value !== "object") {
      return false;
    }
    const record = /** @type {Record<string, unknown>} */ (value);
    return (
      (record.kind === "branch" || record.kind === "tag" || record.kind === "remote") &&
      typeof record.query === "string" &&
      Array.isArray(record.refs)
    );
  }

  /**
   * What a row of the origin's branches says where the reader's own remote-tracking
   * branch is not at the row's commit, or `null` where it is. Pure.
   *
   * The row is the origin's branch as Metabrowser last fetched it into its own store;
   * the checkout's `origin/<branch>` is where the reader's own last fetch left it. The
   * server says only that the two differ, and where the checkout's is: which is ahead
   * needs a walk of the history between them, which the listing does not make. The
   * commits' dates are in the listing, so the tooltip says which was committed later.
   *
   * @param {MetabrowserSourceRef} row
   * @returns {{text: string, tip: string} | null}
   */
  function ownDifference(row) {
    const own = row.checkout;
    if (own === undefined || own === null) {
      return null;
    }
    if (own.commit === null) {
      return {
        text: "not in checkout",
        tip: `Your checkout has no ${row.name} of its own. This row is the origin's, as last fetched.`,
      };
    }
    const mine = own.committed_at;
    const theirs = row.committed_at;
    const where =
      mine === null || theirs === null || mine === theirs
        ? "another commit"
        : mine < theirs
          ? "an earlier commit by date"
          : "a later commit by date";
    return {
      text: "yours differs",
      tip: `Your checkout's ${row.name} is at ${where}. This row is the origin's, as last fetched.`,
    };
  }

  /**
   * What the selector shows for one state. Pure.
   *
   * @param {MetabrowserSourceRefSelectorState} state
   * @returns {MetabrowserSourceRefSelectorModel}
   */
  function describe(state) {
    const checkout = state.checkout === true;
    const workingBranch = checkout && state.shown === null ? state.workingBranch : undefined;
    const label = workingBranch
      ? { kind: "Branch", name: workingBranch }
      : shownLabel(state.shown, checkout);
    const plural = KIND_PLURAL[state.kind];
    const listing = state.listing;
    // A mirror's branch is its origin's, a remote chip; a checkout's own is a local one.
    const chip =
      state.kind === "tag" ? "tag" : state.kind === "branch" && checkout ? "local" : "remote";
    /** @type {MetabrowserSourceRefSelectorModel["rows"]} */
    const rows =
      listing === null
        ? []
        : listing.refs.map((row) => ({
            name: row.name,
            ref: row.ref,
            commit: window.MetabrowserFormatters.shortCommit(row.commit),
            committedAt: row.committed_at,
            default: row.default,
            checkedOut: row.checked_out === true,
            current: row.current,
            chip,
            own: ownDifference(row),
            pulls: (row.pulls ?? []).map((pull) => ({
              number: pull.number,
              title: pull.title,
              state: pull.state,
            })),
            // How many the branch heads, of which the row lists the first few.
            pullsTotal: row.pulls_total ?? row.pulls?.length ?? 0,
          }));
    let note = "";
    if (state.loading && listing === null) {
      note = `Loading ${plural}…`;
    } else if (listing !== null && listing.refs.length === 0) {
      note =
        listing.query === ""
          ? `The ${checkout ? "checkout" : "mirror"} has no ${plural}.`
          : `No ${plural} match.`;
    }
    // The working tree is a checkout's alone, and is no ref: it is listed whatever the
    // list and the filter show, named by the folder's path. Until the first listing says
    // whether it is served, the page does: a checkout's page with no pin shows it. The
    // branch it is on is not repeated here: the Branches list marks it "checked out".
    const tree = listing?.working_tree ?? null;
    const location = tree?.location ?? "";
    // The folder's own name, which the row keeps whole: the path ends with it, in the
    // platform's separator, except at the home directory, whose path is `~` alone.
    const name = tree?.name ?? "";
    const cut = name !== "" && location.endsWith(name) ? location.length - name.length : 0;
    /** @type {MetabrowserSourceRefSelectorModel["workingTree"]} */
    const workingTree = !checkout
      ? null
      : {
          current: tree !== null ? tree.current : state.shown === null,
          location,
          directory: location.slice(0, cut),
          base: location.slice(cut),
        };
    // The filter finds a branch by its pull request's number or title once the server has
    // them; a tag has none.
    const pullsReady = listing?.pull_requests?.state === "ready";
    // A filter finds only the pull requests the server has cached, so while it has some of
    // them it says so, beside what the filter found (mb-tjbm review A8).
    if (pullsReady && listing?.pull_requests?.complete === false && state.query !== "") {
      note = note === "" ? PULLS_INCOMPLETE : `${note} ${PULLS_INCOMPLETE}`;
    }
    // What the list says of the store its origin's refs are read from: only for the lists
    // that read it, a checkout's remote-tracking branches and its tags.
    /** @type {MetabrowserSourceRefSelectorModel["origin"]} */
    let origin = null;
    const store = listing?.origin ?? null;
    if (checkout && store !== null && state.kind !== "branch") {
      const what = state.kind === "tag" ? "tags" : "branches";
      if (store.state === "ready") {
        origin = {
          text: `The origin's ${what} are as Metabrowser last fetched them`,
          fetchedAt: store.last_fetch_at,
          tone: "quiet",
        };
      } else if (store.state === "acquiring") {
        origin = {
          text: `Fetching the origin's ${what}. Until then these are the checkout's own.`,
          fetchedAt: null,
          tone: "quiet",
        };
      } else {
        // The store's reason (`store.detail`) is the answer's, for an agent.
        origin = {
          text: "Origin not fetched. These are the checkout's own.",
          fetchedAt: null,
          tone: "warning",
        };
      }
    }
    return {
      button: label.name === "" ? label.kind : `${label.kind}: ${label.name}`,
      // A pull request's number, which the button sets in its own weight
      // (docs/design-system.md, "Pull Request Numbers").
      pullNumber: label.kind === "Pull request" ? label.name : null,
      // A bare commit's ID, which the button sets in the commit-ID face.
      commitId: label.kind === "Commit" ? label.name : null,
      selectedRef:
        label.kind === "Branch" || label.kind === "Tag" || label.kind === "Remote branch"
          ? {
              name: label.name,
              label: label.name,
              ref: workingBranch
                ? LOCAL_BRANCH_PREFIX + workingBranch
                : (state.shown?.ref ?? undefined),
              kind:
                label.kind === "Tag"
                  ? "tag"
                  : label.kind === "Branch" && checkout
                    ? "local"
                    : "remote",
            }
          : null,
      open: state.open,
      kind: state.kind,
      kinds: [...(listing?.kinds ?? (checkout ? CHECKOUT_KINDS : MIRROR_KINDS))],
      query: state.query,
      filterLabel: pullsReady ? `Filter ${plural} or pull requests` : `Filter ${plural}`,
      pullRequests: listing?.pull_requests ?? null,
      loading: state.loading,
      switching: state.switching,
      workingTree,
      rows,
      note,
      origin,
      error: state.error,
      removed: state.removed === true,
      stale:
        state.stale === null || state.stale === undefined
          ? null
          : state.stale === ""
            ? "The server now shows the working tree"
            : "The server now shows another revision",
    };
  }

  /**
   * Where a key moves focus among the list's rows. Pure.
   *
   * *index* is the focused row, or -1 for the filter box; the answer is the row to
   * focus, -1 for the filter box, or `null` when the key does not move focus there.
   * Down from the filter box enters the list and up from the first row leaves it;
   * Home and End jump within the list but are left to the filter box's own caret.
   *
   * @param {string} key
   * @param {number} index
   * @param {number} count
   * @returns {number | null}
   */
  function moveRow(key, index, count) {
    if (count === 0) {
      return null;
    }
    if (index < 0) {
      return key === "ArrowDown" ? 0 : null;
    }
    switch (key) {
      case "ArrowDown":
        return Math.min(index + 1, count - 1);
      case "ArrowUp":
        return index - 1;
      case "Home":
        return 0;
      case "End":
        return count - 1;
      default:
        return null;
    }
  }

  /**
   * Where each of *rows* sits in the list, and where the last one ends. A row with a pull
   * request is *tall* high and any other *plain*, so the answer has one more entry than
   * there are rows: row *at* is from `offsets[at]` to `offsets[at + 1]`. Pure.
   *
   * @param {ReadonlyArray<{pulls: ReadonlyArray<unknown>}>} rows
   * @param {number} plain A row with no pull request.
   * @param {number} tall A row with one.
   * @returns {number[]}
   */
  function rowOffsets(rows, plain, tall) {
    /** @type {number[]} */
    const offsets = new Array(rows.length + 1);
    let top = 0;
    for (let at = 0; at < rows.length; at += 1) {
      offsets[at] = top;
      top += rows[at].pulls.length > 0 ? tall : plain;
    }
    offsets[rows.length] = top;
    return offsets;
  }

  /**
   * How many rows begin before *y*, or at it with *atIt*: the index of the first row that
   * begins after it. Pure.
   *
   * @param {readonly number[]} offsets
   * @param {number} y
   * @param {boolean} [atIt]
   * @returns {number}
   */
  function rowsBefore(offsets, y, atIt = false) {
    let low = 0;
    let high = offsets.length - 1;
    while (low < high) {
      const middle = (low + high) >> 1;
      if (atIt ? offsets[middle] <= y : offsets[middle] < y) {
        low = middle + 1;
      } else {
        high = middle;
      }
    }
    return low;
  }

  /**
   * Which rows a list scrolled to *scrollTop* draws in a view *viewHeight* tall, over rows
   * placed at *offsets* (`rowOffsets`): those in view and ROWS_OVERSCAN more on either
   * side, as the range from *start* up to *end*, and the row at *roving*, the one that
   * takes Tab, as *also* when the range leaves it out, else -1. That row may have focus,
   * and Tab from the filter box goes to it, so it stays drawn however far the list scrolls
   * from it. Until a row has been measured, every offset is 0 and the first rows are
   * drawn, as many as the overscan on both sides. Pure.
   *
   * @param {readonly number[]} offsets
   * @param {number} scrollTop
   * @param {number} viewHeight
   * @param {number} roving
   * @returns {{start: number, end: number, also: number}}
   */
  function rowWindow(offsets, scrollTop, viewHeight, roving) {
    const count = offsets.length - 1;
    if (count <= 0) {
      return { start: 0, end: 0, also: -1 };
    }
    let start = 0;
    let end = Math.min(count, 2 * ROWS_OVERSCAN);
    if (offsets[count] > 0) {
      // The row at the view's top is the last that begins at or before it, and the view's
      // foot is in the last row that begins before it.
      const first = rowsBefore(offsets, scrollTop, true) - 1;
      const last = rowsBefore(offsets, scrollTop + viewHeight);
      start = Math.max(0, Math.min(count, first - ROWS_OVERSCAN));
      end = Math.max(start, Math.min(count, last + ROWS_OVERSCAN));
    }
    const outside = roving >= 0 && roving < count && (roving < start || roving >= end);
    return { start, end, also: outside ? roving : -1 };
  }

  /**
   * Whether two answers of the refs route say the same, so an answer asked for again while
   * the server fills its pull requests need not be drawn when nothing in it moved. Pure.
   *
   * @param {MetabrowserSourceRefListing | null} a
   * @param {MetabrowserSourceRefListing | null} b
   * @returns {boolean}
   */
  function sameListing(a, b) {
    if (a === null || b === null) {
      return a === b;
    }
    const pa = a.pull_requests;
    const pb = b.pull_requests;
    if (
      a.kind !== b.kind ||
      a.query !== b.query ||
      a.pin !== b.pin ||
      a.ref !== b.ref ||
      a.refs.length !== b.refs.length ||
      (pa?.state ?? null) !== (pb?.state ?? null) ||
      pa?.complete !== pb?.complete ||
      pa?.refreshing !== pb?.refreshing ||
      JSON.stringify(a.origin ?? null) !== JSON.stringify(b.origin ?? null) ||
      JSON.stringify(a.working_tree) !== JSON.stringify(b.working_tree)
    ) {
      return false;
    }
    for (let at = 0; at < a.refs.length; at += 1) {
      const x = a.refs[at];
      const y = b.refs[at];
      if (
        x.ref !== y.ref ||
        x.name !== y.name ||
        x.commit !== y.commit ||
        x.committed_at !== y.committed_at ||
        x.default !== y.default ||
        x.checked_out !== y.checked_out ||
        x.current !== y.current ||
        JSON.stringify(x.checkout ?? null) !== JSON.stringify(y.checkout ?? null) ||
        (x.pulls_total ?? 0) !== (y.pulls_total ?? 0) ||
        pullsSignature(x.pulls ?? []) !== pullsSignature(y.pulls ?? [])
      ) {
        return false;
      }
    }
    return true;
  }

  /**
   * What a row's pull requests say, as one string to compare. Pure.
   *
   * @param {ReadonlyArray<{number: number, title: string, state: string}>} pulls
   * @returns {string}
   */
  function pullsSignature(pulls) {
    return pulls.map((pull) => `${pull.number}\0${pull.state}\0${pull.title}`).join("\n");
  }

  /**
   * Whether two lists of model rows are the same refs drawn the same way, whatever pull
   * requests they have: the rows a drawn list can keep as they are, and patch. Pure.
   *
   * @param {ReadonlyArray<MetabrowserSourceRefSelectorModel["rows"][number]>} a
   * @param {ReadonlyArray<MetabrowserSourceRefSelectorModel["rows"][number]>} b
   * @returns {boolean}
   */
  function sameRefLines(a, b) {
    if (a.length !== b.length) {
      return false;
    }
    for (let at = 0; at < a.length; at += 1) {
      const x = a[at];
      const y = b[at];
      if (
        x.ref !== y.ref ||
        x.name !== y.name ||
        x.commit !== y.commit ||
        x.committedAt !== y.committedAt ||
        x.default !== y.default ||
        x.checkedOut !== y.checkedOut ||
        x.current !== y.current ||
        x.chip !== y.chip ||
        (x.own?.tip ?? "") !== (y.own?.tip ?? "")
      ) {
        return false;
      }
    }
    return true;
  }

  /**
   * Where a list scrolls to when its rows are laid out again, as they are when pull
   * requests arrive for rows above the view and make those rows taller. Pure.
   *
   * The reader keeps what they were looking at: the row at the top of the view stays
   * where it was in the view, by its ref; a list scrolled to its foot, as End leaves it,
   * stays at its foot; and a row that had focus and was in view is in view still.
   *
   * *before* and *after* are each the refs in order and where each sits
   * (`rowOffsets`); *top* and *view* are the list's scroll position and its height;
   * *focused* is the ref of the row that has focus, or null.
   *
   * @param {{refs: readonly string[], offsets: readonly number[]}} before
   * @param {{refs: readonly string[], offsets: readonly number[]}} after
   * @param {number} top
   * @param {number} view
   * @param {string | null} focused
   * @returns {number}
   */
  function anchoredScroll(before, after, top, view, focused) {
    const was = before.offsets[before.refs.length] ?? 0;
    const now = after.offsets[after.refs.length] ?? 0;
    const most = Math.max(0, now - view);
    if (!(was > 0) || !(now > 0) || before.refs.length === 0) {
      return Math.min(top, most);
    }
    if (top > 0 && top + view >= was - 0.5) {
      return most;
    }
    const first = Math.max(0, rowsBefore(before.offsets, top, true) - 1);
    const anchor = after.refs.indexOf(before.refs[first]);
    let next = anchor < 0 ? top : after.offsets[anchor] + (top - before.offsets[first]);
    if (focused !== null) {
      const was_ = before.refs.indexOf(focused);
      const is = after.refs.indexOf(focused);
      const visible =
        was_ >= 0 && before.offsets[was_ + 1] > top && before.offsets[was_] < top + view;
      if (visible && is >= 0) {
        if (after.offsets[is + 1] > next + view) {
          next = after.offsets[is + 1] - view;
        }
        if (after.offsets[is] < next) {
          next = after.offsets[is];
        }
      }
    }
    return Math.max(0, Math.min(next, most));
  }

  /**
   * Why a switch was refused, the way the selector says it.
   *
   * @param {unknown} body
   * @param {boolean} checkout Whether the refs are a checkout's, which fetches nothing.
   */
  function switchFailure(body, checkout) {
    const record = /** @type {{code?: unknown} | null} */ (
      body !== null && typeof body === "object" ? body : null
    );
    const code = record !== null && typeof record.code === "string" ? record.code : "";
    if (code === "selection_pending") {
      return "That branch or tag is still being fetched. Choose it again shortly.";
    }
    if (code === "selection_not_found") {
      return `That branch or tag is no longer in the ${checkout ? "checkout" : "mirror"}.`;
    }
    // The status and code are the answer's, for an agent (docs/design-system-messages.md).
    return "Could not switch. Try again.";
  }

  /**
   * The loading, filtering, and switching state machine for one page.
   *
   * *options.shown* is the pin and ref the page was rendered for, which the server
   * writes into a pin's page. A switch that leaves the server serving exactly that
   * only closes the selector; any other answer opens where the server says.
   * *options.checkout* is whether the page is a checkout's: with no pin it shows the
   * working tree, which is then what a switch is compared with.
   *
   * @param {MetabrowserSourceRefSelectorDependencies} deps
   * @param {{shown?: MetabrowserSourcePage | null, checkout?: boolean, workingBranch?: string}} [options]
   */
  function createSelector(deps, options = {}) {
    const checkout = options.checkout === true;
    /** @type {MetabrowserSourceRefSelectorState} */
    const state = {
      shown: options.shown ?? null,
      open: false,
      kind: "branch",
      query: "",
      listing: null,
      loading: false,
      switching: false,
      error: null,
      ...(checkout ? { checkout, workingBranch: options.workingBranch, stale: null } : {}),
    };
    // Each listing request takes the next number; only the newest one's answer counts,
    // so a slow answer to an older filter never replaces a newer one. A newer request,
    // closing, or disposal also aborts the older one, so the server is not left reading
    // refs for a list nobody will see.
    let requested = 0;
    /** @type {AbortController | null} */
    let inflight = null;
    /** @type {unknown} */
    let filterTimer = null;
    /** The wait before the next ask for pull requests the server was still filling. */
    /** @type {unknown} */
    let pullsTimer = null;
    // Whether the visible page's own ask went out since the list was opened.
    let askedForOrigin = false;
    let disposed = false;

    function render() {
      if (!disposed) {
        deps.render(describe(state));
      }
    }

    function clearFilterTimer() {
      if (filterTimer !== null) {
        deps.cancel(filterTimer);
        filterTimer = null;
      }
    }

    function clearPullsTimer() {
      if (pullsTimer !== null) {
        deps.cancel(pullsTimer);
        pullsTimer = null;
      }
    }

    function abortInflight() {
      inflight?.abort();
      inflight = null;
    }

    /** Ask again after PULLS_POLL_MS while the server fills its pull requests, or fetches
     * the store a checkout's origin is listed from. */
    function watchPulls() {
      clearPullsTimer();
      const filling =
        state.listing?.pull_requests?.refreshing === true ||
        state.listing?.origin?.refreshing === true;
      if (disposed || !state.open || !filling) {
        return;
      }
      pullsTimer = deps.schedule(() => {
        pullsTimer = null;
        void load(true);
      }, PULLS_POLL_MS);
    }

    /**
     * Ask for the list. *quiet* is the ask for pull requests the server was filling: it
     * shows nothing while it waits, and a refusal leaves the rows as they are.
     *
     * @param {boolean} [quiet]
     */
    async function load(quiet = false) {
      // A quiet ask never stands in for one the reader waits on: a filter still in its
      // pause asks for itself, with what was typed, and a quiet ask that failed meanwhile
      // would have dropped it (mb-tjbm review A9).
      if (quiet && filterTimer !== null) {
        watchPulls();
        return;
      }
      if (!quiet) {
        clearFilterTimer();
      }
      clearPullsTimer();
      abortInflight();
      requested += 1;
      const ticket = requested;
      const controller = new AbortController();
      inflight = controller;
      if (!quiet) {
        state.loading = true;
        render();
      }
      const asked = { kind: state.kind, query: state.query };
      const params = new URLSearchParams({ kind: state.kind });
      if (state.query !== "") {
        params.set("q", state.query);
      }
      /** @type {MetabrowserSourceRefListing | null} */
      let listing = null;
      /** @type {string | null} */
      let error = null;
      let gone = false;
      try {
        const response = await deps.request(
          "GET",
          `${REFS_ROUTE}?${params}`,
          undefined,
          controller.signal,
        );
        const refusal = /** @type {{code?: unknown, error?: unknown} | null} */ (
          response.body !== null && typeof response.body === "object" ? response.body : null
        );
        if (response.status === 200 && isListing(response.body)) {
          listing = response.body;
        } else if (checkout && refusal?.code === "unsupported_for_subject") {
          // The server drew the row for a folder holding a `.git`, and Git does not take
          // that folder for a repository's root: there is nothing to choose among, so
          // the row goes, as the Commits tab does when discovery says the same.
          gone = true;
        } else if (refusal?.code === "unsupported_git") {
          // Which Git is needed, and why, is the answer's `error`, for an agent.
          error = "Git on this machine is too old to list these. Update Git to see them.";
        } else {
          // The status is the answer's, which the network panel shows.
          error = `The ${KIND_PLURAL[state.kind]} could not be listed. Try again.`;
        }
      } catch {
        error = "The server did not answer.";
      }
      if (disposed || ticket !== requested) {
        return;
      }
      inflight = null;
      if (quiet) {
        // A refusal, or an answer for a list the reader has since left, leaves the rows.
        if (listing === null || asked.kind !== state.kind || asked.query !== state.query) {
          return;
        }
        // Nothing moved, so nothing is drawn: the rows keep their focus, their tooltips,
        // and a press in progress (mb-tjbm review A2).
        if (sameListing(state.listing, listing)) {
          watchPulls();
          return;
        }
      }
      state.loading = false;
      state.listing = listing;
      state.error = error;
      if (gone) {
        state.open = false;
        state.removed = true;
      }
      render();
      watchPulls();
    }

    /**
     * A visible page's own ask, for a checkout that keeps a store of its origin: the server
     * fetches the store when it is older than its freshness window, and makes it when it
     * has none. Sent once each time the list opens, with the first list that reads the
     * store, the Remotes or the Tags, and never
     * waited for: when the server says a fetch runs, the list is asked for again and then
     * watched until it ends. The reader did not ask, so a refusal says nothing.
     */
    async function askForOrigin() {
      // Only for a list that reads the store, the origin's branches or its tags: the
      // checkout's own branches are read from the checkout, and a fetch moves none.
      if (
        !checkout ||
        disposed ||
        !state.open ||
        askedForOrigin ||
        state.kind === "branch" ||
        (state.listing?.origin ?? null) === null
      ) {
        return;
      }
      askedForOrigin = true;
      try {
        const response = await deps.request("POST", REFRESH_ROUTE, { for: "page" });
        const answer = /** @type {{refresh?: unknown} | null} */ (
          response.body !== null && typeof response.body === "object" ? response.body : null
        );
        const started = answer?.refresh === "started" || answer?.refresh === "joined";
        if (!disposed && state.open && response.status === 202 && started) {
          await load(true);
        }
      } catch {
        // The list is the server's as it was; the next opening asks again.
      }
    }

    function open() {
      if (disposed || state.open) {
        return Promise.resolve();
      }
      state.open = true;
      state.error = null;
      askedForOrigin = false;
      return load().then(() => {
        void askForOrigin();
      });
    }

    function close() {
      if (disposed || !state.open) {
        return;
      }
      clearFilterTimer();
      clearPullsTimer();
      // An answer still on its way belongs to a list nobody is looking at.
      abortInflight();
      requested += 1;
      state.open = false;
      state.loading = false;
      render();
    }

    function toggle() {
      if (state.open) {
        close();
        return Promise.resolve();
      }
      return open();
    }

    /** @param {MetabrowserSourceRefKind} kind */
    function setKind(kind) {
      if (disposed || !state.open || kind === state.kind) {
        return Promise.resolve();
      }
      state.kind = kind;
      state.listing = null;
      return load().then(() => {
        void askForOrigin();
      });
    }

    /** @param {string} query */
    function setQuery(query) {
      if (disposed || !state.open || query === state.query) {
        return;
      }
      state.query = query;
      clearFilterTimer();
      filterTimer = deps.schedule(() => {
        filterTimer = null;
        void load();
      }, FILTER_DELAY_MS);
    }

    /** @param {string} ref The full store ref a listed row names. */
    function choose(ref) {
      return switchTo({ ref });
    }

    /** Serve a checkout's working tree again: the one choice that is not a ref. */
    function chooseWorkingTree() {
      return checkout ? switchTo({ working_tree: true }) : Promise.resolve();
    }

    /** @param {Record<string, string | boolean>} body What the pin route is asked for. */
    async function switchTo(body) {
      if (disposed || state.switching) {
        return;
      }
      state.switching = true;
      state.error = null;
      render();
      const view = deps.currentView();
      if (view?.startsWith(VIEW_PREFIX)) {
        body.view = view;
      }
      // From here the server may serve the other subject while this page is still here,
      // and would refuse what it asks as a page left behind: its requests wait for the
      // answer, and go with the page when it goes (static/source-pin-guard.js).
      /** @type {(gone: boolean) => void} */
      let decided = () => {};
      const held = deps.hold?.(
        new Promise((resolve) => {
          decided = resolve;
        }),
      );
      if (held === false) {
        decided(false);
        state.switching = false;
        state.error = "Another switch is already in progress.";
        render();
        return;
      }
      try {
        const response = await deps.request("POST", PIN_ROUTE, body);
        if (disposed) {
          return;
        }
        const answer =
          /** @type {{status?: MetabrowserSourceStatus, view_href?: unknown} | null} */ (
            response.body
          );
        if (response.status === 200 && answer !== null) {
          const served = answer.status;
          const shown = state.shown;
          // A checkout's page with no pin shows the working tree, which the status names
          // by a null pin and ref.
          if (
            served !== undefined &&
            (shown !== null || checkout) &&
            served.pin === (shown?.pin ?? null) &&
            served.ref === (shown?.ref ?? null)
          ) {
            state.switching = false;
            close();
            return;
          }
          const href = answer.view_href;
          deps.navigate(
            typeof href === "string" && href.startsWith(VIEW_PREFIX) ? href : VIEW_PREFIX,
          );
          decided(true);
          return;
        }
        state.error = switchFailure(response.body, checkout);
      } catch {
        state.error = "The switch request failed.";
      } finally {
        decided(false);
      }
      state.switching = false;
      render();
    }

    /**
     * A data request of this page was refused: the server serves something else.
     * *served* is the commit it serves, or "" for the working tree. Only a checkout's
     * page says so here; a mirror's freshness row does.
     *
     * @param {string} served
     */
    function servedChanged(served) {
      if (disposed || !checkout) {
        return;
      }
      state.stale = served;
      render();
    }

    function dispose() {
      disposed = true;
      clearFilterTimer();
      clearPullsTimer();
      abortInflight();
    }

    render();
    return Object.freeze({
      open,
      close,
      toggle,
      setKind,
      setQuery,
      choose,
      chooseWorkingTree,
      servedChanged,
      dispose,
      snapshot: () => ({ ...state, filterPending: filterTimer !== null }),
    });
  }

  // The group's key in the shared chip controls' markup and events.
  const KIND_GROUP = "source-ref-kind";
  // The plugin that draws a pull request's state, whose exports the rows load; the Pulls
  // tab loads the same plugin for its kind (static/pulls-nav.js). The plugin is 15
  // requests and about 240 KB transferred, of which the four icons are `pull-state.js`'s 3 KB,
  // and nothing loads them alone. Measured 2026-11-20 in headless Chrome against this
  // repository's mirror, 137 branches of which most head a pull request, with the cache off:
  // a list opened at once, before the Pulls tab's idle prefetch has loaded the plugin
  // (`PREFETCH_IDLE_TIMEOUT_MS`), draws its rows in 209 ms and its icons in 338 ms, so the
  // load costs the icons 129 ms and the rows nothing, their slots being as wide as the
  // icons; opened after 5 s the plugin is there and the icons come with the rows, in 93 ms;
  // opened at once with the cache warm, rows 75 ms and icons 82 ms.
  const PULL_ICON_PLUGIN = "github";
  /**
   * The GitHub plugin's `pullStateIcon`, once its exports have loaded.
   *
   * @type {MetabrowserGithubPullStateIcon | null}
   */
  let drawPullState = null;

  /** How every menu closes, which the shell loads before anything lazy.
   * @returns {MetabrowserMenus} */
  function menus() {
    const controls = window.metabrowser.menus;
    if (!controls) {
      throw new Error("source ref selector: the menu helper is unavailable");
    }
    return controls;
  }

  /** The shared chip controls, which the shell loads before anything lazy. */
  function chipControls() {
    const controls = window.metabrowser.filterControls;
    if (!controls) {
      throw new Error("source ref selector: filter controls are unavailable");
    }
    return controls;
  }

  /**
   * Paint one model. Browser only.
   *
   * The skeleton is built once so the filter box keeps its focus and caret while the
   * list under it changes; only the button's text, the tabs' state, the list, and the
   * notes are repainted.
   *
   * @param {MetabrowserSourceRefSelectorParts} parts
   * @param {MetabrowserSourceRefSelectorModel} model
   */
  function paint(parts, model) {
    // A folder Git does not take for a repository's root has no selector after all.
    parts.root.hidden = model.removed;
    // Shown while the list is closed too: the page is no longer what the server shows.
    parts.staleText.textContent = model.stale ?? "";
    parts.stale.hidden = model.stale === null;
    const refKey = JSON.stringify(model.selectedRef);
    if (parts.label.dataset.refKey !== refKey) {
      parts.label.dataset.refKey = refKey;
      parts.label.replaceChildren();
      if (model.selectedRef !== null) {
        const chip = window.metabrowser.refChip(model.selectedRef.name, {
          label: model.selectedRef.label,
          kind: model.selectedRef.kind,
          ref: model.selectedRef.ref,
          current: true,
        });
        if (model.workingTree?.current) {
          const context = model.selectedRef.label + " · Working tree";
          chip.dataset.tipText = context;
          chip.setAttribute("aria-label", "Actions for " + context);
        }
        parts.label.append(chip);
      } else if (model.pullNumber !== null) {
        const number = document.createElement("span");
        number.className = "source-ref-selector-pull-number";
        number.textContent = model.pullNumber;
        parts.label.append(model.button.slice(0, -model.pullNumber.length), number);
      } else if (model.commitId !== null) {
        // A commit's ID is set in the commit-ID face wherever it appears
        // (docs/design-system.md, "Short Commit IDs").
        const id = document.createElement("span");
        id.className = "git-commit-sha";
        id.textContent = model.commitId;
        parts.label.append(model.button.slice(0, -model.commitId.length), id);
      } else {
        parts.label.textContent = model.button;
      }
    }
    parts.toggle.setAttribute("aria-expanded", String(model.open));
    parts.panel.hidden = !model.open;
    parts.root.dataset.open = String(model.open);
    if (!model.open) {
      return;
    }
    // The chip group's markup, kept up to date in place so focus stays on the chosen one.
    for (const [kind, tab] of Object.entries(parts.tabs)) {
      tab.setAttribute("aria-checked", String(kind === model.kind));
      tab.tabIndex = kind === model.kind ? 0 : -1;
    }
    // A checkout's working tree, above its refs: the one choice that is not a ref, named
    // by the folder's path. The folder's own name, the path's last part, is kept whole,
    // and what is before it shortens with an ellipsis.
    parts.workingTree.hidden = model.workingTree === null;
    if (model.workingTree !== null) {
      parts.workingTree.disabled = model.switching;
      parts.workingTreeDirectory.textContent = model.workingTree.directory;
      parts.workingTreeBase.textContent = model.workingTree.base;
      if (model.workingTree.current) {
        parts.workingTree.setAttribute("aria-current", "true");
      } else {
        parts.workingTree.removeAttribute("aria-current");
      }
    }
    parts.filter.placeholder = model.filterLabel;
    parts.filter.setAttribute("aria-label", model.filterLabel);
    if (parts.filter.value !== model.query) {
      parts.filter.value = model.query;
    }
    parts.list.setAttribute("aria-busy", String(model.loading || model.switching));
    paintRows(parts, model);
    parts.note.textContent = model.note;
    parts.note.hidden = model.note === "";
    const origin = model.origin;
    if (origin === null) {
      parts.origin.hidden = true;
      parts.origin.textContent = "";
    } else {
      // When the store was fetched, as a row says its commit's age, with the exact time
      // as its tooltip (docs/design-system.md, "Age").
      const at = origin.fetchedAt === null ? Number.NaN : Date.parse(origin.fetchedAt) / 1000;
      const fetched = Number.isFinite(at)
        ? window.MetabrowserFormatters.age(at, { style: "relative" }).label
        : "";
      parts.origin.textContent = fetched === "" ? origin.text : `${origin.text}, ${fetched}.`;
      if (Number.isFinite(at)) {
        parts.origin.dataset.tipText = window.metabrowser.formatTimestamp(at);
      } else {
        delete parts.origin.dataset.tipText;
      }
      parts.origin.dataset.tone = origin.tone;
      parts.origin.hidden = false;
    }
    parts.error.textContent = model.error ?? "";
    parts.error.hidden = model.error === null;
  }

  /**
   * The state's icon, drawn by the GitHub plugin once it has loaded: the shapes and hues of
   * a pull request's state are the plugin's, in one place, so a row here and a row of the
   * Pulls tab cannot disagree (docs/design-system.md, "A Pull Request's State"). Until it
   * has, the slot is as wide as the icon will be, so nothing moves when it arrives.
   * Browser only.
   *
   * @param {"open" | "draft" | "merged" | "closed"} state
   * @returns {HTMLElement}
   */
  function pullIcon(state) {
    const slot = document.createElement("span");
    slot.className = "source-ref-selector-pull-icon";
    if (drawPullState !== null) {
      slot.append(drawPullState(state));
    }
    return slot;
  }

  /**
   * A row's pull request line: the first pull request's state icon, its number, and its
   * title, and a count of the others. Browser only.
   *
   * @param {MetabrowserSourceRefSelectorModel["rows"][number]} row
   * @returns {HTMLElement}
   */
  function pullLine(row) {
    const [first] = row.pulls;
    const others = row.pullsTotal - 1;
    const line = document.createElement("span");
    line.className = "source-ref-selector-pull";
    const number = document.createElement("span");
    number.className = "source-ref-selector-pull-number";
    number.textContent = `#${first.number}`;
    // A conventional-commit prefix is regular and the rest of the title bold
    // (docs/design-system.md, "Titles").
    const title = document.createElement("span");
    title.className = "source-ref-selector-pull-title";
    title.append(...window.MetabrowserFormatters.titleNodes(document, first.title));
    line.append(pullIcon(first.state), number, title);
    if (others > 0) {
      const more = document.createElement("span");
      more.className = "source-ref-selector-pull-more";
      more.textContent = `+${others}`;
      more.setAttribute("aria-label", `and ${others} more pull request${others === 1 ? "" : "s"}`);
      line.append(more);
    }
    return line;
  }

  /**
   * The branch's other pull requests, named: the first PULL_MORE_LIMIT of those the row
   * lists, and how many more there are. "" when it has one. Pure.
   *
   * @param {MetabrowserSourceRefSelectorModel["rows"][number]} row
   * @returns {string}
   */
  function otherPulls(row) {
    if (row.pullsTotal <= 1) {
      return "";
    }
    const named = row.pulls
      .slice(1, 1 + PULL_MORE_LIMIT)
      .map((pull) => `#${pull.number} ${pull.title}`);
    const rest = row.pullsTotal - 1 - named.length;
    return `Also ${named.join(", ")}${rest > 0 ? `, and ${rest} more` : ""}`;
  }

  /**
   * What the row's tooltip says of its pull requests: the first one's whole title when the
   * line cuts it short, and the others, which the line shows only as a count. A tooltip
   * is one run of text, so these join with a dot. Pure.
   *
   * @param {MetabrowserSourceRefSelectorModel["rows"][number]} row
   * @param {boolean} cut Whether the first one's title is cut short.
   * @returns {string}
   */
  function pullTip(row, cut) {
    /** @type {string[]} */
    const parts = cut ? [`#${row.pulls[0].number} ${row.pulls[0].title}`] : [];
    const others = otherPulls(row);
    if (others !== "") {
      parts.push(others);
    }
    return parts.join(" · ");
  }

  /**
   * What a row's pull request line is drawn from, to tell whether it needs drawing again.
   * Pure.
   *
   * @param {MetabrowserSourceRefSelectorModel["rows"][number]} row
   * @returns {string}
   */
  function pullKey(row) {
    return `${row.pullsTotal}\n${pullsSignature(row.pulls)}`;
  }

  /**
   * Draw, or draw again, a row's pull request line, and say the branch's others to
   * assistive technology, which a tooltip does not reach (mb-tjbm review A11). Browser only.
   *
   * @param {HTMLLIElement} item
   * @param {MetabrowserSourceRefSelectorModel["rows"][number]} row
   */
  function drawPulls(item, row) {
    const button = /** @type {HTMLButtonElement} */ (item.firstElementChild);
    item.dataset.pulls = pullKey(row);
    button.querySelector(":scope > .source-ref-selector-pull")?.remove();
    if (row.pulls.length > 0) {
      button.append(pullLine(row));
    }
    const others = otherPulls(row);
    if (others === "") {
      button.removeAttribute("aria-description");
    } else {
      button.setAttribute("aria-description", others);
    }
  }

  /**
   * One row: its ref's chip, a badge, its commit, and its commit's age, and under them the
   * pull request it is the head of, if it is. Browser only.
   *
   * What the handlers say is read from the list when they run, not kept from here, so a
   * row whose pull requests arrive later is patched in place (`patchRow`) and keeps its
   * element, its focus, and its tooltip.
   *
   * @param {MetabrowserSourceRefSelectorModel["rows"][number]} row
   * @param {number} at Its index among every row the list shows.
   * @param {MetabrowserSourceRefSelectorRows} rows
   * @returns {HTMLLIElement}
   */
  function rowElement(row, at, rows) {
    const item = document.createElement("li");
    item.className = "source-ref-selector-item";
    // Only the rows near the view are in the document, so each says where it stands.
    item.setAttribute("aria-posinset", String(at + 1));
    item.setAttribute("aria-setsize", String(rows.shown.length));
    item.style.top = `${rows.offsets[at] ?? 0}px`;
    const button = document.createElement("button");
    button.type = "button";
    button.className = "menu-item source-ref-selector-row";
    button.dataset.index = String(at);
    button.disabled = rows.switching;
    button.tabIndex = at === rows.roving ? 0 : -1;
    if (row.current) {
      button.setAttribute("aria-current", "true");
    }
    // The ref's own line, which every row has; a pull request's line goes under it.
    const main = document.createElement("span");
    main.className = "source-ref-selector-main";
    const name = document.createElement("span");
    name.className = "source-ref-selector-name";
    // A mirror's branch is a remote chip and its tag a tag chip, as on the button; a
    // checkout's own branch is a local chip. The default branch is not drawn as trunk:
    // trunk is the server's `is_trunk` on a Git ref, and the mirror's default need not
    // be the branch the history draws solid. The badge below says "default", or
    // "checked out" for the branch a checkout's HEAD is on, in words
    // (docs/design-system.md, "Branch Chips").
    name.appendChild(
      window.metabrowser.refChip(row.ref, { label: row.name, kind: row.chip, menu: false }),
    );
    main.append(name);
    if (row.default || row.checkedOut) {
      const badge = document.createElement("span");
      badge.className = "source-ref-selector-badge";
      badge.textContent = row.default ? "default" : "checked out";
      main.append(badge);
    }
    // Where the reader's own `origin/<branch>` is not where the origin's branch is: a
    // second tag, in a warning's ink, whose sentence the row's tooltip carries.
    if (row.own !== null) {
      const own = document.createElement("span");
      own.className = "source-ref-selector-badge source-ref-selector-own";
      own.textContent = row.own.text;
      main.append(own);
    }
    // The commit as every line names one, its short ID in the commit-ID face, then
    // its age, in the compact style of navigation, with the exact time as its tooltip
    // (docs/design-system.md, "Age"). A date Git did not give has no age.
    const commit = document.createElement("span");
    commit.className = "git-commit-sha source-ref-selector-commit";
    commit.textContent = row.commit;
    const age = document.createElement("span");
    if (row.committedAt !== null) {
      const shown = window.MetabrowserFormatters.age(row.committedAt);
      age.className = `source-ref-selector-age ${shown.className}`;
      age.textContent = shown.label;
      age.dataset.tipText = window.metabrowser.formatTimestamp(row.committedAt);
    } else {
      age.className = "source-ref-selector-age";
    }
    main.append(commit, age);
    button.append(main);
    item.append(button);
    drawPulls(item, row);
    button.addEventListener("click", () => rows.choose(row.ref));
    // The row's name, or its pull request's title, is cut short with an ellipsis when it
    // is wider than the list; the tooltip then carries the whole of it, and the other
    // pull requests a branch is the head of. pointerenter comes before the mouseenter the
    // shell's tooltip listens for.
    button.addEventListener("pointerenter", () => {
      const now = rows.shown[at] ?? row;
      const title = button.querySelector(".source-ref-selector-pull-title");
      const cut = title instanceof HTMLElement && title.scrollWidth > title.clientWidth;
      /** @type {string[]} */
      const tips = [];
      if (name.scrollWidth > name.clientWidth) {
        tips.push(row.name);
      }
      if (row.own !== null) {
        tips.push(row.own.tip);
      }
      if (now.pulls.length > 0) {
        const tip = pullTip(now, cut);
        if (tip !== "") {
          tips.push(tip);
        }
      }
      if (tips.length > 0) {
        button.dataset.tipText = tips.join(" · ");
      } else {
        delete button.dataset.tipText;
      }
    });
    return item;
  }

  /**
   * Bring a drawn row up to date with its model row, where its ref's line is what it was:
   * where it sits, whether it takes Tab, and its pull request line, drawn again only if
   * the pull requests moved. The element stays, so focus, a tooltip, and a press survive.
   * Browser only.
   *
   * @param {HTMLLIElement} item
   * @param {MetabrowserSourceRefSelectorModel["rows"][number]} row
   * @param {number} at
   * @param {MetabrowserSourceRefSelectorRows} rows
   */
  function patchRow(item, row, at, rows) {
    const top = `${rows.offsets[at] ?? 0}px`;
    if (item.style.top !== top) {
      item.style.top = top;
    }
    const button = /** @type {HTMLButtonElement} */ (item.firstElementChild);
    button.disabled = rows.switching;
    button.tabIndex = at === rows.roving ? 0 : -1;
    if (item.dataset.pulls !== pullKey(row)) {
      drawPulls(item, row);
    }
  }

  /**
   * Draw the rows in the list's view, ROWS_OVERSCAN more on either side, and the row that
   * takes Tab, wherever it is; take the rest out. Browser only.
   *
   * Each row is placed by its offset over the sizer, which is as tall as every row, so the
   * list scrolls over all of them and its scroll bar says how far through it is. A row
   * already drawn is kept, so a scroll draws only the rows it brings near, and the rows
   * stay in the document in their order.
   *
   * @param {MetabrowserSourceRefSelectorParts} parts
   */
  function drawWindow(parts) {
    const rows = parts.rows;
    const count = rows.shown.length;
    parts.sizer.style.height = `${rows.offsets[count] ?? 0}px`;
    const { start, end, also } = rowWindow(
      rows.offsets,
      parts.list.scrollTop || 0,
      parts.list.clientHeight || 0,
      rows.roving,
    );
    /** @type {number[]} */
    const wanted = [];
    if (also >= 0 && also < start) {
      wanted.push(also);
    }
    for (let at = start; at < end; at += 1) {
      wanted.push(at);
    }
    if (also >= end) {
      wanted.push(also);
    }
    const keep = new Set(wanted);
    for (const [at, item] of rows.drawn) {
      if (!keep.has(at)) {
        item.remove();
        rows.drawn.delete(at);
      }
    }
    let cursor = /** @type {Element | null} */ (parts.sizer.nextElementSibling);
    for (const at of wanted) {
      const drawn = rows.drawn.get(at);
      if (drawn === undefined) {
        const item = rowElement(rows.shown[at], at, rows);
        rows.drawn.set(at, item);
        parts.list.insertBefore(item, cursor);
      } else if (drawn === cursor) {
        cursor = cursor.nextElementSibling;
      }
    }
  }

  /**
   * How tall a row is with no pull request and with one, measured by a row of each drawn
   * out of sight, as the list lays it out. Browser only.
   *
   * Every row is placed by its offset, so the two must be exact, and each is the same for
   * every row of its kind (docs/design-system.md, "The Ref Selector"). A pull request's
   * line has a height of its own, and one row measured in the document, as this once did,
   * says nothing of a kind of row it is not. The tall row is measured only when a row of
   * the list is one.
   *
   * @param {MetabrowserSourceRefSelectorParts} parts
   * @param {boolean} annotated Whether any row of the list has a pull request.
   * @returns {{plain: number, tall: number}}
   */
  function measureRows(parts, annotated) {
    /** @type {HTMLElement[]} */
    const probes = [];
    /** @param {boolean} tall */
    const probe = (tall) => {
      const item = rowElement(
        {
          name: "probe",
          ref: "refs/remotes/origin/probe",
          commit: "0000000",
          committedAt: null,
          default: false,
          checkedOut: false,
          current: false,
          chip: "remote",
          own: null,
          pulls: tall ? [{ number: 1, title: "probe", state: "open" }] : [],
          pullsTotal: tall ? 1 : 0,
        },
        0,
        { ...parts.rows, shown: [], offsets: [0] },
      );
      item.style.visibility = "hidden";
      item.setAttribute("aria-hidden", "true");
      item.inert = true;
      probes.push(item);
      return item;
    };
    const plain = probe(false);
    const tall = annotated ? probe(true) : null;
    parts.list.append(...probes);
    const measured = {
      plain: plain.getBoundingClientRect().height,
      tall: tall === null ? 0 : tall.getBoundingClientRect().height,
    };
    for (const item of probes) {
      item.remove();
    }
    return measured;
  }

  /**
   * The rows of a new model, the window first measured by a row of each kind. Browser only.
   *
   * A new list, or a new filter, is drawn afresh and starts at its top. The same list drawn
   * again, as it is when the server's pull requests arrive, keeps what the reader sees:
   * the rows that are the same refs stay as they are, patched (`patchRow`), so focus,
   * a tooltip, and a press in progress survive, and the list scrolls so that the row at the
   * top of its view stays where it was, the foot stays the foot, and a focused row stays
   * in view, though the rows above have grown (`anchoredScroll`; mb-tjbm review A1, A2).
   *
   * The row that takes Tab is the one that had focus when this listing still has its
   * ref, else the served one, else the first; a row that had focus keeps it.
   *
   * @param {MetabrowserSourceRefSelectorParts} parts
   * @param {MetabrowserSourceRefSelectorModel} model
   */
  function paintRows(parts, model) {
    const rows = parts.rows;
    rows.model = model;
    const active = /** @type {HTMLElement | null} */ (document.activeElement);
    const hadFocus =
      active !== null && parts.list.contains(active) && active.dataset.index !== undefined
        ? rows.shown[Number(active.dataset.index)]?.ref
        : undefined;
    // A new list, or a new filter, starts at its top, its newest refs, unless it shows
    // the served ref: then at that ref's row, once its rows arrive (below).
    const shows = `${model.kind}\0${model.query}`;
    const again = rows.listing === shows;
    if (!again) {
      rows.listing = shows;
      rows.revealed = false;
      parts.list.scrollTop = 0;
    }
    // Where the rows were, for the reader to keep their place among them.
    const before = again ? { refs: rows.shown.map((row) => row.ref), offsets: rows.offsets } : null;
    const scrolled = parts.list.scrollTop;
    const view = parts.list.clientHeight || 0;
    const inPlace = again && !rows.rebuild && sameRefLines(rows.shown, model.rows);
    rows.rebuild = false;
    if (!inPlace) {
      for (const item of rows.drawn.values()) {
        item.remove();
      }
      rows.drawn.clear();
    }
    rows.shown = model.rows;
    rows.switching = model.switching;
    const annotated = model.rows.some((row) => row.pulls.length > 0);
    // The icons of a pull request's state are the GitHub plugin's, which loads on demand
    // and then draws the rows again (`drawIcons`).
    if (annotated) {
      drawIcons(parts);
    }
    // One height places every row of a kind; both are measured again on each new listing,
    // so a change of font or density is followed.
    const measured = measureRows(parts, annotated);
    rows.offsets = rowOffsets(model.rows, measured.plain, measured.tall);
    const kept = hadFocus === undefined ? -1 : model.rows.findIndex((row) => row.ref === hadFocus);
    const current = model.rows.findIndex((row) => row.current);
    rows.roving = kept >= 0 ? kept : current >= 0 ? current : 0;
    // The box is as tall as the rows are now before the list is scrolled in it, or the
    // browser holds the scroll to the old height.
    parts.sizer.style.height = `${rows.offsets[model.rows.length] ?? 0}px`;
    if (before !== null) {
      parts.list.scrollTop = anchoredScroll(
        before,
        { refs: model.rows.map((row) => row.ref), offsets: rows.offsets },
        scrolled,
        view,
        hadFocus ?? null,
      );
    }
    if (inPlace) {
      for (const [at, item] of rows.drawn) {
        patchRow(item, model.rows[at], at, rows);
      }
    }
    drawWindow(parts);
    if (!rows.revealed && model.rows.length > 0 && rows.offsets[model.rows.length] > 0) {
      rows.revealed = true;
      if (current > 0 && kept < 0) {
        revealRow(parts, current);
        drawWindow(parts);
      }
    }
    if (kept >= 0 && !inPlace) {
      /** @type {HTMLElement | null | undefined} */ (
        rows.drawn.get(kept)?.firstElementChild
      )?.focus({ preventScroll: true });
    }
  }

  /**
   * Load the GitHub plugin, which draws a pull request's state, once, and draw the rows
   * again when it has: they were drawn with an empty slot where its icon goes, the slot's
   * own width, so nothing moves. A plugin that cannot load leaves the slots empty, and
   * each row's accessible text still says the number and title. Browser only.
   *
   * @param {MetabrowserSourceRefSelectorParts} parts
   */
  function drawIcons(parts) {
    const rows = parts.rows;
    if (rows.iconsAsked || drawPullState !== null) {
      return;
    }
    rows.iconsAsked = true;
    void window.metabrowser.plugins.load(PULL_ICON_PLUGIN).then(
      (github) => {
        drawPullState = github.pullStateIcon;
        if (!parts.disposed && rows.model !== null) {
          // Drawn with an empty slot where the icon goes, so every row is drawn again.
          rows.rebuild = true;
          paintRows(parts, rows.model);
        }
      },
      () => {},
    );
  }

  /**
   * Scroll the list the least that brings the row at *at* into its view; nothing until a
   * row has been measured. Browser only.
   *
   * @param {MetabrowserSourceRefSelectorParts} parts
   * @param {number} at
   */
  function revealRow(parts, at) {
    const { list, rows } = parts;
    const top = rows.offsets[at];
    const foot = rows.offsets[at + 1];
    if (!(foot > top)) {
      return;
    }
    if (top < list.scrollTop) {
      list.scrollTop = top;
    } else if (foot > list.scrollTop + list.clientHeight) {
      list.scrollTop = foot - list.clientHeight;
    }
  }

  /**
   * Move the row that takes Tab to *at*, bring it into the list's view, and focus it.
   * Browser only.
   *
   * @param {MetabrowserSourceRefSelectorParts} parts
   * @param {number} at
   */
  function focusRow(parts, at) {
    const rows = parts.rows;
    rows.roving = at;
    revealRow(parts, at);
    drawWindow(parts);
    for (const [index, item] of rows.drawn) {
      /** @type {HTMLElement} */ (item.firstElementChild).tabIndex = index === at ? 0 : -1;
    }
    /** @type {HTMLElement | null | undefined} */ (rows.drawn.get(at)?.firstElementChild)?.focus({
      preventScroll: true,
    });
  }

  /**
   * Build the selector's elements inside *element*. Browser only.
   *
   * @param {HTMLElement} element
   * @param {boolean} checkout Whether the page is a checkout's, with its third list.
   * @param {(ref: string) => void} choose What a press on a row does.
   * @returns {MetabrowserSourceRefSelectorParts}
   */
  function build(element, checkout, choose) {
    // Adopt the server's chooser so it keeps any focus it received before mounting.
    const drawn = /** @type {HTMLButtonElement | null} */ (
      element.querySelector("button.source-ref-selector-toggle")
    );
    const toggle = drawn ?? document.createElement("button");
    toggle.type = "button";
    toggle.className = "icon-btn source-ref-selector-toggle disclosure-toggle";
    toggle.setAttribute("aria-haspopup", "dialog");
    toggle.setAttribute("aria-label", "Switch branch or tag");
    toggle.dataset.tipText = "Switch branch or tag";
    toggle.innerHTML = window.MetabrowserIcons?.toggle ?? "";
    const label =
      /** @type {HTMLElement | null} */ (element.querySelector(".source-ref-selector-label")) ??
      document.createElement("span");
    label.className = "source-ref-selector-label";
    // What a checkout's page says when the server comes to show something else, as a
    // freshness row: at the foot of the navigation pane, where a mirror's makes the same
    // offer, so every tab shows it. The Pulls tab's requests and a comparison's are
    // refused as the Files tab's are, and the chooser is in the Files row, which the
    // other tabs hide.
    const stale = document.createElement("div");
    stale.className = "source-freshness source-ref-selector-stale";
    stale.setAttribute("role", "status");
    stale.hidden = true;
    const staleOffer = document.createElement("span");
    staleOffer.className = "source-freshness-offer";
    const staleText = document.createElement("span");
    const reload = document.createElement("button");
    reload.type = "button";
    reload.className = "btn source-ref-selector-reload";
    reload.textContent = "Reload page";
    staleOffer.append(staleText, reload);
    stale.append(staleOffer);
    const panel = document.createElement("div");
    panel.className = "source-ref-selector-panel menu";
    panel.setAttribute("role", "dialog");
    panel.setAttribute("aria-label", "Switch branch or tag");
    panel.hidden = true;
    // One of two lists, so an exclusive chip group: docs/design-system.md, "Choosing Among
    // Values". It says nothing until the first paint, which marks the kind shown.
    const kinds = document.createElement("div");
    kinds.className = "source-ref-selector-kinds";
    kinds.innerHTML = chipControls().groupHtml({
      key: KIND_GROUP,
      select: "one",
      layout: "joined",
      label: "Show",
      options: (checkout ? CHECKOUT_KINDS : MIRROR_KINDS).map((value) => ({
        value,
        label: KIND_LABEL[value],
      })),
      value: "branch",
    });
    const tabs = /** @type {Record<MetabrowserSourceRefKind, HTMLButtonElement>} */ ({});
    for (const tab of kinds.querySelectorAll("button")) {
      tabs[/** @type {MetabrowserSourceRefKind} */ (tab.dataset.chipValue)] = tab;
    }
    const filter = document.createElement("input");
    filter.type = "search";
    filter.className = "field source-ref-selector-filter";
    filter.autocomplete = "off";
    filter.spellcheck = false;
    const list = document.createElement("ul");
    list.className = "source-ref-selector-list";
    // `list-style: none` drops a list's role in WebKit; the rows' places need it.
    list.setAttribute("role", "list");
    // As tall as every row together; the rows near the view are placed over it.
    const sizer = document.createElement("li");
    sizer.className = "source-ref-selector-sizer";
    sizer.setAttribute("role", "none");
    sizer.setAttribute("aria-hidden", "true");
    list.append(sizer);
    const note = document.createElement("p");
    note.className = "source-ref-selector-note";
    note.setAttribute("role", "status");
    // What the list says of the store a checkout's origin is listed from, and when it
    // was fetched. Not a live region: its age is repainted with the list.
    const origin = document.createElement("p");
    origin.className = "source-ref-selector-note source-ref-selector-origin";
    origin.hidden = true;
    const error = document.createElement("p");
    error.className = "source-ref-selector-error";
    error.setAttribute("role", "alert");
    // A menu row like a ref's, with the folder's path in place of a commit, in the path
    // markup the shell names a folder by (`.path`, its last part `.path-base`).
    const workingTree = document.createElement("button");
    workingTree.type = "button";
    workingTree.className = "menu-item source-ref-selector-working-tree";
    workingTree.hidden = true;
    const workingTreeName = document.createElement("span");
    workingTreeName.className = "source-ref-selector-working-tree-name";
    workingTreeName.textContent = WORKING_TREE;
    const workingTreeLocation = document.createElement("span");
    workingTreeLocation.className = "path source-ref-selector-location";
    const workingTreeDirectory = document.createElement("span");
    workingTreeDirectory.className = "source-ref-selector-location-directory";
    const workingTreeBase = document.createElement("span");
    workingTreeBase.className = "path-base";
    workingTreeLocation.append(workingTreeDirectory, workingTreeBase);
    workingTree.append(workingTreeName, workingTreeLocation);
    // The path is shortened when the list is narrower than it; the tooltip then carries
    // all of it. pointerenter comes before the mouseenter the shell's tooltip listens for.
    workingTree.addEventListener("pointerenter", () => {
      if (workingTreeDirectory.scrollWidth > workingTreeDirectory.clientWidth) {
        workingTree.dataset.tipText = workingTreeLocation.textContent ?? "";
      } else {
        delete workingTree.dataset.tipText;
      }
    });
    panel.append(workingTree, kinds, filter, list, note, origin, error);
    if (drawn === null) {
      const buttonHost = document.createElement("span");
      buttonHost.className = "source-ref-selector-button";
      buttonHost.append(label, toggle);
      element.replaceChildren(buttonHost);
    }
    const foot = document.getElementById("index-progress");
    if (foot) {
      foot.after(stale);
    } else {
      element.append(stale);
    }
    element.hidden = false;
    return {
      root: element,
      toggle,
      label,
      stale,
      staleText,
      reload,
      panel,
      workingTree,
      workingTreeDirectory,
      workingTreeBase,
      kinds,
      tabs,
      filter,
      list,
      sizer,
      note,
      origin,
      error,
      rows: {
        shown: [],
        drawn: new Map(),
        roving: 0,
        offsets: [0],
        model: null,
        iconsAsked: false,
        rebuild: false,
        listing: "",
        revealed: false,
        switching: false,
        choose,
      },
    };
  }

  /** The selector this page mounted, kept for the branch or tag key, which runs the
   * button's path through it; null until it mounts and after it is disposed.
   * @type {MetabrowserSourceRefSelectorMount | null} */
  let mountedSelector = null;

  /**
   * Start the selector on this page with the browser's fetch, timers, focus, and paint.
   *
   * @param {HTMLElement} element
   */
  function mount(element) {
    const checkout = Boolean(window.METABROWSER_SOURCE_CHECKOUT);
    /** @type {ReturnType<typeof createSelector> | null} */
    let selector = null;
    const parts = build(element, checkout, (ref) => void selector?.choose(ref));
    selector = createSelector(
      {
        async request(method, route, body, signal) {
          const response = await fetch(route, {
            method,
            signal,
            headers: method === "POST" ? { "content-type": "application/json" } : {},
            cache: "no-store",
            body: method === "POST" ? JSON.stringify(body ?? {}) : undefined,
          });
          let parsed = null;
          try {
            parsed = await response.json();
          } catch {
            parsed = null;
          }
          return { status: response.status, etag: null, body: parsed };
        },
        schedule: (callback, delayMs) => window.setTimeout(callback, delayMs),
        cancel: (handle) => window.clearTimeout(/** @type {number} */ (handle)),
        render: (model) => paint(parts, model),
        navigate: (href) => window.location.assign(href),
        currentView: () => window.location.pathname,
        hold: (going) => window.MetabrowserSourcePinGuard?.hold(going),
      },
      {
        shown: window.METABROWSER_SOURCE_PIN ?? null,
        checkout,
        workingBranch: element.dataset.workingBranch,
      },
    );
    const mounted = selector;
    const listening = new AbortController();
    const signal = listening.signal;
    parts.workingTree.addEventListener("click", () => void mounted.chooseWorkingTree(), {
      signal,
    });
    parts.reload.addEventListener("click", () => window.location.reload(), { signal });
    // The pin guard announces a data request refused because the server serves
    // something else (static/source-pin-guard.js); only a checkout's selector says so.
    window.addEventListener(
      "metabrowser:pin-changed",
      (event) => {
        const detail = /** @type {CustomEvent<{pin?: unknown}>} */ (event).detail;
        mounted.servedChanged(typeof detail?.pin === "string" ? detail.pin : "");
      },
      { signal },
    );
    // An open list takes focus in its filter box, so typing narrows it at once.
    const focusOpenFilter = () => {
      if (!parts.panel.hidden) {
        parts.filter.focus();
      }
    };
    const closeActionMenu = () => {
      /** @type {HTMLButtonElement | null} */ (
        parts.label.querySelector('button[aria-expanded="true"]')
      )?.click();
    };
    // The list closes as every menu does (docs/design-system.md, "Every Menu Closes
    // Alike"), and opening it, by its button or its key, closes any other.
    const dismissal = menus().dismissible({
      name: "source-ref-selector-panel",
      trigger: parts.toggle,
      inside: (node) => parts.panel.contains(node),
      isOpen: () => !parts.panel.hidden,
      close: () => mounted.close(),
    });
    parts.toggle.addEventListener(
      "click",
      () => {
        void mounted.toggle();
        if (parts.panel.hidden) {
          dismissal.closed();
        } else {
          dismissal.opened();
        }
        focusOpenFilter();
      },
      { signal },
    );
    const unbindKinds = chipControls().bind(parts.kinds, {
      onChange(key, value, select) {
        if (key === KIND_GROUP && select === "one") {
          void mounted.setKind(/** @type {MetabrowserSourceRefKind} */ (value));
        }
      },
    });
    element.append(parts.panel);
    parts.filter.addEventListener("input", () => mounted.setQuery(parts.filter.value), {
      signal,
    });
    // The rows drawn now: those near the list's view, and the one that takes Tab.
    const rows = () =>
      /** @type {HTMLButtonElement[]} */ ([...parts.list.querySelectorAll("button")]);
    // A scroll draws the rows it brings near; a scroll event comes at most once a frame.
    parts.list.addEventListener("scroll", () => drawWindow(parts), { signal, passive: true });
    // While the list is open, Tab stays inside it, wrapping at either end, as in a dialog.
    // A key held with Command or Control is the browser's, as is one held with Option
    // other than Tab, which Safari moves focus with, so the trap keeps Option-Tab.
    document.addEventListener(
      "keydown",
      (event) => {
        if (
          parts.panel.hidden ||
          event.ctrlKey ||
          event.metaKey ||
          (event.altKey && event.key !== "Tab")
        ) {
          return;
        }
        if (event.key !== "Tab") {
          return;
        }
        /** @type {HTMLElement[]} */
        const stops = [
          ...(parts.workingTree.hidden || parts.workingTree.disabled ? [] : [parts.workingTree]),
          // One stop: the group's arrow keys move within it.
          ...Object.values(parts.tabs).filter((tab) => tab.tabIndex === 0),
          parts.filter,
          ...rows().filter((row) => row.tabIndex === 0 && !row.disabled),
        ];
        const at = stops.indexOf(/** @type {HTMLElement} */ (document.activeElement));
        const next = event.shiftKey
          ? at <= 0
            ? stops.length - 1
            : at - 1
          : at === -1 || at === stops.length - 1
            ? 0
            : at + 1;
        event.preventDefault();
        stops[next]?.focus();
      },
      { signal },
    );
    parts.panel.addEventListener(
      "keydown",
      (event) => {
        // Command-Up in the filter moves its caret, and Command-Left goes back.
        if (event.altKey || event.ctrlKey || event.metaKey) {
          return;
        }
        // A row's index is among every row the list shows, drawn or not.
        const target = /** @type {HTMLElement} */ (event.target);
        const index =
          rows().includes(/** @type {HTMLButtonElement} */ (target)) &&
          target.dataset.index !== undefined
            ? Number(target.dataset.index)
            : -1;
        if (index < 0 && target !== parts.filter) {
          return;
        }
        const next = moveRow(event.key, index, parts.rows.shown.length);
        if (next === null) {
          return;
        }
        event.preventDefault();
        if (next < 0) {
          parts.filter.focus();
          return;
        }
        focusRow(parts, next);
      },
      { signal },
    );
    const handle = Object.freeze({
      ...mounted,
      // The control a key's badge marks, and what the key does: the button's path,
      // except that it opens the list rather than toggling it.
      button: parts.toggle,
      activate() {
        const opened = mounted.open();
        dismissal.opened();
        focusOpenFilter();
        return opened;
      },
      close() {
        closeActionMenu();
        mounted.close();
        dismissal.closed();
      },
      dispose() {
        closeActionMenu();
        parts.disposed = true;
        dismissal.dispose();
        listening.abort();
        unbindKinds();
        mounted.dispose();
        parts.stale.remove();
        element.replaceChildren();
        element.hidden = true;
        if (mountedSelector === handle) {
          mountedSelector = null;
        }
      },
    });
    mountedSelector = handle;
    return handle;
  }

  window.MetabrowserSourceRefSelector = Object.freeze({
    FILTER_DELAY_MS,
    ROWS_OVERSCAN,
    createSelector,
    describe,
    mount,
    mounted: () => mountedSelector,
    anchoredScroll,
    moveRow,
    PULLS_POLL_MS,
    rowOffsets,
    rowWindow,
    sameListing,
    sameRefLines,
    shownLabel,
  });
})();

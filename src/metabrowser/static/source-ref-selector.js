// The branch and tag selector of a served mirror, and of a served checkout.
//
// A page on a mirror's pin shows a compact button naming the ref it was rendered for.
// Opening it lists the mirror's branches or tags from GET /api/source/refs, the
// default branch first and the served ref marked, narrowed by a filter box; the server
// bounds and counts the list, and the page says when it stops short. Choosing a ref
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
//   freshness row makes and a checkout's page has no such row to make.
//
// The selector chooses what the Files tab shows and nothing else, so it leads that tab's
// toolbar row, beside Group by, where the server draws its button (server.py); the Pulls
// and Commits tabs do not follow it. Each listed ref shows its commit as the history
// does, Git's short ID in the commit-ID face, and the commit's age by the shared
// formatter (docs/design-system.md, "Age").
//
// Every decision lives here without a DOM: `describe` turns the selector's state into
// what it shows, and `createSelector` owns loading, filtering, stale answers, and the
// switch through injected dependencies. `mount` is the browser glue that supplies real
// fetch, timers, focus, and paint. tests/dom/source-ref-selector-session.js runs the
// same functions from the command line.

(() => {
  const REFS_ROUTE = "/api/source/refs";
  const PIN_ROUTE = "/api/source/pin";
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

  /** @type {Readonly<Record<MetabrowserSourceRefKind, string>>} */
  const KIND_PLURAL = Object.freeze({
    branch: "branches",
    tag: "tags",
    remote: "remote branches",
  });
  /** @type {Readonly<Record<MetabrowserSourceRefKind, string>>} */
  const KIND_LABEL = Object.freeze({ branch: "Branches", tag: "Tags", remote: "Remotes" });
  /** The lists each subject has; the listing says the same in `kinds`.
   * @type {readonly MetabrowserSourceRefKind[]} */
  const MIRROR_KINDS = Object.freeze(["branch", "tag"]);
  /** @type {readonly MetabrowserSourceRefKind[]} */
  const CHECKOUT_KINDS = Object.freeze(["branch", "tag", "remote"]);

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
    // As the navigation heading and every row name a commit (`shortCommit`).
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
      typeof record.total === "number" &&
      typeof record.truncated === "boolean" &&
      Array.isArray(record.refs)
    );
  }

  /**
   * What the selector shows for one state. Pure.
   *
   * @param {MetabrowserSourceRefSelectorState} state
   * @returns {MetabrowserSourceRefSelectorModel}
   */
  function describe(state) {
    const checkout = state.checkout === true;
    const label = shownLabel(state.shown, checkout);
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
          }));
    let note = "";
    if (state.loading && listing === null) {
      note = `Loading ${plural}…`;
    } else if (listing !== null && listing.refs.length === 0) {
      note =
        listing.query === ""
          ? `The ${checkout ? "checkout" : "mirror"} has no ${plural}.`
          : `No ${plural} match.`;
    } else if (listing?.truncated) {
      note = `Showing ${listing.refs.length} of ${listing.total} ${plural}; filter to narrow.`;
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
      loading: state.loading,
      switching: state.switching,
      workingTree,
      rows,
      note,
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
   * Why a switch was refused, the way the selector says it.
   *
   * @param {number} status
   * @param {unknown} body
   * @param {boolean} checkout Whether the refs are a checkout's, which fetches nothing.
   */
  function switchFailure(status, body, checkout) {
    const record = /** @type {{code?: unknown} | null} */ (
      body !== null && typeof body === "object" ? body : null
    );
    const code = record !== null && typeof record.code === "string" ? record.code : "";
    if (code === "selection_pending") {
      return "The mirror is fetching that ref; choose it again when the fetch ends.";
    }
    if (code === "selection_not_found") {
      return `That ref is no longer in the ${checkout ? "checkout" : "mirror"}.`;
    }
    return `Could not switch (${code || `HTTP ${status}`}).`;
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
   * @param {{shown?: MetabrowserSourcePage | null, checkout?: boolean}} [options]
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
      ...(checkout ? { checkout, stale: null } : {}),
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

    function abortInflight() {
      inflight?.abort();
      inflight = null;
    }

    async function load() {
      clearFilterTimer();
      abortInflight();
      requested += 1;
      const ticket = requested;
      const controller = new AbortController();
      inflight = controller;
      state.loading = true;
      render();
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
        } else if (refusal?.code === "unsupported_git" && typeof refusal.error === "string") {
          // The server's own words: which Git a checkout's revisions are read with.
          error = refusal.error;
        } else {
          error = `The ${KIND_PLURAL[state.kind]} could not be listed (HTTP ${response.status}).`;
        }
      } catch {
        error = "The server did not answer.";
      }
      if (disposed || ticket !== requested) {
        return;
      }
      inflight = null;
      state.loading = false;
      state.listing = listing;
      state.error = error;
      if (gone) {
        state.open = false;
        state.removed = true;
      }
      render();
    }

    function open() {
      if (disposed || state.open) {
        return Promise.resolve();
      }
      state.open = true;
      state.error = null;
      return load();
    }

    function close() {
      if (disposed || !state.open) {
        return;
      }
      clearFilterTimer();
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
      return load();
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
      deps.hold?.(
        new Promise((resolve) => {
          decided = resolve;
        }),
      );
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
        state.error = switchFailure(response.status, response.body, checkout);
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
   * @param {(ref: string) => void} choose
   */
  function paint(parts, model, choose) {
    // A folder Git does not take for a repository's root has no selector after all.
    parts.root.hidden = model.removed;
    // Shown while the list is closed too: the page is no longer what the server shows.
    parts.staleText.textContent = model.stale ?? "";
    parts.stale.hidden = model.stale === null;
    const refKey = JSON.stringify(model.selectedRef);
    if (parts.label.dataset.refKey !== refKey) {
      parts.releaseCopies?.();
      parts.label.dataset.refKey = refKey;
      parts.label.replaceChildren();
      if (model.selectedRef !== null) {
        parts.label.appendChild(
          window.metabrowser.refChip(model.selectedRef.name, {
            label: model.selectedRef.label,
            kind: model.selectedRef.kind,
            copy: "sibling",
          }),
        );
      } else if (model.pullNumber !== null) {
        const number = document.createElement("span");
        number.className = "source-ref-selector-pull-number";
        number.textContent = model.pullNumber;
        parts.label.append(model.button.slice(0, -model.pullNumber.length), number);
      } else if (model.commitId !== null) {
        // A commit's ID is set in the commit-ID face wherever it appears
        // (docs/design-system.md, "Git Commit Summary").
        const id = document.createElement("span");
        id.className = "git-commit-sha";
        id.textContent = model.commitId;
        parts.label.append(model.button.slice(0, -model.commitId.length), id);
      } else {
        parts.label.textContent = model.button;
      }
      parts.releaseCopies = window.metabrowser.mountRefCopies(parts.toggle, parts.buttonHost);
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
    parts.filter.placeholder = `Filter ${KIND_PLURAL[model.kind]}`;
    parts.filter.setAttribute("aria-label", `Filter ${KIND_PLURAL[model.kind]}`);
    if (parts.filter.value !== model.query) {
      parts.filter.value = model.query;
    }
    parts.list.setAttribute("aria-busy", String(model.loading || model.switching));
    // One row takes Tab at a time: the served one, else the first. Arrow keys move
    // among the rest.
    const current = model.rows.findIndex((row) => row.current);
    const roving = current >= 0 ? current : 0;
    const items = model.rows.map((row, index) => {
      const item = document.createElement("li");
      const button = document.createElement("button");
      button.type = "button";
      button.className = "menu-item source-ref-selector-row";
      button.disabled = model.switching;
      button.tabIndex = index === roving ? 0 : -1;
      if (row.current) {
        button.setAttribute("aria-current", "true");
      }
      const name = document.createElement("span");
      name.className = "source-ref-selector-name";
      // A mirror's branch is a remote chip and its tag a tag chip, as on the button; a
      // checkout's own branch is a local chip. The default branch is not drawn as trunk:
      // trunk is the server's `is_trunk` on a Git ref, and the mirror's default need not
      // be the branch the history draws solid. The badge below says "default", or
      // "checked out" for the branch a checkout's HEAD is on, in words
      // (docs/design-system.md, "Branch Chips").
      name.appendChild(
        window.metabrowser.refChip(row.ref, { label: row.name, kind: row.chip, copy: false }),
      );
      button.append(name);
      if (row.default || row.checkedOut) {
        const badge = document.createElement("span");
        badge.className = "source-ref-selector-badge";
        badge.textContent = row.default ? "default" : "checked out";
        button.append(badge);
      }
      // The commit as the history shows one: Git's short ID in the commit-ID face, then
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
      button.append(commit, age);
      button.addEventListener("click", () => choose(row.ref));
      // The row's name is cut short with an ellipsis when it is wider than the list;
      // the tooltip then carries the whole name. pointerenter comes before the
      // mouseenter the shell's tooltip listens for.
      button.addEventListener("pointerenter", () => {
        if (name.scrollWidth > name.clientWidth) {
          button.dataset.tipText = row.name;
        } else {
          delete button.dataset.tipText;
        }
      });
      item.append(button);
      return item;
    });
    parts.list.replaceChildren(...items);
    parts.note.textContent = model.note;
    parts.note.hidden = model.note === "";
    parts.error.textContent = model.error ?? "";
    parts.error.hidden = model.error === null;
  }

  /**
   * Build the selector's elements inside *element*. Browser only.
   *
   * @param {HTMLElement} element
   * @param {boolean} checkout Whether the page is a checkout's, with its third list.
   * @returns {MetabrowserSourceRefSelectorParts}
   */
  function build(element, checkout) {
    // The server draws the button in the Files toolbar's row, so the row keeps its layout
    // from first paint. That button is adopted, not replaced: focus a reader put on it
    // before this module arrived stays where it is.
    const drawn = /** @type {HTMLButtonElement | null} */ (
      element.querySelector("button.source-ref-selector-toggle")
    );
    const toggle = drawn ?? document.createElement("button");
    toggle.type = "button";
    toggle.setAttribute("aria-haspopup", "dialog");
    toggle.dataset.tipText = "Switch branch or tag";
    const label =
      /** @type {HTMLElement | null} */ (toggle.querySelector(".source-ref-selector-label")) ??
      document.createElement("span");
    label.className = "source-ref-selector-label";
    const caret =
      /** @type {HTMLElement | null} */ (toggle.querySelector(".chip-menu-caret")) ??
      document.createElement("span");
    toggle.className = "chip chip-menu-trigger source-ref-selector-toggle disclosure-toggle";
    caret.className = "chip-menu-caret";
    caret.setAttribute("aria-hidden", "true");
    caret.innerHTML = window.MetabrowserIcons?.toggle ?? "";
    if (drawn === null) {
      toggle.append(label, caret);
    }
    // What a checkout's page says when the server comes to show something else, as a
    // freshness row: at the foot of the navigation pane, where a mirror's makes the same
    // offer, so every tab shows it. The Pulls tab's requests and a comparison's are
    // refused as the Files tab's are, and this button is in the Files toolbar, which the
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
    reload.textContent = "Reload";
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
    filter.className = "source-ref-selector-filter";
    filter.autocomplete = "off";
    filter.spellcheck = false;
    const list = document.createElement("ul");
    list.className = "source-ref-selector-list";
    const note = document.createElement("p");
    note.className = "source-ref-selector-note";
    note.setAttribute("role", "status");
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
    panel.append(workingTree, kinds, filter, list, note, error);
    // The button's own box, which a ref chip's copy control is placed against, so that
    // the list's containing block stays the toolbar and the list spans the pane. Drawn
    // by the server around its button, and adopted with it.
    const buttonHost =
      /** @type {HTMLElement | null} */ (
        toggle.parentElement?.closest(".source-ref-selector-button")
      ) ?? document.createElement("span");
    buttonHost.className = "source-ref-selector-button";
    // The list is put in by `mount`, once its kinds are bound.
    if (drawn === null) {
      buttonHost.append(toggle);
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
      buttonHost,
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
      note,
      error,
    };
  }

  /**
   * Keep focus in the selector across the Files toolbar's refills. Browser only.
   *
   * The selector leads the toolbar's row, which app.js draws again whenever a filter or a
   * tally changes, while the index warms up too (renderNavFilterBar). It carries this
   * element over rather than drawing it, so the list stays open with what was typed, but
   * the element is out of the page for that moment, and an element taken out loses focus.
   * So the control that had it gets it back, unless the reader has since put focus
   * somewhere else: elsewhere by a key, or anywhere by a press outside the selector.
   * Focus events do not fire in a page that is not focused, a background window's or a
   * headless test's, so a refill that finds nothing recorded asks *fallback*: an open
   * list's filter box, since a key or a press that takes focus out of the selector closes
   * the list.
   *
   * @param {HTMLElement} element
   * @param {() => HTMLElement | null} fallback
   * @param {AbortSignal} signal
   * @returns {() => void} What stops it.
   */
  function keepFocusAcross(element, fallback, signal) {
    const bar = element.closest("[data-nav-toolbar]");
    if (bar === null) {
      return () => {};
    }
    /** @type {HTMLElement | null} */
    let focused = null;
    element.addEventListener(
      "focusin",
      (event) => {
        focused = /** @type {HTMLElement} */ (event.target);
      },
      { signal },
    );
    for (const type of ["focusin", "pointerdown"]) {
      document.addEventListener(
        type,
        (event) => {
          if (!element.contains(/** @type {Node | null} */ (event.target))) {
            focused = null;
          }
        },
        { signal, capture: true },
      );
    }
    // The refill replaces the bar's children and puts this element back before the
    // observer is told, so focus is back before the frame paints.
    const refills = new MutationObserver(() => {
      const active = document.activeElement;
      if (active === null || active === document.body) {
        (focused?.isConnected && element.contains(focused) ? focused : fallback())?.focus({
          preventScroll: true,
        });
      }
    });
    refills.observe(bar, { childList: true });
    return () => refills.disconnect();
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
    const parts = build(element, checkout);
    /** @type {ReturnType<typeof createSelector> | null} */
    let selector = null;
    const choose = (/** @type {string} */ ref) => void selector?.choose(ref);
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
        render: (model) => paint(parts, model, choose),
        navigate: (href) => window.location.assign(href),
        currentView: () => window.location.pathname,
        hold: (going) => window.MetabrowserSourcePinGuard?.hold(going),
      },
      { shown: window.METABROWSER_SOURCE_PIN ?? null, checkout },
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
    // One popup at a time. The toolbar's filter menus close on a press outside the
    // toolbar, and this button is in it, so opening the list closes an open filter menu
    // the way a reader would, by its trigger.
    const closeToolbarMenu = () => {
      if (parts.panel.hidden) {
        /** @type {HTMLElement | null | undefined} */ (
          element
            .closest("[data-nav-toolbar]")
            ?.querySelector('.chip-menu[aria-expanded="true"] [data-chip-menu-toggle]')
        )?.click();
      }
    };
    parts.toggle.addEventListener(
      "click",
      () => {
        closeToolbarMenu();
        void mounted.toggle();
        focusOpenFilter();
      },
      { signal },
    );
    // Bound before the list joins the toolbar, so the toolbar's own binding is the one that
    // fits the kinds' joined group to its line. A binding made inside a toolbar fits the
    // groups under it too (filter-controls.js#keepJoinedGroupsFitted), and two fitting one
    // group each took the other's measuring for a change to fit again, without end: the
    // page stopped answering when the list opened.
    const unbindKinds = chipControls().bind(parts.kinds, {
      onChange(key, value, select) {
        if (key === KIND_GROUP && select === "one") {
          void mounted.setKind(/** @type {MetabrowserSourceRefKind} */ (value));
        }
      },
    });
    element.append(parts.panel);
    // The toolbar's own chip controls are bound on the whole toolbar (app.js,
    // initFilterBar), and would take a kind for a filter's value: a click or an arrow key
    // on the kinds, which the binding above has handled, goes no further.
    parts.kinds.addEventListener("click", (event) => event.stopPropagation(), { signal });
    parts.kinds.addEventListener(
      "keydown",
      (event) => {
        if (["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) {
          event.stopPropagation();
        }
      },
      { signal },
    );
    const stopKeepingFocus = keepFocusAcross(
      element,
      () => (parts.panel.hidden ? null : parts.filter),
      signal,
    );
    parts.filter.addEventListener("input", () => mounted.setQuery(parts.filter.value), {
      signal,
    });
    const rows = () =>
      /** @type {HTMLButtonElement[]} */ ([...parts.list.querySelectorAll("button")]);
    // While the list is open, Escape closes it from anywhere on the page and Tab stays
    // inside it, wrapping at either end, as in a dialog.
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
        if (event.key === "Escape") {
          event.preventDefault();
          mounted.close();
          parts.toggle.focus();
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
        const list = rows();
        const index = list.indexOf(/** @type {HTMLButtonElement} */ (event.target));
        if (index < 0 && event.target !== parts.filter) {
          return;
        }
        const next = moveRow(event.key, index, list.length);
        if (next === null) {
          return;
        }
        event.preventDefault();
        if (next < 0) {
          parts.filter.focus();
          return;
        }
        for (const [at, row] of list.entries()) {
          row.tabIndex = at === next ? 0 : -1;
        }
        list[next]?.focus();
      },
      { signal },
    );
    // Focus that leaves the selector for another part of the page closes the list.
    element.addEventListener(
      "focusout",
      (event) => {
        const to = /** @type {Node | null} */ (event.relatedTarget);
        if (!parts.panel.hidden && to !== null && !element.contains(to)) {
          mounted.close();
        }
      },
      { signal },
    );
    // A pointer press anywhere else closes the list, as a menu closes.
    document.addEventListener(
      "pointerdown",
      (event) => {
        if (!parts.panel.hidden && !element.contains(/** @type {Node | null} */ (event.target))) {
          mounted.close();
        }
      },
      { signal },
    );
    const handle = Object.freeze({
      ...mounted,
      // The control a key's badge marks, and what the key does: the button's path,
      // except that it opens the list rather than toggling it.
      button: parts.toggle,
      activate() {
        closeToolbarMenu();
        const opened = mounted.open();
        focusOpenFilter();
        return opened;
      },
      dispose() {
        listening.abort();
        stopKeepingFocus();
        unbindKinds();
        mounted.dispose();
        parts.releaseCopies?.();
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
    createSelector,
    describe,
    mount,
    mounted: () => mountedSelector,
    moveRow,
    shownLabel,
  });
})();

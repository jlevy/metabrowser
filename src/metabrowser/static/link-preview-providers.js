// What a link card says of the page an in-app link opens, and what resting on the link
// starts loading (docs/project/specs/active/plan-2026-11-26-link-preview-tooltips.md,
// "Data and Prefetch").
//
// One provider for each kind of in-app link registers with the card's registry,
// `window.MetabrowserLinkPreviews.provide(kind, {summary, known, prefetch})` (static/
// link-previews.js), which asks `known` as the pointer arrives on a link and `summary` and
// `prefetch` once it has rested there. A summary is plain text, never markup, and says only
// what its data gives: a pull request's title and state from the catalog's exact-number
// search, a stack's top member and size from the stacks snapshot, a commit's subject,
// author, and age from the Commits panel's own detail cache, a folder's totals from what the
// page already holds, and nothing for a file or the list. Only a commit's card says its
// object is missing: nothing the page holds lists every file a link can open (`knownPath`).
// A prefetch starts what the click opens: the page's plugin assets, a pull request's record,
// a commit prepared as a hover on its row prepares it, and a file's or folder's View on
// GitHub answer.
//
// The registry keeps no answer, so each provider keeps what it reads only for as long as it
// stays true, and reads again what failed or was not yet known: a pull request's summary and
// the stacks snapshot for as long as the Pulls tab's pollers wait between their reads, a
// commit's for as long as the Commits panel keeps it, and a folder's never, since the page's
// own state answers at once. What is kept is bounded.
//
// Every read is one the app already makes for that object, from the cache alone: none asks
// GitHub, fetches from origin, or counts a view, and none is aborted, since an aborted
// request counts against the page's `fetch_aborts` budget. A file's body is not prefetched:
// the tree's hover prefetch has no seam a link can call within the startup scripts' budget
// (the plan's Follow-ups).

(() => {
  /** @typedef {"open" | "closed" | "merged" | "draft"} PullState */
  /**
   * What a card says of its object, each field plain text: a title, a pull request's state,
   * a line of detail, and why the object is not there.
   *
   * @typedef {{title?: string, state?: PullState, detail?: string, missing?: string}} Summary
   */
  /**
   * The object an in-app link opens, as the card's registry names it.
   *
   * @typedef {{kind: "pull", number: number, tab: "" | "files" | "checks", file: string}} PullSubject
   * @typedef {{kind: "stack", number: number, file: string}} StackSubject
   * @typedef {{kind: "commit", revision: string}} CommitSubject
   * @typedef {{
   *   kind: "file" | "folder", path: string, opens: "here" | "working-tree" | "served-revision",
   *   target: {path: string, query?: string, fragment?: string},
   * }} PathSubject
   * @typedef {{kind: "pulls"}} PullsSubject
   */
  /**
   * @typedef {Pick<MetabrowserPublicSdk,
   *   | "directoryTotals" | "ensureKindAssets" | "fetchPluginData"
   *   | "formatAge" | "formatFileCount" | "formatSize" | "navigation"
   *   | "prefetchCounterpart" | "repository">} Sdk
   * @typedef {Awaited<ReturnType<Sdk["fetchPluginData"]>>} PluginData
   */
  /**
   * @template S
   * @typedef {{
   *   summary(subject: S, how: {mb: Sdk}): Promise<Summary | null>,
   *   known(subject: S, how: {mb: Sdk}): Summary | null,
   *   prefetch(subject: S, how: {mb: Sdk}): Promise<void>,
   * }} Provider
   */
  /**
   * @typedef {{
   *   provide(kind: "pull", provider: Provider<PullSubject>): void,
   *   provide(kind: "stack", provider: Provider<StackSubject>): void,
   *   provide(kind: "commit", provider: Provider<CommitSubject>): void,
   *   provide(kind: "file" | "folder", provider: Provider<PathSubject>): void,
   *   provide(kind: "pulls", provider: Provider<PullsSubject>): void,
   * }} Registry
   */

  // ── How long an answer is kept ─────────────────────────────

  /**
   * How long a pull request's summary and the stacks snapshot are reused before a rest reads
   * them again: as long as the Pulls tab's pollers wait between their reads while it is shown
   * (`SLOW_POLL_MS` in builtin_plugins/github/pull-page.js, `STACKS_POLL_MS` in
   * builtin_plugins/github/pull-stacks.js), so a card is never staler than that tab, and a
   * second while the snapshot says it is being refreshed, as the pollers then wait
   * (`FAST_POLL_MS`, `STACKS_REFRESHING_POLL_MS`). Those pollers are the github plugin's own
   * and ask GitHub to refresh what is due, so a card reads the routes itself.
   * tests/test_link_preview_providers_session.py holds these equal to the plugin's.
   */
  const REUSE_MS = 30_000;
  const REFRESHING_REUSE_MS = 1_000;

  // ── Pull requests ──────────────────────────────────────────

  // The states a catalog row names (pull_catalog.py, `PullSearchRow`). A row naming any
  // other gives its card no state: only the pull request's own metadata establishes one.
  /** @type {ReadonlyArray<string>} */
  const PULL_STATES = Object.freeze(["open", "closed", "merged", "draft"]);
  /**
   * How many pull requests' summaries a page keeps, by number, so a rest on a link again
   * asks nothing, and how many it has warmed. In Node 24 on 2026-11-26, 256 summaries held
   * 32 KB of heap with 40-character titles and 88 KB with 256-character titles, each string
   * flat and distinct (median of five).
   */
  const PULLS_KEPT_MAX = 256;
  /** Each summary, by number, and when it was read: `Date.now()`. */
  /** @type {Map<number, {at: number, summary: Summary | null}>} */
  const pullSummaries = new Map();
  /** @type {Map<number, Promise<Summary | null>>} */
  const pullReads = new Map();
  /** The numbers whose record this page has read with `warm=1`, oldest first. */
  /** @type {Map<number, true>} */
  const warmedPulls = new Map();

  /**
   * A pull request's title and state, from the catalog's exact-number search
   * (`GET /api/plugin/github/pulls?q=<n>`), the read Quick Search makes for a number: the
   * cache alone, in about a millisecond. A number the catalog does not hold has no summary,
   * and the card names the link's identity alone. A kept answer is reused for `REUSE_MS`;
   * one that says nothing is kept only from a whole catalog no refresh is filling, and a
   * read that failed is not kept, so the next rest asks again.
   *
   * @param {PullSubject} subject
   * @param {{mb: Sdk}} how
   * @returns {Promise<Summary | null>}
   */
  function summarizePull(subject, { mb }) {
    const { number } = subject;
    const kept = keptPull(number);
    if (kept !== undefined) {
      return Promise.resolve(kept);
    }
    let read = pullReads.get(number);
    if (read === undefined) {
      const reading = readPull(mb, number);
      pullReads.set(number, reading);
      void reading.then(() => pullReads.delete(number));
      read = reading;
    }
    return read;
  }

  /**
   * The summary kept for *number* while it is fresh, or undefined.
   *
   * @param {number} number
   * @returns {Summary | null | undefined}
   */
  function keptPull(number) {
    const kept = pullSummaries.get(number);
    if (kept === undefined) {
      return undefined;
    }
    if (Date.now() - kept.at >= REUSE_MS) {
      pullSummaries.delete(number);
      return undefined;
    }
    remember(pullSummaries, number, kept);
    return kept.summary;
  }

  /**
   * @param {Sdk} mb
   * @param {number} number
   * @returns {Promise<Summary | null>}
   */
  async function readPull(mb, number) {
    const at = Date.now();
    /** @type {PluginData} */
    let answer;
    try {
      answer = await mb.fetchPluginData("github", "pulls", { q: String(number) });
    } catch {
      // A read that failed gives the card nothing to add, and the next rest asks again.
      return null;
    }
    const rows = Array.isArray(answer.rows) ? answer.rows : [];
    const row = rows.find(
      (/** @type {unknown} */ candidate) =>
        typeof candidate === "object" &&
        candidate !== null &&
        /** @type {{number?: unknown}} */ (candidate).number === number,
    );
    const summary = row === undefined ? null : pullCard(row);
    // A catalog still being filled, or not yet whole, may hold the number at the next rest.
    if (summary !== null || (answer.complete === true && answer.refreshing !== true)) {
      remember(pullSummaries, number, { at, summary });
    }
    return summary;
  }

  /**
   * A row's title and state, or null for a row that names neither.
   *
   * @param {{title?: unknown, state?: unknown}} row
   * @returns {Summary | null}
   */
  function pullCard(row) {
    const { title, state } = row;
    /** @type {Summary} */
    const summary = {
      ...(typeof title === "string" && title ? { title } : {}),
      ...(typeof state === "string" && PULL_STATES.includes(state)
        ? { state: /** @type {PullState} */ (state) }
        : {}),
    };
    return Object.keys(summary).length > 0 ? summary : null;
  }

  /**
   * The pull request's page: the github plugin's page assets, and its record read from the
   * cache with `warm=1`, as the Pulls tab warms a pull request it may open, which counts no
   * view and asks GitHub nothing. The read starts the server's Markdown child, which a cold
   * page's first paint otherwise waits on (sidekick.py, `pull_handler`), and keeps the
   * record parsed there. Once a page for each number; a warming that failed is tried again.
   *
   * @param {PullSubject} subject
   * @param {{mb: Sdk}} how
   * @returns {Promise<void>}
   */
  function prefetchPullPage(subject, { mb }) {
    const { number } = subject;
    /** @type {Array<Promise<unknown>>} */
    const work = [mb.ensureKindAssets("pull-request")];
    if (!warmedPulls.has(number)) {
      remember(warmedPulls, number, true);
      work.push(
        mb.fetchPluginData("github", "pull", { number, warm: 1 }).catch(() => {
          // Not warmed; a later rest may try again.
          warmedPulls.delete(number);
        }),
      );
    }
    return settled(work);
  }

  // ── Stacks ─────────────────────────────────────────────────

  /**
   * A read of the stacks snapshot: when it was asked for, and, once it has answered, the
   * snapshot's stacks and how long the answer is reused.
   *
   * @typedef {{at: number, read: Promise<Array<StackMembers> | null>,
   *   answer?: {stacks: Array<StackMembers>, reuseMs: number}}} StacksRead
   */
  /** The one read of the snapshot a page reuses. @type {StacksRead | null} */
  let stacksRead = null;

  /** @typedef {{number: number, pulls: number[], titles: Array<string | null>}} StackMembers */

  /**
   * A stack's top member's title and its size, from the stacks snapshot
   * (`GET /api/plugin/github/stacks`), which reads the cache alone. A stack the snapshot
   * does not hold has no summary: an incomplete snapshot never means a stack is gone, and
   * the next read of the snapshot may hold it.
   *
   * @param {StackSubject} subject
   * @param {{mb: Sdk}} how
   * @returns {Promise<Summary | null>}
   */
  async function summarizeStack(subject, { mb }) {
    return stackCard(await readStacks(mb), subject.number);
  }

  /**
   * The stack's summary from the snapshot read last, while it is reused, or null.
   *
   * @param {StackSubject} subject
   * @param {{mb: Sdk}} _how
   * @returns {Summary | null}
   */
  function knownStack(subject, _how) {
    return stackCard(freshStacks()?.answer?.stacks ?? null, subject.number);
  }

  /**
   * @param {Array<StackMembers> | null} stacks
   * @param {number} number
   * @returns {Summary | null}
   */
  function stackCard(stacks, number) {
    const stack = stacks?.find((candidate) => candidate.number === number);
    if (stack === undefined) {
      return null;
    }
    // GitHub lists a stack's members from its base (pull_stacks.py, `NativeStack`), so the
    // top is the last.
    const top = stack.titles[stack.titles.length - 1];
    const count = stack.pulls.length;
    return {
      ...(typeof top === "string" && top ? { title: top } : {}),
      detail: `${count} pull request${count === 1 ? "" : "s"}`,
    };
  }

  /** The snapshot's read while it is reused: still on its way, or answered and fresh. */
  function freshStacks() {
    const read = stacksRead;
    if (read === null) {
      return null;
    }
    const reuseMs = read.answer?.reuseMs ?? REUSE_MS;
    return Date.now() - read.at < reuseMs ? read : null;
  }

  /**
   * @param {Sdk} mb
   * @returns {Promise<Array<StackMembers> | null>}
   */
  function readStacks(mb) {
    const fresh = freshStacks();
    if (fresh !== null) {
      return fresh.read;
    }
    /** @type {StacksRead} */
    const reading = { at: Date.now(), read: Promise.resolve(null) };
    reading.read = mb.fetchPluginData("github", "stacks", {}).then(
      (answer) => {
        const stacks = stackMembers(answer);
        if (stacks === null) {
          // Not a snapshot: not reused, so the next rest asks again.
          forgetStacks(reading);
        } else {
          reading.answer = {
            stacks,
            reuseMs: answer.refreshing === true ? REFRESHING_REUSE_MS : REUSE_MS,
          };
        }
        return stacks;
      },
      () => {
        // A read that failed is not reused: the next rest asks again.
        forgetStacks(reading);
        return null;
      },
    );
    stacksRead = reading;
    return reading.read;
  }

  /** @param {StacksRead} reading */
  function forgetStacks(reading) {
    if (stacksRead === reading) {
      stacksRead = null;
    }
  }

  /**
   * The snapshot's stacks, each its number, its members, and their titles, or null for an
   * answer that is not one.
   *
   * @param {PluginData} answer
   * @returns {Array<StackMembers> | null}
   */
  function stackMembers(answer) {
    if (!Array.isArray(answer.stacks)) {
      return null;
    }
    return answer.stacks.flatMap((/** @type {unknown} */ value) => {
      const stack = /** @type {{number?: unknown, pulls?: unknown, titles?: unknown}} */ (
        typeof value === "object" && value !== null ? value : {}
      );
      const { number, pulls, titles } = stack;
      return typeof number === "number" &&
        Array.isArray(pulls) &&
        pulls.length > 0 &&
        Array.isArray(titles) &&
        titles.length === pulls.length
        ? [{ number, pulls, titles }]
        : [];
    });
  }

  /**
   * A stack's page: the github plugin's page assets.
   *
   * @param {StackSubject} _subject
   * @param {{mb: Sdk}} how
   * @returns {Promise<void>}
   */
  function prefetchStackPage(_subject, { mb }) {
    return settled([mb.ensureKindAssets("pull-stack")]);
  }

  // ── Commits ────────────────────────────────────────────────

  const COMMIT_MISSING = "Not in this repository";

  /**
   * A commit's subject, then its author and age, from the Commits panel's own detail cache
   * and missing set (`MetabrowserGitPanel.commitSummary`), which never fetches from origin.
   * Nothing is kept here: the panel's cache is what the card says, so the card follows it,
   * and a commit the panel no longer calls missing after its Refresh or a fetch is read
   * again. The panel comes with the shell's tools once the first tree is in (server.py,
   * `shell-tools`); a rest before then has no summary, and the card names the commit alone.
   *
   * @param {CommitSubject} subject
   * @param {{mb: Sdk}} how
   * @returns {Promise<Summary | null>}
   */
  async function summarizeCommit(subject, { mb }) {
    const panel = window.MetabrowserGitPanel;
    return panel === undefined ? null : commitCard(await panel.commitSummary(subject.revision), mb);
  }

  /**
   * The commit's summary from what the panel holds now, with no read.
   *
   * @param {CommitSubject} subject
   * @param {{mb: Sdk}} how
   * @returns {Summary | null}
   */
  function knownCommit(subject, { mb }) {
    const panel = window.MetabrowserGitPanel;
    return panel === undefined ? null : commitCard(panel.keptCommitSummary(subject.revision), mb);
  }

  /**
   * @param {MetabrowserGitCommitSummary | null} commit
   * @param {Sdk} mb
   * @returns {Summary | null}
   */
  function commitCard(commit, mb) {
    if (commit === null) {
      return null;
    }
    if (commit.missing) {
      return { missing: COMMIT_MISSING };
    }
    const age =
      commit.committedAt === null
        ? ""
        : mb.formatAge(commit.committedAt, { style: "relative" }).label;
    const detail = [commit.author ?? "", age].filter(Boolean).join(" · ");
    if (!commit.subject && !detail) {
      return null;
    }
    return {
      ...(commit.subject ? { title: commit.subject } : {}),
      ...(detail ? { detail } : {}),
    };
  }

  /**
   * A commit's page: the commit prepared as a hover on its row prepares it
   * (`MetabrowserGitPanel.prefetchCommit`), and nothing for one the repository lacks.
   *
   * @param {CommitSubject} subject
   * @param {{mb: Sdk}} _how
   * @returns {Promise<void>}
   */
  function prefetchCommitPage(subject, _how) {
    const panel = window.MetabrowserGitPanel;
    return panel === undefined
      ? Promise.resolve()
      : settled([panel.prefetchCommit(subject.revision)]);
  }

  // ── Files and folders ──────────────────────────────────────

  /**
   * A folder's file count and size where the tree has totaled it, from the page's own state
   * at the moment it is asked, so nothing is read or kept and the card says what the tree
   * holds now; nothing for a file, whose type is its mark's to say (`fileTypeIcon`) and its
   * name's extension, so no line repeats it.
   *
   * No card says a file or folder is missing, because nothing the page holds is every path
   * a link can open, so the absence of one from it proves nothing. A served folder's Quick
   * File catalog, even whole, leaves out what the server still opens: a symbolic link and a
   * gitignored file (`_catalog_entry_filter` in inventory_engine/providers/python_inventory.py)
   * and whatever the walker hides, a dot-named file or anything under a dot-named folder
   * (`is_visible` in fs_paths.py). A pin's lists its blobs alone, and its file route opens a
   * folder or a submodule named with no closing slash, which a link names as a file
   * (git/content_routes.py, `git_revision_catalog` and `git_revision_file`). So the
   * providers read no catalog (`Sdk` picks none).
   *
   * @param {PathSubject} subject
   * @param {{mb: Sdk}} how
   * @returns {Summary | null}
   */
  function knownPath(subject, { mb }) {
    if (subject.kind !== "folder") {
      return null;
    }
    const totals = mb.directoryTotals.get(servedPath(subject));
    return totals?.state === "complete"
      ? {
          detail: `${mb.formatFileCount(totals.totalFiles)} · ${mb.formatSize(totals.totalBytes)}`,
        }
      : null;
  }

  /**
   * @param {PathSubject} subject
   * @param {{mb: Sdk}} how
   * @returns {Promise<Summary | null>}
   */
  function summarizePath(subject, how) {
    return Promise.resolve(knownPath(subject, how));
  }

  /**
   * The subject's path as the served tree's inventory spells it, the identity its totals
   * and its addresses use: the path of the navigation target the resolver gave the link
   * (static/repository-links.js, `viewTarget`), on a pin the GitPath wire, less a folder's
   * closing slash. The spelling is the resolver's alone.
   *
   * @param {PathSubject} subject
   * @returns {string}
   */
  function servedPath(subject) {
    return subject.target.path.replace(/\/+$/, "");
  }

  /**
   * A file's or folder's page: its View on GitHub answer, asked for as the page itself asks
   * when it starts loading, so the button comes with the header (plugin-sdk-views.js,
   * `prefetchCounterpart`). Keep the prefetch slot until that request finishes. Only a page
   * on a GitHub repository draws the button.
   *
   * @param {PathSubject} subject
   * @param {{mb: Sdk}} how
   * @returns {Promise<void>}
   */
  function prefetchPathPage(subject, { mb }) {
    // The SDK's view helpers bring it, so a page that has drawn no view has none yet.
    if (!mb.repository || typeof mb.prefetchCounterpart !== "function") {
      return Promise.resolve();
    }
    let page;
    try {
      // The page's own address, as its header asks: the target's path, with no query or
      // fragment, which name a place on the page rather than another page.
      page = mb.navigation.href({ path: subject.target.path });
    } catch {
      // An address the navigation codec will not spell has no page to warm.
      return Promise.resolve();
    }
    return mb.prefetchCounterpart(page);
  }

  // ── The list of pull requests ──────────────────────────────

  /**
   * The list has nothing to add to its card.
   *
   * @param {PullsSubject} _subject
   * @param {{mb: Sdk}} _how
   * @returns {Summary | null}
   */
  function knownPulls(_subject, _how) {
    return null;
  }

  /**
   * @param {PullsSubject} subject
   * @param {{mb: Sdk}} how
   * @returns {Promise<Summary | null>}
   */
  function summarizePulls(subject, how) {
    return Promise.resolve(knownPulls(subject, how));
  }

  /**
   * The list's page: the github plugin's assets for the list's view.
   *
   * @param {PullsSubject} _subject
   * @param {{mb: Sdk}} how
   * @returns {Promise<void>}
   */
  function prefetchPullsPage(_subject, { mb }) {
    return settled([mb.ensureKindAssets("pull-request-list")]);
  }

  // ── Shared ─────────────────────────────────────────────────

  /**
   * Keep *value* under *key* as the newest of *kept*, dropping the oldest past
   * `PULLS_KEPT_MAX`.
   *
   * @template K, V
   * @param {Map<K, V>} kept
   * @param {K} key
   * @param {V} value
   */
  function remember(kept, key, value) {
    kept.delete(key);
    kept.set(key, value);
    for (const oldest of kept.keys()) {
      if (kept.size <= PULLS_KEPT_MAX) {
        break;
      }
      kept.delete(oldest);
    }
  }

  /**
   * Once every piece of *work* has settled. A prefetch that fails is the opened page's to
   * report, so it is not this one's.
   *
   * @param {Array<Promise<unknown>>} work
   * @returns {Promise<void>}
   */
  async function settled(work) {
    await Promise.allSettled(work);
  }

  // The card's registry comes first in this bundle (server.py, `link-previews`); a page
  // where it did not load shows no card, and so asks for nothing here.
  const registry = /** @type {{MetabrowserLinkPreviews?: Registry}} */ (
    /** @type {unknown} */ (window)
  ).MetabrowserLinkPreviews;
  if (registry === undefined) {
    return;
  }
  registry.provide("pull", {
    summary: summarizePull,
    known: (subject) => keptPull(subject.number) ?? null,
    prefetch: prefetchPullPage,
  });
  registry.provide("stack", {
    summary: summarizeStack,
    known: knownStack,
    prefetch: prefetchStackPage,
  });
  registry.provide("commit", {
    summary: summarizeCommit,
    known: knownCommit,
    prefetch: prefetchCommitPage,
  });
  const path = { summary: summarizePath, known: knownPath, prefetch: prefetchPathPage };
  registry.provide("file", path);
  registry.provide("folder", path);
  registry.provide("pulls", {
    summary: summarizePulls,
    known: knownPulls,
    prefetch: prefetchPullsPage,
  });
})();

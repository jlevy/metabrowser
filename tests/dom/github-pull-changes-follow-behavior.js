// Production page, mounted in a pane with a history entry: Changes follows a moved head,
// and what joins that to the reader's place and to the entry's memory, and Docs, which
// draws the same comparison, does the same.
//
// The pure halves are in github-pull-page-session.js: `filesAction`, `followedNote`,
// `rememberedChanges`, and the keeper on a stage of names. This is the join (A4 of review A
// on #745): the page's own `keepPlace` reading which file a block is from the mounted diff's
// `sectionForPath` and `pathForSection`, `pullPlace` and `pullChanges` written into the
// entry, and a page mounted again on that entry reading them back. The diff view is a
// stand-in that lays its files out as blocks of known heights under a 100 px header and
// answers the two accessors from its own section map, as the production view does from its
// (tests/dom/diff-file-jump-session.js holds those). What a browser does with `scrollTop` is
// Chrome's; the pane here is a number.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const { pathToFileURL } = require("node:url");
const { Element, recorded, root, settle, perf } = require("./github-pull-page-mount-behavior.js");

const HEADER = 100;
const NEWER = "9".repeat(40);
const FILES = {
  earlier: [
    ["a.py", 500],
    ["b.py", 500],
    ["c.py", 500],
    ["d.py", 500],
  ],
  newer: [
    ["new.py", 310],
    ["a.py", 500],
    ["b.py", 500],
    ["c.py", 500],
    ["d.py", 500],
  ],
};

async function run() {
  const timers = new Map();
  const resize = new Set();
  // Every listener the document is given, the page's and its stacks' alike; one whose
  // signal aborted, a disposed page's, hears nothing.
  const documentListeners = [];
  const fire = (type) => {
    for (const { name, listener, signal } of documentListeners) {
      if (name === type && signal?.aborted !== true) {
        listener();
      }
    }
  };
  const pane = new Element("pane");
  pane.scrollTop = 0;
  pane.getBoundingClientRect = () => ({ top: 0 });
  Element.prototype.closest = () => pane;
  globalThis.document = {
    visibilityState: "visible",
    addEventListener: (name, listener, options) =>
      documentListeners.push({ name, listener, signal: options?.signal }),
    removeEventListener() {},
    createElement: (tag) => new Element(tag),
    importNode: () => new Element("svg"),
  };
  globalThis.window = {
    location: { pathname: "/pull/7/files", hash: "" },
    history: {
      state: null,
      replaceState(state) {
        this.state = state;
      },
    },
    addEventListener() {},
    setTimeout(callback, delay) {
      const id = Symbol();
      timers.set(id, { callback, delay });
      return id;
    },
    clearTimeout: (id) => timers.delete(id),
  };
  globalThis.DOMParser = class {
    parseFromString() {
      return { body: { firstElementChild: null } };
    }
  };
  globalThis.ResizeObserver = class {
    constructor(callback) {
      this.callback = callback;
      resize.add(callback);
    }
    observe() {}
    disconnect() {
      resize.delete(this.callback);
    }
  };
  const first = structuredClone(recorded.current.body);
  first.probe_every_s = null;
  const earlier = first.record.comparison.head;
  const moved = structuredClone(first);
  moved.record.comparison.head = NEWER;
  moved.record.pull.head.sha = NEWER;
  moved.comparison_route = moved.comparison_route.replace(/right=[0-9a-f]+/, `right=${NEWER}`);
  moved.fetched_at = "2026-09-17T12:00:01Z";
  let current = first;
  /** The bodies the page posted, as its refresh asks. */
  const posts = [];
  globalThis.fetch = async (route, options = {}) => {
    if (options.method === "POST") {
      posts.push(JSON.parse(options.body));
    }
    return String(route).startsWith("/api/plugin/github/pull?")
      ? { status: 200, headers: { get: () => null }, json: async () => structuredClone(current) }
      : { status: 304, headers: { get: () => null } };
  };
  vm.runInThisContext(
    fs.readFileSync(path.join(root, "src/metabrowser/static/pull-route.js"), "utf8"),
  );
  const page = await import(
    pathToFileURL(path.join(root, "src/metabrowser/builtin_plugins/github/pull-page.js")).href
  );
  const mounted = [];
  /** Each comparison a diff was drawn with, as the view was given it. */
  const drawn = [];
  /** A gate the next render waits at, for a comparison that takes a while to read. */
  let gate = null;
  const mount = (body, tab = "files") => {
    const container = new Element("main");
    const handle = page.mountPullPage(
      container,
      { number: 7, tab, reader: { initial: { etag: null, body }, fetchAfterMs: 60000 } },
      {
        perf,
        ensureAsset: async () => {},
        whenIdle: require("./sdk-idle-fixture.js").whenIdle,
        ensureKindAssets: async () => {},
        getRegisteredView: () => ({
          render: async (host, options) => {
            mounted.push(options.comparison.right);
            drawn.push(options.comparison);
            if (gate !== null) {
              await gate;
            }
            const sections = new Map();
            let top = HEADER;
            for (const [name, height] of FILES[
              options.comparison.right === earlier ? "earlier" : "newer"
            ]) {
              const section = new Element("section");
              section.setAttribute("class", "diff-file");
              const at = top;
              section.getBoundingClientRect = () => ({ top: at - pane.scrollTop });
              host.append(section);
              sections.set(name, section);
              top += height;
            }
            return {
              sectionForPath: (name) => sections.get(name) ?? null,
              pathForSection: (section) =>
                [...sections].find(([, held]) => held === section)?.[0] ?? null,
              dispose() {},
            };
          },
        }),
        ...require("./sdk-ref-fixture.js").refHelpers(document),
        formatAge: () => ({ label: "now", className: "age" }),
        formatTimestamp: () => "now",
        navigation: { href: () => "/view/" },
        sourceKind: () => "git_revision",
        icons: { toggle: "" },
      },
    );
    handle.activate();
    return { container, handle };
  };
  /**
   * The production page host (static/pull-route.js) over this pane, mounting the record
   * now served, with the shell's address writes as app.js makes them (`pullPageHostDeps`):
   * `pushState(null, …)` and `replaceState(null, …)`. Only the entry the address is on is
   * held here, so a push and a replacement both leave it with no state.
   */
  const hosted = () => {
    let claims = 0;
    let opened = null;
    const leave = (href) => {
      window.location.pathname = href;
      window.history.state = null;
    };
    const host = window.MetabrowserPullRoute.createPullPageHost({
      claim: () => ++claims,
      isCurrent: (claim) => claim === claims,
      mount: async (_claim, route) => {
        opened = mount(current, route.tab);
        return opened.handle;
      },
      mountList: async () => null,
      pathname: () => window.location.pathname,
      pushHref: leave,
      replaceHref: leave,
    });
    return { ...host, opened: () => opened };
  };
  /** The pane scrolled and stayed still: the place's write timer fires. */
  const scrolledAndStill = () => {
    pane.events.get("scroll")();
    for (const [id, timer] of [...timers]) {
      if (timer.delay === page.PLACE_WRITE_MS) {
        timers.delete(id);
        timer.callback();
      }
    }
  };
  const painted = async (handle) => {
    await settle();
    await handle.whenFilesReady();
    await settle();
    for (const callback of resize) {
      callback();
    }
  };
  const entry = () => window.history.state ?? {};
  const said = (container, name) => container.querySelector(name)?.textContent ?? null;

  let { container, handle } = mount(first);
  await painted(handle);
  // The reader moves to 120 px into c.py: the entry holds the place by its file, and what
  // Changes shows.
  pane.events.get("wheel")();
  pane.scrollTop = HEADER + 1000 + 120;
  scrolledAndStill();
  assert.deepEqual(entry().pullPlace, { block: 2, offset: 120, top: 1220, file: "c.py" });
  assert.equal(entry().pullChanges.shown.right, earlier);
  assert.deepEqual(
    [entry().pullChanges.from, entry().pullChanges.chosen],
    [null, false],
    "the first diff replaced none, and is no one's choice",
  );

  // The head moves. The newer comparison takes a while to read: the body is empty
  // meanwhile, the pane clamps to its top, and a page reloaded now, as a followed pin
  // reloads it, must still land in c.py (A3).
  let release;
  gate = new Promise((resolve) => {
    release = resolve;
  });
  current = moved;
  fire("visibilitychange");
  await settle();
  assert.deepEqual(mounted, [earlier, NEWER], "Changes follows the newer head");
  pane.scrollTop = 0;
  scrolledAndStill();
  assert.deepEqual(
    entry().pullPlace,
    { block: 2, offset: 120, top: 1220, file: "c.py" },
    "the emptied pane's clamp to the top is not written as the reader's place",
  );
  gate = null;
  release();
  await painted(handle);
  const inNewer = HEADER + 310 + 1000 + 120;
  assert.equal(pane.scrollTop, inNewer, "the reader is in c.py, a file further down, as before");
  const note = "Changes now show this pull request’s newer commits. Show the earlier changes";
  assert.equal(said(container, ".github-pull-followed"), note);
  assert.deepEqual(
    [entry().pullChanges.shown.right, entry().pullChanges.from.right, entry().pullChanges.chosen],
    [NEWER, earlier, false],
  );

  // The reload a followed pin makes: another page on the same entry, the record at the
  // newer head. It says the same line, from the entry, and lands in the same file.
  handle.dispose();
  pane.scrollTop = 0;
  ({ container, handle } = mount(moved));
  await painted(handle);
  assert.equal(said(container, ".github-pull-followed"), note, "a reloaded page says it too");
  assert.equal(pane.scrollTop, inNewer, "and lands in the reader's file");

  // The way back is the reader's choice, which the entry remembers, so the reload the next
  // push makes keeps the earlier diff and offers the newer (A5).
  pane.events.get("wheel")();
  container.querySelector(".github-pull-earlier").events.get("click")();
  await painted(handle);
  assert.equal(mounted.at(-1), earlier);
  assert.equal(pane.scrollTop, HEADER + 1000 + 120, "the way back keeps the file too");
  assert.deepEqual([entry().pullChanges.shown.right, entry().pullChanges.chosen], [earlier, true]);
  handle.dispose();
  pane.scrollTop = 0;
  ({ container, handle } = mount(moved));
  await painted(handle);
  assert.equal(mounted.at(-1), earlier, "a reload keeps the diff the reader went back to");
  assert.equal(said(container, ".github-pull-followed"), null);
  assert.equal(
    said(container, ".github-pull-newer-offer"),
    "This pull request has newer commits. Show the newer changes",
  );
  assert.equal(pane.scrollTop, HEADER + 1000 + 120);
  pane.events.get("wheel")();
  container.querySelector(".github-pull-newer").events.get("click")();
  await painted(handle);
  assert.deepEqual([mounted.at(-1), entry().pullChanges.chosen], [NEWER, false]);
  assert.equal(said(container, ".github-pull-followed"), note);
  assert.equal(pane.scrollTop, inNewer);
  handle.dispose();

  // A file the newer diff does not have: the place is the top of the block at its index,
  // not that block's line at the old offset (A8).
  window.history.state = {
    ...entry(),
    pullPlace: { block: 2, offset: 120, top: 1220, file: "gone.py" },
  };
  pane.scrollTop = 0;
  ({ container, handle } = mount(moved));
  await painted(handle);
  assert.equal(pane.scrollTop, HEADER + 310 + 500, "the top of the third file");
  handle.dispose();

  // While a followed diff is read the body is emptied, with nothing in it to measure, so
  // what replaces it then keeps the place already kept (B1 of review B on #745). A third
  // head, laid out as the newer one, so c.py is a file further down again.
  const NEWEST = "8".repeat(40);
  const newest = structuredClone(moved);
  newest.record.comparison.head = NEWEST;
  newest.record.pull.head.sha = NEWEST;
  newest.comparison_route = newest.comparison_route.replace(/right=[0-9a-f]+/, `right=${NEWEST}`);
  newest.fetched_at = "2026-09-17T12:00:02Z";
  const inEarlier = HEADER + 1000 + 120;
  const inC = { block: 2, offset: 120, top: 1220, file: "c.py" };
  /** The next renders wait until the answer is called, as a comparison read slowly does. */
  const slowRead = () => {
    let open;
    gate = new Promise((resolve) => {
      open = resolve;
    });
    return () => {
      gate = null;
      open();
    };
  };
  /** A page on a new entry, the reader 120 px into c.py of the earlier diff. */
  const readingC = async () => {
    window.history.state = null;
    pane.scrollTop = 0;
    current = first;
    const opened = mount(first);
    await painted(opened.handle);
    pane.events.get("wheel")();
    pane.scrollTop = inEarlier;
    scrolledAndStill();
    assert.deepEqual(entry().pullPlace, inC);
    return opened;
  };
  /** The head moves while the pane shows c.py, and Changes follows it into a slow read. */
  const followedSlowly = async () => {
    const read = slowRead();
    current = moved;
    fire("visibilitychange");
    await settle();
    assert.equal(mounted.at(-1), NEWER);
    pane.scrollTop = 0;
    scrolledAndStill();
    return read;
  };

  // A second push read while the first followed diff is still read: Changes follows again,
  // from the emptied body.
  ({ container, handle } = await readingC());
  release = await followedSlowly();
  current = newest;
  fire("visibilitychange");
  await settle();
  assert.equal(mounted.at(-1), NEWEST, "Changes follows the second push too");
  assert.deepEqual(entry().pullPlace, inC, "a second follow during the read keeps the place");
  release();
  await painted(handle);
  assert.equal(pane.scrollTop, inNewer, "and the newest diff lands in c.py");
  handle.dispose();

  // The same on a page loaded again on its entry, as a followed pin reloads it on a
  // repository URL: a push read while its first diff is read keeps the place it landed on.
  ({ container, handle } = await readingC());
  handle.dispose();
  pane.scrollTop = 0;
  release = slowRead();
  ({ container, handle } = mount(first));
  await settle();
  current = newest;
  fire("visibilitychange");
  await settle();
  assert.equal(mounted.at(-1), NEWEST, "the reloaded page follows the push");
  assert.deepEqual(entry().pullPlace, inC, "a follow during a reload's first read keeps it");
  release();
  await painted(handle);
  assert.equal(pane.scrollTop, inNewer, "and the reloaded page lands in c.py");
  handle.dispose();

  // Show the earlier changes, painted over the emptied body, pressed during the read. The
  // press ends the hold first, as any input in the pane does, so the place kept is the one
  // the entry has.
  ({ container, handle } = await readingC());
  release = await followedSlowly();
  assert.equal(said(container, ".github-pull-followed"), note, "the note is over the read");
  pane.events.get("pointerdown")();
  container.querySelector(".github-pull-earlier").events.get("click")();
  assert.deepEqual(entry().pullPlace, inC, "the way back during the read keeps the place");
  release();
  await painted(handle);
  assert.equal(mounted.at(-1), earlier);
  assert.equal(pane.scrollTop, inEarlier, "and the earlier diff lands in c.py");
  // Changes and Docs draw one comparison: a move to Docs draws the earlier diff the reader
  // chose, not the record's newer one, and the way back to Changes draws it again.
  window.location.pathname = "/pull/7/docs";
  handle.setTab("docs");
  await painted(handle);
  assert.equal(mounted.at(-1), earlier, "Docs draws the earlier diff the reader chose");
  window.location.pathname = "/pull/7/files";
  handle.setTab("files");
  await painted(handle);
  assert.equal(mounted.at(-1), earlier, "and Changes draws it again");
  assert.equal(entry().pullChanges.chosen, true, "the choice stays the reader's");
  handle.dispose();

  // Where nothing was chosen, a move to Docs draws the record's comparison as it is now,
  // not the one Changes mounted (C2 of review C on #745). The record is read again at the
  // same commits after the pull request's head moved on, before its comparison was read:
  // the diff is of a commit that is no longer the branch's tip, so it has no View on branch.
  window.location.pathname = "/pull/7/files";
  window.history.state = null;
  pane.scrollTop = 0;
  current = first;
  ({ container, handle } = mount(first));
  await painted(handle);
  assert.deepEqual(drawn.at(-1).branch, { ref: "refs/pull/7/head" });
  const draws = drawn.length;
  const aheadOfDiff = structuredClone(first);
  aheadOfDiff.record.pull.head.sha = NEWER;
  aheadOfDiff.fetched_at = "2026-09-17T12:00:01Z";
  current = aheadOfDiff;
  fire("visibilitychange");
  await settle();
  await painted(handle);
  assert.equal(drawn.length, draws, "Changes keeps the diff of the same commits");
  window.location.pathname = "/pull/7/docs";
  handle.setTab("docs");
  await painted(handle);
  assert.deepEqual(
    [drawn.at(-1).right, drawn.at(-1).branch],
    [earlier, null],
    "Docs draws the record's comparison as it is now",
  );
  handle.dispose();

  // Docs draws the same comparison and follows a moved head as Changes does, so its entry
  // remembers what it shows as Changes's does (C1 of review C on #745): the reload a
  // followed pin makes says the note and lands in the reader's file, and an earlier diff
  // the reader chose there stays through a reload, with the newer offered.
  window.location.pathname = "/pull/7/docs";
  window.history.state = null;
  pane.scrollTop = 0;
  current = first;
  ({ container, handle } = mount(first, "docs"));
  await painted(handle);
  pane.events.get("wheel")();
  pane.scrollTop = inEarlier;
  scrolledAndStill();
  assert.deepEqual(entry().pullPlace, inC);
  assert.equal(entry().pullChanges?.shown.right, earlier, "Docs's entry remembers what it shows");
  current = moved;
  fire("visibilitychange");
  await settle();
  await painted(handle);
  assert.equal(mounted.at(-1), NEWER, "Docs follows the newer head");
  assert.equal(said(container, ".github-pull-followed"), note);
  assert.equal(pane.scrollTop, inNewer, "in the reader's file");
  handle.dispose();
  pane.scrollTop = 0;
  ({ container, handle } = mount(moved, "docs"));
  await painted(handle);
  assert.equal(said(container, ".github-pull-followed"), note, "a reloaded Docs says it too");
  assert.equal(pane.scrollTop, inNewer, "and lands in the reader's file");
  pane.events.get("wheel")();
  container.querySelector(".github-pull-earlier").events.get("click")();
  await painted(handle);
  assert.equal(mounted.at(-1), earlier);
  assert.deepEqual([entry().pullChanges.shown.right, entry().pullChanges.chosen], [earlier, true]);
  handle.dispose();
  pane.scrollTop = 0;
  ({ container, handle } = mount(moved, "docs"));
  await painted(handle);
  assert.equal(mounted.at(-1), earlier, "a reloaded Docs keeps the diff the reader went back to");
  assert.equal(said(container, ".github-pull-followed"), null);
  assert.equal(
    said(container, ".github-pull-newer-offer"),
    "This pull request has newer commits. Show the newer changes",
  );
  assert.equal(pane.scrollTop, inEarlier);
  handle.dispose();

  // The host moves the address without mounting a diff: a key's walk of the Pulls tab's
  // changed files that stops replaces the entry with the file's address and no state
  // (pull-files-tree.js `settleWalk`, then pull-route.js `open`), and a click on a file
  // pushes an entry with none. The page writes what its diff shows into the entry it lands
  // on, so the reload the next push makes keeps the earlier diff the reader chose there,
  // with the newer offered (mb-eg5f, A1 of review A on #758).
  const offerNewest = "This pull request has newer commits. Show the newer changes";
  for (const [how, route] of [
    ["walk", { number: 7, tab: "files", file: "b.py", replace: true, jumped: true }],
    ["click", { number: 7, tab: "files", file: "b.py" }],
  ]) {
    window.location.pathname = "/pull/7/files";
    window.history.state = null;
    pane.scrollTop = 0;
    current = first;
    const host = hosted();
    await host.show({ number: 7, tab: "files" });
    ({ container, handle } = host.opened());
    await painted(handle);
    current = moved;
    fire("visibilitychange");
    await settle();
    await painted(handle);
    container.querySelector(".github-pull-earlier").events.get("click")();
    await painted(handle);
    assert.equal(entry().pullChanges.chosen, true);
    await host.open(route);
    await settle();
    assert.equal(window.location.pathname, "/pull/7/files/b.py");
    assert.deepEqual(
      [entry().pullChanges?.shown.right, entry().pullChanges?.chosen],
      [earlier, true],
      `the entry the ${how} lands on remembers the reader's choice`,
    );
    current = newest;
    fire("visibilitychange");
    await settle();
    await painted(handle);
    assert.equal(said(container, ".github-pull-newer-offer"), offerNewest);
    host.dispose();
    pane.scrollTop = 0;
    ({ container, handle } = mount(newest));
    await painted(handle);
    assert.equal(mounted.at(-1), earlier, `a reload after the ${how} keeps the earlier diff`);
    assert.equal(said(container, ".github-pull-newer-offer"), offerNewest);
    handle.dispose();
  }

  // Back lands the page on an entry it left, whose state is as the page last wrote it there,
  // so the page writes what its diff shows now (`land`). Entry A follows the first push; a
  // click on a file pushes entry B, where the second push is followed and the reader goes
  // back to the diff entry A shows, now chosen. So A's memory differs from the page's in
  // the diff its note names and in the choice, not in the diff shown (B1 of review B on
  // #758).
  {
    window.location.pathname = "/pull/7/files";
    window.history.state = null;
    pane.scrollTop = 0;
    current = first;
    const host = hosted();
    await host.show({ number: 7, tab: "files" });
    ({ container, handle } = host.opened());
    await painted(handle);
    current = moved;
    fire("visibilitychange");
    await settle();
    await painted(handle);
    const entryA = structuredClone(window.history.state);
    assert.deepEqual(
      [entryA.pullChanges.shown.right, entryA.pullChanges.from?.right, entryA.pullChanges.chosen],
      [NEWER, earlier, false],
    );
    await host.open({ number: 7, tab: "files", file: "b.py" });
    await settle();
    current = newest;
    fire("visibilitychange");
    await settle();
    await painted(handle);
    assert.equal(mounted.at(-1), NEWEST, "entry B follows the second push");
    container.querySelector(".github-pull-earlier").events.get("click")();
    await painted(handle);
    assert.equal(mounted.at(-1), NEWER);
    // Back to A in the same document: the browser restores A's state, and the host lands.
    window.location.pathname = "/pull/7/files";
    window.history.state = entryA;
    host.onHistory(window.location.pathname, false);
    await settle();
    await painted(handle);
    assert.deepEqual(
      [entry().pullChanges.shown.right, entry().pullChanges.from, entry().pullChanges.chosen],
      [NEWER, null, true],
      "the entry Back lands on remembers the reader's choice",
    );
    // The reload a push makes on A, the record at the second push's head.
    host.dispose();
    pane.scrollTop = 0;
    ({ container, handle } = mount(newest));
    await painted(handle);
    assert.equal(mounted.at(-1), NEWER, "a reload after Back keeps the diff the reader chose");
    assert.equal(said(container, ".github-pull-followed"), null);
    assert.equal(said(container, ".github-pull-newer-offer"), offerNewest);
    handle.dispose();
  }

  // While the pull request's head has moved and its record is read again, both diff tabs
  // say so over the diff they have, and Conversation does not (A2 of review A on #758).
  const pushed = structuredClone(first);
  pushed.head_moved = true;
  pushed.state = "stale";
  pushed.refreshing = true;
  for (const [address, tab, line] of [
    ["/pull/7/files", "files", "New commits were pushed; updating."],
    ["/pull/7/docs", "docs", "New commits were pushed; updating."],
    ["/pull/7", "", null],
  ]) {
    window.location.pathname = address;
    window.history.state = null;
    pane.scrollTop = 0;
    current = pushed;
    ({ container, handle } = mount(pushed, tab));
    await painted(handle);
    assert.equal(said(container, ".github-pull-new-commits"), line, `on ${address}`);
    handle.dispose();
  }

  // On a server with no store to compare in, Docs asks for the comparison by itself, as
  // Changes does, while the address is its own (`ownsChanges`), and a Docs page mounted
  // after the address moved away asks nothing (A3 of review A on #758).
  const unstored = structuredClone(first);
  unstored.record.comparison = null;
  unstored.comparison_route = null;
  unstored.record.unavailable = { ...unstored.record.unavailable, comparison: "no_store" };
  for (const [address, asked] of [
    ["/pull/7/docs", [{ number: 7, retry: true, comparison: true }]],
    ["/pull/7", []],
  ]) {
    window.location.pathname = address;
    window.history.state = null;
    current = unstored;
    posts.length = 0;
    ({ container, handle } = mount(unstored, "docs"));
    fire("visibilitychange");
    await settle();
    assert.deepEqual(posts, asked, `Docs on ${address}`);
    handle.dispose();
  }
  assert.equal(resize.size, 0, "a disposed page left an observer");
  return {
    placeNamesItsFile: true,
    clampIsNotWritten: true,
    followKeepsTheFile: true,
    reloadSaysAndLands: true,
    choiceSurvivesReload: true,
    missingFileLandsOnABlockTop: true,
    secondFollowDuringReadKeepsTheFile: true,
    followDuringReloadReadKeepsTheFile: true,
    wayBackDuringReadKeepsTheFile: true,
    docsDrawsTheRecordsComparison: true,
    docsRemembersWhatItShows: true,
    walkAndClickKeepTheChoice: true,
    backKeepsTheChoice: true,
    newCommitsOnBothDiffTabs: true,
    docsAsksForTheComparison: true,
  };
}
run()
  .then((result) => process.stdout.write(`${JSON.stringify(result)}\n`))
  .catch((error) => {
    process.stderr.write(`${error.stack}\n`);
    process.exitCode = 1;
  });

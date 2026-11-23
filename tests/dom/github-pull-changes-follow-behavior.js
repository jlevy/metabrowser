// Production page, mounted in a pane with a history entry: Changes follows a moved head,
// and what joins that to the reader's place and to the entry's memory.
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
const path = require("node:path");
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
  globalThis.fetch = async (route) =>
    String(route).startsWith("/api/plugin/github/pull?")
      ? { status: 200, headers: { get: () => null }, json: async () => structuredClone(current) }
      : { status: 304, headers: { get: () => null } };
  const page = await import(
    pathToFileURL(path.join(root, "src/metabrowser/builtin_plugins/github/pull-page.js")).href
  );
  const mounted = [];
  /** A gate the next render waits at, for a comparison that takes a while to read. */
  let gate = null;
  const mount = (body, files = FILES) => {
    const container = new Element("main");
    const handle = page.mountPullPage(
      container,
      { number: 7, tab: "files", reader: { initial: { etag: null, body }, fetchAfterMs: 60000 } },
      {
        perf,
        ensureAsset: async () => {},
        whenIdle: require("./sdk-idle-fixture.js").whenIdle,
        ensureKindAssets: async () => {},
        getRegisteredView: () => ({
          render: async (host, options) => {
            mounted.push(options.comparison.right);
            if (gate !== null) {
              await gate;
            }
            const sections = new Map();
            let top = HEADER;
            for (const [name, height] of files[
              options.comparison.right === NEWER ? "newer" : "earlier"
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
  const note = "The pull request’s head moved from 85fcb2f to 9999999. Show the earlier changes";
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
    "The pull request now ends at 9999999. Show the newer changes",
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
  assert.equal(resize.size, 0, "a disposed page left an observer");
  return {
    placeNamesItsFile: true,
    clampIsNotWritten: true,
    followKeepsTheFile: true,
    reloadSaysAndLands: true,
    choiceSurvivesReload: true,
    missingFileLandsOnABlockTop: true,
  };
}
run()
  .then((result) => process.stdout.write(`${JSON.stringify(result)}\n`))
  .catch((error) => {
    process.stderr.write(`${error.stack}\n`);
    process.exitCode = 1;
  });

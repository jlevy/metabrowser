// A pending file belongs to its Files visit, and survives replacement within that visit.
const assert = require("node:assert/strict");
const path = require("node:path");
const { pathToFileURL } = require("node:url");
const { Element, recorded, root, settle } = require("./github-pull-page-mount-behavior.js");
function deferred() {
  let resolve;
  const promise = new Promise((done) => {
    resolve = done;
  });
  return { promise, resolve };
}
function setup() {
  const timers = new Map();
  globalThis.document = {
    visibilityState: "visible",
    addEventListener() {},
    createElement: (tag) => new Element(tag),
    importNode: () => new Element("svg"),
  };
  globalThis.window = {
    location: { pathname: "/pull/7/files" },
    setTimeout(callback) {
      const id = Symbol();
      timers.set(id, callback);
      return id;
    },
    clearTimeout: (id) => timers.delete(id),
  };
  globalThis.DOMParser = class {
    parseFromString() {
      return { body: { firstElementChild: null } };
    }
  };
}
const response = (body) => ({ status: 200, headers: { get: () => null }, json: async () => body });
async function run() {
  const { mountPullPage } = await import(
    pathToFileURL(path.join(root, "src/metabrowser/builtin_plugins/github/pull-page.js")).href
  );
  const mount = (initial, assets, jumps) =>
    mountPullPage(
      new Element("main"),
      { number: 7, tab: "files", reader: { initial, fetchAfterMs: 0 } },
      {
        ensureAsset: async () => {},
        ensureKindAssets: () => assets,
        getRegisteredView: () => ({
          render: async () => ({
            scrollToFile(file) {
              jumps.push(file);
              return { kind: "jumped", path: file };
            },
            dispose() {},
          }),
        }),
        formatAge: () => ({ label: "now", className: "age" }),
        formatTimestamp: () => "now",
        navigation: { href: () => "/view/" },
        sourceKind: () => "git_revision",
        icons: { toggle: "" },
      },
    );
  setup();
  globalThis.fetch = async () => ({ status: 304, headers: { get: () => null } });
  const assets = deferred();
  const abandoned = [];
  const page = mount(recorded.current, assets.promise, abandoned);
  await settle();
  assert.equal(page.showFile("src/app.txt").kind, "no_diff");
  window.location.pathname = "/pull/7";
  page.setTab("");
  assets.resolve();
  await settle();
  window.location.pathname = "/pull/7/files";
  page.setTab("files");
  await settle();
  await page.whenFilesReady();
  assert.deepEqual(abandoned, [], "a fileless visit must not consume the abandoned file");
  page.dispose();

  setup();
  const metadata = deferred();
  globalThis.fetch = () => metadata.promise;
  const unavailable = structuredClone(recorded.current);
  unavailable.body.record.comparison = null;
  unavailable.body.comparison_route = null;
  unavailable.body.record.unavailable.comparison = "base_uncertain";
  const retained = [];
  const waiting = mount(unavailable, Promise.resolve(), retained);
  await settle();
  assert.equal(waiting.showFile("docs/new.md").kind, "no_diff");
  metadata.resolve(response(recorded.current.body));
  await settle();
  await waiting.whenFilesReady();
  assert.deepEqual(
    retained,
    ["docs/new.md"],
    "temporary unavailability in Files retains the current selection",
  );
  waiting.dispose();

  setup();
  const newer = deferred();
  globalThis.fetch = () => newer.promise;
  const oldAssets = deferred();
  const replacements = [];
  const container = new Element("main");
  const sameVisit = mountPullPage(
    container,
    { number: 7, tab: "files", reader: { initial: recorded.current, fetchAfterMs: 0 } },
    {
      ensureAsset: async () => {},
      ensureKindAssets: () => oldAssets.promise,
      getRegisteredView: () => ({
        render: async () => ({
          scrollToFile(file) {
            replacements.push(file);
            return { kind: "jumped", path: file };
          },
          dispose() {},
        }),
      }),
      formatAge: () => ({ label: "now", className: "age" }),
      formatTimestamp: () => "now",
      navigation: { href: () => "/view/" },
      sourceKind: () => "git_revision",
      icons: { toggle: "" },
    },
  );
  await settle();
  sameVisit.showFile("docs/new.md");
  const updated = structuredClone(recorded.current.body);
  updated.record.comparison.head = "c".repeat(40);
  updated.record.pull.head.sha = "c".repeat(40);
  updated.fetched_at = "2026-09-17T12:00:01Z";
  newer.resolve(response(updated));
  await settle();
  const offer = [...container.descendants()].find(
    (element) => element.textContent === "Show the newer changes",
  );
  assert.ok(offer);
  offer.events.get("click")();
  oldAssets.resolve();
  await settle();
  await sameVisit.whenFilesReady();
  assert.deepEqual(
    replacements,
    ["docs/new.md"],
    "same-Files replacement retains the newest pending selection",
  );
  sameVisit.dispose();
  return {
    abandonedJump: false,
    unavailableRetainsSelection: true,
    replacementRetainsSelection: true,
  };
}
run()
  .then((result) => process.stdout.write(`${JSON.stringify(result)}\n`))
  .catch((error) => {
    process.stderr.write(`${error.stack}\n`);
    process.exitCode = 1;
  });

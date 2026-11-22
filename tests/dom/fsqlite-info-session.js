// Browserless session: the fsqlite store's Info view, for every state its route answers.
//
// The fsqlite plugin (src/metabrowser/builtin_plugins/fsqlite/) shows a store as a reader
// sees it: the store's own section (store-model.js), then the snapshot `current` names as
// the SQLite plugin's Info view shows a database (sqlite/info-model.js), drawn by that
// plugin's drawInfo (sqlite/info-view.js), which store-view.js reaches through the SQLite
// plugin's exports.
//
// This loads all four production modules whole and mounts the view through stand-ins for
// the SDK's `fetchPluginData`, `formatInteger`, and `plugins.load`, over a DOM of just
// enough nodes to read the drawing back (pulls-test-dom.js). The answers are the server's,
// recorded in tests/fixtures/fsqlite-info-responses.json by
// tests/test_fsqlite_info_session.py, which fails when they drift. A generation is
// recorded as `G` and the SQLite library's version as `L`.
//
// It prints, for each store, what the page shows: each notice, then each section's rows.
// Then it checks the view's lifecycle: a view disposed before its answer draws nothing
// and aborts its request, a refused request is said as an unreadable store, and a SQLite
// plugin that failed to load is said instead of a blank page. Exits 1 on a failed
// invariant.

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { pathToFileURL } = require("node:url");
const { FakeElement } = require("./pulls-test-dom.js");

const repoRoot = path.resolve(__dirname, "../..");
const plugins = path.join(repoRoot, "src/metabrowser/builtin_plugins");
const recording = JSON.parse(
  fs.readFileSync(path.join(repoRoot, "tests/fixtures/fsqlite-info-responses.json"), "utf8"),
).answers;

globalThis.document = { createElement: (tag) => new FakeElement(tag) };

/** Every element under *node*, in document order. */
function* walk(node) {
  for (const child of node.childNodes ?? []) {
    if (child instanceof FakeElement) {
      yield child;
      yield* walk(child);
    }
  }
}

const has = (element, name) => element.className.split(" ").includes(name);

/** What the drawn page says: notices, then sections of `label: value` lines. */
function readPage(root) {
  const lines = [];
  for (const element of walk(root)) {
    if (has(element, "sqlite-info-notice")) {
      const [title, text] = element.childNodes.map((node) => node.textContent);
      lines.push(`[${element.dataset.severity} ${element.getAttribute("role")}] ${title}: ${text}`);
    } else if (has(element, "sqlite-info-heading")) {
      lines.push(`## ${element.textContent}`);
    } else if (element.localName === "tr" || element.tagName === "TR") {
      const [label, value] = element.childNodes;
      const marks = ["data-literal", "sqlite-info-number", "sqlite-info-muted"]
        .filter((name) => has(value, name))
        .map((name) => name.replace(/^(data|sqlite-info)-/, ""));
      lines.push(
        `${label.textContent}: ${value.textContent}${marks.length ? `  (${marks.join(", ")})` : ""}`,
      );
    } else if (has(element, "sqlite-info-loading")) {
      lines.push(`(${element.textContent})`);
    }
  }
  return lines;
}

const formatInteger = (value) => value.toLocaleString("en-US");

async function main() {
  const { storeModel, pendingText } = await import(
    pathToFileURL(path.join(plugins, "fsqlite/store-model.js")).href
  );
  const { mountStoreInfo } = await import(
    pathToFileURL(path.join(plugins, "fsqlite/store-view.js")).href
  );
  const { infoModel } = await import(
    pathToFileURL(path.join(plugins, "sqlite/info-model.js")).href
  );
  const { drawInfo } = await import(pathToFileURL(path.join(plugins, "sqlite/info-view.js")).href);
  const sqliteExports = { infoModel, drawInfo };

  /** An SDK whose fetch answers from the recording, or as *fetch* says. */
  function sdk({ fetch, load } = {}) {
    const asked = [];
    return {
      asked,
      formatInteger,
      plugins: {
        load: (name) => {
          asked.push(`load ${name}`);
          return load ? load(name) : Promise.resolve(sqliteExports);
        },
      },
      fetchPluginData(plugin, route, params, options) {
        asked.push(`${plugin}/${route}?path=${params.path}`);
        if (fetch) {
          return fetch(params, options);
        }
        const answer = recording[params.path];
        if (!answer) {
          return Promise.reject(new Error(`unrecorded request for ${params.path}`));
        }
        return answer.status === 200
          ? Promise.resolve(answer.body)
          : Promise.reject(Object.assign(new Error("refused"), { payload: answer.body }));
      },
    };
  }

  const transcript = { stores: {}, lifecycle: {} };

  for (const store of Object.keys(recording)) {
    const container = new FakeElement("div");
    const fake = sdk();
    const view = mountStoreInfo(container, { path: store }, fake);
    assert.deepEqual(readPage(container), ["(Reading this store…)"], "it says it is reading");
    await view.ready;
    const shown = readPage(container);
    // The page draws exactly the model, which puts the store's section first.
    const model = storeModel(recording[store].body, { formatInteger }, infoModel);
    assert.equal(
      shown.filter((line) => line.startsWith("## ")).join("|"),
      model.sections.map((section) => `## ${section.title}`).join("|"),
    );
    if (recording[store].body.store?.version !== undefined) {
      assert.equal(model.sections[0].title, "Store", `${store}: the store's section is first`);
    }
    assert.deepEqual(fake.asked, ["load sqlite", `fsqlite/info?path=${store}`]);
    transcript.stores[store] = shown;
    view.dispose();
  }

  // A pointer read again after garbage collection says so; the recording cannot hold
  // that race, so it is the notes store's answer with its second attempt.
  const notes = recording["notes/fsqlite.json"].body;
  const retried = storeModel(
    { ...notes, store: { ...notes.store, attempts: 2 } },
    { formatInteger },
    infoModel,
  );
  const pointer = retried.sections[0].rows.find((row) => row.label === "Pointer");
  assert.ok(pointer, "a second attempt is shown");
  transcript.lifecycle["a pointer read again"] = `${pointer.label}: ${pointer.value}`;

  // Pending envelopes: none, committed, uncommitted, and a scan that stopped.
  transcript.lifecycle.pending = [
    { committed: 0, uncommitted: 0, complete: true },
    { committed: 1, uncommitted: 0, complete: true },
    { committed: 0, uncommitted: 2, complete: true },
    { committed: 1200, uncommitted: 3, complete: false },
    { committed: 0, uncommitted: 0, complete: false },
  ].map((pending) => pendingText(pending, formatInteger));

  // Disposed before its answer: nothing is drawn, and the request is aborted.
  {
    let release;
    let signal;
    const container = new FakeElement("div");
    const view = mountStoreInfo(
      container,
      { path: "notes/fsqlite.json" },
      sdk({
        fetch: (_params, options) => {
          signal = options.signal;
          return new Promise((resolve) => {
            release = () => resolve(recording["notes/fsqlite.json"].body);
          });
        },
      }),
    );
    view.dispose();
    release();
    await view.ready;
    assert.equal(signal.aborted, true, "disposal aborts the request");
    transcript.lifecycle["disposed before its answer"] = readPage(container);
  }

  // A refused request is an unreadable store, in the route's words.
  {
    const container = new FakeElement("div");
    const view = mountStoreInfo(
      container,
      { path: "notes/current" },
      sdk({
        fetch: () =>
          Promise.reject(
            Object.assign(new Error("404"), {
              payload: { error: "This is not an fsqlite store's marker." },
            }),
          ),
      }),
    );
    await view.ready;
    transcript.lifecycle["a refused request"] = readPage(container);
  }

  // The SQLite plugin it draws with failed to load: said, never a blank page.
  {
    const container = new FakeElement("div");
    const view = mountStoreInfo(
      container,
      { path: "notes/fsqlite.json" },
      sdk({ load: () => Promise.reject(new Error("no sqlite")) }),
    );
    await view.ready;
    const shown = readPage(container);
    assert.equal(shown.length, 1);
    transcript.lifecycle["the SQLite plugin failed to load"] = shown;
  }

  console.log(JSON.stringify(transcript, null, 2));
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});

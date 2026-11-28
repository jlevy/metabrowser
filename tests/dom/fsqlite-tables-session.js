// Browserless session: the fsqlite store's Table and Schema views, drawn from what the
// routes answered.
//
// A store's tables are its snapshot's, each at `<marker>/<segment>`. The store's Table
// and Schema views (src/metabrowser/builtin_plugins/fsqlite/store-tables.js) are the
// SQLite plugin's, which they reach through that plugin's exports: the Table view is the
// store's overview at the marker's address, from /api/plugin/table/tables, and the table
// plugin's view at a table's; the Schema view reads /api/plugin/fsqlite/schema.
//
// This loads the production modules whole, the store's and the SQLite plugin's
// tables-view.js and tables-model.js, and mounts each view on the answers in
// tests/fixtures/fsqlite-tables-responses.json, which tests/test_fsqlite_tables_session.py
// records from the routes over stores it builds. The table plugin is a stand-in. It
// prints what each view shows and what it asked for, a store the routes refuse, and the
// views' lifecycle: disposed before the SQLite plugin loads, disposed once drawn, and a
// SQLite plugin that failed to load. Exits 1 on a failed invariant.

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { pathToFileURL } = require("node:url");
const { FakeElement } = require("./pulls-test-dom.js");

const repoRoot = path.resolve(__dirname, "../..");
const plugins = path.join(repoRoot, "src/metabrowser/builtin_plugins");
const { answers } = JSON.parse(
  fs.readFileSync(path.join(repoRoot, "tests/fixtures/fsqlite-tables-responses.json"), "utf8"),
);

globalThis.document = { createElement: (tag) => new FakeElement(tag) };

const formatInteger = (value) => value.toLocaleString("en-US");

/** Every element under *node*, in document order. */
function* walk(node) {
  for (const child of node.childNodes ?? []) {
    if (child instanceof FakeElement) {
      yield child;
      yield* walk(child);
    }
  }
}

/** The recorded answer for *plugin*'s *route* at *address*. */
function answerFor(pluginName, route, address) {
  return (
    answers[`${pluginName}/${route} ${address}`] ?? {
      status: 404,
      body: { error: `Nothing recorded for ${pluginName}/${route} ${address}` },
    }
  );
}

/**
 * A page whose SDK answers from the recording. *load* stands in for
 * `plugins.load("sqlite")`; the table plugin is a stand-in that draws one node.
 */
function page(sqlite, renderTableCatalog, { load } = {}) {
  const asked = [];
  const loaded = [];
  const aborted = [];
  return {
    asked,
    loaded,
    aborted,
    sdk: {
      formatInteger,
      navigation: {
        href: (target) => `/view/${target.path}`,
        open: () => Promise.resolve(),
      },
      plugins: {
        load: (name) => {
          loaded.push(name);
          if (name === "sqlite") {
            return load ? load() : Promise.resolve(sqlite);
          }
          return Promise.resolve({
            renderTableCatalog,
            mountTable: (container, ctx) => {
              container.replaceChildren(new FakeElement("table-view"));
              return { ready: Promise.resolve(), dispose() {}, path: ctx.path };
            },
          });
        },
      },
      fetchPluginData(pluginName, route, params, options) {
        asked.push(`${pluginName}/${route}?path=${params.path}`);
        options?.signal?.addEventListener?.("abort", () => aborted.push(route));
        const answer = answerFor(pluginName, route, params.path);
        if (answer.status !== 200) {
          return Promise.reject(
            Object.assign(new Error(`HTTP ${answer.status}`), {
              status: answer.status,
              payload: answer.body,
            }),
          );
        }
        return Promise.resolve(answer.body);
      },
    },
  };
}

/** What a mounted overview shows: each group's rows, or what it said instead. */
function shownOverview(container) {
  const out = {};
  for (const element of walk(container)) {
    if (element.localName === "section") {
      const heading = [...walk(element)].find((node) => node.localName === "h2");
      out[heading.textContent] = [...walk(element)]
        .filter((node) => node.localName === "tr")
        .map((row) => {
          const link = [...walk(row)].find((node) => node.localName === "a");
          const estimate = [...walk(row)].find((node) => node.localName === "td");
          return `${link.textContent} → ${link.getAttribute("href")}  ${estimate.textContent}`;
        });
    }
    if (element.classes.has("sqlite-error") || element.classes.has("sqlite-empty")) {
      out.said = element.textContent;
    }
  }
  return out;
}

/** What a mounted Schema view shows: each section's DDL, or its alert. */
function shownSchema(container) {
  const out = {};
  for (const element of walk(container)) {
    if (element.localName === "section") {
      const heading = [...walk(element)].find((node) => node.localName === "h2");
      out[heading.textContent] = [...walk(element)]
        .filter((node) => node.localName === "pre")
        .map((node) => node.textContent);
    }
    if (element.classes.has("sqlite-error")) {
      const role = element.getAttribute("role");
      out.said = role ? `[${role}] ${element.textContent}` : element.textContent;
    }
  }
  return out;
}

async function main() {
  // What the SQLite plugin's index.js exports to a plugin that requires it.
  const index = fs.readFileSync(path.join(plugins, "sqlite/index.js"), "utf8");
  assert.match(index, /export \{ mountSchema, mountTableView \} from "\.\/tables-view\.js";/);
  const { mountSchema, mountTableView } = await import(
    pathToFileURL(path.join(plugins, "sqlite/tables-view.js")).href
  );
  const sqlite = { mountSchema, mountTableView };
  const { renderTableCatalog } = await import(
    pathToFileURL(path.join(plugins, "table/table-catalog.js")).href
  );
  const { mountStoreSchema, mountStoreTable } = await import(
    pathToFileURL(path.join(plugins, "fsqlite/store-tables.js")).href
  );
  const transcript = {};

  // The Table view at the marker's address: the store's overview.
  for (const store of ["notes/fsqlite.json", "torn/fsqlite.json"]) {
    const host = page(sqlite, renderTableCatalog);
    const container = new FakeElement("div");
    const view = mountStoreTable(container, { path: store, raw: {} }, host.sdk);
    await view.ready;
    assert.deepEqual(host.loaded, ["sqlite", "table"]);
    assert.deepEqual(host.asked, [`table/tables?path=${store}`]);
    transcript[`Table view of ${store}`] = shownOverview(container);
    view.dispose();
  }

  // At a table's address it is the table plugin's view of that table.
  {
    const host = page(sqlite, renderTableCatalog);
    const container = new FakeElement("div");
    const view = mountStoreTable(
      container,
      { path: "notes/fsqlite.json/notes", raw: { container_inner: "notes" } },
      host.sdk,
    );
    await view.ready;
    assert.deepEqual(host.asked, [], "the table plugin asks for its own answers");
    transcript["Table view of notes/fsqlite.json/notes"] = {
      loaded: host.loaded,
      drawn: container.childNodes.map((node) => node.localName),
    };
    view.dispose();
  }

  // The Schema view reads the store's own route, which answers as the SQLite one does.
  for (const address of ["notes/fsqlite.json", "notes/fsqlite.json/notes", "torn/fsqlite.json"]) {
    const host = page(sqlite, renderTableCatalog);
    const container = new FakeElement("div");
    const view = mountStoreSchema(container, { path: address }, host.sdk);
    await view.ready;
    assert.deepEqual(host.asked, [`fsqlite/schema?path=${address}`]);
    transcript[`Schema view of ${address}`] = shownSchema(container);
    view.dispose();
  }

  // Disposed before the SQLite plugin loads: nothing is mounted and nothing is asked.
  {
    let release;
    const host = page(sqlite, renderTableCatalog, {
      load: () =>
        new Promise((resolve) => {
          release = () => resolve(sqlite);
        }),
    });
    const container = new FakeElement("div");
    const view = mountStoreSchema(container, { path: "notes/fsqlite.json" }, host.sdk);
    view.dispose();
    release();
    await view.ready;
    assert.deepEqual(host.asked, []);
    assert.equal(container.childNodes.length, 0);
    transcript["disposed before the SQLite plugin loads"] = {
      asked: host.asked,
      drawn: container.childNodes.length,
    };
  }

  // Disposed once drawn: the SQLite view's own disposal runs.
  {
    const host = page(sqlite, renderTableCatalog);
    const container = new FakeElement("div");
    const view = mountStoreSchema(container, { path: "notes/fsqlite.json" }, host.sdk);
    await view.ready;
    view.dispose();
    assert.deepEqual(host.aborted, ["schema"], "disposal reaches the drawn view");
    transcript["disposed once drawn"] = { aborted: host.aborted };
  }

  // The SQLite plugin failed to load: said, never a blank page.
  {
    const host = page(sqlite, renderTableCatalog, {
      load: () => Promise.reject(new Error("no sqlite")),
    });
    const container = new FakeElement("div");
    const view = mountStoreTable(container, { path: "notes/fsqlite.json" }, host.sdk);
    await view.ready;
    const shown = shownOverview(container);
    assert.ok(shown.said);
    transcript["the SQLite plugin failed to load"] = shown;
  }

  process.stdout.write(`${JSON.stringify(transcript, null, 2)}\n`);
}

main().catch((error) => {
  process.stderr.write(`${error.stack ?? error}\n`);
  process.exit(1);
});

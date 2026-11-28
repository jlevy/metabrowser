// Browserless session: the SQLite overview, Schema view, and table cells, drawn from what
// the routes answered.
//
// A database's Table view at its own address is its overview: its tables by group, each
// a link to its address with its estimate. At a table's address it is the table plugin's
// view of that table. The Schema view lists each object's DDL and every table's foreign
// keys. What each says is tables-model.js's; tables-view.js fetches, draws, and disposes.
// The table plugin's `presentCell` decides how each SQLite cell is drawn.
//
// This loads the production modules whole and mounts each view on the answers in
// tests/fixtures/sqlite-tables-responses.json, which tests/test_sqlite_tables_session.py
// records from the routes over databases built from tests/fixtures/sqlite-tables/. It
// prints what each view shows, follows an overview link, mounts a table's address through
// a stand-in table plugin, presents every cell of the recorded pages, and draws a request
// that fails and a view disposed before its answer arrives. Exits 1 on a failed
// invariant.

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { pathToFileURL } = require("node:url");
const { FakeElement } = require("./pulls-test-dom.js");

const repoRoot = path.resolve(__dirname, "../..");
const plugins = path.join(repoRoot, "src/metabrowser/builtin_plugins");
const { answers } = JSON.parse(
  fs.readFileSync(path.join(repoRoot, "tests/fixtures/sqlite-tables-responses.json"), "utf8"),
);

globalThis.document = { createElement: (tag) => new FakeElement(tag) };

const formatInteger = (value) => value.toLocaleString("en-US");
let renderTableCatalog;

/** Every element under *node*, in document order. */
function* walk(node) {
  for (const child of node.childNodes ?? []) {
    if (child instanceof FakeElement) {
      yield child;
      yield* walk(child);
    }
  }
}

/** The recorded answer for *plugin*'s *route* with *params*. */
function answerFor(pluginName, route, params) {
  for (const [name, answer] of Object.entries(answers)) {
    const [kind, address] = name.split(" ");
    const wanted = {
      tables: "overview",
      schema: pluginName === "sqlite" ? "schema" : "schema-of",
      rows: "rows",
    }[route];
    if (kind === wanted && address === params.path) {
      return answer;
    }
  }
  return { status: 404, body: { type: "sqlite_error", error: `Nothing recorded for ${route}` } };
}

/** A page whose SDK answers from the recording when released. */
function page() {
  const asked = [];
  const opened = [];
  const loaded = [];
  let release;
  const gate = new Promise((resolve) => {
    release = resolve;
  });
  return {
    asked,
    opened,
    loaded,
    release: () => release(),
    sdk: {
      formatInteger,
      navigation: {
        href: (target) => `/view/${target.path}`,
        open: (target) => {
          opened.push(target.path);
          return Promise.resolve();
        },
      },
      plugins: {
        load: (name) => {
          loaded.push(name);
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
        asked.push({ pluginName, route, params, signal: Boolean(options?.signal) });
        const answer = answerFor(pluginName, route, params);
        return gate.then(() => {
          if (answer.status !== 200) {
            const error = new Error(`HTTP ${answer.status}`);
            Object.assign(error, { status: answer.status, payload: answer.body });
            throw error;
          }
          return answer.body;
        });
      },
    },
  };
}

/** What a mounted overview shows: each group's rows as a reader reads them. */
function shownOverview(container) {
  const out = {};
  for (const element of walk(container)) {
    if (element.localName === "section") {
      const heading = [...walk(element)].find((node) => node.localName === "h2");
      out[heading.textContent] = [...walk(element)]
        .filter((node) => node.localName === "tr")
        .map((row) => {
          const link = [...walk(row)].find((node) => node.localName === "a");
          const note = [...walk(row)].find((node) => node.classes.has("table-catalog-note"));
          const estimate = [...walk(row)].find((node) => node.localName === "td");
          return [
            `${link.textContent} → ${link.getAttribute("href")}`,
            note ? `(${note.textContent})` : "",
            estimate.textContent,
          ]
            .filter(Boolean)
            .join("  ");
        });
    }
    if (element.classes.has("sqlite-empty") || element.classes.has("sqlite-error")) {
      out.said = element.textContent;
    }
    if (element.classes.has("sqlite-loading")) {
      out.loading = element.textContent;
    }
  }
  return out;
}

/** What a mounted Schema view shows: each section's DDL and foreign keys. */
function shownSchema(container) {
  const out = {};
  for (const element of walk(container)) {
    if (element.localName === "section") {
      const heading = [...walk(element)].find((node) => node.localName === "h2");
      out[heading.textContent] = [...walk(element)]
        .filter((node) => node.localName === "pre" || node.localName === "li")
        .map((node) => (node.localName === "li" ? `FK ${node.textContent}` : node.textContent));
    }
    if (element.classes.has("sqlite-error")) {
      out.alert = `[${element.getAttribute("role")}] ${element.textContent}`;
    }
  }
  return out;
}

/** How the table view presents each cell of a recorded page. */
function presented(presentCell, rows, schema) {
  const fields = new Map(schema.fields.map((field) => [field.name, field]));
  return rows.map((row) =>
    Object.entries(row.cells).map(([name, cell]) => {
      const view = presentCell(cell, fields.get(name));
      const marks = [
        view.cut !== null ? `cut ${view.cut}` : "",
        view.size !== null ? `size ${view.size}` : "",
        view.missing ? "missing" : "",
        view.stored ? `stored ${view.stored}` : "",
        view.invalid ? "invalid" : "",
        view.ref ? `ref ${view.ref.table}` : "",
        view.literal ? "literal" : "",
      ].filter(Boolean);
      const text = view.text.length > 24 ? `${view.text.slice(0, 24)}…` : view.text;
      return `${name}: ${view.kind} ${JSON.stringify(text)}${marks.length ? `  {${marks.join(", ")}}` : ""}`;
    }),
  );
}

async function main() {
  const sqlite = path.join(plugins, "sqlite");
  ({ renderTableCatalog } = await import(
    pathToFileURL(path.join(plugins, "table/table-catalog.js")).href
  ));
  const { mountOverview, mountSchema, mountTableView } = await import(
    pathToFileURL(path.join(sqlite, "tables-view.js")).href
  );
  const { overviewModel } = await import(pathToFileURL(path.join(sqlite, "tables-model.js")).href);
  const { presentCell } = await import(
    pathToFileURL(path.join(plugins, "table/table-model.js")).href
  );
  const transcript = {};

  for (const database of ["app.db", "snapshot.db"]) {
    const host = page();
    const container = new FakeElement("div");
    const view = mountOverview(container, { path: database }, host.sdk);
    assert.equal(shownOverview(container).loading, "Reading this database…");
    host.release();
    await view.ready;
    assert.deepEqual(host.asked, [
      { pluginName: "table", route: "tables", params: { path: database }, signal: true },
    ]);
    const drawn = shownOverview(container);
    const model = overviewModel(answerFor("table", "tables", { path: database }).body, {
      formatInteger,
    });
    assert.deepEqual(
      Object.keys(drawn),
      model.groups.map((group) => group.title),
    );
    transcript[`overview of ${database}`] = drawn;
    if (database === "app.db") {
      // A plain click opens the table's address in place; a modified one is the browser's.
      const link = [...walk(container)].find((node) => node.localName === "a");
      let prevented = 0;
      link.listeners.get("click")({
        button: 0,
        preventDefault: () => {
          prevented += 1;
        },
      });
      link.listeners.get("click")({ button: 0, metaKey: true, preventDefault: () => {} });
      transcript["an overview link, clicked and Command-clicked"] = {
        opened: host.opened,
        prevented,
      };
    }
    view.dispose();
  }

  for (const address of ["app.db", "app.db/grants", "fake.db"]) {
    const host = page();
    const container = new FakeElement("div");
    const view = mountSchema(container, { path: address }, host.sdk);
    host.release();
    await view.ready;
    assert.deepEqual(host.asked, [
      { pluginName: "sqlite", route: "schema", params: { path: address }, signal: true },
    ]);
    transcript[`schema of ${address}`] = shownSchema(container);
    view.dispose();
  }

  // The Table view at a table's address is the table plugin's, loaded on demand.
  const tableHost = page();
  const tableContainer = new FakeElement("div");
  const mounted = await mountTableView(
    tableContainer,
    { path: "app.db/users", raw: { container_inner: "users" } },
    tableHost.sdk,
  );
  assert.deepEqual(tableHost.loaded, ["table"]);
  assert.deepEqual(tableHost.asked, [], "the table plugin asks for its own answers");
  transcript["the Table view at a table's address"] = {
    loaded: tableHost.loaded,
    mounted: mounted.path,
    drawn: tableContainer.childNodes.map((node) => node.localName),
  };

  for (const table of ["users", "orders", "grants", "huge"]) {
    const rows = answerFor("table", "rows", { path: `app.db/${table}` }).body.rows;
    const schema = answerFor("table", "schema", { path: `app.db/${table}` }).body;
    transcript[`cells of app.db/${table}`] = presented(presentCell, rows, schema);
  }

  const failing = page();
  const failed = new FakeElement("div");
  const failedView = mountOverview(failed, { path: "gone.db" }, failing.sdk);
  failing.release();
  await failedView.ready;
  transcript["a request that fails"] = shownOverview(failed);
  assert.ok(transcript["a request that fails"].said);

  const late = page();
  const lateHost = new FakeElement("div");
  const lateView = mountSchema(lateHost, { path: "app.db" }, late.sdk);
  lateView.dispose();
  late.release();
  await lateView.ready;
  const lateShown = shownSchema(lateHost);
  assert.deepEqual(lateShown, {}, "a disposed view draws nothing from its answer");
  transcript["a view disposed before its answer"] = lateShown;

  process.stdout.write(`${JSON.stringify(transcript, null, 2)}\n`);
}

main().catch((error) => {
  process.stderr.write(`${error.stack ?? error}\n`);
  process.exit(1);
});

// Browserless session: the SQLite Info view, drawn from what the route answered.
//
// The sqlite plugin's Info view (src/metabrowser/builtin_plugins/sqlite/) says what a
// reader process saw of a database: how it opened it and why, the database as its
// connection reads it, the files beside it, and the SQLite library against the reader's
// minimum. What it says is info-model.js's `infoModel`; info-view.js's `mountInfo`
// fetches the answer, draws the model, and disposes.
//
// This loads both production modules whole and mounts the view once per recorded answer,
// in tests/fixtures/sqlite-info-responses.json, which tests/test_sqlite_info_session.py
// records from the route over databases staged in each state with real owners. It prints
// what the view shows for each: its notices with their severity and role, and each
// section's rows. It then draws an older library from the first answer, a request that
// fails, and a view disposed before its answer arrives, which draws nothing.
// Exits 1 on a failed invariant.

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { pathToFileURL } = require("node:url");
const { FakeElement } = require("./pulls-test-dom.js");

const repoRoot = path.resolve(__dirname, "../..");
const plugin = path.join(repoRoot, "src/metabrowser/builtin_plugins/sqlite");
const { answers } = JSON.parse(
  fs.readFileSync(path.join(repoRoot, "tests/fixtures/sqlite-info-responses.json"), "utf8"),
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

/** What the mounted view shows, as a reader reads it. */
function shown(container) {
  const out = { notices: [], sections: {} };
  for (const element of walk(container)) {
    if (element.classes.has("notice")) {
      out.notices.push(
        `[${element.dataset.severity}, ${element.getAttribute("role")}] ${element.textContent}`,
      );
    }
    if (element.localName === "section") {
      const heading = [...walk(element)].find((node) => node.localName === "h2");
      const rows = [...walk(element)].filter((node) => node.localName === "tr");
      out.sections[heading.textContent] = rows.map((row) => {
        const [label, value] = [...walk(row)];
        const marks = [...value.classes].filter((name) => name !== "sqlite-info-value");
        return `${label.textContent}: ${value.textContent}${marks.length ? `  {${marks.join(" ")}}` : ""}`;
      });
    }
    if (element.classes.has("sqlite-info-loading")) {
      out.loading = element.textContent;
    }
  }
  return out;
}

/** A page whose `fetchPluginData` answers *answer* (or fails with it) when released. */
function page(answer) {
  const asked = [];
  let release;
  const gate = new Promise((resolve) => {
    release = resolve;
  });
  return {
    asked,
    release: () => release(),
    sdk: {
      formatInteger,
      fetchPluginData(pluginName, route, params, options) {
        asked.push({ pluginName, route, params, signal: Boolean(options?.signal) });
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

/** Whether a release is at or before 3.40.1, the older library the session draws. */
function older340(version) {
  const [major, minor, patch] = version.split(".").map(Number);
  return major * 1e6 + minor * 1e3 + patch <= 3 * 1e6 + 40 * 1e3 + 1;
}

async function main() {
  const { mountInfo } = await import(pathToFileURL(path.join(plugin, "info-view.js")).href);
  const { infoModel } = await import(pathToFileURL(path.join(plugin, "info-model.js")).href);
  const transcript = { answers: {} };

  for (const [name, answer] of Object.entries(answers)) {
    const host = page(answer);
    const container = new FakeElement("div");
    const view = mountInfo(container, { path: name }, host.sdk);
    assert.equal(shown(container).loading, "Reading this database…");
    host.release();
    await view.ready;
    assert.deepEqual(host.asked, [
      { pluginName: "sqlite", route: "info", params: { path: name }, signal: true },
    ]);
    const drawn = shown(container);
    assert.equal(drawn.loading, undefined, "the answer replaces the loading line");
    // What is drawn is the model, notice for notice and row for row.
    const model = infoModel(answer.body, { formatInteger });
    assert.equal(drawn.notices.length, model.notices.length);
    assert.deepEqual(
      Object.keys(drawn.sections),
      model.sections.map((section) => section.title),
    );
    transcript.answers[name] = drawn;
    view.dispose();
  }

  const first = Object.values(answers)[0].body;
  const older = {
    ...first,
    library: {
      ...first.library,
      version: "3.40.1",
      meets_minimum: false,
      versions: first.library.versions.map((entry) => ({
        ...entry,
        available: older340(entry.version),
      })),
    },
  };
  transcript["an older library"] = infoModel(older, { formatInteger }).sections.find(
    (section) => section.title === "Library",
  ).rows;

  const failing = page({ status: 404, body: { type: "sqlite_error", error: "Not found" } });
  const failed = new FakeElement("div");
  const failedView = mountInfo(failed, { path: "gone.db" }, failing.sdk);
  failing.release();
  await failedView.ready;
  transcript["a request that fails"] = shown(failed);
  assert.equal(transcript["a request that fails"].notices.length, 1);

  const late = page(Object.values(answers)[0]);
  const lateHost = new FakeElement("div");
  const lateView = mountInfo(lateHost, { path: "app.db" }, late.sdk);
  lateView.dispose();
  late.release();
  await lateView.ready;
  const lateShown = shown(lateHost);
  assert.deepEqual(lateShown.sections, {}, "a disposed view draws nothing from its answer");
  transcript["a view disposed before its answer"] = lateShown;

  process.stdout.write(`${JSON.stringify(transcript, null, 2)}\n`);
}

main().catch((error) => {
  process.stderr.write(`${error.stack ?? error}\n`);
  process.exit(1);
});

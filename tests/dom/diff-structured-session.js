// The rows a changed YAML or JSON file's Rendered view draws, through the production
// diff-structured.js and the structured plugin's own preview.js and tree.js: which rows a
// merged tree has, which open first, what a click opens, and how a row is marked.
//
// The trees drawn into the transcript are the server's, recorded in
// tests/fixtures/diff-structured-responses.json by tests/test_diff_structured_session.py;
// the focused checks below build their own small trees. Prints the transcript
// tests/golden/cli-ui-diff-structured.tryscript.md pins.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { pathToFileURL } = require("node:url");

const root = process.argv[2] ?? path.resolve(__dirname, "../..");
const plugins = path.join(root, "src/metabrowser/builtin_plugins");
const recording = JSON.parse(
  fs.readFileSync(path.join(root, "tests/fixtures/diff-structured-responses.json"), "utf8"),
);

async function main() {
  // The tree helpers are classic scripts that publish on the global object.
  require(path.join(plugins, "structured/preview.js"));
  require(path.join(plugins, "structured/tree.js"));
  const tree = globalThis.__structuredTree;
  const preview = globalThis.__structuredPreview;
  const helpers = {
    materializeRows: tree.materializeRows,
    renderRowHtml: tree.renderRowHtml,
    calculateOptimalExpansion: preview.calculateOptimalExpansion,
  };
  const { diffRows, initialExpansion, isStructuredProjection } = await import(
    pathToFileURL(path.join(plugins, "diff/diff-structured.js")).href
  );

  // As the server answers `name: demo / version: 3 / services: {...}` changed to bump
  // the version, add a port, and drop `db`.
  const projection = {
    version: "structured-diff-v1",
    status: "ready",
    format: "yaml",
    source_only: false,
    root: [
      {
        change: "modified",
        type: "map",
        entries: [
          { key: "name", change: "context", value: "demo" },
          { key: "version", change: "removed", value: 3 },
          { key: "version", change: "added", value: 4 },
          {
            key: "services",
            change: "modified",
            type: "map",
            entries: [
              {
                key: "web",
                change: "modified",
                type: "map",
                entries: [
                  { key: "image", change: "context", value: "nginx" },
                  {
                    key: "ports",
                    change: "modified",
                    type: "list",
                    entries: [
                      { change: "context", value: 80 },
                      { change: "added", value: 443 },
                    ],
                  },
                ],
              },
              { key: "db", change: "removed", value: { image: "postgres", port: 5432 } },
            ],
          },
          { key: "flags", change: "context", value: ["fast", "safe"] },
        ],
      },
    ],
  };
  assert.ok(isStructuredProjection(projection), "the server's answer is admitted");
  assert.ok(
    !isStructuredProjection({ ...projection, root: [{ change: "modified", type: "map" }] }),
    "a modified entry without entries is not",
  );
  assert.ok(!isStructuredProjection({ ...projection, status: "unsupported" }));

  const open = initialExpansion(projection.root, helpers);
  assert.deepEqual(
    [...open].sort(),
    ["$", "$.services", "$.services.db", "$.services.web", "$.services.web.ports"],
    "every modified container opens, and a removed one as the file view opens it; " +
      "unchanged ones stay closed",
  );

  const line = (row) =>
    `${"  ".repeat(row.level)}${row.change} ${row.kind} ${row.key ?? (row.isArrayIndex ? "-" : "$")}`;
  const rows = diffRows(projection.root, open, helpers);
  assert.deepEqual(rows.map(line), [
    "modified open $",
    "  context kv name",
    "  removed kv version",
    "  added kv version",
    "  modified open services",
    "    modified open web",
    "      context kv image",
    "      modified open ports",
    "        context item -",
    "        added item -",
    "    removed open db",
    "      removed kv image",
    "      removed kv port",
    "  context open flags",
  ]);
  assert.deepEqual(
    rows.map((row) => row.path),
    [
      "$",
      "$.name",
      "$.version",
      "$.version~2",
      "$.services",
      "$.services.web",
      "$.services.web.image",
      "$.services.web.ports",
      "$.services.web.ports[0]",
      "$.services.web.ports[1]",
      "$.services.db",
      "$.services.db.image",
      "$.services.db.port",
      "$.flags",
    ],
    "a removed key and its added successor have their own paths",
  );
  const services = rows.find((row) => row.path === "$.services");
  assert.equal(services.childCount, 1, "a modified mapping counts the keys its new side holds");

  // A click on a closed unchanged list opens it, as the file view's tree does.
  open.add("$.flags");
  const flags = diffRows(projection.root, open, helpers).filter((row) =>
    row.path.startsWith("$.flags"),
  );
  assert.deepEqual(flags.map(line), [
    "  context open flags",
    "    context item -",
    "    context item -",
  ]);
  // Closing a modified mapping previews its new side.
  open.delete("$.services");
  const closed = diffRows(projection.root, open, helpers).find((row) => row.path === "$.services");
  assert.deepEqual(closed.value, { web: { image: "nginx", ports: [80, 443] } });
  assert.equal(closed.expanded, false);

  // Rows are the tree view's own, marked for the change gutter and for screen readers.
  const removed = tree.renderRowHtml(rows[2], 2);
  assert.match(removed, /class="srow srow-change-removed"/);
  assert.match(
    removed,
    /<span class="sr-only">Removed: <\/span><span class="tok-key">version<\/span>/,
  );
  const added = tree.renderRowHtml(rows[9], 2);
  assert.match(added, /srow-change-added/);
  assert.match(
    added,
    /Added: <\/span><span class="tok-punct">- <\/span><span class="tok-number">443/,
  );
  const modified = tree.renderRowHtml(rows[0], 2);
  assert.match(modified, /srow-container disclosure-toggle srow-expanded srow-change-modified/);
  assert.doesNotMatch(modified, /sr-only/, "a modified container is announced by its rows");
  const context = tree.renderRowHtml(rows[1], 2);
  assert.doesNotMatch(context, /srow-change/);
  const { change: _ignored, ...plain } = rows[1];
  assert.equal(context, tree.renderRowHtml(plain, 2), "an unchanged row is the file view's row");

  // An added file is one whole value, opened as the file view opens it.
  const whole = [{ change: "added", value: { a: 1, b: [1, 2] } }];
  const wholeRows = diffRows(whole, initialExpansion(whole, helpers), helpers);
  assert.deepEqual(wholeRows.map(line), [
    "added open $",
    "  added kv a",
    "  added open b",
    "    added item -",
    "    added item -",
  ]);
  // A changed type at the root draws both documents.
  const swapped = [
    { change: "removed", value: [1] },
    { change: "added", value: "text" },
  ];
  assert.deepEqual(
    diffRows(swapped, initialExpansion(swapped, helpers), helpers).map((row) => row.path),
    ["$", "$[0]", "$~2"],
  );

  // The transcript: each recorded tree as the page first draws it, a row per line with
  // its change, kind, key and text, then after a click opens a closed row and another
  // closes an open one.
  const text = (row) => {
    const html = tree.renderRowHtml(row, 2);
    const shown = html
      .replace(/<span class="sr-only">[^<]*<\/span>/g, "")
      .replace(/<[^>]+>/g, "")
      .replaceAll("&quot;", '"')
      .replaceAll("&#39;", "'")
      .replaceAll("&amp;", "&")
      .replace(/[▸]/g, "")
      .trim();
    return `${"  ".repeat(row.level)}${row.change} ${row.kind} ${shown}`;
  };
  const transcript = {};
  for (const [file, answer] of Object.entries(recording)) {
    assert.ok(isStructuredProjection(answer), `${file}: the server's answer is admitted`);
    const opened = initialExpansion(answer.root, helpers);
    const entry = { opens: [...opened].sort(), "first draw": [] };
    entry["first draw"] = diffRows(answer.root, opened, helpers).map(text);
    const closed = diffRows(answer.root, opened, helpers).find(
      (row) => row.kind === "open" && !row.expanded,
    );
    if (closed !== undefined) {
      opened.add(closed.path);
      entry[`after opening ${closed.path}`] = diffRows(answer.root, opened, helpers).map(text);
    }
    const first = entry.opens.find((each) => each !== "$");
    if (first !== undefined) {
      opened.delete(first);
      entry[`after closing ${first}`] = diffRows(answer.root, opened, helpers).map(text);
    }
    transcript[file] = entry;
  }
  console.log(JSON.stringify(transcript, null, 2));
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});

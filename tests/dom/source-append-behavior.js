// Contract checks for the source view's incremental growth.
//
// Both behaviors here replaced something measurably worse: a full re-render on
// every Load more (cost grew with the running total, not the chunk) and a
// fixed 128 KiB request (31 clicks to open a 4 MiB source file).

const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const repoRoot = path.resolve(process.argv[2]);
const failures = [];

function check(name, condition, detail = "failed") {
  if (!condition) {
    failures.push(`${name}: ${detail}`);
  }
}

/** Minimal DOM double: just the shapes appendSourceText navigates. */
function makeNode(tag, className) {
  const classes = new Set(
    String(className || "")
      .split(/\s+/)
      .filter(Boolean),
  );
  return {
    tag,
    children: [],
    text: "",
    classList: {
      contains: (name) => classes.has(name),
      add: (name) => classes.add(name),
    },
    appendChild(node) {
      this.children.push(node);
      if (typeof node === "string") {
        this.text += node;
      } else if (node && typeof node.data === "string") {
        this.text += node.data;
      }
      return node;
    },
    querySelector(selector) {
      return this._map?.[selector] ?? null;
    },
  };
}

function makeWarning() {
  return {
    removed: false,
    outerHTML: '<div class="metabrowser-source-truncation-warning">old</div>',
    remove() {
      this.removed = true;
    },
  };
}

function makeDocument({ highlighted = false, missingCode = false, warning = null } = {}) {
  const code = makeNode("code", highlighted ? "hljs" : "plaintext");
  const host = makeNode("div", "metabrowser-source-host");
  host._map = { "pre.code-block > code": missingCode ? null : code };
  host.inserted = [];
  host.insertAdjacentHTML = function (position, html) {
    this.inserted.push({ position, html });
  };
  const doc = makeNode("#document", "");
  doc._map = {
    ".metabrowser-source-host": host,
    ".metabrowser-source-truncation-warning": warning,
  };
  return { doc, code, host, warning };
}

const sandbox = {
  console,
  document: {
    createTextNode: (data) => ({ data }),
  },
  Math,
  Number,
  Object,
  String,
};
sandbox.window = sandbox;
sandbox.globalThis = sandbox;
vm.createContext(sandbox);
vm.runInContext(
  fs.readFileSync(path.join(repoRoot, "src/metabrowser/static/source-append.js"), "utf-8"),
  sandbox,
  { filename: "source-append.js" },
);

const api = sandbox.MetabrowserSourceAppend;
check("the module installs its namespace", !!api, "MetabrowserSourceAppend missing");

// ── Growth ────────────────────────────────────────────────────────
check("growth doubles the last request", api.nextChunkBytes(1024, 1 << 30) === 2048);
check("growth stops at the cap", api.nextChunkBytes(6 * 1024, 8 * 1024) === 8 * 1024);
check("growth never exceeds the cap", api.nextChunkBytes(1 << 30, 8 * 1024) === 8 * 1024);
check("growth tolerates a zero start", api.nextChunkBytes(0, 4096) === 2);
check(
  "a sequence reaches a large file in few steps",
  (() => {
    let size = 2 * 1024 * 1024;
    let total = size;
    let clicks = 0;
    while (total < 32 * 1024 * 1024 && clicks < 50) {
      size = api.nextChunkBytes(size, 8 * 1024 * 1024);
      total += size;
      clicks += 1;
    }
    return clicks <= 6;
  })(),
  "took more than six clicks to reach 32 MiB",
);

// ── Appending ─────────────────────────────────────────────────────
{
  const { doc, code } = makeDocument();
  check("an append reports success", api.appendSourceText(doc, "hello") === true);
  check("the chunk lands as text", code.text === "hello", code.text);
  api.appendSourceText(doc, " world");
  check("appends accumulate", code.text === "hello world", code.text);
  check(
    "content is appended as a text node, never markup",
    code.children.every((child) => typeof child === "object" && typeof child.data === "string"),
    JSON.stringify(code.children),
  );
}

{
  const { doc, code } = makeDocument();
  check("an empty chunk is a no-op success", api.appendSourceText(doc, "") === true);
  check("an empty chunk appends nothing", code.text === "");
}

{
  // A highlighted block carries markup a raw text append would corrupt, so the
  // caller must be told to fall back to a full render.
  const { doc, code } = makeDocument({ highlighted: true });
  check("a highlighted block refuses the append", api.appendSourceText(doc, "x") === false);
  check("a refused append changes nothing", code.text === "");
}

{
  const { doc } = makeDocument({ missingCode: true });
  check(
    "an unexpected shape refuses rather than dropping content",
    api.appendSourceText(doc, "x") === false,
  );
}

check("a missing root refuses", api.appendSourceText(null, "x") === false);

// ── Truncation banner ─────────────────────────────────────────────
//
// The append skips the plugin's render, so a banner left untouched keeps the
// byte counts from the previous chunk and survives past the final one.
{
  const warning = makeWarning();
  const { doc } = makeDocument({ warning });
  check("a completed load removes the banner", api.syncTruncationWarning(doc, "") === true);
  check("the stale banner is actually gone", warning.removed === true);
}

{
  const warning = makeWarning();
  const { doc } = makeDocument({ warning });
  const fresh =
    '<div class="metabrowser-source-truncation-warning">Showing 4.0 MB of 8.0 MB.</div>';
  check("a partial load refreshes the banner", api.syncTruncationWarning(doc, fresh) === true);
  check("the banner reports the new counts", warning.outerHTML === fresh, warning.outerHTML);
  check("refreshing does not remove it", warning.removed === false);
}

{
  const { doc, host } = makeDocument();
  const fresh =
    '<div class="metabrowser-source-truncation-warning">Showing 2.0 MB of 8.0 MB.</div>';
  check("an absent banner is inserted", api.syncTruncationWarning(doc, fresh) === true);
  check(
    "the banner leads the source host",
    host.inserted.length === 1 && host.inserted[0].position === "afterbegin",
    JSON.stringify(host.inserted),
  );
}

check("syncing a missing root refuses", api.syncTruncationWarning(null, "") === false);

if (failures.length) {
  console.error(`source append FAILURES:\n- ${failures.join("\n- ")}`);
  process.exit(1);
}
console.log("source append OK");

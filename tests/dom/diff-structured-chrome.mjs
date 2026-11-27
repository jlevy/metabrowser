// A changed YAML or JSON file's Rendered tree, laid out and timed by headless Chrome: the
// production `mountStructuredDiff` (builtin_plugins/diff/diff-structured.js) draws merged
// trees with the core preview and tree scripts, under the shell's, the
// shared tree's and the diff plugin's stylesheets, in a pull request's diff host.
//
//   CHROME_BIN=/path/to/chrome CHROME_PROFILES=/dir/the/caller/removes \
//     [STRUCTURED_SWEEP=1] node tests/dom/diff-structured-chrome.mjs
//
// tests/test_diff_structured_chrome.py owns the profile and runs this in a process group
// of its own. It holds:
//
// - that a changed value's row wraps, so a long changed string shows where it changed,
//   while an unchanged row and a container's row keep the file view's one line (C8 of
//   mb-8274 review);
// - that a first draw stays within `ROW_BUDGET` rows, that a whole value's root past the
//   file view's threshold opens only on a click and then draws a page, and that a "more"
//   row or a click draws again only the rows it changes (A5);
// - that the note a `source_only` tree draws is the app's quiet chrome.
//
// Each shape's mount and click times go to stderr. STRUCTURED_SWEEP=1 instead times
// drawing the first N rows of four row shapes, the measurement `ROW_BUDGET` and `PAGE`
// record, and prints it as JSON.
import fs from "node:fs";
import http from "node:http";
import os from "node:os";
import path from "node:path";
import { launchChrome } from "./chrome-session.mjs";

const root = path.resolve(import.meta.dirname, "../..");
const STATIC = path.join(root, "src/metabrowser/static");
const PLUGINS = path.join(root, "src/metabrowser/builtin_plugins");
const SWEEP = process.env.STRUCTURED_SWEEP === "1";
const failures = [];
let checks = 0;
const check = (label, ok, detail = "") => {
  checks += 1;
  if (!ok) {
    failures.push(`${label}${detail ? `: ${detail}` : ""}`);
  }
};

const PAGE_HTML = `<!doctype html><html style="--doc-max-chars: ${process.env.DOC_MAX_CHARS}"><head><meta charset="utf-8"><title>structured diff</title>
<link rel="stylesheet" href="/static/styles.css">
<link rel="stylesheet" href="/static/structured-tree.css">
<link rel="stylesheet" href="/plugins/diff/styles.css">
<script src="/static/structured-preview.js"></script>
<script src="/static/structured-tree.js"></script>
<script type="module">
import * as structured from "/plugins/diff/diff-structured.js";
window.structuredDiff = {
  ...structured,
  helpers: {
    ...window.__structuredPreview,
    ...window.__structuredTree,
  },
};
</script>
</head><body><div id="preview-pane" class="preview-pane" style="width: 900px"></div></body></html>`;

const TYPES = { ".css": "text/css", ".js": "text/javascript", ".woff2": "font/woff2" };
function serve() {
  const server = http.createServer((request, response) => {
    const url = new URL(request.url ?? "/", "http://localhost");
    let file = null;
    if (url.pathname === "/") {
      response.writeHead(200, { "content-type": "text/html" });
      response.end(PAGE_HTML);
      return;
    }
    if (url.pathname.startsWith("/static/")) {
      file = path.join(STATIC, url.pathname.slice(8));
    } else if (url.pathname.startsWith("/plugins/")) {
      file = path.join(PLUGINS, url.pathname.slice(9));
    }
    if (!file?.startsWith(root + path.sep) || !fs.existsSync(file)) {
      response.writeHead(404);
      response.end();
      return;
    }
    response.writeHead(200, { "content-type": TYPES[path.extname(file)] ?? "text/plain" });
    fs.createReadStream(file).pipe(response);
  });
  return new Promise((resolve) => server.listen(0, "127.0.0.1", () => resolve(server)));
}

// In the page: the helpers below, defined once. `mount` draws a tree in a fresh file of a
// pull request's diff host and times it: the script, the layout it forces, and the next
// frame after them. `press` clicks a row and times it the same way.
const SETUP = `(() => {
  const { mountStructuredDiff, helpers } = window.structuredDiff;
  const frame = () => new Promise((resolve) => requestAnimationFrame(() => setTimeout(resolve, 0)));
  const timed = async (work) => {
    const start = performance.now();
    work();
    const script = performance.now();
    document.body.getBoundingClientRect();
    const layout = performance.now();
    await frame();
    return {
      script: script - start,
      layout: layout - script,
      frame: performance.now() - start,
    };
  };
  const rows = () => [...document.querySelectorAll("#tree .srow")];
  window.page = {
    rows,
    async mount(root, options) {
      const host = document.createElement("div");
      host.className = "github-pull-diff metabrowser-diff-host";
      const file = document.createElement("section");
      file.className = "diff-file";
      const tree = document.createElement("div");
      tree.className = "diff-structured";
      tree.id = "tree";
      file.append(tree);
      host.append(file);
      document.getElementById("preview-pane").replaceChildren(host);
      await frame();
      const time = await timed(() => mountStructuredDiff(tree, root, helpers, options));
      return { ...time, rows: rows().length, elements: tree.querySelectorAll("*").length };
    },
    async press(index) {
      const before = rows();
      const time = await timed(() => before[index].click());
      const after = rows();
      const kept = after.filter((row) => before.includes(row)).length;
      return { ...time, rows: after.length, kept };
    },
  };
  return true;
})()`;

// ── Shapes ──────────────────────────────────────────────────────────────────

const range = (count) => Array.from({ length: count }, (_, index) => index);
const modified = (type, entries) => [{ change: "modified", type, entries }];
const record = (index) => ({
  id: index,
  name: `service-${index}`,
  image: `registry.example.com/team/service-${index}:1.${index % 40}.0`,
  replicas: (index % 5) + 1,
  ports: [8000 + (index % 100), 9000 + (index % 100)],
  labels: { tier: index % 3 ? "backend" : "frontend", owner: `team-${index % 12}` },
});
const SHAPES = {
  // The answers review A5 timed at its node budget, and one of real records.
  "1,998 added lists of 19 items": modified(
    "map",
    range(1998).map((index) => ({ key: `k${index}`, change: "added", value: range(19) })),
  ),
  "one added list of 39,000 items": [{ change: "added", value: range(39_000) }],
  "1,500 added records": modified(
    "list",
    range(1500).map((index) => ({ change: "added", value: record(index) })),
  ),
};

// The four row shapes the sweep draws N rows of: a list's numbers, a mapping's strings,
// closed records, each its preview, and open records, a row per key.
const SWEEP_SHAPES = {
  numbers: [{ change: "added", value: range(8_000) }],
  strings: [
    {
      change: "added",
      value: Object.fromEntries(range(8_000).map((index) => [`key_${index}`, `value ${index}`])),
    },
  ],
  "closed records": [{ change: "added", value: range(8_000).map(record) }],
  "open records": [{ change: "added", value: range(1_000).map(record) }],
};
const SWEEP_ROWS = [250, 500, 1000, 1500, 2000, 4000];
const SWEEP_RUNS = 3;

// In the page: draw the first *count* rows of *root* with every container open, as one
// mount sets them, and then insert the same rows before the last, as a click does.
const DRAW = `async ([root, count, open]) => {
  const { diffRows, helpers } = window.structuredDiff;
  const paths = new Set();
  const all = (value, path) => {
    paths.add(path);
    if (value && typeof value === "object") {
      Object.values(value).forEach((child, index) => all(child, path + "/" + index));
    }
  };
  if (open) all(root[0].value, "$");
  else paths.add("$");
  const rows = diffRows(root, paths, helpers, new Map([["$", 1e9]])).slice(0, count);
  const frame = () => new Promise((resolve) => requestAnimationFrame(() => setTimeout(resolve, 0)));
  const host = document.createElement("div");
  host.className = "github-pull-diff metabrowser-diff-host";
  host.innerHTML = '<section class="diff-file"><div class="diff-structured structured-tree"><div class="tree-viewport tree-viewport-flat"><div class="srow">first</div><div class="srow">last</div></div></div></section>';
  document.getElementById("preview-pane").replaceChildren(host);
  const viewport = host.querySelector(".tree-viewport");
  await frame();
  let start = performance.now();
  viewport.innerHTML = rows.map((row) => helpers.renderRowHtml(row, 2)).join("");
  document.body.getBoundingClientRect();
  const mount = performance.now() - start;
  await frame();
  const mountFrame = performance.now() - start;
  const elements = viewport.querySelectorAll("*").length;
  viewport.innerHTML = '<div class="srow">first</div><div class="srow">last</div>';
  await frame();
  start = performance.now();
  viewport.lastElementChild.insertAdjacentHTML(
    "beforebegin",
    rows.map((row) => helpers.renderRowHtml(row, 2)).join(""),
  );
  document.body.getBoundingClientRect();
  await frame();
  const click = performance.now() - start;
  return { rows: rows.length, elements, mount, mountFrame, click };
}`;

const median = (values) => [...values].sort((a, b) => a - b)[Math.floor(values.length / 2)];
const ms = (value) => Math.round(value * 10) / 10;

const server = await serve();
const { port } = /** @type {import("node:net").AddressInfo} */ (server.address());
/** @type {Awaited<ReturnType<typeof launchChrome>> | null} */
let chrome = null;
try {
  chrome = await launchChrome(/** @type {string} */ (process.env.CHROME_BIN), {
    profiles: /** @type {string} */ (process.env.CHROME_PROFILES),
    width: 1000,
    height: 1200,
  });
  await chrome.send("Page.enable");
  await chrome.send("Page.navigate", { url: `http://127.0.0.1:${port}/` });
  await chrome.waitFor("document.readyState === 'complete' && !!window.structuredDiff");
  await chrome.evaluate("document.fonts.ready.then(() => true)");
  await chrome.evaluate(SETUP);
  const { ROW_BUDGET, PAGE } = await chrome.evaluate(
    "({ ROW_BUDGET: window.structuredDiff.ROW_BUDGET, PAGE: window.structuredDiff.PAGE })",
  );
  const machine = {
    cpu: os.cpus()[0]?.model,
    cores: os.cpus().length,
    load: os.loadavg().map((each) => Math.round(each * 100) / 100),
    chrome: (await chrome.send("Browser.getVersion")).product,
  };

  if (SWEEP) {
    const results = {};
    for (const [shape, root] of Object.entries(SWEEP_SHAPES)) {
      results[shape] = [];
      for (const count of SWEEP_ROWS) {
        const runs = [];
        for (let run = 0; run < SWEEP_RUNS; run += 1) {
          runs.push(
            await chrome.evaluate(
              `(${DRAW})(${JSON.stringify([root, count, shape === "open records"])})`,
            ),
          );
        }
        results[shape].push({
          rows: runs[0].rows,
          elements: runs[0].elements,
          "mount, script and layout": runs.map((each) => ms(each.mount)),
          "mount, to the next frame": runs.map((each) => ms(each.mountFrame)),
          "click, to the next frame": runs.map((each) => ms(each.click)),
          medians: {
            mount: ms(median(runs.map((each) => each.mount))),
            "mount, to the next frame": ms(median(runs.map((each) => each.mountFrame))),
            "click, to the next frame": ms(median(runs.map((each) => each.click))),
          },
        });
      }
    }
    machine.load = os.loadavg().map((each) => Math.round(each * 100) / 100);
    process.stdout.write(`${JSON.stringify({ machine, results }, null, 2)}\n`);
  } else {
    // C8: a long string changed past where a row would clip it.
    const long = `${"word ".repeat(80)}first difference`;
    const wrapped = await chrome.evaluate(`(async () => {
      await window.page.mount(${JSON.stringify(
        modified("map", [
          { key: "description", change: "removed", value: `${long} before` },
          { key: "description", change: "added", value: `${long} after` },
          { key: "summary", change: "context", value: long },
          { key: "short", change: "added", value: "one line" },
          { key: "script", change: "added", value: "make install\nmake test" },
          { key: "data", change: "added", value: { text: long } },
        ]),
      )});
      const rows = window.page.rows();
      const height = parseFloat(getComputedStyle(rows[0]).getPropertyValue("--tree-row-height"));
      return {
        height,
        rows: rows.map((row) => {
          const content = row.querySelector(".srow-content");
          return {
            text: row.textContent.slice(0, 24),
            height: row.getBoundingClientRect().height,
            clipped: content.scrollWidth > content.clientWidth + 1,
            whiteSpace: getComputedStyle(row).whiteSpace,
          };
        }),
      };
    })()`);
    const [root, removed, added, context, short, script, data] = wrapped.rows;
    check("a modified mapping's row is one line", root.height === wrapped.height, `${root.height}`);
    for (const [label, row] of [
      ["the removed long string", removed],
      ["the added long string", added],
    ]) {
      check(`${label} wraps to more than one line`, row.height > wrapped.height, `${row.height}`);
      check(`${label} is not clipped`, !row.clipped);
    }
    check(
      "both sides of the long string are as tall",
      removed.height === added.height,
      `${removed.height} and ${added.height}`,
    );
    check(
      "an unchanged long string keeps the file view's one line",
      context.height === wrapped.height && context.whiteSpace === "nowrap",
      `${context.height} ${context.whiteSpace}`,
    );
    check("a short changed value is one row", short.height === wrapped.height, `${short.height}`);
    check(
      "a changed value's newline breaks its line",
      script.height === 2 * wrapped.height,
      `${script.height}`,
    );
    check(
      "a changed container's row keeps one line for its preview",
      data.height === wrapped.height,
      `${data.height}`,
    );

    // A top-level row starts the tree column. Measure the chevron and content together.
    const geometry = await chrome.evaluate(`(async () => {
      await window.page.mount([{ key: "mode", change: "added", value: "fast" }]);
      const file = document.querySelector(".diff-file");
      const tree = document.getElementById("tree");
      const row = tree.querySelector(".srow-change-added");
      const read = (width) => {
        file.style.inlineSize = width + "px";
        const start = file.getBoundingClientRect().left + file.clientLeft;
        const end = start + file.clientWidth;
        const band = row.getBoundingClientRect();
        const chevron = row.querySelector(".srow-chevron").getBoundingClientRect();
        const content = row.querySelector(".srow-content").getBoundingClientRect();
        const style = getComputedStyle(row);
        return {
          startInset: chevron.left - start,
          endInset: end - content.right,
          bandStart: band.left - start,
          bandEnd: end - band.right,
          gutterColor: style.borderInlineStartColor,
          gutterWidth: parseFloat(style.borderInlineStartWidth),
        };
      };
      const wide = read(1000);
      const narrow = read(360);
      // The format controller sets hidden on a rendered tree when selecting Source.
      tree.hidden = true;
      return { wide, narrow, hiddenDisplay: getComputedStyle(tree).display };
    })()`);
    for (const [size, measured] of [
      ["wide", geometry.wide],
      ["narrow", geometry.narrow],
    ]) {
      check(
        `${size}: the tree is centered in the diff box`,
        Math.abs(measured.startInset - measured.endInset) < 0.5,
        JSON.stringify(measured),
      );
      check(
        `${size}: the colored change gutter stays at the edge of the full-width band`,
        measured.bandStart === 0 &&
          measured.bandEnd === 0 &&
          measured.gutterWidth > 0 &&
          measured.gutterColor !== "rgba(0, 0, 0, 0)",
        JSON.stringify(measured),
      );
    }
    check(
      "the wide diff box has larger margins than the narrow box",
      geometry.wide.startInset > geometry.narrow.startInset,
      JSON.stringify(geometry),
    );
    check(
      "Source hides the rendered tree",
      geometry.hiddenDisplay === "none",
      geometry.hiddenDisplay,
    );

    // The note above a source-only tree is quiet chrome, in the app's muted token.
    const note = await chrome.evaluate(`(async () => {
      await window.page.mount([{ change: "context", value: { mode: "fast" } }], { sourceOnly: true });
      const note = document.querySelector("#tree > p.diff-structured-note");
      const probe = document.createElement("span");
      probe.style.color = "var(--muted)";
      note.append(probe);
      const muted = getComputedStyle(probe).color;
      probe.remove();
      return { color: getComputedStyle(note).color, muted, rows: window.page.rows().length };
    })()`);
    check("the note is the app's muted tone", note.color === note.muted, JSON.stringify(note));
    check("the note sits above the tree's one row", note.rows === 1, `${note.rows}`);

    // A5: the shapes review A5 timed, each first draw within the budget.
    const timings = {};
    for (const [shape, tree] of Object.entries(SHAPES)) {
      const mounted = await chrome.evaluate(`window.page.mount(${JSON.stringify(tree)})`);
      timings[shape] = { mount: mounted };
      check(
        `${shape}: the first draw is within ${ROW_BUDGET} rows`,
        mounted.rows <= ROW_BUDGET,
        `${mounted.rows}`,
      );
      if (shape === "one added list of 39,000 items") {
        check(`${shape}: the root stays closed`, mounted.rows === 1, `${mounted.rows}`);
        const opened = await chrome.evaluate("window.page.press(0)");
        timings[shape]["open the root"] = opened;
        check(`${shape}: opened, it draws a page`, opened.rows === PAGE + 2, `${opened.rows}`);
        const more = await chrome.evaluate(`window.page.press(${PAGE + 1})`);
        timings[shape]["draw the next page"] = more;
        check(
          `${shape}: the more row draws the next page`,
          more.rows === 2 * PAGE + 2,
          `${more.rows}`,
        );
        check(
          `${shape}: and draws again no row that was drawn`,
          more.kept === PAGE + 1,
          `${more.kept}`,
        );
      } else {
        const index = await chrome.evaluate(
          "window.page.rows().findIndex((row) => row.classList.contains('srow-collapsed'))",
        );
        const before = mounted.rows;
        const opened = await chrome.evaluate(`window.page.press(${index})`);
        timings[shape]["open a closed value"] = opened;
        check(
          `${shape}: a click draws again only the row it opens`,
          opened.kept === before - 1,
          `${opened.kept} of ${before}`,
        );
      }
    }
    process.stderr.write(
      `${JSON.stringify({ machine, ROW_BUDGET, PAGE, wrapped, timings }, (_key, value) => (typeof value === "number" ? ms(value) : value))}\n`,
    );
  }
} finally {
  await chrome?.close();
  server.close();
}
if (failures.length > 0) {
  process.stderr.write(`${failures.join("\n")}\n`);
  process.exit(1);
}
if (!SWEEP) {
  process.stdout.write(`structured diff in Chrome: ${checks} checks passed\n`);
}

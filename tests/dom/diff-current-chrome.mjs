// A diff file bar's end group, laid out by headless Chrome: the production `mountDiffView`
// (builtin_plugins/diff/diff-view.js), with diff-markdown.js's views and the shell's own chip
// family (static/filter-controls.js), mounts a comparison of a Markdown file and a code file
// under the shell's, the diff plugin's, and KPress's stylesheets.
//
//   CHROME_BIN=/path/to/chrome CHROME_PROFILES=/dir/the/caller/removes \
//     KPRESS_STATIC=/dir/with/kpress/css/and/fonts CURRENT_INPUT=/path/to/input.json \
//     [CURRENT_SHOTS=/dir/for/screenshots] node tests/dom/diff-current-chrome.mjs
//
// tests/test_diff_current_chrome.py writes CURRENT_INPUT ({sheets}), copies KPress's
// stylesheets and faces out of the installed package, owns the profile, and runs this in a
// process group of its own. CURRENT_SHOTS, when set, receives a screenshot of the diff in
// Diff and in Current, with the Markdown file in Rendered and in Source, and one narrow.
//
// What it measures is layout, which no browserless DOM computes (docs/design-system.md,
// "Diff File Bar"): the bar's end group is right-aligned, its Diff | Current and the
// Markdown file's Rendered | Source share one line in that order, Rendered | Source ends
// the bar, and a bar with Diff | Current alone ends with it; where the bar is too narrow
// for its two groups, the end group takes the next line, still at the bar's end, with both
// choosers on it; and choosing Current or Source moves neither chooser. The Markdown file's
// answer is the server's projection recorded in tests/fixtures/diff-markdown-responses.json.
import fs from "node:fs";
import http from "node:http";
import path from "node:path";
import { launchChrome } from "./chrome-session.mjs";

const root = path.resolve(import.meta.dirname, "../..");
const STATIC = path.join(root, "src/metabrowser/static");
const DIFF = path.join(root, "src/metabrowser/builtin_plugins/diff");
const KPRESS = path.resolve(/** @type {string} */ (process.env.KPRESS_STATIC));
const INPUT = JSON.parse(
  fs.readFileSync(/** @type {string} */ (process.env.CURRENT_INPUT), "utf8"),
);
const SHOTS = process.env.CURRENT_SHOTS;
const recorded = JSON.parse(
  fs.readFileSync(path.join(root, "tests/fixtures/diff-markdown-responses.json"), "utf8"),
);
// Layout puts box edges on 1/64 px; a box's rounding to it is the same place.
const TOLERANCE_PX = 1 / 64;
const failures = [];
let checks = 0;
const check = (label, ok, detail = "") => {
  checks += 1;
  if (!ok) {
    failures.push(`${label}${detail ? `: ${detail}` : ""}`);
  }
};
const near = (a, b) => Math.abs(a - b) <= TOLERANCE_PX;

const side = (filePath) => ({
  content: { kind: "empty" },
  entry_type: "file",
  mode: "100644",
  path: filePath,
});
const hunk = (oldStart, oldCount, newStart, newCount, lines) => ({
  lines: lines.map(([op, text]) => ({ op, text })),
  new_count: newCount,
  new_start: newStart,
  old_count: oldCount,
  old_start: oldStart,
});
/** A Markdown file, whose bar has both choosers, and a code file, whose bar has one. */
const COMPARISON = {
  manifest: {
    cursor: null,
    files: [
      {
        additions: 2,
        availability: "ready",
        binary: false,
        deletions: 2,
        id: "f1",
        kind: "modified",
        new: side("docs/guide.md"),
        old: side("docs/guide.md"),
      },
      {
        additions: 2,
        availability: "ready",
        binary: false,
        deletions: 1,
        id: "f2",
        kind: "modified",
        new: side("src/metabrowser/a.py"),
        old: side("src/metabrowser/a.py"),
      },
    ],
    totals: { additions: 4, deletions: 3, exact: true, files: 2 },
    truncated: false,
  },
  patches: {
    f1: {
      file_id: "f1",
      hunks: [
        hunk(6, 4, 6, 4, [
          ["context", "# Guide"],
          ["context", ""],
          ["del", "Read the setup notes first."],
          ["add", "Read the [first setup notes](setup.md) first."],
          ["context", ""],
        ]),
        hunk(30, 3, 30, 3, [
          ["context", "![diagram](diagram.png)"],
          ["context", ""],
          ["del", "The ~~old~~ closing line."],
          ["add", "The <ins>new</ins> closing line."],
        ]),
      ],
      truncated: false,
    },
    f2: {
      file_id: "f2",
      hunks: [
        hunk(3, 3, 3, 4, [
          ["context", "def f():"],
          ["del", "    return 1"],
          ["add", "    x = 2"],
          ["add", "    return x"],
          ["context", ""],
        ]),
      ],
      truncated: false,
    },
  },
  resolved: {
    base_policy: "direct",
    comparison_id: "chrome:current",
    kind: "content",
    left: { kind: "patch" },
    options: { context: 3, rename_detection: true, rename_similarity: 50 },
    right: { kind: "patch" },
    source: { name: "chrome" },
  },
  schema: "file-diff-v1",
  schema_version: 1,
};

// The shell's tokens and sheet, then the diff plugin's, then KPress's document sheets; the
// shell's icons, its SDK's chip family, and the inert-HTML runtime the Markdown views use.
const PAGE = `<!doctype html><html><head><meta charset="utf-8"><title>diff current</title>
<link rel="stylesheet" href="/kpress/css/style-tokens.css">
<link rel="stylesheet" href="/static/styles.css">
<link rel="stylesheet" href="/diff/styles.css">
${INPUT.sheets.map((sheet) => `<link rel="stylesheet" href="/kpress/${sheet}">`).join("\n")}
<script src="/static/icons.js"></script>
<script>window.metabrowser = { icons: window.MetabrowserIcons };</script>
<script src="/static/filter-controls.js"></script>
<script src="/static/inert-html.js"></script>
<script type="module">
import { mountDiffView } from "/diff/diff-view.js";
import * as markdownViews from "/diff/diff-markdown.js";
window.diffCurrent = { mountDiffView, markdownViews };
</script>
</head><body><div id="preview-pane" class="preview-pane"><div id="host" class="metabrowser-diff-host" style="width: 900px"></div></div></body></html>`;

const TYPES = { ".css": "text/css", ".js": "text/javascript", ".woff2": "font/woff2" };
function serve() {
  const server = http.createServer((request, response) => {
    const url = new URL(request.url ?? "/", "http://localhost");
    let file = null;
    if (url.pathname === "/") {
      response.writeHead(200, { "content-type": "text/html" });
      response.end(PAGE);
      return;
    }
    if (url.pathname.startsWith("/static/")) {
      file = path.join(STATIC, url.pathname.slice(8));
    } else if (url.pathname.startsWith("/diff/")) {
      file = path.join(DIFF, url.pathname.slice(6));
    } else if (url.pathname.startsWith("/kpress/")) {
      file = path.join(KPRESS, url.pathname.slice(8));
    }
    const within = [root, KPRESS].some((dir) => file?.startsWith(dir + path.sep));
    if (!file || !within || !fs.existsSync(file)) {
      response.writeHead(404);
      response.end();
      return;
    }
    response.writeHead(200, { "content-type": TYPES[path.extname(file)] ?? "text/plain" });
    fs.createReadStream(file).pipe(response);
  });
  return new Promise((resolve) => server.listen(0, "127.0.0.1", () => resolve(server)));
}

// In the page: mount the comparison as a pull request's Changes does, with the shell's chip
// family and a preference store of the page's own, and the recorded answer for the
// Markdown file. Resolves once the Rendered view is drawn.
const MOUNT = `async (comparison, answer, imageRoute) => {
  const { mountDiffView, markdownViews } = window.diffCurrent;
  const prefs = new Map([["diff.layout", "unified"]]);
  const api = {
    highlightSyntax: async () => null,
    isLargeTextPreview: () => true,
    langForPath: () => "",
    ensureAsset: async () => {},
    loadKpressAssets: async () => {},
    prefs: {
      get: (key, fallback) => (prefs.has(key) ? prefs.get(key) : fallback),
      set: (key, value) => (prefs.set(key, value), true),
    },
    filterControls: window.metabrowser.filterControls,
  };
  mountDiffView(document.getElementById("host"), comparison, api, {
    showSummary: false,
    markdownViews,
    renderMarkdown: async () => structuredClone(answer),
    markdownTargets: markdownViews.markdownTargets(imageRoute, () => true),
    markdownHoldMs: 0,
  });
  for (let frame = 0; frame < 120; frame += 1) {
    const rendered = document.querySelector(".diff-markdown");
    if (rendered && !rendered.hidden && rendered.querySelector(".diff-markdown-block")) {
      return true;
    }
    await new Promise((resolve) => requestAnimationFrame(resolve));
  }
  return false;
}`;

// Each bar's boxes at the host's width *width*: the bar's content box, its two groups, and
// its choosers, in the viewport's coordinates.
const BARS = `async (width) => {
  document.getElementById("host").style.width = width + "px";
  for (let frame = 0; frame < 3; frame += 1) {
    await new Promise((resolve) => requestAnimationFrame(resolve));
  }
  const box = (node) => {
    if (!node) return null;
    const rect = node.getBoundingClientRect();
    return { left: rect.left, right: rect.right, top: rect.top, bottom: rect.bottom };
  };
  return [...document.querySelectorAll(".diff-file-bar")].map((bar) => {
    const style = getComputedStyle(bar);
    const rect = bar.getBoundingClientRect();
    return {
      path: bar.querySelector(".diff-file-path")?.textContent ?? bar.textContent,
      top: rect.top,
      contentRight: rect.right - bar.clientLeft - Number.parseFloat(style.paddingRight),
      lead: box(bar.querySelector(".diff-file-lead")),
      end: box(bar.querySelector(".diff-file-end")),
      show: box(bar.querySelector(".diff-show-control")),
      format: box(bar.querySelector(".diff-markdown-control")),
      chips: [...bar.querySelectorAll(".diff-file-end [data-chip-value]")].map((chip) => chip.textContent),
    };
  });
}`;

/** A chip's click, by the shell's chip family, on the first bar that has it. */
const CLICK = `async (value) => {
  document.querySelector('.diff-file-end [data-chip-value="' + value + '"]').click();
  for (let frame = 0; frame < 3; frame += 1) {
    await new Promise((resolve) => requestAnimationFrame(resolve));
  }
  return document.querySelector(".diff-root")?.dataset.show ?? null;
}`;

/** The end group's checks for every bar at one width. */
function endGroup(bars, width) {
  const [markdown, code] = bars;
  check(`${width} px: two bars`, bars.length === 2, `${bars.length}`);
  check(
    `${width} px: the Markdown bar's end group reads Diff | Current, then Rendered | Source`,
    markdown.chips.join(" ") === "Diff Current Rendered Source",
    markdown.chips.join(" "),
  );
  check(
    `${width} px: the Markdown bar's choosers share one line`,
    near(markdown.show.top, markdown.format.top) &&
      near(markdown.show.bottom, markdown.format.bottom),
    JSON.stringify([markdown.show, markdown.format]),
  );
  check(
    `${width} px: Diff | Current comes before Rendered | Source`,
    markdown.show.right <= markdown.format.left + TOLERANCE_PX,
    JSON.stringify([markdown.show, markdown.format]),
  );
  check(
    `${width} px: Rendered | Source ends the bar, at its content box's end`,
    near(markdown.format.right, markdown.end.right) &&
      near(markdown.end.right, markdown.contentRight),
    JSON.stringify({ format: markdown.format, end: markdown.end, right: markdown.contentRight }),
  );
  check(
    `${width} px: a code file's bar ends with its Diff | Current`,
    code.chips.join(" ") === "Diff Current" &&
      code.format === null &&
      near(code.show.right, code.end.right) &&
      near(code.end.right, code.contentRight),
    JSON.stringify({ chips: code.chips, show: code.show, right: code.contentRight }),
  );
}

/** @type {Awaited<ReturnType<typeof launchChrome>> | null} */
let chrome = null;
const server = /** @type {http.Server} */ (await serve());
const { port } = /** @type {import("node:net").AddressInfo} */ (server.address());
/** @param {string} name */
const shot = async (name) => {
  if (!SHOTS || !chrome) {
    return;
  }
  const clip = await chrome.evaluate(`(() => {
    const rect = document.getElementById("host").getBoundingClientRect();
    return { x: rect.left, y: rect.top, width: rect.width, height: rect.height, scale: 1 };
  })()`);
  const { data } = await chrome.send("Page.captureScreenshot", {
    format: "png",
    clip,
    captureBeyondViewport: true,
  });
  fs.mkdirSync(SHOTS, { recursive: true });
  fs.writeFileSync(path.join(SHOTS, `${name}.png`), Buffer.from(data, "base64"));
};
try {
  chrome = await launchChrome(/** @type {string} */ (process.env.CHROME_BIN), {
    profiles: /** @type {string} */ (process.env.CHROME_PROFILES),
    width: 1000,
    height: 1400,
  });
  await chrome.send("Page.enable");
  await chrome.send("Page.navigate", { url: `http://127.0.0.1:${port}/` });
  await chrome.waitFor(
    "document.readyState === 'complete' && !!window.MetabrowserInertHtml && !!window.diffCurrent && !!window.metabrowser.filterControls",
  );
  const mounted = await chrome.evaluate(
    `(${MOUNT})(${JSON.stringify(COMPARISON)}, ${JSON.stringify(recorded.answers.f1)}, ${JSON.stringify(recorded.image_route)})`,
  );
  check("the Markdown file's Rendered view is drawn", mounted === true, `${mounted}`);
  await chrome.evaluate("document.fonts.ready.then(() => true)");

  const wide = await chrome.evaluate(`(${BARS})(900)`);
  endGroup(wide, 900);
  check(
    "900 px: each bar is one line, the end group beside the name's group",
    wide.every((bar) => near(bar.end.top, bar.lead.top) || bar.end.top < bar.lead.bottom),
    JSON.stringify(wide.map((bar) => [bar.lead, bar.end])),
  );
  await shot("diff-rendered");

  // Narrow enough that the name's group and the end group do not fit one line.
  const narrow = await chrome.evaluate(`(${BARS})(380)`);
  endGroup(narrow, 380);
  check(
    "380 px: the Markdown bar's end group takes the next line",
    narrow[0].end.top >= narrow[0].lead.bottom - TOLERANCE_PX,
    JSON.stringify([narrow[0].lead, narrow[0].end]),
  );
  await shot("narrow-diff-rendered");

  // Choosing keeps both choosers on their line at the bar's end. Only the chosen chip's
  // word changes, to the medium weight a selected chip takes ("Choosing Among Values"), so
  // a chooser's width moves by that word's, measured at 0.28 to 0.31 px in Chrome, and the
  // chooser before it moves by as much; a pixel bounds it. A bar below the Markdown file
  // moves with the rows Current hides above it, so each box is read against its own bar.
  const stays = (label, after) => {
    const moved = after.flatMap((bar, index) =>
      [
        [bar.show, before[index].show],
        [bar.format, before[index].format],
      ].flatMap(([now, was]) =>
        now === null && was === null
          ? []
          : [
              now.top - bar.top - (was.top - before[index].top),
              now.bottom - bar.top - (was.bottom - before[index].top),
              now.left - was.left,
              now.right - was.right,
            ],
      ),
    );
    check(
      label,
      after.every(
        (bar, index) =>
          near(bar.show.top - bar.top, before[index].show.top - before[index].top) &&
          near(bar.end.right, before[index].end.right),
      ) && moved.every((delta) => Math.abs(delta) < 1),
      JSON.stringify(moved),
    );
  };
  await chrome.evaluate(`(${BARS})(900)`);
  const before = await chrome.evaluate(`(${BARS})(900)`);
  const shown = await chrome.evaluate(`(${CLICK})("current")`);
  check("Current is chosen", shown === "current", `${shown}`);
  const current = await chrome.evaluate(`(${BARS})(900)`);
  endGroup(current, 900);
  stays("choosing Current keeps both choosers on their line at the bar's end", current);
  await shot("current-rendered");
  await chrome.evaluate(`(${CLICK})("source")`);
  const source = await chrome.evaluate(`(${BARS})(900)`);
  endGroup(source, 900);
  stays("choosing Source keeps both choosers on their line at the bar's end", source);
  await shot("current-source");
  await chrome.evaluate(`(${CLICK})("diff")`);
  await shot("diff-source");
} finally {
  await chrome?.close();
  server.close();
}
if (failures.length > 0) {
  process.stderr.write(`${failures.join("\n")}\n`);
  process.exit(1);
}
process.stdout.write(`diff current in Chrome: ${checks} checks passed\n`);

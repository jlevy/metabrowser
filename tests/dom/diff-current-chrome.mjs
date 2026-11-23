// A diff's toolbar and its file bars' end groups, laid out by headless Chrome: the production
// `mountDiffView` (builtin_plugins/diff/diff-view.js), with diff-markdown.js's views and the
// shell's own chip family (static/filter-controls.js), mounts a comparison of a Markdown file
// and a code file twice under the shell's, the diff plugin's, and KPress's stylesheets: as a
// pull request's Changes mounts it, and as its Docs tab does, with the layout fixed, Current
// its default, and a preference of its own (github/pull-page.js).
//
//   CHROME_BIN=/path/to/chrome CHROME_PROFILES=/dir/the/caller/removes \
//     KPRESS_STATIC=/dir/with/kpress/css/and/fonts CURRENT_INPUT=/path/to/input.json \
//     [CURRENT_SHOTS=/dir/for/screenshots] node tests/dom/diff-current-chrome.mjs
//
// tests/test_diff_current_chrome.py writes CURRENT_INPUT ({sheets}), copies KPress's
// stylesheets and faces out of the installed package, owns the profile, and runs this in a
// process group of its own. CURRENT_SHOTS, when set, receives screenshots: Changes in Diff
// and in Current, Changes narrow, and Docs in Current and in Diff.
//
// What it measures is layout, which no browserless DOM computes (docs/design-system.md,
// "Diff Toolbar" and "Diff File Bar"): on Changes the toolbar's Diff | Current and
// Split | Unified share one line in that order, right-aligned at the toolbar's content end;
// on Docs, Diff | Current alone ends the toolbar there; a file bar's end group holds a
// Markdown file's Rendered | Source alone, which ends the bar, and a code file's nothing; and
// choosing Current, or Source, moves no chooser. The Markdown file's answer is the server's
// projection recorded in tests/fixtures/diff-markdown-responses.json.
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
/** The mount options a pull request's Docs tab passes (github/pull-page.js). */
const DOCS = {
  unfold: true,
  layout: "unified",
  show: "current",
  showPreference: "github.docs.show",
};
/** A Markdown file, whose bar ends with Rendered | Source, and a code file, whose bar ends bare. */
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
</head><body><div id="preview-pane" class="preview-pane">
<div id="changes" class="metabrowser-diff-host" style="width: 900px"></div>
<div id="docs" class="metabrowser-diff-host" style="width: 900px; margin-top: 24px"></div>
</div></body></html>`;

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

// In the page: mount the comparison in the host *hostId* with the host's *options*, the
// shell's chip family, a preference store of its own, and the recorded answer for the
// Markdown file. Resolves once the Rendered view is drawn.
const MOUNT = `async (hostId, options, comparison, answer, imageRoute) => {
  const { mountDiffView, markdownViews } = window.diffCurrent;
  const host = document.getElementById(hostId);
  const prefs = new Map([["diff.layout", "unified"]]);
  const writes = [];
  const api = {
    highlightSyntax: async () => null,
    isLargeTextPreview: () => true,
    langForPath: () => "",
    ensureAsset: async () => {},
    loadKpressAssets: async () => {},
    prefs: {
      get: (key, fallback) => (prefs.has(key) ? prefs.get(key) : fallback),
      set: (key, value) => (prefs.set(key, value), writes.push(key + "=" + value), true),
    },
    filterControls: window.metabrowser.filterControls,
  };
  (window.writes ??= {})[hostId] = writes;
  mountDiffView(host, comparison, api, {
    showSummary: false,
    markdownViews,
    renderMarkdown: async () => structuredClone(answer),
    markdownTargets: markdownViews.markdownTargets(imageRoute, () => true),
    markdownHoldMs: 0,
    ...options,
  });
  for (let frame = 0; frame < 120; frame += 1) {
    const rendered = host.querySelector(".diff-markdown");
    if (rendered && !rendered.hidden && rendered.querySelector(".diff-markdown-block")) {
      return host.querySelector(".diff-root")?.dataset.show ?? null;
    }
    await new Promise((resolve) => requestAnimationFrame(resolve));
  }
  return false;
}`;

// The boxes of the host *hostId* at the width *width*: its toolbar's content box and
// choosers, and each bar's content box, its two groups, and what its end group holds, in the
// viewport's coordinates.
const MEASURE = `async (hostId, width) => {
  const host = document.getElementById(hostId);
  host.style.width = width + "px";
  for (let frame = 0; frame < 3; frame += 1) {
    await new Promise((resolve) => requestAnimationFrame(resolve));
  }
  const box = (node) => {
    if (!node) return null;
    const rect = node.getBoundingClientRect();
    return { left: rect.left, right: rect.right, top: rect.top, bottom: rect.bottom };
  };
  const content = (node) => {
    const style = getComputedStyle(node);
    const rect = node.getBoundingClientRect();
    return {
      left: rect.left + node.clientLeft + Number.parseFloat(style.paddingLeft),
      right: rect.right - node.clientLeft - Number.parseFloat(style.paddingRight),
      top: rect.top,
    };
  };
  const chips = (node) =>
    node ? [...node.querySelectorAll("[data-chip-value]")].map((chip) => chip.textContent) : [];
  const toolbar = host.querySelector(".diff-toolbar");
  return {
    shows: host.querySelector(".diff-root")?.dataset.show ?? null,
    toolbar: toolbar && {
      content: content(toolbar),
      holds: [...toolbar.children].map((child) => child.className),
      show: box(toolbar.querySelector(".diff-show-control")),
      layout: box(toolbar.querySelector(".diff-layout-control")),
      showChips: chips(toolbar.querySelector(".diff-show-control")),
      layoutChips: chips(toolbar.querySelector(".diff-layout-control")),
      scrolls: toolbar.scrollWidth > toolbar.clientWidth,
    },
    bars: [...host.querySelectorAll(".diff-file-bar")].map((bar) => ({
      path: bar.querySelector(".diff-file-path")?.textContent ?? bar.textContent,
      ...content(bar),
      lead: box(bar.querySelector(".diff-file-lead")),
      end: box(bar.querySelector(".diff-file-end")),
      format: box(bar.querySelector(".diff-markdown-control")),
      holds: [...bar.querySelector(".diff-file-end").children]
        .filter((child) => !child.classList.contains("diff-markdown-progress"))
        .map((child) => child.className),
      chips: chips(bar.querySelector(".diff-file-end")),
    })),
  };
}`;

/** A chip's click, by the shell's chip family, in the host *hostId*'s *where*. */
const CLICK = `async (hostId, where, value) => {
  const host = document.getElementById(hostId);
  host.querySelector(where + ' [data-chip-value="' + value + '"]').click();
  for (let frame = 0; frame < 3; frame += 1) {
    await new Promise((resolve) => requestAnimationFrame(resolve));
  }
  return host.querySelector(".diff-root")?.dataset.show ?? null;
}`;

/** The toolbar's checks for one surface at one width. */
function toolbarChecks(surface, measured, width) {
  const { toolbar } = measured;
  const at = `${surface}, ${width} px`;
  check(`${at}: a toolbar is drawn`, toolbar !== null);
  if (toolbar === null) {
    return;
  }
  check(
    `${at}: the toolbar's Diff | Current reads Diff, Current`,
    toolbar.showChips.join(" ") === "Diff Current",
    toolbar.showChips.join(" "),
  );
  check(`${at}: nothing in the toolbar scrolls`, toolbar.scrolls === false);
  check(
    `${at}: Diff | Current is inside the toolbar's content box`,
    toolbar.show.left >= toolbar.content.left - TOLERANCE_PX,
    JSON.stringify({ show: toolbar.show, content: toolbar.content }),
  );
  if (surface === "Docs") {
    check(
      `${at}: the toolbar holds Diff | Current alone, at its content box's end`,
      JSON.stringify(toolbar.holds) === JSON.stringify(["diff-show-control"]) &&
        toolbar.layout === null &&
        near(toolbar.show.right, toolbar.content.right),
      JSON.stringify({ holds: toolbar.holds, show: toolbar.show, content: toolbar.content }),
    );
    return;
  }
  check(
    `${at}: the toolbar holds Diff | Current, then Split | Unified`,
    JSON.stringify(toolbar.holds) ===
      JSON.stringify(["diff-show-control", "diff-layout-control"]) &&
      toolbar.layoutChips.join(" ") === "Split Unified",
    JSON.stringify({ holds: toolbar.holds, chips: toolbar.layoutChips }),
  );
  check(
    `${at}: the two choosers share one line`,
    near(toolbar.show.top, toolbar.layout.top) && near(toolbar.show.bottom, toolbar.layout.bottom),
    JSON.stringify([toolbar.show, toolbar.layout]),
  );
  check(
    `${at}: Diff | Current comes before Split | Unified, which ends the toolbar's content box`,
    toolbar.show.right <= toolbar.layout.left + TOLERANCE_PX &&
      near(toolbar.layout.right, toolbar.content.right),
    JSON.stringify({ show: toolbar.show, layout: toolbar.layout, content: toolbar.content }),
  );
}

/** The file bars' checks for one surface at one width: each end group holds no Diff | Current. */
function barChecks(surface, measured, width) {
  const [markdown, code] = measured.bars;
  const at = `${surface}, ${width} px`;
  check(`${at}: two bars`, measured.bars.length === 2, `${measured.bars.length}`);
  check(
    `${at}: the Markdown bar's end group holds Rendered | Source alone`,
    JSON.stringify(markdown.holds) === JSON.stringify(["diff-markdown-control"]) &&
      markdown.chips.join(" ") === "Rendered Source",
    JSON.stringify({ holds: markdown.holds, chips: markdown.chips }),
  );
  check(
    `${at}: Rendered | Source ends the bar, at its content box's end`,
    near(markdown.format.right, markdown.end.right) && near(markdown.end.right, markdown.right),
    JSON.stringify({ format: markdown.format, end: markdown.end, right: markdown.right }),
  );
  check(
    `${at}: a code file's bar end holds nothing`,
    code.holds.length === 0 && code.chips.length === 0 && code.format === null,
    JSON.stringify({ holds: code.holds, chips: code.chips }),
  );
}

/** @type {Awaited<ReturnType<typeof launchChrome>> | null} */
let chrome = null;
const server = /** @type {http.Server} */ (await serve());
const { port } = /** @type {import("node:net").AddressInfo} */ (server.address());
/**
 * A screenshot of the host *hostId*, its toolbar and files.
 * @param {string} hostId
 * @param {string} name
 */
const shot = async (hostId, name) => {
  if (!SHOTS || !chrome) {
    return;
  }
  // In view first: what the diff draws as it comes into view is drawn before the capture.
  const clip = await chrome.evaluate(`(async () => {
    const host = document.getElementById(${JSON.stringify(hostId)});
    host.scrollIntoView();
    for (let frame = 0; frame < 3; frame += 1) {
      await new Promise((resolve) => requestAnimationFrame(resolve));
    }
    const rect = host.getBoundingClientRect();
    return { x: rect.left, y: rect.top + scrollY, width: rect.width, height: rect.height, scale: 1 };
  })()`);
  const { data } = await chrome.send("Page.captureScreenshot", {
    format: "png",
    clip,
    captureBeyondViewport: true,
  });
  fs.mkdirSync(SHOTS, { recursive: true });
  fs.writeFileSync(path.join(SHOTS, `${name}.png`), Buffer.from(data, "base64"));
};
/**
 * Mount *options* in *hostId*.
 * @param {string} hostId
 * @param {Record<string, unknown>} options
 */
const mount = (hostId, options) =>
  chrome?.evaluate(
    `(${MOUNT})(${JSON.stringify(hostId)}, ${JSON.stringify(options)}, ${JSON.stringify(COMPARISON)}, ${JSON.stringify(recorded.answers.f1)}, ${JSON.stringify(recorded.image_route)})`,
  );
/**
 * @param {string} hostId
 * @param {number} width
 */
const measure = (hostId, width) =>
  chrome?.evaluate(`(${MEASURE})(${JSON.stringify(hostId)}, ${width})`);
/**
 * @param {string} hostId
 * @param {string} where
 * @param {string} value
 */
const click = (hostId, where, value) =>
  chrome?.evaluate(
    `(${CLICK})(${JSON.stringify(hostId)}, ${JSON.stringify(where)}, ${JSON.stringify(value)})`,
  );
// Choosing keeps every chooser where it was. Only the chosen chip's word changes, to the
// medium weight a selected chip takes ("Choosing Among Values"), so a chooser's width moves
// by that word's, measured at 0.28 to 0.31 px in Chrome, and the chooser before it moves by
// as much; a pixel bounds it. A bar below the Markdown file moves with the rows Current
// hides above it, and a screenshot scrolls the page, so each chooser's top is read against
// its own toolbar's or bar's.
const stays = (label, before, after) => {
  const pairs = [
    [
      after.toolbar?.show,
      before.toolbar?.show,
      after.toolbar?.content.top,
      before.toolbar?.content.top,
    ],
    [
      after.toolbar?.layout,
      before.toolbar?.layout,
      after.toolbar?.content.top,
      before.toolbar?.content.top,
    ],
    ...after.bars.map((bar, index) => [
      bar.format,
      before.bars[index].format,
      bar.top,
      before.bars[index].top,
    ]),
  ];
  const moved = pairs.flatMap(([now, was, nowTop, wasTop]) =>
    now == null && was == null
      ? []
      : [
          now.top - nowTop - (was.top - wasTop),
          now.bottom - nowTop - (was.bottom - wasTop),
          now.left - was.left,
          now.right - was.right,
        ],
  );
  check(
    label,
    moved.every((delta) => Math.abs(delta) < 1),
    JSON.stringify(moved),
  );
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
  const changesShows = await mount("changes", {});
  check(
    "Changes opens on Diff, its Rendered view drawn",
    changesShows === "diff",
    `${changesShows}`,
  );
  const docsShows = await mount("docs", DOCS);
  check("Docs opens on Current, its Rendered view drawn", docsShows === "current", `${docsShows}`);
  await chrome.evaluate("document.fonts.ready.then(() => true)");

  for (const width of [900, 380]) {
    for (const [surface, hostId] of [
      ["Changes", "changes"],
      ["Docs", "docs"],
    ]) {
      const measured = await measure(hostId, width);
      toolbarChecks(surface, measured, width);
      barChecks(surface, measured, width);
    }
    if (width === 380) {
      await shot("changes", "narrow-changes-diff");
      await shot("docs", "narrow-docs-current");
    }
  }
  await measure("docs", 900);
  const before = await measure("changes", 900);
  await shot("changes", "changes-diff");
  await shot("docs", "docs-current");

  const shown = await click("changes", ".diff-toolbar .diff-show-control", "current");
  check("Current is chosen on Changes", shown === "current", `${shown}`);
  const current = await measure("changes", 900);
  toolbarChecks("Changes", current, 900);
  barChecks("Changes", current, 900);
  stays("choosing Current on Changes moves no chooser", before, current);
  await shot("changes", "changes-current");
  await click("changes", ".diff-file-end", "source");
  const source = await measure("changes", 900);
  barChecks("Changes", source, 900);
  stays("choosing Source moves no chooser", current, source);
  const docsAfter = await measure("docs", 900);
  check("Changes' choice leaves Docs in Current", docsAfter.shows === "current", docsAfter.shows);

  const docsBefore = docsAfter;
  const docsShown = await click("docs", ".diff-toolbar .diff-show-control", "diff");
  check("Diff is chosen on Docs", docsShown === "diff", `${docsShown}`);
  const docsDiff = await measure("docs", 900);
  toolbarChecks("Docs", docsDiff, 900);
  stays("choosing Diff on Docs moves no chooser", docsBefore, docsDiff);
  await shot("docs", "docs-diff");
  const writes = await chrome.evaluate("window.writes");
  check(
    "each surface writes its own preference",
    JSON.stringify(writes) ===
      JSON.stringify({ changes: ["diff.show=current"], docs: ["github.docs.show=diff"] }),
    JSON.stringify(writes),
  );
} finally {
  await chrome?.close();
  server.close();
}
if (failures.length > 0) {
  process.stderr.write(`${failures.join("\n")}\n`);
  process.exit(1);
}
process.stdout.write(`diff current in Chrome: ${checks} checks passed\n`);

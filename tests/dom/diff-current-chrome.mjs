// A diff's toolbar and its file bars' end groups, laid out by headless Chrome, and the place a
// presentation change keeps: the production `mountDiffView` (builtin_plugins/diff/diff-view.js),
// with diff-markdown.js's views, the shell's brief change line (static/formatters.js), its own
// chip family (static/filter-controls.js), and
// the production File type control (diff-type-filter.js), under the shell's, the diff plugin's,
// and KPress's stylesheets.
//
//   CHROME_BIN=/path/to/chrome CHROME_PROFILES=/dir/the/caller/removes \
//     KPRESS_STATIC=/dir/with/kpress/css/and/fonts CURRENT_INPUT=/path/to/input.json \
//     [CURRENT_SHOTS=/dir/for/screenshots] node tests/dom/diff-current-chrome.mjs
//
// tests/test_diff_current_chrome.py writes CURRENT_INPUT ({sheets, presets}: KPress's sheets and
// the File type menu's presets, FILTER_TYPE_PRESETS), copies KPress's stylesheets and faces out
// of the installed package, owns the profile, and runs this in a process group of its own.
// CURRENT_SHOTS, when set, receives screenshots: Changes with a File type chosen at 900 and
// 380 px, Changes in Diff and in Excerpt, Changes narrow, and Docs in Full and in Diff.
//
// What it measures is layout, which no browserless DOM computes (docs/design-system.md,
// "Diff Toolbar" and "Diff File Bar"), on one page. A comparison of a Markdown file and a code
// file is mounted three times: as a pull request's Changes mounts it, its File type control in
// the toolbar, painted in each state the filter paints; as a diff with no File type control
// mounts it, as Changes does a one-file comparison and a commit's page a one-file commit; and
// as Docs does, with the layout fixed, Full its default, and a preference of its own
// (github/pull-page.js). At each width from 1,063 to 320 px nothing in the toolbar runs past
// it or scrolls sideways. The presentation and layout controls share one line in that order,
// right-aligned at its content end, on the File type control's line or, where they do not fit
// there, on the next. Docs shows only the presentation control. A Markdown file bar ends
// with Rendered | Source. Choosing Excerpt or Source moves no chooser. The Markdown file's answer is the server's
// projection recorded in tests/fixtures/diff-markdown-responses.json.
//
// On a second page, a 600 px pane marked `data-kpress-viewport`, as a pull request's is, holds
// one long file, a code file or a rendered Markdown document of 200 groups of a context, a
// removed and an added line or block, and the reader's place is read before and after each
// choice: the row at the pane's top keeps its offset, Diff to Excerpt and back, in Unified,
// in Split, rendered on Changes and on Docs, and a removed row at the top gives its place to
// the first row after it that Excerpt draws.
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
/** The widths the toolbar is measured at: a wide pane, 900 px, a narrow one, and the narrowest. */
const WIDTHS = [1063, 900, 600, 380, 320];
const failures = [];
/** What each toolbar measured, written beside the screenshots for a reader. */
const table = [];
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
const resolved = {
  base_policy: "direct",
  comparison_id: "chrome:current",
  kind: "content",
  left: { kind: "patch" },
  options: { context: 3, rename_detection: true, rename_similarity: 50 },
  right: { kind: "patch" },
  source: { name: "chrome" },
};
/** The mount options a pull request's Docs tab passes (github/pull-page.js). */
const DOCS = {
  unfold: true,
  layout: "unified",
  show: "full",
  showPreference: "github.docs.show",
};
/** A Markdown file with a format chooser and a code file without one. */
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
  resolved,
  schema: "file-diff-v1",
  schema_version: 1,
};

// The counts the File type menu lists, as the route's `view=types` answers them.
const TALLY = {
  extensions: [
    [".py", 30, 0],
    [".md", 12, 0],
    [".js", 6, 0],
  ],
  type_presets: [
    ["docs", 12, 0],
    ["code", 36, 0],
  ],
};
const DOCS_TYPES = INPUT.presets.find((preset) => preset.id === "docs").values;
/** What the File type control paints (diff-type-filter.js's TypeFilterState), by name. */
const TYPE_STATES = {
  "any type": { types: null, tally: TALLY, loading: false, failed: false, kept: null, whole: 48 },
  ".md, 12 of 48 files": {
    types: [".md"],
    tally: TALLY,
    loading: false,
    failed: false,
    kept: 12,
    whole: 48,
  },
  "Documentation, 12 of 48 files": {
    types: DOCS_TYPES,
    tally: TALLY,
    loading: false,
    failed: false,
    kept: 12,
    whole: 48,
  },
  ".md and .py, 1,234 of 5,678 files": {
    types: [".md", ".py"],
    tally: TALLY,
    loading: false,
    failed: false,
    kept: 1234,
    whole: 5678,
  },
  ".md, its files failed to load": {
    types: [".md"],
    tally: TALLY,
    loading: false,
    failed: true,
    kept: null,
    whole: 48,
  },
};

// The shell's tokens and sheet, then the diff plugin's, then KPress's document sheets; the
// File type menu's presets, as the shell's settings carry them; the shell's icons, its SDK's
// chip family, and the inert-HTML runtime the Markdown views use.
const head = (title) => `<!doctype html><html><head><meta charset="utf-8"><title>${title}</title>
<link rel="stylesheet" href="/kpress/css/style-tokens.css">
<link rel="stylesheet" href="/static/styles.css">
<link rel="stylesheet" href="/diff/styles.css">
${INPUT.sheets.map((sheet) => `<link rel="stylesheet" href="/kpress/${sheet}">`).join("\n")}
<script>window.METABROWSER_SETTINGS = { FILTER_TYPE_PRESETS: ${JSON.stringify(INPUT.presets)} };</script>
<script src="/static/icons.js"></script>
<script src="/static/formatters.js"></script>
<script>window.metabrowser = { icons: window.MetabrowserIcons };</script>
<script src="/static/filter-controls.js"></script>
<script src="/static/inert-html.js"></script>
<script type="module">
import { mountDiffView } from "/diff/diff-view.js";
import * as markdownViews from "/diff/diff-markdown.js";
import { createTypeFilterControl } from "/diff/diff-type-filter.js";
window.diffCurrent = { mountDiffView, markdownViews, createTypeFilterControl };
</script>
</head>`;
const PAGE = `${head("diff current")}<body><div id="preview-pane" class="preview-pane">
<div id="changes" class="metabrowser-diff-host" style="width: 900px"></div>
<div id="bare" class="metabrowser-diff-host" style="width: 900px; margin-top: 24px"></div>
<div id="docs" class="metabrowser-diff-host" style="width: 900px; margin-top: 24px"></div>
</div></body></html>`;
// The pane a pull request's diff scrolls in: `data-kpress-viewport`, which the diff holds its
// place in.
const PLACE_PAGE = `${head("diff current place")}<body style="margin: 0">
<div id="preview-pane" class="preview-pane" data-kpress-viewport
  style="display: block; height: 600px; width: 900px; overflow-y: auto">
<div id="long" class="metabrowser-diff-host"></div>
</div></body></html>`;

const TYPES = { ".css": "text/css", ".js": "text/javascript", ".woff2": "font/woff2" };
function serve() {
  const server = http.createServer((request, response) => {
    const url = new URL(request.url ?? "/", "http://localhost");
    let file = null;
    if (url.pathname === "/" || url.pathname === "/place") {
      response.writeHead(200, { "content-type": "text/html" });
      response.end(url.pathname === "/" ? PAGE : PLACE_PAGE);
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

// In the page: mount *comparison* in the host *hostId* with the host's *options*, the shell's
// chip family, a preference store of its own (*stored* first), and *answer* for every rendered
// file. With a *typeState*, the toolbar holds the production File type control painted in it,
// as Changes mounts one (diff/index.js, `mountTypeFiltered`), kept as `window.typeControls`
// for a repaint. Resolves once the diff draws its rows, and its rendered view where it has one.
const MOUNT = `async (hostId, options, comparison, answer, imageRoute, typeState, stored) => {
  const { mountDiffView, markdownViews, createTypeFilterControl } = window.diffCurrent;
  const host = document.getElementById(hostId);
  const prefs = new Map([["diff.layout", "unified"], ...Object.entries(stored)]);
  const writes = [];
  const fc = window.metabrowser.filterControls;
  const formatters = window.MetabrowserFormatters;
  const api = {
    // A file's lines are said by the shell's brief change line, as the SDK hands it.
    countPartsNodes: (parts) => formatters.countPartsNodes(document, parts),
    changeLine: (change) => formatters.changeLine(change, formatters.formatInteger),
    changeLineNodes: (line, options) => formatters.changeLineNodes(document, line, options),
    highlightSyntax: async () => null,
    isLargeTextPreview: () => true,
    langForPath: () => "",
    ensureAsset: async () => {},
    loadKpressAssets: async () => {},
    prefs: {
      get: (key, fallback) => (prefs.has(key) ? prefs.get(key) : fallback),
      set: (key, value) => (prefs.set(key, value), writes.push(key + "=" + value), true),
    },
    filterControls: fc,
  };
  (window.writes ??= {})[hostId] = writes;
  let toolbarControl = null;
  if (typeState !== null) {
    toolbarControl = document.createElement("div");
    const control = createTypeFilterControl(toolbarControl, fc, {
      select: () => {},
      formatInteger: (value) => value.toLocaleString("en-US"),
    });
    control.paint(typeState);
    (window.typeControls ??= {})[hostId] = control;
  }
  mountDiffView(host, { ...comparison, __revision: "fixture" }, api, {
    showSummary: false,
    markdownViews,
    renderMarkdown: async () => structuredClone(answer),
    markdownTargets: markdownViews.markdownTargets(imageRoute, () => true),
    markdownHoldMs: 0,
    ...(toolbarControl === null ? {} : { toolbarControl }),
    ...options,
  });
  // A rendered file is asked for as it nears the screen, so the host is brought into view.
  host.scrollIntoView();
  const markdown = comparison.manifest.files.some((file) => file.new.path.endsWith(".md"));
  for (let frame = 0; frame < 240; frame += 1) {
    const rendered = host.querySelector(".diff-markdown");
    const drawn = markdown
      ? rendered && !rendered.hidden && rendered.querySelector(".diff-markdown-block")
      : host.querySelector(".diff-line");
    if (drawn) {
      for (let settle = 0; settle < 3; settle += 1) {
        await new Promise((resolve) => requestAnimationFrame(resolve));
      }
      return host.querySelector(".diff-root")?.dataset.show ?? null;
    }
    await new Promise((resolve) => requestAnimationFrame(resolve));
  }
  return false;
}`;

// The boxes of the host *hostId* at the width *width*: its toolbar's content box, what it
// holds, its File type control, its choosers' group and each chooser, whether anything scrolls
// sideways, and each bar's content box, its two groups, and what its end group holds, in the
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
  const end = toolbar?.querySelector(".diff-toolbar-end") ?? null;
  const diffRoot = host.querySelector(".diff-root");
  // Every box the toolbar draws, so a control past its content box is named.
  const drawn = toolbar
    ? [...toolbar.querySelectorAll("*")]
        .filter((node) => node.getClientRects().length > 0 && !node.closest("[data-chip-menu]"))
        .map((node) => ({ name: node.className || node.tagName, ...box(node) }))
    : [];
  return {
    shows: diffRoot?.dataset.show ?? null,
    toolbar: toolbar && {
      content: content(toolbar),
      height: toolbar.getBoundingClientRect().height,
      holds: [...toolbar.children].map((child) => child.className),
      endHolds: end ? [...end.children].map((child) => child.className) : [],
      type: box(toolbar.querySelector(".diff-type-control")),
      end: box(end),
      show: box(toolbar.querySelector(".diff-show-control")),
      layout: box(toolbar.querySelector(".diff-layout-control")),
      showChips: chips(toolbar.querySelector(".diff-show-control")),
      layoutChips: chips(toolbar.querySelector(".diff-layout-control")),
      scrolls: toolbar.scrollWidth > toolbar.clientWidth,
      rootScrolls: diffRoot.scrollWidth > diffRoot.clientWidth,
      drawn,
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

/** Paint the File type control of the host *hostId* in *state*, as the filter does. */
const PAINT = `async (hostId, state) => {
  window.typeControls[hostId].paint(state);
  for (let frame = 0; frame < 2; frame += 1) {
    await new Promise((resolve) => requestAnimationFrame(resolve));
  }
  return true;
}`;

/**
 * The toolbar's checks for one surface at one width: what it holds, and that nothing runs past
 * it, the choosers together at its right end.
 * @param {"Changes" | "No File type" | "Docs"} surface
 * @param {string} at Where, for the labels.
 */
function toolbarChecks(surface, measured, at) {
  const { toolbar } = measured;
  check(`${at}: a toolbar is drawn`, toolbar !== null);
  if (toolbar === null) {
    return;
  }
  const past = Math.max(
    0,
    ...toolbar.drawn.map((node) =>
      Math.max(node.right - toolbar.content.right, toolbar.content.left - node.left),
    ),
  );
  table.push({
    at,
    height: toolbar.height,
    scrolls: toolbar.scrolls || toolbar.rootScrolls,
    past,
    choosersOwnLine:
      toolbar.type === null ? null : toolbar.end.top >= toolbar.type.bottom - TOLERANCE_PX,
  });
  check(
    `${at}: the toolbar offers Diff, Excerpt, and Full`,
    toolbar.showChips.join(" ") === "Diff Excerpt Full",
    toolbar.showChips.join(" "),
  );
  check(
    `${at}: nothing in the toolbar or the diff scrolls sideways`,
    toolbar.scrolls === false && toolbar.rootScrolls === false,
    JSON.stringify({ toolbar: toolbar.scrolls, root: toolbar.rootScrolls }),
  );
  const outside = toolbar.drawn.filter(
    (node) =>
      node.left < toolbar.content.left - TOLERANCE_PX ||
      node.right > toolbar.content.right + TOLERANCE_PX,
  );
  check(
    `${at}: everything the toolbar draws is inside its content box`,
    outside.length === 0,
    JSON.stringify({ outside, content: toolbar.content }),
  );
  check(
    `${at}: the choosers' group ends the toolbar's content box`,
    toolbar.end !== null && near(toolbar.end.right, toolbar.content.right),
    JSON.stringify({ end: toolbar.end, content: toolbar.content }),
  );
  const holds =
    surface === "Changes" ? ["diff-type-control", "diff-toolbar-end"] : ["diff-toolbar-end"];
  check(
    `${at}: the toolbar holds ${holds.join(", then ")}`,
    JSON.stringify(toolbar.holds) === JSON.stringify(holds),
    JSON.stringify(toolbar.holds),
  );
  if (surface === "Docs") {
    check(
      `${at}: the toolbar holds only the presentation chooser`,
      JSON.stringify(toolbar.endHolds) === JSON.stringify(["diff-show-control"]) &&
        toolbar.layout === null &&
        near(toolbar.show.right, toolbar.content.right),
      JSON.stringify({ holds: toolbar.endHolds, show: toolbar.show, content: toolbar.content }),
    );
    return;
  }
  check(
    `${at}: the toolbar holds presentation, then Split | Unified`,
    JSON.stringify(toolbar.endHolds) ===
      JSON.stringify(["diff-show-control", "diff-layout-control"]) &&
      toolbar.layoutChips.join(" ") === "Split Unified",
    JSON.stringify({ holds: toolbar.endHolds, chips: toolbar.layoutChips }),
  );
  check(
    `${at}: the two choosers share one line`,
    near(toolbar.show.top, toolbar.layout.top) && near(toolbar.show.bottom, toolbar.layout.bottom),
    JSON.stringify([toolbar.show, toolbar.layout]),
  );
  check(
    `${at}: presentation comes before Split | Unified, which ends the toolbar's content box`,
    toolbar.show.right <= toolbar.layout.left + TOLERANCE_PX &&
      near(toolbar.layout.right, toolbar.content.right),
    JSON.stringify({ show: toolbar.show, layout: toolbar.layout, content: toolbar.content }),
  );
  if (surface === "Changes") {
    const shared = toolbar.end.top < toolbar.type.bottom - TOLERANCE_PX;
    check(
      `${at}: the choosers share the File type control's line after it, or take the next line`,
      shared
        ? toolbar.type.right <= toolbar.end.left + TOLERANCE_PX
        : toolbar.end.top >= toolbar.type.bottom - TOLERANCE_PX,
      JSON.stringify({ type: toolbar.type, end: toolbar.end }),
    );
  }
}

/** Check where the format selector lands at each width. */
function barChecks(measured, at) {
  const [markdown, code] = measured.bars;
  check(`${at}: two bars`, measured.bars.length === 2, `${measured.bars.length}`);
  check(
    `${at}: the Markdown bar's end group holds only Rendered | Source`,
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

// ── The long file, for the place a choice keeps ─────────────────────

const GROUPS = 200;
const longFile = (filePath) => {
  const lines = [];
  for (let index = 0; index < GROUPS; index += 1) {
    lines.push(["context", `context line ${index}`], ["del", `old line ${index}`]);
    lines.push(["add", `new line ${index}`]);
  }
  return {
    manifest: {
      cursor: null,
      files: [
        {
          additions: GROUPS,
          availability: "ready",
          binary: false,
          deletions: GROUPS,
          id: "f1",
          kind: "modified",
          new: side(filePath),
          old: side(filePath),
        },
      ],
      totals: { additions: GROUPS, deletions: GROUPS, exact: true, files: 1 },
      truncated: false,
    },
    patches: {
      f1: {
        file_id: "f1",
        hunks: [hunk(1, 2 * GROUPS, 1, 2 * GROUPS, lines)],
        truncated: false,
      },
    },
    resolved,
    schema: "file-diff-v1",
    schema_version: 1,
  };
};
const LONG_CODE = longFile("long.py");
const LONG_MARKDOWN = longFile("long.md");
const blocks = [];
for (let index = 0; index < GROUPS; index += 1) {
  blocks.push({ kind: "context", html: `<p>Context paragraph ${index}.</p>`, source_only: false });
  blocks.push({
    kind: "removed",
    html: `<p>Old paragraph <del>${index}</del>.</p>`,
    source_only: false,
  });
  blocks.push({
    kind: "added",
    html: `<p>New paragraph <ins>${index}</ins>.</p>`,
    source_only: false,
  });
}
// As the route answers it on Changes (Concise) and on Docs (Concise too, past
// FULL_MAX_BLOCKS in metabrowser.diff.markdown_views): no run of unchanged blocks folds.
const LONG_ANSWER = {
  version: "markdown-diff-v1",
  status: "ready",
  blocks,
  source_only: false,
  view: "concise",
  count: blocks.length,
  folds: [],
};
// A document whose one fold holds a long run of unchanged blocks, sent with the answer:
// Concise draws it whole, a bar between three changed blocks on each side, and the fold
// draws its run a chunk at a time when it opens, past WHOLE_UNITS in diff-markdown.js.
const FOLDED_RUN = 600;
const foldedBlocks = [];
for (const [kind, label] of [
  ["removed", "Old opening"],
  ["added", "New opening"],
  ["added", "Added opening"],
]) {
  foldedBlocks.push({ kind, html: `<p>${label}.</p>`, source_only: false });
}
for (let index = 0; index < FOLDED_RUN; index += 1) {
  foldedBlocks.push({
    kind: "context",
    html: `<p>Unchanged paragraph ${index}.</p>`,
    source_only: false,
  });
}
for (const [kind, label] of [
  ["removed", "Old closing"],
  ["added", "New closing"],
  ["added", "Added closing"],
]) {
  foldedBlocks.push({ kind, html: `<p>${label}.</p>`, source_only: false });
}
const FOLDED_ANSWER = {
  ...LONG_ANSWER,
  blocks: foldedBlocks,
  count: foldedBlocks.length,
  folds: [{ at: 3, count: FOLDED_RUN, lines: 2 * FOLDED_RUN }],
};

// What is at the pane's top: the first drawn code row or rendered block whose box ends below it,
// its text (a row's, each side's in Split), and its offset from the pane's top.
const ROWS = `(() => {
  const shown = (node) => node.getClientRects().length > 0;
  return [...document.querySelectorAll(
    "#long .diff-file-body:not([hidden]) .diff-line, #long .diff-file-body:not([hidden]) .diff-split-row, #long .diff-markdown:not([hidden]) .diff-markdown-block"
  )].filter(shown);
})()`;
const TEXT_OF = `(row) => {
  const sides = [...row.querySelectorAll(".diff-line-text")].map((node) => node.textContent);
  return sides.length > 0 ? sides.join(" / ") : row.textContent.replace(/\\s+/g, " ").trim();
}`;
const AT_TOP = `(() => {
  const pane = document.getElementById("preview-pane");
  const paneTop = pane.getBoundingClientRect().top;
  const first = ${ROWS}.find((row) => row.getBoundingClientRect().bottom > paneTop + 1);
  return first
    ? {
        text: (${TEXT_OF})(first),
        offset: first.getBoundingClientRect().top - paneTop,
        shows: document.querySelector("#long .diff-root").dataset.show,
        layout: document.querySelector("#long .diff-root").dataset.layout,
        scrollTop: pane.scrollTop,
      }
    : null;
})()`;
/**
 * The pane scrolled so the first row that reads *needle* is at its top. A rendered
 * document draws a chunk of blocks as the reader comes near it, so the pane is scrolled a
 * screen at a time, as a reader would, until that row is drawn.
 */
const SCROLL_TO = `async (needle) => {
  const pane = document.getElementById("preview-pane");
  const find = () => ${ROWS}.find((candidate) => (${TEXT_OF})(candidate).includes(needle));
  let row = find();
  for (let step = 0; step < 200 && row === undefined; step += 1) {
    pane.scrollTop += pane.clientHeight;
    for (let frame = 0; frame < 3; frame += 1) {
      await new Promise((resolve) => requestAnimationFrame(resolve));
    }
    row = find();
  }
  pane.scrollTop += row.getBoundingClientRect().top - pane.getBoundingClientRect().top;
  for (let frame = 0; frame < 3; frame += 1) {
    await new Promise((resolve) => requestAnimationFrame(resolve));
  }
  return true;
}`;
/** Where the first row that reads *needle* is, from the pane's top. */
const OFFSET_OF = `(needle) => {
  const pane = document.getElementById("preview-pane");
  const row = ${ROWS}.find((candidate) => (${TEXT_OF})(candidate).includes(needle));
  return row ? row.getBoundingClientRect().top - pane.getBoundingClientRect().top : null;
}`;

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
 * Mount *comparison* in *hostId* with *options*, a File type control in *typeState* or none,
 * and *stored* preferences.
 */
const mount = (
  hostId,
  options,
  {
    comparison = COMPARISON,
    answer = recorded.answers.f1["view=concise"],
    typeState = null,
    stored = {},
  } = {},
) =>
  chrome?.evaluate(
    `(${MOUNT})(${JSON.stringify(hostId)}, ${JSON.stringify(options)}, ${JSON.stringify(comparison)}, ${JSON.stringify(answer)}, ${JSON.stringify(recorded.image_route)}, ${JSON.stringify(typeState)}, ${JSON.stringify(stored)})`,
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
/** @param {string} hostId @param {Record<string, unknown>} state */
const paint = (hostId, state) =>
  chrome?.evaluate(`(${PAINT})(${JSON.stringify(hostId)}, ${JSON.stringify(state)})`);
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
/**
 * A row's offset is its place: kept to a pixel, which a font's rounding stays inside. The row
 * reads *needle* before and after; in Split it reads it on both sides.
 */
const samePlace = (label, needle, before, after) =>
  check(
    label,
    before != null &&
      after != null &&
      before.text.includes(needle) &&
      after.text.includes(needle) &&
      Math.abs(before.offset - after.offset) <= 1,
    JSON.stringify({ before, after }),
  );
const started = performance.now();
let launched = started;
try {
  chrome = await launchChrome(/** @type {string} */ (process.env.CHROME_BIN), {
    profiles: /** @type {string} */ (process.env.CHROME_PROFILES),
    width: 1200,
    height: 1400,
  });
  launched = performance.now();
  await chrome.send("Page.enable");
  await chrome.send("Page.navigate", { url: `http://127.0.0.1:${port}/` });
  await chrome.waitFor(
    "document.readyState === 'complete' && !!window.MetabrowserInertHtml && !!window.diffCurrent && !!window.metabrowser.filterControls",
  );
  const changesShows = await mount("changes", {}, { typeState: TYPE_STATES["any type"] });
  check(
    "Changes opens on Diff, its rendered view drawn",
    changesShows === "diff",
    `${changesShows}`,
  );
  const bareShows = await mount("bare", {});
  check("a diff with no File type control opens on Diff", bareShows === "diff", `${bareShows}`);
  const docsShows = await mount("docs", DOCS);
  check("Docs opens on Full, its rendered view drawn", docsShows === "full", `${docsShows}`);
  await chrome.evaluate("document.fonts.ready.then(() => true)");

  // Every state the File type control paints, at every width, and the toolbars beside it.
  for (const [name, state] of Object.entries(TYPE_STATES)) {
    await paint("changes", state);
    for (const width of WIDTHS) {
      const measured = await measure("changes", width);
      toolbarChecks("Changes", measured, `Changes, File type ${name}, ${width} px`);
    }
    if (name === ".md, 12 of 48 files") {
      await measure("changes", 900);
      await shot("changes", "changes-type-900");
      await measure("changes", 380);
      await shot("changes", "changes-type-380");
    }
  }
  await paint("changes", TYPE_STATES["any type"]);
  for (const width of WIDTHS) {
    for (const [surface, hostId] of /** @type {const} */ ([
      ["Changes", "changes"],
      ["No File type", "bare"],
      ["Docs", "docs"],
    ])) {
      const measured = await measure(hostId, width);
      toolbarChecks(surface, measured, `${surface}, ${width} px`);
      barChecks(measured, `${surface}, ${width} px`);
    }
    if (width === 380) {
      await shot("changes", "narrow-changes-diff");
      await shot("docs", "narrow-docs-current");
    }
  }
  await measure("docs", 900);
  await measure("bare", 900);
  const before = await measure("changes", 900);
  await shot("changes", "changes-diff");
  await shot("docs", "docs-current");

  const shown = await click("changes", ".diff-toolbar .diff-show-control", "current");
  check("Current is chosen on Changes", shown === "current", `${shown}`);
  const current = await measure("changes", 900);
  toolbarChecks("Changes", current, "Changes in Current, 900 px");
  barChecks(current, "Changes in Current, 900 px");
  stays("choosing Current on Changes moves no chooser", before, current);
  await shot("changes", "changes-current");
  await click("changes", ".diff-file-end", "source");
  const source = await measure("changes", 900);
  barChecks(source, "Changes in Source, 900 px");
  stays("choosing Source moves no chooser", current, source);
  const docsAfter = await measure("docs", 900);
  check("Changes' choice leaves Docs in Current", docsAfter.shows === "full", docsAfter.shows);

  const docsBefore = docsAfter;
  const docsShown = await click("docs", ".diff-toolbar .diff-show-control", "diff");
  check("Diff is chosen on Docs", docsShown === "diff", `${docsShown}`);
  const docsDiff = await measure("docs", 900);
  toolbarChecks("Docs", docsDiff, "Docs in Diff, 900 px");
  stays("choosing Diff on Docs moves no chooser", docsBefore, docsDiff);
  await shot("docs", "docs-diff");
  const writes = await chrome.evaluate("window.writes");
  check(
    "each surface writes its own preference",
    JSON.stringify(writes) ===
      JSON.stringify({ changes: ["diff.show=excerpt"], bare: [], docs: ["github.docs.show=diff"] }),
    JSON.stringify(writes),
  );

  // The place each choice keeps, in a long file, on a page of its own for each mount.
  const fresh = async () => {
    await chrome?.send("Page.navigate", { url: `http://127.0.0.1:${port}/place` });
    await chrome?.waitFor(
      "document.readyState === 'complete' && !!window.MetabrowserInertHtml && !!window.diffCurrent && !!window.metabrowser.filterControls",
    );
  };
  const atTop = () => chrome?.evaluate(AT_TOP);
  const scrollTo = (needle) => chrome?.evaluate(`(${SCROLL_TO})(${JSON.stringify(needle)})`);
  const offsetOf = (needle) => chrome?.evaluate(`(${OFFSET_OF})(${JSON.stringify(needle)})`);
  /**
   * A round trip from where *needle* is at the pane's top: the row there keeps its offset at
   * each choice.
   */
  const roundTrip = async (label, needle, there, back) => {
    await scrollTo(needle);
    const start = await atTop();
    check(
      `${label}: the pane's top reads ${needle}`,
      start?.text.includes(needle),
      JSON.stringify(start),
    );
    await click("long", ".diff-toolbar .diff-show-control", there);
    samePlace(
      `${label}: choosing ${there} keeps the row at the pane's top`,
      needle,
      start,
      await atTop(),
    );
    await click("long", ".diff-toolbar .diff-show-control", back);
    samePlace(`${label}: choosing ${back} again returns to it`, needle, start, await atTop());
  };

  await fresh();
  await mount("long", {}, { comparison: LONG_CODE, answer: null });
  await roundTrip("a long code file in Unified", "context line 150", "current", "diff");

  await fresh();
  await mount(
    "long",
    {},
    { comparison: LONG_CODE, answer: null, stored: { "diff.layout": "split" } },
  );
  const split = await atTop();
  check("the long code file draws Split", split?.layout === "split", JSON.stringify(split));
  await roundTrip("a long code file in Split", "context line 150", "current", "diff");

  await fresh();
  await mount("long", {}, { comparison: LONG_CODE, answer: null });
  await scrollTo("old line 150");
  const removedTop = await atTop();
  const nextBefore = await offsetOf("new line 150");
  await click("long", ".diff-toolbar .diff-show-control", "current");
  const nextAfter = await offsetOf("new line 150");
  check(
    "a removed line at the pane's top gives its place to the next line Current draws",
    removedTop?.text === "old line 150" &&
      nextBefore !== null &&
      nextAfter !== null &&
      Math.abs(nextBefore - nextAfter) < 1,
    JSON.stringify({ removedTop, nextBefore, nextAfter, now: await atTop() }),
  );

  await fresh();
  await mount("long", DOCS, { comparison: LONG_MARKDOWN, answer: LONG_ANSWER });
  await roundTrip("a long document on Docs, Concise", "Context paragraph 150.", "diff", "current");

  // A view chosen deep in a long document draws its chunk there first, so the block at the
  // pane's top keeps its place, not the first block of its chunk.
  /** A round trip through the file's views from where *needle* is at the pane's top. */
  const viewTrip = async (label, needle) => {
    await scrollTo(needle);
    const start = await atTop();
    check(
      `${label}: the pane's top reads ${needle}`,
      start?.text.includes(needle),
      JSON.stringify(start),
    );
    await click("long", ".diff-toolbar .diff-show-control", "full");
    samePlace(
      `${label}: choosing Full keeps the block at the pane's top`,
      needle,
      start,
      await atTop(),
    );
    await click("long", ".diff-toolbar .diff-show-control", "diff");
    samePlace(`${label}: choosing Diff again returns to it`, needle, start, await atTop());
  };
  await fresh();
  await mount("long", {}, { comparison: LONG_MARKDOWN, answer: LONG_ANSWER });
  await viewTrip("a long document's views", "Context paragraph 150.");

  // Inside an open fold, the block at the pane's top is the place, not the fold: it keeps
  // it as the views are drawn anew, and as the fold's chunks above it are drawn (A2).
  await fresh();
  await mount("long", {}, { comparison: LONG_MARKDOWN, answer: FOLDED_ANSWER });
  await chrome?.evaluate(`(async () => {
    document.querySelector("#long article.diff-markdown .fold-expander").click();
    for (let frame = 0; frame < 3; frame += 1) {
      await new Promise((resolve) => requestAnimationFrame(resolve));
    }
    return true;
  })()`);
  await viewTrip("an open fold's views", "Unchanged paragraph 350.");
  // From the end up, a screen at a time, as a reader pages up: each step draws the chunk
  // above it, whose height was an estimate, and the row at the top moves by the step alone.
  const climbs = await chrome?.evaluate(`(async () => {
    const pane = document.getElementById("preview-pane");
    const frames = async () => {
      for (let frame = 0; frame < 4; frame += 1) {
        await new Promise((resolve) => requestAnimationFrame(resolve));
      }
    };
    pane.scrollTop = pane.scrollHeight;
    await frames();
    const moves = [];
    for (let step = 0; step < 12; step += 1) {
      const before = ${AT_TOP};
      const offset = (${OFFSET_OF})(before.text);
      const by = Math.round(pane.clientHeight * 0.9);
      pane.scrollTop -= by;
      await frames();
      const after = (${OFFSET_OF})(before.text);
      moves.push({ text: before.text, by, moved: after === null ? null : after - offset - by });
    }
    return moves;
  })()`);
  check(
    "paging up through an open fold keeps each row where the scroll put it",
    Array.isArray(climbs) &&
      climbs.length === 12 &&
      climbs.every((each) => each.moved !== null && Math.abs(each.moved) < 1),
    JSON.stringify(climbs),
  );

  await fresh();
  await mount("long", {}, { comparison: LONG_MARKDOWN, answer: LONG_ANSWER });
  await roundTrip(
    "a long document on Changes, Concise",
    "Context paragraph 150.",
    "current",
    "diff",
  );
  await scrollTo("Old paragraph 150.");
  const removedBlock = await atTop();
  const blockBefore = await offsetOf("New paragraph 150.");
  await click("long", ".diff-toolbar .diff-show-control", "current");
  const blockAfter = await offsetOf("New paragraph 150.");
  check(
    "a removed block at the pane's top gives its place to the next block Current draws",
    // A removed block says so to a screen reader ("Removed: "), in its text.
    removedBlock?.text.endsWith("Old paragraph 150.") &&
      blockBefore !== null &&
      blockAfter !== null &&
      Math.abs(blockBefore - blockAfter) < 1,
    JSON.stringify({ removedBlock, blockBefore, blockAfter, now: await atTop() }),
  );
} finally {
  await chrome?.close();
  server.close();
}
// The session's bound is set from these (tests/test_diff_current_chrome.py).
process.stderr.write(
  `Chrome launched in ${((launched - started) / 1000).toFixed(1)} s; measured in ${((performance.now() - launched) / 1000).toFixed(1)} s\n`,
);
if (SHOTS) {
  fs.mkdirSync(SHOTS, { recursive: true });
  fs.writeFileSync(path.join(SHOTS, "toolbar-widths.json"), `${JSON.stringify(table, null, 2)}\n`);
}
if (failures.length > 0) {
  process.stderr.write(`${failures.join("\n")}\n`);
  process.exit(1);
}
process.stdout.write(`diff current in Chrome: ${checks} checks passed\n`);

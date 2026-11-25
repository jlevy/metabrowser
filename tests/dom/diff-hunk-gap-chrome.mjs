// A code diff's hunk gaps, laid out by headless Chrome: the production `mountDiffView`
// (builtin_plugins/diff/diff-view.js) mounts a comparison whose file has two hunks, under
// the shell's, the diff plugin's, and KPress's stylesheets, with a gap loader answering in
// the page as the comparison route's `view=lines` answers (mb-zz81).
//
//   CHROME_BIN=/path/to/chrome CHROME_PROFILES=/dir/the/caller/removes \
//     KPRESS_STATIC=/dir/with/kpress/css/and/fonts GAP_INPUT=/path/to/input.json \
//     [GAP_SHOTS=/dir/for/screenshots] node tests/dom/diff-hunk-gap-chrome.mjs
//
// tests/test_diff_hunk_gap_chrome.py writes GAP_INPUT ({sheets}: KPress's sheets), copies
// KPress's stylesheets and faces out of the installed package, owns the profile, and runs
// this in a process group of its own. GAP_SHOTS, when set, receives screenshots: the file
// closed, a gap open, and the file at 320 px.
//
// `src/app.py` has 900 lines; its first hunk adds lines 10 to 59, a run long enough to fold
// behind the diff's fold bar, and its second changes line 600, so gaps stand before line 7,
// from line 63 to 596, and after line 603. `DIFF_GAP_LINES` is 250 here, so the gap between
// the hunks opens its 250 lines nearest the second hunk, in batches, behind a bar for the
// rest, and that bar opens 250 more.
//
// What it measures is layout and the browser's own scrolling, which no browserless DOM has
// (docs/design-system.md, "Fold Expanders"): every gap's bar, the nested one too, computes
// as the changed run's fold bar does, at rest and under the pointer, in Unified and in
// Split, and spans its file; the separator it keeps is in the muted tone and the bar's own
// sans face, on one line, and gives way to an ellipsis at 320 px while the label stays whole; the
// keyboard reaches a gap's bar with the ring the changed run's bar draws, and Enter opens
// and closes it; and the reader's place holds, which is the browser's scroll anchoring
// beside the diff's own (`settlePlace`): opened from the keyboard while its bar is above
// the pane, a gap leaves the row at the pane's top where it is at every frame while its
// rows are drawn and the group grows, and closing it again does too, in Unified and in
// Split; clicked where the reader sees it, its bar stays under the pointer.
import fs from "node:fs";
import http from "node:http";
import path from "node:path";
import { launchChrome } from "./chrome-session.mjs";

const root = path.resolve(import.meta.dirname, "../..");
const STATIC = path.join(root, "src/metabrowser/static");
const DIFF = path.join(root, "src/metabrowser/builtin_plugins/diff");
const KPRESS = path.resolve(/** @type {string} */ (process.env.KPRESS_STATIC));
const INPUT = JSON.parse(fs.readFileSync(/** @type {string} */ (process.env.GAP_INPUT), "utf8"));
const SHOTS = process.env.GAP_SHOTS;
// Layout puts box edges on 1/64 px; a box's rounding to it is the same place.
const TOLERANCE_PX = 1 / 64;
// A row the reader is reading may move by less than a pixel, which the screen does not show.
const PLACE_PX = 1;
const failures = [];
let checks = 0;
const check = (label, ok, detail = "") => {
  checks += 1;
  if (!ok) {
    failures.push(`${label}${detail ? `: ${detail}` : ""}`);
  }
};
const near = (a, b, within = TOLERANCE_PX) => Math.abs(a - b) <= within;

// ── The comparison ──────────────────────────────────────────────────────────

const LENGTH = 900;
const ADDED = { from: 10, to: 59 };
const CHANGED = 600;
/** The new side of `src/app.py`: lines 10 to 59 added, line 600 changed. */
const NEW = Array.from({ length: LENGTH }, (_, index) => {
  const number = index + 1;
  if (number >= ADDED.from && number <= ADDED.to) {
    return `added line ${number}`;
  }
  return number === CHANGED ? `line ${number}, changed` : `line ${number}`;
});
const context = (from, to) =>
  Array.from({ length: to - from + 1 }, (_, index) => ({
    op: "context",
    text: NEW[from + index - 1],
  }));
const added = NEW.slice(ADDED.from - 1, ADDED.to).map((text) => ({ op: "add", text }));
const side = (oid) => ({
  content: { kind: "git_object", oid },
  entry_type: "file",
  mode: "100644",
  path: "src/app.py",
});
const COMPARISON = {
  manifest: {
    cursor: null,
    files: [
      {
        additions: 51,
        availability: "ready",
        binary: false,
        deletions: 1,
        id: "f1",
        kind: "modified",
        new: side("1".repeat(40)),
        old: side("2".repeat(40)),
      },
    ],
    totals: { additions: 51, deletions: 1, exact: true, files: 1 },
    truncated: false,
  },
  patches: {
    f1: {
      file_id: "f1",
      hunks: [
        {
          heading: "",
          lines: [...context(7, 9), ...added, ...context(60, 62)],
          new_count: 56,
          new_start: 7,
          old_count: 6,
          old_start: 7,
        },
        {
          heading: "def handle_request(request: Request, *, timeout: float = 30.0) -> Response:",
          lines: [
            ...context(597, 599),
            { op: "del", text: `line ${CHANGED}` },
            { op: "add", text: NEW[CHANGED - 1] },
            ...context(601, 603),
          ],
          new_count: 7,
          new_start: 597,
          old_count: 7,
          old_start: 547,
        },
      ],
      truncated: false,
    },
  },
  resolved: {
    base_policy: "direct",
    comparison_id: "git:chrome",
    kind: "content",
    left: { kind: "git" },
    options: { context: 3, rename_detection: true, rename_similarity: 50 },
    right: { kind: "git" },
    source: { name: "chrome" },
  },
  schema: "file-diff-v1",
  schema_version: 1,
};
/** The gap one open of the bar between the hunks shows, `DIFF_GAP_LINES` in the page. */
const GAP_LINES = 250;
/** The separator text each gap's bar keeps, which finds it. */
const BETWEEN = "+597,7";
const LEADING = "+7,56";

// ── The page ────────────────────────────────────────────────────────────────

// The shell's tokens and sheet, then the diff plugin's, then KPress's document sheets; the
// shell's icons and its SDK's chip family; and the comparison and its new side's lines.
// Below the file, room for the pane to bring its last hunk to the top, as the files after
// it do on a page.
const PAGE = `<!doctype html><html><head><meta charset="utf-8"><title>diff hunk gap</title>
<link rel="stylesheet" href="/kpress/css/style-tokens.css">
<link rel="stylesheet" href="/static/styles.css">
<link rel="stylesheet" href="/diff/styles.css">
${INPUT.sheets.map((sheet) => `<link rel="stylesheet" href="/kpress/${sheet}">`).join("\n")}
<script>window.METABROWSER_SETTINGS = { DIFF_GAP_LINES: ${GAP_LINES} };</script>
<script>window.gapInput = ${JSON.stringify({ comparison: COMPARISON, lines: NEW })};</script>
<script src="/static/icons.js"></script>
<script>window.metabrowser = { icons: window.MetabrowserIcons };</script>
<script src="/static/filter-controls.js"></script>
<script type="module">
import { mountDiffView, setGapLoader } from "/diff/diff-view.js";
window.diffGap = { mountDiffView, setGapLoader };
</script>
</head><body style="margin: 0">
<div id="preview-pane" class="preview-pane" data-kpress-viewport
  style="display: block; height: 600px; width: 940px; overflow-y: auto">
<div id="long" class="metabrowser-diff-host" style="width: 900px"></div>
<div style="height: 1200px"></div>
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

// In the page: mount the comparison in *layout*, with a gap loader that answers each ask
// from the new side's lines a moment later, as the route does, and keeps the asks. Resolves
// once the diff draws its rows.
const MOUNT = `async (layout) => {
  const { mountDiffView, setGapLoader } = window.diffGap;
  const { comparison: recorded, lines } = window.gapInput;
  window.asks = [];
  setGapLoader(async (revision, path, ask) => {
    window.asks.push(revision + " " + path + " " + ask.start + "+" + ask.count);
    await new Promise((resolve) => setTimeout(resolve, 30));
    return {
      comparison_id: "git:chrome",
      file_id: "f1",
      path,
      side: "new",
      start: ask.start,
      lines: lines.slice(ask.start - 1, ask.start - 1 + ask.count),
      line_count: lines.length,
      ends_with_newline: true,
    };
  });
  const comparison = structuredClone(recorded);
  Object.defineProperty(comparison, "__revision", { value: "HEAD", enumerable: false });
  const prefs = new Map([["diff.layout", layout]]);
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
  window.diffGapView?.dispose();
  const host = document.getElementById("long");
  window.diffGapView = mountDiffView(host, comparison, api, { showSummary: false });
  for (let frame = 0; frame < 240; frame += 1) {
    if (host.querySelector(".diff-line, .diff-split-row")) {
      for (let settle = 0; settle < 3; settle += 1) {
        await new Promise((resolve) => requestAnimationFrame(resolve));
      }
      return host.querySelector(".diff-root")?.dataset.layout ?? null;
    }
    await new Promise((resolve) => requestAnimationFrame(resolve));
  }
  return false;
}`;

// Page helpers, prefixed to each expression that uses them: a gap's bar by the separator or
// the label it holds, the changed run's fold bar, a row's sides' text, and the drawn rows.
const HELPERS = `
const gapBar = (needle) =>
  [...document.querySelectorAll("#long .diff-gap-control")].find((bar) =>
    bar.textContent.includes(needle),
  ) ?? null;
const runBar = () => document.querySelector("#long .diff-fold-control:not(.diff-gap-control)");
const sidesOf = (row) => [...row.querySelectorAll(".diff-line-text")].map((node) => node.textContent);
const rows = () =>
  [...document.querySelectorAll("#long .diff-line, #long .diff-split-row")].filter(
    (row) => row.getClientRects().length > 0,
  );
const rowOf = (needle) =>
  rows().find((row) => {
    const sides = sidesOf(row);
    return sides.length > 0 && sides.every((text) => text === needle);
  }) ?? null;
const pane = document.getElementById("preview-pane");
`;
const inPage = (/** @type {string} */ body) => `(async () => {${HELPERS}\n${body}\n})()`;

// The bar's computed properties a reader sees, which every fold bar shares.
const BAR_STYLE = [
  "display",
  "box-sizing",
  "padding-top",
  "padding-right",
  "padding-bottom",
  "padding-left",
  "margin-top",
  "margin-bottom",
  "border-top-width",
  "border-top-style",
  "border-top-color",
  "border-bottom-width",
  "border-bottom-style",
  "border-bottom-color",
  "border-left-width",
  "border-right-width",
  "border-radius",
  "background-color",
  "background-image",
  "box-shadow",
  "color",
  "font-family",
  "font-size",
  "font-weight",
  "font-style",
  "line-height",
  "letter-spacing",
  "text-align",
  "text-transform",
  "gap",
  "align-items",
  "cursor",
  "user-select",
];

// In the page: every gap's bar and the changed run's, each with its computed style, its box
// against its file's, where its chevron and label are, and its separator's face, tone, and
// whether it is cut; and the shell's muted tone resolved in the diff.
const READ_BARS = inPage(`
  const names = ${JSON.stringify(BAR_STYLE)};
  const read = (node) => {
    const file = node.closest(".diff-file");
    const fileRect = file.getBoundingClientRect();
    const rect = node.getBoundingClientRect();
    const style = getComputedStyle(node);
    const chevron = node.querySelector(".diff-fold-chevron").getBoundingClientRect();
    const labelNode = node.querySelector(".diff-fold-label");
    const label = labelNode.getBoundingClientRect();
    const detail = node.querySelector(".diff-fold-detail");
    const detailStyle = detail ? getComputedStyle(detail) : null;
    return {
      text: labelNode.textContent,
      className: node.className,
      tag: node.tagName,
      detail: detail?.textContent ?? "",
      style: Object.fromEntries(names.map((name) => [name, style.getPropertyValue(name)])),
      height: rect.height,
      width: rect.width,
      startInFile: rect.left - fileRect.left - file.clientLeft,
      fileWidth: file.clientWidth,
      overflows: node.scrollWidth > node.clientWidth,
      chevronStart: chevron.left - rect.left,
      chevronWidth: chevron.width,
      labelStart: label.left - rect.left,
      labelMiddle: (label.top + label.bottom) / 2 - rect.top,
      labelCut: labelNode.scrollWidth > labelNode.clientWidth,
      detailFace: detailStyle?.fontFamily ?? null,
      detailColor: detailStyle?.color ?? null,
      detailCut: detail ? detail.scrollWidth > detail.clientWidth : null,
      detailRects: detail ? detail.getClientRects().length : 0,
      detailHeight: detail ? detail.getBoundingClientRect().height : 0,
      detailFontSize: detailStyle ? parseFloat(detailStyle.fontSize) : 0,
    };
  };
  const token = (property, value) => {
    const probe = document.createElement("span");
    probe.style.setProperty(property, value);
    document.querySelector("#long .diff-root").append(probe);
    const resolved = getComputedStyle(probe).getPropertyValue(property);
    probe.remove();
    return resolved;
  };
  return {
    gaps: [...document.querySelectorAll("#long .diff-gap-control")].map(read),
    run: read(runBar()),
    separators: document.querySelectorAll("#long .diff-hunk-header").length,
    muted: token("color", "var(--muted)"),
  };
`);

// A bar's background once its transition is over (one value for five frames), and its
// centre, to put the pointer on.
const BACKGROUND = (/** @type {string} */ find) =>
  inPage(`
  const node = ${find};
  const rect = node.getBoundingClientRect();
  let last = "";
  let still = 0;
  return await new Promise((resolve) => {
    const frame = () => {
      const background = getComputedStyle(node).backgroundColor;
      still = background === last ? still + 1 : 0;
      last = background;
      if (still >= 5) {
        resolve({ background, x: rect.left + rect.width / 2, y: rect.top + rect.height / 2 });
      } else {
        requestAnimationFrame(frame);
      }
    };
    requestAnimationFrame(frame);
  });
`);

// Once the keyboard has focused the bar *find* names: the ring it draws, beside the shell's
// ring tokens resolved where it is; null while focus is elsewhere.
const RING = (/** @type {string} */ find) =>
  inPage(`
  const control = ${find};
  if (!control || document.activeElement !== control) return null;
  const probe = document.createElement("span");
  probe.style.outline = "var(--focus-ring-width) solid var(--focus-ring-color)";
  probe.style.outlineOffset = "var(--focus-ring-offset)";
  control.append(probe);
  const token = getComputedStyle(probe);
  const ring = { width: token.outlineWidth, color: token.outlineColor, offset: token.outlineOffset };
  probe.remove();
  const style = getComputedStyle(control);
  return {
    visible: control.matches(":focus-visible"),
    ring,
    drawn: { style: style.outlineStyle, width: style.outlineWidth, color: style.outlineColor, offset: style.outlineOffset },
  };
`);

// Until the bar *find* names is open or closed as *expanded* says, its group holds *count*
// rows, nothing is loading, and the pane, the bar, and the group keep their boxes for five
// frames: the group's height transition is over.
const SETTLED = (
  /** @type {string} */ find,
  /** @type {boolean} */ expanded,
  /** @type {number} */ count,
) =>
  inPage(`
  const bar = ${find};
  const group = document.getElementById(bar.getAttribute("aria-controls"));
  let last = "";
  let still = 0;
  for (let frame = 0; frame < 600; frame += 1) {
    await new Promise((resolve) => requestAnimationFrame(resolve));
    const drawn = [...group.children].filter((node) => node.matches(".diff-line, .diff-split-row")).length;
    const now = JSON.stringify([
      pane.scrollTop,
      bar.getBoundingClientRect().top,
      group.getBoundingClientRect().height,
      drawn,
    ]);
    const ready =
      bar.getAttribute("aria-expanded") === String(${expanded}) &&
      bar.getAttribute("aria-busy") !== "true" &&
      drawn === ${count};
    still = ready && now === last ? still + 1 : 0;
    last = now;
    if (still >= 5) return { drawn, height: group.getBoundingClientRect().height, frames: frame };
  }
  return { drawn: null, last };
`);

// The pane scrolled so the row that reads *needle* is at its top, and the bar *find* names
// focused where it is, without scrolling to it. Resolves with the row's offset from the
// pane's top and the bar's box.
const PLACE = (
  /** @type {string} */ needle,
  /** @type {string} */ find,
  /** @type {number} */ at,
) =>
  inPage(`
  const row = rowOf(${JSON.stringify(needle)});
  pane.scrollTop += row.getBoundingClientRect().top - pane.getBoundingClientRect().top - ${at};
  for (let frame = 0; frame < 3; frame += 1) {
    await new Promise((resolve) => requestAnimationFrame(resolve));
  }
  const bar = ${find};
  bar.focus({ preventScroll: true });
  const paneTop = pane.getBoundingClientRect().top;
  return {
    offset: row.getBoundingClientRect().top - paneTop,
    bar: bar.getBoundingClientRect().top - paneTop,
    barBottom: bar.getBoundingClientRect().bottom - paneTop,
    focused: document.activeElement === bar,
    scrollTop: pane.scrollTop,
  };
`);

// Where the row that reads *needle* is from the pane's top, sampled at every frame from
// now until *frames* have passed, kept as `window.placeSamples`.
const SAMPLE = (/** @type {string} */ needle, /** @type {number} */ frames) =>
  inPage(`
  window.placeSamples = [];
  const frame = () => {
    const row = rowOf(${JSON.stringify(needle)});
    window.placeSamples.push(row ? row.getBoundingClientRect().top - pane.getBoundingClientRect().top : null);
    if (window.placeSamples.length < ${frames}) requestAnimationFrame(frame);
  };
  requestAnimationFrame(frame);
  return true;
`);
const OFFSET = (/** @type {string} */ needle) =>
  inPage(`
  const row = rowOf(${JSON.stringify(needle)});
  return row ? row.getBoundingClientRect().top - pane.getBoundingClientRect().top : null;
`);

// Rounded to hundredths for the record; the checks take the unrounded values.
const rounded = (/** @type {string} */ _key, /** @type {unknown} */ value) =>
  typeof value === "number" ? Math.round(value * 100) / 100 : value;

const server = /** @type {http.Server} */ (await serve());
const { port } = /** @type {import("node:net").AddressInfo} */ (server.address());
/** @type {Awaited<ReturnType<typeof launchChrome>> | null} */
let chrome = null;
/** @param {string} name */
const shot = async (name) => {
  if (!SHOTS || !chrome) {
    return;
  }
  const clip = await chrome.evaluate(`(() => {
    const rect = document.getElementById("preview-pane").getBoundingClientRect();
    return { x: rect.left, y: rect.top, width: rect.width, height: rect.height, scale: 1 };
  })()`);
  const { data } = await chrome.send("Page.captureScreenshot", { format: "png", clip });
  fs.mkdirSync(SHOTS, { recursive: true });
  fs.writeFileSync(path.join(SHOTS, `${name}.png`), Buffer.from(data, "base64"));
};
/** @param {{x: number, y: number}} at */
const point = (at) =>
  chrome?.send("Input.dispatchMouseEvent", { type: "mouseMoved", x: at.x, y: at.y });
/** @param {{x: number, y: number}} at */
const click = async (at) => {
  for (const type of ["mousePressed", "mouseReleased"]) {
    await chrome?.send("Input.dispatchMouseEvent", {
      type,
      x: at.x,
      y: at.y,
      button: "left",
      clickCount: 1,
    });
  }
};
/** @param {"Tab" | "Enter"} key */
const press = async (key) => {
  const codes = { Tab: 9, Enter: 13 };
  const text = key === "Enter" ? { text: "\r", unmodifiedText: "\r" } : {};
  await chrome?.send("Input.dispatchKeyEvent", {
    type: "keyDown",
    key,
    code: key,
    windowsVirtualKeyCode: codes[key],
    ...text,
  });
  await chrome?.send("Input.dispatchKeyEvent", {
    type: "keyUp",
    key,
    code: key,
    windowsVirtualKeyCode: codes[key],
  });
};
const fresh = async (/** @type {string} */ layout) => {
  await chrome?.send("Page.navigate", { url: `http://127.0.0.1:${port}/` });
  await chrome?.waitFor(
    "document.readyState === 'complete' && !!window.diffGap && !!window.metabrowser.filterControls",
  );
  const drawn = await chrome?.evaluate(`(${MOUNT})(${JSON.stringify(layout)})`);
  check(`the diff draws in ${layout}`, drawn === layout, `${drawn}`);
  await chrome?.evaluate("document.fonts.ready.then(() => true)");
};
const between = `gapBar(${JSON.stringify(BETWEEN)})`;
const leading = `gapBar(${JSON.stringify(LEADING)})`;
const record = {};

/** Every gap's bar computes as the changed run's does, in *at*'s layout and width. */
function lookChecks(/** @type {any} */ read, /** @type {string} */ at, /** @type {number} */ gaps) {
  check(
    `${at}: every hunk's separator is a gap's bar`,
    read.separators === 0 && read.gaps.length === gaps,
    `${read.separators} plain separators, ${read.gaps.length} bars`,
  );
  check(
    `${at}: the changed run folds behind the diff's fold bar`,
    read.run.tag === "BUTTON" &&
      read.run.className === "fold-expander diff-fold-control disclosure-toggle",
    read.run.className,
  );
  for (const gap of read.gaps) {
    const name = `${at}, the bar "${gap.text}"`;
    check(
      `${name} is the diff's fold bar`,
      gap.tag === "BUTTON" &&
        gap.className === "fold-expander diff-fold-control disclosure-toggle diff-gap-control",
      gap.className,
    );
    for (const [property, value] of Object.entries(read.run.style)) {
      check(
        `${name}: its ${property} is the changed run's bar's`,
        gap.style[property] === value,
        `${gap.style[property]} against ${value}`,
      );
    }
    for (const part of ["chevronStart", "chevronWidth", "labelStart", "labelMiddle", "height"]) {
      check(
        `${name}: its ${part} is the changed run's bar's`,
        near(gap[part], read.run[part]),
        `${gap[part]} against ${read.run[part]}`,
      );
    }
    check(
      `${name} spans its file and nothing in it runs past it`,
      near(gap.startInFile, 0) && near(gap.width, gap.fileWidth) && !gap.overflows,
      `${gap.startInFile}+${gap.width} of ${gap.fileWidth}, overflows ${gap.overflows}`,
    );
    check(`${name}: its label is whole`, !gap.labelCut, gap.text);
    if (gap.detail !== "") {
      check(
        `${name}: its separator is in the bar's face and the muted tone`,
        gap.detailFace === gap.style["font-family"] && gap.detailColor === read.muted,
        `${gap.detailFace} ${gap.detailColor} against ${gap.style["font-family"]} ${read.muted}`,
      );
    }
  }
}

try {
  chrome = await launchChrome(/** @type {string} */ (process.env.CHROME_BIN), {
    profiles: /** @type {string} */ (process.env.CHROME_PROFILES),
    width: 1000,
    height: 800,
  });
  await chrome.send("Page.enable");

  // The look, in Unified: three gaps (before the first hunk, between them, and the rest of
  // the file) and the changed run's bar between them, at rest and under the pointer.
  await fresh("unified");
  const unified = await chrome.evaluate(READ_BARS);
  record.unified = unified;
  lookChecks(unified, "Unified", 3);
  check(
    "the gaps' bars are before the first hunk, between the hunks, and after the last",
    unified.gaps.map((/** @type {any} */ gap) => gap.text).join(" | ") ===
      "6 unchanged lines | 534 unchanged lines | Rest of the file" &&
      unified.gaps[0].detail.startsWith("@@ -7,6 +7,56 @@") &&
      unified.gaps[1].detail.startsWith("@@ -547,7 +597,7 @@ def handle_request(") &&
      unified.gaps[2].detail === "",
    JSON.stringify(unified.gaps.map((/** @type {any} */ gap) => [gap.text, gap.detail])),
  );
  check(
    "a separator stands on one line beside its label",
    unified.gaps.every(
      (/** @type {any} */ gap) =>
        gap.detail === "" || (gap.detailRects === 1 && gap.detailHeight < 2 * gap.detailFontSize),
    ),
    JSON.stringify(
      unified.gaps.map((/** @type {any} */ gap) => [gap.detailRects, gap.detailHeight]),
    ),
  );
  await shot("closed");
  const resting = await chrome.evaluate(BACKGROUND(leading));
  const runResting = await chrome.evaluate(BACKGROUND("runBar()"));
  await point(resting);
  const hovered = await chrome.evaluate(BACKGROUND(leading));
  await point(runResting);
  const runHovered = await chrome.evaluate(BACKGROUND("runBar()"));
  // The pointer leaves the bars, beside the pane, and their backgrounds settle at rest.
  await point({ x: 990, y: 790 });
  await chrome.evaluate(BACKGROUND("runBar()"));
  await chrome.evaluate(BACKGROUND(leading));
  record.hover = { resting, hovered, runResting, runHovered };
  check(
    "under the pointer, a gap's bar takes the changed run's bar's hover",
    hovered.background === runHovered.background &&
      resting.background === runResting.background &&
      hovered.background !== resting.background,
    `${resting.background} -> ${hovered.background}, run ${runResting.background} -> ${runHovered.background}`,
  );

  // The keyboard reaches the first gap's bar and the changed run's, with one ring, and
  // Enter opens and closes a gap.
  await chrome.evaluate("(document.activeElement?.blur(), true)");
  /** @type {Record<string, any>} */
  const rings = {};
  for (let step = 0; step < 40 && !(rings.gap && rings.run); step += 1) {
    await press("Tab");
    rings.gap ??= await chrome.evaluate(RING(leading));
    rings.run ??= await chrome.evaluate(RING("runBar()"));
  }
  record.rings = rings;
  check(
    "the keyboard reaches a gap's bar and draws the changed run's bar's ring",
    rings.gap?.visible === true &&
      rings.run?.visible === true &&
      JSON.stringify(rings.gap.drawn) === JSON.stringify(rings.run.drawn) &&
      rings.gap.drawn.style === "solid" &&
      rings.gap.drawn.width === rings.gap.ring.width &&
      rings.gap.drawn.color === rings.gap.ring.color,
    JSON.stringify(rings),
  );
  await chrome.evaluate(inPage(`${leading}.focus(); return true;`));
  await press("Enter");
  const leadOpen = await chrome.evaluate(SETTLED(leading, true, 6));
  check("Enter opens a gap's bar to its lines", leadOpen.drawn === 6, JSON.stringify(leadOpen));
  const leadRows = await chrome.evaluate(
    inPage(`return [...document.getElementById(${leading}.getAttribute("aria-controls")).children]
      .map((row) => sidesOf(row).join(" / ")).join(" | ");`),
  );
  check(
    "the lines it opens are the file's own, in order",
    leadRows === NEW.slice(0, 6).join(" | "),
    leadRows,
  );
  await press("Enter");
  const leadClosed = await chrome.evaluate(SETTLED(leading, false, 0));
  check(
    "Enter closes it again, its group of no height",
    leadClosed.drawn === 0 && near(leadClosed.height, 0),
    JSON.stringify(leadClosed),
  );

  // At 320 px the separator gives way to an ellipsis on the bar's one line.
  await chrome.evaluate(
    inPage(`document.getElementById("long").style.width = "320px"; return true;`),
  );
  const narrow = await chrome.evaluate(READ_BARS);
  record.narrow = narrow.gaps;
  lookChecks(narrow, "Unified at 320 px", 3);
  check(
    "at 320 px the separator between the hunks ends in an ellipsis and its bar keeps its height",
    narrow.gaps[1].detailCut === true &&
      narrow.gaps[1].detailRects === 1 &&
      near(narrow.gaps[1].height, unified.gaps[1].height),
    JSON.stringify(narrow.gaps[1]),
  );
  await shot("narrow");
  await chrome.evaluate(
    inPage(`document.getElementById("long").style.width = "900px"; return true;`),
  );

  // The look in Split.
  await fresh("split");
  const split = await chrome.evaluate(READ_BARS);
  record.split = split.gaps;
  lookChecks(split, "Split", 3);

  // The place, opened from the keyboard while the bar is above the pane: the row at the
  // pane's top, the second hunk's first changed line's neighbour, keeps its offset at every
  // frame while the gap's rows are drawn in batches and its group grows, and so does the
  // nested bar for the rest. Closing it keeps the place too.
  for (const layout of ["unified", "split"]) {
    await fresh(layout);
    const needle = "line 598";
    const before = await chrome.evaluate(PLACE(needle, between, 0));
    check(
      `${layout}: the bar between the hunks is above the pane and has the focus`,
      before.barBottom <= 0 && before.focused === true && near(before.offset, 0),
      JSON.stringify(before),
    );
    await chrome.evaluate(SAMPLE(needle, 90));
    await press("Enter");
    const opened = await chrome.evaluate(SETTLED(between, true, GAP_LINES));
    const samples = await chrome.evaluate("window.placeSamples");
    const after = await chrome.evaluate(OFFSET(needle));
    const moved = Math.max(
      ...samples.map((/** @type {number | null} */ at) => Math.abs((at ?? 1e6) - before.offset)),
    );
    record[`${layout}Open`] = { before, opened, after, moved };
    check(
      `${layout}: the gap opens its ${GAP_LINES} lines nearest the hunk`,
      opened.drawn === GAP_LINES,
      JSON.stringify(opened),
    );
    check(
      `${layout}: opening it leaves the row at the pane's top where it was`,
      after !== null && near(after, before.offset, PLACE_PX),
      `${before.offset} -> ${after}`,
    );
    check(
      `${layout}: and at every frame while it opened`,
      moved <= PLACE_PX,
      `${moved} px; ${JSON.stringify(samples, rounded)}`,
    );
    if (layout === "unified") {
      await shot("between-open");
    }
    // Its label changes as it opens, so it is marked to be found again.
    const rest = `document.querySelector("#long [data-probe='rest']")`;
    const restFound = await chrome.evaluate(
      inPage(
        `const bar = gapBar("284 unchanged lines"); if (bar) bar.dataset.probe = "rest"; return bar !== null;`,
      ),
    );
    check(`${layout}: a bar for the rest of the gap opens first in it`, restFound === true);
    if (restFound) {
      const restRead = await chrome.evaluate(
        inPage(`const bar = ${rest}; const group = document.getElementById(${between}.getAttribute("aria-controls"));
          return { first: group.firstElementChild === bar, bottom: bar.getBoundingClientRect().bottom - pane.getBoundingClientRect().top };`),
      );
      check(
        `${layout}: the rest's bar leads the gap's group, above the pane`,
        restRead.first === true && restRead.bottom <= 0,
        JSON.stringify(restRead),
      );
      await chrome.evaluate(inPage(`${rest}.focus({ preventScroll: true }); return true;`));
      const restBefore = await chrome.evaluate(OFFSET(needle));
      await press("Enter");
      const restOpen = await chrome.evaluate(SETTLED(rest, true, GAP_LINES));
      const restAfter = await chrome.evaluate(OFFSET(needle));
      record[`${layout}Rest`] = { restBefore, restOpen, restAfter };
      check(
        `${layout}: opening the rest's bar leaves the row at the pane's top where it was`,
        restOpen.drawn === GAP_LINES && restAfter !== null && near(restAfter, restBefore, PLACE_PX),
        `${restBefore} -> ${restAfter}, ${JSON.stringify(restOpen)}`,
      );
    }
    await chrome.evaluate(inPage(`${between}.focus({ preventScroll: true }); return true;`));
    const closeBefore = await chrome.evaluate(OFFSET(needle));
    await press("Enter");
    const closed = await chrome.evaluate(SETTLED(between, false, 0));
    const closeAfter = await chrome.evaluate(OFFSET(needle));
    record[`${layout}Close`] = { closeBefore, closed, closeAfter };
    check(
      `${layout}: closing the gap above the pane leaves the row at its top where it was`,
      closed.drawn === 0 && closeAfter !== null && near(closeAfter, closeBefore, PLACE_PX),
      `${closeBefore} -> ${closeAfter}, ${JSON.stringify(closed)}`,
    );
  }

  // Clicked where the reader sees it, 200 px below the pane's top, a gap's bar stays under
  // the pointer while its lines open after it.
  await fresh("unified");
  const seen = await chrome.evaluate(PLACE("line 597", between, 220));
  const barAt = await chrome.evaluate(
    inPage(
      `const rect = ${between}.getBoundingClientRect(); return { x: rect.left + 40, y: rect.top + rect.height / 2, top: rect.top - pane.getBoundingClientRect().top };`,
    ),
  );
  await click(barAt);
  const clicked = await chrome.evaluate(SETTLED(between, true, GAP_LINES));
  const barThen = await chrome.evaluate(
    inPage(`return ${between}.getBoundingClientRect().top - pane.getBoundingClientRect().top;`),
  );
  record.clicked = { seen, barAt, clicked, barThen };
  check(
    "a gap's bar clicked in view opens and stays under the pointer",
    clicked.drawn === GAP_LINES && near(barThen, barAt.top, PLACE_PX),
    `${barAt.top} -> ${barThen}, ${JSON.stringify(clicked)}`,
  );
  const asks = await chrome.evaluate("window.asks");
  check(
    "each open asks the route once, for its lines",
    JSON.stringify(asks) === JSON.stringify(["HEAD src/app.py 347+250"]),
    JSON.stringify(asks),
  );
  process.stderr.write(`${JSON.stringify(record, rounded)}\n`);
} finally {
  await chrome?.close();
  server.close();
}
if (failures.length > 0) {
  process.stderr.write(`${failures.join("\n")}\n`);
  process.exit(1);
}
process.stdout.write(`diff hunk gap in Chrome: ${checks} checks passed\n`);

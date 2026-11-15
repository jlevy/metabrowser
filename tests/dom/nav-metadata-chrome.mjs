// The navigation metadata line under each main tab, laid out by headless Chrome against a
// live `metab` server: the Files totals, the Commits tally, and the Pulls count and
// connection lines, in the states each one passes through.
//
//   CHROME_BIN=... CHROME_PROFILES=<dir> GH_HOLD=<file> GH_SCENARIO=<file> GH_BIN=<file> \
//     node tests/dom/nav-metadata-chrome.mjs <server base URL>
//
// tests/test_nav_metadata_chrome.py serves a checkout of the GitHub stand-in with a fake
// `gh` (GH_BIN, the only gh on the server's PATH) that waits while GH_HOLD exists and
// answers from GH_SCENARIO. This script rewrites the scenario to make the next refresh
// fail, and finally takes the fake's execute bit away, so the server finds no gh at all.
// The test owns the profile directory and stops this process's whole group, Chrome
// included, however the run ends (tests/process_group.py).
//
// The three were three recipes: 13px text 6px under the Files filters, 13px text centred
// in the Commits toolbar slot, and 12px muted text hard against the Pulls filters' rule.
// They are one component, `.nav-metadata` (docs/design-system.md, "Navigation Metadata
// Line"), and what that promises is layout, which only a browser computes. In every state
// below, at the default pane width and at a wide one: every line has one type and inset,
// the first line sits the same distance under the rule above it on every tab, the last the
// same distance over the rule under it, a pending tally sits where its figures will, and a
// band is its lines and nothing else. At the wide width, where every state's text fits on
// its lines, each tab's band is one height in every state; at the default width a Pulls
// remedy and the Files split wrap, as they should. In a narrow pane the Pulls count is cut
// short on its one line.
//
// The states are the real ones where the running app can reach them, and otherwise the
// markup the production code writes: the server's own Commits slot, read from the page it
// serves; the class and text git-panel.js and app.js give the failed tally and the Files
// remarks, read from their source; and `treeSummaryHtml`, which the page itself calls.
//
// Each step writes `phase <name> <ms since start>` to stderr, so a slow run says where.
import fs from "node:fs";
import path from "node:path";
import { launchChrome } from "./chrome-session.mjs";

const [base] = process.argv.slice(2);
const { GH_HOLD: HOLD, GH_SCENARIO: SCENARIO, GH_BIN } = process.env;
if (!base || !HOLD || !SCENARIO || !GH_BIN || !process.env.CHROME_BIN) {
  throw new Error(
    "usage: CHROME_BIN CHROME_PROFILES GH_HOLD GH_SCENARIO GH_BIN nav-metadata-chrome.mjs <base URL>",
  );
}
const STATIC = path.resolve(import.meta.dirname, "../../src/metabrowser/static");
const started = Date.now();
const phase = (name) => process.stderr.write(`phase ${name} ${Date.now() - started}\n`);
// Text positions are fractional; under half a pixel is not a different place.
const TOLERANCE_PX = 0.5;
// Wide enough that every state's text, the longest remedy included, is one line; and
// narrower than the stand-in's count, "102 PRs on octo/demo", which must keep to its line.
const WIDE_PX = 720;
const NARROW_PX = 120;
// Each wait's bound: a paint, or a fake `gh` refresh of the stand-in's catalog, which takes
// a second or two on a loaded machine. Chrome's start is bounded in chrome-session.mjs.
const STEP_MS = 30000;

const failures = [];
let checks = 0;
const check = (label, ok, detail = "") => {
  checks += 1;
  if (!ok) {
    failures.push(`${label}${detail ? `: ${detail}` : ""}`);
  }
};
const near = (a, b) => Math.abs(a - b) <= TOLERANCE_PX;

/** A class string or text the production source writes, read from it. */
function sourceString(file, pattern) {
  const match = pattern.exec(fs.readFileSync(path.join(STATIC, file), "utf8"));
  if (!match) {
    throw new Error(`${file}: ${pattern} not found`);
  }
  return match[1];
}
const FAILED_TALLY = sourceString("git-panel.js", /failed\.className = "([^"]+)";/);
const SELECTION_NOTE = sourceString("app.js", /note\.className = "(tree-selection-note[^"]*)";/);
const STALE_NOTE = sourceString("app.js", /note\.className = "(recent-stale-note[^"]*)";/);
const STALE_TEXT = sourceString("app.js", /"(Recent files may be out of date; retrying…)"/);

// In the page: the visible metadata lines of the tab in front, as one band, with the rule
// above it (the tab bar's when the band stands in the toolbar slot, the toolbar's when it
// stands under it) and the rule under its last line.
const BAND = `(() => {
  const visible = (el) => el.getClientRects().length > 0;
  const lines = [...document.querySelectorAll(".nav-metadata")].filter(visible);
  if (lines.length === 0) return null;
  const toolbar = [...document.querySelectorAll("[data-nav-toolbar]")].find(visible);
  const tabBar = document.querySelector(".nav-tab-bar").getBoundingClientRect();
  const inToolbar = lines[0].closest(".nav-toolbar") !== null;
  const above = inToolbar ? tabBar.bottom : toolbar.getBoundingClientRect().bottom;
  const pane = document.querySelector(".tree-pane").getBoundingClientRect();
  const px = (value) => parseFloat(value) || 0;
  const described = lines.map((el) => {
    const cs = getComputedStyle(el);
    const r = el.getBoundingClientRect();
    const contentTop = r.top + px(cs.borderTopWidth) + px(cs.paddingTop);
    const contentBottom = r.bottom - px(cs.borderBottomWidth) - px(cs.paddingBottom);
    const range = document.createRange();
    range.selectNodeContents(el);
    const glyphs = [...range.getClientRects()].filter((g) => g.width > 0 && g.height > 0);
    // Where a pending tally's middle sits in its line box, as a share of the line.
    const shimmers = [...el.querySelectorAll(".tally-pending")].map((shimmer) => {
      const s = shimmer.getBoundingClientRect();
      return (s.top + s.height / 2 - contentTop) / px(cs.lineHeight);
    });
    return {
      cls: el.className,
      text: el.textContent.replace(/\\s+/g, " ").trim(),
      note: el.classList.contains("nav-metadata-note"),
      fontSize: cs.fontSize,
      fontWeight: cs.fontWeight,
      fontFamily: cs.fontFamily,
      lineHeight: px(cs.lineHeight),
      color: cs.color,
      columnGap: cs.columnGap,
      contentTop,
      contentBottom,
      lines: Math.round((contentBottom - contentTop) / px(cs.lineHeight)),
      textLeft: glyphs.length ? Math.min(...glyphs.map((g) => g.left)) - pane.left : null,
      shimmers,
    };
  });
  const first = described[0];
  const last = described[described.length - 1];
  // The rule under the band: the slot's own when the band stands in it.
  const under = inToolbar ? toolbar : lines[lines.length - 1];
  const ruleWidth = parseFloat(getComputedStyle(under).borderBottomWidth) || 0;
  const ruleTop = under.getBoundingClientRect().bottom - ruleWidth;
  return {
    inToolbar,
    lines: described,
    ruleWidth,
    above: first.contentTop - above,
    below: ruleTop - last.contentBottom,
    height: ruleTop + ruleWidth - above,
  };
})()`;

const chrome = await launchChrome(process.env.CHROME_BIN, {
  profiles: process.env.CHROME_PROFILES,
  width: 1280,
  height: 900,
});
// Each state's band at the default pane width, and at the wide one.
const bands = {};
const wide = {};
let narrowCount = null;
try {
  phase("chrome");
  const evaluate = chrome.evaluate;
  const waitFor = (expression) => chrome.waitFor(expression, STEP_MS);
  const click = (selector) =>
    evaluate(`document.querySelector(${JSON.stringify(selector)}).click()`);
  const frames = () =>
    evaluate("new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)))");
  const paneWidth = async (px) => {
    await evaluate(`(() => {
      const pane = document.querySelector(".tree-pane");
      pane.style.width = ${JSON.stringify(px ? `${px}px` : "")};
      pane.style.minWidth = ${JSON.stringify(px === NARROW_PX ? "0" : "")};
      document.querySelector(".tree-content").scrollTop = 0;
    })()`);
    await frames();
  };
  const measure = async (name) => {
    await paneWidth(null);
    bands[name] = await evaluate(BAND);
    await paneWidth(WIDE_PX);
    wide[name] = await evaluate(BAND);
    await paneWidth(null);
    check(`${name}: has a metadata line`, bands[name] !== null && wide[name] !== null);
    phase(name);
  };
  const connection = `document.querySelector(".github-pulls-connection")?.textContent ?? ""`;
  const scenario = (failure) => {
    const answers = JSON.parse(fs.readFileSync(SCENARIO, "utf8"));
    answers.api_failure = failure;
    fs.writeFileSync(SCENARIO, JSON.stringify(answers));
  };
  const afterSummary = (html) =>
    evaluate(
      `[...document.querySelectorAll("#tab-files .nav-metadata")].at(-1).insertAdjacentHTML("afterend", ${JSON.stringify(html)})`,
    );

  await chrome.send("Page.enable");
  await chrome.send("Page.navigate", { url: `${base}/view/` });
  await waitFor(`document.querySelector(".tree-summary .tree-summary-tracked") !== null`);
  await measure("files");
  // The line as the inline first paint draws it, before its counts arrive, and as it
  // reads while the index is still being counted: the same words in the same type.
  await evaluate(
    `document.querySelector(".tree-summary").outerHTML = treeSummaryHtml(null, null, null)`,
  );
  await measure("files pending");
  await evaluate(
    `document.querySelector(".tree-summary").outerHTML = treeSummaryHtml(null, 12797, 413800000)`,
  );
  await measure("files counting");
  // A filter's remarks: muted lines of the same band.
  await evaluate(
    `_renderFilteredTally(document.getElementById("tab-files"), {recency: "all", types: "md", size: "all", showIgnored: true}, 2)`,
  );
  await measure("files filtered");
  await afterSummary(
    `<div class="${SELECTION_NOTE}" role="status">docs is outside this filter.</div>`,
  );
  await measure("files selection outside");
  await evaluate(`document.querySelector(".tree-selection-note").remove()`);
  await afterSummary(`<div class="${STALE_NOTE}" role="status">${STALE_TEXT}</div>`);
  await measure("files recent stale");
  await evaluate(
    `document.querySelectorAll(".tree-summary-filtered, .recent-stale-note").forEach((n) => n.remove())`,
  );

  await click('.nav-tab-bar [data-tab="git"]');
  await waitFor(`document.querySelector(".git-history-summary-count") !== null`);
  await measure("commits");
  // The slot as the server ships it, before the count arrives, read from the page it serves.
  await evaluate(`(async () => {
    const page = await (await fetch("/view/")).text();
    const shipped = new DOMParser().parseFromString(page, "text/html");
    document.getElementById("nav-toolbar-git").innerHTML =
      shipped.getElementById("nav-toolbar-git").innerHTML;
  })()`);
  await measure("commits pending");
  await evaluate(
    `document.getElementById("nav-toolbar-git").innerHTML = '<div class="${FAILED_TALLY}">History unavailable</div>'`,
  );
  await measure("commits failed");

  // The fake gh holds every call while GH_HOLD exists, so the list has no rows yet.
  await click('.nav-tab-bar [data-tab="pulls"]');
  await waitFor(`(${connection}).includes("Fetching pull requests")`);
  await measure("pulls loading");
  fs.rmSync(HOLD);
  await waitFor(
    `document.querySelector(".github-pulls-item") !== null && (${connection}).startsWith("Updated")`,
  );
  await measure("pulls updated");
  // In a pane narrower than the count, the count is cut short on its one line.
  await paneWidth(NARROW_PX);
  narrowCount = await evaluate(`(() => {
    const line = document.querySelector(".github-pulls-status");
    const total = line.querySelector(".github-pulls-total-line");
    const cs = getComputedStyle(line);
    return {
      lines: Math.round(parseFloat(cs.height) / parseFloat(cs.lineHeight)),
      cut: total.scrollWidth > total.clientWidth,
    };
  })()`);
  await paneWidth(null);
  // A refresh that cannot reach GitHub, then one gh refuses until it is signed in, then no
  // gh at all: the rows stay, and the connection line says why and what to do.
  // Reload answers only while no refresh runs, as when the catalog's pages still arrive.
  const reloadReady = `document.querySelector(".github-pulls-reload")?.getAttribute("aria-disabled") === "false"`;
  scenario({ stderr: "error connecting to api.github.com\n", exit: 1 });
  await waitFor(reloadReady);
  await click(".github-pulls-reload");
  await waitFor(`(${connection}).includes("could not be reached")`);
  await measure("pulls unreachable");
  scenario({ stderr: "To get started with GitHub CLI, please run:  gh auth login\n", exit: 4 });
  await waitFor(reloadReady);
  await click(".github-pulls-reload");
  await waitFor(`(${connection}).includes("gh auth login")`);
  await measure("pulls signed out");
  fs.chmodSync(GH_BIN, 0o644);
  await waitFor(reloadReady);
  await click(".github-pulls-reload");
  await waitFor(`(${connection}).includes("Install GitHub CLI")`);
  await measure("pulls without gh");
} finally {
  await chrome.close();
  phase("closed");
}

// One type for every line on every tab, in every state, at both widths: the Files totals'
// first line is the reference, a remark is the same type in the muted ink, and the text
// starts at the navigation column's one inset.
const reference = bands.files?.lines[0];
const notes = Object.values(bands).flatMap((band) => band?.lines.filter((line) => line.note) ?? []);
for (const [width, measured] of [
  ["default", bands],
  ["wide", wide],
]) {
  for (const [name, band] of Object.entries(measured)) {
    if (band === null || reference === undefined) {
      continue;
    }
    const at = `${name} (${width})`;
    for (const line of band.lines) {
      const where = `${at} "${line.text.slice(0, 40)}"`;
      check(`${where}: is a metadata line`, line.cls.split(" ").includes("nav-metadata"), line.cls);
      for (const property of ["fontSize", "fontWeight", "fontFamily", "lineHeight", "columnGap"]) {
        check(
          `${where}: ${property}`,
          line[property] === reference[property],
          `${line[property]} against ${reference[property]}`,
        );
      }
      const ink = line.note ? notes[0].color : reference.color;
      check(`${where}: color`, line.color === ink, `${line.color} against ${ink}`);
      if (line.textLeft !== null) {
        check(`${where}: inset`, near(line.textLeft, reference.textLeft), `${line.textLeft}`);
      }
      // A pending tally sits where its figures will: across the middle of the line box,
      // where the text's own middle is, not at its top.
      for (const middle of line.shimmers) {
        check(`${where}: a pending tally's middle`, middle > 0.4 && middle < 0.65, `${middle}`);
      }
    }
    // The same distance under the rule above and over the rule below, in the toolbar slot
    // (Commits) as under a toolbar (Files, Pulls).
    check(`${at}: above`, near(band.above, bands.files.above), `${band.above}`);
    check(`${at}: below`, near(band.below, bands.files.below), `${band.below}`);
    check(`${at}: above equals below`, near(band.above, band.below), `${band.above}/${band.below}`);
    // Its height is its lines' and nothing else.
    const lines = band.lines.reduce((sum, line) => sum + line.lines, 0);
    const expected = lines * reference.lineHeight + band.above + band.below + band.ruleWidth;
    check(`${at}: height`, near(band.height, expected), `${band.height} against ${expected}`);
  }
}
check("a remark is muted", notes.length > 0 && notes[0].color !== reference?.color);
// The pending tallies of Files and Commits sit alike in their lines.
const shimmerOf = (name) => bands[name]?.lines[0].shimmers[0];
check(
  "Files and Commits pending tallies sit alike",
  shimmerOf("commits pending") !== undefined &&
    Math.abs(shimmerOf("commits pending") - shimmerOf("files pending")) * reference.lineHeight <=
      TOLERANCE_PX,
  `${shimmerOf("files pending")} / ${shimmerOf("commits pending")}`,
);
// Where every state's text fits, one height on each tab whatever the state: one line on
// Files and Commits, two on Pulls.
for (const name of [
  "files pending",
  "files counting",
  "commits",
  "commits pending",
  "commits failed",
]) {
  check(`${name}: one line's height`, near(wide[name]?.height, wide.files?.height));
}
check("commits: the line fills the toolbar slot", bands.commits?.inToolbar === true);
for (const name of ["pulls updated", "pulls unreachable", "pulls signed out", "pulls without gh"]) {
  check(
    `${name}: the loading band's height`,
    near(wide[name]?.height, wide["pulls loading"]?.height),
  );
}
check("pulls: two lines", wide["pulls loading"]?.lines.length === 2);
check(
  "pulls: in a narrow pane the count is cut short on its one line",
  narrowCount?.lines === 1 && narrowCount?.cut === true,
  JSON.stringify(narrowCount),
);

if (failures.length > 0) {
  process.stderr.write(`${JSON.stringify({ bands, wide }, null, 1)}\n`);
  throw new Error(
    `nav metadata line in Chrome, ${failures.length} of ${checks} checks failed:\n${failures.join("\n")}`,
  );
}
process.stdout.write(`nav metadata line in Chrome: ${checks} checks passed\n`);

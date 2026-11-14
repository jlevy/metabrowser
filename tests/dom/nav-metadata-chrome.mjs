// The navigation metadata line under each main tab, laid out by headless Chrome against a
// live `metab` server: the Files totals, the Commits tally, and the Pulls count and
// connection lines, in the states each one passes through.
//
//   CHROME_BIN=... CHROME_PROFILES=<dir> GH_HOLD=<file> GH_SCENARIO=<file> \
//     node tests/dom/nav-metadata-chrome.mjs <server base URL>
//
// tests/test_nav_metadata_chrome.py serves a checkout of the GitHub stand-in with a fake
// `gh` that waits while GH_HOLD exists and answers from GH_SCENARIO, which this script
// rewrites to make the next refresh fail. It owns the profile directory and stops this
// process's whole group, Chrome included, however the run ends (tests/process_group.py).
//
// The three were three recipes: 13px text 6px under the Files filters, 13px text centred
// in the Commits toolbar slot, and 12px muted text hard against the Pulls filters' rule.
// They are one component, `.nav-metadata` (docs/design-system.md, "Navigation Metadata
// Line"), and what that promises is layout, which only a browser computes: every line has
// one type, its first line sits the same distance under the rule above it on every tab,
// its last the same distance over the rule under it, and a band holds one height whatever
// state it is in. The pane is widened so that every state's text fits on its lines; a
// remedy longer than the pane wraps, as it should, and that is the one height change.
//
// Each step writes `phase <name> <ms since start>` to stderr, so a slow run says where.
import fs from "node:fs";
import { launchChrome } from "./chrome-session.mjs";

const [base] = process.argv.slice(2);
const HOLD = process.env.GH_HOLD;
const SCENARIO = process.env.GH_SCENARIO;
if (!base || !HOLD || !SCENARIO || !process.env.CHROME_BIN || !process.env.CHROME_PROFILES) {
  throw new Error(
    "usage: CHROME_BIN CHROME_PROFILES GH_HOLD GH_SCENARIO nav-metadata-chrome.mjs <base URL>",
  );
}
const started = Date.now();
const phase = (name) => process.stderr.write(`phase ${name} ${Date.now() - started}\n`);
// Text positions are fractional; under half a pixel is not a different place.
const TOLERANCE_PX = 0.5;
// Wide enough that every state's text, the longest remedy included, is one line.
const PANE_PX = 720;
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
  const described = lines.map((el) => {
    const cs = getComputedStyle(el);
    const r = el.getBoundingClientRect();
    const px = (value) => parseFloat(value) || 0;
    const contentTop = r.top + px(cs.borderTopWidth) + px(cs.paddingTop);
    const contentBottom = r.bottom - px(cs.borderBottomWidth) - px(cs.paddingBottom);
    const range = document.createRange();
    range.selectNodeContents(el);
    const glyphs = [...range.getClientRects()].filter((g) => g.width > 0 && g.height > 0);
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
const bands = {};
try {
  phase("chrome");
  const evaluate = chrome.evaluate;
  const waitFor = (expression) => chrome.waitFor(expression, STEP_MS);
  const click = (selector) =>
    evaluate(`document.querySelector(${JSON.stringify(selector)}).click()`);
  const widen = () =>
    evaluate(`(() => {
      document.querySelector(".tree-pane").style.width = "${PANE_PX}px";
      document.querySelector(".tree-content").scrollTop = 0;
    })()`);
  const measure = async (name) => {
    await widen();
    // Two frames, so the widened pane is laid out before it is read.
    await evaluate("new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)))");
    bands[name] = await evaluate(BAND);
    check(`${name}: has a metadata line`, bands[name] !== null);
    phase(name);
  };
  const connection = `document.querySelector(".github-pulls-connection")?.textContent ?? ""`;
  const scenario = (failure) => {
    const answers = JSON.parse(fs.readFileSync(SCENARIO, "utf8"));
    answers.api_failure = failure;
    fs.writeFileSync(SCENARIO, JSON.stringify(answers));
  };

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
  // A filter's remark: a second, muted line of the same band.
  await evaluate(
    `_renderFilteredTally(document.getElementById("tab-files"), {recency: "all", types: "md", size: "all", showIgnored: true}, 2)`,
  );
  await measure("files filtered");
  await evaluate(`document.querySelector(".tree-summary-filtered").remove()`);

  await click('.nav-tab-bar [data-tab="git"]');
  await waitFor(`document.querySelector(".git-history-summary-count") !== null`);
  await measure("commits");

  // The fake gh holds every call while GH_HOLD exists, so the list has no rows yet.
  await click('.nav-tab-bar [data-tab="pulls"]');
  await waitFor(`(${connection}).includes("Fetching pull requests")`);
  await measure("pulls loading");
  fs.rmSync(HOLD);
  await waitFor(
    `document.querySelector(".github-pulls-item") !== null && (${connection}).startsWith("Updated")`,
  );
  await measure("pulls updated");
  // A refresh that cannot reach GitHub, then one gh refuses until it is signed in: the
  // rows stay, and the connection line says why and what to do.
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
} finally {
  await chrome.close();
  phase("closed");
}

// One type for every line on every tab, in every state: the Files totals' first line is
// the reference, a remark is the same type in the muted ink, and the text starts at the
// navigation column's one inset.
const reference = bands.files?.lines[0];
const notes = Object.values(bands).flatMap((band) => band?.lines.filter((line) => line.note) ?? []);
for (const [name, band] of Object.entries(bands)) {
  if (band === null || reference === undefined) {
    continue;
  }
  for (const line of band.lines) {
    const where = `${name} "${line.text.slice(0, 40)}"`;
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
  }
  // The same distance under the rule above and over the rule below, in the toolbar slot
  // (Commits) as under a toolbar (Files, Pulls).
  check(`${name}: above`, near(band.above, bands.files.above), `${band.above}`);
  check(`${name}: below`, near(band.below, bands.files.below), `${band.below}`);
  check(`${name}: above equals below`, near(band.above, band.below), `${band.above}/${band.below}`);
  // Its height is its lines' and nothing else, so no state's text moves what is under it.
  const lines = band.lines.reduce((sum, line) => sum + line.lines, 0);
  const expected = lines * reference.lineHeight + band.above + band.below + band.ruleWidth;
  check(`${name}: height`, near(band.height, expected), `${band.height} against ${expected}`);
}
check("a remark is muted", notes.length > 0 && notes[0].color !== reference?.color);
// One line on Files and Commits whatever the line says; two on Pulls in every state.
for (const name of ["files pending", "files counting", "commits"]) {
  check(`${name}: one line's height`, near(bands[name]?.height, bands.files?.height));
}
check("commits: the line fills the toolbar slot", bands.commits?.inToolbar === true);
for (const name of ["pulls updated", "pulls unreachable", "pulls signed out"]) {
  check(
    `${name}: the loading band's height`,
    near(bands[name]?.height, bands["pulls loading"]?.height),
  );
}
check("pulls: two lines", bands["pulls loading"]?.lines.length === 2);

if (failures.length > 0) {
  process.stderr.write(`${JSON.stringify(bands, null, 1)}\n`);
  throw new Error(
    `nav metadata line in Chrome, ${failures.length} of ${checks} checks failed:\n${failures.join("\n")}`,
  );
}
process.stdout.write(`nav metadata line in Chrome: ${checks} checks passed\n`);

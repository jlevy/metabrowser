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
// short on its one line. And in a pane too narrow for it, the Commits tally, which stands in
// the toolbar slot, wraps between its phrases at its own line height, as the tab bar over
// it wraps between its tabs (docs/design-system.md, "Navigation Toolbars Wrap"), held to
// that rule by tests/dom/nav-toolbar-wrap.mjs at every width from the narrowest. Over all of
// it the navigation's header holds still in every state on every tab: the navigation's
// Refresh is there under every tab from the first paint.
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
import { judge, linesOf, NARROWEST, SWEEP, WIDTHS } from "./nav-toolbar-wrap.mjs";

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

// In the page: the visible metadata lines of the tab in front, as one band, with the edge
// above it and the rule under its last line. The edge above is the toolbar's rule when the
// band stands under it; in the toolbar slot it is the foot of what stands over the slot:
// the revision row, which a checkout shows over Files and Commits alike, or else the tab
// bar's rule.
const BAND = `(() => {
  const visible = (el) => el.getClientRects().length > 0;
  const lines = [...document.querySelectorAll(".nav-metadata")].filter(visible);
  if (lines.length === 0) return null;
  const toolbar = [...document.querySelectorAll("[data-nav-toolbar]")].find(visible);
  const over = [document.querySelector(".nav-tab-bar"), document.getElementById("nav-source-ref")]
    .filter((el) => el && visible(el))
    .at(-1);
  const inToolbar = lines[0].closest(".nav-toolbar") !== null;
  const above = (inToolbar ? over : toolbar).getBoundingClientRect().bottom;
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
      // What the line reads as laid out: each item of the flex line is a run of its own.
      innerText: el.innerText,
      // A count summary's numbers, each with its weight and the display of what holds it
      // ("Count Summaries Bold Their Numbers"): inline in one item, never an item itself.
      numbers: [...el.querySelectorAll(".summary-number")].map((number) => ({
        text: number.textContent,
        weight: getComputedStyle(number).fontWeight,
        within: getComputedStyle(number.parentElement).display,
      })),
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

// In the page: each rule between the navigation's sections that is on screen (the tab
// bar's, the toolbar's in front, and a band's under its last line) as far as it paints,
// its ends against the pane's own edges inside its border. The tree's scroller reserves
// its scrollbar's gutter (`scrollbar-gutter: stable`) and clips what it holds at its
// padding box, so a line inside it painted its rule 11 px short of the pane's right edge
// in a 300 px pane, wherever the tree was scrolled and whether or not it overflowed.
const RULES = `(() => {
  const pane = document.querySelector(".tree-pane");
  const box = pane.getBoundingClientRect();
  const style = getComputedStyle(pane);
  const left = box.left + parseFloat(style.borderLeftWidth);
  const right = box.right - parseFloat(style.borderRightWidth);
  const scroller = document.getElementById("tree-content");
  const clip = scroller.getBoundingClientRect().left + scroller.clientLeft + scroller.clientWidth;
  const ruled = (el) =>
    el.getClientRects().length > 0 && parseFloat(getComputedStyle(el).borderBottomWidth) > 0;
  return {
    overflows: scroller.scrollHeight > scroller.clientHeight,
    rules: [...pane.querySelectorAll(".nav-tab-bar, [data-nav-toolbar], .nav-metadata")]
      .filter(ruled)
      .map((el) => {
        const r = el.getBoundingClientRect();
        const held = scroller.contains(el);
        return {
          cls: el.className,
          held,
          left: r.left - left,
          right: right - (held ? Math.min(r.right, clip) : r.right),
        };
      }),
  };
})()`;
// The pane's heights each tab's rules are read at: the window's, where the stand-in's tree
// fits, and one short enough that every tab's content overflows its scroller.
const SHORT_PANE_PX = 220;

// In the page: the navigation's header, which no tab and no state moves: each box in it, and
// whether the navigation's Refresh shows.
const HEADER = `(() => {
  const round = (value) => Math.round(value * 100) / 100;
  const at = (el) => {
    const r = el.getBoundingClientRect();
    return { left: round(r.left), top: round(r.top), width: round(r.width), height: round(r.height) };
  };
  const refresh = document.getElementById("nav-refresh");
  return {
    boxes: [...document.querySelector(".app-header").children]
      .filter((el) => el.getClientRects().length > 0)
      .map((el) => [el.id || el.className, at(el)]),
    shown: refresh !== null && getComputedStyle(refresh).visibility === "visible",
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
// Each state's header, at the default pane width.
const headers = {};
// Each state's rules, at the narrowest, default, and wide panes, at the window's height and
// a short one.
const rules = [];
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
  // `setup`, an expression, puts a state in place in the same task as each read, so a live
  // repaint cannot land between them: the tree summary repaints itself when its counts or a
  // tree reload arrive (`paintTreeSummary` in app.js), and on a slow runner one replaced a
  // stubbed pending line before it was read (CI, 2026-11-23).
  const measure = async (name, setup = null) => {
    const read = setup === null ? BAND : `(${setup}, ${BAND})`;
    await paneWidth(null);
    bands[name] = await evaluate(read);
    headers[name] = await evaluate(HEADER);
    await paneWidth(WIDE_PX);
    wide[name] = await evaluate(read);
    await paneWidth(null);
    check(`${name}: has a metadata line`, bands[name] !== null && wide[name] !== null);
    phase(name);
  };
  const measureRules = async (name) => {
    for (const height of [null, SHORT_PANE_PX]) {
      await evaluate(
        `document.querySelector(".tree-pane").style.height = ${JSON.stringify(height ? `${height}px` : "")}`,
      );
      for (const width of [NARROWEST + 1, null, WIDE_PX]) {
        await paneWidth(width);
        rules.push({
          name,
          width: width ?? "default",
          height: height ?? "window",
          ...(await evaluate(RULES)),
        });
      }
    }
    await evaluate(`document.querySelector(".tree-pane").style.height = ""`);
    await paneWidth(null);
    phase(`${name} rules`);
  };
  const connection = `document.querySelector(".github-pulls-connection")?.textContent ?? ""`;
  const scenario = (failure) => {
    const answers = JSON.parse(fs.readFileSync(SCENARIO, "utf8"));
    answers.api_failure = failure;
    fs.writeFileSync(SCENARIO, JSON.stringify(answers));
  };
  // A panel that could not load: its band gives way to the alert, as the lines went with the
  // panel when they were its first rows, and shows again once the alert is gone (styles.css,
  // after `.nav-metadata-band`). `fail` puts the alert where the shell's failure does, and
  // returns how to take it away; each state reads whether the band is shown.
  const givesWay = (band, fail) =>
    evaluate(`(() => {
      const band = document.getElementById(${JSON.stringify(band)});
      const shown = () => band.childElementCount > 0 && getComputedStyle(band).display !== "none";
      const before = shown();
      const restore = (${fail})();
      const failed = shown();
      restore();
      return [before, failed, shown()];
    })()`);
  const afterSummary = (html) =>
    evaluate(
      `[...document.querySelectorAll("#nav-metadata-files .nav-metadata")].at(-1).insertAdjacentHTML("afterend", ${JSON.stringify(html)})`,
    );

  await chrome.send("Page.enable");
  await chrome.send("Page.navigate", { url: `${base}/view/` });
  await waitFor(`document.querySelector(".tree-summary .tree-summary-tracked") !== null`);
  await measure("files");
  await measureRules("files");
  // The line as the inline first paint draws it, before its counts arrive, and as it
  // reads while the index is still being counted: the same words in the same type.
  const stubSummary = (args) =>
    `document.querySelector(".tree-summary").outerHTML = treeSummaryHtml(${args})`;
  await measure("files pending", stubSummary("null, null, null"));
  await evaluate(stubSummary("null, 12797, 413800000"));
  await measure("files counting", stubSummary("null, 12797, 413800000"));
  // A filter's remarks: muted lines of the same band.
  await evaluate(
    `_renderFilteredTally({recency: "all", types: "md", size: "all", showIgnored: true}, 2)`,
  );
  await measure("files filtered");
  await measureRules("files filtered");
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
  // Grouped or recency, the panel's alert (failGroupedTree's own); the tree's, the scroller's.
  const filesFailed = await givesWay(
    "nav-metadata-files",
    `() => {
      const panel = document.getElementById("tab-files");
      const kept = [...panel.childNodes];
      failGroupedTree("nav-metadata-chrome");
      return () => panel.replaceChildren(...kept);
    }`,
  );
  check(
    "files: the band gives way to the panel's alert",
    `${filesFailed}` === "true,false,true",
    filesFailed,
  );
  const treeFailed = await givesWay(
    "nav-metadata-files",
    `() => {
      const alert = document.createElement("div");
      alert.setAttribute("role", "alert");
      document.getElementById("tree-content").prepend(alert);
      return () => alert.remove();
    }`,
  );
  check(
    "files: the band gives way to the scroller's alert",
    `${treeFailed}` === "true,false,true",
    treeFailed,
  );
  // The band's shadow is over what the scroller holds, positioned rows too, and the toolbars,
  // whose menus open over it, are over the band.
  const stacking = await evaluate(`["nav-metadata-files", "nav-filter-bar", "nav-toolbar-git"].map(
    (id) => getComputedStyle(document.getElementById(id)).zIndex,
  )`);
  check(
    "the band stacks over the scroller and under the toolbars",
    `${stacking}` === "1,2,2",
    stacking,
  );

  await click('.nav-tab-bar [data-tab="git"]');
  // The click opens Commits once Git discovery registers it, and the server ships its slot
  // with a count span, so wait for the slot to be the one in front.
  await waitFor(`document.getElementById("nav-toolbar-git")?.hidden === false`);
  await waitFor(`document.querySelector(".git-history-summary-count") !== null`);
  await measure("commits");
  await measureRules("commits");
  // The Commits tally and the tab bar wrap in a pane too narrow for them: every width from
  // the narrowest, in both font sets, the tally as the stand-in has it and as a large, old
  // repository's reads. Each is held to the wrap rule; the tally's lines are its own line
  // height apart, with no gap, and the tabs' a tab's height.
  const COMMITS = {
    bar: "#nav-toolbar-git",
    row: "#nav-toolbar-git .nav-metadata",
    tokens: {
      pad: "var(--nav-metadata-padding-y)",
      line: "calc(var(--nav-metadata-line-height) * var(--nav-font-size))",
      column: "var(--nav-metadata-gap)",
    },
  };
  const TABS = { bar: ".nav-tab-bar", row: ".nav-tab-bar", tokens: {} };
  // The tally the stand-in settles at, not the pending shimmer, which has a count span too:
  // its first commit's age lands with its count. Each case writes its own markup in the
  // sweep's own page call, so what a sweep measures does not depend on when the summary
  // lands or whether the panel draws it again.
  await waitFor(`document.querySelector("#nav-toolbar-git .git-history-summary-first") !== null`);
  const SUMMARY = `document.querySelector("#nav-toolbar-git .git-history-summary")`;
  const tallyOf = (html) => `(() => { ${SUMMARY}.innerHTML = ${JSON.stringify(html)}; })()`;
  const TALLY = tallyOf(await evaluate(`${SUMMARY}.innerHTML`));
  // The spans git-panel.js (renderHistorySummary) writes, with a large, old repository's text.
  const LONG_TALLY = tallyOf(
    '<span class="git-history-summary-count"><span class="summary-number">123,456</span> commits</span>' +
      '<span class="git-history-summary-first"><span>begun</span>' +
      '<span class="git-history-summary-age age-old">12mo</span><span>ago</span></span>',
  );
  const sweep = (spec, before = "undefined") =>
    evaluate(`(${before}, (${SWEEP})(${JSON.stringify({ widths: WIDTHS, ...spec })}))`);
  const wrapped = {
    tally: await evaluate(
      `[...${SUMMARY}.querySelectorAll(".git-history-summary-count, .git-history-summary-first > span")].map((span) => span.textContent).join(" ")`,
    ),
  };
  for (const set of ["clean", "system"]) {
    await evaluate(
      `document.documentElement.setAttribute("data-app-font", ${JSON.stringify(set)})`,
    );
    await evaluate("document.fonts.ready.then(() => true)");
    await frames();
    for (const [name, before] of [
      ["the tally", TALLY],
      ["a long tally", LONG_TALLY],
    ]) {
      const measured = await sweep(COMMITS, before);
      const { pad, line, column } = measured.tokens;
      const verdict = judge(`Commits, ${name}, ${set} fonts`, measured, {
        pad,
        line,
        gap: 0,
        column,
      });
      check(
        `Commits, ${name}, ${set} fonts: keeps the wrap rule`,
        verdict.failures.length === 0,
        verdict.failures.slice(0, 6).join("\n"),
      );
      wrapped[`commits, ${name}, ${set}`] = verdict.oneLineFrom;
    }
    // The settled tally back in place of the long one.
    await evaluate(TALLY);
    const tabs = await sweep(TABS);
    // A tab is its own line: its height, as the widest pane draws it.
    const tab = tabs.rows.at(-1).units[0];
    const verdict = judge(`the tab bar, ${set} fonts`, tabs, {
      pad: 0,
      line: tab.bottom - tab.top,
      gap: 0,
      column: 0,
      overlap: 1,
    });
    check(
      `the tab bar, ${set} fonts: keeps the wrap rule`,
      verdict.failures.length === 0,
      verdict.failures.slice(0, 6).join("\n"),
    );
    check(
      `the tab bar, ${set} fonts: wraps at the narrowest pane, Commits under Files and Pulls`,
      JSON.stringify(
        linesOf(tabs.rows.find((row) => row.width === NARROWEST)).map((l) =>
          l.units.map((u) => u.name),
        ),
      ) === JSON.stringify([["files", "pulls"], ["git"]]),
    );
    wrapped[`tabs, ${set}`] = verdict.oneLineFrom;
  }
  await evaluate(`document.documentElement.setAttribute("data-app-font", "clean")`);
  await evaluate("document.fonts.ready.then(() => true)");
  await frames();
  phase(`wrapped ${JSON.stringify(wrapped)}`);
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
  await measureRules("pulls loading");
  fs.rmSync(HOLD);
  await waitFor(
    `document.querySelector(".github-pulls-item") !== null && (${connection}).startsWith("Updated")`,
  );
  await measure("pulls updated");
  await measureRules("pulls updated");
  // As pulls-nav.js's showFailure puts it, first in the tab's panel.
  const pullsFailed = await givesWay(
    "nav-metadata-pulls",
    `() => {
      const alert = document.createElement("p");
      alert.className = "github-pulls-empty";
      alert.setAttribute("role", "alert");
      document.getElementById("tab-pulls").prepend(alert);
      return () => alert.remove();
    }`,
  );
  check(
    "pulls: the band gives way to the panel's alert",
    `${pullsFailed}` === "true,false,true",
    pullsFailed,
  );
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
  // The list's part of Refresh asks only while no refresh of the list runs, as when the
  // catalog's pages still arrive, which its connection line says by being busy; and Refresh
  // takes a press only while it does not wait.
  const reloadReady = `!document.querySelector("#nav-refresh")?.hasAttribute("aria-disabled") &&
    document.querySelector(".github-pulls-connection-text")?.getAttribute("aria-busy") !== "true"`;
  scenario({ stderr: "error connecting to api.github.com\n", exit: 1 });
  await waitFor(reloadReady);
  await click("#nav-refresh");
  await waitFor(`(${connection}).includes("Could not reach GitHub")`);
  await measure("pulls unreachable");
  scenario({ stderr: "To get started with GitHub CLI, please run:  gh auth login\n", exit: 4 });
  await waitFor(reloadReady);
  await click("#nav-refresh");
  await waitFor(`(${connection}).includes("gh auth login")`);
  await measure("pulls signed out");
  fs.chmodSync(GH_BIN, 0o644);
  await waitFor(reloadReady);
  await click("#nav-refresh");
  await waitFor(`(${connection}).includes("Install GitHub CLI")`);
  await measure("pulls without gh");
} finally {
  await chrome.close();
  phase("closed");
}

// The header holds still on every tab and in every state: the navigation's Refresh is there
// under every tab from the first paint, so nothing in the row moves when another tab comes
// to the front.
check(
  "the header was read on every tab",
  ["files", "commits", "pulls loading", "pulls updated"].every((name) => name in headers),
  Object.keys(headers).join(", "),
);
for (const [name, header] of Object.entries(headers)) {
  check(
    `${name}: the header holds still`,
    JSON.stringify(header.boxes) === JSON.stringify(headers.files.boxes),
    `${JSON.stringify(header.boxes)} against ${JSON.stringify(headers.files.boxes)}`,
  );
  check(`${name}: the navigation's Refresh shows`, header.shown, String(header.shown));
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
      // A count summary's number is bold, and inline in one item of the line with its
      // words: as an item of its own, the line's gap would part it from them, and it
      // would read as a run of its own (docs/design-system.md, "Count Summaries Bold Their
      // Numbers").
      for (const number of line.numbers) {
        check(`${where}: ${number.text} is bold`, number.weight === "700", number.weight);
        check(
          `${where}: ${number.text} is inline in its item`,
          !/flex|grid/.test(number.within),
          number.within,
        );
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
// The filter's remark is one item of its line: its number bold and inline with its words,
// so it reads as one run, its spaces where they are written (mb-roa9).
for (const [width, measured] of [
  ["default", bands],
  ["wide", wide],
]) {
  const remark = measured["files filtered"]?.lines.find((line) =>
    line.cls.split(" ").includes("tree-summary-filtered"),
  );
  check(
    `files filtered (${width}): the remark's one number`,
    JSON.stringify(remark?.numbers.map((number) => number.text)) === JSON.stringify(["2"]),
    JSON.stringify(remark?.numbers),
  );
  check(
    `files filtered (${width}): the remark reads as one run`,
    remark?.innerText === remark?.text && remark?.text === "Filtered to 2 files.",
    JSON.stringify(remark?.innerText),
  );
  // The Pulls count's number is bold, as every count summary's, and its words regular.
  const count = measured["pulls updated"]?.lines[0];
  check(
    `pulls updated (${width}): the count's one number is bold`,
    count?.numbers.length === 1 && count.numbers[0].weight === "700",
    JSON.stringify(count?.numbers),
  );
}
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

// Every rule between the navigation's sections runs the pane's full width, as the tab bar's
// does, on every tab, at every pane width and height, whether the content under it
// overflows its scroller or not: no metadata line is inside the scroller, so none is cut
// short at its scrollbar's gutter (mb-vgx3).
for (const measured of rules) {
  const at = `${measured.name} (${measured.width} wide, ${measured.height} tall)`;
  check(`${at}: a tab bar and toolbar rule`, measured.rules.length >= 2, JSON.stringify(measured));
  check(
    `${at}: a metadata line's rule`,
    measured.rules.some((rule) => rule.cls.split(" ").includes("nav-metadata")) ||
      measured.name === "commits",
    JSON.stringify(measured.rules),
  );
  for (const rule of measured.rules) {
    const what = `${at}: "${rule.cls}"`;
    check(`${what} is not in the tree's scroller`, rule.held === false);
    check(`${what} starts at the pane's left edge`, near(rule.left, 0), `${rule.left}`);
    check(`${what} ends at the pane's right edge`, near(rule.right, 0), `${rule.right} short`);
  }
}
for (const tab of ["files", "pulls"]) {
  const seen = rules.filter((measured) => measured.name.startsWith(tab));
  check(
    `${tab}: rules read over content that overflows`,
    seen.some((m) => m.overflows),
  );
  check(
    `${tab}: rules read over content that fits`,
    seen.some((m) => !m.overflows),
  );
}
process.stderr.write(
  `rules ${JSON.stringify(
    rules.map((m) => ({
      at: `${m.name} ${m.width}x${m.height}${m.overflows ? " overflowing" : ""}`,
      short: m.rules.map((rule) => `${rule.cls.split(" ")[0]} ${rule.right.toFixed(2)}`),
    })),
  )}\n`,
);

if (failures.length > 0) {
  process.stderr.write(`${JSON.stringify({ bands, wide }, null, 1)}\n`);
  throw new Error(
    `nav metadata line in Chrome, ${failures.length} of ${checks} checks failed:\n${failures.join("\n")}`,
  );
}
process.stdout.write(`nav metadata line in Chrome: ${checks} checks passed\n`);

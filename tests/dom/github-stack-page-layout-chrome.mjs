// A native stack's page laid out against a pull request's in headless Chrome, against a live
// `metab` server serving the GitHub stand-in with guides (tests/github_pull_fixture.py,
// `--guided-stack`): pull request 7's own guide, and stack 70 (8, then 10), whose top, 10,
// carries the stack's guide.
//
//   CHROME_BIN=... CHROME_PROFILES=<dir> [SHOTS_DIR=<dir>] \
//     node tests/dom/github-stack-page-layout-chrome.mjs <server base URL>
//
// tests/test_github_stack_page_chrome.py builds that server, owns the profile directory, and
// stops this process's whole group, Chrome included, however the run ends.
//
// The stack's page is a pull request's page for the whole stack, made of the same parts
// (docs/design-system.md, "The Stack Page"), so each part it shares stands at the same edges
// with the same padding as on a pull request's page: the header, the tab bar, each tab's
// body, Guided Review's step list and its step's card, and the diff's host on Docs and
// Changes. Each is measured on both pages, in the light and the dark scheme, at a desktop
// width with the navigation pane shown and at a phone's with it hidden, and held equal
// within `NEAR`, border and ground included; a part whose padding the pull request's
// page gives it cannot lose it on the stack's. Changes and Guided Review are measured again
// once the reader has pressed their tabs on the stack's page, which draws the body again in
// place rather than on a page of its own. The members, the one part a pull request's
// page lacks, are a page card as Guided Review's are, its rows inset as a card's head is,
// so a member's state icon starts where Guided Review's badge does.
import fs from "node:fs";
import path from "node:path";
import { launchChrome } from "./chrome-session.mjs";

const [base] = process.argv.slice(2);
if (!base || !process.env.CHROME_BIN || !process.env.CHROME_PROFILES) {
  throw new Error("usage: CHROME_BIN CHROME_PROFILES github-stack-page-layout-chrome.mjs <base>");
}
const SHOTS = process.env.SHOTS_DIR ?? null;
// One page load, a member's fetch through the fake gh, or a diff's first screen; a loaded
// machine has needed several seconds for one.
const STEP_MS = 45000;
// Layout lands on fractional pixels, and two edges set from the same tokens round alike.
const NEAR = 0.5;
const started = Date.now();
const phase = (name) => process.stderr.write(`phase ${name} ${Date.now() - started}\n`);

const failures = [];
let checks = 0;
const check = (label, ok, detail = "") => {
  checks += 1;
  if (!ok) {
    failures.push(`${label}${detail ? `: ${detail}` : ""}`);
  }
};
const near = (a, b) => Math.abs(a - b) <= NEAR;

// The parts both pages draw, by the selector that finds each in the page's root; the first
// match is the part. The first tab starts where a pull request's does, and its label is its
// own, Guided Review on the stack's page and on 7's, Conversation on 10's.
const PARTS = {
  header: ".github-pull-header",
  title: ".github-pull-header > .page-heading",
  "tab column": ":scope > .page-reading-column:has(> .tab-bar)",
  "tab bar": ".tab-bar",
  "first tab": ".tab-bar .tab-btn",
  body: ".github-pull-body",
  "step list": ".github-pull-guide-outline",
  "step list's head": ".github-pull-guide-outline-head",
  "current step's row": '.github-pull-guide-steps-link[aria-current="step"]',
  "step card": ".github-pull-guide-card",
  "step card's head": ".github-pull-guide-card > .github-pull-card-head",
  "step card's note": ".github-pull-guide-card > .github-pull-text",
  "step card's references": ".github-pull-guide-card > .github-pull-guide-references",
  "way on": ".github-pull-guide-pager",
  "diff's host": ".github-pull-body > .github-pull-diff",
};
const GUIDED = [
  "header",
  "title",
  "tab column",
  "tab bar",
  "first tab",
  "body",
  "step list",
  "step list's head",
  "current step's row",
  "step card",
  "step card's head",
  "step card's note",
  "step card's references",
  "way on",
];
const DIFF = ["header", "title", "tab column", "tab bar", "first tab", "body", "diff's host"];

/** Each part's box, padding, border, and ground, and the members' card and rows. */
const MEASURE = (root) => `(() => {
  const page = document.querySelector(${JSON.stringify(root)});
  const parts = ${JSON.stringify(PARTS)};
  const four = (style, side) => ["top", "right", "bottom", "left"].map((edge) => parseFloat(style.getPropertyValue(side.replace("*", edge))));
  const measure = (node) => {
    if (node === null) return null;
    const box = node.getBoundingClientRect();
    const style = getComputedStyle(node);
    return {
      left: box.left,
      width: box.width,
      padding: four(style, "padding-*"),
      border: four(style, "border-*-width"),
      borderColor: style.borderTopColor,
      ground: style.backgroundColor,
      radius: style.borderTopLeftRadius,
    };
  };
  const found = {};
  for (const [name, selector] of Object.entries(parts)) {
    found[name] = measure(page.querySelector(selector));
  }
  const card = page.querySelector(".github-pull-stack-members");
  const badge = page.querySelector(".github-pull-guide-card-head .github-pull-guide-badge");
  return {
    theme: document.documentElement.getAttribute("data-theme"),
    width: window.innerWidth,
    parts: found,
    members: card === null ? null : {
      card: measure(card),
      rows: [...card.querySelectorAll(".github-pull-stack-member")].map((row) => ({
        ...measure(row),
        icon: row.querySelector(".github-pull-state-icon").getBoundingClientRect().left,
      })),
    },
    badge: badge === null ? null : badge.getBoundingClientRect().left,
    scrolls: document.scrollingElement.scrollWidth > document.scrollingElement.clientWidth,
  };
})()`;

const chrome = await launchChrome(process.env.CHROME_BIN, {
  profiles: process.env.CHROME_PROFILES,
  width: 1280,
  height: 900,
});
try {
  phase("chrome");
  const { evaluate, send } = chrome;
  const pageErrors = [];
  chrome.on("Runtime.exceptionThrown", ({ exceptionDetails }) =>
    pageErrors.push(exceptionDetails.exception?.description ?? exceptionDetails.text),
  );
  await send("Runtime.enable");
  await send("Page.enable");
  const waitFor = (expression) => chrome.waitFor(expression, STEP_MS);
  const frames = () =>
    evaluate("new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)))");
  // `\`, which hides the navigation pane and shows it again (static/nav-collapse.js).
  const togglePane = async () => {
    const key = { key: "\\", code: "Backslash", windowsVirtualKeyCode: 220 };
    await send("Input.dispatchKeyEvent", { type: "keyDown", text: "\\", ...key });
    await send("Input.dispatchKeyEvent", { type: "keyUp", ...key });
  };
  const COLLAPSED = `document.querySelector(".container").hasAttribute("data-nav-collapsed")`;
  // The shell follows the system's scheme by setting `data-theme` when the media query
  // changes (static/app.js), so a scheme is in force once the attribute names it; its color
  // transitions run out before a measurement reads a ground.
  const scheme = async (value) => {
    await send("Emulation.setEmulatedMedia", {
      features: [{ name: "prefers-color-scheme", value }],
    });
    await waitFor(
      `document.documentElement.getAttribute("data-theme") === ${JSON.stringify(value)}`,
    );
    // A transition starts on the style change after the attribute's, so the scheme is
    // settled once two frames pass with none running.
    for (let quiet = 0; quiet < 2; ) {
      await frames();
      const running = await evaluate(
        `document.getAnimations().some((a) => a instanceof CSSTransition && a.playState === "running")`,
      );
      quiet = running ? 0 : quiet + 1;
    }
  };
  const shot = async (name) => {
    if (SHOTS === null) {
      return;
    }
    await frames();
    const { data } = await send("Page.captureScreenshot", { format: "png" });
    fs.mkdirSync(SHOTS, { recursive: true });
    fs.writeFileSync(path.join(SHOTS, `${name}.png`), Buffer.from(data, "base64"));
  };

  // The stand-in's records and the repository's stacks, as a reader has them once they have
  // opened the stack's pull requests; then the stack's answer, which names 10 as the
  // member that carries its guide.
  for (const number of [8, 10]) {
    await send("Page.navigate", { url: `${base}/pull/${number}` });
    await waitFor(`document.querySelector(".github-pull-title-text") !== null`);
  }
  await waitFor(
    `fetch("/api/plugin/github/stack?number=70", {cache: "no-store"}).then((r) => r.json()).then((a) => a.state === "current" && a.guide?.number === 10)`,
  );
  phase("stack 70 and its guide read");

  /**
   * Open *route*, wait for *ready*, and measure the page under *root* in each scheme at a
   * desktop width and at a phone's with the navigation pane hidden.
   * @returns {Promise<Record<string, any>>} each measurement by "<width> <scheme>"
   */
  const take = async (route, root, ready, name, before = null) => {
    await send("Page.navigate", { url: `${base}${route}` });
    await waitFor(`location.pathname === ${JSON.stringify(route)}`);
    if (before !== null) {
      await before();
    }
    await waitFor(ready);
    await waitFor(`document.fonts.status === "loaded"`);
    // The page's keys, `\` among them, once it has attached them.
    await waitFor(
      `document.querySelector(${JSON.stringify(`${root} .tab-btn`)})?.getAttribute("aria-keyshortcuts") !== null`,
    );
    const measured = {};
    for (const value of ["light", "dark"]) {
      await scheme(value);
      measured[`desktop ${value}`] = await evaluate(MEASURE(root));
      await shot(`${name}-desktop-${value}`);
    }
    await send("Emulation.setDeviceMetricsOverride", {
      width: 375,
      height: 812,
      deviceScaleFactor: 1,
      mobile: false,
    });
    await waitFor(`window.innerWidth === 375`);
    await togglePane();
    await waitFor(COLLAPSED);
    await frames();
    for (const value of ["dark", "light"]) {
      await scheme(value);
      measured[`phone ${value}`] = await evaluate(MEASURE(root));
      await shot(`${name}-phone-${value}`);
    }
    await togglePane();
    await waitFor(`!${COLLAPSED}`);
    await send("Emulation.clearDeviceMetricsOverride");
    phase(`measured ${name}`);
    return measured;
  };

  const DIFF_READY = (root) => `(() => {
    const page = document.querySelector(${JSON.stringify(root)});
    return page !== null && page.querySelector(".github-pull-body > .github-pull-diff .diff-file") !== null &&
      page.querySelector(".github-pull-diff-holding, .github-pull-diff-loading") === null;
  })()`;
  const STACK = ".github-pull-stack-page";
  const PULL = ".github-pull:not(.github-pull-stack-page)";
  // The stack's front page is Guided Review, on its first step; a pull request's on its
  // overview, so the reader's way on takes it to its first step's card.
  const STACK_GUIDED = `document.querySelector("${STACK} .github-pull-guide-position")?.textContent === "Step 1 of 2" && document.querySelector("${STACK} .github-pull-guide-card .github-pull-guide-references") !== null`;
  const stackGuided = await take("/stack/70", STACK, STACK_GUIDED, "stack-70-guided");
  const pullGuided = await take(
    "/pull/7/guided",
    PULL,
    `document.querySelector("${PULL} .github-pull-guide-position")?.textContent === "Step 1 of 2" && document.querySelector("${PULL} .github-pull-guide-card .github-pull-guide-references") !== null`,
    "pull-7-guided",
    async () => {
      await waitFor(
        `document.querySelector("${PULL} .github-pull-guide-position")?.textContent === "Overview"`,
      );
      await evaluate(`document.querySelectorAll("${PULL} .github-pull-guide-arrow")[1].click()`);
    },
  );
  const stackDocs = await take("/stack/70/docs", STACK, DIFF_READY(STACK), "stack-70-docs");
  const pullDocs = await take("/pull/10/docs", PULL, DIFF_READY(PULL), "pull-10-docs");
  const stackChanges = await take(
    "/stack/70/changes",
    STACK,
    DIFF_READY(STACK),
    "stack-70-changes",
  );
  const pullChanges = await take("/pull/10/files", PULL, DIFF_READY(PULL), "pull-10-changes");

  // A press of a tab's link on the stack's page, which the shell lands on the page already
  // mounted (stack-page.js's `land`). The page's root is marked before the first press, so
  // the mark still there once the switched tab is measured shows its body was drawn in place.
  const MARK = `document.querySelector(${JSON.stringify(STACK)}).dataset.layoutSwitch = "kept"`;
  const KEPT = `document.querySelector(${JSON.stringify(STACK)})?.dataset.layoutSwitch === "kept"`;
  const press = async (label, path) => {
    await evaluate(
      `[...document.querySelectorAll(${JSON.stringify(`${STACK} .tab-bar .tab-btn`)})].find((tab) => tab.textContent === ${JSON.stringify(label)}).click()`,
    );
    await waitFor(`location.pathname === ${JSON.stringify(path)}`);
  };
  const stackSwitchedChanges = await take(
    "/stack/70",
    STACK,
    DIFF_READY(STACK),
    "stack-70-switched-changes",
    async () => {
      await waitFor(STACK_GUIDED);
      await evaluate(MARK);
      await press("Changes", "/stack/70/changes");
    },
  );
  const changesKept = await evaluate(KEPT);
  const stackSwitchedGuided = await take(
    "/stack/70",
    STACK,
    STACK_GUIDED,
    "stack-70-switched-guided",
    async () => {
      await waitFor(STACK_GUIDED);
      await evaluate(MARK);
      await press("Changes", "/stack/70/changes");
      await waitFor(DIFF_READY(STACK));
      await press("Guided Review", "/stack/70/guided");
    },
  );
  const guidedKept = await evaluate(KEPT);

  /** Hold each of *names* on the stack's page to the pull request's, in every measurement. */
  const compare = (label, stack, pull, names) => {
    for (const [at, ours] of Object.entries(stack)) {
      const theirs = pull[at];
      check(`${label}, ${at}: the page's scheme`, ours.theme === at.split(" ")[1], ours.theme);
      check(`${label}, ${at}: the stack's page does not scroll sideways`, !ours.scrolls);
      for (const name of names) {
        const a = ours.parts[name];
        const b = theirs.parts[name];
        check(`${label}, ${at}: the ${name} is on both pages`, a !== null && b !== null);
        if (a === null || b === null) {
          continue;
        }
        const detail = JSON.stringify({ stack: a, pull: b });
        check(
          `${label}, ${at}: the ${name} starts and ends where a pull request's does`,
          near(a.left, b.left) && (name === "first tab" || near(a.width, b.width)),
          detail,
        );
        check(
          `${label}, ${at}: the ${name} has a pull request's padding`,
          a.padding.every((value, side) => near(value, b.padding[side])),
          detail,
        );
        // Said on its own, so a box left with no room inside its border reads as that.
        for (const side of [1, 3]) {
          if (b.padding[side] > 0) {
            check(
              `${label}, ${at}: the ${name} keeps its inline padding`,
              a.padding[side] > 0,
              detail,
            );
          }
        }
        check(
          `${label}, ${at}: the ${name} has a pull request's border and ground`,
          a.border.every((value, side) => value === b.border[side]) &&
            (a.border.every((value) => value === 0) || a.borderColor === b.borderColor) &&
            a.ground === b.ground &&
            a.radius === b.radius,
          detail,
        );
      }
    }
  };
  compare("Guided Review", stackGuided, pullGuided, GUIDED);
  compare("Docs", stackDocs, pullDocs, DIFF);
  compare("Changes", stackChanges, pullChanges, DIFF);
  check("Changes after a switch of tabs: drawn in place", changesKept === true);
  check("Guided Review after a switch of tabs: drawn in place", guidedKept === true);
  compare("Changes after a switch of tabs", stackSwitchedChanges, pullChanges, DIFF);
  compare("Guided Review after a switch of tabs", stackSwitchedGuided, pullGuided, GUIDED);

  // The members: on the page's ground with no border, as the Diff summary's files under its
  // toggle are; the bordered card is the stack popover menu's alone (the owner's word of
  // 2026-11-26, mb-4qpz).
  for (const [at, ours] of Object.entries(stackGuided)) {
    const { card, rows } = ours.members;
    check(
      `the members, ${at}: no border and no ground of their own`,
      card.border.every((value) => value === 0) && card.ground === "rgba(0, 0, 0, 0)",
      JSON.stringify(card),
    );
    check(
      `the members, ${at}: the list spans the header's content, as the title does`,
      near(card.left, ours.parts.title.left) && near(card.width, ours.parts.title.width),
      JSON.stringify({ card, title: ours.parts.title }),
    );
    check(`the members, ${at}: both members are listed`, rows.length === 2, String(rows.length));
  }
  check("no script error on the pages", pageErrors.length === 0, pageErrors.join("\n"));
} finally {
  await chrome.close();
}
if (failures.length > 0) {
  process.stderr.write(`${failures.join("\n")}\n`);
  process.exit(1);
}
process.stdout.write(`stack page layout in Chrome: ${checks} checks passed\n`);

// A guided-review step's file card and its chevron, in headless Chrome, against a live `metab`
// server that serves the GitHub stand-in, whose pull request 7 has a guide
// (`--guided-documents`).
//
//   CHROME_BIN=... CHROME_PROFILES=<dir> \
//     node tests/dom/github-guided-review-fold-chrome.mjs <base URL>
//
// tests/test_github_guided_review_chrome.py builds that server, owns the profile directory, and
// stops this process's whole group, Chrome included, however the run ends
// (tests/process_group.py).
//
// Browserless, tests/dom/diff-view-behavior.js pins that the bar the diff view's builder hands
// a page is the one Changes draws and what a press on it does, and
// tests/dom/github-guided-review-mount-behavior.js that a step's card is built from it. What
// only a browser holds is where the chevron sits and how the bar is painted, so this measures
// two things, each against the same server's Changes tab and never against a number written
// here:
//
// 1. The card's chevron is Changes' chevron: it sits where Changes' sits in its bar and is as
//    large, in a bar as tall and painted alike, open and folded.
// 2. A real press on the bar folds the card, and another opens it.
//
// A press is made at a point measured one protocol call earlier, so nothing may move the
// target in between. In Changes something can: a Markdown file above the measured card gets
// its rendered layer from a request of its own, the page shows the diff after
// `CHANGES_FIRST_SCREEN_MS` whether or not that layer is in, and the layer's arrival moves
// every card under it down. A press measured before that and made after it lands on the
// Markdown above, in no bar, and folds nothing (review A on #872, A1). So Changes is measured
// only once no rendered layer is still on its way, which the diff marks in the document
// (`drawProgress` in diff-markdown.js). A bar is also measured only once its card is at rest:
// a chevron measured while it turns has a turning square's larger box.
import { launchChrome } from "./chrome-session.mjs";

const [base] = process.argv.slice(2);
if (!base || !process.env.CHROME_BIN || !process.env.CHROME_PROFILES) {
  throw new Error("usage: CHROME_BIN CHROME_PROFILES github-guided-review-fold-chrome.mjs <base>");
}
// One page load or fake gh fetch; a loaded machine has needed several seconds for one.
const STEP_MS = 30000;
/** Whether no rendered layer of the diff is still on its way: a file whose layer is pending
 * or being read marks its bar's progress so (`drawProgress` in diff-markdown.js). */
const LAYERS_IN = `document.querySelector(".diff-markdown-progress.mb-delayed-loading") === null`;

const failures = [];
let checks = 0;
const same = (label, got, want) => {
  checks += 1;
  if (JSON.stringify(got) !== JSON.stringify(want)) {
    failures.push(`${label}: got ${JSON.stringify(got)}, want ${JSON.stringify(want)}`);
  }
};

/** The shown step's first card that draws a diff. */
const GUIDE_CARD = `[...document.querySelectorAll(".github-pull-guide-step:not(.github-pull-guide-incoming) .github-pull-guide-reference")].find((card) => card.querySelector(".github-pull-guide-excerpt") !== null)`;
/** Changes' first file card whose body is its rows, drawn: one with no rendered view. The
 * page holds its diff out of sight until it is laid out (`.github-pull-diff-holding`). */
const CHANGES_CARD = `[...document.querySelectorAll(".github-pull-diff:not(.github-pull-diff-holding) .diff-root .diff-file")].find((card) => card.querySelector(".diff-file-bar-markdown") === null && card.querySelector(".diff-file-body .diff-hunk-header") !== null)`;

/**
 * The card *card* finds, at rest, or null while its body or its chevron still travels: how
 * it stands, and its bar's chevron and paint, each box from the bar's corner so two cards in
 * different places compare, to a tenth of a pixel.
 */
const CARD = (card) => `(() => {
  const section = (${card});
  const bar = section.querySelector(".diff-file-bar");
  const toggle = bar.querySelector(".diff-file-toggle");
  const glyph = toggle.querySelector(".diff-file-chevron svg");
  const body = section.querySelector(".diff-file-body");
  if (glyph === null || [body, glyph].some((node) => node.getAnimations().length > 0)) {
    return null;
  }
  const round = (value) => Math.round(value * 10) / 10;
  const from = bar.getBoundingClientRect();
  const rect = glyph.getBoundingClientRect();
  const style = (node, names) => Object.fromEntries(names.map((name) => [name, getComputedStyle(node)[name]]));
  return {
    open: toggle.getAttribute("aria-expanded"),
    bodyHeight: Math.round(body.getBoundingClientRect().height),
    bar: {
      trigger: toggle.tagName,
      chevron: { x: round(rect.left - from.left), y: round(rect.top - from.top), w: round(rect.width), h: round(rect.height) },
      turn: getComputedStyle(glyph).transform,
      height: round(from.height),
      // Not its fill, which is the hover's while the pointer that pressed it rests on it.
      paint: style(bar, ["cursor", "paddingLeft", "borderBottomWidth"]),
      triggerPaint: style(toggle, ["cursor", "color", "fontSize"]),
    },
  };
})()`;

const chrome = await launchChrome(process.env.CHROME_BIN, {
  profiles: process.env.CHROME_PROFILES,
});
try {
  const { evaluate } = chrome;
  const waitFor = (expression) => chrome.waitFor(expression, STEP_MS);
  const go = async (route) => {
    await chrome.send("Page.navigate", { url: `${base}${route}` });
    await waitFor(`location.pathname === ${JSON.stringify(route)}`);
  };
  /** The card at rest. */
  const rest = async (card) => {
    await waitFor(`${CARD(card)} !== null`);
    return evaluate(CARD(card));
  };
  /** A real press on the path in the bar of the card *card* finds, then the card at rest. */
  const press = async (card) => {
    const point = await evaluate(`(() => {
      const rect = (${card}).querySelector(".diff-file-bar .diff-file-path").getBoundingClientRect();
      return { x: rect.left + rect.width / 2, y: rect.top + rect.height / 2 };
    })()`);
    for (const type of ["mousePressed", "mouseReleased"]) {
      await chrome.send("Input.dispatchMouseEvent", {
        ...point,
        type,
        button: "left",
        clickCount: 1,
      });
    }
    return rest(card);
  };
  await chrome.send("Page.enable");

  // Changes' own file card, open and folded, once no rendered layer is still to land.
  await go("/pull/7/files");
  await waitFor(`${CHANGES_CARD} !== undefined`);
  await waitFor(LAYERS_IN);
  // The card found is the one measured throughout.
  await evaluate(`(${CHANGES_CARD}).setAttribute("data-fold-measured", "")`);
  const changes = `document.querySelector("[data-fold-measured]")`;
  await evaluate(`${changes}.querySelector(".diff-file-bar").scrollIntoView({block: "center"})`);
  await evaluate("document.fonts.ready.then(() => true)");
  const changesOpen = await rest(changes);
  const changesFolded = await press(changes);
  same("Changes' file folds at a press on its bar", changesFolded.open, "false");

  // The guide: its first step that draws a diff.
  await go("/pull/7");
  await waitFor(`document.querySelector(".github-pull-guide-steps-link") !== null`);
  const steps = await evaluate(`document.querySelectorAll(".github-pull-guide-steps-link").length`);
  let found = false;
  for (let at = 0; at < steps && !found; at += 1) {
    await evaluate(`document.querySelectorAll(".github-pull-guide-steps-link")[${at}].click()`);
    await waitFor(
      `document.querySelectorAll(".github-pull-guide-steps-link")[${at}].getAttribute("aria-current") === "step" && document.querySelector(".github-pull-guide-incoming") === null`,
    );
    found = await evaluate(`${GUIDE_CARD} !== undefined`);
  }
  if (!found) {
    throw new Error("the guide has no step that draws a diff");
  }
  await evaluate(
    `(${GUIDE_CARD}).querySelector(".diff-file-bar").scrollIntoView({block: "center"})`,
  );
  await evaluate("document.fonts.ready.then(() => true)");

  const guideOpen = await rest(GUIDE_CARD);
  same("the card starts open, as Changes' file does", guideOpen.open, changesOpen.open);
  same("open, its bar and chevron are Changes'", guideOpen.bar, changesOpen.bar);
  const guideFolded = await press(GUIDE_CARD);
  same(
    "a press on the bar folds the card to no height",
    [guideFolded.open, guideFolded.bodyHeight],
    ["false", 0],
  );
  same("folded, its bar and chevron are Changes'", guideFolded.bar, changesFolded.bar);
  const guideAgain = await press(GUIDE_CARD);
  same(
    "another press opens it as it was",
    [guideAgain.open, guideAgain.bodyHeight, guideAgain.bar],
    [guideOpen.open, guideOpen.bodyHeight, guideOpen.bar],
  );
} finally {
  await chrome.close();
}
if (failures.length > 0) {
  process.stderr.write(`${failures.join("\n")}\n`);
  process.exitCode = 1;
} else {
  process.stdout.write(`guided review fold in Chrome: ${checks} checks passed\n`);
}

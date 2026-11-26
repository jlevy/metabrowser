// A guided-review step's file card folding, in headless Chrome, against a live `metab` server
// that serves the GitHub stand-in.
//
//   CHROME_BIN=... CHROME_PROFILES=<dir> \
//     node tests/dom/github-guided-review-fold-chrome.mjs <base URL>
//
// It measures the guide of pull request 7 (the stand-in's `--guided-documents`) against that
// pull request's Changes. A stack's guide is the same module mounted by the stack's page,
// whose mount tests/dom/github-stack-guide-mount-session.js pins, and the stand-in's stack
// changes one Markdown file, whose card in Changes is a rendered one with no rows to compare.
// tests/test_github_guided_review_chrome.py builds that server, owns the profile directory, and
// stops this process's whole group, Chrome included, however the run ends
// (tests/process_group.py). With SHOTS=<dir> it also writes a picture of the card open and
// folded, and with SHOTS_ONLY=1 it writes the open one and checks nothing, for a picture of a
// build whose cards do not fold.
//
// Browserless, tests/dom/diff-view-behavior.js pins that the bar a file patch hands its card
// is the one Changes draws and what a press on it does, and
// tests/dom/github-guided-review-mount-behavior.js that a step's card is built from it. What
// only a browser holds is paint and the platform:
//
// 1. The card's bar is laid out as a file's bar in Changes is: the chevron sits where Changes'
//    sits in its bar and is as large, the bar is as tall, and the bar, the trigger, and the
//    path are set in the same type, fills, and pointer. The two are measured on the same
//    server and compared with each other, never with a number written here.
// 2. The chevron turns, and the body travels to no height, by the same rules: the same
//    computed rotation open and folded, and the same transition on the body.
// 3. A real press on the bar folds the card and another opens it, and so do Enter and Space
//    on the trigger, which keeps the focus.
// 4. Folding does not lose the reader's place: the bar stays where it was in the document,
//    and the scroller does not move while it still has room to stay.
//
// A press is made at a point measured one protocol call earlier, so nothing may move the
// target in between. In Changes something can: a Markdown file above the measured card gets
// its rendered layer from a request of its own (`/api/plugin/github/pull-rendered-diff`), the
// page shows the diff after `CHANGES_FIRST_SCREEN_MS` whether or not that layer is in, and
// the layer's arrival makes its card taller and moves every card under it down. A press
// measured before that and made after it lands on the Markdown above, in no bar, and folds
// nothing; a loaded machine, whose server answers late, did that once (review A on #872,
// A1). So Changes is measured only once no rendered layer is still on its way, which the
// diff marks in the document (`drawProgress` in diff-markdown.js). The check does not leave
// that to the machine's speed: it holds the rendered answers itself until Changes shows
// without them, and lets go of any it still holds between the measurement and the press, so
// a check that measured too early misses every time.
import fs from "node:fs";
import path from "node:path";
import { launchChrome } from "./chrome-session.mjs";

const [base] = process.argv.slice(2);
if (!base || !process.env.CHROME_BIN || !process.env.CHROME_PROFILES) {
  throw new Error("usage: CHROME_BIN CHROME_PROFILES github-guided-review-fold-chrome.mjs <base>");
}
const SHOTS = process.env.SHOTS ?? "";
const SHOTS_ONLY = process.env.SHOTS_ONLY === "1";
// One page load or fake gh fetch; a loaded machine has needed several seconds for one.
const STEP_MS = 30000;
// How long the check holds the rendered answers once Changes shows without them: long enough
// that a measurement made without waiting for them comes first, at a few protocol calls of
// some milliseconds each, and short beside the run.
const RENDERED_HOLD_MS = 1500;
/** Whether no rendered layer of the diff is still on its way: a file whose layer is pending
 * or being read marks its bar's progress so (`drawProgress` in diff-markdown.js). */
const LAYERS_IN = `document.querySelector(".diff-markdown-progress.mb-delayed-loading") === null`;
const ROUTES = { guide: "/pull/7", changes: "/pull/7/files" };

const failures = [];
let checks = 0;
const check = (label, ok, detail = "") => {
  checks += 1;
  if (!ok) {
    failures.push(`${label}${detail ? `: ${detail}` : ""}`);
  }
};
const same = (label, got, want) =>
  check(
    label,
    JSON.stringify(got) === JSON.stringify(want),
    `got ${JSON.stringify(got)}, want ${JSON.stringify(want)}`,
  );

/** The shown step's first card that draws a diff. */
const GUIDE_CARD = `[...document.querySelectorAll(".github-pull-guide-step:not(.github-pull-guide-incoming) .github-pull-guide-reference")].find((card) => card.querySelector(".github-pull-guide-excerpt") !== null)`;
/** Changes' first file card whose body is its rows, drawn: one with no rendered view, whose
 * body stands aside for it. The page holds its diff out of sight until it is laid out
 * (`.github-pull-diff-holding`), so there is none to find before then. */
const CHANGES_CARD = `[...document.querySelectorAll(".github-pull-diff:not(.github-pull-diff-holding) .diff-root .diff-file")].find((card) => card.querySelector(".diff-file-bar-markdown") === null && (card.querySelector(".diff-file-body")?.getBoundingClientRect().height ?? 0) > 0 && card.querySelector(".diff-file-body .diff-hunk-header") !== null)`;

/**
 * How the bar of the card *card* finds is laid out and painted, each box from its bar's
 * corner so two cards in different places compare, to a tenth of a pixel.
 */
const BAR = (card) => `(() => {
  const section = (${card});
  const bar = section.querySelector(".diff-file-bar");
  const toggle = bar.querySelector(".diff-file-toggle");
  const chevron = toggle.querySelector(".diff-file-chevron");
  const glyph = chevron?.querySelector("svg") ?? null;
  const name = toggle.querySelector(".diff-file-path");
  const body = section.querySelector(".diff-file-body");
  const round = (value) => Math.round(value * 10) / 10;
  const from = bar.getBoundingClientRect();
  const box = (node) => {
    if (node === null) {
      return null;
    }
    const rect = node.getBoundingClientRect();
    return { x: round(rect.left - from.left), y: round(rect.top - from.top), w: round(rect.width), h: round(rect.height) };
  };
  const style = (node, names) =>
    node === null ? null : Object.fromEntries(names.map((name) => [name, getComputedStyle(node)[name]]));
  return {
    trigger: toggle.tagName + (toggle.getAttribute("type") === null ? "" : "[" + toggle.getAttribute("type") + "]"),
    leads: bar.querySelector("*:not(.diff-file-lead)") === toggle,
    chevron: box(chevron),
    glyph: box(glyph),
    triggerStart: box(toggle)?.x ?? null,
    nameY: box(name)?.y ?? null,
    barHeight: round(from.height),
    bar: style(bar, ["cursor", "backgroundColor", "paddingLeft", "minHeight", "borderBottomWidth", "borderBottomColor", "userSelect"]),
    toggle: style(toggle, ["cursor", "color", "fontFamily", "fontSize", "columnGap", "backgroundColor", "borderTopWidth"]),
    name: style(name, ["fontWeight", "fontSize", "color"]),
    glyphPaint: style(glyph, ["color", "strokeWidth", "transform", "transitionDuration", "transitionProperty"]),
    travel: style(body, ["transitionDuration", "transitionProperty", "interpolateSize"]),
  };
})()`;

/** How the card *card* finds stands, once its body and its chevron have come to rest. */
const STANDS = (card) => `(() => {
  const section = (${card});
  const bar = section.querySelector(".diff-file-bar");
  const toggle = bar.querySelector(".diff-file-toggle");
  const body = section.querySelector(".diff-file-body");
  const glyph = toggle.querySelector("svg");
  const moving = [body, glyph].some((node) => node.getAnimations().length > 0);
  return {
    moving,
    said: toggle.getAttribute("aria-expanded"),
    bodyHeight: Math.round(body.getBoundingClientRect().height),
    bodyShown: getComputedStyle(body).visibility,
    turn: getComputedStyle(glyph).transform,
    barBorder: getComputedStyle(bar).borderBottomWidth,
    focused: document.activeElement === toggle,
  };
})()`;

/** What scrolls the guide's card, and the card's bar. */
const SCROLLER = `(() => {
  const bar = (${GUIDE_CARD}).querySelector(".diff-file-bar");
  let scroller = bar.parentElement;
  while (scroller !== null && !(/(auto|scroll)/.test(getComputedStyle(scroller).overflowY) && scroller.scrollHeight > scroller.clientHeight)) {
    scroller = scroller.parentElement;
  }
  return { bar, scroller: scroller ?? document.scrollingElement };
})()`;
/** Where the bar of the guide's card is in the document, and where its scroller stands. */
const PLACE = `(() => {
  const { bar, scroller } = ${SCROLLER};
  const top = bar.getBoundingClientRect().top;
  return {
    top: Math.round(top * 10) / 10,
    scroll: Math.round(scroller.scrollTop * 10) / 10,
    room: Math.round((scroller.scrollHeight - scroller.clientHeight) * 10) / 10,
  };
})()`;

// A window short enough that a step scrolls, so folding has a place to lose.
const chrome = await launchChrome(process.env.CHROME_BIN, {
  profiles: process.env.CHROME_PROFILES,
  width: 1100,
  height: 520,
});
try {
  const { evaluate } = chrome;
  const waitFor = (expression) => chrome.waitFor(expression, STEP_MS);
  const go = async (route) => {
    await chrome.send("Page.navigate", { url: `${base}${route}` });
    await waitFor(`location.pathname === ${JSON.stringify(route)}`);
  };
  const shot = async (name) => {
    if (SHOTS) {
      const { data } = await chrome.send("Page.captureScreenshot", { format: "png" });
      fs.writeFileSync(path.join(SHOTS, `guide-file-${name}.png`), Buffer.from(data, "base64"));
    }
  };
  /** The card at rest, after a press: nothing of it still travelling. */
  const rest = async (card) => {
    await waitFor(`${STANDS(card)}.moving === false`);
    return evaluate(STANDS(card));
  };
  /** A real press on the middle of what *expression* finds. The point is measured in one
   * protocol call and pressed in the next, so the caller makes sure beforehand that nothing
   * is still to move the target between the two: what moved it in Changes was a rendered
   * layer landing above it (the head of this file). *between* runs after the measurement
   * and before the press, where a check puts the arrival it must have waited out. */
  const press = async (expression, between = async () => {}) => {
    const point = await evaluate(`(() => {
      const target = (${expression});
      const rect = target.getBoundingClientRect();
      const x = rect.left + rect.width / 2;
      const y = rect.top + rect.height / 2;
      const hit = document.elementFromPoint(x, y);
      return { x, y, hits: hit !== null && target.contains(hit), hit: hit?.className ?? null };
    })()`);
    if (!point.hits) {
      throw new Error(`a press at ${point.x}, ${point.y} would land on ${point.hit}`);
    }
    await between();
    for (const type of ["mousePressed", "mouseReleased"]) {
      await chrome.send("Input.dispatchMouseEvent", {
        x: point.x,
        y: point.y,
        type,
        button: "left",
        clickCount: 1,
      });
    }
  };
  const key = async (name, code, text) => {
    await chrome.send("Input.dispatchKeyEvent", {
      type: "keyDown",
      key: name,
      code,
      windowsVirtualKeyCode: name === "Enter" ? 13 : 32,
      ...(text === undefined ? {} : { text }),
    });
    await chrome.send("Input.dispatchKeyEvent", {
      type: "keyUp",
      key: name,
      code,
      windowsVirtualKeyCode: name === "Enter" ? 13 : 32,
    });
  };
  await chrome.send("Page.enable");

  // Changes' own file card, which the guide's must match, open and folded.
  /** @type {Record<string, unknown>} */
  let changesOpen = {};
  /** @type {Record<string, unknown>} */
  let changesFolded = {};
  if (!SHOTS_ONLY) {
    // The rendered layers' answers are held here, so Changes shows without them, as it does
    // when the server is slow, and are let go after `RENDERED_HOLD_MS` or at the press,
    // whichever is first.
    /** @type {string[]} */
    const held = [];
    let holding = true;
    chrome.on("Fetch.requestPaused", (params) => {
      if (holding) {
        held.push(params.requestId);
      } else {
        void chrome.send("Fetch.continueRequest", { requestId: params.requestId });
      }
    });
    const letGo = async () => {
      holding = false;
      for (const requestId of held.splice(0)) {
        await chrome.send("Fetch.continueRequest", { requestId });
      }
    };
    await chrome.send("Fetch.enable", { patterns: [{ urlPattern: "*pull-rendered-diff*" }] });
    await go(ROUTES.changes);
    await waitFor(`${CHANGES_CARD} !== undefined`);
    check(
      "Changes shows with a rendered layer still on its way, which the check holds",
      held.length > 0 && !(await evaluate(LAYERS_IN)),
      `${held.length} answers held`,
    );
    const release = setTimeout(() => void letGo(), RENDERED_HOLD_MS);
    // Nothing in Changes is measured until every rendered layer is in: one landing later
    // moves the cards under it.
    await waitFor(LAYERS_IN);
    // The card found is the one measured throughout, folded too, when it no longer has rows
    // with height to be found by.
    await evaluate(`(${CHANGES_CARD}).setAttribute("data-fold-measured", "")`);
    const measured = `document.querySelector("[data-fold-measured]")`;
    await evaluate(`${measured}.querySelector(".diff-file-bar").scrollIntoView({block: "center"})`);
    await evaluate("document.fonts.ready.then(() => true)");
    changesOpen = { bar: await evaluate(BAR(measured)), stands: await rest(measured) };
    // Where each click on the page lands, so a press that folds nothing says what it hit.
    await evaluate(`(() => {
      window.__foldClicks = [];
      document.addEventListener("click", (event) => window.__foldClicks.push(event.target.className), true);
    })()`);
    // Had a layer still been on its way at the measurement, it lands here, before the press.
    await press(`${measured}.querySelector(".diff-file-bar .diff-file-path")`, async () => {
      clearTimeout(release);
      await letGo();
      await waitFor(LAYERS_IN);
    });
    await chrome.send("Fetch.disable");
    changesFolded = { bar: await evaluate(BAR(measured)), stands: await rest(measured) };
    check(
      "Changes' file folds at a press on its bar",
      changesFolded.stands.said === "false",
      `clicks landed on ${JSON.stringify(await evaluate("window.__foldClicks"))}; the card is ${JSON.stringify(changesFolded.stands)}`,
    );
  }

  // The guide: the first step that draws a diff.
  await go(ROUTES.guide);
  await waitFor(
    `document.querySelector(".github-pull-guide-step:not(.github-pull-guide-incoming)") !== null && document.querySelector(".github-pull-guide-steps-link") !== null`,
  );
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
  await evaluate("document.fonts.ready.then(() => true)");
  // Scrolled as far as leaves the page room to stay there once the card's body is gone, so
  // a place lost to folding shows as one, apart from a scroller with nowhere left to be.
  await evaluate(`(() => {
    const { scroller } = ${SCROLLER};
    const body = (${GUIDE_CARD}).querySelector(".diff-file-body").getBoundingClientRect().height;
    scroller.scrollTop = scroller.scrollHeight - scroller.clientHeight - body - 8;
  })()`);
  await shot("open");
  if (SHOTS_ONLY) {
    process.stdout.write(`guided review fold in Chrome: pictures only\n`);
  } else {
    // 1 and 2. The bar is Changes' bar, open.
    const guideOpen = { bar: await evaluate(BAR(GUIDE_CARD)), stands: await rest(GUIDE_CARD) };
    same("the card's trigger is Changes' trigger", guideOpen.bar.trigger, changesOpen.bar.trigger);
    check("the trigger leads the bar", guideOpen.bar.leads === true);
    for (const part of ["chevron", "glyph", "triggerStart", "nameY", "barHeight"]) {
      same(
        `open, the bar's ${part} is where Changes' is`,
        guideOpen.bar[part],
        changesOpen.bar[part],
      );
    }
    check(
      "the chevron is drawn: a glyph with a box",
      (guideOpen.bar.glyph?.w ?? 0) > 0 && (guideOpen.bar.glyph?.h ?? 0) > 0,
      JSON.stringify(guideOpen.bar.glyph),
    );
    for (const part of ["bar", "toggle", "name", "glyphPaint", "travel"]) {
      same(`open, the ${part} is painted as Changes'`, guideOpen.bar[part], changesOpen.bar[part]);
    }
    same(
      "the card starts open, as Changes' file does",
      guideOpen.stands.said,
      changesOpen.stands.said,
    );
    same(
      "open, the chevron is turned as Changes' is",
      guideOpen.stands.turn,
      changesOpen.stands.turn,
    );
    check("open, the body has height", guideOpen.stands.bodyHeight > 0);

    // 3 and 4. A press on the bar's free space folds the card where it is.
    const before = await evaluate(PLACE);
    await press(`(${GUIDE_CARD}).querySelector(".diff-file-bar .diff-file-path")`);
    const folded = await rest(GUIDE_CARD);
    const foldedBar = await evaluate(BAR(GUIDE_CARD));
    const after = await evaluate(PLACE);
    await shot("folded");
    same(
      "a press on the bar folds the card as it folds Changes' file",
      [folded.said, folded.bodyHeight, folded.bodyShown, folded.turn, folded.barBorder],
      [
        changesFolded.stands.said,
        changesFolded.stands.bodyHeight,
        changesFolded.stands.bodyShown,
        changesFolded.stands.turn,
        changesFolded.stands.barBorder,
      ],
    );
    check("folded, the body has no height", folded.bodyHeight === 0, String(folded.bodyHeight));
    check(
      "the chevron turned",
      folded.turn !== guideOpen.stands.turn,
      `${guideOpen.stands.turn} then ${folded.turn}`,
    );
    for (const part of ["chevron", "glyph", "triggerStart", "nameY", "barHeight"]) {
      same(
        `folded, the bar's ${part} is where Changes' is`,
        foldedBar[part],
        changesFolded.bar[part],
      );
    }
    // The bar keeps its place in the document, and the scroller stays while it has room to.
    same(
      "folding leaves the bar where it was in the document",
      Math.round((after.top + after.scroll) * 10) / 10,
      Math.round((before.top + before.scroll) * 10) / 10,
    );
    check(
      "and the scroller where it was, while it has room",
      after.scroll === Math.min(before.scroll, after.room),
      JSON.stringify({ before, after }),
    );
    check(
      "the step still scrolls when folded, so the reader's place was kept, not clamped",
      before.scroll > 0 && after.scroll === before.scroll,
      JSON.stringify({ before, after }),
    );

    // Enter and Space on the trigger, which keeps the focus.
    await evaluate(
      `(${GUIDE_CARD}).querySelector(".diff-file-toggle").focus({preventScroll: true})`,
    );
    await key("Enter", "Enter", "\r");
    const entered = await rest(GUIDE_CARD);
    same(
      "Enter on the trigger opens the card, and keeps the focus",
      [entered.said, entered.focused],
      ["true", true],
    );
    check(
      "open again, the body is as tall as it was",
      entered.bodyHeight === guideOpen.stands.bodyHeight,
      `${entered.bodyHeight}, was ${guideOpen.stands.bodyHeight}`,
    );
    const reopened = await evaluate(PLACE);
    same(
      "opening leaves the bar where it was",
      [reopened.top, reopened.scroll],
      [before.top, before.scroll],
    );
    await key(" ", "Space", " ");
    const spaced = await rest(GUIDE_CARD);
    same(
      "Space on the trigger folds it, and keeps the focus",
      [spaced.said, spaced.focused],
      ["false", true],
    );
    await key(" ", "Space", " ");
    same("and opens it", (await rest(GUIDE_CARD)).said, "true");

    // A press on Open full diff is the link's: the card stays as it is while the page goes.
    const link = `(${GUIDE_CARD}).querySelector(".diff-file-bar a.diff-file-view")`;
    if (await evaluate(`${link} !== null`)) {
      await evaluate(`(() => {
        window.__foldAtLeave = null;
        const card = (${GUIDE_CARD});
        (${link}).addEventListener("click", () => {
          queueMicrotask(() => {
            window.__foldAtLeave = card.querySelector(".diff-file-toggle").getAttribute("aria-expanded");
          });
        });
      })()`);
      await press(link);
      await waitFor("window.__foldAtLeave !== null");
      same(
        "a press on Open full diff does not fold the card",
        await evaluate("window.__foldAtLeave"),
        "true",
      );
    }
    process.stdout.write(
      failures.length > 0 ? "" : `guided review fold in Chrome: ${checks} checks passed\n`,
    );
  }
} finally {
  await chrome.close();
}
if (failures.length > 0) {
  process.stderr.write(`${failures.join("\n")}\n`);
  process.exitCode = 1;
}

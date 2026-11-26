// A native stack's page in headless Chrome while its stack moves: when the notice of a new
// comparison shows, what it says, and that its button draws the new comparison.
//
//   CHROME_BIN=... CHROME_PROFILES=<dir> STACK_ANSWERS=<file> STACK_MOVED=<file> \
//     [SHOTS_DIR=<dir>] node tests/dom/github-stack-page-notice-chrome.mjs <server base URL>
//
// tests/test_github_stack_page_chrome.py serves the stand-in's home with a fake `gh` whose
// answers are STACK_ANSWERS, where `gh stack` answers #70 as 8, then 10; STACK_MOVED is the
// same answers with #70 as 10 alone. This moves the stack by writing one over the other and
// asking the server to read the stacks again, as the Pulls tab's refresh does, and the page
// reads the move on its own poll:
//
// 1. Before the reader does anything on the page, 8 leaves: the page is catching up, so the
//    new comparison is drawn with no notice.
// 2. The reader scrolls the page, then 8 joins again: the comparison looks different, so it
//    is offered, not drawn, and the notice names #8. Its words are the browserless golden's.
// 3. The reader presses Show the new comparison: the body is drawn at it, and the notice
//    goes.
//
// What the rule decides is the browserless session's (tests/dom/github-stack-page-session.js,
// `answerAction`); this holds the page's glue to it in a real browser: that a press or a wheel
// is what counts as the reader's, that the poll asks `since` the comparison drawn, that the
// notice lands in the status line, and that the button draws again. With SHOTS_DIR it saves a
// screenshot of each step. Each step writes `phase <name> <ms since start>` to stderr.
import fs from "node:fs";
import path from "node:path";
import { launchChrome } from "./chrome-session.mjs";

const [base] = process.argv.slice(2);
const ANSWERS = process.env.STACK_ANSWERS;
const MOVED = process.env.STACK_MOVED;
if (!base || !process.env.CHROME_BIN || !process.env.CHROME_PROFILES || !ANSWERS || !MOVED) {
  throw new Error(
    "usage: CHROME_BIN CHROME_PROFILES STACK_ANSWERS STACK_MOVED github-stack-page-notice-chrome.mjs <base URL>",
  );
}
const SHOTS = process.env.SHOTS_DIR ?? null;
const started = Date.now();
const phase = (name) => process.stderr.write(`phase ${name} ${Date.now() - started}\n`);
// Each wait's bound: the stacks' refresh through the fake gh, then the page's next poll, at
// the top member's probe interval (5 s, `ATTENDED_PROBE_S` in served_pull.py), on a loaded
// machine. Chrome's start is bounded in chrome-session.mjs.
const STEP_MS = 45000;

const failures = [];
let checks = 0;
const check = (label, ok, detail = "") => {
  checks += 1;
  if (!ok) {
    failures.push(`${label}${detail ? `: ${detail}` : ""}`);
  }
};

const together = fs.readFileSync(ANSWERS);
const apart = fs.readFileSync(MOVED);

const chrome = await launchChrome(process.env.CHROME_BIN, {
  profiles: process.env.CHROME_PROFILES,
  width: 1280,
  height: 900,
});
const measured = {};
try {
  phase("chrome");
  const { evaluate, send } = chrome;
  const pageErrors = [];
  chrome.on("Runtime.exceptionThrown", ({ exceptionDetails }) =>
    pageErrors.push(exceptionDetails.exception?.description ?? exceptionDetails.text),
  );
  await send("Runtime.enable");
  // What the page shows: its members, the status line's words and whether it offers the new
  // comparison, and whether the body's drawing is the one marked before the stack moved.
  const SHOWN = `(() => {
    const page = document.querySelector(".github-pull-stack-page");
    const status = page?.querySelector(".github-pull-status") ?? null;
    const drawn = page?.querySelector(".github-pull-body > .github-pull-diff") ?? null;
    return {
      members: [...(page?.querySelectorAll(".github-pull-stack-members .github-pull-stack-member") ?? [])]
        .map((row) => row.innerText.replace(/\\s+/g, " ").trim()),
      status: status === null || status.hidden ? null : status.innerText.replace(/\\s+/g, " ").trim(),
      offered: status?.querySelector(".github-pull-stack-take") != null,
      marked: drawn?.dataset.checkDrawn ?? null,
      ready: drawn !== null && page.querySelector(".github-pull-diff-holding, .github-pull-diff-loading") === null &&
        page.querySelector(".github-pull-summary .diff-summary") !== null,
    };
  })()`;
  const shown = () => evaluate(SHOWN);
  const waitFor = async (expression) => {
    try {
      return await chrome.waitFor(expression, STEP_MS);
    } catch (error) {
      const stack = await evaluate(
        `fetch("/api/plugin/github/stack?number=70", {cache: "no-store"}).then((r) => r.text()).then((t) => t.slice(0, 1500))`,
      );
      throw new Error(
        `${error.message}\nshown: ${JSON.stringify(await shown())}\nstack 70: ${stack}\npage errors: ${pageErrors.join("\n")}`,
      );
    }
  };
  const frames = () =>
    evaluate("new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)))");
  const shot = async (name) => {
    if (SHOTS === null) {
      return;
    }
    await frames();
    const { data } = await send("Page.captureScreenshot", { format: "png" });
    fs.mkdirSync(SHOTS, { recursive: true });
    fs.writeFileSync(path.join(SHOTS, `${name}.png`), Buffer.from(data, "base64"));
  };
  /** Mark the body's drawing, so a step can tell whether the page drew it again. */
  const mark = (name) =>
    evaluate(
      `document.querySelector(".github-pull-stack-page .github-pull-body > .github-pull-diff").dataset.checkDrawn = ${JSON.stringify(name)}`,
    );
  /** Move the stack: the fake gh answers *answers*, and the server reads the stacks again. */
  const move = async (answers) => {
    fs.writeFileSync(ANSWERS, answers);
    const status = await evaluate(
      `fetch("/api/plugin/github/stacks-refresh", {method: "POST", headers: {"content-type": "application/json"}, body: JSON.stringify({retry: true})}).then((r) => r.status)`,
    );
    check("the stacks are read again", status === 200 || status === 202, String(status));
  };
  /** The centre of the element *selector* names, in the viewport. */
  const centre = (selector) =>
    evaluate(`(() => {
      const box = document.querySelector(${JSON.stringify(selector)}).getBoundingClientRect();
      return { x: Math.round(box.left + box.width / 2), y: Math.round(box.top + box.height / 2) };
    })()`);

  await send("Page.navigate", { url: `${base}/stack/70/changes` });
  await waitFor(`(${SHOWN}).ready && (${SHOWN}).members.length === 2`);
  await frames();
  phase("opened");
  measured.opened = await shown();
  await mark("first");

  // 1. Before the reader does anything, 8 leaves: drawn at once, with no notice.
  await move(apart);
  await waitFor(
    `(${SHOWN}).members.length === 1 && (${SHOWN}).ready && (${SHOWN}).marked === null`,
  );
  phase("caught up");
  measured.caught_up = await shown();
  check(
    "before the reader's move, a new comparison is drawn with no notice",
    measured.caught_up.status === null && !measured.caught_up.offered,
    JSON.stringify(measured.caught_up),
  );
  await shot("notice-1-caught-up");

  // 2. The reader scrolls the page, then 8 joins again: offered, saying so, and not drawn.
  await mark("second");
  const body = await centre(".github-pull-stack-page .github-pull-body");
  await send("Input.dispatchMouseEvent", {
    type: "mouseWheel",
    x: body.x,
    y: body.y,
    deltaX: 0,
    deltaY: 120,
  });
  await move(together);
  await waitFor(`(${SHOWN}).offered`);
  phase("offered");
  measured.offered = await shown();
  check(
    "after the reader's move, a notice names 8 and offers the new comparison",
    measured.offered.status?.includes("#8") === true && measured.offered.offered,
    JSON.stringify(measured.offered),
  );
  check(
    "the comparison offered is not drawn under the reader",
    measured.offered.marked === "second",
    JSON.stringify(measured.offered),
  );
  check(
    "the header lists the members as they are now",
    measured.offered.members.length === 2,
    JSON.stringify(measured.offered.members),
  );
  const asked = await evaluate(
    `performance.getEntriesByType("resource").map((entry) => entry.name).filter((name) => name.includes("/api/plugin/github/stack?"))`,
  );
  check(
    "the poll asks since the comparison drawn",
    asked.some((name) => /&since=[0-9a-f]{32}$/.test(name)),
    JSON.stringify(asked.slice(-3)),
  );
  await shot("notice-2-offered");

  // 3. The reader presses Show the new comparison: drawn, and the notice goes.
  const take = await centre(".github-pull-status .github-pull-stack-take");
  for (const type of ["mousePressed", "mouseReleased"]) {
    await send("Input.dispatchMouseEvent", {
      type,
      x: take.x,
      y: take.y,
      button: "left",
      clickCount: 1,
    });
  }
  await waitFor(`(${SHOWN}).ready && (${SHOWN}).marked === null && !(${SHOWN}).offered`);
  phase("taken");
  measured.taken = await shown();
  check(
    "the button draws the new comparison and the notice goes",
    measured.taken.status === null && measured.taken.members.length === 2,
    JSON.stringify(measured.taken),
  );
  await shot("notice-3-taken");

  check("no script error on the page", pageErrors.length === 0, pageErrors.join("\n"));
} finally {
  fs.writeFileSync(ANSWERS, together);
  await chrome.close();
}
if (process.env.MEASURE_OUT) {
  fs.writeFileSync(process.env.MEASURE_OUT, `${JSON.stringify(measured, null, 2)}\n`);
}
if (failures.length > 0) {
  process.stderr.write(`${failures.join("\n")}\n`);
  process.exit(1);
}
process.stdout.write(`stack page notice in Chrome: ${checks} checks passed\n`);

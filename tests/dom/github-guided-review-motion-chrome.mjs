// Guided Review holds still in headless Chrome: from the first frame a step shows to the frame
// it settles in, nothing it shows moves or changes size, and the step a reader leaves stays as
// it was until the next one replaces it whole. Against a live `metab` server serving the GitHub
// stand-in.
//
//   CHROME_BIN=... CHROME_PROFILES=<dir> \
//     node tests/dom/github-guided-review-motion-chrome.mjs <base URL> pull|stack
//
// `pull` measures pull request 7, whose guide ends on a step citing a Markdown and a YAML file
// whole (the stand-in's `--guided-documents`); `stack` measures the guide of stack 70, whose
// second step cites a Markdown file whole (`--guided-stack`, with the native stacks of
// tests/test_github_stack_page_chrome.py). tests/test_github_guided_review_chrome.py builds the
// server, owns the profile directory, and stops this process's whole group, Chrome included,
// however the run ends (tests/process_group.py).
//
// Each recording samples the guide every animation frame, as the stack page's check samples
// its page (tests/dom/github-stack-page-chrome.mjs): the box of each part of the guide, of the
// step's card, its notes, its references, and its documents' files, and whether a loading
// block or the arrows' waiting mark shows. A recording starts before the reader's press, or
// with the document for a page load, and ends once the guide waits for nothing, no step out
// of sight and no loading state, and nothing has changed for `SETTLE_MS` since.
// The guide is measured cold, with nothing read ahead: a page loaded on Guided Review, and a
// step the guide has not read; and warm: Guided Review opened once the page has read its first
// step ahead, a step next to the one shown, and the tab again after another, where a warm
// guide must show no loading state at all, but for the arrows' delayed mark while a step's
// documents draw, which are drawn as it shows and not read ahead (mb-ukmm). Browserless,
// what is read ahead and kept is pinned in github-guided-review-session.js and
// github-guided-review-mount-behavior.js.
//
// Each step writes `phase <name> <ms since start>` to stderr, so a slow run says where.
import fs from "node:fs";
import { launchChrome } from "./chrome-session.mjs";

const [base, mode] = process.argv.slice(2);
if (!base || !["pull", "stack"].includes(mode ?? "")) {
  throw new Error(
    "usage: CHROME_BIN CHROME_PROFILES github-guided-review-motion-chrome.mjs <base> pull|stack",
  );
}
if (!process.env.CHROME_BIN || !process.env.CHROME_PROFILES) {
  throw new Error("CHROME_BIN and CHROME_PROFILES are required");
}
const started = Date.now();
const phase = (name) => process.stderr.write(`phase ${name} ${Date.now() - started}\n`);
// One page load, a guide's read, or a member's fetch through the fake gh; a loaded machine has
// needed several seconds for one.
const STEP_MS = 45000;
// A recording ends once the guide waits for nothing and its frames have not changed for this
// long: past the longest wait a step's parts have between them once it shows, a document's
// rendered layer, which a loaded machine has taken over a second to answer.
const SETTLE_MS = 2500;
// And at most this long after the press.
const RECORD_MS = 30000;
// How long a page may take to read a step ahead of the reader: its idle callback's timeout
// (`PREFETCH_IDLE_TIMEOUT_MS` in pull-page.js) and one read of the guide, which a loaded
// machine has taken seconds to answer.
const READ_AHEAD_MS = 15000;

const failures = [];
let checks = 0;
const check = (label, ok, detail = "") => {
  checks += 1;
  if (!ok) {
    failures.push(`${label}${detail ? `: ${detail}` : ""}`);
  }
};

// In the page, from the document's start: a recorder of what the guide shows. `start()`
// samples at once, so a recording's first frame is what the reader saw before the press, then
// every animation frame, and keeps a frame wherever any part changed.
const RECORDER = `(() => {
  const describe = (node) =>
    node.tagName.toLowerCase() + [...node.classList].slice(0, 2).map((c) => "." + c).join("");
  // [top, height], "hidden" while held out of sight; null while not laid out.
  const box = (el) => {
    if (!el) return null;
    const b = el.getBoundingClientRect();
    if (b.width === 0 || b.height === 0) return null;
    const hidden = getComputedStyle(el).visibility === "hidden";
    return [Math.round(b.top), Math.round(b.height)].concat(hidden ? ["hidden"] : []);
  };
  const shows = (el) => { const at = box(el); return at !== null && at[2] !== "hidden"; };
  const state = { frames: [], last: "", t0: 0, on: false };
  const sample = () => {
    const host = document.querySelector(".github-pull-guided-review");
    const parts = host === null ? [] : [...host.children]
      .filter((child) => !child.classList.contains("github-pull-guide-incoming") &&
        !child.classList.contains("mb-delayed-loading"))
      .map((child, at) => [at + " " + describe(child), box(child)]);
    const detail = host?.querySelector(":scope > .github-pull-guide-step:not(.github-pull-guide-incoming)") ?? null;
    const pieces = detail === null ? [] : [...detail.querySelectorAll(
      ".github-pull-guide-card, .kpress-prose, .github-pull-guide-reference, .diff-file, .diff-markdown, .diff-structured",
    )].map((piece, at) => [at + " " + describe(piece) + " " +
      (piece.querySelector(".diff-file-path")?.textContent ?? ""), box(piece)]);
    const outline = host?.querySelector(":scope > .github-pull-guide-outline") ?? null;
    const key = !shows(outline) ? null :
      (outline.querySelector(".github-pull-guide-position")?.textContent ?? "") + " / " +
      (detail?.querySelector(".github-pull-guide-title")?.textContent ?? "no step");
    const frame = {
      key,
      loading: shows(host?.querySelector(":scope > .mb-delayed-loading") ?? null),
      waiting: shows(host?.querySelector(".github-pull-guide-waiting") ?? null),
      parts,
      pieces,
    };
    const signature = JSON.stringify(frame);
    if (signature !== state.last) {
      state.last = signature;
      state.frames.push({ t: Math.round(performance.now() - state.t0), ...frame });
    }
  };
  const loop = () => {
    if (!state.on) return;
    sample();
    requestAnimationFrame(loop);
  };
  window.__guideMotion = {
    start() {
      state.frames = [];
      state.last = "";
      state.t0 = performance.now();
      sample();
      if (!state.on) {
        state.on = true;
        requestAnimationFrame(loop);
      }
    },
    count: () => state.frames.length,
    t0: () => state.t0,
    stop() {
      state.on = false;
      return state.frames;
    },
  };
  window.__guideMotion.start();
})()`;

/**
 * What moved in a recording: a frame of the settled step whose parts are not where, or not
 * the size, they settle at, or that lacks one the settled step has; before the settled step
 * shows, a frame where the step the reader left changed, or, on a tab or page opening, where
 * part of the guide showed; and, warm, any frame that shows a loading state, or, for a step
 * whose answer is in hand and whose documents draw as it is shown (`"documents"`), the
 * loading block, since only the arrows' delayed mark may say its documents are on their way.
 *
 * @param {Array<{t: number, key: string | null, loading: boolean, waiting: boolean,
 *   parts: Array<[string, unknown]>, pieces: Array<[string, unknown]>}>} frames
 * @param {boolean | "documents"} warm
 */
function motion(frames, warm) {
  const settled = frames.at(-1);
  if (settled === undefined || settled.key === null) {
    return ["the guide never showed"];
  }
  const out = [];
  const json = (value) => JSON.stringify(value);
  const visible = (at) => at !== null && at[2] !== "hidden";
  /** Where *frame*'s parts differ from *want*'s. */
  const differs = (frame, want) => {
    const said = [];
    for (const field of ["parts", "pieces"]) {
      const have = new Map(frame[field]);
      const wanted = new Map(want[field]);
      for (const [name, at] of wanted) {
        if (!have.has(name)) {
          if (visible(at)) {
            said.push(`${frame.t} ms: ${name} not yet shown, settles at ${json(at)}`);
          }
        } else if (json(have.get(name)) !== json(at)) {
          said.push(`${frame.t} ms: ${name} at ${json(have.get(name))}, settles at ${json(at)}`);
        }
      }
      for (const [name, at] of have) {
        if (!wanted.has(name) && visible(at)) {
          said.push(`${frame.t} ms: ${name} at ${json(at)} is not in the settled step`);
        }
      }
    }
    return said;
  };
  const first = frames.findIndex((frame) => frame.key === settled.key);
  for (const frame of frames.slice(first)) {
    out.push(...differs(frame, settled));
    if (frame.loading || frame.waiting) {
      out.push(`${frame.t} ms: a loading state shows with ${frame.key}`);
    }
  }
  const before = frames[0];
  for (const frame of frames.slice(1, first)) {
    if (before.key === null) {
      const shown = [...frame.parts, ...frame.pieces].filter(([, at]) => visible(at));
      if (frame.key !== null || shown.length > 0) {
        out.push(
          `${frame.t} ms: ${frame.key ?? shown.map(([name]) => name).join(", ")} shows before ${settled.key}`,
        );
      }
    } else if (frame.key !== before.key) {
      out.push(`${frame.t} ms: ${frame.key} shows between ${before.key} and ${settled.key}`);
    } else {
      out.push(...differs(frame, before));
    }
  }
  if (warm !== false) {
    for (const frame of frames.filter((each) => each.loading || (warm === true && each.waiting))) {
      out.push(`${frame.t} ms: a loading state shows, warm`);
    }
  }
  return [...new Set(out)];
}

const chrome = await launchChrome(process.env.CHROME_BIN, {
  profiles: process.env.CHROME_PROFILES,
});
/** Each recording, by name: its frames' count, when the settled step first showed, and what
 * moved. */
const measured = {};
try {
  phase("chrome");
  const { evaluate, send } = chrome;
  const pageErrors = [];
  chrome.on("Runtime.exceptionThrown", ({ exceptionDetails }) =>
    pageErrors.push(exceptionDetails.exception?.description ?? exceptionDetails.text),
  );
  await send("Runtime.enable");
  await send("Page.enable");
  await send("Page.addScriptToEvaluateOnNewDocument", { source: RECORDER });
  const waitFor = (expression) => chrome.waitFor(expression, STEP_MS);
  const go = (route) => send("Page.navigate", { url: `${base}${route}` });
  /** Whether the page has read *query* of the guide's route, its answer in. */
  const read = (query) =>
    `performance.getEntriesByType("resource").some((entry) => entry.name.includes("/api/plugin/github/guided-review?") && entry.name.includes(${JSON.stringify(query)}) && entry.responseEnd > 0)`;
  const loaded = `performance.getEntriesByType("resource").some((entry) => /\\/guided-review\\.js$/.test(new URL(entry.name).pathname) && entry.responseEnd > 0)`;
  const position = `document.querySelector(".github-pull-guided-review .github-pull-guide-position")?.textContent ?? ""`;
  /**
   * Whether the guide still waits for what it shows: not mounted yet, its loading block shown,
   * a step composed out of sight (`.github-pull-guide-incoming`, which the frames leave out
   * and which may wait `GUIDE_DOCUMENT_HOLD_MS` for a document), or the arrows' waiting mark
   * on. A quiet stretch of frames while it does says nothing about where the guide settles.
   */
  const WAITS = `(() => {
    const host = document.querySelector(".github-pull-guided-review");
    const mark = host?.querySelector(".github-pull-guide-waiting") ?? null;
    return host === null ||
      host.querySelector(":scope > .github-pull-guide-incoming, :scope > .mb-delayed-loading") !== null ||
      (mark !== null && !mark.hidden);
  })()`;
  /**
   * Wait until the guide waits for nothing and the recording has not changed for SETTLE_MS
   * since, or RECORD_MS has passed, then end it.
   */
  const settle = async (name, warm) => {
    const began = Date.now();
    let count = -1;
    let quiet = 0;
    for (;;) {
      await new Promise((resolve) => setTimeout(resolve, 250));
      const frames = await evaluate("window.__guideMotion.count()");
      quiet = frames === count && !(await evaluate(WAITS)) ? quiet + 250 : 0;
      count = frames;
      if (quiet >= SETTLE_MS || Date.now() - began >= RECORD_MS) {
        break;
      }
    }
    const frames = await evaluate("window.__guideMotion.stop()");
    const moved = motion(frames, warm);
    const settled = frames.at(-1);
    measured[name] = {
      frames: frames.length,
      shows: settled?.key ?? null,
      first_shown_ms: frames.find((frame) => frame.key === settled?.key)?.t ?? null,
      settled_ms: settled?.t ?? null,
      loading_shown: frames.some((frame) => frame.loading || frame.waiting),
      moved,
      // The requests behind it, by when each started and ended since the recording began.
      requests: await evaluate(`performance.getEntriesByType("resource")
        .filter((entry) => /guided-review|pull-markdown|pull-rendered|kpress|diff/.test(entry.name))
        .map((entry) => [Math.round(entry.startTime - window.__guideMotion.t0()), Math.round(entry.responseEnd - window.__guideMotion.t0()), new URL(entry.name).pathname.split("/").slice(-1)[0] + new URL(entry.name).search.slice(0, 40), entry.serverTiming.map((timing) => timing.name + "=" + Math.round(timing.duration)).join(",")])
        .filter(([, end]) => end >= -50)`),
    };
    phase(`recorded ${name}: ${frames.length} frames`);
    check(
      `${name}: nothing moves from its first paint`,
      moved.length === 0,
      moved.slice(0, 6).join("; "),
    );
    return settled;
  };
  /** Record *press*, from just before it until the guide settles. */
  const record = async (name, warm, press) => {
    await evaluate(`window.__guideMotion.start(); ${press}`);
    return settle(name, warm);
  };
  const tab = (label) =>
    `[...document.querySelectorAll(".github-pull .tab-bar .tab-btn, .github-pull-stack-page .tab-bar .tab-btn")].find((link) => link.textContent.trim() === ${JSON.stringify(label)}).click()`;
  const arrow = (label) =>
    `document.querySelector('.github-pull-guided-review .github-pull-guide-arrows [aria-label="${label}"]').click()`;
  const listed = (step) =>
    `[...document.querySelectorAll(".github-pull-guide-steps-link")].find((link) => link.querySelector(".github-pull-guide-steps-number")?.textContent === ${JSON.stringify(String(step))}).click()`;
  /** Whether the page has read *expression*'s step ahead of the reader, checked as *label*:
   * a page that does not fails the check, and what follows is recorded as cold. */
  const ahead = async (label, expression) => {
    try {
      await chrome.waitFor(expression, READ_AHEAD_MS);
      check(label, true);
      return true;
    } catch {
      check(label, false, `not read within ${READ_AHEAD_MS} ms`);
      return false;
    }
  };
  const count = async () =>
    Number((await evaluate(position)).match(/of (\d+)/)?.[1] ?? 0) ||
    evaluate(`document.querySelectorAll(".github-pull-guide-steps-number").length`);

  if (mode === "pull") {
    // Cold: a page loaded on Guided Review, the front page of a pull request with a guide.
    await go("/pull/7");
    await waitFor(`window.__guideMotion !== undefined && (${position}) !== ""`);
    const opened = await settle("pull: the page opens on Guided Review, cold", false);
    check("the page opens on the overview", /^Overview/.test(opened?.key ?? ""), opened?.key);
    // Warm: step 1 is the overview's own answer.
    await record("pull: Next to step 1, warm", true, arrow("Next step"));
    // Cold: the last step, from the list, two moves from step 1, which only the step after
    // step 1 is read ahead of. It cites the guide's documents.
    const second = await ahead("step 2 is read ahead", read("number=7&step=2"));
    const last = await count();
    check("the guide has a step two moves past step 1", last >= 3, String(last));
    check("the last step is not read ahead", !(await evaluate(read(`number=7&step=${last}`))));
    const lastShown = await record("pull: the last step from the list, cold", false, listed(last));
    check(
      "the last step cites its documents",
      (lastShown?.pieces ?? []).some(([name]) => name.includes("diff-file")),
      JSON.stringify(lastShown?.pieces),
    );
    // Warm: the step before it, read ahead of step 1, and the last step again, kept.
    await record("pull: Previous to step 2, read ahead", second, arrow("Previous step"));
    // Its documents are drawn again as it shows (mb-ukmm): the arrows' mark may show.
    await record("pull: Next to the last step again, kept", "documents", arrow("Next step"));
    // Another tab and back: the guide is mounted again over what the document kept.
    await evaluate(tab("Conversation"));
    await waitFor(`document.querySelector(".github-pull-guided-review") === null`);
    await record("pull: Guided Review again, kept", true, tab("Guided Review"));
    // Warm from a new document: Conversation reads the guide's first step and its module
    // when the page is idle.
    await go("/pull/7/conversation");
    await waitFor(
      `location.pathname === "/pull/7/conversation" && document.querySelector(".github-pull-title-text") !== null`,
    );
    const first = await ahead(
      "Conversation reads the guide's first step and its module ahead",
      `${read("number=7&step=1")} && ${loaded}`,
    );
    await record("pull: Guided Review from Conversation, read ahead", first, tab("Guided Review"));
  } else {
    // The stand-in's records and commits, as a reader has them once they have opened the
    // stack's pull requests (tests/dom/github-stack-page-chrome.mjs).
    for (const number of [8, 10]) {
      await go(`/pull/${number}`);
      await waitFor(`document.querySelector(".github-pull-title-text") !== null`);
    }
    await waitFor(
      `fetch("/api/plugin/github/stack?number=70", {cache: "no-store"}).then((r) => r.json()).then((a) => a.state === "current")`,
    );
    phase("members read");
    // Cold: the stack's page loaded on its front page, Guided Review.
    await go("/stack/70");
    await waitFor(`window.__guideMotion !== undefined && (${position}) !== ""`);
    const opened = await settle("stack: the page opens on Guided Review, cold", false);
    check("the page opens on step 1", /^Step 1 of/.test(opened?.key ?? ""), opened?.key);
    const second = await ahead(
      "step 2 is read ahead",
      `performance.getEntriesByType("resource").some((entry) => entry.name.includes("/api/plugin/github/guided-review?stack=70&") && entry.name.includes("step=2") && entry.responseEnd > 0)`,
    );
    // Its answer is read ahead and its document drawn as it shows (mb-ukmm).
    const drafted = await record(
      "stack: Next to its document's step, read ahead",
      second ? "documents" : false,
      arrow("Next step"),
    );
    check(
      "the step cites its document",
      (drafted?.pieces ?? []).some(([name]) => name.includes("diff-file")),
      JSON.stringify(drafted?.pieces),
    );
    await evaluate(tab("Changes"));
    await waitFor(`document.querySelector(".github-pull-guided-review") === null`);
    await record("stack: Guided Review again, kept", true, tab("Guided Review"));
  }
  check("no page error", pageErrors.length === 0, pageErrors.join("\n"));
} finally {
  await chrome.close();
}
process.stderr.write(`${JSON.stringify(measured, null, 2)}\n`);
if (process.env.MEASURE_OUT) {
  fs.writeFileSync(`${process.env.MEASURE_OUT}-${mode}.json`, JSON.stringify(measured, null, 2));
}
if (failures.length > 0) {
  process.stderr.write(`${failures.join("\n")}\n`);
  process.exitCode = 1;
} else {
  process.stdout.write(`guided review motion in Chrome (${mode}): ${checks} checks passed\n`);
}

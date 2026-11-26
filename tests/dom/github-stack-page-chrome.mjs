// A native stack's page laid out by headless Chrome against a live `metab` server serving the
// GitHub stand-in with native stacks.
//
//   CHROME_BIN=... CHROME_PROFILES=<dir> [SHOTS_DIR=<dir>] [MEASURE_OUT=<file>] \
//     node tests/dom/github-stack-page-chrome.mjs <server base URL>
//
// tests/test_github_stack_page_chrome.py serves the stand-in's home with a fake `gh` whose
// `gh stack` answers #70 (8, then 10) and #71 (8, 7, then 10). The test owns the
// profile directory and stops this process's whole group, Chrome included, however the run
// ends (tests/process_group.py). With SHOTS_DIR it saves the screenshots.
//
// Each step writes `phase <name> <ms since start>` to stderr, so a slow run says where.
import fs from "node:fs";
import path from "node:path";
import { launchChrome } from "./chrome-session.mjs";

const [base] = process.argv.slice(2);
if (!base || !process.env.CHROME_BIN || !process.env.CHROME_PROFILES) {
  throw new Error("usage: CHROME_BIN CHROME_PROFILES github-stack-page-chrome.mjs <base URL>");
}
const SHOTS = process.env.SHOTS_DIR ?? null;
const started = Date.now();
const phase = (name) => process.stderr.write(`phase ${name} ${Date.now() - started}\n`);
// Each wait's bound: a paint, or a member's fetch through the fake gh, which the page asks
// for and which takes a few seconds on a loaded machine. Chrome's start is bounded in
// chrome-session.mjs.
const STEP_MS = 45000;

const failures = [];
let checks = 0;
const check = (label, ok, detail = "") => {
  checks += 1;
  if (!ok) {
    failures.push(`${label}${detail ? `: ${detail}` : ""}`);
  }
};

// In the page: a recorder of what the main view shows from a reader's press until it settles,
// started before the press. Each animation frame it reads the page's parts, the header's
// lines, the tab bar, the body's first element, and the body's first files' bars, and keeps a
// frame wherever any of their boxes or kinds changed, marked `held` while the header is out of
// sight for the cold page's quiet period (`.github-pull-cold`); a PerformanceObserver keeps
// every layout shift, its sources' boxes before and after. `ROOT` names the page's element.
const RECORDER = (root) => `(() => {
  const ROOT = ${JSON.stringify(root)};
  const t0 = performance.now();
  const record = { frames: [], shifts: [], done: false };
  window.__stackRecord = record;
  const describe = (node) => !node || node.nodeType !== 1 ? null :
    node.tagName.toLowerCase() + [...node.classList].slice(0, 3).map((c) => "." + c).join("");
  const box = (el) => {
    if (!el) return null;
    const b = el.getBoundingClientRect();
    const hidden = getComputedStyle(el).visibility === "hidden";
    return [Math.round(b.top), Math.round(b.height)].concat(hidden ? ["hidden"] : []);
  };
  const observer = new PerformanceObserver((list) => {
    for (const entry of list.getEntries()) {
      record.shifts.push({
        t: Math.round(entry.startTime - t0),
        value: Number(entry.value.toFixed(5)),
        input: entry.hadRecentInput,
        sources: entry.sources.map((s) => ({
          node: describe(s.node),
          from: [Math.round(s.previousRect.y), Math.round(s.previousRect.height)],
          to: [Math.round(s.currentRect.y), Math.round(s.currentRect.height)],
        })),
      });
    }
  });
  observer.observe({ type: "layout-shift" });
  let last = "";
  const sample = () => {
    if (record.done) { observer.disconnect(); return; }
    const page = document.querySelector(ROOT);
    const parts = page === null ? null : [...page.children].map((child) => [describe(child), box(child)]);
    const header = page?.querySelector(".page-header") ?? null;
    const lines = header === null ? null : [...header.children].map((child) => [describe(child), box(child), child.textContent.slice(0, 60)]);
    const held = header !== null && getComputedStyle(header).opacity === "0";
    const body = page?.querySelector(".github-pull-body") ?? null;
    const first = body?.firstElementChild ?? null;
    const loading = body?.querySelector(".github-pull-diff-loading") ?? null;
    const files = [...(body?.querySelectorAll(".diff-file") ?? [])].slice(0, 4).map((file) => [
      file.querySelector(".diff-file-path")?.textContent ?? null,
      box(file),
      describe(file.querySelector(".diff-file-body")?.firstElementChild ?? null),
    ]);
    const shown = { parts, lines, held, first: [describe(first), box(first)], loading: box(loading), files };
    const signature = JSON.stringify(shown);
    if (signature !== last) {
      last = signature;
      record.frames.push({ t: Math.round(performance.now() - t0), ...shown });
    }
    requestAnimationFrame(sample);
  };
  requestAnimationFrame(sample);
})()`;

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
  const waitFor = async (expression) => {
    try {
      return await chrome.waitFor(expression, STEP_MS);
    } catch (error) {
      const header = await evaluate(
        `(document.querySelector(".github-pull-stack-page") ?? document.querySelector("main") ?? document.body).innerText.slice(0, 800)`,
      );
      const stack = await evaluate(
        `fetch("/api/plugin/github/stack?number=70", {cache: "no-store"}).then((r) => r.text()).then((t) => t.slice(0, 1500))`,
      );
      throw new Error(
        `${error.message}\npage: ${header}\nstack 70: ${stack}\npage errors: ${pageErrors.join("\n")}`,
      );
    }
  };
  const click = (selector) =>
    evaluate(`document.querySelector(${JSON.stringify(selector)}).click()`);
  const frames = () =>
    evaluate("new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)))");
  /** A screenshot for review, in the theme the page shows. */
  const shot = async (name, clip = null) => {
    if (SHOTS === null) {
      return;
    }
    await frames();
    const { data } = await send("Page.captureScreenshot", {
      format: "png",
      ...(clip === null ? {} : { clip: { ...clip, scale: 1 } }),
    });
    fs.mkdirSync(SHOTS, { recursive: true });
    fs.writeFileSync(path.join(SHOTS, `${name}.png`), Buffer.from(data, "base64"));
  };
  // A theme, once its color transitions (never an endless animation) have run, so a screenshot
  // shows the theme and not a blend of two.
  const theme = (name) =>
    evaluate(`(async () => {
      document.documentElement.dataset.theme = ${JSON.stringify(name)};
      await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));
      await Promise.all(document.getAnimations().filter((animation) => animation instanceof CSSTransition).map((animation) => animation.finished.catch(() => null)));
    })()`);
  // The stack's page once every member's record is read and its comparison is drawn: the
  // header's Diff summary, and the diff of the tab it shows out of its hold.
  const pageReady = `(() => {
    const page = document.querySelector(".github-pull-stack-page");
    return page !== null &&
      !/Fetching/.test(page.querySelector(".page-header")?.innerText ?? "") &&
      page.querySelector(".github-pull-summary .diff-summary") !== null &&
      page.querySelector(".github-pull-diff-holding, .github-pull-diff-loading") === null;
  })()`;

  /**
   * What moved in a recording from the page's first paint the reader sees to its settled
   * layout: a header row or the tab column whose box changed, a header row the settled header
   * lacks, and a diff file or the body's first element that moved once shown. Boxes are
   * [top, height], with "hidden" while held out of sight. A frame whose header is held out of
   * sight for the cold page's quiet period is not seen, so it is not measured: a stack's
   * answer that lands within it is the first header the reader sees, as a pull request's
   * record is.
   */
  const moves = (result) => {
    const shown = result.frames.filter(
      (frame) => frame.parts !== null && frame.lines !== null && !frame.held,
    );
    const settled = shown.at(-1);
    if (settled === undefined) {
      return ["the page never painted"];
    }
    const out = [];
    const same = (a, b) => a !== null && b !== null && a[0] === b[0] && a[1] === b[1];
    for (const frame of shown) {
      for (const [name, at] of frame.lines) {
        const final = settled.lines.find(([other]) => other === name);
        if (final === undefined) {
          out.push(`${frame.t} ms: ${name} is not in the settled header`);
        } else if (!same(at, final[1])) {
          out.push(
            `${frame.t} ms: ${name} at ${JSON.stringify(at)}, settles at ${JSON.stringify(final[1])}`,
          );
        }
      }
      for (const [name, at] of frame.parts.slice(0, 2)) {
        const final = settled.parts.find(([other]) => other === name);
        if (final !== undefined && !same(at, final[1])) {
          out.push(
            `${frame.t} ms: ${name} at ${JSON.stringify(at)}, settles at ${JSON.stringify(final[1])}`,
          );
        }
      }
    }
    // Once shown, the body's first element and each file stay where they are.
    const visible = (at) => at !== null && at[2] !== "hidden";
    const firsts = shown.filter(
      (frame) => visible(frame.first[1]) && frame.first[0] === settled.first[0],
    );
    for (const frame of firsts) {
      if (frame.first[1][0] !== settled.first[1][0]) {
        out.push(
          `${frame.t} ms: the body's ${frame.first[0]} at ${frame.first[1][0]}, settles at ${settled.first[1][0]}`,
        );
      }
    }
    for (const frame of shown) {
      for (const [file, at] of frame.files) {
        const final = settled.files.find(([other]) => other === file);
        if (visible(at) && final !== undefined && at[0] !== final[1][0]) {
          out.push(`${frame.t} ms: ${file} at ${at[0]}, settles at ${final[1][0]}`);
        }
      }
    }
    return out;
  };
  /** Where the diff's loading block stood in each frame that had one. */
  const loadingTops = (result) => [
    ...new Set(
      result.frames.flatMap((frame) => (frame.loading === null ? [] : [frame.loading[0]])),
    ),
  ];

  /** Screencast frames, saved under SHOTS_DIR/<name>/ while a recording runs. */
  let filming = null;
  chrome.on("Page.screencastFrame", ({ data, sessionId, metadata }) => {
    void send("Page.screencastFrameAck", { sessionId });
    if (filming === null || filming.count >= 80) {
      return;
    }
    filming.count += 1;
    const ms = Math.round(metadata.timestamp * 1000 - filming.wall);
    fs.writeFileSync(
      path.join(filming.dir, `${String(filming.count).padStart(3, "0")}-${ms}ms.jpg`),
      Buffer.from(data, "base64"),
    );
  });
  /**
   * Record the main view from *press* until it has not changed for SETTLE_MS, at most
   * RECORD_MS: the recorder's frames and shifts, and with SHOTS_DIR a screencast.
   */
  const record = async (name, root, press) => {
    await evaluate(RECORDER(root));
    if (SHOTS !== null) {
      const dir = path.join(SHOTS, name);
      fs.rmSync(dir, { recursive: true, force: true });
      fs.mkdirSync(dir, { recursive: true });
      filming = { dir, count: 0, wall: Date.now() };
      await send("Page.startScreencast", { format: "jpeg", quality: 70, everyNthFrame: 1 });
    }
    await press();
    const SETTLE_MS = 2500;
    const RECORD_MS = 30000;
    const began = Date.now();
    let count = -1;
    let quiet = 0;
    for (;;) {
      await new Promise((resolve) => setTimeout(resolve, 250));
      const frames = await evaluate("window.__stackRecord.frames.length");
      quiet = frames === count ? quiet + 250 : 0;
      count = frames;
      if (quiet >= SETTLE_MS || Date.now() - began >= RECORD_MS) {
        break;
      }
    }
    if (SHOTS !== null) {
      await send("Page.stopScreencast");
      filming = null;
    }
    const result = await evaluate(
      `(() => { const r = window.__stackRecord; r.done = true; return { frames: r.frames, shifts: r.shifts }; })()`,
    );
    measured[name] = result;
    phase(`recorded ${name}: ${result.frames.length} frames, ${result.shifts.length} shifts`);
    return result;
  };

  await send("Page.enable");
  // The stand-in's records and its commits, as a reader has them once they have opened the
  // stack's pull requests: a stack's page reads its members' records and the repository's
  // store from the cache.
  for (const number of [8, 10]) {
    await send("Page.navigate", { url: `${base}/pull/${number}` });
    await waitFor(`document.querySelector(".github-pull-title-text") !== null`);
  }
  const stackState = (number) =>
    `fetch("/api/plugin/github/stack?number=${number}", {cache: "no-store"}).then((r) => r.json()).then((a) => a.state)`;
  await waitFor(`${stackState(70)}.then((state) => state === "current")`);
  phase("members read");
  // The reader's way to the stack's page: the stack menu's Stack Overview row, on 10's page.
  await waitFor(
    `document.querySelector(".github-pull-stack-trigger:not(.github-pull-stack-strut)") !== null`,
  );
  await click(".github-pull-stack-trigger:not(.github-pull-stack-strut)");
  await waitFor(`document.querySelector(".github-pull-stack-whole") !== null`);
  check(
    "the stack menu names the Stack Overview",
    await evaluate(
      `document.querySelector(".github-pull-stack-whole .github-pull-stack-member-title")?.textContent === "Stack Overview"`,
    ),
  );
  const opened = await record("open-stack", ".github-pull-stack-page", () =>
    click(".github-pull-stack-whole"),
  );
  await waitFor(pageReady);
  await frames();
  phase("stack 70");
  check(
    "the stack page title names Stack Overview and keeps its number",
    await evaluate(
      `document.querySelector(".github-pull-stack-page h1")?.textContent === "Stack Overview #70"`,
    ),
  );
  // Opened from the menu, the stack's Stack Overview row in the Pulls tab is the current row
  // and in view. Here the list draws the row only after the address names the page; until
  // its reveal waited for the row (`wholeRevealPending`), it was marked but left 3,745 px
  // above the view (mb-cm31).
  await waitFor(
    `document.querySelector('#tab-pulls .github-pulls-whole-row[data-stack="70"]')?.getAttribute("aria-current") === "page"`,
  );
  await frames();
  const fromMenu = await evaluate(`(() => {
    const whole = document.querySelector('#tab-pulls .github-pulls-whole-row[data-stack="70"]');
    const box = whole.getBoundingClientRect();
    const view = document.querySelector(".tree-content").getBoundingClientRect();
    return { top: box.top, bottom: box.bottom, viewTop: view.top, viewBottom: view.bottom };
  })()`);
  measured.wholeFromMenu = fromMenu;
  check(
    "opened from the menu, the Pulls tab's Stack Overview row is current and in view",
    fromMenu.top >= fromMenu.viewTop - 1 && fromMenu.bottom <= fromMenu.viewBottom + 1,
    JSON.stringify(fromMenu),
  );
  // Its other tabs, as a reader opens them, recorded before any theme changes, whose
  // transitions a screencast would catch.
  const docs = await record("stack-docs", ".github-pull-stack-page", () =>
    click('.github-pull-stack-page .tab-bar a[href$="/docs"]'),
  );
  await shot(`stack-70-docs`);
  const changes = await record("stack-changes", ".github-pull-stack-page", () =>
    click('.github-pull-stack-page .tab-bar a[href$="/changes"]'),
  );
  await waitFor(pageReady);
  await shot(`stack-70-changes`);
  for (const [name, result] of [
    ["opening the stack's page", opened],
    ["its Docs", docs],
    ["its Changes", changes],
  ]) {
    const moved = moves(result);
    check(
      `${name}: nothing moves from first paint`,
      moved.length === 0,
      moved.slice(0, 6).join("; "),
    );
  }
  // The members' toggle, closed as the Diff summary is: a press opens its card and another
  // closes it, each travelling as every disclosure does, and its words start where the Diff
  // summary's do, the two toggles' hover grounds at one edge.
  const MEMBERS = `(() => {
    const page = document.querySelector(".github-pull-stack-page");
    const toggle = page.querySelector(".github-pull-stack-members-toggle");
    const body = page.querySelector(".github-pull-stack-members-body");
    const summary = page.querySelector(".github-pull-summary .diff-summary-toggle");
    const left = (el) => el === null ? null : Math.round(el.getBoundingClientRect().left * 100) / 100;
    // Where a toggle's words start: the first box its contents draw.
    const firstText = (el) => {
      if (el === null) return null;
      const range = document.createRange();
      range.selectNodeContents(el);
      const rect = [...range.getClientRects()].find((r) => r.width > 0);
      return rect === undefined ? null : Math.round(rect.left * 100) / 100;
    };
    return {
      text: toggle?.textContent ?? null,
      expanded: toggle?.getAttribute("aria-expanded") ?? null,
      controls: toggle?.getAttribute("aria-controls") === body?.id,
      height: body === null ? null : Math.round(body.getBoundingClientRect().height),
      card: Math.round(page.querySelector(".github-pull-stack-members")?.getBoundingClientRect().height ?? -1),
      visibility: body === null ? null : getComputedStyle(body).visibility,
      toggleLeft: left(toggle),
      summaryLeft: left(summary),
      wordsLeft: firstText(toggle),
      summaryWordsLeft: firstText(summary),
      bodyBelowToggle: body !== null && toggle !== null && body.getBoundingClientRect().top >= toggle.getBoundingClientRect().bottom - 0.5,
      summaryBelow: summary !== null && toggle !== null && summary.getBoundingClientRect().top >= toggle.getBoundingClientRect().bottom - 0.5,
    };
  })()`;
  // Wait out a disclosure's travel: its transitions end.
  const travelled = () =>
    evaluate(`(async () => {
      await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));
      await Promise.all(document.getAnimations().filter((animation) => animation instanceof CSSTransition).map((animation) => animation.finished.catch(() => null)));
    })()`);
  const closedFirst = await evaluate(MEMBERS);
  await click(".github-pull-stack-members-toggle");
  await travelled();
  const openedMembers = await evaluate(MEMBERS);
  await shot(`stack-70-members-open`);
  measured.members = { closed: closedFirst, opened: openedMembers };
  check(
    "the members' toggle says how many, is closed at first, and opens its card under it",
    closedFirst.text === "2 Pulls" &&
      closedFirst.expanded === "false" &&
      closedFirst.controls &&
      closedFirst.height === 0 &&
      closedFirst.visibility === "hidden" &&
      openedMembers.expanded === "true" &&
      openedMembers.visibility === "visible" &&
      openedMembers.height > 0 &&
      openedMembers.height >= openedMembers.card &&
      openedMembers.bodyBelowToggle &&
      openedMembers.summaryBelow,
    JSON.stringify(measured.members),
  );
  check(
    "the members' toggle and the Diff summary's start their grounds and their words at one edge",
    closedFirst.toggleLeft === closedFirst.summaryLeft &&
      closedFirst.wordsLeft === closedFirst.summaryWordsLeft,
    JSON.stringify(closedFirst),
  );
  // The header's tally: a badge for each state some member is in, each in the ink a pull
  // request's badge of that state has.
  const tally = await evaluate(`(() => {
    const page = document.querySelector(".github-pull-stack-page");
    return [...page.querySelectorAll(".github-pull-stack-tally .github-pull-badge")].map((badge) => {
      const probe = document.createElement("span");
      probe.className = "file-header-badge github-pull-badge github-pull-state";
      probe.dataset.state = badge.dataset.state;
      page.querySelector(".github-pull-opened").append(probe);
      const ink = getComputedStyle(probe).color;
      probe.remove();
      return { state: badge.dataset.state, text: badge.textContent, ink: getComputedStyle(badge).color, pullInk: ink };
    });
  })()`);
  measured.tally = tally;
  check(
    "the tally's badges are a pull request's state badges, one per state a member is in",
    tally.length > 0 &&
      new Set(tally.map((badge) => badge.state)).size === tally.length &&
      tally.every((badge) => badge.ink === badge.pullInk),
    JSON.stringify(tally),
  );
  const page = await evaluate(`(() => {
    const page = document.querySelector(".github-pull-stack-page");
    const members = [...page.querySelectorAll(".github-pull-stack-members .github-pull-stack-member")];
    const summary = page.querySelector(".github-pull-summary .diff-summary-toggle");
    const counterpart = page.querySelector(".view-header-end[data-counterpart] a.counterpart-open");
    return {
      members: members.map((row) => ({
        text: row.innerText.replace(/\\s+/g, " ").trim(),
        current: row.hasAttribute("aria-current"),
        author: row.querySelector(".github-pull-stack-member-by:not([hidden]) .github-pull-stack-member-author")?.textContent ?? null,
      })),
      summary_open: summary?.getAttribute("aria-expanded") ?? null,
      counterpart: counterpart?.getAttribute("href") ?? null,
      tabs: [...page.querySelectorAll(".tab-bar .tab-btn")].filter((tab) => !tab.hidden).map((tab) => tab.textContent),
      // The size line as it reads on screen: its words, with the commas said in place of its
      // dots left out.
      size: (() => {
        const line = page.querySelector(".github-pull-size")?.cloneNode(true) ?? null;
        line?.querySelectorAll(".visually-hidden").forEach((node) => node.remove());
        return line === null ? null : line.textContent.replace(/\\s+/g, " ").trim();
      })(),
    };
  })()`);
  // The size line the shell's builder writes for the stack's answer: its commits, its files,
  // and its comparison's size, with nothing restated here.
  const sizeLine = await evaluate(`(async () => {
    const answer = await (await fetch("/api/plugin/github/stack?number=70", {cache: "no-store"})).json();
    return {
      commits: answer.commits,
      files: answer.totals?.files ?? null,
      size: answer.size,
      text: window.metabrowser.changeSizeLine({
        commits: answer.commits,
        files: answer.totals.files,
        pushedBytes: answer.size?.pushed_bytes ?? null,
        diffBytes: answer.size?.diff_bytes ?? null,
      }).text.replace(/\\s+/g, " ").trim(),
    };
  })()`);
  measured.sizeLine = sizeLine;
  measured.page = page;
  // Each member row is the stack menu's (`stackMemberRow`), so its layout is the menu's by
  // construction. What the running app adds is its data: every member's author, its
  // record's from the stack's answer, which a member the Pulls tab's lists have not read
  // (merged 8, which the Open list leaves out) has too. The stand-in's pull requests are
  // all the maintainer's.
  check(
    "every member names its author",
    page.members.length === 2 && page.members.every((row) => row.author === "maintainer"),
    JSON.stringify(page.members),
  );
  for (const row of page.members) {
    check(`${row.text}: no member is the page`, !row.current);
  }
  check("the Diff summary is closed", page.summary_open === "false", String(page.summary_open));
  check(
    "View on GitHub opens the whole stack",
    page.counterpart === "https://github.com/octo/demo/stack/70",
    String(page.counterpart),
  );
  // The stand-in's stack carries no guide, so its tabs are a pull request's without Guided
  // Review, and never a Files tab, which the stack's page no longer has.
  check(
    "the tabs are Docs and Changes, and no Files",
    JSON.stringify(page.tabs) === JSON.stringify(["Docs", "Changes"]),
    JSON.stringify(page.tabs),
  );
  // The size line says the answer's commits and files, and its comparison's size where it is
  // kept, as the shell's builder writes them.
  check(
    "the size line is the shell's for the stack's commits, files, and size",
    sizeLine.commits === 2 && sizeLine.files === 1 && page.size === sizeLine.text,
    JSON.stringify({ shown: page.size, built: sizeLine }),
  );
  await click(".github-pull-stack-members-toggle");
  await travelled();
  const closed = await evaluate(MEMBERS);
  measured.members.closed_again = closed;
  check(
    "a second press closes the members' card",
    closed.expanded === "false" && closed.height === 0 && closed.visibility === "hidden",
    JSON.stringify(closed),
  );
  await theme("dark");
  await shot(`stack-70-dark`);
  await theme("light");
  await shot(`stack-70-light`);

  // In a narrow pane, 560 px, and at a phone's width, 375 px, the stack's answer as a larger
  // stack's: four states with two-digit counts, and six authors. The page reads it as it
  // reads any answer, here when it comes back into sight. The tally gives way after the
  // ages, each badge cut short and keeping its count, and stays inside its row. The author's
  // row gives way in its names and its action together, so neither is cut to nothing while
  // the other is whole: at 560 px both keep some of their words, and at 375 px six names at
  // their floors fill the row, the action given way first since the size line under it
  // says its commits too.
  await evaluate(`(async () => {
    const original = window.fetch;
    const answer = await (await original("/api/plugin/github/stack?number=70", {cache: "no-store"})).json();
    const larger = {
      ...answer,
      states: { open: 12, draft: 12, merged: 12, closed: 12 },
      authors: ["maintainer", "a-long-contributor-name", "reviewer-two", "octocat", "someone-else", "sixth-author"]
        .map((login) => ({ login, avatar: null })),
      commits: 48,
    };
    window.fetch = async (route, init) => {
      const url = typeof route === "string" ? route : route.url;
      if (url.startsWith("/api/plugin/github/stack?")) {
        return new Response(JSON.stringify(larger), {
          status: 200,
          headers: { "content-type": "application/json", etag: '"phone"' },
        });
      }
      return original(route, init);
    };
    document.dispatchEvent(new Event("visibilitychange"));
  })()`);
  await waitFor(
    `document.querySelectorAll(".github-pull-stack-page .github-pull-stack-tally .github-pull-badge").length === 4 && document.querySelectorAll(".github-pull-stack-page .github-pull-meta-details .github-pull-identity").length === 6`,
  );
  const NARROW = `(() => {
    const page = document.querySelector(".github-pull-stack-page");
    const r = (n) => Math.round(n * 100) / 100;
    const box = (el) => el.getBoundingClientRect();
    // An element's own width, laid out whole.
    const natural = (el) => {
      const copy = el.cloneNode(true);
      copy.style.cssText = "position:absolute;visibility:hidden;width:max-content;max-width:none;min-width:0;flex:none";
      el.parentElement.append(copy);
      const width = box(copy).width;
      copy.remove();
      return r(width);
    };
    const row = page.querySelector(".github-pull-opened");
    const tally = row.querySelector(".github-pull-stack-tally");
    const badges = [...tally.querySelectorAll(".github-pull-badge")].map((badge) => {
      const style = getComputedStyle(badge);
      const count = badge.textContent.split(" ")[0];
      const range = document.createRange();
      range.setStart(badge.firstChild, 0);
      range.setEnd(badge.firstChild, count.length);
      const probe = document.createElement("span");
      probe.textContent = "\u2026";
      badge.append(probe);
      const ellipsis = box(probe).width;
      probe.remove();
      const word = document.createRange();
      word.selectNodeContents(badge.lastChild);
      return {
        text: badge.textContent,
        shown: badge.innerText,
        tip: badge.dataset.tipText ?? null,
        cut: badge.scrollWidth > badge.clientWidth,
        // Where the state's word ends, which tells the badges apart.
        wordEnd: r(word.getBoundingClientRect().right),
        width: r(box(badge).width),
        natural: natural(badge),
        floor: r(parseFloat(style.minWidth)),
        // Where the count ends, and where an ellipsis after it would: inside the content box.
        countEnd: r(range.getBoundingClientRect().right + ellipsis),
        contentEnd: r(box(badge).right - parseFloat(style.paddingRight) - parseFloat(style.borderRightWidth)),
      };
    });
    const meta = page.querySelector(".github-pull-meta-details");
    const floor = (identity) => parseFloat(getComputedStyle(identity).minWidth);
    const names = [...meta.querySelectorAll(":scope > .github-pull-identity")].map((identity) => ({
      login: identity.querySelector(".github-pull-author").textContent,
      tip: identity.querySelector(".github-pull-author").dataset.tipText ?? null,
      // Whether the box that carries the tooltip is the one cut short, which is when the
      // shell shows a tooltip that is its anchor's own text.
      cut:
        identity.querySelector(".github-pull-author").scrollWidth >
        identity.querySelector(".github-pull-author").clientWidth,
      width: r(box(identity).width),
      natural: natural(identity),
      floor: r(floor(identity)),
    }));
    const action = meta.querySelector(".github-pull-action");
    return {
      row: {
        left: r(box(row).left),
        right: r(box(row).right),
        width: r(box(row).width),
        font: parseFloat(getComputedStyle(row).fontSize),
      },
      tally: { right: r(box(tally).right), width: r(box(tally).width), natural: natural(tally) },
      badges,
      sentence: {
        lead: r(box(page.querySelector(".github-pull-meta-lead")).width),
        right: r(box(meta).right),
        rowRight: r(box(page.querySelector(".github-pull-meta")).right),
        names,
        action: { width: r(box(action).width), natural: natural(action), text: action.textContent },
      },
    };
  })()`;
  measured.narrow = {};
  for (const width of [560, 375]) {
    await evaluate(`(() => {
      const pane = document.getElementById("preview-pane");
      pane.style.flex = "none";
      pane.style.width = "${width}px";
    })()`);
    await frames();
    await shot(`stack-70-larger-${width}`);
    const narrow = await evaluate(NARROW);
    measured.narrow[width] = narrow;
    check(
      `at ${width} px the tally gives way inside its row, each badge keeping its count`,
      narrow.tally.right <= narrow.row.right + 0.5 &&
        narrow.badges.length === 4 &&
        narrow.badges.every((badge) => badge.width >= badge.floor - 0.5) &&
        narrow.badges.every((badge) => badge.countEnd <= badge.contentEnd + 0.5),
      JSON.stringify({ row: narrow.row, tally: narrow.tally, badges: narrow.badges }),
    );
    // What tells four badges of one noun apart is each one's state: its word is whole, or
    // the badge is cut short and its tooltip, which the shell shows then, is its whole label.
    check(
      `at ${width} px each badge of the tally says its state, in its words or its tooltip`,
      narrow.badges.every(
        (badge) =>
          badge.tip === badge.text && (badge.cut || badge.wordEnd <= badge.contentEnd + 0.5),
      ),
      JSON.stringify(narrow.badges),
    );
    const { sentence } = narrow;
    const cutNames = sentence.names.filter((name) => name.width < name.natural - 0.5);
    const actionCut = sentence.action.width < sentence.action.natural - 0.5;
    check(
      `at ${width} px the author's row gives way in its names and its action together`,
      sentence.right <= sentence.rowRight + 0.5 &&
        (!actionCut || cutNames.length > 0) &&
        (cutNames.length === 0 || actionCut) &&
        sentence.names.every((name) => name.width >= name.floor - 0.5) &&
        // A name cut short is still said: its tooltip, which the shell shows then, is it whole.
        sentence.names.every((name) => name.tip === name.login) &&
        cutNames.every((name) => name.cut) &&
        // Both keep some of their words while a name is above its floor.
        (sentence.action.width >= 1 ||
          sentence.names.every((name) => name.width <= name.floor + 0.5)),
      JSON.stringify(sentence),
    );
  }
  // At a phone's width the four badges leave out their noun and so are whole, each a count
  // and its state's word; in the wider pane they have room for all three words.
  check(
    "at 375 px the four badges are whole without their noun, and at 560 px whole with it",
    measured.narrow[375].badges.every(
      (badge) =>
        !badge.cut &&
        badge.shown ===
          badge.text
            .split(" ")
            .filter((_, at) => at !== 1)
            .join(" "),
    ) && measured.narrow[560].badges.every((badge) => !badge.cut && badge.shown === badge.text),
    JSON.stringify([measured.narrow[375].badges, measured.narrow[560].badges]),
  );
  // Where both give way short of the names' floors, the action keeps some of its words.
  check(
    "at 560 px the action keeps some of its words beside six cut names",
    measured.narrow[560].sentence.action.width >= 1,
    JSON.stringify(measured.narrow[560].sentence),
  );

  // A pull request's own Docs and Changes, for comparison.
  await send("Page.navigate", { url: `${base}/pull/10` });
  await waitFor(`document.querySelector(".github-pull .diff-summary") !== null`);
  await frames();
  const pullDocs = await record("pull-docs", ".github-pull", () =>
    click('.github-pull .tab-bar a[href$="/docs"]'),
  );
  const pullChanges = await record("pull-changes", ".github-pull", () =>
    click('.github-pull .tab-bar a[href$="/files"]'),
  );
  for (const [name, result] of [
    ["the stack's Docs", docs],
    ["the stack's Changes", changes],
    ["a pull request's Docs", pullDocs],
    ["a pull request's Changes", pullChanges],
  ]) {
    const tops = loadingTops(result);
    check(
      `${name}: the loading block stays where it showed`,
      tops.length <= 1,
      JSON.stringify(tops),
    );
  }

  // The Pulls tab beside the page, its stacks grouped.
  await send("Page.navigate", { url: `${base}/stack/70` });
  await waitFor(pageReady);
  await click('.nav-tab-bar [data-tab="pulls"]');
  await waitFor(`document.querySelector(".github-pulls-stack-row") !== null`);
  await frames();
  phase("pulls");
  await shot(`stack-70-with-pulls`);
  // The Pulls tab's Stack Overview row (mb-cm31, mb-odt4): the first of Stack #70's rows, its
  // members beside it at one level, the current row while the stack's page is open, and in view.
  const WHOLE = `document.querySelector('#tab-pulls .github-pulls-whole-row[data-stack="70"]')`;
  const NAV = `(() => {
    const whole = ${WHOLE};
    if (whole === null) return null;
    // The stack's rows: the second-level items after its stack's row, its Stack Overview row
    // first, then its members, to the next row a level out.
    const members = [];
    const first = document.querySelector('#tab-pulls .github-pulls-stack-row[data-stack="70"]')?.closest("li")?.nextElementSibling;
    const under = first === whole.closest("li") && first.dataset.level === "2";
    for (let item = first?.nextElementSibling; item?.dataset.level === "2"; item = item.nextElementSibling) {
      members.push(Number(item.dataset.number));
    }
    const view = document.querySelector(".tree-content").getBoundingClientRect();
    const box = whole.getBoundingClientRect();
    return {
      address: location.pathname,
      text: whole.querySelector(".github-pulls-whole-title")?.textContent ?? null,
      under,
      href: whole.getAttribute("href"),
      current: whole.getAttribute("aria-current"),
      selected: whole.classList.contains("selected"),
      focused: document.activeElement === whole,
      place: whole.getAttribute("aria-posinset") + "/" + whole.getAttribute("aria-setsize"),
      members,
      inView: box.height > 0 && box.top >= view.top - 1 && box.bottom <= view.bottom + 1,
    };
  })()`;
  await waitFor(`${WHOLE}?.getAttribute("aria-current") === "page"`);
  const nav = await evaluate(NAV);
  measured.nav = { open: nav };
  check(
    "the Pulls tab's Stack Overview row is the first of Stack #70's rows, its members beside it, and links to its page",
    nav?.under &&
      nav.text === "Stack Overview" &&
      nav.href === "/stack/70" &&
      nav.members.length > 0 &&
      nav.members.every((number) => [10, 8].includes(number)) &&
      nav.place === `1/${nav.members.length + 1}`,
    JSON.stringify(nav),
  );
  check(
    "it is the current row while the stack's page is open, and in view",
    nav?.current === "page" && nav.selected && nav.inView,
    JSON.stringify(nav),
  );
  const last = nav?.members.at(-1);
  // A member's row takes the mark; a press on the Stack Overview row opens the stack's page
  // again and gives it back; and J from the stack's row walks onto it and opens the page.
  await click(`#tab-pulls a.github-pulls-row[data-number="${last}"]`);
  await waitFor(
    `location.pathname === "/pull/${last}" && ${WHOLE}.getAttribute("aria-current") === null`,
  );
  await click('#tab-pulls .github-pulls-whole-row[data-stack="70"] .github-pulls-whole-title');
  await waitFor(
    `location.pathname === "/stack/70" && ${WHOLE}.getAttribute("aria-current") === "page"`,
  );
  measured.nav.pressed = await evaluate(NAV);
  await click(`#tab-pulls a.github-pulls-row[data-number="${last}"]`);
  await waitFor(`location.pathname === "/pull/${last}"`);
  await evaluate(
    `document.querySelector('#tab-pulls .github-pulls-stack-row[data-stack="70"]').focus()`,
  );
  for (const type of ["keyDown", "keyUp"]) {
    await send("Input.dispatchKeyEvent", {
      type,
      key: "j",
      code: "KeyJ",
      windowsVirtualKeyCode: 74,
      ...(type === "keyDown" ? { text: "j" } : {}),
    });
  }
  await waitFor(`location.pathname === "/stack/70" && document.activeElement === ${WHOLE}`);
  await waitFor(`${WHOLE}.getAttribute("aria-current") === "page"`);
  measured.nav.walked = await evaluate(NAV);
  check(
    "a press on it, and J onto it from the stack's row, open the stack's page and mark it",
    measured.nav.pressed?.address === "/stack/70" &&
      measured.nav.pressed.current === "page" &&
      measured.nav.walked?.address === "/stack/70" &&
      measured.nav.walked.current === "page" &&
      measured.nav.walked.focused,
    JSON.stringify(measured.nav),
  );
  await shot(`stack-70-whole-row`);
  // The Stack Overview row's change line and the chevron after it open the stack's changed
  // files under it (mb-odt4): the files the page's Diff summary lists, the same rows in the
  // same order, and the press opens no page.
  const SUMMARY_ROWS = `[...document.querySelectorAll(".github-pull-stack-page .github-pull-summary .changed-file-row[data-id]")].map((row) => row.dataset.id)`;
  const NAV_ROWS = `[...document.querySelectorAll('#tab-pulls .github-pulls-whole-item[data-level="2"] > .github-pull-files .changed-file-row[data-id]')].map((row) => row.dataset.id)`;
  // The walk above opened the stack's page again. The address and the row's mark move at
  // once, but the pane holds the outgoing page while the incoming one mounts in its stage
  // (`beginPreviewNavigation` in static/app.js, `preview-navigation-pending`), so for a
  // moment the document holds two stack pages, and `pageReady` alone would find the
  // outgoing one, whose Diff summary is about to go with it. Once the navigation commits
  // there is one page, which draws its Diff summary once, closed.
  await waitFor(
    `!document.getElementById("preview-pane").classList.contains("preview-navigation-pending") &&
      document.querySelectorAll(".github-pull-stack-page").length === 1 &&
      ${pageReady}`,
  );
  await click(".github-pull-stack-page .github-pull-summary .diff-summary-toggle");
  await waitFor(`${SUMMARY_ROWS}.length > 0`);
  await click('#tab-pulls .github-pulls-whole-row[data-stack="70"] .github-pulls-whole-change');
  await waitFor(`${NAV_ROWS}.length > 0`);
  await frames();
  const stackFiles = {
    summary: await evaluate(SUMMARY_ROWS),
    nav: await evaluate(NAV_ROWS),
    address: await evaluate("location.pathname"),
    expanded: await evaluate(`${WHOLE}.getAttribute("aria-expanded")`),
    // The files hang under the Stack Overview row's item, a level in from it.
    levels: await evaluate(
      `[${WHOLE}.getAttribute("aria-level"), document.querySelector('#tab-pulls .github-pulls-whole-item > .github-pull-files .changed-file-row')?.getAttribute("aria-level") ?? null]`,
    ),
    members: (await evaluate(NAV))?.members ?? null,
  };
  measured.nav.files = stackFiles;
  check(
    "a press on the Stack Overview row's change line lists the stack's files under it, the Diff summary's own, and opens no page",
    stackFiles.nav.length > 0 &&
      JSON.stringify(stackFiles.nav) === JSON.stringify(stackFiles.summary) &&
      stackFiles.address === "/stack/70" &&
      stackFiles.expanded === "true" &&
      JSON.stringify(stackFiles.levels) === '["2","3"]' &&
      JSON.stringify(stackFiles.members) === JSON.stringify(nav?.members),
    JSON.stringify(stackFiles),
  );
  await shot(`stack-70-whole-row-files`);
  await click('#tab-pulls .github-pulls-whole-row[data-stack="70"] .github-pulls-whole-change');
  await waitFor(`${WHOLE}.getAttribute("aria-expanded") === "false"`);

  await send("Page.navigate", { url: `${base}/stack/71` });
  await waitFor(pageReady);
  await frames();
  phase("stack 71");
  await shot(`stack-71-light`);

  check("no script error on the page", pageErrors.length === 0, pageErrors.join("\n"));
} finally {
  await chrome.close();
}
if (process.env.MEASURE_OUT) {
  fs.writeFileSync(process.env.MEASURE_OUT, `${JSON.stringify(measured, null, 2)}\n`);
}
if (failures.length > 0) {
  process.stderr.write(`${failures.join("\n")}\n`);
  process.exit(1);
}
process.stdout.write(`stack page in Chrome: ${checks} checks passed\n`);

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
// frame wherever any of their boxes or kinds changed; a PerformanceObserver keeps every layout
// shift, its sources' boxes before and after. `ROOT` names the page's element.
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
    const body = page?.querySelector(".github-pull-body") ?? null;
    const first = body?.firstElementChild ?? null;
    const loading = body?.querySelector(".github-pull-diff-loading") ?? null;
    const files = [...(body?.querySelectorAll(".diff-file") ?? [])].slice(0, 4).map((file) => [
      file.querySelector(".diff-file-path")?.textContent ?? null,
      box(file),
      describe(file.querySelector(".diff-file-body")?.firstElementChild ?? null),
    ]);
    const shown = { parts, lines, first: [describe(first), box(first)], loading: box(loading), files };
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
   * What moved in a recording from the page's first paint to its settled layout: a header
   * row or the tab column whose box changed, a header row the settled header lacks, and a
   * diff file or the body's first element that moved once shown. Boxes are [top, height],
   * with "hidden" while held out of sight.
   */
  const moves = (result) => {
    const shown = result.frames.filter((frame) => frame.parts !== null && frame.lines !== null);
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
  // The reader's way to the stack's page: the stack menu's Whole stack row, on 10's page.
  await waitFor(
    `document.querySelector(".github-pull-stack-trigger:not(.github-pull-stack-strut)") !== null`,
  );
  await click(".github-pull-stack-trigger:not(.github-pull-stack-strut)");
  await waitFor(`document.querySelector(".github-pull-stack-whole") !== null`);
  const opened = await record("open-stack", ".github-pull-stack-page", () =>
    click(".github-pull-stack-whole"),
  );
  await waitFor(pageReady);
  await frames();
  phase("stack 70");
  // Opened from the menu, the stack's Whole stack row in the Pulls tab is the current row
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
    "opened from the menu, the Pulls tab's Whole stack row is current and in view",
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
      size: page.querySelector(".github-pull-size")?.innerText ?? null,
    };
  })()`);
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
  check("the size line says the files", page.size === "1 file changed", String(page.size));
  await theme("dark");
  await shot(`stack-70-dark`);
  await theme("light");
  await shot(`stack-70-light`);

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
  // The Pulls tab's Whole stack row (mb-cm31): the last of Stack #70's rows, under its
  // members, the current row while the stack's page is open, and in view.
  const WHOLE = `document.querySelector('#tab-pulls .github-pulls-whole-row[data-stack="70"]')`;
  const NAV = `(() => {
    const whole = ${WHOLE};
    if (whole === null) return null;
    const members = [];
    for (let item = whole.closest("li").previousElementSibling; item?.dataset.level === "2"; item = item.previousElementSibling) {
      members.unshift(Number(item.dataset.number));
    }
    const view = document.querySelector(".tree-content").getBoundingClientRect();
    const box = whole.getBoundingClientRect();
    return {
      address: location.pathname,
      text: whole.textContent,
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
    "the Pulls tab's Whole stack row ends Stack #70's members and links to its page",
    nav !== null &&
      nav.text === "Whole stack" &&
      nav.href === "/stack/70" &&
      nav.members.length > 0 &&
      nav.members.every((number) => [10, 8].includes(number)) &&
      nav.place === `${nav.members.length + 1}/${nav.members.length + 1}`,
    JSON.stringify(nav),
  );
  check(
    "it is the current row while the stack's page is open, and in view",
    nav?.current === "page" && nav.selected && nav.inView,
    JSON.stringify(nav),
  );
  const last = nav?.members.at(-1);
  // A member's row takes the mark; a press on the Whole stack row opens the stack's page
  // again and gives it back; and J from the last member walks onto it and opens the page.
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
    `document.querySelector('#tab-pulls a.github-pulls-row[data-number="${last}"]').focus()`,
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
    "a press on it, and J onto it from the last member, open the stack's page and mark it",
    measured.nav.pressed?.address === "/stack/70" &&
      measured.nav.pressed.current === "page" &&
      measured.nav.walked?.address === "/stack/70" &&
      measured.nav.walked.current === "page" &&
      measured.nav.walked.focused,
    JSON.stringify(measured.nav),
  );
  await shot(`stack-70-whole-row`);

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

// Guided Review in headless Chrome against a live `metab` server that serves the GitHub stand-in
// with guides in the descriptions of pull requests 7 to 9 and none in 10's.
//
//   CHROME_BIN=... CHROME_PROFILES=<dir> node tests/dom/github-guided-pr-chrome.mjs <base URL>
//
// tests/test_github_guided_pr_chrome.py builds that server, owns the profile directory, and stops
// this process's whole group, Chrome included, however the run ends (tests/process_group.py).
//
// What only a browser holds, and the browserless sessions cannot (github-guided-pr-session.js,
// github-guided-pr-mount-behavior.js, and the tab and key in github-pull-page-mount-behavior.js):
//
// 1. The tab and its key on the real shell: Guided Review leads the bar on a pull request whose
//    description has a guide and is its front page, opened by the description; Conversation
//    has its own address, where the guide's block is a card; R opens the guide once the page
//    has attached its keys; and on one with no guide there is no tab and R opens nothing.
// 2. An excerpt's rows after the shell's highlighter has run over the page. The shell highlights
//    every `pre code` that does not carry `no-highlight` (`highlightCode` in app.js), one row at a
//    time as a one-line snippet, which gave each row a padded, gray block of its own inside the
//    row's tint (review A of #599, A3). The diff plugin draws the excerpt, as it draws Changes, so
//    no row is a `pre code`. A control block outside the excerpt proves the pass runs here: it is
//    highlighted, and the rows keep no padding or background of their own.
// 3. A row is one line: its number columns, its mark, and its code share a top and do not overlap,
//    and the tint is the row's, never the code's. The excerpt opens on the diff's hunk bar.
// 4. The guide opens on its overview under a list of its steps; a step in the list, the
//    arrows, and the way on below a step move between them, the step's text sits at the
//    description's inset, Open full diff goes to the file's Changes address, and a guide that
//    cannot be read says so in place: none, stale, and two blocks.
import { launchChrome } from "./chrome-session.mjs";

const [base] = process.argv.slice(2);
if (!base || !process.env.CHROME_BIN || !process.env.CHROME_PROFILES) {
  throw new Error("usage: CHROME_BIN CHROME_PROFILES github-guided-pr-chrome.mjs <base>");
}
// One page load or fake gh fetch; a loaded machine has needed several seconds for one.
const STEP_MS = 30000;

const failures = [];
let checks = 0;
const check = (label, ok, detail = "") => {
  checks += 1;
  if (!ok) {
    failures.push(`${label}${detail ? `: ${detail}` : ""}`);
  }
};
const same = (label, got, want) =>
  check(label, JSON.stringify(got) === JSON.stringify(want), `got ${JSON.stringify(got)}`);

const TABS = `[...document.querySelectorAll(".github-pull .tab-btn")].map((tab) => tab.textContent.trim())`;
const GUIDE_TAB = `[...document.querySelectorAll(".github-pull .tab-btn")].find((tab) => tab.textContent.trim() === "Guided Review")`;
const ROWS = `[...document.querySelectorAll(".github-pull-guide-excerpt .diff-line")].map((line) => {
  const code = line.querySelector(".diff-line-text");
  const style = getComputedStyle(code);
  const boxes = [...line.children].map((child) => child.getBoundingClientRect());
  return {
    op: ["add", "del", "context"].find((op) => line.classList.contains(\`diff-line-\${op}\`)),
    text: code.textContent,
    noHighlight: code.closest("pre") === null,
    // The diff's type: the guide's rows are the size of Changes' rows.
    fontSize: style.fontSize,
    monoBlock: getComputedStyle(document.documentElement).getPropertyValue("--mono-block-font-size").trim(),
    padding: style.padding,
    background: style.backgroundColor,
    tinted: getComputedStyle(line).backgroundColor !== "rgba(0, 0, 0, 0)",
    // One row: the columns share a top, and each starts after the one before it ends.
    oneLine: Math.max(...boxes.map((box) => box.top)) - Math.min(...boxes.map((box) => box.top)) <= 1,
    apart: boxes.every((box, at) => at === 0 || box.left >= boxes[at - 1].right - 1),
  };
})`;

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
  const press = async (key) => {
    const code = {
      key,
      code: `Key${key.toUpperCase()}`,
      windowsVirtualKeyCode: key.toUpperCase().charCodeAt(0),
    };
    await chrome.send("Input.dispatchKeyEvent", { type: "keyDown", text: key, ...code });
    await chrome.send("Input.dispatchKeyEvent", { type: "keyUp", ...code });
  };
  const pressR = () => press("r");
  const settled = (title) =>
    waitFor(
      `document.querySelector(".github-pull-guide-step .github-pull-guide-title")?.textContent === ${JSON.stringify(title)}`,
    );
  const introduced = () =>
    waitFor(`document.querySelector(".github-pull-guide-position")?.textContent === "Overview"`);
  /** Click the guide's button named *label*. */
  const click = (label) =>
    evaluate(
      `document.querySelector(${JSON.stringify(`.github-pull-guided-pr button[aria-label="${label}"]`)}).click()`,
    );
  const said = async () => {
    await waitFor(
      `document.querySelector(".github-pull-guided-pr > p.github-pull-quiet:not([hidden])")?.textContent`,
    );
    return evaluate(
      `document.querySelector(".github-pull-guided-pr > p.github-pull-quiet:not([hidden])").textContent`,
    );
  };
  await chrome.send("Page.enable");

  // 1. A pull request with a guide: the tab leads the bar once its record is in, its front
  // page is the guide, opened by the description, and Conversation has an address of its own,
  // where the description's block is a card. R opens the guide once the page has its keys.
  await go("/pull/7");
  await waitFor(`${GUIDE_TAB} !== undefined`);
  same("the tabs of a pull request with a guide", await evaluate(TABS), [
    "Guided Review",
    "Conversation",
    "Docs",
    "Changes",
    "Checks",
  ]);
  await introduced();
  same(
    "the front page is the guide",
    await evaluate(`${GUIDE_TAB}.getAttribute("aria-selected")`),
    "true",
  );
  await waitFor(`document.querySelector(".github-pull-guide-introduction .kpress-prose") !== null`);
  same(
    "the guide opens with the description, without its block",
    await evaluate(
      `document.querySelector(".github-pull-guide-introduction").textContent.replace(/\\s+/g, " ").trim()`,
    ),
    "The app learns to count to two. Its count and its explanation live in separate files.",
  );
  same(
    "Conversation's address",
    await evaluate(
      `[...document.querySelectorAll(".github-pull .tab-btn")].find((tab) => tab.textContent.trim() === "Conversation").getAttribute("href")`,
    ),
    "/pull/7/conversation",
  );
  await waitFor(`${GUIDE_TAB}.getAttribute("aria-keyshortcuts") !== null`);
  await press("c");
  await waitFor(`location.pathname === "/pull/7/conversation"`);
  await waitFor(
    `[...document.querySelectorAll(".github-pull-text + .notice")].some((node) => node.textContent.includes("guided review"))`,
  );
  check(
    "Conversation's description has no guided-pr block",
    await evaluate(
      `!document.querySelector(".github-pull-text").textContent.includes("softschema")`,
    ),
  );
  await pressR();
  await waitFor(`location.pathname === "/pull/7/guided"`);
  await introduced();
  same(
    "the step list",
    await evaluate(
      `[...document.querySelectorAll(".github-pull-guide-steps-title")].map((title) => title.textContent)`,
    ),
    ["Overview", "Start with the count", "Read the new guide"],
  );
  same(
    "the arrows are icons",
    await evaluate(`document.querySelectorAll(".github-pull-guide-arrows button svg").length`),
    2,
  );
  same(
    "each arrow sits at its button's center",
    await evaluate(`[...document.querySelectorAll(".github-pull-guide-arrows button")].map((button) => {
      const outer = button.getBoundingClientRect();
      const inner = button.querySelector("svg").getBoundingClientRect();
      const off = (a, b, c, d) => Math.abs((a + b) / 2 - (c + d) / 2) <= 1;
      return off(outer.left, outer.right, inner.left, inner.right) && off(outer.top, outer.bottom, inner.top, inner.bottom);
    })`),
    [true, true],
  );
  await evaluate(
    `[...document.querySelectorAll(".github-pull-guide-steps-link")].find((link) => link.textContent.includes("Start with the count")).click()`,
  );
  await settled("Start with the count");
  same(
    "the step's text sits at the description's inset",
    await evaluate(`getComputedStyle(document.querySelector(".github-pull-guide-prose")).padding`),
    await evaluate(`(() => {
      const text = document.createElement("div");
      text.className = "github-pull-text";
      document.querySelector(".github-pull-guided-pr").append(text);
      const padding = getComputedStyle(text).padding;
      text.remove();
      return padding;
    })()`),
  );

  // 2. Rows after the shell's highlighter. Wait until it has loaded, put a control block beside
  // the excerpt, and run the shell's own pass over the page.
  await waitFor(`typeof hljs !== "undefined" && typeof highlightCode === "function"`);
  const pass = await evaluate(`(() => {
    const pre = document.createElement("pre");
    const code = document.createElement("code");
    code.textContent = "function control() { return 1; }";
    pre.append(code);
    document.body.append(pre);
    highlightCode(document);
    const highlighted = code.classList.contains("hljs");
    pre.remove();
    return { highlighted, excerpt: document.querySelectorAll(".github-pull-guide-excerpt pre").length };
  })()`);
  check("the shell's pass highlights a block outside the excerpt", pass.highlighted === true);
  check("and the excerpt has no block for it", pass.excerpt === 0, `${pass.excerpt} blocks`);
  same(
    "the excerpt opens on the diff's hunk bar",
    await evaluate(
      `[...document.querySelectorAll(".github-pull-guide-excerpt .diff-hunk-header")].map((bar) => bar.textContent)`,
    ),
    ["@@ -1,1 +1,2 @@"],
  );
  const rows = await evaluate(ROWS);
  same(
    "step 1's rows",
    rows.map((row) => `${row.op} ${row.text}`),
    ["context one", "add two"],
  );
  for (const row of rows) {
    check(`${row.op} row's code is no block for the highlighter`, row.noHighlight);
    check(`${row.op} row's code has no padding of its own`, row.padding === "0px", row.padding);
    check(
      `${row.op} row's code has no background of its own`,
      row.background === "rgba(0, 0, 0, 0)",
      row.background,
    );
    check(`${row.op} row is one line, its columns apart`, row.oneLine && row.apart);
    check(
      `${row.op} row is set at the diff's code size`,
      row.fontSize === row.monoBlock,
      `${row.fontSize} vs ${row.monoBlock}`,
    );
  }
  same(
    "only the changed row is tinted",
    rows.map((row) => row.tinted),
    [false, true],
  );

  // 4. Steps, Open full diff.
  await click("Next step");
  await settled("Read the new guide");
  const second = await evaluate(ROWS);
  same(
    "step 2's added line, then the whole diff of the file it cites with no range",
    second.map((row) => `${row.op} ${row.text}`),
    ["add # New", "context one", "add two"],
  );
  check(
    "its row too",
    second.every((row) => row.noHighlight && row.padding === "0px"),
  );
  await click("Previous step");
  await settled("Start with the count");
  // The way on below a step names the next one.
  same(
    "the way on below step 1",
    await evaluate(`document.querySelector(".github-pull-guide-pager-next").textContent`),
    "Step 2: Read the new guide",
  );
  await evaluate(`document.querySelector(".github-pull-guide-pager-next").click()`);
  await settled("Read the new guide");
  await evaluate(`document.querySelector(".github-pull-guide-reference-header a").click()`);
  await waitFor(`location.pathname.startsWith("/pull/7/files")`);
  same(
    "Open full diff goes to the file's Changes address",
    await evaluate("location.pathname"),
    "/pull/7/files/docs/new.md",
  );

  // 1. A pull request with none: no tab, R opens nothing, and its address says so in place.
  await go("/pull/10");
  await waitFor(`document.querySelectorAll(".github-pull .tab-btn").length >= 3`);
  await waitFor(
    `document.querySelector(".github-pull .tab-btn").getAttribute("aria-keyshortcuts") !== null`,
  );
  same("the tabs of a pull request with no guide", await evaluate(TABS), [
    "Conversation",
    "Docs",
    "Changes",
    "Checks",
  ]);
  await pressR();
  await evaluate("new Promise((resolve) => setTimeout(resolve, 500))");
  same("R opens nothing there", await evaluate("location.pathname"), "/pull/10");
  await go("/pull/10/guided");
  same("its guided address says so", await said(), "This pull request has no guide.");
  check("and keeps the tab it was asked for", (await evaluate(TABS)).includes("Guided Review"));

  // 4. A stale guide (its head is not the record's) still shows its steps, under a notice at
  // the top of the page that says what is out of date; a guide that cannot be read says why.
  await go("/pull/8/guided");
  await introduced();
  await click("Next step");
  await settled("Start with the count");
  await waitFor(`document.querySelector(".github-pull-guide-stale") !== null`);
  same(
    "a stale guide's notice leads the page",
    await evaluate(
      `document.querySelector(".github-pull-guided-pr").firstElementChild.contains(document.querySelector(".github-pull-guide-stale"))`,
    ),
    true,
  );
  check(
    "and names the revisions and the commits since",
    await evaluate(`(() => {
      const text = document.querySelector(".github-pull-guide-stale").textContent;
      return text.includes("It was written for head 85fcb2f") && text.includes("more guide");
    })()`),
  );
  same(
    "its step is a guided-review card",
    await evaluate(
      `[...document.querySelector(".github-pull-guide-card .github-pull-card-head").children].map((part) => part.textContent)`,
    ),
    ["Guided Review", "Step 1 of 2 · cites files changed since the guide"],
  );
  // The badge stands apart from its label, as a page header's state badge from its line.
  same(
    "the badge is the page header's gap from its label",
    await evaluate(`(() => {
      const [badge, label] = document.querySelector(".github-pull-guide-card .github-pull-card-head").children;
      return Math.round(label.getBoundingClientRect().left - badge.getBoundingClientRect().right);
    })()`),
    8,
  );
  await go("/pull/9/guided");
  same("two blocks", await said(), "Use one guided-pr block in the pull request description.");
} finally {
  await chrome.close();
}
if (failures.length > 0) {
  process.stderr.write(`${failures.join("\n")}\n`);
  process.exitCode = 1;
} else {
  process.stdout.write(`guided PR in Chrome: ${checks} checks passed\n`);
}

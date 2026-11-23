// Guided PR in headless Chrome against a live `metab` server that serves the GitHub stand-in
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
// 1. The tab and its key on the real shell: Guided PR sits between Changes and Checks on a pull
//    request whose description has a guide, D opens it once the page has attached its keys, and on
//    one with no guide there is no tab and D opens nothing.
// 2. An excerpt's rows after the shell's highlighter has run over the page. The shell highlights
//    every `pre code` that does not carry `no-highlight` (`highlightCode` in app.js), one row at a
//    time as a one-line snippet, which gave each row a padded, gray block of its own inside the
//    row's tint (review A of #599, A3). A control block outside the excerpt proves the pass runs
//    here: it is highlighted, and the rows are not.
// 3. A row is one line: its number columns, its mark, and its code share a top and do not overlap,
//    and the tint is the row's, never the code's.
// 4. Next and Previous move between steps, Open full diff goes to the file's Changes address, and
//    a guide that cannot be read says so in place: none, stale, and two blocks.
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
const GUIDE_TAB = `[...document.querySelectorAll(".github-pull .tab-btn")].find((tab) => tab.textContent.trim() === "Guided PR")`;
const ROWS = `[...document.querySelectorAll(".github-pull-guide-line")].map((line) => {
  const code = line.querySelector(".diff-line-text");
  const style = getComputedStyle(code);
  const boxes = [...line.children].map((child) => child.getBoundingClientRect());
  return {
    op: line.dataset.op,
    text: code.textContent,
    noHighlight: code.closest("pre") === null,
    // The diff's type: the guide's rows are the size of Changes' rows.
    fontSize: style.fontSize,
    monoBlock: getComputedStyle(document.documentElement).getPropertyValue("--mono-block-font-size").trim(),
    hljs: code.classList.contains("hljs") || code.querySelector("span") !== null,
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
  const pressD = async () => {
    const code = { key: "d", code: "KeyD", windowsVirtualKeyCode: 68 };
    await chrome.send("Input.dispatchKeyEvent", { type: "keyDown", text: "d", ...code });
    await chrome.send("Input.dispatchKeyEvent", { type: "keyUp", ...code });
  };
  const settled = (title) =>
    waitFor(
      `document.querySelector(".github-pull-guide-step .github-pull-guide-title")?.textContent === ${JSON.stringify(title)}`,
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

  // 1. A pull request with a guide: the tab joins the bar once its record is in, and D opens it
  // once the page has attached its keys.
  await go("/pull/7");
  await waitFor(`${GUIDE_TAB} !== undefined`);
  same("the tabs of a pull request with a guide", await evaluate(TABS), [
    "Conversation",
    "Changes",
    "Guided PR",
    "Checks",
  ]);
  await waitFor(`${GUIDE_TAB}.getAttribute("aria-keyshortcuts") !== null`);
  await pressD();
  await waitFor(`location.pathname === "/pull/7/guided"`);
  await settled("Start with the count");
  same(
    "the guide's tab is the one shown",
    await evaluate(`${GUIDE_TAB}.getAttribute("aria-selected")`),
    "true",
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
    return { highlighted, excerpt: document.querySelectorAll(".github-pull-guide-excerpt .hljs").length };
  })()`);
  check("the shell's pass highlights a block outside the excerpt", pass.highlighted === true);
  check("and no row of the excerpt", pass.excerpt === 0, `${pass.excerpt} highlighted`);
  const rows = await evaluate(ROWS);
  same(
    "step 1's rows",
    rows.map((row) => `${row.op} ${row.text}`),
    ["context one", "add two"],
  );
  for (const row of rows) {
    check(`${row.op} row's code skips the highlighter`, row.noHighlight && !row.hljs);
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
  await evaluate(
    `[...document.querySelectorAll(".github-pull-guided-pr button")].find((button) => button.textContent === "Next").click()`,
  );
  await settled("Read the new guide");
  const second = await evaluate(ROWS);
  same(
    "step 2's added line",
    second.map((row) => `${row.op} ${row.text}`),
    ["add # New"],
  );
  check(
    "its row too",
    second.every((row) => row.noHighlight && !row.hljs && row.padding === "0px"),
  );
  await evaluate(
    `[...document.querySelectorAll(".github-pull-guided-pr button")].find((button) => button.textContent === "Previous").click()`,
  );
  await settled("Start with the count");
  await evaluate(
    `[...document.querySelectorAll(".github-pull-guided-pr button")].find((button) => button.textContent === "Next").click()`,
  );
  await settled("Read the new guide");
  await evaluate(`document.querySelector(".github-pull-guide-reference-header a").click()`);
  await waitFor(`location.pathname.startsWith("/pull/7/files")`);
  same(
    "Open full diff goes to the file's Changes address",
    await evaluate("location.pathname"),
    "/pull/7/files/docs/new.md",
  );

  // 1. A pull request with none: no tab, D opens nothing, and its address says so in place.
  await go("/pull/10");
  await waitFor(`document.querySelectorAll(".github-pull .tab-btn").length >= 3`);
  await waitFor(
    `document.querySelector(".github-pull .tab-btn").getAttribute("aria-keyshortcuts") !== null`,
  );
  same("the tabs of a pull request with no guide", await evaluate(TABS), [
    "Conversation",
    "Changes",
    "Checks",
  ]);
  await pressD();
  await evaluate("new Promise((resolve) => setTimeout(resolve, 500))");
  same("D opens nothing there", await evaluate("location.pathname"), "/pull/10");
  await go("/pull/10/guided");
  same("its guided address says so", await said(), "This pull request has no guide.");
  check("and keeps the tab it was asked for", (await evaluate(TABS)).includes("Guided PR"));

  // 4. A guide that cannot be read says why: stale (its head is not the record's), and two blocks.
  await go("/pull/8/guided");
  same(
    "a stale guide",
    await said(),
    "This guide is out of date. Its author needs to update it for the current comparison.",
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

// Guided Review in headless Chrome against a live `metab` server that serves the GitHub stand-in
// with guides in the descriptions of pull requests 7 to 9, 8's rewritten into groups, and none
// in 10's.
//
//   CHROME_BIN=... CHROME_PROFILES=<dir> node tests/dom/github-guided-review-chrome.mjs <base URL>
//
// tests/test_github_guided_review_chrome.py builds that server, owns the profile directory, and stops
// this process's whole group, Chrome included, however the run ends (tests/process_group.py).
//
// What only a browser holds, and the browserless sessions cannot (github-guided-review-session.js,
// github-guided-review-mount-behavior.js, and the tab and key in github-pull-page-mount-behavior.js):
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
//    cannot be read says so in place: none and two blocks. A stale guide still reads, under
//    one warning and its remedy, with no list. Below the overview there is no way back, and
//    below the last step no way on (mb-meoh): the pager's buttons once set a display that
//    outranked `[hidden]`, which drew a bare arrow at each end.
// 5. Where a list's markers fall (mb-u46w): the out-of-date notice once listed commits in a
//    list whose bullets sat on the notice's left border. An outside marker has no box of its
//    own, so each is measured by setting it inside for a moment, which moves the item's first
//    text right by the marker's width: every marker in the guide sits inside its panel's
//    border, a description's list among them, and a list placed as the old notice drew its
//    own is caught, which shows the measurement sees the fault.
// 6. A guide in groups (8's, as the test rewrites it): each group is the shell's group heading in the step list,
//    above its steps and starting on the edge their numbers start on, with nothing to press
//    and no number, while the steps keep theirs; a step's card names its group before its
//    place, and a group's note sits above its first step's card. A guide without groups (7's)
//    has no heading.
import { launchChrome } from "./chrome-session.mjs";

const [base] = process.argv.slice(2);
if (!base || !process.env.CHROME_BIN || !process.env.CHROME_PROFILES) {
  throw new Error("usage: CHROME_BIN CHROME_PROFILES github-guided-review-chrome.mjs <base>");
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
/** Whether the way back and the way on below a step each have a box on the page. A button
 * marked `hidden` has none. */
const WAYS = `[".github-pull-guide-pager-previous", ".github-pull-guide-pager-next"].map(
  (selector) => (document.querySelector(selector)?.getClientRects().length ?? 0) > 0,
)`;
/** Each list marker under *scope*: how far its left edge is inside its panel's border, in
 * pixels, negative when it is outside. A marker is the list's own, measured by setting it
 * inside for a moment, or a bullet drawn as a positioned `::before`, as KPress draws a
 * description's. */
const MARKERS = (scope) => `(() => {
  const found = [];
  for (const item of ${scope}.querySelectorAll("li")) {
    if (item.getClientRects().length === 0) {
      continue;
    }
    const style = getComputedStyle(item);
    const before = getComputedStyle(item, "::before");
    let left = null;
    if (style.display === "list-item" && style.listStyleType !== "none") {
      const probe = document.createElement("span");
      item.prepend(probe);
      const start = probe.getBoundingClientRect().left;
      item.style.listStylePosition = "inside";
      const width = probe.getBoundingClientRect().left - start;
      item.style.listStylePosition = "";
      probe.remove();
      left = start - width;
    } else if (
      before.content !== "none" &&
      before.position === "absolute" &&
      style.position !== "static" &&
      parseFloat(before.width) > 0
    ) {
      left = item.getBoundingClientRect().left + parseFloat(style.borderLeftWidth) + parseFloat(before.left);
    }
    if (left === null) {
      continue;
    }
    let panel = item.parentElement;
    while (panel !== null && parseFloat(getComputedStyle(panel).borderLeftWidth) === 0) {
      panel = panel.parentElement;
    }
    const edge = panel.getBoundingClientRect().left + parseFloat(getComputedStyle(panel).borderLeftWidth);
    found.push(Math.floor(left - edge));
  }
  return found;
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
  // A step is composed out of sight (`.github-pull-guide-incoming`, guided-review.js) and
  // shows whole once what it draws is in, so a check reads only the step shown.
  const settled = (title) =>
    waitFor(
      `document.querySelector(".github-pull-guide-step:not(.github-pull-guide-incoming) .github-pull-guide-title")?.textContent === ${JSON.stringify(title)}`,
    );
  const introduced = () =>
    waitFor(`document.querySelector(".github-pull-guide-position")?.textContent === "Overview"`);
  /** Click the guide's button named *label*. */
  const click = (label) =>
    evaluate(
      `document.querySelector(${JSON.stringify(`.github-pull-guided-review button[aria-label="${label}"]`)}).click()`,
    );
  const said = async () => {
    await waitFor(
      `document.querySelector(".github-pull-guided-review > p.github-pull-quiet:not([hidden])")?.textContent`,
    );
    return evaluate(
      `document.querySelector(".github-pull-guided-review > p.github-pull-quiet:not([hidden])").textContent`,
    );
  };
  await chrome.send("Page.enable");

  // 1. A pull request with a guide: the tab leads the bar once its record is in, its front
  // page is the guide, opened by the description, and Conversation has an address of its own,
  // where the description's block is a card. R opens the guide once the page has its keys,
  // at the front page's address, which shows it.
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
  same(
    "Guided Review's address is the front page's",
    await evaluate(`${GUIDE_TAB}.getAttribute("href")`),
    "/pull/7",
  );
  await waitFor(`${GUIDE_TAB}.getAttribute("aria-keyshortcuts") !== null`);
  await press("c");
  await waitFor(`location.pathname === "/pull/7/conversation"`);
  await waitFor(
    `[...document.querySelectorAll(".github-pull-text + .notice")].some((node) => node.textContent.includes("guided review"))`,
  );
  check(
    "Conversation's description has no guided-review block",
    await evaluate(
      `!document.querySelector(".github-pull-text").textContent.includes("softschema")`,
    ),
  );
  await pressR();
  await waitFor(`location.pathname === "/pull/7"`);
  await introduced();
  await waitFor(`document.querySelector(".github-pull-guide-pager")?.hidden === false`);
  same("below the overview, the way on and no way back", await evaluate(WAYS), [false, true]);
  same(
    "the step list",
    await evaluate(
      `[...document.querySelectorAll(".github-pull-guide-steps-title")].map((title) => title.textContent)`,
    ),
    ["Overview", "Start with the count", "Read the new guide"],
  );
  same(
    "a guide without groups lists no group heading",
    await evaluate(`document.querySelectorAll(".github-pull-guide-steps-heading").length`),
    0,
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
      document.querySelector(".github-pull-guided-review").append(text);
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
  same("below a middle step, both ways", await evaluate(WAYS), [true, true]);
  await click("Next step");
  await settled("Read the new guide");
  same("below the last step, the way back and no way on", await evaluate(WAYS), [true, false]);
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

  // 4. A stale guide (its head is not the record's) still shows its steps, read at the
  // current head, under one warning and its remedy at the top of the page; a guide that
  // cannot be read says why.
  await go("/pull/8/guided");
  await introduced();
  await waitFor(`document.querySelector(".github-pull-guide-stale") !== null`);
  await waitFor(`document.querySelector(".github-pull-guide-introduction .kpress-prose") !== null`);
  same(
    "a stale guide's notice leads the page",
    await evaluate(
      `document.querySelector(".github-pull-guided-review").firstElementChild.contains(document.querySelector(".github-pull-guide-stale"))`,
    ),
    true,
  );
  same(
    "and says one warning and its remedy",
    await evaluate(`document.querySelector(".github-pull-guide-stale").textContent`),
    "This guide was written for an earlier version of this pull request, so steps marked changed may not match it. Its author can update the guide.",
  );
  same(
    "the steps it marks",
    await evaluate(
      `[...document.querySelectorAll(".github-pull-guide-steps-link")].map((link) => link.querySelector(".github-pull-guide-step-changed")?.textContent ?? "")`,
    ),
    ["", "changed", "changed"],
  );

  // 5. Where a list's markers fall: none in the notice, every one inside its panel, and the
  // old notice's list caught.
  same(
    "the notice holds no list",
    await evaluate(
      `document.querySelector(".github-pull-guide-stale").querySelectorAll("ul, ol, li").length`,
    ),
    0,
  );
  const inset = await evaluate(`(() => {
    const prose = document.querySelector(".github-pull-guide-introduction .kpress-prose");
    const list = document.createElement("ul");
    list.innerHTML = "<li>A description's list, drawn as KPress draws it</li>";
    prose.append(list);
    const found = ${MARKERS(`document.querySelector(".github-pull-guided-review")`)};
    list.remove();
    return found;
  })()`);
  check(
    "every list marker in the guide sits inside its panel, a description's among them",
    inset.length === 1 && inset.every((gap) => gap >= 0),
    JSON.stringify(inset),
  );
  const caught = await evaluate(`(() => {
    const notice = document.querySelector(".github-pull-guide-stale");
    const list = document.createElement("ul");
    list.innerHTML = "<li>8ae2761 more guide</li>";
    notice.append(list);
    const found = ${MARKERS(`notice`)};
    list.remove();
    return found;
  })()`);
  check(
    "a list placed as the old notice drew its commits is caught on the border",
    caught.length === 1 && caught[0] < 0,
    JSON.stringify(caught),
  );

  // 6. 8's guide puts each step in a group.
  same(
    "a grouped guide's list: each group's heading above its steps, which keep their numbers",
    await evaluate(
      `[...document.querySelectorAll(".github-pull-guide-steps-heading, .github-pull-guide-steps-link")].map((node) =>
        node.matches("button") ? node.innerText.replace(/\\s+/g, " ").trim() : \`[\${node.textContent}]\`)`,
    ),
    [
      "Overview",
      "[The count]",
      "1 Start with the count changed",
      "[The docs]",
      "2 Read the new guide changed",
    ],
  );
  const headings =
    await evaluate(`[...document.querySelectorAll(".github-pull-guide-steps-heading")].map((heading) => {
    const style = getComputedStyle(heading);
    const probe = document.createElement("div");
    probe.className = "group-heading";
    probe.textContent = "Probe";
    document.body.append(probe);
    const shell = getComputedStyle(probe);
    const register = ["color", "fontSize", "fontWeight", "letterSpacing", "textTransform"].every(
      (name) => style[name] === shell[name],
    );
    probe.remove();
    const steps = heading.nextElementSibling;
    const first = steps.querySelector(".github-pull-guide-steps-link");
    const number = first.querySelector(".github-pull-guide-steps-number");
    const text = document.createRange();
    text.selectNodeContents(heading);
    return {
      control: heading.closest("button, a") !== null || heading.tabIndex >= 0,
      register,
      above: heading.getBoundingClientRect().bottom <= first.getBoundingClientRect().top + 0.5,
      onTheNumbers: Math.abs(text.getBoundingClientRect().left - number.getBoundingClientRect().left) <= 1,
      named: steps.getAttribute("aria-labelledby") === heading.id && heading.id !== "",
    };
  })`);
  same(
    "each heading is the shell's group heading, no control, above its steps, on their numbers' edge, and names their list",
    headings,
    Array(2).fill({ control: false, register: true, above: true, onTheNumbers: true, named: true }),
  );
  await click("Next step");
  await settled("Start with the count");
  same(
    "its step is a guided-review card, named by its group",
    await evaluate(
      `[...document.querySelector(".github-pull-guide-card .github-pull-card-head").children].map((part) => part.textContent)`,
    ),
    ["Guided Review", "The count · Step 1 of 2 · changed"],
  );
  same(
    "the group's note sits above its first step's card",
    await evaluate(`(() => {
      const note = document.querySelector(".github-pull-guide-step:not(.github-pull-guide-incoming) > .github-pull-guide-group-note");
      const card = document.querySelector(".github-pull-guide-card");
      return note === null ? null : [note.textContent, note.getBoundingClientRect().bottom <= card.getBoundingClientRect().top];
    })()`),
    ["Read the value before its explanation.", true],
  );
  // A note is Markdown the route rendered, set as a description's paragraphs are: a line
  // break in it is the render's, not the source's, and a group's note is in the type of the
  // step's own note.
  same(
    "a note's rendered paragraph is a description's, and the group's note is in its type",
    await evaluate(`(() => {
      const note = getComputedStyle(document.querySelector(".github-pull-guide-card .kpress-prose > h2 + p"));
      const group = getComputedStyle(document.querySelector(".github-pull-guide-group-note .kpress-prose > p"));
      return [note.whiteSpace, group.whiteSpace, group.fontSize === note.fontSize, group.fontFamily === note.fontFamily];
    })()`),
    ["normal", "normal", true, true],
  );
  same(
    "its file, no longer in the pull request's changes, says so in its place",
    await evaluate(
      `[...document.querySelectorAll(".github-pull-guide-reference > .diff-file-body > p")].map((note) => note.textContent)`,
    ),
    ["This file is no longer in the pull request's changes."],
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
  await click("Next step");
  await settled("Read the new guide");
  same(
    "a group without a note shows none above its step",
    await evaluate(
      `[document.querySelector(".github-pull-guide-card .github-pull-card-head").lastElementChild.textContent, document.querySelector(".github-pull-guide-group-note")]`,
    ),
    ["The docs · Step 2 of 2 · changed", null],
  );
  await go("/pull/9/guided");
  same("two blocks", await said(), "Use one guided-review block in the pull request description.");
} finally {
  await chrome.close();
}
if (failures.length > 0) {
  process.stderr.write(`${failures.join("\n")}\n`);
  process.exitCode = 1;
} else {
  process.stdout.write(`guided review in Chrome: ${checks} checks passed\n`);
}

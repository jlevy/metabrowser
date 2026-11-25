// Guided Review's references past its pull request in headless Chrome, against a live `metab`
// server that serves the GitHub stand-in with pull request 7's guide rewritten to cite every
// kind of reference (`kinds` in tests/github_pull_fixture.py): its second step cites 8, a
// merged pull request; 10's draft document and 9's change to src/app.txt; 50, which the
// list of pull requests alone knows, and 2000, which nothing here knows; 7's own head as a
// commit; and a commit the store lacks.
//
//   CHROME_BIN=... CHROME_PROFILES=<dir> node tests/dom/github-guided-review-kinds-chrome.mjs <base URL>
//
// tests/test_github_guided_review_chrome.py builds that server, owns the profile directory, and
// stops this process's whole group, Chrome included, however the run ends.
//
// What only a browser holds, and the browserless session cannot
// (github-guided-review-mount-behavior.js pins the rows' words and where they go):
//
// 1. A row is one line, the stack menu's member row's height, inside its bordered card, its
//    icon or ID, its number, its dot, and its title side by side, the title cut short at
//    the row's end with its ellipsis when it does not fit, at a desktop width and at a
//    phone's with the navigation pane hidden, as the reading column is on a phone, and
//    nothing runs past the page.
// 2. Another pull request's document is drawn by the diff view from that pull request's own
//    routes, which the real server admits: its bar is the diff's own, and the guide's bar
//    for the file names the pull request only when the view could not draw it.
// 3. A pull request's row goes to that pull request's page in place.
import { launchChrome } from "./chrome-session.mjs";

const [base] = process.argv.slice(2);
if (!base || !process.env.CHROME_BIN || !process.env.CHROME_PROFILES) {
  throw new Error("usage: CHROME_BIN CHROME_PROFILES github-guided-review-kinds-chrome.mjs <base>");
}
// One page load or fake gh fetch; a loaded machine has needed several seconds for one.
const STEP_MS = 30000;
const STEP = "Read it beside its neighbors";
// A title long enough to pass any row's width here, set in place of one row's.
const LONG = "A title much longer than any row is wide, ".repeat(6).trim();

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

/** Each row of the step on screen, as the browser lays it out. */
const ROWS = `[...document.querySelectorAll(".github-pull-guide-row")].map((card) => {
  const row = card.querySelector(".github-pull-guide-row-link");
  const box = row.getBoundingClientRect();
  const frame = card.getBoundingClientRect();
  const title = row.querySelector(".github-pull-guide-row-title");
  const parts = [...row.children].map((part) => part.getBoundingClientRect());
  const style = title ? getComputedStyle(title) : null;
  return {
    text: row.textContent.replace(/\\s+/g, " ").trim(),
    height: Math.round(box.height),
    rowHeight: parseFloat(getComputedStyle(document.documentElement).getPropertyValue("--ui-row-height")),
    // The row inside its card's border, and the card inside the step's.
    inside: box.left >= frame.left && box.right <= frame.right + 0.5,
    // Its parts on one line: they share a middle, each after the one before.
    oneLine: parts.every((part) => Math.abs((part.top + part.bottom) / 2 - (box.top + box.bottom) / 2) <= 2),
    apart: parts.every((part, at) => at === 0 || part.left >= parts[at - 1].right - 0.5),
    cut: title ? title.scrollWidth > title.clientWidth : null,
    ellipsis: style ? style.textOverflow : null,
    bordered: parseFloat(getComputedStyle(card).borderTopWidth) > 0,
  };
})`;
const PAGE_FITS = `document.documentElement.scrollWidth <= window.innerWidth`;

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
  // `\`, which hides the navigation pane and shows it again (static/nav-collapse.js).
  const togglePane = async () => {
    const key = { key: "\\", code: "Backslash", windowsVirtualKeyCode: 220 };
    await chrome.send("Input.dispatchKeyEvent", { type: "keyDown", text: "\\", ...key });
    await chrome.send("Input.dispatchKeyEvent", { type: "keyUp", ...key });
  };
  await chrome.send("Page.enable");
  await go("/pull/7");
  await waitFor(
    `document.querySelector(".github-pull-guide-position")?.textContent === "Overview"`,
  );
  await evaluate(
    `[...document.querySelectorAll(".github-pull-guide-steps-link")].find((link) => link.textContent.includes(${JSON.stringify(STEP)})).click()`,
  );
  await waitFor(
    `document.querySelector(".github-pull-guide-step .github-pull-guide-title")?.textContent === ${JSON.stringify(STEP)}`,
  );
  await waitFor(`document.querySelectorAll(".github-pull-guide-row").length === 5`);

  // 1. The rows, at a desktop width, then with one title too long for its row, then at a
  // phone's width. The pane keeps its width in a narrow window, so it is hidden there, as
  // `\` hides it, and the reading column takes the window.
  const rows = await evaluate(ROWS);
  // Each with its author after its title, where this copy knows the pull request
  // (docs/design-system.md, "Authors Follow Pull Requests").
  same(
    "the step's pull requests",
    rows.slice(0, 3).map((row) => row.text),
    [
      "#8 · Say more in the guide · maintainer",
      "#50 · Work item 50 · contributor",
      "#2000 · Pull request #2000",
    ],
  );
  check(
    "the commit's row: its short ID, its subject, and when it was committed",
    /^[0-9a-f]{7,} count to two committed \S/.test(rows[3]?.text ?? ""),
    rows[3]?.text,
  );
  check(
    "a commit the store lacks: its short ID, and that it is unavailable",
    /^e{7,} This commit is unavailable\.$/.test(rows[4]?.text ?? ""),
    rows[4]?.text,
  );
  const measure = (label, measured) => {
    for (const [at, row] of measured.entries()) {
      check(
        `${label}: row ${at + 1} is one row high`,
        row.height === row.rowHeight,
        `${row.height} vs ${row.rowHeight}`,
      );
      check(`${label}: row ${at + 1} is inside its card`, row.inside);
      check(`${label}: row ${at + 1}'s parts are on one line`, row.oneLine && row.apart);
      check(`${label}: row ${at + 1}'s card has a border`, row.bordered);
      if (row.ellipsis !== null) {
        check(
          `${label}: row ${at + 1}'s title ends in an ellipsis when cut`,
          row.ellipsis === "ellipsis",
        );
      }
    }
  };
  measure("desktop", rows);
  await evaluate(
    `document.querySelector(".github-pull-guide-row .github-pull-guide-row-title").textContent = ${JSON.stringify(LONG)}`,
  );
  const long = await evaluate(ROWS);
  measure("a long title", long);
  check("a long title is cut short", long[0]?.cut === true);
  check("and runs nothing past the page", await evaluate(PAGE_FITS));
  await chrome.send("Emulation.setDeviceMetricsOverride", {
    width: 375,
    height: 812,
    deviceScaleFactor: 1,
    mobile: false,
  });
  await waitFor(`window.innerWidth === 375`);
  await togglePane();
  await waitFor(
    `document.querySelector(".container").hasAttribute("data-nav-collapsed") && document.querySelector(".github-pull-guide-row").getBoundingClientRect().width > 250`,
  );
  measure("a phone's width", await evaluate(ROWS));
  check("at a phone's width nothing runs past the page", await evaluate(PAGE_FITS));
  await togglePane();
  await waitFor(`!document.querySelector(".container").hasAttribute("data-nav-collapsed")`);
  await chrome.send("Emulation.clearDeviceMetricsOverride");

  // 2. Another pull request's document, drawn by the diff view from its own routes: the
  // view's own bar names the file, and no guide's bar stands above it.
  await waitFor(
    `document.querySelector(".github-pull-guide-document .diff-file-path")?.textContent === "docs/draft.md" || (document.querySelector(".github-pull-guide-document .diff-notice")?.textContent.trim() ?? "") !== ""`,
  );
  same(
    "10's document is drawn by the diff view",
    await evaluate(`(() => {
      const document_ = document.querySelector(".github-pull-guide-document");
      return {
        path: document_.querySelector(".diff-file-path")?.textContent ?? null,
        notice: document_.querySelector(".diff-notice")?.textContent.trim() || null,
        guideBar: document_.querySelector(".github-pull-guide-reference-header") !== null,
      };
    })()`),
    { path: "docs/draft.md", notice: null, guideBar: false },
  );
  same(
    "9's file is drawn under a bar that names its pull request, then its path",
    await evaluate(
      `[...document.querySelectorAll(".github-pull-guide-reference-header .diff-file-toggle")].map((name) => [...name.children].map((part) => part.textContent))`,
    ),
    [["#9", "src/app.txt"]],
  );
  check(
    "and the number stands apart from the path",
    await evaluate(`(() => {
      const [number, path] = document.querySelector(".github-pull-guide-reference-header .diff-file-toggle").children;
      return path.getBoundingClientRect().left - number.getBoundingClientRect().right >= 2;
    })()`),
  );

  // 3. A pull request's row opens its page in place.
  await evaluate(`document.querySelector(".github-pull-guide-pull").click()`);
  await waitFor(`location.pathname === "/pull/8"`);
  check("8's row opened its page", await evaluate(`location.pathname === "/pull/8"`));
} finally {
  await chrome.close();
}
if (failures.length > 0) {
  process.stderr.write(`${failures.join("\n")}\n`);
  process.exitCode = 1;
} else {
  process.stdout.write(`guided review references in Chrome: ${checks} checks passed\n`);
}

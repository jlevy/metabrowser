// Guided Review's references past its pull request in headless Chrome, against a live `metab`
// server that serves the GitHub stand-in with pull request 7's guide rewritten to cite every
// kind of reference (`kinds` in tests/github_pull_fixture.py): its second step cites 8, a
// merged pull request; 10's draft document and 9's change to src/app.txt; 50, which the
// list of pull requests alone knows, and 2000, which nothing here knows; 7's own head as a
// commit; and a commit the store lacks. Its native stacks are the stack page's, 70 (8, then
// 10) and 71 (8, 7, then 10), and 300 (9, then 50; `KINDS_STACKS` in
// tests/test_github_guided_review_chrome.py), so 8's place is in 71, 7's own stack, 50's in
// 300, another, and 2000 is in none. With `checkout` the server serves a reader's clone of
// the repository, which lacks 7's head (`--serve 7 <port> --checkout` in
// tests/github_pull_fixture.py), so the commit's row says it is not in this checkout, and
// only the rows are measured.
//
//   CHROME_BIN=... CHROME_PROFILES=<dir> node tests/dom/github-guided-review-kinds-chrome.mjs <base URL> [checkout]
//
// tests/test_github_guided_review_chrome.py builds that server, owns the profile directory, and
// stops this process's whole group, Chrome included, however the run ends.
//
// What only a browser holds, and the browserless session cannot
// (github-guided-review-mount-behavior.js pins the rows' words and where they go):
//
// 1. A row is one line, the stack menu's member row's height, inside its bordered card. A
//    pull request's is a stack's member row (stack-member-row.js), its title at the row's
//    start and its last part at the row's end. A place in its guide's own stack is drawn
//    bare and one in another stack after the Layers glyph, and each is an image that Chrome
//    names by its tip, which the row's link says in the place's letters' stead; a row with
//    no place has no dot before its number. A commit's row ends in its age, also when the
//    checkout lacks it and a note says so. The title, and a commit's subject and note, are
//    cut short with their ellipsis when they do not fit, at a desktop width and at a phone's
//    with the navigation pane hidden, as the reading column is on a phone, and nothing runs
//    past the page.
// 2. Another pull request's document is drawn by the diff view from that pull request's own
//    routes, which the real server admits: its bar is the diff's own, and the guide's bar
//    for the file names the pull request only when the view could not draw it.
// 3. A pull request's row goes to that pull request's page in place.
import { launchChrome } from "./chrome-session.mjs";

const [base, mode] = process.argv.slice(2);
if (
  !base ||
  ![undefined, "checkout"].includes(mode) ||
  !process.env.CHROME_BIN ||
  !process.env.CHROME_PROFILES
) {
  throw new Error(
    "usage: CHROME_BIN CHROME_PROFILES github-guided-review-kinds-chrome.mjs <base> [checkout]",
  );
}
const checkout = mode === "checkout";
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
const ROWS = `[...document.querySelectorAll(".github-pull-guide-step:not(.github-pull-guide-incoming) .github-pull-guide-row")].map((card) => {
  const row = card.querySelector(".github-pull-guide-row-link");
  const box = row.getBoundingClientRect();
  const frame = card.getBoundingClientRect();
  const title = row.querySelector(".github-pull-guide-row-title, .github-pull-stack-member-title");
  const parts = [...row.children].map((part) => part.getBoundingClientRect());
  const style = title ? getComputedStyle(title) : null;
  // A pull request's run, each part shown, in the order drawn, and the part that ends the
  // row: the run's last shown, and a commit's age, its own element.
  const run = row.querySelector(".github-pull-stack-member-copy");
  const shown = (part) => part.getClientRects().length > 0;
  const runParts = run ? [...run.children].filter(shown) : [];
  const age = row.querySelector(".github-pull-age");
  const last = run ? runParts.at(-1) : age;
  const edge = box.right - parseFloat(getComputedStyle(row).paddingRight);
  const position = row.querySelector(".github-pull-stack-member-position");
  const placed = (position?.textContent.trim() ?? "") !== "";
  const number = run?.querySelector(".github-pull-stack-member-number") ?? null;
  return {
    text: row.textContent.replace(/\\s+/g, " ").trim(),
    height: Math.round(box.height),
    rowHeight: parseFloat(getComputedStyle(document.documentElement).getPropertyValue("--ui-row-height")),
    // The row inside its card's border, and the card inside the step's.
    inside: box.left >= frame.left && box.right <= frame.right + 0.5,
    // Its parts on one line: they share a middle, each after the one before.
    oneLine: parts.every((part) => Math.abs((part.top + part.bottom) / 2 - (box.top + box.bottom) / 2) <= 2),
    apart: parts.every((part, at) => at === 0 || part.left >= parts[at - 1].right - 0.5),
    runApart: runParts.every(
      (part, at) =>
        at === 0 ||
        part.getBoundingClientRect().left >= runParts[at - 1].getBoundingClientRect().right - 0.5,
    ),
    // Its last part ends where the row's text ends: a pull request's author, or its number
    // when it has none, and a commit's age.
    ends: last ? Math.abs(last.getBoundingClientRect().right - edge) <= 1 : null,
    place: placed ? position.textContent.trim() : null,
    tip: position?.getAttribute("data-tip-text") ?? null,
    // The Layers glyph before a place, which names another stack, drawn.
    glyph: [...(position?.querySelectorAll(".github-pull-stack-other svg") ?? [])].some(
      (glyph) => glyph.getBoundingClientRect().width > 0,
    ),
    // A commit's row: whether it goes anywhere, a quiet note shown, and its age shown.
    linked: row.tagName === "A",
    note: [...row.querySelectorAll(".github-pull-quiet")].some(shown),
    age: age !== null && shown(age),
    // A dot shown before the number of a row with no place, which has no field there for it
    // to follow.
    strayDot:
      run === null || placed
        ? null
        : [...run.children]
            .slice(0, [...run.children].indexOf(number))
            .some((part) => part.matches(".github-pull-stack-dot") && shown(part)),
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
  // The repository's stacks, as a reader has them once they have opened a member, before the
  // guide asks where its pull requests sit.
  await go("/pull/8");
  await waitFor(`document.querySelector(".github-pull-title-text") !== null`);
  await waitFor(
    `fetch("/api/plugin/github/stack?number=71", {cache: "no-store"}).then((r) => r.json()).then((a) => a.state === "current")`,
  );
  await go("/pull/7");
  await waitFor(
    `document.querySelector(".github-pull-guide-position")?.textContent === "Overview"`,
  );
  await evaluate(
    `[...document.querySelectorAll(".github-pull-guide-steps-link")].find((link) => link.textContent.includes(${JSON.stringify(STEP)})).click()`,
  );
  // A step is composed out of sight (`.github-pull-guide-incoming`, guided-review.js) and
  // shows whole once what it draws is in, so a check reads only the step shown.
  await waitFor(
    `document.querySelector(".github-pull-guide-step:not(.github-pull-guide-incoming) .github-pull-guide-title")?.textContent === ${JSON.stringify(STEP)}`,
  );
  await waitFor(
    `document.querySelectorAll(".github-pull-guide-step:not(.github-pull-guide-incoming) .github-pull-guide-row").length === 5`,
  );

  // 1. The rows, at a desktop width, then with one title too long for its row, then at a
  // phone's width. The pane keeps its width in a narrow window, so it is hidden there, as
  // `\` hides it, and the reading column takes the window.
  const rows = await evaluate(ROWS);
  // The rows' words and order, and a place's hint, are the member row's builder's
  // (stack-member-row.js), which the browserless session pins; here, what is drawn where,
  // and what assistive technology is told. 8 is in 71, its guide's own stack, 50 in 300,
  // another, and 2000 in none.
  for (const [at, who] of [
    [0, "8"],
    [1, "50"],
  ]) {
    check(
      `${who}'s place has a tip, which is not its own words`,
      rows[at]?.place != null && rows[at]?.tip != null && rows[at]?.tip !== rows[at]?.place,
      JSON.stringify(rows[at]),
    );
  }
  check("8's place, in its guide's own stack, is drawn bare", rows[0]?.glyph === false);
  check("50's place, in another stack, is drawn after the Layers glyph", rows[1]?.glyph === true);
  check("and its tip is not 8's", rows[1]?.tip !== rows[0]?.tip);
  same("2000, in no stack, has no place and no tip", [rows[2]?.place, rows[2]?.tip], [null, null]);
  check("and no dot before its number", rows[2]?.strayDot === false, rows[2]?.text);
  // Each pull request row's place and link as Chrome computes them for assistive technology,
  // as the Pulls tab's stacks session reads a member line's (github-pulls-stacks-chrome.mjs):
  // a place is an image named by its tip, which the link's name says in place of the
  // place's letters.
  const named = async (expression) => {
    const { result } = await chrome.send("Runtime.evaluate", { expression });
    if (result.objectId === undefined) {
      return null;
    }
    const { nodes } = await chrome.send("Accessibility.getPartialAXTree", {
      objectId: result.objectId,
      fetchRelatives: false,
    });
    const node = nodes?.[0];
    return node === undefined || node.ignored
      ? null
      : { role: node.role?.value ?? null, name: node.name?.value ?? null };
  };
  await chrome.send("Accessibility.enable");
  const names = [];
  for (let at = 0; at < 3; at += 1) {
    const link = `document.querySelectorAll(".github-pull-guide-step:not(.github-pull-guide-incoming) .github-pull-guide-row")[${at}].querySelector(".github-pull-guide-row-link")`;
    names.push({
      place: await named(`${link}.querySelector(".github-pull-stack-member-position")`),
      link: await named(link),
    });
  }
  await chrome.send("Accessibility.disable");
  for (const [at, who] of [
    [0, "8"],
    [1, "50"],
  ]) {
    same(`${who}'s place is an image Chrome names by its tip`, names[at]?.place, {
      role: "image",
      name: rows[at]?.tip,
    });
    const link = names[at]?.link?.name ?? "";
    check(
      `${who}'s row's name says its place's tip, not the place's letters`,
      rows[at]?.tip != null &&
        link.includes(rows[at].tip) &&
        !link.includes(rows[at]?.place ?? "\u0000"),
      link,
    );
  }
  check(
    "2000's row has no place to name",
    names[2]?.place?.role !== "image" && !names[2]?.place?.name,
    JSON.stringify(names[2]),
  );
  // A commit's row: whether it goes anywhere, its note, and its age; their words and order
  // are the browserless session's, and the age ending the row is measured below.
  same(
    checkout
      ? "the commit the checkout lacks: a row that goes nowhere, with a note and its age"
      : "the commit's row: a link with its age and no note",
    [rows[3]?.linked, rows[3]?.note, rows[3]?.age],
    [!checkout, checkout, true],
  );
  same(
    "a commit the store lacks: a row that goes nowhere, with a note and no age",
    [rows[4]?.linked, rows[4]?.note, rows[4]?.age],
    [false, true, false],
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
      check(`${label}: row ${at + 1}'s run's parts stand apart`, row.runApart);
      // The rows but the commit the store lacks, which names nothing at its end.
      if (at < 4) {
        check(`${label}: row ${at + 1}'s last part ends the row`, row.ends === true);
      }
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
    `document.querySelector(".github-pull-guide-row .github-pull-stack-member-title").textContent = ${JSON.stringify(LONG)}`,
  );
  if (checkout) {
    // A subject too long for its row: it and the note give way, and the age still ends it.
    await evaluate(
      `document.querySelector(".github-pull-guide-commit .github-pull-guide-row-title").textContent = ${JSON.stringify(LONG)}`,
    );
  }
  const long = await evaluate(ROWS);
  measure("a long title", long);
  check("a long title is cut short", long[0]?.cut === true);
  if (checkout) {
    check("a long subject is cut short", long[3]?.cut === true);
  }
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
    `document.querySelector(".container").hasAttribute("data-nav-collapsed") && document.querySelector(".github-pull-guide-step:not(.github-pull-guide-incoming) .github-pull-guide-row").getBoundingClientRect().width > 250`,
  );
  measure("a phone's width", await evaluate(ROWS));
  check("at a phone's width nothing runs past the page", await evaluate(PAGE_FITS));
  await togglePane();
  await waitFor(`!document.querySelector(".container").hasAttribute("data-nav-collapsed")`);
  await chrome.send("Emulation.clearDeviceMetricsOverride");

  if (!checkout) {
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
        `[...document.querySelectorAll(".github-pull-guide-reference-header .diff-file-toggle")].map((name) => [...name.children].filter((part) => !part.classList.contains("diff-file-chevron")).map((part) => part.textContent))`,
      ),
      [["#9", "src/app.txt"]],
    );
    check(
      "and the number stands apart from the path",
      await evaluate(`(() => {
      const [number, path] = [...document.querySelector(".github-pull-guide-reference-header .diff-file-toggle").children].filter((part) => !part.classList.contains("diff-file-chevron"));
      return path.getBoundingClientRect().left - number.getBoundingClientRect().right >= 2;
    })()`),
    );

    // 3. A pull request's row opens its page in place.
    await evaluate(`document.querySelector(".github-pull-guide-pull").click()`);
    await waitFor(`location.pathname === "/pull/8"`);
    check("8's row opened its page", await evaluate(`location.pathname === "/pull/8"`));
  }
} finally {
  await chrome.close();
}
if (failures.length > 0) {
  process.stderr.write(`${failures.join("\n")}\n`);
  process.exitCode = 1;
} else {
  process.stdout.write(
    `guided review references${checkout ? " from a checkout" : ""} in Chrome: ${checks} checks passed\n`,
  );
}

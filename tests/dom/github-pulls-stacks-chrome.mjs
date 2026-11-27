// The Pulls tab grouped by stack, and the pull request page's stack menu, laid out by headless
// Chrome against a live `metab` server serving the GitHub stand-in with a native stack.
//
//   CHROME_BIN=... CHROME_PROFILES=<dir> [SHOTS_DIR=<dir>] [MEASURE_OUT=<file>] \
//     node tests/dom/github-pulls-stacks-chrome.mjs <server base URL> [--before]
//
// tests/test_github_pulls_stacks_chrome.py serves a checkout of the stand-in with a fake
// `gh` whose `gh stack` answers two native stacks: #286, pull requests 7 to 10 from the base,
// and #300, 5 and 10. The test owns the profile directory and stops this process's whole
// group, Chrome included, however the run ends (tests/process_group.py).
//
// What it holds is the one stack design (docs/design-system.md, "Stacks") where only a
// browser can tell: that a stack row's header and the stack menu's heading resolve to the
// same label tokens, gray, all caps, and tracked; that a stack row starts on the list's row
// inset and its pull requests one tree level in; that a stack row and a pull request's row
// hover alike and are as tall as the row contract says; that the toolbar fits the default
// pane with no Group by stack chip, since the tab always groups; that the keys move real
// focus onto and off a stack row, and over a pull request's item, its run and last line one stop
// (mb-1z7j), whose changed files Space, Right, and Left open and close as a folder's; and that
// the groups list a stack's
// members in the order the page's stack menu does. It times the first row and the grouping's arrival, and with
// SHOTS_DIR it saves the screenshots. `--before` takes only the screenshots and the first
// row's time, for the shell as it was before grouping, and checks nothing of it.
//
// Each step writes `phase <name> <ms since start>` to stderr, so a slow run says where.
import fs from "node:fs";
import path from "node:path";
import { launchChrome } from "./chrome-session.mjs";
import { judge, NARROWEST, SWEEP, WIDEST, WIDTHS } from "./nav-toolbar-wrap.mjs";

const [base, mode] = process.argv.slice(2);
const before = mode === "--before";
if (!base || !process.env.CHROME_BIN || !process.env.CHROME_PROFILES) {
  throw new Error("usage: CHROME_BIN CHROME_PROFILES github-pulls-stacks-chrome.mjs <base URL>");
}
const SHOTS = process.env.SHOTS_DIR ?? null;
const started = Date.now();
const phase = (name) => process.stderr.write(`phase ${name} ${Date.now() - started}\n`);
// Each wait's bound: a paint, or the fake gh's refresh of the stand-in's catalog or stacks,
// which takes a second or two on a loaded machine. Chrome's start is bounded in
// chrome-session.mjs.
const STEP_MS = 30000;
const TOLERANCE_PX = 0.5;
// #8's author in the stand-in's catalog, GitHub's longest login
// (test_github_pulls_stacks_chrome.py, `LONG_LOGIN`).
const _LONG_AUTHOR_PULL = 8;
const _LONG_LOGIN = "contributor-with-the-longest-login-name";

const failures = [];
let checks = 0;
const check = (label, ok, detail = "") => {
  checks += 1;
  if (!ok) {
    failures.push(`${label}${detail ? `: ${detail}` : ""}`);
  }
};
const near = (a, b) =>
  typeof a === "number" && typeof b === "number" && Math.abs(a - b) <= TOLERANCE_PX;

// In the page: the label register's computed style of an element, and of the tokens.
const REGISTER = `(() => {
  const props = ["color", "fontFamily", "fontSize", "fontWeight", "letterSpacing", "textTransform"];
  const read = (el) => el === null ? null : Object.fromEntries(props.map((p) => [p, getComputedStyle(el)[p]]));
  const probe = document.createElement("span");
  probe.style.cssText = "color: var(--label-color); font-family: var(--font-sans); font-size: var(--label-font-size); font-weight: var(--label-font-weight); letter-spacing: var(--label-letter-spacing); text-transform: var(--label-text-transform)";
  document.body.append(probe);
  const tokens = read(probe);
  probe.remove();
  return {
    tokens,
    row: read(document.querySelector(".github-pulls-stack-row .github-pull-stack-label")),
    menu: read(document.querySelector(".github-pull-stack-menu .group-heading")),
  };
})()`;

// In the page: at every width the pane allows, in both themes, each drawn row's state icon and
// the first box of its title, its run's first text for a member too, whose place follows the
// title (mb-pw8t), on the row the Pulls panel paints (mb-ma3f): whether the two overlap by more
// than half a pixel either way, and where the title starts, one column gap past the icon's
// slot. In the app's WKWebView the first line's indent was dropped, and a member's place,
// which then led the title, and the title both started at the icon's left edge.
const PLACE_SWEEP = `(widths) => {
  const pane = document.querySelector(".tree-pane");
  const root = document.documentElement;
  const saved = [pane.style.width, pane.style.minWidth, root.dataset.theme];
  const r = (value) => Math.round(value * 100) / 100;
  const rows = [];
  let seen = 0;
  let members = 0;
  for (const theme of ["light", "dark"]) {
    root.dataset.theme = theme;
    for (const width of widths) {
      pane.style.minWidth = "0";
      pane.style.width = width + 1 + "px";
      for (const row of document.querySelectorAll("a.github-pulls-row")) {
        const icon = row.querySelector(".github-pulls-heading > .github-pull-state-icon");
        const place = row.querySelector(".github-pull-row-copy > .github-pulls-place:not([hidden])");
        const text = row.querySelector(".github-pull-row-copy > .github-pulls-title");
        const [box] = text?.getClientRects() ?? [];
        if (!icon || !box) continue;
        seen += 1;
        if (place) members += 1;
        const a = icon.getBoundingClientRect();
        const gap = parseFloat(getComputedStyle(row).columnGap);
        const across = Math.min(a.right, box.right) - Math.max(a.left, box.left);
        const down = Math.min(a.bottom, box.bottom) - Math.max(a.top, box.top);
        if ((across > 0.5 && down > 0.5) || Math.abs(box.left - (a.right + gap)) > 0.5) {
          rows.push({ theme, width, number: Number(row.dataset.number), member: place !== null, icon: [r(a.left), r(a.right)], text: [r(box.left), r(box.right)], gap });
        }
      }
    }
  }
  pane.style.width = saved[0];
  pane.style.minWidth = saved[1];
  if (saved[2] === undefined) delete root.dataset.theme; else root.dataset.theme = saved[2];
  return { seen, members, overlaps: rows.slice(0, 20), overlapCount: rows.length };
}`;

// In the page: the grouped list as drawn, and where its rows start.
const LIST = `(() => {
  const list = document.querySelector(".github-pulls-list");
  const rows = [...list.querySelectorAll(".github-pulls-row")];
  const left = (el) => el?.getBoundingClientRect().left ?? null;
  const stacks = [];
  let open = null;
  for (const row of rows) {
    if (row.classList.contains("github-pulls-stack-row")) {
      open = {
        stack: Number(row.dataset.stack),
        label: row.querySelector(".github-pull-stack-label").textContent,
        shown: row.querySelector(".github-pull-stack-label").innerText,
        // Everything the row says on screen: its label, its size, a count summary, and its
        // age (mb-tvhs).
        text: row.textContent,
        count: row.querySelector(".github-pulls-stack-count")?.textContent ?? "",
        countNumber: row.querySelector(".github-pulls-stack-count .summary-number")?.textContent ?? "",
        age: row.querySelector(".github-pulls-age")?.textContent ?? "",
        icons: row.querySelectorAll(".github-pull-stack-icon").length,
        name: row.getAttribute("aria-label"),
        expanded: row.getAttribute("aria-expanded"),
        tip: row.dataset.tipText,
        members: [],
      };
      stacks.push(open);
    } else if (row.classList.contains("github-pulls-whole-row") && open !== null) {
      // The stack's Stack Overview row, one of its set (mb-cm31): its words, then its stack's
      // change line, if the server could sum one (mb-9ekj), and the chevron after it, the
      // toggle of the stack's changed files (mb-odt4).
      const glyph = row.querySelector(".github-pull-stack-icon");
      open.whole = {
        text: row.querySelector(".github-pulls-whole-title")?.textContent ?? "",
        change: row.querySelector(".github-pulls-stack-change")?.textContent ?? "",
        name: row.getAttribute("aria-label"),
        href: row.getAttribute("href"),
        level: row.getAttribute("aria-level"),
        expanded: row.getAttribute("aria-expanded"),
        place: row.getAttribute("aria-posinset") + "/" + row.getAttribute("aria-setsize"),
        // Its Layers glyph is in the row's text's ink, as the stack page's title glyph is
        // (mb-68uk).
        inked: glyph !== null && getComputedStyle(glyph).color === getComputedStyle(row).color,
      };
    } else if (row.getAttribute("aria-level") === "2" && open !== null) {
      const place = row.querySelector(".github-pulls-place");
      open.members.push({
        number: Number(row.dataset.number),
        // Its place in its stacks, after its title and before its number (mb-vkhd, mb-pw8t).
        badge: row.querySelector(".github-pulls-place .github-pull-stack-position")?.textContent ?? "",
        // The run as it reads: the title, then the dot and the place, its no-break space a
        // space; and the number after them.
        heading: ((row.querySelector(".github-pulls-title")?.textContent ?? "") + (place?.textContent ?? "")).replaceAll("\u00a0", " "),
        line: row.querySelector(".github-pulls-number")?.textContent ?? "",
        // Another stack named in it, by the Layers glyph before its number.
        others: row.querySelectorAll(".github-pulls-place .github-pull-stack-other svg").length,
        // A member's row draws no stack icon.
        icons: row.querySelectorAll(".github-pull-stack-icon").length,
        tip: row.querySelector(".github-pulls-place")?.getAttribute("aria-label") ?? "",
      });
    } else {
      open = null;
    }
  }
  const stackRow = list.querySelector(".github-pulls-stack-row");
  const wholeRow = list.querySelector(".github-pulls-whole-row");
  const member = list.querySelector(
    '.github-pulls-item[data-level="2"] > .github-pulls-entry > .github-pulls-row',
  );
  const flat = [...list.querySelectorAll('.github-pulls-row[aria-level="1"]')].find(
    (row) => !row.classList.contains("github-pulls-stack-row"),
  );
  const box = (el) => el?.getBoundingClientRect() ?? null;
  // Where a pull request's row's text starts: its run's first box, the title's, on the first
  // line, after the state icon (mb-pw8t).
  const textStart = (row) => row?.querySelector(".github-pulls-title")?.getClientRects()[0]?.left ?? null;
  // The room a row's run gets: its width, in which a long title wraps. A member's and a
  // first-level pull request's, and the pane they are in.
  const titleBox = (number) =>
    list.querySelector('a.github-pulls-row[data-number="' + number + '"] .github-pulls-heading')?.getBoundingClientRect().width ?? null;
  // The Pulls column carries no tooltip (mb-8mpo): every pull request's and stack's row and
  // its parts, after a pointer has crossed each title, as a reader's would.
  for (const title of list.querySelectorAll(".github-pulls-row .github-pulls-title")) {
    title.dispatchEvent(new PointerEvent("pointerover", { bubbles: true }));
    // Leaving, so no hover is left to read a pull request ahead.
    title.dispatchEvent(new PointerEvent("pointerout", { bubbles: true }));
  }
  // A pull request's toggle, the lines and the chevron at its run's end, is read as its row
  // is, inside it (mb-pw8t).
  const tips = [...list.querySelectorAll(".github-pulls-row")].flatMap((row) =>
    [row, ...row.querySelectorAll("*")]
      .filter((node) => node.hasAttribute("data-tip-text") || node.hasAttribute("title"))
      .map((node) => (row.dataset.number ?? "stack " + row.dataset.stack) + ": " + node.className),
  );
  const titleRoom = {
    pane: Math.round(document.querySelector(".tree-pane").getBoundingClientRect().width),
    member: titleBox(10),
    memberSingle: titleBox(9),
    flat: titleBox(106),
    memberRow: list.querySelector('a.github-pulls-row[data-number="10"]')?.getBoundingClientRect().height ?? null,
    flatRow: list.querySelector('a.github-pulls-row[data-number="106"]')?.getBoundingClientRect().height ?? null,
  };
  // A pull request's row (mb-pw8t, mb-rb3n): its run, one flow of the state icon, the title, a
  // member's place, the number, and the author, every line of it in the text column, from the
  // row's inset to its end; and under it its last line, the toggle, the lines and the chevron,
  // in the text column, and the age at the row's end. Each row's parts, from its link's content
  // box.
  const lines = Object.fromEntries(
    [10, 9, 106].map((number) => {
      const row = list.querySelector('a.github-pulls-row[data-number="' + number + '"]');
      if (row === null) return [number, null];
      const style = getComputedStyle(row);
      const r = row.getBoundingClientRect();
      const inset = r.left + parseFloat(style.borderLeftWidth) + parseFloat(style.paddingLeft);
      const end = r.right - parseFloat(style.paddingRight);
      const of = (selector) => row.querySelector(selector).getBoundingClientRect();
      const item = row.closest("li");
      const headingBox = row.querySelector(".github-pulls-heading");
      const heading = headingBox.getBoundingClientRect();
      const lh = parseFloat(getComputedStyle(headingBox).lineHeight);
      const column = headingBox.querySelector(".github-pull-row-copy").getBoundingClientRect().left;
      const icon = of(".github-pull-state-icon");
      const tail = of(":scope > .github-pulls-tail");
      const change = of(".github-pulls-change");
      const age = of(":scope > .github-pulls-tail > .github-pulls-age");
      const tailBox = row.querySelector(":scope > .github-pulls-tail");
      const numberEnd = of(".github-pulls-number").right;
      const tailEnd = tail.right - parseFloat(getComputedStyle(tailBox).paddingInlineEnd);
      const toggle = row.querySelector(".github-pulls-toggle")?.getBoundingClientRect() ?? null;
      const round = (value) => Math.round(value * 100) / 100;
      return [number, {
        text: row.querySelector(".github-pulls-number").textContent,
        // The run is as tall as its lines, never cut short (mb-pw8t), above the last line.
        runAbove: heading.bottom <= tail.top + 0.5,
        runLines: Math.round(heading.height / lh),
        runFits: Math.abs(heading.height - Math.round(heading.height / lh) * lh) < 0.5,
        // The last line's toggle starts in the text column, under the title's first text; the
        // age ends that line at the row's end, past the chevron (docs/design-system.md, "Ages
        // End the Row").
        lastFromText: round(change.left - textStart(row)),
        ageOnLast:
          age.top >= tail.top - 0.5 &&
          age.bottom <= tail.bottom + 0.5 &&
          Math.abs(numberEnd - tailEnd) < 0.5 &&
          Math.abs(age.left - change.right - parseFloat(getComputedStyle(tailBox).gap)) < 0.5 &&
          Math.abs(end - tailEnd) < 0.5 &&
          (toggle === null || toggle.right <= age.left + 0.5),
        // The run runs from the row's inset to its end, its text in the text column, after the
        // state icon's slot.
        runToEnd: round(end - heading.right),
        runFromInset: round(heading.left - inset),
        textFromInset: round(textStart(row) - inset),
        columnFromInset: round(column - inset),
        // The text column is one icon slot and gap in: a row in no stack is flush (mb-3vil).
        textColumn: round(parseFloat(style.getPropertyValue("--tree-icon-slot")) + parseFloat(style.columnGap)),
        // The state icon is the run's first line's start, one line of it tall.
        withTitle: Math.abs(icon.top - heading.top) < 0.5 && Math.abs(icon.height - lh) < 0.5,
        iconFromInset: round(icon.left - inset),
        // The link's one toggle is its last line, under the run (mb-rb3n).
        linkToggles: row.querySelectorAll(".github-pulls-toggle").length,
        toggleOnLast:
          tailBox.lastElementChild?.classList.contains("github-pull-row-end") === true &&
          toggle !== null &&
          toggle.top >= tail.top - 0.5 &&
          toggle.bottom <= tail.bottom + 0.5,
        // A closed row's item is its link.
        itemIsRow: Math.abs(item.getBoundingClientRect().height - r.height) < 0.5,
        runWidth: round(heading.width),
        height: round(r.height),
        itemHeight: round(item.getBoundingClientRect().height),
      }];
    }),
  );
  return {
    tips,
    lines,
    titleRoom,
    stacks,
    rows: rows.length,
    stackToggle: left(stackRow?.querySelector(".github-pulls-toggle")),
    stackLabel: left(stackRow?.querySelector(".github-pull-stack-label")),
    wholeToggle: left(wholeRow?.querySelector(".github-pulls-toggle")),
    wholeTitle: left(wholeRow?.querySelector(".github-pulls-whole-title")),
    wholeRowHeight: box(wholeRow)?.height ?? null,
    wholeIcon: left(wholeRow?.querySelector(".github-pull-stack-icon")),
    // A stack's row draws no icon (mb-68uk): its heading is its name.
    stackIcons: stackRow?.querySelectorAll(".github-pull-stack-icon").length ?? null,
    // The text column: the run's first text, the title's, and the last line's, the toggle's.
    flatTitle: textStart(flat),
    flatIcon: left(flat?.querySelector(".github-pull-state-icon")),
    memberTitle: textStart(member),
    memberIcon: left(member?.querySelector(".github-pull-state-icon")),
    memberLast: left(member?.querySelector(".github-pulls-change")),
    flatLast: left(flat?.querySelector(".github-pulls-change")),
    slotWidth: parseFloat(getComputedStyle(document.documentElement).getPropertyValue("--tree-icon-slot")),
    rowGap: parseFloat(getComputedStyle(flat ?? document.body).columnGap),
    // A tree level's indent: one icon slot and the rows' column gap (mb-3vil). A stack's
    // Stack Overview row and its members are one in.
    memberIndent:
      parseFloat(getComputedStyle(document.documentElement).getPropertyValue("--tree-icon-slot")) +
      parseFloat(getComputedStyle(stackRow ?? document.body).columnGap),
    stackRowHeight: box(stackRow)?.height ?? null,
    rowHeightToken: parseFloat(getComputedStyle(document.documentElement).getPropertyValue("--ui-row-height")),
    treeIndent: parseFloat(getComputedStyle(document.documentElement).getPropertyValue("--tree-indent")),
    stackAgeGap: box(stackRow?.querySelector(".github-pulls-age"))?.left - box(stackRow?.querySelector(".github-pulls-stack-count"))?.right,
    ageGapToken: parseFloat(getComputedStyle(document.documentElement).getPropertyValue("--tree-inline-age-gap")),
    // The toolbar's one line: how far past the pane it reaches, and the room left between
    // the filters and the line's end.
    toolbar: (() => {
      const bar = document.getElementById("nav-toolbar-pulls");
      const row = document.querySelector(".github-pulls-filters");
      const group = box(row?.querySelector(".chip-group"));
      const style = row === null ? null : getComputedStyle(row);
      const end =
        row === null || style === null
          ? null
          : row.getBoundingClientRect().right - parseFloat(style.paddingRight) - parseFloat(style.borderRightWidth);
      return {
        width: bar?.clientWidth ?? null,
        overflow: bar === null ? null : bar.scrollWidth - bar.clientWidth,
        spare: group === null || end === null ? null : Math.round(end - group.right),
        chip: document.querySelector(".github-pulls-group-toggle") !== null,
      };
    })(),
    // A row's slots, the chevron's and the icon's, from the row's content edge: a pull
    // request's (#106, first level), whose chevron ends its run (mb-pw8t), a stack's, whose
    // chevron leads its row (mb-hmv7, --tree-icon-slot), and its Stack Overview row's, whose
    // glyph leads the row and whose chevron follows its line (mb-odt4).
    slots: (() => {
      const round = (value) => Math.round(value * 100) / 100;
      const of = (row, holder, toggle, icon, text) => {
        if (!row || !holder) return null;
        const r = row.getBoundingClientRect();
        const style = getComputedStyle(row);
        const inset = r.left + parseFloat(style.borderLeftWidth) + parseFloat(style.paddingLeft);
        const t = holder.querySelector(toggle).getBoundingClientRect();
        const i = icon === null ? null : row.querySelector(icon).getBoundingClientRect();
        const g = icon === null ? null : row.querySelector(icon + " svg").getBoundingClientRect();
        // The text's first box: a title of two lines is one box over both.
        const first = row.querySelector(text).getClientRects()[0];
        return {
          toggle: round(t.width),
          toggleFromInset: round(t.left - inset),
          chevron: round(holder.querySelector(toggle + " svg").getBoundingClientRect().width),
          icon: i === null ? null : round(i.width),
          iconFromInset: i === null ? null : round(i.left - inset),
          glyph: g === null ? null : round(g.width),
          text: round(first.left - inset),
          gap: parseFloat(style.columnGap),
        };
      };
      return {
        token: getComputedStyle(document.documentElement).getPropertyValue("--tree-icon-slot").trim(),
        pull: of(flat, flat, ".github-pulls-toggle", ".github-pull-state-icon", ".github-pulls-title"),
        stack: of(stackRow, stackRow, ".github-pulls-toggle", null, ".github-pull-stack-label"),
        whole: of(wholeRow, wholeRow, ".github-pulls-toggle", ".github-pull-stack-icon", ".github-pulls-whole-title"),
      };
    })(),
  };
})()`;

// In the page: what the shell's tooltip shows when a pointer enters *anchor*, or null when
// it shows none. The document's own listener decides (`showTipText` in static/app.js, and
// `tipAddsInformation`, docs/design-system.md, "Tooltips Add Information"), and a tip it
// shows is up once the shell's own delay, TOOLTIP_APPEAR_DELAY, has passed. The pointer
// then leaves, and the tooltip is gone, after TOOLTIP_FADE_OUT, before the next anchor.
const TIP_SHOWN = `async (anchor) => {
  const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
  const frames = () => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
  const up = () => document.querySelector(".custom-tooltip")?.style.display === "block";
  const gone = async () => {
    const bound = performance.now() + 20 * TOOLTIP_FADE_OUT;
    while (up() && performance.now() < bound) {
      await wait(TOOLTIP_FADE_OUT / 5);
    }
  };
  await gone();
  anchor.dispatchEvent(new MouseEvent("mouseenter"));
  await wait(TOOLTIP_APPEAR_DELAY);
  await frames();
  const shown = up() ? document.querySelector(".custom-tooltip").textContent : null;
  anchor.dispatchEvent(new MouseEvent("mouseleave"));
  await gone();
  return shown;
}`;

// In the page: the shell's tooltip rule on anchors built over its own stylesheet. A tip that
// is its button's whole text, in any case or spacing; the same tip on text cut short by an
// ellipsis; a branch chip whole, and one cut short, as a chip is, by its label inside it; and
// a glyph-only control's name.
const SHELL_TIPS = `(async () => {
  const shown = ${TIP_SHOWN};
  const h = (tag, attributes = {}, children = []) => {
    const node = document.createElement(tag);
    for (const [key, value] of Object.entries(attributes)) node.setAttribute(key, value);
    node.append(...children);
    return node;
  };
  const long = "A pull request title far longer than the box it is drawn in";
  const branch = "feature/a-branch-name-longer-than-its-chip";
  const chipCut = window.metabrowser.refChip(branch, { menu: false });
  chipCut.style.maxWidth = "80px";
  const anchors = {
    whole: h("button", { type: "button", "data-tip-text": "Refresh" }, ["Refresh"]),
    wholeSpaced: h("span", { "data-tip-text": "stack #286" }, ["  Stack   #286 "]),
    cut: h("span", { "data-tip-text": long, style: "display: block; width: 80px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap" }, [long]),
    chipWhole: window.metabrowser.refChip("main", { menu: false }),
    chipCut,
    glyph: h("button", { type: "button", "data-tip-text": "Copy path", "aria-label": "Copy path" }, ["↑"]),
  };
  const host = h("div", { style: "position: fixed; left: 320px; top: 120px; display: flex; flex-direction: column; align-items: flex-start; gap: 4px" }, Object.values(anchors));
  document.body.append(host);
  const label = chipCut.querySelector(".git-ref-label");
  const wholeLabel = anchors.chipWhole.querySelector(".git-ref-label");
  // Force the vertical overflow that a tight line can report with some fonts.
  wholeLabel.style.height = "8px";
  const result = {
    chipWholeOverflowsVertically: wholeLabel.scrollHeight > wholeLabel.clientHeight,
    chipWholeOverflowsHorizontally: wholeLabel.scrollWidth > wholeLabel.clientWidth,
    // The chip's label is the box cut short, inside the chip.
    chipLabelCut: label.scrollWidth > label.clientWidth,
  };
  for (const [name, anchor] of Object.entries(anchors)) {
    result[name] = await shown(anchor);
  }
  host.remove();
  return result;
})()`;

// In the page: a changed file's row, #106's README.md at the top level, whose tip is its name
// beside its status letter and counts: while its name is whole, and cut short (mb-n1ye).
// Folders come first and #106 holds them all open, so it is the tree's last row, drawn once
// the end of the tree is in view. Each reading says whether the row was still the one in the
// document after it, so a row the tree redrew meanwhile cannot pass as one that showed
// nothing.
const FILE_TIPS = `(async () => {
  const shown = ${TIP_SHOWN};
  const frames = () => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
  const item = document.querySelector('.github-pulls-item[data-number="106"]');
  const find = () => [...item.querySelectorAll(".github-pull-file-row")].find(
    (node) => node.querySelector(".github-pull-file-name")?.textContent === "README.md",
  );
  // The row, in the middle of the view, the same element two frames apart.
  const settled = async () => {
    for (let tries = 0; tries < 60; tries += 1) {
      const row = find();
      if (row === undefined) {
        item.querySelector(".github-pull-files-rows").scrollIntoView({ block: "end" });
      } else {
        row.scrollIntoView({ block: "center" });
      }
      await frames();
      if (row !== undefined && find() === row) {
        return row;
      }
    }
    return undefined;
  };
  const read = async (narrow) => {
    const row = await settled();
    if (row === undefined) {
      return { missing: [...item.querySelectorAll(".github-pull-file-name")].map((node) => node.textContent).slice(-6) };
    }
    const name = row.querySelector(".github-pull-file-name");
    if (narrow) {
      name.style.maxWidth = "3ch";
    }
    const reading = {
      tip: row.dataset.tipText,
      text: row.textContent,
      cut: name.scrollWidth > name.clientWidth,
      shown: await shown(row),
      kept: row.isConnected && find() === row,
    };
    name.style.removeProperty("max-width");
    return reading;
  };
  return { whole: await read(false), narrow: await read(true) };
})()`;

// In the page: a nested changed file's row, #7's docs/new.md, whose tip is its whole path
// where the row shows only its name.
const NESTED_TIP = `(async () => {
  const shown = ${TIP_SHOWN};
  const row = [...document.querySelectorAll('.github-pulls-item[data-number="7"] .github-pull-file-row')].find(
    (node) => node.querySelector(".github-pull-file-name")?.textContent === "new.md",
  );
  return { tip: row?.dataset.tipText ?? null, shown: row === undefined ? null : await shown(row) };
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
  // A script error on the page fails the run, with what the list held when it did.
  const pageErrors = [];
  chrome.on("Runtime.exceptionThrown", ({ exceptionDetails }) =>
    pageErrors.push(exceptionDetails.exception?.description ?? exceptionDetails.text),
  );
  await send("Runtime.enable");
  const waitFor = async (expression, description = expression, timeoutMs = STEP_MS) => {
    try {
      return await chrome.waitFor(expression, timeoutMs);
    } catch (error) {
      const held = await evaluate(
        `[...document.querySelectorAll(".github-pulls-row")].slice(0, 8).map((r) => (r.dataset.stack ? "S" + r.dataset.stack : r.dataset.number) + ":" + r.getAttribute("aria-level")).join(" ") + " | " + (document.querySelector(".github-pulls-list")?.dataset.filter ?? "") + " | " + (document.querySelector(".github-pulls-connection")?.textContent ?? "")`,
      );
      const stacks = await evaluate(`fetch("/api/plugin/github/stacks").then((r) => r.text())`);
      throw new Error(
        `${description}: ${error.message}\nlist: ${held}\nstacks: ${stacks.slice(0, 600)}\npage errors: ${pageErrors.join("\n")}`,
      );
    }
  };
  const click = (selector) =>
    evaluate(`document.querySelector(${JSON.stringify(selector)}).click()`);
  const frames = () =>
    evaluate("new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)))");
  const now = () => evaluate("performance.now()");
  /** A screenshot for review, in the theme the page loaded in. */
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
  const paneClip = () =>
    evaluate(`(() => {
      const r = document.querySelector(".tree-pane").getBoundingClientRect();
      return { x: 0, y: 0, width: Math.ceil(r.right), height: Math.min(900, Math.ceil(r.bottom)) };
    })()`);
  /** A real key, as the keyboard sends it, to the focused element. */
  const press = async (key) => {
    const codes = {
      j: [74, "KeyJ"],
      k: [75, "KeyK"],
      ArrowLeft: [37, "ArrowLeft"],
      ArrowRight: [39, "ArrowRight"],
      ArrowUp: [38, "ArrowUp"],
      ArrowDown: [40, "ArrowDown"],
      Enter: [13, "Enter"],
      Escape: [27, "Escape"],
      " ": [32, "Space"],
    };
    const [keyCode, code] = codes[key];
    const text = key.length === 1 ? { text: key } : {};
    await send("Input.dispatchKeyEvent", {
      type: "keyDown",
      key,
      code,
      windowsVirtualKeyCode: keyCode,
      ...text,
    });
    await send("Input.dispatchKeyEvent", {
      type: "keyUp",
      key,
      code,
      windowsVirtualKeyCode: keyCode,
    });
    await frames();
  };
  // A pull request's toggle (mb-d0a3, mb-pw8t) carries its number too, and is named apart: it
  // is never focused (mb-1z7j), which naming it would show.
  const FOCUSED = `(() => {
      const el = document.activeElement;
      if (el?.matches?.(".github-pulls-change")) return "line " + el.dataset.number;
      if (el?.matches?.(".github-pull-file-row, .github-pull-folder-row")) return "file";
      if (el?.matches?.(".github-pulls-whole-row")) return "whole " + el.dataset.stack;
      return el?.dataset?.stack ? "stack " + el.dataset.stack : el?.dataset?.number ? "#" + el.dataset.number : el?.tagName ?? null;
    })()`;
  const focused = () => evaluate(FOCUSED);
  /** Whether the first stack's row is inside the list's scroller's view, and where it is. */
  const stackInView = () =>
    evaluate(`(() => {
      const row = document.querySelector(".github-pulls-stack-row");
      const scroller = document.querySelector(".tree-content");
      const view = scroller.getBoundingClientRect();
      const box = row?.getBoundingClientRect();
      return {
        inView: box !== undefined && box.bottom > view.top && box.top < view.bottom,
        rowTop: box === undefined ? null : Math.round(box.top - view.top),
        scrollTop: Math.round(scroller.scrollTop),
      };
    })()`);
  const hover = async (selector) => {
    const point = await evaluate(`(() => {
      const r = document.querySelector(${JSON.stringify(selector)}).getBoundingClientRect();
      return { x: r.left + 4, y: r.top + r.height / 2 };
    })()`);
    await send("Input.dispatchMouseEvent", { type: "mouseMoved", ...point });
    await frames();
    return evaluate(
      `getComputedStyle(document.querySelector(${JSON.stringify(selector)})).backgroundColor`,
    );
  };

  await send("Page.enable");
  await send("Page.navigate", { url: `${base}/view/` });
  // The shell binds its tabs once the first tree has settled, as a reader's press needs.
  const tabReady = `document.querySelector(".tree-summary .tree-summary-tracked") !== null && window.MetabrowserPullsNav !== undefined`;
  const openPulls = async () => {
    await click('.nav-tab-bar [data-tab="pulls"]');
    await waitFor(
      `document.querySelector('.nav-tab-bar [data-tab="pulls"]').classList.contains("active")`,
    );
  };
  await waitFor(tabReady);
  phase("shell");
  const asked = await now();
  await openPulls();
  await waitFor(`document.querySelector(".github-pulls-item") !== null`);
  measured.firstRowMs = Math.round((await now()) - asked);
  phase("first row");
  if (!before) {
    // Open starts flat. The recent stack joins the first viewport below the newest PR.
    await waitFor(`document.querySelector(".github-pulls-stack-row") !== null`);
    measured.groupedMs = Math.round((await now()) - asked);
    phase("grouped");
    await frames();
    measured.groupedInView = await stackInView();
    check(
      "grouping that arrives after the first paint shows its first stack's row",
      measured.groupedInView.inView && measured.groupedInView.scrollTop === 0,
      JSON.stringify(measured.groupedInView),
    );
    check(
      "the newer standalone pull request stays ahead of the stack",
      (await evaluate(`
        document.querySelector('.github-pulls-list :is(.github-pulls-item, .github-pulls-stack-row)')
          ?.querySelector('a.github-pulls-row')?.dataset.number === "106"
      `)) === true,
    );
  }
  await click('.github-pulls-filters [data-chip-value="all"]');
  await waitFor(
    `document.querySelector('.github-pulls-list[data-filter="all"] a.github-pulls-row') !== null`,
  );

  if (before) {
    // The stack badges arrive from the same snapshot, on rows near the list's end; the
    // list draws no groups. That shell drew a badge on the title line, `.github-pulls-stack`.
    // Scrolled to the end as it grows: the rows near it mount once the window reaches them.
    await waitFor(
      `(document.querySelector(".tree-content").scrollTop = 1e6) && document.querySelector('a.github-pulls-row[data-number="10"]') !== null`,
    );
    await evaluate(
      `document.querySelector('a.github-pulls-row[data-number="10"]').scrollIntoView({block: "center"})`,
    );
    await waitFor(
      `!document.querySelector('a.github-pulls-row[data-number="10"] .github-pulls-stack').hidden`,
    );
    measured.badgesMs = Math.round((await now()) - asked);
    await shot("before-pulls-all", await paneClip());
  } else {
    // All may have #8's new activity before the visible stack reader next polls.
    // Wait for the four members to share a group, then check their order independently.
    await waitFor(
      `(() => {
        const heading = document.querySelector('.github-pulls-stack-row[data-stack="286"]');
        const members = new Set();
        let item = heading?.parentElement.nextElementSibling;
        while (item?.dataset.level === "2") {
          members.add(item.dataset.number);
          item = item.nextElementSibling;
        }
        return ["7", "8", "9", "10"].every((number) => members.has(number));
      })()`,
      "all four fixture members under Stack #286",
      2 * STEP_MS,
    );
    await frames();
    const list = await evaluate(LIST);
    measured.list = list;
    // A row's title, a member's as well, starts one column gap after its state icon wherever
    // the pane is and in both themes: the two boxes never overlap (mb-ma3f, mb-pw8t).
    measured.placeSweep = await evaluate(`(${PLACE_SWEEP})(${JSON.stringify(WIDTHS)})`);
    check(
      "a row's title, a member's too, never overlaps its state icon, at any width, in either theme",
      measured.placeSweep.members > 0 &&
        measured.placeSweep.seen > measured.placeSweep.members &&
        measured.placeSweep.overlapCount === 0,
      JSON.stringify(measured.placeSweep),
    );
    const first = list.stacks[0];
    check(
      "the list is grouped, Stack #286 first",
      first?.stack === 286,
      JSON.stringify(list.stacks),
    );
    check("its header text is the stack's label", first?.label === "Stack #286");
    check("which shows gray and all caps", first?.shown === "STACK #286", first?.shown);
    check("it is open by default", first?.expanded === "true");
    check(
      "its pull requests are under it, top of the stack first",
      JSON.stringify(first?.members.map((m) => m.number).filter((number) => number !== 10)) ===
        "[9,8,7]",
      JSON.stringify(first?.members),
    );
    // Its heading says the stack's size, a count summary, "· 4 pulls", then its age at the
    // row's end, and draws no Layers icon (docs/design-system.md, "Heading Tallies";
    // mb-tvhs); its accessible name says the count the heading shows, and the age.
    check(
      "its heading is its label, its size, and its age, with no Layers icon",
      first?.count === "· 4 pulls" &&
        first.countNumber === "4" &&
        first.age !== "" &&
        first.text === `Stack #286· 4 pulls${first.age}` &&
        first.icons === 0,
      JSON.stringify(first),
    );
    check(
      "its accessible name says the count it shows, then its age",
      /^Stack #286, 4 pull requests(?:, 1 under Stack #300)? · /.test(first?.name ?? "") &&
        first.name.endsWith(first.age),
      first?.name,
    );
    // Each open stack's rows hold its Stack Overview row (mb-cm31), a link to the stack's own
    // page, one of the stack's set, at its pull requests' level, its files closed, which
    // shows the stack's change line and says it in its name; the keys below say where it is.
    check(
      "each open stack has its Stack Overview row, one of its set, its files closed, its glyph in its text's ink, which links to the stack's page and says its change line",
      list.stacks.every(
        (stack) =>
          stack.expanded !== "true" ||
          (stack.whole?.text === "Stack Overview" &&
            stack.whole.href === `/stack/${stack.stack}` &&
            stack.whole.level === "2" &&
            stack.whole.expanded === "false" &&
            stack.whole.place === `1/${stack.members.length + 1}` &&
            stack.whole.inked &&
            (stack.whole.change === ""
              ? // No line, or its read on its way, which the name says is pending.
                [
                  `Stack Overview, Stack #${stack.stack}`,
                  `Stack Overview, Stack #${stack.stack}: change pending`,
                ].includes(stack.whole.name)
              : stack.whole.name.startsWith(`Stack Overview, Stack #${stack.stack}: `))),
      ),
      JSON.stringify(list.stacks.map(({ stack, expanded, whole }) => ({ stack, expanded, whole }))),
    );
    const placesForTen = list.stacks.flatMap((stack) =>
      stack.members.filter((member) => member.number === 10).map((member) => [stack.stack, member]),
    );
    const [home, ten] = placesForTen[0] ?? [];
    check(
      "#10, in two stacks, sits once and names both positions",
      placesForTen.length === 1 &&
        ten?.others === 1 &&
        (home === 286
          ? ten.badge === "4/4 · 300 2/2"
          : home === 300 && ten.badge === "2/2 · 286 4/4") &&
        ten.tip.includes("Stack #286, position 4 of 4") &&
        ten.tip.includes("Stack #300, position 2 of 2"),
      JSON.stringify(placesForTen),
    );
    const nine = first?.members.find((member) => member.number === 9);
    check(
      "a member’s accessible heading includes its stack place and its summary shows the number",
      nine?.heading.endsWith(" · 3/4") && nine.line === "#9",
      JSON.stringify(nine),
    );
    check(
      "no pull request's or stack's row, nor any part of one, its toggle included, carries a tooltip",
      list.tips.length === 0,
      JSON.stringify(list.tips),
    );
    check(
      "a member's row draws no stack icon",
      list.stacks.every((stack) => stack.members.every((m) => m.icons === 0)),
      JSON.stringify(list.stacks.map((stack) => stack.members.map((m) => m.icons))),
    );
    // Its place on the title line once cut a member's title to 65 px at the default pane,
    // where a first-level row's had 176 (mb-dzsi, measured before the change).
    // The title on a line of its own to the row's end (mb-lkkt): at the default pane a
    // member's title had 170 px, beside its age, and has 208. The title's line comes first,
    // the icon leading it, and the number's line under it, with the age (2026-11-17, at the
    // owner's word: the title is what a reader scans for); before, the number's line came
    // first and the icon led it (mb-3cbf). The icon is in the row's one slot, on its inset, so a
    // row in no stack is flush (mb-3vil). The chevron was on the row's third line, its change
    // line (mb-d0a3), in that slot under the icon, and the line's values in the title's column:
    // on the number's line it led the row's link, which a press then both opened and expanded.
    // Under the title's start it put the values a slot and gap past the other two lines' text,
    // which the owner asked to have start at one x (2026-11-18).
    // The title took two lines, and the number's line joined the change line (mb-85op,
    // mb-lqkb): before, the title was alone on the first line and the number's line, with the
    // age, the second. Then the number and the lines joined the title's run, and the author
    // and the age were the last line (mb-pw8t). Now the author ends the run, and the lines, the
    // chevron, and the age at the row's end are the last line (mb-rb3n).
    check(
      "a pull request's run is its first lines, the icon on the row's inset and the text from the text column to the row's end, and its last line has the toggle, adjacent age, and right-aligned PR number",
      [10, 9, 106].every((number) => {
        const row = list.lines[number];
        return (
          row?.runAbove &&
          row.runFits &&
          Math.abs(row.lastFromText) < 0.5 &&
          row.ageOnLast &&
          Math.abs(row.runToEnd) < 0.5 &&
          Math.abs(row.runFromInset) < 0.5 &&
          Math.abs(row.textFromInset - row.textColumn) < 0.5 &&
          Math.abs(row.columnFromInset - row.textColumn) < 0.5 &&
          row.withTitle &&
          Math.abs(row.iconFromInset) < 0.5 &&
          row.linkToggles === 1 &&
          row.toggleOnLast &&
          row.itemIsRow &&
          // Rows whose runs take as many lines are as tall as each other.
          [10, 9, 106].every((other) => {
            const that = list.lines[other];
            return (
              that?.runLines !== row.runLines ||
              (that.height === row.height && that.itemHeight === row.itemHeight)
            );
          })
        );
      }) &&
        list.lines[9].text === "#9" &&
        list.lines[106].text === "#106",
      JSON.stringify(list.lines),
    );
    check(
      "a member's run has a first-level row's room, less its one indent",
      Math.abs(list.titleRoom.member - (list.titleRoom.flat - list.memberIndent)) < 0.5 &&
        Math.abs(list.titleRoom.memberSingle - (list.titleRoom.flat - list.memberIndent)) < 0.5,
      JSON.stringify(list.titleRoom),
    );
    // The leading slots are the tree's one icon slot, 14 px, the Files tree's too: at 16 px
    // a title and a stack's label started 44 px from the row's content edge, and at 14,
    // 40 (mb-hmv7). A pull request's row has one slot, the state icon's, on its inset, and its
    // chevron ends its run (mb-pw8t); a stack's row has one too, its chevron's, and its label
    // after it, with no icon (mb-68uk), where it had the Layers icon's slot as well (mb-3vil);
    // its Stack Overview row has one, the stack's Layers glyph's, where a member's state icon
    // is, and its chevron follows its line, as a pull request's does (mb-odt4).
    const slots = list.slots;
    check(
      "a row's chevron and icon, a stack row's chevron, and its Stack Overview row's glyph and chevron, are each the tree's 14 px icon slot",
      slots.token === "14px" &&
        [slots.pull, slots.stack, slots.whole].every(
          (row) => row !== null && row.toggle === 14 && row.chevron === 12,
        ) &&
        slots.pull.glyph === 14 &&
        slots.whole.glyph === 14 &&
        slots.stack.icon === null &&
        list.stackIcons === 0 &&
        // A stack's chevron leads its row; a pull request's ends its run, and a Stack
        // Overview row's follows its words.
        slots.stack.toggleFromInset === 0 &&
        slots.whole.toggleFromInset > slots.whole.text &&
        near(slots.pull.iconFromInset, 0) &&
        near(slots.pull.text, 14 + slots.pull.gap) &&
        near(slots.stack.text, 14 + slots.stack.gap) &&
        near(slots.whole.iconFromInset, 0) &&
        near(slots.whole.text, 14 + slots.whole.gap) &&
        slots.pull.icon === 14,
      JSON.stringify({ ...slots, stackIcons: list.stackIcons }),
    );
    check(
      "a stack's row starts on the list's row inset, where a first-level pull request's does",
      near(list.stackToggle, list.flatIcon),
      `${list.stackToggle} ${list.flatIcon} ${list.flatTitle}`,
    );
    // A row's lines share one text column (the owner, 2026-11-18; mb-3vil, mb-pw8t, mb-rb3n):
    // the title's first text and the last line's toggle, the rows' one column gap after the
    // state icon's slot, and every line of the run between (`rowShape` in
    // tests/dom/github-pulls-row-lines-chrome.mjs).
    check(
      "a row's lines start at one x: the title's first text over the lines, one column gap after the icon's slot",
      [
        [list.flatIcon, list.flatTitle, list.flatLast],
        [list.memberIcon, list.memberTitle, list.memberLast],
      ].every(
        ([icon, title, last]) =>
          near(title, last) && near(title - (icon + list.slotWidth), list.rowGap),
      ),
      JSON.stringify({
        flat: [list.flatIcon, list.flatTitle, list.flatLast],
        member: [list.memberIcon, list.memberTitle, list.memberLast],
        slot: list.slotWidth,
        gap: list.rowGap,
      }),
    );
    check(
      "its label starts where its pull requests' state icons and its Stack Overview row's glyph do, and their titles where that row's words do",
      near(list.stackLabel, list.memberIcon) &&
        near(list.wholeIcon, list.memberIcon) &&
        near(list.wholeTitle, list.memberTitle),
      `${list.stackLabel} ${list.wholeToggle} ${list.wholeIcon} ${list.memberIcon} ${list.wholeTitle} ${list.memberTitle}`,
    );
    check(
      "its Stack Overview row and its pull requests start one tree level in, one icon slot and gap",
      near(list.wholeIcon - list.stackToggle, list.memberIndent) &&
        near(list.memberIcon - list.stackToggle, list.memberIndent),
      `${list.wholeToggle} ${list.memberIcon} ${list.stackToggle} ${list.memberIndent} ${list.memberTitle}`,
    );
    check(
      "a stack's row, and its Stack Overview row, are one row tall",
      near(list.stackRowHeight, list.rowHeightToken) &&
        near(list.wholeRowHeight, list.rowHeightToken),
      `${list.stackRowHeight} ${list.wholeRowHeight} ${list.rowHeightToken}`,
    );
    check(
      "its age follows the stack count with the File nav gap",
      near(list.stackAgeGap, list.ageGapToken),
      String(list.stackAgeGap),
    );
    // The tab always groups by stack, so its toolbar holds no Group by stack chip, and at
    // the default pane width its one line fits, with room to spare (mb-vmwh): the worded
    // chip reached 36 px past it, and every other form of it past it too.
    measured.toolbar = list.toolbar;
    check(
      "the toolbar has no Group by stack chip, and fits the default pane with room to spare",
      list.toolbar.chip === false &&
        list.toolbar.width === 299 &&
        list.toolbar.overflow === 0 &&
        list.toolbar.spare > 0,
      JSON.stringify(list.toolbar),
    );
    // A stack's row and a pull request's item (mb-1z7j) hover alike.
    const stackHover = await hover(".github-pulls-stack-row");
    const memberHover = await hover('.github-pulls-item[data-level="2"] > .github-pulls-entry');
    const rest = await evaluate(
      `getComputedStyle(document.querySelector('a.github-pulls-row[data-number="106"]').parentElement).backgroundColor`,
    );
    measured.hover = { stackHover, memberHover, rest };
    check(
      "a stack's row hovers as a pull request's row does",
      stackHover === memberHover && stackHover !== rest,
      JSON.stringify(measured.hover),
    );
    await send("Input.dispatchMouseEvent", { type: "mouseMoved", x: 1200, y: 880 });
    await shot("after-pulls-grouped", await paneClip());

    // Real keys: off a stack's row and back, closing and opening it. J from the stack's row
    // lands on its Stack Overview row first, and so does Right on the open stack.
    await evaluate(`document.querySelector(".github-pulls-stack-row").focus()`);
    const keys = [];
    for (const key of ["j", "k", "ArrowLeft", "ArrowRight", "ArrowRight"]) {
      await press(key);
      await waitFor(`document.activeElement !== document.body`);
      keys.push({
        key,
        focus: await focused(),
        expanded: await evaluate(
          `document.querySelector(".github-pulls-stack-row").getAttribute("aria-expanded")`,
        ),
        // A pull request's ring is drawn round its item, the link's parent (mb-1z7j).
        ring: await evaluate(
          `(() => { const el = document.activeElement; return getComputedStyle(el.matches(".github-pulls-entry > .github-pulls-row") ? el.parentElement : el).outlineStyle; })()`,
        ),
        place: await stackInView(),
      });
    }
    measured.keys = keys;
    check(
      "J, K, Left and Right move real focus over a stack's row, J and Right onto its Stack Overview row first",
      JSON.stringify(keys.map((k) => [k.focus, k.expanded])) ===
        JSON.stringify([
          ["whole 286", "true"],
          ["stack 286", "true"],
          ["stack 286", "false"],
          ["stack 286", "true"],
          ["whole 286", "true"],
        ]),
      JSON.stringify(keys),
    );
    check(
      "Left then Right on a stack's row leaves it in view",
      keys[2].place.inView && keys[3].place.inView,
      JSON.stringify(keys.map((k) => k.place)),
    );
    // Space on a stack's row, and a press on it, close and open it; focus stays on it.
    const stackState = () =>
      evaluate(
        `[document.querySelector(".github-pulls-stack-row").getAttribute("aria-expanded"), document.activeElement?.dataset?.stack ?? null]`,
      );
    await evaluate(`document.querySelector(".github-pulls-stack-row").focus()`);
    const toggles = [];
    for (const how of ["space", "space", "press", "press"]) {
      if (how === "space") {
        await press(" ");
      } else {
        await click(".github-pulls-stack-row .github-pull-stack-label");
        await frames();
      }
      toggles.push([how, ...(await stackState())]);
    }
    measured.toggles = toggles;
    check(
      "Space and a press on a stack's row close and open it, and focus stays on it",
      JSON.stringify(toggles) ===
        JSON.stringify([
          ["space", "false", "286"],
          ["space", "true", "286"],
          ["press", "false", "286"],
          ["press", "true", "286"],
        ]),
      JSON.stringify(toggles),
    );
    // The Stack Overview row's children are its stack's changed files (mb-odt4), as a pull
    // request's row's are its own: Space, Right, and a press on its change line's chevron
    // open them under it, Space and Left close them, focus stays on the row, and none of
    // them opens a page, though the toggle is in the row's link. The stack's pull requests
    // stay drawn beside it throughout: none is ever under it.
    const wholeState = async () => [
      ...(await evaluate(
        `[document.querySelector(".github-pulls-whole-row").getAttribute("aria-expanded"), document.querySelector(".github-pulls-whole-item > .github-pull-files:not(.tree-children-collapsed)") !== null, document.querySelector('a.github-pulls-row[data-number="7"]')?.getAttribute("aria-level") ?? null, location.pathname]`,
      )),
      await focused(),
    ];
    await evaluate(`document.querySelector(".github-pulls-whole-row").focus()`);
    const wholeAt = (await wholeState())[3];
    const folds = [];
    for (const how of [" ", " ", "ArrowRight", "ArrowLeft", "toggle", "toggle"]) {
      if (how === "toggle") {
        await click(".github-pulls-whole-row .github-pulls-whole-change > .github-pulls-toggle");
      } else {
        await press(how);
      }
      // A tree that opens with no rows waits briefly for its first read before it paints
      // open (pull-files-tree.js, `FILES_OPEN_HOLD_MS`).
      await waitFor(
        `(document.querySelector(".github-pulls-whole-item > .github-pull-files:not(.tree-children-collapsed)") !== null) === (document.querySelector(".github-pulls-whole-row").getAttribute("aria-expanded") === "true")`,
        `the Stack Overview row's files follow its state after ${how}`,
      );
      await frames();
      folds.push([how, ...(await wholeState())]);
    }
    measured.wholeFiles = folds;
    check(
      "Space, Right, Left, and a press on its change line's chevron open and close a stack's changed files under its Stack Overview row, its pull requests stay beside it, focus stays on it, and no page opens",
      JSON.stringify(folds) ===
        JSON.stringify([
          [" ", "true", true, "2", wholeAt, "whole 286"],
          [" ", "false", false, "2", wholeAt, "whole 286"],
          ["ArrowRight", "true", true, "2", wholeAt, "whole 286"],
          ["ArrowLeft", "false", false, "2", wholeAt, "whole 286"],
          ["toggle", "true", true, "2", wholeAt, "whole 286"],
          ["toggle", "false", false, "2", wholeAt, "whole 286"],
        ]),
      JSON.stringify(folds),
    );
    // A member's changed files hang under its item (mb-1z7j): Right on the row opens them, as on a folder's, a tree level further in than the row, and focus stays
    // on the row; Left closes them, and Left again goes to the stack's row.
    const SEVEN = `document.querySelector('.github-pulls-change[data-number="7"]')`;
    const SEVEN_ROW = `document.querySelector('a.github-pulls-row[data-number="7"]')`;
    const sevenFiles = `document.querySelector('.github-pulls-item[data-number="7"] .github-pull-file-row, .github-pulls-item[data-number="7"] .github-pull-folder-row')`;
    await evaluate(`${SEVEN_ROW}.focus()`);
    await press("ArrowRight");
    await waitFor(`${sevenFiles} !== null`);
    const files = await evaluate(`(() => {
      const member = ${SEVEN_ROW};
      const change = ${SEVEN};
      const file = ${sevenFiles};
      const start = (row) => parseFloat(getComputedStyle(row).paddingLeft) + row.getBoundingClientRect().left;
      // The file row's leading glyph, a folder's chevron or a file's change letter, from the
      // pull request's state icon, which leads its run (mb-pw8t).
      const icon = member?.querySelector(".github-pull-state-icon").getBoundingClientRect() ?? null;
      const active = document.activeElement;
      return {
        focus: active === member ? "#7" : active?.className ?? null,
        expanded: member?.getAttribute("aria-expanded") ?? null,
        // The toggle, hidden from assistive technology, only turns its chevron.
        lineTurned: change?.classList.contains("expanded") ?? null,
        level: file.getAttribute("aria-level"),
        rowLevel: member?.getAttribute("aria-level") ?? null,
        indent: Math.round(start(file) - start(member)),
        fromIcon: icon === null ? null : Math.round((file.firstElementChild.getBoundingClientRect().left - icon.left) * 100) / 100,
        belowRow: member === null ? null : Math.round((file.getBoundingClientRect().top - member.getBoundingClientRect().bottom) * 100) / 100,
      };
    })()`);
    measured.nestedTip = await evaluate(NESTED_TIP);
    await press("ArrowLeft");
    files.afterLeft = [
      await evaluate(`${SEVEN_ROW}?.getAttribute("aria-expanded") ?? null`),
      await focused(),
    ];
    await press("ArrowLeft");
    files.afterSecondLeft = await focused();
    measured.memberFiles = files;
    check(
      "a member's changed files are a tree level under its item, which Right opens with focus kept on its row, and Left closes them, then leaves for its stack",
      files.focus === "#7" &&
        files.expanded === "true" &&
        files.lineTurned === true &&
        files.rowLevel === "2" &&
        files.level === "3" &&
        // One tree level under the state icon, in the row's one slot (mb-3vil, mb-pw8t).
        files.indent === Math.round(list.treeIndent) &&
        near(files.fromIcon, list.treeIndent) &&
        files.belowRow >= -0.5 &&
        JSON.stringify(files.afterLeft) === JSON.stringify(["false", "#7"]) &&
        files.afterSecondLeft === "stack 286",
      JSON.stringify(files),
    );
    // The keys on a first-level pull request (mb-1l4i, mb-1z7j): its item is one stop.
    // Space opens and closes its changed files with focus kept on its row, and the list does
    // not scroll a page from under it, as the browser's Space on a link would; Up and Down walk
    // whole pull requests, over open files, and expand nothing; Right opens the files, Left
    // closes them, Left on a closed first-level row stays, and Right on an open row goes into
    // its files, as on a folder's.
    const ROW106 = `document.querySelector('a.github-pulls-row[data-number="106"]')`;
    const LINE = `document.querySelector('.github-pulls-change[data-number="106"]')`;
    // Observe focus, disclosure and the number of expanded pull requests in the same
    // browser turn. An opening tree may still be waiting for its cached files.
    const state = async (expanded) => {
      const deadline = Date.now() + STEP_MS;
      let sample;
      do {
        sample = await evaluate(`[${FOCUSED}, ${ROW106}?.getAttribute("aria-expanded") ?? null,
          document.querySelectorAll('a.github-pulls-row[aria-expanded="true"]:not(.github-pulls-whole-row)').length]`);
        if (sample[1] === expanded) {
          return sample;
        }
        await frames();
      } while (Date.now() < deadline);
      throw new Error(
        `#106 disclosure did not settle; last keyboard state ${JSON.stringify(sample)}`,
      );
    };
    // The previous walk finishes at Stack #286. Start this walk with its two adjacent
    // rows in view so both remain observable when Down moves the focus from #106.
    await evaluate(`document.querySelector(".tree-content").scrollTop = 0`);
    await waitFor(`[105, 106].every((number) => {
      const row = document.querySelector('a.github-pulls-row[data-number="' + number + '"]');
      const pane = document.querySelector(".tree-content").getBoundingClientRect();
      const box = row?.getBoundingClientRect();
      return box && box.bottom > pane.top && box.top < pane.bottom;
    })`);
    await evaluate(`document.activeElement?.blur(), ${ROW106}.focus({preventScroll: true})`);
    const scrolled = `Math.round(document.querySelector(".tree-content").scrollTop)`;
    const spaceBefore = await evaluate(scrolled);
    const walk = [];
    for (const [key, want] of [
      [" ", ["#106", "true", 1]],
      [" ", ["#106", "false", 0]],
      ["ArrowDown", ["#105", "false", 0]],
      ["ArrowUp", ["#106", "false", 0]],
      ["ArrowRight", ["#106", "true", 1]],
      ["ArrowLeft", ["#106", "false", 0]],
      ["ArrowLeft", ["#106", "false", 0]],
      ["ArrowRight", ["#106", "true", 1]],
      ["ArrowDown", ["#105", "true", 1]],
      ["ArrowUp", ["#106", "true", 1]],
      ["ArrowRight", ["file", "true", 1]],
    ]) {
      if (key === "ArrowRight" && want[0] === "file") {
        // Its files are read and shown before Right can go into them: an opening tree draws
        // its rows in its group while it holds the group closed (pull-files-view.js).
        await waitFor(
          `(() => { const files = document.querySelector('.github-pulls-item[data-number="106"] .github-pull-files'); const row = files?.querySelector(":is(.github-pull-file-row, .github-pull-folder-row)"); return row != null && !files.classList.contains("tree-children-collapsed") && getComputedStyle(row).visibility === "visible"; })()`,
        );
      }
      await press(key);
      walk.push([key, ...(await state(want[1]))]);
      if (walk.length === 2) {
        measured.spaceOnRow = { before: spaceBefore, after: await evaluate(scrolled) };
      }
    }
    measured.walk = walk;
    check(
      "Space on a pull request's row opens and closes its files and leaves the list where it was",
      measured.spaceOnRow.after === measured.spaceOnRow.before,
      JSON.stringify(measured.spaceOnRow),
    );
    check(
      "Space toggles a pull request's files with focus on its row; Up and Down walk whole pull requests and expand nothing; Right opens the files, Left closes them and then stays, and Right on an open row goes into them",
      JSON.stringify(walk) ===
        JSON.stringify([
          [" ", "#106", "true", 1],
          [" ", "#106", "false", 0],
          ["ArrowDown", "#105", "false", 0],
          ["ArrowUp", "#106", "false", 0],
          ["ArrowRight", "#106", "true", 1],
          ["ArrowLeft", "#106", "false", 0],
          ["ArrowLeft", "#106", "false", 0],
          ["ArrowRight", "#106", "true", 1],
          ["ArrowDown", "#105", "true", 1],
          ["ArrowUp", "#106", "true", 1],
          ["ArrowRight", "file", "true", 1],
        ]),
      JSON.stringify(walk),
    );
    // Its toggle was never focused, is hidden from assistive technology, and turns its chevron
    // with its row's state.
    check(
      "a pull request's toggle is never focused, is hidden, and turns its chevron with its row's state",
      walk.every(([, focus]) => !String(focus).startsWith("line ")) &&
        (await evaluate(
          `[${LINE}?.getAttribute("aria-hidden"), ${LINE}?.classList.contains("expanded")].join()`,
        )) === "true,true",
      JSON.stringify(walk),
    );
    // Closed again, from its row, for what follows.
    await evaluate(`document.activeElement?.blur(), ${ROW106}.focus()`);
    await press(" ");
    await waitFor(`${ROW106}?.getAttribute("aria-expanded") !== "true"`);
    check(
      "a stack's row takes the focus ring a pull request's row does",
      keys[1].ring === "solid" && keys[0].ring === "solid",
      JSON.stringify(keys),
    );
    phase("keys");
  }

  if (!before) {
    // The shell's tooltip rule where it runs, the document's own listener, read from the
    // tooltip it shows or does not (docs/design-system.md, "Tooltips Add Information").
    const tips = await evaluate(SHELL_TIPS);
    measured.shellTips = tips;
    check(
      "the shell shows no tooltip that is its element's whole text, in any case or spacing, and shows it while the text is cut short",
      tips.whole === null &&
        tips.wholeSpaced === null &&
        tips.cut === "A pull request title far longer than the box it is drawn in",
      JSON.stringify(tips),
    );
    check(
      "the shell shows no tooltip on a whole branch chip, and shows the full name while the chip's label is cut short",
      tips.chipWhole === null &&
        tips.chipWholeOverflowsVertically &&
        !tips.chipWholeOverflowsHorizontally &&
        tips.chipLabelCut === true &&
        tips.chipCut === "feature/a-branch-name-longer-than-its-chip",
      JSON.stringify(tips),
    );
    check("the shell shows a glyph-only control's tooltip", tips.glyph === "Copy path");
    // A top-level changed file's tip is its name, beside its status letter and counts
    // (mb-n1ye): it shows only while the name is cut short. A nested file's is its whole
    // path, which the row does not show.
    check(
      "a nested changed file's row shows its whole path as its tooltip",
      measured.nestedTip.tip === "docs/new.md" && measured.nestedTip.shown === "docs/new.md",
      JSON.stringify(measured.nestedTip),
    );
    // #106 holds every folder open, and its one top-level file is its last row. Right on its
    // row opens them.
    await evaluate(
      `document.activeElement?.blur(), document.querySelector('a.github-pulls-row[data-number="106"]')?.focus()`,
    );
    await press("ArrowRight");
    // Every page of its files is in, so its rows stand still.
    await waitFor(
      `(() => { const files = document.querySelector('.github-pulls-item[data-number="106"] .github-pull-files'); return files?.querySelector(".github-pull-files-rows")?.firstElementChild != null && files.querySelector(".mb-delayed-loading")?.hidden === true; })()`,
    );
    const fileTips = await evaluate(FILE_TIPS);
    measured.fileTips = fileTips;
    check(
      "a top-level changed file's row shows no tooltip while its name is whole, and shows it while the name is cut short",
      fileTips.whole.tip === "README.md" &&
        fileTips.whole.kept === true &&
        fileTips.whole.cut === false &&
        fileTips.whole.shown === null &&
        fileTips.narrow.kept === true &&
        fileTips.narrow.cut === true &&
        fileTips.narrow.shown === "README.md",
      JSON.stringify(fileTips),
    );
    await evaluate(
      `document.activeElement?.blur(), document.querySelector('a.github-pulls-row[data-number="106"]')?.focus()`,
    );
    await press("ArrowLeft");
    await waitFor(
      `document.querySelector('a.github-pulls-row[data-number="106"]')?.getAttribute("aria-expanded") !== "true"`,
    );
    await evaluate(`document.querySelector(".tree-content").scrollTop = 0, true`);
    await frames();
    phase("tips");
  }

  if (!before) {
    // The toolbar wraps in a narrow pane (docs/design-system.md, "Navigation Toolbars Wrap"),
    // and its Show group, a segmented control, takes the cluster layout where its line cannot
    // hold it joined (filter-controls.js, `fitJoinedGroups`). Every pane width from the
    // narrowest to well past the default, in both font sets, with three- and four-digit
    // tallies: the sweep fits the group at each width as the row's observer does a frame
    // later.
    await evaluate(
      `window.wrapErrors = []; window.addEventListener("error", (event) => window.wrapErrors.push(String(event.message))), true`,
    );
    const ROW = "#nav-toolbar-pulls .nav-toolbar-row";
    const SPEC = {
      bar: "#nav-toolbar-pulls",
      row: ROW,
      fit: true,
      tokens: {
        gap: "var(--nav-toolbar-gap)",
        line: "var(--nav-toolbar-line-height)",
        cluster: "var(--chip-cluster-gap)",
      },
    };
    // The tallies, pinned: the panel writes them on every render, so a write that would
    // take a pinned one back is answered with the pinned text, before the browser paints.
    // `null` lets the panel's own text stand again.
    const TALLIES = `(texts) => {
      window.pinnedTallies?.disconnect();
      window.pinnedTallies = null;
      if (texts === null) return;
      const row = document.querySelector("${ROW}");
      const pin = () => {
        for (const [value, text] of Object.entries(texts)) {
          const tally = row.querySelector('[data-chip-value="' + value + '"] .count');
          if (tally.textContent !== text) tally.textContent = text;
        }
      };
      pin();
      window.pinnedTallies = new MutationObserver(pin);
      window.pinnedTallies.observe(row, { childList: true, characterData: true, subtree: true });
    }`;
    const shown = await evaluate(
      `Object.fromEntries([...document.querySelectorAll('${ROW} .chip-group .chip')].map((chip) => [chip.dataset.chipValue, chip.querySelector(".count").textContent]))`,
    );
    const font = async (name) => {
      await evaluate(
        `document.documentElement.setAttribute("data-app-font", ${JSON.stringify(name)}), true`,
      );
      await evaluate("document.fonts.ready.then(() => true)");
      await frames();
    };
    const paneWidth = (width) =>
      evaluate(
        `(() => { const pane = document.querySelector(".tree-pane"); pane.style.width = ${JSON.stringify(width === null ? "" : `${width + 1}px`)}; return true; })()`,
      );
    // Long enough for a resize to reach the row's observer, and its fit the next frame.
    const settle = () =>
      evaluate(
        "new Promise((r) => { let k = 4; const step = () => (--k ? requestAnimationFrame(step) : r(true)); requestAnimationFrame(step); })",
      );
    // The group's layout as drawn: its fit, and whose border frames the chips.
    const LOOK = `(() => {
      const group = document.querySelector("${ROW} .chip-group");
      const chip = group.querySelector(".chip");
      return {
        fit: group.getAttribute("data-fit"),
        groupBorder: getComputedStyle(group).borderTopWidth,
        chipBorder: getComputedStyle(chip).borderTopWidth,
      };
    })()`;
    // Every frame of a few: the group's fit while the pane holds one width.
    const HOLD = `new Promise((resolve) => {
      const group = document.querySelector("${ROW} .chip-group");
      const seen = [];
      const step = () => {
        seen.push(group.getAttribute("data-fit"));
        if (seen.length < 8) requestAnimationFrame(step); else resolve(seen);
      };
      requestAnimationFrame(step);
    })`;
    // A drag across the break, a pixel a frame: the fit each frame shows.
    const DRAG = `(from, to) => new Promise((resolve) => {
      const pane = document.querySelector(".tree-pane");
      const group = document.querySelector("${ROW} .chip-group");
      const seen = [];
      let width = from;
      const step = () => {
        seen.push(group.getAttribute("data-fit"));
        if (width < to) { resolve(seen); return; }
        pane.style.width = width + 1 + "px";
        width -= 1;
        requestAnimationFrame(step);
      };
      requestAnimationFrame(step);
    })`;
    measured.wrap = {};
    for (const set of ["clean", "system"]) {
      await font(set);
      for (const [digits, texts] of [
        ["3-digit", { open: "100", closed: "200", all: "300" }],
        ["4-digit", { open: "1,234", closed: "5,678", all: "6,912" }],
      ]) {
        const label = `${set} fonts, ${digits} tallies`;
        const swept = await evaluate(
          `((${TALLIES})(${JSON.stringify(texts)}), (${SWEEP})(${JSON.stringify({ widths: WIDTHS, ...SPEC })}))`,
        );
        const { gap, line, cluster } = swept.tokens;
        const verdict = judge(label, swept, {
          pad: gap,
          line,
          gap,
          column: gap,
          cluster,
        });
        check(
          `${label}: the toolbar keeps the wrap rule`,
          verdict.failures.length === 0,
          verdict.failures.slice(0, 6).join("\n"),
        );
        // Joined from one width up, the cluster below it, never one then the other again.
        const fits = swept.rows.map((row) => row.fit);
        const joinedFrom =
          swept.rows.find((_row, index) => fits.slice(index).every((fit) => fit === null))?.width ??
          null;
        check(
          `${label}: the group is the cluster below one width and joined from it`,
          joinedFrom !== null &&
            swept.rows.every((row) =>
              row.width < joinedFrom ? row.fit === "wrap" : row.fit === null,
            ),
          JSON.stringify(fits),
        );
        measured.wrap[label] = { oneLineFrom: verdict.oneLineFrom, joinedFrom };
        // The row's own observers, with no sweep fitting for them: joined at a pane that
        // holds the group, the cluster at the narrowest, each a frame or two after the resize.
        await evaluate(`(${TALLIES})(${JSON.stringify(texts)}), true`);
        await paneWidth(WIDEST);
        await settle();
        const wide = await evaluate(LOOK);
        check(
          `${set} fonts, ${digits} tallies: at ${WIDEST} px the group is joined, one frame round its chips`,
          wide.fit === null && wide.groupBorder === "1px" && wide.chipBorder === "0px",
          JSON.stringify(wide),
        );
        await paneWidth(NARROWEST);
        await settle();
        const narrow = await evaluate(LOOK);
        check(
          `${set} fonts, ${digits} tallies: at ${NARROWEST} px the group is the cluster, a frame round each chip`,
          narrow.fit === "wrap" && narrow.groupBorder === "0px" && narrow.chipBorder === "1px",
          JSON.stringify(narrow),
        );
        await shot(`after-pulls-wrap-${set}-${digits}`, await paneClip());
        // At the break and a pixel under it the group holds one layout, frame after frame,
        // and a drag across the break switches it once.
        const breakAt = measured.wrap[`${set} fonts, ${digits} tallies`].joinedFrom;
        if (breakAt !== null && breakAt > NARROWEST) {
          for (const [width, fit] of [
            [breakAt - 1, "wrap"],
            [breakAt, null],
          ]) {
            await paneWidth(width);
            await settle();
            const held = await evaluate(HOLD);
            check(
              `${set} fonts, ${digits} tallies: at ${width} px the group holds its layout`,
              held.every((seen) => seen === fit),
              JSON.stringify(held),
            );
          }
          await paneWidth(breakAt + 8);
          await settle();
          const dragged = await evaluate(`(${DRAG})(${breakAt + 8}, ${breakAt - 8})`);
          await settle();
          const switches = dragged.slice(1).filter((fit, index) => fit !== dragged[index]).length;
          check(
            `${set} fonts, ${digits} tallies: a drag across the break switches the layout once`,
            switches === 1 && dragged[0] === null && dragged.at(-1) === "wrap",
            JSON.stringify(dragged),
          );
        }
        await paneWidth(null);
        await settle();
      }
      // Shown again after the pane crossed the break behind another tab, the group is
      // fitted before the first frame paints it: at that frame's ResizeObserver delivery,
      // after layout and before paint, it is already the cluster, whole, and the toolbar
      // is the height it settles at, so the list under it does not jump a frame later.
      await paneWidth(WIDEST);
      await settle();
      await click('.nav-tab-bar [data-tab="files"]');
      await waitFor(`document.getElementById("nav-toolbar-pulls").hidden`);
      await paneWidth(NARROWEST);
      await settle();
      const BAR_LOOK = `{
        fit: group.getAttribute("data-fit"),
        cut: group.scrollWidth > group.clientWidth,
        height: Math.round(bar.getBoundingClientRect().height * 100) / 100,
      }`;
      const firstFrame = await evaluate(`new Promise((resolve) => {
        const bar = document.getElementById("nav-toolbar-pulls");
        const group = bar.querySelector(".chip-group");
        const behind = group.getAttribute("data-fit");
        const delivery = new ResizeObserver(() => {
          delivery.disconnect();
          resolve({ behind, ...${BAR_LOOK} });
        });
        document.querySelector('.nav-tab-bar [data-tab="pulls"]').click();
        delivery.observe(bar);
      })`);
      await settle();
      const settledShown = await evaluate(`(() => {
        const bar = document.getElementById("nav-toolbar-pulls");
        const group = bar.querySelector(".chip-group");
        return ${BAR_LOOK};
      })()`);
      check(
        `${set} fonts: Pulls shown again after the pane narrowed behind Files is the cluster in its first frame`,
        firstFrame.behind === null &&
          firstFrame.fit === "wrap" &&
          !firstFrame.cut &&
          firstFrame.height === settledShown.height &&
          settledShown.fit === "wrap",
        JSON.stringify({ firstFrame, settledShown }),
      );
      measured.wrap[`${set} fonts, shown again`] = { firstFrame, settledShown };
      await paneWidth(null);
      await settle();
    }
    await evaluate(`(${TALLIES})(null), true`);
    await evaluate(
      `(() => { for (const [value, text] of Object.entries(${JSON.stringify(shown)})) document.querySelector('${ROW} [data-chip-value="' + value + '"] .count').textContent = text; return true; })()`,
    );
    await font("clean");
    // Bound, the observers fit a group; disposed, nothing of them fires.
    const disposal = await evaluate(`(async () => {
      const fc = window.metabrowser.filterControls;
      const frame = () => new Promise((resolve) => requestAnimationFrame(() => resolve()));
      const frames = async () => { for (let k = 0; k < 4; k += 1) await frame(); };
      const host = document.createElement("div");
      host.className = "nav-toolbar";
      host.dataset.navToolbar = "probe";
      host.style.cssText = "position: fixed; inset-block-start: 0; inset-inline-start: 0; width: 120px; visibility: hidden;";
      host.innerHTML = '<div class="nav-toolbar-row">' + fc.groupHtml({
        key: "probe", select: "one", layout: "joined", label: "Probe", value: "a",
        options: [{ value: "a", label: "Alpha 1,234" }, { value: "b", label: "Beta 5,678" }, { value: "c", label: "Gamma 6,912" }],
      }) + "</div>";
      document.body.append(host);
      const group = host.querySelector(".chip-group");
      const dispose = fc.bind(host.firstElementChild, {});
      const bound = group.getAttribute("data-fit");
      host.style.width = "1000px";
      await frames();
      const widened = group.getAttribute("data-fit");
      host.style.width = "120px";
      await frames();
      const narrowed = group.getAttribute("data-fit");
      dispose();
      host.style.width = "1000px";
      await frames();
      const resizedAfter = group.getAttribute("data-fit");
      group.querySelector(".chip").textContent = "A";
      await frames();
      const mutatedAfter = group.getAttribute("data-fit");
      host.hidden = true;
      await frames();
      host.hidden = false;
      await frames();
      const shownAfter = group.getAttribute("data-fit");
      host.remove();
      return { bound, widened, narrowed, resizedAfter, mutatedAfter, shownAfter };
    })()`);
    measured.wrapDisposal = disposal;
    check(
      "bound, a joined group is fitted at once and on each resize; disposed, nothing fires",
      JSON.stringify(disposal) ===
        JSON.stringify({
          bound: "wrap",
          widened: null,
          narrowed: "wrap",
          resizedAfter: "wrap",
          mutatedAfter: "wrap",
          shownAfter: "wrap",
        }),
      JSON.stringify(disposal),
    );
    const errors = await evaluate("window.wrapErrors");
    check(
      "no ResizeObserver loop error, nor any other, while the toolbar wraps",
      errors.length === 0,
      errors.join("\n"),
    );
    phase("wrapped");
  }

  // The page's stack menu, from a member's row, brought into view as a reader would.
  if (before) {
    // Scrolled to the end as it grows: the rows near it mount once the window reaches them.
    await waitFor(
      `(document.querySelector(".tree-content").scrollTop = 1e6) && document.querySelector('a.github-pulls-row[data-number="9"]') !== null`,
    );
    await evaluate(
      `document.querySelector('a.github-pulls-row[data-number="9"]').scrollIntoView({block: "center"})`,
    );
  }
  await click('a.github-pulls-row[data-number="9"]');
  await waitFor(
    `[...document.querySelectorAll(".github-pull-stack-trigger:not(.github-pull-stack-strut)")].some((t) => t.getAttribute("aria-label") === "Navigate Stack #286, position 3 of 4")`,
  );
  phase("page");
  await evaluate(
    `[...document.querySelectorAll(".github-pull-stack-trigger:not(.github-pull-stack-strut)")].find((t) => t.getAttribute("aria-label") === "Navigate Stack #286, position 3 of 4").click()`,
  );
  await waitFor(
    `document.querySelector(".github-pull-stack-menu .github-pull-stack-member") !== null`,
  );
  const menu = await evaluate(`(() => {
    const menu = document.querySelector(".github-pull-stack-menu");
    const heading = menu.querySelector(".group-heading");
    return {
      heading: heading.textContent,
      shown: heading.innerText,
      classes: heading.className,
      members: [...menu.querySelectorAll(".github-pull-stack-member")].map((a) => Number(new URL(a.href).pathname.split("/")[2])),
      tip: document.querySelector(".github-pull-stack-trigger[aria-expanded='true']")?.dataset.tipText ?? null,
      // A member's position and title, and a Pulls row's place: their ink.
      ink: (() => {
        const color = (selector) => {
          const el = document.querySelector(selector);
          return el === null ? null : getComputedStyle(el).color;
        };
        const probe = document.createElement("span");
        probe.style.color = "var(--text)";
        document.body.append(probe);
        const text = getComputedStyle(probe).color;
        probe.remove();
        return {
          position: color(".github-pull-stack-menu .github-pull-stack-member-position"),
          title: color(".github-pull-stack-menu .github-pull-stack-member-title"),
          trigger: color(".github-pull-stack-trigger[aria-expanded='true'] .github-pull-stack-position"),
          badge: color(".github-pulls-row .github-pulls-place:not([hidden]) .github-pull-stack-position"),
          text,
        };
      })(),
      // A pull request's number where it names the pull request, and a stack's position:
      // their computed weights (mb-vrvs).
      weights: (() => {
        const weight = (selector) => {
          const el = document.querySelector(selector);
          return el === null ? null : getComputedStyle(el).fontWeight;
        };
        return {
          row: weight(".github-pulls-row .github-pulls-number"),
          title: weight(".github-pull-title .github-pull-number"),
          position: weight(".github-pull-stack-menu .github-pull-stack-member-position"),
          place: weight(".github-pulls-row .github-pulls-place:not([hidden]) .github-pull-stack-position"),
        };
      })(),
      // The Stack Overview row (mb-7cn4): its glyph and its words, measured as a member's are.
      whole: (() => {
        const row = menu.querySelector(".github-pull-stack-whole");
        if (row === null) return null;
        const [icon, copy] = row.children;
        const words = copy?.firstElementChild ?? null;
        const r = (value) => Math.round(value * 100) / 100;
        return {
          parts: [...row.children].map((el) => el.className),
          glyph: icon?.querySelector("svg") !== null,
          ink: icon ? getComputedStyle(icon).color : null,
          // The text's ink, which the glyph takes, as the stack page's title icon does.
          textInk: (() => {
            const probe = document.createElement("span");
            probe.style.color = "var(--text)";
            document.body.append(probe);
            const ink = getComputedStyle(probe).color;
            probe.remove();
            return ink;
          })(),
          iconLeft: r(icon.getBoundingClientRect().left),
          iconWidth: r(icon.getBoundingClientRect().width),
          titleLeft: words === null ? null : r(words.getBoundingClientRect().left),
          text: row.textContent,
        };
      })(),
      // Each member's one line (mb-as06): its state icon, then its title, and at the line's end
      // its bold place, the muted dot, its number, and another dot and its author (mb-1kzu,
      // mb-pw8t, mb-x0z1), measured part by part, with the Pulls row of the same pull request.
      lines: (() => {
        const probe = document.createElement("span");
        probe.style.color = "var(--muted)";
        document.body.append(probe);
        const muted = getComputedStyle(probe).color;
        probe.remove();
        const box = (el) => el.getBoundingClientRect();
        return [...menu.querySelectorAll(".github-pull-stack-member")].map((link) => {
          const number = new URL(link.href).pathname.split("/")[2];
          // The readiness's words, out of view, follow the icon, and its glyph's cell ends the
          // line (mb-3n21), so the icon and the line are read by their classes.
          const icon = link.querySelector(":scope > .github-pull-state-icon");
          const copy = link.querySelector(":scope > .github-pull-row-copy");
          const [title, position, by, end] = copy.children;
          const cell = end.querySelector(".github-pull-stack-member-readiness");
          const shown = end.querySelector(".github-pull-stack-member-number");
          const dot = position.querySelector(".github-pull-stack-dot");
          // The row's state icon starts its run (mb-85op, mb-pw8t).
          const row = document.querySelector(\`a.github-pulls-row[data-number="\${number}"] > .github-pulls-heading > .github-pull-state-icon\`);
          // The row's number is in its run, after its title and place, and its author after it.
          const rowNumber = document.querySelector(\`li.github-pulls-item[data-number="\${number}"] .github-pulls-number\`);
          const rowAuthor = document.querySelector(\`li.github-pulls-item[data-number="\${number}"] > .github-pulls-entry > .github-pulls-row > .sr-only\`);
          const face = (el) => el === null ? null : {
            color: getComputedStyle(el).color,
            weight: getComputedStyle(el).fontWeight,
            size: getComputedStyle(el).fontSize,
            numerals: getComputedStyle(el).fontVariantNumeric,
          };
          const fontSize = parseFloat(getComputedStyle(title).fontSize);
          return {
            number: Number(number),
            parts: [...link.children].map((el) => el.className),
            // The readiness's cell, the glyph's width, ends the line after the author's copy.
            readinessCell: cell === null ? null : {
              width: Math.round(box(cell).width * 100) / 100,
              beforeNumber: cell.nextElementSibling === shown && box(cell).right <= box(shown).left + 0.5,
              endGap: Math.round((link.getBoundingClientRect().right - parseFloat(getComputedStyle(link).paddingRight) - box(shown).right) * 100) / 100,
              glyph: parseFloat(getComputedStyle(link).getPropertyValue("--icon-glyph")),
            },
            line: [...(copy?.children ?? [])].map((el) => el.className),
            state: icon?.dataset.state ?? null,
            glyph: icon?.querySelector("svg") !== null,
            rowState: row?.dataset.state ?? null,
            iconLeft: Math.round(box(icon).left * 100) / 100,
            iconWidth: Math.round(box(icon).width * 100) / 100,
            titleLeft: Math.round(box(title).left * 100) / 100,
            // The place, the dot, and the number are together at the line's end, the place
            // after the title (mb-pw8t).
            placeAfterTitle: title.nextElementSibling === position,
            placeBeforeNumber: position.nextElementSibling === by && by.nextElementSibling === end,
            height: Math.round(box(link).height * 100) / 100,
            copyHeight: Math.round(box(copy).height * 100) / 100,
            fontSize,
            positionWeight: getComputedStyle(position).fontWeight,
            positionText: position.querySelector(".github-pull-stack-position").textContent,
            dot: { text: dot.textContent, color: getComputedStyle(dot).color, size: getComputedStyle(dot).fontSize, hidden: dot.getAttribute("aria-hidden") },
            muted,
            titleWeight: getComputedStyle(title).fontWeight,
            titleCut: { overflow: getComputedStyle(title).textOverflow, wrap: getComputedStyle(title).whiteSpace },
            tip: link.dataset.tipText ?? null,
            titleText: title.textContent,
            shown: shown === undefined ? null : {
              text: shown.textContent,
              whole: shown.scrollWidth <= shown.clientWidth + 1,
              width: Math.round(box(shown).width * 100) / 100,
              onLastLine: Math.abs(box(end).bottom - box(copy).bottom) <= 0.5,
              face: face(shown),
              rowText: rowNumber?.textContent ?? null,
              rowFace: face(rowNumber),
              titleSize: getComputedStyle(title).fontSize,
            },
            // The author, after a dot after the number, ends the line (mb-x0z1).
            by: by === undefined ? null : {
              parts: [...by.children].map((el) => el.className),
              hidden: by.hidden,
              name: by.querySelector(".github-pull-stack-member-author")?.textContent ?? null,
              rowName: rowAuthor?.textContent ?? null,
              beforeNumber: by.nextElementSibling === end,
              endGap: Math.round((box(copy).right - box(by).right) * 100) / 100,
              dot: by.firstElementChild ? getComputedStyle(by.firstElementChild).color : null,
              whole: (() => {
                const name = by.querySelector(".github-pull-stack-member-author");
                return name !== null && name.scrollWidth <= name.clientWidth;
              })(),
              // The author's share of the line, which its own rule caps at a third, and whether
              // its name is cut short.
              share: Math.round((box(by).width / box(copy).width) * 1000) / 1000,
              cut: (() => {
                const name = by.querySelector(".github-pull-stack-member-author");
                return name !== null && name.scrollWidth > name.clientWidth + 0.5;
              })(),
              // The name's baseline less the number's: an empty inline block's foot is its
              // line's baseline.
              baseline: (() => {
                const at = (el) => {
                  if (el === null) return null;
                  const probe = document.createElement("span");
                  probe.style.cssText = "display:inline-block;width:0;height:0;vertical-align:baseline";
                  el.append(probe);
                  const foot = probe.getBoundingClientRect().bottom;
                  probe.remove();
                  return foot;
                };
                const name = at(by.querySelector(".github-pull-stack-member-author"));
                const number = at(shown);
                return name === null || number === null ? null : Math.round((name - number) * 100) / 100;
              })(),
            },
            current: link.getAttribute("aria-current") === "page",
          };
        });
      })(),
    };
  })()`);
  measured.menu = menu;
  // Each member's name as Chrome computes it for assistive technology: its state and title,
  // then its place, its number, and its author, which the line shows at its end (mb-1kzu,
  // mb-pw8t, mb-x0z1).
  if (!before) {
    await send("Accessibility.enable");
    menu.names = [];
    for (let at = 0; at < menu.lines.length; at += 1) {
      const { result: handle } = await send("Runtime.evaluate", {
        expression: `document.querySelectorAll(".github-pull-stack-menu .github-pull-stack-member")[${at}]`,
      });
      const { nodes } = await send("Accessibility.getPartialAXTree", {
        objectId: handle.objectId,
        fetchRelatives: false,
      });
      menu.names.push(nodes?.[0]?.name?.value ?? null);
    }
    await send("Accessibility.disable");
  }
  const menuClip = await evaluate(`(() => {
    const r = document.querySelector(".github-pull-stack-menu").getBoundingClientRect();
    const t = document.querySelector(".github-pull-stack-trigger[aria-expanded='true']").getBoundingClientRect();
    return { x: Math.max(0, Math.min(r.left, t.left) - 16), y: Math.max(0, t.top - 16), width: Math.ceil(Math.max(r.right, t.right) - Math.min(r.left, t.left) + 32), height: Math.ceil(r.bottom - t.top + 32) };
  })()`);
  await shot(before ? "before-stack-menu" : "after-stack-menu", menuClip);
  if (!before) {
    const register = await evaluate(REGISTER);
    measured.register = register;
    check(
      "the stack menu's heading and a stack row's header resolve to the same label tokens",
      register.row !== null &&
        JSON.stringify(register.row) === JSON.stringify(register.menu) &&
        JSON.stringify(register.menu) === JSON.stringify(register.tokens),
      JSON.stringify(register),
    );
    check(
      "the menu's heading is the stack's label",
      menu.heading === "Stack #286" && menu.shown === "STACK #286",
    );
    check(
      "the menu includes every member in stack order",
      JSON.stringify(menu.members) === "[10,9,8,7]",
      JSON.stringify(menu.members),
    );
    check(
      "the trigger's tip names the stack and the place",
      menu.tip === "Stack #286, position 3 of 4",
      menu.tip,
    );
    check(
      "a member's position is in its row's ink, as its title is, not a link's",
      menu.ink.position === menu.ink.title && menu.ink.position === menu.ink.text,
      JSON.stringify(menu.ink),
    );
    check(
      "a pull request's number is bold in a Pulls row and the page's title, as a stack's position is",
      ["row", "title", "position", "place"].every((key) => menu.weights[key] === "700"),
      JSON.stringify(menu.weights),
    );
    // Every member one line in one layout (mb-as06): the state icon, the bold title cut short,
    // and at the line's end the bold place, the muted dot, and the number (mb-1kzu, mb-pw8t),
    // a Pulls row's order; the icon is the Pulls row's state for the same pull request, and
    // every member's icon and title start at one edge.
    const lines = menu.lines;
    const first = lines[0];
    check(
      "every stack member is the state icon, then the title, and the place, the dot, the number, and the author, and its line ends with its readiness's cell, the glyph's width",
      lines.length === menu.members.length &&
        lines.every(
          (line) =>
            JSON.stringify(line.parts) ===
              JSON.stringify([
                "github-pull-state-icon",
                "sr-only github-pull-readiness-said",
                "github-pull-row-copy",
              ]) &&
            line.readinessCell !== null &&
            Math.abs(line.readinessCell.width - line.readinessCell.glyph) <= 0.5 &&
            line.readinessCell.beforeNumber &&
            Math.abs(line.readinessCell.endGap) <= 0.5 &&
            JSON.stringify(line.line) ===
              JSON.stringify([
                "github-pull-stack-member-title",
                "github-pull-stack-member-position",
                "github-pull-stack-member-by",
                "github-pull-row-end",
              ]) &&
            line.placeAfterTitle &&
            line.placeBeforeNumber,
        ),
      JSON.stringify(lines),
    );
    check(
      "each stack member shows the sidebar author before the readiness and number",
      lines.every(
        (line) =>
          line.by &&
          !line.by.hidden &&
          (line.by.rowName?.includes(line.by.name) ?? false) &&
          line.by.beforeNumber &&
          line.by.dot === line.muted,
      ),
      JSON.stringify(lines.map(({ number, by }) => ({ number, by }))),
    );
    // The Stack Overview row is in the members' row grid (mb-7cn4): the stack's Layers glyph,
    // in the text's ink as the stack page's title glyph is (mb-68uk), in the state icon's
    // slot, where every member's icon starts, and its words where every member's title
    // starts. With the menu row's own gap and an empty slot, its words started 2 px past the
    // titles.
    check(
      "the Stack Overview row's glyph and words start where the members' icons and titles do",
      menu.whole !== null &&
        menu.whole.text === "Stack Overview" &&
        menu.whole.glyph &&
        menu.whole.ink === menu.whole.textInk &&
        Math.abs(menu.whole.iconLeft - first.iconLeft) <= 0.5 &&
        Math.abs(menu.whole.iconWidth - first.iconWidth) <= 0.5 &&
        Math.abs(menu.whole.titleLeft - first.titleLeft) <= 0.5,
      JSON.stringify({
        whole: menu.whole,
        first: { iconLeft: first.iconLeft, iconWidth: first.iconWidth, titleLeft: first.titleLeft },
      }),
    );
    // Each member shows its number as its Pulls row does, "#455" (mb-1kzu): whole, after the
    // title and the place, before the author, in the row's number's ink, weight, and
    // numerals at the title's size, and the member's name ends in its title, place, number,
    // and author.
    check(
      "each member's number is shown whole, as its Pulls row's, and its name ends in it and the author",
      lines.every(
        (line, at) =>
          line.shown?.text === `#${line.number}` &&
          line.shown.rowText === line.shown.text &&
          line.shown.whole &&
          line.shown.width > 1 &&
          line.shown.onLastLine &&
          line.shown.rowFace !== null &&
          line.shown.face.color === line.shown.rowFace.color &&
          line.shown.face.weight === line.shown.rowFace.weight &&
          line.shown.face.weight === "700" &&
          line.shown.face.numerals === line.shown.rowFace.numerals &&
          line.shown.face.size === line.shown.titleSize &&
          typeof menu.names[at] === "string" &&
          menu.names[at]
            .replace(/\s+/g, " ")
            .trim()
            .endsWith(`${line.titleText} ${line.positionText} ${line.by?.name} #${line.number}`),
      ),
      JSON.stringify({
        shown: lines.map(({ number, shown }) => ({ number, shown })),
        names: menu.names,
      }),
    );
    check(
      "each member's icon draws its Pulls row's state",
      lines.every((line) => line.glyph && line.state !== null && line.state === line.rowState),
      JSON.stringify(lines.map(({ number, state, rowState }) => ({ number, state, rowState }))),
    );
    check(
      "member headings have enough height for their wrapped copy",
      lines.every((line) => line.height >= line.copyHeight && line.shown.onLastLine),
      JSON.stringify(
        lines.map(({ number, height, copyHeight, fontSize }) => ({
          number,
          height,
          copyHeight,
          fontSize,
        })),
      ),
    );
    check(
      "every member's icon and title start at one edge, the current member's too",
      lines.every((line) => line.iconLeft === first.iconLeft && line.titleLeft === first.titleLeft),
      JSON.stringify(
        lines.map(({ number, iconLeft, titleLeft, current }) => ({
          number,
          iconLeft,
          titleLeft,
          current,
        })),
      ),
    );
    check(
      "the place is bold, the dot muted and small, and the title bold, cut short at the line's end",
      lines.every(
        (line) =>
          line.positionWeight === "700" &&
          line.dot.text === "·" &&
          line.dot.hidden === "true" &&
          line.dot.color === line.muted &&
          line.dot.size === "10px" &&
          line.titleWeight === "700" &&
          line.titleCut.overflow === "clip" &&
          line.titleCut.wrap === "normal" &&
          line.tip === line.titleText,
      ),
      JSON.stringify(lines),
    );
    check(
      "a Pulls row's place is in its number's ink, the row's text",
      menu.ink.badge === menu.ink.text,
      JSON.stringify(menu.ink),
    );
  }
  await shot(before ? "before-window" : "after-window");
  phase("menu");

  if (!before) {
    // The stack menu's keys (docs/design-system.md, "Keys in a Menu", mb-xlla): every way
    // it opens puts focus on the current member, #9, the row marked, and Escape gives focus
    // back to the trigger. The press above opened it.
    const FOCUS = `(() => {
      const el = document.activeElement;
      if (el?.classList.contains("github-pull-stack-member")) {
        return "#" + new URL(el.href).pathname.split("/")[2] + (el.getAttribute("aria-current") === "page" ? " current" : "");
      }
      return el?.classList.contains("github-pull-stack-trigger") ? "trigger " + el.getAttribute("aria-expanded") : (el?.tagName ?? null);
    })()`;
    const menuKeys = [["press", await evaluate(FOCUS)]];
    for (const key of [
      "Escape",
      "ArrowDown",
      "Escape",
      "Enter",
      "Escape",
      " ",
      "Escape",
      "ArrowUp",
    ]) {
      await press(key);
      menuKeys.push([key, await evaluate(FOCUS)]);
    }
    measured.menuKeys = menuKeys;
    const opened = "#9 current";
    const closed = "trigger false";
    check(
      "the stack menu opens on its current member however it opens, and Escape gives focus back",
      JSON.stringify(menuKeys) ===
        JSON.stringify([
          ["press", opened],
          ["Escape", closed],
          ["ArrowDown", opened],
          ["Escape", closed],
          ["Enter", opened],
          ["Escape", closed],
          [" ", opened],
          ["Escape", closed],
          ["ArrowUp", opened],
        ]),
      JSON.stringify(menuKeys),
    );
    // The current member is marked as the Pulls list marks its current row, #9's: the
    // highlight's ground, its item's (mb-1z7j), and its 2px bar, not the hover ground,
    // hovered, focused, or not (mb-xlla). Focus shows on it as on every member, by the ring.
    await send("Input.dispatchMouseEvent", { type: "mouseMoved", x: 640, y: 895 });
    const CURRENT = `(() => {
      const member = document.querySelector('.github-pull-stack-menu .github-pull-stack-member[aria-current="page"]');
      const row = document.querySelector(".github-pulls-row.selected");
      const ms = getComputedStyle(member);
      const rs = row === null ? null : getComputedStyle(row);
      const focused = document.activeElement;
      return {
        focused: focused === member,
        member: { background: ms.backgroundColor, shadow: ms.boxShadow, outline: ms.outlineStyle },
        row: rs === null ? null : { number: row.dataset.number, background: getComputedStyle(row.parentElement).backgroundColor, bar: rs.borderLeftColor, width: rs.borderLeftWidth },
        focusGround: getComputedStyle(focused).backgroundColor,
        focusRing: getComputedStyle(focused).outlineStyle,
      };
    })()`;
    await press("ArrowDown");
    const atRest = await evaluate(CURRENT);
    await press("ArrowUp");
    const focusedCurrent = await evaluate(CURRENT);
    const hoveredCurrent = await (async () => {
      await hover('.github-pull-stack-menu .github-pull-stack-member[aria-current="page"]');
      return evaluate(CURRENT);
    })();
    await send("Input.dispatchMouseEvent", { type: "mouseMoved", x: 640, y: 895 });
    measured.currentMember = { atRest, focusedCurrent, hoveredCurrent };
    const marked = (state) =>
      state.row?.number === "9" &&
      state.member.background === state.row.background &&
      state.member.shadow === `${state.row.bar} 2px 0px 0px 0px inset` &&
      state.row.width === "2px";
    check(
      "the stack menu's current member takes the Pulls list's current row's ground and bar",
      !atRest.focused &&
        marked(atRest) &&
        atRest.member.background !== atRest.focusGround &&
        atRest.member.outline === "none",
      JSON.stringify(atRest),
    );
    check(
      "focused or hovered, it keeps them, and focus shows on it by the ring",
      focusedCurrent.focused &&
        marked(focusedCurrent) &&
        focusedCurrent.focusRing === "solid" &&
        marked(hoveredCurrent),
      JSON.stringify({ focusedCurrent, hoveredCurrent }),
    );
    await press("Escape");
    // One stack: the chip is its glyph and position. A pull request in two, #10, has a chip
    // for each, and each names its stack before its position, as #10's Pulls row does,
    // "4/4 · 300 2/2" (mb-xlla): two bare positions differed only in their tips.
    const CHIPS = `[...document.querySelectorAll(".github-pull-stacks .github-pull-stack-trigger")].map((t) => ({
      text: t.textContent,
      icon: t.querySelector(".github-pull-stack-icon svg") !== null,
      label: t.getAttribute("aria-label"),
      whole: t.scrollWidth <= t.clientWidth,
    }))`;
    const oneStack = await evaluate(CHIPS);
    await click('a.github-pulls-row[data-number="10"]');
    // #10's page, committed, with both its chips (mb-66qu). Until the shell commits it, the
    // page is built in a hidden stage beside #9's (createFilePreviewStage in app.js), and
    // its header holds a strut, a hidden chip of the same class, until its stacks arrive:
    // #9's chip and #10's strut made two chips while #9's page was still the one shown.
    await waitFor(
      `document.querySelector(".preview-file-stage") === null &&
        document.querySelectorAll(".github-pull-stacks").length === 1 &&
        document.querySelectorAll(".github-pull-stacks .github-pull-stack-trigger:not(.github-pull-stack-strut)").length === 2`,
    );
    await frames();
    const twoStacks = await evaluate(CHIPS);
    measured.chips = { oneStack, twoStacks };
    check(
      "one stack's chip is its glyph and bare position; in two, each chip names its stack",
      JSON.stringify(oneStack) ===
        JSON.stringify([
          { text: "3/4", icon: true, label: "Navigate Stack #286, position 3 of 4", whole: true },
        ]) &&
        JSON.stringify(twoStacks) ===
          JSON.stringify([
            {
              text: "286 4/4",
              icon: true,
              label: "Navigate Stack #286, position 4 of 4",
              whole: true,
            },
            {
              text: "300 2/2",
              icon: true,
              label: "Navigate Stack #300, position 2 of 2",
              whole: true,
            },
          ]),
      JSON.stringify(measured.chips),
    );
    phase("chips");
  }
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
process.stdout.write(`pulls stacks in Chrome: ${checks} checks passed\n`);

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
// focus onto and off a stack row; and that the groups list a stack's members in the order
// the page's stack menu does. It times the first row and the grouping's arrival, and with
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
        count: row.querySelector(".github-pulls-stack-count").textContent,
        expanded: row.getAttribute("aria-expanded"),
        tip: row.dataset.tipText,
        members: [],
      };
      stacks.push(open);
    } else if (row.getAttribute("aria-level") === "2" && open !== null) {
      open.members.push({
        number: Number(row.dataset.number),
        // Its place in its stacks, on its number's line, before the number (mb-dzsi).
        badge: row.querySelector(".github-pulls-place .github-pull-stack-position")?.textContent ?? "",
        line: row.querySelector(".github-pulls-line")?.textContent ?? "",
        // Another stack named in it, by the Layers glyph before its number.
        others: row.querySelectorAll(".github-pulls-place .github-pull-stack-other svg").length,
        // A member's row draws no stack icon: the stack's row it sits under has it.
        icons: row.querySelectorAll(".github-pull-stack-icon").length,
        tip: row.querySelector(".github-pulls-place")?.getAttribute("aria-label") ?? "",
      });
    } else {
      open = null;
    }
  }
  const stackRow = list.querySelector(".github-pulls-stack-row");
  const member = list.querySelector('.github-pulls-item[data-level="2"] > .github-pulls-row');
  const flat = [...list.querySelectorAll('.github-pulls-row[aria-level="1"]')].find(
    (row) => !row.classList.contains("github-pulls-stack-row"),
  );
  const box = (el) => el?.getBoundingClientRect() ?? null;
  // The room a row's title gets: its grid cell's width, which a long title fills and is
  // cut at. A member's and a first-level pull request's, and the pane they are in.
  const titleBox = (number) =>
    list.querySelector('a.github-pulls-row[data-number="' + number + '"] .github-pulls-title')?.getBoundingClientRect().width ?? null;
  // The Pulls column carries no tooltip (mb-8mpo): every pull request's and stack's row and
  // its parts, after a pointer has crossed each title, as a reader's would.
  for (const title of list.querySelectorAll(".github-pulls-row .github-pulls-title")) {
    title.dispatchEvent(new PointerEvent("pointerover", { bubbles: true }));
    // Leaving, so no hover is left to read a pull request ahead.
    title.dispatchEvent(new PointerEvent("pointerout", { bubbles: true }));
  }
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
  // A pull request's two lines (mb-lkkt, mb-3cbf): the chevron, the icon, the number's line,
  // and the age, then the title alone, from the text column to the row's end. Each row's
  // parts, from its content box.
  const lines = Object.fromEntries(
    [10, 9, 106].map((number) => {
      const row = list.querySelector('a.github-pulls-row[data-number="' + number + '"]');
      if (row === null) return [number, null];
      const style = getComputedStyle(row);
      const r = row.getBoundingClientRect();
      const inset = r.left + parseFloat(style.borderLeftWidth) + parseFloat(style.paddingLeft);
      const end = r.right - parseFloat(style.paddingRight);
      const of = (selector) => row.querySelector(selector).getBoundingClientRect();
      const meta = of(".github-pulls-meta");
      const age = of(".github-pulls-age");
      const title = of(".github-pulls-title");
      const toggle = of(".github-pulls-toggle");
      const icon = of(".github-pull-state-icon");
      const numberBox = of(".github-pulls-number");
      const metaBox = row.querySelector(".github-pulls-meta");
      const round = (value) => Math.round(value * 100) / 100;
      return [number, {
        text: metaBox.textContent,
        // The number's line is above the title's, and one line of the number's type.
        firstAbove: meta.bottom <= title.top + 0.5 && age.bottom <= title.top + 0.5,
        oneLine: Math.abs(meta.height - parseFloat(getComputedStyle(metaBox).lineHeight)) < 0.5,
        // The number's line starts in the title's column; the age ends at the row's end.
        metaFromTitle: round(meta.left - title.left),
        ageToEnd: round(end - age.right),
        // The title runs from the text column, after the two glyph slots, to the row's end.
        titleToEnd: round(end - title.right),
        titleFromInset: round(title.left - inset),
        textColumn: round(2 * parseFloat(style.getPropertyValue("--tree-icon-slot")) + 2 * parseFloat(style.columnGap)),
        // The chevron and the icon are on the number's line, inside its box, above the title.
        withNumber: [toggle, icon].every((box) => box.top >= meta.top - 0.5 && box.bottom <= meta.bottom + 0.5 && box.bottom <= title.top + 0.5),
        // How far each glyph's middle is from the number's line's middle, and from the title's.
        toggleOffNumber: round((toggle.top + toggle.bottom) / 2 - (meta.top + meta.bottom) / 2),
        iconOffNumber: round((icon.top + icon.bottom) / 2 - (meta.top + meta.bottom) / 2),
        toggleOffTitle: round((toggle.top + toggle.bottom) / 2 - (title.top + title.bottom) / 2),
        toggleFromInset: round(toggle.left - inset),
        iconFromInset: round(icon.left - inset),
        numberLeft: round(numberBox.left - meta.left),
        titleWidth: round(title.width),
        height: round(r.height),
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
    memberToggle: left(member?.querySelector(".github-pulls-toggle")),
    flatToggle: left(flat?.querySelector(".github-pulls-toggle")),
    stackLabel: left(stackRow?.querySelector(".github-pull-stack-label")),
    flatTitle: left(flat?.querySelector(".github-pulls-title")),
    stackRowHeight: box(stackRow)?.height ?? null,
    rowHeightToken: parseFloat(getComputedStyle(document.documentElement).getPropertyValue("--ui-row-height")),
    treeIndent: parseFloat(getComputedStyle(document.documentElement).getPropertyValue("--tree-indent")),
    countRight: box(stackRow?.querySelector(".github-pulls-stack-count"))?.right ?? null,
    flatAgeRight: box(flat?.querySelector(".github-pulls-age"))?.right ?? null,
    // The toolbar's one line: how far past the pane it reaches, and the room left between
    // the filters and Reload, which sits at the line's end.
    toolbar: (() => {
      const bar = document.getElementById("nav-toolbar-pulls");
      const group = box(document.querySelector(".github-pulls-filters .chip-group"));
      const reload = box(document.querySelector(".github-pulls-reload"));
      const gap = parseFloat(getComputedStyle(document.querySelector(".github-pulls-filters")).columnGap) || 0;
      return {
        width: bar?.clientWidth ?? null,
        overflow: bar === null ? null : bar.scrollWidth - bar.clientWidth,
        spare: group === null || reload === null ? null : Math.round(reload.left - group.right - gap),
        chip: document.querySelector(".github-pulls-group-toggle") !== null,
      };
    })(),
    // A row's leading slots, the chevron's and the icon's, from the row's content edge: a
    // pull request's (#106, first level) and a stack's (mb-hmv7, --tree-icon-slot).
    slots: (() => {
      const round = (value) => Math.round(value * 100) / 100;
      const of = (row, toggle, icon, text) => {
        if (!row) return null;
        const r = row.getBoundingClientRect();
        const style = getComputedStyle(row);
        const inset = r.left + parseFloat(style.borderLeftWidth) + parseFloat(style.paddingLeft);
        const t = row.querySelector(toggle).getBoundingClientRect();
        const i = row.querySelector(icon).getBoundingClientRect();
        const g = row.querySelector(icon + " svg").getBoundingClientRect();
        return {
          toggle: round(t.width),
          toggleFromInset: round(t.left - inset),
          chevron: round(row.querySelector(toggle + " svg").getBoundingClientRect().width),
          icon: round(i.width),
          iconFromInset: round(i.left - inset),
          glyph: round(g.width),
          text: round(row.querySelector(text).getBoundingClientRect().left - inset),
          gap: parseFloat(style.columnGap),
        };
      };
      return {
        token: getComputedStyle(document.documentElement).getPropertyValue("--tree-icon-slot").trim(),
        pull: of(flat, ".github-pulls-toggle", ".github-pull-state-icon", ".github-pulls-title"),
        stack: of(stackRow, ".github-pulls-toggle", ".github-pull-stack-icon", ".github-pull-stack-label"),
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
  const chipCut = window.metabrowser.refChip(branch, { copy: false });
  chipCut.style.maxWidth = "80px";
  const anchors = {
    whole: h("button", { type: "button", "data-tip-text": "Reload" }, ["Reload"]),
    wholeSpaced: h("span", { "data-tip-text": "stack #286" }, ["  Stack   #286 "]),
    cut: h("span", { "data-tip-text": long, style: "display: block; width: 80px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap" }, [long]),
    chipWhole: window.metabrowser.refChip("main", { copy: false }),
    chipCut,
    glyph: h("button", { type: "button", "data-tip-text": "Copy path", "aria-label": "Copy path" }, ["↑"]),
  };
  const host = h("div", { style: "position: fixed; left: 320px; top: 120px; display: flex; flex-direction: column; align-items: flex-start; gap: 4px" }, Object.values(anchors));
  document.body.append(host);
  const label = chipCut.querySelector(".git-ref-label");
  const result = {
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
  const waitFor = async (expression) => {
    try {
      return await chrome.waitFor(expression, STEP_MS);
    } catch (error) {
      const held = await evaluate(
        `[...document.querySelectorAll(".github-pulls-row")].slice(0, 8).map((r) => (r.dataset.stack ? "S" + r.dataset.stack : r.dataset.number) + ":" + r.getAttribute("aria-level")).join(" ") + " | " + (document.querySelector(".github-pulls-list")?.dataset.filter ?? "") + " | " + (document.querySelector(".github-pulls-connection")?.textContent ?? "")`,
      );
      const stacks = await evaluate(`fetch("/api/plugin/github/stacks").then((r) => r.text())`);
      throw new Error(
        `${error.message}\nlist: ${held}\nstacks: ${stacks.slice(0, 600)}\npage errors: ${pageErrors.join("\n")}`,
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
  const focused = () =>
    evaluate(`(() => {
      const el = document.activeElement;
      return el?.dataset?.stack ? "stack " + el.dataset.stack : el?.dataset?.number ? "#" + el.dataset.number : el?.tagName ?? null;
    })()`);
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
    // Open, the default list, paints flat and its stacks arrive after it: at the top of the
    // list, the groups take the top, rather than the first row read keeping its place
    // below them.
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
    await waitFor(
      `document.querySelector(".github-pulls-stack-row .github-pulls-stack-count")?.textContent === "4"`,
    );
    await frames();
    const list = await evaluate(LIST);
    measured.list = list;
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
      JSON.stringify(first?.members.map((m) => m.number)) === "[10,9,8,7]",
      JSON.stringify(first?.members),
    );
    check("with its count", first?.count === "4", first?.count);
    check(
      "#10, in two stacks, sits once, and its badge names the other",
      first?.members[0]?.badge === "4/4 · 300 2/2" &&
        first.members[0].others === 1 &&
        first.members[0].tip === "Stack #286, position 4 of 4; Stack #300, position 2 of 2" &&
        !list.stacks.slice(1).some((s) => s.members.some((m) => m.number === 10)),
      JSON.stringify(list.stacks),
    );
    check(
      "a member's place is on its number's line, before the number, as 1/6 · #455 reads",
      first?.members[0]?.line.startsWith("4/4 · 300 2/2 · #10 · ") &&
        first.members[1]?.line.startsWith("3/4 · #9 · "),
      JSON.stringify(first?.members.map((m) => m.line)),
    );
    check(
      "no pull request's or stack's row, nor any part of one, carries a tooltip",
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
    // The number's line first and the title under it, to the row's end (mb-lkkt): at the
    // default pane a member's title had 170 px, beside its age, and has 208. The chevron and
    // the icon lead the number's line (mb-3cbf): on the title's line their middles sat 19.5 px
    // below its middle, and the title, after them, started in the text column it starts in
    // alone.
    check(
      "a pull request's first line is the chevron, the icon, its number's line, and its age, its second the title alone, from the text column to the row's end",
      [10, 9, 106].every((number) => {
        const row = list.lines[number];
        return (
          row?.firstAbove &&
          row.oneLine &&
          Math.abs(row.metaFromTitle) < 0.5 &&
          Math.abs(row.ageToEnd) < 0.5 &&
          Math.abs(row.titleToEnd) < 0.5 &&
          Math.abs(row.titleFromInset - row.textColumn) < 0.5 &&
          row.withNumber &&
          Math.abs(row.toggleOffNumber) < 0.5 &&
          Math.abs(row.iconOffNumber) < 0.5 &&
          row.toggleFromInset === 0 &&
          row.height === list.titleRoom.flatRow
        );
      }) &&
        list.lines[9].text.startsWith("3/4 · #9 · ") &&
        list.lines[106].text.startsWith("#106 · ") &&
        list.lines[106].numberLeft === 0,
      JSON.stringify(list.lines),
    );
    check(
      "a member's title has a first-level row's room, less its one indent",
      Math.abs(list.titleRoom.member - (list.titleRoom.flat - list.treeIndent)) < 0.5 &&
        Math.abs(list.titleRoom.memberSingle - (list.titleRoom.flat - list.treeIndent)) < 0.5,
      JSON.stringify(list.titleRoom),
    );
    // The leading slots are the tree's one icon slot, 14 px, the Files tree's too: at 16 px
    // a title and a stack's label started 44 px from the row's content edge, and at 14,
    // 40 (mb-hmv7).
    const slots = list.slots;
    check(
      "a row's chevron and icon, and a stack row's, are each the tree's 14 px icon slot",
      slots.token === "14px" &&
        [slots.pull, slots.stack].every(
          (row) =>
            row !== null &&
            row.toggle === 14 &&
            row.toggleFromInset === 0 &&
            row.chevron === 12 &&
            row.glyph === 14 &&
            near(row.iconFromInset, 14 + row.gap) &&
            near(row.text, 2 * 14 + 2 * row.gap),
        ) &&
        slots.pull.icon === 14,
      JSON.stringify(slots),
    );
    check(
      "a stack's row starts on the list's row inset, where a first-level pull request's does",
      near(list.stackToggle, list.flatToggle),
      `${list.stackToggle} ${list.flatToggle}`,
    );
    check(
      "its label starts where a pull request's title does",
      near(list.stackLabel, list.flatTitle),
      `${list.stackLabel} ${list.flatTitle}`,
    );
    check(
      "its pull requests start one tree level in",
      near(list.memberToggle - list.stackToggle, list.treeIndent),
      `${list.memberToggle} ${list.stackToggle} ${list.treeIndent}`,
    );
    check(
      "a stack's row is one row tall",
      near(list.stackRowHeight, list.rowHeightToken),
      `${list.stackRowHeight} ${list.rowHeightToken}`,
    );
    check(
      "its count ends where a row's age does",
      near(list.countRight, list.flatAgeRight),
      `${list.countRight} ${list.flatAgeRight}`,
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
    // A stack's row and a pull request's row hover alike.
    const stackHover = await hover(".github-pulls-stack-row");
    const memberHover = await hover('.github-pulls-item[data-level="2"] > .github-pulls-row');
    const rest = await evaluate(
      `getComputedStyle(document.querySelector('a.github-pulls-row[data-number="106"]')).backgroundColor`,
    );
    measured.hover = { stackHover, memberHover, rest };
    check(
      "a stack's row hovers as a pull request's row does",
      stackHover === memberHover && stackHover !== rest,
      JSON.stringify(measured.hover),
    );
    await send("Input.dispatchMouseEvent", { type: "mouseMoved", x: 1200, y: 880 });
    await shot("after-pulls-grouped", await paneClip());

    // Real keys: onto a stack's row and off it, closing and opening it.
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
        ring: await evaluate(`getComputedStyle(document.activeElement).outlineStyle`),
        place: await stackInView(),
      });
    }
    measured.keys = keys;
    check(
      "J, K, Left and Right move real focus over a stack's row",
      JSON.stringify(keys.map((k) => [k.focus, k.expanded])) ===
        JSON.stringify([
          ["#10", "true"],
          ["stack 286", "true"],
          ["stack 286", "false"],
          ["stack 286", "true"],
          ["#10", "true"],
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
    // A member's changed files: Right opens them a tree level further in; Left closes them
    // and keeps the pull request, and Left again goes to the stack's row.
    await evaluate(`document.querySelector('a.github-pulls-row[data-number="7"]').focus()`);
    await press("ArrowRight");
    await waitFor(
      `document.querySelector('.github-pulls-item[data-number="7"] .github-pull-file-row, .github-pulls-item[data-number="7"] .github-pull-folder-row') !== null`,
    );
    const files = await evaluate(`(() => {
      const member = document.querySelector('a.github-pulls-row[data-number="7"]');
      const file = document.querySelector('.github-pulls-item[data-number="7"] :is(.github-pull-file-row, .github-pull-folder-row)');
      const start = (row) => parseFloat(getComputedStyle(row).paddingLeft) + row.getBoundingClientRect().left;
      // The file row's leading glyph, a folder's chevron or a file's change letter, from the
      // pull request's chevron, which leads its number's line (mb-3cbf).
      const chevron = member.querySelector(".github-pulls-toggle").getBoundingClientRect();
      return {
        expanded: member.getAttribute("aria-expanded"),
        level: file.getAttribute("aria-level"),
        indent: Math.round(start(file) - start(member)),
        fromChevron: Math.round((file.firstElementChild.getBoundingClientRect().left - chevron.left) * 100) / 100,
        belowRow: Math.round((file.getBoundingClientRect().top - member.getBoundingClientRect().bottom) * 100) / 100,
      };
    })()`);
    measured.nestedTip = await evaluate(NESTED_TIP);
    await press("ArrowLeft");
    const afterLeft = await evaluate(
      `[document.querySelector('a.github-pulls-row[data-number="7"]').getAttribute("aria-expanded"), document.activeElement?.dataset?.number ?? null]`,
    );
    await press("ArrowLeft");
    files.afterLeft = afterLeft;
    files.afterSecondLeft = await focused();
    measured.memberFiles = files;
    check(
      "a member's changed files are a tree level further in, and Left closes them, then leaves for its stack",
      files.expanded === "true" &&
        files.level === "3" &&
        files.indent === Math.round(list.treeIndent) &&
        near(files.fromChevron, list.treeIndent) &&
        JSON.stringify(files.afterLeft) === JSON.stringify(["false", "7"]) &&
        files.afterSecondLeft === "stack 286",
      JSON.stringify(files),
    );
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
    // #106 holds every folder open, and its one top-level file is its last row.
    await evaluate(`document.querySelector('a.github-pulls-row[data-number="106"]').focus()`);
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
    await evaluate(`document.querySelector('a.github-pulls-row[data-number="106"]').focus()`);
    await press("ArrowLeft");
    await waitFor(
      `document.querySelector('a.github-pulls-row[data-number="106"]').getAttribute("aria-expanded") === "false"`,
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
          trailing: "github-pulls-reload",
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
      // A member's position, title and number, and a Pulls row's place: their ink.
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
          number: color(".github-pull-stack-menu .github-pull-stack-member-number"),
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
          member: weight(".github-pull-stack-menu .github-pull-stack-member-number"),
          title: weight(".github-pull-title .github-pull-number"),
          position: weight(".github-pull-stack-menu .github-pull-stack-member-position"),
          place: weight(".github-pulls-row .github-pulls-place:not([hidden]) .github-pull-stack-position"),
        };
      })(),
    };
  })()`);
  measured.menu = menu;
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
      "the menu lists the members in the group's order",
      JSON.stringify(menu.members) ===
        JSON.stringify(
          measured.list.stacks.find((s) => s.stack === 286)?.members.map((m) => m.number),
        ),
      JSON.stringify(menu.members),
    );
    check(
      "the trigger's tip names the stack and the place",
      menu.tip === "Stack #286, position 3 of 4",
      menu.tip,
    );
    check(
      "a member's position is in its row's ink, as its title and number are, not a link's",
      menu.ink.position === menu.ink.title &&
        menu.ink.title === menu.ink.number &&
        menu.ink.position === menu.ink.text,
      JSON.stringify(menu.ink),
    );
    check(
      "a pull request's number is bold in a Pulls row, a stack member, and the page's title, as a stack's position is",
      ["row", "member", "title", "position", "place"].every((key) => menu.weights[key] === "700"),
      JSON.stringify(menu.weights),
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
    // it opens puts focus on the current member, #9, the row checked, and Escape gives focus
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
    // highlight's ground and its 2px bar, not the hover ground, hovered, focused, or not
    // (mb-xlla). Focus shows on it as on every member, by the ring.
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
        row: rs === null ? null : { number: row.dataset.number, background: rs.backgroundColor, bar: rs.borderLeftColor, width: rs.borderLeftWidth },
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
    await waitFor(
      `document.querySelectorAll(".github-pull-stacks .github-pull-stack-trigger").length === 2`,
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

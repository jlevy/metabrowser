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
// hover alike and are as tall as the row contract says; that the option's chip is a chip's
// height; that the keys move real focus onto and off a stack row; that the groups list a
// stack's members in the order the page's stack menu does; and that the choice persists
// across a reload. It times the first row, the grouping's arrival, and a toggle, and with
// SHOTS_DIR it saves the screenshots. `--before` takes only the screenshots and the first
// row's time, for the shell as it was before grouping, and checks nothing of it.
//
// Each step writes `phase <name> <ms since start>` to stderr, so a slow run says where.
import fs from "node:fs";
import path from "node:path";
import { launchChrome } from "./chrome-session.mjs";

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
        badge: row.querySelector(".github-pulls-stack")?.textContent ?? "",
        // Another stack named in it, by the Layers glyph before its number.
        others: row.querySelectorAll(".github-pulls-stack .github-pull-stack-other svg").length,
        tip: row.querySelector(".github-pulls-stack")?.getAttribute("aria-label") ?? "",
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
  return {
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
    toggle: (() => {
      const chip = document.querySelector(".github-pulls-group-toggle");
      const filter = document.querySelector(".github-pulls-filters .chip-group");
      return chip === null
        ? null
        : {
            pressed: chip.getAttribute("aria-pressed"),
            disabled: chip.getAttribute("aria-disabled"),
            tip: chip.dataset.tipText,
            height: box(chip).height,
            filterHeight: box(filter).height,
            label: chip.getAttribute("aria-label"),
            word: chip.textContent,
            // The toolbar keeps its controls on one line, and scrolls sideways past that.
            toolbarOverflow: (() => {
              const bar = document.getElementById("nav-toolbar-pulls");
              return bar === null ? null : bar.scrollWidth - bar.clientWidth;
            })(),
            toolbarWidth: document.getElementById("nav-toolbar-pulls")?.clientWidth ?? null,
          };
    })(),
  };
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
    // list draws no groups.
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
    check(
      "the option's chip is on, worded, named Group by stack, and a chip's height",
      list.toggle?.pressed === "true" &&
        list.toggle.disabled === "false" &&
        list.toggle.word === "Stacks" &&
        list.toggle.label === "Group by stack" &&
        near(list.toggle.height, list.toggle.filterHeight),
      JSON.stringify(list.toggle),
    );
    // How far past the pane the toolbar's one line reaches, which it scrolls along rather
    // than wrapping or cutting (static/styles.css, `.nav-toolbar`): recorded, not held.
    measured.toolbarOverflow = list.toggle?.toolbarOverflow ?? null;
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
      return {
        expanded: member.getAttribute("aria-expanded"),
        level: file.getAttribute("aria-level"),
        indent: Math.round(start(file) - start(member)),
      };
    })()`);
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
        JSON.stringify(files.afterLeft) === JSON.stringify(["false", "7"]) &&
        files.afterSecondLeft === "stack 286",
      JSON.stringify(files),
    );
    check(
      "a stack's row takes the focus ring a pull request's row does",
      keys[1].ring === "solid" && keys[0].ring === "solid",
      JSON.stringify(keys),
    );
    // The Group by stack option, off and on.
    const offAt = await now();
    await click(".github-pulls-group-toggle");
    await waitFor(`document.querySelector(".github-pulls-stack-row") === null`);
    measured.toggleOffMs = Math.round((await now()) - offAt);
    await evaluate(`document.querySelector(".tree-content").scrollTop = 0`);
    await shot("after-pulls-flat", await paneClip());
    await send("Page.navigate", { url: `${base}/view/` });
    await waitFor(tabReady);
    await openPulls();
    await waitFor(
      `document.querySelector(".github-pulls-group-toggle")?.getAttribute("aria-disabled") === "false"`,
    );
    await frames();
    check(
      "the choice persists across a reload",
      (await evaluate(`document.querySelector(".github-pulls-stack-row") === null`)) &&
        (await evaluate(
          `document.querySelector(".github-pulls-group-toggle").getAttribute("aria-pressed")`,
        )) === "false",
    );
    await click('.github-pulls-filters [data-chip-value="all"]');
    await waitFor(
      `document.querySelector('.github-pulls-list[data-filter="all"] a.github-pulls-row') !== null`,
    );
    const onAt = await now();
    await click(".github-pulls-group-toggle");
    await waitFor(`document.querySelector(".github-pulls-stack-row") !== null`);
    measured.toggleOnMs = Math.round((await now()) - onAt);
    await frames();
    measured.toggledInView = await stackInView();
    check(
      "turning grouping on at the top shows its first stack's row",
      measured.toggledInView.inView,
      JSON.stringify(measured.toggledInView),
    );
    phase("toggled");
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
    `[...document.querySelectorAll(".github-pull-stack-trigger:not(.github-pull-stack-strut)")].some((t) => t.getAttribute("aria-label").includes("Stack #286"))`,
  );
  phase("page");
  await evaluate(
    `[...document.querySelectorAll(".github-pull-stack-trigger:not(.github-pull-stack-strut)")].find((t) => t.getAttribute("aria-label").includes("Stack #286")).click()`,
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
      // A member's position, title and number, and a Pulls badge's position: their ink.
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
          badge: color(".github-pulls-row .github-pulls-stack:not([hidden]) .github-pull-stack-position"),
          text,
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
  }
  await shot(before ? "before-window" : "after-window");
  phase("menu");
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

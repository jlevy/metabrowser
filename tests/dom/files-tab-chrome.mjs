// The Files tab's filter menus, laid out by a real engine: a served folder with many file
// types, the shell's own page, and headless Chrome.
//
//   CHROME_BIN=/path/to/chrome CHROME_PROFILES=/dir/the/caller/removes \
//     node tests/dom/files-tab-chrome.mjs METAB ROOT PORT STATE_DIR
//
// tests/test_files_tab_chrome.py writes the folder, owns the profile and STATE_DIR, runs
// this in a process group of its own, which Chrome and the server join, and judges what it
// prints: one JSON line of measurements.
//
// What it measures is layout, which no browserless DOM computes: where a menu's group
// heading starts against its rows, how tall an open menu is drawn against its rows and
// the window, which controls the bar's row and closed drawer hold and the lines the open
// drawer lays them on, whether the row fits its pane, how it wraps in a narrower one, and
// which take keyboard numbers, where a Group by section's heading starts against its tree
// and where its tally sits beside its name, at the default pane and the narrowest, whether a name cut short there shows its
// tooltip, and what Chrome names the section, whether a refresh after a write keeps the
// scroll position and the focused row, what a Group by choice shows while its request is
// held, and a tree row's leading slot, a folder's chevron and a file's icon, against the
// name after it (docs/design-system.md, "Groups in a Menu", "Heading Tallies", "Tooltips
// Add Information", "Menu Height", "Grouping the Files Tree", "One Glyph Size", and
// "Navigation Toolbars Wrap"). The wrap is held to its rule by
// tests/dom/nav-toolbar-wrap.mjs. The requests and sections themselves run browserlessly
// in tests/dom/files-group-by-session.js. The pure rule, `menuMaxHeight`, is checked
// without a browser in tests/dom/filter-controls-behavior.js.
import { spawn } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { launchChrome } from "./chrome-session.mjs";
import { judge, linesOf, NARROWEST, SWEEP, WIDTHS } from "./nav-toolbar-wrap.mjs";

const [metab, root, port, state] = process.argv.slice(2);
const base = `http://127.0.0.1:${port}`;
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
const started = Date.now();
const phase = (name) => process.stderr.write(`phase ${name} ${Date.now() - started}\n`);

// The two windows: one with room for a full menu under the filter row, and one short enough
// that the room, not the row cap, sets the type menu's height. Chrome's viewport, which is
// what the page sees, is set directly so the numbers do not depend on window chrome.
const TALL = { width: 1280, height: 900 };
const SHORT = { width: 1280, height: 420 };

async function serve() {
  const server = spawn(
    metab,
    [
      root,
      "--no-open",
      "--port",
      port,
      "--cache-dir",
      path.join(state, "cache"),
      "--config-dir",
      path.join(state, "config"),
    ],
    {
      stdio: ["ignore", "pipe", "pipe"],
      env: { ...process.env, METABROWSER_LOG_LEVEL: "WARNING" },
    },
  );
  const exited = new Promise((resolve) => server.once("exit", resolve));
  let output = "";
  await new Promise((resolve, reject) => {
    const bound = setTimeout(() => reject(new Error(`no server: ${output}`)), 30000);
    const read = (chunk) => {
      output += chunk;
      if (output.includes("Serving ") && output.includes(base)) {
        clearTimeout(bound);
        resolve();
      }
    };
    server.stdout.on("data", read);
    server.stderr.on("data", read);
    server.once("exit", () => reject(new Error(`server exited: ${output}`)));
  });
  return {
    async stop() {
      server.kill("SIGTERM");
      await Promise.race([exited, sleep(20000)]);
      if (server.exitCode === null) {
        server.kill("SIGKILL");
        await exited;
      }
    },
  };
}

// In the page: an open menu's box, its rows, and where its headings' text starts.
const MEASURE = `(key) => {
  const wrap = document.querySelector('.chip-menu[data-chip-menu="' + key + '"]');
  const panel = wrap && wrap.querySelector(".chip-menu-panel");
  if (!panel || wrap.getAttribute("aria-expanded") !== "true") return null;
  const round = (value) => Math.round(value * 100) / 100;
  const box = panel.getBoundingClientRect();
  const style = getComputedStyle(panel);
  const textLeft = (element) => {
    const walker = document.createTreeWalker(element, NodeFilter.SHOW_TEXT);
    for (let node = walker.nextNode(); node; node = walker.nextNode()) {
      if (node.textContent.trim()) {
        const range = document.createRange();
        range.selectNodeContents(node);
        return range.getBoundingClientRect().left;
      }
    }
    return null;
  };
  const rows = [...panel.querySelectorAll(".menu-item")];
  const first = rows[0];
  const firstBox = first.getBoundingClientRect();
  const rowInset = firstBox.left + parseFloat(getComputedStyle(first).paddingLeft);
  // A category's heading leads with its icon (docs/design-system.md, "File-Type Category
  // Icons"): the icon starts on the inset, in the heading's ink, and the name follows it.
  const iconOf = (heading) => {
    const icon = heading.querySelector(":scope > .category-icon");
    if (!icon) return null;
    const iconBox = icon.getBoundingClientRect();
    const ink = getComputedStyle(heading).color;
    return {
      width: round(iconBox.width),
      height: round(iconBox.height),
      textFromIcon: round(textLeft(heading) - iconBox.right),
      inHeadingInk: getComputedStyle(icon).color === ink && getComputedStyle(icon).stroke === ink,
    };
  };
  const headings = [...panel.querySelectorAll(".group-heading")].map((heading) => {
    const group = heading.parentElement;
    const icon = heading.querySelector(":scope > .category-icon");
    return {
      text: heading.textContent,
      // The heading's lead, its icon where it has one, else its name.
      fromRowInset: round((icon ? icon.getBoundingClientRect().left : textLeft(heading)) - rowInset),
      icon: iconOf(heading),
      namesItsGroup:
        group.classList.contains("menu-group") &&
        group.getAttribute("role") === "group" &&
        group.getAttribute("aria-labelledby") === heading.id &&
        group.firstElementChild === heading &&
        group.querySelectorAll(".menu-item").length > 0,
      // The group's divider: its own top border, a rule the menu's separator draws.
      divider: round(parseFloat(getComputedStyle(group).borderTopWidth)),
    };
  });
  return {
    windowHeight: window.innerHeight,
    top: round(box.top),
    bottom: round(box.bottom),
    height: round(box.height),
    scrollHeight: panel.scrollHeight,
    clientHeight: panel.clientHeight,
    frame: round(
      parseFloat(style.paddingTop) + parseFloat(style.paddingBottom) +
        parseFloat(style.borderTopWidth) + parseFloat(style.borderBottomWidth),
    ),
    rowHeights: [...new Set(rows.map((row) => round(row.getBoundingClientRect().height)))],
    rows: rows.length,
    labelFromRowInset: round(textLeft(first.querySelector(".menu-item-label")) - rowInset),
    // The rule between the groups and the raw rows, whose 1px a scrolling menu keeps.
    separators: [...panel.querySelectorAll(":scope > .menu-separator")].map((rule) =>
      round(rule.getBoundingClientRect().height),
    ),
    headings,
    // The glyph size and the gap from icon to name, which a category's heading takes.
    glyph: round(parseFloat(getComputedStyle(document.documentElement).getPropertyValue("--icon-glyph"))),
    categoryIconGap: round(
      parseFloat(getComputedStyle(document.documentElement).getPropertyValue("--category-icon-gap")),
    ),
  };
}`;

// A tree row's leading slot: a folder's chevron and a file's type icon, at one depth, each
// in its box from the row's content edge, and where the name after it starts. The box is
// `--tree-icon-slot` wide (styles.css, mb-hmv7); a folder's chevron is its toggle's margin
// box, as a container row's is.
const SLOTS = `(() => {
  const round = (value) => Math.round(value * 100) / 100;
  const tree = document.querySelector('#tab-files [role="tree"]');
  const measure = (row, slot) => {
    const box = row.getBoundingClientRect();
    const style = getComputedStyle(row);
    const inset = box.left + parseFloat(style.borderLeftWidth) + parseFloat(style.paddingLeft);
    const r = slot.getBoundingClientRect();
    const s = getComputedStyle(slot);
    const glyph = slot.querySelector("svg").getBoundingClientRect();
    const left = r.left - parseFloat(s.marginLeft);
    return {
      slot: round(r.width + parseFloat(s.marginLeft) + parseFloat(s.marginRight)),
      fromInset: round(left - inset),
      glyph: round(glyph.width),
      glyphFromSlot: round(glyph.left - left),
      name: round(row.querySelector(".tree-item-name").getBoundingClientRect().left - inset),
      gap: parseFloat(style.columnGap),
    };
  };
  const folder = tree.querySelector('.tree-folder[data-path="src"]');
  const file = tree.querySelector('.tree-file[data-path="README.md"]');
  return {
    token: getComputedStyle(document.documentElement).getPropertyValue("--tree-icon-slot").trim(),
    folder: measure(folder, folder.querySelector(":scope > .tree-toggle")),
    file: measure(file, file.querySelector(":scope > .tree-item-icon")),
  };
})()`;

// The page's one tooltip, waited on rather than slept for: a tooltip appears on a 300 ms
// timer (TOOLTIP_APPEAR_DELAY) and goes on a 150 ms one, and a fixed sleep only guesses at
// either. `until` polls a condition up to a bound and returns whether it held. A read
// leaves focus where a choice from a menu left it, in the filter bar: the bar, rebuilt
// when the tree's tallies answer, puts focus back on the menu's trigger, which on a loaded
// runner lands inside the delay, and that repair leaves the tooltip (TIP_REPAINTS, mb-alff).
const TIP_WAITS = `
  const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
  const until = async (test, ms) => {
    const end = performance.now() + ms;
    while (performance.now() < end) {
      if (test()) return true;
      await wait(20);
    }
    return test();
  };
  const tipShown = () => document.querySelector(".custom-tooltip")?.style.display === "block";
`;

// A tree row's tooltip, once it shows: what it holds, and what the row's chip shows. It
// leaves out what the row shows and gives the exact date, and the exact size behind one its
// chip rounds (mb-8mpo, mb-qg4z, docs/design-system.md, "Tooltips Add Information").
const TREE_TIPS = `(async () => {
  ${TIP_WAITS}
  const tree = document.querySelector('#tab-files [role="tree"]');
  // A focus change during a read, kept beside the readings for a failure's message.
  const focused = [];
  const onFocus = (event) =>
    focused.push([event.target?.tagName, event.target?.className, event.target?.dataset?.treeId ?? ""].join(" ").trim());
  document.addEventListener("focusin", onFocus, true);
  const read = async (row) => {
    await until(() => !tipShown(), 5000);
    focused.length = 0;
    const entered = performance.now();
    row.dispatchEvent(new MouseEvent("mouseenter"));
    await until(tipShown, 5000);
    const tip = document.querySelector(".custom-tooltip");
    const chip = row.querySelector(".tree-item-size");
    const shown = {
      chip: chip === null ? null : chip.classList.contains("count") ? "count" : "size",
      chipText: chip?.textContent ?? null,
      visible: tipShown(),
      size: tip?.querySelector(".size") !== null,
      // The size's digits, which the locale groups as it likes.
      sizeDigits: tip?.querySelector(".size")?.textContent.replace(/\\D/g, "") ?? null,
      count: tip?.querySelector(".count") !== null,
      lines: tip === null ? 0 : tip.querySelectorAll(".tip-detail").length,
      name: tip?.querySelector(".tip-name") !== null,
    };
    const why = { ms: Math.round(performance.now() - entered), connected: row.isConnected, focused: [...focused] };
    row.dispatchEvent(new MouseEvent("mouseleave"));
    await until(() => !tipShown(), 5000);
    return [shown, why];
  };
  const [file, fileWhy] = await read(tree.querySelector('.tree-file[data-path="README.md"]'));
  const [folder, folderWhy] = await read(tree.querySelector('.tree-folder[data-path="src"]'));
  document.removeEventListener("focusin", onFocus, true);
  return { file, folder, why: { file: fileWhy, folder: folderWhy } };
})()`;

// A tree row's tooltip while something else on the page repaints, under a pointer that has
// not moved: it stays, or still appears (mb-alff, docs/design-system.md, "A Surface Puts
// Away Only Its Own Tooltip" and "Tooltip Input Modality"). With the row's tooltip up, the
// folder view's totals draw again, as they do when the folder's sums arrive: the shell
// announces that anything may have changed, as it does when the scan completes, and the
// totals' rollup answers again. Then, during the row's appear delay, the filter bar
// rebuilds with focus on its Group by trigger, as it does when new tallies arrive, and
// puts focus back on the rebuilt trigger. Focus moving on from there, to a tree row, does
// put the tooltip away. The totals' draw and the bar's rebuild each used to put the
// row's tooltip away, and their race against its delay was this test's flake.
const TIP_REPAINTS = `(async () => {
  ${TIP_WAITS}
  const tip = () => document.querySelector(".custom-tooltip");
  const tree = document.querySelector('#tab-files [role="tree"]');
  const readme = () => tree.querySelector('.tree-file[data-path="README.md"]');

  let row = readme();
  row.dispatchEvent(new MouseEvent("mouseenter"));
  await until(tipShown, 5000);
  const up = tipShown();
  let drawn = 0;
  const totalsRoot = document.querySelector(".folder-totals");
  const observer = new MutationObserver((records) => {
    drawn += records.length;
  });
  if (totalsRoot) {
    observer.observe(totalsRoot, { attributes: true, characterData: true, childList: true, subtree: true });
  }
  window.dispatchEvent(
    new CustomEvent("metabrowser:inventory-change", { detail: { kind: "snapshot", paths: null } }),
  );
  // The totals' rollup is asked again after a debounce, so its answer gets a longer bound.
  await until(() => drawn > 0, 10000);
  observer.disconnect();
  // Longer than the fade a hide starts, so a tooltip put away is gone by the read.
  await wait(2 * TOOLTIP_FADE_OUT);
  const totals = {
    up,
    drawn: drawn > 0,
    stayed: tipShown() && tip().classList.contains("visible"),
  };
  row.dispatchEvent(new MouseEvent("mouseleave"));
  await until(() => !tipShown(), 5000);

  const trigger = document.querySelector('[data-chip-menu-toggle="group"]');
  trigger.focus({ preventScroll: true });
  row = readme();
  row.dispatchEvent(new MouseEvent("mouseenter"));
  renderNavFilterBar();
  const after = document.activeElement;
  const refocused =
    trigger.isConnected === false && after !== trigger && after?.dataset?.chipMenuToggle === "group";
  await until(tipShown, 5000);
  const bar = { refocused, shown: tipShown() };
  tree.querySelector('.tree-folder[data-path="src"]').focus({ preventScroll: true });
  await until(() => !tipShown(), 5000);
  bar.focusMovedOn = !tipShown();
  row.dispatchEvent(new MouseEvent("mouseleave"));
  return { totals, bar };
})()`;

// The bar's row and drawer: which controls each holds.
const ROW = `(() => ({
  row: [...document.querySelector(".nav-filter-bar-main").children].map((child) =>
    child.matches(".chip-menu") ? "menu:" + child.dataset.chipMenu : child.className),
  drawer: [...document.querySelectorAll("#filter-drawer [data-chip-menu-toggle], #filter-drawer [data-chip-check]")]
    .map((control) => control.dataset.chipMenuToggle || control.dataset.chipCheck),
  drawerOpen: document.getElementById("filter-drawer").dataset.open,
  drawerInert: document.getElementById("filter-drawer").inert,
}))()`;

// Whether the row fits its pane: Group by's trigger at its natural width, the room to
// spare before Clear and the chevron, any count badge, and the chevron's name, which
// carries the count. `spare` is the space
// between Group by and the trailing span beyond the row's gap, less how far that span
// runs past the row's edge: positive when the row fits with room left, negative by the
// overflow when it does not (the span's auto margin is 0 then, so the space alone cannot
// say).
const ROW_FIT = `(() => {
  const row = document.querySelector(".nav-filter-bar-main");
  const trigger = row.querySelector('[data-chip-menu-toggle="group"]');
  const group = row.querySelector('.chip-menu[data-chip-menu="group"]');
  const end = row.querySelector(".nav-filter-bar-end");
  const round = (value) => Math.round(value * 100) / 100;
  const rowBox = row.getBoundingClientRect();
  const endBox = end.getBoundingClientRect();
  const gap = parseFloat(getComputedStyle(row).columnGap);
  const overflow = Math.max(0, endBox.right - rowBox.right);
  return {
    trigger: trigger.textContent.trim(),
    pane: round(document.getElementById("nav-filter-bar").getBoundingClientRect().width),
    row: row.clientWidth,
    content: row.scrollWidth,
    spare: round(endBox.left - group.getBoundingClientRect().right - gap - overflow),
    triggerClipped: trigger.scrollWidth > trigger.clientWidth,
    clear: Boolean(end.querySelector("[data-chip-clear]")),
    badge: end.querySelector(".chip-badge")?.textContent.trim() || null,
    name: end.querySelector(".filter-drawer-toggle")?.getAttribute("aria-label") ?? null,
  };
})()`;

// The filter row's wrap: the bar, its row, and the toolbar's spacing tokens.
const ROW_WRAP = {
  bar: "#nav-filter-bar",
  row: "#nav-filter-bar .nav-filter-bar-main",
  tokens: { gap: "var(--nav-toolbar-gap)", line: "var(--nav-toolbar-line-height)" },
};

// In a narrow pane, wrapped: whether reading the row's lines meets its controls in their
// Tab order, and the bar's height with the drawer as it is.
const NARROW = `(() => {
  const bar = document.getElementById("nav-filter-bar");
  const row = bar.querySelector(".nav-filter-bar-main");
  const stops = [...row.querySelectorAll("button, input")].filter(
    (el) => el.tabIndex >= 0 && el.getClientRects().length > 0 && !el.closest("[inert]"),
  );
  const at = stops.map((el, index) => {
    const box = el.getBoundingClientRect();
    return { index, middle: Math.round(box.top + box.height / 2), left: box.left };
  });
  const read = [...at].sort((a, b) => a.middle - b.middle || a.left - b.left);
  return {
    stops: stops.map((el) => el.dataset.chipMenuToggle || el.dataset.chipCheck || el.dataset.chipKey || (el.matches("[data-chip-clear]") ? "clear" : el.tagName)),
    lines: new Set(at.map((stop) => stop.middle)).size,
    readInTabOrder: read.every((stop, index) => stop.index === index),
    height: Math.round(bar.getBoundingClientRect().height * 100) / 100,
  };
})()`;

// The open drawer's line: its controls in order, the lines they take, and whether each is
// whole inside the bar, Show ignored's checkbox among them, one line tall and centred in
// it as the toolbar row's controls are (docs/design-system.md, "Navigation Toolbars Wrap").
const DRAWER = `(() => {
  const bar = document.getElementById("nav-filter-bar");
  const drawerRow = bar.querySelector(".filter-drawer-row");
  const barBox = bar.getBoundingClientRect();
  const round = (value) => Math.round(value * 100) / 100;
  const controls = [...drawerRow.children].map((child) => {
    const box = child.getBoundingClientRect();
    return {
      name: child.matches(".chip-menu")
        ? "menu:" + child.dataset.chipMenu
        : child.matches(".filter-check")
          ? "check:" + child.querySelector("[data-chip-check]").dataset.chipCheck
          : child.className,
      top: round(box.top),
      height: round(box.height),
      middle: round(box.top + box.height / 2),
      inside: box.left >= barBox.left - 0.5 && box.right <= barBox.right + 0.5,
      clipped: child.scrollWidth > child.clientWidth,
    };
  });
  return {
    controls,
    lines: new Set(controls.map((control) => control.top)).size,
    content: drawerRow.scrollWidth,
    width: drawerRow.clientWidth,
  };
})()`;

// Which filter menu is open, and whether the drawer is.
const OPEN_MENU = `({
  menu: document.querySelector('.chip-menu[aria-expanded="true"]')?.dataset.chipMenu ?? null,
  drawerOpen: document.getElementById("filter-drawer").dataset.open,
})`;

// Each Group by section: its heading against its rows, how the heading names it, and
// where its tally sits: beside the name, after the separator, on the heading's one line
// (docs/design-system.md, "Heading Tallies").
const SECTIONS = `[...document.querySelectorAll(".tree-section")].map((section) => {
  const round = (value) => Math.round(value * 100) / 100;
  const heading = section.querySelector(":scope > .tree-section-heading");
  const label = heading.querySelector(".tree-section-label");
  const icon = heading.querySelector(":scope > .category-icon");
  const range = document.createRange();
  range.selectNodeContents(label);
  const row = section.querySelector(".tree-item");
  const box = row.getBoundingClientRect();
  const style = getComputedStyle(row);
  const tree = section.querySelector(":scope > [role='tree']");
  const tally = heading.querySelector(":scope > .heading-tally");
  const figure = tally.querySelector(".heading-tally-figure");
  const dot = tally.querySelector(".heading-tally-dot");
  const headingBox = heading.getBoundingClientRect();
  const headingStyle = getComputedStyle(heading);
  const tallyBox = tally.getBoundingClientRect();
  const labelBox = label.getBoundingClientRect();
  const lineTops = new Set(
    [...range.getClientRects(), tallyBox].map((rect) => Math.round(rect.top)),
  );
  return {
    key: section.dataset.treeGroup,
    label: label.textContent,
    tally: tally.textContent,
    // The tally starts where the name's box ends.
    tallyFromLabel: round(tallyBox.left - labelBox.right),
    // And its dot stands one space's advance after the name: the tally keeps its spaces
    // (white-space: pre), which a flex heading would otherwise drop.
    dotFromLabel: round(dot.getBoundingClientRect().left - labelBox.right),
    // And it does not reach for the far end: the room left after it.
    tallyToEnd: round(headingBox.right - parseFloat(headingStyle.paddingRight) - tallyBox.right),
    // The name and the tally share one line, and the heading is that line.
    lines: lineTops.size,
    headingHeight: round(headingBox.height),
    nameCut: label.scrollWidth > label.clientWidth,
    tallyWhole: tally.scrollWidth <= tally.clientWidth + 0.5 &&
      tallyBox.right <= headingBox.right - parseFloat(headingStyle.paddingRight) + 0.5,
    weights: {
      label: getComputedStyle(label).fontWeight,
      tally: getComputedStyle(tally).fontWeight,
      figure: getComputedStyle(figure).fontWeight,
    },
    numeralWeight: getComputedStyle(document.documentElement).getPropertyValue("--count-numeral-weight").trim(),
    dotHidden: dot.getAttribute("aria-hidden") === "true",
    headingClasses: [...heading.classList],
    // The heading's lead, its category icon, starts on the tree's row inset, and the name
    // follows it by the gap, in the heading's ink (docs/design-system.md, "File-Type
    // Category Icons").
    fromRowInset: round(((icon ? icon.getBoundingClientRect().left : range.getBoundingClientRect().left) -
      box.left - parseFloat(style.borderLeftWidth) - parseFloat(style.paddingLeft))),
    icon: icon
      ? {
          width: round(icon.getBoundingClientRect().width),
          height: round(icon.getBoundingClientRect().height),
          textFromIcon: round(range.getBoundingClientRect().left - icon.getBoundingClientRect().right),
          inHeadingInk:
            getComputedStyle(icon).color === headingStyle.color &&
            getComputedStyle(icon).stroke === headingStyle.color,
        }
      : null,
    namesItsTree: section.getAttribute("aria-labelledby") === heading.id &&
      tree?.getAttribute("aria-labelledby") === heading.id,
    divider: parseFloat(getComputedStyle(section).borderTopWidth),
  };
})`;

// A section name's tooltip at the narrowest pane: shown while the name is cut short, with
// the whole name, and not while it is whole, since it would only repeat it
// (docs/design-system.md, "Tooltips Add Information"). Documentation's name, the longest,
// is cut by its tally set to a 10,004-file group's, a size that cuts it at 180 px; Code's
// short name stays whole. The tally is put back after.
const SECTION_TIPS = `(async () => {
  ${TIP_WAITS}
  const heading = (key) =>
    document.querySelector('.tree-section[data-tree-group="' + key + '"] > .tree-section-heading');
  const read = async (key, expectShown) => {
    const label = heading(key).querySelector(".tree-section-label");
    await until(() => !tipShown(), 5000);
    label.dispatchEvent(new MouseEvent("mouseenter"));
    // A tooltip that should show is waited for; one that should not is given well past
    // its delay to appear.
    const visible = expectShown ? await until(tipShown, 5000) : (await wait(900), tipShown());
    const found = {
      cut: label.scrollWidth > label.clientWidth,
      visible,
      text: visible ? document.querySelector(".custom-tooltip").textContent : null,
    };
    label.dispatchEvent(new MouseEvent("mouseleave"));
    await until(() => !tipShown(), 5000);
    return found;
  };
  const figure = heading("type:docs").querySelector(".heading-tally-figure");
  const was = figure.textContent;
  figure.textContent = (10004).toLocaleString();
  await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
  const cut = await read("type:docs", true);
  figure.textContent = was;
  const whole = await read("type:code", false);
  return { cut, whole };
})()`;

// The gear menu: where its title, its labelled row, and its foot start, against the menu.
const GEAR = `(() => {
  const menu = document.querySelector("#settings-control .settings-menu");
  const left = (element) => {
    const walker = document.createTreeWalker(element, NodeFilter.SHOW_TEXT);
    for (let node = walker.nextNode(); node; node = walker.nextNode()) {
      if (node.textContent.trim()) {
        const range = document.createRange();
        range.selectNodeContents(node);
        return Math.round((range.getBoundingClientRect().left - menu.getBoundingClientRect().left) * 100) / 100;
      }
    }
    return null;
  };
  return {
    title: left(menu.querySelector(".menu-title")),
    labelledRow: left(menu.querySelector(".menu-row")),
    foot: left(menu.querySelector(".menu-version")),
  };
})()`;

const frames =
  "new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(() => resolve(true))))";

// The bar's transitions run to their end, the drawer's grid track and the bar's row-gap
// on --transition-fast among them. `getAnimations` brings style up to date first, so a
// transition the last change started is among them.
const BAR_SETTLED = `(async () => {
  const bar = document.getElementById("nav-filter-bar");
  const running = () =>
    bar.getAnimations({ subtree: true }).filter((animation) => animation instanceof CSSTransition);
  for (let now = running(); now.length > 0; now = running()) {
    await Promise.all(now.map((animation) => animation.finished.catch(() => null)));
  }
  return true;
})()`;

const profiles = process.env.CHROME_PROFILES;
if (!process.env.CHROME_BIN || !profiles) {
  throw new Error("CHROME_BIN and CHROME_PROFILES are required");
}
const server = await serve();
phase("served");
/** @type {Awaited<ReturnType<typeof launchChrome>> | null} */
let chrome = null;
try {
  chrome = await launchChrome(process.env.CHROME_BIN, { profiles });
  phase("chrome");
  const browser = chrome;
  const viewport = (size) =>
    browser.send("Emulation.setDeviceMetricsOverride", {
      ...size,
      deviceScaleFactor: 1,
      mobile: false,
    });
  /** Click a menu's trigger and wait until it reports the state asked for. */
  const toggle = async (key, open) => {
    await browser.evaluate(
      `document.querySelector('[data-chip-menu-toggle="${key}"]').click(), true`,
    );
    await browser.waitFor(
      `document.querySelector('.chip-menu[data-chip-menu="${key}"]')?.getAttribute("aria-expanded") === "${open}"`,
    );
    await browser.evaluate(frames);
  };
  const measure = (key) => browser.evaluate(`(${MEASURE})(${JSON.stringify(key)})`);
  /** Press one key, as the reader does, at the page. */
  /** @type {Record<string, number>} */
  const NAMED_KEYS = { Enter: 13, Escape: 27, ArrowLeft: 37, ArrowDown: 40, ArrowRight: 39 };
  const press = async (key) => {
    const named = key in NAMED_KEYS;
    const letter = /^[a-z]$/.test(key);
    const code = named ? key : letter ? `Key${key.toUpperCase()}` : `Digit${key}`;
    const windowsVirtualKeyCode = named ? NAMED_KEYS[key] : key.toUpperCase().charCodeAt(0);
    await browser.send("Input.dispatchKeyEvent", {
      type: "keyDown",
      key,
      code,
      windowsVirtualKeyCode,
      ...(key === "Enter" ? { text: "\r" } : named ? {} : { text: key }),
    });
    await browser.send("Input.dispatchKeyEvent", {
      type: "keyUp",
      key,
      code,
      windowsVirtualKeyCode,
    });
    await browser.evaluate(frames);
  };

  await viewport(TALL);
  await browser.send("Page.enable");
  await browser.send("Page.navigate", { url: `${base}/view/` });
  // The type menu lists the folder's extensions once the tree's tally arrives.
  await browser.waitFor(
    `document.querySelectorAll('.chip-menu[data-chip-menu="types"] .chip-menu-item').length > 30`,
    30000,
  );
  await browser.evaluate("document.fonts.ready.then(() => true)");
  phase("loaded");
  // The gear menu's lines start on one inset.
  await browser.evaluate(`document.getElementById("settings-btn").click(), true`);
  await browser.waitFor(
    `document.getElementById("settings-control").getAttribute("aria-expanded") === "true"`,
  );
  await browser.evaluate(frames);
  const gear = await browser.evaluate(GEAR);
  await browser.evaluate(`document.getElementById("settings-btn").click(), true`);
  await browser.waitFor(
    `document.getElementById("settings-control").getAttribute("aria-expanded") === "false"`,
  );

  const result = { gear };
  // Group by is the row; the three filters and Show ignored wait in the closed drawer.
  result.row = await browser.evaluate(ROW);
  // The row at its widest: a filter set, so Clear shows, under each Group by value. Then
  // Show ignored off alone: Clear shows, and the chevron's name counts it.
  const setFilters = async (patch) => {
    await browser.evaluate(`window.metabrowser.filterState.set(${JSON.stringify(patch)}), true`);
    await browser.evaluate(frames);
  };
  await setFilters({ size: "1m" });
  result.rowFit = {};
  for (const group of ["none", "age", "type"]) {
    await setFilters({ group });
    result.rowFit[group] = await browser.evaluate(ROW_FIT);
  }
  // The row wraps in a pane too narrow for it: every width from the narrowest to well past
  // the default, in both font sets, with no filter set and with one set under each Group by
  // value. The drawer is closed, so the bar is the row's lines and nothing more.
  const font = async (name) => {
    await browser.evaluate(
      `document.documentElement.setAttribute("data-app-font", ${JSON.stringify(name)}), true`,
    );
    await browser.evaluate("document.fonts.ready.then(() => true)");
    await browser.evaluate(frames);
  };
  const sweep = () =>
    browser.evaluate(`(${SWEEP})(${JSON.stringify({ widths: WIDTHS, ...ROW_WRAP })})`);
  result.wrap = {};
  for (const set of ["clean", "system"]) {
    await font(set);
    for (const [state, patch] of [
      ["no filter", { size: "all", group: "none" }],
      ["No grouping", { size: "1m", group: "none" }],
      ["By age", { size: "1m", group: "age" }],
      ["By file type", { size: "1m", group: "type" }],
    ]) {
      await setFilters(patch);
      const measured = await sweep();
      const { gap, line } = measured.tokens;
      const verdict = judge(`${state}, ${set} fonts`, measured, {
        pad: gap,
        line,
        gap,
        column: gap,
        trailing: "nav-filter-bar-end",
      });
      const narrowest = measured.rows.find((row) => row.width === NARROWEST);
      result.wrap[`${state}, ${set}`] = {
        ...verdict,
        tokens: measured.tokens,
        narrowest: linesOf(narrowest).map((wrapped) => wrapped.units.map((unit) => unit.name)),
      };
    }
  }
  await font("clean");
  // The themes lay the row out alike.
  await setFilters({ size: "1m", group: "none" });
  const light = await sweep();
  await browser.evaluate(`document.documentElement.setAttribute("data-theme", "dark"), true`);
  await browser.evaluate(frames);
  const dark = await sweep();
  await browser.evaluate(`document.documentElement.setAttribute("data-theme", "light"), true`);
  await browser.evaluate(frames);
  result.themesAlike = JSON.stringify(light) === JSON.stringify(dark);
  phase("wrapped");
  // At the narrowest pane, with a filter set, the row is two lines. Reading them meets
  // the controls in their Tab order, the keyboard numbers still open Group by and the
  // drawer's filters, and the drawer opens under the lines and closes back to them with no
  // gap left standing.
  const paneWidth = (width) =>
    browser.evaluate(
      `(() => { const pane = document.querySelector(".tree-pane"); pane.style.width = ${JSON.stringify(width ? `${width + 1}px` : "")}; return true; })()`,
    );
  await paneWidth(NARROWEST);
  await browser.evaluate(frames);
  result.narrow = await browser.evaluate(NARROW);
  await press("2");
  result.narrowGroupKey = await browser.evaluate(OPEN_MENU);
  await press("Escape");
  await browser.waitFor(`!document.querySelector('.chip-menu[aria-expanded="true"]')`);
  await press("4");
  await browser.waitFor(`document.getElementById("filter-drawer").dataset.open === "true"`);
  await browser.evaluate(BAR_SETTLED);
  result.narrowTypesKey = await browser.evaluate(OPEN_MENU);
  await press("Escape");
  await browser.waitFor(`!document.querySelector('.chip-menu[aria-expanded="true"]')`);
  result.narrowOpen = await browser.evaluate(NARROW);
  result.narrowDrawer = await browser.evaluate(DRAWER);
  const drawerToggle = async (open) => {
    await browser.evaluate(`document.querySelector('[data-chip-key="drawer"]').click(), true`);
    await browser.waitFor(`document.getElementById("filter-drawer").dataset.open === "${open}"`);
    await browser.evaluate(BAR_SETTLED);
  };
  await drawerToggle(false);
  result.narrowClosed = await browser.evaluate(NARROW);
  await paneWidth(null);
  await browser.evaluate(frames);
  // At the default pane the open drawer holds its three filters and Show ignored.
  await drawerToggle(true);
  result.drawer = await browser.evaluate(DRAWER);
  await drawerToggle(false);
  phase("narrow");

  await setFilters({ size: "all", group: "none", showIgnored: false });
  result.ignoredOff = await browser.evaluate(ROW_FIT);
  await setFilters({ showIgnored: true });
  await browser.waitFor("document.querySelectorAll('.tree-section').length === 0", 30000);
  await browser.waitFor(
    `document.querySelectorAll('.chip-menu[data-chip-menu="types"] .chip-menu-item').length > 30`,
    30000,
  );
  await browser.evaluate(frames);
  // The numbers: 1 is the navigation's Refresh, 2 is Group by, and the drawer's filters
  // keep theirs while it is closed,
  // on stand-ins beside the chevron.
  // Where focus is: a menu row by its menu, label, and whether it is checked, or a trigger.
  const FOCUS = `(() => {
    const active = document.activeElement;
    if (!active || active === document.body) return "body";
    const trigger = active.getAttribute("data-chip-menu-toggle");
    if (trigger) return trigger + " trigger";
    const row = active.closest(".chip-menu-item");
    if (!row) return active.tagName.toLowerCase();
    const checked = row.getAttribute("aria-checked") === "true" ? ", checked" : "";
    return row.closest(".chip-menu").dataset.chipMenu + ": " +
      row.querySelector(".menu-item-label").textContent + checked;
  })()`;
  // Every key that opens a menu focuses its checked row, and Escape and a choice that
  // closes it give focus back to its trigger (docs/design-system.md, "Keys in a Menu").
  result.focus = {};
  await press("2");
  result.groupKeyOpens = await browser.evaluate(OPEN_MENU);
  result.focus.group = await browser.evaluate(FOCUS);
  // Group by's rows read as its trigger does: "By age", not "Age".
  result.groupRows = await browser.evaluate(
    `[...document.querySelectorAll("#filter-group-menu .menu-item-label")].map((label) => label.textContent)`,
  );
  await press("Escape");
  await browser.waitFor(`!document.querySelector('.chip-menu[aria-expanded="true"]')`);
  result.focus.groupEscaped = await browser.evaluate(FOCUS);
  // Group by's rows take N, A, and T while its menu is open and has focus, each running
  // the row's click path; with the menu closed, T is Quick Search (docs/design-system.md,
  // "Keys in a Menu").
  const GROUP_STATE = `({
    trigger: document.querySelector('[data-chip-menu-toggle="group"]').textContent.trim(),
    open: document.querySelector('.chip-menu[aria-expanded="true"]')?.dataset.chipMenu ?? null,
    sections: document.querySelectorAll(".tree-section").length,
  })`;
  result.letters = {};
  for (const [letter, trigger, sections] of [
    ["a", "By age", "> 0"],
    ["t", "By file type", "> 1"],
    ["n", "No grouping", "=== 0"],
  ]) {
    await press("2");
    result.focus[`group before ${letter}`] = await browser.evaluate(FOCUS);
    await press(letter);
    await browser.waitFor(
      `document.querySelector('[data-chip-menu-toggle="group"]').textContent.trim() === ${JSON.stringify(trigger)} && document.querySelectorAll(".tree-section").length ${sections}`,
      30000,
    );
    result.letters[letter] = await browser.evaluate(GROUP_STATE);
    result.focus[letter] = await browser.evaluate(FOCUS);
  }
  await browser.evaluate("document.activeElement?.blur(), true");
  await press("t");
  await browser.waitFor(`document.activeElement?.getAttribute("role") === "combobox"`);
  result.closedT = await browser.evaluate(
    `({ focus: document.activeElement.getAttribute("role"), ...${GROUP_STATE} })`,
  );
  await press("Escape");
  await browser.waitFor(`document.activeElement?.getAttribute("role") !== "combobox"`);
  await browser.waitFor(
    `document.querySelectorAll('.chip-menu[data-chip-menu="types"] .chip-menu-item').length > 30`,
    30000,
  );
  // 4 is File type: it opens the closed drawer with its menu.
  await press("4");
  await browser.waitFor(`document.getElementById("filter-drawer").dataset.open === "true"`);
  await browser.evaluate(BAR_SETTLED);
  result.typesKeyOpens = await browser.evaluate(OPEN_MENU);
  result.focus.types = await browser.evaluate(FOCUS);
  // A pick in the multi-select menu keeps it open, and the bar rebuilds under it,
  // synchronously from the filter's change: focus stays on the row picked, and on it again
  // unpicked. A MutationObserver counts the bar's rebuilds, so each read waits for the
  // rebuild it is about instead of for a time. New tallies rebuild the bar asynchronously
  // too (loadTree in app.js), but a file written here does not, because the root summary's
  // refresh leaves the bar alone while a menu is open; a rebuild with a row focused is
  // pinned browserlessly in tests/dom/key-reveal-session.js and filter-controls-behavior.js.
  await browser.evaluate(`(() => {
    window.filterBarRebuilds = 0;
    new MutationObserver((records) => { window.filterBarRebuilds += records.length; })
      .observe(document.getElementById("nav-filter-bar"), { childList: true });
    return true;
  })()`);
  const rebuilds = () => browser.evaluate("window.filterBarRebuilds");
  const rebuiltSince = (count) => browser.waitFor(`window.filterBarRebuilds > ${count}`, 30000);
  await press("ArrowDown");
  result.typesRow = await browser.evaluate(FOCUS);
  let rebuildCount = await rebuilds();
  await press("Enter");
  await rebuiltSince(rebuildCount);
  result.typesPicked = await browser.evaluate(FOCUS);
  rebuildCount = await rebuilds();
  await press("Enter");
  await rebuiltSince(rebuildCount);
  result.typesUnpicked = await browser.evaluate(FOCUS);
  result.typesRebuilds = await rebuilds();
  await browser.waitFor(
    `document.querySelectorAll('.chip-menu[data-chip-menu="types"] .chip-menu-item').length > 30`,
    30000,
  );
  await press("Escape");
  await browser.waitFor(`!document.querySelector('.chip-menu[aria-expanded="true"]')`);
  result.focus.typesEscaped = await browser.evaluate(FOCUS);
  // 3 is Modified within, in the drawer 4 left open.
  await press("3");
  result.focus.recency = await browser.evaluate(FOCUS);
  await press("Escape");
  await browser.waitFor(`!document.querySelector('.chip-menu[aria-expanded="true"]')`);
  result.focus.recencyEscaped = await browser.evaluate(FOCUS);
  // A trigger's own keys: ↓ opens its menu, and Enter clicks it, as Space does.
  await browser.evaluate(`document.querySelector('[data-chip-menu-toggle="group"]').focus(), true`);
  await press("ArrowDown");
  result.focus.arrowDown = await browser.evaluate(FOCUS);
  await press("Escape");
  result.focus.arrowDownEscaped = await browser.evaluate(FOCUS);
  await press("Enter");
  result.focus.enter = await browser.evaluate(FOCUS);
  await press("Escape");
  result.focus.enterEscaped = await browser.evaluate(FOCUS);
  await browser.evaluate("document.activeElement?.blur(), true");
  await toggle("types", true);
  result.typesTall = await measure("types");
  // The window shrinks under the open menu: it is fitted again to the room left.
  await viewport(SHORT);
  await browser.waitFor(`window.innerHeight === ${SHORT.height}`);
  await browser.evaluate(frames);
  result.typesShortResized = await measure("types");
  // Closed and opened again in the short window, it is fitted when it opens.
  await toggle("types", false);
  await toggle("types", true);
  result.typesShortOpened = await measure("types");
  // The window grows back: the row cap applies again.
  await viewport(TALL);
  await browser.waitFor(`window.innerHeight === ${TALL.height}`);
  await browser.evaluate(frames);
  result.typesTallAgain = await measure("types");
  await toggle("types", false);
  // The age menu has few rows, so neither cap reaches it at either height.
  await toggle("recency", true);
  result.ageTall = await measure("recency");
  await viewport(SHORT);
  await browser.waitFor(`window.innerHeight === ${SHORT.height}`);
  await browser.evaluate(frames);
  result.ageShort = await measure("recency");
  await toggle("recency", false);
  await viewport(TALL);
  await browser.waitFor(`window.innerHeight === ${TALL.height}`);
  phase("measured");

  // Group by File type: one section per group, headed in the menu group pattern.
  await toggle("group", true);
  await browser.evaluate(
    `document.querySelector('#filter-group-menu [data-chip-value="type"]').click(), true`,
  );
  await browser.waitFor("document.querySelectorAll('.tree-section').length > 1", 30000);
  await browser.evaluate(frames);
  result.byType = await browser.evaluate(SECTIONS);
  // What a section and its tree are named, as Chrome computes it for assistive technology:
  // the heading's words, its tally's dot left out.
  await browser.send("Accessibility.enable");
  result.byTypeNames = [];
  const sectionCount = await browser.evaluate("document.querySelectorAll('.tree-section').length");
  for (let index = 0; index < sectionCount; index += 1) {
    const named = {};
    for (const [part, selector] of [
      ["section", ""],
      ["tree", ".querySelector(':scope > [role=\"tree\"]')"],
    ]) {
      const { result: handle } = await browser.send("Runtime.evaluate", {
        expression: `document.querySelectorAll('.tree-section')[${index}]${selector}`,
      });
      const { nodes } = await browser.send("Accessibility.getPartialAXTree", {
        objectId: handle.objectId,
        fetchRelatives: false,
      });
      named[part] = nodes.find((node) => !node.ignored)?.name?.value ?? null;
    }
    result.byTypeNames.push(named);
  }
  // Off again, so the accessibility tree is not kept up through the steps after this.
  await browser.send("Accessibility.disable");
  // At the narrowest pane the heading is still one line: a name too long for it is cut
  // short and the tally stays whole.
  await paneWidth(NARROWEST);
  await browser.evaluate(frames);
  result.byTypeNarrow = await browser.evaluate(SECTIONS);
  // There, a name cut short gives its whole in its tooltip, and a whole one shows none.
  result.sectionTips = await browser.evaluate(SECTION_TIPS);
  await paneWidth(null);
  await browser.evaluate(frames);
  // A folder inside a section opens under that section's group.
  await browser.evaluate(
    `document.querySelector('.tree-section[data-tree-group="type:code"] .tree-folder[data-path="src"]').click(), true`,
  );
  await browser.waitFor(
    `document.querySelectorAll('.tree-section[data-tree-group="type:code"] .tree-file').length > 3`,
    30000,
  );
  result.codeFiles = await browser.evaluate(
    `[...document.querySelectorAll('.tree-section[data-tree-group="type:code"] .tree-file')].map((row) => row.dataset.path)`,
  );
  // src also stands in Documentation. With focus on Code's copy, the keys that close and
  // open it are mutations the tree repairs focus after: focus stays on Code's copy.
  const FOCUSED = `(() => { const row = document.activeElement; return { section: row?.closest(".tree-section")?.dataset.treeGroup ?? null, path: row?.dataset?.path ?? null, expanded: row?.getAttribute("aria-expanded") ?? null }; })()`;
  await browser.evaluate(
    `document.querySelector('.tree-section[data-tree-group="type:code"] .tree-folder[data-path="src"]').focus(), true`,
  );
  await press("ArrowLeft");
  await browser.evaluate(frames);
  result.focusAfterClose = await browser.evaluate(FOCUSED);
  await press("ArrowRight");
  await browser.waitFor(
    `document.querySelector('.tree-section[data-tree-group="type:code"] .tree-folder[data-path="src"]').getAttribute("aria-expanded") === "true"`,
  );
  await browser.evaluate(frames);
  result.focusAfterOpen = await browser.evaluate(FOCUSED);
  // A file written into a folder open two levels down refreshes the sections in place: the
  // folder stays open with the new file in it, and the scroll position and the focused row
  // inside it are kept. A headless page has no window focus, so its rows hear no focus
  // events, which a reader's window does; the emulation gives it that.
  await browser.send("Emulation.setFocusEmulationEnabled", { enabled: true });
  const LIB = `.tree-section[data-tree-group="type:code"] .tree-folder[data-path="src/lib"]`;
  await browser.evaluate(`document.querySelector('${LIB}').click(), true`);
  await browser.waitFor(
    `document.querySelector('${LIB}')?.getAttribute("aria-expanded") === "true"`,
  );
  const FOCUS_ROW = `.tree-section[data-tree-group="type:code"] .tree-file[data-path="src/lib/k06.py"]`;
  // The row takes focus once its folder's opening has made it visible; scrolled to the top
  // of the tree, it leaves the tree scrolled.
  await browser.waitFor(
    `(() => { const row = document.querySelector('${FOCUS_ROW}'); if (!row) return false; row.focus({ preventScroll: true }); return document.activeElement === row; })()`,
    30000,
  );
  await browser.evaluate(
    `document.querySelector('${FOCUS_ROW}').scrollIntoView({ block: "start" }), true`,
  );
  await browser.evaluate(frames);
  const REFRESH_STATE = `({ scrollTop: document.getElementById("tree-content").scrollTop, focused: document.activeElement?.dataset?.treeId ?? null, libOpen: document.querySelector('${LIB}')?.getAttribute("aria-expanded") ?? null, written: Boolean(document.querySelector('.tree-section[data-tree-group="type:code"] .tree-file[data-path="src/lib/k99.py"]')) })`;
  const beforeWrite = await browser.evaluate(REFRESH_STATE);
  // Code's heading, marked, to tell a heading refreshed in place from one drawn again.
  const CODE_HEADING = `document.querySelector('.tree-section[data-tree-group="type:code"] > .tree-section-heading')`;
  await browser.evaluate(`(${CODE_HEADING}.dataset.before = "1", true)`);
  // The page's own event stream, counted from here. It carries the tree two levels deep,
  // so the write shows on it as a change to the folders above the file.
  await browser.evaluate(
    `(window.__fsChanges = 0, inventoryEventSource.addEventListener("fs.change", () => { window.__fsChanges += 1; }), true)`,
  );
  fs.writeFileSync(path.join(root, "src", "lib", "k99.py"), "x99\n");
  const written = Date.now();
  let afterWrite = await browser.evaluate(REFRESH_STATE);
  while (!afterWrite.written && Date.now() - written < 15000) {
    await sleep(100);
    afterWrite = await browser.evaluate(REFRESH_STATE);
  }
  await browser.evaluate(frames);
  result.refresh = { before: beforeWrite, after: await browser.evaluate(REFRESH_STATE) };
  // Whether any change reached the page after the write, which says where a refresh that
  // did not come stopped: before the page, in the operating system's file events, the
  // server's watcher, or the event stream; or in the page, with the change in hand.
  result.refreshDelivered = await browser.evaluate("window.__fsChanges > 0");
  // The heading kept its place, its category's icon, and its name, and updated its tally
  // beside its name.
  result.refreshedHeading = await browser.evaluate(
    `(() => { const heading = ${CODE_HEADING}; return { kept: heading.dataset.before === "1", icon: heading.firstElementChild?.matches(".category-icon") ?? false, tally: heading.querySelector(":scope > .heading-tally").textContent }; })()`,
  );
  phase("refreshed");
  // No grouping is the one tree again.
  await toggle("group", true);
  await browser.evaluate(
    `document.querySelector('#filter-group-menu [data-chip-any]').click(), true`,
  );
  await browser.waitFor("document.querySelectorAll('.tree-section').length === 0", 30000);
  result.ungrouped = await browser.evaluate(
    `({ sections: document.querySelectorAll('.tree-section').length, trees: [...document.querySelectorAll('#tab-files [role="tree"]')].map((tree) => tree.getAttribute("aria-label")) })`,
  );
  result.slots = await browser.evaluate(SLOTS);
  result.treeTips = await browser.evaluate(TREE_TIPS);
  result.tipRepaints = await browser.evaluate(TIP_REPAINTS);
  phase("grouped");

  // Waiting (docs/design-system.md, "Grouping the Files Tree"): every grouped request is
  // held at the page until it is released, so each load is as slow as the session says.
  /** @type {string[]} */
  const held = [];
  let releaseAll = false;
  browser.on("Fetch.requestPaused", (params) => {
    if (releaseAll) {
      browser.send("Fetch.continueRequest", { requestId: params.requestId }).catch(() => {});
    } else {
      held.push(params.requestId);
    }
  });
  const release = async () => {
    for (const requestId of held.splice(0)) {
      // A request the page aborted while it was held is gone already.
      await browser.send("Fetch.continueRequest", { requestId }).catch(() => {});
    }
  };
  let requested = 0;
  /** @type {string[]} the groupings asked for, in order */
  const asked = [];
  browser.on("Fetch.requestPaused", (params) => {
    requested += 1;
    asked.push(new URL(params.request.url).searchParams.get("group_by") || "");
  });
  await browser.send("Fetch.enable", { patterns: [{ urlPattern: "*group_by=*" }] });
  const WAITING = `(() => {
    const panel = document.getElementById("tab-files");
    const progress = document.getElementById("index-progress");
    const tree = panel.querySelector(":scope > :not(.nav-metadata, .notice)");
    const trigger = document.querySelector('[data-chip-menu-toggle="group"]');
    const token = (name) => Number(getComputedStyle(document.documentElement).getPropertyValue(name));
    return {
      trigger: trigger.textContent.trim(),
      // Breathing is an animation on the trigger, by any class.
      breathing: trigger.getAnimations().some((a) => a instanceof CSSAnimation) || trigger.classList.contains("mb-refreshing"),
      progress: progress.hidden ? null : progress.querySelector(".index-progress-text").textContent,
      progressShown: !progress.hidden && getComputedStyle(progress).visibility === "visible",
      treeOpacity: tree ? Math.round(Number(getComputedStyle(tree).opacity) * 100) / 100 : null,
      busy: panel.getAttribute("aria-busy"),
      sections: panel.querySelectorAll(".tree-section").length,
      dimmedToken: token("--dimmed-content-opacity"),
      loadingDimToken: token("--loading-dim-opacity"),
    };
  })()`;
  // Paint, as Chrome draws it: a color as 8-bit sRGB, alpha-composited over the ground
  // behind an element (the backgrounds of its ancestors, from the first opaque one in),
  // and WCAG contrast. Opacity composites in sRGB, as a canvas does.
  const PAINT = `(() => {
    const canvas = document.createElement("canvas");
    canvas.width = canvas.height = 1;
    const ctx = canvas.getContext("2d", { willReadFrequently: true });
    const paint = (layers) => {
      ctx.globalAlpha = 1;
      ctx.clearRect(0, 0, 1, 1);
      for (const [color, alpha] of layers) {
        ctx.globalAlpha = alpha;
        ctx.fillStyle = color;
        ctx.fillRect(0, 0, 1, 1);
      }
      return [...ctx.getImageData(0, 0, 1, 1).data];
    };
    const css = (rgba) => "rgb(" + rgba.slice(0, 3).join(" ") + ")";
    const ground = (el, self = false) => {
      const layers = [];
      for (let node = self ? el : el.parentElement; node; node = node.parentElement) {
        const background = getComputedStyle(node).backgroundColor;
        const alpha = paint([[background, 1]])[3];
        if (alpha > 0) layers.unshift([background, 1]);
        if (alpha === 255) break;
      }
      layers.unshift(["rgb(255 255 255)", 1]);
      return css(paint(layers));
    };
    const luminance = (rgba) => {
      const [r, g, b] = rgba.slice(0, 3).map((v) => {
        const c = v / 255;
        return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
      });
      return 0.2126 * r + 0.7152 * g + 0.0722 * b;
    };
    const contrast = (a, b) => {
      const [hi, lo] = [luminance(paint([[a, 1]])), luminance(paint([[b, 1]]))].sort((x, y) => y - x);
      return Math.round(((hi + 0.05) / (lo + 0.05)) * 100) / 100;
    };
    // The opacity an element is drawn at: its own and every ancestor's, multiplied.
    const opacity = (el) => {
      let product = 1;
      for (let node = el; node; node = node.parentElement) product *= Number(getComputedStyle(node).opacity);
      return Math.round(product * 10000) / 10000;
    };
    return { paint, css, ground, contrast, opacity };
  })()`;
  // The Group by trigger as it reads while a choice waits: its ink on its own ground, at
  // rest, and what breathing did at its dimmest, the whole trigger at
  // --refreshing-text-dim-opacity over the bar (before mb-xlla), in both themes.
  const TRIGGER_INK = `(() => {
    const { paint, css, ground, contrast } = ${PAINT};
    const trigger = document.querySelector('[data-chip-menu-toggle="group"]');
    const style = getComputedStyle(trigger);
    const outer = ground(trigger);
    const own = ground(trigger, true);
    const dim = Number(getComputedStyle(document.documentElement).getPropertyValue("--refreshing-text-dim-opacity"));
    return {
      active: trigger.dataset.active,
      rest: contrast(style.color, own),
      breathingDimmest: contrast(
        css(paint([[outer, 1], [style.color, dim]])),
        css(paint([[outer, 1], [style.backgroundColor, dim]])),
      ),
    };
  })()`;
  // A theme set, once the transitions it starts are over: the chip's own color
  // (`.chip`, --transition-fast) and the surfaces' crossfade (--theme-transition).
  const THEME = (theme) => `(async () => {
    document.documentElement.setAttribute("data-theme", ${JSON.stringify(theme)});
    const frame = () => new Promise((resolve) => requestAnimationFrame(resolve));
    await frame();
    for (let at = 0; at < 120 && document.getAnimations().some((a) => a instanceof CSSTransition); at += 1) {
      await frame();
    }
    await frame();
    return true;
  })()`;
  /** The trigger's ink in each theme. */
  const triggerInk = async () => {
    const themes = {};
    for (const theme of ["light", "dark"]) {
      await browser.evaluate(THEME(theme));
      themes[theme] = await browser.evaluate(TRIGGER_INK);
    }
    await browser.evaluate(THEME("light"));
    return themes;
  };
  // A tree row as an ignored file's is drawn (app.js gives an ignored entry's row
  // `tree-item-gitignored`; this fixture has no Git repository, so none is ignored): the
  // opacity its name is drawn at and its contrast on the tree's ground, once the dim's quiet
  // period has passed for it. The row's class is put back as it was. Not the row under the
  // pointer, which the menu's press left over the tree: hover lifts an ignored row.
  const IGNORED_ROW = `(async () => {
    const { paint, css, ground, contrast, opacity } = ${PAINT};
    const row = document.querySelector("#tab-files .tree-item:not(.tree-item-gitignored, .tree-item-empty, :hover)");
    row.classList.add("tree-item-gitignored");
    // Under the dim the row holds itself after the quiet period, by an animation; at rest it
    // has none, so this is at once.
    await Promise.all(row.getAnimations().map((animation) => animation.finished));
    await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
    const name = row.querySelector(".tree-item-name");
    const drawn = opacity(name);
    const under = ground(document.getElementById("tab-files"), true);
    const ink = css(paint([[under, 1], [getComputedStyle(name).color, drawn]]));
    row.classList.remove("tree-item-gitignored");
    return { opacity: drawn, contrast: contrast(ink, under) };
  })()`;
  // The trigger as the click that chose leaves it, read before the frame it paints in.
  const ARM_CHOICE = `(() => {
    window.__groupChoice = null;
    document.addEventListener("click", () => {
      window.__groupChoice = document.querySelector('[data-chip-menu-toggle="group"]').textContent.trim();
    }, { once: true });
    return true;
  })()`;
  const rowCenter = (value) =>
    browser.evaluate(
      `(() => { const row = document.querySelector('#filter-group-menu ${value === "none" ? "[data-chip-any]" : `[data-chip-value="${value}"]`}'); const box = row.getBoundingClientRect(); return { x: box.left + box.width / 2, y: box.top + box.height / 2 }; })()`,
    );
  const pointer = (type, at) =>
    browser.send("Input.dispatchMouseEvent", {
      type,
      x: at.x,
      y: at.y,
      button: "left",
      clickCount: 1,
    });
  /** Choose *value* in Group by with a click, and read the trigger as the click left it. */
  const choose = async (value) => {
    await toggle("group", true);
    const at = await rowCenter(value);
    await browser.evaluate(ARM_CHOICE);
    await pointer("mousePressed", at);
    await pointer("mouseReleased", at);
    return browser.evaluate("window.__groupChoice");
  };
  result.waiting = {};
  // Pressing By file type asks for it ahead, and a file written before the press lets
  // go is a change that answer predates: the answer is kept rather than dropped.
  await toggle("group", true);
  const typeRow = await rowCenter("type");
  await browser.evaluate(ARM_CHOICE);
  const beforePress = requested;
  await pointer("mousePressed", typeRow);
  const pressDeadline = Date.now() + 10000;
  while (requested === beforePress && Date.now() < pressDeadline) {
    await sleep(20);
  }
  const prefetched = requested - beforePress;
  fs.writeFileSync(path.join(root, "docs", "waiting.md"), "# Waiting\n");
  await sleep(1200);
  await pointer("mouseReleased", typeRow);
  result.waiting.chosenInFrame = await browser.evaluate("window.__groupChoice");
  result.waiting.requestsForChoice = { prefetched, afterChoice: requested - beforePress };
  // Past the quiet period the tree dims under the scan row's words.
  await sleep(300);
  result.waiting.slow = await browser.evaluate(WAITING);
  // The trigger reads the choice without breathing, and a row already dimmed is not dimmed
  // twice under the wait.
  result.waiting.triggerInk = await triggerInk();
  result.waiting.ignoredUnderDim = await browser.evaluate(IGNORED_ROW);
  // A reveal while those sections are on their way, as navigating to a file makes one,
  // lands once they paint (app.js, revealInTree).
  await browser.evaluate(
    `(window.__revealed = undefined, revealFileRow("src/lib/k03.py", { scroll: "nearest", isCurrent: () => true }).then((shown) => { window.__revealed = shown; }), true)`,
  );
  // The write asks the sections to refresh; that waits for the sections on their way
  // instead of starting them over.
  await sleep(1500);
  result.waiting.refreshWaits = { requests: requested - beforePress, held: held.length };
  // Released, the answer paints, and the refresh it waited for follows.
  const beforeRelease = requested;
  await release();
  await browser.waitFor("document.querySelectorAll('.tree-section').length > 1", 30000);
  await browser.evaluate(frames);
  result.waiting.painted = await browser.evaluate(WAITING);
  result.waiting.ignoredAtRest = await browser.evaluate(IGNORED_ROW);
  result.waiting.triggerInkAfter = await triggerInk();
  await browser.waitFor("window.__revealed !== undefined", 30000);
  result.waiting.revealed = await browser.evaluate(
    `({ shown: window.__revealed, row: document.querySelector('.tree-section[data-tree-group="type:code"] .tree-item[data-path="src/lib/k03.py"]')?.classList.contains("selected") ?? null })`,
  );
  const refreshDeadline = Date.now() + 10000;
  while (requested === beforeRelease && Date.now() < refreshDeadline) {
    await sleep(50);
  }
  result.waiting.refreshedAfter = requested > beforeRelease;
  await release();
  await browser.waitFor(
    `document.getElementById("tab-files").getAttribute("aria-busy") === "false"`,
    30000,
  );
  releaseAll = true;
  await choose("none");
  await browser.waitFor("document.querySelectorAll('.tree-section').length === 0", 30000);
  releaseAll = false;
  // A newer choice cancels a load on its way, and No grouping ends the wait at once.
  result.waiting.chosen = {};
  result.waiting.chosen.type = await choose("type");
  await sleep(300);
  result.waiting.typeLoading = await browser.evaluate(WAITING);
  result.waiting.chosen.age = await choose("age");
  await sleep(300);
  result.waiting.ageLoading = await browser.evaluate(WAITING);
  result.waiting.chosen.none = await choose("none");
  await browser.evaluate(frames);
  result.waiting.cancelled = await browser.evaluate(WAITING);
  // The answers the reader left arrive and paint nothing.
  await release();
  await sleep(800);
  result.waiting.stale = await browser.evaluate(WAITING);
  releaseAll = true;
  await release();
  // The keyboard asks only for a row it rests on (createGroupsPrefetch, rest). ↓ ↓ ↓ and
  // Enter on the trigger, each in the frame after the last, pass By age on the way to By
  // file type: the choice asks for By file type, and By age is never asked for.
  const keyboard = async (keys, restMs = 0) => {
    const before = asked.length;
    await browser.evaluate(
      `document.querySelector('[data-chip-menu-toggle="group"]').focus(), true`,
    );
    for (const key of keys) {
      if (key === "rest") {
        await sleep(restMs);
      } else {
        await press(key);
      }
    }
    await browser.waitFor(
      `!document.querySelector('[data-chip-menu-toggle="group"]').classList.contains("mb-refreshing") && document.querySelectorAll('.tree-section').length > 0`,
      30000,
    );
    return asked.slice(before);
  };
  result.keyboard = {};
  result.keyboard.walk = await keyboard(["ArrowDown", "ArrowDown", "ArrowDown", "Enter"]);
  result.keyboard.walkTrigger = await browser.evaluate(
    `document.querySelector('[data-chip-menu-toggle="group"]').textContent.trim()`,
  );
  await choose("none");
  await browser.waitFor("document.querySelectorAll('.tree-section').length === 0", 30000);
  // Resting on By age past the dwell asks for it ahead, and Enter takes that answer.
  result.keyboard.rest = await keyboard(["ArrowDown", "ArrowDown", "rest", "Enter"], 700);
  result.keyboard.restTrigger = await browser.evaluate(
    `document.querySelector('[data-chip-menu-toggle="group"]').textContent.trim()`,
  );
  await choose("none");
  await browser.waitFor("document.querySelectorAll('.tree-section').length === 0", 30000);
  await browser.send("Fetch.disable");
  phase("waited");
  process.stdout.write(`${JSON.stringify(result)}\n`);
} finally {
  await chrome?.close();
  await server.stop();
  phase("closed");
}

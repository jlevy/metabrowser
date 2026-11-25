// Browserless session: how every menu closes (docs/design-system.md, "Every Menu Closes
// Alike").
//
// The production static/filter-controls.js, whose `metabrowser.menus.dismissible` every
// menu closes through, and static/menus.js, the shell tool it forwards to, load whole on
// the key reveal's stand-in DOM (tests/dom/key-reveal-dom.js), which keeps focus, event
// capture and bubbling, and the window's blur.
//
// `menu` is one menu as a plugin wires it: a press or a tap outside it and its trigger,
// focus arriving outside them, the window losing focus, and Escape close it, each for the
// reason the helper gives its `close`; a press inside it, a second press of its trigger,
// focus that goes nowhere, an Escape a surface above took first, and an Escape held with a
// modifier do not close it from outside; opening one closes another; and the document is
// listened to only while a menu is open.
//
// `filesBar` is the Files tab's filter bar as app.js draws it with the same renderers and
// `bind`, its consumer rebuilding the bar on every change: Group by and the drawer's
// dropdowns close on a press on the bar beside them, on the drawer's chevron, on Show
// ignored, on another dropdown's trigger, and outside the bar; what each press landed on
// still acts; and Escape gives focus back to the trigger.
//
// `early` is a menu that opens before the shell's tools arrive: it asks for them, and once
// they land it closes as every menu does.
//
// A press is a browser's: `pointerdown`, then focus for a button, as Chrome gives it, then
// `click`. Exits 1 on a failed invariant.

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const { FakeDocument, element, keyEvent } = require("./key-reveal-dom.js");

const staticDir = path.resolve(__dirname, "../../src/metabrowser/static");
const read = (name) => fs.readFileSync(path.join(staticDir, name), "utf8");

/** A page's scripts: filter-controls.js, then menus.js unless `early` holds it back. */
function loadShell({ early = null } = {}) {
  const sandbox = {
    console,
    JSON,
    String,
    Array,
    Object,
    MetabrowserIcons: { toggle: '<svg class="toggle-chevron"></svg>' },
    metabrowser: {},
  };
  sandbox.window = sandbox;
  sandbox.globalThis = sandbox;
  if (early) {
    sandbox.MetabrowserAssets = {
      ensureAsset(name) {
        early.asked.push(name);
        return new Promise((resolve) => {
          early.land = () => {
            vm.runInContext(read("menus.js"), sandbox, {
              filename: path.join(staticDir, "menus.js"),
            });
            resolve();
          };
        });
      },
    };
  }
  vm.createContext(sandbox);
  vm.runInContext(read("filter-controls.js"), sandbox, {
    filename: path.join(staticDir, "filter-controls.js"),
  });
  if (!early) {
    vm.runInContext(read("menus.js"), sandbox, { filename: path.join(staticDir, "menus.js") });
  }
  return sandbox.metabrowser;
}

/** The listeners the document and the window hold for open menus. */
function listening(doc) {
  const kinds = new Set(["pointerdown", "click", "focusin", "keydown"]);
  return (
    doc.listeners.filter((entry) => kinds.has(entry.type)).length +
    doc.defaultView.listeners.filter((entry) => entry.type === "blur").length
  );
}

/**
 * A press as Chrome delivers one: down, then focus for a button or a checkbox and none for
 * anything else, then the click, and a checkbox's change.
 */
function press(node, { check = false } = {}) {
  node.dispatchEvent({ type: "pointerdown", target: node, button: 0 });
  if (/^(BUTTON|INPUT)$/.test(node.tagName)) {
    node.focus();
  } else {
    node.ownerDocument.activeElement?.blur();
  }
  if (check) {
    node.checked = !(node.checked ?? node.hasAttribute("checked"));
  }
  node.dispatchEvent({ type: "click", target: node, button: 0 });
  if (check) {
    node.dispatchEvent({ type: "change", target: node });
  }
}

/** A key at the focused element, bubbling to the document; whether it was prevented. */
function key(doc, name, init = {}) {
  const event = keyEvent("keydown", name, { target: doc.activeElement, ...init });
  doc.activeElement.dispatchEvent(event);
  return event.defaultPrevented;
}

/** Where focus is, by the name the session gave each control. */
function focusName(doc) {
  const active = doc.activeElement;
  if (!active || active === doc.body) {
    return "the page";
  }
  return (
    active.getAttribute("data-name") ??
    active.getAttribute("data-chip-menu-toggle") ??
    active.getAttribute("data-chip-key") ??
    active.getAttribute("data-chip-check") ??
    (active.closest(".chip-menu-panel") ? "a row" : active.tagName.toLowerCase())
  );
}

// ── One menu, as a plugin wires it ───────────────────────────────────

function menuSession() {
  const mb = loadShell();
  const doc = new FakeDocument();
  const closes = [];
  /** A trigger, its panel of two items, and the wiring every menu has. */
  function makeMenu(name) {
    const trigger = element(doc, "button", { "data-name": `${name} trigger` });
    const first = element(doc, "button", { "data-name": `${name} first item` });
    const panel = element(doc, "div", { class: "menu", hidden: true }, first);
    doc.body.append(element(doc, "div", {}, trigger, panel));
    const dismissal = mb.menus.dismissible({
      name: `${name}-menu`,
      trigger,
      inside: (node) => panel.contains(node),
      isOpen: () => !panel.hidden,
      close(how) {
        panel.hidden = true;
        closes.push(`${name}: ${how}`);
      },
    });
    trigger.addEventListener("click", () => {
      panel.hidden = !panel.hidden;
      if (panel.hidden) {
        dismissal.closed();
      } else {
        dismissal.opened();
        first.focus();
      }
    });
    return { name, trigger, first, panel, dismissal };
  }
  const a = makeMenu("A");
  const b = makeMenu("B");
  const outside = element(doc, "button", { "data-name": "a button outside" });
  const text = element(doc, "p", {}, "text outside");
  doc.body.append(outside, text);

  const steps = [];
  const step = (label, extra = {}) => {
    steps.push({
      step: label,
      open: [a, b].filter((menu) => !menu.panel.hidden).map((menu) => menu.name),
      closed: closes.splice(0),
      focus: focusName(doc),
      listening: listening(doc),
      ...extra,
    });
  };
  const open = (menu) => {
    if (menu.panel.hidden) {
      press(menu.trigger);
    }
    closes.splice(0);
  };

  step("nothing open");
  press(a.trigger);
  step("a press on A's trigger opens it");
  press(a.first);
  step("a press inside it leaves it open");
  press(outside);
  step("a press on a button outside closes it");
  open(a);
  press(text);
  step("a press on text outside closes it");
  open(a);
  press(a.trigger);
  step("a second press on its trigger closes it");
  open(a);
  step("Escape closes it and gives focus back to its trigger", {
    prevented: key(doc, "Escape"),
  });
  open(a);
  step("an Escape a surface above took first leaves it open", {
    prevented: key(doc, "Escape", { defaultPrevented: true }),
  });
  step("Option-Escape is the browser's and leaves it open", {
    prevented: key(doc, "Escape", { altKey: true }),
  });
  key(doc, "Escape");
  open(a);
  outside.focus();
  step("focus arriving outside closes it");
  open(a);
  a.first.blur();
  step("focus that goes nowhere leaves it to a press");
  doc.defaultView.loseFocus();
  step("the window losing focus, to a frame or another window, closes it");
  doc.defaultView.regainFocus();
  open(a);
  b.panel.hidden = false;
  b.dismissal.opened();
  step("B opening by a key, with focus left in A, closes A");
  open(a);
  press(b.trigger);
  step("a press on B's trigger closes A and opens B");
  b.dismissal.dispose();
  step("a menu disposed open, as when its view goes, lets the document go", { disposed: "B" });
  b.panel.hidden = true;
  a.dismissal.dispose();
  return steps;
}

// ── The Files tab's filter bar ───────────────────────────────────────

function filesBarSession() {
  const mb = loadShell();
  const fc = mb.filterControls;
  const doc = new FakeDocument();
  const bar = element(doc, "div", { id: "nav-filter-bar", class: "nav-filter-bar" });
  const treeRow = element(doc, "button", { "data-name": "a tree row" });
  doc.body.append(bar, treeRow);
  const state = { open: null, group: "none", recency: "all", types: [], drawer: false };
  state.showIgnored = true;
  const acted = [];
  const option = (value, label) => ({ value, label });
  // The bar as app.js's renderNavFilterBar draws it, from the same renderers.
  const render = () => {
    const restore = fc.keepFocus(bar);
    bar.innerHTML =
      '<div class="nav-filter-bar-main nav-toolbar-row">' +
      fc.menuGroupHtml({
        key: "group",
        select: "one",
        label: "Group by",
        options: [option("age", "By age"), option("type", "By file type")],
        value: state.group,
        anyLabel: "No grouping",
        anyValue: "none",
        open: state.open === "group",
        menuId: "filter-group-menu",
      }) +
      '<span class="nav-filter-bar-end">' +
      fc.toggleHtml({
        key: "drawer",
        icon: '<svg class="toggle-chevron"></svg>',
        className: "filter-drawer-toggle disclosure-toggle",
        pressed: state.drawer,
        ariaLabel: state.drawer ? "Hide filters" : "Show filters",
        controls: "filter-drawer",
      }) +
      "</span></div>" +
      `<div class="filter-drawer" id="filter-drawer" data-open="${state.drawer}">` +
      '<div class="filter-drawer-row">' +
      fc.menuGroupHtml({
        key: "recency",
        select: "one",
        label: "Modified within",
        options: [option("1d", "Last day"), option("7d", "Last week")],
        value: state.recency,
        anyLabel: "Any age",
        anyValue: "all",
        open: state.open === "recency",
        menuId: "filter-recency-menu",
      }) +
      fc.menuGroupHtml({
        key: "types",
        label: "File type",
        options: [option(".md", ".md"), option(".py", ".py")],
        value: state.types,
        anyLabel: "Any type",
        open: state.open === "types",
        menuId: "filter-type-menu",
      }) +
      fc.checkHtml({ key: "showIgnored", label: "Show ignored", checked: state.showIgnored }) +
      "</div></div>";
    restore();
  };
  render();
  const unbind = fc.bind(bar, {
    onMenuToggle(name, open) {
      state.open = open ? name : state.open === name ? null : state.open;
      render();
    },
    onMenuPick(name, value) {
      if (name === "group") {
        state.group = value ?? "none";
        state.open = null;
      }
      render();
    },
    onToggle(name, pressed) {
      acted.push(`${name} ${pressed ? "on" : "off"}`);
      state[name] = pressed;
      render();
    },
  });

  const trigger = (name) => bar.querySelector(`[data-chip-menu-toggle="${name}"]`);
  const steps = [];
  let otherOpen = false;
  const step = (label, extra = {}) => {
    steps.push({
      step: label,
      open: state.open ?? "none",
      ...extra,
      ...(otherOpen ? { otherMenu: "open" } : {}),
      acted: acted.splice(0),
      focus: focusName(doc),
      listening: listening(doc),
    });
  };
  const open = (name) => {
    if (state.open !== name) {
      press(trigger(name));
    }
    acted.splice(0);
  };

  press(trigger("group"));
  step("a press on Group by opens it");
  press(bar.querySelector(".nav-filter-bar-main"));
  step("a press on the bar beside it closes it");
  open("group");
  press(bar.querySelector('[data-chip-key="drawer"]'));
  step("a press on the drawer's chevron closes Group by and opens the drawer");
  open("types");
  press(trigger("recency"));
  step("a press on Modified within, with File type open, opens Modified within");
  press(bar.querySelector('[data-chip-check="showIgnored"]'), { check: true });
  step("a press on Show ignored closes Modified within and turns Show ignored off");
  open("types");
  press(treeRow);
  step("a press outside the bar closes File type");
  open("group");
  press(trigger("group"));
  step("a second press on Group by closes it");
  open("types");
  key(doc, "Escape");
  step("Escape closes File type and gives focus back to its trigger");
  open("group");
  const other = element(doc, "button", { "data-name": "another menu's trigger" });
  doc.body.append(other);
  const otherDismissal = mb.menus.dismissible({
    name: "other-menu",
    trigger: other,
    inside: () => false,
    isOpen: () => otherOpen,
    close() {
      otherOpen = false;
    },
  });
  otherOpen = true;
  otherDismissal.opened();
  step("another menu opening closes Group by");
  press(trigger("group"));
  step("Group by opening closes the other menu");
  press(trigger("group"));
  open("group");
  unbind();
  step("unbinding the bar with Group by drawn open lets the document go", { unbound: true });
  return steps;
}

// ── A menu opened before the shell's tools arrive ────────────────────

async function earlySession() {
  const early = { asked: [], land: null };
  const mb = loadShell({ early });
  const doc = new FakeDocument();
  const trigger = element(doc, "button", { "data-name": "trigger" });
  const panel = element(doc, "div", { class: "menu" });
  const outside = element(doc, "button", { "data-name": "a button outside" });
  doc.body.append(trigger, panel, outside);
  const closes = [];
  const dismissal = mb.menus.dismissible({
    name: "early-menu",
    trigger,
    inside: (node) => panel.contains(node),
    isOpen: () => !panel.hidden,
    close(how) {
      panel.hidden = true;
      closes.push(how);
    },
  });
  dismissal.opened();
  const asked = {
    step: "a menu opens before the shell's tools: it asks for them",
    asked: [...early.asked],
    listening: listening(doc),
  };
  early.land();
  await new Promise((resolve) => setImmediate(resolve));
  const landed = { step: "they land, and the open menu listens", listening: listening(doc) };
  press(outside);
  const closed = {
    step: "a press outside closes it",
    closed: closes.splice(0),
    listening: listening(doc),
  };
  return [asked, landed, closed];
}

async function main() {
  const told = { menu: menuSession(), filesBar: filesBarSession(), early: await earlySession() };
  // No menu holds the document while none is open, and one holds it while open.
  for (const step of told.menu.filter((each) => !each.disposed)) {
    assert.equal(step.listening > 0, step.open.length > 0, step.step);
  }
  for (const step of told.filesBar.filter((each) => !each.unbound)) {
    assert.equal(step.listening > 0, step.open !== "none" || "otherMenu" in step, step.step);
  }
  process.stdout.write(`${JSON.stringify(told, null, 2)}\n`);
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});

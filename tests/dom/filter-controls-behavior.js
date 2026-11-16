// Behavioural checks for static/filter-controls.js: the selection
// semantics that separate single- from multi-select, and the markup
// contract the stylesheet keys off.

const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const repoRoot = path.resolve(__dirname, "../..");

const menuChevron = '<svg class="toggle-chevron" data-test-icon="shared-chevron"></svg>';
const sandbox = {
  console: { warn() {} },
  JSON,
  String,
  Array,
  Object,
  MetabrowserIcons: { toggle: menuChevron },
  metabrowser: {},
};
sandbox.window = sandbox;
sandbox.globalThis = sandbox;
vm.createContext(sandbox);

const source = fs.readFileSync(
  path.join(repoRoot, "src/metabrowser/static/filter-controls.js"),
  "utf-8",
);
vm.runInContext(source, sandbox, { filename: "filter-controls.js" });

const fc = sandbox.metabrowser.filterControls;
const failures = [];

assertEqual("filter controls join the plugin SDK", sandbox.metabrowser.filterControls, fc);

function assertEqual(label, actual, expected) {
  if (JSON.stringify(actual) !== JSON.stringify(expected)) {
    failures.push(`${label}: expected ${JSON.stringify(expected)} got ${JSON.stringify(actual)}`);
  }
}

function assertContains(label, haystack, needle) {
  if (String(haystack).indexOf(needle) === -1) {
    failures.push(`${label}: ${JSON.stringify(needle)} not found in ${JSON.stringify(haystack)}`);
  }
}

function assertMissing(label, haystack, needle) {
  if (String(haystack).indexOf(needle) !== -1) {
    failures.push(`${label}: ${JSON.stringify(needle)} unexpectedly present`);
  }
}

// ── Selection semantics ────────────────────────────────────────

assertEqual("single-select replaces the current value", fc.nextSelection("one", "a", "b"), "b");
assertEqual(
  "single-select re-picking the same value is idempotent",
  fc.nextSelection("one", "a", "a"),
  "a",
);

assertEqual("multi-select adds to an empty set", fc.nextSelection("many", null, "a"), ["a"]);
assertEqual("multi-select accumulates", fc.nextSelection("many", ["a"], "b"), ["a", "b"]);
assertEqual("multi-select toggles off", fc.nextSelection("many", ["a", "b"], "a"), ["b"]);
// Empty and null both mean "no constraint", so they must normalize to
// one value or activeCount would report a filter nobody set.
assertEqual(
  "emptying a multi-select normalizes to null",
  fc.nextSelection("many", ["a"], "a"),
  null,
);

assertEqual("isSelected on a scalar", fc.isSelected("a", "a"), true);
assertEqual("isSelected on a list", fc.isSelected(["a", "b"], "b"), true);
assertEqual("isSelected rejects a miss", fc.isSelected(["a"], "b"), false);

// ── Markup contract ────────────────────────────────────────────

const single = fc.groupHtml({
  key: "recency",
  select: "one",
  label: "Modified within",
  options: [
    { value: "all", label: "All" },
    { value: "1h", label: "1h" },
  ],
  value: "1h",
});
assertContains("single-select group is a radiogroup", single, 'role="radiogroup"');
assertContains("single-select group declares its variant", single, 'data-select="one"');
assertContains("single-row groups default to joined layout", single, 'data-layout="joined"');
assertContains("segments are radios", single, 'role="radio"');
assertContains(
  "the active segment is checked",
  single,
  'data-chip-value="1h" role="radio" aria-checked="true"',
);
assertContains(
  "the inactive segment is not",
  single,
  'data-chip-value="all" role="radio" aria-checked="false"',
);
// Roving tabindex: the group is one tab stop.
assertContains("the active segment is the tab stop", single, 'aria-checked="true" tabindex="0"');
assertContains("inactive segments are skipped", single, 'aria-checked="false" tabindex="-1"');
assertMissing("single-select does not use aria-pressed", single, "aria-pressed");

const multi = fc.groupHtml({
  key: "types",
  select: "many",
  layout: "wrap",
  label: "File type",
  options: [
    { value: "ft-md", label: "md", className: "chip-ft ft-md" },
    { value: "ft-code", label: "code", className: "chip-ft ft-code" },
  ],
  value: ["ft-md"],
});
assertContains("multi-select group is a plain group", multi, 'role="group"');
assertContains("multi-select group declares its variant", multi, 'data-select="many"');
assertContains("long multi-select groups declare wrapped layout", multi, 'data-layout="wrap"');
assertContains("selected chips are pressed", multi, 'data-chip-value="ft-md" aria-pressed="true"');
assertContains("unselected chips are not", multi, 'data-chip-value="ft-code" aria-pressed="false"');
assertContains("type chips carry their file-type class", multi, 'class="chip chip-ft ft-md"');
assertMissing("multi-select does not use radio semantics", multi, 'role="radio"');
// Every multi-select chip is independently reachable.
assertMissing("multi-select chips are not roving", multi, "tabindex");

const toggle = fc.toggleHtml({ key: "showIgnored", label: "Gitignored", pressed: false, badge: 3 });
assertContains("a toggle is a pressed button", toggle, 'aria-pressed="false"');
assertContains("a toggle can carry a count", toggle, '<span class="chip-badge">3</span>');
assertMissing(
  "a zero count renders nothing",
  fc.toggleHtml({ key: "showIgnored", label: "Gitignored", badge: 0 }),
  "chip-badge",
);

// Icon variant: every icon-only control in the app is the same
// control, so this renders on .icon-btn rather than as a pill with a
// glyph in it. A glyph says nothing to a screen reader, so the
// accessible name is not optional — it describes the action, not the
// icon.
const iconToggle = fc.toggleHtml({
  key: "drawer",
  icon: "<svg></svg>",
  className: "filter-drawer-toggle",
  pressed: true,
  badge: 2,
  ariaLabel: "Hide more filters (2 active)",
});
assertContains("the icon variant uses the icon-btn primitive", iconToggle, 'class="icon-btn');
assertMissing("the icon variant is not a pill", iconToggle, "chip-toggle");
assertContains("the icon variant carries its glyph", iconToggle, "<svg></svg>");
assertContains(
  "the icon variant names itself",
  iconToggle,
  'aria-label="Hide more filters (2 active)"',
);
// The badge rides outside the button: .icon-btn is a fixed box built
// to hold exactly one glyph.
assertContains(
  "the badge precedes the button",
  iconToggle,
  '<span class="chip-badge">2</span><button',
);

// Chips and groups are buttons, never hidden inputs — one state
// mechanism for anything that carries a filter *value*.
for (const [label, html] of [
  ["single-select", single],
  ["multi-select", multi],
  ["toggle", toggle],
]) {
  assertMissing(`${label} uses buttons, not checkboxes`, html, "<input");
}

// The one deliberate exception: a boolean whose polarity has to be
// legible. "Show ignored" with a tick says which way it points;
// a pressed pill reading "Gitignored" does not.
const check = fc.checkHtml({ key: "showIgnored", label: "Show ignored", checked: true });
assertContains("a check is a real checkbox", check, '<input type="checkbox"');
assertContains("it carries its key", check, 'data-chip-check="showIgnored"');
assertContains("a checked box reports it", check, "checked>");
assertContains("the label states the polarity", check, "<span>Show ignored</span>");
assertMissing(
  "an unchecked box has no checked attribute",
  fc.checkHtml({ key: "showIgnored", label: "Show ignored" }),
  "checked>",
);

// ── Multi-select dropdown ──────────────────────────────────────

const menuOptions = [
  { value: ".py", label: ".py", count: 156, icon: "<svg id='py'></svg>", iconClass: "ft-code" },
  { value: ".md", label: ".md", count: 33, icon: "<svg id='md'></svg>", iconClass: "ft-md" },
];
const menuClosed = fc.menuGroupHtml({
  key: "types",
  label: "File extension",
  options: menuOptions,
  value: null,
  anyLabel: "Any type",
  menuId: "m",
});
assertContains("closed menu reports its state", menuClosed, 'aria-expanded="false"');
// The trigger has to answer "what is filtered?" without being opened.
assertContains("no selection summarises as the any-label", menuClosed, ">Any type<");
assertContains("menu triggers use the shared disclosure chevron", menuClosed, menuChevron);
assertMissing("menu triggers do not use a text caret", menuClosed, "⌄");
assertContains("the any row is checked when nothing is picked", menuClosed, "data-chip-any");
assertContains("rows are checkbox menu items", menuClosed, 'role="menuitemcheckbox"');
assertContains("rows carry their tally", menuClosed, '<span class="chip-menu-count">156</span>');
// The icon identifies the type, the way it does on a tree row; the
// ft-* class on it supplies the subtype hue. The label stays plain so
// eight tinted rows do not fight the check mark for the eye.
assertContains("rows carry the file-type icon", menuClosed, "<svg id='py'></svg>");
assertContains("the icon carries the subtype hue", menuClosed, 'class="menu-item-icon ft-code"');
assertMissing("row labels are not tinted", menuClosed, 'class="menu-item-label ft-');

const menuOne = fc.menuGroupHtml({
  key: "types",
  label: "File extension",
  options: menuOptions,
  value: [".py"],
  anyLabel: "Any type",
  open: true,
  menuId: "m",
});
assertContains("open menu reports its state", menuOne, 'aria-expanded="true"');
assertContains("a single pick shows as itself", menuOne, ">.py<");
assertContains(
  "the picked row is checked",
  menuOne,
  'aria-checked="true" data-chip-key="types" data-chip-value=".py"',
);
// The any row goes unchecked once a real value is picked.
assertContains(
  "the any row clears",
  menuOne,
  'aria-checked="false" data-chip-key="types" data-chip-any',
);

const menuMany = fc.menuGroupHtml({
  key: "types",
  label: "File extension",
  options: menuOptions,
  value: [".py", ".md"],
  anyLabel: "Any type",
  menuId: "m",
});
// Several picks summarise as "first +n" rather than overflowing the
// 300px pane with a comma list.
assertContains("several picks summarise compactly", menuMany, ">.py +1<");

// Single-select dropdown: a scalar value and radio rows. Getting the
// role wrong is the same failure the chip groups guard against — the
// control would not say which kind it is.
const menuOne1 = fc.menuGroupHtml({
  key: "recency",
  select: "one",
  label: "Modified within",
  options: [
    { value: "live", label: "Live" },
    { value: "7d", label: "Past week" },
  ],
  value: "7d",
  anyLabel: "Any age",
  anyValue: "all",
  menuId: "r",
});
assertContains("single-select rows are radios", menuOne1, 'role="menuitemradio"');
assertMissing("single-select rows are not checkboxes", menuOne1, "menuitemcheckbox");
assertContains("the trigger names the choice", menuOne1, ">Past week<");
assertContains(
  "the chosen row is checked",
  menuOne1,
  'aria-checked="true" data-chip-key="recency" data-chip-value="7d"',
);

// The any-row is checked when the scalar sits at its default, so the
// menu never shows a dimension as constrained when it is not.
const menuOneAny = fc.menuGroupHtml({
  key: "recency",
  select: "one",
  label: "Modified within",
  options: [{ value: "live", label: "Live" }],
  value: "all",
  anyLabel: "Any age",
  anyValue: "all",
  menuId: "r",
});
assertContains("the default reads as the any-label", menuOneAny, ">Any age<");

// Age rows wear the tree's freshness ramp, so the menu is the legend
// for the colours in the listing below it.
const menuAged = fc.menuGroupHtml({
  key: "recency",
  select: "one",
  label: "Modified within",
  options: [
    {
      value: "live",
      label: "Live",
      ageClass: "age-live",
      tip: "Files modified in the past 90 seconds",
      count: 12,
    },
    { value: "1h", label: "Past hour", ageClass: "age-min" },
  ],
  value: "all",
  anyLabel: "Any age",
  anyValue: "all",
  menuId: "r",
});
assertContains(
  "age-menu Live uses the shared freshest colour",
  menuAged,
  "chip-menu-item age-live",
);
assertMissing("age rows use text color without a marker", menuAged, "file-age-marker");
assertContains(
  "live explains its exact cutoff",
  menuAged,
  'data-tip-text="Files modified in the past 90 seconds"',
);
assertContains("the hour row takes the under-an-hour colour", menuAged, "chip-menu-item age-min");
assertContains(
  "age rows carry the same tally as file-type rows",
  menuAged,
  '<span class="chip-menu-count">12</span>',
);
assertContains(
  "the any row is checked at the default",
  menuOneAny,
  'aria-checked="true" data-chip-key="recency" data-chip-any',
);

// ── Menu presets ───────────────────────────────────────────────

const PRESETS = [
  { id: "docs", label: "Docs", values: [".md", "readme"], count: 34 },
  { id: "code", label: "Code", values: [".py", ".ts"], count: 159 },
];
const menuPresets = fc.menuGroupHtml({
  key: "types",
  label: "File extension",
  options: menuOptions,
  presets: PRESETS,
  value: null,
  anyLabel: "Any type",
  menuId: "m",
});
assertContains("presets render above the raw list", menuPresets, 'data-chip-preset="docs"');
assertContains("presets are separated from the extensions", menuPresets, "menu-separator");
assertContains(
  "presets carry the same tally as extension rows",
  menuPresets,
  '<span class="chip-menu-count">34</span>',
);
// A half-covered group must not claim to be on.
assertContains(
  "an unselected preset is unchecked",
  menuPresets,
  'aria-checked="false" data-chip-key="types" data-chip-preset="docs"',
);

const menuHalfPreset = fc.menuGroupHtml({
  key: "types",
  label: "File extension",
  options: menuOptions,
  presets: PRESETS,
  value: [".md"],
  anyLabel: "Any type",
  menuId: "m",
});
assertContains(
  "a partially covered preset stays unchecked",
  menuHalfPreset,
  'aria-checked="false" data-chip-key="types" data-chip-preset="docs"',
);

const menuFullPreset = fc.menuGroupHtml({
  key: "types",
  label: "File extension",
  options: menuOptions,
  presets: PRESETS,
  value: [".md", "readme"],
  anyLabel: "Any type",
  menuId: "m",
});
assertContains(
  "a fully covered preset is checked",
  menuFullPreset,
  'aria-checked="true" data-chip-key="types" data-chip-preset="docs"',
);
// The user picked "Docs"; say Docs rather than ".md +1".
assertContains("an exact preset names the trigger", menuFullPreset, ">Docs<");

const menuSections = fc.menuGroupHtml({
  key: "types",
  label: "File type",
  options: menuOptions,
  presetSections: [
    { id: "categories", label: "Groups", presets: PRESETS },
    {
      id: "families",
      label: "Code",
      presets: [
        { id: "family:javascript", label: "JavaScript", values: [".js", ".mjs"], count: 10 },
      ],
    },
  ],
  value: [".js", ".mjs"],
  anyLabel: "Any type",
  menuId: "m",
});
assertContains(
  "preset sections keep category and family tiers distinct",
  menuSections,
  'data-chip-menu-section="categories"',
);
assertContains("preset sections have visible group labels", menuSections, ">Groups</div>");
assertContains("family sections have visible group labels", menuSections, ">Code</div>");
assertContains(
  "preset section labels name semantic groups",
  menuSections,
  'role="group" aria-labelledby="m-section-0"',
);
assertContains(
  "semantic families are selectable parents",
  menuSections,
  'data-chip-preset="family:javascript"',
);
// One group pattern (docs/design-system.md, "Groups in a Menu"): each section is a
// .menu-group named by its .group-heading, and draws its own divider, so the one
// .menu-separator left is the one before the raw rows, which no heading names.
assertContains(
  "a preset section is the menu group",
  menuSections,
  '<div class="menu-group" role="group" aria-labelledby="m-section-1" data-chip-menu-section="families">' +
    '<div class="group-heading" id="m-section-1">Code</div>',
);
assertEqual(
  "only the raw rows are set off by a separator",
  menuSections.split('class="menu-separator"').length - 1,
  1,
);

// ── Menu height ────────────────────────────────────────────────
// Up to 16 rows of the rendered row, and never past the window's bottom edge less 8 px.
// The numbers are the Files type menu's, measured in Chrome: 29 px rows, a 10 px frame,
// and the panel's top at 105 px under the filter row.
const menuGeometry = { rowHeight: 29, frame: 10, top: 105 };
assertEqual(
  "a tall window holds 16 rows",
  fc.menuMaxHeight({ ...menuGeometry, windowHeight: 900 }),
  16 * 29 + 10,
);
assertEqual(
  "a short window holds what fits above its edge",
  fc.menuMaxHeight({ ...menuGeometry, windowHeight: 420 }),
  420 - 8 - 105,
);
assertEqual(
  "the cap follows the rendered row",
  fc.menuMaxHeight({ ...menuGeometry, rowHeight: 24, windowHeight: 900 }),
  16 * 24 + 10,
);
assertEqual(
  "a menu with no room still shows one row",
  fc.menuMaxHeight({ ...menuGeometry, windowHeight: 120 }),
  29 + 10,
);

// Fitting reads that geometry from the rendered panel and sets max-height on every open
// menu; bind fits them again when the window resizes, and its disposer stops.
{
  const viewListeners = {};
  const view = {
    innerHeight: 420,
    getComputedStyle: () => ({
      paddingTop: "4px",
      paddingBottom: "4px",
      borderTopWidth: "1px",
      borderBottomWidth: "1px",
    }),
    addEventListener(type, listener) {
      viewListeners[type] = listener;
    },
    removeEventListener(type, listener) {
      if (viewListeners[type] === listener) {
        delete viewListeners[type];
      }
    },
  };
  const doc = { defaultView: view, addEventListener() {}, removeEventListener() {} };
  const panel = {
    ownerDocument: doc,
    style: {},
    getClientRects: () => [{}],
    getBoundingClientRect: () => ({ top: 105 }),
    querySelector: (selector) =>
      selector === ".menu-item" ? { getBoundingClientRect: () => ({ height: 29 }) } : null,
  };
  const empty = {
    ownerDocument: doc,
    style: {},
    getClientRects: () => [{}],
    querySelector: () => null,
  };
  // Under a hidden toolbar a panel has rows but no box: every rect reads zero.
  const hidden = {
    ownerDocument: doc,
    style: {},
    getClientRects: () => [],
    getBoundingClientRect: () => ({ top: 0 }),
    querySelector: (selector) =>
      selector === ".menu-item" ? { getBoundingClientRect: () => ({ height: 0 }) } : null,
  };
  let asked = "";
  const root = {
    ownerDocument: doc,
    addEventListener() {},
    removeEventListener() {},
    querySelectorAll(selector) {
      asked = selector;
      return [panel, empty, hidden];
    },
  };
  fc.fitOpenMenus(root);
  assertEqual(
    "fitting looks only at open menus",
    asked,
    '.chip-menu[aria-expanded="true"] > .chip-menu-panel',
  );
  assertEqual("an open menu is fitted to the room", panel.style.maxHeight, "307px");
  assertEqual("a menu with no rows is left alone", empty.style.maxHeight, undefined);
  assertEqual("a menu with no box is not fitted to nothing", hidden.style.maxHeight, undefined);
  const dispose = fc.bind(root, {});
  view.innerHeight = 900;
  viewListeners.resize?.();
  assertEqual("a resize fits the open menu again", panel.style.maxHeight, "474px");
  dispose();
  assertEqual("the disposer stops listening for resizes", viewListeners.resize, undefined);

  // A click on a trigger: the consumer renders the menu open, then bind fits it, so a
  // consumer that only binds still gets a fitted menu.
  const rootListeners = {};
  const order = [];
  const toggle = {
    getAttribute: (name) => (name === "data-chip-menu-toggle" ? "types" : null),
    closest: (selector) => (selector === ".chip-menu" ? { getAttribute: () => "false" } : null),
  };
  const clicked = {
    ownerDocument: doc,
    addEventListener(type, listener) {
      rootListeners[type] = listener;
    },
    removeEventListener() {},
    contains: () => true,
    querySelectorAll() {
      order.push("fit");
      return [];
    },
  };
  fc.bind(clicked, {
    onMenuToggle(key, open) {
      order.push(`toggle ${key} ${open}`);
    },
  });
  rootListeners.click({
    target: { closest: (selector) => (selector === "[data-chip-menu-toggle]" ? toggle : null) },
  });
  assertEqual("bind fits a menu after its consumer opens it", order, ["toggle types true", "fit"]);
}
assertContains("an exact family names the trigger", menuSections, ">JavaScript<");

const emptyPreset = fc.menuGroupHtml({
  key: "types",
  label: "File type",
  options: menuOptions,
  presets: [{ id: "other", label: "Other", values: [] }],
  value: [],
  anyLabel: "Any type",
  menuId: "m",
});
assertContains("an empty preset cannot claim the empty selection", emptyPreset, ">Any type<");

// ── Escaping ───────────────────────────────────────────────────

const hostile = fc.groupHtml({
  key: 'k"><script>',
  select: "one",
  label: '"><img>',
  options: [{ value: '"><b>', label: "<i>x</i>" }],
  value: null,
});
assertMissing("option labels are escaped", hostile, "<i>x</i>");
assertMissing("values cannot break out of the attribute", hostile, '"><b>');
assertMissing("group labels are escaped", hostile, '"><img>');

// An arrow key selects, and a consumer repaints the group from its state, which replaces
// the element holding focus. Focus follows the chosen value, or the next key does nothing.
{
  const listeners = {};
  let focused = null;
  const group = {};
  const chip = (value) => {
    const element = {
      isConnected: true,
      getAttribute: (name) =>
        name === "data-chip-key" ? "measure" : name === "data-chip-value" ? value : null,
      focus() {
        focused = element;
      },
      closest: (selector) =>
        selector.startsWith(".chip[") ? element : selector.startsWith(".chip-group") ? group : null,
    };
    return element;
  };
  let chips = [chip("files"), chip("size")];
  group.querySelectorAll = () => chips;
  const root = {
    addEventListener(type, listener) {
      listeners[type] = listener;
    },
    removeEventListener() {},
    contains: () => true,
    ownerDocument: null,
    querySelectorAll: () => chips,
  };
  const chosen = [];
  fc.bind(root, {
    onChange(_key, value) {
      chosen.push(value);
      for (const old of chips) {
        old.isConnected = false;
      }
      chips = [chip("files"), chip("size")];
    },
  });
  // A key held with Command, Control, or Option is the browser's: Command-Left and
  // Alt-Left go back, and Command-Up scrolls to the top. A segmented group's arrows and a
  // menu's rows move only unmodified.
  const menuRow = {
    focus() {
      focused = menuRow;
    },
    closest: (selector) =>
      selector === ".chip-menu-panel"
        ? { querySelectorAll: () => [menuRow, menuRow] }
        : selector === ".chip-menu-item"
          ? menuRow
          : null,
  };
  const swallowed = [];
  for (const [target, keys] of [
    [chips[0], ["ArrowLeft", "ArrowRight", "Home", "End", "r"]],
    [menuRow, ["ArrowDown", "ArrowUp", "Home", "End", "r"]],
  ]) {
    for (const key of keys) {
      for (const modifier of ["metaKey", "ctrlKey", "altKey"]) {
        let prevented = false;
        listeners.keydown({
          key,
          [modifier]: true,
          target,
          preventDefault() {
            prevented = true;
          },
        });
        if (prevented) {
          swallowed.push(`${target === menuRow ? "menu" : "group"} ${modifier} ${key}`);
        }
      }
    }
  }
  if (swallowed.length > 0 || chosen.length > 0) {
    failures.push(
      `a modified key is the browser's: ${swallowed.join(", ")}; chose ${chosen.join()}`,
    );
  }
  listeners.keydown({ key: "ArrowRight", target: chips[0], preventDefault() {} });
  if (chosen.join() !== "size") {
    failures.push(`an arrow key selects: ${chosen.join()}`);
  }
  if (focused !== chips[1]) {
    failures.push("focus follows the chosen value across a repaint");
  }
}

// ── A segmented group wider than its line ──────────────────────
// In a navigation toolbar a joined group that its line cannot hold takes the cluster
// layout. Whether it fits is pure; the widths it is asked about are layout, measured in
// Chrome (tests/test_github_pulls_stacks_chrome.py).

assertEqual(
  "a joined group fits a line exactly its width",
  fc.joinedGroupFits({ joined: 193, room: 193 }),
  true,
);
assertEqual(
  "a joined group a 64th of a pixel wider than its line does not fit",
  fc.joinedGroupFits({ joined: 193.015625, room: 193 }),
  false,
);

// Bound in a navigation toolbar, the groups are fitted at once, on a change to the row's
// text before the browser paints it, and on a change of size in the next frame, never in
// the ResizeObserver's own callback. The disposer takes the observers and any waiting
// frame down, and nothing fires after it.
{
  const log = [];
  /** @type {{resize: any, mutation: any}} */
  const observers = { resize: null, mutation: null };
  const frames = new Map();
  let nextFrame = 1;
  class FakeResizeObserver {
    constructor(callback) {
      this.callback = callback;
      this.targets = new Set();
      observers.resize = this;
    }
    observe(target) {
      this.targets.add(target);
    }
    unobserve(target) {
      this.targets.delete(target);
    }
    disconnect() {
      this.targets.clear();
      log.push("resize observer disconnected");
    }
  }
  class FakeMutationObserver {
    constructor(callback) {
      this.callback = callback;
      this.watching = false;
      /** @type {Array<[unknown, unknown]>} */
      this.targets = [];
      observers.mutation = this;
    }
    observe(target, options) {
      this.watching = true;
      this.targets.push([target, options]);
    }
    takeRecords() {
      return [];
    }
    disconnect() {
      this.watching = false;
      log.push("mutation observer disconnected");
    }
  }
  const view = {
    ResizeObserver: FakeResizeObserver,
    MutationObserver: FakeMutationObserver,
    requestAnimationFrame(callback) {
      const id = nextFrame;
      nextFrame += 1;
      frames.set(id, callback);
      return id;
    },
    cancelAnimationFrame(id) {
      if (frames.delete(id)) {
        log.push("frame cancelled");
      }
    },
    addEventListener() {},
    removeEventListener() {},
  };
  const doc = { defaultView: view, addEventListener() {}, removeEventListener() {} };
  let fitted = 0;
  const rootIn = (toolbar) => ({
    ownerDocument: doc,
    addEventListener() {},
    removeEventListener() {},
    closest: (selector) => (selector === "[data-nav-toolbar]" ? toolbar : null),
    querySelectorAll(selector) {
      if (selector === '.chip-group[data-layout="joined"]') {
        fitted += 1;
      }
      return [];
    },
  });
  const runFrames = () => {
    const waiting = [...frames.values()];
    frames.clear();
    for (const callback of waiting) {
      callback();
    }
  };

  fc.bind(rootIn(null), {})();
  assertEqual(
    "outside a navigation toolbar, nothing is observed or fitted",
    [observers, fitted],
    [{ resize: null, mutation: null }, 0],
  );

  const toolbar = {};
  const root = rootIn(toolbar);
  const dispose = fc.bind(root, {});
  assertEqual("bound in a toolbar, the groups are fitted at once", fitted, 1);
  assertEqual("the row is watched for its size", observers.resize.targets.has(root), true);
  assertEqual("and for changes to its text", observers.mutation.watching, true);
  assertEqual(
    "and its toolbar for being shown, so a stale layout is fitted before it paints",
    observers.mutation.targets.map(([target, options]) => [
      target === root ? "row" : target === toolbar ? "toolbar" : "other",
      options,
    ]),
    [
      ["row", { childList: true, characterData: true, subtree: true }],
      ["toolbar", { attributes: true, attributeFilter: ["hidden"] }],
    ],
  );
  observers.resize.callback([]);
  observers.resize.callback([]);
  assertEqual(
    "a change of size waits for one next frame, not the observer's own callback",
    [fitted, frames.size],
    [1, 1],
  );
  runFrames();
  assertEqual("the frame fits the groups", fitted, 2);
  observers.mutation.callback([]);
  assertEqual("a change to the row's text is fitted before the browser paints it", fitted, 3);
  observers.resize.callback([]);
  dispose();
  assertEqual("the disposer takes the observers and the waiting frame down", log, [
    "resize observer disconnected",
    "mutation observer disconnected",
    "frame cancelled",
  ]);
  observers.resize.callback([]);
  observers.mutation.callback([]);
  runFrames();
  assertEqual("after the disposer nothing fires", [fitted, frames.size], [3, 0]);

  // A row that is its own toolbar, as the Files bar is, is one node to observe, and a
  // second `observe` of a node replaces the first's options: it takes both in one.
  const own = rootIn(null);
  own.closest = (selector) => (selector === "[data-nav-toolbar]" ? own : null);
  fc.bind(own, {})();
  assertEqual(
    "a row that is its own toolbar is watched for its text and for being shown at once",
    observers.mutation.targets.map(([target, options]) => [target === own, options]),
    [
      [
        true,
        {
          childList: true,
          characterData: true,
          subtree: true,
          attributes: true,
          attributeFilter: ["hidden"],
        },
      ],
    ],
  );
}

if (failures.length > 0) {
  process.stderr.write(`${failures.join("\n")}\n`);
  process.exit(1);
}

process.stdout.write("OK filter controls\n");

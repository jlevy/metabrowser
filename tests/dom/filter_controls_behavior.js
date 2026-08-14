// Behavioural checks for static/filter_controls.js: the selection
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
  path.join(repoRoot, "src/metabrowser/static/filter_controls.js"),
  "utf-8",
);
vm.runInContext(source, sandbox, { filename: "filter_controls.js" });

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
      ageClass: "age-sec",
      title: "Files modified in the past 90 seconds",
      count: 12,
    },
    { value: "1h", label: "Past hour", ageClass: "age-min" },
  ],
  value: "all",
  anyLabel: "Any age",
  anyValue: "all",
  menuId: "r",
});
assertContains("live takes the under-a-minute colour", menuAged, "chip-menu-item age-sec");
assertContains(
  "live explains its exact cutoff",
  menuAged,
  'title="Files modified in the past 90 seconds"',
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
    { id: "categories", presets: PRESETS },
    {
      id: "families",
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
assertContains(
  "semantic families are selectable parents",
  menuSections,
  'data-chip-preset="family:javascript"',
);
assertContains("an exact family names the trigger", menuSections, ">JavaScript<");

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

if (failures.length > 0) {
  process.stderr.write(`${failures.join("\n")}\n`);
  process.exit(1);
}

process.stdout.write("OK filter controls\n");

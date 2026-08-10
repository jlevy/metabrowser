// Behavioural checks for static/filter_controls.js: the selection
// semantics that separate single- from multi-select, and the markup
// contract the stylesheet keys off.

const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const repoRoot = path.resolve(__dirname, "../..");

const sandbox = { console: { warn() {} }, JSON, String, Array, Object };
sandbox.window = sandbox;
sandbox.globalThis = sandbox;
vm.createContext(sandbox);

const source = fs.readFileSync(
  path.join(repoRoot, "src/metabrowser/static/filter_controls.js"),
  "utf-8",
);
vm.runInContext(source, sandbox, { filename: "filter_controls.js" });

const fc = sandbox.MetabrowserFilterControls;
const failures = [];

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
  label: "File type",
  options: [
    { value: "ft-md", label: "md", className: "chip-ft ft-md" },
    { value: "ft-code", label: "code", className: "chip-ft ft-code" },
  ],
  value: ["ft-md"],
});
assertContains("multi-select group is a plain group", multi, 'role="group"');
assertContains("multi-select group declares its variant", multi, 'data-select="many"');
assertContains("selected chips are pressed", multi, 'data-chip-value="ft-md" aria-pressed="true"');
assertContains("unselected chips are not", multi, 'data-chip-value="ft-code" aria-pressed="false"');
assertContains("type chips carry their file-type class", multi, 'class="chip chip-ft ft-md"');
assertMissing("multi-select does not use radio semantics", multi, 'role="radio"');
// Every multi-select chip is independently reachable.
assertMissing("multi-select chips are not roving", multi, "tabindex");

const toggle = fc.toggleHtml({ key: "drawer", label: "More", pressed: false, badge: 3 });
assertContains("a toggle is a pressed button", toggle, 'aria-pressed="false"');
assertContains("a toggle can carry a count", toggle, '<span class="chip-badge">3</span>');
assertMissing(
  "a zero count renders nothing",
  fc.toggleHtml({ key: "drawer", label: "More", badge: 0 }),
  "chip-badge",
);

// No hidden inputs: one state mechanism across the whole family.
for (const [label, html] of [
  ["single-select", single],
  ["multi-select", multi],
  ["toggle", toggle],
]) {
  assertMissing(`${label} uses buttons, not checkboxes`, html, "<input");
}

// ── Multi-select dropdown ──────────────────────────────────────

const menuOptions = [
  { value: ".py", label: ".py", count: 156, className: "chip-ft ft-code" },
  { value: ".md", label: ".md", count: 33, className: "chip-ft ft-md" },
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
assertContains("the any row is checked when nothing is picked", menuClosed, "data-chip-any");
assertContains("rows are checkbox menu items", menuClosed, 'role="menuitemcheckbox"');
assertContains("rows carry their tally", menuClosed, '<span class="chip-menu-count">156</span>');
assertContains("rows keep their file-type hue", menuClosed, "chip-ft ft-code");

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

const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const repoRoot = path.resolve(__dirname, "../..");

class FakeElement {
  constructor(tagName) {
    this.tagName = tagName.toUpperCase();
    this.attributes = new Map();
    this.children = [];
    this.isContentEditable = false;
    this.textContent = "";
  }

  append(...children) {
    this.children.push(...children);
  }

  setAttribute(name, value) {
    this.attributes.set(name, String(value));
  }

  getAttribute(name) {
    return this.attributes.get(name) ?? null;
  }
}

class FakeDocument {
  constructor() {
    this.listeners = new Map();
  }

  addEventListener(type, listener, options) {
    const values = this.listeners.get(type) || [];
    values.push({ listener, options });
    this.listeners.set(type, values);
  }

  removeEventListener(type, listener) {
    this.listeners.set(
      type,
      (this.listeners.get(type) || []).filter((entry) => entry.listener !== listener),
    );
  }

  createElement(tagName) {
    return new FakeElement(tagName);
  }

  dispatch(event) {
    for (const entry of this.listeners.get("keydown") || []) {
      entry.listener(event);
    }
  }
}

function keyboardEvent(key, values = {}) {
  return {
    altKey: false,
    ctrlKey: false,
    defaultPrevented: false,
    isComposing: false,
    key,
    metaKey: false,
    prevented: false,
    repeat: false,
    shiftKey: false,
    target: new FakeElement("div"),
    preventDefault() {
      this.defaultPrevented = true;
      this.prevented = true;
    },
    ...values,
  };
}

const document = new FakeDocument();
const sandbox = { document };
sandbox.window = sandbox;
sandbox.globalThis = sandbox;
vm.createContext(sandbox);
vm.runInContext(
  fs.readFileSync(path.join(repoRoot, "src/metabrowser/static/keyboard-shortcuts.js"), "utf-8"),
  sandbox,
  { filename: "keyboard-shortcuts.js" },
);

const failures = [];
function check(label, condition, detail = "") {
  if (!condition) {
    failures.push(`${label}${detail ? `: ${detail}` : ""}`);
  }
}

function equal(label, actual, expected) {
  check(label, JSON.stringify(actual) === JSON.stringify(expected), JSON.stringify(actual));
}

function rejects(label, work) {
  let rejected = false;
  try {
    work();
  } catch (error) {
    rejected = error?.name === "TypeError";
  }
  check(label, rejected);
}

function command(overrides = {}) {
  return {
    bindings: [{ key: "?" }],
    copy: {
      action: "Help",
      description: "Show keyboard shortcuts and application help.",
      hint: "Help",
    },
    group: "help",
    handler: () => true,
    id: "help.open",
    order: 10,
    scope: "global",
    surfaces: { help: "always", nav: "always" },
    ...overrides,
  };
}

const shortcuts = sandbox.MetabrowserKeyboardShortcuts;
check("global installed", Boolean(shortcuts));

const question = shortcuts.describeBindings([{ key: "?" }]);
equal("question visible", question.visible, ["?"]);
equal("question spoken", question.spoken, "Question mark");
equal("question aria omitted", question.ariaKeyshortcuts, "");

const alternatives = shortcuts.describeBindings([{ key: "t" }, { key: "/" }]);
equal("alternative key labels", alternatives.visible, ["T", "/"]);
equal("alternative spoken phrase", alternatives.spoken, "T or slash");
equal("representable aria alias retained", alternatives.ariaKeyshortcuts, "T");

const digit = shortcuts.describeBindings([{ key: "1" }]);
equal(
  "a digit is its own label, spoken name, and ARIA token",
  [digit.visible, digit.spoken, digit.ariaKeyshortcuts],
  [["1"], "1", "1"],
);

// No shortcut uses a modifier, so no binding may state a policy for one, Shift
// included. The old chords and Shift policies are the cases that would return.
for (const [label, binding] of [
  ["Ctrl+F", { key: "f", modifiers: { control: "require" } }],
  ["Command+1", { key: "1", modifiers: { meta: "require" } }],
  ["Alt+Enter", { key: "Enter", modifiers: { alt: "require" } }],
  ["Shift+J", { key: "j", modifiers: { shift: "require" } }],
  ["Shift+Up", { key: "ArrowUp", modifiers: { shift: "require" } }],
  ["a ? that allows Shift", { key: "?", modifiers: { shift: "allow" } }],
  ["a / that forbids Shift", { key: "/", modifiers: { shift: "forbid" } }],
  ["an empty policy", { key: "k", modifiers: {} }],
]) {
  rejects(`the formatter rejects ${label}`, () => shortcuts.describeBindings([binding]));
}

// Every key the vocabulary can bind renders without a modifier in any form.
for (const key of [
  ...Object.keys(shortcuts.KEY_DEFINITIONS),
  ..."abcdefghijklmnopqrstuvwxyz",
  ..."0123456789",
]) {
  const rendered = JSON.stringify(shortcuts.describeBindings([{ key }]));
  check(
    `${JSON.stringify(key)} names no modifier`,
    !/[⇧⌘+]|Shift|Command|Meta|Control|Ctrl|Alt/.test(rendered),
    rendered,
  );
}

// The single-key entry point names a key that is not a binding: the Shift in
// Help's closing note and a badge's keycap. Shift is a name only there.
equal("Shift reads as its name", shortcuts.describeKey("Shift"), {
  aria: "Shift",
  spoken: "Shift",
  visible: "Shift",
});
equal("a single letter renders as its capital", shortcuts.describeKey("t").visible, "T");
equal("a single arrow uses the formatter's glyph", shortcuts.describeKey("ArrowDown").visible, "↓");
rejects("Shift is not a binding key", () => shortcuts.describeBindings([{ key: "Shift" }]));
rejects("the single-key names stay a closed vocabulary", () => shortcuts.describeKey("Control"));
const noteHost = new FakeElement("p");
const shiftKeycap = shortcuts.appendKey(document, noteHost, "Shift");
check(
  "a single key renders as one keycap",
  noteHost.children.length === 1 &&
    noteHost.children[0] === shiftKeycap &&
    shiftKeycap.tagName === "KBD" &&
    shiftKeycap.className === "kbd" &&
    shiftKeycap.textContent === "Shift",
);

equal(
  "the main tabs work outside text fields",
  shortcuts.GROUP_DEFINITIONS["main-tabs"].context,
  "Available outside text fields.",
);

// The tree's movement shape: an arrow with a letter alias. The arrow leads, so
// a surface with room for one key names the arrow.
const movement = shortcuts.describeBindings([{ key: "ArrowDown" }, { key: "j" }]);
equal("arrow and letter labels", movement.visible, ["↓", "J"]);
equal("arrow and letter spoken phrase", movement.spoken, "Down arrow or J");
equal("arrow and letter aria", movement.ariaKeyshortcuts, "ArrowDown J");
equal("arrow is the preferred key", movement.preferred.ariaKeyshortcuts, "ArrowDown");

// Shift never changes what a key means.
const field = new FakeElement("input");
for (const [label, event, binding] of [
  ["a capital without Shift, as with Caps Lock, is its letter", keyboardEvent("J"), { key: "j" }],
  ["a letter typed with Shift is its letter", keyboardEvent("J", { shiftKey: true }), { key: "j" }],
  [
    "a letter typed with Shift under Caps Lock is its letter",
    keyboardEvent("j", { shiftKey: true }),
    { key: "j" },
  ],
  [
    "Shift with a named key outside a text field is that key",
    keyboardEvent("ArrowDown", { shiftKey: true }),
    { key: "ArrowDown" },
  ],
  [
    "punctuation typed with Shift is that character",
    keyboardEvent("?", { code: "Slash", shiftKey: true }),
    { key: "?" },
  ],
  [
    "a slash typed with Shift, as on a German layout, is a slash",
    keyboardEvent("/", { code: "Digit7", shiftKey: true }),
    { key: "/" },
  ],
  ["a Numpad digit matches by key", keyboardEvent("1", { code: "Numpad1" }), { key: "1" }],
  [
    "a named key in a text field without Shift still matches",
    keyboardEvent("ArrowDown", { target: field }),
    { key: "ArrowDown" },
  ],
]) {
  check(label, shortcuts.eventMatchesBinding(event, binding));
}
for (const modifier of ["altKey", "ctrlKey", "metaKey"]) {
  for (const [key, binding] of [
    ["j", { key: "j" }],
    ["1", { key: "1" }],
    ["?", { key: "?" }],
    ["ArrowDown", { key: "ArrowDown" }],
  ]) {
    check(
      `${modifier} with ${key} never matches`,
      !shortcuts.eventMatchesBinding(keyboardEvent(key, { [modifier]: true }), binding),
    );
  }
  check(
    `${modifier} disqualifies the physical digit row too`,
    !shortcuts.eventMatchesBinding(
      keyboardEvent("!", { code: "Digit1", [modifier]: true, shiftKey: true }),
      { key: "1" },
      { physical: true },
    ),
  );
}
check(
  "? and / stay distinct on the key they share",
  !shortcuts.eventMatchesBinding(keyboardEvent("?", { code: "Slash", shiftKey: true }), {
    key: "/",
  }),
);
check(
  "Shift with a selection key in a text field belongs to the field",
  !shortcuts.eventMatchesBinding(keyboardEvent("ArrowDown", { shiftKey: true, target: field }), {
    key: "ArrowDown",
  }),
);
for (const key of ["Enter", "Escape"]) {
  check(
    `Shift+${key} in a text field is ${key}, since it selects no text`,
    shortcuts.eventMatchesBinding(keyboardEvent(key, { shiftKey: true, target: field }), { key }),
  );
}
for (const key of ["ArrowLeft", "ArrowRight", "ArrowUp", "Home", "End"]) {
  check(
    `Shift+${key} in a text field belongs to the field`,
    !shortcuts.eventMatchesBinding(keyboardEvent(key, { shiftKey: true, target: field }), { key }),
  );
}
// The physical digit row is a second pass the dispatcher takes only when the
// typed character matched nothing; matching by key never reads the code.
check(
  "matching by key never reads the code",
  !shortcuts.eventMatchesBinding(keyboardEvent("!", { code: "Digit1", shiftKey: true }), {
    key: "1",
  }),
);
check(
  "the physical pass matches the digit row",
  shortcuts.eventMatchesBinding(
    keyboardEvent("!", { code: "Digit1", shiftKey: true }),
    { key: "1" },
    { physical: true },
  ),
);
check(
  "the physical pass leaves a typed digit to its key",
  !shortcuts.eventMatchesBinding(
    keyboardEvent("5", { code: "Digit2" }),
    { key: "2" },
    { physical: true },
  ),
);
check(
  "the physical pass is for digits only",
  !shortcuts.eventMatchesBinding(
    keyboardEvent("J", { code: "KeyJ" }),
    { key: "j" },
    { physical: true },
  ),
);

const bindingHost = new FakeElement("span");
shortcuts.appendBinding(document, bindingHost, alternatives);
check(
  "binding renderer uses keycaps",
  bindingHost.children.filter((node) => node.tagName === "KBD").length === 2,
);
check(
  "binding renderer provides one spoken phrase",
  bindingHost.children.some((node) => node.textContent === "T or slash"),
);
equal(
  "alternatives join with one hidden or, and nothing joins keys within one",
  bindingHost.children
    .filter((node) => node.tagName === "SPAN" && node.className !== "visually-hidden")
    .map((node) => [node.textContent, node.getAttribute("aria-hidden")]),
  [["or", "true"]],
);
const singleHost = new FakeElement("span");
shortcuts.appendBinding(document, singleHost, question);
equal(
  "a single key is one keycap that names itself",
  singleHost.children.map((node) => [
    node.tagName,
    node.textContent,
    node.getAttribute("aria-hidden"),
  ]),
  [["KBD", "?", null]],
);

const registry = shortcuts.create({ document });
check("one capture dispatcher", document.listeners.get("keydown").length === 1);
check("dispatcher uses capture", document.listeners.get("keydown")[0].options === true);

let helpCalls = 0;
const unregisterHelp = registry.register(
  command({
    control: Object.freeze({ connect: () => () => {} }),
    handler: () => {
      helpCalls += 1;
      return true;
    },
  }),
);
const helpEvent = keyboardEvent("?", { shiftKey: true });
document.dispatch(helpEvent);
check("matching global command runs", helpCalls === 1);
check("handled command prevents browser behavior", helpEvent.prevented);

const editable = new FakeElement("input");
document.dispatch(keyboardEvent("?", { shiftKey: true, target: editable }));
check("editable target preserves native behavior", helpCalls === 1);
document.dispatch(keyboardEvent("?", { isComposing: true, shiftKey: true }));
document.dispatch(keyboardEvent("?", { ctrlKey: true, shiftKey: true }));
document.dispatch(keyboardEvent("?", { defaultPrevented: true, shiftKey: true }));
check("composition modifiers and handled events are ignored", helpCalls === 1);

let movementCalls = 0;
registry.register(
  command({
    bindings: [{ key: "ArrowDown" }],
    copy: {
      action: "Next item",
      description: "Move to the next visible item.",
      hint: "Move",
    },
    group: "navigation",
    handler: () => {
      movementCalls += 1;
      return true;
    },
    id: "tree.next",
    order: 20,
    repeat: true,
    scope: "tree",
    surfaces: { help: "always", nav: "active" },
  }),
);
registry.register(
  command({
    bindings: [{ key: "ArrowUp" }],
    copy: {
      action: "Previous item",
      description: "Move to the previous visible item.",
      hint: "Move",
    },
    group: "navigation",
    handler: () => true,
    id: "tree.previous",
    order: 10,
    repeat: true,
    scope: "tree",
    surfaces: { help: "always", nav: "active" },
  }),
);
const deactivateTree = registry.activateScope("tree");
document.dispatch(keyboardEvent("ArrowDown", { repeat: true }));
check("declared repeats run in active scope", movementCalls === 1);

let closeCalls = 0;
registry.register(
  command({
    bindings: [{ key: "Escape" }],
    copy: {
      action: "Close Help",
      description: "Close Help and return to the previous location.",
      hint: "Close",
    },
    handler: () => {
      closeCalls += 1;
      return true;
    },
    id: "help.close",
    order: 10,
    scope: "help",
    surfaces: { help: "always", nav: "active" },
  }),
);
const deactivateHelp = registry.activateScope("help", { exclusive: true });
const blockedTree = keyboardEvent("ArrowDown");
document.dispatch(blockedTree);
check("exclusive modal blocks lower scopes", movementCalls === 1 && !blockedTree.prevented);
document.dispatch(keyboardEvent("Escape"));
check("exclusive modal command runs", closeCalls === 1);

const helpSnapshot = registry.snapshot("help", { includeInactive: true });
equal(
  "help groups follow canonical order",
  helpSnapshot.map((group) => group.id),
  ["navigation", "help"],
);
check("presentations are frozen", Object.isFrozen(helpSnapshot[0].commands[0]));
check(
  "control binding is surface owned",
  registry.present("help.open").control.connect instanceof Function,
);
equal(
  "nav hides inactive contextual hints",
  registry.snapshot("nav").map((group) => group.id),
  ["help"],
);

let duplicateRejected = false;
try {
  registry.register(command({ id: "help.other" }));
} catch (error) {
  duplicateRejected = error?.name === "TypeError";
}
check("duplicate scope binding rejected", duplicateRejected);

let incompleteRejected = false;
try {
  registry.register(command({ id: "bad", copy: { action: "Bad", description: "Bad." } }));
} catch (error) {
  incompleteRejected = error?.name === "TypeError";
}
check("incomplete presented copy rejected", incompleteRejected);

for (const binding of [
  { key: "f", modifiers: { control: "require" } },
  { key: "ArrowUp", modifiers: { shift: "require" } },
]) {
  rejects(`registration rejects ${JSON.stringify(binding)}`, () =>
    registry.register(command({ bindings: [binding], id: "chord" })),
  );
}
check("a rejected binding registers nothing", registry.present("chord") === null);

deactivateHelp();
equal(
  "contextual nav returns after modal closes",
  registry.snapshot("nav").map((group) => group.id),
  ["navigation", "help"],
);
equal(
  "adjacent compact hints coalesce in explicit command order",
  registry.snapshot("nav")[0].commands[0].commandIds,
  ["tree.previous", "tree.next"],
);
deactivateTree();
unregisterHelp();
registry.dispose();
check("dispose removes dispatcher", document.listeners.get("keydown").length === 0);

// Keyboard layouts: one event can name two keys, so the registry matches the
// typed character first and the physical digit row only when that matched
// nothing and the character is not itself a digit.
const layoutDocument = new FakeDocument();
const layouts = shortcuts.create({ document: layoutDocument });
const ran = [];
const record = (id) => () => {
  ran.push(id);
  return true;
};
for (const key of ["1", "2", "3", "7"]) {
  layouts.register(
    command({
      bindings: [{ key }],
      group: "main-tabs",
      handler: record(key),
      id: `digit.${key}`,
      order: Number(key),
      surfaces: { help: "always" },
    }),
  );
}
layouts.register(
  command({
    bindings: [{ key: "t" }, { key: "/" }],
    group: "anywhere",
    handler: record("quick"),
    id: "quick-file.open",
    order: 20,
  }),
);
layouts.register(command({ group: "anywhere", handler: record("help") }));
function typed(label, values, expected) {
  ran.length = 0;
  const event = keyboardEvent(values.key, values);
  layoutDocument.dispatch(event);
  equal(label, [ran.slice(), event.prevented], [expected ? [expected] : [], Boolean(expected)]);
}
typed("US Shift+1 types ! and is 1", { code: "Digit1", key: "!", shiftKey: true }, "1");
typed("AZERTY's unshifted 1 key types & and is 1", { code: "Digit1", key: "&" }, "1");
typed("AZERTY's unshifted 2 key types é and is 2", { code: "Digit2", key: "é" }, "2");
typed("AZERTY's Shift+1 types 1 and is 1", { code: "Digit1", key: "1", shiftKey: true }, "1");
typed(
  "German Shift+7 types / and is Quick Search, never 7",
  { code: "Digit7", key: "/", shiftKey: true },
  "quick",
);
typed("US Shift+/ types ? and is Help", { code: "Slash", key: "?", shiftKey: true }, "help");
typed(
  "a remapped digit row runs the digit it types",
  { code: "Digit2", key: "7", shiftKey: true },
  "7",
);
typed(
  "a typed digit with no binding never falls back to its key's position",
  { code: "Digit2", key: "5" },
  null,
);
typed("a Numpad digit runs by key", { code: "Numpad3", key: "3" }, "3");
typed("Shift+T is T", { code: "KeyT", key: "T", shiftKey: true }, "quick");
typed("Command+1 is the browser's", { code: "Digit1", key: "1", metaKey: true }, null);
typed("Ctrl+1 is the browser's", { code: "Digit1", ctrlKey: true, key: "1" }, null);
typed(
  "AltGr punctuation stays outside the rule",
  { altKey: true, code: "Digit7", ctrlKey: true, key: "/" },
  null,
);

// A command that opts into a text field still leaves Shift with a selection key
// to the field, as Quick Search's result keys leave Shift+Arrow to text
// selection.
layouts.register(
  command({
    allowInEditable: true,
    bindings: [{ key: "ArrowDown" }],
    group: "quick-file",
    handler: record("next result"),
    id: "results.next",
    repeat: true,
    scope: "results",
    surfaces: { help: "always" },
  }),
);
const closeResults = layouts.activateScope("results", { exclusive: true });
typed(
  "Shift+Down in the query selects text",
  { key: "ArrowDown", shiftKey: true, target: new FakeElement("input") },
  null,
);
typed("Down in the query moves the result", { key: "ArrowDown", target: field }, "next result");
typed(
  "Shift+Down outside a text field is Down",
  { key: "ArrowDown", shiftKey: true },
  "next result",
);
closeResults();

// The permanent view-tabs scope sits below global, so a letter both use keeps
// one meaning at a time: the stack's P while a stack is open, the Preview
// tab's P otherwise.
let stackOpen = false;
layouts.register(
  command({
    available: () => stackOpen,
    bindings: [{ key: "p" }],
    group: "pull-stack",
    handler: record("stack"),
    id: "pulls.stack.base",
    surfaces: { help: "always" },
  }),
);
let viewTabRegistered = false;
try {
  layouts.register(
    command({
      bindings: [{ key: "p" }],
      group: "navigation",
      handler: record("preview"),
      id: "view-tabs.p",
      scope: "view-tabs",
      surfaces: { help: "active" },
    }),
  );
  viewTabRegistered = true;
} catch (error) {
  check("view tab registration", false, String(error));
}
check("a global P and a view-tabs P register together", viewTabRegistered);
typed("P reaches the view tab while no stack is open", { key: "p" }, "preview");
typed("Shift+P reaches the view tab too", { key: "P", shiftKey: true }, "preview");
stackOpen = true;
typed("the global P outranks the view tab while a stack is open", { key: "p" }, "stack");
// A permanent scope is always active in its fixed place, so activating one, which
// would lift view-tabs above global and hand the stack's P to the view tab, is refused.
for (const permanent of ["global", "view-tabs"]) {
  rejects(`activating the permanent ${permanent} scope is refused`, () =>
    layouts.activateScope(permanent),
  );
}
typed("the global P still outranks the view tab after the refusal", { key: "p" }, "stack");
stackOpen = false;
rejects("two P bindings in one scope still fail", () =>
  layouts.register(
    command({
      bindings: [{ key: "P" }],
      group: "pull-stack",
      id: "pulls.stack.other",
    }),
  ),
);
check(
  "a view-tabs command can be invoked",
  layouts.invoke("view-tabs.p") && ran.at(-1) === "preview",
);
check(
  "a view-tabs command is active in snapshots",
  layouts
    .snapshot("help")
    .flatMap((group) => group.commands)
    .some((presented) => presented.id === "view-tabs.p"),
);
const closeLayoutHelp = layouts.activateScope("help", { exclusive: true });
typed("an exclusive modal silences the view tabs", { key: "p" }, null);
check(
  "an exclusive modal hides the view tabs from snapshots",
  !layouts
    .snapshot("help")
    .flatMap((group) => group.commands)
    .some((presented) => presented.id === "view-tabs.p"),
);
closeLayoutHelp();
layouts.dispose();

// A batch coalesces the publications it contains into one, at its outermost end.
const batched = shortcuts.create({ document: new FakeDocument() });
const published = [];
batched.subscribe((event) => published.push(JSON.parse(JSON.stringify(event))));
const batchResult = batched.batch(() => {
  const releaseA = batched.register(command({ bindings: [{ key: "a" }], id: "a" }));
  batched.register(command({ bindings: [{ key: "b" }], id: "b" }));
  releaseA();
  check("a batch publishes nothing while it runs", published.length === 0);
  return "done";
});
equal("a batch returns its work's result", batchResult, "done");
equal("a batch publishes once", published, [{ kind: "batch", kinds: ["registration"] }]);
published.length = 0;
batched.batch(() =>
  batched.batch(() => {
    batched.register(command({ bindings: [{ key: "c" }], id: "c" }));
    batched.activateScope("tree");
  }),
);
equal("nested batches publish once, at the outermost end", published, [
  { kind: "batch", kinds: ["registration", "scope"] },
]);
published.length = 0;
batched.batch(() => {});
equal("an empty batch publishes nothing", published, []);
batched.batch(() => batched.register(command({ bindings: [{ key: "d" }], id: "d" })));
equal("a batch of one publishes that event", published, [{ commandId: "d", kind: "registration" }]);
published.length = 0;
rejects("a batch rethrows its work's error", () =>
  batched.batch(() => {
    batched.register(command({ bindings: [{ key: "e" }], id: "e" }));
    throw new TypeError("stopped");
  }),
);
equal("a failed batch still publishes what it changed", published, [
  { commandId: "e", kind: "registration" },
]);
batched.dispose();

// ── Badge targets ────────────────────────────────────────────────
// A command's targets are the elements its key acts on. The registry reads their
// liveness at dispatch, gives them `aria-keyshortcuts`, and badges the first live one
// while revealed. These run on a stand-in tree, because liveness is a property of it.
{
  const { FakeDocument, element, keyEvent } = require("./key-reveal-dom.js");
  const tree = new FakeDocument();
  const targetRegistry = shortcuts.create({ document: tree });
  const events = [];
  targetRegistry.subscribe((event) => events.push(JSON.parse(JSON.stringify(event))));
  const ran = [];
  function tab(id, label) {
    return element(tree, "button", { class: "tab-btn", "data-tab": id }, label);
  }
  const bar = element(tree, "div", { class: "tab-bar" });
  const tree1 = tab("tree", "Tree");
  const source = tab("source", "Source");
  bar.append(tree1, source);
  tree.body.append(bar);
  targetRegistry.register(
    command({
      bindings: [{ key: "r" }],
      copy: { action: "Tree", description: "Show the Tree view.", hint: "Tree" },
      group: "view-tabs",
      handler: (context) => {
        ran.push(context.target?.dataset.tab ?? null);
        return true;
      },
      id: "view-tabs.r",
      scope: "view-tabs",
      surfaces: { help: "always", reveal: "always" },
      targeted: true,
    }),
  );
  const press = (key, init = {}) => {
    const event = keyEvent("keydown", key, { target: tree.body, ...init });
    tree.dispatchEvent(event);
    return event.defaultPrevented;
  };
  const liveIds = () =>
    targetRegistry
      .snapshot("reveal")
      .flatMap((group) => group.commands)
      .map((presented) => presented.id);

  check("a targeted command with no target leaves the key to the browser", !press("r"));
  equal("a targeted command with no target is not live", liveIds(), []);
  equal("nothing ran without a target", ran, []);

  events.length = 0;
  const handle = targetRegistry.attachTarget("view-tabs.r", tree1);
  equal("attaching publishes a target event", events, [
    { commandId: "view-tabs.r", kind: "target" },
  ]);
  equal("an attached target carries the key", tree1.getAttribute("aria-keyshortcuts"), "R");
  check("a live target takes the key", press("R", { shiftKey: true }));
  equal("the handler is told which target it serves", ran, ["tree"]);
  equal("a live targeted command is in a live snapshot", liveIds(), ["view-tabs.r"]);
  check("a target at rest carries no badge", tree1.querySelector(".kbd-badge") === null);

  // Each way a target stops being live: hidden by an ancestor's display, disabled,
  // inside an inert subtree, and disconnected.
  ran.length = 0;
  bar.style.display = "none";
  check("a target under display: none does not take the key", !press("r"));
  bar.style.display = "";
  tree1.disabled = true;
  check("a disabled target does not take the key", !press("r"));
  tree1.disabled = false;
  bar.inert = true;
  check("a target inside an inert subtree does not take the key", !press("r"));
  // checkVisibility() ignores inert, so the inert walk runs on that path too.
  tree1.checkVisibility = () => true;
  check("an inert target stays dead where checkVisibility() exists", !press("r"));
  bar.inert = false;
  tree1.checkVisibility = () => false;
  check("checkVisibility() decides where the browser has it", !press("r"));
  delete tree1.checkVisibility;
  tree1.style.visibility = "hidden";
  check("a target computing visibility: hidden does not take the key", !press("r"));
  tree1.style.visibility = "";
  equal("no dead target ran the command", ran, []);

  // The first live target in document order wins, and gets the badge.
  const staged = element(tree, "div", { class: "preview-file-stage", inert: true });
  const stagedTab = tab("tree", "Tree");
  staged.append(stagedTab);
  tree.body.append(staged);
  const stagedHandle = targetRegistry.attachTarget("view-tabs.r", stagedTab);
  const second = element(tree, "div", {}, tab("raw", "Raw JSON"));
  tree.body.insertBefore(second, bar);
  const earlier = targetRegistry.attachTarget("view-tabs.r", second.firstElementChild);
  check("the first live target in document order runs", press("r") && ran.at(-1) === "raw");
  check(
    "a target in the inert stage never counts beside the visible ones",
    targetRegistry.liveTarget("view-tabs.r") === second.firstElementChild,
  );
  earlier.detach();
  earlier.detach();
  check(
    "a detached target loses its key, and detaching twice is harmless",
    !second.firstElementChild.hasAttribute("aria-keyshortcuts") &&
      targetRegistry.liveTarget("view-tabs.r") === tree1,
  );

  // While revealed a badge mounts at once, follows a retarget, and goes on release.
  events.length = 0;
  targetRegistry.setRevealed(true);
  equal("revealing publishes a reveal event", events, [{ kind: "reveal" }]);
  const badge = tree1.querySelector(".kbd-badge");
  check(
    "revealing badges the live target with a hidden keycap",
    badge?.tagName === "KBD" &&
      badge.className === "kbd kbd-badge" &&
      badge.getAttribute("aria-hidden") === "true" &&
      badge.textContent === "R" &&
      tree1.classList.contains("kbd-badge-host"),
  );
  check("a dead target gets no badge", stagedTab.querySelector(".kbd-badge") === null);
  const rebuilt = tab("tree", "Tree");
  bar.replaceChildren(rebuilt, source);
  handle.retarget(rebuilt);
  check(
    "a retarget during a reveal moves the badge at once",
    rebuilt.querySelector(".kbd-badge") !== null &&
      rebuilt.getAttribute("aria-keyshortcuts") === "R",
  );
  check(
    "the old element keeps neither badge nor attribute",
    !tree1.hasAttribute("aria-keyshortcuts") && tree1.querySelector(".kbd-badge") === null,
  );
  bar.style.display = "none";
  events.length = 0;
  targetRegistry.refreshBadges();
  check("a refresh after a key reads liveness again", rebuilt.querySelector(".kbd-badge") === null);
  equal("a refresh publishes a dispatch event", events, [{ kind: "dispatch" }]);
  bar.style.display = "";
  targetRegistry.refreshBadges();
  check("a target shown again gets its badge back", rebuilt.querySelector(".kbd-badge") !== null);
  const late = tab("late", "Late");
  bar.append(late);
  targetRegistry.register(
    command({
      bindings: [{ key: "l" }],
      copy: { action: "Late", description: "Show the Late view.", hint: "Late" },
      group: "view-tabs",
      id: "view-tabs.l",
      scope: "view-tabs",
      surfaces: { help: "always" },
      targeted: true,
    }),
  );
  const lateHandle = targetRegistry.attachTarget("view-tabs.l", late);
  check(
    "attaching during a reveal mounts a badge at once",
    late.querySelector(".kbd-badge") !== null,
  );
  lateHandle.detach();
  check("detaching removes the badge", late.querySelector(".kbd-badge") === null);

  // Beside placement: the badge sits in the nearest anchor, measured from it.
  const header = element(tree, "div", { class: "file-header", "data-kbd-badge-anchor": true });
  const copy = element(tree, "button", { class: "icon-btn file-header-copy" });
  const clip = element(tree, "span", { class: "file-header-path" }, copy);
  header.append(clip);
  tree.body.append(header);
  header.rect = { left: 100, top: 40, width: 600, height: 32 };
  copy.rect = { left: 300, top: 44, width: 24, height: 24 };
  targetRegistry.register(
    command({
      bindings: [{ key: "y" }],
      copy: { action: "Copy", description: "Copy the path.", hint: "Copy" },
      group: "controls",
      id: "header.copy",
      targeted: true,
    }),
  );
  targetRegistry.attachTarget("header.copy", copy, { placement: "beside" });
  const besideBadge = header.querySelector(".kbd-badge");
  check(
    "a beside badge mounts in the anchor, outside the clipping row",
    besideBadge?.parentNode === header && copy.querySelector(".kbd-badge") === null,
  );
  equal(
    "a beside badge is placed at the target's inline end and center",
    [
      besideBadge?.dataset.kbdPlacement,
      besideBadge?.style.getPropertyValue("--kbd-badge-inline"),
      besideBadge?.style.getPropertyValue("--kbd-badge-block"),
    ],
    ["beside", "224px", "16px"],
  );
  check("a beside target does not become a badge host", !copy.classList.contains("kbd-badge-host"));
  rejects("an unknown placement is refused", () =>
    targetRegistry.attachTarget("header.copy", copy, { placement: "over" }),
  );
  rejects("a target must be an element", () => targetRegistry.attachTarget("header.copy", null));
  rejects("targeted must be a boolean", () =>
    targetRegistry.register(command({ bindings: [{ key: "q" }], id: "q", targeted: "yes" })),
  );

  // An exclusive modal hides every badge behind it; closing it brings them back.
  const closeModal = targetRegistry.activateScope("help", { exclusive: true });
  check(
    "an exclusive scope hides the badges",
    tree.body.querySelectorAll(".kbd-badge").length === 0,
  );
  closeModal();
  check("closing it brings them back", tree.body.querySelectorAll(".kbd-badge").length === 2);

  targetRegistry.setRevealed(false);
  check(
    "ending the reveal removes every badge",
    tree.body.querySelectorAll(".kbd-badge").length === 0,
  );
  check("ending the reveal leaves no host class", !rebuilt.classList.contains("kbd-badge-host"));
  check(
    "ending the reveal keeps the attributes",
    rebuilt.getAttribute("aria-keyshortcuts") === "R",
  );

  // The key observer hears each key once its handler has returned, and each keyup.
  const heard = [];
  let handlerReturned = false;
  targetRegistry.register(
    command({
      bindings: [{ key: "z" }],
      handler: () => {
        handlerReturned = true;
        return true;
      },
      id: "z",
    }),
  );
  const stopObserving = targetRegistry.observeKeys((event, handled) => {
    heard.push(`${event.type} ${event.key} ${handled} ${handlerReturned}`);
  });
  check(
    "the registry adds a keyup listener only while an observer listens",
    tree.listeners.some((entry) => entry.type === "keyup" && entry.capture),
  );
  press("z");
  press("Shift", { shiftKey: true });
  tree.dispatchEvent(keyEvent("keyup", "Shift", { target: tree.body }));
  equal("observers hear keys after dispatch, and keyups unhandled", heard, [
    "keydown z true true",
    "keydown Shift false true",
    "keyup Shift false true",
  ]);
  stopObserving();
  check(
    "the keyup listener goes with the last observer",
    !tree.listeners.some((entry) => entry.type === "keyup"),
  );

  stagedHandle.detach();
  targetRegistry.dispose();
  check("disposal leaves no attribute", !rebuilt.hasAttribute("aria-keyshortcuts"));
}

if (failures.length > 0) {
  console.error(failures.join("\n"));
  process.exitCode = 1;
} else {
  console.log("OK keyboard shortcuts");
}

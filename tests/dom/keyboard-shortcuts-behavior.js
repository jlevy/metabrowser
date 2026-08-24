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

function command(overrides = {}) {
  return {
    bindings: [{ key: "?", modifiers: { shift: "allow" } }],
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

const question = shortcuts.describeBindings([{ key: "?", modifiers: { shift: "allow" } }]);
equal("question visible", question.visible, [{ keys: ["?"], separators: [] }]);
equal("question spoken", question.spoken, "Question mark");
equal("question aria omitted", question.ariaKeyshortcuts, "");

const alternatives = shortcuts.describeBindings([
  { key: "t" },
  { key: "/", modifiers: { shift: "forbid" } },
]);
equal("alternative key labels", alternatives.visible, [
  { keys: ["T"], separators: [] },
  { keys: ["/"], separators: [] },
]);
equal("alternative spoken phrase", alternatives.spoken, "T or slash");
equal("representable aria alias retained", alternatives.ariaKeyshortcuts, "T");

const chord = shortcuts.describeBindings([
  { key: "f", modifiers: { control: "require", shift: "forbid" } },
]);
equal("chord labels", chord.visible, [{ keys: ["Ctrl", "F"], separators: ["+"] }]);
equal("chord spoken", chord.spoken, "Control plus F");
equal("chord aria", chord.ariaKeyshortcuts, "Control+F");

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

if (failures.length > 0) {
  console.error(failures.join("\n"));
  process.exitCode = 1;
} else {
  console.log("OK keyboard shortcuts");
}

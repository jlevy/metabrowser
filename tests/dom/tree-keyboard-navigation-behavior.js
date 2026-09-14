const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const repoRoot = path.resolve(__dirname, "../..");

class FakeClassList {
  constructor(element) {
    this.element = element;
  }

  add(...names) {
    const values = new Set(this.element.className.split(/\s+/).filter(Boolean));
    for (const name of names) {
      values.add(name);
    }
    this.element.className = Array.from(values).join(" ");
  }

  contains(name) {
    return this.element.className.split(/\s+/).includes(name);
  }

  remove(...names) {
    const removed = new Set(names);
    this.element.className = this.element.className
      .split(/\s+/)
      .filter((name) => name && !removed.has(name))
      .join(" ");
  }

  toggle(name, force) {
    const enabled = force === undefined ? !this.contains(name) : Boolean(force);
    if (enabled) {
      this.add(name);
    } else {
      this.remove(name);
    }
    return enabled;
  }
}

class FakeElement {
  constructor(tagName, document) {
    this.tagName = tagName.toUpperCase();
    this.ownerDocument = document;
    this.parentElement = null;
    this.children = [];
    this.attributes = new Map();
    this.listeners = new Map();
    this.className = "";
    this.classList = new FakeClassList(this);
    this.dataset = {};
    this.hidden = false;
    this.id = "";
    this.isContentEditable = false;
    this.style = { display: "" };
    this.tabIndex = -1;
  }

  get isConnected() {
    return this.ownerDocument.body.contains(this);
  }

  get nextElementSibling() {
    if (!this.parentElement) {
      return null;
    }
    const index = this.parentElement.children.indexOf(this);
    return this.parentElement.children[index + 1] || null;
  }

  get previousElementSibling() {
    if (!this.parentElement) {
      return null;
    }
    const index = this.parentElement.children.indexOf(this);
    return index > 0 ? this.parentElement.children[index - 1] : null;
  }

  append(...children) {
    for (const child of children) {
      child.parentElement = this;
      this.children.push(child);
    }
  }

  remove() {
    if (!this.parentElement) {
      return;
    }
    const index = this.parentElement.children.indexOf(this);
    this.parentElement.children.splice(index, 1);
    this.parentElement = null;
  }

  contains(candidate) {
    return candidate === this || this.children.some((child) => child.contains(candidate));
  }

  matches(selector) {
    if (
      selector === '[role="tree"]' ||
      selector === '[role="treeitem"]' ||
      selector === '[role="group"]'
    ) {
      return this.getAttribute("role") === selector.slice(7, -2);
    }
    return selector.startsWith(".") && this.classList.contains(selector.slice(1));
  }

  closest(selector) {
    let current = this;
    while (current) {
      if (current.matches(selector)) {
        return current;
      }
      current = current.parentElement;
    }
    return null;
  }

  querySelectorAll(selector) {
    const matches = [];
    function visit(node) {
      for (const child of node.children) {
        if (child.matches(selector)) {
          matches.push(child);
        }
        visit(child);
      }
    }
    visit(this);
    return matches;
  }

  setAttribute(name, value) {
    const text = String(value);
    this.attributes.set(name, text);
    if (name === "id") {
      this.id = text;
    } else if (name === "tabindex") {
      this.tabIndex = Number(text);
    } else if (name.startsWith("data-")) {
      const key = name.slice(5).replace(/-([a-z])/g, (_match, letter) => letter.toUpperCase());
      this.dataset[key] = text;
    }
  }

  getAttribute(name) {
    return this.attributes.get(name) ?? null;
  }

  hasAttribute(name) {
    return this.attributes.has(name);
  }

  removeAttribute(name) {
    this.attributes.delete(name);
  }

  addEventListener(type, listener) {
    const listeners = this.listeners.get(type) || [];
    listeners.push(listener);
    this.listeners.set(type, listeners);
  }

  removeEventListener(type, listener) {
    const listeners = this.listeners.get(type) || [];
    this.listeners.set(
      type,
      listeners.filter((candidate) => candidate !== listener),
    );
  }

  dispatch(type, values = {}) {
    const event = { currentTarget: this, target: this, type, ...values };
    for (const listener of this.listeners.get(type) || []) {
      listener(event);
    }
  }

  focus() {
    this.ownerDocument.activeElement = this;
  }
}

class FakeDocument {
  constructor() {
    this.listeners = new Map();
    this.body = new FakeElement("body", this);
    this.activeElement = this.body;
  }

  createElement(tagName) {
    return new FakeElement(tagName, this);
  }

  addEventListener(type, listener, options) {
    const listeners = this.listeners.get(type) || [];
    listeners.push({ listener, options });
    this.listeners.set(type, listeners);
  }

  removeEventListener(type, listener) {
    const listeners = this.listeners.get(type) || [];
    this.listeners.set(
      type,
      listeners.filter((entry) => entry.listener !== listener),
    );
  }

  dispatch(event) {
    for (const entry of this.listeners.get("keydown") || []) {
      entry.listener(event);
    }
  }
}

function keyboardEvent(key, target, values = {}) {
  return {
    altKey: false,
    ctrlKey: false,
    defaultPrevented: false,
    isComposing: false,
    key,
    metaKey: false,
    repeat: false,
    shiftKey: false,
    target,
    preventDefault() {
      this.defaultPrevented = true;
    },
    ...values,
  };
}

function treeItem(document, kind, identity, pathName = identity) {
  const item = document.createElement("div");
  item.className = `tree-item tree-${kind}`;
  item.setAttribute("role", "treeitem");
  item.setAttribute("data-tree-kind", kind);
  item.setAttribute("data-tree-id", identity);
  item.setAttribute("data-path", pathName);
  if (kind === "file" || kind === "symlink") {
    item.setAttribute("aria-selected", "false");
  }
  return item;
}

function group(document, id) {
  const value = document.createElement("div");
  value.className = "tree-children";
  value.setAttribute("id", id);
  value.setAttribute("role", "group");
  return value;
}

const document = new FakeDocument();
const sandbox = { document, queueMicrotask };
sandbox.window = sandbox;
sandbox.globalThis = sandbox;
vm.createContext(sandbox);
for (const fileName of ["keyboard-shortcuts.js", "tree-keyboard-navigation.js"]) {
  vm.runInContext(
    fs.readFileSync(path.join(repoRoot, "src/metabrowser/static", fileName), "utf-8"),
    sandbox,
    { filename: fileName },
  );
}

const failures = [];
function check(label, condition, detail = "") {
  if (!condition) {
    failures.push(`${label}${detail ? `: ${detail}` : ""}`);
  }
}

function equal(label, actual, expected) {
  check(label, JSON.stringify(actual) === JSON.stringify(expected), JSON.stringify(actual));
}

const container = document.createElement("nav");
const root = document.createElement("div");
root.setAttribute("role", "tree");
root.setAttribute("aria-label", "Files");
container.append(root);
document.body.append(container);

const folder = treeItem(document, "folder", "folder:src", "src");
folder.classList.add("collapsed");
folder.setAttribute("aria-expanded", "false");
const children = group(document, "tree-group-src");
children.classList.add("tree-children-collapsed");
const first = treeItem(document, "file", "file:src/a.js", "src/a.js");
const second = treeItem(document, "file", "file:src/b.js", "src/b.js");
children.append(first, second);
const empty = treeItem(document, "folder", "folder:empty", "empty");
empty.classList.add("tree-item-empty", "collapsed");
const outside = treeItem(document, "file", "file:README.md", "README.md");
outside.classList.add("selected");
const page = treeItem(document, "page", "page:root:2", "");
root.append(folder, children, empty, outside, page);

const shortcuts = sandbox.MetabrowserKeyboardShortcuts.create({ document });
const expansionCalls = [];
const activationCalls = [];
const navigationCalls = [];
const navigator = sandbox.MetabrowserTreeKeyboardNavigation.create({
  activate(row) {
    activationCalls.push(row.dataset.treeId);
    return row;
  },
  container,
  document,
  navigate(row) {
    navigationCalls.push(row.dataset.treeId);
  },
  setFolderExpanded(row, expanded) {
    expansionCalls.push([row.dataset.treeId, expanded]);
    const childGroup = row.nextElementSibling;
    row.setAttribute("aria-expanded", String(expanded));
    row.classList.toggle("expanded", expanded);
    row.classList.toggle("collapsed", !expanded);
    if (childGroup?.getAttribute("role") === "group") {
      childGroup.classList.toggle("tree-children-collapsed", !expanded);
    }
  },
  shortcuts,
});

check("tree navigator global installed", Boolean(sandbox.MetabrowserTreeKeyboardNavigation));
equal(
  "durable row identities include row kind",
  sandbox.MetabrowserTreeKeyboardNavigation.rowIdentity(folder),
  "folder:src",
);
check("adjacent group is owned by its folder", folder.getAttribute("aria-owns") === children.id);
equal(
  "root metadata is repaired",
  [
    folder.getAttribute("aria-level"),
    folder.getAttribute("aria-posinset"),
    folder.getAttribute("aria-setsize"),
  ],
  ["1", "1", "4"],
);
equal(
  "child metadata is repaired",
  [
    first.getAttribute("aria-level"),
    first.getAttribute("aria-posinset"),
    first.getAttribute("aria-setsize"),
  ],
  ["2", "1", "2"],
);
check(
  "known-empty folder is an end node",
  !empty.hasAttribute("aria-expanded") && !empty.hasAttribute("aria-owns"),
);
check("selected visible leaf starts as the roving anchor", outside.tabIndex === 0);
check(
  "exactly one visible row is tabbable",
  [folder, empty, outside, page].filter((row) => row.tabIndex === 0).length === 1,
);

folder.focus();
container.dispatch("focusin", { target: folder });
// Arrows in a file tree are the one thing a reader will try unprompted, so
// advertising them costs strip space and teaches nothing. The commands stay
// registered, stay dispatched, and stay listed in Help — they are simply not
// worth a permanent line at the bottom of the navigation pane.
check("tree commands stay out of the compact strip", shortcuts.snapshot("nav").length === 0);
check(
  "tree commands remain discoverable in Help",
  shortcuts
    .snapshot("help")
    .flatMap((group) => group.commands)
    .filter((command) => command.id.startsWith("tree.")).length === 7,
);

let event = keyboardEvent("ArrowDown", folder, { repeat: true });
document.dispatch(event);
check("repeat movement is handled", event.defaultPrevented && document.activeElement === empty);
check("moving opens the row it lands on", navigationCalls.at(-1) === "folder:empty");

event = keyboardEvent("Home", empty);
document.dispatch(event);
check("Home focuses the first visible row", document.activeElement === folder);
check("Home opens the row it lands on", navigationCalls.at(-1) === "folder:src");

// Skimming past the last row must not reopen it: the clamp lands on the row
// that already has focus, and reopening would restart its live stream.
folder.focus();
container.dispatch("focusin", { target: folder });
event = keyboardEvent("ArrowUp", folder);
document.dispatch(event);
check(
  "an arrow clamped at the edge does not reopen the focused row",
  navigationCalls.at(-1) === "folder:src" &&
    navigationCalls.filter((id) => id === "folder:src").length === 1,
);

// A Mac laptop has no Home or End key, so without these the tree has no
// jump-to-edge reachable on the keyboard most readers actually have.
event = keyboardEvent("ArrowDown", folder, { shiftKey: true });
document.dispatch(event);
check(
  "Shift+Down jumps to the last visible row",
  event.defaultPrevented && document.activeElement === page,
);
event = keyboardEvent("ArrowUp", page, { shiftKey: true });
document.dispatch(event);
check(
  "Shift+Up jumps to the first visible row",
  event.defaultPrevented && document.activeElement === folder,
);
// Plain arrows forbid modifiers, so the jump bindings cannot shadow movement.
event = keyboardEvent("ArrowDown", folder);
document.dispatch(event);
check("unmodified Down still steps by one", document.activeElement === empty);
// Hand the folder back to the expansion checks below in the state they expect.
folder.focus();
container.dispatch("focusin", { target: folder });

// J and K are Down and Up on the home row: the same commands, so they repeat,
// open the row they land on, and are listed beside the arrows in Help.
event = keyboardEvent("j", folder, { repeat: true });
document.dispatch(event);
check(
  "repeated j steps down like Down",
  event.defaultPrevented && document.activeElement === empty,
);
check("j opens the row it lands on", navigationCalls.at(-1) === "folder:empty");
const beforeLetterGuards = navigationCalls.length;
for (const modifier of ["altKey", "ctrlKey", "metaKey", "shiftKey"]) {
  for (const letter of ["j", "k"]) {
    const key = modifier === "shiftKey" ? letter.toUpperCase() : letter;
    event = keyboardEvent(key, empty, { [modifier]: true });
    document.dispatch(event);
    check(`${modifier} with ${key} does not move`, !event.defaultPrevented);
  }
}
// A letter from a text field is typing, even while the tree scope is active.
const editableTargets = ["input", "textarea", "select", "div"].map((tagName) => {
  const element = document.createElement(tagName);
  element.isContentEditable = tagName === "div";
  return element;
});
for (const target of editableTargets) {
  for (const key of ["j", "k"]) {
    event = keyboardEvent(key, target);
    document.dispatch(event);
    check(`${key} in an editable ${target.tagName} does not move`, !event.defaultPrevented);
  }
}
check(
  "guarded J and K leave focus and the open row alone",
  document.activeElement === empty && navigationCalls.length === beforeLetterGuards,
);
event = keyboardEvent("k", empty, { repeat: true });
document.dispatch(event);
check("repeated k steps up like Up", event.defaultPrevented && document.activeElement === folder);
check("k opens the row it lands on", navigationCalls.at(-1) === "folder:src");
equal(
  "Next item presents Down or J",
  [
    shortcuts.present("tree.next").bindings.visible.map((alternative) => alternative.keys),
    shortcuts.present("tree.next").bindings.spoken,
    shortcuts.present("tree.next").bindings.ariaKeyshortcuts,
  ],
  [[["↓"], ["J"]], "Down arrow or J", "ArrowDown J"],
);
equal(
  "Previous item presents Up or K",
  [
    shortcuts.present("tree.previous").bindings.visible.map((alternative) => alternative.keys),
    shortcuts.present("tree.previous").bindings.spoken,
    shortcuts.present("tree.previous").bindings.ariaKeyshortcuts,
  ],
  [[["↑"], ["K"]], "Up arrow or K", "ArrowUp K"],
);
// J and K step; they are not also first and last.
equal(
  "first and last keep only their jump bindings",
  [
    shortcuts.present("tree.first").bindings.ariaKeyshortcuts,
    shortcuts.present("tree.last").bindings.ariaKeyshortcuts,
  ],
  ["Shift+ArrowUp Home", "Shift+ArrowDown End"],
);

const beforeExpand = navigationCalls.length;
event = keyboardEvent("ArrowRight", folder);
document.dispatch(event);
check(
  "Right expands a collapsed folder without moving",
  folder.getAttribute("aria-expanded") === "true",
);
check("expanded children join visible order", navigator.visibleRows().includes(first));
check("expanding in place opens nothing new", navigationCalls.length === beforeExpand);

event = keyboardEvent("ArrowRight", folder);
document.dispatch(event);
check("Right enters an expanded folder", document.activeElement === first);
check("entering a folder opens its first child", navigationCalls.at(-1) === "file:src/a.js");

event = keyboardEvent("ArrowLeft", first);
document.dispatch(event);
check("Left from a child focuses its parent", document.activeElement === folder);
check("returning to the parent opens it", navigationCalls.at(-1) === "folder:src");

event = keyboardEvent("ArrowLeft", folder);
document.dispatch(event);
check("Left collapses an expanded folder", folder.getAttribute("aria-expanded") === "false");

empty.focus();
container.dispatch("focusin", { target: empty });
event = keyboardEvent("ArrowRight", empty);
document.dispatch(event);
check("Right on a known-empty folder is handled without expansion", event.defaultPrevented);
check(
  "known-empty folder never delegates expansion",
  !expansionCalls.some(([id]) => id === "folder:empty"),
);

outside.focus();
container.dispatch("focusin", { target: outside });
const beforeActivate = navigationCalls.length;
event = keyboardEvent("Enter", outside);
document.dispatch(event);
check(
  "Enter dispatches activation for the focused row",
  event.defaultPrevented && activationCalls.at(-1) === "file:README.md",
);
// Activation and opening are separate callbacks: arrows opened this row on the
// way in, so Enter must not route through navigation a second time. What
// activation *means* per row type is the shell's decision, not this module's.
check("Enter never opens", navigationCalls.length === beforeActivate);
const activationCount = activationCalls.length;
event = keyboardEvent("Enter", outside, { repeat: true });
document.dispatch(event);
check(
  "activation ignores repeated keydown",
  !event.defaultPrevented && activationCalls.length === activationCount,
);

page.focus();
container.dispatch("focusin", { target: page });
event = keyboardEvent(" ", page);
document.dispatch(event);
check(
  "Space activates pagination",
  event.defaultPrevented && activationCalls.at(-1) === "page:root:2",
);

folder.setAttribute("aria-expanded", "true");
folder.classList.add("expanded");
folder.classList.remove("collapsed");
children.classList.remove("tree-children-collapsed");
navigator.synchronize();
first.focus();
container.dispatch("focusin", { target: first });
const removalMutation = navigator.prepareForMutation();
// An aggregate update can synchronize while the row's exit animation is
// running. The removal retains its own snapshot for the eventual DOM change.
navigator.synchronize();
first.remove();
navigator.synchronize(removalMutation);
check(
  "removal repairs focus to the nearest sibling",
  document.activeElement === second,
  document.activeElement?.dataset?.treeId || document.activeElement?.tagName,
);

second.classList.add("tree-item-filter-hidden");
navigator.synchronize();
check("filtering repairs focus to the parent", document.activeElement === folder);

container.dispatch("click", { target: outside });
check("pointer use updates the future tab stop", outside.tabIndex === 0);
// Focus is still on the folder, so a repair sees a focused row that differs
// from the durable anchor. The anchor must win; adopting focus is only for a
// layer that has no anchor yet.
check("the pointer anchor and the focused row differ", document.activeElement === folder);
navigator.synchronize();
check("a repair keeps the durable anchor over the focused row", outside.tabIndex === 0);

// Tree commands are Help-only, so the compact strip cannot show whether the
// tree scope is active. A movement key that goes unhandled can.
document.body.focus();
container.dispatch("focusout", { relatedTarget: document.body, target: outside });
navigator.synchronize();
event = keyboardEvent("ArrowDown", document.body);
document.dispatch(event);
check(
  "a repair with focus outside the tree leaves tree commands inactive",
  !event.defaultPrevented,
);
event = keyboardEvent("PageDown", document.body);
document.dispatch(event);
check("native main-pane scrolling keys remain untouched", !event.defaultPrevented);

navigator.dispose();
check("dispose removes tree commands", shortcuts.present("tree.next") === null);
// The layer's own async continuations can still call synchronize after
// disposal. With a row focused, that repair must not reactivate a tree scope
// that nothing will ever deactivate.
outside.focus();
const postDisposeScopes = [];
const unsubscribePostDispose = shortcuts.subscribe((change) => {
  if (change.kind === "scope") {
    postDisposeScopes.push(change.scope);
  }
});
navigator.synchronize();
check(
  "synchronize after dispose leaves the tree scope inactive",
  postDisposeScopes.length === 0,
  postDisposeScopes.join(","),
);
unsubscribePostDispose();
shortcuts.dispose();

// A reader can click a row before the keyboard layer attaches. That focus
// happened before the focusin listener existed, so attaching must adopt it:
// the focused row stays focused, becomes the roving anchor, and the tree
// scope is active so movement keys work on the first press.
for (const [label, focusedKey] of [
  ["selected row", "selected"],
  ["other row", "other"],
]) {
  const earlyDocument = new FakeDocument();
  const earlyContainer = earlyDocument.createElement("nav");
  const earlyRoot = earlyDocument.createElement("div");
  earlyRoot.setAttribute("role", "tree");
  earlyContainer.append(earlyRoot);
  earlyDocument.body.append(earlyContainer);
  const earlyFirst = treeItem(earlyDocument, "file", "file:a.md", "a.md");
  const earlyOther = treeItem(earlyDocument, "file", "file:b.md", "b.md");
  const earlySelected = treeItem(earlyDocument, "file", "file:c.md", "c.md");
  const earlyLast = treeItem(earlyDocument, "file", "file:d.md", "d.md");
  earlySelected.classList.add("selected");
  earlyRoot.append(earlyFirst, earlyOther, earlySelected, earlyLast);
  const clicked = focusedKey === "selected" ? earlySelected : earlyOther;
  clicked.focus();

  const earlyShortcuts = sandbox.MetabrowserKeyboardShortcuts.create({ document: earlyDocument });
  const earlyNavigations = [];
  const earlyNavigator = sandbox.MetabrowserTreeKeyboardNavigation.create({
    activate: (row) => row,
    container: earlyContainer,
    document: earlyDocument,
    navigate(row) {
      earlyNavigations.push(row.dataset.treeId);
    },
    setFolderExpanded() {},
    shortcuts: earlyShortcuts,
  });
  check(
    `early focus on the ${label} is kept when the keyboard layer attaches`,
    earlyDocument.activeElement === clicked && clicked.tabIndex === 0,
    earlyDocument.activeElement?.dataset?.treeId,
  );
  equal(`attaching after an early click on the ${label} opens nothing`, earlyNavigations, []);
  const earlyEvent = keyboardEvent("ArrowDown", clicked);
  earlyDocument.dispatch(earlyEvent);
  const expectedNext = focusedKey === "selected" ? earlyLast : earlySelected;
  check(
    `Down works on the first press after an early click on the ${label}`,
    earlyEvent.defaultPrevented && earlyDocument.activeElement === expectedNext,
    `${earlyEvent.defaultPrevented}/${earlyDocument.activeElement?.dataset?.treeId}`,
  );
  equal(
    `the first Down after an early click on the ${label} opens only the next row`,
    earlyNavigations,
    [expectedNext.dataset.treeId],
  );
  earlyNavigator.dispose();
  earlyShortcuts.dispose();
}

if (failures.length > 0) {
  console.error(failures.join("\n"));
  process.exitCode = 1;
} else {
  console.log("OK tree keyboard navigation behavior");
}

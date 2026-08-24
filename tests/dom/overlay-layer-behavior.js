const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const repoRoot = path.resolve(__dirname, "../..");

class FakeElement {
  constructor(tagName, document) {
    this.tagName = tagName.toUpperCase();
    this.ownerDocument = document;
    this.parentNode = null;
    this.children = [];
    this.attributes = new Map();
    this.listeners = new Map();
    this.className = "";
    this.disabled = false;
    this.hidden = false;
    this.id = "";
    this.inert = false;
    this.isContentEditable = false;
    this.tabIndex = this.tagName === "BUTTON" || this.tagName === "INPUT" ? 0 : -1;
    this.textContent = "";
  }

  get isConnected() {
    let node = this;
    while (node) {
      if (node === this.ownerDocument.body) {
        return true;
      }
      node = node.parentNode;
    }
    return false;
  }

  append(...children) {
    for (const child of children) {
      child.parentNode = this;
      this.children.push(child);
    }
  }

  remove() {
    if (!this.parentNode) {
      return;
    }
    const index = this.parentNode.children.indexOf(this);
    this.parentNode.children.splice(index, 1);
    this.parentNode = null;
  }

  contains(candidate) {
    return candidate === this || this.children.some((child) => child.contains(candidate));
  }

  setAttribute(name, value) {
    this.attributes.set(name, String(value));
    if (name === "id") {
      this.id = String(value);
    }
    if (name === "tabindex") {
      this.tabIndex = Number(value);
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
    const values = this.listeners.get(type) || [];
    values.push(listener);
    this.listeners.set(type, values);
  }

  removeEventListener(type, listener) {
    this.listeners.set(
      type,
      (this.listeners.get(type) || []).filter((candidate) => candidate !== listener),
    );
  }

  dispatchEvent(event) {
    if (!event.target) {
      event.target = this;
    }
    event.currentTarget = this;
    for (const listener of this.listeners.get(event.type) || []) {
      listener(event);
    }
  }

  focus() {
    this.ownerDocument.activeElement = this;
  }

  querySelectorAll() {
    const values = [];
    function visit(element) {
      if (
        ["A", "BUTTON", "INPUT", "SELECT", "TEXTAREA"].includes(element.tagName) ||
        element.tabIndex >= 0
      ) {
        values.push(element);
      }
      for (const child of element.children) {
        visit(child);
      }
    }
    for (const child of this.children) {
      visit(child);
    }
    return values;
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

  dispatchEvent(event) {
    if (!event.target) {
      event.target = this.activeElement;
    }
    for (const entry of this.listeners.get(event.type) || []) {
      entry.listener(event);
    }
  }
}

function event(type, values = {}) {
  return {
    altKey: false,
    ctrlKey: false,
    defaultPrevented: false,
    isComposing: false,
    key: "",
    metaKey: false,
    repeat: false,
    shiftKey: false,
    type,
    preventDefault() {
      this.defaultPrevented = true;
    },
    ...values,
  };
}

const document = new FakeDocument();
const sandbox = { document };
sandbox.window = sandbox;
sandbox.globalThis = sandbox;
vm.createContext(sandbox);
for (const filename of ["keyboard-shortcuts.js", "overlay-layer.js"]) {
  vm.runInContext(
    fs.readFileSync(path.join(repoRoot, "src/metabrowser/static", filename), "utf-8"),
    sandbox,
    { filename },
  );
}

const failures = [];
function check(label, condition, detail = "") {
  if (!condition) {
    failures.push(`${label}${detail ? `: ${detail}` : ""}`);
  }
}

const shortcuts = sandbox.MetabrowserKeyboardShortcuts.create({ document });
let modal;
let closeCalls = 0;
shortcuts.register({
  allowInEditable: true,
  bindings: [{ key: "Escape" }],
  copy: {
    action: "Close Help",
    description: "Close Help and restore focus to the previous control.",
    hint: "Close",
  },
  group: "help",
  handler: () => {
    closeCalls += 1;
    modal.close();
    return true;
  },
  id: "help.close",
  order: 10,
  scope: "help",
  surfaces: { help: "always" },
});

const background = document.createElement("main");
const preservedInert = document.createElement("aside");
preservedInert.inert = true;
document.body.append(background, preservedInert);
const fallback = document.createElement("button");
background.append(fallback);

modal = sandbox.MetabrowserOverlay.createModal({
  className: "help-dialog",
  closeCommandId: "help.close",
  document,
  resolveFocusFallback: () => fallback,
  scope: "help",
  shortcuts,
  title: "Help",
});

check("portal is attached hidden", modal.element.isConnected && modal.element.hidden);
check("dialog semantics", modal.dialog.getAttribute("role") === "dialog");
check("dialog is modal", modal.dialog.getAttribute("aria-modal") === "true");
check("dialog title relationship", modal.dialog.getAttribute("aria-labelledby") === modal.title.id);
check(
  "close button uses descriptor action",
  modal.closeButton.getAttribute("aria-label") === "Close Help",
);
check(
  "close button uses descriptor aria",
  modal.closeButton.getAttribute("aria-keyshortcuts") === "Escape",
);

const trigger = document.createElement("button");
trigger.setAttribute("aria-haspopup", "menu");
trigger.setAttribute("aria-expanded", "mixed");
background.append(trigger);
const disconnect = modal.control.connect(trigger);
check("control popup role", trigger.getAttribute("aria-haspopup") === "dialog");
check("control id", trigger.getAttribute("aria-controls") === modal.dialog.id);
check("control starts collapsed", trigger.getAttribute("aria-expanded") === "false");

trigger.focus();
modal.open(trigger);
check("open reveals portal", !modal.element.hidden && modal.isOpen());
check("open updates trigger", trigger.getAttribute("aria-expanded") === "true");
check("background is inert", background.inert);
check("prior inert background stays inert", preservedInert.inert);
check("default focus enters close control", document.activeElement === modal.closeButton);
check("scope becomes active", shortcuts.snapshot("help").length === 1);

const extraButton = document.createElement("button");
modal.body.append(extraButton);
extraButton.focus();
modal.dialog.dispatchEvent(event("keydown", { key: "Tab" }));
check("forward Tab wraps", document.activeElement === modal.closeButton);
modal.closeButton.focus();
modal.dialog.dispatchEvent(event("keydown", { key: "Tab", shiftKey: true }));
check("reverse Tab wraps", document.activeElement === extraButton);

modal.element.dispatchEvent(event("pointerdown", { target: modal.element }));
check("scrim invokes close descriptor", closeCalls === 1 && !modal.isOpen());
check("close restores trigger focus", document.activeElement === trigger);
check("close restores background inert", !background.inert && preservedInert.inert);
check("close updates trigger", trigger.getAttribute("aria-expanded") === "false");

modal.open(trigger);
document.dispatchEvent(event("keydown", { key: "Escape", target: modal.closeButton }));
check("Escape uses registry descriptor", closeCalls === 2 && !modal.isOpen());

modal.open(trigger);
trigger.remove();
shortcuts.invoke("help.close");
check("detached trigger uses consumer fallback", document.activeElement === fallback);

disconnect();
check("disconnect restores aria-haspopup", trigger.getAttribute("aria-haspopup") === "menu");
check("disconnect restores aria-expanded", trigger.getAttribute("aria-expanded") === "mixed");
check("disconnect removes new aria-controls", !trigger.hasAttribute("aria-controls"));

modal.open();
modal.closeButton.dispatchEvent(event("click"));
check("visible close invokes descriptor", closeCalls === 4 && !modal.isOpen());

let secondModal;
shortcuts.register({
  allowInEditable: true,
  bindings: [{ key: "Escape" }],
  copy: {
    action: "Close Quick File",
    description: "Close Quick File and restore focus to the previous control.",
    hint: "Close",
  },
  group: "quick-file",
  handler: () => {
    secondModal.close();
    return true;
  },
  id: "quick-file.close",
  order: 60,
  scope: "quick-file",
  surfaces: { help: "always" },
});
secondModal = sandbox.MetabrowserOverlay.createModal({
  closeCommandId: "quick-file.close",
  document,
  scope: "quick-file",
  shortcuts,
  title: "Quick File",
});
const secondTrigger = document.createElement("button");
background.append(secondTrigger);
const disconnectSecond = secondModal.control.connect(secondTrigger);
modal.open();
secondModal.open(secondTrigger);
check("opening another modal arbitrates the first", !modal.isOpen() && secondModal.isOpen());
check("arbitrated modal keeps background inert", background.inert);
shortcuts.invoke("quick-file.close");
check("second modal closes through its descriptor", !secondModal.isOpen());
secondModal.dispose();
disconnectSecond();

modal.dispose();
check("dispose removes portal", !modal.element.isConnected);
shortcuts.dispose();

if (failures.length > 0) {
  console.error(failures.join("\n"));
  process.exitCode = 1;
} else {
  console.log("OK overlay layer");
}

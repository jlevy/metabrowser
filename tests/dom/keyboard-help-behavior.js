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
    this.hidden = false;
    this.id = "";
    this.isContentEditable = false;
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
      if (child.parentNode) {
        child.parentNode.children = child.parentNode.children.filter((node) => node !== child);
      }
      child.parentNode = this;
      this.children.push(child);
    }
  }

  replaceChildren(...children) {
    for (const child of this.children) {
      child.parentNode = null;
    }
    this.children = [];
    this.append(...children);
  }

  remove() {
    if (this.parentNode) {
      this.parentNode.children = this.parentNode.children.filter((child) => child !== this);
      this.parentNode = null;
    }
  }

  setAttribute(name, value) {
    this.attributes.set(name, String(value));
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
    event.target ||= this;
    for (const listener of this.listeners.get(event.type) || []) {
      listener(event);
    }
  }

  querySelectorAll(selector) {
    const values = [];
    function visit(element) {
      const match = selector.startsWith(".")
        ? element.className.split(/\s+/).includes(selector.slice(1))
        : selector.startsWith("[")
          ? element.getAttribute(selector.slice(1, -1).split("=")[0]) !== null
          : element.tagName.toLowerCase() === selector;
      if (match) {
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

  querySelector(selector) {
    return this.querySelectorAll(selector)[0] || null;
  }
}

class FakeDocument {
  constructor() {
    this.body = new FakeElement("body", this);
    this.activeElement = this.body;
    this.listeners = new Map();
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
}

const document = new FakeDocument();
const sandbox = { document };
sandbox.window = sandbox;
sandbox.globalThis = sandbox;
vm.createContext(sandbox);
for (const filename of ["keyboard-shortcuts.js", "keyboard-help.js"]) {
  vm.runInContext(
    fs.readFileSync(path.join(repoRoot, "src/metabrowser/static", filename), "utf-8"),
    sandbox,
    { filename },
  );
}

const shortcuts = sandbox.MetabrowserKeyboardShortcuts.create({ document });
const hintHost = document.createElement("div");
document.body.append(hintHost);
let modalOpen = false;
let openedTrigger = null;
let closeCount = 0;
let deactivateModalScope = null;
const body = document.createElement("div");
const modalControl = Object.freeze({
  connect(element) {
    element.setAttribute("data-modal-control", "true");
    return () => element.removeAttribute("data-modal-control");
  },
});
const overlay = {
  createModal(options) {
    return Object.freeze({
      body,
      close() {
        closeCount += 1;
        modalOpen = false;
        deactivateModalScope?.();
        deactivateModalScope = null;
      },
      control: modalControl,
      dispose() {},
      isOpen: () => modalOpen,
      open(trigger) {
        modalOpen = true;
        openedTrigger = trigger;
        deactivateModalScope = options.shortcuts.activateScope(options.scope, { exclusive: true });
      },
    });
  },
};

const failures = [];
function check(label, condition, detail = "") {
  if (!condition) {
    failures.push(`${label}${detail ? `: ${detail}` : ""}`);
  }
}

const help = sandbox.MetabrowserKeyboardHelp.create({
  document,
  hintHost,
  overlay,
  resolveFocusFallback: () => null,
  shortcuts,
});

const paragraphs = body.querySelectorAll("p").map((element) => element.textContent);
check(
  "approved three-sentence description",
  paragraphs.includes("Metabrowser runs a local server for one folder."),
);
check(
  "approved navigation description",
  paragraphs.includes(
    "Use the navigation pane and filters to explore its live file inventory; select a file to open a preview in the main pane.",
  ),
);
check(
  "approved trusted-plugin description",
  paragraphs.includes(
    "Built-in and trusted installed plugins provide views for different file types.",
  ),
);
const projectLink = body.querySelector("a");
check(
  "public project URL",
  projectLink.getAttribute("href") === "https://github.com/jlevy/metabrowser",
);
check(
  "safe new tab",
  projectLink.getAttribute("target") === "_blank" &&
    projectLink.getAttribute("rel") === "noopener noreferrer",
);
check(
  "new tab accessible name",
  projectLink.getAttribute("aria-label").includes("opens in a new tab"),
);

const helpButton = hintHost.querySelector("button");
check("persistent Help button", helpButton?.getAttribute("aria-label") === "Help");
check(
  "Help button receives modal control",
  helpButton?.getAttribute("data-modal-control") === "true",
);
check("punctuation shortcut has no guessed ARIA", !helpButton.hasAttribute("aria-keyshortcuts"));
helpButton.dispatchEvent({ type: "click" });
check("pointer trigger reaches modal", modalOpen && openedTrigger === helpButton);
shortcuts.invoke("help.close");
check("Help close descriptor reaches modal", closeCount === 1);

const originalHelpButton = helpButton;
let quickOpenCount = 0;
shortcuts.register({
  bindings: [{ key: "t" }, { key: "/" }],
  control: Object.freeze({
    connect(element) {
      element.setAttribute("data-quick-control", "true");
      return () => element.removeAttribute("data-quick-control");
    },
  }),
  copy: {
    action: "Quick File",
    description: "Find and open a file from the current folder.",
    hint: "Quick File",
  },
  group: "anywhere",
  handler: () => {
    quickOpenCount += 1;
    return true;
  },
  id: "quick-file.open",
  order: 20,
  scope: "global",
  surfaces: { help: "always", nav: "always" },
});
const hintButtons = hintHost.querySelectorAll("button");
check("later registration appears in hints", hintButtons.length === 2);
check("Help trigger identity is stable", hintButtons[0] === originalHelpButton);
check(
  "Quick File exposes representable alias",
  hintButtons[1].getAttribute("aria-keyshortcuts") === "T",
);
// The strip names one way in. `/` stays bound and stays in Help; spelling out
// every alias in a permanent one-line reminder is what made it verbose.
check(
  "compact strip shows only the preferred key",
  hintButtons[1].querySelectorAll(".kbd").length === 1 &&
    hintButtons[1].querySelector(".kbd").textContent === "T",
);
check(
  "the alias is not dropped, only unadvertised",
  hintButtons[1].textContent.indexOf("/") === -1 &&
    shortcuts
      .snapshot("help")
      .flatMap((group) => group.commands)
      .find((command) => command.id === "quick-file.open").bindings.visible.length === 2,
);
hintButtons[1].dispatchEvent({ type: "click" });
check("Quick File button invokes registry", quickOpenCount === 1);

shortcuts.register({
  bindings: [{ key: "Enter" }, { key: " " }],
  copy: {
    action: "Open or toggle",
    description: "Open the focused file, toggle the focused folder, or show the next page.",
    hint: "Open or toggle",
  },
  group: "navigation",
  handler: () => true,
  id: "tree.activate",
  order: 70,
  scope: "tree",
  surfaces: { help: "always", nav: "active" },
});
check(
  "inactive tree hint is absent",
  hintHost.querySelectorAll("button").length === 2 && hintHost.children.length === 2,
);
const deactivateTree = shortcuts.activateScope("tree");
check("active tree hint appears", hintHost.children.length === 3);
check("scope reconciliation keeps Help trigger", hintHost.children[0] === originalHelpButton);
deactivateTree();
check("tree hint disappears", hintHost.children.length === 2);

const headings = body.querySelectorAll("h4").map((element) => element.textContent);
check(
  "full Help preserves group order",
  JSON.stringify(headings) === JSON.stringify(["Anywhere", "Navigation", "Help"]),
  JSON.stringify(headings),
);
check(
  "Help copy comes from descriptors",
  body
    .querySelectorAll(".help-command-description")
    .some((element) => element.textContent.includes("Find and open a file")),
);

help.open(helpButton);
shortcuts.invoke("help.close");
check("Help can reopen and close", closeCount === 2);
help.dispose();
check("dispose clears hints", hintHost.children.length === 0);
check("dispose unregisters Help", shortcuts.present("help.open") === null);
shortcuts.dispose();

if (failures.length > 0) {
  console.error(failures.join("\n"));
  process.exitCode = 1;
} else {
  console.log("OK keyboard help");
}

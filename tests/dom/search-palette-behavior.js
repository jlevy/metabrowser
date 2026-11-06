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

  toggle(name, force) {
    const present = this.contains(name);
    const enabled = force === undefined ? !present : Boolean(force);
    if (enabled) {
      this.add(name);
    } else {
      this.element.className = this.element.className
        .split(/\s+/)
        .filter((value) => value && value !== name)
        .join(" ");
    }
    return enabled;
  }
}

class FakeTextNode {
  constructor(text, document) {
    this.nodeType = 3;
    this.ownerDocument = document;
    this.parentNode = null;
    this.textContent = String(text);
  }

  remove() {
    this.parentNode?.removeChild(this);
  }
}

class FakeElement {
  constructor(tagName, document) {
    this.tagName = tagName.toUpperCase();
    this.nodeName = this.tagName;
    this.ownerDocument = document;
    this.parentNode = null;
    this.children = [];
    this.attributes = new Map();
    this.listeners = new Map();
    this.className = "";
    this.classList = new FakeClassList(this);
    this.disabled = false;
    this.hidden = false;
    this.id = "";
    this.innerHTML = "";
    this.inert = false;
    this.isContentEditable = false;
    this.tabIndex = this.tagName === "BUTTON" || this.tagName === "INPUT" ? 0 : -1;
    this.value = "";
    this._textContent = "";
    this.focusCalls = 0;
    this.selectCalls = 0;
    this.scrollCalls = 0;
    this.scrollTop = 0;
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

  get textContent() {
    if (this.children.length > 0) {
      return this.children.map((child) => child.textContent).join("");
    }
    return this._textContent;
  }

  set textContent(value) {
    this.children = [];
    this._textContent = String(value ?? "");
    this.innerHTML = "";
  }

  append(...nodes) {
    for (const node of nodes) {
      const child = typeof node === "string" ? this.ownerDocument.createTextNode(node) : node;
      child.parentNode = this;
      this.children.push(child);
    }
  }

  appendChild(node) {
    this.append(node);
    return node;
  }

  replaceChildren(...nodes) {
    for (const child of this.children) {
      child.parentNode = null;
    }
    this.children = [];
    this._textContent = "";
    this.append(...nodes);
  }

  removeChild(node) {
    const index = this.children.indexOf(node);
    if (index >= 0) {
      this.children.splice(index, 1);
      node.parentNode = null;
    }
    return node;
  }

  remove() {
    this.parentNode?.removeChild(this);
  }

  setAttribute(name, value) {
    this.attributes.set(name, String(value));
    if (name === "tabindex") {
      this.tabIndex = Number(value);
    }
  }

  getAttribute(name) {
    return this.attributes.has(name) ? this.attributes.get(name) : null;
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

  dispatchEvent(event) {
    if (!event.target) {
      event.target = this;
    }
    event.currentTarget = this;
    if (event.type === "keydown") {
      for (const listener of this.ownerDocument.listeners.get("keydown") || []) {
        listener(event);
      }
    }
    for (const listener of this.listeners.get(event.type) || []) {
      listener(event);
    }
    return !event.defaultPrevented;
  }

  focus() {
    this.focusCalls += 1;
    this.ownerDocument.activeElement = this;
  }

  select() {
    this.selectCalls += 1;
  }

  scrollIntoView() {
    this.scrollCalls += 1;
  }

  contains(candidate) {
    if (candidate === this) {
      return true;
    }
    return this.children.some((child) => child instanceof FakeElement && child.contains(candidate));
  }

  querySelectorAll(selector) {
    const matches = [];
    function visit(node) {
      if (!(node instanceof FakeElement)) {
        return;
      }
      const matchesSelector = selector.startsWith(".")
        ? node.classList.contains(selector.slice(1))
        : selector.startsWith("#")
          ? node.id === selector.slice(1)
          : selector.startsWith('[role="')
            ? node.getAttribute("role") === selector.slice(7, -2)
            : node.tagName.toLowerCase() === selector.toLowerCase();
      if (matchesSelector) {
        matches.push(node);
      }
      for (const child of node.children) {
        visit(child);
      }
    }
    for (const child of this.children) {
      visit(child);
    }
    return matches;
  }

  querySelector(selector) {
    return this.querySelectorAll(selector)[0] || null;
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

  createTextNode(text) {
    return new FakeTextNode(text, this);
  }

  getElementById(id) {
    if (this.body.id === id) {
      return this.body;
    }
    return this.body.querySelector(`#${id}`);
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

  dispatchEvent(event) {
    if (!event.target) {
      event.target = this.body;
    }
    for (const listener of this.listeners.get(event.type) || []) {
      listener(event);
    }
    return !event.defaultPrevented;
  }
}

function fakeEvent(type, values = {}) {
  return {
    altKey: false,
    ctrlKey: false,
    defaultPrevented: false,
    isComposing: false,
    metaKey: false,
    shiftKey: false,
    type,
    preventDefault() {
      this.defaultPrevented = true;
    },
    stopPropagation() {},
    ...values,
  };
}

function searchResult(pathname, score, matchRanges = []) {
  const separator = pathname.lastIndexOf("/");
  return {
    description: separator >= 0 ? pathname.slice(0, separator) : "",
    id: `file:${pathname}`,
    kind: "file",
    label: pathname.slice(separator + 1),
    matchRanges,
    path: pathname,
    providerId: "test",
    score,
  };
}

const document = new FakeDocument();
const sandbox = {
  AbortController,
  AbortSignal,
  clearTimeout,
  document,
  setTimeout,
  URLSearchParams,
};
sandbox.window = sandbox;
sandbox.globalThis = sandbox;
vm.createContext(sandbox);
for (const filename of [
  "navigation.js",
  "file-fuzzy-match.js",
  "known-file-catalog.js",
  "search-controller.js",
  "keyboard-shortcuts.js",
  "overlay-layer.js",
  "search-palette.js",
]) {
  const sourcePath = path.join(repoRoot, "src/metabrowser/static", filename);
  vm.runInContext(fs.readFileSync(sourcePath, "utf-8"), sandbox, { filename: sourcePath });
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

async function settle() {
  for (let index = 0; index < 6; index += 1) {
    await Promise.resolve();
  }
}

/** The catalog-refresh window is a real timer, so microtask flushing cannot
 * advance past it. */
async function waitMs(ms) {
  await new Promise((resolve) => setTimeout(resolve, ms));
  await settle();
}

async function main() {
  let availableResults = [
    searchResult("src/app.js", 5, [
      { start: 4, end: 7 },
      { start: 8, end: 10 },
    ]),
    searchResult("src/application.js", 4, [{ start: 4, end: 7 }]),
    searchResult("examples/happy.js", 3, [{ start: 10, end: 13 }]),
    searchResult("app/config.js", 2, [{ start: 0, end: 3 }]),
    searchResult("unsafe/<img src=x>.md", 1, [{ start: 7, end: 10 }]),
  ];
  const subscribers = new Set();
  const requests = [];
  let cancelCalls = 0;
  let requestId = 0;
  // When set, the completed state is withheld until the test releases it, so
  // assertions can inspect the palette while a search is still in flight.
  let holdCompletion = false;
  let releaseCompletion = null;
  const controller = {
    cancel() {
      cancelCalls += 1;
    },
    search(request) {
      requests.push(request);
      requestId += 1;
      const state = Object.freeze({
        batches: [],
        complete: false,
        errors: [],
        phase: "complete",
        request,
        requestId,
        results: availableResults,
        statusMessage:
          availableResults.length > 0 ? "5 matches in 5 indexed files. Scanning continues." : "",
        truncated: availableResults.length > 3,
      });
      // The real controller publishes one empty "searching" composition before
      // any provider has returned. Reproduce it, or the palette's handling of
      // that state goes untested.
      const pending = Object.freeze({
        ...state,
        complete: false,
        phase: "searching",
        results: [],
        statusMessage: "",
      });
      for (const subscriber of subscribers) {
        subscriber(pending);
      }
      const deliver = () => {
        for (const subscriber of subscribers) {
          subscriber(state);
        }
        return state;
      };
      if (holdCompletion) {
        return new Promise((resolve) => {
          releaseCompletion = () => resolve(deliver());
        });
      }
      return Promise.resolve(deliver());
    },
    subscribe(listener) {
      subscribers.add(listener);
      return () => subscribers.delete(listener);
    },
  };

  /** @type {Array<() => void>} */
  const catalogListeners = [];
  let catalogObservedCount = 5;
  let catalogTruncated = false;
  const emitCatalogChange = () => {
    for (const listener of catalogListeners.slice()) {
      listener();
    }
  };

  const initialFocus = document.createElement("button");
  document.body.append(initialFocus);
  initialFocus.focus();
  const openedPaths = [];
  const removedPaths = [];
  const destination = document.createElement("button");
  document.body.append(destination);
  const shortcuts = sandbox.MetabrowserKeyboardShortcuts.create({ document });
  // Everything the palette asked the classifier to describe. Only a thrown
  // open is unclassified; a settled outcome already carries its message.
  const describedFailures = [];
  const palette = sandbox.MetabrowserSearchPalette.create({
    // The production classifier app.js passes, so an unreachable server reads
    // the same here as in the preview pane.
    describeOpenFailure: (error) => {
      describedFailures.push(error);
      return sandbox.MetabrowserNavigationRoute.openFailureOutcome(error);
    },
    controller,
    document,
    getCatalogSnapshot: () => ({
      complete: false,
      observedCount: catalogObservedCount,
      truncated: catalogTruncated,
    }),
    subscribeCatalog: (listener) => {
      catalogListeners.push(listener);
      return () => {
        const index = catalogListeners.indexOf(listener);
        if (index >= 0) {
          catalogListeners.splice(index, 1);
        }
      };
    },
    getFileIcon: () => ({ cls: "ft-code", svg: "<svg></svg>" }),
    maxRows: 3,
    overlay: sandbox.MetabrowserOverlay,
    onNotFound(pathname) {
      removedPaths.push(pathname);
      availableResults = availableResults.filter((result) => result.path !== pathname);
    },
    async openFile(pathname) {
      openedPaths.push(pathname);
      if (pathname === "gone.md") {
        return { status: "not-found" };
      }
      if (pathname === "error.md") {
        return { message: "Preview failed. Try again.", status: "error" };
      }
      if (pathname === "offline.md") {
        const refused = sandbox.MetabrowserNavigationRoute.requestFailure(
          new TypeError("Failed to fetch"),
        );
        return sandbox.MetabrowserNavigationRoute.openFailureOutcome(refused);
      }
      if (pathname === "offline-throw.md") {
        throw sandbox.MetabrowserNavigationRoute.requestFailure(new TypeError("Failed to fetch"));
      }
      if (pathname === "broken-throw.md") {
        throw new TypeError("Cannot read properties of undefined");
      }
      return { focusTarget: destination, status: "opened" };
    },
    resolveFocusFallback: () => initialFocus,
    shortcuts,
  });

  const overlay = document.body.querySelector(".search-palette-overlay");
  const dialog = overlay.querySelector('[role="dialog"]');
  const input = overlay.querySelector('[role="combobox"]');
  const listbox = overlay.querySelector('[role="listbox"]');
  const status = overlay.querySelector('[role="status"]');
  check("palette mounts once outside replaceable panes", document.body.children.includes(overlay));
  check("palette starts hidden", overlay.hidden === true);
  check("dialog is modal and labelled", dialog.getAttribute("aria-modal") === "true");
  check(
    "combobox controls the listbox",
    input.getAttribute("aria-controls") === listbox.id &&
      listbox.getAttribute("role") === "listbox",
  );
  check("status is polite", status.getAttribute("aria-live") === "polite");
  check(
    "registry remains the only document keydown owner",
    document.listeners.get("keydown").length === 1,
  );
  check("shared modal adds a visible Close control", dialog.querySelector(".modal-close") !== null);

  const hint = dialog.querySelector(".search-palette-hint");
  palette.open();
  const hintKeys = hint ? hint.querySelectorAll("kbd") : [];
  check("hint renders every key through the kbd component", hintKeys.length === 4);
  check(
    "hint keys carry the design-system class",
    Array.from(hintKeys).every((key) => key.className === "kbd"),
  );
  check(
    "hint keys keep their natural accessible name",
    Array.from(hintKeys)
      .map((key) => key.textContent)
      .join(" ") === "↑ ↓ Enter Esc",
    Array.from(hintKeys)
      .map((key) => key.textContent)
      .join(" "),
  );
  palette.close(false);

  const editableTargets = ["input", "textarea", "select"].map((tag) => document.createElement(tag));
  const contentEditable = document.createElement("div");
  contentEditable.isContentEditable = true;
  const guardedEvents = ["/", "t"].flatMap((key) => [
    fakeEvent("keydown", { key, defaultPrevented: true }),
    fakeEvent("keydown", { key, altKey: true }),
    fakeEvent("keydown", { key, ctrlKey: true }),
    fakeEvent("keydown", { key, metaKey: true }),
    fakeEvent("keydown", { key, shiftKey: true }),
    fakeEvent("keydown", { key, isComposing: true }),
    ...editableTargets.map((target) => fakeEvent("keydown", { key, target })),
    fakeEvent("keydown", { key, target: contentEditable }),
  ]);
  for (const event of guardedEvents) {
    document.dispatchEvent(event);
  }
  check("open-key guards leave the palette closed", overlay.hidden === true);

  // `?` is shift+slash and `T` is shift+t; neither may open the palette.
  for (const event of [
    fakeEvent("keydown", { key: "?", target: initialFocus }),
    fakeEvent("keydown", { key: "T", shiftKey: true, target: initialFocus }),
  ]) {
    document.dispatchEvent(event);
  }
  check("shifted open keys stay closed", overlay.hidden === true);

  const slash = fakeEvent("keydown", { key: "/", target: initialFocus });
  document.dispatchEvent(slash);
  check("plain slash opens and prevents browser find", !overlay.hidden && slash.defaultPrevented);
  palette.close(false);
  check("palette closed before testing the t alias", overlay.hidden === true);

  const goToFile = fakeEvent("keydown", { key: "t", target: initialFocus });
  document.dispatchEvent(goToFile);
  check("t opens the palette like github go-to-file", !overlay.hidden && goToFile.defaultPrevented);

  // Caps lock reports an uppercase key with no shift modifier.
  palette.close(false);
  const capsLocked = fakeEvent("keydown", { key: "T", target: initialFocus });
  document.dispatchEvent(capsLocked);
  check("caps-locked T still opens", !overlay.hidden && capsLocked.defaultPrevented);
  palette.close(false);

  // Every open above selected the query, so the remaining checks count from
  // here rather than from zero.
  const selectCallsBeforeReopen = input.selectCalls;
  document.dispatchEvent(fakeEvent("keydown", { key: "/", target: initialFocus }));
  check(
    "open focuses and selects the query",
    document.activeElement === input && input.selectCalls === selectCallsBeforeReopen + 1,
  );
  check(
    "placeholder owns the input instruction",
    input.getAttribute("placeholder") === "Type a file name or path",
    input.getAttribute("placeholder"),
  );
  equal(
    "empty query reports scope without repeating the instruction",
    status.textContent,
    "Search includes 5 indexed files. Scanning continues.",
  );
  palette.open();
  check(
    "reopening reuses one palette",
    document.body.querySelectorAll(".search-palette-overlay").length === 1,
  );
  check("reopening selects the query", input.selectCalls === selectCallsBeforeReopen + 2);

  input.value = "app";
  input.dispatchEvent(fakeEvent("input", { target: input }));
  await settle();
  equal("palette sends the file-fuzzy request", requests[0], {
    match: "fuzzy",
    query: "app",
    target: "file",
  });
  check("result DOM is bounded", listbox.children.length === 3, String(listbox.children.length));
  check("rows expose option semantics", listbox.children[0].getAttribute("role") === "option");
  check("first result starts active", listbox.children[0].getAttribute("aria-selected") === "true");
  check("match ranges render marks", listbox.querySelectorAll("mark").length > 0);
  check(
    "rows split basename and parent path",
    listbox.children[0].textContent.includes("app.js") &&
      listbox.children[0].textContent.includes("src"),
  );
  check(
    "result limit stays visible",
    status.textContent.includes("Showing the top matches"),
    status.textContent,
  );

  const requestCountBeforeComposition = requests.length;
  input.value = "composing";
  input.dispatchEvent(fakeEvent("input", { isComposing: true, target: input }));
  await settle();
  check(
    "intermediate composition input does not start search",
    requests.length === requestCountBeforeComposition,
  );
  input.value = "app";

  input.dispatchEvent(fakeEvent("keydown", { key: "ArrowDown", target: input }));
  check(
    "ArrowDown changes the active option",
    listbox.children[1].getAttribute("aria-selected") === "true",
  );
  input.dispatchEvent(fakeEvent("keydown", { key: "ArrowUp", target: input }));
  check(
    "ArrowUp changes the active option",
    listbox.children[0].getAttribute("aria-selected") === "true",
  );
  input.dispatchEvent(fakeEvent("keydown", { key: "ArrowDown", target: input }));
  const preservedId = input.getAttribute("aria-activedescendant");
  availableResults = [availableResults[2], availableResults[1], availableResults[0]];
  await controller.search({ match: "fuzzy", query: "app", target: "file" });
  check(
    "asynchronous reordering preserves selection identity",
    input.getAttribute("aria-activedescendant") === preservedId,
  );
  input.dispatchEvent(fakeEvent("keydown", { key: "ArrowDown", target: input }));
  check(
    "ArrowDown reaches the last mounted option",
    listbox.children[2].getAttribute("aria-selected") === "true",
  );
  input.dispatchEvent(fakeEvent("keydown", { key: "ArrowDown", target: input }));
  check(
    "ArrowDown wraps to the first option",
    listbox.children[0].getAttribute("aria-selected") === "true",
  );
  input.dispatchEvent(fakeEvent("keydown", { key: "ArrowUp", target: input }));
  check(
    "ArrowUp wraps to the last option",
    listbox.children[2].getAttribute("aria-selected") === "true",
  );

  // The query box is an editable combobox, so Home and End belong to its
  // caret. Claiming them would take line-start and line-end away from the
  // field, and the wrapping arrows already reach both ends of the list.
  const endEvent = fakeEvent("keydown", { key: "End", target: input });
  input.dispatchEvent(endEvent);
  const homeEvent = fakeEvent("keydown", { key: "Home", target: input });
  input.dispatchEvent(homeEvent);
  check(
    "Home and End stay with the query caret",
    !endEvent.defaultPrevented &&
      !homeEvent.defaultPrevented &&
      listbox.children[2].getAttribute("aria-selected") === "true",
  );

  // Tab belongs to the shared modal focus trap (covered in
  // overlay-layer-behavior.js). A palette-local handler would preventDefault
  // before the trap ran and strand Shift+Tab on the query box.
  check(
    "the palette installs no keydown handler on the query box",
    (input.listeners.get("keydown") || []).length === 0,
  );

  input.dispatchEvent(fakeEvent("keydown", { key: "Enter", target: input }));
  await settle();
  check("Enter delegates navigation", openedPaths.length === 1, JSON.stringify(openedPaths));
  check("successful navigation closes the palette", overlay.hidden === true);
  check("successful navigation focuses its destination", document.activeElement === destination);

  initialFocus.focus();
  palette.open();
  input.value = "gone";
  availableResults = [searchResult("gone.md", 10), searchResult("keep.md", 9)];
  input.dispatchEvent(fakeEvent("input", { target: input }));
  await settle();
  listbox.children[0].dispatchEvent(fakeEvent("click", { target: listbox.children[0] }));
  await settle();
  check("not-found selection keeps the palette open", overlay.hidden === false);
  check("not-found selection preserves the query", input.value === "gone", input.value);
  equal("not-found selection removes the stale path", removedPaths, ["gone.md"]);
  check(
    "not-found status is inline",
    status.textContent.includes("no longer available"),
    status.textContent,
  );

  availableResults = [searchResult("error.md", 10)];
  input.value = "error";
  input.dispatchEvent(fakeEvent("input", { target: input }));
  await settle();
  listbox.children[0].dispatchEvent(fakeEvent("click", { target: listbox.children[0] }));
  await settle();
  check("retryable error keeps the palette open", overlay.hidden === false);
  check(
    "retryable error is reported",
    status.textContent.includes("Try again"),
    status.textContent,
  );

  // A stopped server is a connection problem, whether the open settles with
  // that outcome or throws the marked fetch rejection, and never blames the file.
  for (const [pathname, query] of [
    ["offline.md", "offline"],
    ["offline-throw.md", "offline-throw"],
  ]) {
    availableResults = [searchResult(pathname, 10)];
    input.value = query;
    input.dispatchEvent(fakeEvent("input", { target: input }));
    await settle();
    listbox.children[0].dispatchEvent(fakeEvent("click", { target: listbox.children[0] }));
    await settle();
    check(`${pathname}: unreachable server keeps the palette open`, overlay.hidden === false);
    check(`${pathname}: unreachable server preserves the query`, input.value === query);
    check(
      `${pathname}: unreachable server is reported as a connection problem`,
      status.textContent.includes("Metabrowser is not reachable.") &&
        status.textContent.includes("metab <folder>"),
      status.textContent,
    );
    check(
      `${pathname}: unreachable server does not blame the file`,
      !status.textContent.includes("Could not open") &&
        !status.textContent.includes("Failed to fetch"),
      status.textContent,
    );
    // When the server answers again, the connection message no longer
    // describes the page and the query's own status returns.
    palette.reconnected();
    check(
      `${pathname}: a reconnect retires the connection message`,
      !status.textContent.includes("not reachable") && status.textContent.length > 0,
      status.textContent,
    );
    check(`${pathname}: a reconnect keeps the palette open`, overlay.hidden === false);
  }

  availableResults = [searchResult("broken-throw.md", 10)];
  input.value = "broken-throw";
  input.dispatchEvent(fakeEvent("input", { target: input }));
  await settle();
  listbox.children[0].dispatchEvent(fakeEvent("click", { target: listbox.children[0] }));
  await settle();
  check(
    "an unexpected throw keeps the file wording",
    status.textContent.includes("Could not open this file. Try again."),
    status.textContent,
  );
  palette.reconnected();
  check(
    "a reconnect leaves a status that is not about the connection",
    status.textContent.includes("Could not open this file. Try again."),
    status.textContent,
  );
  check(
    "only thrown opens are classified; settled outcomes carry their message",
    describedFailures.length === 2 &&
      // Realm-independent: the marked rejection is built inside the sandbox.
      describedFailures.every(
        (failure) => Object.prototype.toString.call(failure) === "[object Error]",
      ),
    String(describedFailures.map((failure) => failure?.status ?? failure?.name)),
  );

  input.dispatchEvent(fakeEvent("keydown", { key: "Escape", target: input }));
  check(
    "Escape closes and restores focus",
    overlay.hidden && document.activeElement === initialFocus,
  );
  check("closing cancels active work", cancelCalls > 0, String(cancelCalls));

  initialFocus.focus();
  palette.open();
  overlay.dispatchEvent(fakeEvent("pointerdown", { target: overlay }));
  check(
    "outside pointer dismissal restores focus",
    overlay.hidden && document.activeElement === initialFocus,
  );

  // Typing must not blank the list between keystrokes: the rows already on
  // screen stay until the next search actually produces something.
  palette.open();
  input.value = "app";
  input.dispatchEvent(fakeEvent("input", { target: input }));
  await settle();
  const rowsBeforeRetype = listbox.children.length;
  const statusBeforeRetype = status.textContent;
  check("rows are on screen before the next keystroke", rowsBeforeRetype > 0);

  holdCompletion = true;
  input.value = "appl";
  input.dispatchEvent(fakeEvent("input", { target: input }));
  await settle();
  check(
    "pending search keeps the previous rows",
    listbox.children.length === rowsBeforeRetype,
    String(listbox.children.length),
  );
  check(
    "a fast search does not flash a searching status",
    status.textContent === statusBeforeRetype,
    status.textContent,
  );

  // Held rows describe the previous query. Opening one would navigate to a
  // file that matched what the user typed a moment ago, not what is in the
  // box now — so they are inert until their own completion arrives.
  const openedBeforeStaleAccept = openedPaths.length;
  const heldRow = listbox.children[0];
  heldRow.dispatchEvent(fakeEvent("click", { target: heldRow }));
  await settle();
  input.dispatchEvent(fakeEvent("keydown", { key: "Enter", target: input }));
  await settle();
  check(
    "held rows do not open a result for the previous query",
    openedPaths.length === openedBeforeStaleAccept,
    `opened ${openedPaths.length - openedBeforeStaleAccept} stale path(s)`,
  );
  check(
    "held rows report as inert while they lag the query",
    Array.from(listbox.querySelectorAll('[role="option"]')).every(
      (node) => node.getAttribute("aria-disabled") === "true",
    ),
  );

  releaseCompletion();
  await settle();
  holdCompletion = false;
  check("completing the search renders its results", listbox.children.length > 0);
  check(
    "rows go live again once they match the query",
    Array.from(listbox.querySelectorAll('[role="option"]')).every(
      (node) => node.getAttribute("aria-disabled") === "false",
    ),
  );
  const openedBeforeLiveAccept = openedPaths.length;
  input.dispatchEvent(fakeEvent("keydown", { key: "Enter", target: input }));
  await settle();
  check("a live row still opens on Enter", openedPaths.length === openedBeforeLiveAccept + 1);

  // A completed search with no matches still clears the list.
  const heldResults = availableResults;
  availableResults = [];
  input.value = "no-such-file";
  input.dispatchEvent(fakeEvent("input", { target: input }));
  await settle();
  check("a completed empty search clears the rows", listbox.children.length === 0);
  equal(
    "a provider without empty-result copy uses the concise fallback",
    status.textContent,
    "No matches.",
  );
  availableResults = heldResults;

  availableResults = [searchResult("src/metabrowser/app.js", 5, [{ start: 4, end: 8 }])];
  input.value = "meta";
  input.dispatchEvent(fakeEvent("input", { target: input }));
  await settle();
  const describedRow = listbox.querySelector(".search-palette-description");
  check(
    "parent path ends with a separator",
    describedRow ? describedRow.textContent.endsWith("/") : false,
    describedRow ? describedRow.textContent : "no described row",
  );
  check(
    "parent path keeps its highlight offsets",
    describedRow ? describedRow.querySelectorAll("mark").length > 0 : false,
  );

  palette.open();
  availableResults = [searchResult("unsafe/<img src=x>.md", 1)];
  input.value = "img";
  input.dispatchEvent(fakeEvent("input", { target: input }));
  await settle();
  check("result text cannot create markup", listbox.querySelectorAll("img").length === 0);

  // Coverage grows while the palette is open: the bulk feed lands, then live
  // deltas. A query typed against a thinner catalog must converge instead of
  // keeping the results it happened to get first (mb-lzvb).
  palette.open();
  availableResults = [searchResult("src/early.js", 5, [{ start: 4, end: 7 }])];
  input.value = "ear";
  input.dispatchEvent(fakeEvent("input", { target: input }));
  await settle();
  check("the pre-growth query renders what it found", listbox.children.length === 1);
  const requestsBeforeGrowth = requests.length;

  // The catalog gains a file that also matches the standing query.
  availableResults = [
    searchResult("src/early.js", 5, [{ start: 4, end: 7 }]),
    searchResult("deep/nested/earlier.js", 4, [{ start: 12, end: 15 }]),
  ];
  emitCatalogChange();
  await waitMs(220);
  check(
    "a catalog change re-runs the standing query",
    requests.length === requestsBeforeGrowth + 1,
    `${requests.length - requestsBeforeGrowth} re-runs`,
  );
  equal("the re-run reuses the query in the box", requests[requests.length - 1].query, "ear");
  check(
    "results converge on the grown catalog",
    listbox.children.length === 2,
    String(listbox.children.length),
  );
  check(
    "converged rows stay live, not inert",
    Array.from(listbox.querySelectorAll('[role="option"]')).every(
      (node) => node.getAttribute("aria-disabled") === "false",
    ),
  );

  // A burst of deltas coalesces: many notifications, one re-run.
  const requestsBeforeBurst = requests.length;
  for (let index = 0; index < 10; index += 1) {
    emitCatalogChange();
  }
  await waitMs(220);
  check(
    "a burst of catalog changes coalesces into one re-run",
    requests.length === requestsBeforeBurst + 1,
    `${requests.length - requestsBeforeBurst} re-runs`,
  );

  // With an empty query there is no search to re-run, but the idle line quotes
  // the indexed count, which is exactly what a catalog change moves.
  input.value = "";
  input.dispatchEvent(fakeEvent("input", { target: input }));
  await settle();
  equal(
    "the idle line reports the starting scope",
    status.textContent,
    "Search includes 5 indexed files. Scanning continues.",
  );
  const requestsBeforeIdle = requests.length;
  catalogObservedCount = 4242;
  emitCatalogChange();
  await waitMs(220);
  equal(
    "an idle palette refreshes its status line",
    status.textContent,
    "Search includes 4,242 indexed files. Scanning continues.",
  );
  check("an idle palette runs no search", requests.length === requestsBeforeIdle);
  // A walk capped at the file limit is final: the idle line must not promise more.
  catalogTruncated = true;
  emitCatalogChange();
  await waitMs(220);
  equal(
    "an idle palette says indexing stopped at the file limit",
    status.textContent,
    "Search includes 4,242 indexed files. Indexing stopped at the file limit.",
  );
  catalogTruncated = false;
  catalogObservedCount = 5;

  // A closed palette has nothing to converge. Schedule a refresh first and
  // close inside the window, so this exercises timer cleanup rather than the
  // early-return guard a later event would hit anyway (senior review R4).
  const requestsBeforeCloseRace = requests.length;
  emitCatalogChange();
  palette.close(false);
  await waitMs(220);
  check(
    "closing cancels a refresh already scheduled",
    requests.length === requestsBeforeCloseRace,
    `${requests.length - requestsBeforeCloseRace} re-runs after close`,
  );

  const requestsAfterClose = requests.length;
  emitCatalogChange();
  await waitMs(220);
  check("a closed palette does not re-run", requests.length === requestsAfterClose);

  // Same race across dispose: a pending timer must not fire afterwards.
  palette.open();
  input.value = "ear";
  input.dispatchEvent(fakeEvent("input", { target: input }));
  await settle();
  const requestsBeforeDisposeRace = requests.length;
  emitCatalogChange();
  palette.dispose();
  check("dispose removes palette DOM", !document.body.children.includes(overlay));
  // Observe the subscription itself: without this the check below still passes
  // on a retained listener, because the callback exits early once disposed.
  check(
    "dispose unsubscribes from the catalog",
    catalogListeners.length === 0,
    `${catalogListeners.length} listener(s) retained`,
  );
  await waitMs(220);
  check(
    "disposing cancels a refresh already scheduled",
    requests.length === requestsBeforeDisposeRace,
    `${requests.length - requestsBeforeDisposeRace} re-runs after dispose`,
  );
  const requestCountAtDispose = requests.length;
  input.value = "after-dispose";
  input.dispatchEvent(fakeEvent("input", { target: input }));
  await settle();
  check("dispose removes the input listener", requests.length === requestCountAtDispose);
  const focusCallsBefore = input.focusCalls;
  document.dispatchEvent(fakeEvent("keydown", { key: "/", target: initialFocus }));
  check("dispose removes the global shortcut", input.focusCalls === focusCallsBefore);
  shortcuts.dispose();

  if (failures.length > 0) {
    process.stderr.write(`${failures.join("\n")}\n`);
    process.exit(1);
  }
  process.stdout.write("OK accessible search palette\n");
}

async function pullSearchSession() {
  const catalog = sandbox.MetabrowserKnownFileCatalog.create();
  catalog.observeRecent([
    { path: "render.js", type: "file" },
    { path: "src/renderer.js", type: "file" },
    { path: "notes/123.md", type: "file" },
  ]);
  const runtime = sandbox.MetabrowserSearch;
  const controller = runtime.createController();
  controller.registerProvider(
    runtime.createLocalFileProvider({ catalog, matcher: sandbox.MetabrowserFileFuzzyMatch }),
  );
  const requests = [];
  const readyPull = { number: 123, title: "Fix <em>renderer</em>", state: "merged" };
  const newerPull = { number: 124, title: "Render the latest state", state: "closed" };
  const reply = (rows, flags = {}) => ({
    ok: true,
    json: async () => ({
      complete: true,
      limited: false,
      refreshing: false,
      rows,
      truncated: false,
      ...flags,
    }),
  });
  const delayed = Promise.withResolvers();
  const started = Promise.withResolvers();
  const growth = Promise.withResolvers();
  const growthStarted = Promise.withResolvers();
  const exactRecheck = Promise.withResolvers();
  const exactRecheckStarted = Promise.withResolvers();
  const obsolete = Promise.withResolvers();
  const obsoleteStarted = Promise.withResolvers();
  let renderReads = 0;
  let obsoleteReads = 0;
  let now = 1_000;
  sandbox.Date = class extends Date {
    static now() {
      return now;
    }
  };
  let coldReads = 0;
  let warmRequests = 0;
  let lookupSignal;
  controller.registerProvider(
    runtime.createPullProvider({
      fetch: (url, init) => {
        requests.push({ url, method: init.method ?? "GET" });
        if (init.method === "POST") {
          equal("warming preserves active Pulls priority", JSON.parse(init.body), {
            background: true,
          });
          check(
            "warming has its own timeout, separate from the query",
            init.signal !== lookupSignal && !init.signal.aborted,
          );
          return Promise.resolve({ status: ++warmRequests === 1 ? 202 : 200 });
        }
        lookupSignal = init.signal;
        if (url.endsWith("?q=render")) {
          renderReads += 1;
          if (renderReads === 1) {
            started.resolve();
            return delayed.promise;
          }
          if (renderReads === 2) {
            growthStarted.resolve(init.signal);
            return growth.promise;
          }
          return Promise.resolve(reply([newerPull, readyPull], { truncated: true }));
        }
        if (url.endsWith("?q=obsolete")) {
          obsoleteReads += 1;
          if (obsoleteReads === 1) {
            return Promise.resolve(
              reply([{ number: 998, title: "Obsolete cached match", state: "open" }], {
                complete: false,
                refreshing: true,
              }),
            );
          }
          obsoleteStarted.resolve(init.signal);
          return obsolete.promise;
        }
        if (url.endsWith("?q=%23123")) {
          return Promise.resolve(reply([readyPull], { complete: false, refreshing: true }));
        }
        if (url.endsWith("?q=older")) {
          return Promise.resolve(reply([], { limited: true }));
        }
        if (url.endsWith("?q=%2377")) {
          coldReads += 1;
          if (coldReads === 2) {
            exactRecheckStarted.resolve(init.signal);
            return exactRecheck.promise;
          }
          return Promise.resolve(
            coldReads < 4
              ? reply([], { complete: false, refreshing: coldReads > 1 })
              : reply([{ number: 77, title: "Cold catalog match", state: "open" }]),
          );
        }
        return Promise.resolve(reply([], { complete: false }));
      },
    }),
  );
  const shortcuts = sandbox.MetabrowserKeyboardShortcuts.create({ document });
  const opened = [];
  const landing = document.createElement("button");
  document.body.append(landing);
  const palette = sandbox.MetabrowserSearchPalette.create({
    controller,
    document,
    describeOpenFailure: sandbox.MetabrowserNavigationRoute.openFailureOutcome,
    getCatalogSnapshot: () => catalog.snapshot(),
    subscribeCatalog: (listener) => catalog.subscribe(listener),
    openFile: (path) => {
      opened.push(path);
      return { status: "opened" };
    },
    openPull: (number) => {
      if (number === 77) {
        throw new Error("fixture: cannot load the PR page");
      }
      opened.push(number);
      return { focusTarget: landing, status: "opened" };
    },
    overlay: sandbox.MetabrowserOverlay,
    shortcuts,
  });
  const dialog = palette.element.querySelector('[role="dialog"]');
  const input = dialog.querySelector('[role="combobox"]');
  const listbox = dialog.querySelector('[role="listbox"]');
  const choices = () => Array.from(listbox.children, (row) => row.getAttribute("aria-label"));
  const currentChoice = () =>
    listbox.children
      .find((row) => row.getAttribute("aria-selected") === "true")
      ?.getAttribute("aria-label");

  function type(query) {
    input.value = query;
    input.dispatchEvent(fakeEvent("input", { target: input }));
  }
  function key(key) {
    return input.dispatchEvent(fakeEvent("keydown", { key, target: input }));
  }
  function searchCompletes() {
    return new Promise((resolve) => {
      const remove = controller.subscribe((state) => {
        if (state.phase === "complete") {
          remove();
          resolve();
        }
      });
    });
  }

  palette.open();
  const heading = dialog.querySelector(".modal-title").textContent;
  const placeholder = input.getAttribute("placeholder");
  const titleComplete = searchCompletes();
  type("render");
  await started.promise;
  const firstPaint = choices();
  const progress = dialog.querySelector('[role="status"]');
  check(
    "the shared spinner marks a pending PR lookup",
    progress.querySelector(".spinner") !== null,
  );
  equal("file results paint before the PR lookup settles", firstPaint, [
    "render.js",
    "src/renderer.js",
  ]);
  key("ArrowDown");
  const beforeMerge = currentChoice();
  let selectedAfterInsertion = null;
  const unsubscribe = controller.subscribe((state) => {
    if (state.phase === "searching" && state.results.some((result) => result.kind === "pull")) {
      selectedAfterInsertion = listbox.children[2];
    }
  });
  delayed.resolve(reply([readyPull], { complete: false, refreshing: true }));
  const growthSignal = await growthStarted.promise;
  check(
    "cached PR matches paint before the refresh settles",
    controller.state().phase === "searching",
  );
  unsubscribe();
  const mixed = choices();
  const afterMerge = currentChoice();
  equal("a late PR preserves the selected file", afterMerge, beforeMerge);
  equal("one file and one PR of the same rank both stay near the top", mixed, [
    "render.js",
    "Pull request #123, Fix <em>renderer</em>, Merged",
    "src/renderer.js",
  ]);
  const pullOption = listbox.querySelector(".search-palette-option-pull");
  check(
    "the title renders as text, even with tag-like content",
    pullOption.querySelector("em") === null,
  );
  const titleHighlight = pullOption.querySelector("mark").textContent;
  const details = pullOption.querySelector(".search-palette-description").textContent;
  check("a late insertion keeps the selected row in view", selectedAfterInsertion?.scrollCalls > 0);

  key("ArrowUp");
  equal("the first cached PR can be selected during backfill", currentChoice(), mixed[1]);
  catalog.observeRecent([{ path: "z/render-guide.md", type: "file" }]);
  catalog.observeRecent([{ path: "z/render-notes.md", type: "file" }]);
  await waitMs(220);
  const mixedKeptReading = !growthSignal.aborted && renderReads === 2;
  check("file growth leaves an active title recheck running", mixedKeptReading);
  growth.resolve(reply([newerPull, readyPull], { truncated: true }));
  await titleComplete;
  check(
    "the spinner clears when the PR lookup settles",
    progress.querySelector(".spinner") === null,
  );
  const grown = choices();
  const selectedAfterGrowth = currentChoice();
  const truncatedStatus = progress.textContent;
  equal("newly cached PRs update the standing title query", grown, [
    "render.js",
    "Pull request #124, Render the latest state, Closed",
    "src/renderer.js",
    mixed[1],
  ]);
  equal("refresh preserves the chosen PR as its rank changes", selectedAfterGrowth, mixed[1]);
  check(
    "the API result cap reaches the palette independently of its scan scope",
    truncatedStatus.includes("Showing the top matches.") && !truncatedStatus.includes("older"),
  );

  const catalogRefreshComplete = searchCompletes();
  await Promise.race([catalogRefreshComplete, waitMs(600)]);
  const afterFileGrowth = choices();
  const selectedAfterFileGrowth = currentChoice();
  equal("the two file events coalesce into one search", renderReads, 3);
  check(
    "the deferred refresh finds newly indexed files",
    afterFileGrowth.includes("z/render-guide.md") && afterFileGrowth.includes("z/render-notes.md"),
  );
  equal("file growth preserves the selected PR", selectedAfterFileGrowth, mixed[1]);

  const limitedComplete = searchCompletes();
  type("older");
  await limitedComplete;
  const limitedStatus = progress.textContent;
  check(
    "limited title coverage is distinct from the result cap",
    limitedStatus.includes("Search by number for older pull requests.") &&
      !limitedStatus.includes("Showing the top matches."),
  );

  type("obsolete");
  const obsoleteSignal = await obsoleteStarted.promise;
  check(
    "an active refresh paints its cached matches before the next response",
    choices()[0]?.includes("Obsolete cached match"),
  );
  const numberComplete = searchCompletes();
  type("#123");
  key("Enter");
  equal("an obsolete file cannot open while the query changes", opened, []);
  await numberComplete;
  const exact = choices();
  equal("a hash number limits the search to PRs", exact, [mixed[1]]);
  const staleRequestAborted = obsoleteSignal.aborted;
  check("typing a new query aborts the pending catalog read", staleRequestAborted);
  obsolete.resolve(reply([{ number: 999, title: "Obsolete result", state: "open" }]));
  await settle();
  equal("a superseded result cannot repaint the palette", choices(), exact);
  key("Enter");
  await settle();
  check(
    "opening by keyboard closes and focuses the PR landing",
    !palette.isOpen() && document.activeElement === landing,
  );

  palette.open();
  const bareComplete = searchCompletes();
  type("123");
  await bareComplete;
  const bare = choices();
  equal("bare digits keep file matches and include the exact PR", bare, ["notes/123.md", mixed[1]]);
  const barePull = listbox.querySelector(".search-palette-option-pull");
  barePull.dispatchEvent(fakeEvent("click", { target: barePull }));
  await settle();

  palette.open();
  const warmComplete = searchCompletes();
  type("#77");
  const exactSignal = await exactRecheckStarted.promise;
  catalog.observeRecent([{ path: "new/exact-77.txt", type: "file" }]);
  await waitMs(220);
  const exactKeptReading = !exactSignal.aborted && coldReads === 2;
  check("explicit PR numbers ignore file-catalog updates during a recheck", exactKeptReading);
  exactRecheck.resolve(reply([], { complete: false, refreshing: true }));
  await warmComplete;
  const cold = choices();
  equal("an empty cold catalog can populate within one query", cold, [
    "Pull request #77, Cold catalog match, Open",
  ]);
  key("Enter");
  await settle();
  const pullOpenFailure = dialog.querySelector('[role="status"]').textContent;
  check(
    "open failure describes a pull request",
    pullOpenFailure.includes("Could not open this pull request."),
  );

  const noMatchComplete = searchCompletes();
  type("#999");
  await noMatchComplete;
  equal("nearby misses share the refresh cooldown", warmRequests, 1);
  now += 60_001;
  const afterCooldown = searchCompletes();
  type("#998");
  await afterCooldown;
  equal("a later miss can ask for a new refresh", warmRequests, 2);
  delete sandbox.Date;
  const result = {
    heading,
    placeholder,
    firstPaint,
    mixed,
    afterMerge,
    titleHighlight,
    details,
    grown,
    selectedAfterGrowth,
    truncatedStatus,
    mixedKeptReading,
    afterFileGrowth,
    selectedAfterFileGrowth,
    limitedStatus,
    exact,
    staleRequestAborted,
    bare,
    opened,
    cold,
    exactKeptReading,
    pullOpenFailure,
    requests: requests.map(({ method, url }) => `${method} ${url}`),
  };
  palette.dispose();
  controller.dispose();
  shortcuts.dispose();
  if (failures.length > 0) {
    throw new Error(failures.join("\n"));
  }
  process.stdout.write(`${JSON.stringify(result, null, 2)}\n`);
}

if (require.main === module) {
  main().catch((error) => {
    process.stderr.write(`${error?.stack || error}\n`);
    process.exit(1);
  });
}
module.exports = { pullSearchSession };

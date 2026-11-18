// Browserless session: the shortcut strip at the foot of the navigation pane stays one row.
//
// The owner asked for the strip to list Shift first, as Reveal keys, ahead of `?` for Help,
// and to stay one row: where its items do not all fit, it drops them from the end, Quick
// Search first and then Help, and always keeps Shift (mb-k8am). Help keeps it so
// (`keepStripOnOneRow` in static/keyboard-help.js) from the boxes a ResizeObserver reports.
//
// The registry, the overlay layer, Help and its strip, the Shift reveal, and Quick Search,
// whose command is the strip's last item, load whole, on the key reveal's stand-in DOM
// (tests/dom/key-reveal-dom.js) with injected time. That DOM lays nothing out, so this
// session gives the strip its box, the pane's width less the pane's 1px border, with the
// stylesheet's padding and gap, and gives its items the widths Chrome 152 drew them at in
// the default font set (`STRIP_WIDTHS`), by label, whenever Help reads one; an item that
// is `hidden` has no box, as in a browser. It delivers each size change as a browser's
// ResizeObserver would. Each step records what the strip shows: at each pane width in
// `panes`, and in `strip` once the step is done, the revealed layer's items while Shift
// is held; and `unannounced`, whether the strip's group is hidden from assistive
// technology, as it is where only Shift, itself hidden from it, shows. tests/dom/shortcut-strip-chrome.mjs holds every pane width to the same rule in
// Chrome, with the widths Chrome itself draws.

const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const { FakeDocument, FakeElement, element, keyEvent } = require("./key-reveal-dom.js");

const repoRoot = path.resolve(__dirname, "../..");
const staticDir = path.join(repoRoot, "src/metabrowser/static");
// In load order, as the shell's `shell-tools` bundle runs them.
const MODULES = [
  "formatters.js",
  "keyboard-shortcuts.js",
  "overlay-layer.js",
  "keyboard-help.js",
  "key-reveal.js",
  "search-palette.js",
];
const SOURCES = new Map(
  MODULES.map((name) => [name, fs.readFileSync(path.join(staticDir, name), "utf8")]),
);
// REVEAL_HOLD_MS in static/key-reveal.js.
const HOLD_MS = 200;
// The widths, in px, Chrome 152 drew the strip's items at in the default font set, to a
// tenth, by label; tests/dom/shortcut-strip-chrome.mjs reads them in Chrome.
// "Extra" is a command the session registers on the strip; it is no shell command.
const STRIP_WIDTHS = Object.freeze({
  "Reveal keys": 105.7,
  Help: 43.5,
  "Quick Search": 86.7,
  Extra: 40,
});
// `.nav-shortcut-hints` in static/styles.css: its inline padding and its gap.
const STRIP_PADDING = "12px";
const STRIP_GAP = "6px";

/** Injected time: timers fire only when a step says that much time passed. */
function createClock() {
  let now = 0;
  const timers = new Set();
  return {
    schedule(callback, delayMs) {
      const timer = { at: now + delayMs, callback };
      timers.add(timer);
      return timer;
    },
    cancel(timer) {
      timers.delete(timer);
    },
    advance(ms) {
      now += ms;
      for (const timer of [...timers].sort((left, right) => left.at - right.at)) {
        if (timer.at <= now && timers.has(timer)) {
          timers.delete(timer);
          timer.callback();
        }
      }
    },
  };
}

/** JSON, with each array of plain values on one line, so a pane reads as one row. */
function render(value, indent = "") {
  const inner = `${indent}  `;
  if (Array.isArray(value)) {
    if (value.every((item) => item === null || typeof item !== "object")) {
      return JSON.stringify(value);
    }
    return `[\n${value.map((item) => inner + render(item, inner)).join(",\n")}\n${indent}]`;
  }
  if (value !== null && typeof value === "object") {
    const entries = Object.entries(value);
    if (entries.length === 0) {
      return "{}";
    }
    return `{\n${entries
      .map(([name, item]) => `${inner}${JSON.stringify(name)}: ${render(item, inner)}`)
      .join(",\n")}\n${indent}}`;
  }
  return JSON.stringify(value);
}

function main() {
  const document = new FakeDocument();
  const browserWindow = document.defaultView;
  const clock = createClock();

  // A browser's ResizeObserver, as far as Help uses it: what it observes, and `resized()`
  // to deliver what one would after a layout changed those boxes.
  const observers = [];
  browserWindow.ResizeObserver = class {
    constructor(callback) {
      this.callback = callback;
      this.targets = new Set();
      observers.push(this);
    }
    observe(target) {
      this.targets.add(target);
    }
    unobserve(target) {
      this.targets.delete(target);
    }
    disconnect() {
      this.targets.clear();
    }
  };
  const resized = (...targets) => {
    for (const observer of observers) {
      const entries = targets.filter((target) => observer.targets.has(target));
      if (entries.length > 0) {
        observer.callback(entries.map((target) => ({ target })));
      }
    }
  };

  const context = {
    AbortController,
    Array,
    Element: FakeElement,
    Error,
    HTMLElement: FakeElement,
    JSON,
    Map,
    Math,
    Number,
    Object,
    Promise,
    Set,
    String,
    Symbol,
    TypeError,
    URL,
    URLSearchParams,
    addEventListener: (type, listener, options) =>
      browserWindow.addEventListener(type, listener, options),
    clearTimeout: (timer) => clock.cancel(timer),
    console: { error() {}, log() {}, warn() {} },
    document,
    metabrowser: { decorateExternalLink() {}, ensureAsset: () => new Promise(() => {}) },
    queueMicrotask,
    removeEventListener: (type, listener, options) =>
      browserWindow.removeEventListener(type, listener, options),
    setTimeout: (callback, delayMs) => clock.schedule(callback, delayMs),
  };
  context.window = context;
  context.globalThis = context;
  vm.createContext(context);
  for (const name of MODULES) {
    vm.runInContext(SOURCES.get(name), context, { filename: path.join(staticDir, name) });
  }

  // The navigation pane's foot, as server.py writes it, and what app.js builds on it.
  const hints = element(document, "div", { class: "nav-shortcut-hints", id: "nav-shortcut-hints" });
  document.body.append(element(document, "nav", { class: "tree-pane" }, hints));
  hints.style.setProperty("padding-left", STRIP_PADDING);
  hints.style.setProperty("padding-right", STRIP_PADDING);
  hints.style.setProperty("column-gap", STRIP_GAP);
  // The layout: a strip item's box is the width its label is drawn at in the current
  // text, however the item was made, read as Help reads it.
  let drawn = STRIP_WIDTHS;
  const box = FakeElement.prototype.getBoundingClientRect;
  FakeElement.prototype.getBoundingClientRect = function () {
    if (this.parentNode === hints && !this.classList.contains("nav-shortcut-reveal")) {
      const label = this.querySelector(".nav-shortcut-label")?.textContent ?? "";
      this.rect = { left: 0, top: 0, width: drawn[label] ?? 0, height: 26 };
    }
    return box.call(this);
  };
  const shortcuts = context.MetabrowserKeyboardShortcuts.create({ document });
  const help = context.MetabrowserKeyboardHelp.create({
    document,
    hintHost: hints,
    overlay: context.MetabrowserOverlay,
    shortcuts,
  });
  const reveal = context.MetabrowserKeyReveal.createKeyReveal({
    cancel: clock.cancel,
    document,
    schedule: clock.schedule,
    shortcuts,
    visibility: () => "visible",
  });
  const palette = context.MetabrowserSearchPalette.create({
    controller: { cancel() {}, subscribe: () => () => {} },
    describeOpenFailure: () => ({ message: "" }),
    document,
    getCatalogSnapshot: () => ({ complete: true, observedCount: 0, truncated: false }),
    openFile: async () => ({ status: "opened" }),
    overlay: context.MetabrowserOverlay,
    shortcuts,
  });

  /** What the strip shows: its resting items, or the revealed layer's while it is up. */
  function strip() {
    const layer = hints.querySelector(".nav-shortcut-reveal");
    // An item the row has no room for is `hidden`, not drawn, so it is not listed.
    const items = (host) =>
      host.children
        .filter((child) => !child.classList.contains("nav-shortcut-reveal") && !child.hidden)
        .map(
          (item) =>
            `${item
              .querySelectorAll("kbd")
              .map((keycap) => keycap.textContent)
              .join(" or ")} ${item.querySelector(".nav-shortcut-label")?.textContent}`,
        );
    return layer
      ? { surface: "reveal", items: items(layer) }
      : { surface: "nav", items: items(hints) };
  }

  /** Lay the strip out at each pane width, and say what it shows there. */
  function atPanes(panes) {
    return panes.map((pane) => {
      hints.rect = { left: 0, top: 0, width: pane - 1, height: 39 };
      resized(hints);
      return [pane, ...strip().items];
    });
  }

  /** Text drawn at new widths, as a face or font set draws it: the lead's change reported. */
  function layOutItems(widths) {
    drawn = widths;
    resized(hints.children[0]);
  }
  /** Whether the strip's group is hidden from assistive technology. */
  const unannounced = () => hints.getAttribute("aria-hidden") === "true";

  const key = (type, name, init = {}) =>
    document.body.dispatchEvent(keyEvent(type, name, { target: document.body, ...init }));

  const steps = [];
  steps.push({
    step: "before a layout, the strip lists Shift, Help, and Quick Search",
    strip: strip(),
  });
  hints.rect = { left: 0, top: 0, width: 299, height: 39 };
  layOutItems(STRIP_WIDTHS);
  steps.push({
    step: "a narrowing pane drops Quick Search, then Help, and keeps Shift",
    panes: atPanes([300, 273, 272, 200, 181, 180]),
    unannounced: unannounced(),
  });
  key("keydown", "Shift", { shiftKey: true });
  clock.advance(HOLD_MS);
  steps.push({
    step: "Shift held in the narrowest pane lists what the strip dropped",
    reveal: reveal.snapshot().state,
    strip: strip(),
  });
  key("keyup", "Shift", { shiftKey: false });
  steps.push({
    step: "Shift released, the narrowest pane shows Shift alone",
    reveal: reveal.snapshot().state,
    strip: strip(),
    unannounced: unannounced(),
  });
  // The text changes size in the narrowest pane, with Help and Quick Search dropped: Help
  // measures every item shown, so the dropped ones are measured at their own widths.
  layOutItems({ ...STRIP_WIDTHS });
  steps.push({
    step: "text redrawn in the narrowest pane is measured with every item shown",
    panes: atPanes([180, 181, 273]),
  });
  atPanes([180]);
  // A command the strip gains there, as a registration on the `nav` surface does.
  const releaseExtra = shortcuts.register({
    bindings: [{ key: "x" }],
    copy: { action: "Extra", description: "A command the strip gains.", hint: "Extra" },
    group: "anywhere",
    handler: () => true,
    id: "session.extra",
    order: 90,
    scope: "global",
    surfaces: { nav: "always" },
  });
  steps.push({
    step: "a command the strip gains in the narrowest pane is dropped there",
    strip: strip(),
    panes: atPanes([180, 273, 319]),
  });
  releaseExtra();
  steps.push({
    step: "a widening pane brings Help, then Quick Search, back",
    panes: atPanes([180, 181, 272, 273, 300]),
    unannounced: unannounced(),
  });
  // A face or font set that widens the text: the lead's own box changes, so Help measures
  // every item again. These widths need a 301px pane for all three, as the system font
  // set's did in Chrome 152 on macOS.
  layOutItems({ "Reveal keys": 116, Help: 47.5, "Quick Search": 100 });
  steps.push({
    step: "wider text is measured again: the default pane drops Quick Search, a pixel more keeps it",
    panes: atPanes([300, 301]),
  });
  palette.dispose();
  help.dispose();
  steps.push({
    step: "disposed, Help empties the strip and stops observing it",
    strip: strip(),
    observing: observers.reduce((count, observer) => count + observer.targets.size, 0),
  });
  reveal.dispose();
  shortcuts.dispose();
  process.stdout.write(`${render({ steps })}\n`);
}

main();

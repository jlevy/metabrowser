// Behavioral test for the SDK-owned copy delegate in plugin-sdk.js.
//
// Loads the real SDK into a vm sandbox whose document stub captures the
// delegated click listener, then drives it with fake DOM nodes: a
// wrapWithCopy-style button inside a .content-copy-wrap with a <code>
// child, plus an explicit-value identifier button. Asserts clipboard
// writes, control-specific copied-state feedback, rejection handling,
// and that the delegate never touches a shell copyContent global or a
// button without the data-mb-copy marker.

const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const repoRoot = path.resolve(__dirname, "../..");
const failures = [];
const clipboardWrites = [];
let clickHandler = null;
let copyContentCalls = 0;
const timers = [];

/** @type {any} */
const sandbox = {};
sandbox.window = sandbox;
sandbox.globalThis = sandbox;
sandbox.console = console;
sandbox.setTimeout = (fn, _ms) => {
  timers.push(fn);
  return timers.length;
};
sandbox.clearTimeout = () => {};
sandbox.document = {
  addEventListener: (type, handler) => {
    if (type === "click") {
      clickHandler = handler;
    }
  },
};
let clipboardShouldReject = false;
sandbox.navigator = {
  clipboard: {
    writeText: (text) => {
      clipboardWrites.push(text);
      return clipboardShouldReject ? Promise.reject(new Error("denied")) : Promise.resolve();
    },
  },
};
// A shell global that must NOT be used by the SDK delegate.
sandbox.copyContent = () => {
  copyContentCalls += 1;
};
vm.createContext(sandbox);

for (const filename of [
  "request-error.js",
  "formatters.js",
  "inventory-scope.js",
  "resource-context.js",
  "view-state.js",
  "navigation.js",
]) {
  const source = fs.readFileSync(path.join(repoRoot, "src/metabrowser/static", filename), "utf-8");
  vm.runInContext(source, sandbox, { filename });
}
const sdkSource = fs.readFileSync(
  path.join(repoRoot, "src/metabrowser/static/plugin-sdk.js"),
  "utf-8",
);
vm.runInContext(sdkSource, sandbox, { filename: "plugin-sdk.js" });

if (typeof clickHandler !== "function") {
  failures.push("SDK did not install a delegated click listener");
} else {
  // Build the fake wrap/button/code structure.
  function makeButton(withMarker) {
    const classes = new Set();
    const codeNode = { textContent: "visible segment" };
    const copyPayload = { textContent: "print('hi')\n# complete source" };
    const btn = {
      dataset: withMarker
        ? { mbCopy: "wrap", tipText: "Copy content" }
        : { tipText: "Copy content" },
      classList: {
        add: (c) => classes.add(c),
        remove: (c) => classes.delete(c),
        has: (c) => classes.has(c),
      },
      _classes: classes,
    };
    const wrap = {
      childNodes: [btn, copyPayload, codeNode],
      querySelector: (sel) => {
        if (sel === "[data-mb-copy-payload]") {
          return copyPayload;
        }
        return sel === "code" ? codeNode : null;
      },
    };
    btn.closest = (sel) => (sel === ".content-copy-wrap" ? wrap : null);
    const target = { closest: (sel) => (sel === "[data-mb-copy]" && withMarker ? btn : null) };
    return { btn, target };
  }

  function makeTextButton(text, label) {
    const classes = new Set();
    const btn = {
      dataset: { mbCopy: "text", mbCopyText: text, mbCopyLabel: label, tipText: label },
      classList: {
        add: (c) => classes.add(c),
        remove: (c) => classes.delete(c),
        has: (c) => classes.has(c),
      },
      _classes: classes,
    };
    return {
      btn,
      target: { closest: (sel) => (sel === "[data-mb-copy]" ? btn : null) },
    };
  }

  // Case 1: marked button prefers an explicit whole-source payload over a
  // visible segment and shows feedback.
  const first = makeButton(true);
  clickHandler({ target: first.target });
  Promise.resolve()
    .then(() => {
      if (clipboardWrites.length !== 1 || clipboardWrites[0] !== "print('hi')\n# complete source") {
        failures.push(`expected one code write, got ${JSON.stringify(clipboardWrites)}`);
      }
      if (!first.btn.classList.has("copied") || first.btn.dataset.tipText !== "Copied!") {
        failures.push(
          `expected copied feedback, got tip=${first.btn.dataset.tipText} classes=${[...first.btn._classes]}`,
        );
      }
      // Feedback timer restores the resting state.
      for (const fn of timers.splice(0)) {
        fn();
      }
      if (first.btn.classList.has("copied") || first.btn.dataset.tipText !== "Copy content") {
        failures.push("copied state did not reset after the feedback timer");
      }

      // Case 2: an explicit-text button copies its exact hidden payload and
      // restores its control-specific resting label.
      const direct = makeTextButton("0123456789abcdef", "Copy revision");
      clickHandler({ target: direct.target });
      return Promise.resolve().then(() => {
        if (clipboardWrites[1] !== "0123456789abcdef") {
          failures.push(`expected explicit text write, got ${JSON.stringify(clipboardWrites)}`);
        }
        if (!direct.btn.classList.has("copied") || direct.btn.dataset.tipText !== "Copied!") {
          failures.push(`expected direct copied feedback, got tip=${direct.btn.dataset.tipText}`);
        }
        for (const fn of timers.splice(0)) {
          fn();
        }
        if (direct.btn.classList.has("copied") || direct.btn.dataset.tipText !== "Copy revision") {
          failures.push("direct copied state did not restore its resting label");
        }

        // Case 3: rejected clipboard promises report failure without a copied class.
        clipboardShouldReject = true;
        const second = makeButton(true);
        clickHandler({ target: second.target });
        return Promise.resolve()
          .then(() => {})
          .then(() => {
            if (
              second.btn.dataset.tipText !== "Copy failed" ||
              second.btn.classList.has("copied")
            ) {
              failures.push(`expected rejection feedback, got tip=${second.btn.dataset.tipText}`);
            }
          });
      });
    })
    .then(() => {
      // Case 4: unmarked buttons are ignored entirely.
      const third = makeButton(false);
      const before = clipboardWrites.length;
      clickHandler({ target: third.target });
      if (clipboardWrites.length !== before) {
        failures.push("delegate handled a button without data-mb-copy");
      }
      if (copyContentCalls !== 0) {
        failures.push("delegate called the shell copyContent global");
      }
      if (failures.length > 0) {
        console.error(JSON.stringify({ failures }, null, 2));
        process.exit(1);
      }
      console.log("sdk copy delegate OK");
    });
}

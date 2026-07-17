// Behavioral test for the SDK-owned copy delegate in plugin_sdk.js.
//
// Loads the real SDK into a vm sandbox whose document stub captures the
// delegated click listener, then drives it with fake DOM nodes: a
// wrapWithCopy-style button inside a .content-copy-wrap with a <code>
// child. Asserts clipboard writes, copied-state feedback, rejection
// handling, and that the delegate never touches a shell copyContent
// global and ignores buttons without the data-mb-copy marker.

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

const sdkSource = fs.readFileSync(
  path.join(repoRoot, "src/metabrowser/static/plugin_sdk.js"),
  "utf-8",
);
vm.runInContext(sdkSource, sandbox, { filename: "plugin_sdk.js" });

if (typeof clickHandler !== "function") {
  failures.push("SDK did not install a delegated click listener");
} else {
  // Build the fake wrap/button/code structure.
  function makeButton(withMarker) {
    const classes = new Set();
    const codeNode = { textContent: "print('hi')" };
    const btn = {
      title: "Copy content",
      classList: {
        add: (c) => classes.add(c),
        remove: (c) => classes.delete(c),
        has: (c) => classes.has(c),
      },
      _classes: classes,
    };
    const wrap = {
      childNodes: [btn, codeNode],
      querySelector: (sel) => (sel === "code" ? codeNode : null),
    };
    btn.closest = (sel) => (sel === ".content-copy-wrap" ? wrap : null);
    const target = {
      closest: (sel) => (sel === ".content-copy-btn[data-mb-copy]" && withMarker ? btn : null),
    };
    return { btn, target };
  }

  // Case 1: marked button copies the code text and shows feedback.
  const first = makeButton(true);
  clickHandler({ target: first.target });
  Promise.resolve()
    .then(() => {
      if (clipboardWrites.length !== 1 || clipboardWrites[0] !== "print('hi')") {
        failures.push(`expected one code write, got ${JSON.stringify(clipboardWrites)}`);
      }
      if (!first.btn.classList.has("copied") || first.btn.title !== "Copied!") {
        failures.push(
          `expected copied feedback, got title=${first.btn.title} classes=${[...first.btn._classes]}`,
        );
      }
      // Feedback timer restores the resting state.
      for (const fn of timers.splice(0)) {
        fn();
      }
      if (first.btn.classList.has("copied") || first.btn.title !== "Copy content") {
        failures.push("copied state did not reset after the feedback timer");
      }

      // Case 2: rejected clipboard promise reports failure, no copied class.
      clipboardShouldReject = true;
      const second = makeButton(true);
      clickHandler({ target: second.target });
      return Promise.resolve()
        .then(() => {})
        .then(() => {
          if (second.btn.title !== "Copy failed" || second.btn.classList.has("copied")) {
            failures.push(`expected rejection feedback, got title=${second.btn.title}`);
          }
        });
    })
    .then(() => {
      // Case 3: unmarked buttons are ignored entirely.
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

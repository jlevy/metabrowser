// Browserless session: the plugin shortcut surface, on the production code.
//
// `window.metabrowser.shortcuts.attach()` gives a plugin view's control a letter key
// and a badge. The eager SDK (static/plugin-sdk.js) queues each attachment made before
// the facade (static/plugin-shortcuts.js) loads, and the facade takes the queue and
// replays every attachment onto each shortcut registry the shell attaches. This loads
// the SDK and its startup prerequisites, the registry, the overlay layer, Help, the
// facade, and view composition whole, in the shell's order, into one page, and plays a
// plugin view's controls and the shell's side around them: the registry the shell
// builds and rebuilds, a shell key that holds a letter, the inert stage a retained
// navigation mounts into, and the reveal the Shift key turns on.
//
// The reserved shell keys come from METABROWSER_SETTINGS as the server serves them,
// copied here from src/metabrowser/keymap.py; tests/test_keymap.py holds the copy this
// prints, and the letters the facade refused, to that table.
//
// Each step records the plugin keys the registry holds, which run now and on what, the
// controls' `aria-keyshortcuts`, the badges mounted, what the controls were asked to do,
// and what the facade warned.

const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const { FakeDocument, FakeElement, element, keyEvent } = require("./key-reveal-dom.js");

const repoRoot = path.resolve(__dirname, "../..");
const staticDir = path.join(repoRoot, "src/metabrowser/static");

// `serialize_reserved_shell_keys()` in src/metabrowser/keymap.py.
const RESERVED_SHELL_KEYS = Object.freeze({
  t: null,
  j: null,
  k: null,
  u: null,
  w: null,
  x: null,
  y: null,
  a: null,
  ...Object.fromEntries([..."0123456789"].map((digit) => [digit, null])),
  n: ["pull-request"],
  p: ["pull-request"],
});

// The startup scripts the SDK needs, then the SDK; then the `shell-tools` scripts this
// session needs, in the bundle's order; then view composition, which loads on demand.
const STARTUP = [
  "request-error.js",
  "formatters.js",
  "inventory-scope.js",
  "resource-context.js",
  "view-state.js",
  "navigation.js",
  "plugin-sdk.js",
];
const SHELL_TOOLS = ["keyboard-shortcuts.js", "overlay-layer.js", "keyboard-help.js"];
const SOURCES = new Map(
  [...STARTUP, ...SHELL_TOOLS, "plugin-shortcuts.js", "view-composition.js"].map((name) => [
    name,
    fs.readFileSync(path.join(staticDir, name), "utf8"),
  ]),
);

function assert(condition, message) {
  if (!condition) {
    throw new Error(message);
  }
}

/** A control's label as a reader sees it, without a badge mounted inside it. */
function labelOf(node) {
  return node.childNodes
    .filter((child) => !(child instanceof FakeElement && child.classList.contains("kbd-badge")))
    .map((child) => child.textContent)
    .join("")
    .trim();
}

/** One page: its DOM, the production scripts in a fresh global, and what the shell does. */
function createPage() {
  const document = new FakeDocument();
  const did = [];
  const warnings = [];
  const errors = [];
  const context = {
    AbortController,
    Array,
    Element: FakeElement,
    Error,
    HTMLElement: FakeElement,
    JSON,
    Map,
    Math,
    Node: Object.getPrototypeOf(FakeElement),
    Number,
    Object,
    Promise,
    Set,
    String,
    Symbol,
    TypeError,
    URL,
    URLSearchParams,
    addEventListener() {},
    clearTimeout,
    console: {
      error: (...args) => errors.push(args.map((arg) => arg?.message ?? String(arg)).join(" ")),
      log() {},
      warn: (...args) => warnings.push(args.join(" ")),
    },
    document,
    history: { pushState() {}, replaceState() {}, state: null },
    location: { hash: "", origin: "http://metabrowser.test", pathname: "/view/", search: "" },
    METABROWSER_SETTINGS: { RESERVED_SHELL_KEYS },
    queueMicrotask,
    removeEventListener() {},
    setTimeout,
  };
  context.window = context;
  context.globalThis = context;
  vm.createContext(context);
  const load = (name) =>
    vm.runInContext(SOURCES.get(name), context, { filename: path.join(staticDir, name) });
  for (const name of STARTUP) {
    load(name);
  }

  // ── The shell's DOM: a strip, a main pane, and a plugin view in it ─────────
  const hints = element(document, "div", { class: "nav-shortcut-hints", id: "nav-shortcut-hints" });
  const preview = element(document, "main", { id: "preview-pane" });
  document.body.append(element(document, "nav", { class: "tree-pane" }, hints), preview);

  /** A control of a plugin's view, as a plugin renders it. */
  const control = (label, attributes = {}) =>
    element(document, "button", { class: "chip", type: "button", ...attributes }, label);

  /**
   * The spec a plugin passes for one control. Its `activate` records that it ran, and
   * for what: `ran`, which two mounts of one command id tell apart.
   */
  const spec = (id, key, label, extra = {}, ran = label) => ({
    activate: () => did.push(`${id} ran for ${ran}`),
    copy: { action: label, description: `${label}, from the demo plugin.`, hint: label },
    group: "controls",
    id,
    key,
    order: 10,
    ...extra,
  });

  // ── What app.js does with the keyboard infrastructure ─────────────────────
  let shortcuts = null;
  let help = null;
  let detachPluginShortcuts = null;

  /** initKeyboardInfrastructure: the registry, Help, and the plugin facade's replay. */
  function build() {
    shortcuts = context.MetabrowserKeyboardShortcuts.create({ document });
    help = context.MetabrowserKeyboardHelp.create({
      document,
      hintHost: hints,
      overlay: context.MetabrowserOverlay,
      shortcuts,
    });
    detachPluginShortcuts = context.MetabrowserPluginShortcuts.attachShortcutRegistry(shortcuts);
  }

  /** disposeKeyboardInfrastructure, for a real pagehide: the facade lets go first. */
  function teardown() {
    detachPluginShortcuts();
    help.dispose();
    shortcuts.dispose();
    shortcuts = null;
  }

  // ── Reading what the page shows ───────────────────────────────
  const tracked = [];
  /** Follow a control in every step's `aria` line. */
  function track(node) {
    tracked.push(node);
    return node;
  }

  /** The plugin keys the registry holds: key, command, and what it runs on now. */
  function keys() {
    if (!shortcuts) {
      return [];
    }
    return shortcuts
      .snapshot("help", { includeInactive: true })
      .flatMap((group) => group.commands)
      .flatMap((command) => command.commandIds)
      .filter((id) => shortcuts.present(id).scope === "plugin")
      .map((id) => {
        const target = shortcuts.isLive(id) ? shortcuts.liveTarget(id) : null;
        const key = shortcuts.present(id).bindings.visible.join(" or ");
        return `${key} ${id}: ${target ? labelOf(target) : "not live"}`;
      });
  }

  function aria() {
    return tracked.map(
      (node) => `${labelOf(node)}: ${node.getAttribute("aria-keyshortcuts") ?? "none"}`,
    );
  }

  function badges() {
    return document.body
      .querySelectorAll(".kbd-badge")
      .map((badge) => `${badge.textContent} on ${labelOf(badge.parentNode)}`);
  }

  /** What one step shows, and what was done and warned since the last step. */
  function record(step, extra = {}) {
    const entry = { step, keys: keys(), aria: aria(), ...extra };
    if (shortcuts?.isRevealed()) {
      entry.badges = badges();
    }
    for (const [name, list] of [
      ["did", did],
      ["warned", warnings],
      ["errors", errors],
    ]) {
      if (list.length > 0) {
        entry[name] = list.splice(0);
      }
    }
    return entry;
  }

  // ── Input ─────────────────────────────────────────────────────
  /** A key pressed outside any field; true when a command handled it. */
  function press(name, init = {}) {
    const target = document.activeElement ?? document.body;
    const event = keyEvent("keydown", name, { target, ...init });
    target.dispatchEvent(event);
    target.dispatchEvent(keyEvent("keyup", name, { target, ...init }));
    return event.defaultPrevented;
  }

  /** The Help dialog's groups as a reader sees them: heading, then each key and label. */
  function helpShown() {
    return document.body.querySelectorAll(".help-shortcut-group").map((group) => [
      group.querySelector(".help-shortcut-heading").textContent,
      ...group.querySelectorAll(".help-command-row").map(
        (row) =>
          `${row
            .querySelector(".help-command-binding")
            .querySelectorAll("kbd")
            .map((keycap) => keycap.textContent)
            .join(" or ")} ${row.querySelector(".help-command-label").textContent}`,
      ),
    ]);
  }

  return {
    build,
    context,
    control,
    did,
    document,
    errors,
    help: () => help,
    helpShown,
    load,
    preview,
    press,
    record,
    get shortcuts() {
      return shortcuts;
    },
    spec,
    teardown,
    track,
    warnings,
  };
}

/** Whether a node sits in an `inert` subtree, as Help's overlay leaves the page behind it. */
function underInert(node) {
  for (let at = node; at instanceof FakeElement; at = at.parentNode) {
    if (at.inert) {
      return true;
    }
  }
  return false;
}

/** What a malformed call throws, or that it did not throw. */
function thrown(work) {
  try {
    work();
  } catch (error) {
    return error.message;
  }
  return "did not throw";
}

/** JSON, with each array of plain values on one line, so a key reads as one row. */
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

async function main() {
  const steps = [];
  const page = createPage();
  const { context, control, document, preview, spec, track } = page;
  const mb = context.metabrowser;
  const view = element(document, "div", { class: "content-body demo-host" });
  preview.append(view);

  // ── Before the facade and the registry ────────────────────────
  const unified = track(control("Unified", { "aria-checked": "false" }));
  const stale = track(control("Stale"));
  const before = track(control("Before"));
  const after = track(control("After"));
  view.append(unified, stale, before, after);
  const layout = mb.shortcuts.attach(
    unified,
    spec("demo.layout", "L", "Unified", {}, "the first view's layout"),
  );
  mb.shortcuts.attach(stale, spec("demo.stale", "q", "Stale")).detach();
  mb.shortcuts.attach(before, spec("demo.moved", "m", "Moved")).retarget(after);
  mb.shortcuts.attach("#not-an-element", spec("demo.broken", "b", "Broken"));
  steps.push(
    page.record("attached before the facade loads: the SDK queues each one still attached", {
      queued: context.MetabrowserPluginHost.shortcutQueue.size,
    }),
  );

  for (const name of ["keyboard-shortcuts.js", "overlay-layer.js", "keyboard-help.js"]) {
    page.load(name);
  }
  page.load("plugin-shortcuts.js");
  steps.push(
    page.record("the facade loads and takes the queue; the malformed one is logged", {
      queued: context.MetabrowserPluginHost.shortcutQueue.size,
    }),
  );

  page.build();
  steps.push(page.record("the shell's registry: the queue's keys are replayed onto it"));

  // ── Dispatch, with and without Shift ──────────────────────────
  steps.push(
    page.record("L runs the control's own activation", {
      handled: page.press("l"),
    }),
  );
  steps.push(
    page.record("Shift does not change it", {
      handled: page.press("L", { shiftKey: true }),
    }),
  );
  steps.push(
    page.record("M runs on the control it was retargeted to before the facade loaded", {
      handled: page.press("m"),
    }),
  );
  steps.push(
    page.record("Q, detached before the facade loaded, was never bound", {
      handled: page.press("q"),
    }),
  );
  const ctrl = page.press("l", { ctrlKey: true });
  assert(!ctrl, "a plugin key with Ctrl ran");
  const repeated = page.press("l", { repeat: true });
  assert(!repeated, "a plugin key ran on repeat");

  // ── The reveal ────────────────────────────────────────────────
  page.shortcuts.setRevealed(true);
  steps.push(
    page.record("revealed: each live plugin key badges its control, and none is on the strip", {
      strip: page.document
        .querySelectorAll(".nav-shortcut-reveal .nav-shortcut-label")
        .map((label) => label.textContent),
    }),
  );
  page.shortcuts.setRevealed(false);

  // ── Help, through the real overlay layer ──────────────────────
  page.press("?", { shiftKey: true });
  steps.push(
    page.record("Help, open: the plugin keys are listed though Help made their controls inert", {
      controlInert: underInert(unified),
      help: page.helpShown(),
    }),
  );
  page.press("Escape");

  // ── Letters the shell reserves ────────────────────────────────
  const find = track(control("Find"));
  const findAgain = control("Find again");
  const next = track(control("Next"));
  view.append(find, findAgain, next);
  mb.shortcuts.attach(find, spec("demo.find", "t", "Find"));
  mb.shortcuts.attach(findAgain, spec("demo.find", "t", "Find"));
  mb.shortcuts.attach(next, spec("demo.next", "N", "Next", { group: "view-tabs" }));
  steps.push(
    page.record("T and N are the shell's: refused, with one warning for each command id", {
      handledT: page.press("t"),
      handledN: page.press("n"),
    }),
  );
  const probes = [..."abcdefghijklmnopqrstuvwxyz"].map((letter) => {
    const probe = control(`Probe ${letter}`);
    view.append(probe);
    const handle = mb.shortcuts.attach(probe, spec(`probe.${letter}`, letter, `Probe ${letter}`));
    const refused = !probe.hasAttribute("aria-keyshortcuts");
    handle.detach();
    probe.remove();
    return refused ? letter : null;
  });
  page.warnings.splice(0);
  steps.push(
    page.record("every letter tried: the facade refuses exactly the reserved ones", {
      reservedKeys: Object.entries(RESERVED_SHELL_KEYS)
        .map(([key, kinds]) => `${key}: ${kinds === null ? "every kind" : kinds.join(" ")}`)
        .sort(),
      refused: probes.filter(Boolean),
    }),
  );

  // ── Two plugins on one letter ─────────────────────────────────
  const alpha = track(control("Alpha"));
  const beta = track(control("Beta"));
  view.append(alpha, beta);
  const alphaKey = mb.shortcuts.attach(alpha, spec("alpha.open", "o", "Open alpha"));
  mb.shortcuts.attach(beta, spec("beta.open", "o", "Open beta"));
  page.shortcuts.setRevealed(true);
  steps.push(
    page.record("two plugins on O, both shown: the earlier runs and badges, the later is warned", {
      handled: page.press("o"),
    }),
  );
  page.shortcuts.setRevealed(false);
  alpha.style.display = "none";
  steps.push(
    page.record("the earlier's control hidden: the later's key runs", {
      handled: page.press("o"),
    }),
  );
  alpha.style.display = "";
  alphaKey.detach();
  steps.push(
    page.record("the earlier lets go: O is registered again with the later's copy", {
      help: page.shortcuts
        .snapshot("help", { includeInactive: true })
        .flatMap((group) => group.commands)
        .filter((command) => command.scope === "plugin")
        .map((command) => command.copy.action),
    }),
  );

  // ── A shell key beats a plugin key ────────────────────────────
  const logTab = track(
    element(document, "button", { class: "tab-btn", "data-tab": "log", type: "button" }, "Log"),
  );
  preview.insertBefore(logTab, preview.firstChild ?? null);
  // A view tab's L, as static/shell-keymap.js registers one.
  const releaseLog = page.shortcuts.register({
    bindings: [{ key: "l" }],
    copy: { action: "Log", description: "Show the Log view.", hint: "Log" },
    group: "view-tabs",
    handler: () => {
      page.did.push("the shell selected the Log tab");
      return true;
    },
    id: "view-tabs.l",
    order: 1,
    scope: "view-tabs",
    surfaces: { help: "always" },
    targeted: true,
  });
  const logTarget = page.shortcuts.attachTarget("view-tabs.l", logTab);
  page.shortcuts.setRevealed(true);
  steps.push(
    page.record("a shell tab holds L beside the plugin's: the shell's runs and alone badges", {
      handled: page.press("l"),
    }),
  );
  page.shortcuts.setRevealed(false);
  logTarget.detach();
  releaseLog();
  logTab.remove();
  steps.push(
    page.record("the shell's tab gone: L reaches the plugin again", {
      handled: page.press("l"),
    }),
  );

  // ── Two mounts of one command id ──────────────────────────────
  const secondView = element(document, "div", { class: "content-body demo-host" });
  const unifiedTwo = track(control("Unified (second view)", { "aria-checked": "false" }));
  secondView.append(unifiedTwo);
  preview.append(secondView);
  const second = mb.shortcuts.attach(
    unifiedTwo,
    spec("demo.layout", "l", "Unified", {}, "the second view's layout"),
  );
  steps.push(
    page.record("a second mount of demo.layout: one command, two targets, the first runs", {
      handled: page.press("l"),
    }),
  );
  view.style.display = "none";
  steps.push(
    page.record("the first view hidden: the second's runs", {
      handled: page.press("l"),
    }),
  );
  view.style.display = "";
  second.detach();
  secondView.remove();

  // ── Rebuilt markup, removal, and the inert stage ──────────────
  const split = track(control("Split", { "aria-checked": "false" }));
  view.replaceChildren(split, stale, after, find, next, alpha, beta);
  layout.retarget(split);
  steps.push(
    page.record("the control rebuilt its markup and retargeted: the key moves with it", {
      handled: page.press("l"),
    }),
  );
  view.remove();
  steps.push(
    page.record("the view taken out of the page: the attachment stays, and does nothing", {
      handled: page.press("l"),
    }),
  );
  page.shortcuts.setRevealed(true);
  preview.append(view);
  const unbadged = page.document.querySelectorAll(".kbd-badge").length;
  // As the pull request page's header puts its tab column back: the same element.
  layout.retarget(split);
  steps.push(
    page.record("put back while revealed, and retargeted to the same control: badged at once", {
      badgesBeforeRetarget: unbadged,
    }),
  );
  page.shortcuts.setRevealed(false);
  steps.push(
    page.record("the key returns with it", {
      handled: page.press("l"),
    }),
  );
  const stage = element(document, "div", { class: "preview-file-stage", inert: true });
  preview.append(stage);
  stage.append(view);
  steps.push(
    page.record("staged in the shell's inert stage: not live", {
      handled: page.press("l"),
    }),
  );
  preview.append(view);
  stage.remove();
  steps.push(
    page.record("committed out of the stage: live again", {
      handled: page.press("l"),
    }),
  );

  // ── Abort, and an idempotent detach ───────────────────────────
  const close = track(control("Close"));
  view.append(close);
  const closing = new AbortController();
  const closeKey = mb.shortcuts.attach(
    close,
    spec("demo.close", "c", "Close", { signal: closing.signal }),
  );
  const closeAttached = close.getAttribute("aria-keyshortcuts");
  closing.abort();
  closeKey.detach();
  closeKey.detach();
  const aborted = new AbortController();
  aborted.abort();
  const late = control("Late");
  view.append(late);
  mb.shortcuts.attach(late, spec("demo.late", "z", "Late", { signal: aborted.signal })).detach();
  steps.push(
    page.record("its signal aborted, then detached twice: the key is gone, and nothing threw", {
      ariaWhileAttached: closeAttached,
      handled: page.press("c"),
      lateAria: late.getAttribute("aria-keyshortcuts"),
    }),
  );
  late.remove();

  // ── Malformed input ───────────────────────────────────────────
  steps.push(
    page.record("malformed input throws, prefixed shortcuts.attach:", {
      thrown: [
        thrown(() => mb.shortcuts.attach(null, spec("demo.none", "g", "None"))),
        thrown(() => mb.shortcuts.attach(control("x"), spec("demo.digit", "1", "Digit"))),
        thrown(() => mb.shortcuts.attach(control("x"), spec("demo.long", "gg", "Long"))),
        thrown(() =>
          mb.shortcuts.attach(control("x"), spec("demo.group", "g", "Group", { group: "tabs" })),
        ),
        thrown(() =>
          mb.shortcuts.attach(control("x"), spec("demo.inert", "g", "Inert", { activate: null })),
        ),
        thrown(() => mb.shortcuts.attach(control("x"), spec("undotted", "g", "Undotted"))),
        thrown(() =>
          mb.shortcuts.attach(
            control("x"),
            spec("demo.bound", "g", "Bound", { bindings: [{ key: "g" }] }),
          ),
        ),
        thrown(() => mb.shortcuts.attach(control("x"), spec("demo.layout", "g", "Unified"))),
        thrown(() => layout.retarget("#not-an-element")),
      ],
    }),
  );

  // ── Registry teardown and rebuild ─────────────────────────────
  page.teardown();
  steps.push(
    page.record("pagehide: the facade lets go, then the registry is disposed", {
      handled: page.press("l"),
    }),
  );
  page.build();
  steps.push(
    page.record("pageshow: a new registry, and every attachment replayed onto it", {
      handled: page.press("l"),
    }),
  );

  // ── View composition's net under a view's own dispose ─────────
  page.load("view-composition.js");
  const composition = context.MetabrowserViewComposition;
  const lifecycle = composition.createLifecycle();
  const staged = lifecycle.begin();
  const leakyHost = element(document, "div", { class: "content-body leaky-host" });
  let leaky = null;
  preview.append(leakyHost);
  const leakyMount = composition.mount(
    leakyHost,
    {
      render(container) {
        leaky = track(control("Leaky"));
        container.append(leaky);
        mb.shortcuts.attach(leaky, spec("demo.leaky", "v", "Leaky"));
        // Its dispose forgets the key.
        return { dispose() {} };
      },
    },
    {},
    staged.disposers,
  );
  assert((await leakyMount) === "mounted", "the leaky view did not mount");
  staged.commit(() => {});
  const leakyAria = leaky.getAttribute("aria-keyshortcuts");
  lifecycle.disposeActive();
  steps.push(
    page.record("a view whose dispose forgot its key: view composition releases it", {
      ariaWhileMounted: leakyAria,
      handled: page.press("v"),
    }),
  );
  leaky.remove();

  // A view's own root, which its dispose takes out of the container, as the diff view's does.
  const rootedHost = element(document, "div", { class: "content-body rooted-host" });
  preview.append(rootedHost);
  const rootedStage = lifecycle.begin();
  let rooted = null;
  const rootedMount = composition.mount(
    rootedHost,
    {
      render(container) {
        const root = element(document, "div", { class: "rooted-root" });
        rooted = track(control("Rooted"));
        root.append(rooted);
        container.append(root);
        mb.shortcuts.attach(rooted, spec("demo.rooted", "r", "Rooted"));
        // Its dispose removes its root and forgets the key.
        return {
          dispose() {
            root.remove();
          },
        };
      },
    },
    {},
    rootedStage.disposers,
  );
  assert((await rootedMount) === "mounted", "the rooted view did not mount");
  rootedStage.commit(() => {});
  const rootedAria = rooted.getAttribute("aria-keyshortcuts");
  lifecycle.disposeActive();
  steps.push(
    page.record("a view whose dispose removed its own root and forgot its key: released", {
      ariaWhileMounted: rootedAria,
    }),
  );
  rootedHost.remove();

  // A render that finishes after its stage was cancelled, which view composition disposes.
  const slowHost = element(document, "div", { class: "content-body slow-host" });
  preview.append(slowHost);
  const slowStage = lifecycle.begin();
  let finishSlow = () => {};
  const slowMount = composition.mount(
    slowHost,
    {
      async render(container) {
        await new Promise((resolve) => {
          finishSlow = resolve;
        });
        const root = element(document, "div", { class: "slow-root" });
        const slow = track(control("Slow"));
        root.append(slow);
        container.append(root);
        mb.shortcuts.attach(slow, spec("demo.slow", "s", "Slow"));
        return {
          dispose() {
            root.remove();
          },
        };
      },
    },
    {},
    slowStage.disposers,
  );
  slowStage.cancel();
  finishSlow();
  assert((await slowMount) === "cancelled", "the slow view was not cancelled");
  steps.push(page.record("a render that finished after its stage was cancelled: released"));
  slowHost.remove();

  // A render that attached a key and then failed, whose error state replaces its DOM.
  const failingHost = element(document, "div", { class: "content-body failing-host" });
  preview.append(failingHost);
  const failingStage = lifecycle.begin();
  const failingMount = composition.mount(
    failingHost,
    {
      render(container) {
        const failing = track(control("Failing"));
        container.append(failing);
        mb.shortcuts.attach(failing, spec("demo.failing", "f", "Failing"));
        throw new Error("the demo view failed");
      },
    },
    {},
    failingStage.disposers,
    { renderError: (container) => container.replaceChildren() },
  );
  assert((await failingMount) === "error", "the failing view did not fail");
  steps.push(page.record("a render that attached a key and then failed: released"));
  failingStage.cancel();
  failingHost.remove();

  // The same net before the facade has loaded, on a page of its own.
  const early = createPage();
  early.load("view-composition.js");
  const earlyHost = element(early.document, "div", { class: "content-body" });
  early.preview.append(earlyHost);
  const earlyLifecycle = early.context.MetabrowserViewComposition.createLifecycle();
  const earlyStage = earlyLifecycle.begin();
  const earlyControl = early.track(early.control("Early"));
  const earlyMount = early.context.MetabrowserViewComposition.mount(
    earlyHost,
    {
      render(container) {
        container.append(earlyControl);
        early.context.metabrowser.shortcuts.attach(
          earlyControl,
          early.spec("demo.early", "e", "Early"),
        );
        return { dispose() {} };
      },
    },
    {},
    earlyStage.disposers,
  );
  assert((await earlyMount) === "mounted", "the early view did not mount");
  assert(
    early.context.MetabrowserPluginHost.shortcutQueue.size === 1,
    "the early view's key was not queued",
  );
  earlyStage.commit(() => {});
  earlyLifecycle.disposeActive();
  const queuedAfterDispose = early.context.MetabrowserPluginHost.shortcutQueue.size;
  for (const name of [...SHELL_TOOLS, "plugin-shortcuts.js"]) {
    early.load(name);
  }
  early.build();
  steps.push(
    early.record("disposed while queued, before the facade loaded: never bound", {
      queuedAfterDispose,
      handled: early.press("e"),
    }),
  );

  console.log(render({ steps }));
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});

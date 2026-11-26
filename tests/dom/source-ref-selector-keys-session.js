// Browserless session: the branch switcher's open list leaves every chord to the browser
// (mb-i1wy), and still moves, wraps, and closes on the plain keys.
//
// static/filter-controls.js and static/source-ref-selector.js load whole on the stand-in DOM
// of tests/dom/key-reveal-dom.js, and the selector mounts as the shell mounts it. Its listing
// is answered with the recorded branches of tests/fixtures/source-ref-selector-responses.json,
// so the list has rows. With the list open, every key its two listeners handle is pressed
// with Command, Shift-Command, Control, and Option, from the filter, from a row, and from a
// kind tab: none may be taken (`preventDefault`), close the list, or move focus. Option-Tab
// is the one chord the list keeps, since Safari moves focus with it, so the trap wraps it.
// The session prints what each place saw and what the plain keys did, and exits 1 when a
// chord was taken; tests/golden/cli-ui-source-ref-selector-keys.tryscript.md pins it.

const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const { FakeDocument, FakeElement, element, keyEvent } = require("./key-reveal-dom.js");

const repoRoot = path.resolve(__dirname, "../..");
const staticDir = path.join(repoRoot, "src/metabrowser/static");
const recorded = JSON.parse(
  fs.readFileSync(path.join(repoRoot, "tests/fixtures/source-ref-selector-responses.json"), "utf8"),
);
const failures = [];
let answer = recorded.branches;

function check(name, condition, detail = "") {
  if (!condition) {
    failures.push(`${name}${detail ? `: ${detail}` : ""}`);
  }
}

const document = new FakeDocument();
const browserWindow = document.defaultView;
const requests = [];
let rejectNextHead = false;
let now = Date.parse("2026-11-26T12:00:00Z");
const context = {
  AbortController,
  Date: class extends Date {
    static now() {
      return now;
    }
  },
  HTMLElement: FakeElement,
  Error,
  JSON,
  Map,
  Object,
  Promise,
  Set,
  String,
  URLSearchParams,
  console,
  document,
  location: { pathname: "/view/", assign() {} },
  metabrowser: {
    formatTimestamp: (seconds) => new Date(seconds * 1000).toISOString(),
    mountRefMenus: () => () => {},
    refChip: (name) => element(document, "span", { class: "ref-chip git-ref" }, name),
    escapeHtml: (text) =>
      String(text).replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;"),
  },
  METABROWSER_SOURCE_PIN: { ref: recorded.branches.body.ref, ref_name: "topic" },
  async fetch(route, init) {
    requests.push(init?.method === "POST" ? `POST ${route} ${init.body}` : route);
    if (rejectNextHead && route === "/api/source/refs?kind=working_tree") {
      rejectNextHead = false;
      throw new Error("Network unavailable");
    }
    return { status: answer.status, json: async () => answer.body };
  },
  setTimeout: () => 0,
  clearTimeout() {},
  addEventListener: (type, listener, options) =>
    browserWindow.addEventListener(type, listener, options),
  removeEventListener: (type, listener, options) =>
    browserWindow.removeEventListener(type, listener, options),
};
context.window = context;
context.globalThis = context;
vm.createContext(context);
// formatters.js gives each row's commit its short ID and age, as the shell's startup
// scripts do, and menus.js closes the list as every menu closes.
for (const name of [
  "formatters.js",
  "filter-controls.js",
  "menus.js",
  "source-ref-selector.js",
  "refresh-plan.js",
]) {
  vm.runInContext(fs.readFileSync(path.join(staticDir, name), "utf8"), context, {
    filename: path.join(staticDir, name),
  });
}

/** Let every promise chain that needs no further input run. */
async function settle() {
  for (let turn = 0; turn < 10; turn += 1) {
    await new Promise((resolve) => setImmediate(resolve));
  }
}

const host = element(document, "div", { id: "source-ref-selector", class: "source-ref-selector" });
const elsewhere = element(document, "button", { type: "button" }, "Elsewhere");
document.body.append(host, elsewhere);

/** What a stop in the list is, as the transcript names it. */
function describe(node) {
  if (node === document.body) {
    return "body";
  }
  if (node.classList.contains("source-ref-selector-filter")) {
    return "the filter";
  }
  if (node.classList.contains("source-ref-selector-toggle")) {
    return node.getAttribute("aria-label");
  }
  if (node.classList.contains("source-ref-selector-row")) {
    return `the row ${node.querySelector(".ref-chip")?.textContent ?? "?"}`;
  }
  return node.textContent || node.tagName.toLowerCase();
}

// A checkout's page on a branch, whose chooser has the Working tree tab before its lists.
// An arrow key onto that tab only shows it: the page asks for a listing and switches
// nothing. A press on it, which is what a pointer's click and Enter or Space on the
// focused tab both are, asks the pin route for the working tree. The same glue, so the
// same listeners the shell has; the listing's answer is the recorded mirror's, which is
// enough for the list to open.
async function pressAndArrow() {
  context.METABROWSER_SOURCE_CHECKOUT = { working_tree: false };
  context.METABROWSER_SOURCE_PIN = { pin: recorded.branches.body.pin, ref: "refs/heads/feature" };
  const selector = context.MetabrowserSourceRefSelector.mount(host);
  selector.activate();
  await settle();
  const tabs = () => host.querySelectorAll(".source-ref-selector-kinds button");
  const checked = () => tabs().find((tab) => tab.getAttribute("aria-checked") === "true");
  const named = () => tabs().map((tab) => tab.textContent + (tab === checked() ? " (shown)" : ""));
  const opened = { tabs: named(), focus: describe(document.activeElement) };
  check("a page on a branch opens on Branches", checked()?.textContent === "Branches");
  requests.length = 0;
  checked().focus();
  const arrow = keyEvent("keydown", "ArrowLeft", { target: document.activeElement });
  document.activeElement.dispatchEvent(arrow);
  await settle();
  const arrowed = {
    tabs: named(),
    focus: describe(document.activeElement),
    requests: [...requests],
  };
  check("← from Branches shows Working tree", checked()?.textContent === "Working tree");
  check(
    "an arrow key onto Working tree switches nothing",
    requests.length === 1 && !requests.some((request) => request.startsWith("POST")),
    requests.join(", "),
  );
  requests.length = 0;
  checked().click();
  await settle();
  const pressed = { requests: [...requests] };
  check(
    "a press on Working tree asks the pin route for the working tree, once",
    requests.length === 1 && requests[0].startsWith('POST /api/source/pin {"working_tree":true'),
    requests.join(", "),
  );
  selector.dispose();
  return { opened, arrowed, pressed, refresh: await pressRefresh() };
}

// The navigation's Refresh reads an open list again, so a press on it is not a press away
// from the list, as a press anywhere else beside it is: the list stays open, is asked for
// again, and the row that had focus has it back.
async function pressRefresh() {
  const refresh = element(document, "button", { type: "button", id: "nav-refresh" }, "Refresh");
  document.body.append(refresh);
  const selector = context.MetabrowserSourceRefSelector.mount(host);
  selector.activate();
  await settle();
  const panel = host.querySelector(".source-ref-selector-panel");
  const row = host.querySelectorAll(".source-ref-selector-row")[1];
  row.focus();
  requests.length = 0;
  // A pointer's press: the button takes focus, and its click asks the plan, which asks
  // the mounted selector to read its list again (static/refresh-plan.js, `refs`).
  refresh.dispatchEvent({ type: "pointerdown", target: refresh, bubbles: true });
  refresh.focus();
  refresh.click();
  const stayedOpen = !panel.hidden;
  await selector.reread();
  await settle();
  const after = {
    listOpen: stayedOpen && !panel.hidden,
    requests: [...requests],
    focus: describe(document.activeElement),
  };
  check("a press on Refresh leaves the list open", after.listOpen);
  check("Refresh asks for the open list again", requests.length === 1, requests.join(", "));
  check("the row that had focus has it back", document.activeElement === row, after.focus);
  elsewhere.dispatchEvent({ type: "pointerdown", target: elsewhere, bubbles: true });
  elsewhere.click();
  const pressedElsewhere = { listOpen: !panel.hidden };
  check("a press anywhere else closes the list", panel.hidden);
  selector.dispose();
  refresh.remove();
  return { after, pressedElsewhere };
}

async function checkSourceTips() {
  let tip = null;
  const hidden = [];
  context.MetabrowserTooltip = {
    show(html, anchor) {
      tip = { html, anchor };
    },
    hide(within) {
      hidden.push(within);
      if (tip && within.contains(tip.anchor)) {
        tip = null;
      }
    },
  };
  const hover = () => {
    const label = host.querySelector(".source-ref-selector-label");
    label?.dispatchEvent({ type: "mouseenter", target: label });
    return label;
  };
  const freshness = element(document, "div", { id: "source-freshness" });
  document.body.append(freshness);
  context.METABROWSER_SOURCE_CHECKOUT = false;
  context.METABROWSER_SOURCE_PIN = {
    pin: recorded.branches.body.pin,
    ref: recorded.branches.body.ref,
  };
  host.dataset.sourceMode = "cloud-mirror";
  host.dataset.sourceOrigin = "github.com/owner/repository";
  host.dataset.sourceSyncedAt = "2026-11-26T11:58:00Z";
  const selector = context.MetabrowserSourceRefSelector.mount(host);
  const mirrorLabel = hover();
  check(
    "the source chip describes its remote and recorded sync",
    tip?.anchor === mirrorLabel &&
      tip.html.includes(
        '<div class="tip-name">Cloud mirror of github.com/owner/repository</div>',
      ) &&
      tip.html.includes('<div class="tip-detail">Last synced 2m ago.</div>') &&
      !tip.html.includes('class="path"'),
  );
  freshness.dataset.lastFetchAt = "2026-11-26T11:59:00Z";
  now = Date.parse("2026-11-26T12:02:00Z");
  hover();
  check(
    "the tip uses the latest successful sync when it is next hovered",
    tip?.html.includes("Last synced 3m ago."),
  );
  selector.dispose();
  check("disposal hides only the source tooltip", tip === null && hidden.at(-1) === mirrorLabel);
  freshness.remove();

  context.METABROWSER_SOURCE_PIN = null;
  context.METABROWSER_SOURCE_CHECKOUT = true;
  let watchedHead;
  let fileRereads = 0;
  context.MetabrowserShell = {
    async sourceFreshness() {
      return null;
    },
    async rereadFiles() {
      fileRereads += 1;
    },
  };
  context.metabrowser.watchFile = (path, options) => {
    if (path === ".git/HEAD") {
      watchedHead = options.onChange;
    }
    return () => {};
  };
  host.dataset.sourceMode = "working-tree";
  host.dataset.sourcePath = "/absolute/path/to/<checkout>&";
  host.dataset.workingCommit = recorded.branches.body.pin;
  const working = context.MetabrowserSourceRefSelector.mount(host);
  const workingLabel = hover();
  const detached = context.MetabrowserFormatters.shortCommit(recorded.branches.body.pin);
  check(
    "the working tree tip shows a styled escaped path and its detached HEAD before observation",
    tip?.html.includes(
      '<span class="path" dir="ltr">/absolute/path/to/<span class="path-base">&lt;checkout&gt;&amp;</span>',
    ) && tip.html.includes(`HEAD is detached at ${detached}.`),
  );
  const checkout = JSON.parse(
    fs.readFileSync(
      path.join(repoRoot, "tests/fixtures/source-ref-selector-checkout-responses.json"),
      "utf8",
    ),
  );
  answer = checkout.working_tree_moved;
  const refresh = element(document, "button", { id: "nav-refresh", type: "button" });
  document.body.append(refresh);
  const plan = context.MetabrowserRefreshPlan.mount();
  rejectNextHead = true;
  await plan.press();
  check(
    "a rejected HEAD read leaves the branch label in place and reads Files once",
    !rejectNextHead &&
      host.querySelector(".source-ref-selector-label .git-commit-sha")?.textContent === detached &&
      fileRereads === 1,
  );
  await plan.press();
  check(
    "the next manual Refresh retries HEAD and reads Files once",
    host.querySelector(".source-ref-selector-label .git-ref")?.textContent === "feature" &&
      fileRereads === 2,
  );
  check(
    "changing the branch hides its old tooltip",
    tip === null && hidden.at(-1) === workingLabel,
  );
  now += 120_000;
  hover();
  check(
    "the checkout read age comes from the successful manual HEAD response",
    tip?.html.includes("Checkout state read 2m ago."),
  );
  answer = checkout.working_tree_detached;
  watchedHead();
  await settle();
  check(
    "the next external checkout updates the label and reads Files once",
    host.querySelector(".source-ref-selector-label .git-commit-sha") !== null && fileRereads === 3,
  );
  watchedHead();
  await settle();
  check("an unchanged HEAD observation leaves the Files view in place", fileRereads === 3);
  working.dispose();
  refresh.remove();
}

async function main() {
  const selector = context.MetabrowserSourceRefSelector.mount(host);
  selector.activate();
  await settle();
  const panel = host.querySelector(".source-ref-selector-panel");
  const filter = host.querySelector(".source-ref-selector-filter");
  const rows = () => host.querySelectorAll(".source-ref-selector-row");
  const tab = host.querySelector('.source-ref-selector-kinds button[aria-checked="true"]');
  const opened = {
    open: !panel.hidden,
    focus: describe(document.activeElement),
    requests: [...requests],
    rows: rows().map(describe),
  };
  check("the list opens on its filter", opened.open && document.activeElement === filter);
  check("the recorded branches are rows", rows().length === 2, String(rows().length));

  const focused = () => document.activeElement;
  const press = (name, init = {}) => {
    const event = keyEvent("keydown", name, { target: focused(), ...init });
    focused().dispatchEvent(event);
    return event.defaultPrevented;
  };

  const keys = ["ArrowDown", "ArrowUp", "Home", "End", "Escape", "Tab", "r"];
  const chords = {
    Command: { metaKey: true },
    "Shift-Command": { metaKey: true, shiftKey: true },
    Control: { ctrlKey: true },
    Option: { altKey: true },
  };
  const places = [
    ["the filter", () => filter],
    ["a row", () => rows()[1]],
    ["the kind tab", () => tab],
  ];
  const chorded = [];
  for (const [place, target] of places) {
    target().focus();
    const before = focused();
    let presses = 0;
    const taken = [];
    for (const [chord, init] of Object.entries(chords)) {
      for (const name of keys) {
        if (chord === "Option" && name === "Tab") {
          continue;
        }
        presses += 1;
        if (press(name, init)) {
          taken.push(`${chord}-${name}`);
        }
      }
    }
    const step = {
      place,
      focus: describe(before),
      presses,
      taken,
      listOpen: !panel.hidden,
      focusMoved: focused() === before ? null : describe(focused()),
    };
    chorded.push(step);
    check(`from ${place}, no chord is taken`, taken.length === 0, taken.join(", "));
    check(`from ${place}, the list stays open`, step.listOpen);
    check(`from ${place}, focus stays`, step.focusMoved === null);
  }

  // The plain keys still work, and Option-Tab still wraps inside the trap.
  const plain = [];
  const plainKey = (from, name, init = {}) => {
    from.focus();
    const label = `${init.altKey ? "Option-" : ""}${name} from ${describe(from)}`;
    const taken = press(name, init);
    plain.push({ key: label, taken, focus: describe(focused()), listOpen: !panel.hidden });
  };
  plainKey(filter, "ArrowDown");
  plainKey(rows().at(-1), "Tab");
  plainKey(rows().at(-1), "Tab", { altKey: true });
  plainKey(rows()[0], "Escape");
  check("↓ from the filter moves to a row", plain[0].taken && plain[0].focus.startsWith("the row"));
  check("Tab and Option-Tab wrap from the last stop", plain[1].taken && plain[2].taken);
  check(
    "Escape closes the list and restores focus to the chooser button",
    plain[3].taken && !plain[3].listOpen && focused() === selector.button,
  );
  selector.dispose();
  const workingTreeTab = await pressAndArrow();
  await checkSourceTips();

  process.stdout.write(
    `${JSON.stringify({ opened, chords: Object.keys(chords), chorded, plain, workingTreeTab }, null, 2)}\n`,
  );
  if (failures.length > 0) {
    process.stderr.write(`${failures.join("\n")}\n`);
    process.exitCode = 1;
  }
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});

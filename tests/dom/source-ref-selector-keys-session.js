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
const { FakeDocument, element, keyEvent } = require("./key-reveal-dom.js");

const repoRoot = path.resolve(__dirname, "../..");
const staticDir = path.join(repoRoot, "src/metabrowser/static");
const recorded = JSON.parse(
  fs.readFileSync(path.join(repoRoot, "tests/fixtures/source-ref-selector-responses.json"), "utf8"),
);
const failures = [];

function check(name, condition, detail = "") {
  if (!condition) {
    failures.push(`${name}${detail ? `: ${detail}` : ""}`);
  }
}

const document = new FakeDocument();
const browserWindow = document.defaultView;
const requests = [];
const context = {
  AbortController,
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
    refChip: (name) => element(document, "span", { class: "ref-chip" }, name),
  },
  METABROWSER_SOURCE_PIN: { ref: recorded.branches.body.ref, ref_name: "topic" },
  async fetch(route) {
    requests.push(route);
    const answer = recorded.branches;
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
for (const name of ["formatters.js", "filter-controls.js", "menus.js", "source-ref-selector.js"]) {
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

const host = element(document, "div", { class: "source-ref-selector" });
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
    requests,
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

  process.stdout.write(
    `${JSON.stringify({ opened, chords: Object.keys(chords), chorded, plain }, null, 2)}\n`,
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

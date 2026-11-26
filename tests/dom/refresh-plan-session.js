// Browserless session: the navigation's one Refresh, on the production static/refresh-plan.js.
//
// The module loads whole in a realm of its own, as the `shell-tools` bundle loads it. Its
// plan runs with scripted parts, each a refresh that records when it starts and when it
// settles, a turn of the event loop later, so the record shows what one press ran and in
// what order: the parts on screen, while the button waits, then the parts behind other
// tabs. Its browser glue, `mount`, then runs on a stand-in page: the server's button, the
// main pane with its owner, the tab bar, and the shell's own parts as app.js, the freshness
// row, and the Commits panel lend them, with the Pulls tab's list lending its two as
// pulls-panel.js does. A click on the button presses the plan, and the record says what each
// part was asked, in order, and when the button waited.
//
// `node tests/dom/refresh-plan-session.js` prints the record;
// cli-ui-refresh-plan.tryscript.md pins it, and tests/test_refresh_plan_session.py holds it
// to its invariants.

const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const file = path.resolve(__dirname, "../../src/metabrowser/static/refresh-plan.js");
const source = fs.readFileSync(file, "utf8");

/** The module in a fresh realm, with *globals* as its window. */
function load(globals = {}) {
  const context = vm.createContext({ console, Promise, ...globals });
  context.window = context;
  vm.runInContext(source, context, { filename: file });
  return context;
}

const turn = () => new Promise((resolve) => setImmediate(resolve));

/**
 * A plan whose parts each record their start and their end, a turn later; a part named in
 * *failing* throws instead of settling.
 */
function scripted(runtime, shown, failing = []) {
  const events = [];
  const plan = runtime.createPlan({
    shown: (id) => shown.includes(id),
    waiting: (on) => events.push(on ? "waits" : "offered"),
    failed: (id, error) => events.push(`${id} failed: ${error.message}`),
  });
  const part = (id) => async () => {
    events.push(`${id} starts`);
    await turn();
    if (failing.includes(id)) {
      throw new Error(`${id} could not be read`);
    }
    events.push(`${id} settles`);
  };
  const releases = Object.fromEntries(runtime.PARTS.map((id) => [id, plan.provide(id, part(id))]));
  return { events, plan, releases, part };
}

async function planSteps() {
  const runtime = load().MetabrowserRefreshPlan;
  const steps = [];

  // What is on screen on each screen the page can show, and so the order of a press: the
  // tab in front, and what holds the main pane.
  const screens = [
    ["Files in front, a file in the pane", { front: "files", owner: "file" }],
    ["Files in front, nothing chosen", { front: "files", owner: "none" }],
    ["Files in front, a pull request still in the pane", { front: "files", owner: "pull-request" }],
    ["Pulls in front, a pull request in the pane", { front: "pulls", owner: "pull-request" }],
    ["Pulls in front, a file still in the pane", { front: "pulls", owner: "file" }],
    ["Commits in front, a commit in the pane", { front: "git", owner: "git" }],
    ["Commits in front, a file still in the pane", { front: "git", owner: "file" }],
    // The branch and tag chooser's list is on screen while it is open, under Files or
    // Commits, and a working tree's fetch of its origin never is.
    ["Files in front, the chooser's list open", { front: "files", owner: "file", chooser: true }],
  ];
  steps.push({
    step: "each screen's order: the parts on screen, then the rest, each half in plan order",
    parts: runtime.PARTS,
    screens: screens.map(([name, view]) => ({
      screen: name,
      ...runtime.inVisibilityOrder(runtime.PARTS, (id) => runtime.isShown(id, view)),
    })),
  });

  // One press with Pulls in front and a pull request in the pane.
  {
    const { events, plan } = scripted(runtime, ["source", "page", "pulls"]);
    const pressed = plan.press();
    await turn();
    const again = await plan.press();
    const first = await pressed;
    steps.push({
      step: "a press runs the parts on screen while the button waits, then the rest",
      events,
      "a second press while it waits": again,
      "the first press": first,
      "waiting after": plan.waiting(),
    });
  }

  // A part that fails says so, and the rest still run.
  {
    const { events, plan } = scripted(runtime, ["source", "files"], ["source"]);
    await plan.press();
    steps.push({ step: "a part that fails leaves the rest to run", events });
  }

  // A part whose owner went is not run; a part provided again runs its new refresh, and the
  // old owner's release, come late, keeps it.
  {
    const { events, plan, releases, part } = scripted(runtime, ["source", "files"]);
    releases.pulls();
    releases.page();
    plan.provide("git", async () => {
      events.push("git, provided again, starts");
      await part("git")();
    });
    releases.git();
    const parts = plan.parts().join(", ");
    await plan.press();
    steps.push({
      step: "a released part is not run, and a stale release keeps the newer refresh",
      parts,
      events,
    });
  }

  // A second press once the button is offered again supersedes what the first had not yet
  // reached behind the other tabs.
  {
    const { events, plan } = scripted(runtime, ["source", "files"]);
    const first = plan.press();
    while (!events.includes("offered")) {
      await turn();
    }
    const second = plan.press();
    await Promise.all([first, second]);
    steps.push({
      step: "a press while the hidden parts run supersedes the rest of the first",
      events,
    });
  }

  // An unknown part is refused.
  {
    const plan = runtime.createPlan({ shown: () => true, waiting() {} });
    let refused = null;
    try {
      plan.provide("tree", () => {});
    } catch (error) {
      refused = error.message;
    }
    steps.push({ step: "a part the plan does not list is refused", refused });
  }
  return steps;
}

/** A stand-in element: attributes, a dataset, and click listeners. */
function stub(attributes = {}) {
  const attrs = new Map(Object.entries(attributes));
  const listeners = [];
  return {
    dataset: {},
    getAttribute: (name) => (attrs.has(name) ? attrs.get(name) : null),
    setAttribute: (name, value) => attrs.set(name, String(value)),
    removeAttribute: (name) => attrs.delete(name),
    addEventListener: (type, listener) => type === "click" && listeners.push(listener),
    click: () => {
      for (const listener of listeners) {
        listener();
      }
    },
  };
}

/**
 * The glue on a stand-in page with *front* in front and *owner* holding the pane: a
 * mirror's, with its freshness row and the Pulls tab, or, without *store*, a local
 * repository's, with neither. With *sourceFails*, the freshness row's script fails to load
 * that many times first, as a dropped connection fails it. With *chooser*, the page has
 * the branch and tag chooser, its list "open" or "closed"; with *workingTree* it is a
 * checkout's working tree's page, which has no freshness row and fetches its origin last.
 */
async function pageSteps(
  front,
  owner,
  { store = true, sourceFails = 0, chooser = null, workingTree = false } = {},
) {
  const asked = [];
  let failures = sourceFails;
  const record = (what) => async () => {
    asked.push(`${what} starts`);
    await turn();
    asked.push(`${what} settles`);
  };
  class HTMLElement {}
  const button = Object.assign(Object.create(HTMLElement.prototype), stub({ id: "nav-refresh" }));
  // The button's waiting state, as the plan sets it.
  const set = button.setAttribute;
  button.setAttribute = (name, value) => {
    set(name, value);
    asked.push(`the button: ${name}=${value}`);
  };
  const remove = button.removeAttribute;
  button.removeAttribute = (name) => {
    remove(name);
    asked.push(`the button: no ${name}`);
  };
  const preview = stub();
  preview.dataset.previewOwner = owner;
  const tab = stub({ "data-tab": front });
  const selector = stub();
  selector.dataset.open = String(chooser === "open");
  const elements = {
    "nav-refresh": button,
    "preview-pane": preview,
    ...(chooser === null ? {} : { "source-ref-selector": selector }),
  };
  const document = {
    getElementById: (id) => elements[id] ?? null,
    querySelector: (selector) => (selector === ".nav-tab-bar .tab-btn.active" ? tab : null),
  };
  const context = load({
    console: { error: (what) => asked.push(`the console: ${what}`) },
    HTMLElement,
    document,
    MetabrowserShell: {
      rereadFiles: record("files: the shell's rereadFiles"),
      sourceFreshness: () => {
        if (failures > 0) {
          failures -= 1;
          asked.push("the freshness row's script fails to load");
          return Promise.reject(new Error("Failed to load asset"));
        }
        return Promise.resolve(
          store && !workingTree
            ? { refreshNow: record("source: the freshness row's refreshNow") }
            : null,
        );
      },
    },
    MetabrowserGitPanel: { refresh: record("git: the Commits panel's refresh") },
    // The chooser the page mounted, whose two parts the plan asks it for at each press.
    MetabrowserSourceRefSelector: {
      mounted: () => ({
        reread: record("refs: the chooser's reread"),
        fetchOrigin: record("origin: the chooser's fetchOrigin"),
      }),
    },
    ...(workingTree ? { METABROWSER_SOURCE_CHECKOUT: { working_tree: true } } : {}),
  });
  await turn();
  const plan = context.MetabrowserRefreshPlan.plan();
  // The Pulls tab's list, mounted, lends its two parts through its host (pulls-nav.js). What
  // each part then asks, and when it asks nothing, is the list's own: the Pulls panel's
  // session runs the production list's parts, behind another tab too
  // (github-pulls-panel-session.js, "Refresh behind the Files tab").
  if (store && !workingTree) {
    plan.provide("page", record("page: the part the Pulls list lends for the page beside it"));
    plan.provide("pulls", record("pulls: the part the Pulls list lends for itself"));
  }
  button.click();
  for (let settled = 0; settled < 30; settled += 1) {
    await turn();
  }
  return {
    step: `a click with ${front} in front and the pane's owner "${owner}"${store ? "" : ", a local repository with no store and no Pulls tab"}${sourceFails ? `, after the freshness row's script failed to load ${sourceFails === 1 ? "once" : `${sourceFails} times`}` : ""}${workingTree ? ", a checkout's working tree" : chooser === null ? "" : ", a revision"}${chooser === null ? "" : ` with the chooser's list ${chooser}`}`,
    parts: plan.parts(),
    asked,
  };
}

async function main() {
  const steps = await planSteps();
  steps.push(await pageSteps("pulls", "pull-request"));
  steps.push(await pageSteps("files", "file"));
  steps.push(await pageSteps("git", "git"));
  steps.push(await pageSteps("files", "file", { store: false }));
  steps.push(await pageSteps("files", "file", { sourceFails: 1 }));
  // A page with the chooser. A revision's fetches, then reads again, the open list
  // straight after the fetch; a working tree's reads the disk and the history again, and
  // only then fetches its origin, once the button is offered again.
  steps.push(await pageSteps("files", "file", { chooser: "open" }));
  steps.push(await pageSteps("files", "file", { chooser: "closed" }));
  steps.push(await pageSteps("files", "file", { chooser: "open", workingTree: true }));
  steps.push(await pageSteps("git", "git", { chooser: "closed", workingTree: true }));
  process.stdout.write(`${JSON.stringify({ steps }, null, 2)}\n`);
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});

// Browserless session: a Git revision's page while the server reads its files' ages.
//
// The server dates a revision's files in the background and never makes a page wait for
// it, so a tree, a grouped tree, or a Recent list asked for early says `ages.state:
// "dating"` with every file undated. static/revision-ages.js watches for that state, asks
// /api/index/progress until it changes, and asks the shell to draw once more when it does
// (docs/project/architecture/arch-git.md, "File Ages").
//
// This runs the real module under fake timers and a scripted /api/index/progress, in two
// parts: the controller, which owns every decision, with the state each poll returns, and
// `mount`, the browser glue, with a scripted `fetch` and the page's own settings. Every
// line below is what the module did: how many timers it holds, when it asked the shell to
// draw, and with what state.

const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const repoRoot = path.resolve(__dirname, "../..");
const file = path.join(repoRoot, "src/metabrowser/static/revision-ages.js");
const source = fs.readFileSync(file, "utf8");

/** A page with the module loaded: fake timers that run when told to, and a clock. */
function page(extra = {}) {
  const timers = new Map();
  let nextId = 1;
  const context = vm.createContext({
    ...extra,
    setTimeout(run, ms) {
      const id = nextId++;
      timers.set(id, { run, ms });
      return id;
    },
    clearTimeout(id) {
      timers.delete(id);
    },
  });
  context.window = context;
  vm.runInContext(source, context, { filename: file });
  return {
    api: context.MetabrowserRevisionAges,
    /** Run the oldest timer, as the browser would when it fires; its poll settles after. */
    async fire() {
      const [id, timer] = timers.entries().next().value;
      timers.delete(id);
      timer.run();
      await new Promise((resolve) => setImmediate(resolve));
      return timer.ms;
    },
  };
}

const transcript = {};

async function scenario(name, answers, run) {
  const p = page();
  let clock = 0;
  const timers = new Map();
  let nextId = 1;
  const lines = [];
  const asked = [];
  const c = p.api.createController({
    fetchState: async () => {
      asked.push("progress");
      const next = answers.shift();
      if (next instanceof Error) {
        throw next;
      }
      return next;
    },
    landed: (state) => lines.push(`landed ${JSON.stringify(state)}`),
    setTimer: (fn, ms) => {
      const id = nextId++;
      timers.set(id, { fn, ms });
      return id;
    },
    clearTimer: (id) => timers.delete(id),
    now: () => clock,
    pollMs: 500,
  });
  const state = () => ({
    watching: c.isWatching(),
    timers: timers.size,
    progressRequests: asked.length,
    landed: [...lines],
  });
  const env = {
    c,
    state,
    async fire() {
      const [id, timer] = timers.entries().next().value;
      timers.delete(id);
      timer.fn();
      await new Promise((resolve) => setImmediate(resolve));
    },
    advance(ms) {
      clock += ms;
    },
    delays: () => [...timers.values()].map((timer) => timer.ms),
  };
  transcript[name] = await run(env);
}

(async () => {
  await scenario("a response with no ages is not about file ages", [], async ({ c, state }) => {
    c.observe(undefined);
    c.observe({});
    return state();
  });

  await scenario("an answer that has landed starts no watch", [], async ({ c, state }) => {
    c.observe({ state: "ready" });
    c.observe({ state: "unavailable" });
    return state();
  });

  await scenario(
    "dating starts one watch that polls until the answer lands, then draws once",
    [{ state: "dating" }, { state: "dating" }, { state: "ready", dated: 7 }],
    async ({ c, state, fire, delays }) => {
      const steps = {};
      c.observe({ state: "dating" });
      steps.observed = { ...state(), delays: delays() };
      c.observe({ state: "dating" });
      steps.observedAgain = { ...state(), delays: delays() };
      await fire();
      steps.firstPoll = state();
      await fire();
      steps.secondPoll = state();
      await fire();
      steps.landed = state();
      return steps;
    },
  );

  await scenario(
    "a partial answer is an answer: it draws once and stops",
    [{ state: "partial", dated: 3, older_than: 1700000000 }],
    async ({ c, state, fire }) => {
      c.observe({ state: "dating" });
      await fire();
      return state();
    },
  );

  await scenario(
    "a poll that fails ends the watch without drawing",
    [new Error("offline")],
    async ({ c, state, fire }) => {
      c.observe({ state: "dating" });
      await fire();
      return state();
    },
  );

  await scenario(
    "a response that says the answer landed ends the watch",
    [{ state: "ready" }],
    async ({ c, state }) => {
      c.observe({ state: "dating" });
      c.observe({ state: "ready" });
      return state();
    },
  );

  await scenario(
    "a watch that outlasts the server's own bound gives up",
    [{ state: "dating" }],
    async ({ c, state, fire, advance }) => {
      c.observe({ state: "dating" });
      advance(121_000);
      await fire();
      return state();
    },
  );

  // Part two: the glue the page runs, with its own fetch and settings.
  const asked = [];
  const answers = [{ ages: { state: "dating" } }, { ages: { state: "partial", dated: 2 } }];
  const landed = [];
  const glue = page({
    METABROWSER_SETTINGS: { GIT_AGES_POLL_MS: 250 },
    async fetch(url, options) {
      asked.push({ url, options });
      return { ok: true, json: async () => answers.shift() };
    },
  });
  const mounted = glue.api.mount({ reload: (state) => landed.push(state) });
  mounted.observe({ state: "dating" });
  const delays = [];
  delays.push(await glue.fire());
  delays.push(await glue.fire());
  transcript["the page's glue asks the progress route at the settings' pace"] = {
    delays,
    asked,
    landed,
    watching: mounted.isWatching(),
  };

  console.log(JSON.stringify(transcript, null, 2));
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});

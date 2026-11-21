// Browserless session: the agents views' state machines, run against the production modules.
//
// The agents home, the session list, and the Session view are views of data the `catalog`,
// `sessions`, `session`, `records`, and `live` routes own (their goldens are
// cli-api-agents-*.tryscript.md and cli-api-agents-views.tryscript.md). What the browser
// owns is how a person's changes become requests, and when the page asks again:
//
// - The session list's state (agent, origins, statuses, window, sort, page): each change
//   returns the first page, a column reverses on a second choice, a page never leaves the
//   rows the response says exist, and the state names the `sessions` request.
// - The poll that keeps the home current: one request in flight, none while the page is
//   hidden, a failed request backs off, a tick that answers `false` ends it, and a disposed
//   poll aborts what it asked.
// - What the home derives before it paints: the activity window, the size histogram, the
//   progress sentence, and the ages and durations.
// - The markup of a session table and an event row, from the exact modules the views use.
//
// The modules load whole. The clock, the timer, and the page's visibility are the
// injected ones a poller takes, which this session advances by hand. Each step prints what
// it observed. Exits 1 on a failed invariant.

const path = require("node:path");
const { pathToFileURL } = require("node:url");

// The plugin's modules have no package.json saying they are modules, which the browser
// never asks about. Node's warning names the process and the checkout, so it is kept out
// of the transcript.
const emitWarning = process.emitWarning;
process.emitWarning = (warning, ...rest) => {
  if (String(warning).includes("is not specified and it doesn't parse as CommonJS")) {
    return;
  }
  emitWarning.call(process, warning, ...rest);
};

const pluginDir = path.resolve(__dirname, "../../src/metabrowser/builtin_plugins/agents");
const load = (name) => import(pathToFileURL(path.join(pluginDir, name)).href);

function assert(condition, message) {
  if (!condition) {
    throw new Error(message);
  }
}

/** A clock, timers, and a visibility flag the session moves by hand. */
function createClock() {
  let now = 1_000_000;
  let nextHandle = 1;
  const timers = new Map();
  let visible = true;
  const listeners = new Set();
  return {
    isVisible: () => visible,
    // Like the SDK's `viewState.subscribeActive`, it reports the page's state as it is
    // subscribed: a poll that starts a request on that report asks twice at once.
    subscribeVisibility(listener) {
      listeners.add(listener);
      listener();
      return () => listeners.delete(listener);
    },
    setTimer(callback, ms) {
      const handle = nextHandle++;
      timers.set(handle, { callback, at: now + ms });
      return handle;
    },
    clearTimer: (handle) => timers.delete(handle),
    now: () => now,
    setVisible(value) {
      visible = value;
      for (const listener of [...listeners]) {
        listener();
      }
    },
    pendingTimers: () => timers.size,
    /** Move time forward, running each timer that falls due in order. */
    async advance(ms) {
      const end = now + ms;
      for (;;) {
        const due = [...timers.entries()]
          .filter(([, timer]) => timer.at <= end)
          .sort((a, b) => a[1].at - b[1].at)[0];
        if (!due) {
          break;
        }
        now = Math.max(now, due[1].at);
        timers.delete(due[0]);
        due[1].callback();
        await settle();
      }
      now = end;
    },
  };
}

/** Let every pending promise continuation run. */
async function settle() {
  for (let turn = 0; turn < 10; turn += 1) {
    await new Promise((resolve) => setImmediate(resolve));
  }
}

async function main() {
  const poller = await load("poller.js");
  const state = await load("session-list-state.js");
  const model = await load("home-model.js");
  const rows = await load("session-rows.js");
  const session = await load("session.js");
  const transcript = {};

  // -- the session list's state ----------------------------------------------------------

  const NOW = 1_800_000_000;
  const steps = {};
  let current = state.initialState();
  const record = (label, next) => {
    current = next;
    steps[label] = {
      offset: next.offset,
      sort: `${next.sort} ${next.order}`,
      query: state.queryString(state.queryOf(next, "", NOW)),
    };
  };
  record("the list opens without automatic reviews, newest activity first", current);
  assert(!current.origins.includes("review"), "reviews are hidden by default");
  assert(current.sort === "activity" && current.order === "desc", "starts newest first");

  record("showing reviews too asks for every origin", state.toggleOrigin(current, "review"));
  assert(
    !state.queryOf(current, "", NOW).origin,
    "all five origins is no origin filter, as the route reads it",
  );
  record("hiding them again", state.toggleOrigin(current, "review"));

  const answer = { total: 130, sessions: new Array(state.PAGE_SIZE).fill({}) };
  record("a second page", state.withPage(current, "next", answer));
  assert(current.offset === state.PAGE_SIZE, "next moves one page on");
  record("a third", state.withPage(current, "next", answer));
  record("a fourth stops at the last page", state.withPage(current, "next", answer));
  assert(current.offset === 2 * state.PAGE_SIZE, "a page never leaves the rows that exist");
  steps["the pager after the third page"] = state.pageOf(current, {
    total: 130,
    sessions: new Array(30).fill({}),
  });
  record("back one page", state.withPage(current, "previous", answer));
  record("a filter returns to the first page", state.withFilter(current, { agent: "codex" }));
  assert(current.offset === 0, "a filter resets the page");

  record(
    "a text column sorts as the route defaults it: ascending",
    state.withSort(current, "title"),
  );
  record("the same column reverses", state.withSort(current, "title"));
  record("a numeric column sorts largest first", state.withSort(current, "size"));
  assert(current.order === "desc", "size starts largest first");
  const unchanged = state.withSort(current, "mood");
  assert(unchanged === current, "a column the route does not offer changes nothing");

  current = state.withFilter(current, {
    statuses: ["running", "failed"],
    project: "/work/alpha",
    window: "week",
  });
  steps["the filters together"] = {
    query: state.queryString(state.queryOf(current, "", NOW)),
  };
  record("a status chip toggled off", state.toggleStatus(current, "running"));
  assert(current.statuses.join() === "failed", "toggling a status removes only it");
  record("and back on, in the route's order", state.toggleStatus(current, "running"));
  assert(current.statuses.join() === "running,failed", "statuses keep the route's order");
  transcript["session list state"] = steps;

  // -- the poll --------------------------------------------------------------------------

  const polling = {};
  {
    const clock = createClock();
    const seen = [];
    let nextAnswer = true;
    let release = null;
    const poll = poller.createPoller({
      ...clock,
      intervalMs: 1000,
      run: async (signal) => {
        seen.push(`tick at ${clock.now() - 1_000_000}`);
        if (release === "hold") {
          await new Promise((resolve) => {
            release = resolve;
          });
        }
        if (signal.aborted) {
          seen.push("aborted");
        }
        if (nextAnswer === "fail") {
          throw new Error("down");
        }
        return nextAnswer;
      },
      onError: () => seen.push("error"),
    });
    poll.start();
    polling["a started poll waits one interval"] = {
      ticks: [...seen],
      timers: clock.pendingTimers(),
    };
    await clock.advance(1000);
    polling["then asks"] = { ticks: [...seen], state: poll.state() };

    clock.setVisible(false);
    await clock.advance(3000);
    polling["a hidden page asks nothing"] = { ticks: [...seen] };
    assert(seen.length === 1, "no request while hidden");
    clock.setVisible(true);
    await settle();
    polling["shown again, it asks at once"] = { ticks: [...seen] };

    nextAnswer = "fail";
    await clock.advance(1000);
    polling["a failure doubles the wait"] = { ticks: [...seen], state: poll.state() };
    assert(poll.state().waitMs === 2000, "one failure doubles the wait");
    await clock.advance(2000);
    await clock.advance(4000);
    assert(poll.state().waitMs === 4000, "the wait stops doubling at the cap");
    nextAnswer = true;
    await clock.advance(4000);
    polling["a good answer resets it"] = { state: poll.state() };
    assert(poll.state().waitMs === 1000, "success resets the wait");

    const beforeHold = seen.filter((entry) => entry.startsWith("tick")).length;
    release = "hold";
    await clock.advance(1000);
    await clock.advance(5000);
    const before = seen.filter((entry) => entry.startsWith("tick")).length;
    polling["a slow request is not queued behind itself"] = {
      inFlight: poll.state().inFlight,
      requestsWhileHeld: before - beforeHold,
    };
    assert(before - beforeHold === 1, "one request is in flight at most");
    poll.dispose();
    polling["disposing aborts the request in flight"] = {
      inFlight: poll.state().inFlight,
      running: poll.state().running,
      timers: clock.pendingTimers(),
      requestsAfter: seen.filter((entry) => entry.startsWith("tick")).length - before,
    };
    assert(clock.pendingTimers() === 0, "a disposed poll leaves no timer");
  }
  {
    const clock = createClock();
    let calls = 0;
    const poll = poller.createPoller({
      ...clock,
      intervalMs: 1000,
      run: async () => {
        calls += 1;
        return calls < 3;
      },
    });
    poll.start();
    await clock.advance(10_000);
    polling["a tick that answers false ends the poll, as a complete summary does"] = {
      calls,
      running: poll.state().running,
      timers: clock.pendingTimers(),
    };
    assert(calls === 3 && !poll.state().running, "the poll stops on false");
    poll.dispose();
  }
  {
    // A view that asks until its answer settles (`retrying`): the session page waiting for
    // the catalog's first pass, and the home and the list retrying a first load that failed.
    const clock = createClock();
    let next = "down";
    const seen = [];
    const poll = poller.createPoller({
      ...clock,
      intervalMs: 1000,
      run: poller.retrying(async () => {
        seen.push(next);
        if (next === "down") {
          throw new Error("down");
        }
        if (next === "refused") {
          throw Object.assign(new Error("refused"), { status: 404 });
        }
        return next === "again";
      }),
    });
    poll.start();
    await clock.advance(1000);
    assert(poll.state().failures === 1 && poll.state().running, "a failure backs off and goes on");
    assert(poll.state().waitMs === 2000, "the wait doubles");
    next = "again";
    await clock.advance(2000);
    assert(poll.state().failures === 0 && poll.state().waitMs === 1000, "an answer resets it");
    next = "refused";
    await clock.advance(1000);
    polling["a retried ask backs off on a failure, resets on an answer, and ends on a refusal"] = {
      asked: [...seen],
      running: poll.state().running,
      failures: poll.state().failures,
    };
    assert(!poll.state().running, "a refusal asking again cannot cure ends the poll");
    assert(clock.pendingTimers() === 0, "an ended poll leaves no timer");
    polling["which failures are worth asking again"] = [
      new Error("no status"),
      { status: 503 },
      { status: 429 },
      { status: 404 },
      { status: 400 },
    ].map((error) => poller.isRetryable(error));
    poll.dispose();
  }
  {
    // The summary poll of the home and the list (`progressRun`): it goes on while the
    // summary is incomplete, ends when it is complete, and backs off on a failed load.
    const clock = createClock();
    const answers = [
      { progress: { complete: false } },
      "fail",
      null,
      { progress: { complete: false } },
      { progress: { complete: true } },
    ];
    const poll = poller.createPoller({
      ...clock,
      intervalMs: 1000,
      run: poller.progressRun(async () => {
        const answer = answers.shift();
        if (answer === "fail") {
          throw new Error("down");
        }
        return answer ?? null;
      }),
    });
    poll.start();
    await clock.advance(1000);
    const afterFirst = poll.state().failures;
    await clock.advance(1000);
    const afterFailure = { failures: poll.state().failures, waitMs: poll.state().waitMs };
    await clock.advance(30_000);
    polling["a summary poll backs off on a failed load and ends when the summary is complete"] = {
      afterFirst,
      afterFailure,
      unasked: answers.length,
      running: poll.state().running,
    };
    assert(afterFailure.failures === 1, "a failed load is counted, not swallowed");
    assert(answers.length === 0 && !poll.state().running, "it ends on a complete summary");
    poll.dispose();
  }
  transcript.poll = polling;

  // -- what the home derives -------------------------------------------------------------

  const derived = {};
  const formatInteger = (value) => String(value);
  const formatSize = (bytes) => (bytes >= 1024 ? `${bytes / 1024} KB` : `${bytes} B`);
  const activity = model.activityBars(
    [
      { day: "2027-01-14", sessions: 4 },
      { day: "2027-01-15", sessions: 2 },
      { day: "2026-01-01", sessions: 9 },
    ],
    NOW,
  );
  derived["activity window"] = {
    bars: activity.bars.length,
    first: activity.bars[0].day,
    last: activity.bars[activity.bars.length - 1].day,
    peak: activity.peak,
    total: activity.total,
    heights: activity.bars.slice(-3).map((bar) => bar.height),
  };
  assert(activity.bars.length === model.ACTIVITY_DAYS, "one bar per day of the window");
  assert(activity.total === 6, "a day outside the window is not counted");
  const sizes = model.sizeBars(
    [
      { lower: 0, upper: 1024, count: 0 },
      { lower: 1024, upper: 4096, count: 3 },
      { lower: 4096, upper: 16384, count: 6 },
      { lower: 16384, upper: null, count: 0 },
    ],
    formatSize,
  );
  derived["size histogram"] = sizes;
  derived["progress while summarizing"] = model.progressView(
    { state: "summarizing", total: 10, summarized: 4, failed: 1, complete: false },
    formatInteger,
  );
  derived["progress at first, with nothing found yet"] = model.progressView(
    { state: "scanning", total: 0, summarized: 0, failed: 0, complete: false },
    formatInteger,
  );
  derived["progress when complete"] = model.progressView(
    { state: "idle", total: 10, summarized: 10, failed: 0, complete: true },
    formatInteger,
  );
  derived["progress when complete with an unreadable session"] = model.progressView(
    { state: "idle", total: 10, summarized: 9, failed: 1, complete: true },
    formatInteger,
  );
  derived["the session page while the catalog's first pass runs"] = [
    session.waitingText(null, formatInteger),
    session.waitingText(
      { state: "scanning", total: 0, summarized: 0, failed: 0, complete: false },
      formatInteger,
    ),
    session.waitingText(
      { state: "scanning", total: 12, summarized: 0, failed: 0, complete: false },
      formatInteger,
    ),
  ];
  const said = (shown, nextCursor, truncated) =>
    session.eventsSaid({ shown, nextCursor, truncated });
  derived["what the events say"] = {
    "none match, the scan reached the end": said(0, null, false),
    "none matched yet, more to scan": said(0, 40, false),
    "none matched, the bound stopped the scan": said(0, null, true),
    "some, the scan went on": said(5, 40, false),
    "some, the bound stopped the scan": said(5, null, true),
  };
  assert(said(0, 40, false).notice !== "No events match.", "none match only at the scan's end");
  assert(said(5, null, true).note !== "", "a truncated scan says so beside rows");
  derived.ages = [3, 40, 600, 7300, 400_000].map((seconds) => model.ageText(NOW - seconds, NOW));
  derived.durations = [31, 252, 7500].map((seconds) => model.durationText(seconds));
  transcript.home = derived;

  // -- the markup ------------------------------------------------------------------------

  const mb = {
    escapeHtml: (value) =>
      String(value)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;"),
    formatInteger,
    formatSize,
    formatTimestamp: (seconds) => `t${seconds}`,
    navigation: { href: ({ path: target }) => `/view/${target}` },
    // The shell's count painter, as the dot between a line's groups: muted, hidden from
    // assistive technology (docs/design-system.md, "Count Summaries Bold Their Numbers").
    countPartsNodes: (parts) =>
      parts.map((part) => ({
        outerHTML: `<span class="summary-punctuation" aria-hidden="true">${part.separator}</span>`,
      })),
  };
  const row = (overrides) => ({
    agent: "claude",
    session_id: "s1",
    title: "A <b>title</b>",
    origin: "human",
    project: "~/work/alpha",
    models: ["m1"],
    started_at: 10,
    last_activity: NOW - 30,
    duration_seconds: 31,
    turns: 2,
    size_bytes: 2048,
    status: "running",
    source_paths: [".claude/projects/p/s1.jsonl"],
    ...overrides,
  });
  const table = rows.sessionTableHtml(
    mb,
    [row({}), row({ agent: "codex", session_id: "s2", status: "finished", source_paths: [] })],
    {
      columns: ["agent", "title", "status", "size"],
      now: NOW,
      sorting: { sort: "size", order: "desc" },
      caption: "Sessions",
      empty: "none",
    },
  );
  const items = rows.sessionRowsHtml(
    mb,
    [
      {
        agent: "claude",
        session_id: "s1",
        title: "A <b>title</b>",
        path: ".claude/projects/p/s1.jsonl",
        age: "30 s ago",
        project: "~/work/alpha",
        models: ["m1", "m2"],
        status: "running",
      },
      {
        agent: "codex",
        session_id: "s2",
        title: "No file",
        path: null,
        age: "2 min ago",
        project: null,
        models: [],
        status: null,
      },
    ],
    { label: "Running now" },
  );
  // Every value a row shows comes from a session's own files, so each is escaped.
  const hostile = rows.sessionRowsHtml(
    mb,
    [
      {
        agent: "claude",
        session_id: "<i>id</i>",
        title: "",
        path: null,
        age: "<i>age</i>",
        project: "~/<i>project</i>",
        models: ["<i>model</i>"],
        status: "<i>status</i>",
      },
    ],
    { label: "<i>label</i>" },
  );
  const markup = {
    "no value a session holds reaches the row as markup": !hostile.includes("<i>"),
    "a session row's first line holds the agent, the title link, and the age last":
      /agents-row-line"><span class="agents-agent">Claude Code<\/span><a class="agents-session-link agents-row-title"[^>]*>A &lt;b&gt;title&lt;\/b&gt;<\/a><span class="agents-row-age">30 s ago<\/span><\/div>/.test(
        items,
      ),
    "its second line is the status, the project, and the model, parted by the design's separator":
      items.includes(
        '<div class="agents-row-meta agents-muted"><span class="file-header-badge badge-running">running</span><span class="agents-row-project" data-tip-text="~/work/alpha">~/work/alpha</span> <span class="summary-punctuation" aria-hidden="true">·</span> <span class="agents-row-model" data-tip-text="m1, m2">m1, m2</span>',
      ),
    "a row with neither leaves the line empty and no stray separator":
      /agents-row-meta agents-muted"><\/div><\/li>/.test(items),
    "a title with no file is plain text in the row": items.includes(
      '<span class="agents-session-link agents-row-title agents-no-file">No file</span>',
    ),
    "the list names itself": items.startsWith(
      '<ul class="agents-session-rows" aria-label="Running now">',
    ),
    "the sorted column says so": /aria-sort="descending"/.test(table),
    "an unsorted column offers its sort": /aria-sort="none"/.test(table),
    "a title is escaped": table.includes("A &lt;b&gt;title&lt;/b&gt;") && !table.includes("<b>"),
    "a session with a file is a link to it": table.includes(
      'data-agents-open=".claude/projects/p/s1.jsonl"',
    ),
    "a session with no file is plain text": table.includes("agents-no-file"),
    "a running status wears the running badge": table.includes("badge-running"),
    "no rows is a sentence": rows.sessionTableHtml(mb, [], {
      columns: ["agent"],
      now: NOW,
      sorting: null,
      caption: "x",
      empty: "No sessions match these filters.",
    }),
  };
  const event = session.eventHtml(mb, {
    locator: "s1:3",
    timestamp: 5,
    kind: "tool-call",
    tool_name: "mcp:srv.lookup",
    tool_family: "mcp",
    summary: "x < y",
    replay: false,
  });
  markup["an event wears its kind's and its tool family's color class"] =
    event.includes("kind-tool-call") && event.includes("tool-mcp");
  markup["an unknown kind is neutral"] = session
    .eventHtml(mb, {
      locator: "l",
      timestamp: null,
      kind: "weird",
      tool_name: null,
      tool_family: null,
      summary: "s",
      replay: true,
    })
    .includes("kind-unknown");
  markup["a replayed event is marked apart"] = session
    .eventHtml(mb, {
      locator: "l",
      timestamp: null,
      kind: "prompt",
      tool_name: null,
      tool_family: null,
      summary: "s",
      replay: true,
    })
    .includes("agents-event-replay");
  for (const [label, ok] of Object.entries(markup)) {
    if (typeof ok === "boolean") {
      assert(ok, label);
    }
  }
  transcript.markup = markup;

  process.stdout.write(`${JSON.stringify(transcript, null, 2)}\n`);
}

main().catch((error) => {
  process.stderr.write(`${error.stack || error}\n`);
  process.exit(1);
});

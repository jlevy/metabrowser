// Browserless session: the served pull request's page, driven through the production
// browser code.
//
// The page talks to the server through three GitHub plugin routes and the pin route.
// Every response here is one the in-process application gave while it served pull
// request 7 of the stand-in in tests/github_pull_fixture.py, from its default branch
// until the page switched to the head, recorded in
// tests/fixtures/github-pull-page-responses.json. tests/test_github_pull_page_session.py
// replays that story and fails when the recording drifts, so this session never runs on
// an envelope a test wrote by hand.
//
// builtin_plugins/github/pull-page.js loads whole, as the shell loads the plugin: its
// describePull decides what the page shows, and createPullController owns polling, the
// refresh, the switch to the head, the tab, and asking for Markdown one part at a time.
// Timers, the clock, visibility, and paint are injected; the browser glue's
// IntersectionObserver is played by asking for parts in reading order. Each step prints
// the requests the page made, the timer it left, how many times it painted, what it
// would paint, whether it reloaded, and which parts it rendered as Markdown.
//
// `place` is the reader's place in the pane through history, from createScrollKeeper, on a
// stage standing for the pane: see placeStory.

const fs = require("node:fs");
const path = require("node:path");
const { pathToFileURL } = require("node:url");

const repoRoot = path.resolve(__dirname, "../..");
const recorded = JSON.parse(
  fs.readFileSync(path.join(repoRoot, "tests/fixtures/github-pull-page-responses.json"), "utf8"),
);
// The recording holds each distinct record once: an answer whose record an earlier
// pull-route answer carried names that answer, and reads here as that record.
for (const answer of Object.values(recorded)) {
  for (const envelope of [answer.body, answer.body?.pull]) {
    const holder = envelope?.record?.same_as;
    if (holder !== undefined) {
      envelope.record = recorded[holder].body.record;
    }
  }
}
const pagePath = path.join(repoRoot, "src/metabrowser/builtin_plugins/github/pull-page.js");
// The allowlist the page passes a text's Markdown through, loaded whole as the shell
// loads it on demand.
const inertPath = path.join(repoRoot, "src/metabrowser/static/inert-html.js");
const inertContext = { window: {}, URL };
require("node:vm").runInNewContext(fs.readFileSync(inertPath, "utf8"), inertContext, {
  filename: inertPath,
});
const inertHtml = inertContext.window.MetabrowserInertHtml;
// The route codec, whose wire encoder the page uses for a review comment's file.
const routeContext = { atob, btoa, TextDecoder, TextEncoder, Uint8Array };
routeContext.window = routeContext;
const routePath = path.join(repoRoot, "src/metabrowser/static/navigation.js");
require("node:vm").runInNewContext(fs.readFileSync(routePath, "utf8"), routeContext, {
  filename: routePath,
});
// git-path.js holds the wire encoder; a pinned revision's shell loads it, and a pull
// request is always served from one.
const gitPathFile = path.join(repoRoot, "src/metabrowser/static/git-path.js");
require("node:vm").runInNewContext(fs.readFileSync(gitPathFile, "utf8"), routeContext, {
  filename: gitPathFile,
});
globalThis.window = {
  MetabrowserGitPath: routeContext.MetabrowserGitPath,
  MetabrowserNavigationRoute: routeContext.MetabrowserNavigationRoute,
};

function assert(condition, message) {
  if (!condition) {
    throw new Error(message);
  }
}

/** What a reader would see, in a line per item. */
function summarize(model) {
  const pull = model.pull;
  return {
    status: model.status,
    tab: model.tab || "conversation",
    message: model.message,
    canRefresh: model.canRefresh,
    freshness: model.freshness,
    failure: model.failure,
    header:
      pull === null
        ? null
        : `${pull.title} #${pull.number} [${pull.stateLabel}] ${pull.actor === null ? "" : `${pull.actor} `}${pull.action} ${pull.base} from ${pull.head}`,
    labels: pull === null ? [] : pull.labels,
    merge: pull?.merge?.label ?? null,
    timeline: model.timeline.map(
      (item) =>
        `${item.kind} ${item.author}${item.review ? ` [${item.review.label}]` : ""} ${item.at ?? "pending"} ${item.part}`,
    ),
    reviewComments: model.reviewComments.map(
      (comment) =>
        `${comment.path}:${comment.line ?? "outdated"} ${comment.author}${comment.reply ? " (reply)" : ""}${comment.hunk ? " +hunk" : ""}`,
    ),
    checks:
      model.checks === null
        ? null
        : {
            counts: model.checks.counts,
            items: model.checks.items.map((item) => `[${item.label}] ${item.name} -> ${item.url}`),
          },
    notes: model.notes,
    headOffer:
      model.headOffer === null
        ? null
        : `${model.headOffer.text} [Switch to the head] -> ${model.headOffer.ref}`,
    comparison:
      model.comparison === null
        ? null
        : `${model.comparison.left.slice(0, 12)}...${model.comparison.right.slice(0, 12)}${model.comparison.headMoved ? " (head moved)" : ""}`,
  };
}

// ── The template the page parses a text into ──────────────────────
//
// The page parses a text's HTML into an inert template and inserts only nodes that
// sanitizeNodes rebuilds from the allowlist. The session plays the template with plain
// objects built from the recording's tree, which Python's HTML parser made from what
// KPress alone renders; the real browser's parse is checked in the QA runbook's
// walkthrough with a network watch.

const ALLOWED_ATTRIBUTES = {
  a: ["href", "target", "rel"],
  ol: ["start"],
  td: ["colspan", "rowspan", "align"],
  th: ["colspan", "rowspan", "align"],
  details: ["open"],
};

function templateNodes(tree) {
  return tree.map((node) =>
    typeof node === "string"
      ? { nodeType: 3, nodeValue: node }
      : {
          nodeType: 1,
          tagName: node.tag.toUpperCase(),
          getAttribute: (name) => node.attrs.find(([key]) => key === name)?.[1] ?? null,
          childNodes: templateNodes(node.children),
        },
  );
}

// What sanitizeNodes builds: new elements and text, then serialized as a browser would.
const pageDocument = {
  createTextNode: (value) => ({ text: String(value) }),
  createElement: (tag) => ({
    tag,
    attributes: [],
    children: [],
    setAttribute(name, value) {
      this.attributes.push([name, String(value)]);
    },
    append(...nodes) {
      this.children.push(...nodes);
    },
  }),
};

function escapeText(value) {
  return value.replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;");
}

function serialize(nodes) {
  return nodes
    .map((node) => {
      if ("text" in node) {
        return escapeText(node.text);
      }
      for (const [name] of node.attributes) {
        assert(
          (ALLOWED_ATTRIBUTES[node.tag] ?? []).includes(name),
          `the page kept ${node.tag}[${name}]`,
        );
      }
      const attributes = node.attributes
        .map(([name, value]) =>
          name === "open" ? " open" : ` ${name}="${escapeText(value).replaceAll('"', "&quot;")}"`,
        )
        .join("");
      const inner = serialize(node.children);
      return node.tag === "br" || node.tag === "hr"
        ? `<${node.tag}${attributes}>`
        : `<${node.tag}${attributes}>${inner}</${node.tag}>`;
    })
    .join("");
}

/**
 * A scripted server and injected browser facilities for one page.
 *
 * The pull route answers the recording the step set, or a 304 when the page sends that
 * answer's entity tag; the refresh route answers from its own queue; the Markdown route
 * holds each answer until the step settles it, so concurrency is visible.
 */
function createPage(runtime, options) {
  const log = [];
  const timers = new Map();
  let nextTimer = 1;
  let visible = true;
  let paints = [];
  let rendered = [];
  let reloads = 0;
  // What the conversation last painted, to run the page's own paint decision on each paint.
  let conversation = { key: "", recordAt: null };
  const server = { pull: null, refresh: [], pin: [], markdown: new Map(), held: [] };
  const clock = { now: Date.parse("2026-09-17T12:00:30Z") };

  const deps = {
    async request(method, route, requestOptions) {
      if (method === "POST") {
        log.push(`POST ${route} ${JSON.stringify(requestOptions.body)}`);
        const answer = (route === "/api/source/pin" ? server.pin : server.refresh).shift();
        assert(answer, `no scripted answer for POST ${route}`);
        return answer;
      }
      if (route.startsWith("/api/plugin/github/pull-markdown")) {
        log.push(`GET ${route}`);
        const part = decodeURIComponent(route.split("?part=")[1]);
        const answer = server.markdown.get(part) ?? recorded["markdown missing"];
        return new Promise((resolve) => server.held.push(() => resolve(answer)));
      }
      const answer = server.pull;
      assert(answer, "no scripted answer for the pull route");
      if (requestOptions.etag) {
        log.push(`GET ${route} (If-None-Match)`);
        if (requestOptions.etag === answer.etag) {
          return { status: 304, etag: answer.etag, body: null };
        }
      } else {
        log.push(`GET ${route}`);
      }
      return answer;
    },
    schedule(callback, delayMs) {
      const id = nextTimer++;
      timers.set(id, { callback, delayMs });
      return id;
    },
    cancel(handle) {
      timers.delete(handle);
    },
    now: () => clock.now,
    isVisible: () => visible,
    render(model) {
      paints.push(model);
    },
    renderMarkdown(part, body) {
      rendered.push({ part, html: body.html });
    },
    reload() {
      reloads += 1;
    },
  };
  const controller = runtime.createPullController(deps, options);

  async function settle() {
    for (let turn = 0; turn < 20; turn += 1) {
      await new Promise((resolve) => setImmediate(resolve));
    }
  }

  return {
    controller,
    server,
    clock,
    setVisible(value) {
      visible = value;
    },
    async releaseMarkdown() {
      while (server.held.length > 0) {
        server.held.shift()();
        await settle();
      }
    },
    async step(name, action) {
      log.length = 0;
      paints = [];
      rendered = [];
      reloads = 0;
      await action();
      await settle();
      const [timer] = [...timers.values()];
      const snapshot = controller.snapshot();
      const entry = {
        step: name,
        requests: [...log],
        timer:
          timers.size === 0
            ? null
            : timer.delayMs === runtime.FAST_POLL_MS
              ? "fast"
              : timer.delayMs === runtime.SLOW_POLL_MS
                ? "slow"
                : timer.delayMs,
        paints: paints.length,
      };
      if (reloads > 0) {
        entry.reloads = reloads;
      }
      if (paints.length > 0) {
        const last = paints[paints.length - 1];
        entry.paint = summarize(last);
        if (last.pull !== null && last.tab === "") {
          const next = { key: runtime.conversationKey(last), recordAt: last.recordAt };
          entry.conversation = runtime.conversationAction(conversation, next);
          conversation = next;
        }
      }
      entry.markdown = rendered.map((item) => `${item.part}: ${item.html.trim()}`);
      if (snapshot.inFlight > 0 || snapshot.queued.length > 0) {
        entry.waiting = { inFlight: snapshot.inFlight, queued: snapshot.queued };
      }
      return entry;
    },
    fire() {
      const [[id, timer]] = [...timers.entries()];
      timers.delete(id);
      timer.callback();
    },
  };
}

/**
 * What a first open of a hunk's disclosure does, through the page's own function: nothing
 * until the disclosure toggles, and then one build of a line each, whatever toggles after.
 * The browser's part is firing `toggle`; an EventTarget keeps a listener's `once` as it does.
 */
function firstOpen(runtime, earlier) {
  const details = new EventTarget();
  const built = [];
  const plain = { replaceWith: (lines) => built.push(lines) };
  runtime.tintOnFirstOpen(details, plain, earlier, (lines) => lines);
  assert(built.length === 0, "a disclosure built its lines before it was opened");
  for (let toggles = 0; toggles < 3; toggles += 1) {
    details.dispatchEvent(new Event("toggle"));
  }
  assert(built.length === 1, `a disclosure built its lines ${built.length} times`);
  return built[0];
}

/** Context lines of a long hunk, numbered from *from* to *to*. */
function context(from, to) {
  return Array.from({ length: to - from + 1 }, (_, index) => ` line ${from + index}`);
}

/** A review comment's hunk and where it points, for each thing the page decides of it. */
function hunkCases() {
  const header = "@@ -1,30 +1,30 @@ def main():";
  const single = { line: 30, original_line: 30, start_line: null, original_start_line: null };
  const hunk = (...lines) => lines.flat(2).join("\n");
  // Lines 1 to 30 of the new side, where 15 and 25 replaced older lines.
  const changed = [
    context(1, 14),
    "-old 15",
    "+new 15",
    context(16, 24),
    "-old 25",
    "+new 25",
    context(26, 30),
  ];
  return [
    ["a short hunk is whole", { ...single, diff_hunk: "@@ -1 +1,2 @@\n one\n+two" }],
    [
      "the header and a tail's worth is whole: a disclosure hides no single line",
      { ...single, diff_hunk: hunk(header, context(23, 30)) },
    ],
    ["one line more is past the tail", { ...single, diff_hunk: hunk(header, context(22, 30)) }],
    ["a long hunk shows its tail", { ...single, diff_hunk: hunk(header, changed) }],
    [
      "a range longer than the tail is all shown, from its first line, not counting a deletion",
      {
        ...single,
        start_line: 14,
        original_start_line: 14,
        diff_hunk: hunk(header, changed),
      },
    ],
    [
      "a range on the left counts deletions and not additions",
      {
        ...single,
        side: "LEFT",
        start_line: 15,
        original_start_line: 15,
        diff_hunk: hunk(header, changed),
      },
    ],
    [
      "an outdated comment's range is its original one",
      {
        line: null,
        start_line: null,
        original_line: 30,
        original_start_line: 14,
        diff_hunk: hunk(header, changed),
      },
    ],
    [
      "a range above what the record kept shows all it kept",
      {
        ...single,
        start_line: 1,
        original_start_line: 1,
        diff_hunk: hunk(context(19, 30)),
      },
    ],
    [
      "a range of the most shown is all shown",
      {
        ...single,
        line: 130,
        original_line: 130,
        start_line: 31,
        original_start_line: 31,
        diff_hunk: hunk(header, context(1, 130)),
      },
    ],
    [
      "a range past the most shown shows the most, and the rest is behind the disclosure",
      {
        ...single,
        line: 130,
        original_line: 130,
        start_line: 1,
        original_start_line: 1,
        diff_hunk: hunk(header, context(1, 130)),
      },
    ],
    [
      "the other side's lines do not carry a range past the most shown",
      {
        ...single,
        start_line: 29,
        original_start_line: 29,
        diff_hunk: hunk(
          header,
          " line 29",
          Array.from({ length: 150 }, (_, index) => `-old ${index}`),
          "+new 30",
        ),
      },
    ],
    [
      "a hunk's text is only ever text",
      {
        ...single,
        diff_hunk: hunk(
          header,
          "+<img src=x onerror=alert(1)>",
          "-</pre><script>alert(1)</script>",
          " @@ not a header",
          "\\ No newline at end of file",
        ),
      },
    ],
  ];
}

/**
 * A reader's place, on a stage that stands for the pane and its page: blocks of the heights
 * a step gives them under a 120 px header, a scroll offset, and the history entry's state.
 * The geometry is the production `placeAt` and `scrollTopOf` over those heights; what the
 * browser does with `scrollTop`, a click, and a wheel is checked in Chrome. Each step prints
 * where the pane is, what the entry holds, and what the keeper still has running.
 */
function placeStory(runtime) {
  const timers = new Map();
  let nextTimer = 1;
  const stage = { heights: [], scrollTop: 0, entry: null, anchored: false, writes: 0 };
  const tops = () => {
    let next = 120;
    return stage.heights.map((height) => {
      const top = next;
      next += height;
      return top;
    });
  };
  const keeperFor = () =>
    runtime.createScrollKeeper({
      read: () => stage.entry,
      write(place) {
        stage.entry = place;
        stage.writes += 1;
      },
      measure: () => runtime.placeAt(tops(), stage.scrollTop),
      apply(place) {
        const top = runtime.scrollTopOf(place, tops());
        if (top === null) {
          return false;
        }
        stage.scrollTop = top;
        return true;
      },
      anchored: () => stage.anchored,
      toTop() {
        stage.scrollTop = 0;
      },
      schedule(callback, delayMs) {
        const id = nextTimer++;
        timers.set(id, { callback, delayMs });
        return id;
      },
      cancel: (handle) => timers.delete(handle),
    });
  const fire = (delayMs) => {
    for (const [id, timer] of [...timers]) {
      if (timer.delayMs === delayMs) {
        timers.delete(id);
        timer.callback();
      }
    }
  };
  const fireWrite = () => fire(runtime.PLACE_WRITE_MS);
  const fireSettle = () => fire(runtime.LANDING_SETTLE_MS);
  let keeper = keeperFor();
  // A line per step, so the transcript stays within what tryscript can match.
  const steps = {};
  const step = (name, action) => {
    stage.writes = 0;
    action();
    const { holding, writing, settling } = keeper.snapshot();
    const running = [
      ...(holding === null ? [] : ["holding"]),
      ...(writing ? ["write waiting"] : []),
      ...(settling ? ["settling"] : []),
    ];
    steps[name] =
      `pane at ${stage.scrollTop}; entry ${JSON.stringify(stage.entry)}; ` +
      `${stage.writes} written; ${running.join(", ") || "nothing running"}`;
  };
  /** Another page, as a landing that loads the document again has: the entry alone remains. */
  const reopen = (heights = []) => {
    keeper.dispose();
    keeper = keeperFor();
    stage.heights = heights;
    stage.scrollTop = 0;
  };

  stage.scrollTop = 500;
  step("a new entry starts at the top and writes nothing", () => keeper.land());
  stage.heights = [300, 400, 500, 600, 700];
  step("the page paints: the pane stays at the top", () => keeper.contentChanged());
  step("the reader scrolls: nothing is written while the pane moves", () => {
    stage.scrollTop = 600;
    keeper.scrolled();
    stage.scrollTop = 900;
    keeper.scrolled();
  });
  step("the pane is still: its place is written", fireWrite);
  step("still in the header: the scroll offset says where", () => {
    stage.scrollTop = 80;
    keeper.scrolled();
    fireWrite();
  });
  step("a click writes a waiting place before it can leave this entry", () => {
    stage.scrollTop = 900;
    keeper.scrolled();
    keeper.flush();
  });
  step("with nothing waiting, a click writes nothing", () => keeper.flush());

  // Back onto the entry, which loads the page again. The texts are plain, and shorter, and
  // what was rendered above the place has not been asked for, so the same pixels would be
  // somewhere else.
  reopen();
  step("back: nothing is painted, so the place waits", () => keeper.land());
  stage.heights = [200, 300, 500, 600, 700];
  step("the page paints: the pane goes to the block, not to the pixels", () =>
    keeper.contentChanged(),
  );
  stage.heights = [200, 300, 800, 600, 700];
  step("a text at the place renders: the block's top has not moved", () => keeper.contentChanged());
  stage.heights = [200, 650, 800, 600, 700];
  step("a text above the place renders: the pane is put back", () => keeper.contentChanged());
  step("the hold's own scrolling is not the reader's and writes nothing", () => keeper.scrolled());
  step("the page has been still long enough: the landing is over", fireSettle);
  stage.heights = [200, 900, 800, 600, 700];
  step("a later change no longer moves the pane", () => keeper.contentChanged());

  stage.entry = { block: 3, offset: 40, top: 2000 };
  reopen();
  step("back again: the place waits for the page", () => keeper.land());
  step("the reader moves first: the place is theirs", () => keeper.readerMoved());
  stage.heights = [300, 400, 500, 600, 700];
  step("the page paints: the pane is not moved", () => keeper.contentChanged());

  reopen(stage.heights);
  step("back with the page there: the pane is placed at once", () => keeper.land());
  step("the reader moves during the hold", () => {
    keeper.readerMoved();
    stage.scrollTop = 2500;
    keeper.scrolled();
  });
  stage.heights = [900, 400, 500, 600, 700];
  step("a change after that does not undo it", () => keeper.contentChanged());
  step("and the reader's new place is written", fireWrite);

  stage.entry = { block: 2, offset: 10, top: 900 };
  stage.anchored = true;
  reopen(stage.heights);
  stage.scrollTop = 700;
  step("an address with a fragment names its own place: the pane is left alone", () =>
    keeper.land(),
  );
  stage.anchored = false;

  stage.entry = { block: 2, offset: 10, top: 900 };
  reopen(stage.heights);
  step("back and forward between tabs: this tab's place", () => keeper.land());
  fireSettle();
  stage.entry = { block: 1, offset: 5, top: 400 };
  step("a write still waiting when history moves is dropped with the old entry", () => {
    stage.scrollTop = 1500;
    keeper.scrolled();
    keeper.land();
  });
  fireSettle();

  stage.entry = { block: 40, offset: 10, top: 90000 };
  reopen([300, 400]);
  step("a page with fewer blocks than the place shows its last", () => keeper.land());
  keeper.readerMoved();

  for (const value of [{ block: "1", offset: 0, top: 0 }, { block: 1 }, "nonsense"]) {
    stage.entry = value;
    reopen([300, 400]);
    stage.scrollTop = 200;
    step(`what is not a place is no place: ${JSON.stringify(value)}`, () => keeper.land());
  }

  stage.entry = { block: 1, offset: 5, top: 400 };
  reopen([300, 400]);
  keeper.land();
  stage.scrollTop = 900;
  step("dispose ends all of it", () => {
    keeper.scrolled();
    keeper.dispose();
  });
  assert(timers.size === 0, "a disposed keeper left a timer running");
  step("a disposed keeper does nothing", () => {
    keeper.land();
    keeper.contentChanged();
    keeper.scrolled();
    keeper.flush();
  });
  assert(timers.size === 0, "a disposed keeper started a timer");
  // Asserted rather than printed, because this transcript is at the size tryscript can match.
  // Safari throws past 100 `history.replaceState` calls in 30 s, however the moves are paced.
  for (const betweenMoves of [101, 150, 200, 333, 351, 400, 1000]) {
    const written = writesWhileMoving(runtime, betweenMoves);
    assert(written < 100, `${written} writes in 30 s, moving every ${betweenMoves} ms`);
  }
  // A key ends a hold only if it can move the pane: not a bare modifier, and not typing.
  const field = { closest: () => ({}) };
  for (const [key, target, moves] of [
    ["PageDown", null, true],
    ["ArrowDown", null, true],
    [" ", null, true],
    ["Tab", null, true],
    ["Tab", field, true],
    ["ArrowDown", field, false],
    [" ", field, false],
    ["Shift", null, false],
    ["Meta", null, false],
    ["a", null, false],
  ]) {
    assert(
      runtime.keyMovesPane(key, target) === moves,
      `"${key}"${target ? " in a field" : ""} should${moves ? "" : " not"} end a hold`,
    );
  }
  return steps;
}

/** How many places a keeper writes in 30 s to a pane that moves every *betweenMs*. */
function writesWhileMoving(runtime, betweenMs) {
  const timers = new Map();
  let nextTimer = 1;
  let clock = 0;
  let written = 0;
  const keeper = runtime.createScrollKeeper({
    read: () => null,
    write() {
      written += 1;
    },
    measure: () => ({ block: 0, offset: 0, top: 0 }),
    apply: () => true,
    anchored: () => false,
    toTop() {},
    schedule(callback, delayMs) {
      const id = nextTimer++;
      timers.set(id, { at: clock + delayMs, callback });
      return id;
    },
    cancel: (handle) => timers.delete(handle),
  });
  for (clock = 0; clock < 30000; clock += betweenMs) {
    for (const [id, timer] of [...timers]) {
      if (timer.at <= clock) {
        timers.delete(id);
        timer.callback();
      }
    }
    keeper.scrolled();
  }
  keeper.dispose();
  return written;
}

async function main() {
  const runtime = await import(pathToFileURL(pagePath).href);
  const record = recorded.current.body.record;
  const comment = record.issue_comments[0].id;
  const review = record.reviews[1].id;
  const threadStart = record.review_comments[0].id;
  const added = recorded.refreshed.body.record.issue_comments[1].id;
  const page = createPage(runtime, { number: 7, tab: "" });
  const { controller, server } = page;
  const steps = [];

  server.pull = recorded.absent;
  steps.push(await page.step("open with nothing cached", () => controller.start()));
  steps.push(await page.step("an unchanged answer is a 304", async () => page.fire()));

  server.refresh.push(recorded.refresh_started);
  steps.push(await page.step("fetch it", () => controller.requestRefresh()));
  server.pull = recorded.pending;
  steps.push(await page.step("still fetching", async () => page.fire()));

  server.pull = recorded.current;
  steps.push(await page.step("the record arrives", async () => page.fire()));

  server.markdown.set("body", recorded["markdown body"]);
  server.markdown.set(`issue_comment/${comment}`, recorded["markdown issue_comment"]);
  server.markdown.set(`review/${review}`, recorded["markdown review"]);
  server.markdown.set(`review_comment/${threadStart}`, recorded["markdown review_comment"]);
  steps.push(
    await page.step("a reader reaches four texts; two renders run at once", async () => {
      for (const part of [
        "body",
        `issue_comment/${comment}`,
        `review/${review}`,
        `review_comment/${threadStart}`,
      ]) {
        controller.requestMarkdown(part);
      }
    }),
  );
  steps.push(await page.step("the renders arrive", () => page.releaseMarkdown()));
  steps.push(
    await page.step("a part asked for again comes from memory", async () =>
      controller.requestMarkdown("body"),
    ),
  );
  steps.push(
    await page.step("a part the record lacks stays plain", async () => {
      controller.requestMarkdown("issue_comment/1");
      await page.releaseMarkdown();
    }),
  );

  // Serving began on the default branch, because the pull request could not be opened
  // then; the record now names its head, which the page offers and the pin route takes.
  server.pin.push(recorded.switch_to_head);
  steps.push(
    await page.step("switch the pin to the head the record names", () => controller.switchToHead()),
  );
  server.pull = recorded.on_head;
  steps.push(await page.step("reloaded on the head, nothing is offered", async () => page.fire()));

  steps.push(await page.step("open Files changed", async () => controller.setTab("files")));
  steps.push(await page.step("back to the conversation", async () => controller.setTab("")));

  page.clock.now = Date.parse("2026-09-17T12:05:30Z");
  server.pull = recorded.stale;
  steps.push(await page.step("the record goes stale", async () => page.fire()));

  server.refresh.push(recorded.refresh_again);
  steps.push(await page.step("refresh the stale page", () => controller.requestRefresh()));
  server.pull = recorded.stale_refreshing;
  steps.push(await page.step("still refreshing", async () => page.fire()));

  server.pull = recorded.refreshed_unchanged;
  steps.push(
    await page.step("a refresh that changed no text keeps the conversation", async () =>
      page.fire(),
    ),
  );
  // The body's render was made from the older record; answered now, it is dropped.
  steps.push(
    await page.step("a render of the older record is dropped", async () => {
      controller.requestMarkdown("body");
      await page.releaseMarkdown();
    }),
  );
  // Another tab refreshed it; the page learns of the new record from its poll.
  server.pull = recorded.refreshed;
  steps.push(
    await page.step("another refresh brought a comment full of markup", async () => page.fire()),
  );
  server.markdown.set(`issue_comment/${added}`, recorded["markdown added"]);
  steps.push(
    await page.step("the hook sends the comment inert", async () => {
      controller.requestMarkdown(`issue_comment/${added}`);
      await page.releaseMarkdown();
    }),
  );

  page.setVisible(false);
  steps.push(
    await page.step("a hidden page stops polling", async () => controller.onVisibilityChange()),
  );
  page.setVisible(true);
  steps.push(
    await page.step("shown again, it polls at once", async () => controller.onVisibilityChange()),
  );
  steps.push(await page.step("dispose", async () => controller.dispose()));

  // A page opened in a background tab, on its Files changed: it reads the record once so
  // it has something to show, and polls only once it is visible.
  const background = createPage(runtime, { number: 7, tab: "files" });
  background.setVisible(false);
  background.server.pull = recorded.current;
  steps.push(
    await background.step("a page opened in the background reads once", () =>
      background.controller.start(),
    ),
  );

  // A tab the page does not have, which the route's grammar never sends: taken, it would
  // select neither tab above the conversation it shows. Asked for at the start or later,
  // the page stays on a tab it has.
  const unknownTab = createPage(runtime, { number: 7, tab: "commits" });
  unknownTab.server.pull = recorded.absent;
  steps.push(
    await unknownTab.step("a page opened on a tab it does not have shows the conversation", () =>
      unknownTab.controller.start(),
    ),
  );
  steps.push(
    await unknownTab.step("a tab it does not have is not taken later", async () =>
      unknownTab.controller.setTab("commits"),
    ),
  );

  // What the header says, and how the checks are counted, for an open, a merged, and a
  // closed pull request, each as the served server answered it.
  const states = Object.fromEntries(
    [
      ["open", recorded.current.body],
      ["merged", recorded.merged.body],
      ["closed", recorded.closed.body],
      ["merged_unattributed", recorded.merged_unattributed.body],
    ].map(([name, body]) => {
      const model = runtime.describePull(body, {
        number: body.number,
        tab: "",
        nowMs: page.clock.now,
      });
      return [name, { header: summarize(model).header, checks: model.checks?.counts ?? null }];
    }),
  );

  // What a page for another number, and the links a rendered text keeps, would show.
  const other = runtime.describePull(recorded.current.body, {
    number: 8,
    tab: "",
    nowMs: page.clock.now,
  });
  const base = record.pull.html_url;
  const links = [
    "docs/new.md",
    "https://example.com/a",
    "javascript:alert(1)",
    "data:text/html,x",
    "//evil.example/x",
  ].map((href) => ({ href, followed: runtime.safeLink(href, base) }));

  // The page's own defense, played on what KPress alone made of the hostile comment: the
  // nodes rebuilt from the template the page parses it into.
  const inert = serialize(
    inertHtml.sanitizeNodes(templateNodes(recorded["kpress added"].body.tree), pageDocument, base),
  );

  // Files changed keeps the diff it opened: a record whose comparison moved offers it.
  // The diff opened before the switch compared the base with the pin served then.
  const comparison = recorded.current.body.record.comparison;
  const recordComparison = { left: comparison.base, right: comparison.head };
  const openedOnPin = { left: comparison.base, right: recorded.current.body.pin };
  const files = [
    ["nothing open yet", null, recordComparison],
    ["open on the record's comparison", recordComparison, recordComparison],
    ["open on an older head", openedOnPin, recordComparison],
    ["no comparison in the record", recordComparison, null],
  ].map(([when, mounted, next]) => `${when}: ${runtime.filesAction(mounted, next)}`);

  // What Files changed says instead, for a record whose comparison could not be made and
  // for one whose merge base the store's shallow history cannot settle.
  const filesUnavailable = Object.fromEntries(
    ["fetch_failed", "no_merge_base", "base_uncertain", "commits_unavailable"].map((why) => {
      const answer = structuredClone(recorded.current.body);
      answer.record.comparison = null;
      answer.record.unavailable = { comparison: why };
      const model = runtime.describePull(answer, { number: 7, tab: "", nowMs: page.clock.now });
      return [why, { files: model.filesUnavailable, notes: model.notes }];
    }),
  );

  // What a review comment shows of its hunk: the recorded pull request with one comment,
  // whose fields are the case's, through describePull. The stand-in's hunks are short, as
  // a recording is small, so the long ones are written here. Whatever the case, the two
  // parts hold the hunk's every line in order, and the tail ends with the hunk's end. What
  // is painted at once never passes the most shown, with the one line a disclosure is too
  // big for.
  const reviewComment = record.review_comments[0];
  const hunks = Object.fromEntries(
    hunkCases().map(([name, fields]) => {
      const answer = structuredClone(recorded.current.body);
      answer.record.review_comments = [{ ...reviewComment, ...fields }];
      const [{ hunk }] = runtime.describePull(answer, {
        number: 7,
        tab: "",
        nowMs: page.clock.now,
      }).reviewComments;
      const earlier = hunk.earlierLines === 0 ? [] : firstOpen(runtime, hunk.earlier);
      assert(earlier.length === hunk.earlierLines, `${name}: the disclosure's count is wrong`);
      const parts = [...earlier, ...hunk.shown].map((line) => line.text);
      assert(parts.join("\n") === fields.diff_hunk, `${name}: a line of the hunk was lost`);
      assert(hunk.shown.at(-1).text === parts.at(-1), `${name}: the tail lost the commented line`);
      assert(hunk.shown.length <= runtime.HUNK_RANGE_LINES + 1, `${name}: past the most shown`);
      const said = (line) => `${line.kind}: ${line.text}`;
      const shown = hunk.shown.map(said);
      return [
        name,
        {
          earlier:
            earlier.length === 0
              ? null
              : `${earlier.length} lines: ${said(earlier[0])} ... ${said(earlier.at(-1))}`,
          // All of a tail, or its count and its ends where a range has made it long.
          shown:
            shown.length <= 40 ? shown : `${shown.length} lines: ${shown[0]} ... ${shown.at(-1)}`,
        },
      ];
    }),
  );

  // Printed in two parts: this script prints the first, and
  // github-pull-page-second-session.js, which runs this same session, the second.
  // tryscript matches a command's expected output as one regular expression, and the
  // whole transcript in one block is larger than V8 compiles. `--part 2` selects the
  // second here, and `--part all` prints everything, for a reader.
  const first = {
    steps,
    states,
    otherNumber: { status: other.status, message: other.message, served: other.served },
    links,
    wire: runtime.gitPathWire("src/app.txt"),
    pageDefense: inert,
    filesChanged: files,
  };
  const second = { filesUnavailable, hunks, place: placeStory(runtime) };
  const part = process.argv.indexOf("--part");
  const wanted = part === -1 ? "1" : process.argv[part + 1];
  const chosen = wanted === "all" ? { ...first, ...second } : wanted === "2" ? second : first;
  console.log(JSON.stringify(chosen, null, 2));
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});

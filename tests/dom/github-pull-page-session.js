// Browserless session: a pull request's page, driven through the production
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
// would paint, and which parts it rendered as Markdown.
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
// What KPress alone made of the hostile comment, recorded beside the server's answers.
const kpressTree = JSON.parse(
  fs.readFileSync(path.join(repoRoot, "tests/fixtures/github-pull-page-kpress-tree.json"), "utf8"),
);
// The recording holds each distinct record, status, verdict, and checks once: an answer
// whose record an earlier pull-route answer carried names that answer, and reads here as
// that answer's, and so for each of the others.
// A status whose checks were listed when it was observed is recorded without the time they
// were listed, which is its own `observed_at`, and one whose checks were never seen
// otherwise without `moved_at`, which is none; any other value is as recorded.
function listedWhenObserved(field, value) {
  if (field !== "status" || value === null || typeof value !== "object" || !value.checks) {
    return value;
  }
  if (value.same_as !== undefined) {
    return value;
  }
  const checks = { ...value.checks };
  if (!("listed_at" in checks)) {
    checks.listed_at = value.observed_at;
  }
  if (!("moved_at" in checks)) {
    checks.moved_at = null;
  }
  return { ...value, checks };
}
for (const answer of Object.values(recorded)) {
  for (const envelope of [answer.body, answer.body?.pull]) {
    for (const field of ["record", "status", "readiness", "checks"]) {
      const holder = envelope?.[field]?.same_as;
      if (holder !== undefined) {
        // Anything kept beside the name, a status's own time, is this answer's; a dotted
        // name is a part of a part, as the time its checks were listed. Checks the held
        // status listed when it was observed are listed when this one was, unless it says.
        const { same_as: _held, ...own } = envelope[field];
        const held = listedWhenObserved(field, recorded[holder].body[field]);
        const value = { ...held };
        if (held.checks?.listed_at !== undefined && held.checks.listed_at === held.observed_at) {
          value.checks = { ...held.checks, listed_at: own.observed_at ?? held.observed_at };
        }
        for (const [name, part] of Object.entries(own)) {
          const [outer, inner] = name.split(".");
          value[outer] = inner === undefined ? part : { ...value[outer], [inner]: part };
        }
        envelope[field] = value;
      } else if (envelope?.[field] !== undefined) {
        envelope[field] = listedWhenObserved(field, envelope[field]);
      }
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
  // The SDK as the diff plugin's pin switch reads it, for the commit a refusal names: the
  // shell's own formatter.
  metabrowser: {
    shortCommit: require("./changed-files-tree-fixture.js").shellPainters().shortCommit,
  },
};

function assert(condition, message) {
  if (!condition) {
    throw new Error(message);
  }
}

/**
 * What a page that a step opens for one decision shows of it: its state and what it offers.
 * The whole page is `summarize`'s, once per kind of record, and tryscript's matcher has a
 * limit on how long one transcript can be.
 */
function summarizeState(model) {
  return {
    status: model.status,
    message: model.message,
    canRefresh: model.canRefresh,
    freshness: model.freshness,
    // Shown content is refreshing, by the breathing age and never a spinner; said only when so.
    ...(model.revalidating ? { revalidating: true } : {}),
    failure: model.failure,
    browse: browseCode(model),
  };
}

/** What Browse code does. */
function browseCode(model) {
  if (model.browse === null) {
    return null;
  }
  return model.browse.kind === "link" ? "link to the root" : `switches to ${model.browse.ref}`;
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
    ...(model.revalidating ? { revalidating: true } : {}),
    failure: model.failure,
    header:
      pull === null
        ? null
        : `${pull.title} #${pull.number} [${pull.stateLabel}] ${pull.actor === null ? "" : `${pull.actor} `}${pull.action}: ${pull.head} → ${pull.base}`,
    // Each label's name, GitHub's color and the properties its chip is painted from, or
    // "neutral", and its description, the chip's tooltip, or "no tip".
    labels:
      pull === null
        ? []
        : pull.labels.map(
            (label) =>
              `${label.name} ${label.color === null ? "neutral" : `#${label.color} ${label.style}`} ${label.tip === null ? "no tip" : `tip: ${label.tip}`}`,
          ),
    merge: model.merge === null ? null : `[${model.merge.state}] ${model.merge.label}`,
    timeline: model.timeline.map(
      (item) =>
        // A review's chip is only for a state its verb does not say (mb-novh).
        `${item.kind} ${item.author}${item.review?.label ? ` [${item.review.label}]` : ""} ${item.at ?? "pending"} ${item.part}`,
    ),
    reviewComments: model.reviewComments.map(
      (comment) =>
        `${comment.path}:${comment.line ?? "outdated"} ${comment.author}${comment.reply ? " (reply)" : ""}${comment.hunk ? " +hunk" : ""}`,
    ),
    // Each check's badge, its bucket's ink and its own words, as `gh pr checks` lists them.
    // The summary as its paragraph reads, gh's headline and then each bucket's tally.
    checks:
      model.checks === null
        ? null
        : {
            summary: `${model.checks.headline}: ${Object.entries(model.checks.counts)
              .map(([word, count]) => `${count} ${word}`)
              .join(" · ")}`,
            items: model.checks.items.map(
              (item) =>
                `[${item.bucket}: ${item.label}] ${item.name}${item.detail === null ? "" : ` (${item.detail})`} -> ${item.action === null ? "no action" : `${item.action.label} ${item.action.href}`}`,
            ),
          },
    ...(model.checkNotes.length === 0 ? {} : { checkNotes: model.checkNotes }),
    notes: model.notes,
    browse: browseCode(model),
    comparison:
      model.comparison === null
        ? null
        : `${model.comparison.left.slice(0, 12)}...${model.comparison.right.slice(0, 12)}`,
  };
}

// ── The template the page parses a text into ──────────────────────
//
// The page parses a text's HTML into an inert template and inserts only nodes that
// sanitizeNodes rebuilds from the allowlist. The session plays the template with plain
// objects built from the recording's tree, which Python's HTML parser made from what
// KPress alone renders; the real browser's parse is checked in the QA runbook's
// walkthrough with a network watch.

// A pull request's text keeps no image of a tree and no anchor; an image written in full
// over https is kept with no referrer, or is the fallback span; its layout attributes are
// github.com's.
const ALLOWED_ATTRIBUTES = {
  a: ["href", "target", "rel"],
  img: ["loading", "referrerpolicy", "src", "alt", "align", "width", "height"],
  span: ["class", "data-tip-text"],
  ol: ["start"],
  p: ["align"],
  div: ["align"],
  ...Object.fromEntries(["h1", "h2", "h3", "h4", "h5", "h6"].map((tag) => [tag, ["align"]])),
  table: ["align", "width"],
  thead: ["align"],
  tbody: ["align"],
  tfoot: ["align"],
  tr: ["align"],
  td: ["colspan", "rowspan", "align", "width", "height"],
  th: ["colspan", "rowspan", "align", "width", "height"],
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
  // The model last painted, in any step, for an invariant the brief summary leaves out.
  let lastModel = null;
  let rendered = [];
  let navigations = [];
  // What the conversation last painted, to run the page's own paint decision on each paint.
  let conversation = { key: "", textRevision: null };
  const server = {
    pull: null,
    refresh: [],
    pin: [],
    markdown: new Map(),
    held: [],
    waiting: [],
  };
  const clock = { now: Date.parse("2026-09-17T12:00:30Z") };

  const deps = {
    async request(method, route, requestOptions) {
      if (method === "POST") {
        log.push(`POST ${route} ${JSON.stringify(requestOptions.body)}`);
        const answer = (route === "/api/source/pin" ? server.pin : server.refresh).shift();
        assert(answer, `no scripted answer for POST ${route}`);
        if (answer.unanswered) {
          throw new Error("the server did not answer");
        }
        if (answer.waits) {
          // An answer still on its way, until the step releases it (`releaseRefresh`).
          return new Promise((resolve) => server.waiting.push(() => resolve(answer)));
        }
        // An answer that takes this long, on the page's clock.
        clock.now += answer.takesMs ?? 0;
        return answer;
      }
      if (route.startsWith("/api/plugin/github/pull-markdown")) {
        log.push(`GET ${route}`);
        const part = decodeURIComponent(route.split("&part=")[1]);
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
    schedule(callback, delayMs, kind) {
      const id = nextTimer++;
      timers.set(id, { callback, delayMs, kind });
      return id;
    },
    cancel(handle) {
      timers.delete(handle);
    },
    now: () => clock.now,
    isVisible: () => visible,
    // A hold's lift as the page says it, in en-US and UTC so the golden is the same on every
    // machine (`holdLiftText`).
    formatHold: (liftMs, nowMs) => runtime.holdLiftText(liftMs, nowMs, "en-US", "UTC"),
    render(model) {
      paints.push(model);
      lastModel = model;
    },
    renderMarkdown(part, body) {
      rendered.push({ part, html: body.html });
    },
    navigate(href) {
      navigations.push(href);
    },
    // The page's one pin switch, the diff plugin's own (diff-view-file.js), which in the
    // browser posts with fetch and here through the scripted pin route.
    switchPin: (selection, wanted) => pinSwitch.switchTo(selection, wanted),
  };
  const pinSwitch = runtime.createPinSwitch({
    post: (selection) => deps.request("POST", "/api/source/pin", { body: selection }),
    onRestored: () => () => {},
  });
  const controller = runtime.createPullController(deps, options);
  // The page names its asks (`askAfter`), so a poll and an ask with the same delay differ.
  const isAsk = (timer) => timer.kind === "ask";

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
    /** Answer the oldest refresh request still on its way. */
    async releaseRefresh() {
      server.waiting.shift()();
      await settle();
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
      navigations = [];
      await action();
      await settle();
      const timer = [...timers.values()].find((each) => !isAsk(each));
      const snapshot = controller.snapshot();
      const entry = {
        step: name,
        requests: [...log],
        timer:
          timer === undefined
            ? null
            : timer.delayMs === runtime.FAST_POLL_MS
              ? "fast"
              : timer.delayMs === runtime.SLOW_POLL_MS
                ? "slow"
                : timer.delayMs,
        paints: paints.length,
      };
      const ask = [...timers.values()].find(isAsk);
      if (ask?.delayMs === runtime.REFRESH_ASK_MS) {
        entry.askWaits = true;
      } else if (ask !== undefined && ask.delayMs > 0) {
        // A current record's next probe ask, every `probe_every_s` while the page is visible.
        entry.probeAskMs = ask.delayMs;
      }
      if (navigations.length > 0) {
        entry.navigated = navigations;
      }
      if (paints.length > 0) {
        const last = paints[paints.length - 1];
        entry.paint = options.brief ? summarizeState(last) : summarize(last);
        if (last.pull !== null && last.tab === "") {
          const next = { key: runtime.conversationKey(last), textRevision: last.textRevision };
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
    /** The poll that is due. */
    fire() {
      const [id, timer] = [...timers.entries()].find(([, each]) => !isAsk(each));
      timers.delete(id);
      timer.callback();
    },
    /** A cold page asks immediately; a stale page waits for the reader to stay. */
    fireAsk(delayMs = runtime.REFRESH_ASK_MS) {
      const [[id, timer]] = [...timers.entries()].filter(
        ([, each]) => isAsk(each) && each.delayMs === delayMs,
      );
      timers.delete(id);
      timer.callback();
    },
    timersLeft: () => timers.size,
    lastModel: () => lastModel,
    /** The waiting ask's delay, or null with none waiting. */
    askDelay: () => [...timers.values()].find(isAsk)?.delayMs ?? null,
    /** The poll's timer, to tell a poll left waiting from one armed again. */
    pollTimer: () => [...timers.entries()].find(([, each]) => !isAsk(each))?.[0] ?? null,
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
  // `files` names each block's changed file, as Changes' blocks have one; null on a page of
  // cards, whose places name none.
  const stage = {
    heights: [],
    files: null,
    scrollTop: 0,
    entry: null,
    anchored: false,
    writes: 0,
  };
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
      measure() {
        const at = runtime.placeAt(tops(), stage.scrollTop);
        return stage.files === null || at.block < 0 ? at : { ...at, file: stage.files[at.block] };
      },
      apply(place) {
        // As the page's own keeper asks the mounted diff: a place that names no file, or a
        // page with no diff to ask, leaves it out; a diff without the file answers -1.
        const fileBlock =
          place.file === undefined || stage.files === null
            ? undefined
            : stage.files.indexOf(place.file);
        const top = runtime.scrollTopOf(place, tops(), fileBlock);
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

  // A place deep in a header that was taller, an open Diff summary's rows, on a page that
  // draws its header shorter: the first block, not that many pixels into the page.
  stage.entry = { block: -1, offset: 0, top: 30000 };
  reopen([300, 400]);
  step("a place in a header now shorter shows the first block", () => keeper.land());
  keeper.readerMoved();

  for (const value of [{ block: "1", offset: 0, top: 0 }, { block: 1 }, "nonsense"]) {
    stage.entry = value;
    reopen([300, 400]);
    stage.scrollTop = 200;
    step(`what is not a place is no place: ${JSON.stringify(value)}`, () => keeper.land());
  }

  // Changes, whose blocks are files. The diff is replaced by a newer head's, with a file
  // added above the reader's and one removed: the place is its file's, not its index's.
  stage.entry = null;
  reopen([300, 400, 500]);
  stage.files = ["a.py", "b.py", "c.py"];
  keeper.land();
  stage.scrollTop = 460;
  let reading = null;
  step("in Changes a place names its file", () => {
    keeper.scrolled();
    fireWrite();
    reading = keeper.snapshot().holding ?? stage.entry;
  });
  stage.heights = [];
  stage.scrollTop = 0;
  step("the diff is replaced: the place is held, and written for a reload", () =>
    keeper.holdAt(reading),
  );
  // The emptied pane clamps to its top while the newer comparison is read, which arrives as
  // a scroll: it is the hold's, so the place a reload lands on stays the reader's (A3 of
  // review A on #745).
  step("the emptied pane clamps to its top: the place stays written", () => {
    keeper.scrolled();
    fireWrite();
  });
  stage.heights = [250, 300, 400, 500];
  stage.files = ["new.py", "a.py", "b.py", "c.py"];
  step("the newer diff paints: the pane is in the same file, a block further on", () =>
    keeper.contentChanged(),
  );
  stage.heights = [250, 900, 400, 500];
  step("a file above it draws its lines: the pane is put back", () => keeper.contentChanged());
  fireSettle();
  stage.files = ["new.py", "a.py", "c.py"];
  stage.heights = [250, 900, 500];
  reopen(stage.heights);
  step("loaded again on a diff without the file: the top of the block at its index", () =>
    keeper.land(),
  );
  keeper.readerMoved();
  stage.files = null;
  stage.entry = { block: 1, offset: 5, top: 400, file: 7 };
  reopen([300, 400]);
  stage.scrollTop = 200;
  step("a place whose file is not a name is no place", () => keeper.land());

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
  const viewFilePath = path.join(
    repoRoot,
    "src/metabrowser/builtin_plugins/diff/diff-view-file.js",
  );
  const runtime = {
    ...(await import(pathToFileURL(pagePath).href)),
    createPinSwitch: (await import(pathToFileURL(viewFilePath).href)).createPinSwitch,
  };
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
  server.refresh.push(recorded.refresh_started);
  steps.push(await page.step("a visible cold page fetches itself", async () => page.fireAsk(0)));
  server.pull = recorded.pending;
  steps.push(await page.step("still fetching", async () => page.fire()));

  server.pull = recorded.current;
  steps.push(await page.step("the record arrives", async () => page.fire()));
  steps.push(await page.step("an unchanged answer is a 304", async () => page.fire()));

  const hiddenCold = createPage(runtime, { number: 7, tab: "", brief: true });
  hiddenCold.setVisible(false);
  hiddenCold.server.pull = recorded.absent;
  const hiddenOpen = await hiddenCold.step("open a cold page in the background", () =>
    hiddenCold.controller.start(),
  );
  assert(hiddenOpen.requests.length === 1 && hiddenOpen.requests[0].startsWith("GET "));
  assert(hiddenCold.timersLeft() === 0, "a hidden cold page schedules no network work");
  hiddenCold.setVisible(true);
  hiddenCold.server.refresh.push(recorded.refresh_started);
  await hiddenCold.step("show it", () => hiddenCold.controller.onVisibilityChange());
  const hiddenFetch = await hiddenCold.step("it fetches now", async () => hiddenCold.fireAsk(0));
  assert(
    hiddenFetch.requests.includes(
      'POST /api/plugin/github/pull-refresh {"number":7,"retry":true,"wait_core":true}',
    ),
    "a newly visible cold page fills its cache",
  );
  hiddenCold.controller.dispose();

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
  // then, and a reader who opened any pull request from a branch is in the same place.
  // Nothing is wrong, so nothing is offered: Browse code serves the head and then opens.
  server.pin.push(recorded.switch_refused);
  steps.push(
    await page.step("Browse code that the server refuses says why and stays", () =>
      controller.browseCode("/view/"),
    ),
  );
  server.pin.push(recorded.switch_to_head);
  steps.push(
    await page.step("Browse code serves the head and opens the root", () =>
      controller.browseCode("/view/"),
    ),
  );
  server.pull = recorded.on_head;
  steps.push(await page.step("on the head, Browse code is a link", async () => page.fire()));
  steps.push(
    await page.step("with a link, the controller switches nothing", () =>
      controller.browseCode("/view/"),
    ),
  );

  steps.push(await page.step("open Changes", async () => controller.setTab("files")));
  steps.push(await page.step("back to the conversation", async () => controller.setTab("")));

  page.clock.now = Date.parse("2026-09-17T12:05:30Z");
  server.pull = recorded.stale;
  steps.push(await page.step("the record goes stale", async () => page.fire()));
  server.refresh.push(recorded.refresh_again);
  steps.push(
    await page.step("the reader stayed: the page asks for a refresh by itself", async () =>
      page.fireAsk(),
    ),
  );
  server.pull = recorded.stale_refreshing;
  steps.push(await page.step("still refreshing", async () => page.fire()));

  server.pull = recorded.refreshed_unchanged;
  steps.push(
    await page.step("a refresh that changed no text keeps the conversation", async () =>
      page.fire(),
    ),
  );
  // The same content revision keeps an already requested render usable after refresh.
  steps.push(
    await page.step("a same-content render remains usable after a refresh", async () => {
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
  // A prior failed poll must not survive the pin guard's refusal.
  server.pull = { status: 502, etag: null, body: null };
  const failedPoll = await page.step("a poll failed before the pin moved", async () => page.fire());
  assert(
    failedPoll.paint.message.includes("could not be loaded"),
    "the failed poll did not show its error",
  );
  // A page Back restores after the pin moved polls before the pin guard reloads it. The
  // guard's refusal is the guard's to answer, so the page says nothing of its own.
  server.pull = {
    status: 409,
    etag: null,
    body: { error: "the server now serves another revision", code: "pin_changed", pin: null },
  };
  const refused = await page.step("a poll the pin guard refused", async () => page.fire());
  assert(refused.requests.length === 1, `the refused poll was not sent: ${refused.requests}`);
  assert(
    refused.paint !== undefined && refused.paint.message === null,
    `a pin_changed poll painted: ${JSON.stringify(refused.paint)}`,
  );
  server.pull = recorded.refreshed;
  steps.push(await page.step("dispose", async () => controller.dispose()));

  // A page opened in a background tab, on its Files changed: it reads the record once so
  // it has something to show, and polls only once it is visible. Its record is stale, and
  // it asks for a refresh only then.
  const background = createPage(runtime, { number: 7, tab: "files", brief: true });
  background.setVisible(false);
  background.clock.now = page.clock.now;
  background.server.pull = recorded.stale;
  steps.push(
    await background.step("a page opened in the background reads once and asks for nothing", () =>
      background.controller.start(),
    ),
  );
  background.setVisible(true);
  steps.push(
    await background.step("shown, its ask waits for the reader to stay", async () =>
      background.controller.onVisibilityChange(),
    ),
  );
  background.server.refresh.push(recorded.refresh_again);
  steps.push(await background.step("the reader stayed: it asks", async () => background.fireAsk()));

  // A page left open keeps refreshing: once its refresh has landed and the record goes stale
  // again, it asks again, at once, showing the plain age and offering nothing to press, rather
  // than staying stale.
  const leftOpen = createPage(runtime, { number: 7, tab: "", brief: true });
  /** Printed with the second part: tryscript compiles one block's output as one regex. */
  const leftOpenStory = [];
  leftOpen.clock.now = page.clock.now;
  leftOpen.server.pull = recorded.stale;
  await leftOpen.controller.start();
  leftOpen.server.refresh.push(recorded.refresh_again);
  leftOpenStory.push(
    await leftOpen.step("a page left open asks for its refresh", () => leftOpen.fireAsk()),
  );
  leftOpen.server.pull = recorded.refreshed;
  leftOpenStory.push(await leftOpen.step("the refresh lands", async () => leftOpen.fire()));
  leftOpen.clock.now = Date.parse("2026-09-17T12:07:30Z");
  const staleAgain = { ...recorded.refreshed.body, state: "stale" };
  leftOpen.server.pull = { status: 200, etag: '"stale again"', body: staleAgain };
  const wentStale = await leftOpen.step("a minute on, its record goes stale again", async () =>
    leftOpen.fire(),
  );
  assert(
    wentStale.paint.revalidating === true &&
      wentStale.paint.canRefresh === false &&
      wentStale.paint.freshness === "Fetched 1 min ago via GitHub CLI",
    `a page left open went stale without refreshing: ${JSON.stringify(wentStale.paint)}`,
  );
  leftOpenStory.push(wentStale);
  leftOpen.server.refresh.push({
    status: 202,
    etag: null,
    body: { pull: { ...staleAgain, refreshing: true } },
  });
  leftOpenStory.push(
    await leftOpen.step("it asks for the next refresh at once", async () => leftOpen.fireAsk(0)),
  );
  leftOpen.controller.dispose();

  // A current page left open asks every `probe_every_s`, and the server answers each ask
  // with a probe, a conditional read GitHub answers for free: unchanged, it is not due,
  // and the record is vouched for by the probe, with the age line not pulsing. Hidden, the
  // page asks nothing; shown again, it asks when its interval has passed. A probe that
  // finds a change starts the refresh, which the page then follows.
  const probing = createPage(runtime, { number: 7, tab: "", brief: true });
  /** Printed with the second part, as `leftOpen` is. */
  const probingStory = [];
  probing.clock.now = Date.parse("2026-09-17T12:06:00Z");
  probing.server.pull = recorded.refreshed;
  await probing.controller.start();
  probing.server.refresh.push(recorded.probed);
  probingStory.push(
    await probing.step("a current page asks once the reader stays, and a probe answers", () =>
      probing.fireAsk(),
    ),
  );
  const firstAsk = probingStory.at(-1);
  assert(
    firstAsk.probeAskMs === recorded.refreshed.body.probe_every_s * 1000 &&
      firstAsk.paint?.revalidating !== true,
    `a probed page does not ask again after probe_every_s: ${JSON.stringify(firstAsk)}`,
  );
  // The ask named the record the page shows, and the answer came without it (mb-jd08: the
  // cost of the whole envelope every interval is recorded beside `refresh_answer_pull` in
  // pull_route.py). The page still shows that record, under the verdict the answer brought.
  const heldAsk = `POST /api/plugin/github/pull-refresh ${JSON.stringify({
    number: 7,
    held: recorded.refreshed.body.record_revision,
  })}`;
  assert(
    recorded.probed.body.pull.record_held === true &&
      !("record" in recorded.probed.body.pull) &&
      JSON.stringify(firstAsk.requests) === JSON.stringify([heldAsk]),
    `a page that shows a record did not ask naming it: ${JSON.stringify(firstAsk.requests)}`,
  );
  assert(
    probing.lastModel().status === "current" &&
      probing.lastModel().recordRevision === recorded.refreshed.body.record_revision &&
      probing.lastModel().pull?.title === recorded.refreshed.body.record.pull.title,
    `an answer without the record took the page's record: ${JSON.stringify(firstAsk)}`,
  );
  probing.clock.now += recorded.refreshed.body.probe_every_s * 1000;
  probing.server.pull = recorded.probed_current;
  probing.server.refresh.push(recorded.probed);
  probingStory.push(
    await probing.step("its interval later it asks again, and the probe vouches", async () =>
      probing.fireAsk(recorded.refreshed.body.probe_every_s * 1000),
    ),
  );
  // The poll keeps its own slow interval while probe asks answer: an ask that started
  // nothing leaves it waiting, so it still fires, and a server that stops answering is
  // reported by it and by the failed ask itself.
  const pollWaiting = probing.pollTimer();
  const interval = recorded.refreshed.body.probe_every_s * 1000;
  for (let ask = 0; ask < 2; ask += 1) {
    probing.clock.now += interval;
    probing.server.refresh.push(recorded.probed);
    await probing.step("another interval, another probe", async () => probing.fireAsk(interval));
  }
  assert(
    probing.pollTimer() === pollWaiting,
    "a probe ask that started nothing armed the poll again, so it never fires",
  );
  probingStory.push(
    await probing.step("the poll's own interval still reads, between probe asks", async () =>
      probing.fire(),
    ),
  );
  probing.clock.now += interval;
  probing.server.refresh.push({ unanswered: true });
  probingStory.push(
    await probing.step("a probe ask the server does not answer is reported", async () =>
      probing.fireAsk(interval),
    ),
  );
  assert(
    probingStory.at(-1).paint?.message === "The server did not answer.",
    `a failed probe ask was not reported: ${JSON.stringify(probingStory.at(-1))}`,
  );
  probing.clock.now += interval;
  probing.server.refresh.push(recorded.probed);
  probingStory.push(
    await probing.step("the next probe ask that answers clears it", async () =>
      probing.fireAsk(interval),
    ),
  );
  probing.clock.now += interval;
  probing.server.refresh.push({ ...recorded.probed, takesMs: interval + 1000 });
  probingStory.push(
    await probing.step("an answer slower than the interval is followed by a short gap", async () =>
      probing.fireAsk(interval),
    ),
  );
  assert(
    probingStory.at(-1).probeAskMs === runtime.PROBE_ASK_GAP_MS,
    `a slow answer was followed by an ask at once: ${JSON.stringify(probingStory.at(-1))}`,
  );
  probing.clock.now += runtime.PROBE_ASK_GAP_MS;
  probing.server.refresh.push(recorded.probed);
  await probing.step("the gap passes and it asks", async () =>
    probing.fireAsk(runtime.PROBE_ASK_GAP_MS),
  );
  // Review B1 on #709: the record goes stale when its full read comes due, a few seconds
  // before the next probe ask would start it. The poll that reads it so asks at once,
  // since no ask for a stale record was sent within a window; it does not wait a window
  // from the probe ask before it. Asserted rather than printed: the page's transcript is at
  // its review budget, and the two steps repeat paints the story already shows.
  probing.clock.now += 2000;
  const overdue = recorded.probed_current.body;
  probing.server.pull = {
    ...recorded.probed_current,
    etag: `${recorded.probed_current.etag}-overdue`,
    body: { ...overdue, state: "stale", verified_by: "fetch", verified_at: overdue.fetched_at },
  };
  const overdueRead = await probing.step("past its full read the poll reads it stale", async () =>
    probing.fire(),
  );
  assert(
    overdueRead.paint?.status === "stale" &&
      overdueRead.paint.revalidating === true &&
      overdueRead.paint.canRefresh === false,
    `an overdue record did not paint as revalidating: ${JSON.stringify(overdueRead)}`,
  );
  assert(
    probing.askDelay() === 0,
    `a record gone stale between probe asks waited a window: ${probing.askDelay()}`,
  );
  probing.server.refresh.push({
    status: 202,
    etag: null,
    body: { pull: { ...overdue, refreshing: true } },
  });
  const fullRead = await probing.step("its full read starts", async () => probing.fireAsk(0));
  assert(
    JSON.stringify(fullRead.requests) === JSON.stringify([heldAsk]) && fullRead.timer === "fast",
    `an overdue record's ask did not start its full read: ${JSON.stringify(fullRead)}`,
  );
  probing.server.pull = recorded.probed_current;
  await probing.step("the full read ends and the record is current", async () => probing.fire());
  // An answer that leaves out a record the page does not hold is not shown: the server's
  // moved on between the ask and its answer, or it has no store and so drops the
  // comparison of a record with the same revision. The page reads the route at once,
  // unconditionally, and shows what that read brings. Asserted rather than printed, as
  // the steps above are.
  for (const differs of [{ record_revision: "0".repeat(64) }, { no_store: true }]) {
    probing.clock.now += interval;
    probing.server.refresh.push({
      ...recorded.probed,
      body: { ...recorded.probed.body, pull: { ...recorded.probed.body.pull, ...differs } },
    });
    const unheld = await probing.step("an answer about a record the page lacks", async () =>
      probing.fireAsk(interval),
    );
    assert(
      JSON.stringify(unheld.requests) === JSON.stringify([heldAsk]) && unheld.timer === 0,
      `an answer about another record did not make a read due: ${JSON.stringify(unheld)}`,
    );
    const reread = await probing.step("which the page reads at once", async () => probing.fire());
    assert(
      JSON.stringify(reread.requests) ===
        JSON.stringify(["GET /api/plugin/github/pull?number=7"]) &&
        probing.lastModel().status === "current" &&
        !probing.lastModel().message &&
        probing.lastModel().recordRevision === recorded.refreshed.body.record_revision,
      `an answer about another record was not followed by a whole read: ${JSON.stringify(reread)}`,
    );
  }
  // The revision leaves out `fetched_at`, so a read another asker made of the same content
  // is answered without the record too: the page's record takes the answer's time, and its
  // age line says what the whole answer would have (review A1 on #746).
  probing.clock.now += 5 * 60_000;
  const readElsewhere = new Date(probing.clock.now).toISOString().replace(".000Z", "Z");
  const heldPull = recorded.probed.body.pull;
  probing.server.refresh.push({
    ...recorded.probed,
    body: {
      ...recorded.probed.body,
      pull: { ...heldPull, fetched_at: readElsewhere, verified_at: readElsewhere },
    },
  });
  await probing.step("a held answer after another asker's read", async () =>
    probing.fireAsk(interval),
  );
  const wholeAnswer = runtime.describePull(
    {
      ...probing.server.pull.body,
      fetched_at: readElsewhere,
      verified_at: readElsewhere,
      verified_by: heldPull.verified_by,
      record: { ...probing.server.pull.body.record, fetched_at: readElsewhere },
    },
    { number: 7, tab: "", nowMs: probing.clock.now, online: true },
  );
  assert(
    /just now/u.test(wholeAnswer.freshness) &&
      probing.lastModel().freshness === wholeAnswer.freshness,
    `a held record kept its own age: ${probing.lastModel().freshness}, not ${wholeAnswer.freshness}`,
  );
  // A held answer that lands after a newer read was shown is dropped, as a whole one is:
  // it is merged with the page's record and then refused by its request's number.
  probing.clock.now += interval;
  probing.server.refresh.push({
    ...recorded.probed,
    waits: true,
    body: { ...recorded.probed.body, pull: { ...heldPull, state: "stale" } },
  });
  await probing.step("an ask whose answer is slow", async () => probing.fireAsk(interval));
  probing.server.pull = {
    ...recorded.probed_current,
    etag: `${recorded.probed_current.etag}-newer`,
  };
  const newer = await probing.step("a poll answers first", async () => probing.fire());
  assert(
    JSON.stringify(newer.requests) ===
      JSON.stringify(["GET /api/plugin/github/pull?number=7 (If-None-Match)"]) &&
      probing.lastModel().status === "current",
    `a poll beside a slow ask did not read: ${JSON.stringify(newer)}`,
  );
  const late = await probing.step("the slow held answer lands", () => probing.releaseRefresh());
  assert(
    probing.lastModel().status === "current" && late.paint?.status !== "stale",
    `a held answer older than what the page shows replaced it: ${JSON.stringify(late)}`,
  );
  // A mismatch that lands while a reader's Refresh is on its way, as Changes offers one for
  // a current record: its read finds the Refresh pending and sends nothing, and the
  // Refresh's own answer arms the poll again.
  const crossing = createPage(runtime, { number: 7, tab: "files", brief: true });
  crossing.clock.now = Date.parse("2026-09-17T12:06:00Z");
  crossing.server.pull = recorded.refreshed;
  await crossing.controller.start();
  crossing.server.refresh.push({
    ...recorded.probed,
    waits: true,
    body: { ...recorded.probed.body, pull: { ...heldPull, record_revision: "0".repeat(64) } },
  });
  await crossing.step("an ask whose answer is slow", async () => crossing.fireAsk());
  crossing.server.refresh.push({
    status: 202,
    etag: null,
    waits: true,
    body: { pull: { ...recorded.refreshed.body, refreshing: true } },
  });
  const pressed = await crossing.step("the reader presses Refresh meanwhile", () => {
    void crossing.controller.requestRefresh();
  });
  assert(
    pressed.requests.length === 1 && /"retry":true/u.test(pressed.requests[0]),
    `Changes sent no Refresh beside the page's own ask: ${JSON.stringify(pressed)}`,
  );
  const crossed = await crossing.step(
    "the ask's answer names a record the page lacks",
    async () => {
      await crossing.releaseRefresh();
      crossing.fire();
    },
  );
  assert(
    crossed.requests.length === 0 && crossing.pollTimer() === null,
    `a read was sent under a pending Refresh: ${JSON.stringify(crossed)}`,
  );
  const answered = await crossing.step("the Refresh answers", () => crossing.releaseRefresh());
  assert(
    crossing.pollTimer() !== null && answered.timer === "fast",
    `a mismatch under a pending Refresh left no poll armed: ${JSON.stringify(answered)}`,
  );
  crossing.controller.dispose();
  probing.setVisible(false);
  await probing.controller.onVisibilityChange();
  probingStory.push(
    await probing.step("hidden, it asks nothing", async () => {
      probing.clock.now += 60_000;
    }),
  );
  assert(probingStory.at(-1).probeAskMs === undefined, "a hidden page keeps a probe ask waiting");
  probing.setVisible(true);
  probing.server.refresh.push({
    status: 202,
    etag: null,
    body: { pull: { ...recorded.probed_current.body, refreshing: true } },
  });
  probingStory.push(
    await probing.step(
      "shown again past its interval it asks at once, and a probe that found a change refreshes",
      async () => {
        await probing.controller.onVisibilityChange();
        probing.fireAsk(0);
      },
    ),
  );
  probing.controller.dispose();
  assert(probing.timersLeft() === 0, "a disposed probing page left a timer running");

  // GitHub's rate limit refused the page's refresh. It is a hold, not a failure: the page
  // offers no Refresh, names when it will ask again, which is not before `reset_at` and not
  // within a freshness window of the refused attempt, and asks at that time, at once.
  const held = createPage(runtime, { number: 7, tab: "", brief: true });
  /** Printed with the second part, as `leftOpen` is. */
  const rateLimitedStory = [];
  held.clock.now = page.clock.now;
  held.server.pull = recorded.stale;
  await held.controller.start();
  held.server.refresh.push(recorded.refresh_again);
  rateLimitedStory.push(await held.step("a stale page asks for its refresh", () => held.fireAsk()));
  const refusedAt = held.clock.now + 2000;
  const limited = {
    ...recorded.stale.body,
    last_refresh: {
      outcome: "rate_limited",
      message: "GitHub's API rate limit is exhausted",
      reset_at: new Date(refusedAt + 30_000).toISOString(),
      at: new Date(refusedAt).toISOString(),
    },
  };
  held.clock.now = refusedAt + 10_000;
  held.server.pull = { status: 200, etag: '"rate limited"', body: limited };
  const holding = await held.step("GitHub's rate limit refused it", async () => held.fire());
  const named = runtime.holdLiftText(refusedAt + 60_000, held.clock.now, "en-US", "UTC");
  assert(
    holding.paint.canRefresh === false &&
      holding.paint.failure === `GitHub rate limit reached. Next attempt after ${named}.`,
    `a held page offers Refresh or names another time: ${JSON.stringify(holding)}`,
  );
  rateLimitedStory.push(holding);
  held.clock.now = refusedAt + 40_000;
  const waking = await held.step("still held, it wakes at the time it named", async () =>
    held.fire(),
  );
  assert(waking.timer === 20_000, `a held page does not wake at the lift: ${waking.timer}`);
  rateLimitedStory.push(waking);
  held.clock.now = refusedAt + 60_000;
  rateLimitedStory.push(
    await held.step("at the time it named, its poll asks again at once", async () => held.fire()),
  );
  held.server.refresh.push(recorded.refresh_again);
  rateLimitedStory.push(
    await held.step("and sends that ask with no wait", async () => held.fireAsk(0)),
  );
  held.controller.dispose();

  // A reader walking past a stale page, holding Back or a key, spends no refresh on it.
  const walkedPast = createPage(runtime, { number: 7, tab: "", brief: true });
  walkedPast.clock.now = page.clock.now;
  walkedPast.server.pull = recorded.stale;
  steps.push(
    await walkedPast.step("a page walked past reads once", () => walkedPast.controller.start()),
  );
  steps.push(
    await walkedPast.step("and leaves before its ask, which is cancelled", async () =>
      walkedPast.controller.dispose(),
    ),
  );
  assert(walkedPast.timersLeft() === 0, "a disposed page left a timer running");

  // A page whose refresh failed a moment ago: its own request is not due, and it asks again
  // once a freshness window has passed while it is still stale, not on every poll and not on
  // every return to the tab. A reader's press still goes through.
  const failing = createPage(runtime, { number: 8, tab: "", brief: true });
  /** Printed with the second part, as `leftOpen` is. */
  const failingStory = [];
  failing.clock.now = Date.parse("2026-09-17T12:30:30Z");
  failing.server.pull = recorded.failed;
  failing.server.refresh.push(recorded.not_due);
  await failing.controller.start();
  failingStory.push(
    await failing.step("a stale page asks once, and its refresh is not due", async () =>
      failing.fireAsk(),
    ),
  );
  failingStory.push(await failing.step("its next poll asks nothing", async () => failing.fire()));
  failing.setVisible(false);
  await failing.controller.onVisibilityChange();
  failing.setVisible(true);
  failingStory.push(
    await failing.step("shown again within the window, it asks nothing", async () =>
      failing.controller.onVisibilityChange(),
    ),
  );
  failing.clock.now += 60_000;
  failingStory.push(
    await failing.step("a window later and still stale, its poll asks again at once", async () =>
      failing.fire(),
    ),
  );
  failing.server.refresh.push(recorded.not_due);
  failingStory.push(
    await failing.step("that ask is sent with no wait, and is not due", async () =>
      failing.fireAsk(0),
    ),
  );
  failing.server.refresh.push(recorded.failed_again);
  failingStory.push(
    await failing.step("a reader's Refresh is always taken", () =>
      failing.controller.requestRefresh(),
    ),
  );

  // Served an older head of this pull request when a refresh found a newer one: the server
  // followed the head, as it follows a branch, so the page is on it and offers nothing.
  const followed = createPage(runtime, { number: 7, tab: "", brief: true });
  followed.clock.now = Date.parse("2026-09-17T12:41:30Z");
  followed.server.pull = recorded.followed_head;
  steps.push(
    await followed.step("the served head followed the pull request, and nothing is offered", () =>
      followed.controller.start(),
    ),
  );
  followed.controller.dispose();

  // A previous failed attempt leaves a manual Fetch. Reopening or showing the page
  // does not keep retrying, and a refused manual request explains why it stopped.
  const absent = createPage(runtime, { number: 14, tab: "", brief: true });
  absent.clock.now = failing.clock.now;
  absent.server.pull = {
    ...recorded.absent_14,
    body: {
      ...recorded.absent_14.body,
      last_refresh: recorded.failed.body.last_refresh,
    },
  };
  steps.push(
    await absent.step("a cold page with an earlier failure leaves Fetch available", () =>
      absent.controller.start(),
    ),
  );
  steps.push(await absent.step("polling it asks for no fetch", async () => absent.fire()));
  absent.setVisible(false);
  await absent.controller.onVisibilityChange();
  absent.setVisible(true);
  steps.push(
    await absent.step("nor does showing it again", async () =>
      absent.controller.onVisibilityChange(),
    ),
  );
  assert(absent.timersLeft() === 1, "an earlier failure leaves only the normal poll");
  absent.server.refresh.push(recorded.too_many);
  steps.push(
    await absent.step("a press past the bound is refused and says why", () =>
      absent.controller.requestRefresh(),
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

  unknownTab.controller.dispose();

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

  // A server with no GitHub repository offers nothing to fetch.
  const notGithub = runtime.describePull(recorded.not_github.body, {
    number: 7,
    tab: "",
    nowMs: page.clock.now,
  });

  // The links a rendered text keeps.
  const base = record.pull.html_url;
  const links = [
    "docs/new.md",
    "https://example.com/a",
    "javascript:alert(1)",
    "data:text/html,x",
    "//evil.example/x",
  ].map((href) => ({ href, followed: runtime.safeLink(href, base) }));

  // Where each check's action goes, decided in the model: a GitHub Actions run, another
  // github.com page and a check's own site each say where they open, an address a page
  // may not follow has no action, and only an Actions link stands in for the app's name.
  const variedChecks = structuredClone(recorded.current.body);
  const passed = { kind: "run", bucket: "pass", status: "COMPLETED", conclusion: "SUCCESS" };
  variedChecks.checks.items.push(
    {
      ...passed,
      name: "coverage",
      details_url: "https://github.com/octo/demo/runs/123",
      app: "Codecov",
    },
    { ...passed, name: "lint", details_url: "https://ci.example/runs/2", app: "GitHub Actions" },
    { ...passed, name: "gist", details_url: "https://gist.github.com/octo/abc", app: "Gist bot" },
    {
      ...passed,
      name: "proxied",
      details_url: "https://github.com:8443/octo/demo/actions/runs/9",
      app: "Proxy",
    },
    {
      ...passed,
      name: "credentialed",
      details_url: "https://bot@github.com/octo/demo/runs/5",
      app: "Bot",
    },
    {
      kind: "status",
      bucket: "pass",
      conclusion: "SUCCESS",
      name: "legacy-ci",
      description: "Passed",
      details_url: "ftp://ci.example/7",
    },
  );
  const checkActions = runtime
    .describePull(variedChecks, { number: 7, tab: "checks", nowMs: page.clock.now })
    .checks.items.map(({ name, detail, action }) => ({ name, detail, action }));

  // The page's own defense, played on what KPress alone made of the hostile comment: the
  // nodes rebuilt from the template the page parses it into.
  const inert = serialize(
    inertHtml.sanitizeNodes(templateNodes(kpressTree.tree), pageDocument, base),
  );

  // Changes follows the pull request: a record whose comparison moved replaces the diff
  // shown, and the reader who went back to the earlier one is offered the newer instead.
  // The earlier diff here compared the base with the pin served before the switch.
  const comparison = recorded.current.body.record.comparison;
  const recordComparison = { left: comparison.base, right: comparison.head };
  const openedOnPin = { left: comparison.base, right: recorded.current.body.pin };
  const files = [
    ["nothing open yet", null, recordComparison],
    ["open on the record's comparison", recordComparison, recordComparison],
    ["open on an older head", openedOnPin, recordComparison],
    ["open on an older head the reader went back to", openedOnPin, recordComparison, true],
    ["no comparison in the record", recordComparison, null],
  ].map(
    ([when, mounted, next, chosen]) => `${when}: ${runtime.filesAction(mounted, next, chosen)}`,
  );
  // What Changes says over a diff that replaced another, as the page paints `followedNote`:
  // a sentence that names no commit, and the way back. The diff it replaced is the one shown before, on this page
  // or as the history entry remembers it across the reload a followed pin makes.
  const commit = (oid) => window.metabrowser.shortCommit(oid);
  const noted = (last, from, next) => {
    const earlier = runtime.followedFrom(last, from, next);
    const note = runtime.followedNote(earlier, next);
    if (note === null) {
      return "no note";
    }
    const said =
      note.kind === "head"
        ? "Changes now show this pull request’s newer commits."
        : "The comparison has changed.";
    return `${said} [Show the earlier changes] -> ${commit(earlier.left)}...${commit(earlier.right)}`;
  };
  const laterHead = { left: comparison.base, right: "c".repeat(40) };
  const otherBase = { left: "b".repeat(40), right: comparison.head };
  const entry = (state) => runtime.rememberedChanges(JSON.parse(JSON.stringify(state)));
  const reloaded = entry({ shown: { ...openedOnPin, route: "/r", junk: 1 }, from: null });
  assert(
    JSON.stringify(reloaded.shown) === JSON.stringify({ ...openedOnPin, route: "/r" }),
    "an entry's memory kept something other than the comparison's commits and routes",
  );
  const kept = entry({ shown: recordComparison, from: openedOnPin });
  for (const junk of [null, "nonsense", {}, { shown: { left: 1, right: "a" } }]) {
    assert(runtime.rememberedChanges(junk) === null, `not a memory: ${JSON.stringify(junk)}`);
  }
  assert(entry({ shown: recordComparison, from: "x" }).from === null, "a from that is none");
  // The reader's choice of the earlier diff is in the entry too, so the reload each later
  // push makes keeps it (A5 of review A on #745): only `true` is a choice, and a record that
  // names the remembered commits again has nothing earlier to show.
  const choice = entry({ shown: openedOnPin, from: null, chosen: true });
  assert(
    choice.chosen === true &&
      entry({ shown: openedOnPin, from: null, chosen: "yes" }).chosen === false &&
      entry({ shown: openedOnPin, from: null }).chosen === false,
    "an entry's choice is true or none",
  );
  assert(
    runtime.chosenEarlier(choice, recordComparison) === choice.shown &&
      runtime.chosenEarlier(choice, openedOnPin) === null &&
      runtime.chosenEarlier({ ...choice, chosen: false }, recordComparison) === null &&
      runtime.chosenEarlier(null, recordComparison) === null,
    "a page loaded again shows the earlier diff its reader chose, and only that",
  );
  const changesFollowed = {
    "the first diff of a page": noted(null, null, recordComparison),
    "a newer head replaces the diff shown": noted(openedOnPin, null, recordComparison),
    "the same diff mounted again keeps its note": noted(
      recordComparison,
      openedOnPin,
      recordComparison,
    ),
    "a second head names the one before it": noted(recordComparison, openedOnPin, laterHead),
    "the same head from another base": noted(otherBase, null, recordComparison),
    "the page loaded again on the newer head, its entry remembering the earlier diff": noted(
      reloaded.shown,
      reloaded.from,
      recordComparison,
    ),
    "the page loaded again after it had followed": noted(kept.shown, kept.from, recordComparison),
    "an entry that last showed this diff and no other": noted(
      entry({ shown: recordComparison, from: null }).shown,
      null,
      recordComparison,
    ),
  };

  // What Files changed says instead, for a record whose comparison could not be made and
  // for one whose merge base the store's shallow history cannot settle. A record without a
  // store says it on Changes once the page's attempt to prepare one failed.
  const filesUnavailable = Object.fromEntries(
    [
      "fetch_failed",
      "no_merge_base",
      "base_uncertain",
      "commits_unavailable",
      "no_store",
      "comparison_timeout",
      "comparison_too_large",
    ].map((why) => {
      const answer = structuredClone(recorded.current.body);
      answer.record.comparison = null;
      answer.record.unavailable = { comparison: why };
      const model = runtime.describePull(answer, {
        number: 7,
        tab: "files",
        nowMs: page.clock.now,
        comparisonAttempted: true,
      });
      return [why, { files: model.filesUnavailable, notes: model.notes }];
    }),
  );

  // A checkout's page: the server has no pin and no store, so the record has no comparison,
  // there is no Browse code, and the page says only when the checkout's HEAD is the pull
  // request's head. Its review comments name their files as text, since nothing is served
  // at the pull request's commits. Its Changes is read after a failed attempt.
  const onCheckout = structuredClone(recorded.current.body);
  onCheckout.pin = null;
  onCheckout.pin_ref = null;
  onCheckout.comparison_route = null;
  onCheckout.record.comparison = null;
  onCheckout.record.unavailable = { comparison: "no_store" };
  const head = onCheckout.record.pull.head.sha;
  const checkout = Object.fromEntries(
    [
      ["HEAD is the pull request's head", head],
      ["HEAD is elsewhere", "0".repeat(40)],
      ["no repository context", null],
    ].map(([when, checkoutHead]) => {
      const model = runtime.describePull(onCheckout, {
        number: 7,
        tab: "files",
        nowMs: page.clock.now,
        comparisonAttempted: true,
        checkoutHead,
      });
      return [
        when,
        {
          browse: browseCode(model),
          checkoutAtHead: model.checkoutAtHead,
          comparison: model.comparison,
          files: model.filesUnavailable,
        },
      ];
    }),
  );
  // On a mirror the same HEAD says nothing: the page has a pin, and Browse code.
  const onMirror = runtime.describePull(recorded.current.body, {
    number: 7,
    tab: "",
    nowMs: page.clock.now,
    checkoutHead: recorded.current.body.record.pull.head.sha,
  });
  checkout["a mirror's page, whatever it is handed"] = {
    browse: browseCode(onMirror),
    checkoutAtHead: onMirror.checkoutAtHead,
  };
  const pinnedCheckoutPage = { number: 7, tab: "files", nowMs: page.clock.now, checkoutPin: true };
  const pinnedCheckout = structuredClone(recorded.current.body);
  pinnedCheckout.pin_ref = "refs/heads/topic";
  pinnedCheckout.pin = pinnedCheckout.record.pull.base.sha;
  const otherPin = runtime.describePull(pinnedCheckout, pinnedCheckoutPage);
  assert(
    otherPin.browse === null && otherPin.comparison?.branch === null,
    "an unrelated checkout pin offers no code or file switch",
  );
  pinnedCheckout.pin = head;
  const headPin = runtime.describePull(pinnedCheckout, pinnedCheckoutPage);
  assert(
    headPin.browse?.kind === "link" &&
      headPin.browse.at === head &&
      headPin.comparison?.branch?.ref === null,
    "a checkout already at the PR head keeps its direct code and file links",
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
    notGithub: {
      status: notGithub.status,
      message: notGithub.message,
      canRefresh: notGithub.canRefresh,
    },
    links,
    wire: runtime.gitPathWire("src/app.txt"),
    pageDefense: inert,
    filesChanged: files,
    changesFollowed,
  };
  // Which address is the page's entry on a tab, for a tab switch from beside the page and for
  // writing a reader's place: a changed file's address is its Files changed too.
  const pageRoutes = [
    ["/pull/7", 7, ""],
    ["/pull/7/", 7, ""],
    ["/pull/7/files", 7, "files"],
    ["/pull/7/files/src/app.py", 7, "files"],
    ["/pull/7/files/src/app.py", 7, ""],
    ["/pull/7/checks", 7, "checks"],
    ["/pull/7/checks", 7, ""],
    ["/pull/7/checks/src/app.py", 7, "checks"],
    ["/pull/7/docs", 7, "docs"],
    ["/pull/7/docs", 7, ""],
    ["/pull/7/docs/README.md", 7, "docs"],
    ["/pull/70/files", 7, "files"],
    ["/pull/7/filesx", 7, "files"],
    ["/pull/8/files/src/app.py", 7, "files"],
  ].map(
    ([pathname, number, tab]) =>
      `${pathname} is #${number}'s ${tab || "conversation"}: ${runtime.onPageRoute(pathname, number, tab)}`,
  );
  // Docs and Changes both draw the diff, and own its fetch; Docs says so when its group
  // holds no changed file.
  const diffTabs = runtime.TABS.map((tab) => `${tab || "the front page"}: ${runtime.diffTab(tab)}`);
  const docsEmpty = [
    ["no changed document", { manifest: { files: [] } }],
    ["one changed document", { manifest: { files: [{ id: "f1" }] } }],
    ["no manifest", {}],
  ].map(([when, document_]) => `${when}: ${runtime.noFiles(document_)}`);
  // Docs is offered where the comparison's File type counts (`view=types`) say a document
  // changed; a list cut short that counts none, or an answer without the row, does not say.
  const docsOffered = [
    ["two documents", { type_presets: [["docs", 2, 0]], truncated: false }],
    [
      "no document",
      {
        type_presets: [
          ["code", 3, 0],
          ["docs", 0, 0],
        ],
        truncated: false,
      },
    ],
    ["no document listed of a cut-short list", { type_presets: [["docs", 0, 0]], truncated: true }],
    ["no docs row", { type_presets: [["code", 3, 0]], truncated: false }],
    ["no counts", null],
  ].map(([when, counts]) => `${when}: ${runtime.changesDocuments(counts)}`);
  const second = {
    leftOpen: leftOpenStory,
    probing: probingStory,
    failing: failingStory,
    rateLimited: rateLimitedStory,
    checkActions,
    filesUnavailable,
    checkout,
    hunks,
    place: placeStory(runtime),
    pageRoutes,
    diffTabs,
    docsEmpty,
    docsOffered,
  };
  const part = process.argv.indexOf("--part");
  const wanted = part === -1 ? "1" : process.argv[part + 1];
  const chosen = wanted === "all" ? { ...first, ...second } : wanted === "2" ? second : first;
  console.log(JSON.stringify(chosen, null, 2));
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});

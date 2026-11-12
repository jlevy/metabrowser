// The conversation's description is final at its first paint: the exact production page
// holds that paint for the Markdown it asked for, within its bound, and a revisit, or a
// refreshed record with the same text, paints the render an earlier page kept. Layout is
// not measured here; what is pinned is that plain text never paints first when Markdown
// can, and that a section above a change keeps its node.
const assert = require("node:assert/strict");
const path = require("node:path");
const { pathToFileURL } = require("node:url");
const { Element, recorded, root, settle, perf } = require("./github-pull-page-mount-behavior.js");
const { refHelpers } = require("./sdk-ref-fixture.js");

const pagePath = path.join(root, "src/metabrowser/builtin_plugins/github/pull-page.js");

function envelope(revision, text) {
  const body = structuredClone(recorded.current.body);
  body.record_revision = revision;
  body.record.pull.body = text;
  body.record.issue_comments = [];
  body.record.reviews = [];
  body.record.review_comments = [];
  body.record.comparison = null;
  body.record.unavailable.comparison = "no_store";
  return body;
}

function host() {
  const timers = new Map();
  const markdown = [];
  /** Markdown answers the session releases; none is held unless asked. */
  const held = [];
  let holdMarkdown = false;
  let current = null;
  globalThis.document = {
    visibilityState: "visible",
    addEventListener() {},
    removeEventListener() {},
    createElement: (tag) => new Element(tag),
    importNode: () => new Element("svg"),
  };
  globalThis.window = {
    location: { pathname: "/pull/7" },
    setTimeout(callback, delay) {
      const id = Symbol();
      timers.set(id, { callback, delay });
      return id;
    },
    clearTimeout: (id) => timers.delete(id),
    MetabrowserInertHtml: {
      sanitizeHtml: (html) => html,
      kpressProse(html) {
        const node = document.createElement("p");
        node.textContent = html;
        return node;
      },
    },
  };
  globalThis.DOMParser = class {
    parseFromString() {
      return { body: { firstElementChild: null } };
    }
  };
  const response = (body, status = 200) => ({
    status,
    headers: { get: () => null },
    json: async () => body,
  });
  globalThis.fetch = async (route) => {
    if (route.startsWith("/api/plugin/github/pull-markdown?")) {
      markdown.push(new URL(route, "http://localhost").searchParams.get("part"));
      const answer = response({
        record_revision: current.record_revision,
        fetched_at: current.fetched_at,
        html: `rendered ${current.record.pull.body}`,
        assets: {},
      });
      if (holdMarkdown) {
        return new Promise((resolve) => held.push(() => resolve(answer)));
      }
      return answer;
    }
    if (route.startsWith("/api/plugin/github/pull?")) {
      return response(current);
    }
    return { status: 404, headers: { get: () => null }, json: async () => ({}) };
  };
  return {
    timers,
    markdown,
    held,
    set current(value) {
      current = value;
    },
    holdMarkdown(on) {
      holdMarkdown = on;
    },
    mount(page, initial, how = {}) {
      const container = how.container ?? new Element("main");
      if (how.pane !== undefined) {
        // The pane the page scrolls in, which the shell marks.
        container.closest = () => how.pane;
      }
      let ready = false;
      const handle = page.mountPullPage(
        container,
        {
          number: 7,
          tab: "",
          // A direct landing has no reader: the page reads the record itself.
          reader:
            initial === null ? null : { initial: { etag: null, body: initial }, fetchAfterMs: 0 },
        },
        {
          perf: how.perf ?? perf,
          ensureAsset: async () => {},
          loadKpressAssets: async () => {},
          ...refHelpers(document),
          formatAge: how.formatAge ?? (() => ({ label: "now", className: "age" })),
          formatTimestamp: () => "now",
          navigation: { href: () => "/view/" },
          sourceKind: () => "git_revision",
          icons: { toggle: "" },
        },
      );
      handle.ready.then(() => {
        ready = true;
      });
      const body = () => container.querySelector(".github-pull-body");
      const description = () =>
        [...container.descendants()].find((node) => node.getAttribute("data-part") === "body");
      return {
        handle,
        body,
        description,
        ready: () => ready,
        plain: () => description()?.querySelector(":scope > .github-pull-plain") ?? null,
        rendered: () => description()?.querySelector(":scope > .metabrowser-kpress-host") ?? null,
        // Laid out out of sight while its first paint waits.
        holding: () => body().classes.has("github-pull-body-holding"),
        texts: () =>
          [...container.descendants()].filter((node) => node.getAttribute("data-part") !== null),
      };
    },
    async poll() {
      const due = [...timers].filter(([, timer]) => timer.delay === 1000 || timer.delay === 30000);
      for (const [id, timer] of due) {
        timers.delete(id);
        timer.callback();
      }
      await settle();
    },
  };
}

async function run() {
  const page = await import(pathToFileURL(pagePath).href);
  const facts = {};
  const first = envelope("a".repeat(64), "first text");
  const session = host();
  session.current = first;

  // A first visit: the body is out of sight until the description's Markdown can show.
  session.holdMarkdown(true);
  const visit = session.mount(page, first);
  await settle();
  assert.equal(visit.holding(), true, "no plain description shows while held");
  assert.equal(visit.ready(), false, "a held page is not ready, so the page it replaces stays");
  assert.deepEqual(session.markdown, ["body"], "the description is asked for at once");
  session.holdMarkdown(false);
  session.held.shift()();
  await settle();
  assert.equal(visit.plain(), null, "the first paint is the Markdown");
  assert.equal(visit.rendered()?.textContent, "rendered first text");
  assert.equal(visit.holding(), false);
  assert.equal(visit.ready(), true);
  assert.equal(
    [...session.timers.values()].some((timer) => timer.delay === page.DESCRIPTION_HOLD_MS),
    false,
    "a hold met clears its bound",
  );
  facts.firstVisit = "held, then final";

  // A refreshed record with the same text keeps the description's node, rendered.
  const kept = visit.description();
  session.current = envelope("b".repeat(64), "first text");
  await session.poll();
  assert.equal(visit.description(), kept, "the description above any change stays put");
  assert.equal(visit.plain(), null);
  assert.deepEqual(session.markdown, ["body"], "its same text is not asked for again");
  visit.handle.dispose();
  facts.refreshedSameText = "kept";

  // A revisit, another page of the same document: final at once, with nothing asked.
  session.current = first;
  // It waits for nothing, commits included: the mount's own task paints it final.
  const revisit = session.mount(page, first);
  assert.equal(revisit.plain(), null, "a revisit never paints plain text");
  assert.equal(revisit.rendered()?.textContent, "rendered first text", "final in the mount's task");
  assert.equal(
    [...session.timers.values()].some((timer) => timer.delay === page.DESCRIPTION_HOLD_MS),
    false,
    "a kept render holds nothing",
  );
  await settle();
  assert.equal(revisit.plain(), null);
  assert.equal(revisit.ready(), true);
  assert.deepEqual(session.markdown, ["body"], "a revisit asks for no Markdown");
  revisit.handle.dispose();
  facts.revisit = "final at first paint";

  // A text never rendered, whose Markdown does not come in time: plain once the bound passes.
  const slow = envelope("c".repeat(64), "slow text");
  session.current = slow;
  session.holdMarkdown(true);
  const late = session.mount(page, slow);
  await settle();
  assert.equal(late.holding(), true);
  const [bound] = [...session.timers].filter(
    ([, timer]) => timer.delay === page.DESCRIPTION_HOLD_MS,
  );
  session.timers.delete(bound[0]);
  bound[1].callback();
  await settle();
  assert.equal(late.plain()?.textContent, "slow text", "past the bound the text paints plain");
  assert.equal(late.holding(), false);
  assert.equal(late.ready(), true);
  session.holdMarkdown(false);
  session.held.shift()();
  await settle();
  assert.equal(late.rendered()?.textContent, "rendered slow text", "and its Markdown follows");
  late.handle.dispose();
  facts.pastTheBound = "plain, then Markdown";

  // Comments and reviews the first screen shows wait with the description (review A6): at
  // the paint that makes the page ready every text is Markdown, none plain.
  const conversation = structuredClone(recorded.current.body);
  conversation.record_revision = "f".repeat(64);
  conversation.record.comparison = null;
  conversation.record.unavailable.comparison = "no_store";
  session.current = conversation;
  session.holdMarkdown(true);
  const askedBefore = session.markdown.length;
  const discussed = session.mount(page, conversation);
  await settle();
  const atHold = discussed.texts().length;
  assert.ok(atHold > 1, "the recorded conversation has texts beside its description");
  assert.equal(discussed.holding(), true);
  const plainShown = () =>
    discussed.texts().filter((node) => node.querySelector(":scope > .github-pull-plain") !== null)
      .length;
  /** How many texts were plain when the page first became ready. @type {number | null} */
  let plainAtReady = null;
  while (session.held.length > 0) {
    session.held.shift()();
    await settle();
    if (discussed.ready() && plainAtReady === null) {
      plainAtReady = plainShown();
    }
  }
  session.holdMarkdown(false);
  await settle();
  assert.equal(discussed.ready(), true);
  assert.equal(plainAtReady, 0, "no text the first screen shows is plain at ready");
  assert.equal(discussed.holding(), false);
  facts.comments = { texts: atHold, asked: session.markdown.length - askedBefore, plainAtReady };
  discussed.handle.dispose();

  // Each hold says how long it held and why it ended (review B1): met when its texts came,
  // bound when its time ran out.
  {
    /** @type {{label: string, meta: Record<string, any>}[]} */
    const spans = [];
    const recording = {
      measure(label, work, meta) {
        spans.push({ label, meta });
        return work();
      },
      measureAsync: async (_label, work) => work(),
    };
    const met = envelope("1".repeat(64), "met text");
    session.current = met;
    session.holdMarkdown(true);
    const metPage = session.mount(page, met, { perf: recording });
    await settle();
    session.held.shift()();
    await settle();
    metPage.handle.dispose();
    const bounded = envelope("2".repeat(64), "bounded text");
    session.current = bounded;
    const boundPage = session.mount(page, bounded, { perf: recording });
    await settle();
    const [bound] = [...session.timers].filter(
      ([, timer]) => timer.delay === page.DESCRIPTION_HOLD_MS,
    );
    session.timers.delete(bound[0]);
    bound[1].callback();
    await settle();
    session.holdMarkdown(false);
    session.held.shift()();
    await settle();
    boundPage.handle.dispose();
    facts.holdSpans = spans
      .filter((span) => span.label === "githubPull:firstPaintHold")
      .map((span) => `${span.meta.mode} ${span.meta.outcome} ${span.meta.parts}`);
  }

  // A direct landing paints the loading blocks, and its held first paint replaces them with
  // the conversation laid out out of sight (review B5): no loading block shows while it waits.
  {
    const landed = envelope("3".repeat(64), "landing text");
    session.current = landed;
    session.holdMarkdown(true);
    const landing = session.mount(page, null);
    const blocks = () =>
      [...landing.body().descendants()].some((node) => node.classes.has("github-pull-loading"));
    const before = blocks();
    await settle();
    const whileHeld = { holding: landing.holding(), blocks: blocks() };
    session.holdMarkdown(false);
    session.held.shift()();
    await settle();
    facts.landing = { blocksBefore: before, whileHeld, final: landing.plain() === null };
    landing.handle.dispose();
  }

  // A landing whose loading blocks have shown when the record comes: they stay over the held
  // conversation, the same blocks, until it shows, so the body never blinks empty between
  // them (review C2). Blocks not shown yet go at once, as in the landing above.
  {
    const landed = envelope("6".repeat(64), "late landing text");
    session.current = landed;
    session.holdMarkdown(true);
    // The loading blocks' reveal has run: the browser reports them visible.
    window.getComputedStyle = (element) => ({
      visibility: element.classes.has("mb-delayed-loading") ? "visible" : "hidden",
    });
    const landing = session.mount(page, null);
    const blocks = () =>
      [...landing.body().children].find((node) => node.classes?.has("mb-delayed-loading")) ?? null;
    const before = blocks();
    await settle();
    const whileHeld = {
      holding: landing.holding(),
      sameBlocks: before !== null && blocks() === before,
      cover: blocks()?.classes.has("github-pull-loading-cover") ?? false,
    };
    assert.ok(whileHeld.sameBlocks, "the blocks that showed stay, the same node, while held");
    session.holdMarkdown(false);
    session.held.shift()();
    await settle();
    facts.landingAfterBlocksShowed = {
      whileHeld,
      shown: {
        blocks: blocks() !== null,
        holding: landing.holding(),
        final: landing.plain() === null,
      },
    };
    landing.handle.dispose();
    delete window.getComputedStyle;
  }

  // A page replaced while its first paint is held keeps what it holds out of sight: it stays
  // as the page replacing it found it until that one is ready, and never shows plain text
  // (review C7).
  {
    const replaced = envelope("7".repeat(64), "replaced text");
    session.current = replaced;
    session.holdMarkdown(true);
    const going = session.mount(page, replaced);
    await settle();
    going.handle.cancelPending();
    assert.equal(going.holding(), true, "a cancelled held page stays out of sight");
    facts.cancelledWhileHeld = { holding: going.holding() };
    session.holdMarkdown(false);
    session.held.shift()();
    await settle();
    going.handle.dispose();
  }

  // The first screen in a browser, where an observer reports texts as they near the pane:
  // the page is laid out by a stub, each text 400 px tall plain and 200 rendered, so a text
  // that renders moves those below it up. The page that it replaces is at its top, or
  // scrolled past the whole conversation, as a reader who read one conversation and clicks the
  // next is. Either way the first screen is the new page's own: no text on it is plain when
  // the page is ready, those that come into it as the texts above render included (review C1).
  facts.firstScreen = {};
  for (const scrolled of [0, 5000]) {
    const PANE = 700;
    const threaded = envelope(`${scrolled}`.padStart(64, "8"), `threaded text ${scrolled}`);
    const comment = recorded.current.body.record.issue_comments[0];
    threaded.record.issue_comments = Array.from({ length: 10 }, (_, at) => ({
      ...comment,
      id: 100 + at,
      timeline_id: String(100 + at),
      body: `comment ${at} of ${scrolled}`,
    }));
    const container = new Element("main");
    const layout = (node) => {
      const top = -scrolled;
      if (node === container) {
        return { top, bottom: top + 6000, width: 800, height: 6000 };
      }
      let y = top + 100;
      for (const text of container.descendants()) {
        if (text.getAttribute("data-part") === null) {
          continue;
        }
        const height = text.querySelector(":scope > .github-pull-plain") === null ? 200 : 400;
        if (text === node) {
          return { top: y, bottom: y + height, width: 800, height };
        }
        y += height + 50;
      }
      return { top: 0, bottom: 0, width: 0, height: 0 };
    };
    const observers = [];
    globalThis.IntersectionObserver = class {
      constructor(callback) {
        this.callback = callback;
        this.observed = new Set();
        observers.push(this);
      }
      observe(element) {
        this.observed.add(element);
      }
      unobserve(element) {
        this.observed.delete(element);
      }
      disconnect() {
        this.observed.clear();
      }
      // What a browser reports for what it watches: within a pane's height of the pane.
      deliver() {
        const entries = [...this.observed].map((target) => {
          const box = target.getBoundingClientRect();
          return {
            target,
            boundingClientRect: box,
            isIntersecting: box.bottom > -PANE && box.top < 2 * PANE,
          };
        });
        if (entries.length > 0) {
          this.callback(entries);
        }
      }
    };
    Element.prototype.getBoundingClientRect = function () {
      return layout(this);
    };
    const spans = [];
    const recording = {
      measure(label, work, meta) {
        spans.push({ label, meta });
        return work();
      },
      measureAsync: async (_label, work) => work(),
    };
    const pane = { clientHeight: PANE, getBoundingClientRect: () => ({ top: 0, bottom: PANE }) };
    session.current = threaded;
    session.holdMarkdown(true);
    const screened = session.mount(page, threaded, { container, pane, perf: recording });
    const deliver = () => {
      for (const observer of observers) {
        observer.deliver();
      }
    };
    await settle();
    deliver();
    await settle();
    /** The plain texts on the page's first screen, from its own top. */
    const plainOnFirstScreen = () =>
      screened
        .texts()
        .filter(
          (text) =>
            text.querySelector(":scope > .github-pull-plain") !== null &&
            layout(text).top - layout(container).top < PANE,
        )
        .map((text) => text.getAttribute("data-part"));
    let atReady = null;
    while (session.held.length > 0 && atReady === null) {
      session.held.shift()();
      await settle();
      deliver();
      await settle();
      if (screened.ready()) {
        atReady = plainOnFirstScreen();
      }
    }
    session.holdMarkdown(false);
    while (session.held.length > 0) {
      session.held.shift()();
    }
    await settle();
    assert.deepEqual(atReady, [], "no text on the page's first screen is plain when it is ready");
    const hold = spans.find((span) => span.label === "githubPull:firstPaintHold")?.meta;
    facts.firstScreen[scrolled] = {
      plainOnFirstScreenAtReady: atReady,
      waitedFor: hold?.parts ?? null,
      outcome: hold?.outcome ?? null,
    };
    screened.handle.dispose();
    delete Element.prototype.getBoundingClientRect;
    delete globalThis.IntersectionObserver;
  }

  // A kept section tells its ages again at every paint (review A5): three hours after two
  // comments were painted, a refresh that adds a third reads all three as of now.
  {
    let clock = Date.parse("2026-09-17T12:00:00Z");
    const minutesAgo = (seconds) => ({
      label: `${Math.round((clock - seconds * 1000) / 60_000)} min`,
      className: "age",
    });
    const comment = recorded.current.body.record.issue_comments[0];
    const at = (minutes) => new Date(clock - minutes * 60_000).toISOString().replace(".000Z", "Z");
    const aged = envelope("4".repeat(64), "aged text");
    aged.record.issue_comments = [
      { ...comment, id: 11, timeline_id: "11", created_at: at(6), body: "six" },
      { ...comment, id: 12, timeline_id: "12", created_at: at(5), body: "five" },
    ];
    session.current = aged;
    const agedPage = session.mount(page, aged, { formatAge: minutesAgo });
    await settle();
    clock += 180 * 60_000;
    const refreshed = structuredClone(aged);
    refreshed.record_revision = "5".repeat(64);
    refreshed.record.issue_comments.push({
      ...comment,
      id: 13,
      timeline_id: "13",
      created_at: at(4),
      body: "four",
    });
    session.current = refreshed;
    await session.poll();
    facts.ages = [...agedPage.body().descendants()]
      .filter((node) => node.classes.has("github-pull-age"))
      .map((node) => node.textContent)
      .slice(1);
    agedPage.handle.dispose();
  }

  // A stale cached record paints the state the repository's list already knows, when the
  // list saw a later update; an older list leaves the record's own.
  const states = await import(
    pathToFileURL(path.join(root, "src/metabrowser/builtin_plugins/github/pull-state.js")).href
  );
  const badge = async (listedAt) => {
    const cached = envelope("d".repeat(64), "first text");
    cached.state = "stale";
    Object.assign(cached.record.pull, {
      state: "open",
      merged: false,
      draft: false,
      updated_at: "2026-09-17T12:00:00Z",
    });
    states.noteListed(cached.source, [{ number: 7, state: "merged", updatedAt: listedAt }]);
    session.current = cached;
    const opened = session.mount(page, cached);
    // Read in the mount's own task: the first paint of the header.
    const container = opened.body().parentNode;
    const shown = [...container.descendants()].find((node) =>
      node.classes.has("github-pull-state"),
    );
    const text = shown?.textContent;
    await settle();
    opened.handle.dispose();
    return text;
  };
  facts.listedState = {
    newerList: await badge("2026-09-18T00:00:00Z"),
    olderList: await badge("2026-09-16T00:00:00Z"),
  };

  // Changes with rendered Markdown stays out of sight until its first screen settles, or
  // its bound passes, and is ready only then.
  const changes = async (settles) => {
    const files = envelope("e".repeat(64), "first text");
    files.record.comparison = { base: "1".repeat(40), head: "2".repeat(40) };
    files.rendered_route = "/api/plugin/github/pull-rendered-diff?number=7";
    session.current = files;
    window.location.pathname = "/pull/7/files";
    /** @type {() => void} */
    let settle_ = () => {};
    const firstScreen = new Promise((resolve) => {
      settle_ = resolve;
    });
    let asked = null;
    let holdingAtJump = null;
    const container = new Element("main");
    const handle = page.mountPullPage(
      container,
      {
        number: 7,
        tab: "files",
        reader: { initial: { etag: null, body: files }, fetchAfterMs: 0 },
      },
      {
        perf,
        ensureAsset: async () => {},
        ensureKindAssets: async () => {},
        getRegisteredView: () => ({
          render(host, ctx) {
            asked = ctx.markdownHoldMs;
            return {
              currentFile: () => null,
              firstScreen: () => firstScreen,
              fileForPath: (path) => ({ kind: "file", path }),
              // The file the address names is landed on before the wait (review B2), so the
              // first screen the Markdown layer reports is the one the reader lands on.
              scrollToFile(path) {
                holdingAtJump = host.classes.has("github-pull-diff-holding");
                return { kind: "jumped", path };
              },
              dispose() {},
            };
          },
        }),
        loadKpressAssets: async () => {},
        ...refHelpers(document),
        formatAge: () => ({ label: "now", className: "age" }),
        formatTimestamp: () => "now",
        navigation: { href: () => "/view/" },
        sourceKind: () => "git_revision",
        icons: { toggle: "" },
      },
    );
    handle.showFile("docs/new.md");
    let ready = false;
    void handle.whenFilesReady().then(() => {
      ready = true;
    });
    await settle();
    const host = [...container.descendants()].find((node) => node.classes.has("github-pull-diff"));
    const held = host.classes.has("github-pull-diff-holding");
    if (settles) {
      settle_();
    } else {
      const [bound] = [...session.timers].filter(
        ([, timer]) => timer.delay === page.CHANGES_FIRST_SCREEN_MS,
      );
      session.timers.delete(bound[0]);
      bound[1].callback();
    }
    const readyWhileHeld = ready;
    await settle();
    const shown = !host.classes.has("github-pull-diff-holding");
    handle.dispose();
    window.location.pathname = "/pull/7";
    return { asked, held, readyWhileHeld, shown, ready, holdingAtJump };
  };
  facts.changes = { settled: await changes(true), bound: await changes(false) };

  // The kept renders are bounded by count and by characters, the oldest dropped first, and
  // descriptions apart from the other parts, so a long conversation keeps them.
  const bounds = await import(`${pathToFileURL(pagePath).href}?bounds`);
  bounds.rememberRendered("s", 1, "body", "a description", { html: "d", assets: { kept: 1 } });
  for (let index = 0; index < bounds.RENDERED_PARTS + 10; index += 1) {
    bounds.rememberRendered("s", 1, `issue_comment/${index}`, `text ${index}`, { html: "x" });
  }
  assert.equal(bounds.renderedTextsHeld().parts.texts, bounds.RENDERED_PARTS);
  assert.equal(bounds.renderedText("s", 1, "issue_comment/0", "text 0"), null, "oldest dropped");
  assert.ok(bounds.renderedText("s", 1, "issue_comment/10", "text 10"));
  assert.deepEqual(
    bounds.renderedText("s", 1, "body", "a description"),
    { html: "d", assets: { kept: 1 } },
    "a description outlives a long conversation, with the one manifest kept beside it",
  );
  assert.equal(
    bounds.renderedText("s", 1, "issue_comment/10", "another text"),
    null,
    "a render serves only its own text",
  );
  // Several that together pass the characters' bound: the oldest go, the newest stay.
  const each = Math.floor(bounds.RENDERED_DESCRIPTION_CHARS / 4);
  for (let index = 0; index < 6; index += 1) {
    bounds.rememberRendered("s", 2 + index, "body", `big ${index}`, { html: "y".repeat(each) });
  }
  const held = bounds.renderedTextsHeld().descriptions;
  assert.ok(held.chars <= bounds.RENDERED_DESCRIPTION_CHARS);
  assert.equal(bounds.renderedText("s", 2, "body", "big 0"), null, "the oldest went");
  assert.ok(bounds.renderedText("s", 7, "body", "big 5"), "the newest stayed");
  assert.equal(held.texts, 3, "three of a quarter each fit beside their texts");
  facts.bounded = true;
  return facts;
}

run()
  .then((result) => process.stdout.write(`${JSON.stringify(result, null, 2)}\n`))
  .catch((error) => {
    process.stderr.write(`${error.stack}\n`);
    process.exitCode = 1;
  });

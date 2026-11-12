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
    mount(page, initial) {
      const container = new Element("main");
      let ready = false;
      const handle = page.mountPullPage(
        container,
        { number: 7, tab: "", reader: { initial: { etag: null, body: initial }, fetchAfterMs: 0 } },
        {
          perf,
          ensureAsset: async () => {},
          loadKpressAssets: async () => {},
          ...refHelpers(document),
          formatAge: () => ({ label: "now", className: "age" }),
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

  // A first visit: nothing paints in the body until the description's Markdown can.
  session.holdMarkdown(true);
  const visit = session.mount(page, first);
  await settle();
  assert.equal(visit.description(), undefined, "no plain description paints while held");
  assert.equal(visit.ready(), false, "a held page is not ready, so the page it replaces stays");
  assert.deepEqual(session.markdown, ["body"], "the description is asked for at once");
  session.holdMarkdown(false);
  session.held.shift()();
  await settle();
  assert.equal(visit.plain(), null, "the first paint is the Markdown");
  assert.equal(visit.rendered()?.textContent, "rendered first text");
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
  // It still waits for the commits the server holds, a local read, before it paints.
  const revisit = session.mount(page, first);
  assert.equal(revisit.plain(), null, "a revisit never paints plain text");
  await settle();
  assert.equal(revisit.plain(), null);
  assert.equal(revisit.rendered()?.textContent, "rendered first text");
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
  assert.equal(late.description(), undefined);
  const [bound] = [...session.timers].filter(
    ([, timer]) => timer.delay === page.DESCRIPTION_HOLD_MS,
  );
  session.timers.delete(bound[0]);
  bound[1].callback();
  await settle();
  assert.equal(late.plain()?.textContent, "slow text", "past the bound the text paints plain");
  assert.equal(late.ready(), true);
  session.holdMarkdown(false);
  session.held.shift()();
  await settle();
  assert.equal(late.rendered()?.textContent, "rendered slow text", "and its Markdown follows");
  late.handle.dispose();
  facts.pastTheBound = "plain, then Markdown";

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
          render(_host, ctx) {
            asked = ctx.markdownHoldMs;
            return { currentFile: () => null, firstScreen: () => firstScreen, dispose() {} };
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
    return { asked, held, readyWhileHeld, shown, ready };
  };
  facts.changes = { settled: await changes(true), bound: await changes(false) };

  // The kept renders are bounded by count and by characters, the oldest dropped first.
  const bounds = await import(`${pathToFileURL(pagePath).href}?bounds`);
  for (let index = 0; index < bounds.RENDERED_TEXTS + 10; index += 1) {
    bounds.rememberRendered("s", 1, `issue_comment/${index}`, `text ${index}`, { html: "x" });
  }
  assert.equal(bounds.renderedTextsHeld().texts, bounds.RENDERED_TEXTS);
  assert.equal(bounds.renderedText("s", 1, "issue_comment/0", "text 0"), null, "oldest dropped");
  assert.ok(bounds.renderedText("s", 1, "issue_comment/10", "text 10"));
  assert.equal(
    bounds.renderedText("s", 1, "issue_comment/10", "another text"),
    null,
    "a render serves only its own text",
  );
  bounds.rememberRendered("s", 1, "body", "big", { html: "y".repeat(bounds.RENDERED_TEXT_CHARS) });
  assert.ok(bounds.renderedTextsHeld().chars <= bounds.RENDERED_TEXT_CHARS);
  facts.bounded = true;
  return facts;
}

run()
  .then((result) => process.stdout.write(`${JSON.stringify(result)}\n`))
  .catch((error) => {
    process.stderr.write(`${error.stack}\n`);
    process.exitCode = 1;
  });

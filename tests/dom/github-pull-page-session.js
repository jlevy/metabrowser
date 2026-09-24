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

const fs = require("node:fs");
const path = require("node:path");
const { pathToFileURL } = require("node:url");

const repoRoot = path.resolve(__dirname, "../..");
const recorded = JSON.parse(
  fs.readFileSync(path.join(repoRoot, "tests/fixtures/github-pull-page-responses.json"), "utf8"),
);
const pagePath = path.join(repoRoot, "src/metabrowser/builtin_plugins/github/pull-page.js");
// The allowlist the page passes a text's Markdown through, loaded whole as the shell
// loads it on demand.
const inertPath = path.join(repoRoot, "src/metabrowser/static/inert-html.js");
const inertContext = { window: {}, URL };
require("node:vm").runInNewContext(fs.readFileSync(inertPath, "utf8"), inertContext, {
  filename: inertPath,
});
const inertHtml = inertContext.window.MetabrowserInertHtml;

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
        : `${pull.title} #${pull.number} [${pull.stateLabel}] ${pull.author}: ${pull.base} <- ${pull.head}`,
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

  console.log(
    JSON.stringify(
      {
        steps,
        otherNumber: { status: other.status, message: other.message, served: other.served },
        links,
        wire: runtime.gitPathWire("src/app.txt"),
        pageDefense: inert,
        filesChanged: files,
      },
      null,
      2,
    ),
  );
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});

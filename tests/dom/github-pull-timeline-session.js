// A selected Conversation paints before its optional GitHub projection.
const assert = require("node:assert/strict");
const path = require("node:path");
const { pathToFileURL } = require("node:url");
const { Element, recorded, root, settle } = require("./github-pull-page-mount-behavior.js");
const { refHelpers } = require("./sdk-ref-fixture.js");

class TimelineElement extends Element {
  contains(node) {
    return node === this || [...this.descendants()].includes(node);
  }
  get previousElementSibling() {
    return this.parentNode?.children[this.parentNode.children.indexOf(this) - 1] ?? null;
  }
  get nextElementSibling() {
    return this.parentNode?.children[this.parentNode.children.indexOf(this) + 1] ?? null;
  }
  insertBefore(node, before) {
    // Browsers drop focus if an ancestor of the focused link is detached.
    if (node.parentNode !== null && node.contains(document.activeElement)) {
      document.activeElement = null;
    }
    node.remove();
    const at = before === null ? this.children.length : this.children.indexOf(before);
    assert.ok(at >= 0);
    this.children.splice(at, 0, node);
    node.parentNode = this;
  }
}

const firstRevision = "a".repeat(64);
const nextRevision = "b".repeat(64);
const firstCommit = "0123456789".repeat(4);
const lastCommit = "abcdef0123".repeat(4);
const wideId = "9007199254740993";
const timelineRoute = "/api/plugin/github/pull-timeline";

function fixture(state = "current") {
  const envelope = structuredClone(recorded.current.body);
  envelope.state = state;
  envelope.record_revision = firstRevision;
  envelope.comparison_route = null;
  const record = envelope.record;
  record.comparison = null;
  record.unavailable.comparison = "no_store";
  record.issue_comments[0].id = Number(wideId);
  record.issue_comments[0].timeline_id = wideId;
  record.reviews[0].id = Number(wideId);
  record.reviews[0].timeline_id = wideId;
  record.reviews[0].body = "review body";
  record.reviews.push({ ...record.reviews[1], id: 15, state: "PENDING", submitted_at: null });
  return envelope;
}

const response = (body, status = 200) => ({
  status,
  headers: { get: () => null },
  json: async () => body,
});

function mount(mountPullPage, envelope) {
  const frames = new Map();
  const timers = new Map();
  const marks = [];
  const timelines = [];
  const markdown = [];
  let current = envelope;
  let finishRefresh;
  globalThis.document = {
    visibilityState: "visible",
    activeElement: null,
    addEventListener() {},
    createElement: (tag) => new TimelineElement(tag),
    importNode: () => new TimelineElement("svg"),
  };
  globalThis.window = {
    location: { pathname: "/pull/7" },
    setTimeout(callback, delay) {
      const id = Symbol();
      timers.set(id, { callback, delay });
      return id;
    },
    clearTimeout: (id) => timers.delete(id),
    requestAnimationFrame(callback) {
      const id = Symbol();
      frames.set(id, callback);
      return id;
    },
    cancelAnimationFrame: (id) => frames.delete(id),
    MetabrowserInertHtml: {
      sanitizeHtml: (html) => html,
      kpressProse(html) {
        const link = document.createElement("a");
        link.setAttribute("href", "https://example.com/message");
        link.textContent = html;
        return link;
      },
    },
  };
  globalThis.DOMParser = class {
    parseFromString() {
      return { body: { firstElementChild: null } };
    }
  };
  globalThis.fetch = async (route, options) => {
    if (route === timelineRoute) {
      assert.equal(options.method, "POST");
      assert.equal(options.headers["content-type"], "application/json");
      const request = JSON.parse(options.body);
      marks.push("timeline request");
      return new Promise((finish) =>
        timelines.push({
          request,
          signal: options.signal,
          answer: (state, events, revision = request.record_revision, retryable = false) =>
            finish(
              response({
                state,
                events,
                record_revision: revision,
                ...(retryable ? { retryable } : {}),
              }),
            ),
        }),
      );
    }
    if (route === "/api/plugin/github/pull-refresh") {
      return new Promise((finish) => {
        finishRefresh = () => finish(response({ pull: current }, 202));
      });
    }
    if (route.startsWith("/api/plugin/github/pull-markdown?")) {
      const part = new URL(route, "http://localhost").searchParams.get("part");
      markdown.push(part);
      return response({ record_revision: current.record_revision, html: part, assets: {} });
    }
    if (route.startsWith("/api/plugin/github/stacks")) {
      return { status: 404, headers: { get: () => null } };
    }
    assert.equal(route, "/api/plugin/github/pull?number=7");
    return response(current);
  };
  const container = new TimelineElement("main");
  const handle = mountPullPage(
    container,
    { number: 7, tab: "", reader: { initial: { body: envelope }, fetchAfterMs: 0 } },
    {
      perf: {
        measure(label, work) {
          const result = work();
          marks.push(label);
          return result;
        },
        measureAsync: (_label, work) => work(),
      },
      ensureAsset: async () => {},
      loadKpressAssets: async () => {},
      ...refHelpers(document),
      formatAge: () => ({ label: "1d ago", className: "age" }),
      formatTimestamp: () => "Sep 16, 2026",
      navigation: { href: () => "/view/" },
      sourceKind: () => "filesystem",
      icons: { toggle: "" },
    },
  );
  return {
    handle,
    marks,
    markdown,
    timelines,
    body: () => container.querySelector(".github-pull-body"),
    frame() {
      const ready = [...frames.values()];
      frames.clear();
      for (const callback of ready) {
        callback();
      }
    },
    hasTimer(delay) {
      return [...timers.values()].some((timer) => timer.delay === delay);
    },
    timer(delay) {
      const found = [...timers].findLast(([, timer]) => timer.delay === delay);
      assert.ok(
        found,
        `no ${delay}ms timer among ${[...timers.values()].map((timer) => timer.delay)}`,
      );
      const [id, task] = found;
      timers.delete(id);
      task.callback();
    },
    replace(envelope) {
      current = envelope;
    },
    acknowledgeRefresh() {
      finishRefresh();
    },
  };
}

function order(body) {
  return body.children.map((node) => {
    if (node.classes.has("github-pull-commit")) {
      return node.querySelector(".github-pull-commit-subject").textContent;
    }
    const text = node.querySelector(":scope > .github-pull-text");
    if (text !== null) {
      return text.getAttribute("data-part");
    }
    return node.textContent;
  });
}

async function run() {
  const { mountPullPage, REFRESH_ASK_MS, FAST_POLL_MS, SLOW_POLL_MS, TIMELINE_RETRY_MS } =
    await import(
      pathToFileURL(path.join(root, "src/metabrowser/builtin_plugins/github/pull-page.js")).href
    );
  const session = mount(mountPullPage, fixture());
  await session.handle.ready;
  await settle();
  session.frame();
  assert.equal(session.timelines.length, 0, "staging never starts a timeline read");
  const body = session.body();
  const original = order(body);
  const description = body.children[0].querySelector(".metabrowser-kpress-host");
  const focus = body.children[1].querySelector("a[href]");
  assert.ok(description && focus);
  document.activeElement = focus;
  assert.ok(session.markdown.includes(`review/${wideId}`));
  assert.ok(session.markdown.includes(`issue_comment/${wideId}`));
  session.handle.activate();
  session.frame();
  assert.equal(session.timelines.length, 0, "the useful Conversation paints first");
  session.frame();
  const [first] = session.timelines;
  const spinner = body.querySelector(".github-pull-timeline-loading");
  assert.equal(spinner?.getAttribute("aria-label"), "Loading commits…");
  assert.ok(spinner?.classes.has("mb-delayed-loading") && spinner.querySelector(".spinner"));
  assert.deepEqual(first.request, { number: 7, record_revision: firstRevision });
  assert.ok(
    session.marks.indexOf("githubPull:conversationReady") <
      session.marks.indexOf("timeline request"),
  );
  const commit = {
    kind: "commit",
    oid: firstCommit,
    subject: "<img> First commit",
    committed_at: "2026-09-16T09:00:00Z",
  };
  first.answer("partial", [
    { kind: "review", id: "15" }, // A pending review stays with the unmatched discussion.
    { kind: "comment", id: wideId },
    commit,
    commit, // A page boundary can repeat an event.
    { kind: "comment", id: wideId },
    { kind: "review", id: wideId },
    { kind: "commit", oid: lastCommit, subject: "Last commit", committed_at: null },
    { kind: "commit", oid: "https://example.com/", subject: "Invalid ID" },
  ]);
  await settle();
  const interleaved = order(body);
  assert.equal(body.querySelector(".github-pull-timeline-loading"), null);
  assert.deepEqual(interleaved.slice(0, 8), [
    "body",
    `issue_comment/${wideId}`,
    "<img> First commit",
    `review/${wideId}`,
    "Last commit",
    "review/3279967139",
    "review/15",
    "Some commits may be missing.",
  ]);
  assert.equal(body.children[0].querySelector(".metabrowser-kpress-host"), description);
  assert.equal(body.children[3].querySelector("a[href]"), focus);
  assert.equal(document.activeElement, focus);
  assert.ok(body.children[2].textContent.includes("committed 1d ago"));
  assert.doesNotMatch(body.children[4].textContent, /committed/);
  const link = body.children[2].querySelector("a[href]");
  const destination = link.getAttribute("href");
  assert.equal(destination, `https://github.com/octo/demo/pull/7/commits/${firstCommit}`);
  assert.equal(link.textContent, firstCommit.slice(0, 7));
  assert.equal(link.getAttribute("target"), "_blank");
  assert.equal(link.getAttribute("rel"), "noopener noreferrer");
  assert.equal(link.children.at(0).getAttribute("data-external-kind"), "github");
  assert.ok(session.marks.includes("githubPull:timelineReady"));

  // The last published result is still shown if this exact record starts refreshing.
  session.replace({ ...fixture(), refreshing: true });
  session.timer(SLOW_POLL_MS);
  await settle();
  assert.deepEqual(order(body), interleaved);
  assert.equal(session.timelines.length, 1);
  // A changed record immediately retires its ordering, without repainting its same texts.
  session.replace({ ...fixture(), record_revision: nextRevision });
  session.timer(FAST_POLL_MS);
  await settle();
  assert.deepEqual(order(body), original);
  assert.equal(body.children[0].querySelector(".metabrowser-kpress-host"), description);
  session.frame();
  session.frame();
  const replacement = session.timelines[1];
  assert.equal(replacement.request.record_revision, nextRevision);
  // A held response from the prior revision may still resolve after its abort.
  session.replace(fixture());
  session.timer(SLOW_POLL_MS);
  await settle();
  assert.equal(replacement.signal.aborted, true);
  replacement.answer("complete", [commit]);
  await settle();
  assert.deepEqual(order(body), original);
  session.frame();
  session.frame();
  const departing = session.timelines[2];
  assert.equal(departing.request.record_revision, firstRevision);
  window.location.pathname = "/pull/7/files";
  session.handle.setTab("files");
  assert.equal(departing.signal.aborted, true);
  departing.answer("complete", [commit]);
  await settle();
  assert.equal(body.querySelector(".github-pull-commit"), null);
  session.handle.dispose();

  // A stale page can show held commits without putting a timeline provider read
  // ahead of metadata. A missed lookup is remembered throughout the refresh.
  for (const outcome of ["hit", "miss", "late-miss", "replaced"]) {
    const stale = mount(mountPullPage, fixture("stale"));
    await stale.handle.ready;
    await settle();
    stale.handle.activate();
    stale.frame();
    stale.frame();
    const [cached] = stale.timelines;
    assert.deepEqual(cached.request, {
      number: 7,
      record_revision: firstRevision,
      cached_only: true,
    });
    assert.equal(stale.body().querySelector(".github-pull-timeline-loading"), null);
    if (outcome === "hit") {
      cached.answer("complete", [commit]);
      await settle();
      assert.ok(stale.body().querySelector(".github-pull-commit"));
    } else if (outcome === "miss") {
      cached.answer("unavailable", []);
      await settle();
      assert.deepEqual(order(stale.body()), original);
    }
    stale.timer(REFRESH_ASK_MS);
    stale.frame();
    stale.frame();
    assert.equal(stale.timelines.length, 1);
    stale.replace({ ...fixture("stale"), refreshing: true });
    stale.acknowledgeRefresh();
    await settle();
    stale.frame();
    stale.frame();
    assert.equal(stale.timelines.length, 1);
    assert.equal(stale.body().querySelector(".github-pull-timeline-loading"), null);
    const settledRevision = outcome === "replaced" ? nextRevision : firstRevision;
    stale.replace({ ...fixture(), record_revision: settledRevision });
    stale.timer(FAST_POLL_MS);
    await settle();
    if (outcome === "late-miss") {
      assert.equal(stale.timelines.length, 1);
      cached.answer("unavailable", []);
      await settle();
    } else if (outcome === "replaced") {
      assert.equal(cached.signal.aborted, true);
      cached.answer("complete", [commit]);
      await settle();
      assert.equal(stale.body().querySelector(".github-pull-commit"), null);
    }
    stale.frame();
    stale.frame();
    if (outcome === "hit") {
      assert.equal(stale.timelines.length, 1);
      assert.ok(stale.body().querySelector(".github-pull-commit"));
    } else {
      assert.equal(stale.timelines.length, 2);
      assert.deepEqual(stale.timelines[1].request, { number: 7, record_revision: settledRevision });
      stale.timelines[1].answer("unavailable", [commit]);
      await settle();
      assert.deepEqual(order(stale.body()), original);
      stale.timer(SLOW_POLL_MS);
      await settle();
      stale.frame();
      stale.frame();
      assert.equal(stale.timelines.length, 2, "the settled provider result is not requested again");
      assert.equal(stale.hasTimer(TIMELINE_RETRY_MS), false, "an unflagged failure never retries");
    }
    stale.handle.dispose();
  }
  // The provider may flag one transient failure. The retry keeps partial output and
  // does not compete with metadata or leave its owning Conversation.
  for (const outcome of ["partial", "unavailable", "departed"]) {
    const transient = mount(mountPullPage, fixture());
    await transient.handle.ready;
    await settle();
    transient.handle.activate();
    transient.frame();
    transient.frame();
    const firstRead = transient.timelines[0];
    firstRead.answer(
      outcome === "partial" ? "partial" : "unavailable",
      [commit],
      firstRevision,
      true,
    );
    await settle();
    assert.ok(transient.hasTimer(TIMELINE_RETRY_MS));
    assert.equal(transient.timelines.length, 1);
    if (outcome === "departed") {
      window.location.pathname = "/pull/7/files";
      transient.handle.setTab("files");
      assert.equal(transient.hasTimer(TIMELINE_RETRY_MS), false);
      transient.handle.dispose();
      continue;
    }
    const commitLink = transient
      .body()
      .querySelector(".github-pull-commit")
      ?.querySelector("a[href]");
    if (outcome === "partial") {
      assert.ok(commitLink);
      document.activeElement = commitLink;
      transient.replace({ ...fixture(), refreshing: true });
      transient.timer(SLOW_POLL_MS);
      await settle();
      assert.equal(transient.timelines.length, 1);
      assert.equal(
        transient.body().querySelector(".github-pull-commit")?.querySelector("a[href]"),
        commitLink,
      );
      transient.replace(fixture());
      transient.timer(FAST_POLL_MS);
      await settle();
    }
    transient.timer(TIMELINE_RETRY_MS);
    assert.equal(transient.timelines.length, 2);
    assert.deepEqual(transient.timelines[1].request, firstRead.request);
    if (outcome === "partial") {
      assert.equal(
        transient.body().querySelector(".github-pull-commit")?.querySelector("a[href]"),
        commitLink,
      );
      transient.timelines[1].answer("complete", [
        { kind: "commit", oid: lastCommit, subject: "Recovered commit", committed_at: null },
        commit,
      ]);
      await settle();
      assert.equal(transient.body().querySelectorAll(".github-pull-commit").length, 2);
      assert.equal(document.activeElement, commitLink);
      assert.ok(transient.body().querySelectorAll(".github-pull-commit")[1].contains(commitLink));
      assert.equal(
        transient.marks.filter((label) => label === "githubPull:timelineReady").length,
        1,
      );
    } else {
      transient.timelines[1].answer("unavailable", [], firstRevision, true);
      await settle();
    }
    assert.equal(transient.hasTimer(TIMELINE_RETRY_MS), false, "the retry budget is exhausted");
    transient.handle.dispose();
  }
  return {
    interleaved: interleaved.slice(0, 8),
    destination,
    heldMarkdownAndFocus: true,
    staleCacheHitBeforeMetadata: true,
    staleCacheMissWaited: true,
    supersededReadAborted: true,
    departedReadAborted: true,
    unavailableKeepsDiscussion: true,
    transientRetryIsBoundedAndKeepsPartial: true,
  };
}

run()
  .then((result) => process.stdout.write(`${JSON.stringify(result, null, 2)}\n`))
  .catch((error) => {
    process.stderr.write(`${error.stack}\n`);
    process.exitCode = 1;
  });

const fs = require("node:fs");
const path = require("node:path");
const { pathToFileURL } = require("node:url");

const repoRoot = path.resolve(process.argv[2]);
const failures = [];
function check(name, condition, detail = "failed") {
  if (!condition) {
    failures.push(`${name}: ${detail}`);
  }
}

function makeContainer() {
  return {
    innerHTML: "",
    prepended: [],
    classList: { add() {} },
    querySelector() {
      return null;
    },
    prepend(node) {
      this.prepended.push(node);
    },
  };
}

async function flush() {
  for (let turn = 0; turn < 8; turn += 1) {
    await new Promise((resolve) => setImmediate(resolve));
  }
}

function rejected(promise) {
  return promise.then(
    () => null,
    (error) => error,
  );
}

/**
 * A module Worker double driven by the production worker client. It answers a
 * primary preparation on a microtask, and a `[[crash]]` source raises the
 * Worker error event that latches the client as fatally failed.
 */
const workers = [];
class FakeWorker {
  constructor(url, options) {
    this.url = String(url);
    this.options = options;
    this.messages = [];
    this.onerror = null;
    this.onmessage = null;
    this.onmessageerror = null;
    this.terminated = false;
    workers.push(this);
  }

  postMessage(message) {
    this.messages.push(message);
    const source = message.payload.source;
    queueMicrotask(() => {
      if (this.terminated) {
        return;
      }
      if (source.includes("[[crash]]")) {
        this.onerror?.({ message: "worker crashed" });
        return;
      }
      const changed = source.includes("[[wiki]]");
      const limited = source.includes("[[limited]]");
      this.onmessage?.({
        data: {
          id: message.id,
          result: {
            changed,
            complete: !limited,
            diagnostics: limited ? [{ code: "transformed-source-byte-limit" }] : [],
            source: changed ? `processed ${source}` : null,
          },
        },
      });
    });
  }

  terminate() {
    this.terminated = true;
  }
}

/**
 * The shared Worker outlives its last reference for an idle period. The period runs on a
 * clock the session advances, so a check can say what is alive during it and after it.
 */
const idleTimers = new Map();
let nextIdleTimer = 1;
globalThis.setTimeout = (callback, delay) => {
  const id = nextIdleTimer;
  nextIdleTimer += 1;
  idleTimers.set(id, { callback, delay });
  return id;
};
globalThis.clearTimeout = (id) => {
  idleTimers.delete(id);
};
function elapseIdlePeriod() {
  for (const [id, timer] of [...idleTimers]) {
    idleTimers.delete(id);
    timer.callback();
  }
}
/** Run the timers due within *ms*, as the event loop would once that much time passed. */
function runTimersDueWithin(ms) {
  for (const [id, timer] of [...idleTimers]) {
    if (timer.delay <= ms) {
      idleTimers.delete(id);
      timer.callback();
    }
  }
}

/**
 * Animation frames run when the session paints one, so a check can tell the task an input
 * runs in from the frame it paints and the task after it.
 */
const animationFrames = new Map();
let nextAnimationFrame = 1;
globalThis.requestAnimationFrame = (callback) => {
  const id = nextAnimationFrame;
  nextAnimationFrame += 1;
  animationFrames.set(id, callback);
  return id;
};
globalThis.cancelAnimationFrame = (id) => {
  animationFrames.delete(id);
};
function paintFrame() {
  for (const [id, callback] of [...animationFrames]) {
    animationFrames.delete(id);
    callback(0);
  }
}
/** Settle every microtask the current task queued, and nothing else. */
async function endOfTask() {
  for (let turn = 0; turn < 20; turn += 1) {
    await Promise.resolve();
  }
}

(async () => {
  const source = fs.readFileSync(
    path.join(repoRoot, "src/metabrowser/builtin_plugins/markdown/rendered.js"),
    "utf8",
  );
  globalThis.__markdownEnhanceDisposals = [];
  globalThis.__markdownEnhanceCalls = [];
  globalThis.Worker = FakeWorker;
  globalThis.document = {
    createElement() {
      return {
        firstElementChild: null,
        set innerHTML(value) {
          this.firstElementChild = { html: value };
        },
      };
    },
  };
  const enhancerStub =
    "export function enhanceRenderedLinks(container,sourcePath,mb,options){" +
    "globalThis.__markdownEnhanceCalls.push({sourcePath,options});" +
    "return {dispose(){globalThis.__markdownEnhanceDisposals.push(container)}}}";
  const enhancerUrl = `data:text/javascript;base64,${Buffer.from(enhancerStub).toString("base64")}`;
  const tocFallbackStub =
    "export function initTocWithIntersectionFallback(init){" +
    "globalThis.__markdownTocFallbackCalls=(globalThis.__markdownTocFallbackCalls||0)+1;" +
    "return init()||(()=>{})}";
  const tocFallbackUrl = `data:text/javascript;base64,${Buffer.from(tocFallbackStub).toString("base64")}`;
  // The production worker client owns sharing, cancellation, and recovery, so
  // the mount runs against it and only the Worker itself is a double.
  const workerClientUrl = pathToFileURL(
    path.join(repoRoot, "src/metabrowser/builtin_plugins/markdown/markdown-worker-client.js"),
  ).href;
  // A recognizable stand-in rather than a copy of the key format: this test
  // proves the mount seeds a chain derived from ctx.path, and
  // markdown-transclusion-behavior.js covers the real key spelling.
  const transclusionStub =
    'export function transclusionKey(path){return Object.freeze({fragment:"",path})}';
  const transclusionUrl = `data:text/javascript;base64,${Buffer.from(transclusionStub).toString("base64")}`;
  // The production placement module, with the inert render it imports on demand
  // replaced by a double that counts its own evaluation: a trusted mount must never
  // import it, and an inert one must run its table of contents instead of KPress's.
  const inertRenderStub =
    "globalThis.__markdownInertImports=(globalThis.__markdownInertImports||0)+1;" +
    "export async function placeRendered(target,rendered,mb,enhance){" +
    "target.innerHTML='<article class=kpress-inert>'+rendered.html+'</article>';" +
    "target.inertArticle={of:target};return enhance?enhance(target):null}" +
    "export function inertArticle(root){return root.inertArticle||null}" +
    "export function wireInertToc(article,options){" +
    "globalThis.__markdownInertTocs.push({article,options});" +
    "return ()=>globalThis.__markdownInertTocDisposals.push(article)}";
  const inertRenderUrl = `data:text/javascript;base64,${Buffer.from(inertRenderStub).toString("base64")}`;
  const placeRenderedSource = fs
    .readFileSync(
      path.join(repoRoot, "src/metabrowser/builtin_plugins/markdown/place-rendered.js"),
      "utf8",
    )
    .replaceAll('"./inert-render.js"', JSON.stringify(inertRenderUrl));
  check(
    "the placement module imports the inert render on demand",
    placeRenderedSource.includes(`await import(${JSON.stringify(inertRenderUrl)})`),
  );
  const placeRenderedUrl = `data:text/javascript;base64,${Buffer.from(placeRenderedSource).toString("base64")}`;
  globalThis.__markdownInertTocs = [];
  globalThis.__markdownInertTocDisposals = [];
  const importableSource = source
    .replace('"./link-enhancer.js"', JSON.stringify(enhancerUrl))
    .replace('"./markdown-worker-client.js"', JSON.stringify(workerClientUrl))
    .replace('"./toc-intersection-fallback.js"', JSON.stringify(tocFallbackUrl))
    .replace('"./place-rendered.js"', JSON.stringify(placeRenderedUrl))
    .replace('"./transclusion.js"', JSON.stringify(transclusionUrl));
  const module = await import(
    `data:text/javascript;base64,${Buffer.from(importableSource).toString("base64")}`
  );
  const requests = [];
  const completeTextRequests = [];
  const tocDisposals = [];
  const assetLoads = [];
  const mb = {
    escapeHtml: String,
    errors: { isAbortError: (error) => error?.name === "AbortError" },
    fetchKpressRender(ctx, _view, options) {
      return new Promise((resolve, reject) => requests.push({ ctx, resolve, reject, options }));
    },
    async loadKpressAssets(manifest) {
      assetLoads.push(manifest);
    },
    async fetchCompleteText(ctx, options) {
      completeTextRequests.push({ ctx, options });
      return "[[wiki]]";
    },
    kpressInitToc(container) {
      return () => tocDisposals.push(container);
    },
  };
  const requestFor = (filePath) => requests.find((request) => request.ctx.path === filePath);
  const requestsFor = (filePath) => requests.filter((request) => request.ctx.path === filePath);
  const enhanceCallFor = (filePath) =>
    globalThis.__markdownEnhanceCalls.find((call) => call.sourcePath === filePath);

  // Concurrent mounts share one lazily constructed Worker.
  check("no Worker exists before a mount needs one", workers.length === 0);
  const first = makeContainer();
  const second = makeContainer();
  const firstMount = module.mountRenderedMarkdown(
    first,
    { path: "a.md", raw: { content: "# A [[wiki]]" } },
    mb,
  );
  const secondMount = module.mountRenderedMarkdown(
    second,
    { path: "b.md", raw: { content: "# B" } },
    mb,
  );
  check("first mount declares readiness", firstMount.ready instanceof Promise);
  check("second mount declares readiness", secondMount.ready instanceof Promise);
  await flush();
  check("independent requests", requests.length === 2, String(requests.length));
  check(
    "concurrent mounts share one Worker",
    workers.length === 1 && workers[0].messages.length === 2,
    JSON.stringify(workers.map((worker) => worker.messages.length)),
  );
  check(
    "each mount receives its own preprocessing result",
    requestFor("a.md")?.options.sourceText === "processed # A [[wiki]]" &&
      requestFor("b.md")?.options.sourceText === undefined,
  );
  requestFor("b.md").resolve({ html: "<article>second</article>", diagnostics: [] });
  requestFor("a.md").resolve({ html: "<article>first</article>", diagnostics: [] });
  await Promise.all([firstMount.ready, secondMount.ready]);
  check("first painted", first.innerHTML.includes("first"), first.innerHTML);
  check("second painted", second.innerHTML.includes("second"), second.innerHTML);
  check("TOC fallback wraps every mount", globalThis.__markdownTocFallbackCalls === 2);
  // A rendered document is its own transclusion ancestor. Without this seed a
  // note embedding itself renders one complete duplicate before the repeat is
  // caught one level down.
  const firstEnhanceCall = enhanceCallFor("a.md");
  check(
    "mount seeds its own transclusion ancestry",
    JSON.stringify(firstEnhanceCall?.options?.transclusionChain) ===
      JSON.stringify([{ fragment: "", path: "a.md" }]),
    JSON.stringify(globalThis.__markdownEnhanceCalls),
  );
  const firstLease = firstEnhanceCall?.options?.workerClient;
  const secondLease = enhanceCallFor("b.md")?.options?.workerClient;
  check(
    "each root passes its Worker reference into link enhancement",
    typeof firstLease?.run === "function" && typeof secondLease?.run === "function",
  );

  firstMount.dispose();
  firstMount.dispose();
  check("first disposer exactly once", tocDisposals.length === 1, String(tocDisposals.length));
  check(
    "first enhancer disposer exactly once",
    globalThis.__markdownEnhanceDisposals.length === 1,
    String(globalThis.__markdownEnhanceDisposals.length),
  );
  check("second remains mounted", !tocDisposals.includes(second));
  check("disposing one mount keeps the shared Worker for the other", !workers[0].terminated);
  const releasedRun = await rejected(firstLease.run("prepare-primary", { source: "late" }));
  check(
    "a disposed mount's Worker reference refuses new work",
    releasedRun?.name === "AbortError" && workers[0].messages.length === 2,
  );
  const nestedResult = await secondLease.run("prepare-primary", { source: "nested [[wiki]]" });
  check(
    "the remaining mount keeps using the shared Worker",
    nestedResult?.source === "processed nested [[wiki]]" && workers.length === 1,
  );

  const third = makeContainer();
  const thirdMount = module.mountRenderedMarkdown(
    third,
    { path: "c.md", raw: { content: "# C" } },
    mb,
  );
  await flush();
  check(
    "a mount added while another is live reuses the Worker",
    workers.length === 1 && workers[0].messages.length === 4,
    String(workers.length),
  );
  requestFor("c.md").resolve({ html: "<article>third</article>", diagnostics: [] });
  await thirdMount.ready;
  secondMount.dispose();
  check("second disposer", tocDisposals.length === 2, String(tocDisposals.length));
  check("second enhancer disposer", globalThis.__markdownEnhanceDisposals.length === 2);
  check("a live mount still holds the shared Worker", !workers[0].terminated);
  thirdMount.dispose();
  check(
    "the last mount's disposal keeps the shared Worker for the idle period",
    !workers[0].terminated && idleTimers.size === 1,
  );
  // A Markdown document opened after a file of another kind finds the Worker it left,
  // instead of constructing one and requesting its modules again.
  const afterOtherKind = makeContainer();
  const afterOtherKindMount = module.mountRenderedMarkdown(
    afterOtherKind,
    { path: "after-other-kind.md", raw: { content: "after [[wiki]]" } },
    mb,
  );
  await flush();
  check(
    "a mount within the idle period reuses the Worker",
    workers.length === 1 && workers[0].messages.at(-1)?.payload.source === "after [[wiki]]",
    String(workers.length),
  );
  check("the reusing mount ends the idle period", idleTimers.size === 0);
  requestFor("after-other-kind.md").resolve({ html: "<article>after</article>", diagnostics: [] });
  await afterOtherKindMount.ready;
  afterOtherKindMount.dispose();
  elapseIdlePeriod();
  check("the idle period's end terminates the shared Worker", workers[0].terminated);

  // Cancellation stays per request: disposing a mount whose preparation is
  // running cancels only that request, and the other mount continues.
  const canceled = makeContainer();
  const continuing = makeContainer();
  const canceledMount = module.mountRenderedMarkdown(
    canceled,
    { path: "canceled.md", raw: { content: "canceled [[wiki]]" } },
    mb,
  );
  const continuingMount = module.mountRenderedMarkdown(
    continuing,
    { path: "continuing.md", raw: { content: "continuing [[wiki]]" } },
    mb,
  );
  const activeWorker = workers.at(-1);
  check(
    "a new page-level Worker is created after the previous one was released",
    workers.length === 2 && activeWorker.messages.length === 1,
    String(workers.length),
  );
  canceledMount.dispose();
  await flush();
  check(
    "canceling the active request replaces only the busy Worker",
    activeWorker.terminated && workers.length === 3 && workers[2].messages.length === 1,
  );
  check("the canceled mount requests no render", requestFor("canceled.md") === undefined);
  check(
    "the other mount's queued preparation still completes",
    requestFor("continuing.md")?.options.sourceText === "processed continuing [[wiki]]",
  );
  requestFor("continuing.md").resolve({ html: "<article>continuing</article>", diagnostics: [] });
  await continuingMount.ready;
  await canceledMount.ready;
  check("the canceled mount paints nothing", !canceled.innerHTML.includes("article"));
  check("the continuing mount paints", continuing.innerHTML.includes("continuing"));

  // A fatal Worker failure is not permanent for the page: the mount that saw it
  // renders its authored source with a diagnostic, and the next request gets a
  // new Worker even while another mount kept the shared reference alive.
  const crashed = makeContainer();
  const crashedMount = module.mountRenderedMarkdown(
    crashed,
    { path: "worker-failure.md", raw: { content: "[[crash]] body" } },
    mb,
  );
  const crashedWorker = workers.at(-1);
  await flush();
  check(
    "the optional preprocessing failure still requests the rendered document",
    requestFor("worker-failure.md")?.options.sourceText === undefined,
  );
  requestFor("worker-failure.md")?.resolve({
    html: "<article>authored</article>",
    diagnostics: [],
  });
  await crashedMount.ready;
  check("worker failure paints the document", crashed.innerHTML.includes("authored"));
  check(
    "worker failure is explained by a diagnostic",
    JSON.stringify(crashed.prepended).includes("markdown-preprocessing-unavailable"),
    JSON.stringify(crashed.prepended),
  );
  check("a fatal failure terminates the failed Worker", crashedWorker.terminated);
  const recovered = makeContainer();
  const recoveredMount = module.mountRenderedMarkdown(
    recovered,
    { path: "recovered.md", raw: { content: "recovered [[wiki]]" } },
    mb,
  );
  await flush();
  check(
    "the next preparation after a fatal failure runs on a new Worker",
    workers.at(-1) !== crashedWorker &&
      requestFor("recovered.md")?.options.sourceText === "processed recovered [[wiki]]",
    String(requestFor("recovered.md")?.options.sourceText),
  );
  requestFor("recovered.md").resolve({ html: "<article>recovered</article>", diagnostics: [] });
  await recoveredMount.ready;
  recoveredMount.dispose();
  crashedMount.dispose();
  continuingMount.dispose();
  elapseIdlePeriod();
  check(
    "every Worker is terminated once no mount remains for the idle period",
    workers.every((worker) => worker.terminated),
  );

  const pending = makeContainer();
  const pendingHandle = module.mountRenderedMarkdown(pending, { path: "pending.md" }, mb);
  await flush();
  const pendingSignal = requestFor("pending.md").options.signal;
  pendingHandle.dispose();
  check("direct disposer aborts pending request", pendingSignal.aborted === true);
  requestFor("pending.md").resolve({ html: "<article>too late</article>", diagnostics: [] });
  await pendingHandle.ready;
  check("disposed direct completion ignored", !pending.innerHTML.includes("too late"));

  const late = makeContainer();
  const controller = new AbortController();
  const lateMount = module.mountRenderedMarkdown(late, { path: "late.md" }, mb, {
    signal: controller.signal,
  });
  await flush();
  controller.abort();
  requestFor("late.md").resolve({ html: "<article>too late</article>", diagnostics: [] });
  await lateMount.ready;
  check("late completion ignored", !late.innerHTML.includes("too late"), late.innerHTML);
  lateMount.dispose();

  const truncatedWiki = makeContainer();
  const truncatedWikiMount = module.mountRenderedMarkdown(
    truncatedWiki,
    {
      path: "large-wiki.md",
      raw: {
        content: "[[partial",
        content_max_preview_limit: 8_388_608,
        content_truncated: true,
      },
    },
    mb,
  );
  await flush();
  check("truncated wiki requests complete source", completeTextRequests.length === 1);
  check(
    "complete source request is abortable",
    completeTextRequests[0].options.signal instanceof AbortSignal,
  );
  check(
    "complete wiki source is preprocessed",
    requestFor("large-wiki.md")?.options.sourceText === "processed [[wiki]]",
  );
  requestFor("large-wiki.md").resolve({ html: "<article>large wiki</article>", diagnostics: [] });
  await truncatedWikiMount.ready;
  truncatedWikiMount.dispose();

  const limitedWiki = makeContainer();
  const limitedWikiMount = module.mountRenderedMarkdown(
    limitedWiki,
    { path: "limited.md", raw: { content: "[[limited]]" } },
    mb,
  );
  await flush();
  check(
    "incomplete preprocessing renders the original source",
    requestFor("limited.md")?.options.sourceText === undefined,
  );
  requestFor("limited.md").resolve({
    html: "<article>limited</article>",
    diagnostics: [{ type: "kpress-warning" }],
  });
  await limitedWikiMount.ready;
  const diagnosticHtml = limitedWiki.prepended[0]?.html || "";
  check(
    "preprocessing diagnostics remain visible beside KPress diagnostics",
    diagnosticHtml.includes("transformed-source-byte-limit") &&
      diagnosticHtml.includes("kpress-warning"),
    diagnosticHtml,
  );
  limitedWikiMount.dispose();

  // ── Kept renders ─────────────────────────────────────────────
  // A mount of the envelope the shell holds finds the render an earlier mount of it
  // made: no preparation, no request, and the same document and diagnostics. Another
  // envelope -- a changed file, or the same file fetched again after the shell dropped
  // it -- prepares and asks afresh, and so does a render that did not go as it should.
  const workerMessages = () => workers.reduce((count, worker) => count + worker.messages.length, 0);
  const keptEnvelope = {
    content: "# Kept [[wiki]] [[limited]]",
    mtime_hash: "kept-v1",
    path: "kept.md",
    type: "text",
  };
  const keptFirst = makeContainer();
  const keptFirstMount = module.mountRenderedMarkdown(
    keptFirst,
    { path: "kept.md", raw: keptEnvelope },
    mb,
  );
  await flush();
  check(
    "a first mount prepares the source and posts it",
    requestsFor("kept.md").length === 1 &&
      requestsFor("kept.md")[0].options.sourceText === "processed # Kept [[wiki]] [[limited]]",
  );
  const keptAssets = { schema: "kpress-asset-manifest-v2", assets: [] };
  requestsFor("kept.md")[0].resolve({
    assets: keptAssets,
    diagnostics: [{ type: "kpress-note" }],
    html: "<article>kept v1</article>",
  });
  await keptFirstMount.ready;
  keptFirstMount.dispose();
  check("the render is kept", module.keptRenders.stats().entries === 1);
  const messagesBeforeRevisit = workerMessages();
  const enhanceCallsBeforeRevisit = globalThis.__markdownEnhanceCalls.length;
  const tocCallsBeforeRevisit = globalThis.__markdownTocFallbackCalls;
  const keptRevisit = makeContainer();
  const keptRevisitMount = module.mountRenderedMarkdown(
    keptRevisit,
    { path: "kept.md", raw: keptEnvelope },
    mb,
  );
  await keptRevisitMount.ready;
  check("a revisit runs no preparation", workerMessages() === messagesBeforeRevisit);
  check("a revisit asks for no render", requestsFor("kept.md").length === 1);
  check("a revisit places the kept render", keptRevisit.innerHTML.includes("kept v1"));
  check(
    "a revisit shows the preparation's and the render's diagnostics as the first mount did",
    JSON.stringify(keptRevisit.prepended) === JSON.stringify(keptFirst.prepended) &&
      JSON.stringify(keptRevisit.prepended).includes("transformed-source-byte-limit") &&
      JSON.stringify(keptRevisit.prepended).includes("kpress-note"),
    JSON.stringify([keptFirst.prepended, keptRevisit.prepended]),
  );
  check(
    "a revisit still enhances its links and wires its table of contents",
    globalThis.__markdownEnhanceCalls.length === enhanceCallsBeforeRevisit + 1 &&
      globalThis.__markdownTocFallbackCalls === tocCallsBeforeRevisit + 1,
  );
  check(
    "a revisit makes sure the render's KPress assets are loaded",
    assetLoads.length === 1 && assetLoads[0] === keptAssets,
  );
  keptRevisitMount.dispose();

  const disposedEarly = makeContainer();
  const disposedEarlyMount = module.mountRenderedMarkdown(
    disposedEarly,
    { path: "kept.md", raw: keptEnvelope },
    mb,
  );
  disposedEarlyMount.dispose();
  await disposedEarlyMount.ready;
  check(
    "a kept render is not placed into a mount disposed before it was ready",
    !disposedEarly.innerHTML.includes("kept v1"),
  );

  const optionsVariant = makeContainer();
  const optionsVariantMount = module.mountRenderedMarkdown(
    optionsVariant,
    { path: "kept.md", raw: keptEnvelope },
    mb,
    { includeToc: "off" },
  );
  await flush();
  check(
    "another table-of-contents option is another render",
    requestsFor("kept.md").length === 2 && requestsFor("kept.md")[1].options.includeToc === "off",
  );
  requestsFor("kept.md")[1].resolve({ html: "<article>kept no toc</article>", diagnostics: [] });
  await optionsVariantMount.ready;
  optionsVariantMount.dispose();

  // The shell replaces the envelope when the file changes: the new one has another
  // identity, and its mount must never show the render of the old one.
  const changedEnvelope = { ...keptEnvelope, content: "# Kept v2 [[wiki]]", mtime_hash: "kept-v2" };
  const changed = makeContainer();
  const changedMount = module.mountRenderedMarkdown(
    changed,
    { path: "kept.md", raw: changedEnvelope },
    mb,
  );
  await flush();
  check(
    "a changed file is prepared and asked for afresh",
    requestsFor("kept.md").length === 3 &&
      requestsFor("kept.md")[2].options.sourceText === "processed # Kept v2 [[wiki]]",
  );
  requestsFor("kept.md")[2].resolve({ html: "<article>kept v2</article>", diagnostics: [] });
  await changedMount.ready;
  check(
    "a changed file shows its own render",
    changed.innerHTML.includes("kept v2") && !changed.innerHTML.includes("kept v1"),
  );
  changedMount.dispose();

  // The same identity in an envelope the shell fetched again, after it dropped the one the
  // render was kept with, is asked for again: a render lives as long as its envelope.
  const refetched = makeContainer();
  const refetchedMount = module.mountRenderedMarkdown(
    refetched,
    { path: "kept.md", raw: { ...keptEnvelope } },
    mb,
  );
  await flush();
  check(
    "an envelope the shell fetched again does not find the dropped envelope's render",
    requestsFor("kept.md").length === 4,
  );
  requestsFor("kept.md")[3].resolve({ html: "<article>kept again</article>", diagnostics: [] });
  await refetchedMount.ready;
  refetchedMount.dispose();

  // A folder's README panel mounts with the folder's envelope, whose identity does not
  // move when the README's content does, so its render is never kept.
  const folderEnvelope = { mtime_hash: "folder-identity", path: "docs", type: "folder" };
  for (const round of [1, 2]) {
    const panel = makeContainer();
    const panelMount = module.mountRenderedMarkdown(
      panel,
      { kind: "markdown", path: "docs/README.md", raw: folderEnvelope },
      mb,
      { includeToc: "off" },
    );
    await flush();
    requestsFor("docs/README.md")
      .at(-1)
      .resolve({ html: `<article>readme ${round}</article>` });
    await panelMount.ready;
    panelMount.dispose();
  }
  check(
    "a render made from another file's envelope is asked for every time",
    requestsFor("docs/README.md").length === 2,
  );

  // A render made without its preparation, or one that failed, is not kept.
  const crashEnvelope = { content: "[[crash]] kept?", mtime_hash: "crash-1", path: "crash.md" };
  for (const round of [1, 2]) {
    const crash = makeContainer();
    const crashMount = module.mountRenderedMarkdown(
      crash,
      { path: "crash.md", raw: crashEnvelope },
      mb,
    );
    await flush();
    requestsFor("crash.md")
      .at(-1)
      .resolve({ html: `<article>authored ${round}</article>` });
    await crashMount.ready;
    crashMount.dispose();
  }
  check(
    "a render made without its preparation is asked for again",
    requestsFor("crash.md").length === 2,
  );
  const failingEnvelope = { content: "# Fails", mtime_hash: "fails-1", path: "fails.md" };
  const failing = makeContainer();
  const failingMount = module.mountRenderedMarkdown(
    failing,
    { path: "fails.md", raw: failingEnvelope },
    mb,
  );
  await flush();
  requestsFor("fails.md")[0].reject(new Error("render failed"));
  await failingMount.ready;
  failingMount.dispose();
  const retried = makeContainer();
  const retriedMount = module.mountRenderedMarkdown(
    retried,
    { path: "fails.md", raw: failingEnvelope },
    mb,
  );
  await flush();
  check("a failed render is asked for again", requestsFor("fails.md").length === 2);
  requestsFor("fails.md")[1].resolve({ html: "<article>recovered render</article>" });
  await retriedMount.ready;
  retriedMount.dispose();

  // A truncated envelope's complete source is fetched once, by the mount that renders it.
  const truncatedEnvelope = {
    content: "[[partial",
    content_truncated: true,
    mtime_hash: "large-1",
    path: "large-kept.md",
  };
  const completeTextsBefore = completeTextRequests.length;
  for (const round of [1, 2]) {
    const large = makeContainer();
    const largeMount = module.mountRenderedMarkdown(
      large,
      { path: "large-kept.md", raw: truncatedEnvelope },
      mb,
    );
    await flush();
    if (round === 1) {
      requestsFor("large-kept.md")[0].resolve({ html: "<article>large kept</article>" });
    }
    await largeMount.ready;
    check(
      `a truncated envelope's render ${round} is placed`,
      large.innerHTML.includes("large kept"),
    );
    largeMount.dispose();
  }
  check(
    "a kept render of a truncated envelope fetches no complete source again",
    completeTextRequests.length === completeTextsBefore + 1 &&
      requestsFor("large-kept.md").length === 1,
  );

  // A kept render is found in the task of the input that opened the document. A small one
  // is placed in that task. A large one waits for that input's first paint, which shows the
  // document being left, and is placed in the task after it: placing design-system.md in
  // the input's task was one 80 to 93 ms task and pushed the click's next paint to 96 to
  // 120 ms (exp-061's series).
  const smallKept = makeContainer();
  const smallKeptMount = module.mountRenderedMarkdown(
    smallKept,
    { path: "kept.md", raw: keptEnvelope },
    mb,
  );
  await endOfTask();
  check(
    "a small kept render is placed in the input's own task",
    smallKept.innerHTML.includes("kept v1") && animationFrames.size === 0,
    smallKept.innerHTML,
  );
  await smallKeptMount.ready;
  smallKeptMount.dispose();

  const largeHtml = `<article>large kept ${"x".repeat(module.KEPT_RENDER_INPUT_TASK_MAX_CHARS)}</article>`;
  const largeEnvelope = {
    content: "# Large",
    mtime_hash: "large-kept-1",
    path: "large-kept-doc.md",
    type: "text",
  };
  const largeFirst = makeContainer();
  const largeFirstMount = module.mountRenderedMarkdown(
    largeFirst,
    { path: "large-kept-doc.md", raw: largeEnvelope },
    mb,
  );
  await flush();
  requestsFor("large-kept-doc.md")[0].resolve({ html: largeHtml, diagnostics: [] });
  await largeFirstMount.ready;
  largeFirstMount.dispose();
  const pendingPaintWaits = () => [...idleTimers.values()].filter((timer) => timer.delay <= 100);

  const enhanceCallsBeforeLarge = globalThis.__markdownEnhanceCalls.length;
  const largeRevisit = makeContainer();
  const largeRevisitMount = module.mountRenderedMarkdown(
    largeRevisit,
    { path: "large-kept-doc.md", raw: largeEnvelope },
    mb,
  );
  await endOfTask();
  check(
    "a large kept render is not placed in the input's own task",
    !largeRevisit.innerHTML.includes("large kept") &&
      globalThis.__markdownEnhanceCalls.length === enhanceCallsBeforeLarge,
  );
  check("it waits for the frame the input paints", animationFrames.size === 1);
  paintFrame();
  await endOfTask();
  check(
    "it is not placed in that frame's own callbacks, before the paint",
    !largeRevisit.innerHTML.includes("large kept"),
  );
  runTimersDueWithin(0);
  await largeRevisitMount.ready;
  check(
    "it is placed in the task after the input's first paint",
    largeRevisit.innerHTML.includes("large kept") &&
      globalThis.__markdownEnhanceCalls.length === enhanceCallsBeforeLarge + 1,
  );
  check("and still asks for nothing", requestsFor("large-kept-doc.md").length === 1);
  check(
    "the wait leaves no frame request or timer behind",
    animationFrames.size === 0 && pendingPaintWaits().length === 0,
    JSON.stringify(pendingPaintWaits()),
  );
  largeRevisitMount.dispose();

  const leaving = makeContainer();
  const leavingMount = module.mountRenderedMarkdown(
    leaving,
    { path: "large-kept-doc.md", raw: largeEnvelope },
    mb,
  );
  await endOfTask();
  check("a mount that waits holds one frame request", animationFrames.size === 1);
  leavingMount.dispose();
  await leavingMount.ready;
  check(
    "a mount disposed while it waits places nothing and releases its frame and timers",
    !leaving.innerHTML.includes("large kept") &&
      animationFrames.size === 0 &&
      pendingPaintWaits().length === 0,
  );

  // A page hidden during the wait paints no frame; the wait ends after its bound instead.
  const hiddenDuring = makeContainer();
  const hiddenDuringMount = module.mountRenderedMarkdown(
    hiddenDuring,
    { path: "large-kept-doc.md", raw: largeEnvelope },
    mb,
  );
  await endOfTask();
  runTimersDueWithin(100);
  await hiddenDuringMount.ready;
  check(
    "with no frame, a large kept render is placed after the wait's bound",
    hiddenDuring.innerHTML.includes("large kept") && animationFrames.size === 0,
  );
  hiddenDuringMount.dispose();

  // A page already hidden has no paint to protect, so it does not wait (review B, B6).
  globalThis.document.visibilityState = "hidden";
  const hidden = makeContainer();
  const hiddenMount = module.mountRenderedMarkdown(
    hidden,
    { path: "large-kept-doc.md", raw: largeEnvelope },
    mb,
  );
  await endOfTask();
  check(
    "in a hidden page a large kept render is placed in the input's own task",
    hidden.innerHTML.includes("large kept") &&
      animationFrames.size === 0 &&
      pendingPaintWaits().length === 0,
  );
  await hiddenMount.ready;
  hiddenMount.dispose();
  delete globalThis.document.visibilityState;

  // The bound is bytes: the render's HTML and the JSON of the rest. A store past it evicts
  // the least recently used render, which a lookup refreshes, and a render over a quarter
  // of the bound is shown and not kept.
  const bounded = module.createRenderCache({ maxBytes: 400 });
  const boundedEnvelopes = [1, 2, 3, 4, 5, 6, 7].map((index) => ({ index }));
  const boundedRequest = (index) =>
    Object.freeze({
      identity: `identity-${index}`,
      path: `bounded-${index}.md`,
      profile: "document",
      source: "prepare-primary",
      toc: "auto",
      view: "rendered",
    });
  const boundedRender = (length) =>
    Object.freeze({ diagnostics: [], rendered: { html: "h".repeat(length) } });
  for (const [index, envelope] of boundedEnvelopes.slice(0, 6).entries()) {
    bounded.store(envelope, boundedRequest(index), boundedRender(60));
  }
  check("six 64-byte renders fit in 400 bytes", bounded.stats().entries === 6);
  check(
    "a lookup finds a kept render",
    bounded.lookup(boundedEnvelopes[0], boundedRequest(0))?.rendered.html.length === 60,
  );
  check(
    "a lookup needs the same request as well as the same envelope",
    bounded.lookup(boundedEnvelopes[0], boundedRequest(1)) === undefined,
  );
  bounded.store(boundedEnvelopes[6], boundedRequest(6), boundedRender(60));
  check(
    "a seventh render evicts the least recently used, not the one just read",
    bounded.stats().entries === 6 &&
      bounded.lookup(boundedEnvelopes[1], boundedRequest(1)) === undefined &&
      bounded.lookup(boundedEnvelopes[0], boundedRequest(0)) !== undefined,
    JSON.stringify(bounded.stats()),
  );
  check("the kept bytes stay within the bound", bounded.stats().bytes <= 400);
  check(
    "a render over a quarter of the bound is not kept",
    bounded.store({}, boundedRequest(9), boundedRender(120)) === false &&
      bounded.stats().entries === 6,
  );

  elapseIdlePeriod();
  check(
    "no Worker outlives the idle period after the last mount",
    workers.every((worker) => worker.terminated),
  );

  // Every render above was trusted, as every render of a trusted folder is. The
  // inert path loads with the first inert render and not before.
  check(
    "a trusted render never imports the inert render",
    globalThis.__markdownInertImports === undefined,
    String(globalThis.__markdownInertImports),
  );
  const fallbackCallsBeforeInert = globalThis.__markdownTocFallbackCalls;
  const kpressTocDisposalsBeforeInert = tocDisposals.length;
  const inertContainers = [makeContainer(), makeContainer()];
  const inertMounts = inertContainers.map((container, index) =>
    module.mountRenderedMarkdown(
      container,
      { path: `inert-${index}.md`, raw: { content: "# Inert" } },
      mb,
    ),
  );
  await flush();
  for (const index of [0, 1]) {
    requestFor(`inert-${index}.md`).resolve({ html: `inert ${index}`, inert: true, toc: true });
  }
  await Promise.all(inertMounts.map((mount) => mount.ready));
  check(
    "inert renders import the inert render once between them",
    globalThis.__markdownInertImports === 1,
    String(globalThis.__markdownInertImports),
  );
  check(
    "an inert render is placed by the inert path",
    inertContainers.every((container, index) =>
      container.innerHTML.includes(`kpress-inert>inert ${index}`),
    ),
    JSON.stringify(inertContainers.map((container) => container.innerHTML.slice(0, 200))),
  );
  check(
    "an inert render's links are still enhanced",
    enhanceCallFor("inert-0.md") !== undefined && enhanceCallFor("inert-1.md") !== undefined,
  );
  check(
    "an inert render runs the page's table of contents, not KPress's",
    globalThis.__markdownInertTocs.length === 2 &&
      globalThis.__markdownInertTocs[0].article.of === inertContainers[0] &&
      typeof globalThis.__markdownInertTocs[0].options.open === "function" &&
      globalThis.__markdownTocFallbackCalls === fallbackCallsBeforeInert,
    JSON.stringify([globalThis.__markdownInertTocs.length, globalThis.__markdownTocFallbackCalls]),
  );
  inertMounts[0].dispose();
  inertMounts[0].dispose();
  check(
    "disposing an inert mount releases its table of contents exactly once",
    globalThis.__markdownInertTocDisposals.length === 1 &&
      globalThis.__markdownInertTocDisposals[0].of === inertContainers[0] &&
      tocDisposals.length === kpressTocDisposalsBeforeInert,
    String(globalThis.__markdownInertTocDisposals.length),
  );
  inertMounts[1].dispose();
  elapseIdlePeriod();
  check(
    "no Worker outlives the idle period after the inert mounts",
    workers.every((worker) => worker.terminated),
  );

  if (failures.length) {
    console.error(`markdown mount FAILURES:\n- ${failures.join("\n- ")}`);
    process.exit(1);
  }
  console.log("markdown mount OK");
})().catch((error) => {
  console.error(error);
  process.exit(1);
});

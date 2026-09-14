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
  const importableSource = source
    .replace('"./link-enhancer.js"', JSON.stringify(enhancerUrl))
    .replace('"./markdown-worker-client.js"', JSON.stringify(workerClientUrl))
    .replace('"./toc-intersection-fallback.js"', JSON.stringify(tocFallbackUrl))
    .replace('"./transclusion.js"', JSON.stringify(transclusionUrl));
  const module = await import(
    `data:text/javascript;base64,${Buffer.from(importableSource).toString("base64")}`
  );
  const requests = [];
  const completeTextRequests = [];
  const tocDisposals = [];
  const mb = {
    escapeHtml: String,
    errors: { isAbortError: (error) => error?.name === "AbortError" },
    fetchKpressRender(ctx, _view, options) {
      return new Promise((resolve) => requests.push({ ctx, resolve, options }));
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
  check("the last mount's disposal terminates the shared Worker", workers[0].terminated);

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
  check(
    "every Worker is terminated once no mount remains",
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
  check(
    "no Worker outlives the last mount",
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

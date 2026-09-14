const fs = require("node:fs");
const path = require("node:path");

const repoRoot = path.resolve(process.argv[2]);
const failures = [];

function check(name, condition, detail = "failed") {
  if (!condition) {
    failures.push(`${name}: ${detail}`);
  }
}

class FakeElement {
  constructor(tagName, textContent = "") {
    this.attributes = new Map();
    this.innerHTML = "";
    this.parentElement = null;
    this.tagName = tagName.toUpperCase();
    this.textContent = textContent;
  }

  getAttribute(name) {
    return this.attributes.has(name) ? this.attributes.get(name) : null;
  }

  setAttribute(name, value) {
    this.attributes.set(name, value);
  }

  replaceWith(replacement) {
    const index = this.parentElement.elements.indexOf(this);
    this.parentElement.elements[index] = replacement;
    replacement.parentElement = this.parentElement;
    this.parentElement = null;
  }
}

class FakeContainer extends FakeElement {
  constructor(element) {
    super("main");
    this.elements = [element];
    this.ownerDocument = { createElement: (tagName) => new FakeElement(tagName) };
    element.parentElement = this;
  }
}

/**
 * Deterministic time for deadline checks. Date.now is pinned to the same value
 * while a scenario runs, so a regression back to wall-clock reads observes the
 * virtual time too instead of passing because real time barely moved.
 */
function createVirtualClock() {
  let now = 1_000_000;
  let sequence = 0;
  const timers = new Map();
  const nativeDateNow = Date.now;
  return {
    advance(milliseconds) {
      now += milliseconds;
      const due = [...timers.entries()]
        .filter(([, timer]) => timer.due <= now)
        .sort((left, right) => left[1].due - right[1].due);
      for (const [handle, timer] of due) {
        if (timers.delete(handle)) {
          timer.callback();
        }
      }
    },
    clearTimeout(handle) {
      timers.delete(handle);
    },
    install() {
      Date.now = () => now;
    },
    now: () => now,
    pending: () => timers.size,
    restore() {
      Date.now = nativeDateNow;
    },
    setTimeout(callback, delayMs) {
      sequence += 1;
      timers.set(sequence, { callback, due: now + delayMs });
      return sequence;
    },
  };
}

function settle() {
  return new Promise((resolve) => setImmediate(resolve));
}

async function loadModule() {
  const parserSource = fs.readFileSync(
    path.join(repoRoot, "src/metabrowser/builtin_plugins/markdown/wiki-parser.js"),
    "utf8",
  );
  const parserUrl = `data:text/javascript;base64,${Buffer.from(parserSource).toString("base64")}`;
  const tocFallbackStub =
    "export function initTocWithIntersectionFallback(init){" +
    "globalThis.__transclusionTocFallbackCalls=(globalThis.__transclusionTocFallbackCalls||0)+1;" +
    "return init()||(()=>{})}";
  const tocFallbackUrl = `data:text/javascript;base64,${Buffer.from(tocFallbackStub).toString("base64")}`;
  const workerStub =
    `import {prepareTransclusionMarkdownSource} from ${JSON.stringify(parserUrl)};` +
    "export function acquireMarkdownWorkerClient(){return {dispose(){}," +
    "run(_op,payload){return Promise.resolve(prepareTransclusionMarkdownSource(payload.source,payload.fragment))}}}";
  const workerUrl = `data:text/javascript;base64,${Buffer.from(workerStub).toString("base64")}`;
  const source = fs
    .readFileSync(
      path.join(repoRoot, "src/metabrowser/builtin_plugins/markdown/transclusion.js"),
      "utf8",
    )
    .replace('"./toc-intersection-fallback.js"', JSON.stringify(tocFallbackUrl))
    .replace('"./markdown-worker-client.js"', JSON.stringify(workerUrl));
  const [transclusion, parser] = await Promise.all([
    import(`data:text/javascript;base64,${Buffer.from(source).toString("base64")}`),
    import(parserUrl),
  ]);
  return { ...transclusion, selectTransclusionSource: parser.selectTransclusionSource };
}

(async () => {
  const module = await loadModule();
  const note = `# Intro
Overview.

## Install
First step.

### Details
More detail.

## Next
Later.

Paragraph first line
and second line ^block-id

\`\`\`
## Fenced
\`\`\`
`;

  const whole = module.selectTransclusionSource(note);
  check("whole note selected", whole.status === "selected" && whole.source === note);
  const heading = module.selectTransclusionSource(note, "obsidian-heading-Intro#Install");
  check("heading section selected", heading.status === "selected");
  check("heading includes descendants", heading.source.includes("### Details"));
  check("heading stops at sibling", !heading.source.includes("## Next"));
  const block = module.selectTransclusionSource(note, "obsidian-block-block-id");
  check("named block selected", block.status === "selected");
  check(
    "named block removes identifier",
    block.source.includes("Paragraph first line") && !block.source.includes("^block-id"),
  );
  const afterFence = module.selectTransclusionSource(
    "```md\nnot part of the block\n```\nBlock content ^after-fence\n",
    "obsidian-block-after-fence",
  );
  check(
    "named block stops at fenced block boundary",
    afterFence.status === "selected" && !afterFence.source.includes("not part"),
  );
  check(
    "missing location explicit",
    module.selectTransclusionSource(note, "obsidian-heading-Unknown").status === "missing",
  );

  const budget = module.createTransclusionBudget({ maxDocuments: 2 });
  const firstKey = module.transclusionKey("a.md");
  const first = await module.claimTransclusion(budget, firstKey, []);
  let cycleCode = null;
  try {
    await module.claimTransclusion(budget, module.transclusionKey("a.md"), first.chain);
  } catch (error) {
    cycleCode = error.code;
  }
  check("cycle rejected", cycleCode === "cycle");

  check(
    "whole-note location retains path without concatenation",
    firstKey.path === "a.md" && firstKey.fragment === "",
  );
  check(
    "location identity carries its fragment separately",
    module.transclusionKey("a.md", "obsidian-heading-One").fragment === "obsidian-heading-One",
  );
  // A rendered document is its own ancestor. Seeding the chain the way the
  // top-level renderer does makes a self-embed a cycle at the first embed
  // instead of rendering one complete duplicate before the repeat is caught.
  let selfEmbedCode = null;
  try {
    await module.claimTransclusion(
      module.createTransclusionBudget({}),
      module.transclusionKey("home.md"),
      [module.transclusionKey("home.md")],
    );
  } catch (error) {
    selfEmbedCode = error.code;
  }
  check("self-embed is a cycle at the first embed", selfEmbedCode === "cycle");

  const NativeMessageChannel = globalThis.MessageChannel;
  let cycleContinuations = 0;
  class CountingMessageChannel {
    constructor() {
      this.port1 = { close() {}, onmessage: null, start() {} };
      this.port2 = {
        close() {},
        postMessage: () => {
          cycleContinuations += 1;
          queueMicrotask(() => this.port1.onmessage?.());
        },
      };
    }
  }
  globalThis.MessageChannel = CountingMessageChannel;
  const providerLongPath = `${"p".repeat(2_000_000)}.md`;
  let longCycleCode = null;
  try {
    await module.claimTransclusion(
      module.createTransclusionBudget({ maxDurationMs: 15_000 }),
      module.transclusionKey(providerLongPath),
      [module.transclusionKey(` ${providerLongPath}`.slice(1))],
    );
  } catch (error) {
    longCycleCode = error.code;
  } finally {
    globalThis.MessageChannel = NativeMessageChannel;
  }
  check(
    "provider-long cycle identity is compared through bounded continuations",
    longCycleCode === "cycle" && cycleContinuations >= 122,
    `${longCycleCode}/${cycleContinuations}`,
  );
  // Elapsed time is bounded per claim, not per document. An embed whose catalog
  // resolution arrives long after an earlier embed claimed must still receive
  // its own full load budget.
  const claimClock = createVirtualClock();
  claimClock.install();
  try {
    const perClaimBudget = module.createTransclusionBudget(
      { maxDocuments: 2 },
      { clock: claimClock },
    );
    const earlyClaim = await module.claimTransclusion(
      perClaimBudget,
      module.transclusionKey("early.md"),
      [],
    );
    claimClock.advance(6_000);
    let lateClaim = null;
    let lateClaimCode = null;
    try {
      lateClaim = await module.claimTransclusion(
        perClaimBudget,
        module.transclusionKey("late.md"),
        [],
      );
    } catch (error) {
      lateClaimCode = error.code;
    }
    check(
      "a claim made after another claim's deadline receives its own deadline",
      lateClaim !== null && lateClaim.deadline === claimClock.now() + 5_000,
      String(lateClaimCode),
    );
    check(
      "each claim reports the deadline it started",
      earlyClaim.deadline === lateClaim?.deadline - 6_000,
    );
    let sharedDocumentCode = null;
    try {
      await module.claimTransclusion(perClaimBudget, module.transclusionKey("third.md"), []);
    } catch (error) {
      sharedDocumentCode = error.code;
    }
    check(
      "per-claim deadlines keep the aggregate document limit",
      sharedDocumentCode === "document-limit",
      String(sharedDocumentCode),
    );

    globalThis.MessageChannel = class AdvancingMessageChannel extends CountingMessageChannel {
      constructor() {
        super();
        const post = this.port2.postMessage;
        this.port2.postMessage = () => {
          claimClock.advance(3_000);
          post();
        };
      }
    };
    let slowCycleCode = null;
    try {
      await module.claimTransclusion(
        module.createTransclusionBudget({}, { clock: claimClock }),
        module.transclusionKey(providerLongPath),
        [module.transclusionKey(` ${providerLongPath}`.slice(1))],
      );
    } catch (error) {
      slowCycleCode = error.code;
    } finally {
      globalThis.MessageChannel = NativeMessageChannel;
    }
    check(
      "a claim whose own cycle comparison outlives its deadline times out",
      slowCycleCode === "timed-out",
      String(slowCycleCode),
    );
  } finally {
    claimClock.restore();
  }

  const source = new FakeElement("span", "Embedded setup");
  const container = new FakeContainer(source);
  let nestedDisposed = 0;
  let nestedSource = null;
  let tocDisposed = 0;
  const mb = {
    fetchKpressRender: async (_ctx, _view, options) => {
      check("selected source sent through KPress", options.sourceText.includes("## Install"));
      return { html: '<article class="kpress">Rendered</article>' };
    },
    fetchText: async () => note,
    kpressInitToc: () => () => (tocDisposed += 1),
  };
  const handle = module.mountWikiTransclusion(
    container,
    source,
    { fragment: "obsidian-heading-Intro#Install", path: "docs/note.md" },
    mb,
    {
      enhanceNested: (_element, nestedPath) => {
        nestedSource = nestedPath;
        return { dispose: () => (nestedDisposed += 1) };
      },
    },
  );
  const aside = container.elements[0];
  check("transclusion handle exposes its mounted element", handle.element === aside);
  check("loading transclusion accessible", aside.getAttribute("role") === "region");
  await new Promise((resolve) => setImmediate(resolve));
  check(
    "transclusion rendered",
    aside.getAttribute("data-metabrowser-transclusion-status") === "ready",
  );
  check("nested enhancement uses embedded source", nestedSource === "docs/note.md");
  check("embedded TOC uses observer fallback", globalThis.__transclusionTocFallbackCalls === 1);
  handle.dispose();
  check("nested enhancement disposed", nestedDisposed === 1);
  check("embedded table of contents disposed", tocDisposed === 1);

  // An embed that was pending before its catalog resolved keeps the status
  // text on its placeholder; the mounted note must use the recorded label.
  const formerlyPending = new FakeElement("span", "Setup (resolving link)");
  formerlyPending.setAttribute("data-mb-wiki-label", "Setup");
  const formerlyPendingContainer = new FakeContainer(formerlyPending);
  module
    .mountWikiTransclusion(formerlyPendingContainer, formerlyPending, { path: "docs/setup.md" }, mb)
    .dispose();
  check(
    "a formerly pending embed is labeled by its note, not its status",
    formerlyPendingContainer.elements[0].getAttribute("aria-label") === "Embedded note: Setup",
    formerlyPendingContainer.elements[0].getAttribute("aria-label"),
  );

  const cyclicSource = new FakeElement("span", "Cycle");
  const cyclicContainer = new FakeContainer(cyclicSource);
  module.mountWikiTransclusion(cyclicContainer, cyclicSource, { path: "a.md" }, mb, {
    budget,
    chain: first.chain,
  });
  await new Promise((resolve) => setImmediate(resolve));
  const cyclicAside = cyclicContainer.elements[0];
  check("cycle is accessible error", cyclicAside.getAttribute("role") === "alert");
  check(
    "cycle reason visible",
    cyclicAside.getAttribute("data-metabrowser-transclusion-error") === "cycle",
  );

  let pendingFetches = 0;
  const pendingSource = new FakeElement("span", "Pending");
  const pendingContainer = new FakeContainer(pendingSource);
  const pending = module.mountWikiTransclusion(
    pendingContainer,
    pendingSource,
    { path: "pending.md" },
    {
      ...mb,
      fetchText: (_target, _options) => {
        pendingFetches += 1;
        return new Promise(() => {});
      },
    },
  );
  pending.dispose();
  await Promise.resolve();
  check("dispose before asynchronous claim prevents source fetch", pendingFetches === 0);

  let preAbortedFetches = 0;
  const preAbortedController = new AbortController();
  preAbortedController.abort();
  const preAbortedSource = new FakeElement("span", "Already aborted");
  const preAbortedContainer = new FakeContainer(preAbortedSource);
  module.mountWikiTransclusion(
    preAbortedContainer,
    preAbortedSource,
    { path: "already-aborted.md" },
    {
      ...mb,
      fetchText: async () => {
        preAbortedFetches += 1;
        return note;
      },
    },
    { signal: preAbortedController.signal },
  );
  await new Promise((resolve) => setImmediate(resolve));
  check("pre-aborted transclusion does not fetch", preAbortedFetches === 0);

  const oversizedSource = new FakeElement("span", "Oversized");
  const oversizedContainer = new FakeContainer(oversizedSource);
  module.mountWikiTransclusion(
    oversizedContainer,
    oversizedSource,
    { path: "oversized.md" },
    {
      ...mb,
      fetchText: async () => {
        const error = new Error("source exceeds server limit");
        error.code = "source-too-large";
        throw error;
      },
    },
  );
  await new Promise((resolve) => setImmediate(resolve));
  check(
    "server source limit is visible",
    oversizedContainer.elements[0].getAttribute("data-metabrowser-transclusion-error") ===
      "source-too-large",
  );

  let incompleteRenders = 0;
  const incompleteSource = new FakeElement("span", "Expansion limited");
  const incompleteContainer = new FakeContainer(incompleteSource);
  module.mountWikiTransclusion(
    incompleteContainer,
    incompleteSource,
    { path: "expansion-limited.md" },
    {
      ...mb,
      fetchKpressRender: async () => {
        incompleteRenders += 1;
        return { html: "<article>must not render</article>" };
      },
    },
    {
      workerClient: {
        dispose() {},
        run: async () => ({
          changed: false,
          complete: false,
          diagnostics: [{ code: "transformed-source-byte-limit" }],
          kind: "note",
          source: note,
          status: "selected",
        }),
      },
    },
  );
  await new Promise((resolve) => setImmediate(resolve));
  check("incomplete preprocessing does not render", incompleteRenders === 0);
  check(
    "incomplete preprocessing exposes its diagnostic",
    incompleteContainer.elements[0].getAttribute("data-metabrowser-transclusion-error") ===
      "transformed-source-byte-limit",
  );

  const mountClock = createVirtualClock();
  mountClock.install();
  try {
    const mountBudget = module.createTransclusionBudget({}, { clock: mountClock });
    const quickSource = new FakeElement("span", "Quick");
    const quickContainer = new FakeContainer(quickSource);
    const quick = module.mountWikiTransclusion(
      quickContainer,
      quickSource,
      { path: "quick.md" },
      mb,
      { budget: mountBudget },
    );
    await settle();
    check(
      "the first embed renders",
      quickContainer.elements[0].getAttribute("data-metabrowser-transclusion-status") === "ready",
    );
    check("a settled embed releases its deadline timer", mountClock.pending() === 0);

    // The reported bug: a later embed whose catalog resolved six seconds after
    // the first embed was permanently timed out before it began loading.
    mountClock.advance(6_000);
    const laterSource = new FakeElement("span", "Later");
    const laterContainer = new FakeContainer(laterSource);
    const later = module.mountWikiTransclusion(
      laterContainer,
      laterSource,
      { path: "later.md" },
      mb,
      { budget: mountBudget },
    );
    await settle();
    check(
      "an embed that starts loading after another embed's budget elapsed still renders",
      laterContainer.elements[0].getAttribute("data-metabrowser-transclusion-status") === "ready",
      String(laterContainer.elements[0].getAttribute("data-metabrowser-transclusion-error")),
    );

    const slowSource = new FakeElement("span", "Slow");
    const slowContainer = new FakeContainer(slowSource);
    module.mountWikiTransclusion(
      slowContainer,
      slowSource,
      { path: "slow.md" },
      {
        ...mb,
        fetchText: (_target, options) =>
          new Promise((_resolve, reject) => {
            options.signal.addEventListener("abort", () => reject(options.signal.reason), {
              once: true,
            });
          }),
      },
      { budget: mountBudget },
    );
    await settle();
    mountClock.advance(4_999);
    await settle();
    check(
      "an embed inside its own budget keeps loading",
      slowContainer.elements[0].getAttribute("data-metabrowser-transclusion-status") === "loading",
    );
    mountClock.advance(1);
    await settle();
    check(
      "an embed whose own load exceeds its budget times out",
      slowContainer.elements[0].getAttribute("data-metabrowser-transclusion-error") === "timed-out",
      String(slowContainer.elements[0].getAttribute("data-metabrowser-transclusion-status")),
    );

    let settleIgnoringAbort = null;
    const stubbornSource = new FakeElement("span", "Stubborn");
    const stubbornContainer = new FakeContainer(stubbornSource);
    module.mountWikiTransclusion(
      stubbornContainer,
      stubbornSource,
      { path: "stubborn.md" },
      {
        ...mb,
        fetchText: () =>
          new Promise((resolve) => {
            settleIgnoringAbort = resolve;
          }),
      },
      { budget: mountBudget },
    );
    await settle();
    mountClock.advance(5_000);
    settleIgnoringAbort?.(note);
    await settle();
    check(
      "a load that settles after its deadline without observing the abort still times out",
      stubbornContainer.elements[0].getAttribute("data-metabrowser-transclusion-error") ===
        "timed-out",
      String(stubbornContainer.elements[0].getAttribute("data-metabrowser-transclusion-status")),
    );

    const disposedSource = new FakeElement("span", "Disposed");
    const disposedContainer = new FakeContainer(disposedSource);
    const disposedMount = module.mountWikiTransclusion(
      disposedContainer,
      disposedSource,
      { path: "disposed.md" },
      { ...mb, fetchText: () => new Promise(() => {}) },
      { budget: mountBudget },
    );
    await settle();
    check("a loading embed holds one deadline timer", mountClock.pending() === 1);
    disposedMount.dispose();
    check("disposal releases the deadline timer", mountClock.pending() === 0);
    quick.dispose();
    later.dispose();
  } finally {
    mountClock.restore();
  }

  if (failures.length) {
    console.error(`markdown transclusion FAILURES:\n- ${failures.join("\n- ")}`);
    process.exit(1);
  }
  console.log("markdown transclusion OK");
})().catch((error) => {
  console.error(error);
  process.exit(1);
});

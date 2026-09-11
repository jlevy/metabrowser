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
    "export function createMarkdownWorkerClient(){return {dispose(){}," +
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
  const expiringBudget = module.createTransclusionBudget({ maxDurationMs: 1 });
  await new Promise((resolve) => setTimeout(resolve, 5));
  let timeoutCode = null;
  try {
    await module.claimTransclusion(expiringBudget, module.transclusionKey("late.md"), []);
  } catch (error) {
    timeoutCode = error.code;
  }
  check("elapsed-time budget rejected", timeoutCode === "timed-out");

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

  if (failures.length) {
    console.error(`markdown transclusion FAILURES:\n- ${failures.join("\n- ")}`);
    process.exit(1);
  }
  console.log("markdown transclusion OK");
})().catch((error) => {
  console.error(error);
  process.exit(1);
});

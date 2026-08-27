const fs = require("node:fs");
const path = require("node:path");

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
    classList: { add() {} },
    querySelector() {
      return null;
    },
    prepend() {},
  };
}

(async () => {
  const source = fs.readFileSync(
    path.join(repoRoot, "src/metabrowser/builtin_plugins/markdown/rendered.js"),
    "utf8",
  );
  globalThis.__markdownEnhanceDisposals = [];
  globalThis.__markdownEnhanceCalls = [];
  const enhancerStub =
    "export function enhanceRenderedLinks(container,sourcePath,mb,options){" +
    "globalThis.__markdownEnhanceCalls.push({sourcePath,options});" +
    "return {dispose(){globalThis.__markdownEnhanceDisposals.push(container)}}}";
  const enhancerUrl = `data:text/javascript;base64,${Buffer.from(enhancerStub).toString("base64")}`;
  const wikiStub =
    "export function preprocessObsidianWiki(source){return {changed:source.includes('[[wiki]]'),source:'processed '+source}}";
  const wikiUrl = `data:text/javascript;base64,${Buffer.from(wikiStub).toString("base64")}`;
  // A recognizable stand-in rather than a copy of the key format: this test
  // proves the mount seeds a chain derived from ctx.path, and
  // markdown-transclusion-behavior.js covers the real key spelling.
  const transclusionStub = 'export function transclusionKey(path){return "key:" + path}';
  const transclusionUrl = `data:text/javascript;base64,${Buffer.from(transclusionStub).toString("base64")}`;
  const importableSource = source
    .replace('"./link-enhancer.js"', JSON.stringify(enhancerUrl))
    .replace('"./transclusion.js"', JSON.stringify(transclusionUrl))
    .replace('"./wiki-parser.js"', JSON.stringify(wikiUrl));
  const module = await import(
    `data:text/javascript;base64,${Buffer.from(importableSource).toString("base64")}`
  );
  const requests = [];
  const completeTextRequests = [];
  const tocDisposals = [];
  const mb = {
    escapeHtml: String,
    errors: { isAbortError: (error) => error?.name === "AbortError" },
    fetchKpressRender(_ctx, _view, options) {
      return new Promise((resolve) => requests.push({ resolve, options }));
    },
    async fetchCompleteText(ctx, options) {
      completeTextRequests.push({ ctx, options });
      return "[[wiki]]";
    },
    kpressInitToc(container) {
      return () => tocDisposals.push(container);
    },
  };
  const first = makeContainer();
  const second = makeContainer();
  const firstMount = module.mountRenderedMarkdown(first, { path: "a.md" }, mb);
  const secondMount = module.mountRenderedMarkdown(second, { path: "b.md" }, mb);
  check("first mount declares readiness", firstMount.ready instanceof Promise);
  check("second mount declares readiness", secondMount.ready instanceof Promise);
  check("independent requests", requests.length === 2, String(requests.length));
  requests[1].resolve({ html: "<article>second</article>", diagnostics: [] });
  requests[0].resolve({ html: "<article>first</article>", diagnostics: [] });
  await Promise.all([firstMount.ready, secondMount.ready]);
  const firstHandle = firstMount;
  const secondHandle = secondMount;
  check("first painted", first.innerHTML.includes("first"), first.innerHTML);
  check("second painted", second.innerHTML.includes("second"), second.innerHTML);
  firstHandle.dispose();
  firstHandle.dispose();
  check("first disposer exactly once", tocDisposals.length === 1, String(tocDisposals.length));
  check(
    "first enhancer disposer exactly once",
    globalThis.__markdownEnhanceDisposals.length === 1,
    String(globalThis.__markdownEnhanceDisposals.length),
  );
  // A rendered document is its own transclusion ancestor. Without this seed a
  // note embedding itself renders one complete duplicate before the repeat is
  // caught one level down.
  const enhanceCall = globalThis.__markdownEnhanceCalls.find((call) => call.sourcePath === "a.md");
  check(
    "mount seeds its own transclusion ancestry",
    JSON.stringify(enhanceCall?.options?.transclusionChain) === JSON.stringify(["key:a.md"]),
    JSON.stringify(globalThis.__markdownEnhanceCalls),
  );
  check("second remains mounted", !tocDisposals.includes(second));
  secondHandle.dispose();
  check("second disposer", tocDisposals.length === 2, String(tocDisposals.length));
  check("second enhancer disposer", globalThis.__markdownEnhanceDisposals.length === 2);

  const pending = makeContainer();
  const pendingHandle = module.mountRenderedMarkdown(pending, { path: "pending.md" }, mb);
  const pendingSignal = requests[2].options.signal;
  pendingHandle.dispose();
  check("direct disposer aborts pending request", pendingSignal.aborted === true);
  requests[2].resolve({ html: "<article>too late</article>", diagnostics: [] });
  await pendingHandle.ready;
  check("disposed direct completion ignored", !pending.innerHTML.includes("too late"));

  const late = makeContainer();
  const controller = new AbortController();
  const lateMount = module.mountRenderedMarkdown(late, { path: "late.md" }, mb, {
    signal: controller.signal,
  });
  controller.abort();
  requests[3].resolve({ html: "<article>too late</article>", diagnostics: [] });
  await lateMount.ready;
  const lateHandle = lateMount;
  check("late completion ignored", !late.innerHTML.includes("too late"), late.innerHTML);
  lateHandle.dispose();

  const wiki = makeContainer();
  const wikiMount = module.mountRenderedMarkdown(
    wiki,
    { path: "wiki.md", raw: { content: "[[wiki]]" } },
    mb,
  );
  check(
    "wiki source sent after source-aware preprocessing",
    requests[4].options.sourceText === "processed [[wiki]]",
  );
  requests[4].resolve({ html: "<article>wiki</article>", diagnostics: [] });
  await wikiMount.ready;
  wikiMount.dispose();

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
  await new Promise((resolve) => setImmediate(resolve));
  check("truncated wiki requests complete source", completeTextRequests.length === 1);
  check(
    "complete source request is abortable",
    completeTextRequests[0].options.signal instanceof AbortSignal,
  );
  check(
    "complete wiki source is preprocessed",
    requests[5].options.sourceText === "processed [[wiki]]",
  );
  requests[5].resolve({ html: "<article>large wiki</article>", diagnostics: [] });
  await truncatedWikiMount.ready;
  truncatedWikiMount.dispose();

  if (failures.length) {
    console.error(`markdown mount FAILURES:\n- ${failures.join("\n- ")}`);
    process.exit(1);
  }
  console.log("markdown mount OK");
})();

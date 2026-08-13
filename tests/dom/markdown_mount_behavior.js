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
  const module = await import(
    `data:text/javascript;base64,${Buffer.from(source).toString("base64")}`
  );
  const requests = [];
  const tocDisposals = [];
  const mb = {
    escapeHtml: String,
    errors: { isAbortError: (error) => error?.name === "AbortError" },
    fetchKpressRender(_ctx, _view, options) {
      return new Promise((resolve) => requests.push({ resolve, options }));
    },
    kpressInitToc(container) {
      return () => tocDisposals.push(container);
    },
  };
  const first = makeContainer();
  const second = makeContainer();
  const firstMount = module.mountRenderedMarkdown(first, { path: "a.md" }, mb);
  const secondMount = module.mountRenderedMarkdown(second, { path: "b.md" }, mb);
  check("independent requests", requests.length === 2, String(requests.length));
  requests[1].resolve({ html: "<article>second</article>", diagnostics: [] });
  requests[0].resolve({ html: "<article>first</article>", diagnostics: [] });
  const [firstHandle, secondHandle] = await Promise.all([firstMount, secondMount]);
  check("first painted", first.innerHTML.includes("first"), first.innerHTML);
  check("second painted", second.innerHTML.includes("second"), second.innerHTML);
  firstHandle.dispose();
  firstHandle.dispose();
  check("first disposer exactly once", tocDisposals.length === 1, String(tocDisposals.length));
  check("second remains mounted", !tocDisposals.includes(second));
  secondHandle.dispose();
  check("second disposer", tocDisposals.length === 2, String(tocDisposals.length));

  const pending = makeContainer();
  const pendingHandle = module.mountRenderedMarkdown(pending, { path: "pending.md" }, mb);
  const pendingSignal = requests[2].options.signal;
  pendingHandle.dispose();
  check("direct disposer aborts pending request", pendingSignal.aborted === true);
  requests[2].resolve({ html: "<article>too late</article>", diagnostics: [] });
  await new Promise((resolve) => setImmediate(resolve));
  check("disposed direct completion ignored", !pending.innerHTML.includes("too late"));

  const late = makeContainer();
  const controller = new AbortController();
  const lateMount = module.mountRenderedMarkdown(late, { path: "late.md" }, mb, {
    signal: controller.signal,
  });
  controller.abort();
  requests[3].resolve({ html: "<article>too late</article>", diagnostics: [] });
  const lateHandle = await lateMount;
  check("late completion ignored", !late.innerHTML.includes("too late"), late.innerHTML);
  lateHandle.dispose();

  if (failures.length) {
    console.error(`markdown mount FAILURES:\n- ${failures.join("\n- ")}`);
    process.exit(1);
  }
  console.log("markdown mount OK");
})();

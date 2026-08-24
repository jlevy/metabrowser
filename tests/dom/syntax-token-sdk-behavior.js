// DOM-free behavioral contracts for mb.highlightSyntax.

const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const repoRoot = path.resolve(process.argv[2]);

function check(condition, message) {
  if (!condition) {
    throw new Error(message);
  }
}

function createSandbox() {
  const listeners = new Map();
  const documentListeners = new Map();
  const sandbox = {
    AbortController,
    DOMException,
    Map,
    Promise,
    Set,
    TextEncoder,
    URL,
    clearInterval,
    clearTimeout,
    console,
    fetch: () => Promise.reject(new Error("fetch unavailable in syntax SDK test")),
    location: { origin: "http://localhost" },
    setInterval,
    setTimeout,
    addEventListener(type, listener) {
      const entries = listeners.get(type) ?? [];
      entries.push(listener);
      listeners.set(type, entries);
    },
    removeEventListener(type, listener) {
      listeners.set(
        type,
        (listeners.get(type) ?? []).filter((entry) => entry !== listener),
      );
    },
    dispatchEvent(event) {
      for (const listener of listeners.get(event.type) ?? []) {
        listener(event);
      }
      return true;
    },
    document: {
      cookie: "",
      head: { append() {} },
      body: { append() {} },
      documentElement: { getAttribute: () => null },
      addEventListener(type, listener) {
        const entries = documentListeners.get(type) ?? [];
        entries.push(listener);
        documentListeners.set(type, entries);
      },
      createElement(tag) {
        return {
          tagName: String(tag).toUpperCase(),
          addEventListener() {},
          append() {},
          getAttribute: () => null,
          setAttribute() {},
        };
      },
    },
  };
  sandbox.window = sandbox;
  sandbox.globalThis = sandbox;
  vm.createContext(sandbox);
  return sandbox;
}

function load(sandbox, relativePath) {
  const filename = path.basename(relativePath);
  vm.runInContext(fs.readFileSync(path.join(repoRoot, relativePath), "utf-8"), sandbox, {
    filename,
  });
}

function loadSdk(sandbox) {
  for (const filename of [
    "request-error.js",
    "formatters.js",
    "inventory-scope.js",
    "resource-context.js",
    "view-state.js",
    "navigation.js",
  ]) {
    load(sandbox, `src/metabrowser/static/${filename}`);
  }
  load(sandbox, "src/metabrowser/static/plugin-sdk.js");
}

async function main() {
  const ready = createSandbox();
  load(ready, "src/metabrowser/static/vendor/highlight.min.js");
  loadSdk(ready);

  const source = "/* first line\n+ * second line */";
  const lines = await ready.metabrowser.highlightSyntax(source, "javascript");
  check(Array.isArray(lines), "ready grammar should return token lines");
  check(lines.length === 2, `expected two token lines, got ${lines.length}`);
  check(
    lines.map((runs) => runs.map((run) => run.text).join("")).join("\n") === source,
    "token line text must round-trip exactly",
  );
  check(
    lines.every((runs) => runs.some((run) => run.classes.includes("hljs-comment"))),
    "a multiline token class must remain active across the newline",
  );
  check(
    lines.every((runs) => runs.every((run) => !Object.hasOwn(run, "nodeType"))),
    "token runs must be plain data rather than DOM nodes",
  );
  const trailing = await ready.metabrowser.highlightSyntax("const value = 1;\n", "javascript");
  check(trailing?.length === 2, "a trailing newline must retain its empty final token line");

  const vendoredEntities = ready.hljs.highlight("&<>\"'", {
    language: "plaintext",
    ignoreIllegals: true,
  }).value;
  check(
    vendoredEntities === "&amp;&lt;&gt;&quot;&#x27;",
    `vendored Highlight.js entity vocabulary changed: ${vendoredEntities}`,
  );

  let highlightOptions = null;
  ready.hljs = {
    getLanguage: () => true,
    highlight(_text, options) {
      highlightOptions = options;
      return {
        value:
          '<span class="hljs-string">&amp;&lt;&gt;&quot;&#x27;</span>' +
          '<span class="hljs-variable language_">x</span>',
      };
    },
  };
  const entityLines = await ready.metabrowser.highlightSyntax("&<>\"'x", "javascript");
  check(entityLines?.[0]?.map((run) => run.text).join("") === "&<>\"'x", "entities decode");
  check(
    entityLines?.[0]?.at(-1)?.classes.includes("language_") === true,
    "validated Highlight.js helper classes should survive",
  );
  check(highlightOptions?.ignoreIllegals === true, "lexer calls must ignore illegal lexemes");

  const malformedMarkup = [
    "<em>plain</em>",
    '<span id="x" class="hljs-keyword">plain</span>',
    '<span class="plain">plain</span>',
    '<span class="hljs-keyword invalid!">plain</span>',
    "&nbsp;",
    '<span class="hljs-keyword">plain',
  ];
  for (const value of malformedMarkup) {
    ready.hljs.highlight = () => ({ value });
    check(
      (await ready.metabrowser.highlightSyntax("plain", "javascript")) === null,
      `malformed highlighter markup should return null: ${value}`,
    );
  }
  ready.hljs.highlight = () => {
    throw new Error("simulated grammar failure");
  };
  check(
    (await ready.metabrowser.highlightSyntax("plain", "javascript")) === null,
    "lexer exceptions should return null",
  );

  const bounded = createSandbox();
  bounded.METABROWSER_SETTINGS = { SYNTAX_HIGHLIGHT_MAX_BYTES: 4 };
  load(bounded, "src/metabrowser/static/vendor/highlight.min.js");
  loadSdk(bounded);
  check(
    Array.isArray(await bounded.metabrowser.highlightSyntax("éé", "javascript")),
    "UTF-8 input at the injected byte bound should highlight",
  );
  check(
    (await bounded.metabrowser.highlightSyntax("ééx", "javascript")) === null,
    "UTF-8 input beyond the injected byte bound should stay plain",
  );
  check(
    bounded.metabrowser.isLargeTextPreview({ content: "éé" }) === false &&
      bounded.metabrowser.isLargeTextPreview({ content: "ééx" }) === true,
    "regular previews and syntax tokens should share the injected UTF-8 byte bound",
  );

  const delayed = createSandbox();
  loadSdk(delayed);
  let settled = false;
  const pending = delayed.metabrowser
    .highlightSyntax("const value = 1;", "javascript")
    .then((value) => {
      settled = true;
      return value;
    });
  await new Promise((resolve) => setTimeout(resolve, 0));
  check(!settled, "syntax request should wait while prefetched assets are pending");
  load(delayed, "src/metabrowser/static/vendor/highlight.min.js");
  delayed.dispatchEvent({ type: "metabrowser:optional-asset-loaded" });
  const delayedLines = await pending;
  check(Array.isArray(delayedLines), "an individual asset event should settle a ready grammar");

  const unavailable = createSandbox();
  loadSdk(unavailable);
  const missing = unavailable.metabrowser.highlightSyntax("plain", "not-a-language");
  unavailable.dispatchEvent({ type: "metabrowser:optional-assets-loaded" });
  check((await missing) === null, "terminal asset failure should settle to null");
  check(
    (await unavailable.metabrowser.highlightSyntax("plain", "not-a-language")) === null,
    "unknown language after terminal settlement should return null immediately",
  );

  const aborting = createSandbox();
  loadSdk(aborting);
  const controller = new AbortController();
  const aborted = aborting.metabrowser.highlightSyntax("plain", "javascript", {
    signal: controller.signal,
  });
  controller.abort();
  let abortName = "";
  try {
    await aborted;
  } catch (error) {
    abortName = error?.name ?? "";
  }
  check(abortName === "AbortError", `expected AbortError, got ${abortName || "no rejection"}`);
  console.log("syntax token SDK OK");
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});

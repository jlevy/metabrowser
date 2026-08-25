// DOM-free behavioral contracts for mb.highlightSyntax.

const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const repoRoot = path.resolve(process.argv[2]);
const syntaxSettings = JSON.parse(process.argv[3]);
const syntaxLanguageByBasename = syntaxSettings.SYNTAX_LANGUAGE_BY_BASENAME;
const syntaxLanguageByExtension = syntaxSettings.SYNTAX_LANGUAGE_BY_EXTENSION;

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
    METABROWSER_SETTINGS: {
      SYNTAX_HIGHLIGHT_MAX_BYTES: 512 * 1024,
      SYNTAX_LANGUAGE_BY_BASENAME: syntaxLanguageByBasename,
      SYNTAX_LANGUAGE_BY_EXTENSION: syntaxLanguageByExtension,
    },
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
  load(ready, "src/metabrowser/static/vendor/highlight-toml.min.js");
  loadSdk(ready);
  const readySyntaxFallbacks = [];
  ready.metabrowser.perf = {
    measure(label, work, metadata) {
      readySyntaxFallbacks.push({ label, metadata });
      return work();
    },
    measureAsync(_label, work) {
      return work();
    },
  };

  for (const [extension, language] of Object.entries(syntaxLanguageByExtension)) {
    check(
      ready.hljs.getLanguage(language),
      `${extension} maps to unavailable shipped grammar ${language}`,
    );
    check(
      ready.metabrowser.langForExtension(extension) === language,
      `${extension} should resolve through the injected registry`,
    );
  }
  for (const [basename, language] of Object.entries(syntaxLanguageByBasename)) {
    check(ready.hljs.getLanguage(language), `${basename} maps to unavailable grammar ${language}`);
    check(
      ready.metabrowser.langForPath(`nested/${basename}`) === language,
      `${basename} should resolve through the injected basename registry`,
    );
  }
  check(ready.metabrowser.langForExtension(".unknown") === "", "unknown extensions stay plain");
  check(ready.metabrowser.langForPath("Makefile.gz") === "makefile", "compressed names resolve");
  check(ready.metabrowser.langForPath("nested/example.rs") === "rust", "paths infer extensions");

  const sourceContainer = {
    classList: {
      add(name) {
        this.added = name;
      },
    },
    innerHTML: "",
  };
  ready.metabrowser.renderSourceView(sourceContainer, {
    content: "const literal = '<script>';",
    ext: ".ts",
  });
  check(
    sourceContainer.classList.added === "metabrowser-source-host",
    "shared source renderer should install the host class",
  );
  check(
    sourceContainer.innerHTML.includes('class="language-typescript"'),
    "shared source renderer should use the injected grammar mapping",
  );
  check(
    sourceContainer.innerHTML.includes("&lt;script&gt;") &&
      !sourceContainer.innerHTML.includes("'<script>'"),
    "shared source renderer should escape exact source text",
  );
  ready.metabrowser.renderSourceView(sourceContainer, {
    content: "target:\n\tbuild\n",
    ext: "",
    path: "nested/Makefile",
  });
  check(
    sourceContainer.innerHTML.includes('class="language-makefile"'),
    "shared source renderer should highlight extensionless source names",
  );

  const markdownSource = fs.readFileSync(
    path.join(repoRoot, "src/metabrowser/builtin_plugins/markdown/source.js"),
    "utf-8",
  );
  const markdownModule = await import(
    `data:text/javascript;base64,${Buffer.from(markdownSource).toString("base64")}`
  );
  const markdownText = "---\ntitle: Example\n---\n# Heading\n";
  const markdownHtml = markdownModule.renderMarkdownSourceHtml(
    { content: markdownText },
    {
      renderTextTruncationWarning: () => "TOP",
      renderTextLoadMoreFooter: () => "BOTTOM",
      isLargeTextPreview: () => false,
      escapeHtml: (value) =>
        String(value).replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;"),
      wrapWithCopy: (html) => `<div>${html}</div>`,
    },
  );
  check(markdownHtml.startsWith("TOP<div>"), "Markdown Source should retain its top notice");
  check(markdownHtml.endsWith("</div>BOTTOM"), "Markdown Source should retain its footer");
  check(
    markdownHtml.includes(
      `<code data-mb-copy-payload class="no-highlight" hidden>${markdownText}</code>`,
    ),
    "frontmatter Source should retain one exact whole-document copy payload",
  );
  check(
    markdownHtml.includes('<code class="language-yaml">---\ntitle: Example\n---\n</code>'),
    "the YAML segment should retain the closing-delimiter newline",
  );
  const markdownCrLf = "---\r\ntitle: Example\r\n---\r\n<script>\r\n";
  const markdownCrLfHtml = markdownModule.renderMarkdownSourceHtml(
    { content: markdownCrLf },
    {
      renderTextTruncationWarning: () => "",
      renderTextLoadMoreFooter: () => "",
      isLargeTextPreview: () => false,
      escapeHtml: (value) =>
        String(value).replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;"),
      wrapWithCopy: (html) => html,
    },
  );
  check(
    markdownCrLfHtml.includes("---\r\ntitle: Example\r\n---\r\n</code>"),
    "CRLF frontmatter should retain its exact line endings",
  );
  check(
    markdownCrLfHtml.includes("&lt;script&gt;\r\n") && !markdownCrLfHtml.includes("<script>\r\n"),
    "frontmatter Source should escape its whole-document payload and visible body",
  );

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
  check(
    readySyntaxFallbacks.filter(({ label }) => label === "syntaxHighlight:fallback:markup_rejected")
      .length === malformedMarkup.length,
    "rejected markup should expose one fixed fallback reason per request",
  );
  check(
    readySyntaxFallbacks.at(-1)?.label === "syntaxHighlight:fallback:lexer_threw" &&
      readySyntaxFallbacks.at(-1)?.metadata.language === "javascript" &&
      readySyntaxFallbacks.at(-1)?.metadata.input_bytes === 5,
    "lexer exceptions should expose bounded diagnostic metadata",
  );

  const bounded = createSandbox();
  bounded.METABROWSER_SETTINGS = {
    SYNTAX_HIGHLIGHT_MAX_BYTES: 4,
    SYNTAX_LANGUAGE_BY_BASENAME: syntaxLanguageByBasename,
    SYNTAX_LANGUAGE_BY_EXTENSION: syntaxLanguageByExtension,
  };
  load(bounded, "src/metabrowser/static/vendor/highlight.min.js");
  loadSdk(bounded);
  const boundedSyntaxFallbacks = [];
  bounded.metabrowser.perf = {
    measure(label, work, metadata) {
      boundedSyntaxFallbacks.push({ label, metadata });
      return work();
    },
    measureAsync(_label, work) {
      return work();
    },
  };
  check(
    Array.isArray(await bounded.metabrowser.highlightSyntax("éé", "javascript")),
    "UTF-8 input at the injected byte bound should highlight",
  );
  check(
    (await bounded.metabrowser.highlightSyntax("ééx", "javascript")) === null,
    "UTF-8 input beyond the injected byte bound should stay plain",
  );
  check(
    boundedSyntaxFallbacks.length === 1 &&
      boundedSyntaxFallbacks[0].label === "syntaxHighlight:fallback:over_limit" &&
      boundedSyntaxFallbacks[0].metadata.input_bytes === 5,
    "over-limit input should expose its measured fallback reason",
  );
  check(
    bounded.metabrowser.isLargeTextPreview({ content: "éé" }) === false &&
      bounded.metabrowser.isLargeTextPreview({ content: "ééx" }) === true,
    "regular previews and syntax tokens should share the injected UTF-8 byte bound",
  );
  check(
    bounded.metabrowser.isLargeTextPreview({
      content: "éé",
      content_truncated: true,
      size: 1_000_000,
    }) === false,
    "a bounded loaded prefix should highlight even when the backing file is larger",
  );
  check(
    bounded.metabrowser.isLargeTextPreview({ content: "éé", highlight_disabled: true }) === true,
    "an explicit server decision should disable highlighting",
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
  const unavailableSyntaxFallbacks = [];
  unavailable.metabrowser.perf = {
    measure(label, work, metadata) {
      unavailableSyntaxFallbacks.push({ label, metadata });
      return work();
    },
    measureAsync(_label, work) {
      return work();
    },
  };
  const missing = unavailable.metabrowser.highlightSyntax("plain", "not-a-language");
  unavailable.dispatchEvent({ type: "metabrowser:optional-assets-loaded" });
  check((await missing) === null, "terminal asset failure should settle to null");
  check(
    (await unavailable.metabrowser.highlightSyntax("plain", "not-a-language")) === null,
    "unknown language after terminal settlement should return null immediately",
  );
  check(
    unavailableSyntaxFallbacks.length === 2 &&
      unavailableSyntaxFallbacks.every(
        ({ label, metadata }) =>
          label === "syntaxHighlight:fallback:no_grammar" &&
          metadata.language === "not-a-language" &&
          metadata.input_bytes === 5,
      ),
    "unknown grammars should expose a fixed fallback reason before and after settlement",
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

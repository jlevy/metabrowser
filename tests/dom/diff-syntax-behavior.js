// Pure semantic-model checks for side-specific diff syntax data.

const path = require("node:path");
const { pathToFileURL } = require("node:url");

const repoRoot = path.resolve(process.argv[2]);
const failures = [];

function check(label, condition, detail = "") {
  if (!condition) {
    failures.push(`${label}${detail ? `: ${detail}` : ""}`);
  }
}

function tokenLines(source, side) {
  return source.split("\n").map((text) => [{ classes: [`hljs-${side}`], text }]);
}

async function main() {
  const modelModulePath = path.join(
    repoRoot,
    "src/metabrowser/builtin_plugins/diff/diff-render-model.js",
  );
  const syntaxModulePath = path.join(
    repoRoot,
    "src/metabrowser/builtin_plugins/diff/diff-syntax.js",
  );
  const { buildFileRenderModel } = await import(pathToFileURL(modelModulePath).href);
  const { highlightFileSyntax, syntaxInputBytes } = await import(
    pathToFileURL(syntaxModulePath).href
  );

  const change = {
    id: "renamed",
    kind: "renamed",
    old: { path: "before/example.js" },
    new: { path: "after/example.py" },
  };
  const patch = {
    file_id: "renamed",
    truncated: false,
    hunks: [
      {
        old_start: 10,
        old_count: 3,
        new_start: 20,
        new_count: 3,
        heading: "example",
        lines: [
          { op: "context", text: "/* open" },
          { op: "del", text: "old */" },
          { op: "add", text: "new" },
          { op: "context", text: "tail */", no_newline: true },
        ],
      },
      {
        old_start: 30,
        old_count: 1,
        new_start: 40,
        new_count: 1,
        lines: [{ op: "context", text: "* omitted opener */" }],
      },
    ],
  };
  const resolvedPaths = [];
  const languageForPath = (sourcePath) => {
    resolvedPaths.push(sourcePath);
    return sourcePath.endsWith(".js") ? "javascript" : sourcePath.endsWith(".py") ? "python" : "";
  };
  const model = buildFileRenderModel(change, patch, languageForPath);
  check("old rename language", model.oldLanguage === "javascript", model.oldLanguage);
  check("new rename language", model.newLanguage === "python", model.newLanguage);
  check(
    "language resolver receives full side paths",
    JSON.stringify(resolvedPaths) === '["after/example.py","before/example.js"]',
    JSON.stringify(resolvedPaths),
  );
  check("every hunk stays separate", model.hunks.length === 2, String(model.hunks.length));

  const records = model.hunks[0].lines;
  check(
    "old numbering",
    JSON.stringify(records.map((line) => line.oldNumber)) === "[10,11,null,12]",
  );
  check(
    "new numbering",
    JSON.stringify(records.map((line) => line.newNumber)) === "[20,null,21,22]",
  );
  check("no-newline metadata", records[3].noNewline === true);
  check("changed run identity", records[1].changedRun === 0 && records[2].changedRun === 0);
  check(
    "old stream reconstruction",
    model.hunks[0].oldSource === "/* open\nold */\ntail */",
    model.hunks[0].oldSource,
  );
  check(
    "new stream reconstruction",
    model.hunks[0].newSource === "/* open\nnew\ntail */",
    model.hunks[0].newSource,
  );
  const expectedBytes = model.hunks.reduce(
    (total, hunk) =>
      total +
      new TextEncoder().encode(hunk.oldSource).length +
      new TextEncoder().encode(hunk.newSource).length,
    0,
  );
  check("model construction defers UTF-8 measurement", model.inputBytes === null);
  check(
    "hunk-side UTF-8 measurement starts empty",
    model.hunks.every((hunk) => hunk.oldInputBytes === null && hunk.newInputBytes === null),
  );
  check("lazy combined UTF-8 input is exact", syntaxInputBytes(model.hunks) === expectedBytes);

  const calls = [];
  const highlighted = await highlightFileSyntax(
    model,
    {
      isLargeTextPreview: () => false,
      async highlightSyntax(source, language, options) {
        calls.push({ source, language, inputBytes: options?.inputBytes });
        return tokenLines(source, language === "javascript" ? "old" : "new");
      },
    },
    undefined,
  );
  check("two lexer calls per nonempty hunk", calls.length === 4, String(calls.length));
  check(
    "each hunk side carries its cached UTF-8 byte count",
    calls.every(
      ({ source, inputBytes }) => new TextEncoder().encode(source).byteLength === inputBytes,
    ),
  );
  check("highlight stores the combined byte count", model.inputBytes === expectedBytes);
  check(
    "omitted lexical state never crosses hunk boundaries",
    calls[2].source === "* omitted opener */" && calls[3].source === "* omitted opener */",
  );
  check("file reports enhancement", highlighted === true);
  check("deletion receives only old tokens", records[1].oldTokens?.[0]?.text === "old */");
  check("deletion has no new tokens", records[1].newTokens === null);
  check("addition receives only new tokens", records[2].newTokens?.[0]?.text === "new");
  check("addition has no old tokens", records[2].oldTokens === null);
  check(
    "context retains distinct side tokens",
    records[0].oldTokens?.[0]?.classes[0] === "hljs-old" &&
      records[0].newTokens?.[0]?.classes[0] === "hljs-new",
  );

  const overLimitModel = buildFileRenderModel(change, patch, languageForPath);
  let overLimitCalls = 0;
  const overLimit = await highlightFileSyntax(
    overLimitModel,
    {
      isLargeTextPreview: ({ size }) => size === overLimitModel.inputBytes,
      async highlightSyntax() {
        overLimitCalls += 1;
        return [];
      },
    },
    undefined,
  );
  check("over-limit file stays wholly plain", overLimit === false && overLimitCalls === 0);

  const invalidModel = buildFileRenderModel(change, patch, languageForPath);
  const originalWarn = console.warn;
  let warningCount = 0;
  console.warn = () => {
    warningCount += 1;
  };
  await highlightFileSyntax(
    invalidModel,
    {
      isLargeTextPreview: () => false,
      async highlightSyntax(source, language) {
        return language === "javascript"
          ? [[{ classes: [], text: `${source}!` }]]
          : tokenLines(source, "new");
      },
    },
    undefined,
  );
  console.warn = originalWarn;
  check(
    "round-trip mismatch leaves old side plain",
    invalidModel.hunks[0].lines[0].oldTokens === null,
  );
  check(
    "mismatch reports one diagnostic per rejected side",
    warningCount === 2,
    String(warningCount),
  );

  const addedModel = buildFileRenderModel(
    { id: "added", new: { path: "only.js" } },
    {
      hunks: [
        {
          old_start: 0,
          old_count: 0,
          new_start: 1,
          new_count: 1,
          lines: [{ op: "add", text: "const added = true;" }],
        },
      ],
    },
    languageForPath,
  );
  let addedCalls = 0;
  await highlightFileSyntax(
    addedModel,
    {
      isLargeTextPreview: () => false,
      async highlightSyntax(source) {
        addedCalls += 1;
        return tokenLines(source, "new");
      },
    },
    undefined,
  );
  check("an added file lexes only its new side", addedCalls === 1, String(addedCalls));

  const unknownModel = buildFileRenderModel(change, patch, () => "");
  let unknownCalls = 0;
  const unknown = await highlightFileSyntax(
    unknownModel,
    {
      isLargeTextPreview: () => false,
      async highlightSyntax() {
        unknownCalls += 1;
        return [];
      },
    },
    undefined,
  );
  check("unknown side languages stay plain", unknown === false && unknownCalls === 0);

  const abortedModel = buildFileRenderModel(change, patch, languageForPath);
  const controller = new AbortController();
  let releaseIgnoredAbort;
  const ignoredAbort = highlightFileSyntax(
    abortedModel,
    {
      isLargeTextPreview: () => false,
      highlightSyntax: () =>
        new Promise((resolve) => {
          releaseIgnoredAbort = resolve;
        }),
    },
    controller.signal,
  );
  controller.abort();
  releaseIgnoredAbort(tokenLines(abortedModel.hunks[0].oldSource, "late"));
  let abortName = "";
  try {
    await ignoredAbort;
  } catch (error) {
    abortName = error?.name ?? "";
  }
  check("abort is rechecked after an uncooperative helper", abortName === "AbortError", abortName);
  check(
    "late helper output never mutates cached tokens",
    abortedModel.hunks[0].lines.every((line) => line.oldTokens === null),
  );

  if (failures.length > 0) {
    for (const failure of failures) {
      console.error(failure);
    }
    process.exit(1);
  }
  console.log("diff syntax OK");
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});

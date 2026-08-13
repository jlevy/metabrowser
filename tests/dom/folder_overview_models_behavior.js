const fs = require("node:fs");
const path = require("node:path");

const repoRoot = path.resolve(process.argv[2]);
const failures = [];

function check(name, condition, detail = "failed") {
  if (!condition) {
    failures.push(`${name}: ${detail}`);
  }
}

async function importSource(relative) {
  const source = fs.readFileSync(path.join(repoRoot, relative), "utf8");
  return import(`data:text/javascript;base64,${Buffer.from(source).toString("base64")}`);
}

(async () => {
  const modelModule = await importSource(
    "src/metabrowser/builtin_plugins/folder/file_type_summary_model.js",
  );
  const paletteModule = await importSource(
    "src/metabrowser/builtin_plugins/folder/category_palette.js",
  );
  const treemapModel = await importSource(
    "src/metabrowser/builtin_plugins/folder/treemap_model.js",
  );

  const formatters = {
    formatFileCount: (value) => `${value} ${value === 1 ? "file" : "files"}`,
    formatInteger: String,
    formatSize: (value) => `${value} B`,
  };
  const raw = {
    path: "src",
    index_status: "done",
    indexed_files: 157,
    max_files: 500000,
    truncated: false,
    node: {
      total_files: 157,
      total_size: 11000000,
      unignored_files: 150,
      unignored_size: 10000000,
    },
    ext_tallies: [
      [".py", 150, 10000000, 145, 9500000],
      [".md", 7, 1000000, 5, 500000],
    ],
  };
  const normalized = modelModule.normalizeRollupEnvelope(raw);
  check(
    "rollup tail has a distinct row label",
    modelModule.normalizeTallyRow(["", 1, 1, 1, 1]).label === "Remaining types",
  );
  const classifyCategory = modelModule.createFileTypeCategoryClassifier([
    { id: "docs", values: [".md", ".txt"] },
    { id: "code", values: [".py", ".ts", ".js"] },
    { id: "data", values: [".json", ".jsonl"] },
  ]);
  const visible = modelModule.buildFileTypeSummaryModel(
    normalized,
    true,
    formatters,
    classifyCategory,
  );
  check("populated model", visible.state === "populated", visible.state);
  check("server order retained", visible.rows.map((row) => row.key).join(",") === ".py,.md");
  check(
    "files and size both present",
    visible.rows[0].files === 150 && visible.rows[0].bytes === 10000000,
  );
  check("code category", visible.rows[0].category === "code", visible.rows[0].category);
  check("documentation category", visible.rows[1].category === "docs");
  check("documentation category is case-insensitive", classifyCategory(".TXT") === "docs");
  check(
    "ignored subset is explicit",
    visible.ignoredFiles === 7 &&
      visible.ignoredBytes === 1000000 &&
      visible.ignoredFilesText === "7 files" &&
      visible.ignoredBytesText === "1000000 B",
  );
  check(
    "ignored subset uses all-file denominators when included",
    visible.ignoredFileShare > 4 && visible.ignoredByteShare > 9,
  );
  check("compound code extension", classifyCategory(".d.ts") === "code");
  check("data category", classifyCategory(".jsonl") === "data");
  check("unknown category", classifyCategory(".bin") === "other");
  check(
    "row shares remain numeric",
    visible.rows[0].fileShare > 95 && visible.rows[0].byteShare > 90,
  );
  check(
    "scope switches locally",
    modelModule.buildFileTypeSummaryModel(normalized, false, formatters).rows[0].files === 145,
  );
  const withRemainder = modelModule.normalizeRollupEnvelope({
    ...raw,
    ext_tallies: [
      ["", 1, 1, 1, 1],
      [".py", 150, 10000000, 145, 9500000],
      [".md", 6, 999999, 4, 499999],
    ],
  });
  check(
    "remainder row sorts last with a reflexive comparator",
    modelModule
      .buildFileTypeSummaryModel(withRemainder, true, formatters)
      .rows.map((row) => row.key)
      .join(",") === ".py,.md,",
  );
  const failed = modelModule.normalizeRollupEnvelope({ ...raw, index_status: "failed" });
  const failedModel = modelModule.buildFileTypeSummaryModel(failed, true, formatters);
  check("failed index is terminal", failedModel.scanning === false);
  check("failed index has a distinct flag", failedModel.indexFailed === true);
  const failedWithoutTotals = modelModule.normalizeRollupEnvelope({
    ...raw,
    index_status: "failed",
    node: null,
  });
  check(
    "failed index without totals is not a pending skeleton",
    modelModule.buildFileTypeSummaryModel(failedWithoutTotals, true, formatters).state === "failed",
  );
  const completedWithoutTotals = modelModule.normalizeRollupEnvelope({
    ...raw,
    index_status: "done",
    node: null,
  });
  check(
    "completed index miss is not a pending skeleton",
    modelModule.buildFileTypeSummaryModel(completedWithoutTotals, true, formatters).state ===
      "unavailable",
  );
  check("percent zero", modelModule.formatPercent(0, 0, new Intl.NumberFormat()) === "0%");
  check(
    "percent tiny",
    modelModule.formatPercent(
      1,
      2000,
      new Intl.NumberFormat(undefined, { maximumFractionDigits: 1 }),
    ) === "<0.1%",
  );

  const empty = modelModule.normalizeRollupEnvelope({
    ...raw,
    node: { total_files: 0, total_size: 0, unignored_files: 0, unignored_size: 0 },
    ext_tallies: [],
  });
  check(
    "empty model",
    modelModule.buildFileTypeSummaryModel(empty, false, formatters).state === "empty",
  );
  const ignoredOnly = modelModule.normalizeRollupEnvelope({
    ...raw,
    node: { total_files: 2, total_size: 10, unignored_files: 0, unignored_size: 0 },
    ext_tallies: [[".tmp", 2, 10, 0, 0]],
  });
  const ignoredModel = modelModule.buildFileTypeSummaryModel(ignoredOnly, false, formatters);
  check("ignored-only model", ignoredModel.state === "ignored-only");
  check("ignored-only count", ignoredModel.allFilesText === "2 files", ignoredModel.allFilesText);

  const pool = paletteModule.createCategoryPalettePool(12);
  const first = pool.acquire("src");
  first.sync([".py", ".md", ".json"]);
  const slots = [first.slotFor(".py"), first.slotFor(".md"), first.slotFor(".json")];
  check("palette slots distinct", new Set(slots).size === slots.length, slots.join(","));
  const pySlot = first.slotFor(".py");
  first.sync([".md"]);
  check("palette reservation stable", first.slotFor(".py") === pySlot);
  const churn = paletteModule.createCategoryPalettePool(2).acquire("churn");
  churn.sync(["a", "b"]);
  const releasedSlot = churn.slotFor("a");
  churn.sync(["b"]);
  churn.sync(["b", "c"]);
  check("palette reclaims slots for removed keys", churn.slotFor("c") === releasedSlot);
  churn.release();
  const sharedPool = paletteModule.createCategoryPalettePool(3);
  const overviewPalette = sharedPool.acquire("shared");
  const treemapPalette = sharedPool.acquire("shared");
  overviewPalette.sync([".py", ".md"]);
  const sharedPySlot = overviewPalette.slotFor(".py");
  treemapPalette.sync([".py", ".json"]);
  overviewPalette.sync([".md"]);
  check(
    "palette retains keys used by another view",
    treemapPalette.slotFor(".py") === sharedPySlot,
  );
  overviewPalette.release();
  treemapPalette.release();
  check("other neutral", first.classFor("") === "mb-distribution-other");
  const second = pool.acquire("src");
  check("cross-view palette", second.slotFor(".py") === pySlot);
  first.release();
  second.release();

  const state = treemapModel.sanitizeTreemapState({
    metric: "files",
    grouping: "type",
    color: "age",
    ignored: "hidden",
  });
  check(
    "treemap state keeps only the metric and boolean ignore scope",
    state.metric === "files" &&
      state.includeIgnored === true &&
      Object.keys(state).join(",") === "metric,includeIgnored",
    JSON.stringify(state),
  );
  check(
    "every legacy ignored mode resets to the checked default",
    treemapModel.sanitizeTreemapState({ ignored: "dimmed" }).includeIgnored === true &&
      treemapModel.sanitizeTreemapState({ ignored: "shown" }).includeIgnored === true &&
      treemapModel.sanitizeTreemapState({ ignored: "hidden" }).includeIgnored === true,
  );
  check(
    "the new ignored boolean persists",
    treemapModel.sanitizeTreemapState({ includeIgnored: false }).includeIgnored === false,
  );
  check(
    "ignored is included by default",
    treemapModel.sanitizeTreemapState(null).includeIgnored === true,
  );
  check("treemap parent path", treemapModel.parentPath("a/b") === "a");

  if (failures.length) {
    console.error(`folder overview model FAILURES:\n- ${failures.join("\n- ")}`);
    process.exit(1);
  }
  console.log("folder overview models OK");
})();

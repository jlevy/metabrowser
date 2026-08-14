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
  const metrics = (files, bytes, unignoredFiles = files, unignoredBytes = bytes) => ({
    all: { files, bytes },
    unignored: { files: unignoredFiles, bytes: unignoredBytes },
  });
  const baseRuntime = {
    revision: 7,
    fingerprint: "registry-seven",
    groups: [
      { id: "code", label: "Code" },
      { id: "docs", label: "Documentation" },
      { id: "other", label: "Other" },
    ],
    families: [
      { id: "python", label: "Python", groupId: "code", extensions: [".py"] },
      { id: "markdown", label: "Markdown", groupId: "docs", extensions: [".md"] },
    ],
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
    file_type_breakdown: {
      schema: "file-type-breakdown-v1",
      registry: { schema_version: 1, revision: 7, fingerprint: "registry-seven" },
      metrics: metrics(157, 11000000, 150, 10000000),
      groups: [
        {
          id: "code",
          families: [
            {
              id: "python",
              metrics: metrics(150, 10000000, 145, 9500000),
              extensions: [{ extension: ".py", metrics: metrics(150, 10000000, 145, 9500000) }],
            },
          ],
        },
        {
          id: "docs",
          families: [
            {
              id: "markdown",
              metrics: metrics(7, 1000000, 5, 500000),
              extensions: [{ extension: ".md", metrics: metrics(7, 1000000, 5, 500000) }],
            },
          ],
        },
      ],
      no_extension: { metrics: metrics(0, 0), filenames: [], others: null },
      remaining_types: { metrics: metrics(0, 0), extensions: [], others: null },
    },
  };
  const normalized = modelModule.normalizeRollupEnvelope(raw);
  const visible = modelModule.buildFileTypeSummaryModel(normalized, true, formatters, baseRuntime);
  check("populated model", visible.state === "populated", visible.state);
  check(
    "registry order retained",
    visible.rows.map((row) => row.key).join(",") === "family:python,family:markdown",
  );
  check(
    "files and size both present",
    visible.rows[0].files === 150 && visible.rows[0].bytes === 10000000,
  );
  check("code category", visible.rows[0].category === "code", visible.rows[0].category);
  check("documentation category", visible.rows[1].category === "docs");
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
  check(
    "row shares remain numeric",
    visible.rows[0].fileShare > 95 && visible.rows[0].byteShare > 90,
  );
  check(
    "scope switches locally",
    modelModule.buildFileTypeSummaryModel(normalized, false, formatters, baseRuntime).rows[0]
      .files === 145,
  );
  const registryRuntime = {
    revision: 7,
    fingerprint: "registry-seven",
    groups: [
      { id: "media", label: "Media" },
      { id: "logs", label: "Logs" },
      { id: "other", label: "Other" },
    ],
    families: [
      { id: "images", label: "Images", groupId: "media", extensions: [".png"] },
      { id: "log-files", label: "Log files", groupId: "logs", extensions: [".log"] },
    ],
    categoryForFile: () => "other",
  };
  const breakdownEnvelope = modelModule.normalizeRollupEnvelope({
    ...raw,
    node: { total_files: 6, total_size: 50, unignored_files: 6, unignored_size: 50 },
    file_type_breakdown: {
      schema: "file-type-breakdown-v1",
      registry: { schema_version: 1, revision: 7, fingerprint: "registry-seven" },
      metrics: metrics(6, 50),
      groups: [
        {
          id: "logs",
          families: [
            {
              id: "log-files",
              metrics: metrics(1, 10),
              extensions: [{ extension: ".log", metrics: metrics(1, 10) }],
            },
          ],
        },
        {
          id: "media",
          families: [
            {
              id: "images",
              metrics: metrics(1, 20),
              extensions: [{ extension: ".png", metrics: metrics(1, 20) }],
            },
          ],
        },
      ],
      no_extension: {
        metrics: metrics(2, 5),
        filenames: [{ basename: "README", metrics: metrics(1, 3) }],
        others: { metrics: metrics(1, 2), omitted_distinct_values: 4 },
      },
      remaining_types: {
        metrics: metrics(2, 15),
        extensions: [{ extension: ".bin", metrics: metrics(1, 10) }],
        others: { metrics: metrics(1, 5), omitted_distinct_values: 2 },
      },
    },
  });
  const breakdownModel = modelModule.buildFileTypeSummaryModel(
    breakdownEnvelope,
    true,
    formatters,
    registryRuntime,
  );
  check(
    "file-type definitions control group and family order",
    breakdownModel.groups.map((group) => group.id).join(",") === "media,logs,other" &&
      breakdownModel.rows.map((row) => row.key).join(",") ===
        "family:images,family:log-files,(none),",
  );
  check(
    "singleton file-type families are disclosable",
    breakdownModel.rows[0].disclosable === true && breakdownModel.rows[0].children.length === 1,
  );
  const noExtensionRow = breakdownModel.rows.find((row) => row.key === "(none)");
  const remainingRow = breakdownModel.rows.find((row) => row.key === "");
  check(
    "No extension exposes filenames and a counted Others tail",
    noExtensionRow?.children[0].label === "README" &&
      noExtensionRow.children[0].iconPath === "README" &&
      noExtensionRow.children[1].label === "Others (4 more)",
  );
  check(
    "Other types exposes raw extensions and a counted Others tail",
    remainingRow?.children[0].extension === ".bin" &&
      remainingRow.children[0].iconPath === "x.bin" &&
      remainingRow.children[1].label === "Others (2 more)",
  );
  let identityMismatch = false;
  try {
    modelModule.buildFileTypeSummaryModel(breakdownEnvelope, true, formatters, {
      ...registryRuntime,
      fingerprint: "wrong",
    });
  } catch (error) {
    identityMismatch = error instanceof TypeError;
  }
  check("breakdown rejects a mismatched browser registry", identityMismatch);
  const failed = modelModule.normalizeRollupEnvelope({ ...raw, index_status: "failed" });
  const failedModel = modelModule.buildFileTypeSummaryModel(failed, true, formatters, baseRuntime);
  check("failed index is terminal", failedModel.scanning === false);
  check("failed index has a distinct flag", failedModel.indexFailed === true);
  const failedWithoutTotals = modelModule.normalizeRollupEnvelope({
    ...raw,
    index_status: "failed",
    node: null,
    file_type_breakdown: null,
  });
  check(
    "failed index without totals is not a pending skeleton",
    modelModule.buildFileTypeSummaryModel(failedWithoutTotals, true, formatters).state === "failed",
  );
  const completedWithoutTotals = modelModule.normalizeRollupEnvelope({
    ...raw,
    index_status: "done",
    node: null,
    file_type_breakdown: null,
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
    file_type_breakdown: {
      ...raw.file_type_breakdown,
      metrics: metrics(0, 0),
      groups: [],
    },
  });
  check(
    "empty model",
    modelModule.buildFileTypeSummaryModel(empty, false, formatters, baseRuntime).state === "empty",
  );
  const ignoredOnly = modelModule.normalizeRollupEnvelope({
    ...raw,
    node: { total_files: 2, total_size: 10, unignored_files: 0, unignored_size: 0 },
    file_type_breakdown: {
      ...raw.file_type_breakdown,
      metrics: metrics(2, 10, 0, 0),
      groups: [],
      remaining_types: {
        metrics: metrics(2, 10, 0, 0),
        extensions: [{ extension: ".tmp", metrics: metrics(2, 10, 0, 0) }],
        others: null,
      },
    },
  });
  const ignoredModel = modelModule.buildFileTypeSummaryModel(
    ignoredOnly,
    false,
    formatters,
    baseRuntime,
  );
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

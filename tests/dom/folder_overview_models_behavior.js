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
  check("other neutral", first.classFor("") === "mb-distribution-other");
  const second = pool.acquire("src");
  check("cross-view palette", second.slotFor(".py") === pySlot);
  first.release();
  second.release();

  const state = treemapModel.sanitizeTreemapState({ metric: "files", grouping: "bad" });
  check("treemap state validates", state.metric === "files" && state.grouping === "folder");
  check("treemap parent path", treemapModel.parentPath("a/b") === "a");

  if (failures.length) {
    console.error(`folder overview model FAILURES:\n- ${failures.join("\n- ")}`);
    process.exit(1);
  }
  console.log("folder overview models OK");
})();

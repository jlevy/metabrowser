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
    "src/metabrowser/builtin_plugins/folder/file-type-summary-model.js",
  );
  const paletteModule = await importSource(
    "src/metabrowser/builtin_plugins/folder/category-palette.js",
  );
  const treemapModel = await importSource(
    "src/metabrowser/builtin_plugins/folder/treemap-model.js",
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
    schemaVersion: 4,
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
      registry: { schema_version: 4, revision: 7, fingerprint: "registry-seven" },
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
  check(
    "breakdown preserves the registry schema version",
    normalized.registry?.schemaVersion === 4,
    normalized.registry?.schemaVersion,
  );
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
    schemaVersion: 4,
    revision: 7,
    fingerprint: "registry-seven",
    groups: [
      { id: "media", label: "Media" },
      { id: "other", label: "Other" },
    ],
    families: [
      { id: "images", label: "Images", groupId: "media", extensions: [".png"] },
      { id: "log-files", label: "Log files", groupId: "other", extensions: [".log"] },
    ],
    groupForFile: () => "other",
  };
  const breakdownEnvelope = modelModule.normalizeRollupEnvelope({
    ...raw,
    node: { total_files: 6, total_size: 50, unignored_files: 6, unignored_size: 50 },
    file_type_breakdown: {
      schema: "file-type-breakdown-v1",
      registry: { schema_version: 4, revision: 7, fingerprint: "registry-seven" },
      metrics: metrics(6, 50),
      groups: [
        {
          id: "other",
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
    breakdownModel.groups.map((group) => group.id).join(",") === "media,other" &&
      breakdownModel.rows.map((row) => row.key).join(",") ===
        "family:images,,family:log-files,(none)",
  );
  check(
    "singleton file-type families are disclosable",
    breakdownModel.rows[0].disclosable === true && breakdownModel.rows[0].children.length === 1,
  );
  const noExtensionRow = breakdownModel.rows.find((row) => row.key === "(none)");
  const remainingRow = breakdownModel.rows.find((row) => row.key === "");
  // Every entry in a special rollup takes the same generic page: an icon names
  // a family, and having none is what puts an entry here. Resolving one per
  // entry reached into the old extension table, so whether an entry got a
  // distinct glyph depended on whether it happened to be one of the sixteen
  // that table knows.
  check(
    "No extension exposes filenames and a counted Others tail",
    noExtensionRow?.children[0].label === "README" &&
      noExtensionRow.children[0].iconPath === "file" &&
      noExtensionRow.children[1].label === "4 more",
  );
  check(
    "Other types exposes raw extensions and a counted Others tail",
    remainingRow?.children[0].extension === ".bin" &&
      remainingRow.children[0].iconPath === "file" &&
      remainingRow.children[1].label === "2 more",
  );
  check(
    "no entry in a special rollup resolves an icon of its own",
    [noExtensionRow, remainingRow].every((row) =>
      (row?.children ?? []).every((child) => child.iconPath === "file" || child.iconPath === null),
    ),
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
  let schemaMismatch = false;
  try {
    modelModule.buildFileTypeSummaryModel(breakdownEnvelope, true, formatters, {
      ...registryRuntime,
      schemaVersion: 3,
    });
  } catch (error) {
    schemaMismatch = error instanceof TypeError;
  }
  check("breakdown rejects a mismatched browser registry schema", schemaMismatch);
  const failed = modelModule.normalizeRollupEnvelope({ ...raw, index_status: "failed" });
  const failedModel = modelModule.buildFileTypeSummaryModel(failed, true, formatters, baseRuntime);
  check("failed index is terminal", failedModel.scanning === false);
  check("failed index has a distinct flag", failedModel.indexFailed === true);
  const scanningWithTotals = modelModule.normalizeRollupEnvelope({
    ...raw,
    index_status: "scanning",
  });
  // A crawl in progress still has real counts for what it has indexed, and the
  // view labels them as partial. Withholding them meant a large folder showed
  // a loading state for the whole scan instead of detail that refines.
  const scanningModel = modelModule.buildFileTypeSummaryModel(
    scanningWithTotals,
    false,
    formatters,
    baseRuntime,
  );
  check("scanning rollups expose the rows counted so far", scanningModel.state === "populated");
  check("scanning rollups mark themselves in progress", scanningModel.scanning === true);
  check("scanning rollups carry counted rows", scanningModel.rows.length > 0);

  // With nothing counted yet, "empty" would be a claim the crawl cannot make.
  const scanningNothingYet = modelModule.normalizeRollupEnvelope({
    ...raw,
    index_status: "scanning",
    node: { total_files: 0, total_size: 0, unignored_files: 0, unignored_size: 0 },
    file_type_breakdown: {
      ...raw.file_type_breakdown,
      metrics: metrics(0, 0),
      groups: [],
    },
  });
  check(
    "a scan with nothing counted yet stays pending rather than claiming empty",
    modelModule.buildFileTypeSummaryModel(scanningNothingYet, true, formatters, baseRuntime)
      .state === "pending",
  );

  const manyFamiliesRuntime = {
    schemaVersion: 4,
    revision: 7,
    fingerprint: "registry-seven",
    groups: [{ id: "code", label: "Code" }],
    families: Array.from({ length: 12 }, (_, index) => ({
      id: `family-${index}`,
      label: `Family ${index}`,
      groupId: "code",
      extensions: [`.x${index}`],
    })),
  };
  const manyFamilies = modelModule.normalizeRollupEnvelope({
    ...raw,
    node: { total_files: 78, total_size: 78, unignored_files: 78, unignored_size: 78 },
    file_type_breakdown: {
      schema: "file-type-breakdown-v1",
      registry: { schema_version: 4, revision: 7, fingerprint: "registry-seven" },
      metrics: metrics(78, 78),
      groups: [
        {
          id: "code",
          families: Array.from({ length: 12 }, (_, index) => ({
            id: `family-${index}`,
            metrics: metrics(index + 1, 12 - index),
            extensions: Array.from({ length: 12 }, (__, extensionIndex) => ({
              extension: `.x${index}-${extensionIndex}`,
              metrics: metrics(extensionIndex + 1, 12 - extensionIndex),
            })),
          })),
        },
      ],
      no_extension: { metrics: metrics(0, 0), filenames: [], others: null },
      remaining_types: { metrics: metrics(0, 0), extensions: [], others: null },
    },
  });
  const byFiles = modelModule.buildFileTypeSummaryModel(
    manyFamilies,
    true,
    formatters,
    manyFamiliesRuntime,
    "files",
  );
  check(
    "subsection rows sort by the active metric",
    byFiles.rows[0].label === "Family 11" && byFiles.rows[9].label === "Family 2",
    byFiles.rows.map((row) => row.label).join(","),
  );
  check(
    "subsections expose ten rows plus an aggregate disclosure tail",
    byFiles.rows.length === 11 &&
      byFiles.rows[10].label === "2 more" &&
      byFiles.rows[10].kind === "tail" &&
      byFiles.rows[10].children.length === 2,
    byFiles.rows.map((row) => row.label).join(","),
  );
  check(
    "family children use the same sorting and bounded-tail grammar",
    byFiles.rows[0].children[0].label.endsWith("-11") &&
      byFiles.rows[0].children[10].label === "2 more" &&
      byFiles.rows[0].children[10].children.length === 2,
  );
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

  // The palette is a lookup now, so the properties worth holding are the ones
  // the old allocator could not give: the same key is the same color anywhere,
  // and a key the registry does not know still gets one.
  const declared = [
    { key: "family:python", light: "oklch(62% 0.1 246.5)", dark: "oklch(75% 0.12 246.5)" },
    { key: "family:markdown", light: "oklch(62% 0.15 27)", dark: "oklch(75% 0.13 27)" },
    { key: "family:yaml", light: "oklch(62% 0.11 130)", dark: "oklch(75% 0.12 130)" },
  ];
  const palette = paletteModule.createCategoryPalette(declared);
  check(
    "declared family takes its declared color",
    palette.colorFor("family:python").light === declared[0].light,
  );
  check(
    "same key is the same color in a second palette",
    paletteModule.createCategoryPalette(declared).colorFor("family:python").light ===
      palette.colorFor("family:python").light,
  );
  check(
    "both themes are written together",
    palette.styleFor("family:markdown") ===
      `--mb-distribution-color-light:${declared[1].light};` +
        `--mb-distribution-color-dark:${declared[1].dark};`,
  );
  check(
    "mark class selects the theme",
    palette.classFor("family:python") === "mb-distribution-mark",
  );
  check("other neutral", palette.classFor("") === "mb-distribution-other");
  check("other has no color", palette.colorFor("") === null);
  check("other has no style", palette.styleFor("") === "");
  const unknown = palette.colorFor(".xyz");
  check("an unfamilied extension still gets a color", unknown !== null && Boolean(unknown.light));
  check("and the same one every time", palette.colorFor(".xyz").light === unknown.light);
  check(
    "unfamilied extensions spread rather than pile up",
    new Set([".xyz", ".abc", ".qqq"].map((key) => palette.colorFor(key).light)).size >= 2,
  );
  const painted = { className: "", classes: new Set(), properties: new Map() };
  painted.classList = {
    toggle: (name, on) => (on ? painted.classes.add(name) : painted.classes.delete(name)),
  };
  painted.style = {
    setProperty: (name, value) => painted.properties.set(name, value),
    removeProperty: (name) => painted.properties.delete(name),
  };
  palette.paint(painted, "family:python");
  check(
    "paint sets the class and both properties",
    painted.classes.has("mb-distribution-mark") &&
      painted.properties.get("--mb-distribution-color-light") === declared[0].light &&
      painted.properties.get("--mb-distribution-color-dark") === declared[0].dark,
  );
  palette.paint(painted, "");
  check(
    "repainting to the neutral clears what it replaced",
    painted.classes.has("mb-distribution-other") &&
      !painted.classes.has("mb-distribution-mark") &&
      painted.properties.size === 0,
  );
  const emptyPalette = paletteModule.createCategoryPalette([]);
  check(
    "an empty registry falls back to the neutral",
    emptyPalette.classFor(".py") === "mb-distribution-other",
  );

  check("treemap parent path", treemapModel.parentPath("a/b") === "a");
  check(
    "treemap parent navigation identifies the enclosing folder",
    JSON.stringify(treemapModel.parentNavigation("src/metabrowser")) ===
      JSON.stringify({ path: "src", label: "src/" }),
  );
  check(
    "treemap parent navigation identifies the served root",
    JSON.stringify(treemapModel.parentNavigation("src")) ===
      JSON.stringify({ path: "", label: "/" }),
  );
  check(
    "treemap parent navigation is absent at the served root",
    treemapModel.parentNavigation("") === null,
  );
  // The model takes the served source kind rather than reading a global, so
  // the stub answers the way the real codec does: a wire token decodes only
  // when the caller says the subject is a pin.
  const seenKinds = [];
  globalThis.window = {
    MetabrowserNavigationRoute: {
      displayPath(path, sourceKind) {
        seenKinds.push(sourceKind);
        return sourceKind === "git_revision" && path === "g1-ZG9jcw" ? "docs" : path;
      },
    },
  };
  check(
    "treemap parent navigation decodes GitPath labels and keeps the wire",
    JSON.stringify(treemapModel.parentNavigation("g1-ZG9jcw/g1-bm90ZS50eHQ", "git_revision")) ===
      JSON.stringify({ path: "g1-ZG9jcw", label: "docs/" }),
  );
  check(
    "treemap parent navigation forwards the caller's source kind",
    seenKinds.at(-1) === "git_revision",
  );
  check(
    "treemap parent navigation leaves a filesystem name alone",
    JSON.stringify(treemapModel.parentNavigation("g1-ZG9jcw/note.txt", "filesystem")) ===
      JSON.stringify({ path: "g1-ZG9jcw", label: "g1-ZG9jcw/" }),
  );

  // A row cap bounds how long a list gets and says nothing about whether the
  // rows in it are worth reading. These two cases pin the other half: an entry
  // at or below a 1% share is folded however much room is left, and whichever
  // bound is tighter wins.
  const tailFormatters = {
    formatFileCount: (value) => `${value} files`,
    formatInteger: String,
    formatSize: (value) => `${value} B`,
    formatPercent: (value) => `${value}%`,
  };
  const rollupOf = (extensions, totalFiles, totalBytes) => {
    const envelope = modelModule.normalizeRollupEnvelope({
      ...raw,
      node: {
        total_files: totalFiles,
        total_size: totalBytes,
        unignored_files: totalFiles,
        unignored_size: totalBytes,
      },
      file_type_breakdown: {
        schema: "file-type-breakdown-v1",
        registry: { schema_version: 4, revision: 7, fingerprint: "registry-seven" },
        metrics: metrics(totalFiles, totalBytes),
        groups: [],
        no_extension: { metrics: metrics(0, 0), filenames: [], others: null },
        remaining_types: {
          metrics: metrics(totalFiles, totalBytes),
          extensions,
          others: null,
        },
      },
    });
    return modelModule
      .buildFileTypeSummaryModel(envelope, true, tailFormatters, {
        schemaVersion: 4,
        revision: 7,
        fingerprint: "registry-seven",
        // The special rollups live in the "other" group, so it has to exist.
        groups: [{ id: "other", label: "Other" }],
        families: [],
        groupForFile: () => "other",
      })
      .rows.find((row) => row.key === "");
  };

  // One fat entry and a long thin tail: the share floor bites well before the
  // cap would, so only the entry above 1% keeps a row.
  const thin = [{ extension: ".big", metrics: metrics(900, 900) }];
  for (let i = 0; i < 25; i += 1) {
    thin.push({ extension: `.t${i}`, metrics: metrics(4, 4) });
  }
  const thinRow = rollupOf(thin, 1000, 1000);
  const thinVisible = (thinRow?.children ?? []).filter((child) => child.kind !== "tail");
  const thinTail = (thinRow?.children ?? []).find((child) => child.kind === "tail");
  check(
    "a long thin tail folds on the share floor, not on the row cap",
    thinVisible.length === 1 &&
      thinVisible[0].rawKey === ".big" &&
      thinTail?.label === "25 more" &&
      thinVisible.every((child) => child.fileShare > 1),
    JSON.stringify({
      visible: thinVisible.map((c) => [c.rawKey, c.fileShare]),
      tail: thinTail?.label,
    }),
  );

  // Fifteen entries all comfortably above 1%: now the cap is the tighter bound.
  const fat = [];
  for (let i = 0; i < 15; i += 1) {
    fat.push({ extension: `.f${i}`, metrics: metrics(100, 100) });
  }
  const fatRow = rollupOf(fat, 1500, 1500);
  const fatVisible = (fatRow?.children ?? []).filter((child) => child.kind !== "tail");
  check(
    "a list of entries that all clear the floor still respects the row cap",
    fatVisible.length === 10 && fatVisible.every((child) => child.fileShare > 1),
    JSON.stringify({ visibleCount: fatVisible.length }),
  );

  // The compact summary's legend. Eight families in four groups, plus the two
  // rollups of files no family claims, with Other types the largest bucket of
  // all by files: the legend names families only.
  const legendRuntime = {
    schemaVersion: 4,
    revision: 7,
    fingerprint: "registry-seven",
    groups: [
      { id: "code", label: "Code" },
      { id: "docs", label: "Documentation" },
      { id: "data", label: "Data" },
      { id: "other", label: "Other" },
    ],
    families: [
      { id: "typescript", label: "TypeScript", groupId: "code", extensions: [".ts"] },
      { id: "python", label: "Python", groupId: "code", extensions: [".py"] },
      { id: "javascript", label: "JavaScript", groupId: "code", extensions: [".js"] },
      { id: "rust", label: "Rust", groupId: "code", extensions: [".rs"] },
      { id: "markdown", label: "Markdown", groupId: "docs", extensions: [".md"] },
      { id: "json", label: "JSON", groupId: "data", extensions: [".json"] },
      { id: "yaml", label: "YAML", groupId: "data", extensions: [".yaml"] },
      { id: "log", label: "Log files", groupId: "other", extensions: [".log"] },
    ],
  };
  // [id, files, bytes, unignored files, unignored bytes]
  const legendFamilies = [
    ["typescript", 60, 200, 60, 200],
    ["python", 33, 150, 33, 150],
    ["javascript", 25, 120, 25, 120],
    ["rust", 8, 5, 8, 5],
    ["markdown", 150, 300, 150, 300],
    ["json", 240, 100, 40, 20],
    ["yaml", 170, 50, 170, 50],
    ["log", 21, 25, 21, 25],
  ];
  const legendEnvelope = (families, noExtension, remaining) => {
    const sum = (index) =>
      [
        ...families.map((family) => family[index]),
        noExtension[index - 1],
        remaining[index - 1],
      ].reduce((total, value) => total + value, 0);
    const familyEntry = ([id, files, bytes, unignoredFiles, unignoredBytes]) => ({
      id,
      metrics: metrics(files, bytes, unignoredFiles, unignoredBytes),
      extensions: [
        {
          extension: legendRuntime.families.find((family) => family.id === id).extensions[0],
          metrics: metrics(files, bytes, unignoredFiles, unignoredBytes),
        },
      ],
    });
    return modelModule.normalizeRollupEnvelope({
      path: "",
      index_status: "done",
      truncated: false,
      file_type_breakdown: {
        schema: "file-type-breakdown-v1",
        registry: { schema_version: 4, revision: 7, fingerprint: "registry-seven" },
        metrics: metrics(sum(1), sum(2), sum(3), sum(4)),
        groups: legendRuntime.groups
          .map((group) => ({
            id: group.id,
            families: families
              .filter(
                ([id]) =>
                  legendRuntime.families.find((family) => family.id === id).groupId === group.id,
              )
              .map(familyEntry),
          }))
          .filter((group) => group.families.length > 0),
        no_extension: { metrics: metrics(...noExtension), filenames: [], others: null },
        remaining_types: { metrics: metrics(...remaining), extensions: [], others: null },
      },
    });
  };
  const legendRollup = legendEnvelope(legendFamilies, [40, 20, 40, 20], [253, 30, 253, 30]);
  const legendOf = (envelope, showIgnored, metric, runtime = legendRuntime) =>
    modelModule.buildFileTypeSummaryModel(envelope, showIgnored, formatters, runtime, metric);
  const legendKeys = (model) => model.legend.map((entry) => entry.key).join(",");
  const byFilesLegend = legendOf(legendRollup, true, "files");
  check(
    "the legend names the five largest families across groups, then Other",
    legendKeys(byFilesLegend) ===
      "family:json,family:yaml,family:markdown,family:typescript,family:python,legend:other",
    legendKeys(byFilesLegend),
  );
  check(
    "the legend states each share as the Details rows do, and Other as the rest",
    byFilesLegend.legend.map((entry) => `${entry.label} ${entry.percent}`).join(" | ") ===
      "JSON 24% | YAML 17% | Markdown 15% | TypeScript 6% | Python 3.3% | Other 34.7%",
    byFilesLegend.legend.map((entry) => `${entry.label} ${entry.percent}`).join(" | "),
  );
  check(
    "the legend's values add up to the population the caption names",
    byFilesLegend.legend.reduce((total, entry) => total + entry.value, 0) === byFilesLegend.files &&
      byFilesLegend.caption === "Share of Total (1000 files)",
    JSON.stringify({ files: byFilesLegend.files, caption: byFilesLegend.caption }),
  );
  check(
    "No extension and Other types are never named, however large",
    byFilesLegend.legend.every((entry) => entry.kind === "family" || entry.key === "legend:other"),
  );
  check(
    "Other takes the neutral, as on the population bars",
    byFilesLegend.legend.at(-1).paletteKey === "" &&
      byFilesLegend.legend.slice(0, -1).every((entry) => entry.paletteKey === entry.key),
  );
  const unfoldedFamilies = new Set(
    byFilesLegend.rows.filter((row) => row.kind === "family").map((row) => row.key),
  );
  check(
    "every type the legend names is a row Details shows unfolded",
    byFilesLegend.legend
      .filter((entry) => entry.kind === "family")
      .every((entry) => unfoldedFamilies.has(entry.key)),
    [...unfoldedFamilies].join(","),
  );
  check(
    "the legend follows the measure",
    legendKeys(legendOf(legendRollup, true, "size")) ===
      "family:markdown,family:typescript,family:python,family:javascript,family:json,legend:other",
    legendKeys(legendOf(legendRollup, true, "size")),
  );
  const unignoredLegend = legendOf(legendRollup, false, "files");
  check(
    "the legend follows Show ignored",
    legendKeys(unignoredLegend) ===
      "family:yaml,family:markdown,family:typescript,family:json,family:python,legend:other" &&
      unignoredLegend.legend.reduce((total, entry) => total + entry.value, 0) ===
        unignoredLegend.files,
    legendKeys(unignoredLegend),
  );
  const floorLegend = legendOf(
    legendEnvelope(
      [
        ["python", 995, 995, 995, 995],
        ["rust", 5, 5, 5, 5],
      ],
      [0, 0, 0, 0],
      [0, 0, 0, 0],
    ),
    true,
    "files",
  );
  check(
    "a family at or under the share floor is Other, however much room is left",
    floorLegend.legend.map((entry) => `${entry.label} ${entry.percent}`).join(" | ") ===
      "Python 99.5% | Other 0.5%",
    floorLegend.legend.map((entry) => `${entry.label} ${entry.percent}`).join(" | "),
  );
  const wholeLegend = legendOf(
    legendEnvelope([["python", 10, 10, 10, 10]], [0, 0, 0, 0], [0, 0, 0, 0]),
    true,
    "files",
  );
  check(
    "named types that cover everything leave no Other",
    legendKeys(wholeLegend) === "family:python" && wholeLegend.legend[0].percent === "100%",
    legendKeys(wholeLegend),
  );
  const zeroBytesLegend = legendOf(
    legendEnvelope([["python", 10, 0, 10, 0]], [0, 0, 0, 0], [0, 0, 0, 0]),
    true,
    "size",
  );
  check(
    "a population of zero bytes has nothing to name by size",
    zeroBytesLegend.state === "zero-bytes" && zeroBytesLegend.legend.length === 0,
    `${zeroBytesLegend.state} ${legendKeys(zeroBytesLegend)}`,
  );
  check(
    "a model with no totals has no legend",
    modelModule.buildFileTypeSummaryModel(null, true, formatters, legendRuntime).legend.length ===
      0,
  );
  check("the legend names at most five types", modelModule.LEGEND_TYPE_LIMIT === 5);

  if (failures.length) {
    console.error(`folder overview model FAILURES:\n- ${failures.join("\n- ")}`);
    process.exit(1);
  }
  console.log("folder overview models OK");
})();

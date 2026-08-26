// Shared render-model contracts for intraline progressive enhancement.

const path = require("node:path");
const { pathToFileURL } = require("node:url");

const repoRoot = path.resolve(process.argv[2]);
const failures = [];

function check(label, condition, detail = "") {
  if (!condition) {
    failures.push(`${label}${detail ? `: ${detail}` : ""}`);
  }
}

async function main() {
  const modulePath = path.join(
    repoRoot,
    "src/metabrowser/builtin_plugins/diff/diff-render-model.js",
  );
  const { buildFileRenderModel, refineFileChangedRuns, refineHunkChangedRuns } = await import(
    pathToFileURL(modulePath).href
  );
  const model = buildFileRenderModel(
    { old: { path: "before.js" }, new: { path: "after.js" } },
    {
      hunks: [
        {
          old_start: 1,
          old_count: 4,
          new_start: 1,
          new_count: 5,
          lines: [
            { op: "context", text: "header" },
            { op: "del", text: "alpha = one;" },
            { op: "del", text: "beta = two;" },
            { op: "del", text: "gamma = three;" },
            { op: "add", text: "inserted = zero;" },
            { op: "add", text: "alpha = 1;" },
            { op: "add", text: "beta = 2;" },
            { op: "add", text: "gamma = 3;" },
          ],
        },
      ],
    },
    () => "javascript",
  );
  const hunk = model.hunks[0];
  check("refinement starts pending", hunk.refinementComplete === false);
  check("split rows start uncached", hunk.changedRunRows.size === 0);

  const hunkChanged = refineHunkChangedRuns(hunk, {}, undefined);
  check("hunk reports a refinement", hunkChanged === true);
  check("hunk refinement settles", hunk.refinementComplete === true);
  const rows = hunk.changedRunRows.get(0) ?? [];
  check(
    "cached rows preserve shifted monotonic alignment",
    JSON.stringify(
      rows.map((row) => ({
        new: row.new?.text ?? null,
        old: row.old?.text ?? null,
      })),
    ) ===
      '[{"new":"inserted = zero;","old":null},{"new":"alpha = 1;","old":"alpha = one;"},{"new":"beta = 2;","old":"beta = two;"},{"new":"gamma = 3;","old":"gamma = three;"}]',
    JSON.stringify(rows),
  );
  check(
    "paired records cache side-specific spans",
    hunk.lines[1].oldIntralineRanges.length > 0 && hunk.lines[5].newIntralineRanges.length > 0,
  );
  check(
    "unmatched line joins the refined run hierarchy",
    hunk.lines[4].intralineRefined === true &&
      hunk.changedRunRows.get(hunk.lines[4].changedRun)?.[0]?.refined === true &&
      JSON.stringify(hunk.lines[4].newIntralineRanges) ===
        JSON.stringify([{ start: 0, end: hunk.lines[4].text.length }]),
  );
  check(
    "repeated hunk refinement is idempotent",
    refineHunkChangedRuns(hunk, {}, undefined) === false,
  );

  const controller = new AbortController();
  controller.abort();
  const abortedModel = buildFileRenderModel(
    { old: { path: "a.js" }, new: { path: "b.js" } },
    {
      hunks: [
        {
          old_start: 1,
          old_count: 1,
          new_start: 1,
          new_count: 1,
          lines: [
            { op: "del", text: "old value" },
            { op: "add", text: "new value" },
          ],
        },
      ],
    },
    () => "javascript",
  );
  let abortName = "";
  try {
    refineFileChangedRuns(abortedModel, {}, controller.signal);
  } catch (error) {
    abortName = error?.name ?? "";
  }
  check("aborted file refinement throws AbortError", abortName === "AbortError", abortName);
  check("aborted hunk remains retryable", abortedModel.hunks[0].refinementComplete === false);

  const oneSidedModel = buildFileRenderModel(
    { old: null, new: { path: "generated.json" } },
    {
      hunks: [
        {
          old_start: 0,
          old_count: 0,
          new_start: 1,
          new_count: 10_000,
          lines: Array.from({ length: 10_000 }, (_, index) => ({
            op: "add",
            text: `line ${index}`,
          })),
        },
      ],
    },
    () => "json",
  );
  check(
    "one-sided refinement has no visual work",
    refineFileChangedRuns(oneSidedModel, {}) === false,
  );
  check(
    "one-sided refinement does not allocate positional row caches",
    oneSidedModel.hunks[0].refinementComplete === true &&
      oneSidedModel.hunks[0].changedRunRows.size === 0,
    String(oneSidedModel.hunks[0].changedRunRows.size),
  );
  check(
    "one-sided file additions retain ordinary row treatment",
    oneSidedModel.hunks[0].lines.every(
      (line) => line.intralineRefined === false && line.newIntralineRanges.length === 0,
    ),
  );

  const containedModel = buildFileRenderModel(
    { old: { path: "a.js" }, new: { path: "b.js" } },
    {
      hunks: [
        {
          old_start: 1,
          old_count: 2,
          new_start: 1,
          new_count: 2,
          lines: [
            { op: "del", text: "const oldName = 1;" },
            { op: "add", text: "const newName = 1;" },
            { op: "context", text: "separator" },
            { op: "del", text: "return oldValue;" },
            { op: "add", text: "return newValue;" },
          ],
        },
      ],
    },
    () => "javascript",
  );
  let checks = 0;
  const originalWarn = console.warn;
  let warnings = 0;
  console.warn = () => {
    warnings += 1;
  };
  const contained = refineFileChangedRuns(
    containedModel,
    {
      isValid() {
        checks += 1;
        if (checks === 1) {
          throw new Error("injected failure");
        }
        return true;
      },
    },
    undefined,
  );
  console.warn = originalWarn;
  check("one failed run does not block later runs", contained === true);
  check("contained failure emits one diagnostic", warnings === 1, String(warnings));
  check(
    "failed run keeps positional plain rows",
    containedModel.hunks[0].changedRunRows.get(0)?.[0].old?.text === "const oldName = 1;",
  );
  check(
    "later run can still refine",
    containedModel.hunks[0].changedRunRows.get(1)?.[0].refined === true,
  );

  if (failures.length > 0) {
    for (const failure of failures) {
      console.error(failure);
    }
    process.exit(1);
  }
  console.log("diff render model OK");
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});

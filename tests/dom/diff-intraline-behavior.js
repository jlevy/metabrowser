// Observable contracts for browser-local changed-run refinement.

const path = require("node:path");
const { pathToFileURL } = require("node:url");

const repoRoot = path.resolve(process.argv[2]);
const failures = [];

function check(label, condition, detail = "") {
  if (!condition) {
    failures.push(`${label}${detail ? `: ${detail}` : ""}`);
  }
}

function spanText(lines, spansByIndex) {
  return spansByIndex.map((spans, index) =>
    spans.map((span) => lines[index].slice(span.start, span.end)).join("|"),
  );
}

function validRanges(lines, spansByIndex) {
  return spansByIndex.every((spans, lineIndex) =>
    spans.every(
      (span, index) =>
        Number.isInteger(span.start) &&
        Number.isInteger(span.end) &&
        0 <= span.start &&
        span.start < span.end &&
        span.end <= lines[lineIndex].length &&
        (index === 0 || spans[index - 1].end <= span.start),
    ),
  );
}

function positionalRows(oldLength, newLength) {
  return Array.from({ length: Math.max(oldLength, newLength) }, (_, index) => ({
    newIndex: index < newLength ? index : null,
    oldIndex: index < oldLength ? index : null,
  }));
}

async function main() {
  const modulePath = path.join(repoRoot, "src/metabrowser/builtin_plugins/diff/diff-intraline.js");
  const { refineChangedRun } = await import(pathToFileURL(modulePath).href);

  const word = refineChangedRun(["const color = 'red';"], ["const color = 'blue';"]);
  check("single word refines", word.status === "refined", word.status);
  check(
    "single word ranges",
    JSON.stringify(spanText(["const color = 'red';"], word.oldSpansByIndex)) === '["red"]' &&
      JSON.stringify(spanText(["const color = 'blue';"], word.newSpansByIndex)) === '["blue"]',
    JSON.stringify({ old: word.oldSpansByIndex, new: word.newSpansByIndex }),
  );

  const punctuation = refineChangedRun(
    ["call(alpha, beta);", "const userName = oldValue;"],
    ["call(alpha; beta);", "const userName = newValue;"],
  );
  check("multiple edits refine", punctuation.status === "refined", punctuation.status);
  check(
    "punctuation boundary is readable",
    spanText(
      ["call(alpha, beta);", "const userName = oldValue;"],
      punctuation.oldSpansByIndex,
    )[0] === ",",
  );
  check(
    "camel-case boundary is readable",
    spanText(
      ["call(alpha; beta);", "const userName = newValue;"],
      punctuation.newSpansByIndex,
    )[1] === "newValue",
  );

  const indentation = refineChangedRun(["  return value;"], ["    return value;"]);
  check("indentation-only edit refines", indentation.status === "refined", indentation.status);
  check(
    "indentation-only range stays whitespace",
    spanText(["    return value;"], indentation.newSpansByIndex)[0] === "  ",
  );

  const shifted = refineChangedRun(
    ["alpha = one;", "beta = two;", "gamma = three;"],
    ["inserted = zero;", "alpha = 1;", "beta = 2;", "gamma = 3;"],
  );
  check("shifted unequal run refines", shifted.status === "refined", shifted.status);
  check(
    "shifted unequal lines align monotonically",
    JSON.stringify(shifted.rows) ===
      '[{"oldIndex":null,"newIndex":0},{"oldIndex":0,"newIndex":1},{"oldIndex":1,"newIndex":2},{"oldIndex":2,"newIndex":3}]',
    JSON.stringify(shifted.rows),
  );

  for (const [label, oldLines, newLines] of [
    ["pure addition", [], ["new"]],
    ["pure deletion", ["old"], []],
    ["unrelated replacement", ["north star"], ["quantum field"]],
    ["empty replacement", [""], [""]],
  ]) {
    const result = refineChangedRun(oldLines, newLines);
    check(`${label} stays plain`, result.status === "plain", result.status);
    check(
      `${label} keeps positional rows`,
      JSON.stringify(result.rows) ===
        JSON.stringify(positionalRows(oldLines.length, newLines.length)),
      JSON.stringify(result.rows),
    );
  }

  const lineEndings = refineChangedRun(["value = old\r", ""], ["value = new\r", "tail"]);
  check(
    "CRLF and empty-line projection refines",
    lineEndings.status === "refined",
    lineEndings.status,
  );
  check(
    "all projected ranges are valid and ordered",
    validRanges(["value = old\r", ""], lineEndings.oldSpansByIndex) &&
      validRanges(["value = new\r", "tail"], lineEndings.newSpansByIndex),
  );

  const unicode = refineChangedRun(["const emoji = '😀';"], ["const emoji = '😃';"]);
  check("emoji replacement refines", unicode.status === "refined", unicode.status);
  const oldEmojiRange = unicode.oldSpansByIndex[0][0];
  const newEmojiRange = unicode.newSpansByIndex[0][0];
  check(
    "emoji ranges keep surrogate pairs whole",
    "const emoji = '😀';".slice(oldEmojiRange.start, oldEmojiRange.end) === "😀" &&
      "const emoji = '😃';".slice(newEmojiRange.start, newEmojiRange.end) === "😃",
  );

  const timedOut = refineChangedRun(["const oldName = 1;"], ["const newName = 1;"], {
    isValid: () => false,
  });
  check("timeout is an honest fallback", timedOut.status === "timed_out", timedOut.status);
  let timeoutChecks = 0;
  const interrupted = refineChangedRun(["const oldName = 1;"], ["const newName = 1;"], {
    isValid: () => timeoutChecks++ < 2,
  });
  check(
    "timeout is rechecked during dynamic programming",
    interrupted.status === "timed_out",
    interrupted.status,
  );
  const overBudget = refineChangedRun(["a".repeat(600)], ["b".repeat(600)], {
    maxWork: 1,
  });
  check(
    "work budget is an honest fallback",
    overBudget.status === "over_budget",
    overBudget.status,
  );

  const longPrefix = "const repeatedPrefix = true; ".repeat(20);
  const longLine = refineChangedRun([`${longPrefix}oldValue;`], [`${longPrefix}newValue;`]);
  check("Myers long-line path refines", longLine.status === "refined", longLine.status);
  check(
    "Myers long-line ranges remain ordered",
    validRanges([`${longPrefix}oldValue;`], longLine.oldSpansByIndex) &&
      validRanges([`${longPrefix}newValue;`], longLine.newSpansByIndex),
  );

  const stable = refineChangedRun(["prefix old suffix"], ["prefix new suffix"]);
  check(
    "repeat calls are deterministic",
    JSON.stringify(stable) ===
      JSON.stringify(refineChangedRun(["prefix old suffix"], ["prefix new suffix"])),
  );
  check(
    "all output text remains exact source text",
    stable.rows
      .map((row) => (row.oldIndex === null ? "" : ["prefix old suffix"][row.oldIndex]))
      .join("") === "prefix old suffix" &&
      stable.rows
        .map((row) => (row.newIndex === null ? "" : ["prefix new suffix"][row.newIndex]))
        .join("") === "prefix new suffix",
  );

  if (failures.length > 0) {
    for (const failure of failures) {
      console.error(failure);
    }
    process.exit(1);
  }
  console.log("diff intraline OK");
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});

const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const repoRoot = path.resolve(__dirname, "../..");
const fixture = JSON.parse(
  fs.readFileSync(path.join(repoRoot, "tests/fixtures/file_fuzzy_ranking.json"), "utf-8"),
);
const sandbox = {};
sandbox.window = sandbox;
sandbox.globalThis = sandbox;
vm.createContext(sandbox);

const source = fs.readFileSync(
  path.join(repoRoot, "src/metabrowser/static/file-fuzzy-match.js"),
  "utf-8",
);
vm.runInContext(source, sandbox, { filename: "file-fuzzy-match.js" });

const failures = [];

function check(label, condition, detail = "") {
  if (!condition) {
    failures.push(`${label}${detail ? `: ${detail}` : ""}`);
  }
}

const matcher = sandbox.MetabrowserFileFuzzyMatch;
const rankKeys = [
  "matchClass",
  "boundaryHits",
  "contiguousChars",
  "runCount",
  "gapChars",
  "startOffset",
  "candidateLength",
  "directoryDepth",
  "normalizedPath",
  "originalPath",
];

for (const scenario of fixture.scenarios) {
  const results = matcher.rankPaths(scenario.query, scenario.candidates);
  const actual = results.map((result) => result.path);
  check(
    `${scenario.id} order`,
    JSON.stringify(actual) === JSON.stringify(scenario.expected),
    `expected ${JSON.stringify(scenario.expected)}, got ${JSON.stringify(actual)}; ${results
      .map((result) => `${result.path}=${JSON.stringify(result.rank)}`)
      .join(" | ")}`,
  );
  for (const result of results) {
    check(
      `${scenario.id} exposes named rank components`,
      JSON.stringify(Object.keys(result.rank)) === JSON.stringify(rankKeys),
      JSON.stringify(Object.keys(result.rank)),
    );
    const highlighted = result.matchRanges
      .map((range) => result.path.slice(range.start, range.end))
      .join("")
      .toLowerCase();
    check(
      `${scenario.id} ranges map to the original path`,
      highlighted === scenario.query.trim().toLowerCase(),
      `${result.path}: ${JSON.stringify(result.matchRanges)} -> ${JSON.stringify(highlighted)}`,
    );
  }
  const reversed = matcher
    .rankPaths(scenario.query, scenario.candidates.slice().reverse())
    .map((result) => result.path);
  check(
    `${scenario.id} ignores candidate input order`,
    JSON.stringify(reversed) === JSON.stringify(actual),
    JSON.stringify(reversed),
  );
}

const trimmed = matcher.matchPath("  APP  ", "src/app.js");
check("queries are trimmed", trimmed?.path === "src/app.js");
check("results are frozen", Object.isFrozen(trimmed) && Object.isFrozen(trimmed.rank));
check("blank queries do not match", matcher.matchPath("  ", "src/app.js") === null);

const contextualCase = matcher.matchPath("ος", "docs/ΟΣ");
check(
  "whole-string lowercasing preserves contextual Unicode case behavior",
  JSON.stringify(contextualCase?.matchRanges) === JSON.stringify([{ start: 5, end: 7 }]),
  JSON.stringify(contextualCase),
);

const boundaryChoice = matcher.matchPath("srcapp", "src/metabrowser/static/app.js");
check(
  "alignment honors boundary priority instead of the first eligible letters",
  JSON.stringify(boundaryChoice?.matchRanges) ===
    JSON.stringify([
      { start: 0, end: 3 },
      { start: 23, end: 26 },
    ]),
  JSON.stringify(boundaryChoice?.matchRanges),
);

if (failures.length > 0) {
  process.stderr.write(`${failures.join("\n")}\n`);
  process.exit(1);
}

process.stdout.write("OK fuzzy file matcher\n");

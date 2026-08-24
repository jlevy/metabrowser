const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const { performance } = require("node:perf_hooks");

const repoRoot = path.resolve(__dirname, "../..");
const sandbox = {};
sandbox.window = sandbox;
sandbox.globalThis = sandbox;
vm.createContext(sandbox);
vm.runInContext(
  fs.readFileSync(path.join(repoRoot, "src/metabrowser/static/file-fuzzy-match.js"), "utf-8"),
  sandbox,
  { filename: "file-fuzzy-match.js" },
);

function syntheticPaths(count, prefix) {
  return Array.from({ length: count }, (_, index) => {
    const ordinal = String(index).padStart(5, "0");
    const shard = String(index % 257).padStart(3, "0");
    return `${prefix}/shard-${shard}/nested/result-file-${ordinal}.json`;
  });
}

function profile(label, count, rounds) {
  const paths = syntheticPaths(count, label);
  const durations = [];
  let matches = 0;
  for (let round = 0; round < rounds; round += 1) {
    const started = performance.now();
    matches = 0;
    for (const candidatePath of paths) {
      if (sandbox.MetabrowserFileFuzzyMatch.matchPath("rfl", candidatePath)) {
        matches += 1;
      }
    }
    durations.push(performance.now() - started);
  }
  durations.sort((left, right) => left - right);
  const medianMs = durations[Math.floor(durations.length / 2)];
  return {
    candidates: count,
    matches,
    medianMs: Number(medianMs.toFixed(2)),
    microsecondsPerCandidate: Number(((medianMs * 1000) / count).toFixed(2)),
    rounds,
  };
}

const report = {
  expanded: profile("expanded", 50_000, 3),
  node: process.version,
  recent: profile("recent", 2_000, 5),
};

if (report.recent.matches !== 2_000 || report.expanded.matches !== 50_000) {
  process.stderr.write(`unexpected profile match counts: ${JSON.stringify(report)}\n`);
  process.exit(1);
}

process.stdout.write(`PROFILE ${JSON.stringify(report)}\n`);

// exp-087's judged pairs and its deciding test, as its pre-registration declares them.
//
//   node exp-087-analyze.mjs SAMPLES_OR_RUNS.jsonl POWER.jsonl FILTER.mjs [--count] [--out JUDGED.jsonl]
//
// Load rule: FILTER.mjs (exp-060-062-load-filter.mjs) marks each pair judged or excluded.
// Power rule: a pair has a power mode only when the lowpowermode and power source read before and
// after it all agree. Judged mode: the first mode to reach 10 judged pairs (by series order),
// else the mode with the most, if it has at least 6. --count prints only the largest per-mode
// count (for the driver's stop rule). Otherwise it prints, for each view, M(V), the 2x2 table, the
// two-sided Fisher exact p, and painted ready per build overall and per frames-to-ready count.

import { execFileSync } from "node:child_process";
import fs from "node:fs";

const [rowsPath, powerPath, filterPath, ...rest] = process.argv.slice(2);
const countOnly = rest.includes("--count");
const outAt = rest.indexOf("--out");
const outPath = outAt >= 0 ? rest[outAt + 1] : null;

const rows = fs.existsSync(rowsPath)
  ? fs
      .readFileSync(rowsPath, "utf8")
      .split("\n")
      .filter(Boolean)
      .map((l) => JSON.parse(l))
  : [];
const power = fs.existsSync(powerPath)
  ? fs
      .readFileSync(powerPath, "utf8")
      .split("\n")
      .filter(Boolean)
      .map((l) => JSON.parse(l))
  : [];
const loadJudged = new Set();
if (rows.length) {
  const out = execFileSync("node", [filterPath, rowsPath], { encoding: "utf8" });
  for (const line of out.split("\n").filter(Boolean)) {
    const [key, , , verdict] = line.split("\t");
    if (verdict === "judged") {
      loadJudged.add(key);
    }
  }
}
const modeOf = new Map();
for (const p of power) {
  const same =
    p.lpm_start === p.lpm_end && p.src_start === p.src_end && p.lpm_start !== null && p.src_start;
  modeOf.set(`${p.series}#1`, same ? `lowpowermode=${p.lpm_start} ${p.src_start}` : null);
}
const pairKeys = [...new Set(rows.map((r) => `${r.series}#${r.pair}`))].sort();
const byMode = new Map();
let judgedMode = null;
for (const key of pairKeys) {
  const mode = modeOf.get(key);
  if (!loadJudged.has(key) || !mode) {
    continue;
  }
  byMode.set(mode, [...(byMode.get(mode) ?? []), key]);
  if (!judgedMode && byMode.get(mode).length >= 10) {
    judgedMode = mode;
  }
}
const largest = Math.max(0, ...[...byMode.values()].map((v) => v.length));
if (countOnly) {
  console.log(largest);
  process.exit(0);
}
if (!judgedMode) {
  const best = [...byMode.entries()].sort((a, b) => b[1].length - a[1].length)[0];
  judgedMode = best && best[1].length >= 6 ? best[0] : null;
}
console.log(
  `pairs: ${pairKeys.length}; judged by load and power, per mode: ${JSON.stringify(Object.fromEntries([...byMode].map(([m, v]) => [m, v.length])))}`,
);
if (!judgedMode) {
  console.log("no mode has 6 judged pairs: not decided");
  process.exit(0);
}
const keys = (byMode.get(judgedMode) ?? []).slice(0, 10);
console.log(`judged mode: ${judgedMode}; judged pairs: ${keys.length}`);
const judged = rows.filter((r) => keys.includes(`${r.series}#${r.pair}`));
if (outPath) {
  fs.writeFileSync(outPath, judged.map((r) => `${JSON.stringify(r)}\n`).join(""));
}

function logFact(n) {
  let s = 0;
  for (let i = 2; i <= n; i += 1) {
    s += Math.log(i);
  }
  return s;
}
function hyper(a, b, c, d) {
  return Math.exp(
    logFact(a + b) +
      logFact(c + d) +
      logFact(a + c) +
      logFact(b + d) -
      logFact(a + b + c + d) -
      logFact(a) -
      logFact(b) -
      logFact(c) -
      logFact(d),
  );
}
/** Two-sided Fisher exact p for [[a, b], [c, d]], margins fixed. */
function fisher(a, b, c, d) {
  const r1 = a + b;
  const c1 = a + c;
  const n = a + b + c + d;
  const observed = hyper(a, b, c, d);
  let p = 0;
  for (let x = Math.max(0, r1 + c1 - n); x <= Math.min(r1, c1); x += 1) {
    const pr = hyper(x, r1 - x, c1 - x, n - r1 - c1 + x);
    if (pr <= observed * (1 + 1e-7)) {
      p += pr;
    }
  }
  return Math.min(1, p);
}
const median = (xs) => {
  const s = [...xs].sort((x, y) => x - y);
  const m = Math.floor(s.length / 2);
  return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2;
};
const VIEWS = ["files.cold.json", "files.cold.image", "files.revisit.markdown_large"];
const result = { judgedMode, pairs: keys, views: {} };
for (const v of VIEWS) {
  const vals = { control: [], candidate: [] };
  for (const r of judged) {
    const t = r.journeys.flatMap((j) => j.transitions).find((x) => x.id === v);
    vals[r.condition].push({ frames: t.framesToReady, painted: t.paintedReadyMs });
  }
  const all = [...vals.control, ...vals.candidate].map((x) => x.frames);
  const counts = {};
  for (const f of all) {
    counts[f] = (counts[f] ?? 0) + 1;
  }
  const top = Math.max(...Object.values(counts));
  const M = Math.min(
    ...Object.entries(counts)
      .filter(([, n]) => n === top)
      .map(([f]) => Number(f)),
  );
  const later = (c) => vals[c].filter((x) => x.frames > M).length;
  const a = later("candidate");
  const b = vals.candidate.length - a;
  const c = later("control");
  const d = vals.control.length - c;
  const p = fisher(a, b, c, d);
  const painted = {};
  for (const build of ["control", "candidate"]) {
    const xs = vals[build].map((x) => x.painted);
    const byFrames = {};
    for (const x of vals[build]) {
      byFrames[x.frames] = [...(byFrames[x.frames] ?? []), x.painted];
    }
    painted[build] = {
      overall: { median: median(xs), range: [Math.min(...xs), Math.max(...xs)], n: xs.length },
      byFrames: Object.fromEntries(
        Object.entries(byFrames).map(([f, ps]) => [
          f,
          { n: ps.length, median: median(ps), range: [Math.min(...ps), Math.max(...ps)] },
        ]),
      ),
    };
  }
  result.views[v] = {
    M,
    frameCounts: counts,
    candidate: `${a}/${a + b} later`,
    control: `${c}/${c + d} later`,
    p: Math.round(p * 10000) / 10000,
    differs: p < 0.05,
    painted,
  };
  console.log(
    `${v}: M=${M}, candidate ${a}/${a + b} later, control ${c}/${c + d} later, Fisher two-sided p=${p.toFixed(4)} -> ${p < 0.05 ? "DIFFERS" : "no difference beyond chance"}`,
  );
}
const decided = Object.values(result.views).every((x) => !x.differs);
result.decision = decided
  ? "accepted (clause 3 accounted for as frame-quantization flips)"
  : "unresolved";
console.log(`decision: H87 ${result.decision}`);
console.log(JSON.stringify(result, null, 1));

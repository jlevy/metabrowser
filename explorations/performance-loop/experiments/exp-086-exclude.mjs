// exp-086's exclusion rule (exp-086-protocol.txt, "LOCK, LOAD, POWER, PACING"), from load
// fields and the power-mode samples only; it reads no metric.
//
//   node exp-086-exclude.mjs RUNS.jsonl POWER.log MODE [--split JUDGED.jsonl OTHER.jsonl]
//
// POWER.log has one sample per line, "<ISO time> lowpowermode <0|1> [power source...]".
// MODE is the lowpowermode read when the first paced pair started. A pair (series#pair)
// is excluded if it is incomplete, if either run's one-minute load was above 12 at its
// start or at the start of any measured transition, if either run's power mode changed
// during it or is unknown, or if its two runs' modes differ. A complete pair in the other
// mode is reported and not judged. Prints one line per excluded or unjudged pair, then
// "judged N excluded M other_mode K mode MODE".
import fs from "node:fs";

const [file, powerFile, mode, flag, judgedOut, otherOut] = process.argv.slice(2);
if (mode !== "0" && mode !== "1") {
  throw new Error(`MODE must be 0 or 1, not ${mode}`);
}
const rows = fs.existsSync(file)
  ? fs.readFileSync(file, "utf8").trim().split("\n").filter(Boolean).map(JSON.parse)
  : [];
const samples = fs
  .readFileSync(powerFile, "utf8")
  .trim()
  .split("\n")
  .map((line) => {
    const m = /^(\S+)\s+lowpowermode\s+(\d)/.exec(line);
    return m ? [Date.parse(m[1]), m[2]] : null;
  })
  .filter(Boolean)
  .sort((a, b) => a[0] - b[0]);
const modeAt = (t) => {
  let found = null;
  for (const [ts, v] of samples) {
    if (ts > t) {
      break;
    }
    found = v;
  }
  return found;
};
const modesDuring = (a, b) =>
  new Set([modeAt(a), ...samples.filter(([ts]) => ts > a && ts <= b).map(([, v]) => v)]);
const keyOf = (r) => r.pair_key ?? `${r.series}#${r.pair}`;
const pairs = new Map();
for (const r of rows) {
  if (!pairs.has(keyOf(r))) {
    pairs.set(keyOf(r), []);
  }
  pairs.get(keyOf(r)).push(r);
}
const loads = (r) =>
  [
    r.load_start?.[0],
    ...(r.journeys ?? []).flatMap((j) => (j.transitions ?? []).map((t) => t.load1)),
  ].filter((x) => typeof x === "number");
const judged = new Set();
let excluded = 0;
let other = 0;
for (const [key, runs] of pairs) {
  if (runs.length !== 2) {
    console.log(`excluded ${key}: incomplete (${runs.length} runs)`);
    excluded++;
    continue;
  }
  const highest = Math.max(...runs.flatMap(loads));
  const modes = runs.map((r) => [
    ...modesDuring(Date.parse(r.started_at), Date.parse(r.finished_at)),
  ]);
  const reasons = [];
  if (!(highest <= 12)) {
    reasons.push(`load ${highest}`);
  }
  if (modes.some((m) => m.length !== 1 || m[0] === null)) {
    reasons.push(`power mode changed or unknown ${JSON.stringify(modes)}`);
  } else if (modes[0][0] !== modes[1][0]) {
    reasons.push(`power modes differ ${modes[0][0]}/${modes[1][0]}`);
  }
  if (reasons.length) {
    console.log(`excluded ${key}: ${reasons.join("; ")}`);
    excluded++;
    continue;
  }
  if (modes[0][0] !== mode) {
    console.log(`reported, not judged (mode ${modes[0][0]}): ${key}`);
    other++;
    continue;
  }
  judged.add(key);
}
console.log(`judged ${judged.size} excluded ${excluded} other_mode ${other} mode ${mode}`);
if (flag === "--split") {
  const write = (out, keep) =>
    fs.writeFileSync(
      out,
      `${rows
        .filter((r) => keep(judged.has(keyOf(r))))
        .map((r) => JSON.stringify(r))
        .join("\n")}\n`,
    );
  write(judgedOut, (j) => j);
  write(otherOut, (j) => !j);
}

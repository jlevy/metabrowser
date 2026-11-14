// exp-079's exclusion rule (exp-079-protocol.txt: "Load rule" and "Power rule" in the
// registration, the power mode in amendment 1), from load fields and power readings only;
// it reads no metric.
//
//   node exp-079-exclude.mjs ROWS.jsonl POWER.jsonl [--split JUDGED.jsonl OTHER.jsonl]
//
// ROWS.jsonl is the round's runs or its committed samples. The load rule is the committed
// exp-060-062-load-filter.mjs, run as it is beside this file: a pair (series#pair) is
// excluded if any run in it saw a one-minute load above 12 at its start or at any measured
// transition's start, or if it is incomplete (a run refused, or a condition missing).
//
// POWER.jsonl has one line per attempt: its series, and lowpowermode and the power source
// read before (lpm_start, src_start) and after (lpm_end, src_end) the pair. As in exp-087,
// a pair has a power mode only if both readings of each agree, and the mode is the pair
// "<lowpowermode>|<source>". The judged mode is the first attempt's reading before its
// pair (lpm_start|src_start of attempt 1). A complete pair in another mode is reported and
// not judged; modes are never pooled.
//
// Prints one line per attempt, then "judged N excluded M other_mode K mode MODE".
// --split writes the judged pairs' rows to JUDGED.jsonl and every other row to OTHER.jsonl.
import { execFileSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";

const [rowsFile, powerFile, flag, judgedOut, otherOut] = process.argv.slice(2);
if (!rowsFile || !powerFile || (flag && (flag !== "--split" || !judgedOut || !otherOut))) {
  throw new Error("usage: exp-079-exclude.mjs ROWS.jsonl POWER.jsonl [--split JUDGED OTHER]");
}
const loadFilter = path.join(import.meta.dirname, "exp-060-062-load-filter.mjs");
const rows = fs
  .readFileSync(rowsFile, "utf8")
  .split("\n")
  .filter(Boolean)
  .map((line) => JSON.parse(line));
const loadVerdict = new Map();
for (const line of execFileSync("node", [loadFilter, rowsFile], { encoding: "utf8" })
  .split("\n")
  .filter(Boolean)) {
  const [key, , , verdict] = line.split("\t");
  loadVerdict.set(key, verdict);
}
const attempts = fs
  .readFileSync(powerFile, "utf8")
  .split("\n")
  .filter(Boolean)
  .map((line) => JSON.parse(line))
  .sort((a, b) => a.attempt - b.attempt);
if (!attempts.length) {
  throw new Error(`${powerFile} has no attempts`);
}
const mode = `${attempts[0].lpm_start}|${attempts[0].src_start}`;
const judged = new Set();
let excluded = 0;
let other = 0;
for (const a of attempts) {
  const key = a.series ? `${a.series}#1` : null;
  const reasons = [];
  const load = key ? loadVerdict.get(key) : undefined;
  if (load === undefined) {
    reasons.push("no rows recorded");
  } else if (load !== "judged") {
    reasons.push(load);
  }
  const agree =
    a.lpm_start !== null &&
    a.lpm_start === a.lpm_end &&
    Boolean(a.src_start) &&
    a.src_start === a.src_end;
  const pairMode = agree ? `${a.lpm_start}|${a.src_start}` : null;
  if (!pairMode) {
    reasons.push(
      `power readings disagree (lowpowermode ${a.lpm_start}/${a.lpm_end}, source ${a.src_start}/${a.src_end})`,
    );
  }
  if (reasons.length) {
    excluded += 1;
    console.log(`attempt ${a.attempt} ${key ?? "-"}: excluded: ${reasons.join("; ")}`);
  } else if (pairMode !== mode) {
    other += 1;
    console.log(`attempt ${a.attempt} ${key}: reported, not judged (mode ${pairMode})`);
  } else {
    judged.add(key);
    console.log(`attempt ${a.attempt} ${key}: judged (mode ${pairMode})`);
  }
}
console.log(`judged ${judged.size} excluded ${excluded} other_mode ${other} mode ${mode}`);
if (flag === "--split") {
  const keyOf = (r) => `${r.series}#${r.pair}`;
  const write = (out, keep) =>
    fs.writeFileSync(
      out,
      rows
        .filter((r) => keep(judged.has(keyOf(r))))
        .map((r) => `${JSON.stringify(r)}\n`)
        .join(""),
    );
  write(judgedOut, (j) => j);
  write(otherOut, (j) => !j);
}

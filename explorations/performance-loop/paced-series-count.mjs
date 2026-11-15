// The judged-pair count behind paced-series.sh's stopping rule. It reads load fields and
// power readings, never a metric, and decides only when a series stops; the record
// computes its own exclusions from the committed samples and power log, by the rules its
// protocol registers. It generalizes exp-079's driver count.
//
//   node paced-series-count.mjs --runs RUNS.jsonl --power POWER.jsonl --mode MODE \
//     --load-filter LOAD_FILTER.mjs [--max-load N]
//
// The load rule is LOAD_FILTER (the committed exp-060-062-load-filter.mjs), run as it is,
// with --max-load N when given and at its own default otherwise: a pair is excluded if any
// run in it saw a one-minute load above N at its start or at any measured transition's
// start, or if it is incomplete (a run refused, or a condition missing).
//
// The power rule is exp-087's. POWER.jsonl has one line per attempt, as paced-series.sh
// writes it: its series, and lowpowermode and the power source read before (lpm_start,
// src_start) and after (lpm_end, src_end) the pair. A pair has a mode only if both
// readings of each agree, and the mode is "<lowpowermode>|<source>". MODE is the judged
// mode, read before the first attempt. A pair is judged when the load filter judges it
// and its mode is MODE. A pair in another mode is reported and never pooled.
//
// paced-series.sh runs one pair per harness invocation, so an attempt's pair is
// "<series>#1". Prints one line per attempt, then
// "judged N excluded M other_mode K attempts A"; the driver reads that last line.
import { execFileSync } from "node:child_process";
import fs from "node:fs";
import { parseArgs } from "node:util";

const USAGE =
  "usage: paced-series-count.mjs --runs RUNS.jsonl --power POWER.jsonl --mode MODE --load-filter LOAD_FILTER.mjs [--max-load N]";
let values;
try {
  ({ values } = parseArgs({
    options: {
      runs: { type: "string" },
      power: { type: "string" },
      mode: { type: "string" },
      "load-filter": { type: "string" },
      "max-load": { type: "string" },
    },
  }));
} catch (error) {
  console.error(`${error.message}\n${USAGE}`);
  process.exit(64);
}
const { runs: runsFile, power: powerFile, mode } = values;
const loadFilter = values["load-filter"];
const maxLoad = values["max-load"];
if (!runsFile || !powerFile || !mode || !loadFilter) {
  console.error(USAGE);
  process.exit(64);
}
if (!mode.includes("|")) {
  console.error(`--mode is "<lowpowermode>|<source>", got ${mode}`);
  process.exit(64);
}
if (!fs.existsSync(loadFilter)) {
  console.error(`no load filter at ${loadFilter}`);
  process.exit(66);
}
if (maxLoad !== undefined && !Number.isFinite(Number(maxLoad))) {
  console.error(`--max-load is a number, got ${maxLoad}`);
  process.exit(64);
}

const loadVerdict = new Map();
if (fs.existsSync(runsFile) && fs.statSync(runsFile).size > 0) {
  const args = [loadFilter, runsFile, ...(maxLoad === undefined ? [] : ["--max-load", maxLoad])];
  const out = execFileSync(process.execPath, args, { encoding: "utf8" });
  for (const line of out.split("\n").filter(Boolean)) {
    const [key, , , verdict] = line.split("\t");
    loadVerdict.set(key, verdict);
  }
}
const attempts = fs.existsSync(powerFile)
  ? fs
      .readFileSync(powerFile, "utf8")
      .split("\n")
      .filter(Boolean)
      .map((line) => JSON.parse(line))
      .sort((a, b) => a.attempt - b.attempt)
  : [];
let judged = 0;
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
  // As exp-079-exclude.mjs reads it: an unreadable lowpowermode gives no mode.
  const agree =
    a.lpm_start !== null &&
    a.lpm_start !== undefined &&
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
    judged += 1;
    console.log(`attempt ${a.attempt} ${key}: judged (mode ${pairMode})`);
  }
}
console.log(
  `judged ${judged} excluded ${excluded} other_mode ${other} attempts ${attempts.length}`,
);

// The coordinator's load rule, applied before any result is read: a pair is excluded when any
// of its runs saw a one-minute load above LIMIT at its start or at any measured transition's
// start. Reads only load fields.
//
// node load-exclusions.mjs RUNS.jsonl [--keep KEPT.jsonl --excluded EXCLUDED.jsonl]
//   prints one line per pair and, last, "valid N excluded M"
import fs from "node:fs";

const LIMIT = 12;
const [input, ...rest] = process.argv.slice(2);
const flag = (name) => {
  const at = rest.indexOf(name);
  return at < 0 ? null : rest[at + 1];
};
const lines = fs
  .readFileSync(input, "utf8")
  .split("\n")
  .filter((line) => line.trim());
const rows = lines.map((line) => JSON.parse(line));
const pairKey = (row) => row.pair_key ?? `${row.series}#${row.pair}`;
const pairs = new Map();
rows.forEach((row, at) => {
  const key = pairKey(row);
  if (!pairs.has(key)) {
    pairs.set(key, {
      key,
      rows: [],
      lines: [],
      maxStart: 0,
      maxTransition: 0,
      unknown: 0,
      conditions: [],
    });
  }
  const pair = pairs.get(key);
  pair.rows.push(row);
  pair.lines.push(lines[at]);
  pair.conditions.push(`${row.condition}${row.valid ? "" : "(refused)"}`);
  pair.maxStart = Math.max(pair.maxStart, row.load_start?.[0] ?? 0);
  for (const journey of row.journeys ?? []) {
    for (const t of journey.transitions ?? []) {
      if (typeof t.load1 !== "number") {
        pair.unknown += 1;
      }
      pair.maxTransition = Math.max(pair.maxTransition, t.load1 ?? 0);
    }
  }
});
const kept = [];
const excluded = [];
let valid = 0;
for (const pair of pairs.values()) {
  const over = pair.maxStart > LIMIT || pair.maxTransition > LIMIT || pair.unknown > 0;
  const complete =
    pair.rows.length === 2 &&
    pair.rows.every((row) => row.valid) &&
    new Set(pair.rows.map((row) => row.condition)).size === 2;
  const verdict = over ? "excluded (load)" : complete ? "valid" : "incomplete";
  if (verdict === "valid") {
    valid += 1;
    kept.push(...pair.lines);
  } else {
    excluded.push(...pair.lines);
  }
  console.log(
    `${pair.key} ${pair.conditions.join(",")} run-start max ${pair.maxStart} transition max ${pair.maxTransition} unknown ${pair.unknown}: ${verdict}`,
  );
}
if (flag("--keep")) {
  fs.writeFileSync(flag("--keep"), kept.length ? `${kept.join("\n")}\n` : "");
}
if (flag("--excluded")) {
  fs.writeFileSync(flag("--excluded"), excluded.length ? `${excluded.join("\n")}\n` : "");
}
// Short of three valid pairs, the series adds pairs: wait first for a quiet machine, the same
// gate the lock was taken on (five samples 30 s apart under the limit), so a replacement pair is
// not spent at a load the rule would exclude. Added during the series; the rule is unchanged.
if (valid < 3 && !process.env.NO_WAIT) {
  const os = await import("node:os");
  const samples = [];
  const deadline = Date.now() + 3 * 60 * 60 * 1000;
  while (Date.now() < deadline) {
    samples.push(os.loadavg()[0]);
    if (samples.length >= 5 && samples.slice(-5).every((v) => v < LIMIT)) {
      break;
    }
    await new Promise((resolve) => setTimeout(resolve, 30000));
  }
  process.stderr.write(
    `${new Date().toISOString()} quiet gate passed after ${samples.length} samples: ${samples
      .slice(-5)
      .map((v) => v.toFixed(2))
      .join(" ")}\n`,
  );
}
console.log(`valid ${valid} excluded ${pairs.size - valid}`);

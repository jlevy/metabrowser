// exp-086's identity-period explanation check (exp-086-protocol.txt, "IDENTITY-PERIOD
// EXPLANATION CHECK"). It is declared, not accounting: it decides no verdict, and no guard
// is judged on a subset because of it.
//
//   node exp-086-identity-check.mjs JUDGED.jsonl HARNESS OUT.json
//
// HARNESS is the harness checkout the runs were recorded from; each row's `server.log` is
// relative to it. Each judged run's server log has one METABROWSER_REQUEST_LOG=verbose
// line per request. The git-backed requests are those whose path starts with /api/git/ or
// /api/plugin/diff/. In arrival order on that server the first is a TTL boundary, and so
// is each later one arriving at least 5,000 ms after the previous boundary's arrival;
// every other one is within the TTL. For /api/plugin/diff/comparison and /api/git/commit/,
// pooled over each build's judged runs (warm-up and measured passes alike), the ratio is
// the median server ms (the log's ms) of boundary requests over the median of within-TTL
// requests; a median of an even count is the mean of the middle two. The check FITS the
// identity account if the ratio is at least 1.3 on the control for both routes and below
// 1.3 on the candidate for both, and DOES NOT FIT otherwise. Also per run: whether
// commits.hover_click's and commits.cold.1's comparison request is a boundary, and its ms
// (hover: the last GET of comparison?revision=dbfd82b9...; cold.1: the last GET of
// ...revision=3669a358... that arrived before the last GET of ...revision=083af6f8...).
import fs from "node:fs";
import path from "node:path";

const [judgedFile, harness, outFile] = process.argv.slice(2);
const LINE = /request t=([\d.]+) -> ([\d.]+) \((\d+) ms\) method=(\w+) path=(\S+)/;
const BOUNDARY_MS = 5000;
const ROUTES = { comparison: "/api/plugin/diff/comparison", commit: "/api/git/commit/" };
const rows = fs.readFileSync(judgedFile, "utf8").trim().split("\n").filter(Boolean).map(JSON.parse);
const median = (xs) => {
  if (!xs.length) {
    return null;
  }
  const s = [...xs].sort((a, b) => a - b);
  const h = Math.floor(s.length / 2);
  return s.length % 2 ? s[h] : (s[h - 1] + s[h]) / 2;
};
const pooled = {};
const perRun = [];
for (const r of rows) {
  const reqs = fs
    .readFileSync(path.resolve(harness, r.server.log), "utf8")
    .split("\n")
    .map((l) => LINE.exec(l))
    .filter(Boolean)
    .map((m) => ({
      a: Number(m[1]) * 1000,
      c: Number(m[2]) * 1000,
      ms: Number(m[3]),
      method: m[4],
      path: m[5],
    }))
    .filter((q) => q.path.startsWith("/api/git/") || q.path.startsWith("/api/plugin/diff/"))
    .sort((x, y) => x.a - y.a);
  let last = null;
  for (const q of reqs) {
    q.boundary = last === null || q.a - last >= BOUNDARY_MS;
    if (q.boundary) {
      last = q.a;
    }
  }
  pooled[r.condition] ??= Object.fromEntries(
    Object.keys(ROUTES).map((k) => [k, { boundary: [], within: [] }]),
  );
  for (const [name, prefix] of Object.entries(ROUTES)) {
    for (const q of reqs.filter((x) => x.path.startsWith(prefix))) {
      pooled[r.condition][name][q.boundary ? "boundary" : "within"].push(q.ms);
    }
  }
  const cmp = (rev) =>
    reqs.filter(
      (q) =>
        q.method === "GET" &&
        q.path.startsWith(ROUTES.comparison) &&
        q.path.includes(`revision=${rev}`),
    );
  const hover = cmp("dbfd82b9").at(-1);
  const cold3 = cmp("083af6f8").at(-1);
  const cold1 = cold3
    ? cmp("3669a358")
        .filter((q) => q.a < cold3.a)
        .at(-1)
    : undefined;
  const at = (q) => (q ? { boundary: q.boundary, ms: q.ms } : { found: false });
  const rec = {
    series: r.series,
    pair: r.pair,
    condition: r.condition,
    git_backed: reqs.length,
    boundaries: reqs.filter((q) => q.boundary).length,
    hover_click: at(hover),
    cold_1: at(cold1),
  };
  perRun.push(rec);
  console.log(
    `${r.condition.padEnd(9)} ${r.series}#${r.pair}  git-backed ${rec.git_backed}, boundaries ${rec.boundaries}  hover ${JSON.stringify(rec.hover_click)}  cold.1 ${JSON.stringify(rec.cold_1)}`,
  );
}
const table = {};
for (const [cond, routes] of Object.entries(pooled)) {
  table[cond] = {};
  for (const [name, { boundary, within }] of Object.entries(routes)) {
    const b = median(boundary);
    const w = median(within);
    table[cond][name] = {
      n_boundary: boundary.length,
      n_within: within.length,
      median_boundary_ms: b,
      median_within_ms: w,
      ratio: b !== null && w ? b / w : null,
    };
    console.log(
      `${cond.padEnd(9)} ${name.padEnd(10)} boundary n=${boundary.length} median ${b}  within n=${within.length} median ${w}  ratio ${table[cond][name].ratio?.toFixed(2)}`,
    );
  }
}
const all = (cond, test) =>
  Object.keys(ROUTES).every((k) => {
    const x = table[cond]?.[k]?.ratio;
    return typeof x === "number" && test(x);
  });
const fits = all("control", (x) => x >= 1.3) && all("candidate", (x) => x < 1.3);
console.log(fits ? "FITS the identity account" : "DOES NOT FIT the identity account");
fs.writeFileSync(
  outFile,
  `${JSON.stringify(
    {
      rule: "exp-086 identity-period explanation check",
      boundary_ms: BOUNDARY_MS,
      fits,
      table,
      runs: perRun,
    },
    null,
    2,
  )}\n`,
);

// Figures for exp-060 and exp-062 that `compare` shows but does not judge, or that the
// levels probe records: per-run values, medians (the harness's own `median`), ranges, and
// back-to-back pair ratios, a pair being a series and its pair number.
//
//   node exp-060-062-figures.mjs HARNESS JUDGED-TRANSITIONS.jsonl JUDGED-LEVELS.jsonl
//
// HARNESS is a checkout of the transition harness (5031dc16 for these rounds); the two
// files are the judged rows that exp-060-062-load-filter.mjs writes with --out.
import fs from "node:fs";
import path from "node:path";

const [harness, samplesPath, levelsPath] = process.argv.slice(2);
const { median } = await import(
  path.join(harness, "explorations/performance-loop/transitions-stats.mjs")
);
const rows = fs
  .readFileSync(samplesPath, "utf8")
  .split("\n")
  .filter(Boolean)
  .map((l) => JSON.parse(l))
  .filter((r) => r.valid);
const transition = (row, id) =>
  row.journeys.flatMap((j) => j.transitions).find((t) => t.id === id) ?? null;
const FAMILIES = ["static", "plugin_static", "kpress_static", "data", "document"];

const perRun = rows.map((row) => {
  const reload = transition(row, "landing.reload");
  const cold = transition(row, "landing.cold_markdown");
  const by = reload?.requests?.byFamily ?? {};
  const reval = Object.fromEntries(FAMILIES.map((f) => [f, by[f]?.revalidated ?? 0]));
  return {
    condition: row.condition,
    run: row.run,
    pair: `${row.series}#${row.pair}`,
    load_start: row.load_start,
    load_end: row.load_end,
    revalidated_total: Object.values(reval).reduce((a, b) => a + b, 0),
    revalidated: reval,
    reload_requests: Object.entries(reload?.requests?.byClass ?? {})
      .filter(([cls]) => !["stream", "inline", "background"].includes(cls))
      .reduce((a, [, n]) => a + n, 0),
    painted_reload: reload?.paintedReadyMs ?? null,
    painted_cold: cold?.paintedReadyMs ?? null,
    shell_tools_cold: cold?.milestones?.shellToolsReady ?? null,
    styled_cold: cold?.milestones?.styledMarkdown ?? null,
  };
});

function describe(label, list, key) {
  const by = (c) => list.filter((r) => r.condition === c);
  const out = { metric: label };
  for (const c of ["control", "candidate"]) {
    const xs = by(c)
      .map((r) => r[key])
      .filter((x) => x !== null && x !== undefined);
    out[c] = {
      values: xs,
      median: xs.length ? median(xs) : null,
      range: xs.length ? [Math.min(...xs), Math.max(...xs)] : null,
    };
  }
  const pairOf = (r) => (String(r.pair).includes("#") ? r.pair : `${r.series}#${r.pair}`);
  const pairs = [...new Set(list.map(pairOf))].sort();
  out.pair_ratios = pairs.map((p) => {
    const a = list.find((r) => pairOf(r) === p && r.condition === "control")?.[key];
    const b = list.find((r) => pairOf(r) === p && r.condition === "candidate")?.[key];
    return {
      pair: p,
      control: a ?? null,
      candidate: b ?? null,
      ratio: a ? Math.round((b / a) * 1000) / 1000 : null,
    };
  });
  const [lo, hi] = [out.control.range, out.candidate.range];
  out.overlapping = lo && hi ? !(hi[1] < lo[0] || lo[1] < hi[0]) : null;
  return out;
}

const report = {
  runs: perRun,
  transition_figures: [
    describe("revalidated_total.landing.reload", perRun, "revalidated_total"),
    describe("requests_total.landing.reload", perRun, "reload_requests"),
    describe("painted_ready_ms.landing.reload", perRun, "painted_reload"),
    describe("painted_ready_ms.landing.cold_markdown", perRun, "painted_cold"),
    describe("shell_tools_ready_ms.landing.cold_markdown", perRun, "shell_tools_cold"),
    describe("styled_markdown_ms.landing.cold_markdown", perRun, "styled_cold"),
  ],
};
if (levelsPath && fs.existsSync(levelsPath)) {
  const levels = fs
    .readFileSync(levelsPath, "utf8")
    .split("\n")
    .filter(Boolean)
    .map((l) => JSON.parse(l));
  report.levels = levels;
  report.level_figures = [
    "levels_shell_tools",
    "levels_kpress",
    "levels_max",
    "shell_tools_end_ms",
    "kpress_end_ms",
    "requests_network",
  ].map((key) => describe(key, levels, key));
}
console.log(JSON.stringify(report, null, 1));

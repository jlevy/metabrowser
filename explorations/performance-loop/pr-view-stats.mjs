// Summarize pr-view.mjs runs: per step and build, each metric's median and range, the load
// average each run started at, and, with --control and --candidate, the ratio of each
// back-to-back pair (candidate / control) judged at --tolerance (default 1.3, the rough
// cut), as the performance loop's pair rule reads them.
//
//   node explorations/performance-loop/pr-view-stats.mjs FILE.jsonl [FILE...] \
//     [--control LABEL --candidate LABEL] [--tolerance 1.3] [--json]
//
// A pair is two runs of one step next to each other in the file, one of each build, as
// pr-view-pairs.sh writes them. A run that timed out or failed keeps its row and reports
// the milestones it reached; a milestone it never reached is null and is left out of the
// median, and the count beside each median says how many runs it holds.
import fs from "node:fs";
import { parseArgs } from "node:util";

const { values: opt, positionals: files } = parseArgs({
  allowPositionals: true,
  options: {
    control: { type: "string" },
    candidate: { type: "string" },
    tolerance: { type: "string", default: "1.3" },
    json: { type: "boolean", default: false },
  },
});
const tolerance = Number(opt.tolerance);
const runs = files.flatMap((f) =>
  fs
    .readFileSync(f, "utf8")
    .split("\n")
    .filter(Boolean)
    .map((l) => JSON.parse(l)),
);

const first = (r, test) => (r.api ?? []).find((a) => test(a.path));
const route = (name) => (a) =>
  a.startsWith(`/api/plugin/github/${name}?`) || a === `/api/plugin/github/${name}`;
/** The metrics of one run, by name; null where the run has none. */
function metrics(r) {
  const m = r.marks ?? {};
  const out = {};
  if (r.scenario === "pr") {
    for (const k of [
      "title_any",
      "title",
      "description",
      "description_final",
      "summary_pending",
      "summary",
      "complete",
    ]) {
      out[k] = m[k] ?? null;
    }
    const pull = first(r, (p) => /^\/api\/plugin\/github\/pull\?number=\d+$/.test(p));
    out.pull_ms = pull?.ms ?? null;
    // From the record's arrival (the first GET pull's response end): to the title, which a
    // held first paint keeps out of sight while it waits for the first screen's Markdown;
    // and to the end of the last Markdown answer the page asked for, with their count.
    const markdown = (r.api ?? []).filter((a) => a.path.includes("/pull-markdown?"));
    out.title_after_pull = pull && typeof m.title === "number" ? m.title - pull.end : null;
    out.markdown_after_pull =
      pull && markdown.length ? Math.max(...markdown.map((a) => a.end)) - pull.end : null;
    out.markdown_requests = markdown.length;
    out.pull_srv = pull?.timing?.srv ?? null;
    const refresh = first(r, route("pull-refresh"));
    out.pull_refresh_srv = refresh?.timing?.srv ?? null;
    const cmp = first(r, route("pull-comparison"));
    out.comparison_ms = cmp?.ms ?? null;
    out.comparison_git = cmp?.timing?.git ?? null;
    const stacks = first(r, route("stacks"));
    out.stacks_srv = stacks?.timing?.srv ?? null;
    const wait = first(r, (p) => p.includes("/pull?") && p.includes("wait_full_after"));
    out.wait_full_ms = wait?.ms ?? null;
    const rep = (r.replay ?? []).find((x) => /\/pull\?number=\d+$/.test(x.path));
    out.replay_pull_ms = rep?.ms ?? null;
    const repc = (r.replay ?? []).find((x) => x.path.includes("pull-comparison?"));
    out.replay_comparison_ms = repc?.ms ?? null;
  } else {
    out.first_row = m.first_row ?? null;
    out.last_row = m.last_row ?? null;
    out.first_line = Object.values(r.lines ?? {}).length
      ? Math.min(...Object.values(r.lines))
      : null;
    out.last_line = m.last_line ?? null;
    out.lines = Object.keys(r.lines ?? {}).length;
    out.rows = Object.keys(r.rows ?? {}).length;
    const pend = Object.values(r.pending ?? {});
    out.first_pending = pend.length ? Math.min(...pend) : null;
    const pulls = first(r, (p) => p.startsWith("/api/plugin/github/pulls?"));
    out.pulls_srv = pulls?.timing?.srv ?? null;
    const sum = first(r, route("pull-files-summary"));
    out.files_summary_srv = sum?.timing?.srv ?? null;
    out.lane_items = (r.lane?.outcomes ?? []).filter((o) => o.outcome === "refreshed").length;
  }
  out.gh_calls = r.gh?.calls ?? null;
  out.gh_ms = r.gh?.total_ms ?? null;
  out.server_ready = r.server_ready_ms ?? null;
  out.load = r.load_start?.[0] ?? null;
  return out;
}

const median = (xs) => {
  const s = [...xs].sort((a, b) => a - b);
  const n = s.length;
  return n === 0 ? null : n % 2 ? s[(n - 1) / 2] : (s[n / 2 - 1] + s[n / 2]) / 2;
};
const stepOf = (r) => r.step || `${r.scenario}-${r.cache}`;
const groups = new Map();
for (const r of runs) {
  const key = `${stepOf(r)}\u0000${r.label}`;
  if (!groups.has(key)) {
    groups.set(key, []);
  }
  groups.get(key).push(r);
}
const summary = {};
for (const [key, rs] of groups) {
  const [step, label] = key.split("\u0000");
  const ms = rs.map(metrics);
  const row = {
    n: rs.length,
    version: rs[0].version,
    timed_out: rs.filter((r) => r.timed_out).length,
    errors: rs.filter((r) => r.error).length,
  };
  for (const name of Object.keys(ms[0])) {
    const xs = ms.map((m) => m[name]).filter((x) => typeof x === "number");
    row[name] = {
      median: median(xs),
      min: xs.length ? Math.min(...xs) : null,
      max: xs.length ? Math.max(...xs) : null,
      count: xs.length,
    };
  }
  summary[step] ??= {};
  summary[step][label] = row;
}

const pairs = {};
if (opt.control && opt.candidate) {
  const bySteps = new Map();
  for (const r of runs) {
    if (r.label !== opt.control && r.label !== opt.candidate) {
      continue;
    }
    const s = stepOf(r);
    if (!bySteps.has(s)) {
      bySteps.set(s, []);
    }
    bySteps.get(s).push(r);
  }
  for (const [step, rs] of bySteps) {
    const list = [];
    for (let i = 0; i + 1 < rs.length; i++) {
      if (rs[i].label !== rs[i + 1].label) {
        const ctl = rs[i].label === opt.control ? rs[i] : rs[i + 1];
        const cand = ctl === rs[i] ? rs[i + 1] : rs[i];
        list.push([metrics(ctl), metrics(cand)]);
        i++;
      }
    }
    const out = {};
    for (const name of list.length ? Object.keys(list[0][0]) : []) {
      if (name === "load") {
        continue;
      }
      const ratios = list.map(([a, b]) =>
        typeof a[name] === "number" && typeof b[name] === "number" && a[name] > 0
          ? b[name] / a[name]
          : null,
      );
      const r = ratios.filter((x) => x !== null);
      out[name] = {
        ratios: ratios.map((x) => (x === null ? null : Math.round(x * 100) / 100)),
        beyond: r.filter((x) => x > tolerance).length,
        under: r.filter((x) => x < 1 / tolerance).length,
      };
    }
    pairs[step] = {
      pairs: list.length,
      loads: list.map(([a, b]) => [a.load, b.load]),
      metrics: out,
    };
  }
}

if (opt.json) {
  console.log(JSON.stringify({ summary, pairs, tolerance }, null, 1));
} else {
  const fmt = (v) => (v === null ? "-" : Math.round(v));
  for (const [step, byLabel] of Object.entries(summary)) {
    console.log(`\n## ${step}`);
    const labels = Object.keys(byLabel);
    const names = Object.keys(byLabel[labels[0]]).filter(
      (k) => typeof byLabel[labels[0]][k] === "object",
    );
    console.log(
      [
        "metric",
        ...labels.map(
          (l) =>
            `${l} (n=${byLabel[l].n}${byLabel[l].timed_out ? `, ${byLabel[l].timed_out} timed out` : ""})`,
        ),
      ].join(" | "),
    );
    for (const name of names) {
      console.log(
        [
          name,
          ...labels.map((l) => {
            const v = byLabel[l][name];
            return v.count
              ? `${fmt(v.median)} [${fmt(v.min)}-${fmt(v.max)}]${v.count < byLabel[l].n ? ` (${v.count})` : ""}`
              : "-";
          }),
        ].join(" | "),
      );
    }
    const p = pairs[step];
    if (p) {
      console.log(
        `pairs ${opt.candidate}/${opt.control}: ${p.pairs}, loads ${JSON.stringify(p.loads)}`,
      );
      for (const [name, v] of Object.entries(p.metrics)) {
        if (v.ratios.some((x) => x !== null)) {
          console.log(
            `  ${name}: ${JSON.stringify(v.ratios)} beyond ${tolerance}x: ${v.beyond}, under 1/${tolerance}x: ${v.under}`,
          );
        }
      }
    }
  }
}

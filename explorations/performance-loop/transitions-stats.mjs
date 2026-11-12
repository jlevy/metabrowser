// Statistics for the transition-navigation/v1 scenario: the metrics a row yields, the
// valid runs of each condition, `summarize` tables, `compare`, and `samples`.
//
// Pure functions over parsed rows, so tests/dom/transitions-instrument-behavior.mjs can
// drive every refusal and verdict from fixture rows. transitions.mjs is the command line.
import path from "node:path";

export const SCENARIO = "transition-navigation/v1";
export const SCENARIO_REVISION = 3;
export const MIN_RUNS = 3;

/** A comparison that cannot be made to mean anything; the command exits 2. */
export class CompareRefusal extends Error {}

// `kind` decides how a metric is judged. A `time` and a `frames` count are judged on
// back-to-back pairs against the tolerance (frame counts depend on the frame rate, so on
// load, as times do), except that a zero control median against a non-zero candidate is
// judged on the ranges alone. A `count` or a `value` is judged on its ranges.
// `better` is the direction a round wants; `null` marks a figure that is shown but not
// judged (the instrument's own figures, and work on timers the reader does not drive).
const T = (key, get, better = "lower") => ({ key, kind: "time", better, get });
const F = (key, get, better = "lower") => ({ key, kind: "frames", better, get });
const C = (key, get, better = "lower") => ({ key, kind: "count", better, get });

export const METRICS = [
  T("painted_ready_ms", (t) => t.paintedReadyMs),
  T("ready_ms", (t) => t.readyMs),
  F("frames_to_ready", (t) => t.framesToReady),
  F("blank_frames", (t) => t.blankFrames),
  F("blank_frames_after_ready", (t) => t.blankFramesAfterReady),
  T("blank_ms", (t) => t.blankMs),
  F("placeholder_visible_frames", (t) => t.placeholderVisibleFrames),
  F("placeholder_visible_frames_after_ready", (t) => t.placeholderVisibleFramesAfterReady),
  F("nav_placeholder_visible_frames", (t) => t.navPlaceholderVisibleFrames),
  F("uncredited_frames", (t) => t.uncreditedFrames, null),
  T("settled_ms", (t) => t.settledMs),
  T("nav_settled_ms", (t) => t.navSettledMs, null),
  T("next_frame_ms", (t) => t.nextFrameMs, null),
  T("long_task_max_ms", (t) => t.longTasks?.maxMs),
  T("input_span_ms", (t) => t.inputSpanMs, null),
  T("ready_after_last_input_ms", (t) => t.readyAfterLastInputMs),
  T("shell_tools_ready_ms", (t) => t.milestones?.shellToolsReady),
  T("styled_markdown_ms", (t) => t.milestones?.styledMarkdown),
  T("pr_header_ms", (t) => t.milestones?.prHeader),
  T("pr_description_shown_ms", (t) => t.milestones?.prDescriptionShown),
  T("pr_description_final_ms", (t) => t.milestones?.prDescriptionFinal),
  C("requests_data", (t) => t.requests?.byClass?.data ?? 0),
  C("requests_plugin", (t) => t.requests?.byClass?.plugin ?? 0),
  C("requests_static", (t) => t.requests?.byClass?.static ?? 0),
  C("requests_kpress", (t) => t.requests?.byClass?.kpress ?? 0),
  C("requests_background", (t) => t.requests?.byClass?.background ?? 0, null),
  C("subject_duplicates", (t) => t.requests?.subjectDuplicates),
  C("file_envelope_requests", (t) => t.requests?.fileEnvelopes),
  C("post_body_bytes", (t) => t.requests?.postBytes),
  C("preview_top_replaced", (t) => t.previewTop?.removed),
  C("shift_count", (t) => t.shifts?.count),
  { key: "shift_sum_no_input", kind: "value", better: "lower", get: (t) => t.shifts?.sumNoInput },
  C("dom_nodes_end", (t) => t.dom?.end),
  C("region_movement_px", (t) => t.movementPx),
  C("region_movement_net_px", (t) => t.movementNetPx),
  C("region_movement_path_px", (t) => t.movementPathPx),
  C("tree_movement_px", (t) => t.movementByGroup?.tree?.step),
  C("tree_movement_net_px", (t) => t.movementByGroup?.tree?.net),
  C("tree_movement_path_px", (t) => t.movementByGroup?.tree?.path),
  C("tree_movement_frames", (t) => t.movementByGroup?.tree?.frames),
  C("tree_rows_replaced", (t) => t.movementByGroup?.tree?.replaced, null),
  C("palette_movement_px", (t) => t.movementByGroup?.palette?.step),
  C("palette_movement_path_px", (t) => t.movementByGroup?.palette?.path),
  C("list_rows_replaced_below_selection", (t) => t.list?.rowsReplacedBelowSelection),
  C("list_row_replacements", (t) => t.list?.rowReplacements),
  ...["static", "plugin_static", "kpress_static", "data", "document"].flatMap((family) =>
    [
      ["network", "lower"],
      ["revalidated", null],
      ["cache", "higher"],
    ].map(([d, better]) =>
      C(
        `${family}_${d}`,
        (t) => (t.requests?.byFamily ? (t.requests.byFamily[family]?.[d] ?? 0) : undefined),
        better,
      ),
    ),
  ),
];

export const metric = (key) => METRICS.find((m) => m.key === key);

export function median(xs) {
  const s = [...xs].sort((a, b) => a - b);
  const m = Math.floor(s.length / 2);
  return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2;
}

export function stat(xs) {
  if (!xs?.length) {
    return null;
  }
  return { n: xs.length, median: median(xs), min: Math.min(...xs), max: Math.max(...xs) };
}

/** Parse a runs file's text into rows of this scenario. */
export function parseRows(text, file = "rows") {
  const rows = [];
  for (const line of text.split("\n")) {
    if (line.trim()) {
      const row = JSON.parse(line);
      if (row.schema !== SCENARIO) {
        throw new CompareRefusal(`${file} holds a ${row.schema} row; this reads ${SCENARIO}`);
      }
      rows.push(row);
    }
  }
  return rows;
}

/** The identity of a build: version, commit, dirty state, and content identity. */
export const buildIdentity = (b) =>
  `${b?.version} ${b?.commit} ${b?.dirty}${b?.content ? ` ${b.content}` : ""}`;

/** Valid runs per condition, refusing to pool runs of different builds under one label. */
export function groupConditions(rows, { allowMixed = false } = {}) {
  const out = new Map();
  for (const row of rows) {
    if (!out.has(row.condition)) {
      out.set(row.condition, { label: row.condition, valid: [], refused: [] });
    }
    const c = out.get(row.condition);
    (row.valid ? c.valid : c.refused).push(row);
  }
  for (const c of out.values()) {
    const identities = new Set(c.valid.map((r) => buildIdentity(r.build)));
    if (identities.size > 1 && !allowMixed) {
      throw new CompareRefusal(
        `condition ${c.label} pools ${identities.size} builds: ${[...identities].join(" / ")}`,
      );
    }
  }
  return out;
}

/** The back-to-back pair a run belongs to, so a candidate run meets the control run beside it. */
export const pairKey = (row) => row.pair_key ?? `${row.series}#${row.pair}`;

/**
 * transition id -> { subjects, runs, values: metric key -> [{ v, pair }] } across the
 * condition's valid runs. `runs` counts the runs that measured the transition at all.
 */
export function collect(condition) {
  const byId = new Map();
  for (const run of condition.valid) {
    const pair = pairKey(run);
    for (const journey of run.journeys ?? []) {
      for (const t of journey.transitions ?? []) {
        if (!byId.has(t.id)) {
          byId.set(t.id, { id: t.id, subjects: new Set(), runs: 0, values: {} });
        }
        const entry = byId.get(t.id);
        entry.subjects.add(t.subject);
        entry.runs += 1;
        for (const m of METRICS) {
          const v = m.get(t);
          if (v !== null && v !== undefined) {
            entry.values[m.key] ??= [];
            entry.values[m.key].push({ v, pair });
          }
        }
      }
    }
  }
  return byId;
}

const valuesOf = (entry, key) => (entry?.values[key] ?? []).map((x) => x.v);

// Times are frame-clock readings on a grid of about 16.7 ms: one decimal in compare, so
// two ranges that do not overlap never print as if they did.
export function fmtNum(v, kind, decimals = 1) {
  if (kind === "value") {
    return v.toFixed(4);
  }
  if (kind === "time") {
    return decimals ? v.toFixed(decimals) : String(Math.round(v));
  }
  return Math.abs(v - Math.round(v)) < 1e-9 ? String(Math.round(v)) : v.toFixed(1);
}

export function fmtStat(s, kind, decimals = 1) {
  if (!s) {
    return "n/a";
  }
  if (kind === "time") {
    return `${fmtNum(s.median, kind, decimals)} (${fmtNum(s.min, kind, decimals)}–${fmtNum(s.max, kind, decimals)})`;
  }
  if (kind === "frames") {
    return s.min === s.max
      ? fmtNum(s.min, kind)
      : `${fmtNum(s.median, kind)} (${fmtNum(s.min, kind)}–${fmtNum(s.max, kind)})`;
  }
  return s.min === s.max ? fmtNum(s.min, kind) : `${fmtNum(s.min, kind)}–${fmtNum(s.max, kind)}`;
}

function binomial(n, k) {
  let r = 1;
  for (let i = 1; i <= k; i++) {
    r = (r * (n - k + i)) / i;
  }
  return r;
}

/**
 * The chance that two samples of sizes a and b drawn from one continuous distribution
 * have ranges that do not overlap: 2 / C(a + b, a). Ties make it smaller for counts.
 */
export const chanceApart = (a, b) => 2 / binomial(a + b, a);

/** Per-pair ratios candidate / control for one metric of one transition. */
function pairRatios(ea, eb, key) {
  const a = new Map();
  for (const x of ea.values[key] ?? []) {
    a.set(x.pair, x.v);
  }
  const out = [];
  for (const x of eb.values[key] ?? []) {
    if (!a.has(x.pair)) {
      continue;
    }
    const va = a.get(x.pair);
    const r = va === 0 ? (x.v === 0 ? 1 : Number.POSITIVE_INFINITY) : x.v / va;
    out.push({ pair: x.pair, a: va, b: x.v, r });
  }
  return out;
}

/** The judgement of one metric of one transition, both sides having enough values. */
export function judge(m, sa, sb, pairs, tolerance) {
  const overlap = !(sb.min > sa.max || sb.max < sa.min);
  const direction = sb.median > sa.median ? "higher" : sb.median < sa.median ? "lower" : "same";
  const out = { overlap, direction, outcome: "none", verdict: "no detected difference" };
  const worse = m.better === "lower" ? "higher" : m.better === "higher" ? "lower" : null;
  const finish = () => {
    out.wrongWay =
      worse !== null &&
      out.direction === worse &&
      out.outcome !== "none" &&
      out.outcome !== "within";
    return out;
  };
  if (m.kind === "count" || m.kind === "value") {
    if (!overlap) {
      out.outcome = "result";
      out.verdict = `${direction}, ranges apart (result)`;
    }
    return finish();
  }
  if (sa.median === 0 && sb.median > 0) {
    if (!overlap) {
      out.outcome = "result";
      out.verdict = `${direction} from a zero control, ranges apart (result)`;
    }
    return finish();
  }
  const P = pairs.length;
  out.pairs = {
    n: P,
    median: P ? median(pairs.map((p) => p.r)) : null,
    min: P ? Math.min(...pairs.map((p) => p.r)) : null,
    max: P ? Math.max(...pairs.map((p) => p.r)) : null,
    up: pairs.filter((p) => p.r >= tolerance).map((p) => p.pair),
    down: pairs.filter((p) => p.r <= 1 / tolerance).map((p) => p.pair),
  };
  if (P < MIN_RUNS) {
    if (!overlap) {
      out.outcome = "unpaired";
      out.verdict = `${direction}, ranges apart; the tolerance is not judged with ${P} back-to-back pair(s) (gap)`;
    }
    return finish();
  }
  const beyond = direction === "lower" ? out.pairs.down : out.pairs.up;
  const k = beyond.length;
  if (!overlap && k >= 2) {
    out.outcome = "result";
    out.verdict = `${direction}, ranges apart and beyond the ${tolerance}x tolerance in ${k} of ${P} pairs (result)`;
  } else if (!overlap && k === 1) {
    out.outcome = "rerun";
    out.verdict = `${direction}, ranges apart; one pair of ${P} beyond the ${tolerance}x tolerance (${beyond[0]}): rerun that pair back to back and judge the rerun (not yet a result)`;
  } else if (!overlap) {
    out.outcome = "within";
    out.verdict = `${direction}, ranges apart but every pair within the ${tolerance}x tolerance (not a result)`;
  } else if (k >= 2) {
    out.outcome = "explain";
    out.verdict = `ranges overlap, but ${k} of ${P} pairs are ${direction} beyond the ${tolerance}x tolerance: explain before accepting`;
  }
  return finish();
}

const regimeFlags = (r) =>
  r.regime_flags ?? {
    headed: r.headed === true,
    no_warmup: !r.warmup,
    journey_subset: false,
  };

const sameEverywhere = (rows, get, what, refuse) => {
  const values = new Set(rows.map((r) => JSON.stringify(get(r) ?? null)));
  if (values.size > 1) {
    refuse(`${what} differs across the runs: ${[...values].join(" / ")}`);
  }
  return values.size === 1 ? JSON.parse([...values][0]) : null;
};

/**
 * Compare two conditions of a runs file, or one condition against itself (A/A, odd runs
 * against even ones). Throws CompareRefusal when the runs cannot be compared; otherwise
 * returns every judgement, every gap, and the exit code.
 */
export function compareRuns(rows, { control, candidate, aa, tolerance = 1.3, expect = [] } = {}) {
  if (!(tolerance > 1 && tolerance < 2)) {
    throw new CompareRefusal("--tolerance must be above 1 and below 2 (1.3 rough cut; never 2x)");
  }
  const refuse = (msg) => {
    throw new CompareRefusal(msg);
  };
  let input = rows;
  if (aa) {
    // One condition's valid runs in recorded order, odd against even: runs 1 and 2 are
    // the first back-to-back pair, 3 and 4 the second, and so on.
    input = rows
      .filter((r) => r.condition === aa && r.valid)
      .map((r, i) => ({
        ...r,
        condition: `${aa}.${i % 2 === 0 ? "odd" : "even"}`,
        pair_key: `aa#${Math.floor(i / 2) + 1}`,
      }));
    control = `${aa}.odd`;
    candidate = `${aa}.even`;
  } else if (!control || !candidate) {
    refuse("name both conditions: --control LABEL --candidate LABEL (or --aa LABEL)");
  }
  const conditions = groupConditions(input);
  const A = conditions.get(control);
  const B = conditions.get(candidate);
  if (!A || !B || A === B) {
    refuse(`need two distinct conditions; found ${[...conditions.keys()].join(", ") || "none"}`);
  }
  for (const c of [A, B]) {
    if (c.valid.length < MIN_RUNS) {
      refuse(`condition ${c.label} has ${c.valid.length} valid run(s); compare needs ${MIN_RUNS}`);
    }
  }
  const all = [...A.valid, ...B.valid];
  // The corpus and what the server saw of it: the same tree, clean, on the same refs.
  for (const r of all) {
    if (!r.corpus?.commit) {
      refuse(`run ${r.condition} ${r.run} served a corpus with no commit identity`);
    }
    if (r.corpus.dirty !== false) {
      refuse(`run ${r.condition} ${r.run} served a corpus that was not clean`);
    }
    if (r.build?.dirty === true && !r.build.content) {
      refuse(`run ${r.condition} ${r.run} used a dirty build with no content identity`);
    }
  }
  sameEverywhere(all, (r) => r.corpus.commit, "the corpus commit", refuse);
  sameEverywhere(all, (r) => r.corpus.trunk, "the corpus trunk", refuse);
  sameEverywhere(all, (r) => r.facts?.git_log_head, "the head of the server's git log", refuse);
  sameEverywhere(all, (r) => r.server?.indexed_files, "the indexed file count", refuse);
  const revision = sameEverywhere(
    all,
    (r) => r.scenario_revision ?? 1,
    "the scenario revision",
    refuse,
  );
  const flags = sameEverywhere(all, regimeFlags, "the regime (headed, warm-up, journeys)", refuse);
  sameEverywhere(all, (r) => r.journeys_requested, "the journeys requested", refuse);

  const corpus = all[0];
  const notes = [
    `every run served corpus ${corpus.corpus.commit.slice(0, 8)} (trunk ${String(corpus.corpus.trunk).slice(0, 8)}, server git log head ${String(corpus.facts?.git_log_head).slice(0, 8)}, ${corpus.server?.indexed_files} indexed files)`,
  ];
  if (revision !== SCENARIO_REVISION) {
    notes.push(`runs are scenario revision ${revision}; this reads revision ${SCENARIO_REVISION}`);
  }
  if (flags.headed || flags.no_warmup || flags.journey_subset) {
    notes.push(
      `NOT THE STANDARD REGIME: ${[flags.headed && "headed", flags.no_warmup && "no warm-up pass", flags.journey_subset && "a subset of the journeys"].filter(Boolean).join(", ")}`,
    );
  }
  const harnesses = new Set(
    all.map((r) => `${r.harness?.commit}${r.harness?.dirty ? " (dirty)" : ""}`),
  );
  if (harnesses.size > 1) {
    notes.push(`runs used ${harnesses.size} harness states: ${[...harnesses].join(", ")}`);
  }
  const chromes = new Set(all.flatMap((r) => (r.journeys ?? []).map((j) => j.chrome)));
  if (chromes.size > 1) {
    notes.push(`runs used ${chromes.size} Chrome versions: ${[...chromes].join(", ")}`);
  }
  for (const c of [A, B]) {
    if (c.valid.some((r) => r.build?.dirty)) {
      notes.push(
        `condition ${c.label} is a dirty build, identified by its content ${c.valid[0].build.content}`,
      );
    }
    const totals = new Set(
      c.valid.map((r) => JSON.stringify(r.facts?.github?.filter_totals ?? r.facts?.github ?? null)),
    );
    notes.push(`condition ${c.label} saw pull request catalog totals ${[...totals].join(" / ")}`);
  }
  if (buildIdentity(A.valid[0].build) === buildIdentity(B.valid[0].build)) {
    notes.push(
      aa
        ? `A/A comparison of ${aa}: odd-numbered valid runs against even-numbered ones, paired in recorded order`
        : "both conditions report the same build identity: this is an A/A comparison",
    );
  }
  const keysA = new Set(A.valid.map(pairKey));
  const keysB = new Set(B.valid.map(pairKey));
  const paired = [...keysA].filter((k) => keysB.has(k));
  const unpairedA = A.valid.filter((r) => !keysB.has(pairKey(r))).length;
  const unpairedB = B.valid.filter((r) => !keysA.has(pairKey(r))).length;
  if (unpairedA || unpairedB) {
    notes.push(
      `${paired.length} complete back-to-back pair(s); ${unpairedA} ${A.label} and ${unpairedB} ${B.label} run(s) have no valid partner and enter only the pooled ranges`,
    );
  }

  const ca = collect(A);
  const cb = collect(B);
  const entries = [];
  const gaps = [];
  for (const id of new Set([...ca.keys(), ...cb.keys()])) {
    const ea = ca.get(id);
    const eb = cb.get(id);
    if (!ea || !eb) {
      gaps.push({ id, metric: null, reason: `measured only in ${ea ? A.label : B.label}` });
      continue;
    }
    for (const m of METRICS) {
      const va = valuesOf(ea, m.key);
      const vb = valuesOf(eb, m.key);
      if (!va.length && !vb.length) {
        continue;
      }
      const missA = ea.runs - va.length;
      const missB = eb.runs - vb.length;
      if (missA || missB) {
        gaps.push({
          id,
          metric: m.key,
          reason: `missing in ${missA} of ${ea.runs} ${A.label} run(s) and ${missB} of ${eb.runs} ${B.label} run(s)`,
        });
      }
      if (va.length < MIN_RUNS || vb.length < MIN_RUNS) {
        gaps.push({ id, metric: m.key, reason: `not compared: n=${va.length} and ${vb.length}` });
        continue;
      }
      const sa = stat(va);
      const sb = stat(vb);
      const j = judge(m, sa, sb, pairRatios(ea, eb, m.key), tolerance);
      if (j.outcome === "unpaired") {
        gaps.push({ id, metric: m.key, reason: j.verdict });
      }
      entries.push({
        id,
        metric: m.key,
        kind: m.kind,
        judged: m.better !== null,
        control: sa,
        candidate: sb,
        ratio: sa.median > 0 ? sb.median / sa.median : null,
        // Two sides that hold one and the same value in every run cannot come apart.
        chance:
          sa.min === sa.max && sb.min === sb.max && sa.min === sb.min
            ? 0
            : chanceApart(va.length, vb.length),
        ...j,
      });
    }
  }
  const judged = entries.filter((e) => e.judged);
  const wrongWay = judged.filter((e) => e.wrongWay);
  const chanceExpected = entries.reduce((a, e) => a + e.chance, 0);
  const expectations = expect.map((spec) => {
    const [id, key, predicted] = String(spec).split(":");
    const e = entries.find((x) => x.id === id && x.metric === key);
    if (!e || !["lower", "higher"].includes(predicted)) {
      return { spec, found: false, pass: false, conditions: [`no comparison for ${spec}`] };
    }
    const moved = e.direction === predicted;
    const apart = !e.overlap && e.outcome === "result";
    const others = wrongWay.filter((x) => !(x.id === id && x.metric === key));
    return {
      spec,
      found: true,
      pass: moved && apart,
      conditions: [
        `1. the median moved ${predicted}: ${moved ? "yes" : "no"} (${fmtStat(e.control, e.kind)} → ${fmtStat(e.candidate, e.kind)})`,
        `2. the ranges do not overlap at n≥${MIN_RUNS}${e.kind === "time" || e.kind === "frames" ? ", beyond the tolerance on back-to-back pairs" : ""}: ${apart ? "yes" : "no"} (${e.verdict})`,
        `3. nothing else moved the wrong way without being accounted for: ${others.length} wrong-way result(s) elsewhere to account for`,
      ],
    };
  });
  let exitCode = 0;
  if (aa) {
    exitCode = gaps.length ? 1 : 0;
  } else if (wrongWay.length || gaps.length || expectations.some((x) => !x.pass)) {
    exitCode = 1;
  }
  return {
    control: A,
    candidate: B,
    tolerance,
    aa: aa ?? null,
    notes,
    entries,
    gaps,
    wrongWay,
    expectations,
    chanceExpected,
    pairs: paired.length,
    exitCode,
  };
}

export function loadRange(runs) {
  const all = runs.flatMap((r) => [r.load_start?.[0], r.load_end?.[0]]).filter((v) => v != null);
  return all.length ? `${Math.min(...all)}–${Math.max(...all)}` : "n/a";
}

const firstLine = (s) => String(s).split("\n")[0].slice(0, 200);

/** The markdown report of a comparison. */
export function formatComparison(result) {
  const { control: A, candidate: B, tolerance, notes, entries, gaps, expectations } = result;
  const out = [
    `### \`${B.label}\` against \`${A.label}\``,
    "",
    `${A.valid.length} and ${B.valid.length} valid runs (${A.refused.length} and ${B.refused.length} refused), ${result.pairs} back-to-back pair(s). Load average (1 min) ${loadRange(A.valid)} and ${loadRange(B.valid)}. Times and frame counts are judged on back-to-back pairs against the ${tolerance}x tolerance, with the pooled medians and ranges beside them; counts are judged on their ranges.`,
    "",
  ];
  for (const n of notes) {
    out.push(`- ${n}`);
  }
  if (notes.length) {
    out.push("");
  }
  const pr = (e) =>
    e.pairs?.median === null || e.pairs?.median === undefined
      ? "n/a"
      : `${e.pairs.median.toFixed(2)}x (${e.pairs.min.toFixed(2)}–${Number.isFinite(e.pairs.max) ? e.pairs.max.toFixed(2) : "∞"}), ${(e.direction === "lower" ? e.pairs.down : e.pairs.up).length} of ${e.pairs.n} beyond`;
  out.push(
    `| Transition | ${A.label} painted ready ms | ${B.label} painted ready ms | Pair ratio, median (range) | Verdict |`,
    "| --- | ---: | ---: | ---: | --- |",
  );
  for (const e of entries.filter((x) => x.metric === "painted_ready_ms")) {
    out.push(
      `| \`${e.id}\` | ${fmtStat(e.control, "time")} | ${fmtStat(e.candidate, "time")} | ${pr(e)} | ${e.verdict} |`,
    );
  }
  out.push("");
  const listed = entries.filter((e) => e.outcome !== "none");
  const line = (e) =>
    `- \`${e.id}\` ${e.metric}: ${fmtStat(e.control, e.kind)} → ${fmtStat(e.candidate, e.kind)}${e.pairs ? `; pairs ${pr(e)}` : ""}; ${e.verdict}${e.judged ? "" : " [not judged]"}${e.wrongWay ? " [WRONG WAY]" : ""}`;
  if (!listed.length) {
    out.push("No metric has non-overlapping ranges or pairs beyond the tolerance.");
  } else {
    out.push(`Metrics apart or beyond the tolerance (${listed.length}):`, "");
    out.push(...listed.map(line));
  }
  out.push("");
  const byN = new Map();
  for (const e of entries) {
    const k = `${e.control.n} and ${e.candidate.n}`;
    byN.set(k, (byN.get(k) ?? 0) + 1);
  }
  out.push(
    `Chance: two identical builds give non-overlapping ranges with probability 2 / C(a + b, a) per comparison (${[
      ...byN.keys(),
    ]
      .map((k) => {
        const [a, b] = k.split(" and ").map(Number);
        return `${(100 * chanceApart(a, b)).toFixed(1)}% at ${k}`;
      })
      .join(
        ", ",
      )}; lower for counts, which tie). Of these ${entries.length} comparisons, ${entries.filter((e) => e.chance > 0).length} vary at all, and about ${result.chanceExpected.toFixed(0)} of those would come apart by chance alone; ${listed.filter((e) => !e.overlap).length} did.`,
    "",
  );
  if (gaps.length) {
    out.push(`Not compared, or missing values (${gaps.length}):`, "");
    for (const g of gaps) {
      out.push(`- \`${g.id}\`${g.metric ? ` ${g.metric}` : ""}: ${g.reason}`);
    }
    out.push("");
  }
  for (const x of expectations) {
    out.push(`Expected \`${x.spec}\`: ${x.pass ? "met" : "NOT MET"}`, "");
    out.push(...x.conditions.map((c) => `   ${c}`), "");
  }
  const why = result.aa
    ? result.exitCode === 0
      ? "an A/A check, complete; every difference above is the instrument's own spread"
      : `an A/A check with ${gaps.length} gap(s)`
    : result.exitCode === 0
      ? "complete, with no wrong-way result"
      : `${result.wrongWay.length} wrong-way result(s), ${gaps.length} gap(s)${expectations.some((x) => !x.pass) ? ", an expectation not met" : ""}`;
  out.push(`Exit ${result.exitCode}: ${why}.`);
  return out;
}

// ------------------------------------------------------------------------- summarize

const TABLES = [
  {
    title: "Time and frames",
    columns: [
      ["painted_ready_ms", "Painted ready ms, median (range)"],
      ["ready_ms", "Ready read ms"],
      ["blank_frames", "Blank frames"],
      ["blank_frames_after_ready", "Blank after ready"],
      ["placeholder_visible_frames", "Visible placeholder frames"],
      ["nav_placeholder_visible_frames", "Nav placeholder frames"],
      ["settled_ms", "Preview settled ms"],
      ["long_task_max_ms", "Longest task ms"],
    ],
  },
  {
    title: "Requests",
    columns: [
      ["requests_data", "Data"],
      ["requests_plugin", "Plugin modules"],
      ["requests_static", "Static"],
      ["requests_kpress", "KPress"],
      ["requests_background", "Background"],
      ["subject_duplicates", "Subject duplicates"],
    ],
  },
  {
    title: "Stability and DOM",
    columns: [
      ["preview_top_replaced", "Preview top nodes replaced"],
      ["shift_count", "Layout shifts"],
      ["shift_sum_no_input", "Shift without input"],
      ["region_movement_px", "Largest step px"],
      ["region_movement_net_px", "Net px"],
      ["region_movement_path_px", "Path px"],
      ["dom_nodes_end", "DOM nodes after"],
    ],
  },
  {
    title: "Milestones",
    sparse: true,
    columns: [
      ["shell_tools_ready_ms", "Shell tools ready ms"],
      ["styled_markdown_ms", "Styled Markdown ms"],
      ["pr_header_ms", "PR header ms"],
      ["pr_description_shown_ms", "PR description shown ms"],
      ["pr_description_final_ms", "PR description final ms"],
    ],
  },
  {
    title: "Input, lists, and groups",
    sparse: true,
    columns: [
      ["input_span_ms", "Input span ms"],
      ["ready_after_last_input_ms", "Ready after last input ms"],
      ["file_envelope_requests", "File envelopes"],
      ["post_body_bytes", "POST body bytes"],
      ["list_rows_replaced_below_selection", "List rows replaced below selection"],
      ["list_row_replacements", "List row replacements"],
      ["tree_movement_px", "Tree step px"],
      ["tree_movement_net_px", "Tree net px"],
      ["tree_movement_path_px", "Tree path px"],
      ["tree_movement_frames", "Tree movement frames"],
      ["palette_movement_px", "Palette step px"],
    ],
    // A row only when something here differs from a single-input transition's defaults.
    keep: (v) =>
      v.list_row_replacements !== undefined ||
      ["input_span_ms", "post_body_bytes", "tree_movement_path_px", "palette_movement_px"].some(
        (k) => v[k]?.some((x) => x.v > 0),
      ),
  },
  {
    title: "Cache disposition (network / revalidated / cache)",
    sparse: true,
    families: ["static", "plugin_static", "kpress_static", "data", "document"],
    keep: (_v, id) => id.startsWith("landing.") || id.startsWith("reveal."),
  },
];

/** Markdown tables of one condition's valid runs; times are whole milliseconds. */
export function summaryTables(condition) {
  const byId = collect(condition);
  const lines = [];
  for (const table of TABLES) {
    const columns = table.families
      ? table.families.map((f) => [f, f.replace("_", "-")])
      : table.columns;
    const cell = (entry, key) => {
      if (!table.families) {
        return fmtStat(stat(valuesOf(entry, key)), metric(key).kind, 0);
      }
      const parts = ["network", "revalidated", "cache"].map((d) =>
        fmtStat(stat(valuesOf(entry, `${key}_${d}`)), "count"),
      );
      return parts.every((p) => p === "n/a") ? "n/a" : parts.join(" / ");
    };
    const rows = [];
    for (const entry of byId.values()) {
      const cells = columns.map(([key]) => cell(entry, key));
      if (table.sparse && cells.every((c) => c === "n/a")) {
        continue;
      }
      if (table.keep && !table.keep(entry.values, entry.id)) {
        continue;
      }
      rows.push(`| \`${entry.id}\` | ${cells.join(" | ")} |`);
    }
    if (table.sparse && rows.length === 0) {
      continue;
    }
    lines.push(`#### ${table.title}`, "");
    lines.push(`| Transition | ${columns.map((c) => c[1]).join(" | ")} |`);
    lines.push(`| --- | ${columns.map(() => "---:").join(" | ")} |`);
    lines.push(...rows, "");
  }
  return lines;
}

/** The markdown summary of every condition (or one) in a runs file. */
export function summarize(rows, { condition = null, allowMixed = false } = {}) {
  const conditions = groupConditions(rows, { allowMixed });
  const out = [];
  for (const c of [...conditions.values()].filter((x) => !condition || x.label === condition)) {
    const builds = [...new Set(c.valid.map((r) => r.build.version))];
    out.push(`### Condition \`${c.label}\``, "");
    out.push(
      `${c.valid.length} valid run(s), ${c.refused.length} refused; build ${builds.join(", ") || "n/a"}; load average (1 min) ${loadRange(c.valid)} at run start and end.`,
      "",
    );
    for (const r of c.refused) {
      out.push(
        `- refused run ${r.run} (${r.series}): ${r.refusals
          .slice(0, 3)
          .map((x) => firstLine(x.join(": ")))
          .join(" | ")}`,
      );
    }
    const entries = [...collect(c).values()];
    for (const e of entries.filter((x) => x.subjects.size > 1)) {
      out.push(`- subject drift in \`${e.id}\`: ${[...e.subjects].join(", ")}`);
    }
    for (const e of entries) {
      for (const m of METRICS) {
        const n = (e.values[m.key] ?? []).length;
        if (n && n < e.runs) {
          out.push(`- \`${e.id}\` ${m.key}: missing in ${e.runs - n} of ${e.runs} run(s)`);
        }
      }
    }
    if (out[out.length - 1] !== "") {
      out.push("");
    }
    out.push(...summaryTables(c));
  }
  return out;
}

/** summarize --format json: per condition, per transition, every metric's stat. */
export function summarizeJson(rows, { condition = null, allowMixed = false } = {}) {
  const out = {};
  for (const c of groupConditions(rows, { allowMixed }).values()) {
    if (condition && c.label !== condition) {
      continue;
    }
    out[c.label] = Object.fromEntries(
      [...collect(c).values()].map((e) => [
        e.id,
        {
          subjects: [...e.subjects],
          runs: e.runs,
          ...Object.fromEntries(Object.keys(e.values).map((k) => [k, stat(valuesOf(e, k))])),
        },
      ]),
    );
  }
  return out;
}

// --------------------------------------------------------------------------- samples

/** An absolute path in free text, reduced to its last component. */
export function scrubText(s) {
  return String(s)
    .replace(
      /(?:file:\/\/)?(?:\/(?:Users|home|private|var|tmp|opt|Volumes)\/[^\s:"'),]+)/g,
      (p) => `…/${path.basename(p)}`,
    )
    .slice(0, 600);
}

const scrubRefusals = (list) => (list ?? []).map(([guard, detail]) => [guard, scrubText(detail)]);

/** One transition, reduced to what summarize and compare read. */
export function keepTransition(t) {
  return {
    id: t.id,
    subject: t.subject,
    ok: t.ok,
    refusals: scrubRefusals(t.refusals),
    readyMs: t.readyMs,
    paintedReadyMs: t.paintedReadyMs,
    nextFrameMs: t.nextFrameMs,
    framesToReady: t.framesToReady,
    framesInWindow: t.framesInWindow,
    frameIntervalMs: t.frameIntervalMs,
    blankFrames: t.blankFrames,
    blankFramesAfterReady: t.blankFramesAfterReady,
    blankMs: t.blankMs,
    placeholderVisibleFrames: t.placeholderVisibleFrames,
    placeholderVisibleFramesAfterReady: t.placeholderVisibleFramesAfterReady,
    navPlaceholderVisibleFrames: t.navPlaceholderVisibleFrames,
    uncreditedFrames: t.uncreditedFrames,
    settledMs: t.settledMs,
    navSettledMs: t.navSettledMs,
    movementPx: t.movementPx,
    movementNetPx: t.movementNetPx,
    movementPathPx: t.movementPathPx,
    movementByGroup: t.movementByGroup,
    requests: {
      byClass: t.requests?.byClass,
      subjectDuplicates: t.requests?.subjectDuplicates,
      byFamily: t.requests?.byFamily,
      fileEnvelopes: t.requests?.fileEnvelopes,
      postBytes: t.requests?.postBytes,
    },
    previewTop: { removed: t.previewTop?.removed },
    shifts: { count: t.shifts?.count, sumNoInput: t.shifts?.sumNoInput },
    longTasks: { maxMs: t.longTasks?.maxMs },
    dom: { end: t.dom?.end },
    inputSpanMs: t.inputSpanMs,
    readyAfterLastInputMs: t.readyAfterLastInputMs,
    milestones: t.milestones,
    milestonesMissing: t.milestonesMissing,
    list: t.list
      ? {
          rowReplacements: t.list.rowReplacements,
          rowsReplacedBelowSelection: t.list.rowsReplacedBelowSelection,
        }
      : undefined,
    load1: t.load1,
  };
}

/** One run, reduced to what summarize and compare read, with paths and logs removed. */
export function sampleRow(r) {
  const { journeys, regime: _regime, regions: _regions, ...rest } = r;
  const scrub = (p) => (typeof p === "string" ? path.basename(p) : p);
  return {
    ...rest,
    refusals: scrubRefusals(rest.refusals),
    build: { ...rest.build, metab: scrub(rest.build?.metab), source: scrub(rest.build?.source) },
    build_end: rest.build_end
      ? {
          ...rest.build_end,
          metab: scrub(rest.build_end.metab),
          source: scrub(rest.build_end.source),
        }
      : undefined,
    corpus: { ...rest.corpus, path: scrub(rest.corpus?.path) },
    corpus_end: rest.corpus_end
      ? { ...rest.corpus_end, path: scrub(rest.corpus_end.path) }
      : undefined,
    server: rest.server ? { ...rest.server, serving_line: undefined, log: undefined } : rest.server,
    warmup:
      (rest.warmup ?? undefined) &&
      rest.warmup.map((w) => ({ ...w, refusals: scrubRefusals(w.refusals) })),
    journeys: (journeys ?? []).map((j) => ({
      name: j.name,
      ok: j.ok,
      chrome: j.chrome,
      refusals: scrubRefusals(j.refusals),
      facts: j.facts,
      transitions: (j.transitions ?? []).map(keepTransition),
    })),
  };
}

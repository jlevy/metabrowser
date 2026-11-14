// exp-079's judgments, mechanically, as exp-079-protocol.txt registers them: each included
// hypothesis on the deciding metrics and guards of the record that accepted it, by the
// runbook's accept rule (compare's pair rule at 1.3 for times and frames, ranges for counts
// and values), its third clause seeing only that record's own table. Clause 4, the
// complexity judgment, is not here.
//
//   node exp-079-analyze.mjs HARNESS JUDGED_SAMPLES.jsonl H92_H106.jsonl SKIM.jsonl OUT.json
//
// HARNESS is the frozen harness checkout (3a1ff25e); compare is its compareRuns, run with
// the Commits landings allowed to differ (registration, "Commits landings"). The inputs are
// the judged pairs' samples (exp-079-exclude.mjs --split), and the two derived files from
// their full rows: exp-065-instruments/derive-h92-h106.mjs's output and exp-079-derive.mjs's.
//
// Rules this script applies, fixed before any exp-079 result was read:
// - A transition whose recorded Commits landing differs between a judged pair's two runs is
//   reported and not judged, wherever it appears (registration, "Commits landings").
// - Deciding, "lower" or "higher": compare's median moved that way, and compare's outcome is
//   a result (counts and values: ranges apart; times and frames: ranges apart with two or
//   more pairs beyond 1.3x). A per-run derived count: medians moved that way, ranges apart.
//   "Not higher": not a result in the higher direction.
// - Guards and the rest of the record's table: compare's wrong-way flag in the worse
//   direction with a result or an explain outcome (two or more pairs beyond 1.3x under
//   overlapping ranges), as exp-086 states the rule. compare also flags a rerun (ranges
//   apart, one pair beyond), which it calls not yet a result; it is listed with that
//   account and does not block, as exp-065 read its guards.
// - A wrong-way result is accounted for only by a rule its record declared (exp-085's E1 to
//   E3 for H91 (c)'s guard; exp-087's later-frame test for H87's frame-level metrics on
//   three views), or where the record accepted the same metric on the same transitions
//   moving the same way and gave its account (exp-065 for H92 (a) and (c), exp-080 for
//   H106: the first-paint hold, which is the change). Each such account is named in the
//   output, so it can be read apart.
// - Verdict: accepted when every judged deciding metric passes and every wrong-way result in
//   the table is accounted for; rejected when a deciding metric is a result the other way,
//   or a rule the record declared rejects it; otherwise unresolved. With no deciding metric
//   judged, not measured.
import fs from "node:fs";
import path from "node:path";

const [harness, samplesPath, derivedPath, skimPath, outPath] = process.argv.slice(2);
if (!harness || !samplesPath || !derivedPath || !skimPath || !outPath) {
  throw new Error(
    "usage: exp-079-analyze.mjs HARNESS JUDGED_SAMPLES.jsonl H92_H106.jsonl SKIM.jsonl OUT.json",
  );
}
const { compareRuns, median } = await import(
  path.join(harness, "explorations/performance-loop/transitions-stats.mjs")
);
const readJsonl = (p) =>
  fs
    .readFileSync(p, "utf8")
    .split("\n")
    .filter(Boolean)
    .map((line) => JSON.parse(line));
const rows = readJsonl(samplesPath);
const derived = readJsonl(derivedPath);
const skim = readJsonl(skimPath);
const CONTROL = "control";
const CANDIDATE = "candidate";
const TOLERANCE = 1.3;

const compared = compareRuns(rows, {
  control: CONTROL,
  candidate: CANDIDATE,
  tolerance: TOLERANCE,
  mixedLanding: true,
});
const entries = compared.entries;
const entry = (id, metric) => entries.find((e) => e.id === id && e.metric === metric) ?? null;

// ------------------------------------------------------------------ pairs and landings
const pairOf = (r) => `${r.series}#${r.pair}`;
const transitionsOf = (r) => (r.journeys ?? []).flatMap((j) => j.transitions ?? []);
const pairs = new Map();
for (const r of rows.filter((x) => x.valid)) {
  if (!pairs.has(pairOf(r))) {
    pairs.set(pairOf(r), {});
  }
  pairs.get(pairOf(r))[r.condition] = r;
}
const landed = new Map();
for (const [key, p] of pairs) {
  if (!p[CONTROL] || !p[CANDIDATE]) {
    continue;
  }
  const mine = new Map(
    transitionsOf(p[CANDIDATE])
      .filter((t) => t.landing !== undefined && t.landing !== null)
      .map((t) => [t.id, t.landing]),
  );
  for (const t of transitionsOf(p[CONTROL])) {
    if (t.landing === undefined || t.landing === null || !mine.has(t.id)) {
      continue;
    }
    if (mine.get(t.id) !== t.landing) {
      if (!landed.has(t.id)) {
        landed.set(t.id, new Set());
      }
      landed.get(t.id).add(`${t.landing} / ${mine.get(t.id)} (${key})`);
    }
  }
}
const isLanded = (id) => landed.has(id);

// ------------------------------------------------------------------ per-run readings
const round = (v, d = 4) => (typeof v === "number" ? Math.round(v * 10 ** d) / 10 ** d : v);
const statOf = (xs) =>
  xs.length
    ? { n: xs.length, median: median(xs), min: Math.min(...xs), max: Math.max(...xs) }
    : null;
/** values: [{ condition, pair, v }]; counts and values, judged on their ranges. */
function perRun(name, values) {
  const side = (c) => values.filter((x) => x.condition === c && typeof x.v === "number");
  const a = side(CONTROL);
  const b = side(CANDIDATE);
  const sa = statOf(a.map((x) => x.v));
  const sb = statOf(b.map((x) => x.v));
  if (!sa || !sb || sa.n < 3 || sb.n < 3) {
    return { name, control: sa, candidate: sb, outcome: "gap", direction: null, overlap: null };
  }
  const overlap = !(sb.min > sa.max || sb.max < sa.min);
  const direction = sb.median > sa.median ? "higher" : sb.median < sa.median ? "lower" : "same";
  const ratios = b
    .map((x) => {
      const y = a.find((z) => z.pair === x.pair);
      return y ? (y.v === 0 ? (x.v === 0 ? 1 : null) : round(x.v / y.v, 3)) : undefined;
    })
    .filter((r) => r !== undefined);
  return {
    name,
    control: sa,
    candidate: sb,
    overlap,
    direction,
    outcome: overlap ? "none" : "result",
    verdict: overlap ? "ranges overlap" : `${direction}, ranges apart (result)`,
    pairRatios: ratios,
  };
}
const runPair = new Map(rows.map((r) => [`${r.condition}#${r.run}`, pairOf(r)]));
const derivedRun = derived.filter((r) => r.kind === "run");
// A run that measured none of a reading's transitions has no value for it.
const MEASURED = {
  subjectDuplicatesOnClicks: "clicksMeasured",
  changesBodyShiftAfterReady: "changesMeasured",
  plainFirstTransitions: "conversationTransitions",
  conversationBodyShiftAfterReady: "conversationTransitions",
};
const derivedValues = (key) =>
  derivedRun
    .filter((r) => (r[MEASURED[key]] ?? 0) > 0)
    .map((r) => ({
      condition: r.condition,
      pair: runPair.get(`${r.condition}#${r.run}`),
      v: r[key],
    }));

// ------------------------------------------------------------------ judging
const _NUMERIC = (e) => e.kind === "count" || e.kind === "value";
const show = (e) =>
  e
    ? {
        id: e.id,
        metric: e.metric,
        kind: e.kind,
        control: e.control,
        candidate: e.candidate,
        pairs: e.pairs
          ? {
              n: e.pairs.n,
              median: round(e.pairs.median, 3),
              min: round(e.pairs.min, 3),
              max: round(e.pairs.max, 3),
              up: e.pairs.up.length,
              down: e.pairs.down.length,
            }
          : undefined,
        direction: e.direction,
        outcome: e.outcome,
        verdict: e.verdict,
        wrongWay: e.wrongWay,
      }
    : null;
function deciding(id, metric, predicted) {
  if (isLanded(id)) {
    return { id, metric, predicted, status: "not judged: the Commits landing differs" };
  }
  const e = entry(id, metric);
  if (!e) {
    return { id, metric, predicted, status: "gap: no comparison" };
  }
  const moved = e.direction === predicted;
  const apart = e.outcome === "result";
  const opposite = !moved && e.direction !== "same" && e.outcome === "result";
  return {
    ...show(e),
    predicted,
    clause1: moved,
    clause2: apart,
    status: moved && apart ? "pass" : opposite ? "opposite result" : "fail",
  };
}
function notHigher(id, metric) {
  if (isLanded(id)) {
    return {
      id,
      metric,
      predicted: "not higher",
      status: "not judged: the Commits landing differs",
    };
  }
  const e = entry(id, metric);
  if (!e) {
    return { id, metric, predicted: "not higher", status: "gap: no comparison" };
  }
  const rose = e.direction === "higher" && e.outcome === "result";
  return { ...show(e), predicted: "not higher", status: rose ? "fail" : "pass" };
}
function decidingRun(result, predicted) {
  if (result.outcome === "gap") {
    return { ...result, predicted, status: "gap" };
  }
  const moved = result.direction === predicted;
  const apart = result.outcome === "result";
  const opposite = !moved && result.direction !== "same" && apart;
  return {
    ...result,
    predicted,
    clause1: moved,
    clause2: apart,
    status: moved && apart ? "pass" : opposite ? "opposite result" : "fail",
  };
}
/** The table's wrong-way results, each with the account its record allows, if any. */
function tableWrongWay(cells, account = () => null) {
  const out = [];
  const seen = new Set();
  for (const [id, metric] of cells) {
    const k = `${id}|${metric}`;
    if (seen.has(k)) {
      continue;
    }
    seen.add(k);
    if (isLanded(id)) {
      continue;
    }
    const e = entry(id, metric);
    if (e?.wrongWay) {
      const rerun =
        e.outcome === "rerun"
          ? "a rerun, not a result: ranges apart with one pair beyond 1.3x (compare)"
          : null;
      out.push({ ...show(e), accountedBy: rerun ?? account(e) });
    }
  }
  return out;
}
const cross = (ids, metrics) => ids.flatMap((id) => metrics.map((m) => [id, m]));
const idsMatching = (re) => [...new Set(entries.map((e) => e.id))].filter((id) => re.test(id));
const cellsOf = (ids) => entries.filter((e) => ids.includes(e.id)).map((e) => [e.id, e.metric]);
function verdictOf(decide, wrong, extra = {}) {
  const judged = decide.filter(
    (d) => d.status !== undefined && !String(d.status).startsWith("not judged"),
  );
  if (!judged.length) {
    return "not measured";
  }
  if (extra.rejected || judged.some((d) => d.status === "opposite result")) {
    return "rejected";
  }
  const decided = judged.every((d) => d.status === "pass");
  const accounted = wrong.every((w) => w.accountedBy);
  return decided && accounted && !extra.unresolved ? "accepted" : "unresolved";
}

const hypotheses = [];

// H86 (a), exp-059 (exp-059-064-protocol.txt).
{
  const T27 = [
    "files.cold.source_large",
    "files.cold.json",
    "files.cold.diff",
    "files.cold.image",
    "files.cold.binary",
    "files.revisit.json",
    "keyboard.down_cold.1",
    "keyboard.down_cold.2",
    "keyboard.down_cold.3",
    "keyboard.up_revisit.1",
    "keyboard.up_revisit.2",
    "main.files_to_commits.first",
    "main.commits_to_files.first",
    "main.files_to_commits.again",
    "main.commits_to_files.again",
    "main.files_to_pulls.first",
    "main.pulls_to_files.first",
    "main.files_to_pulls.again",
    "main.pulls_to_files.again",
    "main_subject.files_to_commits",
    "main_subject.pulls_to_files",
    "main_subject.files_to_pulls",
    "main_subject.commits_to_files",
    "commits.first_show",
    "pulls.first_show",
    "tree.expand.docs",
    "skim.held_arrow_down",
  ];
  const decide = [
    ...T27.map((id) => deciding(id, "region_movement_px", "lower")),
    deciding("landing.reload", "shift_sum_no_input", "lower"),
  ];
  const guards = cross(T27, ["painted_ready_ms", "blank_frames"]);
  const wrong = tableWrongWay([...decide.map((d) => [d.id, d.metric]), ...guards]).filter(
    (w) => !decide.some((d) => d.id === w.id && d.metric === w.metric),
  );
  hypotheses.push({
    id: "H86 (a)",
    record: "exp-059",
    deciding: decide,
    wrongWay: wrong,
    verdict: verdictOf(decide, wrong),
  });
}
// H86 (b), exp-059.
{
  const T8 = [
    "pulls.tab.changes_first",
    "pulls.tab.checks_first",
    "pulls.tab.changes_revisit",
    "pulls.tab.conversation_revisit_2",
    "pulls.tab.changes_first_2",
    "pulls.tab.changes_revisit_2",
    "pulls.history_back",
    "pulls.pr_changes_to_pr",
  ];
  const NO_RISE = ["pulls.list_to_pr.cold", ...idsMatching(/^pulls\.pr_to_pr\./)];
  const decide = [
    ...T8.map((id) => deciding(id, "region_movement_px", "lower")),
    ...NO_RISE.map((id) => notHigher(id, "region_movement_px")),
  ];
  const guards = cross([...T8, ...NO_RISE], ["painted_ready_ms", "pr_header_ms"]);
  const wrong = tableWrongWay(guards);
  hypotheses.push({
    id: "H86 (b)",
    record: "exp-059",
    deciding: decide,
    wrongWay: wrong,
    verdict: verdictOf(decide, wrong),
  });
}
// H91 (a), (b), (d), exp-064.
for (const [part, id, metric, guards] of [
  [
    "H91 (a)",
    "landing.cold_markdown",
    "shift_sum_no_input",
    ["painted_ready_ms", "styled_markdown_ms", "blank_frames"],
  ],
  ["H91 (b)", "reveal.deep_landing", "shift_sum_no_input", ["painted_ready_ms", "blank_frames"]],
  ["H91 (d)", "palette.query", "list_row_replacements", ["painted_ready_ms"]],
]) {
  const decide = [deciding(id, metric, "lower")];
  const wrong = tableWrongWay(cross([id], guards));
  const shown = part === "H91 (d)" ? [show(entry(id, "list_rows_replaced_below_selection"))] : [];
  hypotheses.push({
    id: part,
    record: "exp-064",
    deciding: decide,
    shown,
    wrongWay: wrong,
    verdict: verdictOf(decide, wrong),
  });
}
// H91 (c), exp-085 (with exp-064's guards on the single presses).
{
  const id = "skim.held_arrow_down";
  const decide = [deciding(id, "file_envelope_requests", "lower")];
  const guard = entry(id, "ready_after_last_input_ms");
  // exp-085's evidence E1 to E3, from the skim's full rows.
  const by = (c) => skim.filter((s) => s.condition === c && s.measured);
  const cand = by(CANDIDATE);
  const ctrl = by(CONTROL);
  const e1 =
    cand.length > 0 &&
    cand.every((s) => s.readyAfterLastInputMs !== null && s.readyAfterLastInputMs < 120);
  const e3 =
    cand.length > 0 && cand.every((s) => s.blankFrames === 0 && s.placeholderVisibleFrames === 0);
  const beyond = [];
  for (const s of cand) {
    const c = ctrl.find((x) => `${x.series}#${x.pair}` === `${s.series}#${s.pair}`);
    if (!c?.readyAfterLastInputMs) {
      continue;
    }
    const ratio = s.readyAfterLastInputMs / c.readyAfterLastInputMs;
    if (ratio >= TOLERANCE) {
      const excess = s.readyAfterLastInputMs - c.readyAfterLastInputMs;
      const spanExcess =
        s.lastSelectToReadyMs !== null && c.lastSelectToReadyMs !== null
          ? s.lastSelectToReadyMs - c.lastSelectToReadyMs
          : null;
      const blocking = Math.max(s.longTaskTotalMs ?? 0, s.loafMaxBlockingMs ?? 0);
      const matched =
        (spanExcess !== null && Math.abs(excess - spanExcess) <= 16.7) || blocking >= excess;
      beyond.push({
        pair: `${s.series}#${s.pair}`,
        ratio: round(ratio, 3),
        excess: round(excess, 1),
        spanExcess: round(spanExcess, 1),
        blocking,
        matched,
      });
    }
  }
  const e2 = beyond.every((b) => b.matched);
  let guardStatus = "holds";
  let rejected = false;
  let unresolved = false;
  if (isLanded(id) || !guard) {
    guardStatus = "gap";
    unresolved = true;
  } else if (guard.direction === "higher" && guard.outcome === "result") {
    guardStatus = "a guard result: rejected (exp-085)";
    rejected = true;
  } else if (guard.direction === "higher" && guard.outcome === "explain") {
    guardStatus =
      e1 && e2 && e3 ? "explained by E1, E2 and E3 (exp-085)" : "not explained (exp-085)";
    unresolved = !(e1 && e2 && e3);
  } else if (guard.direction === "higher" && guard.outcome === "rerun") {
    // Ranges apart with one pair beyond: exp-085's "fewer than two pairs beyond 1.3x".
    guardStatus = "holds: one pair beyond 1.3x (exp-085, fewer than two pairs beyond)";
  } else if (guard.wrongWay) {
    guardStatus = `wrong-way (${guard.outcome}), not a case exp-085 names`;
    unresolved = true;
  }
  const others = cross(
    [id],
    ["painted_ready_ms", "blank_frames", "placeholder_visible_frames"],
  ).concat(
    cross(
      ["keyboard.down_cold.1", "keyboard.down_cold.2", "keyboard.down_cold.3"],
      ["painted_ready_ms"],
    ),
  );
  const wrong = tableWrongWay(others);
  hypotheses.push({
    id: "H91 (c)",
    record: "exp-085",
    deciding: decide,
    shown: [show(entry(id, "requests_data"))],
    guard: { ...show(guard), status: guardStatus, evidence: { e1, e2, e3, beyond } },
    wrongWay: wrong,
    verdict: verdictOf(decide, wrong, { rejected, unresolved }),
  });
}
// H92 (a) and (c), exp-065; H106, exp-080 (exp-065-080-protocol.txt).
const CLICKS = [
  "pulls.list_to_pr.cold",
  "pulls.pr_to_pr.cold",
  "pulls.pr_to_pr.revisit",
  "pulls.pr_to_pr.hover_click",
  "pulls.pr_changes_to_pr",
];
const COLD_CLICKS = CLICKS.filter((id) => id !== "pulls.pr_to_pr.revisit");
const CHANGES = [
  "pulls.tab.changes_first",
  "pulls.tab.changes_revisit",
  "pulls.tab.changes_first_2",
  "pulls.tab.changes_revisit_2",
];
// Correction, after the results were read: the version amendment 3 names (sha256
// b09ab7c8...) carried a record's account to every transition and metric it listed, which is
// broader than amendment 3's rule ("the same metric on the same transitions moving the same
// way"). Each record's cells are now named one by one, as its own tables give them: a cell
// carries the account only where that record shows the candidate higher. The correction
// only narrows what is accounted for.
const HELD = {
  // exp-065's guard table and "What moved the wrong way" (the holds).
  "exp-065": [
    ["pulls.pr_to_pr.cold", "pr_description_shown_ms"],
    ["pulls.pr_to_pr.hover_click", "pr_description_shown_ms"],
    ["pulls.pr_changes_to_pr", "pr_description_shown_ms"],
    ["pulls.list_to_pr.cold", "pr_description_final_ms"],
    ["pulls.pr_to_pr.hover_click", "pr_description_final_ms"],
    ["pulls.pr_changes_to_pr", "pr_description_final_ms"],
    ...CHANGES.map((id) => [id, "painted_ready_ms"]),
  ],
  // exp-080's guard table: every cell whose candidate median is above the control's.
  "exp-080": [
    ...[
      "pulls.pr_to_pr.cold",
      "pulls.pr_to_pr.revisit",
      "pulls.pr_to_pr.hover_click",
      "pulls.pr_changes_to_pr",
      "pulls.history_back",
    ].map((id) => [id, "pr_description_shown_ms"]),
    ...[
      "pulls.list_to_pr.cold",
      "pulls.pr_to_pr.hover_click",
      "pulls.pr_changes_to_pr",
      "pulls.history_back",
    ].map((id) => [id, "pr_description_final_ms"]),
    ...[
      "pulls.list_to_pr.cold",
      "pulls.pr_to_pr.cold",
      "pulls.pr_to_pr.revisit",
      "pulls.pr_to_pr.hover_click",
      "pulls.pr_changes_to_pr",
      "pulls.history_back",
    ].map((id) => [id, "painted_ready_ms"]),
  ],
};
const holdAccount = (record) => (e) =>
  e.direction === "higher" && HELD[record].some(([id, m]) => id === e.id && m === e.metric)
    ? `${record}: the first-paint hold, which is the change (that record shows the same metric on the same transition higher, and accepted it)`
    : null;
{
  const decide = [
    decidingRun(
      perRun(
        "per run: duplicate reads over the five clicks",
        derivedValues("subjectDuplicatesOnClicks"),
      ),
      "lower",
    ),
  ];
  const detail = CLICKS.map((id) => notHigher(id, "subject_duplicates"));
  const guards = cross(COLD_CLICKS, ["pr_description_shown_ms", "pr_description_final_ms"]);
  const wrong = tableWrongWay(guards, holdAccount("exp-065"));
  hypotheses.push({
    id: "H92 (a)",
    record: "exp-065",
    deciding: [...decide, ...detail],
    wrongWay: wrong,
    verdict: verdictOf([...decide, ...detail], wrong),
  });
}
hypotheses.push({
  id: "H92 (b)",
  record: "exp-065",
  verdict: "not measured",
  reason:
    "decided on the pilot tree probe (probe-tree-late.mjs); the scenario's warm server cannot produce a late file list",
});
{
  const decide = [
    decidingRun(
      perRun(
        "per run: body shift after ready, the four Changes paints",
        derivedValues("changesBodyShiftAfterReady"),
      ),
      "lower",
    ),
  ];
  const wrong = tableWrongWay(cross(CHANGES, ["painted_ready_ms"]), holdAccount("exp-065"));
  hypotheses.push({
    id: "H92 (c)",
    record: "exp-065",
    deciding: decide,
    wrongWay: wrong,
    verdict: verdictOf(decide, wrong),
  });
}
{
  const conversation = [
    ...new Set(
      rows.flatMap((r) =>
        transitionsOf(r)
          .filter((t) => t.milestones && "prDescriptionShown" in t.milestones)
          .map((t) => t.id),
      ),
    ),
  ].sort();
  const prIds = [...new Set(entries.map((e) => e.id))].filter(
    (id) => id.startsWith("pulls.") || /_to_pulls$/.test(id),
  );
  const decide = [
    decidingRun(
      perRun(
        "per run: Conversation transitions whose description showed before its final form",
        derivedValues("plainFirstTransitions"),
      ),
      "lower",
    ),
  ];
  const metric2 = [
    (() => {
      const r = perRun(
        "per run: body shift after ready, every Conversation transition",
        derivedValues("conversationBodyShiftAfterReady"),
      );
      return {
        ...r,
        predicted: "not higher",
        status:
          r.outcome === "gap"
            ? "gap"
            : r.direction === "higher" && r.outcome === "result"
              ? "fail"
              : "pass",
      };
    })(),
    ...prIds.flatMap((id) => [
      notHigher(id, "preview_top_replaced"),
      notHigher(id, "shift_sum_no_input"),
    ]),
  ];
  const guards = [
    ...cross(COLD_CLICKS, ["pr_description_final_ms", "pr_description_shown_ms"]),
    ...cross(conversation, ["painted_ready_ms"]),
  ];
  const wrong = tableWrongWay(guards, holdAccount("exp-080"));
  hypotheses.push({
    id: "H106",
    record: "exp-080",
    deciding: decide,
    metric2,
    conversationTransitions: conversation,
    wrongWay: wrong,
    verdict: verdictOf([...decide, ...metric2.filter((m) => m.status === "fail")], wrong),
  });
}
// H87, exp-083, with exp-087's later-frame reading for its third clause.
function logFact(n) {
  let s = 0;
  for (let i = 2; i <= n; i += 1) {
    s += Math.log(i);
  }
  return s;
}
const hyper = (a, b, c, d) =>
  Math.exp(
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
/** exp-087's two-sided Fisher exact p for [[a, b], [c, d]], margins fixed. */
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
const VIEWS = ["files.cold.json", "files.cold.image", "files.revisit.markdown_large"];
// exp-083 listed these on the three views as one frame later; exp-087 accounted for them as
// the frame-quantization race when no view lands on a later frame more often (p >= 0.05).
const FRAME_LEVEL = [
  "painted_ready_ms",
  "ready_ms",
  "ready_after_last_input_ms",
  "frames_to_ready",
  "settled_ms",
  "blank_frames",
  "blank_ms",
];
const laterFrame = {};
for (const v of VIEWS) {
  const vals = { [CONTROL]: [], [CANDIDATE]: [] };
  for (const r of rows.filter((x) => x.valid)) {
    const t = transitionsOf(r).find((x) => x.id === v);
    if (t && typeof t.framesToReady === "number") {
      vals[r.condition].push(t.framesToReady);
    }
  }
  const counts = {};
  for (const f of [...vals[CONTROL], ...vals[CANDIDATE]]) {
    counts[f] = (counts[f] ?? 0) + 1;
  }
  const top = Math.max(...Object.values(counts));
  const M = Math.min(
    ...Object.entries(counts)
      .filter(([, n]) => n === top)
      .map(([f]) => Number(f)),
  );
  const a = vals[CANDIDATE].filter((f) => f > M).length;
  const b = vals[CANDIDATE].length - a;
  const c = vals[CONTROL].filter((f) => f > M).length;
  const d = vals[CONTROL].length - c;
  const p = fisher(a, b, c, d);
  laterFrame[v] = {
    M,
    frameCounts: counts,
    candidate: `${a}/${a + b} later`,
    control: `${c}/${c + d} later`,
    p: round(p, 4),
    differs: p < 0.05,
  };
}
{
  const FAMILIES = ["static", "plugin_static", "kpress_static", "data", "document"];
  const reval = rows
    .filter((r) => r.valid)
    .map((r) => {
      const t = transitionsOf(r).find((x) => x.id === "landing.reload");
      const by = t?.requests?.byFamily;
      return {
        condition: r.condition,
        pair: pairOf(r),
        v: by ? FAMILIES.reduce((s, f) => s + (by[f]?.revalidated ?? 0), 0) : null,
      };
    });
  const decide = [
    decidingRun(perRun("revalidated_total.landing.reload (five families)", reval), "lower"),
  ];
  const guard = entry("landing.reload", "painted_ready_ms");
  const check = entry("files.revisit.source_large", "long_task_max_ms");
  const cold = ["painted_ready_ms", "blank_frames", "blank_ms", "placeholder_visible_frames"].map(
    (m) => show(entry("landing.cold_markdown", m)),
  );
  const scope = cellsOf(idsMatching(/^(landing|files)\./));
  const account = (e) =>
    VIEWS.includes(e.id) &&
    FRAME_LEVEL.includes(e.metric) &&
    laterFrame[e.id] &&
    !laterFrame[e.id].differs
      ? `exp-087's later-frame reading: ${e.id} lands on a later frame ${laterFrame[e.id].candidate} against ${laterFrame[e.id].control}, Fisher p=${laterFrame[e.id].p}`
      : null;
  const wrong = tableWrongWay(scope, account);
  hypotheses.push({
    id: "H87",
    record: "exp-083 (third clause as in exp-087)",
    deciding: decide,
    guard: show(guard),
    declaredCheck: show(check),
    coldMarkdownPrediction: cold,
    laterFrame,
    wrongWay: wrong,
    verdict: verdictOf(decide, wrong),
  });
}
// H88 (a), exp-086.
{
  const decide = ["commits.revisit.1", "commits.revisit.2"].flatMap((id) => [
    deciding(id, "requests_data", "lower"),
    deciding(id, "painted_ready_ms", "lower"),
  ]);
  const scope = cellsOf(idsMatching(/^commits\.|^main_subject\..*commits/));
  const wrong = tableWrongWay(scope).filter(
    (w) => !decide.some((d) => d.id === w.id && d.metric === w.metric),
  );
  const allValid = rows.every((r) => r.valid);
  hypotheses.push({
    id: "H88 (a)",
    record: "exp-086",
    deciding: decide,
    allRunsValid: allValid,
    wrongWay: wrong,
    verdict: verdictOf(decide, wrong, { unresolved: !allValid }),
  });
}
hypotheses.push({
  id: "H88 (b)",
  record: "exp-086",
  verdict: "not measured",
  reason: "decided on git-route-pairs.mjs, the server half, not on this scenario's rows",
});

// ------------------------------------------------------------------ the campaign summary
const ids = [...new Set(entries.map((e) => e.id))];
const summary = ids.map((id) => ({
  id,
  landing: isLanded(id) ? [...landed.get(id)] : null,
  painted_ready_ms: show(entry(id, "painted_ready_ms")),
  shift_sum_no_input: show(entry(id, "shift_sum_no_input")),
  region_movement_net_px: show(entry(id, "region_movement_net_px")),
}));
const out = {
  inputs: {
    samples: path.basename(samplesPath),
    derived: path.basename(derivedPath),
    skim: path.basename(skimPath),
  },
  pairs: compared.pairs,
  runs: { control: compared.control.valid.length, candidate: compared.candidate.valid.length },
  notes: compared.notes,
  chanceExpected: round(compared.chanceExpected, 2),
  gaps: compared.gaps,
  landingDiffers: Object.fromEntries([...landed].map(([id, s]) => [id, [...s]])),
  hypotheses,
  summary,
  wrongWay: compared.wrongWay.map(show),
};
fs.writeFileSync(outPath, `${JSON.stringify(out, null, 1)}\n`);
for (const h of hypotheses) {
  const failing = (h.deciding ?? []).filter(
    (d) => d.status && d.status !== "pass" && !String(d.status).startsWith("not judged"),
  );
  const unaccounted = (h.wrongWay ?? []).filter((w) => !w.accountedBy);
  console.log(
    `${h.id} (${h.record}): ${h.verdict}${failing.length ? `; deciding not met: ${failing.map((d) => `${d.id ?? d.name} ${d.metric ?? ""} ${d.status}`).join(", ")}` : ""}${unaccounted.length ? `; unaccounted wrong-way: ${unaccounted.map((w) => `${w.id} ${w.metric}`).join(", ")}` : ""}`,
  );
}
console.log(
  `pairs ${out.pairs}; wrong-way ${out.wrongWay.length}; gaps ${out.gaps.length}; landing differs on ${Object.keys(out.landingDiffers).join(", ") || "none"}`,
);

// Statistics for the wkwebview-probe/v1 rows that wkprobe.mjs writes: how a step's
// proxy requests are counted, each run's relaunch freshness regime, the metrics a row
// yields, `summarize`, and `compare`.
//
// Pure functions over parsed rows, so tests/dom/wkprobe-compare-behavior.mjs can drive
// every refusal and verdict from fixture rows. The accept rule's arithmetic is the
// transition scenario's own: `judge`, the back-to-back pair ratios, build identity, and
// the request classes of `transitions-recorder.mjs`, so the campaign's two `compare`s
// cannot drift apart.
import { requestClass, routeFamily } from "./transitions-recorder.mjs";
import {
  CompareRefusal,
  chanceApart,
  fmtStat,
  groupConditions,
  judge,
  loadRange,
  MIN_RUNS,
  pairKey,
  pairRatios,
  sameEverywhere,
  stat,
} from "./transitions-stats.mjs";

export { CompareRefusal, MIN_RUNS };

export const SCHEMA = "wkwebview-probe/v1";
// 2 times show-to-ready to the first painted frame with ready content, loads
// `hidden-then-show` into a store of its own, counts background, stream, and outgoing
// requests apart from the judged totals, and records the relaunch's freshness inputs.
// compare reads revision 2 only: revision 1 rows mean something else in every one of
// those figures, and none was ever valid outside a locked-screen test.
export const PROBE_REVISION = 2;

// ------------------------------------------------------------------------- requests

const DOCUMENT_PATH = /^\/(view|commit|pull|pulls)(\/|$)/;

/** A proxy path's request class and route family, by the transition recorder's rules. */
export function classify(urlPath) {
  const p = String(urlPath).split("?")[0];
  const type = DOCUMENT_PATH.test(p) || p === "/" ? "Document" : undefined;
  const url = `http://127.0.0.1${urlPath}`;
  return { cls: requestClass(url, type), family: routeFamily(url, type) };
}

// Classes kept out of the judged totals: the Pulls catalog's own timer work and the event
// stream, which run however long a step's window stays open.
const UNJUDGED_CLASSES = new Set(["background", "stream"]);

/**
 * The counts of one step, from the proxy entries between its marks and the page's own
 * Resource Timing list. On a reload the outgoing page lives until the new document
 * commits, so a request logged before the step's own document request is the outgoing
 * page's, counted as `outgoing` and nowhere else. A page entry with no matching proxy
 * request in the step was served from WebKit's cache.
 */
export function requestCounts(entries, resources) {
  const proxy = { total: 0, conditional: 0, outgoing: 0, byClass: {}, byFamily: {} };
  const list = entries ?? [];
  const docAt = list.findIndex((e) => classify(e.url).cls === "document");
  const own = docAt > 0 ? list.slice(docAt) : list;
  proxy.outgoing = list.length - own.length;
  for (const e of own) {
    const { cls, family } = classify(e.url);
    proxy.byClass[cls] = (proxy.byClass[cls] ?? 0) + 1;
    if (UNJUDGED_CLASSES.has(cls)) {
      continue;
    }
    proxy.total += 1;
    if (e.inm || e.ims) {
      proxy.conditional += 1;
    }
    proxy.byFamily[family] ??= { network: 0, revalidated: 0, error: 0 };
    const d = e.status === 304 ? "revalidated" : e.status && e.status < 400 ? "network" : "error";
    proxy.byFamily[family][d] += 1;
  }
  const page = { entries: 0, byFamily: {} };
  const reached = new Map();
  for (const e of own) {
    reached.set(e.url, (reached.get(e.url) ?? 0) + 1);
  }
  for (const [u] of resources ?? []) {
    const { cls, family } = classify(u);
    if (UNJUDGED_CLASSES.has(cls)) {
      continue;
    }
    page.entries += 1;
    page.byFamily[family] ??= { entries: 0, cache: 0 };
    page.byFamily[family].entries += 1;
    const n = reached.get(u) ?? 0;
    if (n > 0) {
      reached.set(u, n - 1);
    } else {
      page.byFamily[family].cache += 1;
    }
  }
  return { proxy, page };
}

// ------------------------------------------------------------------------- freshness

const ASSET_FAMILIES = new Set(["static", "plugin_static", "kpress_static"]);
// A Cache-Control directive that decides freshness by itself; without one, WebKit keeps a
// response with a Last-Modified fresh for a tenth of its age when it was validated.
const FRESHNESS_DIRECTIVE = /(?:^|[,\s])(?:max-age|s-maxage|no-cache|no-store)\b/i;
// Seconds of margin on either side of a heuristic lifetime: the relaunch looks an asset up
// a few seconds after it starts, and Last-Modified and Date have a resolution of 1 s.
export const FRESHNESS_GUARD_S = 5;

const range = (xs) =>
  xs.length ? [Math.round(Math.min(...xs) * 10) / 10, Math.round(Math.max(...xs) * 10) / 10] : null;

/**
 * How the assets the first launch stored will be judged at the relaunch, from the first
 * launch's proxy entries: each asset URL's last validation (its last logged response),
 * its Last-Modified (a 304 carries none, so the 200 before it gives it), and its
 * Cache-Control. An asset whose headers decide is counted in `by_headers`. For each
 * asset judged by age, `margin_s` ranges over its heuristic lifetime minus the time from
 * that validation to the relaunch's start: positive is fresh, negative stale.
 */
export function relaunchFreshness(entries, relaunchStartMs) {
  const byUrl = new Map();
  for (const e of entries ?? []) {
    if (e.mark || !e.status || e.status >= 400 || !ASSET_FAMILIES.has(classify(e.url).family)) {
      continue;
    }
    const u = byUrl.get(e.url) ?? { lm: null };
    u.t = e.t;
    u.cc = e.cc ?? null;
    if (e.lm) {
      u.lm = e.lm;
    }
    byUrl.set(e.url, u);
  }
  let byHeaders = 0;
  const ages = [];
  const margins = [];
  for (const u of byUrl.values()) {
    const lm = u.lm ? Date.parse(u.lm) : Number.NaN;
    // No directive and no Last-Modified: nothing makes it fresh, whatever its age.
    if ((u.cc && FRESHNESS_DIRECTIVE.test(u.cc)) || !Number.isFinite(lm)) {
      byHeaders += 1;
      continue;
    }
    const age = (u.t - lm) / 1000;
    ages.push(age);
    margins.push(0.1 * age - (relaunchStartMs - u.t) / 1000);
  }
  return {
    by_headers: byHeaders,
    by_age: ages.length,
    age_s: range(ages),
    margin_s: range(margins),
  };
}

/**
 * A run's relaunch regime: `by-headers` when every asset's freshness came from its
 * headers, so install age plays no part; `fresh` or `stale` when every asset judged by
 * age was fresh, or stale, by more than the guard; `mixed` when some were near or on
 * either side of their lifetime; `unknown` when the row has no record.
 */
export function relaunchRegime(row) {
  const f = row?.relaunch_freshness;
  if (!f) {
    return "unknown";
  }
  if (!f.by_age) {
    return "by-headers";
  }
  const [lo, hi] = f.margin_s;
  if (lo > FRESHNESS_GUARD_S) {
    return "fresh";
  }
  if (hi < -FRESHNESS_GUARD_S) {
    return "stale";
  }
  return "mixed";
}

/**
 * Why `relaunch.*` cannot be judged across these conditions, or null when it can. Counts
 * and times at a relaunch depend on how many assets WebKit revalidates, and for an asset
 * with no freshness directive that depends on how old the install was. Two conditions
 * whose assets were judged by age must share a regime; a condition whose headers decide
 * may be compared with either, because then the headers are what differs.
 */
export function relaunchBlock(regimesA, regimesB, labels) {
  if (!regimesA.length || !regimesB.length) {
    return null;
  }
  const odd = [...regimesA, ...regimesB].find((r) => r === "mixed" || r === "unknown");
  if (odd) {
    return `a run's relaunch regime is ${odd}, so its counts depend on when each asset was installed`;
  }
  if (regimesA.length > 1 || regimesB.length > 1) {
    return `the relaunch regime differs between runs of one condition (${labels[0]} ${regimesA.join("/")}, ${labels[1]} ${regimesB.join("/")})`;
  }
  const [a] = regimesA;
  const [b] = regimesB;
  if (a !== b && a !== "by-headers" && b !== "by-headers") {
    return `${labels[0]}'s assets were ${a} and ${labels[1]}'s ${b} at the relaunch by their install age alone`;
  }
  return null;
}

// ------------------------------------------------------------------------- metrics

const bool01 = (v) => (v === true ? 1 : v === false ? 0 : undefined);

// `kind` and `better` as in transitions-stats.mjs: a `time` is judged on back-to-back
// pairs against the tolerance, a `count` on its ranges, and `better: null` marks a figure
// shown but not judged. `conditional` names the outcome a figure exists only after, so a
// run without it is not missing a value.
const T = (key, get, better = "lower", conditional = null) => ({
  key,
  kind: "time",
  better,
  get,
  conditional,
});
const C = (key, get, better = "lower") => ({ key, kind: "count", better, get, conditional: null });

export const FAMILIES = ["document", "static", "plugin_static", "kpress_static", "data"];

export const METRICS = [
  T("ready_ms", (s) => s.readyMs),
  T("mounted_ms", (s) => s.mountedMs),
  T("commit_ms", (s) => s.commitMs),
  T("show_to_painted_ready_ms", (s) => s.showToPaintedReadyMs),
  T("show_to_first_frame_ms", (s) => s.showToFirstFrameMs, null),
  T("show_to_ready_dom_ms", (s) => s.showToReadyDomMs, null),
  C("mounted_while_hidden", (s) => bool01(s.hiddenMounted), "higher"),
  C("ready_while_hidden", (s) => bool01(s.hiddenReady), "higher"),
  T("hidden_mounted_ms", (s) => s.hiddenMountedMs, "lower", "mounted while hidden"),
  T("hidden_ready_ms", (s) => s.hiddenReadyMs, null, "ready while hidden"),
  C("requests", (s) => s.proxy?.total),
  C("conditional_requests", (s) => s.proxy?.conditional),
  C("requests_background", (s) => (s.proxy ? (s.proxy.byClass?.background ?? 0) : undefined), null),
  C("requests_stream", (s) => (s.proxy ? (s.proxy.byClass?.stream ?? 0) : undefined), null),
  C("requests_outgoing", (s) => s.proxy?.outgoing, null),
  ...FAMILIES.flatMap((f) => [
    C(`${f}_network`, (s) => (s.proxy ? (s.proxy.byFamily?.[f]?.network ?? 0) : undefined)),
    C(
      `${f}_revalidated`,
      (s) => (s.proxy ? (s.proxy.byFamily?.[f]?.revalidated ?? 0) : undefined),
      null,
    ),
    C(`${f}_cache`, (s) => (s.page ? (s.page.byFamily?.[f]?.cache ?? 0) : undefined), "higher"),
  ]),
];

export const metric = (key) => METRICS.find((m) => m.key === key);

/** scenario -> { id, runs, values: metric key -> [{ v, pair }] } over the valid runs. */
export function collect(condition) {
  const byId = new Map();
  for (const run of condition.valid) {
    const pair = pairKey(run);
    for (const [id, sc] of Object.entries(run.scenarios ?? {})) {
      if (!byId.has(id)) {
        byId.set(id, { id, runs: 0, values: {} });
      }
      const entry = byId.get(id);
      entry.runs += 1;
      for (const m of METRICS) {
        const v = m.get(sc);
        if (v !== null && v !== undefined) {
          entry.values[m.key] ??= [];
          entry.values[m.key].push({ v, pair });
        }
      }
    }
  }
  return byId;
}

const valuesOf = (entry, key) => (entry?.values[key] ?? []).map((x) => x.v);

/** Parse a runs file's text into rows of this probe. */
export function parseRows(text, file = "rows") {
  const rows = [];
  for (const line of text.split("\n")) {
    if (line.trim()) {
      const row = JSON.parse(line);
      if (row.schema !== SCHEMA) {
        throw new CompareRefusal(`${file} holds a ${row.schema} row; this reads ${SCHEMA}`);
      }
      rows.push(row);
    }
  }
  return rows;
}

const FMT_DECIMALS = 0;

// ------------------------------------------------------------------------- compare

/**
 * Compare two conditions of a runs file under the accept rule. Throws CompareRefusal when
 * the runs cannot be compared; otherwise returns every judgement, every gap, and the exit
 * code: 0 complete with no wrong-way result, 1 on a wrong-way result, a gap, or an
 * expectation not met.
 */
export function compareProbe(rows, { control, candidate, tolerance = 1.3, expect = [] } = {}) {
  const refuse = (msg) => {
    throw new CompareRefusal(msg);
  };
  if (!(tolerance > 1 && tolerance < 2)) {
    refuse("--tolerance must be above 1 and below 2 (1.3 rough cut; never 2x)");
  }
  if (!control || !candidate) {
    refuse("name both conditions: --control LABEL --candidate LABEL");
  }
  const conditions = groupConditions(rows);
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
  for (const r of all) {
    if ((r.probe_revision ?? 1) !== PROBE_REVISION) {
      refuse(
        `run ${r.condition} ${r.run} is probe revision ${r.probe_revision ?? 1}; compare reads revision ${PROBE_REVISION} only`,
      );
    }
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
  sameEverywhere(all, (r) => r.corpus.refs, "the hash of the corpus refs", refuse);
  sameEverywhere(all, (r) => r.facts?.git_log_head, "the head of the server's git log", refuse);
  sameEverywhere(all, (r) => r.server?.indexed_files, "the indexed file count", refuse);
  sameEverywhere(all, (r) => r.scenarios_requested, "the scenarios requested", refuse);
  sameEverywhere(all, (r) => r.viewport, "the viewport", refuse);
  sameEverywhere(all, (r) => r.device_pixel_ratio, "the device pixel ratio", refuse);
  const flags = sameEverywhere(all, (r) => r.regime_flags, "the regime flags", refuse);

  const notes = [
    `every run served corpus ${all[0].corpus.commit.slice(0, 8)} (${all[0].server?.indexed_files} indexed files) at ${all[0].viewport}, device pixel ratio ${all[0].device_pixel_ratio}`,
  ];
  if (flags?.no_preflight || flags?.exit_delay_ms) {
    notes.push(
      `NOT THE STANDARD REGIME: ${[flags.no_preflight && "no screen preflight", flags.exit_delay_ms && `a ${flags.exit_delay_ms} ms delay before each probe exits`].filter(Boolean).join(", ")}`,
    );
  }
  for (const [what, get] of [
    ["WebKit versions", (r) => r.webkit?.webkitVersion],
    ["macOS builds", (r) => r.host?.macos_build],
    ["harness states", (r) => `${r.harness?.commit}${r.harness?.dirty ? " (dirty)" : ""}`],
  ]) {
    const set = new Set(all.map(get));
    if (set.size > 1) {
      notes.push(`runs used ${set.size} ${what}: ${[...set].join(", ")}`);
    }
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
  const regimes = (c) => [
    ...new Set(c.valid.filter((r) => r.scenarios?.relaunch).map(relaunchRegime)),
  ];
  const ra = regimes(A);
  const rb = regimes(B);
  const block = relaunchBlock(ra, rb, [A.label, B.label]);
  if (ra.length && rb.length) {
    notes.push(
      `relaunch regime: ${A.label} ${ra.join("/")}, ${B.label} ${rb.join("/")}${block ? "; relaunch is not judged" : ""}`,
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
  const conditional = [];
  for (const id of new Set([...ca.keys(), ...cb.keys()])) {
    const ea = ca.get(id);
    const eb = cb.get(id);
    if (!ea || !eb) {
      gaps.push({ id, metric: null, reason: `measured only in ${ea ? A.label : B.label}` });
      continue;
    }
    if (id === "relaunch" && block) {
      gaps.push({ id, metric: null, reason: `not judged: ${block}` });
      continue;
    }
    for (const m of METRICS) {
      const va = valuesOf(ea, m.key);
      const vb = valuesOf(eb, m.key);
      if (!va.length && !vb.length) {
        continue;
      }
      if (m.conditional) {
        if (va.length < MIN_RUNS || vb.length < MIN_RUNS) {
          conditional.push({
            id,
            metric: m.key,
            reason: `exists only in runs ${m.conditional}: ${va.length} of ${ea.runs} ${A.label} and ${vb.length} of ${eb.runs} ${B.label} run(s); not compared`,
          });
          continue;
        }
      } else {
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
        chance:
          sa.min === sa.max && sb.min === sb.max && sa.min === sb.min
            ? 0
            : chanceApart(va.length, vb.length),
        ...j,
      });
    }
  }
  const wrongWay = entries.filter((e) => e.judged && e.wrongWay);
  const expectations = expect.map((spec) => {
    const s = String(spec);
    const colon = s.lastIndexOf(":");
    const dot = s.indexOf(".");
    const id = s.slice(0, dot);
    const key = s.slice(dot + 1, colon);
    const predicted = s.slice(colon + 1);
    const e = entries.find((x) => x.id === id && x.metric === key);
    if (dot <= 0 || colon <= dot || !e || !["lower", "higher"].includes(predicted)) {
      return { spec: s, found: false, pass: false, conditions: [`no comparison for ${s}`] };
    }
    const moved = e.direction === predicted;
    const apart = !e.overlap && e.outcome === "result";
    const others = wrongWay.filter((x) => !(x.id === id && x.metric === key));
    return {
      spec: s,
      found: true,
      pass: moved && apart,
      conditions: [
        `1. the median moved ${predicted}: ${moved ? "yes" : "no"} (${fmtStat(e.control, e.kind, FMT_DECIMALS)} → ${fmtStat(e.candidate, e.kind, FMT_DECIMALS)})`,
        `2. the ranges do not overlap at n≥${MIN_RUNS}${e.kind === "time" ? ", beyond the tolerance on back-to-back pairs" : ""}: ${apart ? "yes" : "no"} (${e.verdict})`,
        `3. nothing else moved the wrong way without being accounted for: ${others.length} wrong-way result(s) elsewhere to account for`,
      ],
    };
  });
  const exitCode = wrongWay.length || gaps.length || expectations.some((x) => !x.pass) ? 1 : 0;
  return {
    control: A,
    candidate: B,
    tolerance,
    notes,
    entries,
    gaps,
    conditional,
    wrongWay,
    expectations,
    chanceExpected: entries.reduce((a, e) => a + e.chance, 0),
    pairs: paired.length,
    exitCode,
  };
}

/** The markdown report of a comparison. */
export function formatComparison(result) {
  const { control: A, candidate: B, tolerance, notes, entries, gaps, conditional } = result;
  const out = [
    `### \`${B.label}\` against \`${A.label}\` in WKWebView`,
    "",
    `${A.valid.length} and ${B.valid.length} valid runs (${A.refused.length} and ${B.refused.length} refused), ${result.pairs} back-to-back pair(s). Load average (1 min) ${loadRange(A.valid)} and ${loadRange(B.valid)}. Times are judged on back-to-back pair ratios against the ${tolerance}x tolerance, with the pooled medians and ranges beside them; counts are judged on their ranges.`,
    "",
    ...notes.map((n) => `- ${n}`),
    "",
  ];
  const pr = (e) =>
    e.pairs?.median === null || e.pairs?.median === undefined
      ? "n/a"
      : `${e.pairs.median.toFixed(2)}x (${e.pairs.min.toFixed(2)}–${Number.isFinite(e.pairs.max) ? e.pairs.max.toFixed(2) : "∞"}), ${(e.direction === "lower" ? e.pairs.down : e.pairs.up).length} of ${e.pairs.n} beyond`;
  out.push(
    `| Metric | ${A.label} | ${B.label} | Pair ratio, median (range) | Verdict |`,
    "| --- | ---: | ---: | ---: | --- |",
  );
  for (const e of entries) {
    if (e.outcome === "none" && e.control.max === 0 && e.candidate.max === 0) {
      continue;
    }
    out.push(
      `| \`${e.id}.${e.metric}\` | ${fmtStat(e.control, e.kind, FMT_DECIMALS)} | ${fmtStat(e.candidate, e.kind, FMT_DECIMALS)} | ${pr(e)} | ${e.verdict}${e.judged ? "" : " [not judged]"}${e.wrongWay ? " [WRONG WAY]" : ""} |`,
    );
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
      )}; lower for counts, which tie). Of these ${entries.length} comparisons, ${entries.filter((e) => e.chance > 0).length} vary at all, and about ${result.chanceExpected.toFixed(0)} of those would come apart by chance alone; ${entries.filter((e) => !e.overlap).length} did.`,
    "",
  );
  if (gaps.length) {
    out.push(`Not compared, or missing values (${gaps.length}):`, "");
    for (const g of gaps) {
      out.push(`- \`${g.id}\`${g.metric ? ` ${g.metric}` : ""}: ${g.reason}`);
    }
    out.push("");
  }
  if (conditional.length) {
    out.push(`Figures that exist only after an outcome, not compared (${conditional.length}):`, "");
    for (const g of conditional) {
      out.push(`- \`${g.id}\` ${g.metric}: ${g.reason}`);
    }
    out.push("");
  }
  for (const x of result.expectations) {
    out.push(`Expected \`${x.spec}\`: ${x.pass ? "met" : "NOT MET"}`, "");
    out.push(...x.conditions.map((c) => `   ${c}`), "");
  }
  const why =
    result.exitCode === 0
      ? "complete, with no wrong-way result"
      : `${result.wrongWay.length} wrong-way result(s), ${gaps.length} gap(s)${result.expectations.some((x) => !x.pass) ? ", an expectation not met" : ""}`;
  out.push(`Exit ${result.exitCode}: ${why}.`);
  return out;
}

// ------------------------------------------------------------------------- summarize

const firstLine = (s) => String(s).split("\n")[0].slice(0, 200);

/** The markdown summary of every condition in a runs file. */
export function summarize(rows) {
  const lines = [];
  for (const c of groupConditions(rows).values()) {
    const v0 = c.valid[0];
    const regimes = c.valid.filter((r) => r.scenarios?.relaunch).map((r) => `${relaunchRegime(r)}`);
    lines.push(`### Condition \`${c.label}\``, "");
    lines.push(
      `${c.valid.length} valid run(s), ${c.refused.length} refused; ${v0?.build.version ?? "no valid run"}; macOS ${v0?.host?.macos ?? "?"}, WebKit ${v0?.webkit?.webkitVersion ?? "?"}, device pixel ratio ${v0?.device_pixel_ratio ?? "?"}; load average (1 min) ${loadRange(c.valid)}${regimes.length ? `; relaunch regime by run: ${regimes.join(", ")}` : ""}.`,
      "",
    );
    for (const r of c.refused) {
      lines.push(
        `- refused run ${r.run}: ${(r.refusals ?? [])
          .slice(0, 3)
          .map((x) => firstLine(x.join(": ")))
          .join(" | ")}`,
      );
    }
    const byId = collect(c);
    for (const e of byId.values()) {
      for (const m of METRICS) {
        const n = (e.values[m.key] ?? []).length;
        if (n && n < e.runs && !m.conditional) {
          lines.push(`- \`${e.id}\` ${m.key}: missing in ${e.runs - n} of ${e.runs} run(s)`);
        }
      }
    }
    if (lines[lines.length - 1] !== "") {
      lines.push("");
    }
    lines.push(
      "| Scenario | Ready ms | Requests | Conditional | Background | network / revalidated / cache by family |",
      "| --- | ---: | ---: | ---: | ---: | --- |",
    );
    const cell = (e, key) => fmtStat(stat(valuesOf(e, key)), metric(key).kind, FMT_DECIMALS);
    for (const e of byId.values()) {
      const shown = e.values.show_to_painted_ready_ms;
      const fams = FAMILIES.map(
        (f) =>
          `${f.replace("_static", "-static")} ${["network", "revalidated", "cache"].map((d) => cell(e, `${f}_${d}`)).join(" / ")}`,
      ).join("; ");
      lines.push(
        `| \`${e.id}\`${shown ? " (show to painted ready)" : ""} | ${cell(e, shown ? "show_to_painted_ready_ms" : "ready_ms")} | ${cell(e, "requests")} | ${cell(e, "conditional_requests")} | ${cell(e, "requests_background")} | ${fams} |`,
      );
    }
    const h = byId.get("hidden-then-show");
    if (h) {
      const ones = (key) => valuesOf(h, key).filter((x) => x === 1).length;
      lines.push(
        "",
        `Hidden then shown: mounted while hidden in ${ones("mounted_while_hidden")} of ${h.runs} runs (at ${cell(h, "hidden_mounted_ms")} ms), ready while hidden in ${ones("ready_while_hidden")} of ${h.runs}; show to first frame ${cell(h, "show_to_first_frame_ms")} ms, to painted ready ${cell(h, "show_to_painted_ready_ms")} ms (the DOM ready read ${cell(h, "show_to_ready_dom_ms")} ms).`,
      );
    }
    lines.push("");
  }
  return lines;
}

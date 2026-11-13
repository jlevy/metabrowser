// The WKWebView probe's compare decisions, browserless: request counting over proxy
// entries, the relaunch freshness regime, the per-metric minimum and gap listing, the
// back-to-back pair rule, expectations, refusals, and the command's exit code. Imports
// the exact modules a series runs; no server, WebKit, or clock is used.
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

const HERE = import.meta.dirname;
const LOOP = path.resolve(HERE, "../../explorations/performance-loop");
const stats = await import(path.join(LOOP, "wkprobe-stats.mjs"));
const {
  CompareRefusal,
  FRESHNESS_GUARD_S,
  PROBE_REVISION,
  compareProbe,
  formatComparison,
  relaunchFreshness,
  relaunchRegime,
  requestCounts,
} = stats;

let checks = 0;
const check = (name, fn) => {
  try {
    fn();
  } catch (error) {
    throw new Error(`${name}: ${error.message}`, { cause: error });
  }
  checks += 1;
};

// ------------------------------------------------------------ requests

check("background, stream, and outgoing requests stay out of the judged totals", () => {
  const e = (url, status = 200, extra = {}) => ({ url, status, t: 0, ...extra });
  const { proxy, page } = requestCounts(
    [
      // The outgoing page's timers, before the reload's own document request.
      e("/api/plugin/github/pulls?state=all&limit=8&after=16"),
      e("/api/file?path=README.md"),
      e("/view/README.md"),
      e("/static/app.js?v=1", 304, { ims: true }),
      e("/static/app.css?v=1"),
      e("/api/plugin/github/pulls?state=all&limit=8"),
      e("/api/plugin/github/pulls-refresh"),
      e("/api/events", null),
      e("/api/file?path=README.md"),
    ],
    [
      ["/static/app.js?v=1"],
      ["/static/app.css?v=1"],
      ["/static/icons.js?v=1"],
      ["/api/file?path=README.md"],
      ["/api/plugin/github/pulls?state=all&limit=8"],
    ],
  );
  assert.equal(proxy.outgoing, 2);
  assert.equal(proxy.total, 4);
  assert.equal(proxy.conditional, 1);
  assert.equal(proxy.byClass.background, 2);
  assert.equal(proxy.byClass.stream, 1);
  assert.deepEqual(proxy.byFamily.static, { network: 1, revalidated: 1, error: 0 });
  assert.deepEqual(proxy.byFamily.data, { network: 1, revalidated: 0, error: 0 });
  // The page listed icons.js and no request reached the proxy for it: a cache hit. The
  // walk's own entry is background and not counted on either side.
  assert.deepEqual(page.byFamily.static, { entries: 3, cache: 1 });
  assert.deepEqual(page.byFamily.data, { entries: 1, cache: 0 });
});

// ------------------------------------------------------------ freshness

const LM = "Mon, 09 Nov 2026 12:00:00 GMT";
const at = (iso) => Date.parse(iso);
check("freshness reads the last validation and the Last-Modified before a 304", () => {
  const t0 = at("2026-11-09T12:10:00Z"); // assets 600 s old: fresh for 60 s
  const f = relaunchFreshness(
    [
      { url: "/static/a.js?v=1", status: 200, t: t0, lm: LM, cc: null },
      // The reload's 304 carries no Last-Modified; the age is from the 200's.
      { url: "/static/a.js?v=1", status: 304, t: t0 + 20000, lm: null, cc: null },
      { url: "/plugin-static/p/index.js", status: 200, t: t0, lm: LM, cc: "no-cache" },
      { url: "/api/file?path=README.md", status: 200, t: t0, lm: LM, cc: null },
      { mark: "load", at: "start", t: t0 },
    ],
    t0 + 30000,
    t0 + 60000,
  );
  assert.equal(f.by_headers, 1);
  assert.equal(f.by_age, 1);
  // At the spawn, 0.1 * 620 s - (30 - 20) s = 52 s; at the step's end, 62 - 40 = 22 s.
  assert.deepEqual(f.assets, [["/static/a.js?v=1", 52, 22]]);
  assert.deepEqual(f.margin_at_start_s, [52, 52]);
  assert.deepEqual(f.margin_at_end_s, [22, 22]);
});
check("a 304 without Cache-Control keeps the 200's directive", () => {
  const t0 = at("2026-11-09T12:10:00Z");
  const f = relaunchFreshness(
    [
      { url: "/static/a.js?v=1", status: 200, t: t0, lm: LM, cc: "max-age=600" },
      { url: "/static/a.js?v=1", status: 304, t: t0 + 20000, lm: null, cc: null },
    ],
    t0 + 30000,
  );
  assert.equal(f.by_headers, 1);
  assert.equal(f.by_age, 0);
  assert.equal(relaunchRegime({ relaunch_freshness: f }), "by-headers");
});
check("assets held no-cache by --stale-assets make a stale regime", () => {
  const t0 = at("2026-11-09T12:10:00Z");
  const f = relaunchFreshness(
    [
      { url: "/static/a.js?v=1", status: 200, t: t0, lm: LM, cc: "no-cache", held: true },
      { url: "/plugin-static/p/index.js", status: 200, t: t0, lm: null, cc: "no-cache" },
    ],
    t0 + 30000,
  );
  assert.deepEqual([f.held_stale, f.by_headers, f.by_age], [1, 1, 0]);
  assert.equal(relaunchRegime({ relaunch_freshness: f }), "stale");
});
const fresh = (start, end = start) => ({
  by_headers: 0,
  held_stale: 0,
  by_age: 40,
  margin_at_start_s: start,
  margin_at_end_s: end,
});
check("a relaunch regime is fresh, stale, mixed, by headers, or unknown", () => {
  const g = FRESHNESS_GUARD_S;
  assert.equal(relaunchRegime({ relaunch_freshness: fresh([g + 1, 900]) }), "fresh");
  assert.equal(relaunchRegime({ relaunch_freshness: fresh([-900, -g - 1]) }), "stale");
  assert.equal(relaunchRegime({ relaunch_freshness: fresh([-30, 30]) }), "mixed");
  assert.equal(relaunchRegime({ relaunch_freshness: fresh([1, 900]) }), "mixed");
  // Fresh at the spawn but within the guard of its lifetime by the step's end.
  assert.equal(relaunchRegime({ relaunch_freshness: fresh([30, 900], [1, 870]) }), "mixed");
  assert.equal(
    relaunchRegime({
      relaunch_freshness: { by_headers: 40, held_stale: 0, by_age: 0, assets: [] },
    }),
    "by-headers",
  );
  assert.equal(relaunchRegime({}), "unknown");
});

// ------------------------------------------------------------ fixture rows

const scenario = (name, over = {}) => ({
  name,
  refusals: [],
  readyMs: 300,
  mountedMs: 360,
  commitMs: 40,
  raf: 60,
  dpr: 2,
  proxy: {
    total: 100,
    conditional: 0,
    outgoing: 0,
    byClass: { static: 40, data: 60, background: 3 },
    byFamily: { static: { network: 40, revalidated: 0, error: 0 } },
  },
  page: { entries: 100, byFamily: { static: { entries: 40, cache: 0 } } },
  ...over,
});

const row = (condition, pair, names) => ({
  schema: "wkwebview-probe/v1",
  probe_revision: PROBE_REVISION,
  name: "fixture",
  series: "s1",
  condition,
  run: pair,
  pair,
  valid: true,
  build: { version: `metab ${condition}`, commit: condition, dirty: false, content: null },
  harness: { commit: "h", dirty: false },
  corpus: { commit: "c".repeat(40), dirty: false, trunk: "t", refs: "r" },
  facts: { git_log_head: "g", github: { filter_totals: { open: 1, closed: 9 } } },
  server: { indexed_files: 10 },
  host: { macos_build: "25F" },
  webkit: { webkitVersion: "21623" },
  viewport: "1440x900",
  device_pixel_ratio: 2,
  regime_flags: { no_preflight: false, exit_delay_ms: 0 },
  scenarios_requested: names,
  scenarios: Object.fromEntries(names.map((n) => [n, scenario(n)])),
  relaunch_freshness: names.includes("relaunch") ? fresh([60, 900]) : undefined,
  load_start: [2, 2, 2],
  load_end: [2, 2, 2],
  refusals: [],
});

/** Three back-to-back pairs of a and b; `edit(row, k)` changes pair k's row of b (or a). */
const series = ({ names = ["cold"], a = () => {}, b = () => {} } = {}) => {
  const rows = [];
  for (let k = 0; k < 3; k++) {
    const ra = row("a", k + 1, names);
    const rb = row("b", k + 1, names);
    a(ra, k);
    b(rb, k);
    rows.push(ra, rb);
  }
  return rows;
};
const cmp = (rows, options = {}) =>
  compareProbe(rows, { control: "a", candidate: "b", ...options });
const find = (res, id, key) => res.entries.find((e) => e.id === id && e.metric === key);
const refuses = (fn, pattern) =>
  assert.throws(fn, (e) => e instanceof CompareRefusal && pattern.test(e.message));

check("identical conditions compare clean", () => {
  const res = cmp(series());
  assert.equal(res.exitCode, 0);
  assert.equal(res.gaps.length, 0);
  assert.equal(res.wrongWay.length, 0);
  assert.equal(res.pairs, 3);
  assert.equal(find(res, "cold", "ready_ms").outcome, "none");
});

// ------------------------------------------------------------ the per-metric minimum

check("a metric with fewer than three values a side is a gap, not a verdict", () => {
  // The control's mounted time is missing in two runs; the candidate's is far lower.
  const res = cmp(
    series({
      a: (r, k) => {
        if (k > 0) {
          r.scenarios.cold.mountedMs = null;
        }
      },
      b: (r) => {
        r.scenarios.cold.mountedMs = 100;
      },
    }),
  );
  assert.equal(find(res, "cold", "mounted_ms"), undefined);
  const reasons = res.gaps.filter((g) => g.metric === "mounted_ms").map((g) => g.reason);
  assert.deepEqual(reasons, [
    "missing in 2 of 3 a run(s) and 0 of 3 b run(s)",
    "not compared: n=1 and 3",
  ]);
  assert.equal(res.exitCode, 1);
});
check("an expected figure that no run on either side has is a gap", () => {
  const none = (r) => {
    r.scenarios.cold.mountedMs = null;
  };
  const res = cmp(series({ a: none, b: none }));
  assert.equal(find(res, "cold", "mounted_ms"), undefined);
  assert.deepEqual(
    res.gaps.filter((g) => g.metric === "mounted_ms").map((g) => g.reason),
    ["missing in all 3 a run(s) and all 3 b run(s)"],
  );
  assert.equal(res.exitCode, 1);
});
check("a scenario measured on one side only is listed, not dropped", () => {
  const rows = series({ names: ["cold", "reload"] });
  for (const r of rows.filter((x) => x.condition === "b")) {
    delete r.scenarios.reload;
  }
  const res = cmp(rows);
  assert.deepEqual(
    res.gaps.filter((g) => g.id === "reload"),
    [{ id: "reload", metric: null, reason: "measured only in a" }],
  );
  assert.equal(res.exitCode, 1);
  assert.match(formatComparison(res).join("\n"), /`reload`: measured only in a/);
});
check("a figure that exists only after an outcome is listed apart and is not a gap", () => {
  const names = ["hidden-then-show"];
  const hidden = (ready) => (r) => {
    Object.assign(r.scenarios["hidden-then-show"], {
      readyMs: undefined,
      mountedMs: undefined,
      hiddenMounted: true,
      hiddenMountedMs: 900,
      hiddenReady: ready,
      hiddenReadyMs: ready ? 1200 : null,
      showToPaintedReadyMs: ready ? 30 : 400,
      showToFirstFrameMs: 15,
      showToReadyFrameMs: ready ? 15 : 380,
    });
  };
  const res = cmp(series({ names, a: hidden(false), b: hidden(true) }));
  assert.deepEqual(
    res.conditional.map((g) => g.metric),
    ["hidden_ready_ms"],
  );
  assert.equal(res.gaps.length, 0);
  const shown = find(res, "hidden-then-show", "show_to_painted_ready_ms");
  assert.equal(shown.outcome, "result");
  assert.equal(shown.direction, "lower");
  assert.equal(find(res, "hidden-then-show", "ready_while_hidden").outcome, "result");
  assert.equal(res.exitCode, 0);
});

// ------------------------------------------------------------ the pair rule

const readyB = (values) => (r, k) => {
  r.scenarios.cold.readyMs = values[k];
};
check("ranges apart with one pair beyond the tolerance is a rerun, not a result", () => {
  // Pair ratios 1.40, 1.20, 1.25: the median ratio is under 1.3 and one pair is beyond.
  const res = cmp(series({ b: readyB([420, 360, 375]) }));
  const e = find(res, "cold", "ready_ms");
  assert.equal(e.overlap, false);
  assert.equal(e.outcome, "rerun");
  assert.match(e.verdict, /rerun that pair/);
  assert.equal(e.wrongWay, true);
  assert.equal(res.exitCode, 1);
});
check("ranges apart with every pair within the tolerance is not a result", () => {
  const res = cmp(series({ b: readyB([330, 340, 350]) }));
  const e = find(res, "cold", "ready_ms");
  assert.equal(e.outcome, "within");
  assert.equal(e.wrongWay, false);
  assert.equal(res.exitCode, 0);
});
check("overlapping ranges with two pairs beyond must be explained", () => {
  // The control's second run is slow, so the ranges overlap; two pairs are beyond 1.3x.
  const res = cmp(
    series({
      a: (r, k) => {
        r.scenarios.cold.readyMs = [300, 600, 300][k];
      },
      b: readyB([420, 400, 400]),
    }),
  );
  const e = find(res, "cold", "ready_ms");
  assert.equal(e.overlap, true);
  assert.equal(e.outcome, "explain");
  assert.equal(e.wrongWay, true);
  assert.equal(res.exitCode, 1);
});
check("ranges apart with two pairs beyond is a result, and meets its expectation", () => {
  const res = cmp(series({ b: readyB([200, 210, 220]) }), { expect: ["cold.ready_ms:lower"] });
  const e = find(res, "cold", "ready_ms");
  assert.equal(e.outcome, "result");
  assert.equal(e.pairs.down.length, 3);
  assert.equal(res.expectations[0].pass, true);
  assert.equal(res.exitCode, 0);
});
check("an expectation in the wrong direction, or of nothing, is not met", () => {
  const rows = series({ b: readyB([200, 210, 220]) });
  assert.equal(cmp(rows, { expect: ["cold.ready_ms:higher"] }).exitCode, 1);
  const none = cmp(rows, { expect: ["cold.no_such_metric:lower"] });
  assert.equal(none.expectations[0].found, false);
  assert.equal(none.exitCode, 1);
});
check("a count is judged on its ranges, and a worse one is a wrong-way result", () => {
  const res = cmp(
    series({
      b: (r, k) => {
        r.scenarios.cold.proxy.total = 104 + k;
      },
    }),
  );
  const e = find(res, "cold", "requests");
  assert.equal(e.outcome, "result");
  assert.equal(e.wrongWay, true);
  assert.equal(res.exitCode, 1);
  // Background requests are shown but never judged.
  const bg = cmp(
    series({
      b: (r) => {
        r.scenarios.cold.proxy.byClass.background = 30;
      },
    }),
  );
  assert.equal(find(bg, "cold", "requests_background").judged, false);
  assert.equal(bg.exitCode, 0);
});

// ------------------------------------------------------------ the relaunch regime

const names = ["cold", "relaunch"];
const regime = (margin) => (r) => {
  r.relaunch_freshness = margin
    ? fresh(margin)
    : { by_headers: 40, held_stale: 0, by_age: 0, assets: [] };
};
const fewerRevalidations = (r) => {
  r.scenarios.relaunch.proxy.byFamily.static = { network: 0, revalidated: 0, error: 0 };
};
check("relaunch counts are not judged across age-decided regimes that differ", () => {
  const rows = series({
    names,
    a: regime([600, 9000]),
    b: (r) => {
      regime([-900, -60])(r);
      r.scenarios.relaunch.proxy.byFamily.static = { network: 0, revalidated: 40, error: 0 };
    },
  });
  const res = cmp(rows);
  const gap = res.gaps.find((g) => g.id === "relaunch");
  assert.match(gap.reason, /not judged: a's assets were fresh and b's stale/);
  assert.equal(
    res.entries.some((e) => e.id === "relaunch"),
    false,
  );
  assert.ok(
    res.notes.some((n) => /relaunch regime: a fresh, b stale; relaunch is not judged/.test(n)),
  );
  assert.equal(res.exitCode, 1);
});
check("a mixed regime, or one that varies within a condition, is not judged", () => {
  assert.match(
    cmp(series({ names, b: regime([-20, 400]) })).gaps.find((g) => g.id === "relaunch").reason,
    /regime is mixed/,
  );
  const varying = series({
    names,
    b: (r, k) => regime(k === 0 ? [-900, -60] : [600, 9000])(r),
  });
  assert.match(
    cmp(varying).gaps.find((g) => g.id === "relaunch").reason,
    /differs between runs of one condition/,
  );
});
check("headers that decide freshness are compared with an age-decided control", () => {
  const res = cmp(
    series({
      names,
      a: (r) => {
        regime([-900, -60])(r);
        r.scenarios.relaunch.proxy.byFamily.static = { network: 0, revalidated: 40, error: 0 };
      },
      b: (r) => {
        regime(null)(r);
        fewerRevalidations(r);
      },
    }),
    { expect: ["relaunch.static_revalidated:lower"] },
  );
  assert.equal(
    res.gaps.some((g) => g.id === "relaunch"),
    false,
  );
  assert.ok(res.notes.some((n) => n === "relaunch regime: a stale, b by-headers"));
  const e = find(res, "relaunch", "static_revalidated");
  assert.equal(e.outcome, "result");
  // Every relaunch verdict and expectation names both sides' regimes.
  assert.match(e.verdict, /; relaunch regime a stale, b by-headers$/);
  assert.equal(res.expectations[0].pass, true);
  assert.equal(
    res.expectations[0].conditions[3],
    "4. under which relaunch regime: relaunch regime a stale, b by-headers",
  );
  assert.equal(res.exitCode, 0);
});
check("a fresh side's static relaunch figures say they cannot show a header saving", () => {
  const res = cmp(series({ names, b: regime(null) }), {
    expect: ["relaunch.static_revalidated:lower"],
  });
  const e = find(res, "relaunch", "static_revalidated");
  assert.match(e.verdict, /relaunch regime a fresh, b by-headers \(a fresh side serves stamped/);
  assert.match(find(res, "relaunch", "ready_ms").verdict, /relaunch regime a fresh, b by-headers$/);
  assert.match(res.expectations[0].conditions[3], /cannot show a header saving/);
  assert.equal(res.expectations[0].pass, false);
});

// ------------------------------------------------------------ refusals

/** Rows whose b runs (or only the first) take the fields `over` gives. */
const withB = (over, firstOnly = false) =>
  series({
    b: (r, k) => {
      if (!firstOnly || k === 0) {
        Object.assign(r, typeof over === "function" ? over(r) : over);
      }
    },
  });

check("compare refuses runs it cannot make mean anything", () => {
  refuses(
    () => cmp(withB({ scenarios_requested: ["cold", "hidden-then-show"] })),
    /scenarios requested differs/,
  );
  refuses(() => cmp(withB({ viewport: "1600x1000" })), /viewport differs/);
  refuses(() => cmp(withB({ device_pixel_ratio: 1 })), /device pixel ratio differs/);
  refuses(() => cmp(withB({ probe_revision: undefined })), /probe revision 1/);
  refuses(
    () => cmp(withB((r) => ({ corpus: { ...r.corpus, commit: null } }))),
    /no commit identity/,
  );
  refuses(() => cmp(withB((r) => ({ corpus: { ...r.corpus, dirty: null } }))), /not clean/);
  refuses(
    () => cmp(withB({ regime_flags: { no_preflight: true, exit_delay_ms: 0 } })),
    /regime flags differs/,
  );
  refuses(
    () => cmp(withB((r) => ({ build: { ...r.build, dirty: true, content: "sha256:x" } }), true)),
    /condition b pools 2 builds/,
  );
  refuses(
    () => cmp(withB((r) => ({ build: { ...r.build, dirty: true } }))),
    /dirty build with no content identity/,
  );
  const short = series().filter((r) => !(r.condition === "b" && r.pair === 3));
  refuses(() => cmp(short), /has 2 valid run\(s\); compare needs 3/);
  refuses(() => compareProbe(series(), { control: "a" }), /name both conditions/);
  refuses(() => cmp(series(), { tolerance: 2 }), /below 2/);
});

// ------------------------------------------------------------ the command's exit code

check("the command exits 0 complete, 1 on a gap or wrong way, and 2 on a refusal", () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "wkprobe-compare-"));
  try {
    const run = (rows, ...extra) => {
      const file = path.join(dir, "runs.jsonl");
      fs.writeFileSync(file, `${rows.map((r) => JSON.stringify(r)).join("\n")}\n`);
      return spawnSync(
        process.execPath,
        [
          path.join(LOOP, "wkprobe.mjs"),
          "compare",
          file,
          "--control",
          "a",
          "--candidate",
          "b",
          ...extra,
        ],
        { encoding: "utf8", timeout: 20000 },
      );
    };
    const clean = run(series());
    assert.equal(clean.status, 0, clean.stderr);
    assert.match(clean.stdout, /Exit 0: complete, with no wrong-way result\./);
    const worse = run(series({ b: readyB([420, 400, 410]) }));
    assert.equal(worse.status, 1, worse.stderr);
    assert.match(worse.stdout, /\[WRONG WAY\]/);
    const refused = run(withB({ viewport: "1600x1000" }));
    assert.equal(refused.status, 2);
    assert.match(refused.stderr, /viewport differs across the runs/);
  } finally {
    fs.rmSync(dir, { recursive: true, force: true });
  }
});

console.log(`wkprobe compare: ${checks} checks passed`);

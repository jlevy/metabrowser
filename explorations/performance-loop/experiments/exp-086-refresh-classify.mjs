// exp-086's server half, judged as exp-081's was (exp-081, "The server half"): the
// standard rule on every sample, and the identity-refresh classification that explains an
// overlap.
//
//   node exp-086-refresh-classify.mjs GIT-ROUTES.json OUT.json
//
// GIT-ROUTES.json is git-route-pairs.mjs's record: per route, a warm-up and `n` samples
// per build, each with `at_ms` on the instrument's clock and the client `ms`. For each
// timed server, its requests on every route, warm-ups included, in start order: the first
// is a refresh, and so is each later one starting at least 5,000 ms after the previous
// refresh started. Per route, with pairs judged control over candidate (lower is better):
//   - standard: the two ranges apart, and the number of pairs beyond 1.3x;
//   - explained: with every pair that holds a refresh sample on either build set aside,
//     the ranges apart with at least 2 pairs beyond 1.3x, and on both builds every refresh
//     sample above that build's largest other sample on the route.
import fs from "node:fs";

const [file, outFile] = process.argv.slice(2);
const record = JSON.parse(fs.readFileSync(file, "utf8"));
const PERIOD_MS = 5000;
const TOLERANCE = 1.3;
const BUILDS = ["control", "candidate"];

const refresh = {};
for (const build of BUILDS) {
  const requests = [];
  for (const [route, entry] of Object.entries(record.routes)) {
    requests.push({ route, pair: 0, at: entry.warmup[build].at_ms });
    entry.samples[build].forEach((s, i) => {
      requests.push({ route, pair: i + 1, at: s.at_ms });
    });
  }
  requests.sort((a, b) => a.at - b.at);
  refresh[build] = new Set();
  let last = null;
  for (const q of requests) {
    if (last === null || q.at - last >= PERIOD_MS) {
      last = q.at;
      refresh[build].add(`${q.route}#${q.pair}`);
    }
  }
}

const range = (xs) => [Math.min(...xs), Math.max(...xs)];
const judge = (control, candidate) => {
  const [cMin, cMax] = range(control);
  const [dMin, dMax] = range(candidate);
  const beyond = control.filter((c, i) => c / candidate[i] > TOLERANCE).length;
  return {
    control_range: [cMin, cMax],
    candidate_range: [dMin, dMax],
    apart: cMin > dMax || dMin > cMax,
    pairs: control.length,
    pairs_beyond: beyond,
  };
};

const out = { rule: "exp-081's identity-refresh classification", period_ms: PERIOD_MS, routes: {} };
for (const [route, entry] of Object.entries(record.routes)) {
  const ms = Object.fromEntries(BUILDS.map((b) => [b, entry.samples[b].map((s) => s.ms)]));
  const isRefresh = (b, i) => refresh[b].has(`${route}#${i + 1}`);
  const standard = judge(ms.control, ms.candidate);
  const keep = ms.control.map((_, i) => !BUILDS.some((b) => isRefresh(b, i)));
  const aside = judge(
    ms.control.filter((_, i) => keep[i]),
    ms.candidate.filter((_, i) => keep[i]),
  );
  const aboveOthers = BUILDS.every((b) => {
    const refreshMs = ms[b].filter((_, i) => isRefresh(b, i));
    const otherMs = ms[b].filter((_, i) => !isRefresh(b, i));
    return !refreshMs.length || Math.min(...refreshMs) > Math.max(...otherMs);
  });
  const refreshPairs = Object.fromEntries(
    BUILDS.map((b) => [b, ms[b].map((_, i) => i + 1).filter((p) => isRefresh(b, p - 1))]),
  );
  const explained = aside.apart && aside.pairs_beyond >= 2 && aboveOthers;
  out.routes[route] = {
    standard,
    refresh_pairs: refreshPairs,
    refresh_set_aside: aside,
    refresh_above_others: aboveOthers,
    overlap_explained: !standard.apart && explained,
  };
  console.log(
    `${route.padEnd(24)} standard: apart ${standard.apart}, ${standard.pairs_beyond} of ${standard.pairs} beyond; refresh pairs control ${refreshPairs.control.join(",") || "-"} candidate ${refreshPairs.candidate.join(",") || "-"}; set aside: apart ${aside.apart}, ${aside.pairs_beyond} of ${aside.pairs} beyond; refresh above others ${aboveOthers}`,
  );
}
fs.writeFileSync(outFile, `${JSON.stringify(out, null, 2)}\n`);

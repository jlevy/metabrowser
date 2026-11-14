// Back-to-back timing of the Git routes on two servers serving the same corpus, with a
// correctness check between pairs on a repository whose refs move.
//
//   node explorations/performance-loop/git-route-pairs.mjs \
//     --control http://127.0.0.1:8910 --candidate http://127.0.0.1:8911 --n 15 --out FILE \
//     [--check-repo PATH --check-control http://127.0.0.1:8912 \
//      --check-candidate http://127.0.0.1:8913]
//
// Start the servers first, each with its own --cache-dir and --config-dir, and wait for
// /api/index/progress to say done. For each route: one unrecorded warm-up request per
// server, then n pairs; odd pairs ask the control first and even pairs the candidate.
// Each request sends `accept-encoding: gzip`, as a browser does, and reads the whole body.
// It records client wall time, status, body bytes, whether an ETag came back, and
// Server-Timing, with no If-None-Match, so a kept answer is served as a 200, and when the
// request started, in ms from the run's start (`at_ms`), so a sample can be placed against
// the server's five-second repository-identity period; each check records its own start
// and end the same way. exp-081 is the round that added the times.
//
// The check, when asked for, runs between pairs and is not timed. Its repository is a
// scratch clone the timed servers never serve, with loose refs, served by both builds.
// Before each move it asks the candidate twice, so a kept answer exists; it then moves a
// ref (a commit on HEAD, a loose branch moved, a tag added, a loose
// branch deleted, in turn) and asks both builds for the refs, the summary in both scopes,
// and the first log page. The candidate's answers must equal the control's, which keeps
// nothing: the refs and summaries byte for byte, and every field of the log page but its
// cursors, which name each server's own session; that includes the commits with their
// refs, the scope, and its fingerprint. exp-061 is the round that used it.
import { execFileSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import { parseArgs } from "node:util";

const { values } = parseArgs({
  options: {
    control: { type: "string" },
    candidate: { type: "string" },
    n: { type: "string", default: "15" },
    out: { type: "string" },
    "check-repo": { type: "string" },
    "check-control": { type: "string" },
    "check-candidate": { type: "string" },
  },
});
const n = Number.parseInt(values.n, 10);
const ROUTES = ["/api/git/log?limit=250", "/api/git/summary", "/api/git/refs"];
const CHECK_ROUTES = [
  "/api/git/refs",
  "/api/git/summary",
  "/api/git/summary?scope=all",
  "/api/git/log?limit=50",
];

// The run's time origin; `started_at` records about the same instant as a date.
const T0 = performance.now();
const at = (t) => Math.round((t - T0) * 10) / 10;

async function once(base, route) {
  const started = performance.now();
  const response = await fetch(`${base}${route}`, { headers: { "accept-encoding": "gzip" } });
  const body = await response.arrayBuffer();
  const ms = performance.now() - started;
  return {
    at_ms: at(started),
    ms: Math.round(ms * 100) / 100,
    status: response.status,
    bytes: body.byteLength,
    etag: response.headers.get("etag") !== null,
    server_timing: response.headers.get("server-timing"),
  };
}

async function answer(base, route) {
  const response = await fetch(`${base}${route}`);
  return {
    status: response.status,
    etag: response.headers.get("etag"),
    text: await response.text(),
  };
}

/** What two builds must agree on for one route's answer. */
function comparable(route, text) {
  if (!route.startsWith("/api/git/log")) {
    return text;
  }
  // The cursors name each server's own session, so only they may differ.
  const { cursor: _c, page_cursor: _p, previous_cursor: _v, ...page } = JSON.parse(text);
  return JSON.stringify(page);
}

const checkRepo = values["check-repo"];
const MOVES = ["commit", "move-loose", "tag", "delete-loose"];
let moveIndex = 0;
function git(...args) {
  return execFileSync("git", ["-C", checkRepo, ...args], {
    encoding: "utf8",
    env: {
      ...process.env,
      GIT_AUTHOR_NAME: "Check",
      GIT_AUTHOR_EMAIL: "check@example.invalid",
      GIT_COMMITTER_NAME: "Check",
      GIT_COMMITTER_EMAIL: "check@example.invalid",
      GIT_CONFIG_GLOBAL: "/dev/null",
      GIT_CONFIG_NOSYSTEM: "1",
    },
  }).trim();
}

function moveRef() {
  const kind = MOVES[moveIndex % MOVES.length];
  const index = moveIndex;
  moveIndex += 1;
  if (kind === "commit") {
    git("commit", "-q", "--allow-empty", "-m", `check move ${index}`);
  } else if (kind === "move-loose") {
    git("update-ref", `refs/heads/loose/b${index % 1000}`, "HEAD");
  } else if (kind === "tag") {
    git("tag", `check-${index}`);
  } else {
    git("update-ref", "-d", `refs/heads/loose/b${(index + 500) % 1000}`);
  }
  return kind;
}

async function check() {
  const checkStarted = performance.now();
  const before = {};
  for (const route of CHECK_ROUTES) {
    await answer(values["check-candidate"], route);
    before[route] = (await answer(values["check-candidate"], route)).etag;
  }
  const move = moveRef();
  const routes = {};
  let correct = true;
  for (const route of CHECK_ROUTES) {
    const candidate = await answer(values["check-candidate"], route);
    const control = await answer(values["check-control"], route);
    const agrees =
      candidate.status === control.status &&
      comparable(route, candidate.text) === comparable(route, control.text);
    correct &&= agrees;
    routes[route] = {
      agrees,
      status: candidate.status,
      tag_moved: before[route] !== null ? before[route] !== candidate.etag : null,
    };
  }
  return { move, correct, routes, at_ms: at(checkStarted), end_ms: at(performance.now()) };
}

const servers = { control: values.control, candidate: values.candidate };
const result = {
  started_at: new Date().toISOString(),
  loadavg_start: os.loadavg(),
  n,
  routes: {},
  checks: [],
};
for (const route of ROUTES) {
  const entry = { warmup: {}, samples: { control: [], candidate: [] } };
  for (const [label, base] of Object.entries(servers)) {
    entry.warmup[label] = await once(base, route);
  }
  for (let pair = 1; pair <= n; pair += 1) {
    const order = pair % 2 === 1 ? ["control", "candidate"] : ["candidate", "control"];
    for (const label of order) {
      entry.samples[label].push(await once(servers[label], route));
    }
    if (checkRepo) {
      result.checks.push({ route, pair, ...(await check()) });
    }
  }
  result.routes[route] = entry;
}
result.loadavg_end = os.loadavg();
result.ended_at = new Date().toISOString();

const median = (xs) => {
  const s = [...xs].sort((a, b) => a - b);
  return s.length % 2 ? s[(s.length - 1) / 2] : (s[s.length / 2 - 1] + s[s.length / 2]) / 2;
};
for (const [route, entry] of Object.entries(result.routes)) {
  const summary = {};
  for (const label of ["control", "candidate"]) {
    const ms = entry.samples[label].map((s) => s.ms);
    summary[label] = {
      median: Math.round(median(ms) * 10) / 10,
      min: Math.min(...ms),
      max: Math.max(...ms),
      statuses: [...new Set(entry.samples[label].map((s) => s.status))],
      etag: entry.samples[label].every((s) => s.etag),
    };
  }
  // The pair rule: each pair's control over candidate time, and how many are beyond 1.3x.
  const ratios = entry.samples.control.map((c, i) => c.ms / entry.samples.candidate[i].ms);
  summary.pair_ratios = {
    min: Math.round(Math.min(...ratios) * 100) / 100,
    median: Math.round(median(ratios) * 100) / 100,
    max: Math.round(Math.max(...ratios) * 100) / 100,
    beyond_1_3: ratios.filter((r) => r > 1.3).length,
  };
  summary.ratio = Math.round((summary.control.median / summary.candidate.median) * 100) / 100;
  summary.apart =
    summary.control.min > summary.candidate.max || summary.candidate.min > summary.control.max;
  entry.summary = summary;
  console.log(route, JSON.stringify(summary));
}
if (checkRepo) {
  const wrong = result.checks.filter((c) => !c.correct);
  result.check_summary = { checks: result.checks.length, wrong: wrong.length };
  console.log("check", JSON.stringify(result.check_summary));
}
if (values.out) {
  fs.writeFileSync(values.out, `${JSON.stringify(result, null, 2)}\n`);
}

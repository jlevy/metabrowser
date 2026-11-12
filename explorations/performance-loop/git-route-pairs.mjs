// Back-to-back timing of the Git routes on two servers serving the same corpus.
//
//   node explorations/performance-loop/git-route-pairs.mjs \
//     --control http://127.0.0.1:8901 --candidate http://127.0.0.1:8902 --n 15 --out FILE
//
// Start the two servers first, each with its own --cache-dir and --config-dir, and wait
// for /api/index/progress to say done. For each route: one unrecorded warm-up request per
// server, then n pairs; odd pairs ask the control first and even pairs the candidate.
// Each request sends `accept-encoding: gzip`, as a browser does, and reads the whole body.
// It records client wall time, status, body bytes, whether an ETag came back, and
// Server-Timing, with no If-None-Match, so a kept answer is served as a 200.
// exp-061 is the round that used it.
import fs from "node:fs";
import os from "node:os";
import { parseArgs } from "node:util";

const { values } = parseArgs({
  options: {
    control: { type: "string" },
    candidate: { type: "string" },
    n: { type: "string", default: "15" },
    out: { type: "string" },
  },
});
const n = Number.parseInt(values.n, 10);
const ROUTES = ["/api/git/log?limit=250", "/api/git/summary", "/api/git/refs"];

async function once(base, route) {
  const started = performance.now();
  const response = await fetch(`${base}${route}`, { headers: { "accept-encoding": "gzip" } });
  const body = await response.arrayBuffer();
  const ms = performance.now() - started;
  return {
    ms: Math.round(ms * 100) / 100,
    status: response.status,
    bytes: body.byteLength,
    etag: response.headers.get("etag") !== null,
    server_timing: response.headers.get("server-timing"),
  };
}

const servers = { control: values.control, candidate: values.candidate };
const result = {
  started_at: new Date().toISOString(),
  loadavg_start: os.loadavg(),
  n,
  routes: {},
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
  summary.ratio = Math.round((summary.control.median / summary.candidate.median) * 100) / 100;
  summary.apart =
    summary.control.min > summary.candidate.max || summary.candidate.min > summary.control.max;
  entry.summary = summary;
  console.log(route, JSON.stringify(summary));
}
if (values.out) {
  fs.writeFileSync(values.out, `${JSON.stringify(result, null, 2)}\n`);
}

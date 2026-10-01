// Read a Chrome net log for who held a host's connections while a request waited.
//
//   node explorations/page-connections/net-log.mjs <net-log.json> <host:port>
//
// Chrome opens at most six HTTP/1.1 connections to a host and logs
// SOCKET_POOL_STALLED_MAX_SOCKETS_PER_GROUP for a request that finds all six in use.
// For every request to the host that stalled 100 ms or longer this prints how long it
// waited and which requests held the host's sockets at that moment. It then lists
// every event stream with the time it held its socket, and every request that held one
// for two seconds or longer, whatever it was.
//
// measure.mjs writes the log with --netlog. It is complete only when Chrome exited
// cleanly; a truncated one is closed here and read as far as it goes.

import fs from "node:fs";

const [file, hostPort] = process.argv.slice(2);
if (!file || !hostPort) {
  console.error("usage: net-log.mjs <net-log.json> <host:port>");
  process.exit(2);
}
let text = fs.readFileSync(file, "utf8");
let log;
try {
  log = JSON.parse(text);
} catch {
  text = `${text.replace(/,\s*$/, "")}]}`;
  log = JSON.parse(text);
}
const invert = (table) => Object.fromEntries(Object.entries(table).map(([k, v]) => [v, k]));
const typeName = invert(log.constants.logEventTypes);
const sourceName = invert(log.constants.logSourceType);
const phaseName = invert(log.constants.logEventPhase);

/** URL_REQUEST id -> its URL, lifetime, and the stream job that found it a socket. */
const requests = new Map();
/** HTTP_STREAM_JOB id -> when it stalled and when it was given which socket. */
const jobs = new Map();
let last = 0;
for (const event of log.events) {
  const time = Number(event.time);
  last = Math.max(last, time);
  const type = typeName[event.type];
  const source = sourceName[event.source.type];
  if (source === "URL_REQUEST") {
    let request = requests.get(event.source.id);
    if (!request) {
      request = { url: null, start: time, end: null, job: null };
      requests.set(event.source.id, request);
    }
    if (type === "URL_REQUEST_START_JOB" && event.params?.url) {
      request.url = event.params.url;
    } else if (type === "REQUEST_ALIVE" && phaseName[event.phase] === "PHASE_END") {
      request.end = time;
    } else if (type === "HTTP_STREAM_REQUEST_BOUND_TO_JOB") {
      request.job = event.params.source_dependency.id;
    }
  } else if (source === "HTTP_STREAM_JOB") {
    let job = jobs.get(event.source.id);
    if (!job) {
      job = { stalledAt: null, boundAt: null, socket: null };
      jobs.set(event.source.id, job);
    }
    if (type === "SOCKET_POOL_STALLED_MAX_SOCKETS_PER_GROUP" && job.stalledAt === null) {
      job.stalledAt = time;
    } else if (type === "SOCKET_POOL_BOUND_TO_SOCKET") {
      job.boundAt = time;
      job.socket = event.params.source_dependency.id;
    }
  }
}

const mine = [...requests.values()].filter((request) => request.url?.includes(hostPort));
if (mine.length === 0) {
  console.error(`no request to ${hostPort} in ${file}`);
  process.exit(1);
}
const t0 = Math.min(...mine.map((request) => request.start));
const at = (time) => `t+${((time - t0) / 1000).toFixed(2)}s`;
const short = (url) => url.replace(/^https?:\/\/[^/]+/, "").replace(/\?v=.*/, "");
const jobOf = (request) => (request.job === null ? null : jobs.get(request.job));
const isStream = (request) => /\/api\/(events|stream)\b/.test(request.url);

const stalled = mine
  .filter((request) => jobOf(request)?.stalledAt != null && jobOf(request).boundAt !== null)
  .map((request) => ({ request, job: jobOf(request) }))
  .filter(({ job }) => job.boundAt - job.stalledAt >= 100)
  .sort((a, b) => a.job.stalledAt - b.job.stalledAt);
console.log(`requests to ${hostPort}: ${mine.length}`);
console.log(`stalled on the six-connection limit for 100 ms or longer: ${stalled.length}`);
let longestBehindStreams = 0;
for (const { request, job } of stalled) {
  // Requests alive at that moment that already held one of the host's sockets.
  const holders = mine.filter((holder) => {
    const held = jobOf(holder);
    return (
      held?.boundAt != null &&
      held.boundAt <= job.stalledAt &&
      (holder.end === null || holder.end > job.stalledAt)
    );
  });
  const streams = holders.filter(isStream);
  const wait = job.boundAt - job.stalledAt;
  if (streams.length >= 5) {
    longestBehindStreams = Math.max(longestBehindStreams, wait);
  }
  console.log(
    `  ${at(job.stalledAt)}  waited ${String(wait).padStart(6)} ms  ${short(request.url)}  (${streams.length} of ${holders.length} sockets held by event streams)`,
  );
}
console.log(
  `longest wait while event streams held five or more of the six: ${longestBehindStreams} ms`,
);

console.log("event streams, and how long each held its socket:");
for (const request of mine.filter(isStream)) {
  const job = jobOf(request);
  const from = job?.boundAt ?? request.start;
  const to = request.end ?? last;
  console.log(
    `  ${short(request.url)}  ${at(from)} to ${request.end === null ? "the end of the log" : at(to)}  (${((to - from) / 1000).toFixed(1)} s)`,
  );
}
const longLived = {};
for (const request of mine) {
  const job = jobOf(request);
  if (job?.boundAt != null && (request.end ?? last) - job.boundAt >= 2000) {
    const key = short(request.url).replace(/\?.*/, "");
    longLived[key] = (longLived[key] ?? 0) + 1;
  }
}
console.log(`requests that held a socket for 2 s or longer: ${JSON.stringify(longLived)}`);

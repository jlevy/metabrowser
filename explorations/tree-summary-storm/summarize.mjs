// The numbers a trial is read for, from the probe's record and the server's request log.
//
//   node explorations/tree-summary-storm/summarize.mjs LABEL.json LABEL-server.log
//
// From the page: how many root-summary requests it sent, the most it had in flight at
// once, when the Commits tab was opened and when its first rows appeared, and when each
// Commits request was sent and answered (with the server's own time from
// Server-Timing). From the server (METABROWSER_REQUEST_LOG=verbose): how many root-summary
// requests reached it, the most it was answering at once, and how long each took.
import fs from "node:fs";

const [recordPath, logPath] = process.argv.slice(2);
const record = JSON.parse(fs.readFileSync(recordPath, "utf8"));
const SUMMARY = "/api/tree?depth=0";

/** @param {number[]} values */
function spread(values) {
  const sorted = [...values].sort((a, b) => a - b);
  const at = (/** @type {number} */ p) =>
    sorted.length ? sorted[Math.min(sorted.length - 1, Math.floor(p * sorted.length))] : null;
  return {
    count: sorted.length,
    min: sorted[0] ?? null,
    median: at(0.5),
    max: sorted.at(-1) ?? null,
  };
}

const requests = record.requests ?? [];
const summaries = requests.filter(
  (/** @type {{path: string}} */ request) => request.path === SUMMARY,
);
const page = {
  engine: record.engine?.name ?? record.engine,
  outcome: record.outcome,
  pages: 1 + (record.frames ?? 0),
  walkAtClick: record.scanAtClick?.status,
  commitsTimeToLoadMs: record.commitsTimeToLoadMs ?? null,
  summaryRequestsSent: summaries.length,
  summaryMostInFlight: record.depth0MaxInFlight,
  summaryServerMs: spread(
    summaries
      .map((/** @type {{srv?: number}} */ request) => request.srv)
      .filter((/** @type {number | undefined} */ value) => value !== undefined),
  ),
};

/** @type {{start: number, end: number, ms: number, path: string}[]} */
const served = [];
let walk = null;
for (const line of fs.readFileSync(logPath, "utf8").split("\n")) {
  const request = /request t=([0-9.]+) -> ([0-9.]+) \((\d+) ms\) method=\w+ path=(\S+)/.exec(line);
  if (request) {
    served.push({
      start: Number(request[1]),
      end: Number(request[2]),
      ms: Number(request[3]),
      path: request[4],
    });
  }
  const walked = /walker complete: .* elapsed=(\d+)ms/.exec(line);
  if (walked) {
    walk = Number(walked[1]);
  }
}
const atServer = served.filter((request) => request.path === SUMMARY);
const server = {
  walkMs: walk,
  summaryRequestsServed: atServer.length,
  summaryMostAtOnce: Math.max(
    0,
    ...atServer.map(
      (request) =>
        atServer.filter((other) => other.start <= request.start && other.end > request.start)
          .length,
    ),
  ),
  summaryMs: spread(atServer.map((request) => request.ms)),
};

console.log(JSON.stringify({ page, server }, null, 1));
console.log("Commits requests (page ms: sent -> answered, server ms):");
for (const request of requests.filter((/** @type {{path: string}} */ r) =>
  r.path.startsWith("/api/git/"),
)) {
  const waited = request.end === undefined ? "never answered" : `${request.end - request.start} ms`;
  console.log(
    `  ${request.path.slice(0, 40).padEnd(40)} ${request.start} -> ${request.end ?? "-"} (${waited}, server ${request.srv ?? "-"})`,
  );
}
console.log("What the Commits tab showed:");
for (const [at, text] of record.snapshots ?? []) {
  console.log(`  ${at}: ${String(text).slice(0, 80) || "(nothing)"}`);
}

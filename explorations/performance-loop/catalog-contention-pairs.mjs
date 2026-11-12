// Does a page of the background pull-request catalog walk slow a concurrent commit
// comparison, and by the same amount on two builds? No browser; two servers that serve
// the same corpus with a pull-request catalog in their caches.
//
//   node explorations/performance-loop/catalog-contention-pairs.mjs \
//     --control http://127.0.0.1:8920 --candidate http://127.0.0.1:8921 \
//     --revision SHA --pages 299,290,280,271 --n 10 --out FILE
//
// Two cells per build. "alone": one GET of `/api/plugin/diff/comparison?revision=SHA`.
// "concurrent": the same GET, and 10 ms after it starts, one page of the walk as the Pulls
// panel issues it: GET `/api/plugin/github/pulls?state=all&limit=8&after=N`, then a POST
// to `/api/plugin/github/pull-cores-prepare` naming that page's numbers under its
// generation. Each iteration runs both builds, the leading build alternating, and both
// cells on each, their order alternating; a 400 ms pause follows each cell, so a page's
// work ends before the next cell starts. Every request reads its whole body, and each
// sample records when it started (`at_ms`, from the run's start). One unrecorded warm-up
// of each cell runs first on each server. exp-081 is the round that used it.
import crypto from "node:crypto";
import fs from "node:fs";
import os from "node:os";
import { parseArgs } from "node:util";

const { values } = parseArgs({
  options: {
    control: { type: "string" },
    candidate: { type: "string" },
    revision: { type: "string" },
    pages: { type: "string", default: "299,290,280,271" },
    n: { type: "string", default: "10" },
    offset: { type: "string", default: "10" },
    out: { type: "string" },
  },
});
const n = Number.parseInt(values.n, 10);
const offsetMs = Number.parseInt(values.offset, 10);
const pages = values.pages.split(",").map((page) => Number.parseInt(page, 10));
const servers = { control: values.control, candidate: values.candidate };
const T0 = performance.now();
const at = (t) => Math.round((t - T0) * 10) / 10;
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

async function timed(base, route, init = {}) {
  const started = performance.now();
  const response = await fetch(`${base}${route}`, init);
  const text = await response.text();
  return {
    at_ms: at(started),
    ms: Math.round((performance.now() - started) * 100) / 100,
    status: response.status,
    server_timing: response.headers.get("server-timing"),
    text,
  };
}

const comparison = (base) =>
  timed(base, `/api/plugin/diff/comparison?revision=${values.revision}`, {
    headers: { "accept-encoding": "gzip" },
  });

async function catalogPage(base, after) {
  const page = await timed(base, `/api/plugin/github/pulls?state=all&limit=8&after=${after}`);
  let numbers = [];
  let generation = null;
  try {
    const envelope = JSON.parse(page.text);
    numbers = (envelope.rows ?? []).map((row) => row.number);
    generation = envelope.generation ?? null;
  } catch {
    // Recorded below as a page with no rows.
  }
  const body = {
    state: "all",
    window: { id: crypto.randomBytes(16).toString("hex"), generation },
    numbers,
  };
  const prepare = await timed(base, "/api/plugin/github/pull-cores-prepare", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });
  return { page, prepare, rows: numbers.length, generation: generation !== null };
}

let pageIndex = 0;
async function cell(label, kind) {
  const base = servers[label];
  if (kind === "alone") {
    const { text: _text, ...cmp } = await comparison(base);
    await sleep(400);
    return { comparison: cmp };
  }
  const after = pages[pageIndex % pages.length];
  pageIndex += 1;
  const cmpPromise = comparison(base);
  await sleep(offsetMs);
  const walk = catalogPage(base, after);
  const { text: _text, ...cmp } = await cmpPromise;
  const { page, prepare, rows, generation } = await walk;
  await sleep(400);
  const strip = ({ text: _t, ...rest }) => rest;
  return {
    comparison: cmp,
    after,
    rows,
    generation,
    page: strip(page),
    prepare: strip(prepare),
    // Whether the page's prepare started before the comparison's answer was read.
    prepare_overlapped: prepare.at_ms < cmp.at_ms + cmp.ms,
  };
}

const result = {
  started_at: new Date().toISOString(),
  loadavg_start: os.loadavg(),
  n,
  offset_ms: offsetMs,
  pages,
  warmup: {},
  samples: [],
};
for (const label of Object.keys(servers)) {
  result.warmup[label] = {
    alone: await cell(label, "alone"),
    concurrent: await cell(label, "concurrent"),
  };
}
for (let i = 1; i <= n; i += 1) {
  const builds = i % 2 === 1 ? ["control", "candidate"] : ["candidate", "control"];
  const kinds = i % 2 === 1 ? ["alone", "concurrent"] : ["concurrent", "alone"];
  for (const label of builds) {
    for (const kind of kinds) {
      result.samples.push({ iteration: i, build: label, cell: kind, ...(await cell(label, kind)) });
    }
  }
}
result.loadavg_end = os.loadavg();
result.ended_at = new Date().toISOString();

const median = (xs) => {
  const s = [...xs].sort((a, b) => a - b);
  return s.length % 2 ? s[(s.length - 1) / 2] : (s[s.length / 2 - 1] + s[s.length / 2]) / 2;
};
const round = (x) => Math.round(x * 10) / 10;
const summary = {};
for (const label of Object.keys(servers)) {
  const ms = (kind) =>
    result.samples.filter((s) => s.build === label && s.cell === kind).map((s) => s.comparison.ms);
  const alone = ms("alone");
  const concurrent = ms("concurrent");
  // Per iteration: the concurrent comparison over the one alone, on the same build.
  const ratios = concurrent.map((c, i) => c / alone[i]);
  const increases = concurrent.map((c, i) => c - alone[i]);
  summary[label] = {
    alone: { median: round(median(alone)), min: Math.min(...alone), max: Math.max(...alone) },
    concurrent: {
      median: round(median(concurrent)),
      min: Math.min(...concurrent),
      max: Math.max(...concurrent),
    },
    apart: Math.min(...concurrent) > Math.max(...alone),
    ratio_median: Math.round(median(ratios) * 100) / 100,
    beyond_1_3: ratios.filter((r) => r > 1.3).length,
    increase_ms: {
      median: round(median(increases)),
      min: round(Math.min(...increases)),
      max: round(Math.max(...increases)),
    },
    overlapped: result.samples.filter(
      (s) => s.build === label && s.cell === "concurrent" && s.prepare_overlapped,
    ).length,
    prepare_statuses: [
      ...new Set(
        result.samples
          .filter((s) => s.build === label && s.cell === "concurrent")
          .map((s) => s.prepare.status),
      ),
    ],
  };
  console.log(label, JSON.stringify(summary[label]));
}
result.summary = summary;
if (values.out) {
  fs.writeFileSync(values.out, `${JSON.stringify(result, null, 2)}\n`);
}

// Run static renderer fixtures in Chrome. Setup and fixture fetches precede the
// measurements; there is no Metabrowser server or data API in the measured path.
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { parseArgs } from "node:util";
import { driver, launchBrowser } from "./transitions-recorder.mjs";

const FIXTURES = {
  "diff-layout": "diffLayout",
  "diff-intraline": "diffIntraline",
};

const { values } = parseArgs({
  options: {
    origin: { type: "string", default: "http://127.0.0.1:8412" },
    fixture: { type: "string", multiple: true },
    runs: { type: "string", default: "3" },
  },
});
const origin = new URL(values.origin);
const runs = Number(values.runs);
const fixtures = values.fixture ?? Object.keys(FIXTURES);
if (origin.protocol !== "http:" || !["127.0.0.1", "[::1]", "localhost"].includes(origin.hostname)) {
  throw new Error("--origin must be a loopback HTTP address serving the repository statically");
}
if (!Number.isSafeInteger(runs) || runs < 1) {
  throw new Error("--runs must be a positive integer");
}
for (const name of fixtures) {
  if (!Object.hasOwn(FIXTURES, name)) {
    throw new Error(`unknown renderer fixture ${name}`);
  }
}

const root = fs.mkdtempSync(path.join(os.tmpdir(), "metab-render-"));
try {
  for (let run = 1; run <= runs; run++) {
    for (const name of fixtures) {
      const load_start = os.loadavg();
      const browser = await launchBrowser({ profileDir: path.join(root, "profile") });
      try {
        const d = driver(browser);
        const property = FIXTURES[name];
        const resultKey = JSON.stringify(`${property}BenchmarkResult`);
        const errorKey = JSON.stringify(`${property}BenchmarkError`);
        await d.navigate(new URL(`/explorations/${name}/benchmark.html`, origin).href);
        const finished = await d.waitFor(
          `Boolean(window[${resultKey}] || window[${errorKey}])`,
          90000,
        );
        if (!finished || browser.exceptions.length) {
          throw new Error(`${name} did not complete without page exceptions`);
        }
        const error = await d.evaluate(`window[${errorKey}] ?? null`);
        if (error) {
          throw new Error(`${name}: ${error}`);
        }
        const result = await d.evaluate(`window[${resultKey}]`);
        console.log(
          JSON.stringify({
            schema: "renderer-fixture/v1",
            fixture: name,
            run,
            load_start,
            load_end: os.loadavg(),
            chrome: browser.version.product,
            result,
          }),
        );
      } finally {
        await browser.close();
      }
    }
  }
} finally {
  fs.rmdirSync(root);
}

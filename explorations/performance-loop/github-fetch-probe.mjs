// Bounded live diagnostic for the public Metabrowser corpus. Output is safe to retain:
// no request arguments, validators, command output, or unlisted headers are emitted.
import { execFile } from "node:child_process";
import { promisify } from "node:util";

const run = promisify(execFile);
const subjects = [351, 353]; // Stable merged PRs used by transitions-journeys.mjs.
const rounds = 3;
const headersToReport = [
  "x-ratelimit-resource",
  "x-ratelimit-limit",
  "x-ratelimit-remaining",
  "x-ratelimit-used",
  "x-ratelimit-reset",
  "retry-after",
];
const report = {
  schema: "github-fetch-probe/v1",
  started_at: new Date().toISOString(),
  repository: "jlevy/metabrowser",
  subjects,
  rounds,
  samples: [],
  batches: [],
  stopped: null,
};

async function gh(args) {
  const start = performance.now();
  const options = {
    timeout: 20000,
    maxBuffer: 2 * 1024 * 1024,
    env: { ...process.env, GH_DEBUG: "", GH_PROMPT_DISABLED: "1", GH_FORCE_TTY: "" },
  };
  try {
    const { stdout } = await run("gh", args, options);
    return { stdout, exit: 0, ms: performance.now() - start };
  } catch (error) {
    return {
      stdout: typeof error.stdout === "string" ? error.stdout : "",
      exit: Number.isInteger(error.code) ? error.code : null,
      ms: performance.now() - start,
    };
  }
}

async function read(kind, round, args) {
  const { stdout, exit, ms } = await gh(["api", "--hostname", "github.com", "--include", ...args]);
  const boundary = /\r?\n\r?\n/.exec(stdout);
  const headerBlock = boundary ? stdout.slice(0, boundary.index) : "";
  const body = boundary ? stdout.slice(boundary.index + boundary[0].length) : "";
  const [statusLine, ...headerLines] = headerBlock.split(/\r?\n/);
  const status = Number(/^HTTP\/\S+ (\d{3})\b/.exec(statusLine)?.[1]) || null;
  const headers = new Map();
  for (const line of headerLines) {
    const split = line.indexOf(":");
    if (split !== -1) {
      headers.set(line.slice(0, split).toLowerCase(), line.slice(split + 1).trim());
    }
  }
  const sample = {
    kind,
    round,
    ms,
    exit,
    status,
    body_bytes: Buffer.byteLength(body),
    etag_present: headers.has("etag"),
    headers: Object.fromEntries(
      headersToReport.filter((key) => headers.has(key)).map((key) => [key, headers.get(key)]),
    ),
  };
  report.samples.push(sample);
  if (
    headers.has("retry-after") ||
    headers.get("x-ratelimit-remaining") === "0" ||
    status === 403 ||
    status === 429
  ) {
    throw new Error("GitHub requested a hold or the request was forbidden");
  }
  if (status === 200 && exit === 0 && kind === "graphql_batch") {
    const response = JSON.parse(body);
    const data = response.data;
    if (
      response.errors?.length ||
      data?.repository?.first?.number !== subjects[0] ||
      data?.repository?.second?.number !== subjects[1] ||
      !Number.isInteger(data.rateLimit?.cost)
    ) {
      throw new Error("GraphQL did not return both subjects and a query cost");
    }
    sample.graphql_cost = data.rateLimit.cost;
  } else if (status === 200 && exit === 0) {
    if (JSON.parse(body).number !== Number(args[0].split("/").at(-1))) {
      throw new Error("REST did not return the requested subject");
    }
  } else if (!(kind === "conditional" && status === 304)) {
    throw new Error(`No usable response for ${kind} (status ${status}, exit ${exit})`);
  }
  return headers.get("etag");
}

const rest = (number) => `repos/jlevy/metabrowser/pulls/${number}`;
const query = `query {
  repository(owner: "jlevy", name: "metabrowser") {
    first: pullRequest(number: ${subjects[0]}) { number }
    second: pullRequest(number: ${subjects[1]}) { number }
  }
  rateLimit { cost }
}`;

try {
  const version = await gh(["--version"]);
  if (version.exit !== 0) {
    throw new Error("gh --version failed");
  }
  report.gh = version.stdout.split("\n", 1)[0];
  for (let round = 1; round <= rounds; round++) {
    const local = await gh(["--version"]);
    if (local.exit !== 0) {
      throw new Error("gh --version failed");
    }
    report.samples.push({ kind: "process_floor", round, ms: local.ms, exit: local.exit });
    for (const mode of round % 2 ? ["serial", "parallel"] : ["parallel", "serial"]) {
      const start = performance.now();
      if (mode === "serial") {
        for (const number of subjects) {
          await read(mode, round, [rest(number)]);
        }
      } else {
        // Finish recording the other in-flight result even if one requests a stop.
        const results = await Promise.allSettled(
          subjects.map((number) => read(mode, round, [rest(number)])),
        );
        const failed = results.find((result) => result.status === "rejected");
        if (failed) {
          throw failed.reason;
        }
      }
      report.batches.push({ kind: mode, round, ms: performance.now() - start });
    }
    const etag = await read("validator_seed", round, [rest(subjects[0])]);
    if (!etag) {
      throw new Error("GitHub did not return a validator");
    }
    await read("conditional", round, [rest(subjects[0]), "-H", `If-None-Match: ${etag}`]);
    await read("graphql_batch", round, ["graphql", "-f", `query=${query}`]);
  }
} catch (error) {
  report.stopped = error instanceof SyntaxError ? "Invalid response JSON" : error.message;
  process.exitCode = 1;
}
console.log(JSON.stringify(report, null, 2));

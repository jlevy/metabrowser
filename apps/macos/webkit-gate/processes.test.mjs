// The gate's process ownership, with shell scripts standing in for metab: `make test` in
// apps/macos runs it with `node --test`.
import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { after, test } from "node:test";
import * as processes from "./processes.mjs";

const work = fs.mkdtempSync(path.join(os.tmpdir(), "webkit-gate-processes-"));
after(() => fs.rmSync(work, { recursive: true, force: true }));

/** A stand-in for metab: it records its arguments and pid beside itself, then runs `body`. */
function fake(name, body) {
  const file = path.join(work, name);
  fs.writeFileSync(
    file,
    `#!/bin/sh\nprintf '%s\\n' "$@" > "$0.args"\necho $$ > "$0.pid"\n${body}\n`,
    { mode: 0o755 },
  );
  return file;
}

// Announces as metab does, then serves: until its stdin closes with `--exit-on-eof`, as
// metab does, and otherwise until it is stopped.
const SERVING = `echo "Serving fake at http://127.0.0.1:$3/view/"
case " $* " in *" --exit-on-eof "*) cat > /dev/null ;; *) exec sleep 600 ;; esac`;

const alive = (pid) => {
  try {
    process.kill(pid, 0);
    return true;
  } catch {
    return false;
  }
};

async function gone(pid, ms) {
  for (let waited = 0; waited < ms; waited += 50) {
    if (!alive(pid)) {
      return true;
    }
    await new Promise((resolve) => setTimeout(resolve, 50));
  }
  return !alive(pid);
}

const pidOf = (file) => Number(fs.readFileSync(`${file}.pid`, "utf8"));

// A fixture prints its readiness line within a second here; the bound is for a loaded
// runner, and a fixture that misses it fails its test instead of hanging the suite.
const READY_TIMEOUT_MS = 10_000;

/** Resolves once `child` prints `text`; rejects if it exits first or `READY_TIMEOUT_MS` pass. */
function printed(child, text) {
  return new Promise((resolve, reject) => {
    let output = "";
    const timer = setTimeout(
      () => reject(new Error(`no "${text}" within ${READY_TIMEOUT_MS} ms: ${output}`)),
      READY_TIMEOUT_MS,
    );
    child.stdout.on("data", (data) => {
      output += data;
      if (output.includes(text)) {
        clearTimeout(timer);
        resolve();
      }
    });
    child.once("exit", (code, signal) => {
      clearTimeout(timer);
      reject(new Error(`exited with ${code ?? signal} before printing "${text}"`));
    });
  });
}

/** Kills `child` if a failed test left it running. */
function stop(child) {
  if (child.exitCode === null && child.signalCode === null) {
    child.kill("SIGKILL");
  }
}

test("a server that misses its deadline is stopped before startMetab rejects", async () => {
  const binary = fake("silent", "exec sleep 600");
  await assert.rejects(
    processes.startMetab(binary, work, work, {
      cleanup: new processes.Cleanup(),
      timeoutMs: 1_500,
    }),
    /did not announce a URL/,
  );
  assert.equal(alive(pidOf(binary)), false, "the server outlived its failed start");
});

test("a server that exits before announcing rejects with its output", async () => {
  const binary = fake("early-exit", 'echo "no such folder" >&2\nexit 2');
  await assert.rejects(
    processes.startMetab(binary, work, work, { cleanup: new processes.Cleanup() }),
    /exited with 2 before serving:\nno such folder/,
  );
});

test("a missing binary rejects instead of crashing the harness", async () => {
  await assert.rejects(
    processes.startMetab(path.join(work, "no-such-metab"), work, work, {
      cleanup: new processes.Cleanup(),
    }),
    /no-such-metab/,
  );
});

test("the server gets --exit-on-eof, and Cleanup stops it by closing its stdin", async () => {
  const binary = fake("serving", SERVING);
  const cleanup = new processes.Cleanup();
  const { origin, child } = await processes.startMetab(binary, work, work, { cleanup });
  assert.match(origin, /^http:\/\/127\.0\.0\.1:\d+$/);
  assert.ok(fs.readFileSync(`${binary}.args`, "utf8").split("\n").includes("--exit-on-eof"));
  assert.deepEqual(await cleanup.run(), []);
  assert.equal(child.exitCode, 0, "the server stopped at the end of its stdin, not by a signal");
});

test("the server ends when the harness is killed outright", async () => {
  const binary = fake("orphan", SERVING);
  const module = new URL("./processes.mjs", import.meta.url).href;
  const harness = spawn(
    process.execPath,
    [
      "--input-type=module",
      "-e",
      `const { Cleanup, startMetab } = await import(${JSON.stringify(module)});
       await startMetab(${JSON.stringify(binary)}, ${JSON.stringify(work)}, ${JSON.stringify(work)}, { cleanup: new Cleanup() });
       console.log("ready");
       setInterval(() => {}, 1000);`,
    ],
    { stdio: ["ignore", "pipe", "inherit"] },
  );
  try {
    await printed(harness, "ready");
    const server = pidOf(binary);
    assert.equal(alive(server), true);
    harness.kill("SIGKILL");
    assert.equal(await gone(server, 5_000), true, "the server outlived a killed harness");
  } finally {
    stop(harness);
  }
});

test("terminate escalates to SIGKILL for a child that ignores SIGTERM", async () => {
  // The shell sets its trap half a second late and says "ready" once it has, so the test
  // fails on a SIGTERM sent before the trap unless it waits for that line.
  const child = spawn(
    "/bin/sh",
    ["-c", "sleep 0.5; trap '' TERM; echo ready; while :; do sleep 0.05; done"],
    { stdio: ["pipe", "pipe", "ignore"] },
  );
  try {
    await printed(child, "ready");
    await processes.terminate(child, { graceMs: 200 });
    assert.equal(child.signalCode, "SIGKILL");
  } finally {
    stop(child);
  }
});

test("terminate returns at once for a child that never started", async () => {
  const child = spawn(path.join(work, "no-such-program"));
  await new Promise((resolve) => child.once("error", resolve));
  await processes.terminate(child, { graceMs: 200 });
});

test("Cleanup runs every step, newest first, and returns the errors", async () => {
  const cleanup = new processes.Cleanup();
  const order = [];
  cleanup.add(() => order.push("first"));
  cleanup.add(() => {
    throw new Error("a step failed");
  });
  cleanup.add(async () => order.push("last"));
  const errors = await cleanup.run();
  assert.deepEqual(order, ["last", "first"]);
  assert.deepEqual(
    errors.map((error) => error.message),
    ["a step failed"],
  );
  assert.deepEqual(await cleanup.run(), [], "a second run has nothing left to do");
});

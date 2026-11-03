// Run the exact recorder with process/CDP stand-ins. These are lifecycle fault probes,
// not browser measurements: no real server, Chrome profile, or clock is used.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const source = fs.readFileSync(
  path.resolve(__dirname, "../../explorations/performance-loop/pr-page.mjs"),
  "utf8",
);

async function probe(failure, keepServer = false) {
  let now = 0;
  let profilePresent = false;
  let chrome = null;
  let server = null;
  let readyProbes = 0;
  let browserCloses = 0;
  let connectionCloses = 0;
  let serverStopped = false;
  let serverUnreferenced = false;
  let serverStdio;
  let output;
  const errors = [];
  const completed = Promise.withResolvers();
  const environment = {
    PR_PERF_ROOT: "/fixture",
  };
  const profile = "/fixture/prof-101";
  const proc = {
    env: environment,
    argv: ["node", "pr-page.mjs", "--build", "new", "--number", "7", "--files", "1"],
    pid: 101,
    kill(pid) {
      if (pid === -201) {
        serverStopped = true;
        server.signalCode = "SIGTERM";
      } else if (pid === 301) {
        chrome.signalCode = "SIGKILL";
      } else {
        assert.fail(`not an owned process: ${pid}`);
      }
    },
    exit: (code) => completed.resolve(code),
    set exitCode(code) {
      completed.resolve(code);
    },
  };
  if (keepServer) {
    proc.argv.push("--keep-server");
  }
  const child = (pid) => ({
    pid,
    exitCode: null,
    signalCode: null,
    stdout: { on() {} },
    stderr: { on() {} },
    kill(signal) {
      this.signalCode = signal;
    },
    unref() {
      serverUnreferenced = true;
    },
  });
  const processApi = {
    execFileSync(command) {
      if (command === "/usr/sbin/sysctl") {
        return Buffer.from("{ 1 1 1 }");
      }
      return Buffer.from("");
    },
    spawn(command, _args, options) {
      if (command.endsWith("/bin/metab")) {
        server = child(201);
        serverStdio = options.stdio;
        return server;
      }
      assert.equal(command, "/fixture/chrome");
      chrome = child(301);
      return chrome;
    },
  };
  const fileApi = {
    mkdirSync(directory) {
      if (directory === profile) {
        profilePresent = true;
      }
    },
    rmSync(directory) {
      assert.equal(directory, profile);
      profilePresent = false;
    },
    existsSync: () => failure !== "port",
    readFileSync: (file) =>
      file.endsWith("DevToolsActivePort") ? "1234\n/devtools/browser/test" : "server log",
    openSync: () => 9,
    closeSync() {},
  };
  const page = {
    on() {},
    async send(method, params) {
      if (method === "Page.navigate" && failure === "navigation") {
        throw Error("navigation failed");
      }
      if (method !== "Runtime.evaluate") {
        return {};
      }
      const value = params.expression.includes("T && T.check()")
        ? { m: {}, p: { firstLine: 1, allBars: 1 }, lt: 0 }
        : {
            painted: { firstLine: 1, allBars: 1 },
            longtasks: [],
            bars: 1,
            lines: 1,
          };
      return { result: { value: JSON.stringify(value) } };
    },
  };
  class Connection {
    async open() {
      if (failure === "connection") {
        throw Error("connection failed");
      }
    }
    async send(method) {
      if (method === "Browser.close") {
        browserCloses += 1;
        if (failure === "connection") {
          throw Error("connection unavailable");
        }
        chrome.exitCode = 0;
      }
      if (method === "Target.getTargets") {
        return { targetInfos: [{ type: "page", targetId: "page" }] };
      }
      return { sessionId: "session" };
    }
    adopt() {
      return page;
    }
    close() {
      connectionCloses += 1;
    }
  }
  const context = vm.createContext({
    process: proc,
    Date: class extends Date {
      static now() {
        return now;
      }
    },
    console: {
      error: (error) => errors.push(String(error)),
      log: (line) => {
        output = JSON.parse(line);
        completed.resolve(0);
      },
    },
    fetch: async () => {
      readyProbes += 1;
      return { ok: failure !== "readiness" };
    },
  });
  const dependencies = {
    "node:child_process": processApi,
    "node:fs": { default: fileApi },
    "node:path": { default: path },
    "./pr-cdp.mjs": {
      CHROME: "/fixture/chrome",
      Connection,
      sleep: async (ms) => {
        now += ms;
      },
    },
  };
  const recorder = new vm.SourceTextModule(source, { context });
  await recorder.link((name) => {
    const values = dependencies[name];
    assert.ok(values, `unexpected import ${name}`);
    return new vm.SyntheticModule(
      Object.keys(values),
      function expose() {
        for (const [key, value] of Object.entries(values)) {
          this.setExport(key, value);
        }
      },
      { context },
    );
  });
  await recorder.evaluate();
  const exit = await completed.promise;
  // Console output may precede finally cleanup; allow the microtask chain to settle.
  await new Promise((resolve) => setImmediate(resolve));
  return {
    exit,
    output,
    errors,
    readyProbes,
    chrome,
    profilePresent,
    browserCloses,
    connectionCloses,
    serverStopped,
    serverUnreferenced,
    serverStdio,
  };
}

async function run() {
  const failures = [];
  for (const [stage, keep] of [
    ["readiness", false],
    ["port", false],
    ["connection", false],
    ["navigation", false],
    ["none", false],
    ["none", true],
    ["navigation", true],
  ]) {
    const result = await probe(stage, keep);
    try {
      assert.equal(result.exit, stage === "none" ? 0 : 1);
      assert.equal(result.serverStopped, !keep);
      assert.equal(result.profilePresent, false, "a completed run owns no profile");
      if (stage === "readiness") {
        assert.equal(result.readyProbes, 600);
        assert.equal(result.chrome, null, "readiness exhaustion never starts Chrome");
        assert.match(result.errors.join("\n"), /server.*ready/i);
        assert.equal(result.output, undefined, "a failed run never publishes a sample");
      } else if (stage === "port") {
        assert.equal(result.browserCloses, 0, "launch may fail before a connection exists");
        assert.equal(result.connectionCloses, 0);
        assert.equal(result.chrome.signalCode, "SIGKILL");
      } else {
        assert.equal(result.browserCloses, 1);
        assert.equal(result.connectionCloses, 1);
        assert.notEqual(result.chrome.exitCode ?? result.chrome.signalCode, null);
      }
      if (keep) {
        assert.equal(
          result.serverUnreferenced,
          true,
          "retained children do not hold the recorder open",
        );
        assert.equal(typeof result.serverStdio[1], "number", "retained logs outlive parent pipes");
        assert.equal(result.serverStdio[1], result.serverStdio[2]);
      }
    } catch (error) {
      failures.push(`${stage}, keep=${keep}: ${error.message}`);
    }
  }
  assert.deepEqual(failures, []);
  process.stdout.write("recorder lifecycle: 7 scenarios passed\n");
}

run().catch((error) => {
  process.stderr.write(`${error.stack}\n`);
  process.exitCode = 1;
});

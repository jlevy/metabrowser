const path = require("node:path");
const { pathToFileURL } = require("node:url");

const repoRoot = path.resolve(process.argv[2]);
const moduleUrl = pathToFileURL(
  path.join(repoRoot, "src/metabrowser/builtin_plugins/markdown/markdown-worker-client.js"),
).href;
const failures = [];

function check(name, condition, detail = "failed") {
  if (!condition) {
    failures.push(`${name}: ${detail}`);
  }
}

function rejected(promise) {
  return promise.then(
    () => null,
    (error) => error,
  );
}

(async () => {
  const { createMarkdownWorkerClient } = await import(moduleUrl);
  const workerMessages = [];
  globalThis.self = { postMessage: (message) => workerMessages.push(message) };
  await import(
    `${
      pathToFileURL(
        path.join(repoRoot, "src/metabrowser/builtin_plugins/markdown/markdown-worker.js"),
      ).href
    }?protocol-test`
  );
  await globalThis.self.onmessage({
    data: { id: 41, op: "prepare-primary", payload: { source: "[[Protocol]]" } },
  });
  await globalThis.self.onmessage({ data: { id: "invalid" } });
  check(
    "Worker endpoint validates requests and dispatches the production operation",
    workerMessages.length === 1 &&
      workerMessages[0].id === 41 &&
      workerMessages[0].result?.targetCount === 1,
    JSON.stringify(workerMessages),
  );
  delete globalThis.self;
  const NativeWorker = globalThis.Worker;
  const NativeWindow = globalThis.window;
  const NativeDocument = globalThis.document;
  const workers = [];

  class FakeWorker {
    constructor(url, options) {
      this.url = String(url);
      this.options = options;
      this.messages = [];
      this.onmessage = null;
      this.onerror = null;
      this.onmessageerror = null;
      this.terminated = false;
      workers.push(this);
    }

    postMessage(message) {
      this.messages.push(message);
    }

    reply(result) {
      const message = this.messages.at(-1);
      this.onmessage?.({ data: { id: message.id, result } });
    }

    terminate() {
      this.terminated = true;
    }
  }

  globalThis.Worker = FakeWorker;
  globalThis.window = {};
  globalThis.document = {};
  const client = createMarkdownWorkerClient();
  check("client construction is lazy", workers.length === 0);
  const alreadyAborted = new AbortController();
  alreadyAborted.abort();
  const preAbortedError = await rejected(
    client.run("prepare-primary", { source: "" }, { signal: alreadyAborted.signal }),
  );
  check(
    "pre-dispatch abort avoids Worker construction",
    preAbortedError?.name === "AbortError" && workers.length === 0,
  );

  const first = client.run("prepare-primary", { source: "first" });
  const second = client.run("prepare-primary", { source: "second" });
  const queuedAbort = new AbortController();
  const thirdErrorPromise = rejected(
    client.run("prepare-transclusion", { source: "third" }, { signal: queuedAbort.signal }),
  );
  check(
    "FIFO dispatches only the active request",
    workers.length === 1 && workers[0].messages.length === 1,
    JSON.stringify(workers.map((worker) => worker.messages)),
  );
  queuedAbort.abort();
  const thirdError = await thirdErrorPromise;
  workers[0].reply("first-result");
  check(
    "settling active dispatches the next request",
    workers[0].messages.length === 2 && workers[0].messages[1].payload.source === "second",
  );
  workers[0].reply("second-result");
  check(
    "FIFO values and queued abort",
    (await first) === "first-result" &&
      (await second) === "second-result" &&
      thirdError?.name === "AbortError",
  );
  client.dispose();
  check("dispose terminates the Worker", workers[0].terminated);

  const activeClient = createMarkdownWorkerClient();
  const activeAbort = new AbortController();
  const activeErrorPromise = rejected(
    activeClient.run("prepare-primary", { source: "active" }, { signal: activeAbort.signal }),
  );
  const afterActive = activeClient.run("prepare-primary", { source: "after" });
  const activeWorker = workers.at(-1);
  activeAbort.abort();
  const replacementWorker = workers.at(-1);
  check(
    "active abort terminates and resumes on a fresh Worker",
    activeWorker.terminated &&
      replacementWorker !== activeWorker &&
      replacementWorker.messages[0].payload.source === "after",
  );
  activeWorker.reply("stale-result");
  activeWorker.onerror({ message: "stale worker error" });
  activeWorker.onmessageerror({});
  check("terminated Worker events cannot poison its replacement", !replacementWorker.terminated);
  replacementWorker.reply("after-result");
  check(
    "active abort rejects only the canceled request",
    (await activeErrorPromise)?.name === "AbortError" && (await afterActive) === "after-result",
  );
  activeClient.dispose();

  const owner = new AbortController();
  const ownerClient = createMarkdownWorkerClient({ signal: owner.signal });
  const ownerActive = rejected(ownerClient.run("prepare-primary", { source: "owner-active" }));
  const ownerQueued = rejected(ownerClient.run("prepare-primary", { source: "owner-queued" }));
  const ownerWorker = workers.at(-1);
  owner.abort();
  check(
    "owner abort rejects active and queued work",
    (await ownerActive)?.name === "AbortError" &&
      (await ownerQueued)?.name === "AbortError" &&
      ownerWorker.terminated,
  );

  const operationClient = createMarkdownWorkerClient();
  const operationFailure = rejected(operationClient.run("prepare-primary", { source: "bad" }));
  const afterOperation = operationClient.run("prepare-primary", { source: "good" });
  const operationWorker = workers.at(-1);
  const operationMessage = operationWorker.messages[0];
  operationWorker.onmessage({
    data: {
      error: { code: "bad-source", message: "bad operation", name: "TypeError" },
      id: operationMessage.id,
    },
  });
  check("operation failure keeps the Worker usable", operationWorker.messages.length === 2);
  operationWorker.reply("recovered");
  check(
    "operation error is reconstructed and FIFO continues",
    (await operationFailure)?.message === "bad operation" && (await afterOperation) === "recovered",
  );
  operationClient.dispose();

  for (const mode of ["error", "messageerror", "protocol"]) {
    const fatalClient = createMarkdownWorkerClient();
    const pending = rejected(fatalClient.run("prepare-primary", { source: mode }));
    const fatalWorker = workers.at(-1);
    if (mode === "error") {
      fatalWorker.onerror({ message: "worker failed" });
    } else if (mode === "messageerror") {
      fatalWorker.onmessageerror({});
    } else {
      fatalWorker.onmessage({ data: { id: 999, result: null } });
    }
    const fatalError = await pending;
    const laterError = await rejected(fatalClient.run("prepare-primary", { source: "later" }));
    check(
      `${mode} is sticky and fatal`,
      fatalWorker.terminated && fatalError instanceof Error && laterError === fatalError,
    );
  }

  // The page-scoped owner shares one lazily constructed client across every
  // reference, cancels only a released reference's requests, terminates the
  // Worker with the last reference, and replaces a fatally failed client.
  const { acquireMarkdownWorkerClient } = await import(moduleUrl);
  const workersBeforeSharing = workers.length;
  const firstReference = acquireMarkdownWorkerClient();
  const secondReference = acquireMarkdownWorkerClient();
  const preAbortedShared = new AbortController();
  preAbortedShared.abort();
  const preAbortedSharedError = await rejected(
    firstReference.run("prepare-primary", { source: "" }, { signal: preAbortedShared.signal }),
  );
  check(
    "shared references construct no Worker before a live request",
    preAbortedSharedError?.name === "AbortError" && workers.length === workersBeforeSharing,
  );
  const firstShared = firstReference.run("prepare-primary", { source: "first-shared" });
  const secondShared = secondReference.run("prepare-primary", { source: "second-shared" });
  const sharedWorker = workers.at(-1);
  check(
    "references share one lazily constructed Worker",
    workers.length === workersBeforeSharing + 1 && sharedWorker.messages.length === 1,
  );
  sharedWorker.reply("first-shared-result");
  check(
    "shared FIFO continues across references",
    (await firstShared) === "first-shared-result" && sharedWorker.messages.length === 2,
  );
  const releasedQueued = rejected(
    firstReference.run("prepare-primary", { source: "released-queued" }),
  );
  firstReference.dispose();
  firstReference.dispose();
  check(
    "releasing a reference cancels only its own queued request",
    (await releasedQueued)?.name === "AbortError" &&
      !sharedWorker.terminated &&
      sharedWorker.messages.at(-1).payload.source === "second-shared",
  );
  sharedWorker.reply("second-shared-result");
  check(
    "the remaining reference keeps the shared Worker",
    (await secondShared) === "second-shared-result" && !sharedWorker.terminated,
  );
  check(
    "a released reference refuses new work",
    (await rejected(firstReference.run("prepare-primary", { source: "late" })))?.name ===
      "AbortError",
  );
  const crashing = rejected(secondReference.run("prepare-primary", { source: "crash" }));
  sharedWorker.onerror({ message: "shared worker failed" });
  const crashError = await crashing;
  const recovering = secondReference.run("prepare-primary", { source: "after-crash" });
  const recoveredWorker = workers.at(-1);
  check(
    "a fatal failure rejects its request and the next request gets a new Worker",
    crashError?.message === "shared worker failed" &&
      sharedWorker.terminated &&
      recoveredWorker !== sharedWorker &&
      recoveredWorker.messages[0]?.payload.source === "after-crash",
  );
  recoveredWorker.reply("recovered-shared-result");
  check("the replacement Worker serves requests", (await recovering) === "recovered-shared-result");
  const lastReference = acquireMarkdownWorkerClient();
  secondReference.dispose();
  check("a remaining reference keeps the replacement Worker", !recoveredWorker.terminated);
  lastReference.dispose();
  check("the last reference terminates the shared Worker", recoveredWorker.terminated);
  const reacquired = acquireMarkdownWorkerClient();
  const reacquiredRun = reacquired.run("prepare-primary", { source: "reacquired" });
  const reacquiredWorker = workers.at(-1);
  check(
    "a reference acquired after full release starts a new Worker lazily",
    reacquiredWorker !== recoveredWorker && reacquiredWorker.messages.length === 1,
  );
  reacquiredWorker.reply("reacquired-result");
  check("the new page Worker serves requests", (await reacquiredRun) === "reacquired-result");
  reacquired.dispose();

  class ConstructorFailure {
    constructor() {
      throw new Error("constructor failed");
    }
  }
  globalThis.Worker = ConstructorFailure;
  const constructorClient = createMarkdownWorkerClient();
  const constructorError = await rejected(
    constructorClient.run("prepare-primary", { source: "constructor" }),
  );
  check("constructor failure rejects", constructorError?.message === "constructor failed");

  class PostFailure extends FakeWorker {
    postMessage() {
      throw new Error("post failed");
    }
  }
  globalThis.Worker = PostFailure;
  const postClient = createMarkdownWorkerClient();
  const postError = await rejected(postClient.run("prepare-primary", { source: "post" }));
  check("postMessage failure rejects and terminates", postError?.message === "post failed");

  globalThis.Worker = undefined;
  const browserClient = createMarkdownWorkerClient();
  const browserError = await rejected(browserClient.run("prepare-primary", { source: "browser" }));
  check(
    "browser never falls back to synchronous preprocessing",
    browserError?.message.includes("requires Worker support"),
  );

  delete globalThis.window;
  delete globalThis.document;
  const directClient = createMarkdownWorkerClient();
  const primary = await directClient.run("prepare-primary", { source: "[[Target]]" });
  const transclusion = await directClient.run("prepare-transclusion", {
    fragment: "obsidian-heading-Selected",
    source: "# Selected\n[[Nested]]\n# Later\n",
  });
  check(
    "browserless direct mode runs both canonical operations",
    primary.changed === true &&
      transclusion.status === "selected" &&
      !transclusion.source.includes("# Later"),
  );
  directClient.dispose();

  globalThis.Worker = NativeWorker;
  if (NativeWindow === undefined) {
    delete globalThis.window;
  } else {
    globalThis.window = NativeWindow;
  }
  if (NativeDocument === undefined) {
    delete globalThis.document;
  } else {
    globalThis.document = NativeDocument;
  }
  if (failures.length) {
    console.error(`markdown worker FAILURES:\n- ${failures.join("\n- ")}`);
    process.exit(1);
  }
  console.log("markdown worker OK");
})().catch((error) => {
  console.error(error);
  process.exit(1);
});

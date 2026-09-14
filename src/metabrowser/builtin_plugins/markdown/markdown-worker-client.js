const WORKER_URL = new URL("./markdown-worker.js", import.meta.url);

/** @typedef {"prepare-primary" | "prepare-transclusion"} MarkdownWorkerOperation */

/**
 * The request surface a Markdown mount uses. `dispose` releases the caller's
 * claim on the Worker; it never cancels another caller's requests.
 *
 * @typedef {Readonly<{dispose: () => void, run: ReturnType<typeof createMarkdownWorkerClient>["run"]}>} MarkdownWorkerRunner
 */

/** @type {ReturnType<typeof createMarkdownWorkerClient> | null} */
let sharedClient = null;
let sharedReferences = 0;

/**
 * Acquire a reference to the page's one shared Markdown Worker client.
 *
 * Every rendered document, folder README panel, and nested transclusion on the
 * page uses the same lazily constructed module Worker instead of constructing and
 * terminating one per mount. Each reference cancels only its own requests when
 * disposed, and the Worker terminates when the last reference is released. A
 * client latched by a fatal Worker failure is replaced on the next request, so one
 * crash does not disable preprocessing for documents mounted afterward.
 *
 * A fatal failure rejects every reference's pending requests, not only the
 * request that was running. The Worker catches operation errors and reports
 * them for their own request, so what remains fatal is a module that cannot
 * load, a Worker that stops, or a reply that breaks the message protocol. The
 * first two fail every request alike and the last is a defect, so pending work
 * is not retried; each rejected mount renders its authored Markdown with a
 * diagnostic instead.
 *
 * @returns {MarkdownWorkerRunner}
 */
export function acquireMarkdownWorkerClient() {
  sharedReferences += 1;
  let released = false;
  /** @type {Set<AbortController>} */
  const requests = new Set();

  function release() {
    if (released) {
      return;
    }
    released = true;
    const reason = disposedError();
    for (const controller of requests) {
      controller.abort(reason);
    }
    requests.clear();
    sharedReferences -= 1;
    if (sharedReferences === 0) {
      const client = sharedClient;
      sharedClient = null;
      client?.dispose();
    }
  }

  return Object.freeze({
    dispose: release,
    /** @param {MarkdownWorkerOperation} op @param {unknown} payload @param {{signal?: AbortSignal}=} requestOptions */
    run(op, payload, requestOptions = {}) {
      if (released) {
        return Promise.reject(disposedError());
      }
      const signal = requestOptions.signal;
      if (signal?.aborted) {
        return Promise.reject(abortReason(signal));
      }
      if (!sharedClient || sharedClient.failed()) {
        sharedClient?.dispose();
        sharedClient = createMarkdownWorkerClient();
      }
      // One controller per request joins the caller's signal with this
      // reference's lifetime, so releasing a reference cancels exactly the
      // requests it started.
      const controller = new AbortController();
      const forwardAbort = () => controller.abort(abortReason(signal));
      signal?.addEventListener("abort", forwardAbort, { once: true });
      requests.add(controller);
      return sharedClient.run(op, payload, { signal: controller.signal }).finally(() => {
        requests.delete(controller);
        signal?.removeEventListener("abort", forwardAbort);
      });
    },
  });
}

/**
 * Create one lazy Markdown CPU-work client that runs one request at a time.
 *
 * Requests queue in two first-in, first-out lanes, and a queued primary
 * preparation always dispatches before a queued transclusion preparation. The
 * shell mounts an incoming document into a stage and waits for its primary
 * preparation before it disposes the outgoing document, whose queued embeds
 * are canceled only by that disposal; one shared queue would make navigation
 * wait for the outgoing document's embeds. A dispatched request always
 * finishes, because Worker operations are synchronous once they start. Embeds
 * cannot starve, since primaries arrive only when a document mounts.
 *
 * Browser requests never fall back to main-thread execution. Node-based contract tests
 * use the same operation modules directly when Worker is unavailable. Mounts use
 * `acquireMarkdownWorkerClient`, which shares one client across the page.
 *
 * @param {{signal?: AbortSignal}=} options
 */
export function createMarkdownWorkerClient(options = {}) {
  if (!options || typeof options !== "object") {
    throw new TypeError("Markdown worker client options must be an object");
  }
  const WorkerConstructor = globalThis.Worker;
  const direct = typeof WorkerConstructor !== "function" && !isBrowserRuntime();
  let sequence = 0;
  let disposed = false;
  /** @type {Error | null} */
  let fatalError = null;
  /** @type {Worker | null} */
  let worker = null;
  let workerGeneration = 0;
  /** @type {WorkerRequest | null} */
  let active = null;
  /** @type {WorkerRequest[]} */
  const primaryQueue = [];
  /** @type {WorkerRequest[]} */
  const transclusionQueue = [];

  const abortOwner = () => disposeWithReason(abortReason(options.signal));
  if (options.signal?.aborted) {
    disposed = true;
  } else {
    options.signal?.addEventListener("abort", abortOwner, { once: true });
  }

  /** @param {unknown} reason */
  function disposeWithReason(reason) {
    if (disposed) {
      return;
    }
    disposed = true;
    options.signal?.removeEventListener("abort", abortOwner);
    worker?.terminate();
    worker = null;
    const requests = drainRequests();
    for (const request of requests) {
      detachAbort(request);
      request.reject(reason);
    }
  }

  /** @param {Error} error */
  function fail(error) {
    if (fatalError || disposed) {
      return;
    }
    fatalError = error;
    worker?.terminate();
    worker = null;
    const requests = drainRequests();
    for (const request of requests) {
      detachAbort(request);
      request.reject(error);
    }
  }

  function ensureWorker() {
    if (worker) {
      return worker;
    }
    if (typeof WorkerConstructor !== "function") {
      throw new Error("Markdown preprocessing requires Worker support in a browser");
    }
    let created;
    try {
      created = new WorkerConstructor(WORKER_URL, { type: "module" });
    } catch (error) {
      const failure = asError(error, "Markdown worker construction failed");
      fail(failure);
      throw failure;
    }
    worker = created;
    workerGeneration += 1;
    const generation = workerGeneration;
    created.onmessage = (event) => {
      if (worker === created && workerGeneration === generation) {
        handleMessage(event);
      }
    };
    created.onerror = (event) => {
      if (worker === created && workerGeneration === generation) {
        fail(new Error(event.message || "Markdown worker failed"));
      }
    };
    created.onmessageerror = () => {
      if (worker === created && workerGeneration === generation) {
        fail(new Error("Markdown worker returned an unreadable message"));
      }
    };
    return created;
  }

  /** @param {MessageEvent} event */
  function handleMessage(event) {
    const message = event.data;
    if (!active || !message || typeof message !== "object" || message.id !== active.id) {
      fail(new Error("Markdown worker violated the request protocol"));
      return;
    }
    const request = active;
    active = null;
    detachAbort(request);
    if ("error" in message) {
      request.reject(workerError(message.error));
    } else if (!("result" in message)) {
      const protocolError = new Error("Markdown worker returned an invalid response");
      request.reject(protocolError);
      fail(protocolError);
      return;
    } else {
      request.resolve(message.result);
    }
    pump();
  }

  function pump() {
    if (disposed || fatalError || active) {
      return;
    }
    const request = primaryQueue.shift() ?? transclusionQueue.shift();
    if (!request) {
      return;
    }
    if (request.signal?.aborted) {
      detachAbort(request);
      request.reject(abortReason(request.signal));
      pump();
      return;
    }
    active = request;
    if (direct) {
      void runDirect(request);
      return;
    }
    let currentWorker;
    try {
      currentWorker = ensureWorker();
      currentWorker.postMessage({ id: request.id, op: request.op, payload: request.payload });
    } catch (error) {
      const failure = asError(error, "Markdown worker request failed");
      if (!fatalError) {
        fail(failure);
      }
    }
  }

  /** @param {WorkerRequest} request */
  async function runDirect(request) {
    try {
      const { runMarkdownOperation } = await import("./markdown-worker-operations.js");
      request.signal?.throwIfAborted();
      const value = await runMarkdownOperation(request.op, request.payload);
      if (active !== request || disposed) {
        return;
      }
      active = null;
      detachAbort(request);
      request.resolve(value);
      pump();
    } catch (error) {
      if (active !== request || disposed) {
        return;
      }
      active = null;
      detachAbort(request);
      request.reject(error);
      pump();
    }
  }

  /** @param {WorkerRequest} request */
  function abortRequest(request) {
    if (active === request) {
      active = null;
      detachAbort(request);
      request.reject(abortReason(request.signal));
      // Worker operations are synchronous once dispatched. Termination is the only
      // reliable cancellation boundary; the next queued request gets a fresh worker.
      worker?.terminate();
      worker = null;
      pump();
      return;
    }
    const lane = laneFor(request.op);
    const index = lane.indexOf(request);
    if (index === -1) {
      return;
    }
    lane.splice(index, 1);
    detachAbort(request);
    request.reject(abortReason(request.signal));
  }

  /** @param {MarkdownWorkerOperation} op */
  function laneFor(op) {
    return op === "prepare-primary" ? primaryQueue : transclusionQueue;
  }

  /** Remove the active request and both lanes, in dispatch order. */
  function drainRequests() {
    const requests = [...(active ? [active] : []), ...primaryQueue, ...transclusionQueue];
    active = null;
    primaryQueue.length = 0;
    transclusionQueue.length = 0;
    return requests;
  }

  /** @param {WorkerRequest} request */
  function detachAbort(request) {
    request.signal?.removeEventListener("abort", request.abort);
  }

  return Object.freeze({
    dispose() {
      disposeWithReason(disposedError());
    },
    /** Whether a fatal Worker failure has permanently latched this client. */
    failed() {
      return fatalError !== null;
    },
    /** @param {MarkdownWorkerOperation} op @param {unknown} payload @param {{signal?: AbortSignal}=} requestOptions */
    run(op, payload, requestOptions = {}) {
      if (!isOperation(op)) {
        return Promise.reject(new TypeError("Unknown Markdown worker operation"));
      }
      if (requestOptions.signal?.aborted) {
        return Promise.reject(abortReason(requestOptions.signal));
      }
      if (disposed) {
        return Promise.reject(
          options.signal?.aborted ? abortReason(options.signal) : disposedError(),
        );
      }
      if (fatalError) {
        return Promise.reject(fatalError);
      }
      sequence += 1;
      return new Promise((resolve, reject) => {
        /** @type {WorkerRequest} */
        const request = {
          abort: () => abortRequest(request),
          id: sequence,
          op,
          payload,
          reject,
          resolve,
          signal: requestOptions.signal,
        };
        request.signal?.addEventListener("abort", request.abort, { once: true });
        laneFor(op).push(request);
        pump();
      });
    },
  });
}

/** @typedef {{abort: () => void, id: number, op: MarkdownWorkerOperation, payload: unknown, reject: (reason: unknown) => void, resolve: (value: unknown) => void, signal?: AbortSignal}} WorkerRequest */

function isBrowserRuntime() {
  return typeof globalThis.window === "object" && typeof globalThis.document === "object";
}

/** @param {unknown} value @returns {value is MarkdownWorkerOperation} */
function isOperation(value) {
  return value === "prepare-primary" || value === "prepare-transclusion";
}

function disposedError() {
  return new DOMException("Markdown worker client disposed", "AbortError");
}

/** @param {AbortSignal | undefined} signal */
function abortReason(signal) {
  return signal?.reason || new DOMException("The operation was aborted", "AbortError");
}

/** @param {unknown} value @param {string} fallback */
function asError(value, fallback) {
  return value instanceof Error ? value : new Error(value === undefined ? fallback : String(value));
}

/** @param {unknown} value */
function workerError(value) {
  if (!value || typeof value !== "object") {
    return new Error("Markdown worker operation failed");
  }
  const record = /** @type {Record<string, unknown>} */ (value);
  const error = new Error(
    typeof record.message === "string" ? record.message : "Markdown worker operation failed",
  );
  if (typeof record.name === "string") {
    error.name = record.name;
  }
  if (typeof record.code === "string") {
    Object.defineProperty(error, "code", { value: record.code });
  }
  return error;
}

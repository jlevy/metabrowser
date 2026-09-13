const WORKER_URL = new URL("./markdown-worker.js", import.meta.url);

/** @typedef {"prepare-primary" | "prepare-transclusion"} MarkdownWorkerOperation */

/**
 * Create one lazy, FIFO Markdown CPU-work client.
 *
 * Browser requests never fall back to main-thread execution. Node-based contract tests
 * use the same operation modules directly when Worker is unavailable.
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
  const queued = [];

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
    const requests = active ? [active, ...queued] : [...queued];
    active = null;
    queued.length = 0;
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
    const requests = active ? [active, ...queued] : [...queued];
    active = null;
    queued.length = 0;
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
    if (disposed || fatalError || active || queued.length === 0) {
      return;
    }
    const request = queued.shift();
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
    const index = queued.indexOf(request);
    if (index === -1) {
      return;
    }
    queued.splice(index, 1);
    detachAbort(request);
    request.reject(abortReason(request.signal));
  }

  /** @param {WorkerRequest} request */
  function detachAbort(request) {
    request.signal?.removeEventListener("abort", request.abort);
  }

  return Object.freeze({
    dispose() {
      disposeWithReason(new DOMException("Markdown worker client disposed", "AbortError"));
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
          options.signal?.aborted
            ? abortReason(options.signal)
            : new DOMException("Markdown worker client disposed", "AbortError"),
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
        queued.push(request);
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

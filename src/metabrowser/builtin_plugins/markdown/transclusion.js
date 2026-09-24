import { inertArticle, placeRendered, wireInertToc } from "./inert-render.js";
import { acquireMarkdownWorkerClient } from "./markdown-worker-client.js";
import { initTocWithIntersectionFallback } from "./toc-intersection-fallback.js";

/** Bounds recursive embedding depth. */
const DEFAULT_MAX_TRANSCLUSION_DEPTH = 4;
/** Bounds note fetches shared by one rendered document. */
const DEFAULT_MAX_TRANSCLUSION_DOCUMENTS = 24;
/** Bounds aggregate UTF-8 source shared by one rendered document. */
const DEFAULT_MAX_TRANSCLUSION_SOURCE_BYTES = 8 * 1024 * 1024;
/**
 * Bounds one embed's own load, from its claim through its render. Each claim
 * starts its own clock: a shared document deadline would expire an embed whose
 * catalog resolution arrived late before that embed ever began loading.
 */
const DEFAULT_MAX_TRANSCLUSION_DURATION_MS = 5000;
/** Absolute ceilings prevent callers from relaxing the renderer's safety envelope. */
const HARD_MAX_TRANSCLUSION_DEPTH = 8;
const HARD_MAX_TRANSCLUSION_DOCUMENTS = 64;
const HARD_MAX_TRANSCLUSION_SOURCE_BYTES = 16 * 1024 * 1024;
const HARD_MAX_TRANSCLUSION_DURATION_MS = 15_000;
/** Shares the reconciliation code-unit slice for provider-long cycle identities. */
const MAX_CYCLE_CODE_UNITS_PER_TASK = 16_384;
const MAX_TRANSCLUSION_LABEL_CODE_UNITS = 512;
const BUDGETS = new WeakSet();
let transclusionSequence = 0;

class TransclusionError extends Error {
  /** @param {string} code */
  constructor(code) {
    super(code);
    this.name = "TransclusionError";
    this.code = code;
  }
}

/**
 * @typedef {Readonly<{now: () => number, setTimeout: (callback: () => void, delayMs: number) => unknown, clearTimeout: (handle: unknown) => void}>} TransclusionClock
 */

const WALL_CLOCK = Object.freeze({
  /** @param {unknown} handle */
  clearTimeout(handle) {
    globalThis.clearTimeout(/** @type {ReturnType<typeof setTimeout>} */ (handle));
  },
  now: () => Date.now(),
  /** @param {() => void} callback @param {number} delayMs */
  setTimeout: (callback, delayMs) => globalThis.setTimeout(callback, delayMs),
});

/**
 * Create shared limits for all embeds descended from one rendered document.
 * Depth, document, source-byte, and cycle limits are aggregate; the elapsed-time
 * limit applies separately to each claimed embed. Caller-provided limits may
 * reduce, but never raise, the hard ceilings.
 *
 * @param {Readonly<{maxDepth?: number, maxDocuments?: number, maxSourceBytes?: number, maxDurationMs?: number}>=} limits
 * @param {Readonly<{clock?: TransclusionClock}>=} options
 */
export function createTransclusionBudget(limits = {}, options = {}) {
  if (!limits || typeof limits !== "object") {
    throw new TypeError("Transclusion limits must be an object");
  }
  if (!options || typeof options !== "object") {
    throw new TypeError("Transclusion budget options must be an object");
  }
  const budget = Object.freeze({
    clock: validClock(options.clock),
    limits: Object.freeze({
      maxDepth: boundedLimit(
        limits.maxDepth,
        DEFAULT_MAX_TRANSCLUSION_DEPTH,
        HARD_MAX_TRANSCLUSION_DEPTH,
      ),
      maxDocuments: boundedLimit(
        limits.maxDocuments,
        DEFAULT_MAX_TRANSCLUSION_DOCUMENTS,
        HARD_MAX_TRANSCLUSION_DOCUMENTS,
      ),
      maxDurationMs: boundedLimit(
        limits.maxDurationMs,
        DEFAULT_MAX_TRANSCLUSION_DURATION_MS,
        HARD_MAX_TRANSCLUSION_DURATION_MS,
      ),
      maxSourceBytes: boundedLimit(
        limits.maxSourceBytes,
        DEFAULT_MAX_TRANSCLUSION_SOURCE_BYTES,
        HARD_MAX_TRANSCLUSION_SOURCE_BYTES,
      ),
    }),
    state: { documents: 0, sourceBytes: 0 },
  });
  BUDGETS.add(budget);
  return budget;
}

/**
 * Identify one transcluded document location for cycle detection.
 *
 * A rendered document is its own ancestor, so the top-level renderer seeds the
 * chain with its whole-note key. Without that seed a note embedding itself
 * renders one complete duplicate before the repeat is detected one level down.
 *
 * @param {string} path
 * @param {string=} fragment
 */
export function transclusionKey(path, fragment) {
  if (
    typeof path !== "string" ||
    !path ||
    (fragment !== undefined && typeof fragment !== "string")
  ) {
    throw new TypeError("Transclusion location requires a path and optional fragment");
  }
  // Keep the provider identity as an opaque reference. Concatenating it into a
  // key can copy hundreds of megabytes synchronously before any fetch begins.
  return Object.freeze({ fragment: fragment || "", path });
}

/**
 * Reserve one document and extend its immutable ancestry chain. The returned
 * deadline belongs to this claim alone and bounds the embed's whole load.
 *
 * @param {ReturnType<typeof createTransclusionBudget>} budget
 * @param {ReturnType<typeof transclusionKey>} key
 * @param {ReadonlyArray<ReturnType<typeof transclusionKey>>} chain
 * @param {{signal?: AbortSignal}=} options
 */
export async function claimTransclusion(budget, key, chain, options = {}) {
  validateBudget(budget);
  if (!isTransclusionKey(key) || !Array.isArray(chain) || !chain.every(isTransclusionKey)) {
    throw new TypeError("Transclusion claim requires a key and ancestry chain");
  }
  options.signal?.throwIfAborted();
  const deadline = budget.clock.now() + budget.limits.maxDurationMs;
  if (chain.length >= budget.limits.maxDepth) {
    throw new TransclusionError("depth-limit");
  }
  if (budget.state.documents >= budget.limits.maxDocuments) {
    throw new TransclusionError("document-limit");
  }
  const yielder = createCycleTaskYielder();
  try {
    for (const ancestor of chain) {
      if (
        await sameTransclusionLocation(ancestor, key, budget, deadline, options.signal, yielder)
      ) {
        throw new TransclusionError("cycle");
      }
    }
  } finally {
    yielder.dispose();
  }
  options.signal?.throwIfAborted();
  if (budget.clock.now() >= deadline) {
    throw new TransclusionError("timed-out");
  }
  if (budget.state.documents >= budget.limits.maxDocuments) {
    throw new TransclusionError("document-limit");
  }
  budget.state.documents += 1;
  return Object.freeze({ chain: Object.freeze([...chain, key]), deadline });
}

/** @param {unknown} value */
function isTransclusionKey(value) {
  if (!value || typeof value !== "object") {
    return false;
  }
  const location = /** @type {Record<string, unknown>} */ (value);
  return (
    typeof location.path === "string" &&
    location.path.length > 0 &&
    typeof location.fragment === "string"
  );
}

/**
 * Compare provider identities cooperatively. Chain depth is hard-capped at eight,
 * and each callback inspects at most the same 16,384 code units as catalog
 * reconciliation, regardless of provider path length.
 *
 * @param {ReturnType<typeof transclusionKey>} left
 * @param {ReturnType<typeof transclusionKey>} right
 * @param {ReturnType<typeof createTransclusionBudget>} budget
 * @param {number} deadline
 * @param {AbortSignal | undefined} signal
 * @param {ReturnType<typeof createCycleTaskYielder>} yielder
 */
async function sameTransclusionLocation(left, right, budget, deadline, signal, yielder) {
  return (
    (await sameProviderString(left.fragment, right.fragment, budget, deadline, signal, yielder)) &&
    (await sameProviderString(left.path, right.path, budget, deadline, signal, yielder))
  );
}

/** @param {string} left @param {string} right @param {ReturnType<typeof createTransclusionBudget>} budget @param {number} deadline @param {AbortSignal | undefined} signal @param {ReturnType<typeof createCycleTaskYielder>} yielder */
async function sameProviderString(left, right, budget, deadline, signal, yielder) {
  if (left.length !== right.length) {
    return false;
  }
  let index = 0;
  while (index < left.length) {
    signal?.throwIfAborted();
    if (budget.clock.now() >= deadline) {
      throw new TransclusionError("timed-out");
    }
    if (yielder.remaining() < 1) {
      await yielder.yieldTask();
      continue;
    }
    const start = index;
    const end = Math.min(left.length, index + yielder.remaining());
    while (index < end) {
      if (left.charCodeAt(index) !== right.charCodeAt(index)) {
        index += 1;
        yielder.consume(index - start);
        return false;
      }
      index += 1;
    }
    yielder.consume(index - start);
  }
  return true;
}

function createCycleTaskYielder() {
  let remaining = MAX_CYCLE_CODE_UNITS_PER_TASK;
  /** @type {MessageChannel | null} */
  let channel = null;
  /** @type {(() => void) | null} */
  let pending = null;
  let disposed = false;

  function ensureChannel() {
    if (channel) {
      return channel;
    }
    if (typeof globalThis.MessageChannel !== "function") {
      return null;
    }
    channel = new globalThis.MessageChannel();
    channel.port1.onmessage = () => {
      const resolve = pending;
      pending = null;
      resolve?.();
    };
    channel.port1.start?.();
    return channel;
  }

  return Object.freeze({
    /** @param {number} visits */
    consume(visits) {
      if (visits < 0 || visits > remaining) {
        throw new Error("Transclusion cycle comparison exceeded its task budget");
      }
      remaining -= visits;
    },
    dispose() {
      if (disposed) {
        return;
      }
      disposed = true;
      const resolve = pending;
      pending = null;
      channel?.port1.close();
      channel?.port2.close();
      channel = null;
      resolve?.();
    },
    remaining() {
      return remaining;
    },
    async yieldTask() {
      if (disposed) {
        return;
      }
      const activeChannel = ensureChannel();
      if (!activeChannel) {
        await new Promise((resolve) => globalThis.setTimeout(resolve, 0));
      } else {
        if (pending) {
          throw new Error("Transclusion cycle continuation is already pending");
        }
        await new Promise((resolve) => {
          pending = () => resolve(undefined);
          activeChannel.port2.postMessage(0);
        });
      }
      remaining = MAX_CYCLE_CODE_UNITS_PER_TASK;
    },
  });
}

/**
 * Replace one resolved note embed with a bounded, safely rendered document region.
 *
 * @param {HTMLElement} container
 * @param {Element} sourceElement
 * @param {Readonly<{path: string, fragment?: string}>} resolved
 * @param {MetabrowserPublicSdk} mb
 * @param {{budget?: ReturnType<typeof createTransclusionBudget>, chain?: ReadonlyArray<ReturnType<typeof transclusionKey>>, signal?: AbortSignal, enhanceNested?: (container: HTMLElement, sourcePath: string, options: {budget: ReturnType<typeof createTransclusionBudget>, chain: ReadonlyArray<ReturnType<typeof transclusionKey>>, signal: AbortSignal}) => {dispose?: () => void}, workerClient?: import("./markdown-worker-client.js").MarkdownWorkerRunner}=} options
 */
export function mountWikiTransclusion(container, sourceElement, resolved, mb, options = {}) {
  const document = container.ownerDocument || globalThis.document;
  if (!document) {
    throw new Error("Wiki transclusion requires a document");
  }
  const aside = document.createElement("aside");
  // A placeholder that was pending shows a status suffix in its text; the
  // authored label it recorded is the name of the note.
  const label = boundedTransclusionLabel(
    sourceElement.getAttribute("data-mb-wiki-label") || sourceElement.textContent || resolved.path,
  );
  aside.setAttribute("class", "metabrowser-wiki-transclusion");
  aside.setAttribute("role", "region");
  aside.setAttribute("aria-label", `Embedded note: ${label}`);
  aside.setAttribute("aria-busy", "true");
  aside.setAttribute("data-metabrowser-transclusion-status", "loading");
  aside.textContent = `Loading embedded note: ${label}…`;
  sourceElement.replaceWith(aside);

  const budget = options.budget || createTransclusionBudget();
  const ownsWorkerClient = !options.workerClient;
  const workerClient = options.workerClient || acquireMarkdownWorkerClient();
  const chain = options.chain || Object.freeze([]);
  const controller = new AbortController();
  let disposed = false;
  let timedOut = false;
  /** @type {unknown} */
  let timeoutHandle = null;
  /** @type {{dispose?: () => void} | null} */
  let nestedHandle = null;
  /** @type {(() => void) | null} */
  let disposeToc = null;
  const abortParent = () => dispose();
  if (options.signal?.aborted) {
    disposed = true;
    controller.abort(options.signal.reason);
    if (ownsWorkerClient) {
      workerClient.dispose();
    }
  } else {
    options.signal?.addEventListener("abort", abortParent, { once: true });
  }

  function dispose() {
    if (disposed) {
      return;
    }
    disposed = true;
    options.signal?.removeEventListener("abort", abortParent);
    clearClaimTimeout();
    controller.abort();
    if (ownsWorkerClient) {
      workerClient.dispose();
    }
    nestedHandle?.dispose?.();
    nestedHandle = null;
    disposeToc?.();
    disposeToc = null;
  }

  function clearClaimTimeout() {
    if (timeoutHandle !== null) {
      budget.clock.clearTimeout(timeoutHandle);
      timeoutHandle = null;
    }
  }

  /**
   * Report whether the load may continue after an await. Disposal ends it
   * silently; this claim's own deadline ends it with a visible timeout even
   * when the awaited operation settled without observing the abort.
   */
  function live() {
    if (disposed) {
      return false;
    }
    if (timedOut) {
      throw new TransclusionError("timed-out");
    }
    return !controller.signal.aborted;
  }

  async function render() {
    try {
      const key = transclusionKey(resolved.path, resolved.fragment);
      const claim = await claimTransclusion(budget, key, chain, {
        signal: controller.signal,
      });
      if (!live()) {
        return;
      }
      const remainingTime = claim.deadline - budget.clock.now();
      if (remainingTime <= 0) {
        throw new TransclusionError("timed-out");
      }
      timeoutHandle = budget.clock.setTimeout(() => {
        timeoutHandle = null;
        timedOut = true;
        controller.abort();
      }, remainingTime);
      const source = await mb.fetchText(Object.freeze({ path: resolved.path }), {
        signal: controller.signal,
      });
      if (!live()) {
        return;
      }
      consumeSourceBytes(budget, source);
      const prepared = await workerClient.run(
        "prepare-transclusion",
        Object.freeze({ fragment: resolved.fragment, source }),
        { signal: controller.signal },
      );
      if (!isTransclusionPreparation(prepared)) {
        throw new TypeError("Markdown worker returned an invalid transclusion preparation");
      }
      if (prepared.status !== "selected") {
        throw new TransclusionError(prepared.reason);
      }
      if (!prepared.complete) {
        throw new TransclusionError(preprocessingDiagnosticCode(prepared.diagnostics));
      }
      const rendered = await mb.fetchKpressRender(
        {
          path: resolved.path,
          raw: { content: prepared.source, content_truncated: false, type: "text" },
        },
        "rendered",
        {
          dedupKey: `markdown-transclusion-${++transclusionSequence}`,
          profile: "document",
          signal: controller.signal,
          sourceText: prepared.source,
        },
      );
      if (!live()) {
        return;
      }
      const nested = await placeRendered(aside, rendered, mb, (root) =>
        options.enhanceNested?.(root, resolved.path, {
          budget,
          chain: claim.chain,
          signal: controller.signal,
        }),
      );
      if (!live()) {
        nested?.dispose?.();
        return;
      }
      aside.setAttribute("aria-busy", "false");
      aside.setAttribute("data-metabrowser-transclusion-status", "ready");
      nestedHandle = nested || null;
      const inert = inertArticle(aside);
      disposeToc = inert
        ? wireInertToc(inert)
        : initTocWithIntersectionFallback(() => mb.kpressInitToc?.(aside) || null);
    } catch (error) {
      if (disposed || options.signal?.aborted) {
        return;
      }
      nestedHandle?.dispose?.();
      nestedHandle = null;
      disposeToc?.();
      disposeToc = null;
      const reportedCode =
        error && typeof error === "object"
          ? /** @type {Record<string, unknown>} */ (error).code
          : null;
      const code =
        error instanceof TransclusionError
          ? error.code
          : timedOut
            ? "timed-out"
            : reportedCode === "source-too-large"
              ? "source-too-large"
              : "render-failed";
      renderTransclusionError(aside, label, code);
    } finally {
      clearClaimTimeout();
    }
  }

  if (!disposed) {
    void render();
  }
  // The additive element reference lets the catalog reconciliation owner replace
  // an early incomplete-revision embed if the pinned complete revision resolves
  // differently. It does not expose mutable transclusion internals.
  return Object.freeze({ dispose, element: aside });
}

/** @param {Array<unknown>} diagnostics */
function preprocessingDiagnosticCode(diagnostics) {
  for (const diagnostic of diagnostics) {
    if (diagnostic && typeof diagnostic === "object") {
      const code = /** @type {Record<string, unknown>} */ (diagnostic).code;
      if (typeof code === "string") {
        return code;
      }
    }
  }
  return "render-failed";
}

/** @param {unknown} value */
function isTransclusionPreparation(value) {
  if (!value || typeof value !== "object") {
    return false;
  }
  const result = /** @type {Record<string, unknown>} */ (value);
  return (
    (result.status === "missing" && typeof result.reason === "string") ||
    (result.status === "selected" &&
      typeof result.complete === "boolean" &&
      Array.isArray(result.diagnostics) &&
      typeof result.kind === "string" &&
      typeof result.source === "string")
  );
}

/** @param {string} value */
function boundedTransclusionLabel(value) {
  return value.length <= MAX_TRANSCLUSION_LABEL_CODE_UNITS
    ? value
    : `${value.slice(0, MAX_TRANSCLUSION_LABEL_CODE_UNITS - 1)}…`;
}

/** @param {ReturnType<typeof createTransclusionBudget>} budget @param {string} source */
function consumeSourceBytes(budget, source) {
  const bytes = new TextEncoder().encode(source).byteLength;
  if (budget.state.sourceBytes + bytes > budget.limits.maxSourceBytes) {
    throw new TransclusionError("source-byte-limit");
  }
  budget.state.sourceBytes += bytes;
}

/** @param {unknown} clock @returns {TransclusionClock} */
function validClock(clock) {
  if (clock === undefined) {
    return WALL_CLOCK;
  }
  const value =
    clock && typeof clock === "object" ? /** @type {Record<string, unknown>} */ (clock) : null;
  if (
    !value ||
    typeof value.now !== "function" ||
    typeof value.setTimeout !== "function" ||
    typeof value.clearTimeout !== "function"
  ) {
    throw new TypeError("Transclusion clock requires now, setTimeout, and clearTimeout");
  }
  return /** @type {TransclusionClock} */ (value);
}

/** @param {unknown} budget */
function validateBudget(budget) {
  if (!budget || typeof budget !== "object" || !BUDGETS.has(budget)) {
    throw new TypeError("Transclusion budget was not created by this module");
  }
}

/** @param {unknown} requested @param {number} fallback @param {number} hardLimit */
function boundedLimit(requested, fallback, hardLimit) {
  if (requested === undefined) {
    return fallback;
  }
  if (typeof requested !== "number" || !Number.isSafeInteger(requested) || requested < 1) {
    throw new TypeError("Transclusion limits must be positive safe integers");
  }
  return Math.min(requested, hardLimit);
}

/** @param {HTMLElement} aside @param {string} label @param {string} code */
function renderTransclusionError(aside, label, code) {
  const explanation = transclusionErrorLabel(code);
  aside.innerHTML = "";
  aside.setAttribute("aria-busy", "false");
  aside.setAttribute("role", "alert");
  aside.setAttribute("data-metabrowser-transclusion-status", "error");
  aside.setAttribute("data-metabrowser-transclusion-error", code);
  aside.setAttribute("title", explanation);
  aside.textContent = `${label}: ${explanation}`;
}

/** @param {string} code */
function transclusionErrorLabel(code) {
  /** @type {Record<string, string>} */
  const labels = {
    cycle: "This embed would create a cycle.",
    "depth-limit": "The nested embed depth limit was reached.",
    "document-limit": "The embedded document limit was reached.",
    "missing-location": "The requested heading or block was not found.",
    "render-failed": "The embedded note could not be rendered.",
    "source-byte-limit": "The embedded source limit was reached.",
    "source-too-large": "The embedded note is too large.",
    "timed-out": "The embedded note timed out.",
    "transformed-source-byte-limit": "The embedded note expands past the render limit.",
    "unsupported-location": "The requested embedded location is unsupported.",
    "wiki-target-limit": "The embedded note has too many wiki targets.",
  };
  return labels[code] || "The embedded note could not be rendered.";
}

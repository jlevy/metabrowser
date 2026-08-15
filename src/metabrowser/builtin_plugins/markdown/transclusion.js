import { findMarkdownHeading, findNamedBlock, preprocessObsidianWiki } from "./wiki_parser.js";

/** Bounds recursive embedding depth. */
const DEFAULT_MAX_TRANSCLUSION_DEPTH = 4;
/** Bounds note fetches shared by one rendered document. */
const DEFAULT_MAX_TRANSCLUSION_DOCUMENTS = 24;
/** Bounds aggregate UTF-8 source shared by one rendered document. */
const DEFAULT_MAX_TRANSCLUSION_SOURCE_BYTES = 8 * 1024 * 1024;
/** Bounds elapsed work shared by one rendered document. */
const DEFAULT_MAX_TRANSCLUSION_DURATION_MS = 5000;
/** Absolute ceilings prevent callers from relaxing the renderer's safety envelope. */
const HARD_MAX_TRANSCLUSION_DEPTH = 8;
const HARD_MAX_TRANSCLUSION_DOCUMENTS = 64;
const HARD_MAX_TRANSCLUSION_SOURCE_BYTES = 16 * 1024 * 1024;
const HARD_MAX_TRANSCLUSION_DURATION_MS = 15_000;
/** Bounds source-location selection before KPress rendering. */
const MAX_SELECTED_SOURCE_CHARACTERS = 2_000_000;
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
 * Create shared limits for all embeds descended from one rendered document.
 * Caller-provided limits may reduce, but never raise, the hard ceilings.
 *
 * @param {Readonly<{maxDepth?: number, maxDocuments?: number, maxSourceBytes?: number, maxDurationMs?: number}>=} limits
 */
export function createTransclusionBudget(limits = {}) {
  if (!limits || typeof limits !== "object") {
    throw new TypeError("Transclusion limits must be an object");
  }
  const budget = Object.freeze({
    deadline:
      Date.now() +
      boundedLimit(
        limits.maxDurationMs,
        DEFAULT_MAX_TRANSCLUSION_DURATION_MS,
        HARD_MAX_TRANSCLUSION_DURATION_MS,
      ),
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
 * Reserve one document and extend its immutable ancestry chain.
 *
 * @param {ReturnType<typeof createTransclusionBudget>} budget
 * @param {string} key
 * @param {ReadonlyArray<string>} chain
 */
export function claimTransclusion(budget, key, chain) {
  validateBudget(budget);
  if (typeof key !== "string" || !key || !Array.isArray(chain)) {
    throw new TypeError("Transclusion claim requires a key and ancestry chain");
  }
  if (Date.now() >= budget.deadline) {
    throw new TransclusionError("timed-out");
  }
  if (chain.includes(key)) {
    throw new TransclusionError("cycle");
  }
  if (chain.length >= budget.limits.maxDepth) {
    throw new TransclusionError("depth-limit");
  }
  if (budget.state.documents >= budget.limits.maxDocuments) {
    throw new TransclusionError("document-limit");
  }
  budget.state.documents += 1;
  return Object.freeze({ chain: Object.freeze([...chain, key]) });
}

/**
 * Select a whole note, heading section, or named block from Markdown source.
 *
 * @param {string} source
 * @param {string=} fragment
 */
export function selectTransclusionSource(source, fragment) {
  if (typeof source !== "string") {
    throw new TypeError("Transclusion selection requires source text");
  }
  if (source.length > MAX_SELECTED_SOURCE_CHARACTERS) {
    return selectionFailure("source-too-large");
  }
  if (!fragment) {
    return selected(source, "note");
  }
  if (fragment.startsWith("obsidian-block-")) {
    return selectNamedBlock(source, fragment.slice("obsidian-block-".length));
  }
  if (fragment.startsWith("obsidian-heading-")) {
    return selectHeadingSection(source, fragment.slice("obsidian-heading-".length));
  }
  return selectionFailure("unsupported-location");
}

/**
 * Replace one resolved note embed with a bounded, safely rendered document region.
 *
 * @param {HTMLElement} container
 * @param {Element} sourceElement
 * @param {Readonly<{path: string, fragment?: string}>} resolved
 * @param {MetabrowserPublicSdk} mb
 * @param {{budget?: ReturnType<typeof createTransclusionBudget>, chain?: ReadonlyArray<string>, signal?: AbortSignal, enhanceNested?: (container: HTMLElement, sourcePath: string, options: {budget: ReturnType<typeof createTransclusionBudget>, chain: ReadonlyArray<string>, signal: AbortSignal}) => {dispose?: () => void}}=} options
 */
export function mountWikiTransclusion(container, sourceElement, resolved, mb, options = {}) {
  const document = container.ownerDocument || globalThis.document;
  if (!document) {
    throw new Error("Wiki transclusion requires a document");
  }
  const aside = document.createElement("aside");
  const label = sourceElement.textContent || resolved.path;
  aside.setAttribute("class", "metabrowser-wiki-transclusion");
  aside.setAttribute("role", "region");
  aside.setAttribute("aria-label", `Embedded note: ${label}`);
  aside.setAttribute("aria-busy", "true");
  aside.setAttribute("data-metabrowser-transclusion-status", "loading");
  aside.textContent = `Loading embedded note: ${label}…`;
  sourceElement.replaceWith(aside);

  const budget = options.budget || createTransclusionBudget();
  const chain = options.chain || Object.freeze([]);
  const controller = new AbortController();
  let disposed = false;
  let timedOut = false;
  let timeoutHandle = 0;
  /** @type {{dispose?: () => void} | null} */
  let nestedHandle = null;
  /** @type {(() => void) | null} */
  let disposeToc = null;
  const abortParent = () => dispose();
  if (options.signal?.aborted) {
    disposed = true;
    controller.abort(options.signal.reason);
  } else {
    options.signal?.addEventListener("abort", abortParent, { once: true });
  }

  function dispose() {
    if (disposed) {
      return;
    }
    disposed = true;
    options.signal?.removeEventListener("abort", abortParent);
    if (timeoutHandle) {
      clearTimeout(timeoutHandle);
      timeoutHandle = 0;
    }
    controller.abort();
    nestedHandle?.dispose?.();
    nestedHandle = null;
    disposeToc?.();
    disposeToc = null;
  }

  async function render() {
    try {
      const key = `${resolved.path}#${resolved.fragment || ""}`;
      const claim = claimTransclusion(budget, key, chain);
      const remainingTime = budget.deadline - Date.now();
      if (remainingTime <= 0) {
        throw new TransclusionError("timed-out");
      }
      timeoutHandle = setTimeout(() => {
        timedOut = true;
        controller.abort();
      }, remainingTime);
      const source = await mb.fetchText(Object.freeze({ path: resolved.path }), {
        signal: controller.signal,
      });
      consumeSourceBytes(budget, source);
      const selection = selectTransclusionSource(source, resolved.fragment);
      if (selection.status !== "selected") {
        throw new TransclusionError(selection.reason);
      }
      const wiki = preprocessObsidianWiki(selection.source);
      const rendered = await mb.fetchKpressRender(
        {
          path: resolved.path,
          raw: { content: selection.source, content_truncated: false, type: "text" },
        },
        "rendered",
        {
          dedupKey: `markdown-transclusion-${++transclusionSequence}`,
          profile: "document",
          signal: controller.signal,
          sourceText: wiki.source,
        },
      );
      if (disposed || controller.signal.aborted) {
        return;
      }
      aside.innerHTML = rendered.html;
      aside.setAttribute("aria-busy", "false");
      aside.setAttribute("data-metabrowser-transclusion-status", "ready");
      nestedHandle =
        options.enhanceNested?.(aside, resolved.path, {
          budget,
          chain: claim.chain,
          signal: controller.signal,
        }) || null;
      disposeToc = mb.kpressInitToc?.(aside) || null;
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
      if (timeoutHandle) {
        clearTimeout(timeoutHandle);
        timeoutHandle = 0;
      }
    }
  }

  if (!disposed) {
    void render();
  }
  return Object.freeze({ dispose });
}

/** @param {string} source @param {string} target */
function selectHeadingSection(source, target) {
  if (!target) {
    return selectionFailure("missing-location");
  }
  const lines = sourceLines(source);
  const headingStack = [];
  let fence = null;
  let selectedStart = -1;
  let selectedLevel = 0;
  for (let index = 0; index < lines.length; index += 1) {
    const line = lineText(lines[index]);
    const fenceRun = /^ {0,3}(`{3,}|~{3,})/.exec(line)?.[1] || null;
    if (fence) {
      if (
        fenceRun &&
        fenceRun[0] === fence.character &&
        fenceRun.length >= fence.length &&
        line.slice(line.indexOf(fenceRun) + fenceRun.length).trim() === ""
      ) {
        fence = null;
      }
      continue;
    }
    if (fenceRun) {
      fence = { character: fenceRun[0], length: fenceRun.length };
      continue;
    }
    const block = findNamedBlock(line);
    const content = block ? line.slice(0, block.start).trimEnd() : line;
    const nextLine = index + 1 < lines.length ? lineText(lines[index + 1]) : "";
    const heading = findMarkdownHeading(content, nextLine);
    if (!heading) {
      continue;
    }
    if (selectedStart !== -1 && heading.level <= selectedLevel) {
      return selected(lines.slice(selectedStart, index).join(""), "heading");
    }
    headingStack.splice(heading.level - 1);
    headingStack[heading.level - 1] = heading.text;
    const hierarchy = headingStack.filter(Boolean);
    const matches = hierarchy.some(
      (_heading, offset) => hierarchy.slice(offset).join("#") === target,
    );
    if (selectedStart === -1 && matches) {
      selectedStart = index;
      selectedLevel = heading.level;
    }
  }
  return selectedStart === -1
    ? selectionFailure("missing-location")
    : selected(lines.slice(selectedStart).join(""), "heading");
}

/** @param {string} source @param {string} target */
function selectNamedBlock(source, target) {
  if (!/^[A-Za-z0-9-]+$/.test(target)) {
    return selectionFailure("missing-location");
  }
  const lines = sourceLines(source);
  let fence = null;
  let blockStart = 0;
  for (let index = 0; index < lines.length; index += 1) {
    const line = lineText(lines[index]);
    const fenceRun = /^ {0,3}(`{3,}|~{3,})/.exec(line)?.[1] || null;
    if (fence) {
      if (
        fenceRun &&
        fenceRun[0] === fence.character &&
        fenceRun.length >= fence.length &&
        line.slice(line.indexOf(fenceRun) + fenceRun.length).trim() === ""
      ) {
        fence = null;
        blockStart = index + 1;
      }
      continue;
    }
    if (fenceRun) {
      fence = { character: fenceRun[0], length: fenceRun.length };
      blockStart = index + 1;
      continue;
    }
    if (!line.trim()) {
      blockStart = index + 1;
      continue;
    }
    const block = findNamedBlock(line);
    if (!block || block.id !== target) {
      const nextLine = index + 1 < lines.length ? lineText(lines[index + 1]) : "";
      if (findMarkdownHeading(line, nextLine) || /^ {0,3}(?:=+|-+)[\t ]*$/.test(line)) {
        blockStart = index + 1;
      }
      continue;
    }
    const selectedLines = lines.slice(blockStart, index + 1);
    selectedLines[selectedLines.length - 1] = `${line.slice(0, block.start).trimEnd()}${lineEnding(
      lines[index],
    )}`;
    return selected(selectedLines.join(""), "block");
  }
  return selectionFailure("missing-location");
}

/** @param {ReturnType<typeof createTransclusionBudget>} budget @param {string} source */
function consumeSourceBytes(budget, source) {
  const bytes = new TextEncoder().encode(source).byteLength;
  if (budget.state.sourceBytes + bytes > budget.limits.maxSourceBytes) {
    throw new TransclusionError("source-byte-limit");
  }
  budget.state.sourceBytes += bytes;
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

/** @param {string} source */
function sourceLines(source) {
  return source.match(/.*(?:\r\n|\n|\r|$)/g)?.filter(Boolean) || [];
}

/** @param {string} line */
function lineText(line) {
  const ending = lineEnding(line);
  return ending ? line.slice(0, -ending.length) : line;
}

/** @param {string} line */
function lineEnding(line) {
  return /\r\n$|[\n\r]$/.exec(line)?.[0] || "";
}

/** @param {string} source @param {"note" | "heading" | "block"} kind */
function selected(source, kind) {
  return Object.freeze({ kind, source, status: /** @type {const} */ ("selected") });
}

/** @param {string} reason */
function selectionFailure(reason) {
  return Object.freeze({ reason, status: /** @type {const} */ ("missing") });
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
    "unsupported-location": "The requested embedded location is unsupported.",
  };
  return labels[code] || "The embedded note could not be rendered.";
}

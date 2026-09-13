import { matchingDescendants } from "./dom-traversal.js";
import { createMarkdownWorkerClient } from "./markdown-worker-client.js";
import {
  createMarkdownEnhancementBudget,
  createMarkdownReconciliationCoordinator,
} from "./reconciliation-coordinator.js";
import { createTransclusionBudget, mountWikiTransclusion } from "./transclusion.js";

const MAX_WIKI_ELEMENTS = 4096;
const MAX_ANNOUNCED_CANDIDATES = 20;
const MAX_ANNOUNCED_CANDIDATE_CODE_UNITS = 512;
const MAX_ANNOUNCEMENT_CODE_UNITS = 2048;
const WIKI_RESOLUTION_IDENTITY = Symbol.for("metabrowser.wiki-resolution-identity");

/**
 * Resolve source-derived wiki placeholders after KPress has produced safe DOM.
 *
 * @param {HTMLElement} container
 * @param {string} sourcePath
 * @param {MetabrowserPublicSdk} mb
 * @param {(element: Element, target: Readonly<{path: string, fragment?: string}>) => void} registerInternal
 * @param {{budget?: ReturnType<typeof createTransclusionBudget>, cancel?: (handle: number) => void, chain?: ReadonlyArray<ReturnType<typeof import("./transclusion.js").transclusionKey>>, elements?: ReadonlyArray<Element>, enhancementBudget?: ReturnType<typeof createMarkdownEnhancementBudget>, signal?: AbortSignal, schedule?: (callback: FrameRequestCallback) => number, reconciliation?: ReturnType<typeof createMarkdownReconciliationCoordinator>, reconciliationScope?: ReturnType<ReturnType<typeof createMarkdownReconciliationCoordinator>["createScope"]>, enhanceNested?: (container: HTMLElement, sourcePath: string, options: {budget: ReturnType<typeof createTransclusionBudget>, chain: ReadonlyArray<ReturnType<typeof import("./transclusion.js").transclusionKey>>, signal: AbortSignal}) => {dispose?: () => void}, workerClient?: ReturnType<typeof createMarkdownWorkerClient>}=} options
 */
export function enhanceWikiLinks(container, sourcePath, mb, registerInternal, options = {}) {
  const transclusions = new Set();
  const ownsWorkerClient = !options.workerClient;
  const workerClient = options.workerClient || createMarkdownWorkerClient();
  let budget = options.budget || null;
  const enhancementBudget = options.enhancementBudget || createMarkdownEnhancementBudget();
  let disposed = false;
  const ownsReconciliation = !options.reconciliation;
  const reconciliation =
    options.reconciliation ||
    createMarkdownReconciliationCoordinator(mb, {
      cancel: options.cancel,
      schedule: options.schedule,
    });
  const ownsScope = !options.reconciliationScope;
  const scope =
    options.reconciliationScope || reconciliation.createScope(options.signal, sourcePath);

  /**
   * @param {{element: Element, transclusion: ReturnType<typeof mountWikiTransclusion> | null}} state
   * @param {Element} template
   * @param {"navigate" | "embed"} action
   * @param {NonNullable<ReturnType<ReturnType<ReturnType<typeof import("./wiki-resolver.js").createWikiResolutionContext>["begin"]>["step"]>["result"]>} resolved
   */
  function enhanceElement(state, template, action, resolved) {
    if (disposed) {
      return state;
    }
    if (state.transclusion) {
      state.transclusion.dispose();
      transclusions.delete(state.transclusion);
      state.transclusion = null;
    }
    if (resolved.status !== "internal") {
      let unresolved = state.element;
      if (unresolved.tagName.toLowerCase() !== template.tagName.toLowerCase()) {
        unresolved = createWikiPlaceholder(container, template);
        state.element.replaceWith(unresolved);
      }
      describeUnresolved(unresolved, resolved);
      state.element = unresolved;
      return state;
    }
    if (action === "embed" && resolved.mediaKind === "markdown") {
      let placeholder = state.element;
      if (placeholder !== template) {
        placeholder = createWikiPlaceholder(container, template);
        state.element.replaceWith(placeholder);
      }
      budget ||= createTransclusionBudget();
      const transclusion = mountWikiTransclusion(container, placeholder, resolved, mb, {
        budget,
        chain: options.chain,
        enhanceNested: options.enhanceNested,
        signal: options.signal,
        workerClient,
      });
      transclusions.add(transclusion);
      state.element = transclusion.element;
      state.transclusion = transclusion;
      return state;
    }
    const replacement =
      action === "embed"
        ? createMediaElement(container, template, resolved)
        : createNavigationAnchor(container, template, resolved, mb);
    state.element.replaceWith(replacement);
    state.element = replacement;
    if (action === "navigate") {
      registerInternal(replacement, navigationTarget(resolved));
    }
    return state;
  }

  const elements =
    options.elements ||
    admittedElements(
      matchingDescendants(container, "[data-mb-wiki-target]", MAX_WIKI_ELEMENTS),
      enhancementBudget,
    );
  for (const element of elements) {
    const authoredTarget = element.getAttribute("data-mb-wiki-target");
    const action = element.getAttribute("data-mb-wiki-action");
    if (authoredTarget === null || (action !== "navigate" && action !== "embed")) {
      continue;
    }
    /** @type {Parameters<typeof sameResolution>[0]} */
    let previousResolution = null;
    /** @type {{element: Element, transclusion: ReturnType<typeof mountWikiTransclusion> | null}} */
    const state = { element, transclusion: null };
    scope.wiki({ action, authoredTarget, sourcePath }, (resolved) => {
      if (sameResolution(previousResolution, resolved)) {
        return;
      }
      enhanceElement(state, element, action, resolved);
      previousResolution = resolved;
    });
  }

  return Object.freeze({
    dispose() {
      if (disposed) {
        return;
      }
      disposed = true;
      if (ownsScope) {
        scope.dispose();
      }
      for (const transclusion of transclusions) {
        transclusion.dispose();
      }
      transclusions.clear();
      if (ownsReconciliation) {
        reconciliation.dispose();
      }
      if (ownsWorkerClient) {
        workerClient.dispose();
      }
    },
  });
}

/**
 * Recreate the inert source placeholder when a later catalog revision changes a
 * previously mounted result. Only authored presentation metadata is copied; stale
 * navigation, media, status, and accessibility state belong to the old result.
 *
 * @param {HTMLElement} container
 * @param {Element} template
 */
function createWikiPlaceholder(container, template) {
  const placeholder = ownerDocument(container).createElement(template.tagName.toLowerCase());
  copyPresentation(template, placeholder);
  for (const attribute of [
    "data-mb-wiki-action",
    "data-mb-wiki-height",
    "data-mb-wiki-label",
    "data-mb-wiki-target",
    "data-mb-wiki-width",
  ]) {
    const value = template.getAttribute(attribute);
    if (value !== null) {
      placeholder.setAttribute(attribute, value);
    }
  }
  return placeholder;
}

/** @param {HTMLElement} container @param {Element} source @param {{path: string, fragment?: string}} resolved @param {MetabrowserPublicSdk} mb */
function createNavigationAnchor(container, source, resolved, mb) {
  const anchor = ownerDocument(container).createElement("a");
  copyPresentation(source, anchor);
  anchor.setAttribute("href", mb.navigation.href(navigationTarget(resolved)));
  anchor.setAttribute("data-metabrowser-link-syntax", "wiki");
  return anchor;
}

/** @param {HTMLElement} container @param {Element} source @param {{path: string, fragment?: string, mediaKind?: "markdown" | "image" | "audio" | "video" | "resource"}} resolved */
function createMediaElement(container, source, resolved) {
  const document = ownerDocument(container);
  const kind =
    !resolved.mediaKind || resolved.mediaKind === "markdown" ? "resource" : resolved.mediaKind;
  const resource = document.createElement(
    kind === "resource" ? "a" : kind === "image" ? "img" : kind,
  );
  copyPresentation(source, resource);
  const href = rawResourceHref(resolved);
  if (kind === "resource") {
    resource.setAttribute("href", href);
  } else {
    resource.setAttribute("src", href);
    if (kind === "image") {
      resource.setAttribute("alt", labelFor(source));
    } else {
      resource.setAttribute("controls", "");
      resource.setAttribute("aria-label", labelFor(source));
    }
  }
  for (const dimension of ["width", "height"]) {
    const value = source.getAttribute(`data-mb-wiki-${dimension}`);
    if (value) {
      resource.setAttribute(dimension, value);
    }
  }
  resource.setAttribute("data-metabrowser-link-syntax", "wiki-embed");
  return resource;
}

/** @param {Element} element @param {{status: string, reason: string, candidateCount?: number, candidates?: ReadonlyArray<string>}} resolved */
function describeUnresolved(element, resolved) {
  const label = labelFor(element);
  element.setAttribute("data-mb-wiki-label", label);
  element.setAttribute("data-metabrowser-link-status", resolved.status);
  element.setAttribute("aria-disabled", "true");
  element.setAttribute(
    "role",
    element.getAttribute("data-mb-wiki-action") === "navigate" ? "link" : "status",
  );
  if (!element.hasAttribute("tabindex")) {
    element.setAttribute("tabindex", "0");
  }
  const suffix = statusLabel(resolved.status);
  const candidates = resolved.candidates || [];
  const announced = boundedCandidateAnnouncement(candidates);
  const remainder = Math.max(0, (resolved.candidateCount ?? candidates.length) - announced.length);
  const candidateDetail = announced.length
    ? ` Candidates: ${announced.join(", ")}${remainder ? `, and ${remainder} more` : ""}.`
    : "";
  const explanation = `${suffix} (${resolved.reason}).${candidateDetail}`;
  element.setAttribute("title", explanation);
  element.setAttribute("aria-label", `${label}. ${explanation}`);
  element.textContent = `${label} (${suffix.toLowerCase()})`;
}

/**
 * Compare only bounded semantic identity. Exact results for one retained intent
 * are stable across incomplete catalog revisions; a fallback result is only
 * published from the pinned complete revision. The resolver's non-enumerable
 * metadata lets this decision avoid copying or comparing a provider-sized path.
 *
 * @param {{status: string, reason?: string, candidateCount?: number} | null} previous
 * @param {{status: string, reason?: string, candidateCount?: number}} next
 */
function sameResolution(previous, next) {
  if (!previous || previous.status !== next.status) {
    return false;
  }
  if (next.status !== "internal") {
    return (
      next.status !== "ambiguous" &&
      previous.reason === next.reason &&
      previous.candidateCount === next.candidateCount
    );
  }
  const previousIdentity = resolutionIdentity(previous);
  const nextIdentity = resolutionIdentity(next);
  return (
    previousIdentity?.kind === "exact" &&
    nextIdentity?.kind === "exact" &&
    previousIdentity.sourceContext === nextIdentity.sourceContext &&
    previousIdentity.authoredTarget === nextIdentity.authoredTarget
  );
}

/** @param {object} resolution */
function resolutionIdentity(resolution) {
  const value = /** @type {Record<PropertyKey, unknown>} */ (resolution)[WIKI_RESOLUTION_IDENTITY];
  return value && typeof value === "object"
    ? /** @type {{authoredTarget?: unknown, kind?: unknown, sourceContext?: unknown}} */ (value)
    : null;
}

/** @param {ReadonlyArray<string>} candidates */
function boundedCandidateAnnouncement(candidates) {
  const announced = [];
  let remaining = MAX_ANNOUNCEMENT_CODE_UNITS;
  for (const candidate of candidates.slice(0, MAX_ANNOUNCED_CANDIDATES)) {
    if (remaining < 2) {
      break;
    }
    const allowance = Math.min(MAX_ANNOUNCED_CANDIDATE_CODE_UNITS, remaining);
    const label =
      candidate.length <= allowance
        ? candidate
        : `${candidate.slice(0, Math.max(allowance - 1, 0))}…`;
    announced.push(label);
    remaining -= label.length + 2;
  }
  return announced;
}

/** @param {string} status */
function statusLabel(status) {
  if (status === "pending") {
    return "Resolving link";
  }
  if (status === "ambiguous") {
    return "Ambiguous link";
  }
  if (status === "missing") {
    return "Missing link";
  }
  if (status === "unsafe") {
    return "Blocked link";
  }
  return "Unsupported link";
}

/** @param {Element} source @param {Element} target */
function copyPresentation(source, target) {
  const className = source.getAttribute("class");
  if (className) {
    target.setAttribute("class", className);
  }
  target.textContent = labelFor(source);
}

/** @param {Element} element */
function labelFor(element) {
  return (
    element.getAttribute("data-mb-wiki-label") ||
    element.textContent ||
    element.getAttribute("data-mb-wiki-target") ||
    "Wiki link"
  );
}

/** @param {HTMLElement} container */
function ownerDocument(container) {
  const document = container.ownerDocument || globalThis.document;
  if (!document) {
    throw new Error("Wiki enhancement requires a document");
  }
  return document;
}

/**
 * Standalone wiki enhancement retains its historical 4,096 ceiling; composed
 * rendering receives the root-shared budget and therefore cannot multiply it.
 *
 * @param {Iterable<Element>} elements
 * @param {ReturnType<typeof createMarkdownEnhancementBudget>} budget
 */
function* admittedElements(elements, budget) {
  let count = 0;
  for (const element of elements) {
    if (count >= MAX_WIKI_ELEMENTS || !budget.claim()) {
      return;
    }
    count += 1;
    yield element;
  }
}

/** @param {{path: string, fragment?: string}} resolved */
function navigationTarget(resolved) {
  return Object.freeze(
    resolved.fragment
      ? { path: resolved.path, fragment: resolved.fragment }
      : { path: resolved.path },
  );
}

/** @param {{path: string, fragment?: string}} resolved */
function rawResourceHref(resolved) {
  const fragment = resolved.fragment ? `#${encodeURIComponent(resolved.fragment)}` : "";
  return `/raw?path=${encodeURIComponent(resolved.path)}${fragment}`;
}

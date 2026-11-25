import { matchingDescendants } from "./dom-traversal.js";
import { acquireMarkdownWorkerClient } from "./markdown-worker-client.js";
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
 * Draw a PDF the document embeds in place of *template*, for the PDF named *target*, and
 * return the element that takes its place with the handle that disposes what it drew.
 *
 * @typedef {(template: Element, target: Readonly<{path: string}>, name: string) => {element: Element, dispose: () => void}} EmbedPdf
 */
/**
 * @typedef {{element: Element, transclusion: ReturnType<typeof mountWikiTransclusion> | null, pdf: {dispose: () => void} | null}} WikiElementState
 */

/**
 * Resolve source-derived wiki placeholders after KPress has produced safe DOM.
 *
 * @param {HTMLElement} container
 * @param {string} sourcePath
 * @param {MetabrowserPublicSdk} mb
 * @param {(element: Element, target: Readonly<{path: string, fragment?: string}>) => void} registerInternal
 * @param {{budget?: ReturnType<typeof createTransclusionBudget>, cancel?: (handle: number) => void, chain?: ReadonlyArray<ReturnType<typeof import("./transclusion.js").transclusionKey>>, elements?: ReadonlyArray<Element>, enhancementBudget?: ReturnType<typeof createMarkdownEnhancementBudget>, signal?: AbortSignal, schedule?: (callback: FrameRequestCallback) => number, reconciliation?: ReturnType<typeof createMarkdownReconciliationCoordinator>, reconciliationScope?: ReturnType<ReturnType<typeof createMarkdownReconciliationCoordinator>["createScope"]>, enhanceNested?: (container: HTMLElement, sourcePath: string, options: {budget: ReturnType<typeof createTransclusionBudget>, chain: ReadonlyArray<ReturnType<typeof import("./transclusion.js").transclusionKey>>, signal: AbortSignal, rawVersions?: unknown}) => {dispose?: () => void}, embedPdf?: EmbedPdf, workerClient?: import("./markdown-worker-client.js").MarkdownWorkerRunner}=} options
 *   `embedPdf` draws `![[report.pdf]]` as the pdf plugin's card (link-enhancer.js
 *   `mountPdfEmbed`); without it such an embed is a link to the PDF's view.
 */
export function enhanceWikiLinks(container, sourcePath, mb, registerInternal, options = {}) {
  const transclusions = new Set();
  /** @type {Set<{dispose: () => void}>} */
  const pdfEmbeds = new Set();
  const ownsWorkerClient = !options.workerClient;
  const workerClient = options.workerClient || acquireMarkdownWorkerClient();
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
   * @param {WikiElementState} state
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
    // A card's slot is a span like the placeholder, so it is never reused for another result.
    const hadPdf = state.pdf !== null;
    if (state.pdf) {
      state.pdf.dispose();
      pdfEmbeds.delete(state.pdf);
      state.pdf = null;
    }
    if (resolved.status !== "internal") {
      let unresolved = state.element;
      if (hadPdf || unresolved.tagName.toLowerCase() !== template.tagName.toLowerCase()) {
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
    if (action === "embed" && resolved.mediaKind === "pdf") {
      const target = Object.freeze({ path: resolved.path });
      if (!options.embedPdf) {
        // No card to draw: the embed is a link to the PDF's view, never to `/raw`.
        const anchor = createNavigationAnchor(container, template, target, mb);
        anchor.setAttribute("data-metabrowser-link-syntax", "wiki-embed");
        state.element.replaceWith(anchor);
        state.element = anchor;
        registerInternal(anchor, target);
        return state;
      }
      const embed = options.embedPdf(template, target, wikiFileName(template));
      embed.element.setAttribute("data-metabrowser-link-syntax", "wiki-embed");
      pdfEmbeds.add(embed);
      state.element.replaceWith(embed.element);
      state.element = embed.element;
      state.pdf = embed;
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
    /** @type {WikiElementState} */
    const state = { element, transclusion: null, pdf: null };
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
      for (const embed of pdfEmbeds) {
        embed.dispose();
      }
      pdfEmbeds.clear();
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

/**
 * An embedded image, audio, or video at its `/raw` address, or a link there for any other
 * file. A PDF never reaches here: `enhanceElement` draws its card, or links to its view.
 *
 * @param {HTMLElement} container @param {Element} source @param {{path: string, fragment?: string, mediaKind?: "markdown" | "image" | "audio" | "video" | "pdf" | "resource"}} resolved
 */
function createMediaElement(container, source, resolved) {
  const document = ownerDocument(container);
  const kind =
    !resolved.mediaKind || resolved.mediaKind === "markdown" || resolved.mediaKind === "pdf"
      ? "resource"
      : resolved.mediaKind;
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

/**
 * The file's name in a wiki embed, as the author wrote it: the target's last segment,
 * without its heading or block fragment.
 *
 * @param {Element} element
 */
function wikiFileName(element) {
  const authored = (element.getAttribute("data-mb-wiki-target") || "").split("#", 1)[0];
  const trimmed = authored.endsWith("/") ? authored.slice(0, -1) : authored;
  return trimmed.slice(trimmed.lastIndexOf("/") + 1) || labelFor(element);
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

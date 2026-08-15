import { createTransclusionBudget, mountWikiTransclusion } from "./transclusion.js";
import { resolveWikiTarget } from "./wiki_resolver.js";

const MAX_WIKI_ELEMENTS = 4096;
const MAX_ANNOUNCED_CANDIDATES = 20;

/**
 * Resolve source-derived wiki placeholders after KPress has produced safe DOM.
 *
 * @param {HTMLElement} container
 * @param {string} sourcePath
 * @param {MetabrowserPublicSdk} mb
 * @param {(element: Element, target: Readonly<{path: string, fragment?: string}>) => void} registerInternal
 * @param {{budget?: ReturnType<typeof createTransclusionBudget>, chain?: ReadonlyArray<string>, signal?: AbortSignal, enhanceNested?: (container: HTMLElement, sourcePath: string, options: {budget: ReturnType<typeof createTransclusionBudget>, chain: ReadonlyArray<string>, signal: AbortSignal}) => {dispose?: () => void}}=} options
 */
export function enhanceWikiLinks(container, sourcePath, mb, registerInternal, options = {}) {
  const pending = new Set(boundedElements(container.querySelectorAll("[data-mb-wiki-target]")));
  const transclusions = new Set();
  let budget = options.budget || null;
  let disposed = false;
  /** @type {(() => void) | null} */
  let unsubscribe = null;

  function enhancePending() {
    if (disposed) {
      return;
    }
    const snapshot = mb.fileCatalog.snapshot();
    for (const element of [...pending]) {
      const authoredTarget = element.getAttribute("data-mb-wiki-target");
      const action = element.getAttribute("data-mb-wiki-action");
      if (authoredTarget === null || (action !== "navigate" && action !== "embed")) {
        pending.delete(element);
        continue;
      }
      const resolved = resolveWikiTarget({ action, authoredTarget, sourcePath }, snapshot);
      if (resolved.status === "pending") {
        describeUnresolved(element, resolved);
        continue;
      }
      pending.delete(element);
      if (resolved.status === "internal") {
        if (action === "embed" && resolved.mediaKind === "markdown") {
          budget ||= createTransclusionBudget();
          transclusions.add(
            mountWikiTransclusion(container, element, resolved, mb, {
              budget,
              chain: options.chain,
              enhanceNested: options.enhanceNested,
              signal: options.signal,
            }),
          );
        } else {
          const replacement =
            action === "embed"
              ? createMediaElement(container, element, resolved)
              : createNavigationAnchor(container, element, resolved, mb);
          element.replaceWith(replacement);
          if (action === "navigate") {
            registerInternal(replacement, navigationTarget(resolved));
          }
        }
      } else {
        describeUnresolved(element, resolved);
      }
    }
    if (pending.size === 0 && unsubscribe) {
      unsubscribe();
      unsubscribe = null;
    }
  }

  if (pending.size > 0) {
    unsubscribe = mb.fileCatalog.subscribe(enhancePending);
    enhancePending();
  }

  return Object.freeze({
    dispose() {
      if (disposed) {
        return;
      }
      disposed = true;
      pending.clear();
      for (const transclusion of transclusions) {
        transclusion.dispose();
      }
      transclusions.clear();
      unsubscribe?.();
      unsubscribe = null;
    },
  });
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

/** @param {Element} element @param {{status: string, reason: string, candidates?: ReadonlyArray<string>}} resolved */
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
  const announced = candidates.slice(0, MAX_ANNOUNCED_CANDIDATES);
  const remainder = candidates.length - announced.length;
  const candidateDetail = announced.length
    ? ` Candidates: ${announced.join(", ")}${remainder ? `, and ${remainder} more` : ""}.`
    : "";
  const explanation = `${suffix} (${resolved.reason}).${candidateDetail}`;
  element.setAttribute("title", explanation);
  element.setAttribute("aria-label", `${label}. ${explanation}`);
  element.textContent = `${label} (${suffix.toLowerCase()})`;
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

/** @param {NodeListOf<Element>} elements */
function boundedElements(elements) {
  return Array.from(elements).slice(0, MAX_WIKI_ELEMENTS);
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

import { findElementById, MAX_ENHANCED_TARGETS, matchingDescendants } from "./dom-traversal.js";
import { localizeGithubUrl } from "./github-localizer.js";
import { createTrustedStandardLinkResolutionContext, gitPathWireForDisplayPath } from "./links.js";
import { acquireMarkdownWorkerClient } from "./markdown-worker-client.js";
import {
  createMarkdownEnhancementBudget,
  createMarkdownReconciliationCoordinator,
} from "./reconciliation-coordinator.js";
import { enhanceWikiLinks } from "./wiki-enhancer.js";

const ENHANCEABLE_TARGET_SELECTOR =
  "a[href],img[src],audio[src],video[src],source[src],object[data],[data-mb-wiki-target]";
const RESOURCE_ATTRIBUTES = Object.freeze([
  Object.freeze({ selector: "img[src]", attribute: "src" }),
  Object.freeze({ selector: "audio[src]", attribute: "src" }),
  Object.freeze({ selector: "video[src]", attribute: "src" }),
  Object.freeze({ selector: "source[src]", attribute: "src" }),
  Object.freeze({ selector: "object[data]", attribute: "data" }),
]);

/** @typedef {Readonly<{path: string, query?: string, fragment?: string}>} NavigationTarget */

/**
 * Enhance the safe HTML emitted by KPress with Metabrowser navigation semantics.
 *
 * @param {HTMLElement} container
 * @param {string} sourcePath
 * @param {MetabrowserPublicSdk} mb
 * @param {{eventTarget?: Pick<Window, "addEventListener" | "removeEventListener">, schedule?: (callback: FrameRequestCallback) => number, cancel?: (handle: number) => void, signal?: AbortSignal, enhancementBudget?: ReturnType<typeof createMarkdownEnhancementBudget>, reconciliation?: ReturnType<typeof createMarkdownReconciliationCoordinator>, transclusionBudget?: ReturnType<typeof import("./transclusion.js").createTransclusionBudget>, transclusionChain?: ReadonlyArray<ReturnType<typeof import("./transclusion.js").transclusionKey>>, workerClient?: import("./markdown-worker-client.js").MarkdownWorkerRunner}=} options
 */
export function enhanceRenderedLinks(container, sourcePath, mb, options = {}) {
  const eventTarget = options.eventTarget ?? window;
  const schedule = options.schedule ?? requestAnimationFrame;
  const cancel = options.cancel ?? cancelAnimationFrame;
  const enhancementBudget = options.enhancementBudget || createMarkdownEnhancementBudget();
  const ownsWorkerClient = !options.workerClient;
  const workerClient = options.workerClient || acquireMarkdownWorkerClient();
  const sourceKind = mb.sourceKind?.() === "git_revision" ? "git_revision" : "filesystem";
  const standardLinks = createTrustedStandardLinkResolutionContext(
    sourcePath,
    undefined,
    sourceKind,
  );
  const preserveFragmentOnlyHrefs = isCurrentDocument(sourcePath, mb.navigation.current());
  /** @type {WeakMap<Element, NavigationTarget>} */
  const internalTargets = new WeakMap();
  const ownsReconciliation = !options.reconciliation;
  const reconciliation =
    options.reconciliation ||
    createMarkdownReconciliationCoordinator(
      mb,
      options.schedule ? { cancel, schedule } : undefined,
    );
  const reconciliationScope = reconciliation.createScope(options.signal, sourcePath);
  const admission = admittedTargetElements(container, enhancementBudget);
  const admittedTargets = admission.elements;
  let disposed = false;
  let fragmentFrame = 0;

  /** @param {unknown} intent @param {(resolved: ReturnType<typeof standardLinks.resolve>) => void} commit */
  function resolveStandard(intent, commit) {
    if (standardLinks.canResolveSynchronously) {
      commit(standardLinks.resolve(intent));
      return;
    }
    reconciliationScope.standard(intent, commit);
  }

  for (const anchor of admittedTargets) {
    if (
      anchor.hasAttribute("data-mb-wiki-target") ||
      anchor.tagName.toLowerCase() !== "a" ||
      !anchor.hasAttribute("href")
    ) {
      continue;
    }
    const authoredTarget = anchor.getAttribute("href");
    if (authoredTarget === null) {
      continue;
    }
    resolveStandard(
      {
        action: "navigate",
        authoredTarget,
        sourcePath,
        syntax: "html",
      },
      (resolved) => {
        if (resolved.status === "internal") {
          if (isPossiblePublishedRoute(authoredTarget)) {
            // A configured static-site route can map somewhere other than the
            // repository-relative path. Keep it inert until the pinned catalog
            // pass decides; otherwise a click before the first continuation can
            // navigate to a transient, incorrect target.
            internalTargets.delete(anchor);
            disableTarget(anchor, "href", "pending", "published-route-pending");
            reconciliationScope.published(
              { authoredTarget, resolvedPath: resolved.path },
              (adapted) => applyInternalAnchor(anchor, authoredTarget, resolved, adapted),
            );
          } else {
            applyInternalAnchor(anchor, authoredTarget, resolved, null);
          }
        } else if (resolved.status === "external") {
          const localized = localizeGithubUrl(authoredTarget, mb.repository);
          if (localized) {
            // A pin addresses its tree by GitPath wire, as every internal link on it does.
            const target = navigationTarget(
              sourceKind === "git_revision"
                ? { ...localized, path: gitPathWireForDisplayPath(localized.path) }
                : localized,
            );
            anchor.setAttribute("href", mb.navigation.href(target));
            anchor.setAttribute("data-metabrowser-github-localization", localized.localization);
            if (localized.localization === "working-tree" && !anchor.hasAttribute("title")) {
              anchor.setAttribute(
                "title",
                "Open the corresponding path in the currently served working tree.",
              );
            }
            internalTargets.set(anchor, target);
          }
        } else {
          disableTarget(anchor, "href", resolved.status, resolved.reason);
        }
      },
    );
  }

  /**
   * @param {Element} anchor
   * @param {string} authoredTarget
   * @param {{status: "internal", path: string, query?: string, fragment?: string}} resolved
   * @param {ReturnType<ReturnType<typeof import("./project-adapters.js").createPublishedRouteResolutionContext>["resolve"]>} adapted
   */
  function applyInternalAnchor(anchor, authoredTarget, resolved, adapted) {
    if (adapted && adapted.status !== "internal") {
      internalTargets.delete(anchor);
      disableTarget(anchor, "href", adapted.status, adapted.reason);
      return;
    }
    const path = adapted?.status === "internal" ? adapted.path : resolved.path;
    const target = navigationTarget({ ...resolved, path });
    clearDisabledTarget(anchor);
    anchor.setAttribute(
      "href",
      preserveFragmentOnlyHrefs && isSameDocumentFragment(authoredTarget, target, sourcePath)
        ? authoredTarget
        : mb.navigation.href(target),
    );
    if (adapted?.status === "internal") {
      anchor.setAttribute("data-metabrowser-link-adapter", adapted.adapter);
    } else {
      anchor.removeAttribute("data-metabrowser-link-adapter");
    }
    internalTargets.set(anchor, target);
  }

  for (const descriptor of RESOURCE_ATTRIBUTES) {
    const tagName = descriptor.selector.slice(0, descriptor.selector.indexOf("[")).toLowerCase();
    for (const resource of admittedTargets) {
      if (
        resource.hasAttribute("data-mb-wiki-target") ||
        resource.tagName.toLowerCase() !== tagName ||
        !resource.hasAttribute(descriptor.attribute)
      ) {
        continue;
      }
      const authoredTarget = resource.getAttribute(descriptor.attribute);
      if (authoredTarget === null) {
        continue;
      }
      resolveStandard(
        {
          action: "embed",
          authoredTarget,
          sourcePath,
          syntax: "html",
        },
        (resolved) => {
          if (resolved.status === "internal") {
            resource.setAttribute(descriptor.attribute, rawResourceHref(resolved));
          } else if (resolved.status !== "external") {
            disableTarget(resource, descriptor.attribute, resolved.status, resolved.reason);
          }
        },
      );
    }
  }

  const wiki = enhanceWikiLinks(
    container,
    sourcePath,
    mb,
    (element, target) => {
      internalTargets.set(element, target);
    },
    {
      budget: options.transclusionBudget,
      cancel,
      chain: options.transclusionChain,
      enhancementBudget,
      reconciliation,
      reconciliationScope,
      schedule,
      signal: options.signal,
      workerClient,
      elements: admittedTargets.filter((element) => element.hasAttribute("data-mb-wiki-target")),
      enhanceNested: (nestedContainer, nestedSourcePath, nestedOptions) =>
        enhanceRenderedLinks(nestedContainer, nestedSourcePath, mb, {
          cancel,
          enhancementBudget,
          eventTarget,
          reconciliation,
          schedule,
          signal: nestedOptions.signal,
          transclusionBudget: nestedOptions.budget,
          transclusionChain: nestedOptions.chain,
          workerClient,
        }),
    },
  );

  /** @param {Event} event */
  function handleClick(event) {
    if (!isPlainPrimaryClick(event)) {
      return;
    }
    let element = event.target;
    while (element && element !== container) {
      if (element instanceof Element) {
        const target = internalTargets.get(element);
        if (target) {
          const anchor = /** @type {HTMLAnchorElement} */ (element);
          if (anchor.hasAttribute("download") || notSameBrowsingContext(anchor)) {
            return;
          }
          event.preventDefault();
          void mb.navigation.open(target).catch((error) => {
            console.warn("Could not open Markdown link", error);
          });
          return;
        }
        element = element.parentElement;
      } else {
        return;
      }
    }
  }

  /** @param {Event} event */
  function handleFragment(event) {
    const detail = /** @type {CustomEvent<{target?: NavigationTarget}>} */ (event).detail;
    scheduleFragment(detail?.target);
  }

  /** @param {NavigationTarget | null | undefined} target */
  function scheduleFragment(target) {
    if (!target?.fragment || normalizedFilePath(target.path) !== normalizedFilePath(sourcePath)) {
      return;
    }
    const fragment = target.fragment;
    if (fragmentFrame) {
      cancel(fragmentFrame);
    }
    fragmentFrame = schedule(() => {
      fragmentFrame = 0;
      const current = mb.navigation.current();
      if (
        disposed ||
        !current ||
        normalizedFilePath(current.path) !== normalizedFilePath(sourcePath) ||
        current.fragment !== fragment
      ) {
        return;
      }
      // As on github.com, `#name` also reaches an inert render's `user-content-name`
      // heading anchor, so a GitHub address's fragment scrolls where it did there.
      (
        findElementById(container, fragment) ??
        findElementById(container, `user-content-${fragment}`)
      )?.scrollIntoView({
        block: "start",
      });
    });
  }

  container.addEventListener("click", handleClick);
  eventTarget.addEventListener("metabrowser:navigation-fragment", handleFragment);
  scheduleFragment(mb.navigation.current());

  return Object.freeze({
    /** Enhanceable targets beyond the aggregate budget stay authored. */
    admissionTruncated: admission.truncated,
    dispose() {
      if (disposed) {
        return;
      }
      disposed = true;
      wiki.dispose();
      reconciliationScope.dispose();
      if (ownsReconciliation) {
        reconciliation.dispose();
      }
      if (ownsWorkerClient) {
        workerClient.dispose();
      }
      container.removeEventListener("click", handleClick);
      eventTarget.removeEventListener("metabrowser:navigation-fragment", handleFragment);
      if (fragmentFrame) {
        cancel(fragmentFrame);
        fragmentFrame = 0;
      }
    },
  });
}

/**
 * Admit the aggregate root budget's deterministic DOM-order prefix and report
 * whether any enhanceable target was left out.
 *
 * @param {HTMLElement} container
 * @param {ReturnType<typeof createMarkdownEnhancementBudget>} budget
 */
function admittedTargetElements(container, budget) {
  /** @type {Element[]} */
  const admitted = [];
  let truncated = false;
  for (const element of matchingDescendants(
    container,
    ENHANCEABLE_TARGET_SELECTOR,
    MAX_ENHANCED_TARGETS + 1,
  )) {
    if (!budget.claim()) {
      truncated = true;
      break;
    }
    admitted.push(element);
  }
  return Object.freeze({ elements: Object.freeze(admitted), truncated });
}

/** @param {{path: string, query?: string, fragment?: string}} resolved */
function navigationTarget(resolved) {
  /** @type {{path: string, query?: string, fragment?: string}} */
  const target = { path: resolved.path };
  if (resolved.query) {
    target.query = resolved.query;
  }
  if (resolved.fragment) {
    target.fragment = resolved.fragment;
  }
  return Object.freeze(target);
}

/** @param {{path: string, fragment?: string}} resolved */
function rawResourceHref(resolved) {
  const fragment = resolved.fragment ? `#${encodeURIComponent(resolved.fragment)}` : "";
  return `/raw?path=${encodeURIComponent(normalizedFilePath(resolved.path))}${fragment}`;
}

/** @param {Element} element @param {string} attribute @param {string} status @param {string} reason */
function disableTarget(element, attribute, status, reason) {
  if (!element.hasAttribute("data-metabrowser-link-status")) {
    // The status explanation borrows the title only while the target is
    // disabled; keep the author's tooltip to restore.
    const authoredTitle = element.getAttribute("title");
    if (authoredTitle !== null) {
      element.setAttribute("data-metabrowser-authored-title", authoredTitle);
    }
  }
  element.removeAttribute(attribute);
  element.setAttribute("data-metabrowser-link-status", status);
  element.setAttribute("aria-disabled", "true");
  element.setAttribute("title", `${destinationStatusMessage(status)} (${reason}).`);
  if (element.tagName.toLowerCase() === "a" && !element.hasAttribute("tabindex")) {
    element.setAttribute("tabindex", "0");
    element.setAttribute("data-metabrowser-managed-tabindex", "true");
  }
}

/** @param {string} status */
function destinationStatusMessage(status) {
  if (status === "pending") {
    return "Metabrowser is resolving this destination";
  }
  if (status === "ambiguous") {
    return "Multiple local documents match this destination";
  }
  if (status === "unsupported") {
    return "Metabrowser cannot resolve this destination";
  }
  return "Metabrowser blocked this destination";
}

/** @param {Element} element */
function clearDisabledTarget(element) {
  if (!element.hasAttribute("data-metabrowser-link-status")) {
    return;
  }
  element.removeAttribute("aria-disabled");
  element.removeAttribute("data-metabrowser-link-status");
  const authoredTitle = element.getAttribute("data-metabrowser-authored-title");
  if (authoredTitle === null) {
    element.removeAttribute("title");
  } else {
    element.setAttribute("title", authoredTitle);
    element.removeAttribute("data-metabrowser-authored-title");
  }
  if (element.getAttribute("data-metabrowser-managed-tabindex") === "true") {
    element.removeAttribute("data-metabrowser-managed-tabindex");
    element.removeAttribute("tabindex");
  }
}

/** @param {string} authoredTarget */
function isPossiblePublishedRoute(authoredTarget) {
  const path = authoredTarget.split("#", 1)[0].split("?", 1)[0];
  const leaf = path.replace(/\/$/, "").split("/").at(-1) || "";
  return path.startsWith("/") && (path.endsWith("/") || !leaf.includes("."));
}

/** @param {Event} event */
function isPlainPrimaryClick(event) {
  const mouse = /** @type {MouseEvent} */ (event);
  return (
    !event.defaultPrevented &&
    mouse.button === 0 &&
    !mouse.altKey &&
    !mouse.ctrlKey &&
    !mouse.metaKey &&
    !mouse.shiftKey
  );
}

/** @param {HTMLAnchorElement} anchor */
function notSameBrowsingContext(anchor) {
  const target = anchor.getAttribute("target");
  return Boolean(target && target.toLowerCase() !== "_self");
}

/** @param {string} path */
function normalizedFilePath(path) {
  return path.endsWith("/") ? path.slice(0, -1) : path;
}

/** @param {string} sourcePath @param {NavigationTarget | null | undefined} current */
function isCurrentDocument(sourcePath, current) {
  return Boolean(current && normalizedFilePath(current.path) === normalizedFilePath(sourcePath));
}

/**
 * KPress identifies the primary document's TOC entries from their fragment-only
 * hrefs. The caller separately verifies that the source is the current document;
 * embedded documents need canonical hrefs relative to their own source.
 *
 * @param {string} authoredTarget
 * @param {NavigationTarget} target
 * @param {string} sourcePath
 */
function isSameDocumentFragment(authoredTarget, target, sourcePath) {
  return (
    authoredTarget.startsWith("#") &&
    normalizedFilePath(target.path) === normalizedFilePath(sourcePath)
  );
}

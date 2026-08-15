import { localizeGithubUrl } from "./github_localizer.js";
import { resolveStandardTarget } from "./links.js";
import { resolvePublishedRoute } from "./project_adapters.js";
import { enhanceWikiLinks } from "./wiki_enhancer.js";

const MAX_ENHANCED_TARGETS = 4096;
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
 * @param {{eventTarget?: Pick<Window, "addEventListener" | "removeEventListener">, schedule?: (callback: FrameRequestCallback) => number, cancel?: (handle: number) => void, signal?: AbortSignal, transclusionBudget?: ReturnType<typeof import("./transclusion.js").createTransclusionBudget>, transclusionChain?: ReadonlyArray<string>}=} options
 */
export function enhanceRenderedLinks(container, sourcePath, mb, options = {}) {
  const eventTarget = options.eventTarget ?? window;
  const schedule = options.schedule ?? requestAnimationFrame;
  const cancel = options.cancel ?? cancelAnimationFrame;
  /** @type {WeakMap<Element, NavigationTarget>} */
  const internalTargets = new WeakMap();
  /** @type {Array<{anchor: Element, authoredTarget: string}>} */
  const possiblePublishedRoutes = [];
  let disposed = false;
  let scheduledFrame = 0;
  /** @type {(() => void) | null} */
  let unsubscribeCatalog = null;

  for (const anchor of boundedElements(container.querySelectorAll("a[href]"))) {
    const authoredTarget = anchor.getAttribute("href");
    if (authoredTarget === null) {
      continue;
    }
    const resolved = resolveStandardTarget({
      action: "navigate",
      authoredTarget,
      sourcePath,
      syntax: "html",
    });
    if (resolved.status === "internal") {
      applyInternalAnchor(anchor, authoredTarget, resolved);
      if (isPossiblePublishedRoute(authoredTarget)) {
        possiblePublishedRoutes.push({ anchor, authoredTarget });
      }
    } else if (resolved.status === "external") {
      const localized = localizeGithubUrl(authoredTarget, mb.repository);
      if (localized) {
        const target = navigationTarget(localized);
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
  }

  /**
   * @param {Element} anchor
   * @param {string} authoredTarget
   * @param {{status: "internal", path: string, query?: string, fragment?: string}} resolved
   */
  function applyInternalAnchor(anchor, authoredTarget, resolved) {
    const adapted = resolvePublishedRoute(
      { authoredTarget, resolvedPath: resolved.path },
      mb.fileCatalog.snapshot(),
    );
    if (adapted && adapted.status !== "internal") {
      internalTargets.delete(anchor);
      disableTarget(anchor, "href", adapted.status, adapted.reason);
      return;
    }
    const path = adapted?.status === "internal" ? adapted.path : resolved.path;
    const target = navigationTarget({ ...resolved, path });
    clearDisabledTarget(anchor);
    anchor.setAttribute("href", mb.navigation.href(target));
    if (adapted?.status === "internal") {
      anchor.setAttribute("data-metabrowser-link-adapter", adapted.adapter);
    } else {
      anchor.removeAttribute("data-metabrowser-link-adapter");
    }
    internalTargets.set(anchor, target);
  }

  if (possiblePublishedRoutes.length > 0 && !mb.fileCatalog.snapshot().complete) {
    unsubscribeCatalog = mb.fileCatalog.subscribe(() => {
      if (disposed) {
        return;
      }
      for (const candidate of possiblePublishedRoutes) {
        const resolved = resolveStandardTarget({
          action: "navigate",
          authoredTarget: candidate.authoredTarget,
          sourcePath,
          syntax: "html",
        });
        if (resolved.status === "internal") {
          applyInternalAnchor(candidate.anchor, candidate.authoredTarget, resolved);
        }
      }
      if (mb.fileCatalog.snapshot().complete) {
        unsubscribeCatalog?.();
        unsubscribeCatalog = null;
      }
    });
  }

  for (const descriptor of RESOURCE_ATTRIBUTES) {
    for (const resource of boundedElements(container.querySelectorAll(descriptor.selector))) {
      const authoredTarget = resource.getAttribute(descriptor.attribute);
      if (authoredTarget === null) {
        continue;
      }
      const resolved = resolveStandardTarget({
        action: "embed",
        authoredTarget,
        sourcePath,
        syntax: "html",
      });
      if (resolved.status === "internal") {
        resource.setAttribute(descriptor.attribute, rawResourceHref(resolved));
      } else if (resolved.status !== "external") {
        disableTarget(resource, descriptor.attribute, resolved.status, resolved.reason);
      }
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
      chain: options.transclusionChain,
      signal: options.signal,
      enhanceNested: (nestedContainer, nestedSourcePath, nestedOptions) =>
        enhanceRenderedLinks(nestedContainer, nestedSourcePath, mb, {
          cancel,
          eventTarget,
          schedule,
          signal: nestedOptions.signal,
          transclusionBudget: nestedOptions.budget,
          transclusionChain: nestedOptions.chain,
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
    if (scheduledFrame) {
      cancel(scheduledFrame);
    }
    scheduledFrame = schedule(() => {
      scheduledFrame = 0;
      const current = mb.navigation.current();
      if (
        disposed ||
        !current ||
        normalizedFilePath(current.path) !== normalizedFilePath(sourcePath) ||
        current.fragment !== fragment
      ) {
        return;
      }
      findFragmentTarget(container, fragment)?.scrollIntoView({ block: "start" });
    });
  }

  container.addEventListener("click", handleClick);
  eventTarget.addEventListener("metabrowser:navigation-fragment", handleFragment);
  scheduleFragment(mb.navigation.current());

  return Object.freeze({
    dispose() {
      if (disposed) {
        return;
      }
      disposed = true;
      wiki.dispose();
      unsubscribeCatalog?.();
      unsubscribeCatalog = null;
      container.removeEventListener("click", handleClick);
      eventTarget.removeEventListener("metabrowser:navigation-fragment", handleFragment);
      if (scheduledFrame) {
        cancel(scheduledFrame);
        scheduledFrame = 0;
      }
    },
  });
}

/** @param {NodeListOf<Element>} elements */
function boundedElements(elements) {
  return Array.from(elements).slice(0, MAX_ENHANCED_TARGETS);
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
  element.removeAttribute("title");
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

/** @param {HTMLElement} container @param {string} fragment */
function findFragmentTarget(container, fragment) {
  for (const element of boundedElements(container.querySelectorAll("[id]"))) {
    if (element.id === fragment) {
      return element;
    }
  }
  return null;
}

/** @param {string} path */
function normalizedFilePath(path) {
  return path.endsWith("/") ? path.slice(0, -1) : path;
}

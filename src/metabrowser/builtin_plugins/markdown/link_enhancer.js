import { resolveStandardTarget } from "./links.js";

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
 * @param {{eventTarget?: Pick<Window, "addEventListener" | "removeEventListener">, schedule?: (callback: FrameRequestCallback) => number, cancel?: (handle: number) => void}=} options
 */
export function enhanceRenderedLinks(container, sourcePath, mb, options = {}) {
  const eventTarget = options.eventTarget ?? window;
  const schedule = options.schedule ?? requestAnimationFrame;
  const cancel = options.cancel ?? cancelAnimationFrame;
  /** @type {WeakMap<Element, NavigationTarget>} */
  const internalTargets = new WeakMap();
  let disposed = false;
  let scheduledFrame = 0;

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
      const target = navigationTarget(resolved);
      anchor.setAttribute("href", mb.navigation.href(target));
      internalTargets.set(anchor, target);
    } else if (resolved.status !== "external") {
      disableTarget(anchor, "href", resolved.status, resolved.reason);
    }
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
  element.setAttribute("title", `Metabrowser blocked this destination (${reason}).`);
  if (element.tagName.toLowerCase() === "a" && !element.hasAttribute("tabindex")) {
    element.setAttribute("tabindex", "0");
  }
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

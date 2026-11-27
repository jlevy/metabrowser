import { findElementById, MAX_ENHANCED_TARGETS, matchingDescendants } from "./dom-traversal.js";
import { createTrustedStandardLinkResolutionContext } from "./links.js";
import { acquireMarkdownWorkerClient } from "./markdown-worker-client.js";
import {
  holdImage,
  isOutsideAddress,
  loadHeldImageEagerly,
  rememberHeldImage,
} from "./place-rendered.js";
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
 * The title an author gave each in-app link, once its link card says it and the link no
 * longer carries it (`enhanceRenderedLinks`), so a later pass over the same link, as a
 * published route's is, still has it.
 *
 * @type {WeakMap<Element, string>}
 */
const authorTitles = new WeakMap();

/**
 * Enhance the safe HTML emitted by KPress with Metabrowser navigation semantics.
 *
 * The plugin decides what an authored link names, and the shell decides how that target is
 * spelled as a `/view/` address. The resolvers do no I/O, so each decision is testable
 * against a catalog snapshot, and a target passes through them in this order:
 *
 * 1. Scheme dispatch (`links.js`): `http`, `https`, `mailto`, and `tel` stay external, and
 *    an unsafe scheme is disabled with a visible reason.
 * 2. Exact resolution (`links.js`): relative, `./`, `../`, and leading-slash targets resolve
 *    from the source document as GitHub resolves them. A missing target keeps its URL and
 *    opens the ordinary not-found state; nothing guesses by basename. Media goes through
 *    `/raw`, except an embedded PDF, which is the pdf plugin's card with a link to the
 *    PDF's view (`mountPdfEmbed`); a link to a PDF opens its view, as any file's does.
 * 3. Repository links (`static/repository-links.js`, *repositoryLinks* below): a `github.com` link into the served repository opens in Metabrowser when
 *    its page exists here and shows the same thing, as the served repository's identity
 *    (`repository_context.py`, read from Git metadata with bounded reads and no Git
 *    process) proves: a file or folder on the served branch or commit, the repository's
 *    root, a pull request and its Changes and Checks, a commit, and the pull request list.
 *    Anything unproven, another branch among it, stays an outbound link.
 * 4. Published-site routes (`project-adapters.js`): with an MkDocs, Docusaurus, or Jekyll
 *    configuration at the served root, a published route such as `/guide/` maps to the
 *    source document behind it; it stays inert until the pinned catalog pass decides.
 * 5. Wiki links (`wiki-resolver.js`, through `wiki-enhancer.js`): `[[...]]` resolves to an
 *    exact path, then the source directory, then a unique catalog match. An ambiguous or
 *    missing note renders visibly with its candidates, and a name unique in an incomplete
 *    catalog stays pending until the catalog is complete, so a target never depends on
 *    walk order.
 *
 * @param {HTMLElement} container
 * @param {string} sourcePath
 * @param {MetabrowserPublicSdk} mb
 * @param {{eventTarget?: Pick<Window, "addEventListener" | "removeEventListener">, schedule?: (callback: FrameRequestCallback) => number, cancel?: (handle: number) => void, signal?: AbortSignal, enhancementBudget?: ReturnType<typeof createMarkdownEnhancementBudget>, reconciliation?: ReturnType<typeof createMarkdownReconciliationCoordinator>, transclusionBudget?: ReturnType<typeof import("./transclusion.js").createTransclusionBudget>, transclusionChain?: ReadonlyArray<ReturnType<typeof import("./transclusion.js").transclusionKey>>, rawVersions?: unknown, pagePath?: string, workerClient?: import("./markdown-worker-client.js").MarkdownWorkerRunner, repositoryLinks?: MetabrowserRepositoryLinksRuntime | null}=} options
 *   `repositoryLinks` is what a link into the served repository opens
 *   (`metabrowser.loadRepositoryLinks`), which `rendered.js` loads beside the render; without
 *   it, as on a page with no GitHub identity, such a link stays as written.
 *   Each link the document opens in Metabrowser has its link card, the tooltip that says
 *   what the link opens, on every page, with or without that runtime: registered through the
 *   SDK (`mb.previewLink`, static/plugin-sdk-views.js) with *container*, whose cards
 *   `dispose` puts away: a link to a file or folder by its path, a wiki link, a PDF's View,
 *   and a `github.com` link the resolver opens here; and so has each link to another site,
 *   whose card says where it goes. A link to a place in the same document has none: it opens
 *   no other page. A title the author gave a link with a card moves into its card, so the
 *   reader never sees two tooltips; a link with none keeps its title.
 *   `rawVersions` is the render's `raw_versions`: the version of each served file it
 *   embeds, by identity, which that file's address carries.
 *   `pagePath` is the path of the page that shows this document as its own, when that is
 *   not `sourcePath`: the folder whose Overview shows its README. A fragment-only link
 *   names a place in this document, so it names that place on that page, and the page's
 *   fragment scrolls to it. A transclusion is not its page's document and keeps its own.
 */
export function enhanceRenderedLinks(container, sourcePath, mb, options = {}) {
  const eventTarget = options.eventTarget ?? window;
  const schedule = options.schedule ?? requestAnimationFrame;
  const cancel = options.cancel ?? cancelAnimationFrame;
  const enhancementBudget = options.enhancementBudget || createMarkdownEnhancementBudget();
  const ownsWorkerClient = !options.workerClient;
  const workerClient = options.workerClient || acquireMarkdownWorkerClient();
  const sourceKind = mb.sourceKind?.() === "git_revision" ? "git_revision" : "filesystem";
  const rawVersions = rawVersionsOf(options.rawVersions);
  const standardLinks = createTrustedStandardLinkResolutionContext(
    sourcePath,
    undefined,
    sourceKind,
  );
  const pagePath = options.pagePath ?? sourcePath;
  const repositoryLinks = options.repositoryLinks ?? null;
  const preserveFragmentOnlyHrefs = isCurrentDocument(pagePath, mb.navigation.current());
  /** @type {WeakMap<Element, NavigationTarget>} */
  const internalTargets = new WeakMap();
  /**
   * Each link into a pull request's, the list's, or a commit's page, by its address, which
   * a plain click asks the shell to open in place (`navigation.openRoute`).
   *
   * @type {WeakMap<Element, string>}
   */
  const routeTargets = new WeakMap();
  /** The PDF cards this document drew, disposed with it. @type {Set<{dispose: () => void}>} */
  const pdfEmbeds = new Set();
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

  /**
   * Give *anchor*, a link this document opens in Metabrowser or one to another site, its
   * link card, saying the title its author gave it, which then leaves the link: its own, or
   * else an image's inside it, as `[![d](d.png "Its title")](x.md)` writes one. Every title
   * inside the link leaves it too, since each would be a second tooltip over the card. A
   * link the SDK gives no card, such as a mail link, keeps its titles, and a download, which
   * saves the file rather than opening its page, has none.
   *
   * @param {Element} anchor
   * @param {MetabrowserLinkPreviewTarget} target
   */
  function previewLink(anchor, target) {
    if (anchor.hasAttribute("download")) {
      return;
    }
    const inner = Array.from(anchor.querySelectorAll("[title]"));
    const authorTitle =
      anchor.getAttribute("title") ??
      authorTitles.get(anchor) ??
      inner.map((element) => element.getAttribute("title")).find(Boolean) ??
      null;
    if (mb.previewLink(container, anchor, target, { authorTitle })) {
      if (authorTitle !== null) {
        authorTitles.set(anchor, authorTitle);
      }
      anchor.removeAttribute("title");
      for (const element of inner) {
        element.removeAttribute("title");
      }
    }
  }

  /**
   * A document's own link to a file or folder, by the path it names, opens that file of the
   * tree the document is in: here, as a link to the served commit does.
   *
   * @param {Element} anchor
   * @param {NavigationTarget} target
   */
  function previewPath(anchor, target) {
    previewLink(anchor, Object.freeze({ kind: "view", target, localization: "revision" }));
  }

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
            mb.forgetPreview(anchor);
            disableTarget(anchor, "href", "pending", "published-route-pending");
            reconciliationScope.published(
              { authoredTarget, resolvedPath: resolved.path },
              (adapted) => applyInternalAnchor(anchor, authoredTarget, resolved, adapted),
            );
          } else {
            applyInternalAnchor(anchor, authoredTarget, resolved, null);
          }
        } else if (resolved.status === "external") {
          const localized =
            repositoryLinks?.localize(authoredTarget, mb.repository, {
              sourceKind,
            }) ?? null;
          // A document has no text context, so the answer is in-app or nothing. An in-app
          // page does not leave the page, so it loses what an inert render gives an outside
          // link, once its address is spelled; a plain click on a `/view/` target, spelled
          // in the GitPath wire on a pin, then opens it here, and one on a pull request's,
          // the list's, or a commit's page opens that page in place, as the shell opens it.
          // Its card says what it opens, and that a link to the served branch opens the
          // served working tree.
          if (localized?.kind === "view") {
            const target = navigationTarget(localized.target);
            anchor.setAttribute("href", mb.navigation.href(target));
            internalTargets.set(anchor, target);
          } else if (localized?.kind === "route") {
            anchor.setAttribute("href", localized.href);
            routeTargets.set(anchor, localized.href);
          }
          if (localized?.kind === "view" || localized?.kind === "route") {
            anchor.removeAttribute("target");
            anchor.removeAttribute("rel");
            anchor.setAttribute("data-metabrowser-github-localization", localized.localization);
            previewLink(anchor, localized);
          } else {
            // It leaves for another site, and its card says which: a mail or phone link names
            // none, and keeps what it had.
            previewLink(anchor, { kind: "external", url: anchor.getAttribute("href") ?? "" });
          }
          mb.decorateExternalLink(/** @type {HTMLElement} */ (anchor));
        } else {
          disableTarget(anchor, "href", resolved.status, resolved.reason);
          mb.decorateExternalLink(/** @type {HTMLElement} */ (anchor));
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
      mb.forgetPreview(anchor);
      disableTarget(anchor, "href", adapted.status, adapted.reason);
      return;
    }
    const path = adapted?.status === "internal" ? adapted.path : resolved.path;
    const documentTarget = navigationTarget({ ...resolved, path });
    const sameDocument = isSameDocumentFragment(authoredTarget, documentTarget, sourcePath);
    const target = sameDocument ? { ...documentTarget, path: pagePath } : documentTarget;
    clearDisabledTarget(anchor);
    anchor.setAttribute(
      "href",
      preserveFragmentOnlyHrefs && sameDocument ? authoredTarget : mb.navigation.href(target),
    );
    if (adapted?.status === "internal") {
      anchor.setAttribute("data-metabrowser-link-adapter", adapted.adapter);
    } else {
      anchor.removeAttribute("data-metabrowser-link-adapter");
    }
    internalTargets.set(anchor, target);
    if (!sameDocument) {
      previewPath(anchor, target);
    }
    mb.decorateExternalLink(/** @type {HTMLElement} */ (anchor));
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
          if (
            resolved.status === "internal" &&
            resolved.mediaKind === "pdf" &&
            (tagName === "img" || tagName === "object")
          ) {
            // Never a viewer in a document, and never `/raw`: the card, linking to the view.
            const embed = mountPdfEmbed(
              resource,
              mb,
              navigationTarget({ path: normalizedFilePath(resolved.path) }),
              authoredFileName(authoredTarget),
              registerInternal,
            );
            pdfEmbeds.add(embed);
            resource.replaceWith(embed.element);
            return;
          }
          if (resolved.status === "internal") {
            const version = rawVersions.get(normalizedFilePath(resolved.path));
            const href = rawResourceHref(resolved, version);
            // Held only at an address that names its bytes: a versioned one, or any on a
            // pinned revision, whose files never change (place-rendered.js).
            if (tagName === "img" && (version !== undefined || sourceKind === "git_revision")) {
              loadHeldImageEagerly(resource, href);
              holdImage(resource);
            }
            resource.setAttribute(descriptor.attribute, href);
          } else if (resolved.status === "external") {
            // Placement made it eager if the page holds it (place-rendered.js).
            if (tagName === "img" && isOutsideAddress(authoredTarget)) {
              holdImage(resource);
            }
          } else {
            disableTarget(resource, descriptor.attribute, resolved.status, resolved.reason);
          }
        },
      );
    }
  }

  /** A wiki link's, or a PDF's link to its view. @param {Element} anchor @param {NavigationTarget} target */
  function registerInternal(anchor, target) {
    internalTargets.set(anchor, target);
    previewPath(anchor, target);
  }

  const wiki = enhanceWikiLinks(container, sourcePath, mb, registerInternal, {
    budget: options.transclusionBudget,
    cancel,
    chain: options.transclusionChain,
    embedPdf: (template, target, name) =>
      mountPdfEmbed(
        template,
        mb,
        navigationTarget({ path: normalizedFilePath(target.path) }),
        name,
        registerInternal,
      ),
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
        rawVersions: nestedOptions.rawVersions,
        repositoryLinks,
        workerClient,
      }),
  });

  /** @param {Event} event */
  function handleClick(event) {
    if (!isPlainPrimaryClick(event)) {
      return;
    }
    let element = event.target;
    while (element && element !== container) {
      if (element instanceof Element) {
        const target = internalTargets.get(element);
        const route = routeTargets.get(element);
        if (target || route !== undefined) {
          const anchor = /** @type {HTMLAnchorElement} */ (element);
          if (anchor.hasAttribute("download") || notSameBrowsingContext(anchor)) {
            return;
          }
          if (target) {
            event.preventDefault();
            void mb.navigation.open(target).catch((error) => {
              console.warn("Could not open Markdown link", error);
            });
          } else if (route !== undefined && mb.navigation.openRoute(route)) {
            // A page the shell cannot open in place yet is the browser's to follow.
            event.preventDefault();
          }
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
    if (!target?.fragment || normalizedFilePath(target.path) !== normalizedFilePath(pagePath)) {
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
        normalizedFilePath(current.path) !== normalizedFilePath(pagePath) ||
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
  // A load does not bubble, so the container hears its images' in the capture phase.
  container.addEventListener("load", rememberHeldImage, true);
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
      // Its links' cards, and the one up on any of them (docs/design-system.md, "A Surface
      // Puts Away Only Its Own Tooltip"); a transclusion's own enhancer puts away its own.
      mb.disposePreviews(container);
      wiki.dispose();
      for (const embed of pdfEmbeds) {
        embed.dispose();
      }
      pdfEmbeds.clear();
      reconciliationScope.dispose();
      if (ownsReconciliation) {
        reconciliation.dispose();
      }
      if (ownsWorkerClient) {
        workerClient.dispose();
      }
      container.removeEventListener("click", handleClick);
      container.removeEventListener("load", rememberHeldImage, true);
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

/**
 * The pdf plugin's `mountPdfCard` (builtin_plugins/pdf/card.js), as `mb.plugins.load("pdf")`
 * answers it.
 *
 * @typedef {(host: HTMLElement, options: {path: string, name: string, links: HTMLElement[]}) => {dispose: () => void}} MountPdfCard
 */

/**
 * Draw a PDF the document embeds, in place of *replaced*: `![](report.pdf)` and
 * `<img src="report.pdf">`, an `<object>` of one, and `![[report.pdf]]`
 * (wiki-enhancer.js). A document never starts the browser's viewer, which is the file
 * page's alone, and never addresses `/raw`: the slot holds the pdf plugin's card, the
 * first page as an image the server drew, the file's name, and one link, View, to the
 * PDF's view in Metabrowser. The image is not a link (card.js).
 *
 * Until the card mounts, and for good when the plugin cannot load, the slot holds a plain
 * link to the view named by the file. Both links are *register*ed, so a plain click opens
 * the view through `mb.navigation` and a modified click is the browser's. The plugin
 * loads on the first PDF a page embeds (`requires = ["pdf"]` in manifest.toml), so a
 * document with none never fetches it. The load settles after the caller returns, so an
 * inert render's slot is in the page's document by then (inert-render.js), and the card
 * is built there.
 *
 * @param {Element} replaced
 * @param {MetabrowserPublicSdk} mb
 * @param {NavigationTarget} target The PDF's view.
 * @param {string} name The file's name, as the document names it.
 * @param {(anchor: Element, target: NavigationTarget) => void} register
 * @returns {{element: HTMLElement, dispose: () => void}}
 */
function mountPdfEmbed(replaced, mb, target, name, register) {
  const slot = replaced.ownerDocument.createElement("span");
  slot.setAttribute("class", "metabrowser-pdf-embed");
  slot.setAttribute("data-metabrowser-pdf-embed", "link");
  const fallback = pdfViewLink(slot.ownerDocument, mb, target, name, register);
  slot.append(fallback);
  /** @type {{dispose: () => void} | null} */
  let card = null;
  let disposed = false;
  const plugins = mb.plugins;
  if (typeof plugins?.load === "function") {
    // A load that throws at once is a page without the plugin, as one that rejects is.
    void new Promise((resolve) => resolve(plugins.load("pdf")))
      .then((pdf) => {
        const mount = /** @type {{mountPdfCard?: MountPdfCard} | undefined} */ (pdf)?.mountPdfCard;
        if (disposed || typeof mount !== "function") {
          return;
        }
        const view = pdfViewLink(slot.ownerDocument, mb, target, "View", register);
        card = mount(slot, { path: target.path, name, links: [view] });
        fallback.remove();
        slot.setAttribute("data-metabrowser-pdf-embed", "card");
      })
      .catch(() => {
        // The link to the view stays, so the PDF is still a click away.
      });
  }
  return {
    element: slot,
    dispose() {
      if (disposed) {
        return;
      }
      disposed = true;
      card?.dispose();
      card = null;
    },
  };
}

/**
 * A plain link to a PDF's view, labelled *label*.
 *
 * @param {Document} doc
 * @param {MetabrowserPublicSdk} mb
 * @param {NavigationTarget} target
 * @param {string} label
 * @param {(anchor: Element, target: NavigationTarget) => void} register
 */
function pdfViewLink(doc, mb, target, label, register) {
  const anchor = doc.createElement("a");
  anchor.setAttribute("href", mb.navigation.href(target));
  anchor.textContent = label;
  register(anchor, target);
  return anchor;
}

/**
 * The file's name in an authored address: its last segment, decoded, without its query
 * or fragment.
 *
 * @param {string} authoredTarget
 */
function authoredFileName(authoredTarget) {
  const path = authoredTarget.split("#", 1)[0].split("?", 1)[0];
  const leaf = (path.endsWith("/") ? path.slice(0, -1) : path).split("/").at(-1) || path;
  try {
    return decodeURIComponent(leaf);
  } catch {
    return leaf;
  }
}

/**
 * A served file's address, with the version the render gave it when it gave one.
 *
 * @param {{path: string, fragment?: string}} resolved
 * @param {string | undefined} version
 */
function rawResourceHref(resolved, version) {
  const fragment = resolved.fragment ? `#${encodeURIComponent(resolved.fragment)}` : "";
  const versioned = version === undefined ? "" : `&v=${encodeURIComponent(version)}`;
  const path = encodeURIComponent(normalizedFilePath(resolved.path));
  return `/raw?path=${path}${versioned}${fragment}`;
}

/**
 * The render's `raw_versions` as a map, keeping only string versions under string
 * identities; anything else versions nothing.
 *
 * @param {unknown} value
 * @returns {ReadonlyMap<string, string>}
 */
function rawVersionsOf(value) {
  /** @type {Map<string, string>} */
  const versions = new Map();
  if (value && typeof value === "object" && !Array.isArray(value)) {
    for (const [identity, version] of Object.entries(value)) {
      if (typeof version === "string" && version) {
        versions.set(identity, version);
      }
    }
  }
  return versions;
}

/** @param {Element} element @param {string} attribute @param {string} status @param {string} reason */
function disableTarget(element, attribute, status, reason) {
  if (!element.hasAttribute("data-metabrowser-link-status")) {
    // The status explanation borrows the title only while the target is
    // disabled; keep the author's tooltip to restore. A disabled link opens no
    // page, so it has no link card (`previewLink`), and this explanation is the
    // one tooltip it has, as an unresolved embed's or wiki link's is.
    const authoredTitle = element.getAttribute("title");
    if (authoredTitle !== null) {
      element.setAttribute("data-metabrowser-authored-title", authoredTitle);
    }
  }
  element.removeAttribute(attribute);
  element.setAttribute("data-metabrowser-link-status", status);
  element.setAttribute("aria-disabled", "true");
  // The reason code is data for a test or an agent, not the tooltip's
  // (docs/design-system-messages.md).
  element.setAttribute("data-metabrowser-link-reason", reason);
  element.setAttribute("title", `${destinationStatusMessage(status)}.`);
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
  element.removeAttribute("data-metabrowser-link-reason");
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

/** @param {string} pagePath @param {NavigationTarget | null | undefined} current */
function isCurrentDocument(pagePath, current) {
  return Boolean(current && normalizedFilePath(current.path) === normalizedFilePath(pagePath));
}

/**
 * KPress identifies the primary document's TOC entries from their fragment-only
 * hrefs. The caller separately verifies that the page showing the source is the
 * current page; embedded documents need canonical hrefs relative to their own source.
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

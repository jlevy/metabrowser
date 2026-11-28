import { enhanceRenderedLinks } from "./link-enhancer.js";
import { acquireMarkdownWorkerClient } from "./markdown-worker-client.js";
import { drawDiagrams, isFrontmatterError, placeRendered } from "./place-rendered.js";
import { holdLightPrintTheme, mountPrintIndicator } from "./print-indicator.js";
import { kpressTocConfig } from "./toc-toggle.js";
import { transclusionKey } from "./transclusion.js";

let mountSequence = 0;

/** Shown when the optional wiki preprocessing step could not run. */
const MARKDOWN_PREPROCESSING_UNAVAILABLE_DIAGNOSTIC = Object.freeze({
  code: "markdown-preprocessing-unavailable",
  message:
    "Wiki links, block references, and heading anchors were not processed for this document.",
  severity: "warning",
});

/** Shown when a document has more links, media, or wiki targets than one mount enhances. */
const MARKDOWN_LINK_LIMIT_DIAGNOSTIC = Object.freeze({
  code: "markdown-link-limit",
  message:
    "This document has more links, media, and wiki references than Metabrowser enhances at once; the rest keep their authored targets.",
  severity: "warning",
});

/** @param {Array<unknown>} diagnostics @param {(value: string) => string} escapeHtml */
export function renderKpressDiagnosticsHtml(diagnostics, escapeHtml) {
  if (!diagnostics.length) {
    return "";
  }
  const rows = diagnostics
    .map((diagnostic) => {
      if (typeof diagnostic === "string") {
        return `<dt>message</dt><dd>${escapeHtml(diagnostic)}</dd>`;
      }
      if (!diagnostic || typeof diagnostic !== "object") {
        return "";
      }
      const value = /** @type {Record<string, unknown>} */ (diagnostic);
      return ["code", "type", "message", "severity"]
        .filter((key) => value[key])
        .map((key) => `<dt>${key}</dt><dd>${escapeHtml(String(value[key]))}</dd>`)
        .join("");
    })
    .join("");
  return `<details class="kpress-frontmatter metabrowser-kpress-diagnostics kpress-no-print"><summary class="section-disclosure-trigger disclosure-toggle">Diagnostics</summary><dl>${rows}</dl></details>`;
}

/** @param {Array<unknown>} diagnostics @param {MetabrowserPublicSdk} mb */
export function buildDiagnosticsNode(diagnostics, mb) {
  const html = renderKpressDiagnosticsHtml(diagnostics, mb.escapeHtml);
  if (!html) {
    return null;
  }
  const temporary = document.createElement("div");
  temporary.innerHTML = html;
  return temporary.firstElementChild;
}

/**
 * Gather a placed document's preamble -- KPress's Frontmatter error notice and
 * Frontmatter disclosure -- with a Diagnostics disclosure of *diagnostics* at the top of
 * its prose. A front-matter error is left out of the disclosure: the document shows it
 * as its notice (`isFrontmatterError`).
 *
 * @param {HTMLElement} container @param {Array<unknown>} diagnostics @param {MetabrowserPublicSdk} mb
 */
export function injectDiagnostics(container, diagnostics, mb) {
  const node = buildDiagnosticsNode(
    diagnostics.filter((diagnostic) => !isFrontmatterError(diagnostic)),
    mb,
  );
  const article = container.querySelector("article.kpress");
  const layout = article?.querySelector(":scope > .kpress-doc-layout");
  const prose = layout?.querySelector(":scope > .kpress-prose");
  if (!article || !prose) {
    if (node) {
      (article || container).prepend(node);
    }
    return;
  }
  const meta = document.createElement("div");
  meta.className = "metabrowser-doc-meta";
  while (article.firstElementChild && article.firstElementChild !== layout) {
    meta.append(article.firstElementChild);
  }
  if (node) {
    meta.append(node);
  }
  if (meta.childElementCount) {
    prose.prepend(meta);
  }
}

/**
 * A failed render's notice: the answer's reader sentence, or the fixed one, and the one
 * remedy. The answer's `detail`, `diagnostics`, and status, and any exception, go to the
 * console (docs/design-system-messages.md, "Where the Detail Goes").
 *
 * @param {unknown} error @param {MetabrowserPublicSdk} mb
 */
export function renderKpressError(error, mb) {
  const value =
    error && typeof error === "object" ? /** @type {Record<string, unknown>} */ (error) : {};
  const payload =
    value.payload && typeof value.payload === "object"
      ? /** @type {Record<string, unknown>} */ (value.payload)
      : {};
  console.error("metabrowser: the document could not be rendered", error);
  const said =
    typeof payload.error === "string" && payload.error.trim()
      ? payload.error.trim()
      : "Could not render this document.";
  return `<div class="notice metabrowser-kpress-render-error" data-severity="error" role="alert"><strong>${mb.escapeHtml(said)}</strong> The Source tab shows its text.</div>`;
}

/**
 * Whether *error*, a rejection of `fetchKpressRender`, carries the server's refusal of an
 * untrusted document's render (`render-refusal.js` reads it), checked before that module
 * is loaded for it.
 *
 * @param {unknown} error
 */
function isRefusal(error) {
  const payload =
    error && typeof error === "object"
      ? /** @type {{payload?: unknown}} */ (error).payload
      : undefined;
  return (
    !!payload &&
    typeof payload === "object" &&
    /** @type {Record<string, unknown>} */ (payload).type === "kpress_render_refused"
  );
}

/**
 * @param {HTMLElement} container
 * @param {{path?: string, raw?: unknown}} ctx
 * @param {MetabrowserPublicSdk} mb
 * @param {{signal?: AbortSignal, includeToc?: "auto" | "on" | "off", pagePath?: string, printIndicator?: boolean, workerClient?: import("./markdown-worker-client.js").MarkdownWorkerRunner, wrapSource?: (text: string) => string}} [options]
 *   `pagePath` is the path of the page that shows this document as its own, when that is
 *   not the document's: the folder whose Overview shows its README. Its fragments are the
 *   document's headings, so a table-of-contents entry or a link to one of them moves within
 *   that page (link-enhancer.js). `printIndicator: true` puts a print button in the corner
 *   of the document's card (print-indicator.js), for a host whose view prints the document
 *   itself; it is off unless the host asks. `wrapSource` renders the file's text as the
 *   Markdown it returns, with no wiki preprocessing: a `.mmd` file is one Mermaid fence
 *   (mermaid-view.js).
 */
export function mountRenderedMarkdown(container, ctx, mb, options = {}) {
  const controller = new AbortController();
  const ownsWorkerClient = !options.workerClient;
  const workerClient = options.workerClient || acquireMarkdownWorkerClient();
  const abort = () => controller.abort();
  if (options.signal?.aborted) {
    controller.abort();
    if (ownsWorkerClient) {
      workerClient.dispose();
    }
  } else {
    options.signal?.addEventListener("abort", abort, { once: true });
  }
  let disposed = false;
  /** @type {(() => void) | null} */
  let disposeToc = null;
  /** @type {(() => void) | null} */
  let disposeLinks = null;
  /** @type {(() => void) | null} */
  let disposePrintIndicator = null;
  /** @type {{dispose(): void, ready: Promise<void>} | null} */
  let diagrams = null;
  // A rendered document prints on light paper, whatever the app's theme.
  const releasePrintTheme = holdLightPrintTheme();
  const dispose = () => {
    if (disposed) {
      return;
    }
    disposed = true;
    releasePrintTheme();
    options.signal?.removeEventListener("abort", abort);
    controller.abort();
    if (ownsWorkerClient) {
      workerClient.dispose();
    }
    disposeLinks?.();
    disposeLinks = null;
    disposeToc?.();
    disposeToc = null;
    disposePrintIndicator?.();
    disposePrintIndicator = null;
    diagrams?.dispose();
    diagrams = null;
  };

  container.classList.add("metabrowser-kpress-host", "metabrowser-markdown-document");
  container.innerHTML =
    '<div class="loading mb-delayed-loading"><div class="spinner"></div>' +
    '<span class="sr-only">Loading document…</span></div>';
  async function render() {
    // Start the optional resolver beside the render. The shared loader limits the wait.
    const repositoryLinks = mb.loadRepositoryLinks?.() ?? null;
    try {
      const raw =
        ctx.raw && typeof ctx.raw === "object"
          ? /** @type {Record<string, unknown>} */ (ctx.raw)
          : {};
      let content = typeof raw.content === "string" ? raw.content : null;
      if (raw.content_truncated === true || (options.wrapSource && content === null)) {
        content = await mb.fetchCompleteText(ctx, { signal: controller.signal });
      }
      /** @type {Array<unknown>} */
      const preparationDiagnostics = [];
      let wiki = null;
      if (content !== null && !options.wrapSource) {
        // Wiki preprocessing is an enhancement. If the worker cannot load or
        // fails, render the authored Markdown and say what is missing rather
        // than replacing the whole document with an error.
        try {
          const prepared = await workerClient.run(
            "prepare-primary",
            Object.freeze({ source: content }),
            { signal: controller.signal },
          );
          if (!isPrimaryPreparation(prepared)) {
            throw new TypeError("Markdown worker returned an invalid primary preparation");
          }
          wiki = prepared;
        } catch (error) {
          if (mb.errors.isAbortError(error) || controller.signal.aborted) {
            throw error;
          }
          preparationDiagnostics.push(MARKDOWN_PREPROCESSING_UNAVAILABLE_DIAGNOSTIC);
        }
      }
      const rendered = await mb.fetchKpressRender(ctx, "rendered", {
        dedupKey: `markdown-mount-${++mountSequence}`,
        profile: "document",
        includeToc: options.includeToc,
        signal: controller.signal,
        sourceText:
          options.wrapSource && content !== null
            ? options.wrapSource(content)
            : wiki?.changed
              ? wiki.source
              : undefined,
      });
      if (disposed || controller.signal.aborted) {
        return;
      }
      const linkRuntime = await repositoryLinks;
      if (disposed || controller.signal.aborted) {
        return;
      }
      const path = ctx.path;
      const pagePath = options.pagePath ?? path;
      const fences = rendered.structured_fences;
      const fenceRevision = rendered.fence_revision;
      const fencedViews =
        path && !options.wrapSource && fences?.length && fenceRevision
          ? await import("./fenced-views.js").catch((error) => {
              console.warn("Could not enhance structured code fences", error);
              return null;
            })
          : null;
      if (controller.signal.aborted) {
        return;
      }
      const { enhanced: links, inert: inertRender } = await placeRendered(
        container,
        rendered,
        mb,
        path
          ? (root) =>
              enhanceRenderedLinks(root, path, mb, {
                pagePath,
                repositoryLinks: linkRuntime,
                rawVersions: rendered.raw_versions,
                signal: controller.signal,
                workerClient,
                // The rendered document is its own ancestor, so a note that embeds
                // itself is a cycle at the first embed rather than the second.
                transclusionChain: Object.freeze([transclusionKey(path)]),
              })
          : null,
        path && fencedViews && fences && fenceRevision
          ? (root) =>
              fencedViews.attachFencedViews(
                root,
                path,
                fenceRevision,
                fences,
                mb,
                controller.signal,
              )
          : null,
      );
      if (disposed || controller.signal.aborted) {
        links?.dispose?.();
        return;
      }
      const diagnostics = [
        ...preparationDiagnostics,
        ...(wiki?.diagnostics || []),
        ...(rendered.diagnostics || []),
      ];
      if (links) {
        disposeLinks = links.dispose;
        if (links.admissionTruncated) {
          diagnostics.push(MARKDOWN_LINK_LIMIT_DIAGNOSTIC);
        }
      }
      if (
        path &&
        !options.wrapSource &&
        raw.frontmatter &&
        typeof raw.frontmatter === "object" &&
        !diagnostics.some(isFrontmatterError)
      ) {
        await import("./frontmatter-view.js")
          .then(({ attachFrontmatter }) => {
            attachFrontmatter(container, path, raw, mb, controller.signal);
          })
          .catch((error) => console.warn("Could not enhance frontmatter", error));
        if (controller.signal.aborted) {
          return;
        }
      }
      injectDiagnostics(container, diagnostics, mb);

      // An inert render's table of contents is the page's own; a trusted one's is KPress's.
      const inert = inertRender?.inertArticle(container);
      disposeToc =
        inertRender && inert
          ? inertRender.wireInertToc(inert, {
              open: (fragment) => {
                if (path && pagePath !== undefined) {
                  void mb.navigation.open({ path: pagePath, fragment }).catch((error) => {
                    console.warn("Could not open the table of contents entry", error);
                  });
                }
              },
            })
          : mb.kpressInitToc(container, kpressTocConfig(container));
      if (options.printIndicator === true) {
        // The button waits for the diagrams before it prints (print-ready.js).
        disposePrintIndicator = mountPrintIndicator(container, mb, {
          diagrams: () => diagrams?.ready,
        });
      }
      // Not awaited: the view's `ready`, which the shell's stage commit and the folder
      // Overview await, settles with the prose. Fetching Mermaid and laying out every
      // diagram follows, each drawing over the source block that already holds its place.
      // The print button waits for them; Command-P waits on nothing, so a diagram not yet
      // drawn prints as its source.
      diagrams = drawDiagrams(container, mb, inertRender ? "image" : "document");
    } catch (error) {
      if (disposed || mb.errors.isAbortError(error)) {
        return;
      }
      // A render the server refused is a readable document: its source, and why. What
      // draws it loads only for a refusal, which only an untrusted document's render can
      // be: 6,729 bytes, 2,548 gzipped (2026-11-17). Any other failure keeps the error box.
      if (isRefusal(error)) {
        try {
          const { mountRefusedSource, renderRefusal } = await import("./render-refusal.js");
          const refusal = renderRefusal(error);
          if (refusal !== null) {
            await mountRefusedSource(container, ctx, refusal, mb, { signal: controller.signal });
            return;
          }
        } catch (sourceError) {
          if (disposed || mb.errors.isAbortError(sourceError)) {
            return;
          }
          // The refusal's own error box follows; say why its source is not shown instead.
          console.warn(
            "metabrowser markdown: the refused document's source could not be read",
            sourceError,
          );
        }
      }
      if (!disposed) {
        container.innerHTML = renderKpressError(error, mb);
      }
    }
  }
  const ready = render();
  return Object.freeze({ dispose, ready });
}

/** @param {unknown} value */
function isPrimaryPreparation(value) {
  if (!value || typeof value !== "object") {
    return false;
  }
  const result = /** @type {Record<string, unknown>} */ (value);
  return (
    typeof result.changed === "boolean" &&
    typeof result.complete === "boolean" &&
    Array.isArray(result.diagnostics) &&
    (result.source === null || typeof result.source === "string") &&
    (!result.changed || typeof result.source === "string")
  );
}

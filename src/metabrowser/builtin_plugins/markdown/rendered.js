import { inertArticle, placeRendered, wireInertToc } from "./inert-render.js";
import { enhanceRenderedLinks } from "./link-enhancer.js";
import { acquireMarkdownWorkerClient } from "./markdown-worker-client.js";
import { initTocWithIntersectionFallback } from "./toc-intersection-fallback.js";
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
  return `<details class="kpress-frontmatter metabrowser-kpress-diagnostics kpress-no-print"><summary class="section-disclosure-trigger">Diagnostics</summary><dl>${rows}</dl></details>`;
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

/** @param {HTMLElement} container @param {Array<unknown>} diagnostics @param {MetabrowserPublicSdk} mb */
export function injectDiagnostics(container, diagnostics, mb) {
  const node = buildDiagnosticsNode(diagnostics, mb);
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

/** @param {unknown} error @param {MetabrowserPublicSdk} mb */
export function renderKpressError(error, mb) {
  const value =
    error && typeof error === "object" ? /** @type {Record<string, unknown>} */ (error) : {};
  const payload =
    value.payload && typeof value.payload === "object"
      ? /** @type {Record<string, unknown>} */ (value.payload)
      : {};
  const diagnostics = Array.isArray(payload.diagnostics) ? payload.diagnostics : [];
  const detail = payload.detail || (error instanceof Error ? error.message : "");
  const message = `${payload.error || "KPress render failed"}${detail ? `: ${detail}` : ""}`;
  return `<div class="notice metabrowser-kpress-render-error" data-severity="error" role="alert"><strong>Could not render this document.</strong><pre class="metabrowser-kpress-error-detail">${mb.escapeHtml(String(message))}</pre>${renderKpressDiagnosticsHtml(diagnostics, mb.escapeHtml)}</div>`;
}

/**
 * @param {HTMLElement} container
 * @param {{path?: string, raw?: unknown}} ctx
 * @param {MetabrowserPublicSdk} mb
 * @param {{signal?: AbortSignal, includeToc?: "auto" | "on" | "off", workerClient?: import("./markdown-worker-client.js").MarkdownWorkerRunner}} [options]
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
  const dispose = () => {
    if (disposed) {
      return;
    }
    disposed = true;
    options.signal?.removeEventListener("abort", abort);
    controller.abort();
    if (ownsWorkerClient) {
      workerClient.dispose();
    }
    disposeLinks?.();
    disposeLinks = null;
    disposeToc?.();
    disposeToc = null;
  };

  container.classList.add("metabrowser-kpress-host");
  container.innerHTML =
    '<div class="loading mb-delayed-loading"><div class="spinner"></div>' +
    '<span class="sr-only">Loading document…</span></div>';
  async function render() {
    try {
      const raw =
        ctx.raw && typeof ctx.raw === "object"
          ? /** @type {Record<string, unknown>} */ (ctx.raw)
          : {};
      let content = typeof raw.content === "string" ? raw.content : null;
      if (raw.content_truncated === true) {
        content = await mb.fetchCompleteText(ctx, { signal: controller.signal });
      }
      /** @type {Array<unknown>} */
      const preparationDiagnostics = [];
      let wiki = null;
      if (content !== null) {
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
        sourceText: wiki?.changed ? wiki.source : undefined,
      });
      if (disposed || controller.signal.aborted) {
        return;
      }
      const path = ctx.path;
      const links = await placeRendered(
        container,
        rendered,
        mb,
        path
          ? (root) =>
              enhanceRenderedLinks(root, path, mb, {
                signal: controller.signal,
                workerClient,
                // The rendered document is its own ancestor, so a note that embeds
                // itself is a cycle at the first embed rather than the second.
                transclusionChain: Object.freeze([transclusionKey(path)]),
              })
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
      injectDiagnostics(container, diagnostics, mb);
      // An inert render's table of contents is the page's own; a trusted one's is KPress's.
      const inert = inertArticle(container);
      disposeToc = inert
        ? wireInertToc(inert)
        : initTocWithIntersectionFallback(() => mb.kpressInitToc(container));
    } catch (error) {
      if (!disposed && !mb.errors.isAbortError(error)) {
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

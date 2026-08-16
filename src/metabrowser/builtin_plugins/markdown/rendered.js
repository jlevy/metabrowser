import { enhanceRenderedLinks } from "./link_enhancer.js";
import { transclusionKey } from "./transclusion.js";
import { preprocessObsidianWiki } from "./wiki_parser.js";

let mountSequence = 0;

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
      return ["type", "message", "severity"]
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
 * @param {{signal?: AbortSignal}} [options]
 */
export function mountRenderedMarkdown(container, ctx, mb, options = {}) {
  const controller = new AbortController();
  const abort = () => controller.abort();
  if (options.signal?.aborted) {
    controller.abort();
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
    disposeLinks?.();
    disposeLinks = null;
    disposeToc?.();
    disposeToc = null;
  };

  container.classList.add("metabrowser-kpress-host");
  container.innerHTML =
    '<div class="loading mb-delayed-loading"><div class="spinner"></div>Loading document…</div>';
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
      const wiki = content !== null ? preprocessObsidianWiki(content) : null;
      const rendered = await mb.fetchKpressRender(ctx, "rendered", {
        dedupKey: `markdown-mount-${++mountSequence}`,
        profile: "document",
        signal: controller.signal,
        sourceText: wiki?.changed ? wiki.source : undefined,
      });
      if (!disposed && !controller.signal.aborted) {
        container.innerHTML = rendered.html;
        injectDiagnostics(container, rendered.diagnostics || [], mb);
        if (ctx.path) {
          disposeLinks = enhanceRenderedLinks(container, ctx.path, mb, {
            signal: controller.signal,
            // The rendered document is its own ancestor, so a note that embeds
            // itself is a cycle at the first embed rather than the second.
            transclusionChain: Object.freeze([transclusionKey(ctx.path)]),
          }).dispose;
        }
        disposeToc = mb.kpressInitToc(container);
      }
    } catch (error) {
      if (!disposed && !mb.errors.isAbortError(error)) {
        container.innerHTML = renderKpressError(error, mb);
      }
    }
  }
  void render();
  return Object.freeze({ dispose });
}

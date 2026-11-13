import { enhanceRenderedLinks } from "./link-enhancer.js";
import { acquireMarkdownWorkerClient } from "./markdown-worker-client.js";
import { placeRendered } from "./place-rendered.js";
import { initTocWithIntersectionFallback } from "./toc-intersection-fallback.js";
import { transclusionKey } from "./transclusion.js";

let mountSequence = 0;

// ── Kept renders ─────────────────────────────────────────────
//
// A rendered view asked the server for its document on every mount. Preparation puts an
// anchor before every heading, so the prepared source differs from the file and is posted
// whole -- 19 KB for README.md, 190 KB for design-system.md -- and the render comes back
// whole (research-2026-11-11-ui-apparent-performance.md). A document shown again is the
// same document, so a mount keeps the render, with what preparation said of the source,
// and a later mount of the same envelope places it with no preparation and no request.
//
// The envelope object is the first part of the key. The shell hands a mount the very
// object its file cache holds, keeps that object across a revalidation the server answers
// 304, and replaces it when the server sends a body or the cache evicts it. So a render is
// found only through the envelope the shell holds now: a changed file arrives as another
// envelope, with another identity, and never finds a render of the old one; and the renders
// of an envelope the shell dropped are dropped with it, with no call from the shell.
//
// The rest of the key is what else the render depends on: the path, the envelope's content
// identity (`mtime_hash`, a pin's blob ID), the view, the profile, the table-of-contents
// option, and which preparation made the posted source. Preparation is a pure function of
// the source, which the identity names (markdown-worker-operations.js), so naming the
// preparation names the posted source before it runs. The server's other inputs, the build
// and whether active content is on, are fixed for the page. Only a render made from the
// envelope of the file it renders is kept: a folder's README panel mounts with the folder's
// envelope, whose identity does not move when the README's content does.

// Characters kept across every envelope: the render's HTML plus the JSON of the rest.
// Measured 2026-11-11 over this repository's 269 Markdown files, each rendered by the
// server from the file as a GET (a posted, prepared source adds its heading anchors): 32 KB
// of JSON at the median, 101 KB at the 90th percentile, 244 KB at the 99th, and 3.2 MB at
// the largest. The shell's file cache holds 30 envelopes, so this keeps a render for each
// of thirty 99th-percentile documents, and one render may take a quarter of it. A count
// of characters, not bytes: V8 stores a string with any character outside Latin-1, which
// typographic quotes are, at two bytes a character (1.92 measured, review B of #368), so
// the heap this bounds is up to about 16 MiB.
export const RENDER_CACHE_BYTES = 8 * 1024 * 1024;

// The largest kept render, in characters of HTML, that a mount places in the task that
// found it. A kept render is found during the input that opened the document, so placing
// it there makes the input's first paint wait for the placement. Measured in exp-061's
// pilot series (Chrome 152, 2026-11-12) with every kept render placed that way:
// architecture.md (52,335 characters, 525 elements) and README.md (29,192) placed with no
// task over 50 ms and the input's next paint 32 ms after it, one frame later than the
// control's 16; design-system.md (211,103 characters, 2,299 elements) placed in one 80 to
// 93 ms task, and the click's next paint came 96 to 120 ms after it. The bound is the
// largest size measured with no long task; every larger render, measured or not, waits
// for the input's first paint, which shows the document being left marked pending, as a
// render fetched from the server does. The cost tracked elements as well as characters,
// which a character count only approximates.
export const KEPT_RENDER_INPUT_TASK_MAX_CHARS = 52_335;

// How long a mount waits for the input's first paint before placing a large kept render
// anyway. It is a guard, not a measured cost: a visible page paints within a frame or
// two, and a hidden one does not wait at all. Only a page hidden during the wait, whose
// frames then stop, reaches it.
const KEPT_RENDER_PAINT_WAIT_MAX_MS = 100;

/**
 * Resolve once the frame now pending has painted: a task posted from that frame's
 * animation callback runs after its paint. Resolves at once on abort, and after
 * {@link KEPT_RENDER_PAINT_WAIT_MAX_MS} when no frame comes; every timer and the frame
 * request are released when it resolves.
 *
 * @param {AbortSignal} signal
 * @returns {Promise<void>}
 */
function afterInputPaint(signal) {
  return new Promise((resolve) => {
    /** @type {ReturnType<typeof setTimeout> | null} */
    let task = null;
    /** @type {number | null} */
    let frame = null;
    let settled = false;
    const settle = () => {
      if (settled) {
        return;
      }
      settled = true;
      clearTimeout(fallback);
      if (task !== null) {
        clearTimeout(task);
      }
      if (frame !== null && typeof cancelAnimationFrame === "function") {
        cancelAnimationFrame(frame);
      }
      signal.removeEventListener("abort", settle);
      resolve();
    };
    const fallback = setTimeout(settle, KEPT_RENDER_PAINT_WAIT_MAX_MS);
    if (signal.aborted) {
      settle();
      return;
    }
    signal.addEventListener("abort", settle, { once: true });
    if (typeof requestAnimationFrame === "function") {
      frame = requestAnimationFrame(() => {
        frame = null;
        task = setTimeout(settle, 0);
      });
    }
  });
}

/**
 * Everything a render depends on beside the envelope that holds it.
 *
 * @typedef {Readonly<{path: string, identity: string, view: string, profile: string, toc: string, source: string}>} RenderRequest
 */

/** @typedef {Awaited<ReturnType<MetabrowserPublicSdk["fetchKpressRender"]>>} KpressRender */

/**
 * A kept render: the server's answer, and the preparation's own diagnostics.
 *
 * @typedef {Readonly<{rendered: KpressRender, diagnostics: ReadonlyArray<unknown>}>} KeptRender
 */

/** @param {RenderRequest} request */
function renderKey(request) {
  return JSON.stringify([
    request.path,
    request.identity,
    request.view,
    request.profile,
    request.toc,
    request.source,
  ]);
}

/** @param {KeptRender} kept */
function keptBytes(kept) {
  const { html, ...rest } = kept.rendered;
  try {
    return (
      (typeof html === "string" ? html.length : 0) +
      JSON.stringify(rest).length +
      JSON.stringify(kept.diagnostics).length
    );
  } catch {
    return Number.POSITIVE_INFINITY;
  }
}

/**
 * Renders kept by envelope, bounded by bytes and evicted least recently used first.
 *
 * Each envelope's renders hang off the envelope itself, so an envelope nothing holds takes
 * them with it. The recency list holds the envelope only weakly, so it never keeps one
 * alive, and a FinalizationRegistry takes a collected envelope's renders out of the byte
 * count when the engine reports it gone.
 *
 * A store never walks the kept renders, so it costs the same however many are kept. While
 * each store checked every kept render for a collected envelope, a lookup miss and a store
 * took 29 µs with 2 kept renders, 56 µs with 300, 1.7 ms with 1,000 and 2.3 ms with 4,000,
 * and the byte bound alone admits thousands of small renders. Without that walk they take
 * 1.5 to 7.6 µs at each of those counts (Node 24, 2026-11-12, at a load average of 14 to
 * 83, 300 steps a count; exp-082 records it).
 *
 * @param {{maxBytes?: number}} [options]
 */
export function createRenderCache(options = {}) {
  const maxBytes = options.maxBytes ?? RENDER_CACHE_BYTES;
  const maxEntryBytes = Math.floor(maxBytes / 4);
  const supported = typeof WeakRef === "function" && typeof FinalizationRegistry === "function";
  /** @type {WeakMap<object, Map<string, {kept: KeptRender, token: object}>>} */
  const byEnvelope = new WeakMap();
  /** @type {Map<object, {envelope: WeakRef<object>, key: string, bytes: number}>} */
  const recency = new Map();
  let total = 0;
  /** @type {FinalizationRegistry<object> | null} */
  const collected = supported ? new FinalizationRegistry((token) => evict(token)) : null;

  /** @param {object} token */
  function evict(token) {
    const record = recency.get(token);
    if (!record) {
      return;
    }
    recency.delete(token);
    collected?.unregister(token);
    total -= record.bytes;
    const envelope = record.envelope.deref();
    if (!envelope) {
      return;
    }
    const renders = byEnvelope.get(envelope);
    if (renders && renders.get(record.key)?.token === token) {
      renders.delete(record.key);
      if (renders.size === 0) {
        byEnvelope.delete(envelope);
      }
    }
  }

  return Object.freeze({
    /**
     * The render kept for *request* in *envelope*, or undefined.
     *
     * @param {object} envelope
     * @param {RenderRequest} request
     * @returns {KeptRender | undefined}
     */
    lookup(envelope, request) {
      const found = byEnvelope.get(envelope)?.get(renderKey(request));
      if (!found) {
        return undefined;
      }
      const record = recency.get(found.token);
      if (record) {
        recency.delete(found.token);
        recency.set(found.token, record);
      }
      return found.kept;
    },
    /**
     * Keep *kept* for *request* in *envelope*. Returns whether it was kept.
     *
     * @param {object} envelope
     * @param {RenderRequest} request
     * @param {KeptRender} kept
     */
    store(envelope, request, kept) {
      if (!supported) {
        return false;
      }
      const key = renderKey(request);
      const previous = byEnvelope.get(envelope)?.get(key);
      if (previous) {
        evict(previous.token);
      }
      const bytes = keptBytes(kept);
      if (bytes > maxEntryBytes) {
        return false;
      }
      let renders = byEnvelope.get(envelope);
      if (!renders) {
        renders = new Map();
        byEnvelope.set(envelope, renders);
      }
      const token = {};
      renders.set(key, { kept, token });
      recency.set(token, { envelope: new WeakRef(envelope), key, bytes });
      collected?.register(envelope, token, token);
      total += bytes;
      for (const oldest of recency.keys()) {
        if (total <= maxBytes) {
          break;
        }
        evict(oldest);
      }
      return true;
    },
    stats() {
      return Object.freeze({ bytes: total, entries: recency.size });
    },
  });
}

/** The page's kept renders, shared by every Markdown mount. */
export const keptRenders = createRenderCache();

/**
 * What a mount's render depends on, or null when it must not be kept.
 *
 * @param {{path?: string}} ctx
 * @param {Record<string, unknown>} envelope
 * @param {"auto" | "on" | "off" | undefined} includeToc
 * @returns {RenderRequest | null}
 */
export function primaryRenderRequest(ctx, envelope, includeToc) {
  const path = ctx.path;
  const identity = envelope.mtime_hash;
  if (
    typeof path !== "string" ||
    !path ||
    envelope.path !== path ||
    typeof identity !== "string" ||
    !identity
  ) {
    return null;
  }
  return Object.freeze({
    path,
    identity,
    view: "rendered",
    profile: "document",
    toc: includeToc ?? "auto",
    source: "prepare-primary",
  });
}

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

  container.classList.add("metabrowser-kpress-host", "metabrowser-markdown-document");
  container.innerHTML =
    '<div class="loading mb-delayed-loading"><div class="spinner"></div>' +
    '<span class="sr-only">Loading document…</span></div>';
  /**
   * Prepare the source and ask the server to render it, keeping the render for *request*.
   *
   * @param {Record<string, unknown>} raw
   * @param {RenderRequest | null} request
   * @returns {Promise<KeptRender>}
   */
  async function prepareAndRender(raw, request) {
    let content = typeof raw.content === "string" ? raw.content : null;
    if (raw.content_truncated === true) {
      content = await mb.fetchCompleteText(ctx, { signal: controller.signal });
    }
    /** @type {Array<unknown>} */
    const diagnostics = [];
    let wiki = null;
    let prepared = true;
    if (content !== null) {
      // Wiki preprocessing is an enhancement. If the worker cannot load or
      // fails, render the authored Markdown and say what is missing rather
      // than replacing the whole document with an error.
      try {
        const preparation = await workerClient.run(
          "prepare-primary",
          Object.freeze({ source: content }),
          { signal: controller.signal },
        );
        if (!isPrimaryPreparation(preparation)) {
          throw new TypeError("Markdown worker returned an invalid primary preparation");
        }
        wiki = preparation;
        diagnostics.push(...wiki.diagnostics);
      } catch (error) {
        if (mb.errors.isAbortError(error) || controller.signal.aborted) {
          throw error;
        }
        prepared = false;
        diagnostics.push(MARKDOWN_PREPROCESSING_UNAVAILABLE_DIAGNOSTIC);
      }
    }
    const rendered = await mb.fetchKpressRender(ctx, "rendered", {
      dedupKey: `markdown-mount-${++mountSequence}`,
      profile: "document",
      includeToc: options.includeToc,
      signal: controller.signal,
      sourceText: wiki?.changed ? wiki.source : undefined,
    });
    const kept = Object.freeze({ rendered, diagnostics: Object.freeze(diagnostics) });
    // A render made without its preparation is the authored document with a warning, for
    // one failure that the next mount may not repeat; it is shown and not kept.
    if (request && prepared) {
      keptRenders.store(raw, request, kept);
    }
    return kept;
  }

  /** @param {KpressRender} rendered */
  async function ensureKeptAssets(rendered) {
    // The first mount loaded these through fetchKpressRender, and a load is once a page;
    // asking again costs nothing then and covers a render kept by anything else.
    if (typeof mb.loadKpressAssets !== "function" || !rendered.assets) {
      return;
    }
    try {
      await mb.loadKpressAssets(rendered.assets);
    } catch (error) {
      console.warn(
        "metabrowser: KPress document rendered with one or more unavailable assets",
        error,
      );
    }
  }

  async function render() {
    try {
      const raw =
        ctx.raw && typeof ctx.raw === "object"
          ? /** @type {Record<string, unknown>} */ (ctx.raw)
          : {};
      const request = primaryRenderRequest(ctx, raw, options.includeToc);
      const found = request ? keptRenders.lookup(raw, request) : undefined;
      if (found) {
        // A hidden page paints nothing a wait could protect, and its frames do not run.
        if (
          found.rendered.html.length > KEPT_RENDER_INPUT_TASK_MAX_CHARS &&
          globalThis.document?.visibilityState !== "hidden"
        ) {
          await afterInputPaint(controller.signal);
        }
        await ensureKeptAssets(found.rendered);
      }
      const { rendered, diagnostics: preparationDiagnostics } =
        found ?? (await prepareAndRender(raw, request));
      if (disposed || controller.signal.aborted) {
        return;
      }
      const path = ctx.path;
      const { enhanced: links, inert: inertRender } = await placeRendered(
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
      const diagnostics = [...preparationDiagnostics, ...(rendered.diagnostics || [])];
      if (links) {
        disposeLinks = links.dispose;
        if (links.admissionTruncated) {
          diagnostics.push(MARKDOWN_LINK_LIMIT_DIAGNOSTIC);
        }
      }
      injectDiagnostics(container, diagnostics, mb);
      // An inert render's table of contents is the page's own; a trusted one's is KPress's.
      const inert = inertRender?.inertArticle(container);
      disposeToc =
        inertRender && inert
          ? inertRender.wireInertToc(inert, {
              open: (fragment) => {
                if (path) {
                  void mb.navigation.open({ path, fragment }).catch((error) => {
                    console.warn("Could not open the table of contents entry", error);
                  });
                }
              },
            })
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

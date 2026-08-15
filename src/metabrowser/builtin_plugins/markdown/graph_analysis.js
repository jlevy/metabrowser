import { localizeGithubUrl } from "./github_localizer.js";
import { scanMarkdownLinks } from "./link_scanner.js";
import { resolveStandardTarget } from "./links.js";
import { resolvePublishedRoute } from "./project_adapters.js";
import { resolveWikiTarget } from "./wiki_resolver.js";

/** Bounds documents read during one graph analysis. */
const MAX_GRAPH_FILES = 1000;
/** Bounds total authored links resolved during one graph analysis. */
const MAX_GRAPH_LINKS = 10_000;
/** Bounds aggregate UTF-8 source read during one graph analysis. */
const MAX_GRAPH_SOURCE_BYTES = 16 * 1024 * 1024;
/** Bounds catalog entries inspected before analysis. */
const MAX_GRAPH_CATALOG_FILES = 500_000;

/** @typedef {Readonly<{complete: boolean, files: ReadonlyArray<unknown>}>} CatalogSnapshot */
/** @typedef {Readonly<{action: "navigate" | "embed", authoredTarget: string, syntax: "markdown" | "html" | "wiki"}>} ScannedLink */
/** @typedef {Readonly<{branch: string | null, host: string, name: string, owner: string, revision: string, served_prefix: string}>} RepositoryContext */
/** @typedef {Readonly<{maxFiles?: number, maxLinks?: number, maxSourceBytes?: number}>} GraphLimits */
/** @typedef {{snapshot: CatalogSnapshot, readText: (target: Readonly<{path: string}>, options: {signal?: AbortSignal}) => Promise<string>, repository?: RepositoryContext | null, signal?: AbortSignal, limits?: GraphLimits}} GraphOptions */

/**
 * Analyze one immutable catalog snapshot without subscribing to later mutations.
 *
 * @param {unknown} options
 */
export async function analyzeMarkdownGraph(options) {
  const value = validateOptions(options);
  const catalogPaths = boundedCatalogPaths(value.snapshot.files);
  if (catalogPaths === null) {
    return emptyGraph(false, [diagnostic("catalog-limit")]);
  }
  const fileSet = new Set(catalogPaths);
  const markdownPaths = [...fileSet].filter((path) => path.toLowerCase().endsWith(".md")).sort();
  const maxFiles = boundedLimit(value.limits?.maxFiles, MAX_GRAPH_FILES);
  const maxLinks = boundedLimit(value.limits?.maxLinks, MAX_GRAPH_LINKS);
  const maxSourceBytes = boundedLimit(value.limits?.maxSourceBytes, MAX_GRAPH_SOURCE_BYTES);
  const selectedPaths = markdownPaths.slice(0, maxFiles);
  const diagnostics = [];
  let complete = value.snapshot.complete;
  if (!value.snapshot.complete) {
    diagnostics.push(diagnostic("catalog-incomplete"));
  }
  if (selectedPaths.length < markdownPaths.length) {
    complete = false;
    diagnostics.push(diagnostic("file-limit"));
  }

  const nodes = new Set(selectedPaths);
  const edges = [];
  const unresolved = [];
  let sourceBytes = 0;
  let linkCount = 0;

  for (const sourcePath of selectedPaths) {
    throwIfAborted(value.signal);
    let source;
    try {
      source = await value.readText(Object.freeze({ path: sourcePath }), {
        signal: value.signal,
      });
    } catch (error) {
      if (isAbortError(error, value.signal)) {
        throw error;
      }
      complete = false;
      diagnostics.push(diagnostic("source-read-failed", sourcePath));
      continue;
    }
    throwIfAborted(value.signal);
    if (typeof source !== "string") {
      complete = false;
      diagnostics.push(diagnostic("invalid-source", sourcePath));
      continue;
    }
    const bytes = new TextEncoder().encode(source).byteLength;
    if (sourceBytes + bytes > maxSourceBytes) {
      complete = false;
      diagnostics.push(diagnostic("source-byte-limit", sourcePath));
      break;
    }
    sourceBytes += bytes;

    const scanned = scanMarkdownLinks(source);
    if (!scanned.complete) {
      complete = false;
      diagnostics.push(...scanned.diagnostics.map((entry) => ({ ...entry, path: sourcePath })));
    }
    const remainingLinks = maxLinks - linkCount;
    const exceededLinkLimit = scanned.links.length > remainingLinks;
    if (exceededLinkLimit) {
      complete = false;
      diagnostics.push(diagnostic("link-limit", sourcePath));
    }
    for (const link of scanned.links.slice(0, Math.max(remainingLinks, 0))) {
      linkCount += 1;
      const resolution = resolveScannedLink(link, sourcePath, value.snapshot, value.repository);
      if (resolution.status === "external") {
        continue;
      }
      if (resolution.status === "internal") {
        if (fileSet.has(resolution.path)) {
          nodes.add(resolution.path);
          edges.push(
            Object.freeze({
              action: link.action,
              source: sourcePath,
              syntax: link.syntax,
              target: resolution.path,
              ...("fragment" in resolution && resolution.fragment
                ? { fragment: resolution.fragment }
                : {}),
            }),
          );
        } else if (!resolution.path.endsWith("/")) {
          unresolved.push(
            unresolvedLink(
              link,
              sourcePath,
              value.snapshot.complete ? "missing" : "pending",
              value.snapshot.complete ? "not-found" : "catalog-incomplete",
            ),
          );
        }
      } else {
        unresolved.push(
          unresolvedLink(
            link,
            sourcePath,
            resolution.status,
            resolution.reason,
            "candidates" in resolution ? resolution.candidates : undefined,
          ),
        );
      }
    }
    if (linkCount >= maxLinks) {
      if (!exceededLinkLimit && selectedPaths.at(-1) !== sourcePath) {
        complete = false;
        diagnostics.push(diagnostic("link-limit", sourcePath));
      }
      break;
    }
  }

  const backlinks = backlinksFor(edges);
  return Object.freeze({
    backlinks: Object.freeze(backlinks),
    complete,
    diagnostics: Object.freeze(diagnostics.map((entry) => Object.freeze(entry))),
    edges: Object.freeze(edges),
    nodes: Object.freeze([...nodes].sort().map((path) => Object.freeze({ path }))),
    sourceBytes,
    unresolved: Object.freeze(unresolved),
  });
}

/** @param {unknown} options */
function validateOptions(options) {
  if (!options || typeof options !== "object") {
    throw new TypeError("Markdown graph analysis requires options");
  }
  const value = /** @type {Record<string, unknown>} */ (options);
  const snapshot =
    value.snapshot && typeof value.snapshot === "object"
      ? /** @type {Record<string, unknown>} */ (value.snapshot)
      : null;
  if (!snapshot || typeof snapshot.complete !== "boolean" || !Array.isArray(snapshot.files)) {
    throw new TypeError("Markdown graph analysis requires a catalog snapshot");
  }
  if (typeof value.readText !== "function") {
    throw new TypeError("Markdown graph analysis requires a source reader");
  }
  if (value.limits !== undefined && (!value.limits || typeof value.limits !== "object")) {
    throw new TypeError("Markdown graph analysis limits must be an object");
  }
  return /** @type {GraphOptions} */ (value);
}

/** @param {unknown} requested @param {number} hardLimit */
function boundedLimit(requested, hardLimit) {
  if (requested === undefined) {
    return hardLimit;
  }
  if (typeof requested !== "number" || !Number.isSafeInteger(requested) || requested < 1) {
    throw new TypeError("Markdown graph limits must be positive safe integers");
  }
  return Math.min(requested, hardLimit);
}

/** @param {ReadonlyArray<unknown>} files */
function boundedCatalogPaths(files) {
  if (files.length > MAX_GRAPH_CATALOG_FILES) {
    return null;
  }
  const paths = [];
  for (const file of files) {
    const path =
      file && typeof file === "object" ? /** @type {Record<string, unknown>} */ (file).path : null;
    if (typeof path === "string" && isSafeCatalogPath(path)) {
      paths.push(path);
    }
  }
  return paths;
}

/** @param {string} path */
function isSafeCatalogPath(path) {
  return (
    path.length > 0 &&
    !path.startsWith("/") &&
    !path.endsWith("/") &&
    !path.includes("\\") &&
    !path.includes("\0") &&
    path.split("/").every((segment) => segment && segment !== "." && segment !== "..")
  );
}

/** @param {ScannedLink} link @param {string} sourcePath @param {CatalogSnapshot} snapshot @param {RepositoryContext | null | undefined} repository */
function resolveScannedLink(link, sourcePath, snapshot, repository) {
  if (link.syntax === "wiki") {
    return resolveWikiTarget(
      {
        action: link.action,
        authoredTarget: link.authoredTarget,
        sourcePath,
      },
      snapshot,
    );
  }
  const resolved = resolveStandardTarget({
    action: link.action,
    authoredTarget: link.authoredTarget,
    sourcePath,
    syntax: link.syntax,
  });
  if (resolved.status === "external") {
    return localizeGithubUrl(link.authoredTarget, repository) || resolved;
  }
  if (resolved.status !== "internal" || link.action !== "navigate") {
    return resolved;
  }
  const adapted = resolvePublishedRoute(
    { authoredTarget: link.authoredTarget, resolvedPath: resolved.path },
    snapshot,
  );
  return adapted?.status === "internal"
    ? Object.freeze({ ...resolved, path: adapted.path })
    : adapted || resolved;
}

/**
 * @param {ScannedLink} link
 * @param {string} source
 * @param {string} status
 * @param {string} reason
 * @param {ReadonlyArray<string>=} candidates
 */
function unresolvedLink(link, source, status, reason, candidates) {
  return Object.freeze({
    action: link.action,
    authoredTarget: link.authoredTarget,
    reason,
    source,
    status,
    syntax: link.syntax,
    ...(candidates ? { candidates: Object.freeze([...candidates]) } : {}),
  });
}

/** @param {Array<{source: string, target: string}>} edges */
function backlinksFor(edges) {
  const grouped = new Map();
  for (const edge of edges) {
    let sources = grouped.get(edge.target);
    if (!sources) {
      sources = new Set();
      grouped.set(edge.target, sources);
    }
    sources.add(edge.source);
  }
  return [...grouped.entries()]
    .sort(([left], [right]) => (left < right ? -1 : left > right ? 1 : 0))
    .map(([target, sources]) =>
      Object.freeze({ sources: Object.freeze([...sources].sort()), target }),
    );
}

/** @param {AbortSignal | undefined} signal */
function throwIfAborted(signal) {
  signal?.throwIfAborted();
}

/** @param {unknown} error @param {AbortSignal | undefined} signal */
function isAbortError(error, signal) {
  return (
    signal?.aborted === true ||
    (typeof DOMException !== "undefined" &&
      error instanceof DOMException &&
      error.name === "AbortError")
  );
}

/** @param {string} code @param {string=} path */
function diagnostic(code, path) {
  return Object.freeze({ code, ...(path ? { path } : {}) });
}

/** @param {boolean} complete @param {Array<object>} diagnostics */
function emptyGraph(complete, diagnostics) {
  return Object.freeze({
    backlinks: Object.freeze([]),
    complete,
    diagnostics: Object.freeze(diagnostics),
    edges: Object.freeze([]),
    nodes: Object.freeze([]),
    sourceBytes: 0,
    unresolved: Object.freeze([]),
  });
}

// Deterministic, completion-aware Obsidian wiki-link resolution.

const MAX_SOURCE_PATH_LENGTH = 8192;
const MAX_AUTHORED_TARGET_LENGTH = 16_384;
const MAX_LOOKUP_FILES = 500_000;
const MAX_LOOKUP_CANDIDATES = 4096;
const IMAGE_EXTENSIONS = new Set([
  ".avif",
  ".bmp",
  ".gif",
  ".ico",
  ".jpeg",
  ".jpg",
  ".png",
  ".svg",
  ".webp",
]);
const AUDIO_EXTENSIONS = new Set([".aac", ".flac", ".m4a", ".mp3", ".ogg", ".wav"]);
const VIDEO_EXTENSIONS = new Set([".m4v", ".mov", ".mp4", ".ogv", ".webm"]);

/**
 * @typedef {object} WikiIntent
 * @property {string} sourcePath
 * @property {string} authoredTarget
 * @property {"navigate" | "embed"} action
 * @property {string=} label
 */

/**
 * Resolve a parsed wiki target against one immutable known-file snapshot.
 *
 * Exact paths are usable before the inventory finishes. Basename and suffix fallback
 * remain pending until completeness proves that a currently unique match is truly
 * unique.
 *
 * @param {unknown} intent
 * @param {unknown} snapshot
 */
export function resolveWikiTarget(intent, snapshot) {
  const value = validateIntent(intent);
  const catalog = validateSnapshot(snapshot);
  if (value.authoredTarget.length > MAX_AUTHORED_TARGET_LENGTH) {
    return unsupported("target-too-long");
  }
  if (catalog.files.length > MAX_LOOKUP_FILES) {
    return unsupported("catalog-too-large");
  }
  if (value.authoredTarget.includes("\\")) {
    return unsafe("backslash-path");
  }
  if (value.authoredTarget.includes("\0")) {
    return unsafe("nul-byte");
  }

  const parsed = parseWikiTarget(value.authoredTarget);
  if ("status" in parsed) {
    return parsed;
  }
  const fragment = locationFragment(parsed.location);
  if (typeof fragment !== "string" && fragment !== undefined) {
    return fragment;
  }

  if (!parsed.note) {
    return internalResult(value.sourcePath, value.action, fragment);
  }

  const notePath = appendMarkdownExtension(parsed.note);
  const sourceDirectory = value.sourcePath.split("/").slice(0, -1);
  const explicitRelative = notePath.startsWith("./") || notePath.startsWith("../");
  const explicitRoot = notePath.startsWith("/");
  const qualified = notePath.includes("/");
  let exactPath;
  if (explicitRelative) {
    exactPath = normalizeWikiPath(sourceDirectory, notePath);
  } else {
    exactPath = normalizeWikiPath([], explicitRoot ? notePath.slice(1) : notePath);
  }
  if (typeof exactPath !== "string") {
    return exactPath;
  }

  const files = boundedCatalogPaths(catalog.files);
  if (files === null) {
    return unsupported("too-many-candidates");
  }
  const exact = files.find((path) => path === exactPath);
  if (explicitRelative || explicitRoot) {
    if (exact) {
      return internalResult(exact, value.action, fragment);
    }
    return catalog.complete ? missing("not-found") : pending("catalog-incomplete");
  }

  if (!qualified) {
    const sourceDirectoryPath = normalizeWikiPath(sourceDirectory, notePath);
    if (typeof sourceDirectoryPath !== "string") {
      return sourceDirectoryPath;
    }
    const sourceDirectoryExact = files.find((path) => path === sourceDirectoryPath);
    if (sourceDirectoryExact) {
      return internalResult(sourceDirectoryExact, value.action, fragment);
    }
  } else if (exact) {
    return internalResult(exact, value.action, fragment);
  }

  const candidates = qualified
    ? files.filter((path) => path === exactPath || path.endsWith(`/${exactPath}`))
    : files.filter((path) => basename(path) === notePath);
  if (candidates.length > MAX_LOOKUP_CANDIDATES) {
    return unsupported("too-many-candidates");
  }
  if (!catalog.complete) {
    return pending("catalog-incomplete");
  }
  if (candidates.length === 0) {
    return missing("not-found");
  }
  if (candidates.length > 1) {
    return Object.freeze({
      status: "ambiguous",
      reason: "ambiguous-target",
      candidates: Object.freeze([...candidates]),
    });
  }
  return internalResult(candidates[0], value.action, fragment);
}

/** @param {unknown} intent @returns {Readonly<WikiIntent>} */
function validateIntent(intent) {
  if (!intent || typeof intent !== "object") {
    throw new TypeError("wiki resolver requires a WikiIntent");
  }
  const value = /** @type {Record<string, unknown>} */ (intent);
  if (value.action !== "navigate" && value.action !== "embed") {
    throw new TypeError("wiki link action must be navigate or embed");
  }
  if (typeof value.sourcePath !== "string" || typeof value.authoredTarget !== "string") {
    throw new TypeError("wiki link paths must be strings");
  }
  if (value.label !== undefined && typeof value.label !== "string") {
    throw new TypeError("wiki link label must be a string");
  }
  validateSourcePath(value.sourcePath);
  return /** @type {Readonly<WikiIntent>} */ (value);
}

/** @param {string} sourcePath */
function validateSourcePath(sourcePath) {
  if (!sourcePath || sourcePath.length > MAX_SOURCE_PATH_LENGTH) {
    throw new TypeError("wiki link source path is invalid");
  }
  if (
    sourcePath.startsWith("/") ||
    sourcePath.endsWith("/") ||
    sourcePath.includes("\\") ||
    sourcePath.includes("\0") ||
    sourcePath.split("/").some((segment) => !segment || segment === "." || segment === "..")
  ) {
    throw new TypeError("wiki link source path must identify a normalized logical file");
  }
}

/** @param {unknown} snapshot */
function validateSnapshot(snapshot) {
  if (!snapshot || typeof snapshot !== "object") {
    throw new TypeError("wiki resolver requires a catalog snapshot");
  }
  const value = /** @type {Record<string, unknown>} */ (snapshot);
  if (typeof value.complete !== "boolean" || !Array.isArray(value.files)) {
    throw new TypeError("wiki resolver requires snapshot completeness and files");
  }
  return /** @type {{complete: boolean, files: ReadonlyArray<unknown>}} */ (value);
}

/** @param {string} authoredTarget */
function parseWikiTarget(authoredTarget) {
  const separator = authoredTarget.indexOf("#");
  const note = (separator === -1 ? authoredTarget : authoredTarget.slice(0, separator)).trim();
  const location = separator === -1 ? undefined : authoredTarget.slice(separator + 1).trim();
  if (!note && !location) {
    return unsupported("empty-target");
  }
  return Object.freeze({ location: location || undefined, note });
}

/** @param {string | undefined} location */
function locationFragment(location) {
  if (!location) {
    return undefined;
  }
  if (location.startsWith("^")) {
    const block = location.slice(1);
    if (!/^[A-Za-z0-9-]+$/.test(block)) {
      return unsupported("invalid-block-id");
    }
    return `obsidian-block-${block}`;
  }
  try {
    encodeURIComponent(location);
    return `obsidian-heading-${location}`;
  } catch (_error) {
    return unsafe("invalid-unicode");
  }
}

/** @param {string} path */
function appendMarkdownExtension(path) {
  const leaf = basename(path);
  return leaf.includes(".") ? path : `${path}.md`;
}

/** @param {string[]} base @param {string} authoredPath */
function normalizeWikiPath(base, authoredPath) {
  if (!authoredPath || authoredPath.endsWith("/")) {
    return unsafe("non-file-path");
  }
  const segments = [...base];
  for (const segment of authoredPath.split("/")) {
    if (!segment) {
      return unsafe("non-canonical-path");
    }
    if (segment === ".") {
      continue;
    }
    if (segment === "..") {
      if (!segments.length) {
        return unsafe("path-escapes-served-root");
      }
      segments.pop();
      continue;
    }
    if (segment.includes("\\") || segment.includes("\0")) {
      return unsafe(segment.includes("\\") ? "backslash-path" : "nul-byte");
    }
    segments.push(segment);
  }
  return segments.join("/");
}

/** @param {ReadonlyArray<unknown>} files */
function boundedCatalogPaths(files) {
  const paths = [];
  for (const file of files) {
    if (!file || typeof file !== "object") {
      continue;
    }
    const path = /** @type {Record<string, unknown>} */ (file).path;
    if (typeof path !== "string" || !isSafeCatalogPath(path)) {
      continue;
    }
    paths.push(path);
  }
  return paths.length > MAX_LOOKUP_FILES ? null : paths;
}

/** @param {string} path */
function isSafeCatalogPath(path) {
  return (
    path.length > 0 &&
    path.length <= MAX_SOURCE_PATH_LENGTH &&
    !path.startsWith("/") &&
    !path.endsWith("/") &&
    !path.includes("\\") &&
    !path.includes("\0") &&
    path.split("/").every((segment) => segment && segment !== "." && segment !== "..")
  );
}

/** @param {string} path */
function basename(path) {
  return path.split("/").at(-1) || "";
}

/** @param {string} path @param {"navigate" | "embed"} action @param {string | undefined} fragment */
function internalResult(path, action, fragment) {
  /** @type {{status: "internal", path: string, fragment?: string, mediaKind?: "markdown" | "image" | "audio" | "video" | "resource"}} */
  const result = { status: "internal", path };
  if (fragment) {
    result.fragment = fragment;
  }
  if (action === "embed") {
    result.mediaKind = path.toLowerCase().endsWith(".md") ? "markdown" : mediaKindForPath(path);
  }
  return Object.freeze(result);
}

/** @param {string} path */
function mediaKindForPath(path) {
  const leaf = basename(path);
  const dot = leaf.lastIndexOf(".");
  const extension = dot === -1 ? "" : leaf.slice(dot).toLowerCase();
  if (IMAGE_EXTENSIONS.has(extension)) {
    return /** @type {const} */ ("image");
  }
  if (AUDIO_EXTENSIONS.has(extension)) {
    return /** @type {const} */ ("audio");
  }
  if (VIDEO_EXTENSIONS.has(extension)) {
    return /** @type {const} */ ("video");
  }
  return /** @type {const} */ ("resource");
}

/** @param {string} reason */
function pending(reason) {
  return Object.freeze({ status: /** @type {const} */ ("pending"), reason });
}

/** @param {string} reason */
function missing(reason) {
  return Object.freeze({ status: /** @type {const} */ ("missing"), reason });
}

/** @param {string} reason */
function unsafe(reason) {
  return Object.freeze({ status: /** @type {const} */ ("unsafe"), reason });
}

/** @param {string} reason */
function unsupported(reason) {
  return Object.freeze({ status: /** @type {const} */ ("unsupported"), reason });
}

// Exact, repository-relative resolution for standard Markdown and sanitized HTML links.

const MAX_SOURCE_PATH_LENGTH = 8192;
const MAX_AUTHORED_TARGET_LENGTH = 16384;
const ALLOWED_EXTERNAL_SCHEMES = new Set(["http", "https", "mailto", "tel"]);
const UNSAFE_SCHEMES = new Set(["blob", "data", "file", "javascript", "vbscript"]);
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
 * @typedef {object} LinkIntent
 * @property {"markdown" | "html"} syntax
 * @property {string} sourcePath
 * @property {string} authoredTarget
 * @property {string=} label
 * @property {"navigate" | "embed"} action
 */

/** @typedef {"image" | "audio" | "video" | "resource"} MediaKind */

/**
 * @typedef {Readonly<{status: "internal", path: string, query?: string, fragment?: string, mediaKind?: MediaKind}> | Readonly<{status: "external", url: string}> | Readonly<{status: "unsafe" | "unsupported", reason: string}>} ResolvedTarget
 */

/**
 * Resolve one standard Markdown or sanitized raw-HTML destination exactly.
 *
 * This function performs no I/O and deliberately has no inventory fallback. A safe
 * exact path remains `internal` even when it does not exist; the ordinary open flow
 * owns the resulting not-found state.
 *
 * @param {unknown} intent
 * @returns {ResolvedTarget}
 */
export function resolveStandardTarget(intent) {
  const value = validateIntent(intent);
  const authoredTarget = value.authoredTarget;
  if (authoredTarget.length > MAX_AUTHORED_TARGET_LENGTH) {
    return unsupported("target-too-long");
  }
  if (authoredTarget.includes("\\")) {
    return unsafe("backslash-path");
  }
  if (authoredTarget.includes("\0")) {
    return unsafe("nul-byte");
  }

  const external = resolveExternal(authoredTarget);
  if (external) {
    return external;
  }

  const parts = splitAuthoredTarget(authoredTarget);
  const resolvedPath = resolveLogicalPath(value.sourcePath, parts.path);
  if (typeof resolvedPath !== "string") {
    return resolvedPath;
  }

  const query = validateSerializedPart(parts.query, false);
  if (typeof query !== "string" && query !== undefined) {
    return query;
  }
  const fragment = validateSerializedPart(parts.fragment, true);
  if (typeof fragment !== "string" && fragment !== undefined) {
    return fragment;
  }

  /** @type {{status: "internal", path: string, query?: string, fragment?: string, mediaKind?: MediaKind}} */
  const resolved = { status: "internal", path: resolvedPath };
  if (query) {
    resolved.query = query;
  }
  if (fragment) {
    resolved.fragment = fragment;
  }
  if (value.action === "embed") {
    resolved.mediaKind = mediaKindForPath(resolvedPath);
  }
  return Object.freeze(resolved);
}

/** @param {unknown} intent @returns {Readonly<LinkIntent>} */
function validateIntent(intent) {
  if (!intent || typeof intent !== "object") {
    throw new TypeError("standard link resolver requires a LinkIntent");
  }
  const value = /** @type {Record<string, unknown>} */ (intent);
  if (value.syntax !== "markdown" && value.syntax !== "html") {
    throw new TypeError("standard link syntax must be markdown or html");
  }
  if (value.action !== "navigate" && value.action !== "embed") {
    throw new TypeError("standard link action must be navigate or embed");
  }
  if (typeof value.sourcePath !== "string" || typeof value.authoredTarget !== "string") {
    throw new TypeError("standard link paths must be strings");
  }
  if (value.label !== undefined && typeof value.label !== "string") {
    throw new TypeError("standard link label must be a string");
  }
  validateSourcePath(value.sourcePath);
  return /** @type {Readonly<LinkIntent>} */ (value);
}

/** @param {string} sourcePath */
function validateSourcePath(sourcePath) {
  if (!sourcePath || sourcePath.length > MAX_SOURCE_PATH_LENGTH) {
    throw new TypeError("standard link source path is invalid");
  }
  if (
    sourcePath.startsWith("/") ||
    sourcePath.endsWith("/") ||
    sourcePath.includes("\\") ||
    sourcePath.includes("\0")
  ) {
    throw new TypeError("standard link source path must identify a safe logical file");
  }
  if (sourcePath.split("/").some((segment) => !segment || segment === "." || segment === "..")) {
    throw new TypeError("standard link source path must already be normalized");
  }
}

/** @param {string} authoredTarget @returns {ResolvedTarget | null} */
function resolveExternal(authoredTarget) {
  const probe = authoredTarget
    .trimStart()
    .split("")
    .filter((character) => character.charCodeAt(0) > 32)
    .join("");
  if (probe.startsWith("//")) {
    return Object.freeze({ status: "external", url: authoredTarget });
  }
  const schemeMatch = /^([A-Za-z][A-Za-z0-9+.-]*):/.exec(probe);
  if (!schemeMatch) {
    return null;
  }
  const scheme = schemeMatch[1].toLowerCase();
  if (ALLOWED_EXTERNAL_SCHEMES.has(scheme)) {
    return Object.freeze({ status: "external", url: authoredTarget });
  }
  return UNSAFE_SCHEMES.has(scheme) ? unsafe("unsafe-scheme") : unsupported("unsupported-scheme");
}

/** @param {string} authoredTarget */
function splitAuthoredTarget(authoredTarget) {
  const fragmentIndex = authoredTarget.indexOf("#");
  const beforeFragment =
    fragmentIndex === -1 ? authoredTarget : authoredTarget.slice(0, fragmentIndex);
  const fragment = fragmentIndex === -1 ? undefined : authoredTarget.slice(fragmentIndex + 1);
  const queryIndex = beforeFragment.indexOf("?");
  return Object.freeze({
    path: queryIndex === -1 ? beforeFragment : beforeFragment.slice(0, queryIndex),
    query: queryIndex === -1 ? undefined : beforeFragment.slice(queryIndex + 1),
    fragment,
  });
}

/**
 * @param {string} sourcePath
 * @param {string} encodedPath
 * @returns {string | ResolvedTarget}
 */
function resolveLogicalPath(sourcePath, encodedPath) {
  if (!encodedPath) {
    return sourcePath;
  }
  const rooted = encodedPath.startsWith("/");
  const relative = rooted ? encodedPath.slice(1) : encodedPath;
  if (!relative) {
    return "";
  }
  const trailingSlash = relative.endsWith("/");
  const segments = rooted ? [] : sourcePath.split("/").slice(0, -1);
  const rawSegments = relative.split("/");
  for (const [index, rawSegment] of rawSegments.entries()) {
    if (!rawSegment) {
      if (trailingSlash && index === rawSegments.length - 1) {
        continue;
      }
      return unsafe("non-canonical-path");
    }
    let segment;
    try {
      segment = decodeURIComponent(rawSegment);
    } catch (_error) {
      return unsafe("malformed-percent-escape");
    }
    if (segment.includes("/")) {
      return unsafe("encoded-path-separator");
    }
    if (segment.includes("\\")) {
      return unsafe("backslash-path");
    }
    if (segment.includes("\0")) {
      return unsafe("nul-byte");
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
    segments.push(segment);
  }
  const path = segments.join("/");
  return trailingSlash && path ? `${path}/` : path;
}

/**
 * @param {string | undefined} serialized
 * @param {boolean} decode
 * @returns {string | undefined | ResolvedTarget}
 */
function validateSerializedPart(serialized, decode) {
  if (!serialized) {
    return undefined;
  }
  let decoded;
  try {
    decoded = decodeURIComponent(serialized);
  } catch (_error) {
    return unsafe("malformed-percent-escape");
  }
  if (decoded.includes("\0")) {
    return unsafe("nul-byte");
  }
  return decode ? decoded : serialized;
}

/** @param {string} path @returns {MediaKind} */
function mediaKindForPath(path) {
  const basename = path.replace(/\/$/, "").split("/").at(-1) || "";
  const dotIndex = basename.lastIndexOf(".");
  const extension = dotIndex === -1 ? "" : basename.slice(dotIndex).toLowerCase();
  if (IMAGE_EXTENSIONS.has(extension)) {
    return "image";
  }
  if (AUDIO_EXTENSIONS.has(extension)) {
    return "audio";
  }
  if (VIDEO_EXTENSIONS.has(extension)) {
    return "video";
  }
  return "resource";
}

/** @param {string} reason @returns {ResolvedTarget} */
function unsafe(reason) {
  return Object.freeze({ status: "unsafe", reason });
}

/** @param {string} reason @returns {ResolvedTarget} */
function unsupported(reason) {
  return Object.freeze({ status: "unsupported", reason });
}

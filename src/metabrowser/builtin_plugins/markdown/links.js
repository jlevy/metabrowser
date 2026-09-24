// Exact, repository-relative resolution for standard Markdown and sanitized HTML links.

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
 * @property {"filesystem" | "git_revision"=} sourceKind
 */

/** @typedef {"image" | "audio" | "video" | "resource"} MediaKind */
/** @typedef {Readonly<{completePrefix: boolean, reverseSlashes: readonly number[], sourcePath: string, sourceKind: "filesystem" | "git_revision"}>} PreparedSourcePath */
/** @typedef {Readonly<{done: boolean, pathVisits: number, result: PreparedSourcePath | null}>} SourcePathStep */
/** @typedef {Readonly<{step: (maxPathVisits: number) => SourcePathStep}>} TrustedSourcePathContext */

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
  const value = validateIntentShape(intent);
  return resolvePreparedTarget(value, prepareSourcePath(value.sourcePath, value.sourceKind));
}

/**
 * Validate and decompose a provider-admitted source identity once for every link in
 * one rendered document. Literal percent sequences remain inventory identities;
 * only authored URL segments are decoded and re-escaped.
 *
 * @param {string} sourcePath
 * @param {"filesystem" | "git_revision"=} sourceKind
 */
export function createStandardLinkResolutionContext(sourcePath, sourceKind) {
  const preparedSource = prepareSourcePath(sourcePath, sourceKind);
  return strictStandardLinkResolutionContext(sourcePath, preparedSource);
}

/**
 * Create a context for a source identity already admitted by the core catalog.
 * This is the browser/plugin boundary: core owns canonical validation, so a view
 * must not rescan an arbitrarily long provider string once for every renderer.
 * Direct callers use `createStandardLinkResolutionContext`, which remains strict.
 *
 * Source paths no longer than the already-supported authored-target envelope are
 * prepared synchronously, preserving ordinary mount behavior. Longer provider
 * identities expose only the cooperative `begin()` path and are prepared by the
 * root reconciliation coordinator.
 *
 * @param {string} sourcePath
 * @param {TrustedSourcePathContext=} sourceContext
 * @param {"filesystem" | "git_revision"=} sourceKind
 */
export function createTrustedStandardLinkResolutionContext(sourcePath, sourceContext, sourceKind) {
  if (typeof sourcePath !== "string" || !sourcePath) {
    throw new TypeError("standard link source path is invalid");
  }
  const immediateSource =
    sourcePath.length <= MAX_AUTHORED_TARGET_LENGTH
      ? prepareTrustedSourcePath(sourcePath, sourceKind)
      : null;
  return Object.freeze({
    /** @param {unknown} intent */
    begin(intent) {
      return beginTrustedResolution(validateIntentShape(intent), immediateSource, sourceContext);
    },
    canResolveSynchronously: immediateSource !== null,
    /** @param {unknown} intent */
    resolve(intent) {
      if (!immediateSource) {
        throw new Error("provider-long standard link resolution must be stepped cooperatively");
      }
      return resolvePreparedTarget(validateIntentShape(intent), immediateSource);
    },
  });
}

/** @param {string} sourcePath @param {PreparedSourcePath} preparedSource */
function strictStandardLinkResolutionContext(sourcePath, preparedSource) {
  return Object.freeze({
    /** @param {unknown} intent */
    resolve(intent) {
      const value = validateIntentShape(intent);
      if (value.sourcePath !== sourcePath) {
        throw new TypeError("standard link context source path does not match intent");
      }
      return resolvePreparedTarget(value, preparedSource);
    },
  });
}

/**
 * @param {Readonly<LinkIntent>} value
 * @param {PreparedSourcePath | null} immediateSource
 * @param {TrustedSourcePathContext | undefined} sourceContext
 */
function beginTrustedResolution(value, immediateSource, sourceContext) {
  let preparedSource = immediateSource;
  /** @type {ResolvedTarget | null} */
  let terminal = sourceIndependentResolution(value);
  return Object.freeze({
    /** @param {number} maxPathVisits */
    step(maxPathVisits) {
      const limit = positiveInteger(maxPathVisits);
      if (terminal) {
        return Object.freeze({ done: true, pathVisits: 0, result: terminal });
      }
      if (!preparedSource) {
        if (!sourceContext) {
          throw new Error("provider-long standard link resolution requires a source context");
        }
        const sourceStep = sourceContext.step(limit);
        if (!sourceStep.done || !sourceStep.result) {
          return Object.freeze({
            done: false,
            pathVisits: sourceStep.pathVisits,
            result: null,
          });
        }
        preparedSource = sourceStep.result;
        terminal = resolvePreparedTarget(value, preparedSource);
        return Object.freeze({
          done: true,
          pathVisits: sourceStep.pathVisits,
          result: terminal,
        });
      }
      terminal = resolvePreparedTarget(value, preparedSource);
      return Object.freeze({ done: true, pathVisits: 0, result: terminal });
    },
  });
}

/** @param {Readonly<LinkIntent>} value */
function sourceIndependentResolution(value) {
  const validation = validateAuthoredTarget(value.authoredTarget);
  if (validation) {
    return validation;
  }
  const external = resolveExternal(value.authoredTarget);
  if (external) {
    return external;
  }
  const path = splitAuthoredTarget(value.authoredTarget).path;
  return !path || path.startsWith("/") ? resolvePreparedTarget(value, null) : null;
}

/** @param {Readonly<LinkIntent>} value @param {PreparedSourcePath | null} preparedSource */
function resolvePreparedTarget(value, preparedSource) {
  const authoredTarget = value.authoredTarget;
  const validation = validateAuthoredTarget(authoredTarget);
  if (validation) {
    return validation;
  }

  const external = resolveExternal(authoredTarget);
  if (external) {
    return external;
  }

  const parts = splitAuthoredTarget(authoredTarget);
  const resolvedPath = resolveLogicalPath(value.sourcePath, preparedSource, parts.path);
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
    resolved.mediaKind = mediaKindForAuthoredPath(parts.path);
  }
  return Object.freeze(resolved);
}

/** @param {unknown} intent @returns {Readonly<LinkIntent>} */
function validateIntentShape(intent) {
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
  if (
    value.sourceKind !== undefined &&
    value.sourceKind !== "filesystem" &&
    value.sourceKind !== "git_revision"
  ) {
    throw new TypeError("standard link sourceKind must be filesystem or git_revision");
  }
  return /** @type {Readonly<LinkIntent>} */ (value);
}

/** @param {string} authoredTarget @returns {ResolvedTarget | null} */
function validateAuthoredTarget(authoredTarget) {
  if (authoredTarget.length > MAX_AUTHORED_TARGET_LENGTH) {
    return unsupported("target-too-long");
  }
  if (authoredTarget.includes("\\")) {
    return unsafe("backslash-path");
  }
  if (authoredTarget.includes("\0")) {
    return unsafe("nul-byte");
  }
  return null;
}

/** @param {string} sourcePath @param {"filesystem" | "git_revision"=} sourceKind @returns {PreparedSourcePath} */
function prepareSourcePath(sourcePath, sourceKind) {
  if (typeof sourcePath !== "string" || !sourcePath) {
    throw new TypeError("standard link source path is invalid");
  }
  if (sourcePath.startsWith("/") || sourcePath.endsWith("/")) {
    throw new TypeError("standard link source path must identify a safe logical file");
  }
  let segmentStart = 0;
  for (let index = 0; index < sourcePath.length; index += 1) {
    const unit = sourcePath.charCodeAt(index);
    if (unit === 0 || unit === 92) {
      throw new TypeError("standard link source path must identify a safe logical file");
    }
    if (unit >= 0xd800 && unit <= 0xdbff) {
      const following = sourcePath.charCodeAt(index + 1);
      if (following < 0xdc00 || following > 0xdfff) {
        throw new TypeError("standard link source path must identify a safe logical file");
      }
      index += 1;
      continue;
    }
    if (unit >= 0xdc00 && unit <= 0xdfff) {
      throw new TypeError("standard link source path must identify a safe logical file");
    }
    if (unit === 47) {
      if (invalidSourceSegment(sourcePath, segmentStart, index)) {
        throw new TypeError("standard link source path must already be normalized");
      }
      segmentStart = index + 1;
    }
  }
  if (invalidSourceSegment(sourcePath, segmentStart, sourcePath.length)) {
    throw new TypeError("standard link source path must already be normalized");
  }
  return prepareTrustedSourcePath(sourcePath, sourceKind);
}

/** @param {string} sourcePath @param {"filesystem" | "git_revision"=} sourceKind @returns {PreparedSourcePath} */
function prepareTrustedSourcePath(sourcePath, sourceKind) {
  const reverseSlashes = [];
  for (let index = sourcePath.length - 1; index >= 0; index -= 1) {
    if (sourcePath.charCodeAt(index) === 47) {
      reverseSlashes.push(index);
    }
  }
  return Object.freeze({
    completePrefix: true,
    reverseSlashes: Object.freeze(reverseSlashes),
    sourceKind: sourceKind === "git_revision" ? "git_revision" : "filesystem",
    sourcePath,
  });
}

/** @param {string} sourcePath @param {number} start @param {number} end */
function invalidSourceSegment(sourcePath, start, end) {
  const length = end - start;
  return (
    length === 0 ||
    (length === 1 && sourcePath.charCodeAt(start) === 46) ||
    (length === 2 && sourcePath.charCodeAt(start) === 46 && sourcePath.charCodeAt(start + 1) === 46)
  );
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
 * A decoded path segment as a served folder's inventory spells it: `%` is `%25` and, on
 * POSIX, a backslash is `%5C`.
 *
 * @param {string} segment
 */
function inventoryName(segment) {
  return segment.replaceAll("%", "%25").replaceAll("\\", "%5C");
}

/**
 * @param {string} sourcePath
 * @param {PreparedSourcePath | null} preparedSource
 * @param {string} encodedPath
 * @returns {string | ResolvedTarget}
 */
function resolveLogicalPath(sourcePath, preparedSource, encodedPath) {
  if (!encodedPath) {
    return sourcePath;
  }
  const rooted = encodedPath.startsWith("/");
  const relative = rooted ? encodedPath.slice(1) : encodedPath;
  if (!relative) {
    return "";
  }
  const trailingSlash = relative.endsWith("/");
  const gitSource = preparedSource?.sourceKind === "git_revision";
  const segments = [];
  let parentPops = 0;
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
    // An escaped backslash (`%5C`; a literal one never reaches here) names a served
    // folder's file whose POSIX name holds one, which the inventory spells `%5C`. A Git
    // pin's paths never hold one, and its routes refuse it.
    if (gitSource && segment.includes("\\")) {
      return unsafe("backslash-path");
    }
    if (segment.includes("\0")) {
      return unsafe("nul-byte");
    }
    if (segment === ".") {
      continue;
    }
    if (segment === "..") {
      if (segments.length) {
        segments.pop();
        continue;
      }
      if (rooted) {
        return unsafe("path-escapes-served-root");
      }
      parentPops += 1;
      continue;
    }
    segments.push(segment);
  }
  const authored = gitSource
    ? encodeGitPathAuthored(segments)
    : segments.map(inventoryName).join("/");
  let base = "";
  if (!rooted) {
    if (!preparedSource) {
      throw new Error("source-relative standard target lacks prepared source context");
    }
    if (parentPops < preparedSource.reverseSlashes.length) {
      base = preparedSource.sourcePath.slice(0, preparedSource.reverseSlashes[parentPops]);
    } else if (preparedSource.completePrefix) {
      if (parentPops > preparedSource.reverseSlashes.length) {
        return unsafe("path-escapes-served-root");
      }
    } else {
      throw new Error("standard source parent window was unexpectedly exhausted");
    }
  }
  const path = base && authored ? `${base}/${authored}` : base || authored;
  return trailingSlash && path ? `${path}/` : path;
}

/** @param {string} name */
function encodeGitPathSegment(name) {
  const bytes = new TextEncoder().encode(name);
  let binary = "";
  for (let i = 0; i < bytes.length; i += 1) {
    binary += String.fromCharCode(bytes[i]);
  }
  const atom = btoa(binary).replaceAll("+", "-").replaceAll("/", "_").replace(/=+$/, "");
  return `g1-${atom}`;
}

/** @param {string[]} names */
function encodeGitPathAuthored(names) {
  return names.map(encodeGitPathSegment).join("/");
}

/**
 * The GitPath wire of a slash-separated display path, keeping a trailing slash.
 *
 * @param {string} path
 */
export function gitPathWireForDisplayPath(path) {
  const trailingSlash = path.endsWith("/");
  const names = path.split("/").filter((name) => name !== "");
  const wire = encodeGitPathAuthored(names);
  return trailingSlash && wire ? `${wire}/` : wire;
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

/** @param {string} encodedPath @returns {MediaKind} */
function mediaKindForAuthoredPath(encodedPath) {
  const withoutSlash = encodedPath.endsWith("/") ? encodedPath.slice(0, -1) : encodedPath;
  const slash = withoutSlash.lastIndexOf("/");
  const rawBasename = slash === -1 ? withoutSlash : withoutSlash.slice(slash + 1);
  let basename;
  try {
    basename = decodeURIComponent(rawBasename);
  } catch (_error) {
    return "resource";
  }
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

/** @param {number} value */
function positiveInteger(value) {
  if (!Number.isFinite(value) || value < 1) {
    throw new TypeError("standard link resolution requires a positive path-visit bound");
  }
  return Math.floor(value);
}

/** @param {string} reason @returns {ResolvedTarget} */
function unsafe(reason) {
  return Object.freeze({ status: "unsafe", reason });
}

/** @param {string} reason @returns {ResolvedTarget} */
function unsupported(reason) {
  return Object.freeze({ status: "unsupported", reason });
}

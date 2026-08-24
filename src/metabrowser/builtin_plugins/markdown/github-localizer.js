/** Bounds URL parsing work for one authored link. */
const MAX_GITHUB_URL_LENGTH = 16 * 1024;
/** Bounds reference and path comparison work for one authored link. */
const MAX_PATH_SEGMENTS = 512;
const FULL_REVISION = /^[0-9a-f]{40}$/i;

/** @typedef {Readonly<{branch: string | null, host: string, name: string, owner: string, revision: string, served_prefix: string}>} RepositoryContext */

/**
 * Localize a GitHub blob or tree URL only when repository identity proves that
 * it denotes the exact working tree currently served by Metabrowser.
 *
 * @param {string} authoredTarget
 * @param {RepositoryContext | null | undefined} context
 * @returns {(Readonly<{status: "internal", path: string, query?: string, fragment?: string, localization: "revision" | "working-tree"}>) | null}
 */
export function localizeGithubUrl(authoredTarget, context) {
  if (
    typeof authoredTarget !== "string" ||
    authoredTarget.length > MAX_GITHUB_URL_LENGTH ||
    !isRepositoryContext(context)
  ) {
    return null;
  }

  let url;
  try {
    url = new URL(authoredTarget);
  } catch (_error) {
    return null;
  }
  if (
    (url.protocol !== "https:" && url.protocol !== "http:") ||
    url.username ||
    url.password ||
    url.port ||
    url.hostname.toLowerCase() !== context.host.toLowerCase()
  ) {
    return null;
  }

  const segments = decodeSegments(url.pathname);
  if (
    !segments ||
    segments.length < 4 ||
    !sameIdentity(segments[0], context.owner) ||
    !sameIdentity(segments[1].replace(/\.git$/i, ""), context.name) ||
    (segments[2] !== "blob" && segments[2] !== "tree")
  ) {
    return null;
  }

  const matched = matchVerifiedReference(segments.slice(3), context);
  if (!matched) {
    return null;
  }
  const repositoryPath = matched.remaining;
  const servedPrefix = safeRelativeSegments(context.served_prefix);
  if (!servedPrefix || !startsWithSegments(repositoryPath, servedPrefix)) {
    return null;
  }
  const localSegments = repositoryPath.slice(servedPrefix.length);
  if (localSegments.length === 0) {
    return null;
  }

  let path = localSegments.join("/");
  if (segments[2] === "tree") {
    path += "/";
  }
  let fragment = null;
  if (url.hash.length > 1) {
    fragment = safeDecode(url.hash.slice(1));
    if (fragment === null || fragment.includes("\0")) {
      return null;
    }
  }
  const target = {
    localization: matched.localization,
    path,
    status: /** @type {const} */ ("internal"),
  };
  if (url.search.length > 1) {
    Object.assign(target, { query: url.search.slice(1) });
  }
  if (fragment) {
    Object.assign(target, { fragment });
  }
  return Object.freeze(target);
}

/** @param {unknown} value @returns {value is RepositoryContext} */
function isRepositoryContext(value) {
  if (!value || typeof value !== "object") {
    return false;
  }
  const context = /** @type {Record<string, unknown>} */ (value);
  return (
    typeof context.host === "string" &&
    context.host.toLowerCase() === "github.com" &&
    typeof context.owner === "string" &&
    context.owner.length > 0 &&
    typeof context.name === "string" &&
    context.name.length > 0 &&
    typeof context.revision === "string" &&
    FULL_REVISION.test(context.revision) &&
    (context.branch === null || typeof context.branch === "string") &&
    typeof context.served_prefix === "string"
  );
}

/**
 * @param {Array<string>} referenceAndPath
 * @param {Readonly<{branch: string | null, revision: string}>} context
 */
function matchVerifiedReference(referenceAndPath, context) {
  if (
    referenceAndPath.length > 1 &&
    FULL_REVISION.test(referenceAndPath[0]) &&
    referenceAndPath[0].toLowerCase() === context.revision.toLowerCase()
  ) {
    return {
      localization: /** @type {const} */ ("revision"),
      remaining: referenceAndPath.slice(1),
    };
  }
  const branch = context.branch ? safeRelativeSegments(context.branch) : null;
  if (
    branch &&
    branch.length > 0 &&
    referenceAndPath.length > branch.length &&
    startsWithSegments(referenceAndPath, branch)
  ) {
    return {
      localization: /** @type {const} */ ("working-tree"),
      remaining: referenceAndPath.slice(branch.length),
    };
  }
  return null;
}

/** @param {string} pathname */
function decodeSegments(pathname) {
  const raw = pathname.split("/").slice(1);
  if (raw.at(-1) === "") {
    raw.pop();
  }
  if (raw.length > MAX_PATH_SEGMENTS || raw.some((segment) => segment.length === 0)) {
    return null;
  }
  const decoded = [];
  for (const segment of raw) {
    const value = safeDecode(segment);
    if (
      value === null ||
      value === "." ||
      value === ".." ||
      value.includes("/") ||
      value.includes("\\") ||
      value.includes("\0")
    ) {
      return null;
    }
    decoded.push(value);
  }
  return decoded;
}

/** @param {string} path */
function safeRelativeSegments(path) {
  if (path === "") {
    return [];
  }
  const segments = path.split("/");
  if (
    segments.length > MAX_PATH_SEGMENTS ||
    segments.some(
      (segment) =>
        !segment ||
        segment === "." ||
        segment === ".." ||
        segment.includes("\\") ||
        segment.includes("\0"),
    )
  ) {
    return null;
  }
  return segments;
}

/** @param {string} value */
function safeDecode(value) {
  try {
    return decodeURIComponent(value);
  } catch (_error) {
    return null;
  }
}

/** @param {Array<string>} value @param {Array<string>} prefix */
function startsWithSegments(value, prefix) {
  return prefix.every((segment, index) => value[index] === segment);
}

/** @param {string} left @param {string} right */
function sameIdentity(left, right) {
  return left.toLowerCase() === right.toLowerCase();
}

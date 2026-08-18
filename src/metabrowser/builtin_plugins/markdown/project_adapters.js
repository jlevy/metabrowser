// Config-gated source lookup for published static-site routes.

const MAX_CATALOG_FILES = 500_000;
const MAX_ROUTE_CHARACTERS = 16_384;
const MAX_ADAPTER_CANDIDATES = 32;

const ADAPTERS = Object.freeze([
  Object.freeze({
    configFiles: Object.freeze(["mkdocs.yml", "mkdocs.yaml"]),
    id: "mkdocs",
  }),
  Object.freeze({
    configFiles: Object.freeze([
      "docusaurus.config.js",
      "docusaurus.config.ts",
      "docusaurus.config.mjs",
      "docusaurus.config.cjs",
    ]),
    id: "docusaurus",
  }),
  Object.freeze({ configFiles: Object.freeze(["_config.yml"]), id: "jekyll" }),
]);

/**
 * Resolve one published root route to a source document after exact lookup fails.
 *
 * A `null` result means ordinary exact Markdown behavior remains authoritative.
 *
 * @param {unknown} intent
 * @param {unknown} snapshot
 */
export function resolvePublishedRoute(intent, snapshot) {
  const value = validateIntent(intent);
  const catalog = validateSnapshot(snapshot);
  if (!isPublishedRoute(value.authoredTarget) || catalog.files.length > MAX_CATALOG_FILES) {
    return null;
  }

  const paths = safeCatalogPaths(catalog.files);
  if (exactTargetExists(value.resolvedPath, paths)) {
    return null;
  }
  const configured = ADAPTERS.filter((adapter) =>
    adapter.configFiles.some((configPath) => paths.has(configPath)),
  );
  if (configured.length === 0) {
    return null;
  }

  const route = decodedPublishedRoute(value.authoredTarget);
  if (route === null) {
    return null;
  }
  /** @type {Map<string, string>} */
  const matches = new Map();
  let candidateCount = 0;
  for (const adapter of configured) {
    for (const candidate of sourceCandidates(adapter.id, route)) {
      candidateCount += 1;
      if (candidateCount > MAX_ADAPTER_CANDIDATES) {
        return Object.freeze({ reason: "too-many-adapter-candidates", status: "unsupported" });
      }
      if (paths.has(candidate) && !matches.has(candidate)) {
        matches.set(candidate, adapter.id);
      }
    }
  }
  if (matches.size === 1) {
    const [path, adapter] = /** @type {[string, string]} */ (matches.entries().next().value);
    return Object.freeze({ adapter, path, status: /** @type {const} */ ("internal") });
  }
  if (matches.size > 1) {
    return Object.freeze({
      candidates: Object.freeze([...matches.keys()]),
      reason: "ambiguous-published-route",
      status: /** @type {const} */ ("ambiguous"),
    });
  }
  return catalog.complete
    ? null
    : Object.freeze({ reason: "catalog-incomplete", status: /** @type {const} */ ("pending") });
}

/** @param {unknown} intent */
function validateIntent(intent) {
  if (!intent || typeof intent !== "object") {
    throw new TypeError("published-route resolver requires an intent");
  }
  const value = /** @type {Record<string, unknown>} */ (intent);
  if (typeof value.authoredTarget !== "string" || typeof value.resolvedPath !== "string") {
    throw new TypeError("published-route paths must be strings");
  }
  if (
    value.authoredTarget.length > MAX_ROUTE_CHARACTERS ||
    value.resolvedPath.length > MAX_ROUTE_CHARACTERS
  ) {
    throw new TypeError("published-route path is too long");
  }
  return /** @type {Readonly<{authoredTarget: string, resolvedPath: string}>} */ (value);
}

/** @param {unknown} snapshot */
function validateSnapshot(snapshot) {
  if (!snapshot || typeof snapshot !== "object") {
    throw new TypeError("published-route resolver requires a catalog snapshot");
  }
  const value = /** @type {Record<string, unknown>} */ (snapshot);
  if (typeof value.complete !== "boolean" || !Array.isArray(value.files)) {
    throw new TypeError("published-route snapshot requires completeness and files");
  }
  return /** @type {{complete: boolean, files: ReadonlyArray<unknown>}} */ (value);
}

/** @param {string} authoredTarget */
function isPublishedRoute(authoredTarget) {
  const path = authoredTarget.split("#", 1)[0].split("?", 1)[0];
  if (!path.startsWith("/")) {
    return false;
  }
  const leaf = path.replace(/\/$/, "").split("/").at(-1) || "";
  return path.endsWith("/") || !leaf.includes(".");
}

/** @param {string} authoredTarget */
function decodedPublishedRoute(authoredTarget) {
  const encoded = authoredTarget.split("#", 1)[0].split("?", 1)[0];
  const trimmed = encoded.replace(/^\/+|\/+$/g, "");
  try {
    const decoded = trimmed
      .split("/")
      .filter(Boolean)
      .map((segment) => decodeURIComponent(segment));
    return decoded.some(
      (segment) =>
        !segment ||
        segment === "." ||
        segment === ".." ||
        segment.includes("/") ||
        segment.includes("\\") ||
        segment.includes("\0"),
    )
      ? null
      : decoded.join("/");
  } catch (_error) {
    return null;
  }
}

/** @param {ReadonlyArray<unknown>} files */
function safeCatalogPaths(files) {
  const paths = new Set();
  for (const file of files) {
    if (!file || typeof file !== "object") {
      continue;
    }
    const path = /** @type {Record<string, unknown>} */ (file).path;
    if (typeof path === "string" && isSafePath(path)) {
      paths.add(path);
    }
  }
  return paths;
}

/** @param {string} path */
function isSafePath(path) {
  return (
    path.length > 0 &&
    path.length <= MAX_ROUTE_CHARACTERS &&
    !path.startsWith("/") &&
    !path.endsWith("/") &&
    !path.includes("\\") &&
    !path.includes("\0") &&
    path.split("/").every((segment) => segment && segment !== "." && segment !== "..")
  );
}

/** @param {string} resolvedPath @param {ReadonlySet<string>} paths */
function exactTargetExists(resolvedPath, paths) {
  if (!resolvedPath) {
    return true;
  }
  if (!resolvedPath.endsWith("/")) {
    return paths.has(resolvedPath);
  }
  for (const path of paths) {
    if (path.startsWith(resolvedPath)) {
      return true;
    }
  }
  return false;
}

/** @param {string} adapter @param {string} route */
function sourceCandidates(adapter, route) {
  if (adapter === "mkdocs") {
    const base = route ? `docs/${route}` : "docs/index";
    return route ? [`${base}.md`, `${base}/index.md`] : [`${base}.md`];
  }
  if (adapter === "docusaurus") {
    if (route !== "docs" && !route.startsWith("docs/")) {
      return [];
    }
    const docsRoute = route === "docs" ? "index" : route.slice("docs/".length);
    const base = `docs/${docsRoute}`;
    return [`${base}.md`, `${base}/index.md`];
  }
  const base = route || "index";
  return [`${base}.md`, `${base}/index.md`, `_pages/${base}.md`];
}

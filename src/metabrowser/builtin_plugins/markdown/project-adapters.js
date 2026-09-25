// Config-gated source lookup for published static-site routes.

const MAX_CATALOG_FILES = 500_000;
const MAX_ROUTE_CHARACTERS = 16_384;
// A resolved published path is produced only from the bounded rooted authored
// target. Three code units per authored code unit covers canonical percent
// escaping without admitting an unrelated provider-sized identity.
const MAX_RESOLVED_ROUTE_CHARACTERS = MAX_ROUTE_CHARACTERS * 3;
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
 * @typedef {null |
 *   Readonly<{adapter: string, path: string, status: "internal"}> |
 *   Readonly<{candidates: readonly string[], reason: string, status: "ambiguous"}> |
 *   Readonly<{reason: string, status: "pending" | "unsupported"}>} PublishedRouteResolution
 */

/**
 * Resolve one published root route to a source document after exact lookup fails.
 *
 * A `null` result means ordinary exact Markdown behavior remains authoritative.
 *
 * @param {unknown} intent
 * @param {unknown} snapshot
 * @returns {PublishedRouteResolution}
 */
export function resolvePublishedRoute(intent, snapshot) {
  return createPublishedRouteResolutionContext(snapshot).resolve(intent);
}

/**
 * Detect project configuration once and memoize exact catalog membership for every
 * published route resolved against the same immutable snapshot.
 *
 * `resolvedPath` is the bounded output of standard resolution for the same rooted
 * authored target, not an independently provider-authored path. The resolver
 * verifies that pairing before any catalog lookup so its synchronous binary
 * searches and memo keys stay within the authored-route envelope.
 *
 * @param {unknown} snapshot
 */
export function createPublishedRouteResolutionContext(snapshot) {
  const catalog = validateSnapshot(snapshot);
  /** @type {Map<string, boolean>} */
  const membership = new Map();
  /** @type {Map<string, boolean>} */
  const exactTargets = new Map();

  /** @param {string} path */
  function contains(path) {
    const cached = membership.get(path);
    if (cached !== undefined) {
      return cached;
    }
    const found = hasPath(catalog.files, path);
    membership.set(path, found);
    return found;
  }

  /** @param {string} path */
  function targetExists(path) {
    const cached = exactTargets.get(path);
    if (cached !== undefined) {
      return cached;
    }
    const found = exactTargetExists(path, catalog.files, contains);
    exactTargets.set(path, found);
    return found;
  }

  /** @type {typeof ADAPTERS | null} */
  let configured = null;

  function configuredAdapters() {
    configured ||=
      catalog.files.length > MAX_CATALOG_FILES
        ? Object.freeze([])
        : Object.freeze(
            ADAPTERS.filter((adapter) =>
              adapter.configFiles.some((configPath) => contains(configPath)),
            ),
          );
    return configured;
  }

  return Object.freeze({
    /** @param {unknown} intent @returns {PublishedRouteResolution} */
    resolve(intent) {
      const value = validateAuthoredIntent(intent);
      if (!isPublishedRoute(value.authoredTarget)) {
        return null;
      }
      if (typeof value.resolvedPath !== "string") {
        throw new TypeError("published-route resolved path must be a string");
      }
      const route = validateResolvedPublishedRoute(value.authoredTarget, value.resolvedPath);
      // Navigation and live changes add entries to a capped catalog and the walk
      // cap is configurable, so a truncated catalog may exceed this envelope. It
      // never infers a route, so it still explains the cap below.
      if (catalog.files.length > MAX_CATALOG_FILES && !catalog.truncated) {
        return null;
      }
      if (targetExists(value.resolvedPath)) {
        return null;
      }
      if (!catalog.complete) {
        // A capped index is final, but the target or an adapter source may lie
        // past the cap, so an inferred route can never be proven unique.
        return catalog.truncated
          ? Object.freeze({
              reason: "catalog-truncated",
              status: /** @type {const} */ ("unsupported"),
            })
          : Object.freeze({
              reason: "catalog-incomplete",
              status: /** @type {const} */ ("pending"),
            });
      }
      const adapters = configuredAdapters();
      if (adapters.length === 0) {
        return null;
      }

      /** @type {Map<string, string>} */
      const matches = new Map();
      let candidateCount = 0;
      for (const adapter of adapters) {
        for (const candidate of sourceCandidates(adapter.id, route)) {
          candidateCount += 1;
          if (candidateCount > MAX_ADAPTER_CANDIDATES) {
            return Object.freeze({
              reason: "too-many-adapter-candidates",
              status: /** @type {const} */ ("unsupported"),
            });
          }
          if (contains(candidate) && !matches.has(candidate)) {
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
          candidates: Object.freeze([...matches.keys()].sort(codeUnitCompare)),
          reason: "ambiguous-published-route",
          status: /** @type {const} */ ("ambiguous"),
        });
      }
      return null;
    },
  });
}

/** @param {unknown} intent */
function validateAuthoredIntent(intent) {
  if (!intent || typeof intent !== "object") {
    throw new TypeError("published-route resolver requires an intent");
  }
  const value = /** @type {Record<string, unknown>} */ (intent);
  if (typeof value.authoredTarget !== "string") {
    throw new TypeError("published-route authored target must be a string");
  }
  if (value.authoredTarget.length > MAX_ROUTE_CHARACTERS) {
    throw new TypeError("published-route authored target is too long");
  }
  return /** @type {Readonly<{authoredTarget: string, resolvedPath?: unknown}>} */ (value);
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
  if (value.truncated !== undefined && typeof value.truncated !== "boolean") {
    throw new TypeError("published-route snapshot truncation must be boolean");
  }
  if (value.complete && value.truncated) {
    throw new TypeError("published-route snapshot cannot be both complete and truncated");
  }
  return Object.freeze({
    complete: value.complete,
    files: /** @type {ReadonlyArray<unknown>} */ (value.files),
    truncated: value.truncated === true,
  });
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

/**
 * Decode a rooted authored route into its canonical inventory identity.
 * Dot segments resolve lexically, as the standard resolver already did before
 * this adapter runs, so `/a/../guide/` names `guide`; a route that climbs above
 * the root has no identity.
 *
 * @param {string} authoredTarget
 */
function decodedPublishedRoute(authoredTarget) {
  const encoded = authoredTarget.split("#", 1)[0].split("?", 1)[0];
  const trimmed = encoded.replace(/^\/+|\/+$/g, "");
  try {
    /** @type {string[]} */
    const segments = [];
    for (const raw of trimmed.split("/")) {
      if (!raw) {
        continue;
      }
      const segment = decodeURIComponent(raw);
      if (segment === ".") {
        continue;
      }
      if (segment === "..") {
        if (segments.length === 0) {
          return null;
        }
        segments.pop();
        continue;
      }
      if (segment.includes("/") || segment.includes("\0")) {
        return null;
      }
      segments.push(segment);
    }
    // The standard resolver's spelling (links.js inventoryName): `%` is `%25` and a
    // backslash `%5C`, which it admits only in a served folder, whose routes alone reach
    // here with one.
    return segments
      .map((segment) => segment.replaceAll("%", "%25").replaceAll("\\", "%5C"))
      .join("/");
  } catch (_error) {
    return null;
  }
}

/**
 * Enforce the composition boundary with the standard resolver. Published-route
 * adaptation is reachable only after a rooted authored target resolves internally;
 * accepting an unrelated path here would turn a bounded route lookup into an
 * unbounded provider-string hash and comparison on the main thread.
 *
 * @param {string} authoredTarget
 * @param {string} resolvedPath
 */
function validateResolvedPublishedRoute(authoredTarget, resolvedPath) {
  if (resolvedPath.length > MAX_RESOLVED_ROUTE_CHARACTERS) {
    throw new TypeError("published-route resolved path is outside the authored-route envelope");
  }
  const route = decodedPublishedRoute(authoredTarget);
  if (route === null) {
    throw new TypeError("published-route authored target is not a canonical rooted route");
  }
  const encodedPath = authoredTarget.split("#", 1)[0].split("?", 1)[0];
  const expectedPath = route && encodedPath.endsWith("/") ? `${route}/` : route;
  if (resolvedPath !== expectedPath) {
    throw new TypeError("published-route resolved path does not match its authored target");
  }
  return route;
}

/** @param {string} resolvedPath @param {ReadonlyArray<unknown>} files @param {(path: string) => boolean} contains */
function exactTargetExists(resolvedPath, files, contains) {
  if (!resolvedPath) {
    return true;
  }
  if (!resolvedPath.endsWith("/")) {
    return contains(resolvedPath);
  }
  const index = lowerBound(files, resolvedPath);
  return index < files.length && catalogPathAt(files, index).startsWith(resolvedPath);
}

/** @param {ReadonlyArray<unknown>} files @param {string} path */
function hasPath(files, path) {
  const index = lowerBound(files, path);
  return index < files.length && catalogPathAt(files, index) === path;
}

/** @param {ReadonlyArray<unknown>} files @param {string} target */
function lowerBound(files, target) {
  let low = 0;
  let high = files.length;
  while (low < high) {
    const middle = low + Math.floor((high - low) / 2);
    if (codeUnitCompare(catalogPathAt(files, middle), target) < 0) {
      low = middle + 1;
    } else {
      high = middle;
    }
  }
  return low;
}

/**
 * Read one path from the core catalog's immutable, canonical, code-unit-sorted
 * projection. Core owns admission validation; consumers must not impose a
 * position-dependent length or normalization policy while searching.
 *
 * @param {ReadonlyArray<unknown>} files
 * @param {number} index
 */
function catalogPathAt(files, index) {
  return /** @type {Readonly<{path: string}>} */ (files[index]).path;
}

/** @param {string} left @param {string} right */
function codeUnitCompare(left, right) {
  if (left < right) {
    return -1;
  }
  if (left > right) {
    return 1;
  }
  return 0;
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

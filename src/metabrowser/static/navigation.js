// Canonical browser routes for served-root resources.

(() => {
  const ROUTE_PREFIX = "/view/";

  /**
   * @typedef {object} NavigationTarget
   * @property {string} path Served-root-relative logical path, or empty for root.
   * @property {string=} query Serialized query metadata without `?`.
   * @property {string=} fragment Document location without `#`.
   */

  /**
   * Validate and freeze a navigation target without URL-encoding it.
   *
   * @param {NavigationTarget} target
   * @returns {Readonly<NavigationTarget>}
   */
  function normalizeTarget(target) {
    if (!target || typeof target !== "object" || typeof target.path !== "string") {
      throw new TypeError("navigation target requires a string path");
    }
    validateLogicalPath(target.path);
    validateOptionalPart("query", target.query);
    validateOptionalPart("fragment", target.fragment);

    /** @type {NavigationTarget} */
    const normalized = { path: target.path };
    if (target.query) {
      normalized.query = canonicalizeQuery(target.query);
    }
    if (target.fragment) {
      normalized.fragment = target.fragment;
    }
    return Object.freeze(normalized);
  }

  /** @param {string} name @param {unknown} value */
  function validateOptionalPart(name, value) {
    if (value !== undefined && typeof value !== "string") {
      throw new TypeError(`navigation target ${name} must be a string`);
    }
    if (typeof value === "string" && value.includes("\0")) {
      throw new TypeError(`navigation target ${name} cannot contain NUL`);
    }
  }

  /** @param {string} logicalPath */
  function validateLogicalPath(logicalPath) {
    if (!logicalPath) {
      return;
    }
    if (logicalPath.startsWith("/") || logicalPath.includes("\\") || logicalPath.includes("\0")) {
      throw new TypeError("navigation path must be a safe served-root-relative path");
    }
    const segments = logicalPath.split("/");
    const finalIndex = segments.length - 1;
    for (const [index, segment] of segments.entries()) {
      const trailingFolderSlash = index === finalIndex && segment === "";
      if ((!segment && !trailingFolderSlash) || segment === "." || segment === "..") {
        throw new TypeError("navigation path must already be normalized");
      }
    }
  }

  /**
   * Encode a canonical browser href for a logical navigation target.
   *
   * @param {NavigationTarget} target
   * @returns {string}
   */
  function href(target) {
    const normalized = normalizeTarget(target);
    let result = ROUTE_PREFIX + encodePath(normalized.path);
    try {
      if (normalized.query) {
        result += `?${normalized.query}`;
      }
      if (normalized.fragment) {
        result += `#${encodeURIComponent(normalized.fragment)}`;
      }
    } catch (error) {
      throw new TypeError("navigation target contains invalid Unicode", { cause: error });
    }
    return result;
  }

  /**
   * Preserve query delimiters and existing escapes while encoding data that cannot
   * appear literally in a URL. Query metadata stays serialized so an escaped `&`
   * cannot be confused with a parameter separator.
   *
   * @param {string} query
   */
  function canonicalizeQuery(query) {
    let result = "";
    for (let index = 0; index < query.length; ) {
      const character = String.fromCodePoint(/** @type {number} */ (query.codePointAt(index)));
      if (character === "%") {
        const hexPair = query.slice(index + 1, index + 3);
        if (!/^[0-9A-Fa-f]{2}$/.test(hexPair)) {
          throw new TypeError("navigation target query contains a malformed escape");
        }
        result += `%${hexPair.toUpperCase()}`;
        index += 3;
        continue;
      }
      if (/^[A-Za-z0-9\-._~!$&'()*+,;=:@/?]$/.test(character)) {
        result += character;
      } else {
        try {
          result += encodeURIComponent(character);
        } catch (error) {
          throw new TypeError("navigation target query contains invalid Unicode", { cause: error });
        }
      }
      index += character.length;
    }
    return result;
  }

  /** @param {string} logicalPath */
  function encodePath(logicalPath) {
    try {
      return logicalPath
        .split("/")
        .map((segment) => encodeURIComponent(segment))
        .join("/");
    } catch (error) {
      throw new TypeError("navigation path contains invalid Unicode", { cause: error });
    }
  }

  /**
   * Parse a browser location only when it uses the canonical `/view/` route.
   * Invalid or unsafe routes are not navigation targets.
   *
   * @param {string} pathname
   * @param {string} [search]
   * @param {string} [hash]
   * @returns {Readonly<NavigationTarget> | null}
   */
  function parse(pathname, search = "", hash = "") {
    if (typeof pathname !== "string" || !pathname.startsWith(ROUTE_PREFIX)) {
      return null;
    }
    const encodedPath = pathname.slice(ROUTE_PREFIX.length);
    const rawSegments = encodedPath.split("/");
    if (rawSegments.some((segment, index) => !segment && index !== rawSegments.length - 1)) {
      return null;
    }

    try {
      const decodedSegments = rawSegments.map((segment) => decodeURIComponent(segment));
      if (
        decodedSegments.some(
          (segment) => segment.includes("/") || segment.includes("\\") || segment.includes("\0"),
        )
      ) {
        return null;
      }
      const logicalPath = decodedSegments.join("/");
      /** @type {NavigationTarget} */
      const target = { path: logicalPath };
      const encodedQuery = stripPrefix(search, "?");
      const encodedFragment = stripPrefix(hash, "#");
      if (encodedQuery) {
        target.query = encodedQuery;
      }
      if (encodedFragment) {
        target.fragment = decodeURIComponent(encodedFragment);
      }
      return normalizeTarget(target);
    } catch (_error) {
      return null;
    }
  }

  /** @param {string} value @param {string} prefix */
  function stripPrefix(value, prefix) {
    if (typeof value !== "string") {
      throw new TypeError("browser location parts must be strings");
    }
    return value.startsWith(prefix) ? value.slice(prefix.length) : value;
  }

  window.MetabrowserNavigationRoute = Object.freeze({ href, normalizeTarget, parse });
})();

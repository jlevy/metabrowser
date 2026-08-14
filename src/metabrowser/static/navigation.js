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

  /**
   * Compose route identity with browser history and application rendering.
   *
   * @param {{
   *   apply: (target: Readonly<NavigationTarget> | null, context: Readonly<{source: "startup" | "user" | "popstate", pathChanged: boolean, isCurrent: () => boolean, viewId?: string}>) => unknown,
   *   eventTarget?: Pick<Window, "addEventListener" | "removeEventListener">,
   *   history?: Pick<History, "pushState" | "replaceState">,
   *   location?: Pick<Location, "pathname" | "search" | "hash">,
   * }} options
   */
  function createController(options) {
    if (!options || typeof options.apply !== "function") {
      throw new TypeError("navigation controller requires an apply callback");
    }
    const browserLocation = options.location ?? window.location;
    const browserHistory = options.history ?? window.history;
    const eventTarget = options.eventTarget ?? window;
    /** @type {Readonly<NavigationTarget> | null} */
    let currentTarget = null;
    let initialized = false;
    let started = false;
    let disposed = false;
    let applyGeneration = 0;

    /** @param {string} path */
    function lookupPath(path) {
      return path.endsWith("/") ? path.slice(0, -1) : path;
    }

    /**
     * @param {Readonly<NavigationTarget> | null} left
     * @param {Readonly<NavigationTarget> | null} right
     */
    function targetsEqual(left, right) {
      return (
        left === right ||
        (!!left &&
          !!right &&
          left.path === right.path &&
          left.query === right.query &&
          left.fragment === right.fragment)
      );
    }

    /**
     * @param {Readonly<NavigationTarget> | null} target
     * @param {"startup" | "user" | "popstate"} source
     * @param {string=} viewId
     */
    async function applyTarget(target, source, viewId) {
      const previous = currentTarget;
      const generation = ++applyGeneration;
      currentTarget = target;
      initialized = true;
      const pathChanged =
        (previous ? lookupPath(previous.path) : null) !== (target ? lookupPath(target.path) : null);
      const isCurrent = () => !disposed && generation === applyGeneration;
      const context = viewId
        ? Object.freeze({ isCurrent, pathChanged, source, viewId })
        : Object.freeze({ isCurrent, pathChanged, source });
      return options.apply(target, context);
    }

    /** @param {"startup" | "popstate"} source */
    async function applyLocation(source) {
      if (disposed) {
        return;
      }
      const target = parse(browserLocation.pathname, browserLocation.search, browserLocation.hash);
      if (initialized && targetsEqual(target, currentTarget)) {
        return;
      }
      return applyTarget(target, source);
    }

    function handlePopstate() {
      void applyLocation("popstate").catch((error) => {
        console.warn("Could not restore browser navigation", error);
      });
    }

    return Object.freeze({
      /** @param {string} path @param {boolean} isFolder */
      canonicalizePath(path, isFolder) {
        const logicalPath = lookupPath(path);
        if (!currentTarget || lookupPath(currentTarget.path) !== logicalPath) {
          return;
        }
        const canonicalPath = isFolder && logicalPath ? `${logicalPath}/` : logicalPath;
        const target = normalizeTarget({
          path: canonicalPath,
          query: currentTarget?.query,
          fragment: currentTarget?.fragment,
        });
        if (!targetsEqual(target, currentTarget)) {
          browserHistory.replaceState(null, "", href(target));
          currentTarget = target;
        }
      },
      current() {
        return currentTarget;
      },
      dispose() {
        if (disposed) {
          return;
        }
        disposed = true;
        applyGeneration += 1;
        if (started) {
          eventTarget.removeEventListener("popstate", handlePopstate);
        }
      },
      /**
       * @param {NavigationTarget} target
       * @param {{replace?: boolean, viewId?: string}=} openOptions
       */
      async open(target, openOptions = {}) {
        if (disposed) {
          throw new Error("navigation controller is disposed");
        }
        const normalized = normalizeTarget(target);
        const routeHref = href(normalized);
        const currentHref = `${browserLocation.pathname}${browserLocation.search}${browserLocation.hash}`;
        if (openOptions.replace) {
          browserHistory.replaceState(null, "", routeHref);
        } else if (routeHref !== currentHref) {
          browserHistory.pushState(null, "", routeHref);
        }
        return applyTarget(normalized, "user", openOptions.viewId);
      },
      async start() {
        if (disposed) {
          throw new Error("navigation controller is disposed");
        }
        if (started) {
          return;
        }
        started = true;
        eventTarget.addEventListener("popstate", handlePopstate);
        return applyLocation("startup");
      },
    });
  }

  window.MetabrowserNavigationRoute = Object.freeze({
    createController,
    href,
    normalizeTarget,
    parse,
  });
})();

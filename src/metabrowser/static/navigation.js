// Canonical browser routes for served-root resources.

(() => {
  const ROUTE_PREFIX = "/view/";
  const COMMIT_PREFIX = "/commit/";

  /**
   * Encode a commit route: `/commit/<rev>` for the whole change set,
   * `/commit/<rev>/<file>` for one file's diff. The shape after the
   * route is `<container address>/<inner path>`, the same shape a patch
   * file's children use inside `/view/`.
   *
   * @param {string} revision
   * @param {string} [file]
   * @returns {string}
   */
  function commitHref(revision, file = "") {
    if (typeof revision !== "string" || !revision) {
      throw new TypeError("commit route requires a revision");
    }
    const head = COMMIT_PREFIX + encodeURIComponent(revision);
    if (!file) {
      return head;
    }
    validateLogicalPath(file);
    return `${head}/${encodePath(file)}`;
  }

  /**
   * Parse a commit route, or null when the location is not one.
   *
   * @param {string} pathname
   * @returns {{revision: string, file: string} | null}
   */
  function parseCommit(pathname) {
    if (typeof pathname !== "string" || !pathname.startsWith(COMMIT_PREFIX)) {
      return null;
    }
    const rawSegments = pathname.slice(COMMIT_PREFIX.length).split("/");
    if (rawSegments[rawSegments.length - 1] === "") {
      rawSegments.pop();
    }
    if (rawSegments.length === 0 || rawSegments.some((segment) => !segment)) {
      return null;
    }
    try {
      const [revision, ...rest] = rawSegments.map((segment) => decodeURIComponent(segment));
      if (!revision || rest.some((segment) => segment === "." || segment === "..")) {
        return null;
      }
      return Object.freeze({ revision, file: rest.join("/") });
    } catch (_error) {
      return null;
    }
  }

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
    // Inventory escapes represent native bytes, while URL encoding also escapes
    // ordinary UTF-8 and URL delimiters. Do not encode the identity a second time.
    let result = ROUTE_PREFIX + encodeIdentityPath(normalized.path);
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
      const decodedSegments = rawSegments.map(pathFromUrl);
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

  /** @param {string} path */
  function encodeIdentityPath(path) {
    // Windows escapes lone UTF-16 code units in the inventory. Encode these as
    // WTF-8 in URLs so they cannot collide with an ordinary UTF-8 scalar.
    if (window.METABROWSER_PATH_ENCODING === "utf16") {
      path = path.replace(/%(D[8-F])%([0-9A-F]{2})/g, (_match, high, low) => {
        const point = Number.parseInt(high + low, 16);
        return [0xed, 0x80 | ((point >> 6) & 63), 0x80 | (point & 63)]
          .map((byte) => `%${byte.toString(16).toUpperCase()}`)
          .join("");
      });
    }
    return encodePath(path).replace(/%25([0-9A-F]{2})/g, "%$1");
  }

  /** Display literal percent signs; undecodable platform bytes stay visibly escaped.
   * @param {string} path
   */
  function displayPath(path) {
    return path.replaceAll("%25", "%");
  }

  /** Convert URL bytes into the provider's lossless identity, including POSIX names
   * with isolated non-UTF-8 bytes. Ordinary UTF-8 takes the fast path.
   * @param {string} segment
   * @returns {string}
   */
  function pathFromUrl(segment) {
    if (window.METABROWSER_PATH_ENCODING === "utf16") {
      const units = [...segment.matchAll(/%ED%([AB][0-9A-F])%([89AB][0-9A-F])/gi)];
      if (units.length) {
        let result = "";
        let start = 0;
        for (const unit of units) {
          result += pathFromUrl(segment.slice(start, unit.index));
          const point =
            0xd000 |
            ((Number.parseInt(unit[1], 16) & 63) << 6) |
            (Number.parseInt(unit[2], 16) & 63);
          result += `%${(point >> 8).toString(16).toUpperCase()}%${(point & 255).toString(16).padStart(2, "0").toUpperCase()}`;
          start = unit.index + unit[0].length;
        }
        return result + pathFromUrl(segment.slice(start));
      }
    }
    try {
      return decodeURIComponent(segment).replaceAll("%", "%25");
    } catch (_error) {
      let result = "";
      for (let index = 0; index < segment.length; ) {
        if (segment[index] !== "%") {
          result += segment[index++];
          continue;
        }
        const escaped = segment.slice(index, index + 3);
        if (!/^%[0-9a-f]{2}$/i.test(escaped)) {
          throw new URIError("malformed path escape");
        }
        let decoded = false;
        // A UTF-8 scalar occupies at most four bytes. Consume valid scalars before
        // retaining an undecodable byte; this keeps adjacent spaces and Unicode intact.
        for (let bytes = 1; bytes <= 4; bytes++) {
          const part = segment.slice(index, index + bytes * 3);
          if (!new RegExp(`^(%[0-9a-f]{2}){${bytes}}$`, "i").test(part)) {
            break;
          }
          try {
            result += decodeURIComponent(part).replaceAll("%", "%25");
            index += part.length;
            decoded = true;
            break;
          } catch (_error) {
            /* Try the next UTF-8 length. */
          }
        }
        if (!decoded) {
          result += escaped.toUpperCase();
          index += 3;
        }
      }
      return result;
    }
  }

  /** @param {string} value @param {string} prefix */
  function stripPrefix(value, prefix) {
    if (typeof value !== "string") {
      throw new TypeError("browser location parts must be strings");
    }
    return value.startsWith(prefix) ? value.slice(prefix.length) : value;
  }

  /** @param {unknown} options */
  function validateOpenOptions(options) {
    if (!options || typeof options !== "object") {
      throw new TypeError("navigation options must be an object");
    }
    const candidate = /** @type {{replace?: unknown, viewId?: unknown}} */ (options);
    if (
      candidate.viewId !== undefined &&
      (typeof candidate.viewId !== "string" || !candidate.viewId)
    ) {
      throw new TypeError("navigation options.viewId must be a non-empty string");
    }
    if (candidate.replace !== undefined && typeof candidate.replace !== "boolean") {
      throw new TypeError("navigation options.replace must be a boolean");
    }
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
        validateOpenOptions(openOptions);
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

  /** @type {ReturnType<typeof createController> | null} */
  let attachedController = null;

  /**
   * Attach the shell-owned controller to the stable public navigation facade.
   *
   * @param {ReturnType<typeof createController>} controller
   */
  function attachController(controller) {
    if (
      !controller ||
      typeof controller.current !== "function" ||
      typeof controller.open !== "function"
    ) {
      throw new TypeError("public navigation requires a navigation controller");
    }
    if (attachedController && attachedController !== controller) {
      throw new Error("a public navigation controller is already attached");
    }
    attachedController = controller;
    let attached = true;
    return () => {
      if (attached && attachedController === controller) {
        attached = false;
        attachedController = null;
      }
    };
  }

  const navigation = Object.freeze({
    current() {
      if (!attachedController) {
        throw new Error("browser navigation is not initialized");
      }
      return attachedController.current();
    },
    href,
    /**
     * @param {NavigationTarget} target
     * @param {{viewId?: string}=} options
     */
    async open(target, options) {
      if (!attachedController) {
        throw new Error("browser navigation is not initialized");
      }
      validateOpenOptions(options ?? {});
      await attachedController.open(target, options);
    },
  });

  window.MetabrowserNavigationRoute = Object.freeze({
    attachController,
    commitHref,
    createController,
    displayPath,
    href,
    navigation,
    normalizeTarget,
    parse,
    parseCommit,
  });
})();

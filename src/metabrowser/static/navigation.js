// Canonical browser routes for served-root resources.

(() => {
  const ROUTE_PREFIX = "/view/";
  const COMMIT_PREFIX = "/commit/";
  // Keep this grammar byte-for-byte aligned with view_routes._ROUTE_REVISION.
  // The revision occupies one encoded URL segment, but its decoded Git ref may
  // contain slashes (for example refs/heads/main).
  const COMMIT_REVISION_PATTERN = /^[0-9A-Za-z][0-9A-Za-z._/@^~-]{0,255}$/;

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
    if (typeof revision !== "string" || !COMMIT_REVISION_PATTERN.test(revision)) {
      throw new TypeError("commit route requires a valid revision");
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
      if (
        !COMMIT_REVISION_PATTERN.test(revision) ||
        rest.some(
          (segment) =>
            segment === "." ||
            segment === ".." ||
            segment.includes("/") ||
            segment.includes("\\") ||
            segment.includes("\0"),
        )
      ) {
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

  /** @param {string} token */
  function isGitPathToken(token) {
    return token.startsWith("g1-") && token.length > 3;
  }

  /** Canonical unpadded base64url atom to replacement-safe UTF-8, or null.
   * @param {string} atom
   */
  function decodeGitPathAtom(atom) {
    if (!atom || /[^A-Za-z0-9_-]/.test(atom)) {
      return null;
    }
    const padded = atom + "=".repeat((4 - (atom.length % 4)) % 4);
    let binary;
    try {
      binary = atob(padded.replaceAll("-", "+").replaceAll("_", "/"));
    } catch (_error) {
      return null;
    }
    let encoded;
    try {
      encoded = btoa(binary).replaceAll("+", "-").replaceAll("/", "_").replace(/=+$/, "");
    } catch (_error) {
      return null;
    }
    if (encoded !== atom) {
      return null;
    }
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i += 1) {
      bytes[i] = binary.charCodeAt(i);
    }
    const text = new TextDecoder("utf-8").decode(bytes);
    if (!text || text.includes("\0") || text.includes("/")) {
      return null;
    }
    let sanitized = "";
    for (const ch of text) {
      const code = ch.charCodeAt(0);
      sanitized += code < 32 || code === 127 ? "\uFFFD" : ch;
    }
    return sanitized;
  }

  /** Decode a contiguous GitPath wire prefix. Null when this is not a GitPath identity.
   * @param {string} path
   */
  function displayGitPathWire(path) {
    const parts = path.split("/");
    let cut = 0;
    while (cut < parts.length && isGitPathToken(parts[cut])) {
      cut += 1;
    }
    if (cut === 0) {
      return null;
    }
    const decoded = [];
    for (let i = 0; i < cut; i += 1) {
      const segment = decodeGitPathAtom(parts[i].slice(3));
      if (segment === null) {
        return null;
      }
      decoded.push(segment);
    }
    const gitDisplay = decoded.join("/");
    if (cut === parts.length) {
      return gitDisplay;
    }
    return `${gitDisplay}/${parts.slice(cut).join("/").replaceAll("%25", "%")}`;
  }

  /** Display a path identity. GitPath wires decode to UTF-8 names; inventory
   * identities show literal percent signs. Undecodable platform bytes stay escaped.
   * @param {string} path
   */
  function displayPath(path) {
    const gitDisplay = displayGitPathWire(path);
    if (gitDisplay !== null) {
      return gitDisplay;
    }
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
   * Create a bounded, Set-like invalidation tracker whose captures distinguish
   * the event one request started from from a newer event on the same path.
   * Keeping a dirty marker present until an owned response settles also means a
   * same-path replacement request cannot mistake an in-flight revalidation for
   * a hot cache hit.
   *
   * @param {number} maxEntries
   */
  function createFileRevalidationTracker(maxEntries) {
    if (!Number.isSafeInteger(maxEntries) || maxEntries <= 0) {
      throw new TypeError("file revalidation tracker requires a positive integer bound");
    }
    /** @type {Map<string, Readonly<{id: number}>>} */
    const markers = new Map();
    let nextId = 0;

    /** @param {string} path */
    function add(path) {
      if (typeof path !== "string" || !path) {
        throw new TypeError("file revalidation path must be a non-empty string");
      }
      nextId += 1;
      const marker = Object.freeze({ id: nextId });
      markers.delete(path);
      markers.set(path, marker);
      while (markers.size > maxEntries) {
        markers.delete(/** @type {string} */ (markers.keys().next().value));
      }
    }

    return Object.freeze({
      add,
      /** @param {string} path */
      capture(path) {
        return markers.get(path) ?? null;
      },
      clear() {
        markers.clear();
      },
      /** @param {string} path */
      delete(path) {
        return markers.delete(path);
      },
      /** @param {string} path */
      has(path) {
        return markers.has(path);
      },
      keys() {
        return markers.keys();
      },
      /**
       * @param {string} path
       * @param {Readonly<{id: number}> | null} marker
       */
      settle(path, marker) {
        if (marker === null || markers.get(path) !== marker) {
          return false;
        }
        markers.delete(path);
        return true;
      },
      get size() {
        return markers.size;
      },
    });
  }

  /**
   * Replace one authoritative, scoped file-store snapshot as a transaction.
   *
   * FileStore holds exactly one `/api/events` connection's scope: its snapshot
   * plus the deltas that connection filters to the same scope. Lazily expanded
   * subtrees are rendered from `/api/tree` and never enter it. Absence from the
   * replacement is therefore authoritative for every previous key.
   *
   * The caller installs the complete next Map before any row callback runs, so
   * every derived read sees one revision. Rows present on both sides are
   * upserted in place, keeping their expansion and any lazily loaded children;
   * only rows absent from the replacement are retired. A resync must keep the
   * current store as this baseline until the reconnect snapshot arrives:
   * replacing it with an empty snapshot first would retire every row.
   *
   * @param {Map<string, Record<string, any>>} previous
   * @param {Array<Record<string, any> & {path: string}>} entries
   * @param {{
   *   install: (next: Map<string, Record<string, any>>) => void,
   *   retire: (path: string) => void,
   *   upsert: (entry: Record<string, any> & {path: string}) => void,
   * }} callbacks
   * @returns {Map<string, Record<string, any>>}
   */
  function replaceFileSnapshot(previous, entries, callbacks) {
    const next = new Map();
    for (const entry of entries) {
      next.set(entry.path, entry);
    }
    callbacks.install(next);
    for (const path of previous.keys()) {
      if (!next.has(path)) {
        callbacks.retire(path);
      }
    }
    for (const entry of entries) {
      callbacks.upsert(entry);
    }
    return next;
  }

  /**
   * Attach both fulfillment and rejection handlers immediately when an
   * independent navigation dependency begins. The caller may await an HTTP
   * result first without creating an unhandled-rejection window.
   *
   * @template T
   * @param {Promise<T>} pending
   * @returns {Promise<Readonly<{status: "ready", value: T} | {status: "error", error: unknown}>>}
   */
  function settleNavigationDependency(pending) {
    return pending.then(
      (value) => Object.freeze({ status: /** @type {"ready"} */ ("ready"), value }),
      (error) => Object.freeze({ error, status: /** @type {"error"} */ ("error") }),
    );
  }

  // ── Preview pane states ──────────────────────────────────────

  const PREVIEW_IDLE_MESSAGE = "Select a file to preview.";
  const FILE_ERROR_SUMMARY = "Could not open this file.";
  const OPEN_ERROR_MESSAGE = "Could not open this file. Try again.";
  const UNREACHABLE_SUMMARY = "Metabrowser is not reachable.";
  const UNREACHABLE_DETAIL =
    "It may have stopped. Start it again with metab <folder>, and this page will reconnect.";

  /** @typedef {"starting" | "idle" | "loading" | "content" | "error" | "unreachable" | "external"} PreviewPanePhase */
  /** @typedef {Readonly<{folder: boolean, path: string, viewId?: string}>} PreviewSelection */
  /**
   * What the pane shows while no rendered view owns it. A loading placeholder
   * names its subject rather than carrying copy: loading is a spinner, and the
   * shell composes the screen-reader-only name from the subject.
   *
   * @typedef {Readonly<{paint: "none"} | {paint: "loading", subject: "preview" | "folder" | "file"} | {paint: "idle", message: string}>} PreviewPlaceholder
   */
  /** @typedef {Readonly<{kind: "error" | "unreachable", summary: string, detail: string}>} PreviewFailure */

  const NO_PLACEHOLDER = /** @type {PreviewPlaceholder} */ (Object.freeze({ paint: "none" }));

  /**
   * A request that received no HTTP response at all.
   *
   * `fetch` rejects only when nothing answered: the server stopped, the
   * connection was refused, or the network dropped. An HTTP 4xx or 5xx still
   * resolves. Marking the rejection where it happens is the one reliable way to
   * tell a transport failure apart, because a renderer bug can throw the same
   * `TypeError` a failed fetch does.
   */
  class ServerUnreachableError extends Error {
    /** @param {unknown} cause */
    constructor(cause) {
      super(UNREACHABLE_SUMMARY, { cause });
      this.name = "ServerUnreachableError";
    }
  }

  /** @param {unknown} error */
  function isAbortError(error) {
    return (
      !!error &&
      typeof error === "object" &&
      /** @type {{name?: unknown}} */ (error).name === "AbortError"
    );
  }

  /**
   * Classify a rejected `fetch`. Aborts pass through unchanged so superseded
   * navigation stays silent; every other rejection means the server could not
   * be reached.
   *
   * @param {unknown} error
   * @returns {unknown}
   */
  function requestFailure(error) {
    if (isAbortError(error) || error instanceof ServerUnreachableError) {
      return error;
    }
    return new ServerUnreachableError(error);
  }

  /**
   * Classify a rejected response body read.
   *
   * `fetch` resolves as soon as the headers arrive, so a server that stops
   * while the body is still streaming rejects the read instead of the fetch.
   * That is the same lost connection. Aborts still pass through, and so does a
   * `SyntaxError`: the server answered with a body that is not JSON, which is
   * a response problem rather than an unreachable server. A renderer cannot
   * reach this promise, so its exceptions keep their file wording.
   *
   * @param {unknown} error
   * @returns {unknown}
   */
  function responseBodyFailure(error) {
    return error instanceof SyntaxError ? error : requestFailure(error);
  }

  /**
   * The message for one failed selection: a connection state when the server
   * could not be reached, otherwise the file error the response described.
   *
   * @param {unknown} error
   * @returns {PreviewFailure}
   */
  function describePreviewFailure(error) {
    if (error instanceof ServerUnreachableError) {
      return Object.freeze({
        detail: UNREACHABLE_DETAIL,
        kind: /** @type {const} */ ("unreachable"),
        summary: UNREACHABLE_SUMMARY,
      });
    }
    const caught = /** @type {{message?: unknown, summary?: unknown}} */ (error ?? {});
    const summary =
      typeof caught.summary === "string" && caught.summary.trim()
        ? caught.summary.trim()
        : FILE_ERROR_SUMMARY;
    const detail =
      typeof caught.message === "string" && caught.message
        ? caught.message
        : String(error || "An unknown error occurred.");
    return Object.freeze({ detail, kind: /** @type {const} */ ("error"), summary });
  }

  /**
   * A Quick File result for an open that threw instead of settling.
   *
   * @param {unknown} error
   * @returns {Readonly<{message: string, status: "error" | "unreachable"}>}
   */
  function openFailureOutcome(error) {
    return error instanceof ServerUnreachableError
      ? Object.freeze({
          message: `${UNREACHABLE_SUMMARY} ${UNREACHABLE_DETAIL}`,
          status: /** @type {const} */ ("unreachable"),
        })
      : Object.freeze({ message: OPEN_ERROR_MESSAGE, status: /** @type {const} */ ("error") });
  }

  /**
   * Track who owns the preview pane and what it is doing.
   *
   * Every producer that paints the pane claims it first and keeps the returned
   * generation; a later claim makes every older write harmless. A file
   * selection names what it loads, so its placeholder can say so and a
   * reconnect can retry it. Owner `none` records that nothing is selected, and
   * any other owner (the Git panel) paints for itself.
   *
   * The pane starts in `starting`: the shell is only served for `/view/` and
   * `/commit/` routes, and each of them selects something, so what ships is a
   * loading indicator rather than a prompt. "Select a file to preview." is the
   * placeholder only when nothing is selected and nothing is loading.
   *
   * Switching navigation tabs is not a claim. It changes which list is visible,
   * not what is selected, so the selection underneath keeps loading and lands.
   */
  function createPreviewPaneLifecycle() {
    let generation = 0;
    let owner = "shell";
    /** @type {PreviewPanePhase} */
    let phase = "starting";
    /** @type {PreviewSelection | null} */
    let selection = null;

    return Object.freeze({
      /**
       * @param {string} nextOwner
       * @param {PreviewSelection} [nextSelection] Required for owner `file`.
       * @returns {number}
       */
      claim(nextOwner, nextSelection) {
        if (typeof nextOwner !== "string" || !nextOwner) {
          throw new TypeError("preview claim requires an owner");
        }
        if (nextOwner === "file" && (!nextSelection || typeof nextSelection.path !== "string")) {
          throw new TypeError("a file preview claim requires the selected path");
        }
        generation += 1;
        owner = nextOwner;
        if (nextOwner === "file" && nextSelection) {
          selection = Object.freeze({
            folder: nextSelection.folder === true,
            path: nextSelection.path,
            ...(nextSelection.viewId ? { viewId: nextSelection.viewId } : {}),
          });
          phase = "loading";
        } else {
          selection = null;
          phase = nextOwner === "none" ? "idle" : "external";
        }
        return generation;
      },
      /**
       * Whether the pane already shows, or is loading, this file selection.
       * Re-opening a path the pane holds only needs its fragment delivered.
       * A selection that failed, or a pane another owner has claimed since,
       * holds nothing: opening the same path again has to load it, which is
       * how a reader retries.
       *
       * @param {string} path
       */
      holds(path) {
        return (
          owner === "file" &&
          selection?.path === path &&
          (phase === "loading" || phase === "content")
        );
      },
      /** @param {number} claim */
      isCurrent(claim) {
        return claim === generation;
      },
      /**
       * @param {number} claim
       * @returns {PreviewPlaceholder}
       */
      placeholder(claim) {
        if (claim !== generation) {
          return NO_PLACEHOLDER;
        }
        if (phase === "starting") {
          // Nothing is selected yet, so the subject is the preview itself.
          // `server.py` ships this placeholder in the shell.
          return Object.freeze({ paint: "loading", subject: "preview" });
        }
        if (phase === "loading") {
          return Object.freeze({
            paint: "loading",
            subject: selection?.folder ? "folder" : "file",
          });
        }
        if (phase === "idle") {
          return Object.freeze({ message: PREVIEW_IDLE_MESSAGE, paint: "idle" });
        }
        return NO_PLACEHOLDER;
      },
      /**
       * Record how the current file selection settled.
       *
       * @param {number} claim
       * @param {"content" | "error" | "unreachable"} outcome
       */
      settle(claim, outcome) {
        if (claim !== generation || owner !== "file") {
          return false;
        }
        phase = outcome;
        return true;
      },
      /**
       * The selection to retry once the server answers again, or null when
       * the pane does not show a connection failure.
       *
       * @returns {PreviewSelection | null}
       */
      reconnected() {
        return phase === "unreachable" ? selection : null;
      },
      /**
       * Settle a startup no owner claimed — a `/commit/` route in a folder
       * that is not a repository, or navigation that failed to start. Nothing
       * is selected or loading then, so the pane shows the prompt.
       *
       * @returns {PreviewPlaceholder}
       */
      settleUnclaimed() {
        if (phase !== "starting") {
          return NO_PLACEHOLDER;
        }
        generation += 1;
        owner = "none";
        phase = "idle";
        return Object.freeze({ message: PREVIEW_IDLE_MESSAGE, paint: "idle" });
      },
      snapshot() {
        return Object.freeze({
          claim: generation,
          owner,
          path: selection ? selection.path : null,
          phase,
        });
      },
    });
  }

  /**
   * Classify one file-selection failure and run mutations only for the
   * selection that still owns the pane.
   *
   * @param {{
   *   cached: boolean,
   *   claim: number,
   *   error: unknown,
   *   isCurrent: () => boolean,
   *   markForRevalidation: () => void,
   *   pane: ReturnType<typeof createPreviewPaneLifecycle>,
   *   path: string,
   *   showError: (failure: PreviewFailure) => void,
   * }} options
   * @returns {{status: "cancelled"} | {message: string, status: "error" | "not-found" | "unreachable"}}
   */
  function settleFileSelectionFailure(options) {
    const caught = /** @type {{notFound?: boolean}} */ (options.error);
    if (isAbortError(options.error) || !options.isCurrent()) {
      return { status: "cancelled" };
    }
    if (options.cached) {
      options.markForRevalidation();
    }
    const failure = describePreviewFailure(options.error);
    options.pane.settle(options.claim, failure.kind);
    options.showError(failure);
    if (failure.kind === "unreachable") {
      return { ...openFailureOutcome(options.error) };
    }
    return caught?.notFound === true
      ? { message: `${options.path} is no longer available.`, status: "not-found" }
      : {
          message: `Could not open ${options.path}. Check that the file still exists and is readable.`,
          status: "error",
        };
  }

  /**
   * Commit a fresh file response only while the selection that requested it
   * still owns the preview.
   *
   * Cache payload, validator, and ownership are one transaction. In
   * particular, a late response from same-path navigation A must not poison
   * the hot cache after navigation B has already won. Folder envelopes are
   * deliberately no-store, but still evict a previous file payload when a path
   * changes shape. Neither branch clears a dirty marker: a filesystem event
   * that arrived during the request belongs to the next selection.
   *
   * @param {{
   *   cacheFile: (data: Record<string, any>) => void,
   *   cacheValidator: (etag: string) => void,
   *   data: Record<string, any>,
   *   etag: string | null,
   *   evictFile: () => void,
   *   evictValidator: () => void,
   *   isCurrent: () => boolean,
   * }} options
   * @returns {"cancelled" | "file" | "folder"}
   */
  function commitFreshFileResponse(options) {
    if (!options.isCurrent()) {
      return "cancelled";
    }
    if (options.data.kind === "folder") {
      options.evictFile();
      options.evictValidator();
      return "folder";
    }
    options.cacheFile(options.data);
    if (options.etag) {
      options.cacheValidator(options.etag);
    } else {
      options.evictValidator();
    }
    return "file";
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
    commitFreshFileResponse,
    commitHref,
    createController,
    createFileRevalidationTracker,
    createPreviewPaneLifecycle,
    displayPath,
    href,
    navigation,
    normalizeTarget,
    openFailureOutcome,
    parse,
    parseCommit,
    replaceFileSnapshot,
    requestFailure,
    responseBodyFailure,
    settleFileSelectionFailure,
    settleNavigationDependency,
  });
})();

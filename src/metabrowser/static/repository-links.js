// What a link in rendered text opens: an in-app page when the link names one in the served
// repository, and otherwise the link as written.
//
// Every surface that shows authored text decides its links here: a Markdown file or a
// folder's README (builtin_plugins/markdown/link-enhancer.js), a pull request's
// description, comments, reviews, and Guided Review notes (builtin_plugins/github), a
// commit's message (static/git-panel.js), and Markdown rendered in a diff
// (builtin_plugins/diff/diff-markdown.js). One decision, so the surfaces cannot drift
// apart; docs/project/specs/active/plan-2026-11-26-in-app-link-resolution.md is its design.
//
// `localize` reads one absolute URL against the served repository's identity,
// `metabrowser.repository`, and answers:
//
// - a `view` target, a `/view/` address of the served tree, for the repository's root
//   and for a `blob` or `tree` URL naming the served branch or the served commit;
// - a `route`, for a pull request and its Changes and Checks tabs, a commit by its full
//   ID, and the pull request list, which name no revision and so open whatever is served;
// - an `external` URL in place of the one written, for a pull request's text only: the
//   file a path-relative reference names, at the commit the text describes, on github.com;
// - or null, and the link stays as it is: another repository, another branch or tag, an
//   abbreviated commit, an issue, a comparison, or any address with nothing in-app to show.
//
// No in-app address names a revision, and a link in authored text never switches the
// served pin, so a link to another branch stays external: opening it here would show the
// served branch's file under another branch's link (diff-markdown.js `markdownTargets`
// holds the same rule).
//
// A pull request's text has its page as its base on the server (pull_text_render.py), so
// a path-relative reference arrives as github.com would resolve it, under
// `/<owner>/<repo>/pull/`, where github.com shows a missing page. With a text context, an
// address there that is not a pull request's is read as the repository path it names, at
// the text's commit: in place when the served tree is that commit, on github.com
// otherwise.
//
// `enhance` applies `localize` to every link of an inert text, already reduced to the
// allowlist (static/inert-html.js): an in-app link loses `target` and `rel`, since it does
// not leave the page, and a plain click on a `/view/` target opens it through
// `metabrowser.navigation.open`, as a Markdown file's links do. A modified click, a new
// tab, and a copied address use the same `href`.
//
// Loaded on demand (`ensureAsset("repository-links")`) by the views that show authored text
// from a GitHub repository: only a page with a repository identity uses it, and the startup
// scripts are at their transfer budget (performance-budgets.toml). The exact module runs
// browserlessly in tests/dom/repository-links-session.js.

(() => {
  /** Bounds URL parsing work for one authored link. */
  const MAX_URL_LENGTH = 16 * 1024;
  /** Bounds path comparison work for one authored link. */
  const MAX_PATH_SEGMENTS = 512;
  const FULL_REVISION = /^[0-9a-f]{40}$/i;
  // Keep aligned with view_routes._PULL_NUMBER and static/pull-route.js.
  const PULL_NUMBER = /^[1-9][0-9]{0,9}$/;
  // GitHub's anchor for one file of a pull request's Changes tab or a commit's page:
  // `diff-` and the SHA-256 of its path (builtin_plugins/github/urls.py), optionally with a
  // line. Only the server can name its file (pull_file_anchor.py), so a link with one opens
  // the page, as `metab URL` does for a commit.
  const FILE_ANCHOR = /^diff-[0-9a-f]{64}(?:[LR][0-9]+(?:-[LR][0-9]+)?)?$/;
  const HOSTS = new Set(["github.com", "www.github.com"]);

  /**
   * @typedef {Readonly<{kind: "view", target: MetabrowserPublicNavigationTarget, localization: "revision" | "working-tree"}>
   *   | Readonly<{kind: "route", href: string, localization: "pull" | "commit" | "pulls", pull: Readonly<{number: number, tab: "" | "files" | "checks"}> | null}>
   *   | Readonly<{kind: "external", url: string}>} RepositoryLinkTarget
   */

  /**
   * @typedef {{
   *   sourceKind?: "filesystem" | "git_revision",
   *   text?: {head: string | null},
   * }} LocalizeOptions
   *   `sourceKind` is what the served tree is (`metabrowser.sourceKind()`): a pinned
   *   revision addresses its paths in the GitPath wire. `text` is a pull request's text,
   *   whose base is its page, with `head`, the commit it describes, or null when not known.
   */

  /**
   * The in-app target of *url*, a replacement for it, or null to leave it as written.
   *
   * @param {string} url An absolute URL, as the page has it.
   * @param {MetabrowserPublicRepositoryContext | null | undefined} context
   * @param {LocalizeOptions} [options]
   * @returns {RepositoryLinkTarget | null}
   */
  function localize(url, context, options = {}) {
    if (typeof url !== "string" || url.length > MAX_URL_LENGTH || !isRepositoryContext(context)) {
      return null;
    }
    let parsed;
    try {
      parsed = new URL(url);
    } catch (_error) {
      return null;
    }
    if (
      (parsed.protocol !== "https:" && parsed.protocol !== "http:") ||
      parsed.username ||
      parsed.password ||
      parsed.port ||
      !HOSTS.has(parsed.hostname.toLowerCase())
    ) {
      return null;
    }
    const segments = decodeSegments(parsed.pathname);
    if (
      !segments ||
      segments.length < 2 ||
      !sameIdentity(segments[0], context.owner) ||
      !sameIdentity(segments[1].replace(/\.git$/i, ""), context.name)
    ) {
      return null;
    }
    const fragment = parsed.hash.length > 1 ? safeDecode(parsed.hash.slice(1)) : "";
    if (fragment === null || fragment.includes("\0")) {
      return null;
    }
    const link = {
      directory: parsed.pathname.endsWith("/"),
      fragment,
      query: parsed.search.length > 1 ? parsed.search.slice(1) : "",
      rest: segments.slice(2),
      search: parsed.search,
      hash: parsed.hash,
    };
    const sourceKind = options.sourceKind === "git_revision" ? "git_revision" : "filesystem";
    const page = link.rest[0];
    if (page === undefined) {
      // The repository's page shows its default branch's README; here the served root does,
      // in its Overview, whose fragment scrolls the README as the page's anchor does there.
      return link.query
        ? null
        : view([], true, "", link.fragment, "working-tree", context, sourceKind);
    }
    if (page === "blob" || page === "tree") {
      return revisionPath(link, page === "tree", context, sourceKind);
    }
    if (page === "pull") {
      return pullLink(link, context, sourceKind, options.text);
    }
    if (page === "commit") {
      return link.rest.length === 2 ? commit(link.rest[1], link) : null;
    }
    if (page === "pulls") {
      return link.rest.length === 1 && !link.query && !link.fragment
        ? route("/pulls", "pulls")
        : null;
    }
    return null;
  }

  /**
   * @typedef {{
   *   directory: boolean, fragment: string, query: string, rest: string[],
   *   search: string, hash: string,
   * }} RepositoryLink
   */

  /**
   * A `blob` or `tree` URL: in place when its reference is the served branch or the served
   * commit, and only then. A branch name may hold slashes, so it is matched as a prefix of
   * the reference and path, as GitHub's own routing reads it.
   *
   * @param {RepositoryLink} link
   * @param {boolean} tree
   * @param {MetabrowserPublicRepositoryContext} context
   * @param {"filesystem" | "git_revision"} sourceKind
   * @returns {RepositoryLinkTarget | null}
   */
  function revisionPath(link, tree, context, sourceKind) {
    const referenceAndPath = link.rest.slice(1);
    // A tree names a folder, its branch's root among them; a blob names a file.
    const least = tree ? 0 : 1;
    if (
      referenceAndPath.length > least &&
      FULL_REVISION.test(referenceAndPath[0]) &&
      referenceAndPath[0].toLowerCase() === context.revision.toLowerCase()
    ) {
      return view(
        referenceAndPath.slice(1),
        tree || link.directory,
        link.query,
        link.fragment,
        "revision",
        context,
        sourceKind,
      );
    }
    const branch = context.branch ? safeRelativeSegments(context.branch) : null;
    if (
      branch &&
      branch.length > 0 &&
      referenceAndPath.length > branch.length + least - 1 &&
      startsWithSegments(referenceAndPath, branch)
    ) {
      return view(
        referenceAndPath.slice(branch.length),
        tree || link.directory,
        link.query,
        link.fragment,
        "working-tree",
        context,
        sourceKind,
      );
    }
    return null;
  }

  /**
   * A pull request's page, its Changes or Checks tab, or one of its commits. An address
   * whose first segment is a number is a pull request's, mapped or not; with a text
   * context, any other address under `pull/` is the repository path a path-relative
   * reference named.
   *
   * @param {RepositoryLink} link
   * @param {MetabrowserPublicRepositoryContext} context
   * @param {"filesystem" | "git_revision"} sourceKind
   * @param {{head: string | null} | undefined} text
   * @returns {RepositoryLinkTarget | null}
   */
  function pullLink(link, context, sourceKind, text) {
    const [number, tab, ...more] = link.rest.slice(1);
    if (number === undefined || !PULL_NUMBER.test(number)) {
      return text ? textPath(link, context, sourceKind, text.head) : null;
    }
    if (link.query) {
      return null;
    }
    const pull = Number(number);
    if (tab === undefined) {
      return link.fragment ? null : pullRoute(pull, "");
    }
    if (more.length === 0 && (tab === "files" || tab === "changes")) {
      return !link.fragment || FILE_ANCHOR.test(link.fragment) ? pullRoute(pull, "files") : null;
    }
    if (more.length === 0 && tab === "checks") {
      return link.fragment ? null : pullRoute(pull, "checks");
    }
    if (more.length === 1 && tab === "commits") {
      return commit(more[0], link);
    }
    return null;
  }

  /**
   * The repository path a pull request's path-relative reference names, at *head*: in
   * place when the served tree is that commit, and on github.com otherwise, where it shows
   * the file the author meant rather than the missing page under `pull/`.
   *
   * @param {RepositoryLink} link
   * @param {MetabrowserPublicRepositoryContext} context
   * @param {"filesystem" | "git_revision"} sourceKind
   * @param {string | null} head
   * @returns {RepositoryLinkTarget | null}
   */
  function textPath(link, context, sourceKind, head) {
    if (typeof head !== "string" || !FULL_REVISION.test(head)) {
      return null;
    }
    const path = link.rest.slice(1);
    if (head.toLowerCase() === context.revision.toLowerCase()) {
      return view(
        path,
        link.directory || path.length === 0,
        link.query,
        link.fragment,
        "revision",
        context,
        sourceKind,
      );
    }
    const url = fileUrl(context, head, path, link.directory, `${link.search}${link.hash}`);
    return url === null ? null : Object.freeze({ kind: "external", url });
  }

  /**
   * A file or folder of the repository at *revision* on github.com, or null without a
   * repository identity or a full commit ID: `blob/` for a file and `tree/` for a folder or
   * the root, each segment escaped, then *suffix*, a serialized query and fragment.
   *
   * @param {MetabrowserPublicRepositoryContext | null | undefined} context
   * @param {string} revision
   * @param {string[]} path The repository path's segments, decoded.
   * @param {boolean} [directory]
   * @param {string} [suffix]
   * @returns {string | null}
   */
  function fileUrl(context, revision, path, directory = false, suffix = "") {
    if (!isRepositoryContext(context) || !FULL_REVISION.test(revision)) {
      return null;
    }
    const kind = directory || path.length === 0 ? "tree" : "blob";
    const encoded = [context.owner, context.name, kind, revision.toLowerCase(), ...path]
      .map(encodeURIComponent)
      .join("/");
    return `https://github.com/${encoded}${directory && path.length > 0 ? "/" : ""}${suffix}`;
  }

  /**
   * A commit's page, by its full ID only: the route refuses anything else
   * (`revision_not_full`). A file anchor is dropped, since only the server can name its
   * file; any other fragment or a query leaves the link external.
   *
   * @param {string} revision
   * @param {RepositoryLink} link
   * @returns {RepositoryLinkTarget | null}
   */
  function commit(revision, link) {
    if (
      !FULL_REVISION.test(revision) ||
      link.query ||
      (link.fragment && !FILE_ANCHOR.test(link.fragment))
    ) {
      return null;
    }
    return route(`/commit/${revision.toLowerCase()}`, "commit");
  }

  /**
   * @param {string} href
   * @param {"commit" | "pulls"} localization
   * @returns {RepositoryLinkTarget}
   */
  function route(href, localization) {
    return Object.freeze({ kind: "route", href, localization, pull: null });
  }

  /**
   * A pull request's page, `/pull/<n>`, on *tab*, as static/pull-route.js spells it.
   *
   * @param {number} number
   * @param {"" | "files" | "checks"} tab
   * @returns {RepositoryLinkTarget}
   */
  function pullRoute(number, tab) {
    return Object.freeze({
      kind: "route",
      href: tab ? `/pull/${number}/${tab}` : `/pull/${number}`,
      localization: "pull",
      pull: Object.freeze({ number, tab }),
    });
  }

  /**
   * A `/view/` target for *repositoryPath*, a path from the repository's root, or null
   * when it is outside the served root or cannot be spelled on a pin.
   *
   * @param {string[]} repositoryPath
   * @param {boolean} directory
   * @param {string} query Serialized, as the navigation target keeps it.
   * @param {string} fragment Decoded, as the navigation target keeps it.
   * @param {"revision" | "working-tree"} localization
   * @param {MetabrowserPublicRepositoryContext} context
   * @param {"filesystem" | "git_revision"} sourceKind
   * @returns {RepositoryLinkTarget | null}
   */
  function view(repositoryPath, directory, query, fragment, localization, context, sourceKind) {
    const prefix = safeRelativeSegments(context.served_prefix);
    if (!prefix || !startsWithSegments(repositoryPath, prefix)) {
      return null;
    }
    const local = repositoryPath.slice(prefix.length);
    let path = "";
    if (local.length > 0) {
      if (sourceKind === "git_revision") {
        // A pin's addresses carry each segment in the GitPath wire, as every internal link
        // on it does; its shell loads the codec before any other script.
        const wire = window.MetabrowserGitPath?.wire(local.join("/")) ?? null;
        if (wire === null) {
          return null;
        }
        path = wire;
      } else {
        // As a served folder's inventory spells a name (builtin_plugins/markdown/links.js).
        path = local.map((segment) => segment.replaceAll("%", "%25")).join("/");
      }
      if (directory) {
        path += "/";
      }
    }
    /** @type {{path: string, query?: string, fragment?: string}} */
    const target = { path };
    if (query) {
      target.query = query;
    }
    if (fragment) {
      target.fragment = fragment;
    }
    return Object.freeze({ kind: "view", target: Object.freeze(target), localization });
  }

  /**
   * Make every link of *root*, an inert text already reduced to the allowlist, open what
   * `localize` says. Returns how many links it changed.
   *
   * @param {ParentNode} root
   * @param {Pick<MetabrowserPublicSdk, "navigation" | "repository" | "sourceKind">} mb
   * @param {{
   *   text?: {head: string | null},
   *   open?: (route: Extract<RepositoryLinkTarget, {kind: "route"}>) => boolean,
   *   views?: boolean,
   * }} [options]
   *   `text` as `localize` takes it. `open` may open an in-app route other than `/view/`
   *   in place, as a pull request's page opens another's, answering whether it did;
   *   otherwise the browser follows the link. `views: false` leaves every `/view/` target
   *   as written, for a text whose page keeps it while the served pin can change under it,
   *   as a rendered diff does: a route names no revision, a `/view/` address the served one.
   * @returns {number}
   */
  function enhance(root, mb, options = {}) {
    if (mb.repository === null) {
      return 0;
    }
    const sourceKind = mb.sourceKind() === "git_revision" ? "git_revision" : "filesystem";
    let changed = 0;
    for (const anchor of Array.from(root.querySelectorAll("a[href]"))) {
      const resolved = localize(anchor.getAttribute("href") ?? "", mb.repository, {
        sourceKind,
        ...(options.text ? { text: options.text } : {}),
      });
      if (resolved === null || (resolved.kind === "view" && options.views === false)) {
        continue;
      }
      changed += 1;
      if (resolved.kind === "external") {
        anchor.setAttribute("href", resolved.url);
        continue;
      }
      const target = resolved.kind === "view" ? resolved.target : null;
      const routed = resolved.kind === "route" ? resolved : null;
      anchor.setAttribute(
        "href",
        resolved.kind === "view" ? mb.navigation.href(resolved.target) : resolved.href,
      );
      anchor.removeAttribute("target");
      anchor.removeAttribute("rel");
      anchor.setAttribute("data-metabrowser-github-localization", resolved.localization);
      anchor.addEventListener("click", (event) => {
        const mouse = /** @type {MouseEvent} */ (event);
        if (
          mouse.defaultPrevented ||
          mouse.button !== 0 ||
          mouse.altKey ||
          mouse.ctrlKey ||
          mouse.metaKey ||
          mouse.shiftKey
        ) {
          return;
        }
        if (target !== null) {
          mouse.preventDefault();
          void mb.navigation.open(target).catch((error) => {
            console.warn("Could not open the link", error);
          });
        } else if (routed !== null && options.open?.(routed) === true) {
          mouse.preventDefault();
        }
      });
    }
    return changed;
  }

  /**
   * @param {unknown} value
   * @returns {value is MetabrowserPublicRepositoryContext}
   */
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
   * A URL path's segments, decoded, or null when one is empty, a dot segment, or holds a
   * separator, a backslash, or NUL once decoded. A trailing slash is not a segment.
   *
   * @param {string} pathname
   * @returns {string[] | null}
   */
  function decodeSegments(pathname) {
    const raw = pathname.split("/").slice(1);
    if (raw.at(-1) === "") {
      raw.pop();
    }
    if (raw.length > MAX_PATH_SEGMENTS || raw.some((segment) => segment.length === 0)) {
      return null;
    }
    /** @type {string[]} */
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

  /**
   * @param {string} path
   * @returns {string[] | null}
   */
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

  /**
   * @param {string} value
   * @returns {string | null}
   */
  function safeDecode(value) {
    try {
      return decodeURIComponent(value);
    } catch (_error) {
      return null;
    }
  }

  /**
   * @param {string[]} value
   * @param {string[]} prefix
   */
  function startsWithSegments(value, prefix) {
    return prefix.every((segment, index) => value[index] === segment);
  }

  /**
   * @param {string} left
   * @param {string} right
   */
  function sameIdentity(left, right) {
    return left.toLowerCase() === right.toLowerCase();
  }

  window.MetabrowserRepositoryLinks = Object.freeze({ enhance, fileUrl, localize });
})();

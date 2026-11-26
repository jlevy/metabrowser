// What a link in rendered text opens: an in-app page when the link names one in the served
// repository, and otherwise the link as written.
//
// Every surface that shows authored text decides its links here: a Markdown file or a
// folder's README (builtin_plugins/markdown/link-enhancer.js), a pull request's
// description, comments, reviews, and Guided Review notes (builtin_plugins/github), a
// commit's message (static/git-panel.js), and Markdown rendered in a diff
// (builtin_plugins/diff). One decision, so the surfaces cannot drift apart;
// docs/project/specs/active/plan-2026-11-26-in-app-link-resolution.md is its design.
//
// A GitHub URL is `https://github.com/<owner>/<repo>/<page>/<args>`, and this module reads
// it in that order: the host and the repository (`readRepositoryUrl`), then the page, each
// one a handler in `PAGES`. Only a link into the served repository (`metabrowser.repository`,
// read from Git metadata by repository_context.py) is read at all, and what it opens is:
//
// | `github.com/<owner>/<repo>` and then | Opens |
// | --- | --- |
// | nothing, `#<heading>`, or `?tab=readme-ov-file` | `/view/`, the served root and its README |
// | `/tree/<ref>[/<path>]`, `/blob/<ref>/<path>`, `<ref>` the served branch or commit | `/view/<path>` |
// | `/pull/<n>` | `/pull/<n>` |
// | `/pull/<n>/files` or `/changes`, without an anchor | `/pull/<n>/files` |
// | `/pull/<n>/checks` | `/pull/<n>/checks` |
// | `/pull/<n>/commits/<id>`, `/commit/<id>`, with a full commit ID | `/commit/<id>` |
// | `/pulls` | `/pulls` |
// | `/pull/<path>`, in a pull request's text | the file at the head (`textPath`) |
// | anything else | the link as written |
//
// A `/view/` address names whatever revision is served, so a link opens one only for the
// served branch or commit; a pull request's, a commit's, or the list's page names no
// revision. A link to another branch, a tag, another commit, an issue, a comparison, or a
// particular comment stays as written: no in-app address names it, and a link in authored
// text never switches the served pin (diff-markdown.js `markdownTargets` holds the same
// rule).
//
// A pull request's text has its page as its base on the server (pull_text_render.py), so
// a path-relative reference such as `docs/development.md` arrives as github.com resolves it,
// `github.com/<owner>/<repo>/pull/docs/development.md`, where github.com shows a missing page.
// Read with a text context, such an address names the repository's file at the text's
// commit, the head, and opens where Metabrowser can show that file (`textPath`).
//
// The answers are in-app addresses, spelled in one place each (In-app addresses, below),
// or a github.com address, spelled by `fileUrl`. `enhance` applies them to every link of
// an inert text, already reduced to the allowlist (static/inert-html.js).
//
// Loaded on demand (`ensureAsset("repository-links")`) by the views that show authored text
// from a GitHub repository: only a page with a repository identity uses it, and the startup
// scripts are at their transfer budget (performance-budgets.toml). The exact module runs
// browserlessly in tests/dom/repository-links-session.js.

(() => {
  // ── Limits ─────────────────────────────────────────────────────

  /** Bounds URL parsing work for one authored link. */
  const MAX_URL_LENGTH = 16 * 1024;
  /** Bounds path comparison work for one authored link. */
  const MAX_PATH_SEGMENTS = 512;

  // ── GitHub's URL grammar ───────────────────────────────────────

  const HOSTS = new Set(["github.com", "www.github.com"]);
  // GitHub's owner and repository names are ASCII; compared without case only once both
  // are, so a character that folds to an ASCII letter (U+212A KELVIN SIGN to `k`) names no
  // repository here, as it names none on github.com.
  const OWNER_NAME = /^[A-Za-z0-9-]+$/;
  const REPOSITORY_NAME = /^[A-Za-z0-9._-]+$/;
  const FULL_REVISION = /^[0-9a-f]{40}$/i;
  // An abbreviated commit ID, as GitHub accepts one in a `blob` or `tree` URL; it names the
  // served commit only when that commit's full ID begins with it.
  const ABBREVIATED_REVISION = /^[0-9a-f]{7,39}$/i;
  // Keep aligned with view_routes._PULL_NUMBER and static/pull-route.js.
  const PULL_NUMBER = /^[1-9][0-9]{0,9}$/;
  // The pages under a pull request's number on github.com. A path-relative reference in a
  // pull request's text whose first folder is named with digits is a pull request's
  // address only when its next segment is one of these, or absent.
  const PULL_PAGES = new Set(["files", "changes", "checks", "commits"]);
  // GitHub's page that opens a pull request, `pull/new/<branch>`, which `git push` prints.
  const NEW_PULL = "new";
  // The repository page's own query when it shows the README (`?tab=readme-ov-file`, as
  // github.com's README anchors copy), which the served root's Overview shows too.
  const README_TAB = "tab=readme-ov-file";
  // A `%` that starts no escape, which the URL parser leaves in a query as written and the
  // navigation codec refuses (`canonicalizeQuery` in static/navigation.js): such a link is
  // left as it is rather than given an address that cannot be spelled.
  const MALFORMED_ESCAPE = /%(?![0-9A-Fa-f]{2})/;

  // ── Types ──────────────────────────────────────────────────────

  /** @typedef {MetabrowserRepositoryLinkTarget} RepositoryLinkTarget */
  /** @typedef {Extract<RepositoryLinkTarget, {kind: "route"}>} RouteTarget */

  /**
   * @typedef {MetabrowserRepositoryTextContext} TextContext
   *   A pull request's text: `head`, the commit it describes, or null when not known, and
   *   `changes`, the pull request's or stack's number and the paths its comparison changes,
   *   which its Changes tab shows at the head, when the page knows them.
   */

  /**
   * @typedef {{
   *   sourceKind?: "filesystem" | "git_revision",
   *   text?: TextContext,
   *   pathRelative?: boolean,
   *   views?: boolean,
   * }} LocalizeOptions
   *   `sourceKind` is what the served tree is (`metabrowser.sourceKind()`): a pinned
   *   revision addresses its paths in the GitPath wire. `text` is a pull request's text.
   */

  /**
   * One URL into the served repository, read: its page, the page's decoded path segments,
   * whether the path ended in `/`, its query and fragment as a navigation target keeps them
   * (the query serialized, the fragment decoded), and both as written (`search`, `hash`).
   *
   * @typedef {{
   *   page: string, args: string[], directory: boolean,
   *   query: string, fragment: string, search: string, hash: string,
   * }} RepositoryLink
   */

  /**
   * What a page reads a link against: the served repository, what its tree is, and a pull
   * request's text, when the link is in one.
   *
   * @typedef {{
   *   context: MetabrowserPublicRepositoryContext,
   *   sourceKind: "filesystem" | "git_revision",
   *   text: TextContext | undefined,
   *   pathRelative: boolean,
   *   views: boolean,
   * }} Scope
   */

  // ── Reading a URL ──────────────────────────────────────────────

  /**
   * The in-app target of *url*, a replacement for it, or null to leave it as written.
   *
   * @param {string} url An absolute URL, as the page has it.
   * @param {MetabrowserPublicRepositoryContext | null | undefined} context
   * @param {LocalizeOptions} [options]
   * @returns {RepositoryLinkTarget | null}
   */
  function localize(url, context, options = {}) {
    if (!isRepositoryContext(context)) {
      return null;
    }
    const link = readRepositoryUrl(url, context);
    const page = link === null ? undefined : PAGES.get(link.page);
    if (link === null || page === undefined) {
      return null;
    }
    const resolved = page(link, {
      context,
      sourceKind: options.sourceKind === "git_revision" ? "git_revision" : "filesystem",
      text: options.text,
      pathRelative: options.pathRelative === true,
      views: options.views !== false,
    });
    return resolved?.kind === "view" && options.views === false ? null : resolved;
  }

  /**
   * *url* read as a link into the served repository: an `http` or `https` address on
   * github.com, with no credentials or port, whose first two segments name the repository,
   * compared without case and with one trailing `.git` removed. Null for anything else,
   * and for a path or fragment that does not decode, a dot segment, an encoded separator,
   * backslash, or NUL, and a query no in-app address could carry.
   *
   * @param {string} url
   * @param {MetabrowserPublicRepositoryContext} context
   * @returns {RepositoryLink | null}
   */
  function readRepositoryUrl(url, context) {
    if (typeof url !== "string" || url.length > MAX_URL_LENGTH) {
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
      !OWNER_NAME.test(segments[0]) ||
      !REPOSITORY_NAME.test(segments[1]) ||
      !sameIdentity(segments[0], context.owner) ||
      !sameIdentity(segments[1].replace(/\.git$/i, ""), context.name)
    ) {
      return null;
    }
    const fragment = parsed.hash.length > 1 ? safeDecode(parsed.hash.slice(1)) : "";
    if (fragment === null || fragment.includes("\0") || MALFORMED_ESCAPE.test(parsed.search)) {
      return null;
    }
    return {
      page: segments[2] ?? "",
      args: segments.slice(3),
      directory: parsed.pathname.endsWith("/"),
      query: parsed.search.length > 1 ? parsed.search.slice(1) : "",
      fragment,
      search: parsed.search,
      hash: parsed.hash,
    };
  }

  // ── GitHub's pages ─────────────────────────────────────────────

  /**
   * The page each URL names, by its third segment, and what it opens; a page not listed
   * here has no in-app counterpart (`issues`, `compare`, `commits`, `wiki`, `raw`, ...).
   *
   * @type {ReadonlyMap<string, (link: RepositoryLink, scope: Scope) => RepositoryLinkTarget | null>}
   */
  const PAGES = new Map([
    ["", repositoryPage],
    ["blob", (link, scope) => revisionPage(link, scope, false)],
    ["tree", (link, scope) => revisionPage(link, scope, true)],
    ["pull", pullPage],
    ["commit", commitPage],
    ["pulls", pullsPage],
  ]);

  /**
   * `github.com/<owner>/<repo>`: the repository's page, which shows its default branch's
   * README. Here the served root does, in its Overview, whose fragment scrolls the README
   * as the page's anchor does there. Only when the served root is the repository's root.
   *
   * @param {RepositoryLink} link
   * @param {Scope} scope
   * @returns {RepositoryLinkTarget | null}
   */
  function repositoryPage(link, scope) {
    if (link.query && link.query !== README_TAB) {
      return null;
    }
    return viewTarget(scope, [], true, "", link.fragment, "working-tree");
  }

  /**
   * `blob/<ref>/<path>` and `tree/<ref>[/<path>]`: a file, and a folder or a branch's root,
   * in place when the reference is the served commit, by its full or abbreviated ID, or the
   * served branch, and only then. A branch name may hold slashes, so it is matched as a
   * prefix of the reference and path, as GitHub's own routing reads it.
   *
   * @param {RepositoryLink} link
   * @param {Scope} scope
   * @param {boolean} tree
   * @returns {RepositoryLinkTarget | null}
   */
  function revisionPage(link, scope, tree) {
    const { context } = scope;
    const referenceAndPath = link.args;
    // A tree names a folder, its branch's root among them; a blob names a file.
    const least = tree ? 0 : 1;
    const directory = tree || link.directory;
    const reference = referenceAndPath[0]?.toLowerCase() ?? "";
    if (
      referenceAndPath.length > least &&
      (FULL_REVISION.test(reference) || ABBREVIATED_REVISION.test(reference)) &&
      context.revision.toLowerCase().startsWith(reference)
    ) {
      const path = referenceAndPath.slice(1);
      return viewTarget(scope, path, directory, link.query, link.fragment, "revision");
    }
    const branch = context.branch ? safeRelativeSegments(context.branch) : null;
    if (
      branch &&
      branch.length > 0 &&
      referenceAndPath.length > branch.length + least - 1 &&
      startsWithSegments(referenceAndPath, branch)
    ) {
      const path = referenceAndPath.slice(branch.length);
      return viewTarget(scope, path, directory, link.query, link.fragment, "working-tree");
    }
    return null;
  }

  /**
   * `pull/<n>[/<page>]`: a pull request's page, its Changes or Checks tab, or one of its
   * commits. `pull/new/<branch>`, and a number followed by nothing or one of the pull
   * request's pages, is a pull request's address, mapped or not; with a text context, any
   * other address under `pull/` is the repository path a path-relative reference named.
   *
   * @param {RepositoryLink} link
   * @param {Scope} scope
   * @returns {RepositoryLinkTarget | null}
   */
  function pullPage(link, scope) {
    const [number, tab, ...more] = link.args;
    if (number === NEW_PULL) {
      return null;
    }
    if (
      number === undefined ||
      !PULL_NUMBER.test(number) ||
      (tab !== undefined && !PULL_PAGES.has(tab))
    ) {
      return scope.text && scope.pathRelative ? textPath(link, scope, scope.text) : null;
    }
    if (link.query) {
      return null;
    }
    const pull = Number(number);
    if (tab === undefined) {
      return link.fragment ? null : pullRoute(pull, "");
    }
    if (more.length === 0 && (tab === "files" || tab === "changes")) {
      return link.fragment ? null : pullRoute(pull, "files");
    }
    if (more.length === 0 && tab === "checks") {
      return link.fragment ? null : pullRoute(pull, "checks");
    }
    if (more.length === 1 && tab === "commits") {
      return commitTarget(more[0], link);
    }
    return null;
  }

  /**
   * `pull/<path>` in a pull request's text: the repository path a path-relative reference
   * names, at the text's head, opened where Metabrowser can show that file without
   * switching what it serves:
   *
   * 1. in place, when the served tree is the head and serves the path;
   * 2. in the pull request's or stack's Changes, when the comparison changes the file, so
   *    Changes shows it at the head, when the link has no query or anchor to keep;
   * 3. on github.com at the head otherwise, where it shows the file the author meant
   *    rather than the missing page under `pull/`.
   *
   * @param {RepositoryLink} link
   * @param {Scope} scope
   * @param {TextContext} text
   * @returns {RepositoryLinkTarget | null}
   */
  function textPath(link, scope, text) {
    const { head } = text;
    const path = link.args;
    // A bare `pull` is an absolute address, not a reference relative to the page.
    if (typeof head !== "string" || !FULL_REVISION.test(head) || path.length === 0) {
      return null;
    }
    const here =
      scope.views &&
      scope.sourceKind === "git_revision" &&
      head.toLowerCase() === scope.context.revision.toLowerCase()
        ? viewTarget(scope, path, link.directory, link.query, link.fragment, "revision")
        : null;
    if (here !== null) {
      return here;
    }
    const file = path.join("/");
    if (
      scope.views &&
      text.changes &&
      !link.directory &&
      !link.query &&
      !link.fragment &&
      text.changes.files.has(file)
    ) {
      return changesRoute(text.changes, file);
    }
    const url = fileUrl(scope.context, head, path, link.directory, `${link.search}${link.hash}`);
    return url === null ? null : Object.freeze({ kind: "external", url });
  }

  /**
   * `commit/<id>`: a commit's page.
   *
   * @param {RepositoryLink} link
   * @returns {RepositoryLinkTarget | null}
   */
  function commitPage(link) {
    return link.args.length === 1 ? commitTarget(link.args[0], link) : null;
  }

  /**
   * `pulls`: the repository's pull requests, when no query filters them, which the list
   * here would not read.
   *
   * @param {RepositoryLink} link
   * @returns {RepositoryLinkTarget | null}
   */
  function pullsPage(link) {
    return link.args.length === 0 && !link.query && !link.fragment ? pullsRoute() : null;
  }

  /**
   * A commit's page, for `commit/<id>` and `pull/<n>/commits/<id>`, by its full ID only:
   * the route refuses anything else (`revision_not_full`). Keep links with a fragment or
   * query on GitHub so they reach the requested location.
   *
   * @param {string} revision
   * @param {RepositoryLink} link
   * @returns {RepositoryLinkTarget | null}
   */
  function commitTarget(revision, link) {
    if (!FULL_REVISION.test(revision) || link.query || link.fragment) {
      return null;
    }
    return commitRoute(revision);
  }

  // ── In-app addresses ───────────────────────────────────────────
  //
  // Each in-app address is spelled here and nowhere else in this module, as the shell's
  // routes spell it (static/navigation.js for `/view/` and `/commit/`, static/pull-route.js
  // for `/pull/`, `/stack/`, and `/pulls`; view_routes.py on the server).

  /**
   * A `/view/` target for *repositoryPath*, a path from the repository's root, or null
   * when it is outside the served root or cannot be spelled on a pin. The navigation API
   * spells its address (`metabrowser.navigation.href`).
   *
   * @param {Scope} scope
   * @param {string[]} repositoryPath
   * @param {boolean} directory
   * @param {string} query Serialized, as the navigation target keeps it.
   * @param {string} fragment Decoded, as the navigation target keeps it.
   * @param {"revision" | "working-tree"} localization
   * @returns {RepositoryLinkTarget | null}
   */
  function viewTarget(scope, repositoryPath, directory, query, fragment, localization) {
    const prefix = safeRelativeSegments(scope.context.served_prefix);
    if (!prefix || !startsWithSegments(repositoryPath, prefix)) {
      return null;
    }
    const local = repositoryPath.slice(prefix.length);
    let path = "";
    if (local.length > 0) {
      if (scope.sourceKind === "git_revision") {
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
   * A pull request's page, `/pull/<n>`, on *tab*.
   *
   * @param {number} number
   * @param {"" | "files" | "checks"} tab
   * @returns {RouteTarget}
   */
  function pullRoute(number, tab) {
    return Object.freeze({
      kind: "route",
      href: tab ? `/pull/${number}/${tab}` : `/pull/${number}`,
      localization: "pull",
      pull: Object.freeze({ number, tab, file: "", stack: false }),
    });
  }

  /**
   * One changed file in a pull request's Changes, `/pull/<n>/files/<path>`, or a stack's,
   * `/stack/<n>/changes/<path>`, each segment escaped as static/pull-route.js
   * (`tabbedHref`) escapes it.
   *
   * @param {NonNullable<TextContext["changes"]>} changes
   * @param {string} file
   * @returns {RouteTarget}
   */
  function changesRoute(changes, file) {
    const tab = changes.stack ? "changes" : "files";
    const encoded = file.split("/").map(encodeURIComponent).join("/");
    return Object.freeze({
      kind: "route",
      href: `/${changes.stack ? "stack" : "pull"}/${changes.number}/${tab}/${encoded}`,
      localization: "pull",
      pull: Object.freeze({ number: changes.number, tab, file, stack: changes.stack }),
    });
  }

  /**
   * A commit's page, `/commit/<id>`, by its full ID, lowercased.
   *
   * @param {string} revision
   * @returns {RouteTarget}
   */
  function commitRoute(revision) {
    return Object.freeze({
      kind: "route",
      href: `/commit/${revision.toLowerCase()}`,
      localization: "commit",
      pull: null,
    });
  }

  /**
   * The repository's pull requests, `/pulls`.
   *
   * @returns {RouteTarget}
   */
  function pullsRoute() {
    return Object.freeze({ kind: "route", href: "/pulls", localization: "pulls", pull: null });
  }

  // ── github.com addresses ───────────────────────────────────────

  /**
   * A file or folder of the repository at *revision* on github.com, or null without a
   * repository identity, a full commit ID, or a path every segment of which is a name:
   * `blob/` for a file and `tree/` for a folder or the root, each segment escaped, then
   * *suffix*, a serialized query and fragment.
   *
   * @param {MetabrowserPublicRepositoryContext | null | undefined} context
   * @param {string} revision
   * @param {string[]} path The repository path's segments, decoded.
   * @param {boolean} [directory]
   * @param {string} [suffix]
   * @returns {string | null}
   */
  function fileUrl(context, revision, path, directory = false, suffix = "") {
    if (
      !isRepositoryContext(context) ||
      !FULL_REVISION.test(revision) ||
      path.some(
        (segment) => segment === "" || segment === "." || segment === ".." || segment.includes("/"),
      )
    ) {
      return null;
    }
    const kind = directory || path.length === 0 ? "tree" : "blob";
    let encoded;
    try {
      encoded = [context.owner, context.name, kind, revision.toLowerCase(), ...path]
        .map(encodeURIComponent)
        .join("/");
    } catch (_error) {
      // A lone surrogate, which no URL can spell.
      return null;
    }
    return `https://github.com/${encoded}${directory && path.length > 0 ? "/" : ""}${suffix}`;
  }

  /**
   * The file a pin's `/view/<GitPath wire>[#<fragment>]` address names, at *revision* on
   * github.com: what a rendered diff's link to a file of the head opens when the page does
   * not show that head (builtin_plugins/diff/index.js). Null for an address that is not a
   * pin's, and for a name the wire holds that is not text, which github.com cannot spell.
   * It reads the wire with the GitPath codec (static/git-path.js), which the caller loads.
   *
   * @param {MetabrowserPublicRepositoryContext | null | undefined} context
   * @param {string} revision
   * @param {string} href
   * @returns {string | null}
   */
  function viewFileUrl(context, revision, href) {
    if (!href.startsWith("/view/")) {
      return null;
    }
    const [wire = "", fragment] = href.slice("/view/".length).split("#", 2);
    const path = window.MetabrowserGitPath?.text(wire) ?? null;
    // biome-ignore lint/suspicious/noControlCharactersInRegex: GitHub rejects C0 and DEL in URL paths.
    if (path === null || /[\\\u0000-\u001f\u007f]/.test(path)) {
      return null;
    }
    return fileUrl(
      context,
      revision,
      path.split("/"),
      false,
      fragment === undefined ? "" : `#${fragment}`,
    );
  }

  // ── Applying it to a text ──────────────────────────────────────

  // Read the sanitized attributes again as the comparison becomes available or the pin
  // changes. Keeping the original lets a later pass undo an earlier rewrite.
  /** @type {WeakMap<Element, {href: string, target: string | null, rel: string | null}>} */
  const authoredLinks = new WeakMap();
  // The tooltip of a link that opens whatever revision is served, not the one it named.
  const WORKING_TREE_TITLE = "Open the corresponding path in the currently served working tree.";
  /**
   * What a plain click on each link `enhance` made in-app opens, read at the click, so a
   * later pass changes it without a second listener.
   *
   * @type {WeakMap<Element, {resolved: RepositoryLinkTarget, mb: Pick<MetabrowserPublicSdk, "navigation">, open: ((route: RouteTarget) => boolean) | undefined}>}
   */
  const opens = new WeakMap();
  /**
   * Each link `enhance` has given its one click listener, kept apart from `opens`, which a
   * link loses while it goes outside, so a link that comes back in-app is not given another.
   *
   * @type {WeakSet<Element>}
   */
  const listening = new WeakSet();

  /**
   * Make every link of *root*, an inert text already reduced to the allowlist, open what
   * `localize` says. An in-app link loses `target` and `rel`, since it does not leave the
   * page, and a plain click opens it in place, as a Markdown file's links do: a `/view/`
   * target through `metabrowser.navigation.open`, and any other in-app page, a pull
   * request's, the list's, or a commit's, through `metabrowser.navigation.openRoute`. A
   * modified click, a new tab, and a copied address use the same `href`, and so does a
   * plain click the shell cannot open in place. Returns how many links it changed.
   *
   * It may run again over the same text with more context, and then reads each link as the
   * text wrote it and moves its one click handler to the new answer.
   *
   * @param {ParentNode} root
   * @param {Pick<MetabrowserPublicSdk, "navigation" | "repository" | "sourceKind">} mb
   * @param {{
   *   text?: TextContext,
   *   open?: (route: RouteTarget) => boolean,
   *   views?: boolean,
   * }} [options]
   *   `text` as `localize` takes it. `open` may open an in-app route other than `/view/`
   *   in place itself, as a pull request's page opens another's, answering whether it did;
   *   otherwise the shell opens it (`navigation.openRoute`), so no text's route link is a
   *   page load while the shell can show it. `views: false` leaves every `/view/` target
   *   as written, for a text whose page keeps it while the served pin can change under it,
   *   as a rendered diff does away from its head: a route names no revision, a `/view/`
   *   address the served one. A later pass with `views: false` restores each `/view/`
   *   target an earlier one made to the link the text wrote, whose click is the browser's.
   * @returns {number}
   */
  function enhance(root, mb, options = {}) {
    if (!mb.repository) {
      return 0;
    }
    const sourceKind = mb.sourceKind() === "git_revision" ? "git_revision" : "filesystem";
    let changed = 0;
    for (const anchor of Array.from(root.querySelectorAll("a[href]"))) {
      const original = authoredLinks.get(anchor);
      const authored = original?.href ?? anchor.getAttribute("href") ?? "";
      const resolved = localize(authored, mb.repository, {
        sourceKind,
        pathRelative: anchor.getAttribute("data-metabrowser-path-relative") === "",
        ...(options.text ? { text: options.text } : {}),
        ...(options.views === false ? { views: false } : {}),
      });
      if (resolved === null) {
        if (original) {
          restoreAuthoredLink(anchor, original);
        }
        continue;
      }
      let href;
      try {
        href =
          resolved.kind === "view"
            ? mb.navigation.href(resolved.target)
            : resolved.kind === "route"
              ? resolved.href
              : resolved.url;
      } catch (error) {
        // An address the codec will not spell leaves this link as written, and the text's
        // other links are still read.
        console.warn("metabrowser: a link was left as written", error);
        if (original) {
          restoreAuthoredLink(anchor, original);
        }
        continue;
      }
      changed += 1;
      if (!original) {
        authoredLinks.set(anchor, {
          href: authored,
          target: anchor.getAttribute("target"),
          rel: anchor.getAttribute("rel"),
        });
      }
      anchor.removeAttribute("data-tip-text");
      anchor.setAttribute("href", href);
      if (resolved.kind === "external") {
        // It leaves the page, as the allowlist's outside links do.
        anchor.setAttribute("target", "_blank");
        anchor.setAttribute("rel", "noopener noreferrer");
        anchor.removeAttribute("data-metabrowser-github-localization");
        opens.delete(anchor);
        continue;
      }
      anchor.removeAttribute("target");
      anchor.removeAttribute("rel");
      anchor.setAttribute("data-metabrowser-github-localization", resolved.localization);
      if (resolved.kind === "view" && resolved.localization === "working-tree") {
        // The app's own tooltip (devtools/check_tooltips.py), which an inert text, keeping no
        // attribute of its own, cannot have set.
        anchor.setAttribute("data-tip-text", WORKING_TREE_TITLE);
      }
      opens.set(anchor, { resolved, mb, open: options.open });
      if (!listening.has(anchor)) {
        listening.add(anchor);
        anchor.addEventListener("click", (event) => openOnPlainClick(anchor, event));
      }
    }
    return changed;
  }

  /**
   * @param {Element} anchor
   * @param {{href: string, target: string | null, rel: string | null}} original
   */
  function restoreAuthoredLink(anchor, original) {
    for (const [name, value] of Object.entries(original)) {
      if (value === null) {
        anchor.removeAttribute(name);
      } else {
        anchor.setAttribute(name, value);
      }
    }
    anchor.removeAttribute("data-metabrowser-github-localization");
    anchor.removeAttribute("data-tip-text");
    authoredLinks.delete(anchor);
    opens.delete(anchor);
  }

  /**
   * Open what `enhance` last made of *anchor* on a plain primary click: a route by the
   * page's own `open` first, then by the shell's. Any other click is the browser's, which
   * follows the same `href`, as it does a route neither opened.
   *
   * @param {Element} anchor
   * @param {Event} event
   */
  function openOnPlainClick(anchor, event) {
    const mouse = /** @type {MouseEvent} */ (event);
    const opened = opens.get(anchor);
    if (
      !opened ||
      mouse.defaultPrevented ||
      mouse.button !== 0 ||
      mouse.altKey ||
      mouse.ctrlKey ||
      mouse.metaKey ||
      mouse.shiftKey
    ) {
      return;
    }
    const { resolved, mb, open } = opened;
    if (resolved.kind === "view") {
      mouse.preventDefault();
      void mb.navigation.open(resolved.target).catch((error) => {
        console.warn("Could not open the link", error);
      });
    } else if (
      resolved.kind === "route" &&
      (open?.(resolved) === true || mb.navigation.openRoute(resolved.href))
    ) {
      mouse.preventDefault();
    }
  }

  // ── Helpers ────────────────────────────────────────────────────

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

  window.MetabrowserRepositoryLinks = Object.freeze({
    WORKING_TREE_TITLE,
    enhance,
    fileUrl,
    localize,
    viewFileUrl,
  });
})();

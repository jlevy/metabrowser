// The link card: the one tooltip a link that opens a page in Metabrowser shows on pointer
// rest, saying what it opens, that object's title where the app knows it, and that it opens
// here (docs/design-system.md, "Tooltips on Links").
//
// A surface that draws links in authored text registers each one here by identity, with
// what the resolver (static/repository-links.js) said it opens: a resolver's `view` or
// `route` target, a rendered diff's link to a file of its head (`view-head`), or, for a link
// that leaves for another site, its address (`external`), whose card says where it goes,
// since the macOS app's web view shows no status bar and only a GitHub address has a mark
// (`decorateExternalLink`). This module
// then owns everything about the card: one delegated pointer listener per registered root,
// one intent timer, the reads and prefetches a rest starts, and the one renderer, `card`,
// so no surface can draw a card of its own (devtools/check_tooltips.py holds that).
//
// What a rest does, on the page's one tooltip (`mb.tooltip`, static/app.js):
//
// 1. The pointer arrives on a registered link: the card is asked for at once, with what the
//    kind's provider holds now (`known`), and the tooltip waits out its own appear delay.
// 2. The pointer has rested `INTENT_MS`: the provider is asked for a summary and a prefetch
//    of what the click opens. At most one of each is in flight; a newer rest waits for them
//    and none is aborted, since an aborted request counts against the page's `fetch_aborts`
//    budget (explorations/performance-loop/performance-budgets.toml).
// 3. A summary that arrives while the pointer still rests, and changes the card, is asked for
//    again: a tooltip still waiting out its delay takes the newer markup (and waits its delay
//    again from then), and a card already up stays as it is.
// 4. The pointer leaves: the card is put away by its anchor, and `dispose(root)` puts away
//    a root's card, and no other surface's (docs/design-system.md, "A Surface Puts Away
//    Only Its Own Tooltip").
//
// Pointer only: focus never shows a card, and a touch is a tap that opens the link
// (docs/design-system.md, "Tooltip Input Modality"). The reader's press or a focus that moves
// ends the rest the pointer is on: the shell puts the tooltip away on focus, and nothing a
// rest asked for brings its card back, though the pointer stays on the link.
//
// Providers (`provide`) return data, never markup, and `card` escapes every value. This
// module keeps no answer: each provider keeps what it reads, for as long as that stays true,
// retries what failed, and answers what it keeps at once, so the next rest says what the
// page knows then. Loaded
// on demand in the `repository-links` bundle, after the resolver (server.py has the
// measurement). The exact module runs browserlessly in tests/dom/link-previews-session.js.

(() => {
  // ── Timing ─────────────────────────────────────────────────────

  /**
   * How long the pointer rests on a link before its summary and prefetch are asked for: the
   * tree's own hover delay, `FILE_PREFETCH_HOVER_DELAY_MS` in static/app.js, a startup
   * script's constant no other script reads. Chosen there rather than measured
   * (docs/project/architecture/arch-browser-shell.md, "Idle Work"): longer than a held
   * key's repeat or a wheel's event interval, so a pointer crossing a paragraph asks for
   * nothing. tests/test_link_previews_js.py holds the two equal.
   */
  const INTENT_MS = 250;

  // ── Words ──────────────────────────────────────────────────────

  /**
   * Where a link opens, by its subject's `opens`: here, for a page that names what it shows;
   * and, for a link to the served branch, which opens whatever the page serves rather than
   * what it named, the served working tree on a folder's page, or the served revision on a
   * pin's or a mirror's, which serve a revision read from Git objects.
   */
  const OPENS = Object.freeze({
    here: "Opens here in Metabrowser",
    "working-tree": "Opens in the served working tree",
    "served-revision": "Opens at the served revision",
  });
  /** A pull request's tabs, as its page names them (builtin_plugins/github/pull-page.js). */
  const TAB_NAMES = Object.freeze({ files: "Changes", checks: "Checks" });
  const SEPARATOR = " · ";
  // What sets an author's title apart as the author's words (docs/design-system.md,
  // "Tooltips on Links").
  const OPEN_QUOTE = "\u201c";
  const CLOSE_QUOTE = "\u201d";

  // ── Vocabulary ─────────────────────────────────────────────────

  /** @type {ReadonlySet<string>} */
  const KINDS = new Set(["pull", "stack", "commit", "file", "folder", "pulls"]);
  /** @type {ReadonlySet<string>} */
  const STATES = new Set(["open", "closed", "merged", "draft"]);
  const COMMIT_HREF = /^\/commit\/([0-9a-f]{40})$/;
  // The schemes of an address on another site whose card says where it goes.
  /** @type {ReadonlySet<string>} */
  const OUTSIDE_SCHEMES = new Set(["http:", "https:"]);
  /** Bounds URL parsing work for one link, as the resolver's `MAX_URL_LENGTH` does. */
  const MAX_OUTSIDE_URL_LENGTH = 16 * 1024;
  const VIEW_PREFIX = "/view/";
  // The plugin that owns a pull request's state glyphs (builtin_plugins/github/pull-state.js).
  const STATE_GLYPH_PLUGIN = "github";

  // ── Types ──────────────────────────────────────────────────────

  /** @typedef {MetabrowserLinkPreviewTarget} Target */
  /** @typedef {MetabrowserLinkPreviewSubject} Subject */
  /** @typedef {MetabrowserLinkPreview} Preview */
  /** @typedef {MetabrowserLinkPreviewProvider} Provider */
  /** @typedef {MetabrowserPublicSdk} Sdk */

  /**
   * A registered link: its root, what it names, the SDK of the surface that drew it, and
   * its author's title, which the surface took off the link.
   *
   * @typedef {{root: Element, subject: Subject, mb: Sdk, authorTitle: string | null}} Entry
   */

  /**
   * A root's listeners and links, and the SDK of its latest registration.
   *
   * @typedef {{
   *   anchors: Set<Element>,
   *   mb: Sdk,
   *   over: (event: Event) => void,
   *   out: (event: Event) => void,
   * }} Root
   */

  /**
   * The pointer's rest on one link: its timer, whether the intent delay has passed, whether
   * this rest has asked for its summary and its prefetch, the summary it was answered, the
   * markup it last asked the tooltip for, and whether the reader's press or a focus has ended
   * it while the pointer stays on the link (`endOnInput`).
   *
   * @typedef {{
   *   anchor: Element,
   *   entry: Entry,
   *   timer: ReturnType<typeof setTimeout> | null,
   *   intent: boolean,
   *   asked: boolean,
   *   prefetched: boolean,
   *   answer: Preview | null | undefined,
   *   html: string | null,
   *   ended: boolean,
   * }} Rest
   */

  // ── State ──────────────────────────────────────────────────────

  /** Each registered link, by identity: no attribute of a text can make one. */
  /** @type {WeakMap<Element, Entry>} */
  const entries = new WeakMap();
  /** @type {WeakMap<Element, Root>} */
  const roots = new WeakMap();
  /** @type {Map<string, Provider>} */
  const providers = new Map();
  /** The key of the subject whose summary, and whose prefetch, is in flight. */
  /** @type {string | null} */
  let reading = null;
  /** @type {string | null} */
  let prefetching = null;
  /** @type {Rest | null} */
  let current = null;

  /**
   * The github plugin's `pullStateIcon`, once its exports have loaded, which the first
   * summary that gives a state asks for, as static/source-ref-selector.js does.
   *
   * @type {MetabrowserGithubPullStateIcon | null}
   */
  let drawPullState = null;
  /** @type {"idle" | "loading" | "loaded" | "failed"} */
  let stateGlyphs = "idle";
  /** A pull request's mark by its state, or "" for none known, as decorated (`pullMark`). */
  /** @type {Map<string, string>} */
  const pullMarks = new Map();

  // ── What a target names ────────────────────────────────────────

  /**
   * What *target* names, or null for a target the card says nothing of: a pull request, one
   * of its tabs or changed files, a stack's changed file, a commit, a file or folder, the
   * pull request list, or a page on another site, by its `http` or `https` address and the
   * host it names. A `/view/` target's path is read as *sourceKind* spells it: a pin's
   * in the GitPath wire (static/git-path.js), a folder's as its inventory escapes `%`. A
   * rendered diff's head link is always a pin's address, as `viewFileUrl` in
   * static/repository-links.js reads it. A path that does not decode names nothing a card
   * can say, so it has none. A file's or folder's subject also keeps the navigation target
   * as the address spelled it (`target`), so a provider looks it up and opens it by the
   * resolver's own spelling rather than spelling the display path again: a view target's
   * own, and a head link's wire path with its fragment decoded. Pure.
   *
   * @param {Target | null | undefined} target
   * @param {"filesystem" | "git_revision"} [sourceKind] The page's (`mb.sourceKind()`).
   * @returns {Subject | null}
   */
  function subject(target, sourceKind = pageSourceKind()) {
    if (!target || typeof target !== "object") {
      return null;
    }
    if (target.kind === "route") {
      return routeSubject(target);
    }
    if (target.kind === "external") {
      return outsideSubject(target.url);
    }
    if (target.kind === "view") {
      const pinned = sourceKind === "git_revision";
      /** @type {"here" | "working-tree" | "served-revision"} */
      let opens = "here";
      if (target.localization === "working-tree") {
        opens = pinned ? "served-revision" : "working-tree";
      }
      return pathSubject(target.target, pinned, opens);
    }
    if (target.kind === "view-head" && typeof target.href === "string") {
      if (!target.href.startsWith(VIEW_PREFIX)) {
        return null;
      }
      const address = target.href.slice(VIEW_PREFIX.length);
      const cut = address.indexOf("#");
      if (cut < 0) {
        return pathSubject({ path: address }, true, "here");
      }
      const fragment = safeDecode(address.slice(cut + 1));
      return fragment === null
        ? null
        : pathSubject(
            { path: address.slice(0, cut), ...(fragment ? { fragment } : {}) },
            true,
            "here",
          );
    }
    return null;
  }

  /**
   * A page on another site, by an `http` or `https` address with a host, as the URL parser
   * reads it: its host is where the address goes, whatever its user name says, and is in
   * ASCII, so a name that only looks like another site's says which it is. An address with
   * no scheme of its own (`//example.com/`) takes the page's, as the browser follows it.
   *
   * @param {unknown} url
   * @returns {Subject | null}
   */
  function outsideSubject(url) {
    if (typeof url !== "string" || url.length > MAX_OUTSIDE_URL_LENGTH) {
      return null;
    }
    const scheme = window.location?.protocol === "http:" ? "http:" : "https:";
    let parsed;
    try {
      parsed = new URL(url.startsWith("//") ? `${scheme}${url}` : url);
    } catch (_error) {
      return null;
    }
    if (!OUTSIDE_SCHEMES.has(parsed.protocol) || parsed.host === "") {
      return null;
    }
    return Object.freeze({ kind: "external", url: parsed.href, host: parsed.host });
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
   * @param {Extract<Target, {kind: "route"}>} target
   * @returns {Subject | null}
   */
  function routeSubject(target) {
    const pull = target.pull;
    if (target.localization === "pull" && pull) {
      if (!Number.isSafeInteger(pull.number) || pull.number < 1 || typeof pull.file !== "string") {
        return null;
      }
      if (pull.stack) {
        return Object.freeze({ kind: "stack", number: pull.number, file: pull.file });
      }
      const tab = pull.tab === "changes" ? "files" : pull.tab;
      if (tab !== "" && tab !== "files" && tab !== "checks") {
        return null;
      }
      return Object.freeze({ kind: "pull", number: pull.number, tab, file: pull.file });
    }
    if (target.localization === "commit") {
      const match = COMMIT_HREF.exec(target.href);
      return match ? Object.freeze({ kind: "commit", revision: match[1] }) : null;
    }
    if (target.localization === "pulls" && target.href === "/pulls") {
      return Object.freeze({ kind: "pulls" });
    }
    return null;
  }

  /**
   * A file or folder by its navigation target: a folder when its path ends in `/` or is the
   * root. The target is kept, copied, with only the fields a navigation target has.
   *
   * @param {Extract<Target, {kind: "view"}>["target"] | undefined} address
   * @param {boolean} wire Whether the path is in the GitPath wire.
   * @param {"here" | "working-tree" | "served-revision"} opens
   * @returns {Subject | null}
   */
  function pathSubject(address, wire, opens) {
    const raw = address?.path;
    if (typeof raw !== "string") {
      return null;
    }
    /** @type {{path: string, query?: string, fragment?: string}} */
    const target = { path: raw };
    if (typeof address?.query === "string") {
      target.query = address.query;
    }
    if (typeof address?.fragment === "string") {
      target.fragment = address.fragment;
    }
    const folder = raw === "" || raw.endsWith("/");
    const spelled = folder ? raw.slice(0, -1) : raw;
    /** @type {string | null} */
    let path = "";
    if (spelled !== "") {
      path = wire
        ? (window.MetabrowserGitPath?.text(spelled) ?? null)
        : spelled.replaceAll("%25", "%");
    }
    if (path === null) {
      return null;
    }
    return Object.freeze({
      kind: folder ? "folder" : "file",
      path,
      opens,
      target: Object.freeze(target),
    });
  }

  /** @returns {"filesystem" | "git_revision"} */
  function pageSourceKind() {
    return window.metabrowser?.sourceKind?.() === "git_revision" ? "git_revision" : "filesystem";
  }

  // ── The card ───────────────────────────────────────────────────

  /**
   * The link card's markup: data in, markup out, every value escaped. Its lines, in order,
   * each left out when it says what the reader already sees, the link's own text or a line
   * above, after case and whitespace folding (docs/design-system.md, "Tooltips Add
   * Information"):
   *
   * 1. `.tip-name`: the object's identity, "Pull request #12 · Changes · src/app.py",
   *    "Stack #3", "Commit a1b2c3d", a path, or "Pull requests";
   * 2. the object's title, as every title is drawn (`titleHtml`, static/formatters.js);
   * 3. the author's title, which the surface took off the link, in quotation marks, since
   *    it is the author's words and never the app's;
   * 4. `.tip-detail`: the provider's detail;
   * 5. `.tip-detail`: where it opens, or the provider's `missing`, always.
   *
   * The first line the card keeps leads with the object's mark (`.link-card-name`), so a
   * link whose text is the identity still shows the state its data gives. A card that says
   * an author's title keeps the identity even then, so the author's words never stand in
   * the place of what the app says the link opens.
   *
   * A pull request's mark is its state's glyph only where *preview* gives the state, and
   * the neutral one otherwise: the address alone never establishes a state. Both are the
   * marks `decorateExternalLink` gives a pull request's address (static/plugin-sdk-views.js),
   * the state's from the github plugin's `pullStateIcon` once loaded. A stack's is the
   * registry's `layers`, a file's its type's (`fileTypeIcon`); a folder ends in `/` and a
   * commit is its ID, as the icon catalog has them (docs/design-system-icons.md). A mark
   * needs the page's SDK and is left out without it. Empty for a subject that is not one.
   *
   * A page on another site has one line of its own, in the tooltip's own ink: where it
   * goes, "Opens example.com", and "in a new tab" when *newTab* says the link opens one; an
   * author's title comes after it, as after an identity, and there is no mark and no
   * provider.
   *
   * @param {Subject} target
   * @param {Preview | null | undefined} preview
   * @param {{linkText?: string | null, authorTitle?: string | null, newTab?: boolean}} [options]
   * @returns {string}
   */
  function card(target, preview, options = {}) {
    if (!isSubject(target)) {
      return "";
    }
    if (target.kind === "external") {
      return outsideCard(target, options);
    }
    const answer = normalizePreview(preview);
    const seen = new Set([fold(options.linkText)]);
    /** @param {string | null | undefined} text */
    const adds = (text) => {
      const folded = fold(text);
      if (folded === "" || seen.has(folded)) {
        return false;
      }
      seen.add(folded);
      return true;
    };
    /** @type {Array<[string, string]>} Each line's class and markup. */
    const lines = [];
    const name = identity(target);
    const authored = fold(options.authorTitle);
    // Whether the card says the author's title: words of its own, not the link's text, its
    // identity, or the object's title.
    const speaks =
      authored !== "" &&
      ![options.linkText, name.text, answer?.title].some((said) => fold(said) === authored);
    if (adds(name.text) || speaks) {
      lines.push(["tip-name", name.html]);
    }
    if (answer?.title && adds(answer.title)) {
      lines.push(["link-card-title", titleHtml(answer.title)]);
    }
    if (speaks && adds(options.authorTitle)) {
      const words = String(options.authorTitle).trim();
      lines.push(["link-card-title", `${OPEN_QUOTE}${escapeHtml(words)}${CLOSE_QUOTE}`]);
    }
    if (answer?.detail && adds(answer.detail)) {
      lines.push(["tip-detail", escapeHtml(answer.detail)]);
    }
    lines.push(["tip-detail", escapeHtml(answer?.missing ?? opensHere(target))]);
    const glyph = mark(target, answer);
    return lines
      .map(([className, html], index) =>
        index === 0 && glyph
          ? `<div class="${className} link-card-name">${glyph}<span>${html}</span></div>`
          : `<div class="${className}">${html}</div>`,
      )
      .join("");
  }

  /**
   * A page on another site's card: where it goes, then an author's title, quoted, unless it
   * says the link's own text or where the link goes.
   *
   * @param {Extract<Subject, {kind: "external"}>} target
   * @param {{linkText?: string | null, authorTitle?: string | null, newTab?: boolean}} options
   * @returns {string}
   */
  function outsideCard(target, options) {
    const goes = `Opens ${target.host}${options.newTab === true ? " in a new tab" : ""}`;
    const authored = fold(options.authorTitle);
    const lines = [`<div>${escapeHtml(goes)}</div>`];
    if (authored !== "" && authored !== fold(options.linkText) && authored !== fold(goes)) {
      const words = String(options.authorTitle).trim();
      lines.push(
        `<div class="link-card-title">${OPEN_QUOTE}${escapeHtml(words)}${CLOSE_QUOTE}</div>`,
      );
    }
    return lines.join("");
  }

  /**
   * The first line's words, as text to compare and as markup.
   *
   * @param {Subject} target
   * @returns {{text: string, html: string}}
   */
  function identity(target) {
    if (target.kind === "commit") {
      const short = window.MetabrowserFormatters.shortCommit(target.revision);
      return {
        text: `Commit ${short}`,
        html: `Commit <span class="git-commit-sha">${escapeHtml(short)}</span>`,
      };
    }
    /** @type {string[]} */
    let parts;
    if (target.kind === "pull") {
      const tab = target.tab === "" ? "" : TAB_NAMES[target.tab];
      parts = [`Pull request #${target.number}`, tab, target.file];
    } else if (target.kind === "stack") {
      parts = [`Stack #${target.number}`, target.file ? TAB_NAMES.files : "", target.file];
    } else if (target.kind === "pulls") {
      parts = ["Pull requests"];
    } else if (target.kind === "folder") {
      parts = [`${target.path === "" ? rootName() : target.path}/`];
    } else if (target.kind === "external") {
      parts = [target.host];
    } else {
      parts = [target.path];
    }
    const text = parts.filter(Boolean).join(SEPARATOR);
    return { text, html: escapeHtml(text) };
  }

  /**
   * The served root's name, as a folder's card names it: the served folder's, the last of
   * the served prefix, or else the repository's, as its view header's title names the root
   * by its folder (static/view-header.js). Empty, so the card says `/`, on a page with no
   * repository identity.
   */
  function rootName() {
    const repository = window.metabrowser?.repository;
    if (!repository) {
      return "";
    }
    const prefix = String(repository.served_prefix ?? "").replace(/\/+$/, "");
    return prefix === ""
      ? String(repository.name ?? "")
      : prefix.slice(prefix.lastIndexOf("/") + 1);
  }

  /** @param {Subject} target */
  function opensHere(target) {
    return "opens" in target ? OPENS[target.opens] : OPENS.here;
  }

  /**
   * The first line's mark, or "" where the object has none or the page cannot draw it.
   *
   * @param {Subject} target
   * @param {Preview | null} answer
   * @returns {string}
   */
  function mark(target, answer) {
    const sdk = window.metabrowser;
    let markup = "";
    let classes = "link-card-mark";
    if (target.kind === "pull") {
      markup = pullMark(target.number, answer?.state ?? null);
    } else if (target.kind === "stack") {
      markup = window.MetabrowserIcons?.layers ?? "";
    } else if (target.kind === "file" && typeof sdk?.fileTypeIcon === "function") {
      const icon = sdk.fileTypeIcon(target.path);
      markup = icon.svg;
      classes = ["link-card-mark file-identity-icon", icon.className].filter(Boolean).join(" ");
    }
    return markup ? `<span class="${escapeHtml(classes)}" aria-hidden="true">${markup}</span>` : "";
  }

  /**
   * A pull request's mark as `decorateExternalLink` draws it on the pull request's own
   * github.com address, with its state's glyph from the github plugin when *state* is given
   * and that plugin has loaded, and the neutral pull request mark otherwise. Kept by state,
   * since the address only says it is a pull request's.
   *
   * @param {number} number
   * @param {Preview["state"] | null} state
   */
  function pullMark(number, state) {
    const draw = drawPullState;
    /** @type {"" | NonNullable<Preview["state"]>} The state drawn, or "" for the neutral mark. */
    const shown = state == null || draw === null ? "" : state;
    const kept = pullMarks.get(shown);
    if (kept !== undefined) {
      return kept;
    }
    const sdk = window.metabrowser;
    const repository = sdk?.repository;
    if (typeof sdk?.decorateExternalLink !== "function" || !repository) {
      return "";
    }
    const probe = document.createElement("a");
    const owner = encodeURIComponent(repository.owner);
    const name = encodeURIComponent(repository.name);
    probe.setAttribute("href", `https://github.com/${owner}/${name}/pull/${number}`);
    probe.textContent = `#${number}`;
    sdk.decorateExternalLink(
      probe,
      shown === "" || draw === null ? {} : { icon: draw(shown, { named: false }) },
    );
    const markup = probe.lastElementChild?.innerHTML ?? "";
    if (markup) {
      pullMarks.set(shown, markup);
    }
    return markup;
  }

  /**
   * A provider's answer as the card reads it: its plain-text fields, a known state, or null.
   *
   * @param {unknown} value
   * @returns {Preview | null}
   */
  function normalizePreview(value) {
    if (!value || typeof value !== "object") {
      return null;
    }
    const source = /** @type {Record<string, unknown>} */ (value);
    /** @type {{title?: string, detail?: string, missing?: string, state?: Preview["state"]}} */
    const preview = {};
    for (const field of /** @type {const} */ (["title", "detail", "missing"])) {
      const text = source[field];
      if (typeof text === "string" && text.trim() !== "") {
        preview[field] = text.trim();
      }
    }
    if (typeof source.state === "string" && STATES.has(source.state)) {
      preview.state = /** @type {Preview["state"]} */ (source.state);
    }
    return Object.keys(preview).length > 0 ? Object.freeze(preview) : null;
  }

  /**
   * @param {unknown} value
   * @returns {value is Subject}
   */
  function isSubject(value) {
    if (!value || typeof value !== "object") {
      return false;
    }
    const target = /** @type {Record<string, unknown>} */ (value);
    switch (target.kind) {
      case "pull":
        return (
          Number.isSafeInteger(target.number) &&
          (target.tab === "" || target.tab === "files" || target.tab === "checks") &&
          typeof target.file === "string"
        );
      case "stack":
        return Number.isSafeInteger(target.number) && typeof target.file === "string";
      case "commit":
        return typeof target.revision === "string" && /^[0-9a-f]{40}$/.test(target.revision);
      case "file":
      case "folder":
        return typeof target.path === "string" && Object.hasOwn(OPENS, String(target.opens));
      case "pulls":
        return true;
      case "external":
        return (
          typeof target.url === "string" && typeof target.host === "string" && target.host !== ""
        );
      default:
        return false;
    }
  }

  /**
   * Text as compared with what the reader sees: one space for every run of white space, no
   * case, as the shell compares a tip with its element's text (`tipComparable`, app.js).
   *
   * @param {string | null | undefined} text
   */
  function fold(text) {
    return String(text ?? "")
      .replace(/\s+/g, " ")
      .trim()
      .toLowerCase();
  }

  /** @param {string} title */
  function titleHtml(title) {
    return window.MetabrowserFormatters.titleHtml(title);
  }

  /** @type {Readonly<Record<string, string>>} */
  const ESCAPES = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };

  /** @param {string} text */
  function escapeHtml(text) {
    return String(text).replace(/[&<>"']/g, (character) => ESCAPES[character] ?? character);
  }

  // ── Providers ──────────────────────────────────────────────────

  /**
   * Answer *kind*'s summaries, and optionally prefetch what its links open. A provider keeps
   * what it reads, and for how long, since only it knows when its data goes stale; `known`
   * answers what it keeps now, with no read, for the card the pointer's arrival asks for. A
   * later call replaces the kind's provider.
   *
   * @param {Subject["kind"]} kind
   * @param {Provider} provider
   */
  function provide(kind, provider) {
    if (!KINDS.has(kind) || typeof provider?.summary !== "function") {
      throw new TypeError(`link previews: no provider for ${String(kind)}`);
    }
    providers.set(kind, provider);
  }

  // ── The registry ───────────────────────────────────────────────

  /**
   * Give *anchor*, a link in *root* that opens *target* here, the link card. A later call
   * replaces its entry, and one whose target names no page here forgets it. *mb* is the
   * SDK of the surface that drew the link; *authorTitle* is the title its author wrote,
   * which the surface takes off the link so the reader never sees two tooltips. Returns
   * whether the link has a card.
   *
   * @param {Element} root
   * @param {Element} anchor
   * @param {Target} target
   * @param {Sdk} mb
   * @param {{authorTitle?: string | null}} [options]
   * @returns {boolean}
   */
  function register(root, anchor, target, mb, options = { authorTitle: null }) {
    const named = subject(
      target,
      mb.sourceKind?.() === "git_revision" ? "git_revision" : "filesystem",
    );
    if (named === null) {
      forget(anchor);
      return false;
    }
    const previous = entries.get(anchor);
    if (previous && previous.root !== root) {
      roots.get(previous.root)?.anchors.delete(anchor);
    }
    const authorTitle = typeof options.authorTitle === "string" ? options.authorTitle : null;
    const entry = { root, subject: named, mb, authorTitle };
    entries.set(anchor, entry);
    listen(root, mb).anchors.add(anchor);
    if (current?.anchor === anchor) {
      current.entry = entry;
      current.asked = false;
      current.prefetched = false;
      current.answer = undefined;
      show(current);
      work();
    }
    return true;
  }

  /**
   * Forget *anchor*: it shows no card, and its card is put away.
   *
   * @param {Element} anchor
   */
  function forget(anchor) {
    const entry = entries.get(anchor);
    if (entry === undefined) {
      return;
    }
    entries.delete(anchor);
    roots.get(entry.root)?.anchors.delete(anchor);
    if (current?.anchor === anchor) {
      leave();
      entry.mb.tooltip.hide(anchor);
    }
  }

  /**
   * Forget every link of *root*, stop listening to it, and put away its card, and no
   * other surface's (`mb.tooltip.hide(root)`).
   *
   * @param {Element} root
   */
  function dispose(root) {
    const state = roots.get(root);
    if (state === undefined) {
      return;
    }
    roots.delete(root);
    root.removeEventListener("pointerover", state.over);
    root.removeEventListener("pointerout", state.out);
    for (const anchor of state.anchors) {
      entries.delete(anchor);
    }
    if (current !== null && current.entry.root === root) {
      leave();
    }
    state.mb.tooltip.hide(root);
  }

  /**
   * *root*'s listeners, added at its first registration.
   *
   * @param {Element} root
   * @param {Sdk} mb
   * @returns {Root}
   */
  function listen(root, mb) {
    let state = roots.get(root);
    if (state === undefined) {
      state = {
        anchors: new Set(),
        mb,
        over: (event) => pointerOver(root, event),
        out: (event) => pointerOut(root, event),
      };
      roots.set(root, state);
      root.addEventListener("pointerover", state.over);
      root.addEventListener("pointerout", state.out);
    }
    state.mb = mb;
    return state;
  }

  // ── The pointer ────────────────────────────────────────────────

  /**
   * The registered link of *root* at or above *node*, or null.
   *
   * @param {Element} root
   * @param {EventTarget | null} node
   * @returns {Element | null}
   */
  function anchorOf(root, node) {
    for (let at = /** @type {Node | null} */ (node); at !== null && at !== root; ) {
      const element = /** @type {Element} */ (at);
      if (entries.get(element)?.root === root) {
        return element;
      }
      at = at.parentNode;
    }
    return null;
  }

  /**
   * The pointer moved onto something in *root*: a rest begins on a registered link it was
   * not already on. Moving within a link, onto any of its descendants, changes nothing.
   *
   * @param {Element} root
   * @param {Event} event
   */
  function pointerOver(root, event) {
    if (/** @type {PointerEvent} */ (event).pointerType === "touch") {
      return;
    }
    const anchor = anchorOf(root, event.target);
    const entry = anchor === null ? undefined : entries.get(anchor);
    if (anchor === null || entry === undefined || current?.anchor === anchor) {
      return;
    }
    if (current !== null) {
      const left = current;
      leave();
      left.entry.mb.tooltip.hide(left.anchor);
    }
    /** @type {Rest} */
    const rest = {
      anchor,
      entry,
      timer: null,
      intent: false,
      asked: false,
      prefetched: false,
      answer: undefined,
      html: null,
      ended: false,
    };
    current = rest;
    show(rest);
    rest.timer = setTimeout(() => {
      rest.timer = null;
      rest.intent = true;
      work();
    }, INTENT_MS);
  }

  /**
   * The pointer left something in *root*: the rest ends when it left the link it rests on
   * for anything outside that link.
   *
   * @param {Element} root
   * @param {Event} event
   */
  function pointerOut(root, event) {
    const rest = current;
    if (rest === null || rest.entry.root !== root) {
      return;
    }
    const related = /** @type {PointerEvent} */ (event).relatedTarget;
    if (related !== null && rest.anchor.contains(/** @type {Node} */ (related))) {
      return;
    }
    if (anchorOf(root, event.target) !== rest.anchor) {
      return;
    }
    leave();
    rest.entry.mb.tooltip.hide(rest.anchor);
  }

  /** End the current rest: its timer, and its claim on answers that arrive later. */
  function leave() {
    if (current?.timer != null) {
      clearTimeout(current.timer);
    }
    current = null;
  }

  /**
   * The reader pressed, or focus moved, which never shows a card (docs/design-system.md,
   * "Tooltip Input Modality"): the current rest asks for nothing more, and no answer that
   * arrives later, no state glyph, and no later registration shows its card again. The shell
   * has put the tooltip away on the focus (`hideTooltipOnFocus` in static/app.js). The rest
   * stays the pointer's until it leaves the link, so moving within it changes nothing, and
   * leaving puts away a card a focus repair kept. Listened for on the document, in the
   * capture phase, so a press or focus a surface stops still ends it.
   */
  function endOnInput() {
    const rest = current;
    if (rest === null) {
      return;
    }
    if (rest.timer !== null) {
      clearTimeout(rest.timer);
      rest.timer = null;
    }
    rest.ended = true;
  }

  /**
   * Ask the tooltip for *rest*'s card, with the summary the rest was answered, or else what
   * its provider holds now, unless the reader's press or a focus has ended the rest. Markup
   * the rest already asked for is not asked for again, since a tooltip still waiting would
   * wait its whole delay again.
   *
   * @param {Rest} rest
   */
  function show(rest) {
    if (rest.ended) {
      return;
    }
    const { anchor, entry } = rest;
    const preview = rest.answer === undefined ? known(entry) : rest.answer;
    const html = card(entry.subject, preview, {
      linkText: anchor.textContent,
      authorTitle: entry.authorTitle,
      newTab: anchor.getAttribute("target") === "_blank",
    });
    if (html === rest.html) {
      return;
    }
    rest.html = html;
    entry.mb.tooltip.show(html, anchor);
  }

  /**
   * What *entry*'s provider holds of its subject now, with no read, or null.
   *
   * @param {Entry} entry
   * @returns {Preview | null}
   */
  function known(entry) {
    const provider = providers.get(entry.subject.kind);
    if (typeof provider?.known !== "function") {
      return null;
    }
    try {
      return normalizePreview(provider.known(entry.subject, { mb: entry.mb }));
    } catch (error) {
      console.warn("metabrowser: a link's kept summary was not read", error);
      return null;
    }
  }

  // ── Reads and prefetches ───────────────────────────────────────

  /** @param {Subject} target */
  function keyOf(target) {
    return JSON.stringify(target);
  }

  /**
   * Start what the current rest wants, once its intent delay has passed, where nothing of
   * the same sort is in flight: its summary and its prefetch, each once a rest. The provider
   * answers what it keeps at once and decides what it reads again. Run again whenever either
   * settles, so a rest that waited starts then, if the pointer is still on it.
   */
  function work() {
    const rest = current;
    if (rest === null || rest.ended || !rest.intent || !rest.anchor.isConnected) {
      return;
    }
    const { subject: target, mb } = rest.entry;
    const provider = providers.get(target.kind);
    if (provider === undefined) {
      return;
    }
    const key = keyOf(target);
    if (reading === null && !rest.asked) {
      rest.asked = true;
      read(provider, target, key, mb);
    }
    if (prefetching === null && typeof provider.prefetch === "function" && !rest.prefetched) {
      rest.prefetched = true;
      prefetch(provider, target, key, mb);
    }
  }

  /**
   * @param {Provider} provider
   * @param {Subject} target
   * @param {string} key
   * @param {Sdk} mb
   */
  function read(provider, target, key, mb) {
    reading = key;
    void Promise.resolve()
      .then(() => provider.summary(target, { mb }))
      .then(
        (value) => {
          const answer = normalizePreview(value);
          if (answer?.state !== undefined) {
            loadStateGlyphs(mb);
          }
          return answer;
        },
        (error) => {
          // Nothing is kept here, so the next rest asks again.
          console.warn("metabrowser: a link's summary was not read", error);
          return undefined;
        },
      )
      .then((answer) => {
        reading = null;
        if (answer !== undefined) {
          answered(key, answer);
        }
        work();
      });
  }

  /**
   * @param {Provider} provider
   * @param {Subject} target
   * @param {string} key
   * @param {Sdk} mb
   */
  function prefetch(provider, target, key, mb) {
    prefetching = key;
    void Promise.resolve()
      .then(() => provider.prefetch?.(target, { mb }))
      .catch((error) => {
        console.warn("metabrowser: a link's page was not prefetched", error);
      })
      .then(() => {
        prefetching = null;
        work();
      });
  }

  /**
   * A summary of the subject *key* names has arrived: the rest on it, which may be a later
   * rest on another link to the same object, says it from now on.
   *
   * @param {string} key
   * @param {Preview | null} answer
   */
  function answered(key, answer) {
    if (current !== null && keyOf(current.entry.subject) === key) {
      current.answer = answer;
      show(current);
    }
  }

  /**
   * Ask again for the card of a rest on a pull request, now that its state's glyph can be
   * drawn: a tooltip still waiting takes it, one already up stays.
   */
  function refreshPulls() {
    if (current !== null && current.entry.subject.kind === "pull") {
      show(current);
    }
  }

  /**
   * Load the github plugin's state glyphs once, for the first summary that gives a state.
   *
   * @param {Sdk} mb
   */
  function loadStateGlyphs(mb) {
    if (stateGlyphs !== "idle" || typeof mb.plugins?.load !== "function") {
      return;
    }
    stateGlyphs = "loading";
    void mb.plugins.load(STATE_GLYPH_PLUGIN).then(
      (exports) => {
        const draw = /** @type {{pullStateIcon?: unknown}} */ (exports).pullStateIcon;
        stateGlyphs = typeof draw === "function" ? "loaded" : "failed";
        if (typeof draw === "function") {
          drawPullState = /** @type {MetabrowserGithubPullStateIcon} */ (draw);
          refreshPulls();
        }
      },
      () => {
        stateGlyphs = "failed";
      },
    );
  }

  document.addEventListener("pointerdown", endOnInput, true);
  document.addEventListener("focusin", endOnInput, true);

  window.MetabrowserLinkPreviews = Object.freeze({
    INTENT_MS,
    OPENS,
    register,
    forget,
    dispose,
    provide,
    subject,
    card,
  });
})();

// The link card: the one tooltip a link that opens a page in Metabrowser shows on pointer
// rest, saying what it opens, that object's title where the app knows it, and that it opens
// here (docs/design-system.md, "Tooltips on Links").
//
// A surface that draws in-app links in authored text registers each one here by identity,
// with what the resolver (static/repository-links.js) said it opens: a resolver's `view` or
// `route` target, or a rendered diff's link to a file of its head (`view-head`). This module
// then owns everything about the card: one delegated pointer listener per registered root,
// one intent timer, the reads and prefetches a rest starts, and the one renderer, `card`,
// so no surface can draw a card of its own (devtools/check_tooltips.py holds that).
//
// What a rest does, on the page's one tooltip (`mb.tooltip`, static/app.js):
//
// 1. The pointer arrives on a registered link: the card is asked for at once, with what the
//    page already knows, and the tooltip waits out its own appear delay.
// 2. The pointer has rested `INTENT_MS`: the kind's provider is asked for a summary and a
//    prefetch of what the click opens. At most one of each is in flight; a newer rest waits
//    for them and none is aborted, since an aborted request counts against the page's
//    `fetch_aborts` budget (explorations/performance-loop/performance-budgets.toml).
// 3. A summary that arrives while the pointer still rests is cached and asked for again: a
//    tooltip still waiting out its delay takes the newer markup (and waits its delay again
//    from then), and a card already up stays as it is. Either way the next rest has it.
// 4. The pointer leaves: the card is put away by its anchor, and `dispose(root)` puts away
//    a root's card, and no other surface's (docs/design-system.md, "A Surface Puts Away
//    Only Its Own Tooltip").
//
// Pointer only: focus never shows a card, and a touch is a tap that opens the link
// (docs/design-system.md, "Tooltip Input Modality").
//
// Providers (`provide`) return data, never markup, and `card` escapes every value. Loaded
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

  const OPENS_HERE = "Opens here in Metabrowser";
  // A link to a branch, which opens whatever the page serves rather than what it named.
  const OPENS_WORKING_TREE = "Opens in the served working tree";
  /** A pull request's tabs, as its page names them (builtin_plugins/github/pull-page.js). */
  const TAB_NAMES = Object.freeze({ files: "Changes", checks: "Checks" });
  const SEPARATOR = " · ";

  // ── Vocabulary ─────────────────────────────────────────────────

  /** @type {ReadonlySet<string>} */
  const KINDS = new Set(["pull", "stack", "commit", "file", "folder", "pulls"]);
  /** @type {ReadonlySet<string>} */
  const STATES = new Set(["open", "closed", "merged", "draft"]);
  const COMMIT_HREF = /^\/commit\/([0-9a-f]{40})$/;
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
   * The pointer's rest on one link: its timer, whether the intent delay has passed, and
   * whether this rest has asked for its summary.
   *
   * @typedef {{
   *   anchor: Element,
   *   entry: Entry,
   *   timer: ReturnType<typeof setTimeout> | null,
   *   intent: boolean,
   *   asked: boolean,
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
  /**
   * Each subject's summary, by its key, once a provider answered: null where it knows
   * nothing. A failed read is not kept, so the next rest asks again. Entries come only from
   * rests, each at least `INTENT_MS` of the reader's pointer, so it grows with reading.
   *
   * @type {Map<string, Preview | null>}
   */
  const answers = new Map();
  /** The subjects whose prefetch has started, by key; each is asked for once a page. */
  /** @type {Set<string>} */
  const prefetched = new Set();
  /** @type {string | null} */
  let reading = null;
  /** @type {string | null} */
  let prefetching = null;
  /** @type {Rest | null} */
  let current = null;
  // A provider may pass this on; nothing here aborts a read (see the head of this file).
  const NEVER_ABORTED = new AbortController().signal;

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
   * What *target* names, or null for a target that opens no page here: a pull request, one
   * of its tabs or changed files, a stack's changed file, a commit, a file or folder, or the
   * pull request list. A `/view/` target's path is read as *sourceKind* spells it: a pin's
   * in the GitPath wire (static/git-path.js), a folder's as its inventory escapes `%`. A
   * rendered diff's head link is always a pin's address, as `viewFileUrl` in
   * static/repository-links.js reads it. A path that does not decode names nothing a card
   * can say, so it has none. Pure.
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
    if (target.kind === "view") {
      const opens = target.localization === "working-tree" ? "working-tree" : "here";
      return pathSubject(target.target?.path, sourceKind === "git_revision", opens);
    }
    if (target.kind === "view-head" && typeof target.href === "string") {
      if (!target.href.startsWith(VIEW_PREFIX)) {
        return null;
      }
      const [wire = ""] = target.href.slice(VIEW_PREFIX.length).split("#", 1);
      return pathSubject(wire, true, "here");
    }
    return null;
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
   * A file or folder by its address's path: a folder when it ends in `/` or is the root.
   *
   * @param {unknown} raw
   * @param {boolean} wire Whether the path is in the GitPath wire.
   * @param {"here" | "working-tree"} opens
   * @returns {Subject | null}
   */
  function pathSubject(raw, wire, opens) {
    if (typeof raw !== "string") {
      return null;
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
    return Object.freeze({ kind: folder ? "folder" : "file", path, opens });
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
   * 3. the author's title, which the surface took off the link;
   * 4. `.tip-detail`: the provider's detail;
   * 5. `.tip-detail`: where it opens, or the provider's `missing`, always.
   *
   * The first line the card keeps leads with the object's mark (`.link-card-name`), so a
   * link whose text is the identity still shows the state its data gives.
   *
   * A pull request's mark is its state's glyph only where *preview* gives the state, and
   * the neutral one otherwise: the address alone never establishes a state. Both are the
   * marks `decorateExternalLink` gives a pull request's address (static/plugin-sdk-views.js),
   * the state's from the github plugin's `pullStateIcon` once loaded. A stack's is the
   * registry's `layers`, a file's its type's (`fileTypeIcon`); a folder ends in `/` and a
   * commit is its ID, as the icon catalog has them (docs/design-system-icons.md). A mark
   * needs the page's SDK and is left out without it. Empty for a subject that is not one.
   *
   * @param {Subject} target
   * @param {Preview | null | undefined} preview
   * @param {{linkText?: string | null, authorTitle?: string | null}} [options]
   * @returns {string}
   */
  function card(target, preview, options = {}) {
    if (!isSubject(target)) {
      return "";
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
    if (adds(name.text)) {
      lines.push(["tip-name", name.html]);
    }
    if (answer?.title && adds(answer.title)) {
      lines.push(["link-card-title", titleHtml(answer.title)]);
    }
    if (options.authorTitle && adds(options.authorTitle)) {
      lines.push(["link-card-title", escapeHtml(options.authorTitle)]);
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
      // The root is `/`, as its view header's Up names it (static/view-header.js).
      parts = [target.path === "" ? "/" : `${target.path}/`];
    } else {
      parts = [target.path];
    }
    const text = parts.filter(Boolean).join(SEPARATOR);
    return { text, html: escapeHtml(text) };
  }

  /** @param {Subject} target */
  function opensHere(target) {
    return "opens" in target && target.opens === "working-tree" ? OPENS_WORKING_TREE : OPENS_HERE;
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
        return (
          typeof target.path === "string" &&
          (target.opens === "here" || target.opens === "working-tree")
        );
      case "pulls":
        return true;
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
   * Answer *kind*'s summaries, and optionally prefetch what its links open. A later call
   * replaces the kind's provider.
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
    const rest = { anchor, entry, timer: null, intent: false, asked: false };
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
   * Ask the tooltip for *rest*'s card, with what the page knows of its subject now.
   *
   * @param {Rest} rest
   */
  function show(rest) {
    const { anchor, entry } = rest;
    const html = card(entry.subject, answers.get(keyOf(entry.subject)) ?? null, {
      linkText: anchor.textContent,
      authorTitle: entry.authorTitle,
    });
    entry.mb.tooltip.show(html, anchor);
  }

  // ── Reads and prefetches ───────────────────────────────────────

  /** @param {Subject} target */
  function keyOf(target) {
    return JSON.stringify(target);
  }

  /**
   * Start what the current rest wants, once its intent delay has passed, where nothing of
   * the same sort is in flight: its summary, unless known or already asked for on this rest,
   * and its prefetch, once a page. Run again whenever either settles, so a rest that waited
   * starts then, if the pointer is still on it.
   */
  function work() {
    const rest = current;
    if (rest === null || !rest.intent || !rest.anchor.isConnected) {
      return;
    }
    const { subject: target, mb } = rest.entry;
    const provider = providers.get(target.kind);
    if (provider === undefined) {
      return;
    }
    const key = keyOf(target);
    if (reading === null && !rest.asked && !answers.has(key)) {
      rest.asked = true;
      read(provider, target, key, mb);
    }
    if (prefetching === null && typeof provider.prefetch === "function" && !prefetched.has(key)) {
      prefetched.add(key);
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
      .then(() => provider.summary(target, { mb, signal: NEVER_ABORTED }))
      .then(
        (value) => {
          const answer = normalizePreview(value);
          answers.set(key, answer);
          if (answer?.state !== undefined) {
            loadStateGlyphs(mb);
          }
          return true;
        },
        (error) => {
          console.warn("metabrowser: a link's summary was not read", error);
          return false;
        },
      )
      .then((known) => {
        reading = null;
        if (known) {
          refresh(key);
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
   * Ask again for the card of a rest on *key*, or on any pull request when *key* is null,
   * now that more is known: a tooltip still waiting takes it, one already up stays.
   *
   * @param {string | null} key
   */
  function refresh(key) {
    if (
      current !== null &&
      (key === null ? current.entry.subject.kind === "pull" : keyOf(current.entry.subject) === key)
    ) {
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
          refresh(null);
        }
      },
      () => {
        stateGlyphs = "failed";
      },
    );
  }

  window.MetabrowserLinkPreviews = Object.freeze({
    INTENT_MS,
    register,
    forget,
    dispose,
    provide,
    subject,
    card,
  });
})();

// What the agents home, the session list, and the Session view share: labels, the one
// stylesheet they load on demand, route errors, and opening a session's file.

/** The agents, as people name them. An agent is a label, never a color. */
const AGENT_LABELS = Object.freeze({ claude: "Claude Code", codex: "Codex" });

/** @param {string} agent */
export function agentLabel(agent) {
  return /** @type {Record<string, string>} */ (AGENT_LABELS)[agent] ?? agent;
}

/**
 * The `folder` parameter for a page's path: the served root is "".
 *
 * @param {string | undefined} path
 */
export function folderParam(path) {
  const value = (path ?? "").replace(/^\/+/, "");
  return value === "." ? "" : value;
}

/**
 * The file a session opens, its first source file.
 *
 * @param {{source_paths?: ReadonlyArray<string>}} row
 * @returns {string | null}
 */
export function sessionFile(row) {
  return row.source_paths?.[0] ?? null;
}

/**
 * The sentence a failed route answers with, or a plain one when it answered with none.
 *
 * @param {unknown} error
 * @returns {{message: string, code: string | null, progress: import("./home-model.js").Progress | null}}
 */
export function refusal(error) {
  const payload = /** @type {{payload?: {error?: unknown, code?: unknown, progress?: unknown}}} */ (
    error
  )?.payload;
  const message = typeof payload?.error === "string" ? payload.error : null;
  const progress = payload?.progress;
  return {
    message: message ?? "The agents data could not be read.",
    code: typeof payload?.code === "string" ? payload.code : null,
    progress:
      progress && typeof progress === "object"
        ? /** @type {import("./home-model.js").Progress} */ (progress)
        : null,
  };
}

/** @type {Map<string, Promise<void>>} */
const sheets = new Map();

/**
 * Load one of the plugin's stylesheets once. The plugin has no `styles.css`, which the
 * shell would load with every folder page (the plugin offers views of that kind), so each
 * view's rules are fetched when the first view that uses them is shown. Resolves when the
 * sheet has loaded or failed; a view that cannot fetch it still reads.
 *
 * @param {string} name The file's name beside this module.
 * @param {Document} doc
 * @returns {Promise<void>}
 */
function ensureSheet(name, doc) {
  let loading = sheets.get(name);
  if (!loading) {
    loading = new Promise((resolve) => {
      const link = doc.createElement("link");
      link.rel = "stylesheet";
      link.href = new URL(`./${name}`, import.meta.url).href;
      link.addEventListener("load", () => resolve(), { once: true });
      link.addEventListener("error", () => resolve(), { once: true });
      doc.head.append(link);
    });
    sheets.set(name, loading);
  }
  return loading;
}

/**
 * The Log, Charts, and Raw views' rules and the event kinds' and tool families' color
 * tokens (`agent-log.css`).
 *
 * @param {Document} [doc]
 * @returns {Promise<void>}
 */
export function ensureLogStyles(doc = document) {
  return ensureSheet("agent-log.css", doc);
}

/**
 * The home's, the list's, and the session page's rules (`agents-views.css`), and the color
 * tokens their event badges and tallies use (`agent-log.css`).
 *
 * @param {Document} [doc]
 * @returns {Promise<void>}
 */
export function ensureViewStyles(doc = document) {
  return Promise.all([ensureSheet("agents-views.css", doc), ensureLogStyles(doc)]).then(() => {});
}

/**
 * Open a session's file on a plain click, leaving a modified click or a middle click to
 * the browser, which opens the anchor's own address.
 *
 * @param {MetabrowserPublicSdk} mb
 * @param {MouseEvent} event
 * @param {HTMLElement} root The view's container: only anchors inside it count.
 * @returns {boolean} True when the click was handled.
 */
export function openSessionLink(mb, event, root) {
  const target = /** @type {Element | null} */ (event.target);
  const anchor = target?.closest?.("a[data-agents-open]");
  if (!anchor || !root.contains(anchor)) {
    return false;
  }
  if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) {
    return false;
  }
  const path = anchor.getAttribute("data-agents-open");
  if (!path) {
    return false;
  }
  event.preventDefault();
  void mb.navigation.open({ path });
  return true;
}

/**
 * An anchor to a session's file, or its title alone when it has no file.
 *
 * @param {MetabrowserPublicSdk} mb
 * @param {string} title
 * @param {string | null} path
 * @param {string} [className]
 */
export function sessionLinkHtml(mb, title, path, className = "agents-session-link") {
  const text = mb.escapeHtml(title);
  if (!path) {
    return `<span class="${className} agents-no-file">${text}</span>`;
  }
  const href = mb.escapeHtml(mb.navigation.href({ path }));
  return `<a class="${className}" href="${href}" data-agents-open="${mb.escapeHtml(path)}">${text}</a>`;
}

/**
 * @param {{title?: string | null, session_id: string}} row
 * @returns {string} A session's title, or its id when it has none.
 */
export function titleOf(row) {
  return row.title?.trim() || row.session_id;
}

/**
 * A count summary's parts as markup, painted by the shell's one painter: each number bold,
 * the comma and the dot between groups muted, the dot hidden from assistive technology
 * (docs/design-system.md, "Count Summaries Bold Their Numbers"). The nodes are the SDK's;
 * this serializes them, since the views paint with `innerHTML`.
 *
 * @param {MetabrowserPublicSdk} mb
 * @param {MetabrowserCountParts} parts
 * @returns {string}
 */
export function countHtml(mb, parts) {
  return mb
    .countPartsNodes(parts)
    .map((node) =>
      typeof node === "string" ? mb.escapeHtml(node) : /** @type {Element} */ (node).outerHTML,
    )
    .join("");
}

/**
 * The dot between a line's groups, with a space either side so a line that wraps breaks
 * after it.
 *
 * @param {MetabrowserPublicSdk} mb
 * @returns {string}
 */
export function separatorHtml(mb) {
  return ` ${countHtml(mb, [{ separator: "·" }])} `;
}

/**
 * Markup groups joined by the design's separator; an empty group is left out.
 *
 * @param {MetabrowserPublicSdk} mb
 * @param {ReadonlyArray<string>} groups
 * @returns {string}
 */
export function joinGroups(mb, groups) {
  return groups.filter((group) => group !== "").join(separatorHtml(mb));
}

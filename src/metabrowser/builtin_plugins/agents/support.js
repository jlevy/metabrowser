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
 * @returns {{message: string, code: string | null}}
 */
export function refusal(error) {
  const payload = /** @type {{payload?: {error?: unknown, code?: unknown}}} */ (error)?.payload;
  const message = typeof payload?.error === "string" ? payload.error : null;
  return {
    message: message ?? "The agents data could not be read.",
    code: typeof payload?.code === "string" ? payload.code : null,
  };
}

/** @type {Promise<void> | null} */
let stylesheet = null;

/**
 * Load the views' stylesheet once, when the first of them mounts. It is not the plugin's
 * `styles.css`, which every folder page and every agent log loads: the home, the list, and
 * the session page are used far less than a folder is opened, so their rules are fetched
 * only when one of them is shown. Resolves when the sheet has loaded or failed; a view
 * that cannot fetch it still reads.
 *
 * @param {Document} [doc]
 * @returns {Promise<void>}
 */
export function ensureViewStyles(doc = document) {
  stylesheet ??= new Promise((resolve) => {
    const link = doc.createElement("link");
    link.rel = "stylesheet";
    link.href = new URL("./agents-views.css", import.meta.url).href;
    link.addEventListener("load", () => resolve(), { once: true });
    link.addEventListener("error", () => resolve(), { once: true });
    doc.head.append(link);
  });
  return stylesheet;
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

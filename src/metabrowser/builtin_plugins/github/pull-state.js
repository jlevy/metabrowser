// A pull request's state, one vocabulary for the Pulls tab's rows and the page's header
// (docs/design-system.md, "The Pulls Tab"): the four states GitHub shows, each with the shape
// GitHub gives it, a color token in GitHub's hue, and a name in the page header's words.
// Color is never the only signal, since the shapes differ and the name is always there.

/** @typedef {"open" | "draft" | "merged" | "closed"} PullState */

/** @type {Readonly<Record<PullState, {icon: string, label: string}>>} */
export const PULL_STATES = Object.freeze({
  open: Object.freeze({ icon: "gitPullRequest", label: "Open" }),
  draft: Object.freeze({ icon: "gitPullRequestDraft", label: "Draft" }),
  merged: Object.freeze({ icon: "gitMerge", label: "Merged" }),
  closed: Object.freeze({ icon: "gitPullRequestClosed", label: "Closed" }),
});

// The four shapes, Lucide v1.17.0 (ISC; https://lucide.dev), by Lucide id. Only a GitHub
// repository's page draws them, so they arrive with this code: in static/icons.js they were 251
// compressed bytes of every folder's startup scripts (check_startup_scripts, 2026-11-03).
const STROKE =
  'viewBox="0 0 24 24" fill="none" stroke="currentColor" ' +
  'stroke-width="2" stroke-linecap="round" stroke-linejoin="round"';
/** @type {Readonly<Record<string, string>>} */
const GLYPHS = Object.freeze({
  gitPullRequest: // Lucide `git-pull-request`
  `<svg ${STROKE}><circle cx="18" cy="18" r="3"/><circle cx="6" cy="6" r="3"/><path d="M13 6h3a2 2 0 0 1 2 2v7"/><line x1="6" x2="6" y1="9" y2="21"/></svg>`,
  gitPullRequestDraft: // Lucide `git-pull-request-draft`
  `<svg ${STROKE}><circle cx="18" cy="18" r="3"/><circle cx="6" cy="6" r="3"/><path d="M18 6V5"/><path d="M18 11v-1"/><line x1="6" x2="6" y1="9" y2="21"/></svg>`,
  gitMerge: // Lucide `git-merge`
  `<svg ${STROKE}><circle cx="18" cy="18" r="3"/><circle cx="6" cy="6" r="3"/><path d="M6 21V9a9 9 0 0 0 9 9"/></svg>`,
  gitPullRequestClosed: // Lucide `git-pull-request-closed`
  `<svg ${STROKE}><circle cx="6" cy="6" r="3"/><path d="M6 9v12"/><path d="m21 3-6 6"/><path d="m21 9-6-6"/><path d="M18 11.5V15"/><circle cx="18" cy="18" r="3"/></svg>`,
});

/**
 * The state GitHub shows: merged and draft before open and closed.
 *
 * A record's pull request says `merged`, and so does a list's row, which the route reads
 * from `merged_at`.
 *
 * @param {Record<string, any>} pull
 * @returns {PullState}
 */
export function displayState(pull) {
  if (pull.merged === true) {
    return "merged";
  }
  if (pull.state === "open") {
    return pull.draft === true ? "draft" : "open";
  }
  return "closed";
}

/** The glyphs, each parsed once: a list has a thousand rows and four shapes. */
/** @type {Map<string, Element | null>} */
const glyphs = new Map();

/** @param {PullState} state */
function glyph(state) {
  let shape = glyphs.get(state);
  if (shape === undefined) {
    const markup = GLYPHS[PULL_STATES[state].icon] ?? "";
    shape = new DOMParser().parseFromString(markup, "text/html").body.firstElementChild;
    glyphs.set(state, shape);
  }
  return shape === null ? null : document.importNode(shape, true);
}

/**
 * The state's icon: this module's constant, not the pull request's text. Browser only.
 *
 * Named by default, for a row, where nothing else says the state. A badge passes
 * `named: false`, as its own text is the name.
 *
 * @param {PullState} state
 * @param {{named?: boolean}} [options]
 */
export function pullStateIcon(state, options = {}) {
  const icon = document.createElement("span");
  icon.className = "github-pull-state-icon";
  icon.dataset.state = state;
  if (options.named === false) {
    icon.setAttribute("aria-hidden", "true");
  } else {
    icon.setAttribute("role", "img");
    icon.setAttribute("aria-label", PULL_STATES[state].label);
    icon.dataset.tipText = PULL_STATES[state].label;
  }
  const shape = glyph(state);
  if (shape !== null) {
    icon.append(shape);
  }
  return icon;
}

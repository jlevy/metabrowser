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

/**
 * @param {PullState} state
 * @param {MetabrowserPublicSdk} mb
 */
function glyph(state, mb) {
  let shape = glyphs.get(state);
  if (shape === undefined) {
    const markup = /** @type {Record<string, string>} */ (/** @type {unknown} */ (mb.icons))[
      PULL_STATES[state].icon
    ];
    shape = new DOMParser().parseFromString(markup || "", "text/html").body.firstElementChild;
    glyphs.set(state, shape);
  }
  return shape === null ? null : document.importNode(shape, true);
}

/**
 * The state's icon: the shell's constant, not the pull request's text. Browser only.
 *
 * Named by default, for a row, where nothing else says the state. A badge passes
 * `named: false`, as its own text is the name.
 *
 * @param {PullState} state
 * @param {MetabrowserPublicSdk} mb
 * @param {{named?: boolean}} [options]
 */
export function pullStateIcon(state, mb, options = {}) {
  const icon = document.createElement("span");
  icon.className = "github-pull-state";
  icon.dataset.state = state;
  if (options.named === false) {
    icon.setAttribute("aria-hidden", "true");
  } else {
    icon.setAttribute("role", "img");
    icon.setAttribute("aria-label", PULL_STATES[state].label);
    icon.dataset.tipText = PULL_STATES[state].label;
  }
  const shape = glyph(state, mb);
  if (shape !== null) {
    icon.append(shape);
  }
  return icon;
}

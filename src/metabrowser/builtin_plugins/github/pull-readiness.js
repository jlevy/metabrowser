// Whether a pull request is ready to merge, one vocabulary for the page's header, its Checks
// tab, and the Pulls tab's rows (docs/design-system.md, "A Pull Request’s Readiness"). The
// server decides the readiness, its verdict, its tone, and its label (pull_readiness.py), and
// this module draws it: one glyph for each verdict, in the color of the readiness's tone. It
// holds no label and no color of its own, so a verdict cannot read one way here and another
// in `metab`. Color is never the only signal, since the glyphs differ and the label is always
// there, as the badge's text or the glyph's accessible name.

/**
 * A verdict, `Verdict` in pull_readiness.py.
 *
 * @typedef {"ready" | "ready_for_review" | "conflicts" | "checks_failing" | "changes_requested"
 *   | "blocked" | "queue_failing" | "queued" | "checks_pending" | "review_required" | "behind"
 *   | "checking"} ReadinessVerdict
 */

/**
 * A verdict's tone, `Tone` in pull_readiness.py: the worst status among its requirements.
 *
 * @typedef {"success" | "attention" | "danger"} ReadinessTone
 */

/**
 * One row of the merge box, `Requirement` in pull_readiness.py.
 *
 * @typedef {{
 *   kind: "queue" | "conflicts" | "checks" | "reviews" | "up_to_date" | "rules",
 *   status: "met" | "waiting" | "unmet" | "unknown",
 *   summary: string,
 *   github_url: string | null,
 * }} ReadinessRequirement
 */

/**
 * A pull request's readiness on the wire, `Readiness` in pull_readiness.py. A closed or merged
 * pull request has none.
 *
 * @typedef {{
 *   verdict: ReadinessVerdict,
 *   tone: ReadinessTone,
 *   label: string,
 *   head: string,
 *   observed_at: string | null,
 *   requirements: ReadonlyArray<ReadinessRequirement>,
 *   auto_merge: {method: "merge" | "squash" | "rebase" | null, enabled_by: string | null,
 *     enabled_at: string | null} | null,
 *   auto_merge_summary: string | null,
 * }} Readiness
 */

/**
 * What a glyph and a badge draw of a readiness, so a row that carries only these draws the
 * same mark as the page that has the whole readiness.
 *
 * @typedef {Pick<Readiness, "verdict" | "tone" | "label">} ShownReadiness
 */

/** @typedef {keyof typeof GLYPHS} ReadinessGlyph */

/**
 * Each verdict's glyph, by this module's name for it. A glyph means one thing: `circleCheck`
 * that nothing blocks the pull request, whether it is ready to merge or, as a draft, ready for
 * review; `listOrdered` that it is in the merge queue, waiting there or leaving it. The label
 * says which.
 *
 * @type {Readonly<Record<ReadinessVerdict, ReadinessGlyph>>}
 */
export const VERDICT_GLYPHS = Object.freeze({
  ready: "circleCheck",
  ready_for_review: "circleCheck",
  conflicts: "triangleAlert",
  checks_failing: "circleX",
  changes_requested: "fileDiff",
  blocked: "ban",
  queue_failing: "listOrdered",
  queued: "listOrdered",
  checks_pending: "clock",
  review_required: "eye",
  behind: "arrowUpToLine",
  checking: "circleDashed",
});

// The shapes, Lucide v1.17.0 (ISC; https://lucide.dev), by Lucide id. Only a GitHub
// repository's page draws them, so they arrive with this code, as the states' do
// (pull-state.js).
const STROKE =
  'viewBox="0 0 24 24" fill="none" stroke="currentColor" ' +
  'stroke-width="2" stroke-linecap="round" stroke-linejoin="round"';
const GLYPHS = Object.freeze({
  circleCheck: // Lucide `circle-check`
  `<svg ${STROKE}><circle cx="12" cy="12" r="10"/><path d="m9 12 2 2 4-4"/></svg>`,
  triangleAlert: // Lucide `triangle-alert`
  `<svg ${STROKE}><path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3"/><path d="M12 9v4"/><path d="M12 17h.01"/></svg>`,
  circleX: // Lucide `circle-x`
  `<svg ${STROKE}><circle cx="12" cy="12" r="10"/><path d="m15 9-6 6"/><path d="m9 9 6 6"/></svg>`,
  fileDiff: // Lucide `file-diff`
  `<svg ${STROKE}><path d="M6 22a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h8a2.4 2.4 0 0 1 1.704.706l3.588 3.588A2.4 2.4 0 0 1 20 8v12a2 2 0 0 1-2 2z"/><path d="M9 10h6"/><path d="M12 13V7"/><path d="M9 17h6"/></svg>`,
  ban: // Lucide `ban`
  `<svg ${STROKE}><circle cx="12" cy="12" r="10"/><path d="M4.929 4.929 19.07 19.071"/></svg>`,
  listOrdered: // Lucide `list-ordered`
  `<svg ${STROKE}><path d="M11 5h10"/><path d="M11 12h10"/><path d="M11 19h10"/><path d="M4 4h1v5"/><path d="M4 9h2"/><path d="M6.5 20H3.4c0-1 2.6-1.925 2.6-3.5a1.5 1.5 0 0 0-2.6-1.02"/></svg>`,
  clock: // Lucide `clock`
  `<svg ${STROKE}><circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/></svg>`,
  eye: // Lucide `eye`
  `<svg ${STROKE}><path d="M2.062 12.348a1 1 0 0 1 0-.696 10.75 10.75 0 0 1 19.876 0 1 1 0 0 1 0 .696 10.75 10.75 0 0 1-19.876 0"/><circle cx="12" cy="12" r="3"/></svg>`,
  arrowUpToLine: // Lucide `arrow-up-to-line`
  `<svg ${STROKE}><path d="M5 3h14"/><path d="m18 13-6-6-6 6"/><path d="M12 7v14"/></svg>`,
  circleDashed: // Lucide `circle-dashed`
  `<svg ${STROKE}><path d="M10.1 2.182a10 10 0 0 1 3.8 0"/><path d="M13.9 21.818a10 10 0 0 1-3.8 0"/><path d="M17.609 3.721a10 10 0 0 1 2.69 2.7"/><path d="M2.182 13.9a10 10 0 0 1 0-3.8"/><path d="M20.279 17.609a10 10 0 0 1-2.7 2.69"/><path d="M21.818 10.1a10 10 0 0 1 0 3.8"/><path d="M3.721 6.391a10 10 0 0 1 2.7-2.69"/><path d="M6.391 20.279a10 10 0 0 1-2.69-2.7"/></svg>`,
});

/** The glyphs, each parsed once: a list has a thousand rows and ten shapes. */
/** @type {Map<ReadinessGlyph, Element | null>} */
const parsed = new Map();

/** @param {ReadinessVerdict} verdict */
function glyph(verdict) {
  const name = VERDICT_GLYPHS[verdict];
  let shape = parsed.get(name);
  if (shape === undefined) {
    const markup = GLYPHS[name] ?? "";
    shape = new DOMParser().parseFromString(markup, "text/html").body.firstElementChild;
    parsed.set(name, shape);
  }
  return shape === null ? null : document.importNode(shape, true);
}

/**
 * The element both forms are: its verdict, for what reads the page, and its tone, which alone
 * sets its color (github/styles.css, "A pull request's readiness").
 *
 * @param {string} className
 * @param {ShownReadiness} readiness
 */
function mark(className, readiness) {
  const element = document.createElement("span");
  element.className = className;
  element.dataset.verdict = readiness.verdict;
  element.dataset.tone = readiness.tone;
  return element;
}

/**
 * The verdict's glyph, in its tone, or null for a pull request with no readiness, as a closed
 * or merged one has none. Browser only.
 *
 * Named by default, for a row, where nothing else says the verdict: its accessible name is the
 * server's label, as a state icon's is the state's (pull-state.js). Text beside it that says
 * the label passes `named: false`, and the glyph is hidden from assistive technology.
 *
 * @param {ShownReadiness | null | undefined} readiness
 * @param {{named?: boolean}} [options]
 */
export function readinessIcon(readiness, options = {}) {
  if (readiness == null) {
    return null;
  }
  const icon = mark("github-pull-readiness-icon", readiness);
  if (options.named === false) {
    icon.setAttribute("aria-hidden", "true");
  } else {
    icon.setAttribute("role", "img");
    icon.setAttribute("aria-label", readiness.label);
  }
  const shape = glyph(readiness.verdict);
  if (shape !== null) {
    icon.append(shape);
  }
  return icon;
}

/**
 * The verdict's badge: the server's label in the outlined form a state's badge has
 * (`stateBadge` in pull-page.js), in the verdict's tone, so the two read as one vocabulary.
 * Null for a pull request with no readiness. Browser only.
 *
 * @param {ShownReadiness | null | undefined} readiness
 */
export function readinessBadge(readiness) {
  if (readiness == null) {
    return null;
  }
  const badge = mark("file-header-badge github-pull-badge github-pull-readiness", readiness);
  badge.textContent = readiness.label;
  return badge;
}

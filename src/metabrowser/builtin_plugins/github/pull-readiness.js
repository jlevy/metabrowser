// A pull request's status, one vocabulary for every surface that draws it: whether it is ready
// to merge, what stands in its way, and each of its checks (docs/design-system.md, "Pull
// Request Status Vocabulary"). One glyph means one thing. The full-size chip is that glyph and
// its label, and the compact form, a Pulls row's column, a stack member's cell, or a narrow
// header, is the same glyph alone, drawn by the same function (`shape`), so a reader learns
// one code. The server decides the readiness, its verdict, its tone, its label, and each
// requirement's tone (pull_readiness.py), and this module draws them: it never infers a color.
// Its only copies of the server's vocabulary are the labels the header's slot is sized by
// (`SLOT_LABELS`), the verdict each requirement heads (`REQUIREMENT_VERDICTS`), the statuses
// worst first (`STATUS_ORDER`), the tones (`TONES`), and a check's tone by its bucket
// (`CHECK_TONES`), each held to the server's by tests/test_github_pull_readiness_js.py. Color
// is never the only signal, since the glyphs differ and the label is always there, as a
// chip's text, the glyph's accessible name, or a row's words.
//
// It loads with the plugin's module graph, as pull-state.js does: the page and the Pulls tab
// that draw it import it statically, and its glyphs are parsed only when first drawn.

/**
 * A verdict, `Verdict` in pull_readiness.py.
 *
 * @typedef {"ready" | "ready_for_review" | "conflicts" | "checks_failing" | "changes_requested"
 *   | "blocked" | "queue_failing" | "queued" | "checks_pending" | "review_required" | "behind"
 *   | "checking" | "status_unavailable"} ReadinessVerdict
 */

/**
 * A verdict's or a requirement's tone, `Tone` in pull_readiness.py: Primer's functional role.
 *
 * @typedef {"success" | "attention" | "severe" | "danger"} ReadinessTone
 */

/**
 * The tone a mark is drawn in: a readiness's, or neutral, a skipped or cancelled check's.
 *
 * @typedef {ReadinessTone | "neutral"} MarkTone
 */

/**
 * A requirement's kind and status, `RequirementKind` and `RequirementStatus` in
 * pull_readiness.py.
 *
 * @typedef {"queue" | "conflicts" | "checks" | "reviews" | "up_to_date" | "rules"} RequirementKind
 * @typedef {"met" | "waiting" | "unmet" | "unknown"} RequirementStatus
 */

/**
 * One row of the merge box, `Requirement` in pull_readiness.py.
 *
 * @typedef {{
 *   kind: RequirementKind,
 *   status: RequirementStatus,
 *   summary: string,
 *   github_url: string | null,
 *   tone: ReadinessTone,
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

/**
 * The readiness a surface draws beside the state it shows: *readiness*, the verdict the server
 * judged with the pull request in *judged*, only where the state *shown* is that one and is
 * open or draft, and null anywhere else. Every surface that draws a verdict draws it through
 * this, so none draws one beside a state the server did not judge it in. Pure.
 *
 * A closed or merged pull request has no readiness. A verdict says what stands in the way of
 * merging an open pull request, or of marking a draft ready, so it says nothing of the pull
 * request in another state: a page that shows the list's state, fresher than its record's
 * (`withListedState` in pull-state.js), draws no verdict once the list has learned of a merge
 * or a draft the record has not, until a read judges the state it shows.
 *
 * @template {ShownReadiness} T
 * @param {T | null} readiness
 * @param {import("./pull-state.js").PullState} judged
 * @param {import("./pull-state.js").PullState} shown
 * @returns {T | null}
 */
export function readinessForState(readiness, judged, shown) {
  return shown === judged && (shown === "open" || shown === "draft") ? readiness : null;
}

/** @typedef {keyof typeof GLYPHS} StatusGlyph */

/**
 * The tones the server gives, `Tone` in pull_readiness.py, so a row drawn from an answer of
 * another build draws only a tone this one colors (row-readiness.js).
 *
 * @type {ReadonlyArray<ReadinessTone>}
 */
export const TONES = Object.freeze(["success", "attention", "severe", "danger"]);

/**
 * Requirement statuses from worst to best, `STATUS_ORDER` in pull_readiness.py: the page's
 * Merge status section says the sentence of the first requirement at the worst of them.
 *
 * @type {ReadonlyArray<RequirementStatus>}
 */
export const STATUS_ORDER = Object.freeze(["unmet", "waiting", "unknown", "met"]);

/**
 * Each verdict's glyph, by this module's name for it. The checks' marks are circles with a mark
 * inside, as GitHub draws a check run's, every other requirement has a shape of its own, and
 * an answer GitHub has not given yet is the empty, dashed circle (docs/design-system.md, "Pull
 * Request Status Vocabulary"). Two verdicts share a glyph only
 * where they mean one thing: `checkCheck` that nothing blocks the pull request, whether it is
 * ready to merge or held by its draft state alone. The label says which.
 *
 * @type {Readonly<Record<ReadinessVerdict, StatusGlyph>>}
 */
export const VERDICT_GLYPHS = Object.freeze({
  ready: "checkCheck",
  ready_for_review: "checkCheck",
  conflicts: "gitMergeConflict",
  checks_failing: "circleX",
  changes_requested: "fileDiff",
  blocked: "shieldBan",
  queue_failing: "listX",
  queued: "listOrdered",
  checks_pending: "clock",
  review_required: "eye",
  behind: "arrowUpToLine",
  checking: "circleDashed",
  status_unavailable: "fileQuestionMark",
});

/**
 * The verdict a requirement heads at each status that stands in the way, `HEADLINES` in
 * pull_readiness.py, so a requirement's row draws the glyph of the verdict it would head and
 * the header's chip and its Merge status row cannot draw one meaning two ways. Any requirement
 * the server has no answer for yet heads `checking`.
 *
 * @type {Readonly<Record<RequirementKind, Readonly<Partial<Record<RequirementStatus, ReadinessVerdict>>>>>}
 */
export const REQUIREMENT_VERDICTS = Object.freeze({
  queue: Object.freeze({ unmet: "queue_failing", waiting: "queued" }),
  conflicts: Object.freeze({ unmet: "conflicts" }),
  checks: Object.freeze({ unmet: "checks_failing", waiting: "checks_pending" }),
  reviews: Object.freeze({ unmet: "changes_requested", waiting: "review_required" }),
  up_to_date: Object.freeze({ waiting: "behind" }),
  rules: Object.freeze({ unmet: "blocked" }),
});

/**
 * The glyph of a requirement that is met, which no verdict names: every check passed, as a
 * check that passed is drawn; the branch merges with no conflicts, the merge's arrow, never the
 * merged state's `gitMerge`; and the changes are approved, the reviewed file with its check, as
 * changes requested is the file with its diff. The other requirements are never met: the
 * server draws a row for them only when they stand in the way.
 *
 * @type {Readonly<Partial<Record<RequirementKind, StatusGlyph>>>}
 */
export const MET_GLYPHS = Object.freeze({
  checks: "circleCheck",
  conflicts: "merge",
  reviews: "fileCheck",
});

/**
 * A requirement's glyph at a status: the verdict's it heads, `checking`'s for any it has no
 * answer for, or its met glyph; null for a pair the server never sends. Pure.
 *
 * @param {string} kind
 * @param {string} status
 * @returns {StatusGlyph | null}
 */
export function requirementGlyph(kind, status) {
  if (!Object.hasOwn(REQUIREMENT_VERDICTS, kind)) {
    return null;
  }
  const at = /** @type {RequirementKind} */ (kind);
  if (status === "unknown") {
    return VERDICT_GLYPHS.checking;
  }
  if (status === "met") {
    return MET_GLYPHS[at] ?? null;
  }
  const verdicts = REQUIREMENT_VERDICTS[at];
  const verdict = Object.hasOwn(verdicts, status)
    ? verdicts[/** @type {RequirementStatus} */ (status)]
    : undefined;
  return verdict === undefined ? null : VERDICT_GLYPHS[verdict];
}

/**
 * The checks requirement's status each bucket of a check stands for: a check that passed is
 * drawn as the checks met, one that failed as the checks failing, and one still running as
 * the checks pending, so a check and the verdict about the checks are one code.
 *
 * @type {Readonly<Record<"pass" | "fail" | "pending", RequirementStatus>>}
 */
const CHECKS_AT = Object.freeze({ pass: "met", fail: "unmet", pending: "waiting" });

/**
 * A check's glyph by the bucket the server sorts it into (`state_bucket` in pull_status.py),
 * as GitHub marks a check run: the checks requirement's glyph for a check that passed, failed,
 * or is pending, and GitHub's own marks, a circle slashed and a circle stopped, for a check
 * skipped (or neutral) and one cancelled. Every check's mark is a circle.
 *
 * @type {Readonly<Record<string, StatusGlyph>>}
 */
export const CHECK_GLYPHS = Object.freeze({
  pass: /** @type {StatusGlyph} */ (requirementGlyph("checks", CHECKS_AT.pass)),
  fail: /** @type {StatusGlyph} */ (requirementGlyph("checks", CHECKS_AT.fail)),
  pending: /** @type {StatusGlyph} */ (requirementGlyph("checks", CHECKS_AT.pending)),
  skipping: "circleSlash",
  cancel: "circleStop",
});

/**
 * A check's tone by its bucket, as `gh pr checks` colors its marks: passing success, failing
 * danger, pending attention, and skipped and cancelled neutral, the muted ink. The first three
 * are the checks requirement's tones at the status the bucket stands for (`CHECKS_AT`), which
 * tests/test_github_pull_readiness_js.py holds to `requirement_tone` in pull_readiness.py.
 *
 * @type {Readonly<Record<string, MarkTone>>}
 */
export const CHECK_TONES = Object.freeze({
  pass: "success",
  fail: "danger",
  pending: "attention",
  skipping: "neutral",
  cancel: "neutral",
});

// The shapes, Lucide v1.17.0 (ISC; https://lucide.dev), by Lucide id. Only a GitHub
// repository's page draws them, so they arrive with this code, as the states' do
// (pull-state.js).
const STROKE =
  'viewBox="0 0 24 24" fill="none" stroke="currentColor" ' +
  'stroke-width="2" stroke-linecap="round" stroke-linejoin="round"';
const GLYPHS = Object.freeze({
  checkCheck: // Lucide `check-check`
  `<svg ${STROKE}><path d="M18 6 7 17l-5-5"/><path d="m22 10-7.5 7.5L13 16"/></svg>`,
  gitMergeConflict: // Lucide `git-merge-conflict`
  `<svg ${STROKE}><path d="M12 6h4a2 2 0 0 1 2 2v7"/><path d="M6 12v9"/><path d="M9 3 3 9"/><path d="M9 9 3 3"/><circle cx="18" cy="18" r="3"/></svg>`,
  merge: // Lucide `merge`
  `<svg ${STROKE}><path d="m8 6 4-4 4 4"/><path d="M12 2v10.3a4 4 0 0 1-1.172 2.872L4 22"/><path d="m20 22-5-5"/></svg>`,
  circleCheck: // Lucide `circle-check`
  `<svg ${STROKE}><circle cx="12" cy="12" r="10"/><path d="m9 12 2 2 4-4"/></svg>`,
  circleX: // Lucide `circle-x`
  `<svg ${STROKE}><circle cx="12" cy="12" r="10"/><path d="m15 9-6 6"/><path d="m9 9 6 6"/></svg>`,
  clock: // Lucide `clock`
  `<svg ${STROKE}><circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/></svg>`,
  circleSlash: // Lucide `circle-slash`
  `<svg ${STROKE}><circle cx="12" cy="12" r="10"/><line x1="9" x2="15" y1="15" y2="9"/></svg>`,
  circleStop: // Lucide `circle-stop`
  `<svg ${STROKE}><circle cx="12" cy="12" r="10"/><rect x="9" y="9" width="6" height="6" rx="1"/></svg>`,
  circleDashed: // Lucide `circle-dashed`
  `<svg ${STROKE}><path d="M10.1 2.182a10 10 0 0 1 3.8 0"/><path d="M13.9 21.818a10 10 0 0 1-3.8 0"/><path d="M17.609 3.721a10 10 0 0 1 2.69 2.7"/><path d="M2.182 13.9a10 10 0 0 1 0-3.8"/><path d="M20.279 17.609a10 10 0 0 1-2.7 2.69"/><path d="M21.818 10.1a10 10 0 0 1 0 3.8"/><path d="M3.721 6.391a10 10 0 0 1 2.7-2.69"/><path d="M6.391 20.279a10 10 0 0 1-2.69-2.7"/></svg>`,
  fileQuestionMark: // Lucide `file-question-mark`
  `<svg ${STROKE}><path d="M6 22a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h8a2.4 2.4 0 0 1 1.704.706l3.588 3.588A2.4 2.4 0 0 1 20 8v12a2 2 0 0 1-2 2z"/><path d="M12 17h.01"/><path d="M9.1 9a3 3 0 0 1 5.82 1c0 2-3 3-3 3"/></svg>`,
  fileDiff: // Lucide `file-diff`
  `<svg ${STROKE}><path d="M6 22a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h8a2.4 2.4 0 0 1 1.704.706l3.588 3.588A2.4 2.4 0 0 1 20 8v12a2 2 0 0 1-2 2z"/><path d="M9 10h6"/><path d="M12 13V7"/><path d="M9 17h6"/></svg>`,
  fileCheck: // Lucide `file-check`
  `<svg ${STROKE}><path d="M6 22a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h8a2.4 2.4 0 0 1 1.704.706l3.588 3.588A2.4 2.4 0 0 1 20 8v12a2 2 0 0 1-2 2z"/><path d="M14 2v5a1 1 0 0 0 1 1h5"/><path d="m9 15 2 2 4-4"/></svg>`,
  eye: // Lucide `eye`
  `<svg ${STROKE}><path d="M2.062 12.348a1 1 0 0 1 0-.696 10.75 10.75 0 0 1 19.876 0 1 1 0 0 1 0 .696 10.75 10.75 0 0 1-19.876 0"/><circle cx="12" cy="12" r="3"/></svg>`,
  shieldBan: // Lucide `shield-ban`
  `<svg ${STROKE}><path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"/><path d="m4.243 5.21 14.39 12.472"/></svg>`,
  listOrdered: // Lucide `list-ordered`
  `<svg ${STROKE}><path d="M11 5h10"/><path d="M11 12h10"/><path d="M11 19h10"/><path d="M4 4h1v5"/><path d="M4 9h2"/><path d="M6.5 20H3.4c0-1 2.6-1.925 2.6-3.5a1.5 1.5 0 0 0-2.6-1.02"/></svg>`,
  listX: // Lucide `list-x`
  `<svg ${STROKE}><path d="M16 5H3"/><path d="M11 12H3"/><path d="M16 19H3"/><path d="m15.5 9.5 5 5"/><path d="m20.5 9.5-5 5"/></svg>`,
  arrowUpToLine: // Lucide `arrow-up-to-line`
  `<svg ${STROKE}><path d="M5 3h14"/><path d="m18 13-6-6-6 6"/><path d="M12 7v14"/></svg>`,
});

/** The glyphs, each parsed once: a list has a thousand rows and a handful of shapes. */
/** @type {Map<StatusGlyph, Element | null>} */
const parsed = new Map();

/**
 * A copy of the glyph *name*, or null for no glyph. Every form draws its glyph through this,
 * so a chip's glyph and its compact form are one drawing.
 *
 * @param {StatusGlyph | null | undefined} name
 */
function shape(name) {
  if (name == null || !Object.hasOwn(GLYPHS, name)) {
    return null;
  }
  let drawn = parsed.get(name);
  if (drawn === undefined) {
    drawn = new DOMParser().parseFromString(GLYPHS[name], "text/html").body.firstElementChild;
    parsed.set(name, drawn);
  }
  return drawn === null ? null : document.importNode(drawn, true);
}

/**
 * A mark colored by its tone alone (github/styles.css, `.github-pull-tone`): its classes, and
 * its tone on `data-tone`, the one thing any rule reads to color it.
 *
 * @param {string} className
 * @param {MarkTone} tone
 */
function toned(className, tone) {
  const element = document.createElement("span");
  element.className = `${className} github-pull-tone`;
  element.dataset.tone = tone;
  return element;
}

/**
 * A chip: the glyph, hidden from assistive technology, then the label, which names the chip,
 * in the outlined form a state's badge has (`stateBadge` in pull-page.js). The glyph sits in a
 * box of the app's one glyph size, centered on the label's capitals (github/styles.css,
 * `.github-pull-badge-glyph`).
 *
 * @param {string} className
 * @param {MarkTone} tone
 * @param {StatusGlyph | null} glyph
 * @param {string} label
 */
function chip(className, tone, glyph, label) {
  const badge = toned(`file-header-badge github-pull-badge ${className}`, tone);
  const drawn = shape(glyph);
  if (drawn !== null) {
    const box = document.createElement("span");
    box.className = "github-pull-badge-glyph";
    box.setAttribute("aria-hidden", "true");
    box.append(drawn);
    badge.append(box);
  }
  badge.append(label);
  return badge;
}

/**
 * The verdict's glyph alone, its compact form, in its tone, or null for a pull request with no
 * readiness, as a closed or merged one has none. Browser only.
 *
 * Named by default: its accessible name is the server's label, as a state icon's is the
 * state's (pull-state.js). Text that says the label passes `named: false`, and the glyph is
 * hidden from assistive technology, as a row's is, whose words say the label after its state
 * (stack-member-row.js).
 *
 * @param {ShownReadiness | null | undefined} readiness
 * @param {{named?: boolean}} [options]
 */
export function readinessIcon(readiness, options = {}) {
  if (readiness == null) {
    return null;
  }
  const icon = toned("github-pull-readiness-icon", readiness.tone);
  icon.dataset.verdict = readiness.verdict;
  if (options.named === false) {
    icon.setAttribute("aria-hidden", "true");
  } else {
    icon.setAttribute("role", "img");
    icon.setAttribute("aria-label", readiness.label);
  }
  const drawn = shape(VERDICT_GLYPHS[readiness.verdict]);
  if (drawn !== null) {
    icon.append(drawn);
  }
  return icon;
}

/**
 * The verdict's chip: its glyph and the server's label, in its tone. Null for a pull request
 * with no readiness. Browser only.
 *
 * @param {ShownReadiness | null | undefined} readiness
 */
export function readinessBadge(readiness) {
  if (readiness == null) {
    return null;
  }
  const badge = chip(
    "github-pull-readiness",
    readiness.tone,
    VERDICT_GLYPHS[readiness.verdict] ?? null,
    readiness.label,
  );
  badge.dataset.verdict = readiness.verdict;
  return badge;
}

/**
 * Every label the server gives a verdict (`LABELS` in pull_readiness.py), for one use only:
 * the width of the header's readiness slot, which is as wide as the widest of them, so a
 * verdict that changes as checks finish moves nothing in the row (`readinessSizers`). A badge
 * always says the label its readiness came with, never one of these.
 * tests/test_github_pull_readiness_js.py holds this list to the server's labels, so a label
 * changed there and not here fails.
 *
 * @type {ReadonlyArray<string>}
 */
export const SLOT_LABELS = Object.freeze([
  "Ready to merge",
  "No other blockers",
  "Merge conflicts",
  "Checks failing",
  "Changes requested",
  "Blocked",
  "Leaving queue",
  "Queued",
  "Checks pending",
  "Review required",
  "Not up to date",
  "Mergeability pending",
  "Status unavailable",
]);

/**
 * A requirement's status as its row says it: the server's own word for it, its first letter a
 * capital, "Waiting". Pure.
 *
 * @param {string} status
 */
export function statusWord(status) {
  return `${status.charAt(0).toUpperCase()}${status.slice(1).replaceAll("_", " ")}`;
}

/**
 * A requirement's chip: its glyph (`requirementGlyph`), the glyph of the verdict it heads, and
 * its status's word (`statusWord`), in the tone the server gave it. Null for a kind, status,
 * or tone the server does not name. Browser only.
 *
 * @param {{kind: string, status: string, tone: string}} requirement
 */
export function requirementBadge(requirement) {
  const { kind, status, tone } = requirement;
  const glyph = requirementGlyph(kind, status);
  if (glyph === null || !TONES.includes(/** @type {ReadinessTone} */ (tone))) {
    return null;
  }
  const badge = chip(
    "github-pull-requirement",
    /** @type {ReadinessTone} */ (tone),
    glyph,
    statusWord(status),
  );
  badge.dataset.kind = kind;
  badge.dataset.status = status;
  return badge;
}

/**
 * A check's chip: its glyph and its own state as GitHub names it, a capital first, in its
 * bucket's tone (`CHECK_GLYPHS`, `CHECK_TONES`). A bucket this build does not know draws the
 * label alone, neutral. Browser only.
 *
 * @param {{bucket: string, label: string}} check
 */
export function checkBadge(check) {
  const known = Object.hasOwn(CHECK_GLYPHS, check.bucket);
  const badge = chip(
    "github-pull-check",
    known ? CHECK_TONES[check.bucket] : "neutral",
    known ? CHECK_GLYPHS[check.bucket] : null,
    `${check.label.charAt(0).toUpperCase()}${check.label.slice(1)}`,
  );
  badge.dataset.bucket = check.bucket;
  return badge;
}

/**
 * The header's readiness slot's sizers: each label in `SLOT_LABELS` in a chip's box of no
 * height, its glyph's box before it, after the chip, so the slot is as wide as the widest chip
 * (github/styles.css, `.github-pull-readiness-slot`), as the state's badge's slot is the
 * widest state's. Hidden from assistive technology. Browser only.
 */
export function readinessSizers() {
  return SLOT_LABELS.map((label) => {
    const sizer = document.createElement("span");
    sizer.className = "file-header-badge github-pull-badge github-pull-badge-sizer";
    sizer.setAttribute("aria-hidden", "true");
    const box = document.createElement("span");
    box.className = "github-pull-badge-glyph";
    sizer.append(box, label);
    return sizer;
  });
}

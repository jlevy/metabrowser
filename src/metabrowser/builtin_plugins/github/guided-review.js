// Prefetched: a page whose guide the reader can open loads this when it is idle, and reads the
// guide's first step with it (guide-reads.js), so Guided Review draws at once when opened.
// A step is shown in one change, once everything its layout depends on is in hand.

import { guideAsks, guideReads, retryable } from "./guide-reads.js";
import {
  namedStackPosition,
  namedStackPositionNodes,
  stackPlaceHint,
  stackPosition,
} from "./pull-stacks.js";
import { stackMemberRow } from "./stack-member-row.js";

/**
 * @typedef {{op: "add" | "del" | "context", text: string}} Line
 * @typedef {{old_start: number, old_count: number, new_start: number, new_count: number,
 *   heading: string | null, lines: Line[]}} Hunk
 * @typedef {"markdown" | "yaml" | "json"} Rendered
 * @typedef {{merge_base: string, head: string, route: string, image_route: string,
 *   rendered_route: string}} PullComparison Another pull request's current comparison, and
 *   the routes that answer it, which a `{pull, path}` reference's document is drawn from.
 * @typedef {{title: string | null, state: import("./pull-state.js").PullState | null,
 *   stack: {number: number, place: number, count: number, own: boolean} | null,
 *   author: string | null, avatar: string | null}} PullTarget What a `{pull}` row names: its
 *   title and state, its place in a stack, `place` counted from the stack's base and `own`
 *   when the stack is the guide's own, and its author and the author's avatar.
 * @typedef {{subject: string | null, committed_at: string | null}} CommitTarget What a
 *   `{commit}` row names; both null for a commit whose line passed its bound.
 * @typedef {{kind: "file" | "pull_file" | "pull" | "commit", path: string | null,
 *   side: "old" | "new" | null, pull: number | null, commit: string | null, state: string,
 *   start_line?: number | null, end_line?: number | null, deleted?: boolean,
 *   rendered: Rendered | null, href: string | null, hunks: Hunk[], truncated: boolean,
 *   comparison: PullComparison | null, target: PullTarget | CommitTarget | null}}
 *   Reference What a step cites (`_references` in guided_review.py): a file of the pull
 *   request (`file`), a file of another pull request at that one's comparison
 *   (`pull_file`, whose *comparison* is that one's), a pull request (`pull`), or a commit
 *   (`commit`); the last two are rows, whose *target* is what they name. *side* is null
 *   for a file named alone, whose whole patch *hunks* are, and a range's side otherwise.
 *   *rendered* is the format of a file named alone that the rendered route renders, by
 *   that route's own rule (`rendered_format` in pull_rendered_diff.py): the page draws it
 *   whole, and the route sends no hunks for it.
 * @typedef {"diff" | "current" | "full"} Presentation
 * @typedef {{dispose: () => void, show?: (mode: Presentation) => void}} GuidedDrawing
 * @typedef {((body: HTMLElement, change: Record<string, unknown>,
 *   patch: {hunks: Hunk[], truncated: boolean}, fullFile?: FullFile | null) => GuidedDrawing) & {
 *   disclose?: (section: HTMLElement, folded: HTMLElement,
 *     changed?: (expanded: boolean) => void) => DiffFileDisclosure,
 *   controls?: (host: HTMLElement, full: boolean, initial: Presentation | null,
 *     choose: (mode: Presentation) => void) => GuidedDrawing
 * }} DrawPatch
 *   The diff plugin's `mountFilePatch`, bound to the SDK: a file's hunks as Changes draws
 *   them.
 * @typedef {{merge_base: string | null, head: string}} Pins
 * @typedef {{path: string, load: (signal: AbortSignal) => Promise<unknown>}} FullFile
 * @typedef {{
 *   draws(pins: Pins | PullComparison): boolean,
 *   source?(path: string, pins: Pins | PullComparison): FullFile | null,
 *   mount(body: HTMLElement, path: string, format: Rendered | null, pins: Pins | PullComparison):
 *     GuidedDrawing & {settled: Promise<boolean>},
 * }} DrawDocument The diff plugin's `mountRenderedFile`, bound by the page to its
 *   comparison: whether it draws a file read at *pins*, which it does for the comparison a
 *   step was read at only while that is the page's own, and always for another pull
 *   request's, which names its own routes; and one file drawn whole, a Markdown file as the
 *   Docs tab draws it and a YAML or JSON file as Changes does. *settled* is true once the
 *   file is drawn, and false when the view's notice says why it is not, or the handle was
 *   disposed first.
 * @typedef {{kind: "pull" | "stack", number: number,
 *   at?: {left: string, right: string, key: string}}} GuideSubject What carries the guide: a
 *   pull request, whose description's `guided-review` block it is, or a native stack, whose
 *   guide is a member's `stack-review` block, read against a combined comparison of the
 *   stack: *at*, the one its page draws, by its two commits and its key, or without it the
 *   stack's current one.
 * @typedef {{open: (path: string) => void,
 *   openPull: (number: number, path: string | null) => void,
 *   age: (iso: string) => HTMLElement, shortCommit: (sha: string) => string,
 *   identity: (login: string, avatar: string | null) => HTMLElement,
 *   titleNodes: (title: string) => Array<Node | string>,
 *   stackGlyph: () => Node | null,
 *   subject: GuideSubject["kind"]}} ReferenceWays
 *   Where a reference goes and how a row says when, which, and whose: a file to its Changes
 *   address, the pull request's or the stack's, and another pull request to its page or a
 *   file in its Changes (`mountGuidedReview`'s deps); *subject* is what the guide's own
 *   files are the changes of.
 * @typedef {{patch: DrawPatch | null, document: DrawDocument | null, pins: Pins}} Drawers
 *   What draws a step's references, each null when the diff plugin did not load, and the
 *   comparison the step was read at.
 * @typedef {{folded: boolean, heard: (expanded: boolean) => void}} Fold Whether the reader
 *   left a card folded, and what hears them fold or open it (`folds` in guide-reads.js).
 * @typedef {{drawn: GuidedDrawing[], waits: Promise<unknown>[]}} Drawing What a
 *   step drew: the views to dispose of when another step is shown or the guide ends, and what
 *   the step waits for before it shows, the documents it draws whole, each until drawn as it
 *   stays.
 * @typedef {{guide: Pins, current: Pins, github_newer: boolean,
 *   history: "ahead" | "rewritten" | "unavailable", commit_count: number | null,
 *   commits: {sha: string, subject: string}[], changed_paths: string[] | null,
 *   changed_steps: number[] | null}} Staleness What a stale guide was written for and what
 *   changed since (`_staleness` in guided_review.py). The page says only whether its steps
 *   may not match; the rest is for an agent that brings the guide up to date.
 * @typedef {{kind: "step", step: number, title: string}} OutlineStep A step in the guide's
 *   outline, numbered through the groups as `step` counts it.
 * @typedef {{kind: "group", title: string, note: string | null, children: OutlineStep[]}}
 *   OutlineGroup A group of the guide's steps, which the reader never lands on alone.
 * @typedef {{state: "ready" | "stale", record_revision: string, step: number,
 *   step_count: number, titles: string[], outline: Array<OutlineStep | OutlineGroup>,
 *   group: number | null, title: string, note: string, note_html: string | null,
 *   note_refusal?: string | null, group_note_html: string | null,
 *   group_note_refusal?: string | null, references: Reference[], comparison: Pins,
 *   stale?: Staleness, assets?: unknown, carrier_url?: string | null}} Step `group` is the
 *   index in `outline` of the
 *   step's group, or null for a step outside one (`_outline` in guided_review.py);
 *   *note_html* is the note's Markdown rendered inert, as the description's is, and
 *   *group_note_html* the note of the group the step opens, each null when its render was
 *   refused or there is none, and *note_refusal* and *group_note_refusal* the code each
 *   refusal was answered with, as the Markdown route answers a text's (`_rendered_note` in
 *   guided_review.py); *comparison* is the one the references were read at, the pull
 *   request's current one. A stack's step names its carrier's page as *carrier_url*, which
 *   its notes' links were made absolute against.
 * @typedef {(html: string, base: string | null) => HTMLElement} DrawProse The page's
 *   insertion of a text's rendered Markdown (`inertProse` in pull-page.js): the server's
 *   inert HTML rebuilt from static/inert-html.js's allowlist into a `.kpress-prose` element,
 *   its links made absolute against *base*, the page of the pull request that carries the
 *   guide, or the page's own pull request when null, and marked as a description's are.
 * @typedef {(code: string) => string | null} RefusalNote What the page says under a text
 *   whose render was refused with *code* (`textRefusalNote` in pull-page.js), or null when
 *   the code needs no word to the reader.
 * @typedef {{state: "absent" | "invalid" | "comparison_unavailable" |
 *   "description_truncated" | "step_not_found" | "not_cached" | "stack_unavailable" |
 *   "stack_moved", record_revision: string | null, message?: string, stale?: Staleness}}
 *   Refusal A stack's answer names its member that carries the guide too, as `carrier`; a
 *   stack this copy cannot pair is `stack_unavailable`, and a comparison of it neither
 *   current nor kept is `stack_moved` (`stack_guided_review` in guided_review.py). A
 *   refusal before the guide is found, a stack's `not_cached` or `stack_unavailable`,
 *   names no revision.
 * @typedef {"unchanged" | "changed" | "unknown"} Change Whether a reference's file changed
 *   since the guide was written: "unknown" when the guide is out of date and what changed
 *   could not be read.
 * @typedef {Step | Refusal | {state: "loading" | "preview" | "error" | "updated"}} GuideState
 */

/**
 * The guide's place and its reads. Step 0 is the overview, the description the page
 * draws itself; steps 1 to `step_count` are the guide's. The overview shows the answer
 * for step 1, whose step titles list the guide, so the first step the reader moves to is
 * already in hand. Answers with a step are kept for the record revision they were read for,
 * and for whether GitHub reported a head past it then, except one that holds what a later
 * read can answer otherwise (`retryable` in guide-reads.js), such as a note a busy renderer
 * refused or another pull request not read yet: that step is read again when the reader
 * returns to it, so it fills in once it can, as a reload would.
 * A step whose read was refused or failed keeps the guide's steps, from the last answer that
 * had them, so the reader can still move, and is read again when the reader returns to it.
 * A refusal that names no revision, a stack's while it is pending or cannot be paired, is
 * that step's, never a new guide: only an answer that names another revision is.
 *
 * A stack's guide is read at the comparison its page draws, which the stack can move past
 * (`behind`). The member that carries the guide moves with it, as the top member usually
 * does, and its author pins the guide again, so until the reader takes the new comparison
 * an answer that names another revision is that step's `stack_moved`, never a new guide,
 * and so is the route's own `stack_moved`, whatever revision it names.
 *
 * A stack's guide has no overview of its own, since no member's description introduces the
 * stack: with *first* 1 it opens on step 1, and no move goes before it.
 *
 * Once a step's answer is shown, the steps one move away, next to the step whose answer it
 * is, are read ahead (*prefetch*), unless this guide already holds them, so the next press
 * of an arrow or the way on finds its step in hand. A step read before this guide asked for
 * it, ahead of it or by an earlier mount, is shown at once from *peek*, with no loading
 * state between.
 *
 * @param {{
 *   read(step: number, signal: AbortSignal, revision: string, moved: boolean):
 *     Promise<Step | Refusal>,
 *   render(state: GuideState, at: number, steps: number): void,
 *   prefetch?(step: number, revision: string, moved: boolean): void,
 *   peek?(step: number, revision: string, moved: boolean): Step | undefined,
 *   first?: 0 | 1,
 * }} deps *read* is told the record revision the guide expects, and whether the head has
 *   moved past it (`show`'s *moved*). *render* is told the guide's step count, 0 while no
 *   answer has had a step. *peek* answers only a step read at *revision* with the same
 *   *moved* that holds nothing a later read answers otherwise, as *read* keeps one. *first*
 *   is the first place, 0, the overview, unless it says 1.
 */
export function createGuideNavigation(deps) {
  const first = deps.first ?? 0;
  /** @type {string | null | undefined} */
  let revision;
  let headMoved = false;
  /** The revision of the guide read at a comparison the stack has moved past, or null. */
  /** @type {string | null} */
  let held = null;
  /** @type {number} */
  let selected = first;
  /** The step count of the last answer of this revision that had a step, which bounds a move. */
  let count = 0;
  /** @type {Map<number, Step | Refusal>} */
  let answers = new Map();
  /** @type {AbortController | null} */
  let pending = null;
  let disposed = false;

  /**
   * Read ahead the steps a move from *at* reaches that this guide does not hold: those
   * next to the step whose answer *at* shows, the overview's being step 1's.
   *
   * @param {number} at @param {string} expected @param {boolean} moved
   */
  function readAhead(at, expected, moved) {
    const shown = Math.max(at, 1);
    for (const step of [shown + 1, shown - 1]) {
      if (step >= 1 && step <= count && !answers.has(step)) {
        deps.prefetch?.(step, expected, moved);
      }
    }
  }

  /** @param {string} expected */
  async function load(expected) {
    pending?.abort();
    const moved = headMoved;
    const at = selected;
    const asked = Math.max(at, 1);
    let kept = answers.get(asked);
    if (kept === undefined) {
      const peeked = deps.peek?.(asked, expected, moved);
      if (peeked !== undefined && peeked.record_revision === expected) {
        answers.set(asked, peeked);
        count = peeked.step_count;
        kept = peeked;
      }
    }
    if (kept !== undefined) {
      pending = null;
      deps.render(kept, at, count);
      readAhead(at, expected, moved);
      return;
    }
    const request = new AbortController();
    pending = request;
    deps.render({ state: "loading" }, at, count);
    // Whether a step's answer was shown, so the steps next to it are read ahead: after the
    // read, so a read ahead that fails never stands for the step's.
    let shownStep = false;
    try {
      let result = await deps.read(asked, request.signal, expected, moved);
      if (request.signal.aborted) {
        return;
      }
      if (result.record_revision === expected && result.state === "step_not_found" && asked > 1) {
        selected = 1;
        result = await deps.read(1, request.signal, expected, moved);
      }
      if (request.signal.aborted) {
        return;
      }
      const another = result.record_revision !== null && result.record_revision !== expected;
      if (another && result.state !== "stack_moved") {
        // Under a comparison the stack has moved past, another revision is the guide written
        // for the new one: this step's refusal, until the reader takes that comparison.
        deps.render(
          held === null
            ? { state: "updated" }
            : { state: "stack_moved", record_revision: result.record_revision },
          selected,
          count,
        );
        return;
      }
      if ("step" in result) {
        if (!retryable(result)) {
          answers.set(Math.max(selected, 1), result);
        }
        count = result.step_count;
      }
      deps.render(result, selected, count);
      shownStep = "step" in result;
    } catch {
      if (!request.signal.aborted) {
        deps.render({ state: "error" }, selected, count);
      }
    } finally {
      if (pending === request) {
        pending = null;
      }
    }
    if (shownStep) {
      readAhead(selected, expected, moved);
    }
  }

  /** @param {number} target */
  function go(target) {
    if (disposed || !revision || count === 0) {
      return;
    }
    // The step on screen is read again only when its read was refused or failed.
    if (target === selected && (pending !== null || answers.has(Math.max(target, 1)))) {
      return;
    }
    if (target >= first && target <= count) {
      selected = target;
      void load(revision);
    }
  }

  return {
    /** @param {string | null} nextRevision @param {boolean} moved */
    show(nextRevision, moved) {
      if (disposed || (revision === nextRevision && headMoved === moved)) {
        return;
      }
      revision = nextRevision;
      headMoved = moved;
      answers = new Map();
      count = 0;
      if (nextRevision === null) {
        pending?.abort();
        deps.render({ state: "preview" }, selected, count);
        return;
      }
      if (held !== null && nextRevision !== held) {
        // Nothing is read: at the comparison drawn, this guide was written for another. It
        // is shown again, and read, once the comparison drawn is the stack's own.
        pending?.abort();
        revision = undefined;
        deps.render({ state: "stack_moved", record_revision: nextRevision }, selected, count);
        return;
      }
      // A head GitHub reports past the record's is the server's to read: it answers the
      // guide's steps with what is out of date.
      void load(nextRevision);
    },
    /**
     * Whether the stack has moved past the comparison the guide is read at: *at* is the
     * revision of the guide read there, or null while that comparison is the stack's own.
     *
     * @param {string | null} at
     */
    behind(at) {
      held = at;
    },
    /** @param {-1 | 1} by */
    move(by) {
      go(selected + by);
    },
    go,
    dispose() {
      disposed = true;
      pending?.abort();
      answers = new Map();
    },
  };
}

const MESSAGES = Object.freeze({
  absent: "This pull request has no guide.",
  comparison_unavailable:
    "The comparison is unavailable. Fetch it from Changes, then reopen the guide.",
  description_truncated: "Only part of the description was loaded, and it holds no complete guide.",
  step_not_found: "This review step is unavailable.",
  not_cached: "The full pull request is unavailable.",
  preview: "The guide needs the full pull request.",
  updated: "The pull request updated. Reopen the guide to read the new version.",
  error: "Could not load the guide. Reopen the tab to try again.",
});

// A stack's guide says the same of the stack. Its overview is its first step, so a refusal
// shows under the step list alone; a member not read yet may carry the guide, and its page
// fetches the members it lacks.
const STACK_MESSAGES = Object.freeze({
  ...MESSAGES,
  absent: "This stack has no guide.",
  comparison_unavailable: "The stack's comparison is unavailable. Reload the page to try again.",
  description_truncated:
    "Only part of the description that carries this stack's guide was loaded, and it holds no complete guide.",
  not_cached: "This stack's pull requests are still being fetched.",
  stack_unavailable: "This stack cannot be shown.",
  stack_moved:
    "This stack has moved since its comparison was drawn. Show the new comparison to read its guide.",
  updated: "The stack's guide changed. Reopen the guide to read the new version.",
});

// One step of a guide whose other steps read: the reader can move on, and a step whose read
// was refused or failed is read again when chosen again.
const STEP_MESSAGES = Object.freeze({
  refused: "This step could not be read. Choose it again to retry.",
  error: "Could not load this step. Choose it again to retry.",
});
// A stack's step refused for the stack's own reason says that reason, in its whole
// refusal's words: the stack's members are fetched, or the comparison drawn has moved.
const STACK_STEP_REFUSALS = new Set(["not_cached", "stack_unavailable", "stack_moved"]);

const REFERENCE_MESSAGES = Object.freeze({
  manifest_truncated: "This path is outside the available changed-file list.",
  path_not_changed: "This path is not in the comparison.",
  diff_unavailable: "This file's diff is unavailable.",
  range_unavailable: "This range is not within a single available diff hunk.",
  excerpt_too_large: "This excerpt is too large to show here.",
  // Past a step's budget for whole files (MAX_STEP_PATCH_BYTES in guided_review.py), or past
  // what the diff source reads in one run beside the step's other files.
  patch_too_large: "This file's diff is too large to show in this step.",
  // A file of another pull request, which is read from what this copy holds of it: one it
  // has not read opens from its Open full diff, which loads it.
  not_cached: "This pull request has not been loaded here. Open it to load its changes.",
  comparison_unavailable: "This pull request's changes are unavailable.",
});

// A commit a step cites that the repository's copy here does not have, as after a force push
// removed it from every branch.
const COMMIT_UNAVAILABLE = "This commit is unavailable.";
// A commit the copy has that the served checkout, where its page reads Git, does not, as a
// pull request's branch only the copy fetched: named and dated, with no page to open.
const COMMIT_ELSEWHERE = "Not in this checkout.";

// A reference of an out-of-date guide, read at the pull request's current head, whose file
// changed since the guide was written: a note above its excerpt when it resolves, and in its
// place when it does not. A range that no longer lies in one hunk may have moved, or the
// change may be elsewhere in the file, so it says only what may be so. One whose change is
// unknown, as after a force push, says only what may be so too, and a path the pull request
// does not change says what any guide's would (`REFERENCE_MESSAGES`), since whether it ever
// did is unknown.
const CHANGED_REFERENCE_MESSAGES = Object.freeze({
  ready: "This file changed after the guide was written.",
  range_unavailable: "These lines may have changed since the guide was written.",
  path_not_changed: "This file is no longer in the pull request's changes.",
});
const STACK_CHANGED_REFERENCE_MESSAGES = Object.freeze({
  ...CHANGED_REFERENCE_MESSAGES,
  path_not_changed: "This file is no longer in the stack's changes.",
});
const UNKNOWN_REFERENCE_MESSAGES = Object.freeze({
  ready: "This file may have changed since the guide was written.",
  range_unavailable: "These lines may have changed since the guide was written.",
});

// What an out-of-date guide says above its steps: one warning and its one remedy, or, when
// none of the files its steps cite changed, a quiet line. Which commits, heads, merge bases,
// and paths changed is the route's answer, for an agent, never the page's.
const OUTDATED = Object.freeze({
  marked:
    "This guide was written for an earlier version of this pull request, so steps marked changed may not match it.",
  unknown:
    "This guide was written for an earlier version of this pull request, so some steps may not match it.",
  remedy: "Its author can update the guide.",
  unchanged:
    "This guide was written for an earlier version of this pull request, but the files it cites have not changed.",
});
// A stack's guide is out of date when any member moved since it was written.
const STACK_OUTDATED = Object.freeze({
  marked:
    "This guide was written for an earlier version of this stack, so steps marked changed may not match it.",
  unknown:
    "This guide was written for an earlier version of this stack, so some steps may not match it.",
  remedy: "Its author can update the guide.",
  unchanged:
    "This guide was written for an earlier version of this stack, but the files it cites have not changed.",
});

/**
 * @param {string} tag
 * @param {string} [content]
 * @param {string} [className]
 */
function element(tag, content = "", className = "") {
  const node = document.createElement(tag);
  node.textContent = content;
  node.className = className;
  return node;
}

/**
 * The guide's own text in a KPress article, as the page sets a description
 * (`kpressHost` in pull-page.js): KPress's prose element sets the headings, paragraphs, and
 * the space between them, and the chrome prose class keeps it in the chrome's sans
 * (docs/design-system.md, "Serif Is for Documents").
 *
 * @param {HTMLElement} prose The `.kpress-prose` element the caller fills.
 * @param {string} [className] The host's place: by default a text in a card, as the page
 *   sets a description's, whose inset and edge margins are `.github-pull-text`'s
 *   (styles.css).
 * @param {HTMLElement | null} [refused] The line under the text that says why its render
 *   did not come, which follows the article, as a description's follows its plain text.
 */
function proseHost(prose, className = "github-pull-text github-pull-guide-prose", refused = null) {
  const article = element("article", "", "kpress kpress-inert");
  article.append(prose);
  const host = element("div", "", "metabrowser-kpress-host");
  host.append(article);
  const text = element("div", "", `${className} chrome-prose`);
  text.append(host, ...(refused === null ? [] : [refused]));
  return text;
}

/**
 * The line under a typed note that says why its render did not come, as the page says it
 * under a description's plain text (`refusalNotice` in pull-page.js), or null when the
 * note was not refused or its refusal needs no word.
 *
 * @param {string | null | undefined} code @param {RefusalNote} refusalNote
 */
function refusalLine(code, refusalNote) {
  const said = typeof code === "string" ? refusalNote(code) : null;
  if (said === null) {
    return null;
  }
  const line = element("div", said, "notice github-pull-notice github-pull-guide-note-refused");
  line.dataset.severity = "warning";
  line.setAttribute("role", "status");
  return line;
}

/**
 * A step's title and note as the page shows them, in KPress's prose element in a KPress
 * article: the title as text, and the note as the route's inert render of its Markdown,
 * inserted as the page inserts a description's (*drawProse*), or, when the render was
 * refused or the allowlist did not load, as typed. A refused note has the line a
 * description's refusal has under it; a note typed because the allowlist did not load has
 * none, as a description's has none.
 *
 * @param {Step} state @param {DrawProse | null} drawProse @param {RefusalNote} refusalNote
 */
function stepProse(state, drawProse, refusalNote) {
  const html = state.note_html;
  const prose =
    typeof html === "string" && drawProse !== null
      ? drawProse(html, state.carrier_url ?? null)
      : null;
  const shown = prose ?? element("div", "", "kpress-prose");
  if (prose === null) {
    shown.append(element("p", state.note, "github-pull-guide-commentary"));
  }
  shown.prepend(element("h2", state.title, "github-pull-guide-title"));
  return proseHost(shown, undefined, refusalLine(state.note_refusal, refusalNote));
}

/**
 * The note of the group a step opens, above the step's card: rendered as a step's note is,
 * in a KPress article at the card text's inset, or as typed when its render did not come,
 * with the line that says why when it was refused.
 *
 * @param {string} note @param {Step} state @param {DrawProse | null} drawProse
 * @param {RefusalNote} refusalNote
 * @returns {HTMLElement[]}
 */
function groupNote(note, state, drawProse, refusalNote) {
  const html = state.group_note_html;
  if (typeof html === "string" && drawProse !== null) {
    return [
      proseHost(
        drawProse(html, state.carrier_url ?? null),
        "github-pull-text github-pull-guide-group-note",
      ),
    ];
  }
  const typed = element(
    "p",
    note,
    "github-pull-guide-group-note github-pull-guide-group-note-typed",
  );
  const refused = refusalLine(state.group_note_refusal, refusalNote);
  return refused === null ? [typed] : [typed, refused];
}

/**
 * What a folded file's card is kept by in its guide at one head: its step, its place in
 * the step, the pull request a file of another one is in, and its path. The pull request
 * is in it because a guide rewritten at the same head can put the same path of another
 * pull request at the same place (review B of #872, B1).
 *
 * @param {number} step @param {number} place @param {Pick<Reference, "pull" | "path">} reference
 */
export function foldKey(step, place, reference) {
  return `${step}\n${place}\n${reference.pull ?? ""}\n${reference.path ?? ""}`;
}

/**
 * How a step draws a reference. A pull request or a commit it cites is a row naming it. A
 * file named alone that the rendered route renders, as the guided route answers it
 * (`rendered`), is a document: the file drawn whole by the diff view, with its Rendered |
 * Source chooser, while the page's comparison is the one the step was read at, or from the
 * other pull request's own comparison for a file of one. Any other ready change with lines
 * is its hunks, as Changes draws them: a range's one hunk, and another file named alone its
 * whole patch. The rest say why there is nothing to draw.
 *
 * @param {Reference} reference @param {Drawers} drawers
 * @returns {"row" | "document" | "patch" | "said"}
 */
export function referenceDrawing(reference, drawers) {
  if (reference.kind === "pull" || reference.kind === "commit") {
    return "row";
  }
  if (reference.state !== "ready") {
    return "said";
  }
  if (typeof reference.rendered === "string") {
    const pins = reference.comparison ?? drawers.pins;
    return drawers.document?.draws(pins) === true ? "document" : "said";
  }
  return reference.hunks.length === 0 || drawers.patch === null ? "said" : "patch";
}

/** @param {Reference} reference @param {Drawers} drawers */
function wholeSource(reference, drawers) {
  return reference.side === null && reference.path !== null && !reference.deleted
    ? (drawers.document?.source?.(reference.path, reference.comparison ?? drawers.pins) ?? null)
    : null;
}

/**
 * Whether *event* is a plain press of the main button, which a link the page opens in place
 * takes over; any other, as one that opens a new tab, is the browser's.
 *
 * @param {MouseEvent} event
 */
const plainPress = (event) =>
  event.button === 0 && !event.metaKey && !event.ctrlKey && !event.shiftKey && !event.altKey;

/**
 * A `{pull}` reference: the pull request as a stack's member row draws it
 * (`stackMemberRow`, docs/design-system.md, "Stacks"), in the one order a member reads in
 * wherever it appears: its state icon, its title, which alone gives way, and at the line's
 * end its place in a stack in bold, its number after a muted dot, and its author after
 * another, "Fix the reader 1/3 · #8 · jlevy". The place is bare in the guide's own stack,
 * which goes without saying, and names any other stack by the Layers glyph and its number,
 * "⧉300 2/2", as a Pulls row's place does (`namedStackPosition`); its hint, "Stack #71,
 * position 1 of 3", is its tip and its accessible name. A pull request in no stack has no
 * place, and its line ends at its number and its author. It goes to the pull request's
 * page. One this copy has not read keeps the icon's slot empty and names itself by its
 * number, as a member with no title does.
 *
 * @param {Reference} reference
 * @param {Pick<ReferenceWays, "openPull" | "identity" | "titleNodes" | "stackGlyph">} ways
 */
function pullRow(reference, ways) {
  const number = reference.pull ?? 0;
  const target = /** @type {PullTarget | null} */ (reference.target);
  const link = /** @type {HTMLAnchorElement} */ (
    element("a", "", "github-pull-guide-row-link github-pull-guide-pull")
  );
  link.href = reference.href ?? `/pull/${number}`;
  link.addEventListener("click", (event) => {
    if (plainPress(event)) {
      event.preventDefault();
      ways.openPull(number, null);
    }
  });
  const stack = target?.stack ?? null;
  const author = target?.author ?? null;
  const position = stack === null ? null : stackPosition(stack.place - 1, stack.count);
  const named = stack === null || stack.own ? null : stack.number;
  stackMemberRow(link, ways.titleNodes, ways.identity).show({
    number,
    place: position === null ? null : namedStackPosition(position, named),
    ...(stack === null || position === null
      ? {}
      : {
          placeNodes: namedStackPositionNodes(position, named, ways.stackGlyph),
          placeHint: stackPlaceHint(stack.number, stack.place - 1, stack.count),
        }),
    title: target?.title ?? null,
    state: target?.state ?? null,
    author: author === null ? null : { login: author, avatar: target?.avatar ?? null },
  });
  const section = element("section", "", "github-pull-guide-reference github-pull-guide-row");
  section.append(link);
  return section;
}

/**
 * A `{commit}` reference: the commit as the Commits tab lists one, its short ID, its subject,
 * and at the row's end when it was committed, the page's age (`pullAge` in pull-page.js) in
 * its freshness ink, going to the commit's own page, which opens in full. One the
 * repository's copy here lacks says so in its place, beside its ID; one this checkout cannot
 * open says so after its subject, so the age still ends the row (docs/design-system.md, "Ages
 * End the Row").
 *
 * @param {Reference} reference
 * @param {{age: (iso: string) => HTMLElement, shortCommit: (sha: string) => string}} words
 */
function commitRow(reference, words) {
  const sha = reference.commit ?? "";
  const target = /** @type {CommitTarget | null} */ (reference.target);
  const section = element("section", "", "github-pull-guide-reference github-pull-guide-row");
  const id = element("span", words.shortCommit(sha), "github-pull-guide-row-id git-commit-sha");
  if (reference.state !== "ready") {
    const row = element("div", "", "github-pull-guide-row-link github-pull-guide-commit");
    row.append(id, " ", element("span", COMMIT_UNAVAILABLE, "github-pull-quiet"));
    section.append(row);
    return section;
  }
  // A commit whose page cannot read it is drawn as a link is, unlinked.
  const href = reference.href;
  const link = element(
    href === null ? "div" : "a",
    "",
    "github-pull-guide-row-link github-pull-guide-commit",
  );
  if (href !== null) {
    /** @type {HTMLAnchorElement} */ (link).href = href;
  }
  const copy = element("span", "", "github-pull-guide-row-copy");
  copy.append(element("span", target?.subject ?? "Commit", "github-pull-guide-row-title"));
  if (href === null) {
    copy.append(" ", element("span", COMMIT_ELSEWHERE, "github-pull-quiet"));
  }
  link.append(id, " ", copy);
  const when = target?.committed_at ?? null;
  if (when !== null) {
    const committed = element("span", "committed ", "github-pull-guide-row-when");
    committed.append(words.age(when));
    link.append(" ", committed);
  }
  section.append(link);
  return section;
}

/**
 * The bar the guide draws above a reference it draws itself: the file's path, after the
 * number of the pull request it is in when that is another, and its Open full diff, which
 * goes to the file in that pull request's Changes.
 *
 * @param {Reference} reference @param {() => void} open
 */
function referenceLink(reference, open) {
  const path = reference.path ?? "";
  const other = reference.kind === "pull_file" ? reference.pull : null;
  if (reference.href === null) {
    return null;
  }
  const full = document.createElement("a");
  full.className = "diff-file-view";
  full.href = reference.href;
  full.textContent = "Open full diff";
  full.setAttribute(
    "aria-label",
    `Open full diff for ${path}${other === null ? "" : ` in pull request #${other}`}`,
  );
  full.addEventListener("click", (event) => {
    if (plainPress(event)) {
      event.preventDefault();
      open();
    }
  });
  return full;
}

/**
 * The bar of a card the guide draws itself. It is the diff view's own (`fileDisclosure`,
 * which the drawer hands over as `disclose`): its chevron leads the name and folds *body*
 * as a file's does in Changes (docs/design-system.md, "Diff File Bar"), and the guide only
 * names the file in its trigger and puts its link on it. Open full diff is a control that
 * views the file (`.diff-file-view`), so a press on it is the link's. A card starts open,
 * and one the reader folded is drawn folded when its step is drawn again (*fold*). Without
 * the diff plugin there is no builder, and the bar only names the file.
 *
 * @param {Reference} reference @param {() => void} open
 * @param {HTMLElement} section @param {HTMLElement} body @param {DrawPatch | null} patch
 * @param {Fold} fold
 */
function referenceBar(reference, open, section, body, patch, fold) {
  const disclosure = patch?.disclose?.(section, body, fold.heard) ?? null;
  if (fold.folded) {
    disclosure?.setExpanded(false);
  }
  const bar = disclosure?.bar ?? element("div", "", "diff-file-bar");
  bar.classList.add("github-pull-guide-reference-header");
  const name = disclosure?.toggle ?? element("span", "", "diff-file-toggle");
  if (reference.kind === "pull_file") {
    name.append(element("span", `#${reference.pull}`, "github-pull-guide-reference-pull"));
  }
  name.append(element("span", reference.path ?? "", "diff-file-path"));
  if (reference.side && reference.start_line != null && reference.end_line != null) {
    const range =
      reference.start_line === reference.end_line
        ? String(reference.start_line)
        : `${reference.start_line}–${reference.end_line}`;
    name.append(element("span", `Cited ${reference.side} lines ${range}`, "diff-file-note"));
  }
  bar.append(name);
  const full = referenceLink(reference, open);
  if (full !== null) {
    bar.append(full);
  }
  return bar;
}

/**
 * A file a step cites whole that the rendered route renders, drawn by the diff plugin's own
 * view of it (`mountRenderedFile`): a Markdown file as the Docs tab draws it, and a YAML or
 * JSON file as Changes does. Either way it is the file's own bar, with its View on branch
 * and its Rendered | Source chooser, the diff's Diff | Current above it, and its rendered
 * layer, which keeps its own bounds and says on its chooser why a file it refuses shows
 * Source. The bar is the file's, so the guide adds none of its own while the file draws, and
 * a note that the file changed since the guide was written leads it. A file the view could
 * not draw shows its notice under the guide's own bar, so the reader still sees which file
 * it is and can open it in Changes. The step waits for the file, which is shown only once
 * drawn as it stays (`Drawing`).
 *
 * @param {Reference} reference @param {Rendered | null} format @param {HTMLElement | null} note
 * @param {() => void} open
 * @param {DrawDocument} drawDocument @param {Pins | PullComparison} pins
 * @param {Drawing} drawing @param {DrawPatch | null} patch @param {Fold} fold
 */
function renderDocument(reference, format, note, open, drawDocument, pins, drawing, patch, fold) {
  const path = reference.path ?? "";
  const section = element("section", "", "github-pull-guide-reference github-pull-guide-document");
  const body = element("div", "", "github-pull-guide-document-body");
  section.append(...(note === null ? [] : [note]), body);
  const view = drawDocument.mount(body, path, format, pins);
  drawing.drawn.push(view);
  drawing.waits.push(
    view.settled.then((drawnFile) => {
      if (!drawnFile) {
        section.classList.add("diff-file");
        section.prepend(referenceBar(reference, open, section, body, patch, fold));
      } else {
        const bar = body.querySelector(".diff-file-bar");
        const full = referenceLink(reference, open);
        if (full !== null) {
          bar?.append(full);
        }
      }
    }),
  );
  return section;
}

/**
 * One reference as Changes draws a changed file: the diff plugin's card and bar, and its
 * hunks drawn by the diff plugin itself (`mountFilePatch`), each under its header bar with
 * its long changed runs behind fold bars, in the plugin's type, gutter, change fills, and
 * syntax (docs/design-system.md, "Diffs"). A range is one hunk of its own lines; a file
 * named alone is its whole patch, or, one the rendered route renders, the whole file drawn
 * by the diff view (`referenceDrawing`). A pull request or a commit is a row naming it.
 *
 * @param {Reference} reference @param {ReferenceWays} ways
 * @param {Change} change Whether the file changed after the guide was written.
 * @param {Drawers} drawers What draws the reference.
 * @param {Drawing} drawing Where each drawn view is kept, and what the step waits for.
 * @param {Fold} fold Whether the reader left this card folded, and what hears a change.
 */
function renderReference(reference, ways, change, drawers, drawing, fold) {
  const how = referenceDrawing(reference, drawers);
  if (how === "row") {
    return reference.kind === "pull" ? pullRow(reference, ways) : commitRow(reference, ways);
  }
  const path = reference.path ?? "";
  const other = reference.kind === "pull_file" ? reference.pull : null;
  const open = other === null ? () => ways.open(path) : () => ways.openPull(other, path);
  const changedWords =
    ways.subject === "stack" ? STACK_CHANGED_REFERENCE_MESSAGES : CHANGED_REFERENCE_MESSAGES;
  const changed =
    reference.state === "ready" && change !== "unchanged"
      ? element(
          "p",
          change === "changed" ? changedWords.ready : UNKNOWN_REFERENCE_MESSAGES.ready,
          "github-pull-quiet github-pull-guide-changed",
        )
      : null;
  const format = typeof reference.rendered === "string" ? reference.rendered : null;
  if (how === "document" && drawers.document !== null) {
    const pins = reference.comparison ?? drawers.pins;
    return renderDocument(
      reference,
      format,
      changed,
      open,
      drawers.document,
      pins,
      drawing,
      drawers.patch,
      fold,
    );
  }
  const section = element("section", "", "diff-file github-pull-guide-reference");
  const content = element("div", "", "diff-file-body");
  section.append(referenceBar(reference, open, section, content, drawers.patch, fold), content);
  if (changed !== null) {
    content.append(changed);
  }
  const drawPatch = drawers.patch;
  if (reference.state === "ready" && format === null && reference.hunks.length === 0) {
    // A rename, a mode change, or a binary file: a change with no text to show.
    content.append(element("p", "This file has no text changes to show.", "github-pull-quiet"));
  } else if (how === "patch" && drawPatch !== null) {
    const body = element("div", "", "diff-file-body github-pull-guide-excerpt");
    body.setAttribute("role", "group");
    body.setAttribute("aria-label", `Diff excerpt for ${path}`);
    content.append(body);
    const side = { path };
    const excerpt = drawPatch(
      body,
      reference.deleted
        ? { id: path, kind: "deleted", old: side, new: null }
        : { id: path, old: side, new: side },
      { hunks: reference.hunks, truncated: reference.truncated },
      wholeSource(reference, drawers),
    );
    drawing.drawn.push(
      reference.side === "old"
        ? { dispose: excerpt.dispose }
        : {
            dispose: excerpt.dispose,
            show: (mode) =>
              excerpt.show?.(mode === "full" && reference.side !== null ? "current" : mode),
          },
    );
  } else {
    /** @type {Readonly<Record<string, string | undefined>>} */
    const said =
      change === "changed" ? changedWords : change === "unknown" ? UNKNOWN_REFERENCE_MESSAGES : {};
    /** @type {Readonly<Record<string, string | undefined>>} */
    const ordinary = REFERENCE_MESSAGES;
    const message =
      reference.state === "ready"
        ? REFERENCE_MESSAGES.diff_unavailable
        : (said[reference.state] ?? ordinary[reference.state]);
    content.append(element("p", message ?? "This excerpt is unavailable.", "github-pull-quiet"));
  }
  return section;
}

/**
 * Whether a stale guide was written for another comparison than this copy's. One this copy
 * still matches is stale only because GitHub reports a newer head, which the page's header
 * already says ("New commits were pushed"), so the guide adds nothing.
 *
 * @param {Staleness | null | undefined} stale
 * @returns {stale is Staleness}
 */
const outdated = (stale) =>
  !!stale &&
  (stale.current.head !== stale.guide.head ||
    (stale.current.merge_base !== null && stale.current.merge_base !== stale.guide.merge_base));

/**
 * Whether the file of the pull request that *reference* cites changed since a stale guide
 * was written. A reference to anything else, another pull request's file among them, is
 * never stale: no push to this pull request moves it.
 *
 * @param {Staleness | null | undefined} stale @param {Reference} reference
 * @returns {Change}
 */
function changeOf(stale, reference) {
  const path = reference.path;
  if (!outdated(stale) || reference.kind !== "file" || path === null) {
    return "unchanged";
  }
  if (stale.changed_paths === null) {
    return "unknown";
  }
  return stale.changed_paths.includes(path) ? "changed" : "unchanged";
}

/**
 * What an out-of-date guide says above its steps, as the route answers it (`_staleness` in
 * guided_review.py), or null when it says nothing: a warning and one remedy when a step it
 * cites changed or what changed is unknown, and a quiet line when none did.
 *
 * @param {Staleness} stale
 * @param {GuideSubject["kind"]} [subject] What the guide was written for: a pull request, or
 *   a stack.
 * @returns {HTMLElement | null}
 */
export function staleNotice(stale, subject = "pull") {
  if (!outdated(stale)) {
    return null;
  }
  const words = subject === "stack" ? STACK_OUTDATED : OUTDATED;
  if (stale.changed_steps !== null && stale.changed_steps.length === 0) {
    const line = element("p", words.unchanged, "github-pull-quiet github-pull-guide-stale");
    line.setAttribute("role", "status");
    return line;
  }
  const warning = stale.changed_steps === null ? words.unknown : words.marked;
  const box = element(
    "div",
    `${warning} ${words.remedy}`,
    "notice github-pull-notice github-pull-guide-stale",
  );
  box.dataset.severity = "warning";
  box.setAttribute("role", "status");
  return box;
}

// Lucide v1.17.0 (ISC; https://lucide.dev), by Lucide id. Only Guided Review draws them, so they
// arrive with this module.
const STROKE =
  'viewBox="0 0 24 24" fill="none" stroke="currentColor" ' +
  'stroke-width="2" stroke-linecap="round" stroke-linejoin="round"';
const GLYPHS = Object.freeze({
  arrowLeft: // Lucide `arrow-left`
  `<svg ${STROKE}><path d="m12 19-7-7 7-7"/><path d="M19 12H5"/></svg>`,
  arrowRight: // Lucide `arrow-right`
  `<svg ${STROKE}><path d="M5 12h14"/><path d="m12 5 7 7-7 7"/></svg>`,
});

/**
 * A glyph as an element, hidden from assistive technology: its button carries the name.
 *
 * @param {keyof typeof GLYPHS} name
 * @returns {Node | null}
 */
function glyph(name) {
  if (typeof DOMParser !== "function") {
    return null;
  }
  const shape = new DOMParser().parseFromString(GLYPHS[name], "text/html").body.firstElementChild;
  if (shape === null) {
    return null;
  }
  shape.setAttribute("aria-hidden", "true");
  shape.setAttribute("class", "github-pull-guide-arrow-glyph");
  return document.importNode(shape, true);
}

/**
 * A step button with an arrow: the way back's before its words, the way on's after them.
 *
 * @param {"previous" | "next"} way
 * @param {string} className
 * @param {boolean} [worded] Whether the button names where it goes beside its arrow; an
 *   arrow alone has no words box, or the gap beside it would push the arrow off center.
 * @returns {[HTMLButtonElement, HTMLElement]} The button and its words.
 */
function arrowButton(way, className, worded = false) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = `btn ${className}`;
  const mark = glyph(way === "previous" ? "arrowLeft" : "arrowRight");
  const label = element("span", "", "github-pull-guide-arrow-label");
  const parts = worded ? (way === "previous" ? [mark, label] : [label, mark]) : [mark];
  button.append(...parts.filter((node) => node !== null));
  return [button, label];
}

// Guided Review's vocabulary. Every place the guide names itself or a step takes its words from
// here (docs/design-system.md, "Guided Review"), so the step list, the arrows, the way on and
// back, and a step's card say the same thing.
/** The guide's own name: its tab's, and its badge on its own parts. */
const GUIDE = "Guided Review";
/** Step 0: the description, the change's overview. */
const OVERVIEW = "Overview";
/** @param {number} at @param {number} count Where the reader is: the overview, or a step of
 * how many. */
const placeName = (at, count) => (at === 0 ? OVERVIEW : `Step ${at} of ${count}`);
/** @param {string | null} group @param {number} at @param {number} count A step's place on its
 * card: its group's title before it, when it has one, as "Decisions · Step 2 of 12". */
const groupedPlace = (group, at, count) =>
  group === null ? placeName(at, count) : `${group} · ${placeName(at, count)}`;
/** @param {number} at @param {string} title A step by name: the overview, or its number and
 * title. */
const stepName = (at, title) => (at === 0 ? OVERVIEW : `Step ${at}: ${title}`);
/** The badge that marks the guide's own parts apart from the discussion. */
const guideBadge = () =>
  element("span", GUIDE, "file-header-badge github-pull-badge github-pull-guide-badge");
/** The mark, in the step list and on a step's card, of a step of an out-of-date guide that
 * cites a file changed since the guide was written: the word its warning names. */
const CHANGED = "changed";
const changedMark = () => element("span", CHANGED, "github-pull-guide-step-changed");
/** How many group headings the page has drawn, so each has an id of its own to name its list. */
let groupHeadings = 0;

/**
 * @param {HTMLElement} host
 * @param {HTMLElement | null} introduction The description's card, which the page draws and
 *   keeps current: the guide's step 0, shown while it is the step and while no step can be.
 *   A stack's guide has none, since no member's description introduces the stack, and
 *   opens on its first step.
 * @param {GuideSubject} subject The pull request or the stack whose guide this is.
 * @param {{
 *   open: (path: string) => void,
 *   openPull: (number: number, path: string | null) => void,
 *   age: (iso: string) => HTMLElement,
 *   shortCommit: (sha: string) => string,
 *   identity: (login: string, avatar: string | null) => HTMLElement,
 *   titleNodes: (title: string) => Array<Node | string>,
 *   stackGlyph: () => Node | null,
 *   loadStyles: (assets: unknown) => Promise<unknown>,
 *   loadDrawPatch: () => Promise<DrawPatch>,
 *   loadDrawDocument: () => Promise<DrawDocument>,
 *   loadDrawProse: () => Promise<DrawProse>,
 *   releaseProse?: (prose: HTMLElement) => void,
 *   refusalNote: RefusalNote,
 *   introductionReady?: () => Promise<unknown>,
 *   ahead?: (read: () => void) => () => void,
 *   moved?: () => void,
 * }} deps *open* goes to a file's Changes address, and *openPull* to another pull
 *   request's page, or to a file in its Changes. *age* and *shortCommit* say when a commit
 *   was made and name it, as the Commits tab does; *identity* draws a pull request's
 *   author, and *titleNodes*, the SDK's, its title, as a stack menu's member does, and
 *   *stackGlyph* makes the Layers glyph that names another stack's place.
 *   *loadStyles* loads the stylesheets the guide is drawn in: KPress's, from the manifest a
 *   ready step carries, and the diff plugin's; the guide waits for them, as a description
 *   does. *loadDrawPatch* loads the diff plugin's file renderer, which draws the excerpts,
 *   and *loadDrawDocument* its view of one whole file, which draws a file the rendered route
 *   renders; the view loads the rendered layer when it draws one, so a guide that cites none
 *   never loads it.
 *   *loadDrawProse* loads the allowlist a note's rendered Markdown is inserted through, and
 *   *refusalNote* says why a note's render was refused, in a description's words.
 *   *releaseProse* hears each note the guide drew once it lets the note go: its step left
 *   for another, a step composed out of sight given up, and the guide's end, so the page
 *   puts away what it gave the note, its links' cards.
 *   *introductionReady* settles once the introduction shows as it will stay, its Markdown
 *   inserted or refused, which the overview waits for. *ahead* schedules a read ahead of the
 *   reader, as the page schedules its idle work, and returns its canceller; without it a
 *   step is read ahead at once.
 *   *moved*, a stack's page's, hears each read the route answers `stack_moved`, which says
 *   the comparison the guide is read at has moved, so the page can read the stack at once
 *   rather than at its next poll, and offer the comparison the refusal names.
 *
 * Nothing the guide shows moves once shown (docs/design-system.md, "Guided Review"). Each
 * answer is composed out of sight, its step's card with every excerpt and document drawn,
 * and replaces what is shown in one change once everything its layout depends on is in hand:
 * the answer, the stylesheets and renderers it is drawn with, each document it draws whole,
 * and, for the overview, the introduction. Until then what was shown stays: before the first
 * answer, the page's delayed loading block, and after it the step the reader left, with a
 * delayed spinner beside the step list that takes no room. The answers are the document's
 * (guide-reads.js), read ahead, so a step the reader goes to is usually in hand.
 */
export function mountGuidedReview(host, introduction, subject, deps) {
  const { loadStyles, loadDrawPatch, loadDrawDocument, loadDrawProse, refusalNote } = deps;
  /** @type {ReferenceWays} */
  const ways = {
    open: deps.open,
    openPull: deps.openPull,
    age: deps.age,
    shortCommit: deps.shortCommit,
    identity: deps.identity,
    titleNodes: deps.titleNodes,
    stackGlyph: deps.stackGlyph,
    subject: subject.kind,
  };
  const stacked = subject.kind === "stack";
  // A stack's guide opens on its first step: it has no overview to show.
  const first = stacked ? 1 : 0;
  /** @type {Readonly<Record<string, string>>} */
  const said = stacked ? STACK_MESSAGES : MESSAGES;
  // The card the overview shows, which a stack's guide never places. It shows with the
  // guide's first answer, never before it.
  const intro = introduction ?? element("div");
  intro.hidden = true;
  // A stack's guide is read at the comparison its page draws, as its other tabs are.
  const asks = guideAsks(subject);
  /** @type {Promise<unknown> | null} */
  let styles = null;
  // Whether the text's stylesheets and what draws a step are in hand, so a step read ahead
  // can be shown at once (`peek`).
  let stylesIn = false;
  let drawersIn = false;
  /** @type {DrawPatch | null} */
  let drawPatch = null;
  /** @type {DrawDocument | null} */
  let drawDocument = null;
  /** @type {DrawProse | null} */
  let drawProse = null;
  /** @type {Map<string, Presentation>} */
  const blockModes = new Map();
  // What draws a step, asked for as the guide mounts, beside its first read. Without the diff
  // plugin a step still reads, and says its excerpts are unavailable; a file the rendered
  // route renders says its diff is unavailable, beside its Open full diff. The view loads the
  // rendered layer only when it draws such a file. Without the allowlist a note shows as
  // typed, as a description's text does.
  const drawers = Promise.all([
    loadDrawPatch().catch((error) => {
      console.warn("metabrowser github: the diff plugin did not load for the guide", error);
      return null;
    }),
    loadDrawDocument().catch((error) => {
      console.warn("metabrowser github: the diff plugin did not load for the guide", error);
      return null;
    }),
    loadDrawProse().catch((error) => {
      console.warn("metabrowser github: the guide's notes will show as typed", error);
      return null;
    }),
  ]).then(([patch, document_, prose]) => {
    drawPatch = patch;
    drawDocument = document_;
    drawProse = prose;
    drawersIn = true;
  });
  /** The views the shown step drew, disposed when another is shown or the guide ends. */
  /** @type {Array<{dispose: () => void}>} */
  let drawn = [];
  const undraw = () => {
    for (const patch of drawn) {
      patch.dispose();
    }
    drawn = [];
  };
  /** The reads ahead of the reader not yet made, each by its canceller. */
  /** @type {Set<() => void>} */
  const reading = new Set();
  // The guide's steps, listed above the one shown: each names its step and goes to it, and
  // the arrows page through them in order.
  const outline = element("nav", "", "page-card github-pull-card github-pull-guide-outline");
  outline.setAttribute("aria-label", `${GUIDE} steps`);
  const outlineHead = element("div", "", "github-pull-card-head github-pull-guide-outline-head");
  const badge = guideBadge();
  const status = element("span", "", "github-pull-guide-position");
  status.setAttribute("role", "status");
  const [previous] = arrowButton("previous", "github-pull-guide-arrow");
  const [next] = arrowButton("next", "github-pull-guide-arrow");
  previous.setAttribute("aria-label", "Previous step");
  next.setAttribute("aria-label", "Next step");
  // While the step a reader goes to is read, past the loading delay, a spinner beside the
  // step list says so. It is out of flow, so it moves nothing when it shows or goes.
  const waiting = element("span", "", "loading mb-delayed-loading github-pull-guide-waiting");
  waiting.setAttribute("role", "status");
  waiting.setAttribute("aria-label", "Loading the review step");
  const spinner = element("span", "", "spinner");
  spinner.setAttribute("aria-hidden", "true");
  waiting.append(spinner);
  waiting.hidden = true;
  const arrows = element("span", "", "github-pull-guide-arrows");
  arrows.append(waiting, previous, status, next);
  outlineHead.append(badge, arrows);
  const list = element("ol", "", "github-pull-guide-steps");
  outline.append(outlineHead, list);
  outline.hidden = true;
  let detail = element("section", "", "github-pull-guide-step");
  const notice = element("p", "", "github-pull-quiet");
  notice.setAttribute("role", "status");
  // After a step, the way on names where it goes, so the reader need not scroll back up.
  const pager = element("div", "", "github-pull-guide-pager");
  const [back, backLabel] = arrowButton("previous", "github-pull-guide-pager-previous", true);
  const [onward, onwardLabel] = arrowButton("next", "github-pull-guide-pager-next", true);
  pager.append(back, onward);
  pager.hidden = true;
  // What an out-of-date guide says leads the page, above its steps.
  const outdatedNote = element("div", "", "github-pull-guide-outdated");
  outdatedNote.hidden = true;
  notice.hidden = true;
  // Until the first answer is shown, the page's delayed loading block holds the guide's
  // place, the one the page drew while the guide loaded when there is one, so a block
  // already shown stays where it is.
  const loading =
    /** @type {HTMLElement | null} */ (host.querySelector(":scope > .mb-delayed-loading")) ??
    (() => {
      const block = element("div", "", "mb-delayed-loading");
      block.setAttribute("role", "status");
      block.setAttribute("aria-label", "Loading the guide");
      const skeleton = element("div", "", "recent-loading github-pull-loading");
      skeleton.setAttribute("aria-hidden", "true");
      block.append(skeleton);
      return block;
    })();
  // Placed around the block, which is not moved, so its delay does not start again.
  for (const child of [...host.children]) {
    if (child !== loading) {
      child.remove();
    }
  }
  if (loading.parentNode !== host) {
    host.append(loading);
  }
  for (const node of [
    outdatedNote,
    outline,
    ...(introduction === null ? [] : [introduction]),
    detail,
    notice,
    pager,
  ]) {
    host.insertBefore(node, loading);
  }
  /** @param {Staleness | null | undefined} stale */
  const showStale = (stale) => {
    const warned = stale ? staleNotice(stale, subject.kind) : null;
    outdatedNote.hidden = warned === null;
    outdatedNote.replaceChildren(...(warned === null ? [] : [warned]));
  };
  /** @type {string[]} */
  let titles = [];
  /** The guide's groups and steps in reading order, as the route answers them.
   * @type {Array<OutlineStep | OutlineGroup>} */
  let entries = [];
  /** @type {number[]} */
  let changedSteps = [];
  /** @param {number} at */
  const nameOf = (at) => stepName(at, titles[at - 1] ?? "");
  /**
   * The step list's rows, built once for each outline and updated in place, so the row a
   * reader activated keeps focus, as the tab bar keeps its links across paints. A row's
   * index is its step's number, the overview's 0.
   *
   * @type {{key: string | null, rows: {link: HTMLButtonElement, mark: HTMLElement}[]}}
   */
  let built = { key: null, rows: [] };

  /**
   * A step's row: its number and its title. The overview's has no number, so its title
   * starts on the edge a group's heading starts on, with nothing before it.
   *
   * @param {number} index @param {string} title
   */
  function stepRow(index, title) {
    const link = document.createElement("button");
    link.type = "button";
    link.className = "github-pull-guide-steps-link";
    if (index !== 0) {
      link.append(element("span", String(index), "github-pull-guide-steps-number"));
    }
    link.append(element("span", title, "github-pull-guide-steps-title"));
    link.addEventListener("click", () => navigation.go(index));
    return { link, mark: changedMark() };
  }

  /** @param {{link: HTMLButtonElement}} row */
  function listItem({ link }) {
    const item = element("li", "", "github-pull-guide-steps-item");
    item.append(link);
    return item;
  }

  /**
   * A group in the step list: its heading, with no number and nothing to press, since the
   * reader moves between steps alone, above its steps, which keep their numbers. The
   * heading names the group's list, as a menu's group heading names its group.
   *
   * @param {OutlineGroup} group @param {{link: HTMLButtonElement}[]} rows
   */
  function groupItem(group, rows) {
    groupHeadings += 1;
    const heading = element("div", group.title, "group-heading github-pull-guide-steps-heading");
    heading.id = `github-pull-guide-group-${groupHeadings}`;
    const steps = element("ol", "", "github-pull-guide-steps-members");
    steps.setAttribute("aria-labelledby", heading.id);
    steps.append(...rows.map(listItem));
    const item = element("li", "", "github-pull-guide-steps-group");
    item.append(heading, steps);
    return item;
  }

  /** @param {number} at */
  function paintOutline(at) {
    outline.hidden = titles.length === 0;
    const count = titles.length;
    // What is shown, by name: the overview, or a step and how many there are. A stack's
    // guide has no overview, so before its first step it names no place.
    status.textContent = at < first ? "" : placeName(at, count);
    previous.disabled = at <= first;
    next.disabled = at >= count;
    const key = JSON.stringify(entries);
    if (built.key !== key) {
      // A row for each place, by its index; a stack's guide lists no overview.
      const rows = [stepRow(0, OVERVIEW)];
      const items = first === 0 ? [listItem(rows[0])] : [];
      for (const entry of entries) {
        if (entry.kind === "step") {
          const row = stepRow(entry.step, entry.title);
          rows.push(row);
          items.push(listItem(row));
        } else {
          const members = entry.children.map((child) => stepRow(child.step, child.title));
          rows.push(...members);
          items.push(groupItem(entry, members));
        }
      }
      built = { key, rows };
      // A step outside any group numbers its row from the list's edge, in a column as wide
      // as the widest such number, so those steps' titles line up (styles.css).
      const loose = entries.flatMap((entry) => (entry.kind === "step" ? [entry.step] : []));
      list.setAttribute(
        "style",
        `--github-pull-guide-loose-digits: ${String(Math.max(1, ...loose)).length}`,
      );
      list.replaceChildren(...items);
    }
    for (const [index, { link, mark }] of built.rows.entries()) {
      if (changedSteps.includes(index)) {
        if (mark.parentNode !== link) {
          link.append(mark);
        }
      } else {
        mark.remove();
      }
      if (index === at) {
        link.setAttribute("aria-current", "step");
      } else {
        link.removeAttribute("aria-current");
      }
    }
    back.hidden = at <= first;
    onward.hidden = at >= count;
    backLabel.textContent = at > first ? nameOf(at - 1) : "";
    onwardLabel.textContent = at < count ? nameOf(at + 1) : "";
    // The arrows say where they go when pointed at, in the same words as the way on and back.
    previous.dataset.tipText = at > first ? `Previous: ${nameOf(at - 1)}` : "Previous step";
    next.dataset.tipText = at < count ? `Next: ${nameOf(at + 1)}` : "Next step";
  }

  /**
   * What an answer shows, composed out of sight: its step's card in a section of its own,
   * which takes the shown one's place, and the change to the rest of the guide, made in the
   * same task (`apply`). *waits* are what its layout depends on that is not in hand yet.
   *
   * @typedef {Drawing & {detail: HTMLElement, apply: () => void}} Stage
   */

  /**
   * The stage for *state* at place *at* of a guide of *steps* steps.
   *
   * @param {GuideState} state Any but the loading state, which shows nothing new.
   * @param {number} at @param {number} steps
   * @returns {Stage}
   */
  function compose(state, at, steps) {
    const shown = element("section", "", "github-pull-guide-step");
    /** @type {Stage} */
    const stage = { detail: shown, drawn: [], waits: [], apply: () => {} };
    // Each note this stage draws goes with the stage, as its excerpts do (`undraw`).
    const draw = drawProse;
    /** @type {DrawProse | null} */
    const drawNote =
      draw === null
        ? null
        : (html, base) => {
            const prose = draw(html, base);
            stage.drawn.push({ dispose: () => deps.releaseProse?.(prose) });
            return prose;
          };
    // The overview's introduction is the page's, and shows once its Markdown is in.
    const introduced = (/** @type {boolean} */ showsIntro) => {
      if (showsIntro && deps.introductionReady !== undefined) {
        stage.waits.push(deps.introductionReady());
      }
    };
    const available = "step" in state;
    if (!available && steps > 0 && state.state !== "updated") {
      // One step's read was refused or failed: the guide keeps its steps and the notice
      // the last answer drew, and the refusal takes the step's place, under the list.
      // The step is read again when the reader returns to it.
      introduced(at === 0);
      stage.apply = () => {
        paintOutline(at);
        pager.hidden = false;
        intro.hidden = at !== 0;
        notice.hidden = false;
        notice.textContent =
          state.state === "invalid"
            ? (state.message ?? "This guide is invalid.")
            : state.state === "error"
              ? STEP_MESSAGES.error
              : stacked && STACK_STEP_REFUSALS.has(state.state)
                ? (said[state.state] ?? STEP_MESSAGES.refused)
                : STEP_MESSAGES.refused;
      };
      return stage;
    }
    if (!available) {
      introduced(true);
      stage.apply = () => {
        // A refusal says one thing, its own reason, whatever a stale guide's answer carries.
        showStale(null);
        titles = [];
        entries = [];
        changedSteps = [];
        paintOutline(0);
        intro.hidden = false;
        pager.hidden = true;
        notice.hidden = false;
        notice.textContent =
          state.state === "invalid"
            ? (state.message ?? "This guide is invalid.")
            : (said[state.state] ?? MESSAGES.error);
      };
      return stage;
    }
    const answered = state;
    introduced(at === 0);
    stage.apply = () => {
      showStale(answered.stale);
      notice.hidden = true;
      titles = answered.titles;
      entries = answered.outline;
      changedSteps = outdated(answered.stale) ? (answered.stale.changed_steps ?? []) : [];
      paintOutline(at);
      pager.hidden = false;
      intro.hidden = at !== 0;
    };
    if (at === 0) {
      return stage;
    }
    const changed = outdated(answered.stale) ? (answered.stale.changed_steps ?? []) : [];
    const step = stepProse(answered, drawNote, refusalNote);
    const stale = answered.stale;
    const references = element("div", "", "metabrowser-diff-host github-pull-guide-references");
    /** @type {Drawers} */
    const by = { patch: drawPatch, document: drawDocument, pins: answered.comparison };
    // A file the reader folded stays folded while this guide is read at this head
    // (`foldKey`, mb-ez0x).
    const folds = guideReads.folds(asks, answered.comparison.head);
    references.append(
      ...answered.references.map((reference, index) => {
        const key = foldKey(answered.step, index, reference);
        return renderReference(reference, ways, changeOf(stale, reference), by, stage, {
          folded: folds.has(key),
          heard: (expanded) => folds.set(key, !expanded),
        });
      }),
    );
    const kinds = answered.references.map((reference) => referenceDrawing(reference, by));
    const canShowFull =
      answered.references.some(
        (reference, index) => kinds[index] === "document" && !reference.deleted,
      ) ||
      answered.references.some(
        (reference, index) => kinds[index] === "patch" && wholeSource(reference, by) !== null,
      );
    const canShowExcerpt = answered.references.some(
      (reference, index) => kinds[index] === "patch" && reference.side !== "old",
    );
    if (drawPatch?.controls && (canShowFull || canShowExcerpt || kinds.includes("document"))) {
      const key = `${answered.comparison.head}:${answered.step}`;
      const saved = blockModes.get(key) ?? (kinds.includes("document") ? null : "diff");
      const initial = saved === "full" && !canShowFull ? "current" : saved;
      const toolbar = element("div");
      /** @param {Presentation} mode */
      const apply = (mode) => {
        for (const view of stage.drawn) {
          view.show?.(mode);
        }
      };
      const control = drawPatch.controls(toolbar, canShowFull, initial, (mode) => {
        blockModes.set(key, mode);
        apply(mode);
      });
      if (initial !== null) {
        apply(initial);
      }
      stage.drawn.push(control);
      references.prepend(toolbar);
    }
    // A step is a card, as Conversation draws a comment, headed as the author's guided
    // review so it reads apart from the discussion.
    const head = element("div", "", "github-pull-card-head github-pull-guide-card-head");
    // The badge leads its label as a page header's state badge leads its line, a gap
    // apart (`.github-pull-guide-card-head`), never a space's width.
    const entry = answered.group === null ? undefined : answered.outline[answered.group];
    const group = entry?.kind === "group" ? entry : null;
    const place = element(
      "span",
      groupedPlace(group?.title ?? null, answered.step, answered.step_count),
    );
    if (changed.includes(answered.step)) {
      place.append(" · ", changedMark());
    }
    head.append(guideBadge(), place);
    const card = element(
      "section",
      "",
      "page-card github-pull-card github-pull-event github-pull-guide-card",
    );
    card.append(head, step, references);
    // A group's note opens the group: it shows above its first step.
    const opens =
      group !== null && group.note !== null && group.children[0]?.step === answered.step;
    shown.append(
      ...(opens ? groupNote(group.note ?? "", answered, drawNote, refusalNote) : []),
      card,
    );
    return stage;
  }

  /** The stage composed and laid out out of sight, until what it waits for is in. */
  /** @type {Stage | null} */
  let incoming = null;

  /** Let a stage not shown yet go: the reader moved on before it was ready. */
  function withdraw() {
    if (incoming !== null) {
      for (const view of incoming.drawn) {
        view.dispose();
      }
      incoming.detail.remove();
      incoming = null;
    }
  }

  /**
   * Show *stage* in place of what is shown, in one change: its section takes the shown one's
   * place, and the step list, the notices, and the way on and back follow it.
   *
   * @param {Stage} stage
   */
  function show(stage) {
    if (incoming === stage) {
      incoming = null;
    }
    undraw();
    drawn = stage.drawn;
    stage.detail.classList.remove("github-pull-guide-incoming");
    detail.replaceWith(stage.detail);
    detail = stage.detail;
    stage.apply();
    waiting.hidden = true;
    loading.remove();
  }

  /**
   * Show *stage* now when nothing it waits for is out, and otherwise lay it out of sight, in
   * the guide's column (`.github-pull-guide-incoming`), so its documents draw at the width
   * they show at, and show it once they are in. Meanwhile the arrows' delayed mark says it
   * is on its way, as it does while a step is read, and the arrows move on from the step at
   * *at* of *steps*, as they do then, so a reader who presses again is not held back.
   *
   * @param {Stage} stage @param {number} at @param {number} steps
   */
  function present(stage, at, steps) {
    withdraw();
    if (stage.waits.length === 0) {
      show(stage);
      return;
    }
    incoming = stage;
    stage.detail.classList.add("github-pull-guide-incoming");
    host.append(stage.detail);
    previous.disabled = at <= first;
    next.disabled = at >= steps;
    waiting.hidden = false;
    void Promise.all(stage.waits.map((wait) => wait.catch(() => {}))).then(() => {
      if (incoming === stage) {
        show(stage);
      }
    });
  }

  const navigation = createGuideNavigation({
    first,
    async read(step, _signal, revision, moved) {
      // The document's read, shared with any read ahead of it; the navigation drops an
      // answer for a step the reader has left.
      const result = await guideReads.read(asks, step, revision, moved);
      if (result.state === "stack_moved") {
        deps.moved?.();
      }
      if ("step" in result) {
        // A failed stylesheet leaves the text readable in the page's own type.
        if (result.assets !== undefined) {
          styles ??= loadStyles(result.assets).then(
            () => {
              stylesIn = true;
            },
            (error) => {
              stylesIn = true;
              console.warn("metabrowser github: the guide's text styles did not load", error);
            },
          );
        }
        await Promise.all([styles, drawers]);
        // A step with no stylesheets to load has its text styled as it stays.
        stylesIn ||= styles === null;
      }
      return result;
    },
    peek(step, revision, moved) {
      return stylesIn && drawersIn ? guideReads.peek(asks, step, revision, moved) : undefined;
    },
    prefetch(step, revision, moved) {
      const run = () => {
        reading.delete(cancel);
        guideReads.prefetch(asks, step, revision, moved);
      };
      const cancel = deps.ahead?.(run) ?? (() => {});
      reading.add(cancel);
      if (deps.ahead === undefined) {
        run();
      }
    },
    render(state, at, steps) {
      if (state.state === "loading") {
        // What is shown stays until the step the reader went to is ready to show whole. The
        // arrows move on from that step, so a reader who presses again is not held back.
        withdraw();
        previous.disabled = at <= first;
        next.disabled = at >= steps;
        waiting.hidden = false;
        return;
      }
      present(compose(state, at, steps), at, steps);
    },
  });
  previous.addEventListener("click", () => navigation.move(-1));
  next.addEventListener("click", () => navigation.move(1));
  // The way on below a step starts the next one at its top, where the step list is.
  for (const [button, by] of /** @type {const} */ ([
    [back, -1],
    [onward, 1],
  ])) {
    button.addEventListener("click", () => {
      navigation.move(by);
      outline.scrollIntoView?.({ block: "start" });
    });
  }
  return {
    ...navigation,
    dispose() {
      navigation.dispose();
      for (const cancel of reading) {
        cancel();
      }
      reading.clear();
      withdraw();
      undraw();
    },
  };
}

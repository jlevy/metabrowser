// A native stack's page at /stack/<n>: the whole stack as one comparison.
//
// The stack route (`GET stack`, pull_stack.py) answers the stack's members and its combined
// comparison: from the bottom member's merge base to the top member's head, restricted to
// the files some layer changes. The page is a pull request's page made of the same parts
// (docs/design-system.md, "Stacks" and "Page Headers"): a header, a tab bar, and a body.
//
// The header is a page header, in a pull request's order: the Layers glyph in the state
// icon's slot, "Stack", and the number, with the View on GitHub button in its corner (the
// SDK's `mountCounterpart`, which asks the server where `/stack/<n>` goes: GitHub's page of
// the whole stack); the members as a stack, top first, each the stack menu's member row
// (stack-member-row.js), in a card; the merge the stack makes, the top member's head → the
// base; the status line while the page has something to say; the size line, "1 file
// changed"; and the Diff summary as the last line, drawn from the comparison the page shows,
// closed, as a pull request's page draws its own. The header, its title, its status line
// with its numbered controls, and its pending placeholders are built with the pull request
// page's own builders (`pageHeaderParts`, `titleHeading`, `statusLine`,
// `numberHeaderControls`, `summaryPlaceholders`), so they are a pull request's by
// construction. Every row but the status line is decided at first paint (`stackHeader`):
// the members come from the shared stack snapshot (pull-stacks.js) before the stack's own
// answer, and the size line and the summary hold the shell's pending placeholder until
// theirs, so nothing under the title moves as the answer lands.
//
// Its tabs are a pull request's Guided Review, Docs, and Changes, with Guided Review only
// when a member's description carries the stack's guide; Conversation and Checks are each
// member's own, and the list of files is the header's Diff summary, as on a pull request's:
//
// - **Guided Review** (`/stack/<n>/guided`), the front page when the stack has a guide: the
//   guide's steps (guided-review.js), read against the stack's comparison
//   (`guided-review?stack=`), opening on its first step, since no member's description
//   introduces the stack.
// - **Docs** (`/stack/<n>/docs`): the documents alone, drawn as a pull request's Docs draws
//   them (`DOCS_DRAWING`, diff-drawing.js).
// - **Changes** (`/stack/<n>/changes[/<path>]`), the front page otherwise: every file, as a
//   pull request's Changes.
//
// Docs and Changes draw the combined diff exactly as a pull request's tabs draw its own:
// the same drawings, and the same hold (`holdDiff`), out of sight until the first screen's
// Markdown waits no more, at most `CHANGES_FIRST_SCREEN_MS`, so the first screen the reader
// sees is the one that stays.
//
// The page reads the stack route on a poll, as a pull request's page reads its own, while
// it is in sight. It asks `pull-refresh` for each member the answer names as pending, a
// member with no record as the reader's own open of it, and asks again, later each time,
// for one whose ask the server refused or that did not reach it (`refreshAsks`,
// `askAnswered`). A member whose fetch ended without a usable record is named, with a
// Retry (`asksAfterRead`). While it is open it sends the top member's automatic ask, which
// keeps the repository's list probed so that the catalog keeps reporting every member's
// head (docs/project/specs/active/plan-2026-11-24-stack-review.md, "Staying Current").
//
// A comparison drawn stays drawn while the stack moves, since the server keeps answering a
// pair it gave, and keeps the one each poll names `since` (pull_stack_retained.py); a new
// one is drawn, kept from, or offered by one rule (`answerAction`). One the reader would see
// no difference in, the same two commits and the same files, is no change: the drawn one
// stays, nothing is drawn again, and a later notice says what changed since that answer.
// Any other, until the reader does anything on the page, is drawn in its place silently,
// since a stack whose members' records arrive one by one catches up and has not changed;
// after that it is offered, its notice saying what changed in each member (`changeText`),
// from the members of the two answers and the commits each new head adds (`moved`, which
// the poll asks `since` the comparison drawn), naming no member whose new head the drawn
// comparison already shows, or, while a member it waits on is fetched, held until it
// arrives. An answer without `moved` says the server no longer keeps the comparison drawn:
// the new one is drawn in its place if it looks the same, and otherwise offered at once.
// `bodyPlan` decides what the body does with each answer, and a file is scrolled to once,
// when the reader opens it, never again by a later answer. Guided Review stays with it
// (`guideShown`): the guide is read again when the reader takes the comparison offered, or
// when the description that carries it changes.
//
// tests/dom/github-stack-page-session.js runs the pure parts and the controller here from
// the command line.

import { CHANGES_DRAWING, citedPullComparison, DOCS_DRAWING, DOCS_GROUP } from "./diff-drawing.js";
import { GUIDE_DOCUMENT_HOLD_MS, guideAsks, guideReads } from "./guide-reads.js";
import {
  actionText,
  actorSentence,
  agesLine,
  attachTabKeys,
  authorLabel,
  CHANGES_FIRST_SCREEN_MS,
  changedPaths,
  changesDocuments,
  describeLabel,
  FAST_POLL_MS,
  fetchedNote,
  h,
  headerSentence,
  holdDiff,
  isPlainClick,
  labelChip,
  manifestFiles,
  noFiles,
  numberHeaderControls,
  PREFETCH_IDLE_TIMEOUT_MS,
  pageHeaderParts,
  paintSizeLine,
  pullAge,
  relativeAge,
  retellAges,
  rowStrut,
  SLOW_POLL_MS,
  showNote,
  stackMemberAuthor,
  stackMemberIdentity,
  stateBadge,
  statusLine,
  summaryPlaceholders,
  textRefusalNote,
  textRouteOpening,
  titleHeading,
} from "./pull-page.js";
import { stackLabel, stackMenuOrder, stackPosition, watchStacks } from "./pull-stacks.js";
import { listedState, PULL_STATES, STACK_STATE_ORDER } from "./pull-state.js";
import { stackMemberRow } from "./stack-member-row.js";

export const STACK_ROUTE = "/api/plugin/github/stack";
const REFRESH_ROUTE = "/api/plugin/github/pull-refresh";
// How long an ask the server refused (`too_many` while its reader jobs are all taken,
// `MAX_PULL_JOBS` in mirror_refresh.py), or that did not reach it, waits before it is sent
// again: doubling from the pull page's fast poll to its slow one, so a cold stack of more
// members than the server fetches at once is asked for as its jobs end, and a server that
// is down is asked at most every thirty seconds.
export const ASK_BACKOFF_MS = Object.freeze([2000, 4000, 8000, 16000, SLOW_POLL_MS]);
// What the page says while the stack route cannot be read. The poll keeps asking, so it offers
// no remedy, and the last answer read stays drawn beneath it.
export const UNREADABLE = "Could not read this stack.";

/** The tabs, in the order the bar shows them; their ids are the route's segments. Guided
 * Review shows only for a stack with a guide, and leads, as the author's reading order. The
 * change set's files are the header's Diff summary, as on a pull request's page, so no tab
 * lists them. */
export const STACK_TABS = Object.freeze([
  Object.freeze({ id: "guided", label: "Guided Review" }),
  Object.freeze({ id: "docs", label: "Docs" }),
  Object.freeze({ id: "changes", label: "Changes" }),
]);

/**
 * @typedef {{number: number, place: number, title: string | null, state: "open" | "draft" | "merged" | "closed" | null, author: string | null, avatar: string | null, base: string | null, head: string | null, in_top: boolean | null, pending: boolean, fetching?: boolean}} StackMember
 * @typedef {{left: string, right: string, key: string, route: string, image_route: string, rendered_route: string}} StackComparison
 * @typedef {{path: string, layers: Array<{number: number, place: number, path: string}>}} StackFile
 * @typedef {{
 *   state: "absent" | "pending" | "current",
 *   reason: string | null,
 *   number: number,
 *   base_ref: string | null,
 *   head_ref: string | null,
 *   open: boolean | null,
 *   members: StackMember[],
 *   pending: number[],
 *   lacking: number[],
 *   states: StackStates,
 *   opened_at: string | null,
 *   updated_at: string | null,
 *   authors: StackPerson[],
 *   mergers: StackPerson[],
 *   fetched_at: string | null,
 *   labels: Array<{name: string, color: string | null, description: string | null}> | null,
 *   commits: number | null,
 *   size: {pushed_bytes: number, diff_bytes: number} | null,
 *   comparison: StackComparison | null,
 *   totals: {files: number, additions: number | null, deletions: number | null, exact: boolean} | null,
 *   truncated: boolean,
 *   files: StackFile[],
 *   guide: {number: number, revision: string} | null,
 *   github_url: string | null,
 *   probe: {number: number, held: string | null, every_s: number} | null,
 *   moved: StackMoved | null,
 * }} StackEnvelope
 * @typedef {{open: number, draft: number, merged: number, closed: number}} StackStates
 *   How many members are in each state.
 * @typedef {{login: string, avatar: string | null}} StackPerson An author or a merger.
 * @typedef {{since: string, members: Array<{number: number, commits: number | null}>}} StackMoved
 *   Asked `since` a comparison the route gave before: each member, in both, whose head moved
 *   from it, with the commits its new head adds, or null when its branch was rewritten.
 */

/**
 * @typedef {{number: number, revision: string}} StackGuide The member whose description
 * carries the stack's guide, and the revision of its record.
 */

/**
 * The guide the page shows: the stack's answer's while the stack is current, and the one
 * it showed while the stack is pending or cannot be shown, as the comparison drawn stays
 * then, so a member's push does not take Guided Review away while it is fetched.
 *
 * @param {StackGuide | null} kept The guide shown before this answer.
 * @param {StackEnvelope | null} envelope
 * @returns {StackGuide | null}
 */
export function guideShown(kept, envelope) {
  if (envelope === null) {
    return kept;
  }
  return envelope.state === "current" ? envelope.guide : (envelope.guide ?? kept);
}

/**
 * The tab a route shows: its own, or the front page's, Guided Review when a member's
 * description carries the stack's guide (`guideShown`) and Changes otherwise. Before the
 * stack is read, the front page shows none, so no tab is marked that the answer then moves
 * from; Guided Review's own address shows Changes for a stack with no guide.
 *
 * @param {string} tab The route's tab, "" for the front page.
 * @param {StackEnvelope | null} envelope
 * @param {StackGuide | null} guide
 * @returns {StackTab}
 */
export function shownTab(tab, envelope, guide) {
  if (tab === "docs" || tab === "changes") {
    return tab;
  }
  if (envelope === null) {
    return tab === "guided" ? "guided" : "";
  }
  return guide === null ? "changes" : "guided";
}

/**
 * What a reader sees of an answer's comparison, as one string: its two commits, and the files
 * the stack's comparison keeps with their totals. Docs, Changes, and the Diff summary are
 * drawn from these alone, since each file's diff is the two commits', so two comparisons
 * with the same look draw the same body; null for an answer that draws none.
 *
 * @param {StackEnvelope | null} envelope
 * @returns {string | null}
 */
export function comparisonLook(envelope) {
  if (envelope === null || envelope.state !== "current" || envelope.comparison === null) {
    return null;
  }
  const { left, right } = envelope.comparison;
  const paths = envelope.files.map((file) => file.path);
  return JSON.stringify([left, right, paths, envelope.totals, envelope.truncated]);
}

/**
 * What a new answer does to the comparison the body draws: `wait` while there is none to
 * show, `show` the first, and `keep` the drawn one while the stack is pending or cannot be
 * shown, and for another comparison that looks the same (`comparisonLook`), since nothing
 * the reader sees would change; any other is drawn in its place, `adopt`, before the reader
 * has done anything on the page, is held, `hold`, while a member it waits on is fetched, and
 * is otherwise offered, `offer`, for the reader to take.
 *
 * The server keeps the comparison drawn while the page's poll names it (`since`), and says
 * so in `moved`, which it answers only for a comparison it keeps. An answer with another
 * comparison and no `moved` says the drawn one is gone, so the reads of what is drawn would
 * be refused: one that looks the same is drawn in its place at once, and any other is
 * offered without waiting for a member's fetch, so the reader always has a way on.
 *
 * @param {StackBody} body
 * @param {StackEnvelope | null} envelope
 * @param {boolean} interacted Whether the reader has scrolled, clicked, pressed a key, or
 *   opened a tab or a file on the page.
 * @param {number[]} failed The members whose fetch ended without a usable record.
 * @returns {"wait" | "show" | "keep" | "adopt" | "hold" | "offer"}
 */
export function answerAction(body, envelope, interacted, failed) {
  const next = envelope?.state === "current" ? (envelope.comparison ?? null) : null;
  if (envelope === null || next === null) {
    return body.drawn === null ? "wait" : "keep";
  }
  if (body.drawn === null) {
    return "show";
  }
  if (next.key === body.drawn.key) {
    return "keep";
  }
  const kept = envelope.moved !== null;
  if (comparisonLook(envelope) === comparisonLook(body.answer)) {
    return kept ? "keep" : "adopt";
  }
  if (!interacted) {
    return "adopt";
  }
  if (!kept) {
    return "offer";
  }
  return envelope.pending.some((number) => !failed.includes(number)) ? "hold" : "offer";
}

// How many changes a notice of a new comparison names before it counts the rest.
export const CHANGES_NAMED = 3;
// What the notice says when the two answers name no change of a member.
const CHANGED = "This stack has changed since its comparison was drawn.";

/**
 * *items* as one list a sentence reads: "a", "a and b", "a, b, and c".
 *
 * @param {string[]} items
 */
function joined(items) {
  return items.length === 1
    ? items[0]
    : `${items.slice(0, -1).join(", ")}${items.length > 2 ? "," : ""} and ${items.at(-1)}`;
}

/**
 * What became of one member, in both answers, since the comparison drawn, or null.
 *
 * @param {StackMember} was
 * @param {StackMember} now
 * @param {Map<number, number | null> | null} added The commits each moved member's new head
 *   adds, or null when the answer does not say.
 * @returns {string | null}
 */
function memberChange(was, now, added) {
  const pull = `#${now.number}`;
  if (was.state !== now.state) {
    if (now.state === "merged") {
      return `${pull} was merged`;
    }
    if (now.state === "closed") {
      return `${pull} was closed`;
    }
    if (was.state === "merged" || was.state === "closed") {
      return `${pull} was reopened`;
    }
  }
  if (was.head !== now.head) {
    const commits = added?.get(now.number);
    if (commits === 0) {
      // Its new head adds nothing the comparison drawn did not show: its record caught up.
      return null;
    }
    if (typeof commits === "number") {
      return `${pull} has ${commits} new ${commits === 1 ? "commit" : "commits"}`;
    }
    return commits === null ? `${pull} was rewritten` : `${pull} was updated`;
  }
  return was.base === now.base ? null : `${pull} was updated`;
}

/**
 * What the notice of a new comparison says: what became of each member since the comparison
 * drawn, top first, in one sentence, "#845 has 2 new commits, #843 was merged, and #848
 * joined the stack.", naming at most `CHANGES_NAMED` changes and counting the rest. A
 * member's new commits come from the answer's `moved`, when it was asked `since` the
 * comparison drawn.
 *
 * @param {StackEnvelope | null} drawn The answer whose comparison is drawn.
 * @param {StackEnvelope} envelope The answer whose comparison is offered.
 * @returns {string}
 */
export function changeText(drawn, envelope) {
  const before = new Map((drawn?.members ?? []).map((member) => [member.number, member]));
  const after = new Set(envelope.members.map((member) => member.number));
  const since = drawn?.comparison?.key ?? null;
  const added =
    envelope.moved !== null && envelope.moved.since === since
      ? new Map(envelope.moved.members.map((member) => [member.number, member.commits]))
      : null;
  /** @type {string[]} */
  const changes = [];
  for (const member of topFirst(envelope)) {
    const was = before.get(member.number);
    const change =
      was === undefined ? `#${member.number} joined the stack` : memberChange(was, member, added);
    if (change !== null) {
      changes.push(change);
    }
  }
  for (const member of topFirst(drawn)) {
    if (!after.has(member.number)) {
      changes.push(`#${member.number} left the stack`);
    }
  }
  if (
    changes.length === 0 &&
    drawn !== null &&
    drawn.members.map((member) => member.number).join() !== [...after].join()
  ) {
    changes.push("the stack’s order changed");
  }
  if (changes.length === 0) {
    return CHANGED;
  }
  const named =
    changes.length > CHANGES_NAMED
      ? [
          ...changes.slice(0, CHANGES_NAMED - 1),
          `${changes.length - CHANGES_NAMED + 1} more pull requests changed`,
        ]
      : changes;
  const sentence = joined(named);
  return `${sentence[0].toUpperCase()}${sentence.slice(1)}.`;
}

/**
 * One member's ask, by the member's number and the head its record has: in flight
 * (`asking`), refused or unanswered and sent again at `due` (`waiting`), taken by the
 * server, which answered once a read sent after the `after`th saw it (`accepted`), or
 * ended without a usable record (`failed`). `checked` marks a reader's ask whose fetch one
 * answer showed ended, which the next read confirms before the page names it failed.
 *
 * @typedef {{number: number, retry: boolean, phase: "asking" | "waiting" | "accepted" | "failed", tries: number, due: number, after: number, checked: boolean}} MemberAsk
 */

/**
 * The members to ask `pull-refresh` for now: each that the answer names as pending and
 * that has no ask of its head yet, or whose refused ask is due again. *asks* holds each
 * member's ask by its key, its number and the head its record has (none, for a member
 * with no record).
 *
 * A member with no record is asked as the reader's own open of it (`retry`), as a pull
 * request's page asks for one opened by a direct link: an automatic ask refreshes only a
 * record the server holds, and answers `not_cached` for one it does not. A member whose
 * record a newer head has passed is asked automatically, which the catalog's newer row
 * makes due at once.
 *
 * @param {StackEnvelope | null} envelope
 * @param {ReadonlyMap<string, MemberAsk>} asks
 * @param {number} now
 * @returns {Array<{number: number, key: string, retry: boolean}>}
 */
export function refreshAsks(envelope, asks, now) {
  if (envelope === null || envelope.state === "absent") {
    return [];
  }
  return envelope.members
    .filter((member) => member.pending)
    .map((member) => ({
      number: member.number,
      key: `${member.number}:${member.head ?? ""}`,
      retry: member.head === null,
    }))
    .filter((due) => {
      const ask = asks.get(due.key);
      return ask === undefined || (ask.phase === "waiting" && now >= ask.due);
    });
}

/**
 * A member's ask once the server answered it: taken when it started or joined a fetch
 * (202), and otherwise to be sent again after `ASK_BACKOFF_MS`, longer each time. *status*
 * is null for an ask that did not reach the server; *reads* is how many reads of the stack
 * the page had sent when the answer came.
 *
 * @param {MemberAsk} ask
 * @param {number | null} status
 * @param {number} now
 * @param {number} reads
 * @returns {MemberAsk}
 */
export function askAnswered(ask, status, now, reads) {
  if (status === 202) {
    return { ...ask, phase: "accepted", after: reads, checked: false };
  }
  const wait = ASK_BACKOFF_MS[Math.min(ask.tries, ASK_BACKOFF_MS.length - 1)];
  return { ...ask, phase: "waiting", tries: ask.tries + 1, due: now + wait };
}

/**
 * Each member's ask once an answer is read: one whose fetch ended, by an answer read after
 * the server took it, with the member still pending and no fetch of it running, has
 * `failed` when it was the reader's own (the page names the member, with a Retry, rather
 * than say it is fetching), once one more read finds it so, and otherwise waits to be sent
 * again, since the server decides when an automatic one is due. The ask of a member no
 * longer pending at that head is dropped.
 *
 * @param {StackEnvelope | null} envelope
 * @param {ReadonlyMap<string, MemberAsk>} asks
 * @param {number} read Which read of the stack the answer is, counting from 1.
 * @param {number} now
 * @param {number} reads How many reads have been sent.
 * @returns {Map<string, MemberAsk>}
 */
export function asksAfterRead(envelope, asks, read, now, reads) {
  /** @type {Map<string, MemberAsk>} */
  const next = new Map();
  for (const member of envelope?.members ?? []) {
    const key = `${member.number}:${member.head ?? ""}`;
    const ask = asks.get(key);
    if (ask === undefined || !member.pending) {
      continue;
    }
    // An absent answer carries its members and their fetches too, so an ask the server took
    // before the stack stopped being one comparison ends as any other does.
    const ended = member.fetching !== true && ask.phase === "accepted" && read > ask.after;
    if (!ended) {
      next.set(key, ask);
    } else if (!ask.retry) {
      next.set(key, askAnswered(ask, null, now, reads));
    } else if (!ask.checked) {
      // The next read confirms it: a record written as the fetch ended is then read too.
      next.set(key, { ...ask, checked: true, after: read });
    } else {
      next.set(key, { ...ask, phase: "failed" });
    }
  }
  return next;
}

/**
 * The members whose fetch failed, in stack order.
 *
 * @param {StackEnvelope | null} envelope
 * @param {ReadonlyMap<string, MemberAsk>} asks
 * @returns {number[]}
 */
export function failedMembers(envelope, asks) {
  return (envelope?.members ?? []).flatMap((member) =>
    asks.get(`${member.number}:${member.head ?? ""}`)?.phase === "failed" ? [member.number] : [],
  );
}

/**
 * *numbers* as a reader reads a list of them: "#7", "#7 and #9", "#7, #8, and #9".
 *
 * @param {number[]} numbers
 */
function named(numbers) {
  return joined(numbers.map((number) => `#${number}`));
}

/**
 * The line about members the top's head does not contain, whose changes the comparison
 * leaves out, or null when it contains them all.
 *
 * @param {StackEnvelope | null} envelope
 * @returns {string | null}
 */
export function lackingText(envelope) {
  const lacking = envelope?.lacking ?? [];
  if (lacking.length === 0) {
    return null;
  }
  const which = lacking.length === 1 ? "its changes" : "each one’s changes";
  return `The top of this stack does not contain ${named(lacking)}, so this view leaves out ${which}. Open ${lacking.length === 1 ? "it" : "each"} to see them.`;
}

/** @type {Readonly<Record<string, string>>} */
const ABSENT = Object.freeze({
  not_github: "This server does not serve a GitHub repository.",
  not_stacked:
    "No stack with this number is known for this repository yet. Open the Pulls tab to look for it.",
  no_store: "This repository’s commits are not fetched yet. Open one of its pull requests first.",
  not_linear:
    "This stack’s changes cannot be shown together. Open each pull request for its changes.",
  commits_unavailable:
    "Some of this stack’s commits are not fetched yet. Open its pull requests to fetch them.",
});

/**
 * What the page says for a stack it cannot show as one comparison.
 *
 * @param {string | null} reason
 */
export function absentText(reason) {
  return (reason !== null && ABSENT[reason]) || "This stack cannot be shown.";
}

/**
 * The poll's next delay, or null for none: a page out of sight reads nothing, as a pull
 * request's does, and reads again when it comes back. In sight it reads soon while a
 * member's fetch is asked for or running, and otherwise at the top member's probe
 * interval.
 *
 * @param {StackEnvelope | null} envelope
 * @param {boolean} visible
 * @param {boolean} [busy] Whether an ask is in flight or a member's fetch runs.
 * @returns {number | null}
 */
export function pollDelay(envelope, visible, busy = false) {
  if (!visible) {
    return null;
  }
  if (envelope === null || busy || envelope.members.some((member) => member.fetching === true)) {
    return FAST_POLL_MS;
  }
  return envelope.probe === null ? SLOW_POLL_MS : envelope.probe.every_s * 1000;
}

/**
 * A notice on the header's status line: a failed read, a comparison it offers, the stack
 * moving or ceasing to be one comparison while one stays drawn, members its top lacks, or
 * members it could not fetch. `take` shows the new comparison; `retry` asks again for the
 * members named.
 *
 * @typedef {{text: string, severity: "error" | "warning" | null, action: "take" | "retry" | null}} StackNotice
 */

/**
 * What the page says about members it is fetching and members it could not, or null.
 *
 * @param {number[]} fetching
 * @param {number[]} failed
 * @param {string} until What the fetches are for: "the stack can be shown".
 * @returns {{fetching: string | null, failed: string | null}}
 */
function fetchText(fetching, failed, until) {
  return {
    fetching: fetching.length === 0 ? null : `Fetching ${named(fetching)} before ${until}.`,
    failed: failed.length === 0 ? null : `Could not fetch ${named(failed)} from GitHub.`,
  };
}

/**
 * What the header's status line says, in order: the read's failure, then what became of
 * the stack since the drawn comparison (`answerAction`): a new comparison offered, saying
 * what changed (`changeText`), or held while a member it waits on is fetched; then the
 * members its top lacks, and its members' fetches. With nothing drawn, the body says why
 * itself (`bodyPlan`).
 *
 * @param {StackEnvelope | null} envelope
 * @param {StackBody} body What the body draws.
 * @param {string | null} error
 * @param {number[]} failed The members whose fetch ended without a usable record.
 * @param {boolean} interacted Whether the reader has done anything on the page.
 * @returns {StackNotice[]}
 */
export function statusNotices(envelope, body, error, failed, interacted) {
  /** @type {StackNotice[]} */
  const notices = [];
  if (error !== null) {
    // A failed read keeps the last answer drawn, so it is a warning; with none, an error.
    notices.push({ text: error, severity: envelope === null ? "error" : "warning", action: null });
  }
  if (envelope === null || body.drawn === null) {
    return notices;
  }
  const action = answerAction(body, envelope, interacted, failed);
  if (action === "offer") {
    notices.push({ text: changeText(body.answer, envelope), severity: null, action: "take" });
  }
  if (envelope.state === "absent") {
    notices.push({ text: absentText(envelope.reason), severity: "warning", action: null });
    return notices;
  }
  const lacking = lackingText(envelope);
  if (lacking !== null) {
    notices.push({ text: lacking, severity: "warning", action: null });
  }
  const waiting = envelope.pending.filter((number) => !failed.includes(number));
  const said = fetchText(
    envelope.state === "pending" || action === "hold" ? waiting : [],
    failed,
    "its new comparison can be shown",
  );
  if (said.fetching !== null) {
    notices.push({ text: said.fetching, severity: null, action: null });
  }
  if (said.failed !== null) {
    notices.push({ text: said.failed, severity: "warning", action: "retry" });
  }
  return notices;
}

/**
 * What the body shows and has shown: the comparison drawn and the answer that named it, the
 * key of what is mounted ("" for nothing or a notice), whether that mount has finished, and
 * a file to scroll to once, which the reader's opening a file sets and the scroll clears.
 *
 * @typedef {{drawn: StackComparison | null, answer: StackEnvelope | null, shown: string,
 *   ready: boolean, jump: string | null}} StackBody
 */

/** The body before any answer. @type {StackBody} */
export const NO_BODY = Object.freeze({
  drawn: null,
  answer: null,
  shown: "",
  ready: false,
  jump: null,
});

/**
 * The body after a new answer: its first comparison is drawn, and a later one is drawn in
 * its place when `answerAction` adopts it; otherwise the drawn one stays, while the stack is
 * pending or absent, while a new one looks the same, and while a new one is held or
 * offered. An answer kept from, the drawn one's or one that looks the same, becomes what a
 * later notice says changed since: the answer, at the comparison drawn, so a member whose
 * record caught up meanwhile is not named as a change.
 *
 * @param {StackBody} body
 * @param {StackEnvelope | null} envelope
 * @param {boolean} interacted Whether the reader has done anything on the page.
 * @param {number[]} failed The members whose fetch ended without a usable record.
 * @returns {StackBody}
 */
export function bodyAnswered(body, envelope, interacted, failed) {
  const action = answerAction(body, envelope, interacted, failed);
  if (envelope === null) {
    return body;
  }
  if (action === "show" || action === "adopt") {
    return { ...body, drawn: envelope.comparison, answer: envelope };
  }
  const next = envelope.state === "current" ? envelope.comparison : null;
  if (action !== "keep" || next === null || body.drawn === null || body.answer === envelope) {
    return body;
  }
  return {
    ...body,
    answer: next.key === body.drawn.key ? envelope : { ...envelope, comparison: body.drawn },
  };
}

/**
 * The body after the reader takes the comparison offered: the answer's own, whatever it
 * holds or offers, since the reader asked for it.
 *
 * @param {StackBody} body
 * @param {StackEnvelope | null} envelope
 * @returns {StackBody}
 */
export function bodyTaken(body, envelope) {
  const next = envelope?.state === "current" ? (envelope.comparison ?? null) : null;
  return envelope === null || next === null || next.key === body.drawn?.key
    ? body
    : { ...body, drawn: next, answer: envelope };
}

/**
 * Whether the comparison drawn is the stack's own, as Guided Review reads its guide: true
 * when the answer's comparison is the one drawn or looks the same (`comparisonLook`), so an
 * edit of the description that carries the guide is read at the comparison drawn; false
 * when the stack has moved past it, so a guide its carrier's move changed is not read there;
 * null while the answer has none or nothing is drawn.
 *
 * @param {StackBody} body
 * @param {StackEnvelope | null} envelope
 * @returns {boolean | null}
 */
export function drawnCurrent(body, envelope) {
  const current = envelope?.state === "current" ? (envelope.comparison ?? null) : null;
  if (current === null || body.drawn === null) {
    return null;
  }
  return current.key === body.drawn.key || comparisonLook(envelope) === comparisonLook(body.answer);
}

// Keys pressed alone that begin a chord, as one that leaves the page for another window or
// tab does, and so are not the reader's move on the page.
const MODIFIER_KEYS = Object.freeze(new Set(["Shift", "Control", "Alt", "AltGraph", "Meta"]));

/**
 * Whether a key the document hears is the reader's move on the page: one pressed with focus
 * in the page, or on nothing in particular, the document's body or root, and not a modifier
 * pressed alone. A key typed into the shell's own fields is not.
 *
 * @param {{key: string, target: unknown}} event
 * @param {{contains(node: unknown): boolean}} container The page's own element.
 * @param {{body: unknown, documentElement: unknown}} doc
 * @returns {boolean}
 */
export function readerKey(event, container, doc) {
  if (MODIFIER_KEYS.has(event.key)) {
    return false;
  }
  const { target } = event;
  return target === doc.body || target === doc.documentElement || container.contains(target);
}

/**
 * The body after the reader opens a tab (*file* "") or a file in Changes, which is scrolled
 * to once.
 *
 * @param {StackBody} body
 * @param {string} file
 * @returns {StackBody}
 */
export function bodyOpened(body, file) {
  return { ...body, jump: file === "" ? null : file };
}

/**
 * @typedef {{do: "wait"} | {do: "notice", text: string, retry: boolean} | {do: "keep"} | {do: "scroll", file: string} | {do: "mount", key: string, tab: "guided" | "docs" | "changes", comparison: StackComparison}} BodyAction
 * @typedef {"" | "guided" | "docs" | "changes"} StackTab The tab the page shows, ""
 * while the front page waits for the stack's answer to choose one.
 */

/**
 * Whether the body is set in the reading column, as a pull request's is (pull-page.js, where
 * Conversation, Guided Review, Checks, and a page with no record take the column, and Docs
 * and Changes the full pane): Guided Review, a notice, and a body with nothing drawn yet
 * start and end where the header and the tab bar do, and Docs and Changes keep the full
 * pane so a diff has room for Split. In the full pane Guided Review's cards ran 233.75 px
 * past the header's end in a 1280 px window with the navigation pane shown (Chrome 152,
 * 2026-11-25; docs/design-system.md, "The Stack Page").
 *
 * @param {StackBody} body
 * @param {StackTab} tab
 */
export function bodyInColumn(body, tab) {
  return body.drawn === null || (tab !== "docs" && tab !== "changes");
}

/**
 * What the body does now, and the body once it has: `wait` before any answer or a tab, a
 * `notice` while nothing is drawn, `mount` the drawn comparison in the tab when that is
 * not what is mounted (Guided Review reads its guide against the stack's comparison, and
 * mounts again when another is drawn), `scroll` to a file the reader opened once the mount
 * is ready, and otherwise `keep`, so an answer that changes nothing the body shows leaves
 * the reader where they are.
 *
 * @param {StackBody} body
 * @param {StackEnvelope | null} envelope
 * @param {StackTab} tab
 * @param {number[]} failed
 * @returns {{action: BodyAction, body: StackBody}}
 */
export function bodyPlan(body, envelope, tab, failed) {
  if (body.drawn === null) {
    if (envelope === null) {
      return { action: { do: "wait" }, body };
    }
    let text = absentText(envelope.reason);
    if (envelope.state !== "absent") {
      const said = fetchText(
        envelope.pending.filter((number) => !failed.includes(number)),
        failed,
        "the stack can be shown",
      );
      text = [said.fetching, said.failed].filter((line) => line !== null).join(" ");
    }
    return {
      action: { do: "notice", text, retry: envelope.state !== "absent" && failed.length > 0 },
      body: { ...body, shown: "", ready: false },
    };
  }
  if (tab === "") {
    return { action: { do: "wait" }, body };
  }
  const key = JSON.stringify([tab, body.drawn.key]);
  if (key !== body.shown) {
    return {
      action: { do: "mount", key, tab, comparison: body.drawn },
      body: { ...body, shown: key, ready: false },
    };
  }
  if (body.ready && body.jump !== null && tab === "changes") {
    return { action: { do: "scroll", file: body.jump }, body: { ...body, jump: null } };
  }
  return { action: { do: "keep" }, body };
}

/**
 * The body once the mount of *key* has finished: ready, and the file to scroll to then,
 * once, if the reader opened one in Changes.
 *
 * @param {StackBody} body
 * @param {string} key
 * @returns {{scroll: string | null, body: StackBody}}
 */
export function bodyMounted(body, key) {
  if (key !== body.shown) {
    return { scroll: null, body };
  }
  const changes = JSON.parse(key)[0] === "changes";
  return {
    scroll: changes ? body.jump : null,
    body: { ...body, ready: true, jump: changes ? null : body.jump },
  };
}

/**
 * @typedef {{status: number, etag: string | null, body: unknown}} StackResponse
 * @typedef {{
 *   request(method: "GET" | "POST", route: string, options: {etag?: string | null, body?: unknown}): Promise<StackResponse>,
 *   schedule(callback: () => void, delayMs: number): unknown,
 *   cancel(handle: unknown): void,
 *   now(): number,
 *   isVisible(): boolean,
 *   since(): string | null,
 *   render(model: {envelope: StackEnvelope | null, error: string | null, failed: number[]}): void,
 * }} StackDependencies
 */

/**
 * The poll and the asks of one stack's page. It reads the stack route while the page is in
 * sight, one read at a time, `since` the comparison the page draws (`deps.since`), so the
 * answer says how each member moved from it; asks for each pending member and again for one
 * refused, sends the top member's automatic ask at its interval, and renders each answer
 * that changed and each change in which members it could not fetch.
 *
 * @param {StackDependencies} deps
 * @param {{number: number}} options
 */
export function createStackController(deps, options) {
  const stackRoute = `${STACK_ROUTE}?number=${options.number}`;
  /** @type {StackEnvelope | null} */
  let envelope = null;
  /** @type {string | null} */
  let error = null;
  /** @type {string | null} */
  let etag = null;
  /** Each member's ask, by its number and the head its record has. @type {Map<string, MemberAsk>} */
  const asks = new Map();
  /** The members whose fetch ended without a usable record, as last rendered. */
  let failedShown = "[]";
  /** When the top member was last asked for, by `deps.now()`. @type {number | null} */
  let probedAt = null;
  /** @type {unknown} */
  let timer = null;
  let disposed = false;
  // One read at a time: a read asked for while one is on its way is made after it, since
  // the one on its way may have left before what the new one is for.
  let polling = false;
  let readAgain = false;
  // How many reads have been sent, which an ask's answer records so that only a read sent
  // after it counts as seeing its fetch end.
  let reads = 0;

  /** @param {number} number @param {string | null} held @param {boolean} retry */
  async function send(number, held, retry) {
    try {
      const response = await deps.request("POST", REFRESH_ROUTE, {
        body: { number, ...(retry ? { retry: true } : {}), ...(held === null ? {} : { held }) },
      });
      return response.status;
    } catch {
      return null;
    }
  }

  /** @param {{number: number, key: string, retry: boolean}} due */
  async function ask(due) {
    const before = asks.get(due.key);
    asks.set(due.key, {
      number: due.number,
      retry: due.retry,
      phase: "asking",
      tries: before?.tries ?? 0,
      due: 0,
      after: 0,
      checked: false,
    });
    const status = await send(due.number, null, due.retry);
    const asked = asks.get(due.key);
    if (disposed || asked === undefined || asked.phase !== "asking") {
      return;
    }
    asks.set(due.key, askAnswered(asked, status, deps.now(), reads));
  }

  function askWhatIsDue() {
    for (const due of refreshAsks(envelope, asks, deps.now())) {
      void ask(due);
    }
    const probe = envelope?.probe ?? null;
    if (
      probe !== null &&
      deps.isVisible() &&
      (probedAt === null || deps.now() - probedAt >= probe.every_s * 1000)
    ) {
      probedAt = deps.now();
      void send(probe.number, probe.held, false);
    }
  }

  /**
   * The next delay: the poll's, or sooner when a refused ask is due before it. An absent
   * stack sends no ask (`refreshAsks`), so its waiting asks set no delay.
   */
  function nextDelay() {
    const sends = envelope !== null && envelope.state !== "absent";
    let busy = false;
    let delay = pollDelay(envelope, deps.isVisible(), false);
    for (const ask of asks.values()) {
      busy ||= ask.phase === "asking" || ask.phase === "accepted";
      if (sends && delay !== null && ask.phase === "waiting") {
        delay = Math.min(delay, Math.max(0, ask.due - deps.now()));
      }
    }
    return busy ? pollDelay(envelope, deps.isVisible(), true) : delay;
  }

  async function poll() {
    timer = null;
    if (disposed) {
      return;
    }
    if (polling) {
      readAgain = true;
      return;
    }
    polling = true;
    reads += 1;
    const read = reads;
    let changed = false;
    let answered = false;
    try {
      const since = deps.since();
      const route = since === null ? stackRoute : `${stackRoute}&since=${since}`;
      const response = await deps.request("GET", route, { etag });
      if (disposed) {
        return;
      }
      if (response.status === 200 && isStackEnvelope(response.body)) {
        envelope = response.body;
        etag = response.etag;
        error = null;
        changed = true;
        answered = true;
      } else if (response.status === 304) {
        answered = true;
        // The answer held is the current one again, so a failure said before is over.
        if (error !== null) {
          error = null;
          changed = true;
        }
      } else if (error === null) {
        // The route's own `error` is for `metab --api`, never the page's sentence.
        error = UNREADABLE;
        changed = true;
      }
    } catch {
      if (disposed) {
        return;
      }
      if (error === null) {
        error = UNREADABLE;
        changed = true;
      }
    } finally {
      polling = false;
    }
    if (answered) {
      const next = asksAfterRead(envelope, asks, read, deps.now(), reads);
      asks.clear();
      for (const [key, ask] of next) {
        asks.set(key, ask);
      }
    }
    const failed = failedMembers(envelope, asks);
    if (JSON.stringify(failed) !== failedShown) {
      failedShown = JSON.stringify(failed);
      changed = true;
    }
    if (changed) {
      deps.render({ envelope, error, failed });
    }
    askWhatIsDue();
    if (readAgain) {
      readAgain = false;
      return poll();
    }
    const delay = nextDelay();
    if (delay !== null) {
      timer = deps.schedule(() => void poll(), delay);
    }
  }

  /** Read the stack now, as the first read and a page coming back into sight do. */
  function start() {
    if (timer !== null) {
      deps.cancel(timer);
      timer = null;
    }
    return poll();
  }

  return Object.freeze({
    start,
    /** Ask again for each member whose fetch failed, as the reader's Retry does. */
    retry() {
      for (const [key, ask] of asks) {
        if (ask.phase === "failed") {
          asks.delete(key);
        }
      }
      if (failedShown !== "[]") {
        failedShown = "[]";
        deps.render({ envelope, error, failed: [] });
      }
      return start();
    },
    envelope: () => envelope,
    dispose() {
      disposed = true;
      if (timer !== null) {
        deps.cancel(timer);
        timer = null;
      }
    },
  });
}

/**
 * The members in the one order every surface lists a stack's in, the top first
 * (`stackMenuOrder`).
 *
 * @param {StackEnvelope | null} envelope
 * @returns {StackMember[]}
 */
export function topFirst(envelope) {
  const members = envelope?.members ?? [];
  const byNumber = new Map(members.map((member) => [member.number, member]));
  const stack = {
    number: envelope?.number ?? 0,
    base_ref: envelope?.base_ref ?? "",
    open: envelope?.open ?? false,
    pulls: members.map((member) => member.number),
    titles: members.map((member) => member.title),
  };
  return stackMenuOrder(stack).flatMap((number) => byNumber.get(number) ?? []);
}

/**
 * Whether *value* is the stack route's answer, as far as the page reads it.
 *
 * @param {unknown} value
 * @returns {value is StackEnvelope}
 */
export function isStackEnvelope(value) {
  const answer = /** @type {Partial<StackEnvelope> | null} */ (value);
  return (
    answer !== null &&
    typeof answer === "object" &&
    (answer.state === "absent" || answer.state === "pending" || answer.state === "current") &&
    Array.isArray(answer.members) &&
    Array.isArray(answer.files) &&
    Array.isArray(answer.pending) &&
    Array.isArray(answer.lacking)
  );
}

/**
 * @typedef {import("./pull-stacks.js").NativeStack} NativeStack
 * @typedef {import("./stack-member-row.js").StackMemberLine} StackMemberLine
 * @typedef {{state: import("./pull-state.js").PullState, title?: string | null} | null} ListedPull
 */

/**
 * The stack numbered *number* in the Pulls tab's snapshot of the repository's stacks
 * (`watchStacks`), or null where the snapshot does not hold it.
 *
 * @param {import("./pull-stacks.js").StackIndex} index
 * @param {number} number
 * @returns {NativeStack | null}
 */
export function knownStack(index, number) {
  for (const stacks of index.byPull.values()) {
    const found = stacks.find((stack) => stack.number === number);
    if (found !== undefined) {
      return found;
    }
  }
  return null;
}

/**
 * The members as the header lists them, top first, each a member row's line
 * (stack-member-row.js): the stack's answer's once it names them, and before that the
 * stack the Pulls tab knows (*known*), titled and stated as its lists last read them
 * (*listed*), so the list the answer lands on is the list the first paint drew. Null while
 * neither names a member.
 *
 * A member's author is the answer's, its record's or else its cached list row's
 * (pull_stack.py), and before the answer the one the stack menu draws, the stacks route's
 * (`stackMemberAuthor`), read from the same cached list. The answer's falls back to the
 * stacks route's too, so an answer never takes away an author the first paint drew; neither
 * names one for a member with no record and no cached row.
 *
 * @param {StackEnvelope | null} envelope
 * @param {NativeStack | null} known
 * @param {(number: number) => ListedPull} listed
 * @returns {StackMemberLine[] | null}
 */
export function memberLines(envelope, known, listed) {
  const members = envelope?.members ?? [];
  /** @param {number} number */
  const knownTitle = (number) => known?.titles?.[known.pulls.indexOf(number)] ?? null;
  /** @param {number} number */
  const author = (number) => {
    const at = known === null ? -1 : known.pulls.indexOf(number);
    return known === null || at < 0 ? null : stackMemberAuthor(known, at, null);
  };
  if (members.length > 0) {
    // A member whose record the server has not read yet keeps the title and the state the
    // Pulls tab gave it, so the answer that says it is being fetched blanks no row.
    return topFirst(envelope).map((member) => ({
      number: member.number,
      place: stackPosition(member.place - 1, members.length),
      title: member.title ?? knownTitle(member.number) ?? listed(member.number)?.title ?? null,
      state: member.state ?? listed(member.number)?.state ?? null,
      author: member.author
        ? { login: member.author, avatar: member.avatar ?? null }
        : author(member.number),
    }));
  }
  if (known === null || known.pulls.length === 0) {
    return null;
  }
  return stackMenuOrder(known).map((number) => {
    const at = known.pulls.indexOf(number);
    const row = listed(number);
    return {
      number,
      place: stackPosition(at, known.pulls.length),
      title: knownTitle(number) ?? row?.title ?? null,
      state: row?.state ?? null,
      author: author(number),
    };
  });
}

/**
 * The tally that leads the row of ages, where a pull request's state badge is
 * (docs/design-system.md, "The Stack Page"): a badge for each state some member is in, in
 * its state's ink, in the order a stack's members run from its top (`STACK_STATE_ORDER`),
 * "5 Pulls Draft", "2 Pulls Open", and none for a state no member is in, nor while the
 * answer is on its way. A badge's `words` are its count, its noun, and its state's word, and
 * its `label` is those said together, so the badge drawn from the words (`tallyBadge`) and
 * its name never differ.
 *
 * @param {StackEnvelope | null} envelope
 * @returns {Array<{state: import("./pull-state.js").PullState, words: [string, string, string], label: string}>}
 */
export function stateTally(envelope) {
  if (envelope === null) {
    return [];
  }
  return STACK_STATE_ORDER.flatMap((state) => {
    const count = envelope.states[state];
    if (count === 0) {
      return [];
    }
    /** @type {[string, string, string]} */
    const words = [String(count), count === 1 ? "Pull" : "Pulls", PULL_STATES[state].label];
    return [{ state, words, label: words.join(" ") }];
  });
}

/**
 * One badge of the tally (`stateTally`), a state's badge (`stateBadge`) whose words are
 * apart: the noun is a part of its own, which a row too narrow for a tally of every state
 * leaves out, "12 Merged", so the four badges still differ by their words and not by ink
 * alone (github/styles.css, `.github-pull-stack-tally-noun`). Its tooltip is its whole
 * label, which the shell shows only while the badge is cut short (docs/design-system.md,
 * "Tooltips Add Information").
 *
 * @param {ReturnType<typeof stateTally>[number]} badge
 */
export function tallyBadge({ state, words: [count, noun, word], label }) {
  const badge = stateBadge(state, label);
  badge.replaceChildren(
    `${count} `,
    h("span", { class: "github-pull-stack-tally-noun" }, [`${noun} `]),
    word,
  );
  badge.dataset.tipText = label;
  return badge;
}

/**
 * One actor of the stack's sentence: the pull request page's (`authorLabel`), its name its
 * own tooltip, which the shell shows only while the name is cut short (docs/design-system.md,
 * "Tooltips Add Information"). A sentence of several names cuts each to its floor in a
 * narrow pane, an avatar and a letter or two (github/styles.css, `.github-pull-identity`).
 *
 * @param {MetabrowserPublicSdk} mb
 * @param {StackPerson} actor
 */
export function sentenceActor(mb, actor) {
  const identity = authorLabel(mb, actor.login, actor.avatar, "", { loading: "eager" });
  const name = identity.querySelector(".github-pull-author");
  if (name instanceof HTMLElement) {
    name.dataset.tipText = actor.login;
  }
  return identity;
}

/**
 * The author's row's sentence, a pull request's said of the stack (`headerSentence`): every
 * member's author, each once, top first, and the commits of the members the top contains,
 * "wants to merge 12 commits", "want to merge" after two or more; once every member is
 * merged, every merger, "merged 12 commits", and none where no merger is known, so the
 * action is said alone rather than crediting the authors, as a pull request's is. Null while
 * the answer is on its way, and for a stack not merged whose authors are not known yet,
 * before any member's record or list row is read.
 *
 * @param {StackEnvelope | null} envelope
 * @returns {{actors: StackPerson[], action: string} | null}
 */
export function stackSentence(envelope) {
  if (envelope === null || envelope.members.length === 0) {
    return null;
  }
  const merged = envelope.states.merged === envelope.members.length;
  if (!merged && envelope.authors.length === 0) {
    return null;
  }
  return headerSentence(merged, envelope.authors, envelope.mergers, envelope.commits);
}

/**
 * The labels the Pulls tab's snapshot of the stack names (`labels` of the stacks route), the
 * members' each once, top first, before the stack's answer says them: by name alone, as a
 * cached list row gives them. Null where it does not know them all, as for a member with
 * neither a record nor a list row, so the labels row is held until the answer says.
 *
 * @param {NativeStack | null} known
 * @returns {Array<{name: string, color: null, description: null}> | null}
 */
export function knownLabels(known) {
  if (known === null || !Array.isArray(known.labels)) {
    return null;
  }
  const names = new Set();
  for (const number of stackMenuOrder(known)) {
    const each = known.labels[known.pulls.indexOf(number)];
    if (!Array.isArray(each)) {
      return null;
    }
    for (const name of each) {
      names.add(name);
    }
  }
  return [...names].map((name) => ({ name, color: null, description: null }));
}

/**
 * The size line's counts for the comparison drawn, as `mb.changeSizeLine` takes them: the
 * commits and the sizes of the answer that names it (`StackBody`'s `answer`), each left out
 * while not known, and the files its Diff summary counts.
 *
 * @param {StackEnvelope | null} answer
 * @param {number | null} files
 */
export function stackSizeInput(answer, files) {
  const commits = answer?.commits ?? null;
  const size = answer?.size ?? null;
  return {
    ...(commits === null ? {} : { commits }),
    files,
    pushedBytes: size?.pushed_bytes ?? null,
    diffBytes: size?.diff_bytes ?? null,
  };
}

/**
 * The header a paint draws, row by row, a pull request's page's header made of the parts a
 * stack has, in a pull request's order (docs/design-system.md, "Stacks", "The Stack Page"):
 * its title and the View on GitHub corner; the row of ages, led by the tally of its members'
 * states (`stateTally`), when a member was last opened and last updated (`ages`); the
 * author's row, its sentence (`stackSentence`) and the freshness note, the oldest member
 * record's fetch (`note`); the merge the stack makes; the labels its members carry, each
 * once; the status line; the size line; the members, a toggle that shows them, "**12**
 * Pulls"; and the Diff summary. *rows* names them in order, and the rest is what they hold:
 * `status` the status line's notices, there only while it has something to say, and
 * `comparison` whether the size line and the Diff summary hold the comparison's pending
 * placeholder (`pending`), their lines (`drawn`), or are not there (`none`), for a stack that
 * cannot be shown as one comparison and has none drawn.
 *
 * Every row but the status line is decided at first paint, as a pull request's are: the
 * members and the labels from what the Pulls tab knows of the stack (`knownLabels`), and the
 * rest held a line tall until the answer fills them. The members' toggle is held, its words
 * empty, while neither the Pulls tab nor the answer names a member. The labels row is there
 * for a stack whose members carry labels, as a pull request's is, and held while they are not
 * known (`labels` null): an answer that says the stack has none then takes it away, as a
 * pull request's record does. Until the answer the page is `cold`, held out of sight for the
 * quiet period as a pull request's page with no record in hand is (`.github-pull-cold`), so
 * an answer that lands within it is the first header the reader sees.
 *
 * The freshness note says "Offline" as a pull request's does (`fetchedNote`) when the
 * browser reports no network (*offline*) and a member's record is behind (`pending`), since
 * no refresh can run.
 *
 * @param {StackEnvelope | null} envelope
 * @param {NativeStack | null} known
 * @param {(number: number) => ListedPull} listed
 * @param {StackNotice[]} status
 * @param {boolean} drawn Whether a comparison is drawn.
 * @param {number} nowMs The time the note's age is said at.
 * @param {boolean} [offline] Whether the browser reports no network.
 */
export function stackHeader(envelope, known, listed, status, drawn, nowMs, offline = false) {
  const members = memberLines(envelope, known, listed);
  const base = envelope?.base_ref ?? known?.base_ref ?? null;
  const head = envelope?.head_ref ?? null;
  /** @type {"pending" | "drawn" | "none"} */
  const comparison = drawn
    ? "drawn"
    : envelope === null || envelope.state !== "absent"
      ? "pending"
      : "none";
  const labels =
    (envelope?.labels ?? knownLabels(known))?.map((label) => describeLabel(label)) ?? null;
  const sized = comparison === "none" ? [] : ["size"];
  return {
    cold: envelope === null,
    rows: [
      "title",
      "corner",
      "opened",
      "meta",
      "merge",
      ...(labels === null || labels.length > 0 ? ["labels"] : []),
      ...(status.length === 0 ? [] : ["status"]),
      ...sized,
      ...(members === null && envelope !== null ? [] : ["members"]),
      ...(comparison === "none" ? [] : ["summary"]),
    ],
    tally: stateTally(envelope),
    ages: envelope === null ? null : { opened: envelope.opened_at, updated: envelope.updated_at },
    sentence: stackSentence(envelope),
    note:
      envelope === null || envelope.fetched_at === null
        ? null
        : fetchedNote(
            relativeAge(envelope.fetched_at, nowMs),
            offline && envelope.pending.length > 0,
          ),
    labels,
    members,
    merge: head === null || base === null ? null : { head, base },
    status,
    comparison,
  };
}

/**
 * The diff view's comparison for the stack's: direct, since the bottom's merge base is an
 * ancestor of the top's head, at the routes the answer names, and with no View file controls,
 * since no one branch holds a stack.
 *
 * @param {StackComparison} comparison
 */
export function diffComparison(comparison) {
  return {
    left: comparison.left,
    right: comparison.right,
    base_policy: /** @type {const} */ ("direct"),
    route: comparison.route,
    image_route: comparison.image_route,
    rendered_route: comparison.rendered_route,
    branch: null,
  };
}

/**
 * What the page passes the diff view's `render` for Docs or Changes: a pull request's Docs
 * and Changes drawings (diff-drawing.js), with no summary of the diff's own, since the
 * header has it, and the first screen's Markdown waiting for Rendered at most
 * `CHANGES_FIRST_SCREEN_MS`, while the page holds the diff out of sight. Changes takes the
 * comparison the Diff summary read (*raw*) and keeps the reader's File type choice across
 * tabs; Docs reads its documents itself.
 *
 * @param {"docs" | "changes"} tab
 * @param {StackComparison} comparison
 * @param {{signal: AbortSignal, raw?: unknown, types?: string[] | null,
 *   onTypes?: (types: string[] | null) => void,
 *   onDocument?: (document: unknown) => void}} using
 */
export function diffDrawing(tab, comparison, using) {
  return {
    comparisonSignal: using.signal,
    comparison: diffComparison(comparison),
    ...(using.raw === undefined ? {} : { raw: using.raw }),
    summary: false,
    ...(tab === "docs"
      ? {
          group: DOCS_GROUP,
          ...DOCS_DRAWING,
          emptyText: "No documents changed in this stack.",
        }
      : {
          ...CHANGES_DRAWING,
          ...(using.types === undefined ? {} : { types: using.types }),
          ...(using.onTypes === undefined ? {} : { onTypes: using.onTypes }),
        }),
    ...(using.onDocument === undefined ? {} : { onDocument: using.onDocument }),
    markdownHoldMs: CHANGES_FIRST_SCREEN_MS,
  };
}

/**
 * Mount a stack's page.
 *
 * @param {HTMLElement} container
 * @param {MetabrowserPublicRenderContext} ctx The shell's: the stack's number, the route's
 *   tab, and `open`, which goes to a tab of this page or to a member's page.
 * @param {MetabrowserPublicSdk} mb
 */
export function mountStackPage(container, ctx, mb) {
  const number = Number(ctx.number);
  const given = /** @type {{open?: unknown}} */ (ctx).open;
  /** @type {(route: {number: number, tab: string, file?: string, stack?: boolean}) => Promise<unknown>} */
  const openRoute =
    typeof given === "function"
      ? /** @type {(route: {number: number, tab: string, file?: string, stack?: boolean}) => Promise<unknown>} */ (
          given
        )
      : async () => undefined;
  const listening = new AbortController();
  container.classList.add("github-pull", "github-pull-stack-page");

  /** @param {{number: number, tab: string, file?: string, stack?: boolean}} route */
  const open = (route) => void openRoute(route);

  /**
   * @param {{number: number, tab: string, file?: string, stack?: boolean}} route
   * @param {string} href
   * @param {string} className
   * @param {Array<Node | string>} children
   */
  function link(route, href, className, children) {
    const anchor = h("a", { href, class: className }, children);
    anchor.addEventListener(
      "click",
      (event) => {
        if (isPlainClick(event)) {
          event.preventDefault();
          open(route);
        }
      },
      { signal: listening.signal },
    );
    return anchor;
  }

  /**
   * Put *nodes* in *parent* when they are not what it holds already, so a paint that
   * changes nothing moves no node and takes no focus.
   *
   * @param {HTMLElement} parent
   * @param {Array<Node>} nodes
   */
  function place(parent, nodes) {
    const held = [...parent.childNodes];
    if (held.length !== nodes.length || held.some((node, at) => node !== nodes[at])) {
      parent.replaceChildren(...nodes);
    }
  }

  // The header: a pull request's page's (docs/design-system.md, "Page Headers"), made of
  // the rows a stack has, in the order a pull request's come (`stackHeader`).
  const {
    header,
    opened: openedRow,
    meta,
    branches: branchesRow,
    labels: { row: labelsRow, list: labelList },
    status,
    size: sizeRow,
    summary: summaryRow,
  } = pageHeaderParts();
  // The row of ages: the tally of the members' states where a pull request's badge is, the
  // ages, and at its end a strut where a pull request's stack chip is, which holds the row at
  // a chip's height, as on a pull request's page (`rowStrut`).
  const tallySlot = h("span", { class: "github-pull-stack-tally" });
  const openedStrut = rowStrut();
  // The Layers glyph in the title's icon slot, where a pull request's state is, then the
  // stack's label, its number where a pull request's is.
  const layers = mb.icons?.layers
    ? new DOMParser().parseFromString(mb.icons.layers, "text/html").body.firstElementChild
    : null;
  const { heading: title } = titleHeading(
    h(
      "span",
      { class: "github-pull-state-icon github-pull-stack-title-icon", "aria-hidden": "true" },
      [layers === null ? null : document.importNode(layers, true)],
    ),
    ["Stack"],
    number,
  );
  // The header's corner, which holds View on GitHub: the SDK's control, which asks the
  // server where this page's address goes (`/api/counterpart`), the stack's own page.
  const corner = h("span", { class: "view-header-end", "data-counterpart": "" });
  // The members, top first, each the stack menu's member row, so the stack reads here as
  // it does under a pull request's stack button. They sit on the page's ground with no card,
  // as the Diff summary's files under its toggle do; the border is the popover menu's alone
  // (the owner's word of 2026-11-26). No member is this page, so none is marked. They are shown by a toggle
  // above the Diff summary, "**12** Pulls", drawn as the summary's own header is, its words
  // and then the chevron, and closed at first, as the summary is; the reader's choice holds
  // for the page's life and is not saved.
  const memberList = h("ol", {
    class: "github-pull-stack-members",
    "aria-label": `Pull requests in ${stackLabel(number)}`,
  });
  const membersId = `github-pull-stack-members-${number}`;
  const membersBody = h(
    "div",
    {
      class: "github-pull-stack-members-body github-pull-stack-members-body-collapsed",
      id: membersId,
    },
    [memberList],
  );
  const membersWords = h("span", { class: "github-pull-stack-members-count" });
  const chevronSvg = mb.icons?.toggle
    ? new DOMParser().parseFromString(mb.icons.toggle, "text/html").body.firstElementChild
    : null;
  const chevron = () => (chevronSvg === null ? null : document.importNode(chevronSvg, true));
  const membersToggle = h(
    "button",
    {
      type: "button",
      class: "summary-toggle github-pull-stack-members-toggle disclosure-toggle collapsed",
      "aria-expanded": "false",
      "aria-controls": membersId,
    },
    [
      membersWords,
      h("span", { class: "summary-toggle-chevron", "aria-hidden": "true" }, [chevron()]),
    ],
  );
  const membersRow = h("div", { class: "github-pull-stack-members-row page-header-line" }, [
    membersToggle,
    membersBody,
  ]);
  let membersOpen = false;
  membersToggle.addEventListener(
    "click",
    () => {
      membersOpen = !membersOpen;
      showMembers();
    },
    { signal: listening.signal },
  );
  // The branches line holds the merge the stack makes, its top member's head → its base, a
  // line tall while the answer that names the head is on its way. The status line is there
  // only while it has something to say.
  status.hidden = true;
  const { summary: summaryPending, size: sizePending } = summaryPlaceholders();
  const tabBar = h("div", { class: "tab-bar", role: "tablist", "aria-label": "Stack" });
  const tabColumn = h("div", { class: "page-reading-column" }, [tabBar]);
  // In the reading column until a diff tab draws (`bodyInColumn`), as a pull request's is.
  const body = h("div", { class: "github-pull-body page-reading-column" });
  const live = h("span", { class: "sr-only", "aria-live": "polite" });
  container.replaceChildren(header, tabColumn, body, live);

  // The route's tab, "" for the front page, and the tab it shows, which the front page's
  // choice decides once the stack is read.
  let routeTab = typeof ctx.tab === "string" ? ctx.tab : "";
  /** The guide the page shows (`guideShown`). @type {StackGuide | null} */
  let guide = null;
  let tab = shownTab(routeTab, null, guide);
  /** @type {StackEnvelope | null} */
  let envelope = null;
  /** @type {string | null} */
  let error = null;
  /** @type {number[]} */
  let failed = [];
  /** The stack as the Pulls tab knows it, and the repository its lists are of.
   * @type {NativeStack | null} */
  let known = null;
  /** @type {string | null} */
  let knownSource = null;
  /** What the body shows (`bodyPlan`). @type {StackBody} */
  let shown = NO_BODY;
  /** Whether the reader has done anything on the page, after which a new comparison that
   * looks different is offered rather than drawn (`answerAction`). */
  let interacted = false;
  /** @type {{dispose?: () => void, scrollToFile?: (path: string) => unknown} | null} */
  let handle = null;
  /** The guide's view while Guided Review is drawn, told each revision of the description
   * that carries the guide, and whether the stack has moved past the comparison drawn.
   * @type {{show: (revision: string | null, moved: boolean) => void,
   *   behind: (at: string | null) => void} | null} */
  let guidedView = null;
  /** The revision of the guide read at the comparison drawn while that comparison was the
   * stack's current one. @type {string | null} */
  let guideRead = null;
  /** The allowlist a guide's notes are inserted through, loaded with the first guide.
   * @type {Promise<MetabrowserInertHtmlRuntime | null> | null} */
  let inertReady = null;
  /** What a note's links open (`linkNote`): `metabrowser.loadRepositoryLinks()`'s answer,
   * asked with the allowlist, or null.
   * @type {MetabrowserRepositoryLinksRuntime | null} */
  let repositoryLinks = null;
  /** Whether the page is held out of sight as cold: null before the first paint.
   * @type {boolean | null} */
  let coldHeld = null;
  let membersKey = "";
  /**
   * Each member's item and row (`stackMemberRow`), by number, kept while the member is, so
   * an answer that changes a line changes only its nodes and an author's avatar keeps its
   * image (docs/design-system.md, "A Repaint Keeps Its Images").
   * @type {Map<number, {item: HTMLElement, row: import("./stack-member-row.js").StackMemberRow}>}
   */
  const memberRows = new Map();
  let mergeKey = "";
  let openedKey = "";
  /** The ages the row of ages shows, kept while they are the same (`paintOpened`).
   * @type {HTMLElement | null} */
  let agesNode = null;
  let metaKey = "";
  /** The sentence's actors, by login and avatar, kept while they are, so an avatar keeps its
   * image. @type {Map<string, HTMLElement>} */
  let actorNodes = new Map();
  let labelsKey = "";
  let countKey = "";
  let statusKey = "";
  /** The comparison read once for the Diff summary and Changes, by its key.
   * @type {{key: string, read: Promise<unknown>} | null} */
  let comparisonRead = null;
  /** The paths that read says the comparison changes, by its key (`changedPaths`): what a
   * note's path-relative link to one of them opens, the stack's Changes at it.
   * @type {{key: string, paths: ReadonlySet<string>} | null} */
  let changedFiles = null;
  /** Each note's prose the guide drew (`loadDrawProse`), by the comparison it was drawn for,
   * which `relinkNotes` reads again; weak, so a note the guide lets go is not held here.
   * @type {WeakMap<Element, StackComparison>} */
  const noteProses = new WeakMap();
  let noteViewsOpen = !window.MetabrowserSourcePinGuard?.hasChanged();
  window.addEventListener?.(
    "metabrowser:pin-changed",
    () => {
      noteViewsOpen = false;
      relinkNotes();
    },
    { signal: listening.signal, once: true },
  );
  /** The Diff summary: the comparison it is drawn for, the claim of its latest draw, its
   * mount, its file count for the size line, and whether its last draw failed. */
  let summary = {
    key: "",
    claim: 0,
    handle: /** @type {{dispose: () => void} | null} */ (null),
    files: /** @type {number | null} */ (null),
    failed: false,
  };
  /** Whether the drawn comparison changes a document (`changesDocuments`), null while not
   * known, so Docs is offered as a pull request's page offers it. @type {boolean | null} */
  let docsChanged = null;
  let docsFor = "";
  /** The reader's File type choice in Changes, kept across tabs as a pull request's is.
   * @type {string[] | null} */
  let diffTypes = null;
  let resolveReady = () => {};
  /** @type {Promise<void>} */
  const ready = new Promise((resolve) => {
    resolveReady = () => resolve(undefined);
  });

  const take = h(
    "button",
    { type: "button", class: "github-pull-text-action github-pull-stack-take" },
    ["Show the new comparison"],
  );
  take.addEventListener("click", () => takeComparison(), { signal: listening.signal });
  const retry = statusLine.action("Retry");
  retry.addEventListener("click", () => retryStack(), { signal: listening.signal });
  /** The status line's numbered controls, as a pull request's (`numberHeaderControls`).
   * @type {Map<string, {handle: MetabrowserPublicPluginShortcutHandle, run: () => unknown}>} */
  const headerNumbers = new Map();
  // Each member's author, the stack menu's (`stackMemberIdentity`).
  const memberIdentity = stackMemberIdentity(mb);

  /** @param {number} member */
  function listed(member) {
    return listedState(knownSource, member);
  }

  function followCounterpart() {
    if (typeof mb.mountCounterpart === "function") {
      void mb.mountCounterpart(corner, window.location.pathname);
    }
  }

  /** @param {StackMemberLine[] | null} lines */
  function paintMembers(lines) {
    const key = JSON.stringify(lines);
    if (key === membersKey) {
      return;
    }
    membersKey = key;
    const drawn = (lines ?? []).map((line) => {
      let member = memberRows.get(line.number);
      if (member === undefined) {
        const anchor = link(
          { number: line.number, tab: "" },
          `/pull/${line.number}`,
          "menu-item",
          [],
        );
        // The stack menu's member row, its author drawn as the menu draws it.
        const row = stackMemberRow(anchor, mb.titleNodes, memberIdentity);
        member = { item: h("li", { class: "github-pull-stack-members-item" }, [anchor]), row };
        memberRows.set(line.number, member);
      }
      member.row.show(line);
      return member.item;
    });
    const kept = new Set((lines ?? []).map((line) => line.number));
    for (const number of [...memberRows.keys()]) {
      if (!kept.has(number)) {
        memberRows.delete(number);
      }
    }
    const shown = [...memberList.children];
    if (shown.length !== drawn.length || shown.some((item, at) => item !== drawn[at])) {
      memberList.replaceChildren(...drawn);
    }
  }

  /** @param {{head: string, base: string} | null} merge */
  function paintMerge(merge) {
    const key = JSON.stringify(merge);
    if (key === mergeKey) {
      return;
    }
    mergeKey = key;
    branchesRow.replaceChildren(
      ...(merge === null || typeof mb.mergeRefs !== "function"
        ? []
        : [
            mb.mergeRefs(
              { name: merge.head, ref: `refs/remotes/origin/${merge.head}` },
              { name: merge.base, ref: `refs/remotes/origin/${merge.base}` },
              { kind: "remote" },
            ),
          ]),
    );
  }

  /** Open or close the members, as the reader asked (`membersOpen`). */
  function showMembers() {
    membersToggle.setAttribute("aria-expanded", String(membersOpen));
    membersToggle.classList.toggle("collapsed", !membersOpen);
    membersToggle.classList.toggle("expanded", membersOpen);
    membersBody.classList.toggle("github-pull-stack-members-body-collapsed", !membersOpen);
  }

  /**
   * The row of ages: the tally's badges (`tallyBadge`), then when a member was last opened
   * and last updated, each in its freshness ink (`pullAge`), held a line tall while the
   * answer is on its way. Kept while the same, and their ages told again as time passes.
   *
   * @param {ReturnType<typeof stackHeader>} model
   */
  function paintOpened(model) {
    const key = JSON.stringify([model.tally, model.ages]);
    if (key === openedKey && agesNode !== null) {
      retellAges(mb, agesNode);
      return;
    }
    openedKey = key;
    tallySlot.replaceChildren(...model.tally.map(tallyBadge));
    const opened = model.ages?.opened ?? null;
    const updated = model.ages?.updated ?? null;
    /** @type {Array<Node | string>} */
    const ages = [];
    if (opened !== null) {
      ages.push("Last opened ", pullAge(mb, opened));
    }
    if (updated !== null) {
      ages.push(ages.length === 0 ? "Last update " : " · Last update ", pullAge(mb, updated));
    }
    agesNode =
      ages.length === 0
        ? h("div", { class: "github-pull-quiet" }, [" "])
        : agesLine([...(model.tally.length === 0 ? [] : ["· "]), ...ages]);
    place(openedRow, [...(model.tally.length === 0 ? [] : [tallySlot]), agesNode, openedStrut]);
  }

  /**
   * The author's row: its sentence (`actorSentence`), each actor kept while the same so its
   * avatar keeps its image, and the freshness note (`showNote`).
   *
   * @param {ReturnType<typeof stackHeader>} model
   */
  function paintMeta(model) {
    const sentence = model.sentence;
    const key = JSON.stringify(sentence);
    if (key !== metaKey) {
      metaKey = key;
      meta.details.hidden = sentence === null;
      /** @type {Map<string, HTMLElement>} */
      const kept = new Map();
      const nodes =
        sentence === null
          ? []
          : actorSentence(
              sentence.actors,
              (actor) => {
                const id = JSON.stringify([actor.login, actor.avatar]);
                const node = actorNodes.get(id) ?? sentenceActor(mb, actor);
                kept.set(id, node);
                return node;
              },
              actionText(sentence.action, sentence.actors.length > 0),
            );
      actorNodes = kept;
      place(meta.details, nodes);
    }
    showNote(meta, model.note, { sized: true, after: sentence !== null });
  }

  /**
   * The labels row's chips (`labelChip`), the members' labels each once.
   *
   * @param {ReturnType<typeof stackHeader>} model
   */
  function paintLabels(model) {
    const key = JSON.stringify(model.labels);
    if (key !== labelsKey) {
      labelsKey = key;
      labelList.replaceChildren(...(model.labels ?? []).map(labelChip));
    }
  }

  /**
   * The members toggle's words, a count summary's (docs/design-system.md, "Count Summaries
   * Bold Their Numbers"): "**12** Pulls". While no member is named the toggle holds its row,
   * out of sight and out of reach.
   *
   * @param {number | null} count
   */
  function paintMembersCount(count) {
    const key = String(count);
    if (key === countKey) {
      return;
    }
    countKey = key;
    membersToggle.classList.toggle("github-pull-stack-members-held", count === null);
    membersWords.replaceChildren(
      ...(count === null
        ? []
        : mb.countPartsNodes([
            { number: mb.formatInteger(count) },
            count === 1 ? " Pull" : " Pulls",
          ])),
    );
  }

  /**
   * The status line, a pull request's, from its parts (`statusLine`): a message muted, a
   * failure or a warning in the warning's ink, and at its end what it asks of the reader,
   * Retry first, then the offer of a new comparison, each numbered as a pull request's
   * status line's controls are (`numberHeaderControls`).
   *
   * @param {StackNotice[]} notices
   */
  function paintStatus(notices) {
    const key = JSON.stringify(notices);
    if (key === statusKey) {
      return;
    }
    statusKey = key;
    const said = notices.filter((notice) => notice.action !== "take");
    const offered = notices.find((notice) => notice.action === "take");
    /** @type {Map<string, {element: HTMLElement, run: () => unknown}>} */
    const numbered = new Map();
    const end = statusLine.end();
    if (notices.some((notice) => notice.action === "retry")) {
      numbered.set("remedy", { element: retry, run: retryStack });
      end.append(retry);
    }
    if (offered !== undefined) {
      numbered.set("take", { element: take, run: takeComparison });
      end.append(statusLine.offer([offered.text], take, listening.signal));
    }
    statusLine.failed(
      status,
      said.some((notice) => notice.severity !== null),
    );
    status.replaceChildren(
      ...said.map((notice) =>
        notice.severity === null
          ? statusLine.message(notice.text)
          : statusLine.failure(notice.text, listening.signal),
      ),
      ...(end.childNodes.length === 0 ? [] : [end]),
    );
    status.hidden = notices.length === 0;
    live.textContent = notices.map((notice) => notice.text).join(" ");
    numberHeaderControls(mb.shortcuts, headerNumbers, numbered, listening.signal);
  }

  /**
   * Hold the header and the tab bar out of sight for the quiet period until the stack's
   * answer, and show them at once with the paint that has it.
   *
   * @param {boolean} cold
   */
  function holdCold(cold) {
    if (coldHeld === null) {
      coldHeld = cold;
    } else if (coldHeld && !cold) {
      coldHeld = false;
    } else {
      return;
    }
    for (const part of [header, tabColumn]) {
      part.classList.toggle("github-pull-cold", coldHeld);
    }
  }

  function paintHeader() {
    const notices = statusNotices(envelope, shown, error, failed, interacted);
    const model = stackHeader(
      envelope,
      known,
      listed,
      notices,
      shown.drawn !== null,
      Date.now(),
      globalThis.navigator?.onLine === false,
    );
    holdCold(model.cold);
    paintOpened(model);
    paintMeta(model);
    paintMembers(model.members);
    paintMembersCount(model.members?.length ?? null);
    paintMerge(model.merge);
    paintLabels(model);
    paintStatus(model.status);
    paintSummaryWait(model.comparison);
    paintSize();
    /** @type {Record<string, HTMLElement>} */
    const rows = {
      title,
      corner,
      opened: openedRow,
      meta: meta.row,
      merge: branchesRow,
      labels: labelsRow,
      status,
      size: sizeRow,
      members: membersRow,
      summary: summaryRow,
    };
    // The status line stays in the header while hidden, as a pull request's does, where it
    // would be: after the labels, or the merge for a stack with none.
    const after = model.rows.indexOf(model.rows.includes("labels") ? "labels" : "merge") + 1;
    const names = model.rows.includes("status")
      ? model.rows
      : [...model.rows.slice(0, after), "status", ...model.rows.slice(after)];
    place(
      header,
      names.map((name) => rows[name]),
    );
    followCounterpart();
  }

  /**
   * The size line and the Diff summary's row while no summary is drawn: the shell's pending
   * placeholder while a comparison is on its way, as on a pull request's page, and empty
   * once a read of it failed or none is coming.
   *
   * @param {"pending" | "drawn" | "none"} comparison
   */
  function paintSummaryWait(comparison) {
    if (summary.handle !== null) {
      return;
    }
    const waits = comparison !== "none" && !summary.failed;
    delete sizeRow.dataset.sizeKey;
    if (waits) {
      if (summaryRow.firstChild !== summaryPending) {
        summaryRow.replaceChildren(summaryPending);
      }
      if (sizeRow.firstChild !== sizePending) {
        sizeRow.replaceChildren(sizePending);
      }
    } else {
      summaryRow.replaceChildren();
      sizeRow.replaceChildren();
    }
  }

  /**
   * The size line once the summary is drawn, a pull request's said of the comparison drawn
   * (`stackSizeInput`): "12 commits · 3 files changed · 6.5 KB compressed (30.4 KB raw
   * diff)", written only when it changes (`paintSizeLine`).
   */
  function paintSize() {
    if (
      summary.handle === null ||
      typeof mb.changeSizeLine !== "function" ||
      typeof mb.changeSizeLineNodes !== "function"
    ) {
      return;
    }
    paintSizeLine(mb, sizeRow, stackSizeInput(shown.answer, summary.files));
  }

  /**
   * The comparison's read, once per comparison, which the Diff summary and Changes share.
   *
   * @param {{prefetch: (comparison: unknown, signal: AbortSignal) => Promise<unknown>}} view
   * @param {StackComparison} comparison
   */
  function readComparison(view, comparison) {
    if (comparisonRead?.key !== comparison.key) {
      const read = Promise.resolve(view.prefetch(diffComparison(comparison), listening.signal));
      // A read that failed is not kept, so the next asks again. One that answered says what
      // the comparison changes, which the notes drawn before it read their links with again.
      read.then(
        (raw) => {
          const paths = changedPaths(raw);
          if (!listening.signal.aborted && comparisonRead?.read === read && paths !== null) {
            changedFiles = { key: comparison.key, paths };
            relinkNotes();
          }
        },
        () => {
          if (comparisonRead?.read === read) {
            comparisonRead = null;
          }
        },
      );
      comparisonRead = { key: comparison.key, read };
    }
    return comparisonRead.read;
  }

  /**
   * What a note of the guide drawn at *comparison* describes, for its links
   * (static/repository-links.js): the comparison's head, the commit the guide reads, and the
   * paths it changes once read, so a path-relative link to a changed file opens it in the
   * stack's Changes.
   *
   * @param {StackComparison} comparison
   * @returns {MetabrowserRepositoryTextContext}
   */
  function noteText(comparison) {
    return changedFiles !== null && changedFiles.key === comparison.key
      ? { head: comparison.right, changes: { number, stack: true, files: changedFiles.paths } }
      : { head: comparison.right };
  }

  /**
   * Make a note's links open what *text* says they open, in place for a pull request's or
   * this stack's page, and mark each outside link as a description's is.
   *
   * @param {Element} prose
   * @param {MetabrowserRepositoryTextContext} text
   */
  function linkNote(prose, text) {
    repositoryLinks?.enhance(prose, mb, {
      text,
      views: noteViewsOpen,
      open: (route) => {
        const opening = textRouteOpening(route);
        if (opening === null || listening.signal.aborted) {
          return false;
        }
        open(opening);
        return true;
      },
    });
    for (const anchor of prose.querySelectorAll("a[href]")) {
      mb.decorateExternalLink(/** @type {HTMLElement} */ (anchor), {});
    }
  }

  /**
   * Read the drawn notes' links again once the paths their comparison changes are read, so a
   * link to a changed file drawn before them becomes the stack's Changes in place, never at
   * its click: one pass for each read, over the notes the page shows.
   */
  function relinkNotes() {
    for (const prose of container.querySelectorAll(".kpress-prose")) {
      const drawnAt = noteProses.get(prose);
      if (drawnAt !== undefined && (!noteViewsOpen || drawnAt.key === changedFiles?.key)) {
        linkNote(prose, noteText(drawnAt));
      }
    }
  }

  /**
   * A read of *comparison* starts again, Changes's or a Retry's: a Diff summary whose last
   * draw failed is drawn again from it, as a pull request's page waits on its diff's read
   * (`summaryReading` in pull-page.js).
   *
   * @param {StackComparison} comparison
   */
  function summaryReading(comparison) {
    if (listening.signal.aborted || !summary.failed || summary.key !== comparison.key) {
      return;
    }
    summary = { ...summary, key: "", failed: false };
    paintSummaryWait("pending");
    void showSummary(comparison);
  }

  /**
   * Ask once per comparison whether it changes a document, through the diff view's
   * `typeCounts`, so Docs is offered as a pull request's page offers it.
   *
   * @param {MetabrowserPublicViewSpec} view
   * @param {StackComparison} comparison
   */
  function askDocs(view, comparison) {
    if (docsFor === comparison.key || typeof view.typeCounts !== "function") {
      return;
    }
    docsFor = comparison.key;
    docsChanged = null;
    void Promise.resolve(view.typeCounts(diffComparison(comparison), listening.signal)).then(
      (counts) => {
        if (!listening.signal.aborted && docsFor === comparison.key) {
          docsChanged = changesDocuments(counts);
          paintTabs();
        }
      },
      // A count that did not come leaves Docs shown, as before it was asked.
      () => {},
    );
  }

  /**
   * Draw the header's Diff summary for the comparison the body shows, once per comparison:
   * out of sight, then in the row's place in one step, so it moves nothing; a newer
   * comparison's replaces it the same way. One that draws nothing empties the row.
   *
   * @param {StackComparison} comparison
   */
  async function showSummary(comparison) {
    if (listening.signal.aborted || summary.key === comparison.key) {
      return;
    }
    const claim = summary.claim + 1;
    summary = { ...summary, key: comparison.key, claim, failed: false };
    const owns = () => !listening.signal.aborted && summary.claim === claim;
    const unavailable = () => {
      if (owns()) {
        summary.handle?.dispose();
        summary = { ...summary, handle: null, files: null, failed: true };
        paintSummaryWait("none");
      }
    };
    try {
      await mb.ensureKindAssets("diff");
      const view = /** @type {any} */ (mb.getRegisteredView("diff", "diff"));
      if (!owns()) {
        return;
      }
      if (typeof view?.summary !== "function" || typeof view?.prefetch !== "function") {
        unavailable();
        return;
      }
      askDocs(view, comparison);
      const raw = await readComparison(view, comparison);
      if (!owns()) {
        return;
      }
      const stage = h("div", {});
      // The comparison read, and where a file the summary opens goes, as a pull request's
      // page passes them, so the summary starts collapsed, as every Diff summary does.
      const mounted = await view.summary(stage, {
        raw,
        openFile: (/** @type {string} */ path) =>
          open({ number, tab: "changes", file: path, stack: true }),
      });
      if (!owns()) {
        mounted?.dispose();
        return;
      }
      if (mounted === null) {
        unavailable();
        return;
      }
      summary.handle?.dispose();
      summary = { ...summary, handle: mounted, files: manifestFiles(raw) };
      summaryRow.replaceChildren(...stage.childNodes);
      paintSize();
    } catch {
      unavailable();
    }
  }

  const tabLinks = STACK_TABS.map(({ id, label }) => {
    const anchor = link({ number, tab: id, stack: true }, `/stack/${number}/${id}`, "tab-btn", [
      label,
    ]);
    anchor.setAttribute("role", "tab");
    tabBar.append(anchor);
    return { id, anchor };
  });
  // The tab keys a pull request's page gives its own tabs: Guided Review's R, Docs's D, and
  // Changes's G, Changes being the pull request's `files` tab.
  attachTabKeys(
    mb.shortcuts,
    tabLinks.map(({ id, anchor }) => ({ id: id === "changes" ? "files" : id, link: anchor })),
    (id) => {
      // A hidden tab's key does nothing, as its link offers nothing; the shell lands the
      // page on the tab, as a press of its link does.
      const next = id === "files" ? "changes" : id;
      if (!tabLinks.some((entry) => entry.id === next && entry.anchor.hidden)) {
        open({ number, tab: next, stack: true });
      }
    },
    listening.signal,
    "stack",
  );

  function paintTabs() {
    for (const { id, anchor } of tabLinks) {
      anchor.hidden =
        (id === "guided" && guide === null) ||
        (id === "docs" && docsChanged === false && tab !== "docs");
      anchor.classList.toggle("active", tab === id);
      anchor.setAttribute("aria-selected", String(tab === id));
    }
  }

  /**
   * A notice in the body, for a stack with no comparison drawn, with its Retry.
   *
   * @param {string} text
   * @param {boolean} retries
   */
  function noticeNode(text, retries) {
    const node = h(
      "div",
      retries
        ? { class: "notice github-pull-notice", "data-severity": "warning", role: "status" }
        : { class: "notice github-pull-notice" },
      [text],
    );
    if (retries) {
      const again = h("button", { type: "button", class: "btn" }, ["Retry"]);
      again.addEventListener("click", () => retryStack(), { signal: listening.signal });
      node.append(" ", again);
    }
    return node;
  }

  function takeComparison() {
    shown = bodyTaken(shown, envelope);
    paintHeader();
    void paintBody();
  }

  // What the reader does on the page: a wheel, a finger, a click, or a scrollbar in the pane
  // that scrolls it, and a key on the page (`readerKey`), as a pull request's page tells the
  // reader's own scroll from the browser's; opening a tab or a file is the reader's too
  // (`setTab`, `showFile`). From then on a new comparison that looks different is offered,
  // not drawn (`answerAction`).
  const pane = /** @type {HTMLElement} */ (
    container.closest("[data-kpress-viewport]") ?? container
  );
  const interact = () => {
    interacted = true;
  };
  for (const type of ["wheel", "touchstart", "pointerdown"]) {
    pane.addEventListener(type, interact, {
      capture: true,
      passive: true,
      signal: listening.signal,
    });
  }
  document.addEventListener(
    "keydown",
    (event) => {
      if (readerKey(event, container, document)) {
        interacted = true;
      }
    },
    { capture: true, signal: listening.signal },
  );

  /** Retry: the stack read again, and a Diff summary whose draw failed drawn again. */
  function retryStack() {
    if (shown.drawn !== null) {
      summaryReading(shown.drawn);
    }
    void controller.retry();
  }

  function disposeBody() {
    handle?.dispose?.();
    handle = null;
    guidedView = null;
  }

  /**
   * The stack's guide (guided-review.js): its steps, read against *comparison*, the one this
   * page drew (`guided-review?stack=` with its commits and key), so the guide shows what
   * the Diff summary, Docs, and Changes show, and follows the reader to a new comparison only
   * when they take it. A file a step cites opens in this page's Changes, and another pull
   * request, or a file of it, in that pull request's page. A file the rendered route renders
   * is drawn whole from *comparison* while that is the one the step was read at, or, a file
   * of another pull request, from that one's. A note's links are absolute against the page
   * of the member that carries the guide, and marked as a description's are.
   *
   * @param {StackComparison} comparison
   * @param {() => boolean} owns Whether the body still shows what this was drawn for.
   * @returns {Promise<ReturnType<import("./guided-review.js").mountGuidedReview> | null>} The
   *   guide's view, which the caller tells the guide's revision, or null when the body moved on.
   */
  async function paintGuided(comparison, owns) {
    /** @type {import("./guided-review.js").GuideSubject} */
    const subject = {
      kind: "stack",
      number,
      at: { left: comparison.left, right: comparison.right, key: comparison.key },
    };
    // The guide's first step is asked for now, beside the module's import, rather than
    // after it; the guide reads the same request (guide-reads.js). A stack's guide is shown
    // with no head moved past its record (`show`'s *moved*), since the stack's comparison
    // says what moved, so it is read ahead the same way.
    const readAt = guideReadAt();
    if (readAt !== null) {
      guideReads.prefetch(guideAsks(subject), 1, readAt, false);
    }
    const host = h(
      "section",
      { class: "github-pull-guided-review", "aria-label": "Guided Review" },
      [
        h(
          "div",
          { class: "mb-delayed-loading", role: "status", "aria-label": "Loading the guide" },
          [h("div", { class: "recent-loading github-pull-loading", "aria-hidden": "true" })],
        ),
      ],
    );
    body.replaceChildren(host);
    const { mountGuidedReview } = await import("./guided-review.js");
    if (!owns()) {
      return null;
    }
    // The allowlist a note passes through, and what its links open (static/repository-links.js),
    // without which they stay github.com links; a page with no repository identity asks for
    // no resolver, which it would answer with none. A note is drawn once both have answered.
    inertReady ??= Promise.all([
      mb.ensureAsset("inert-html").then(() => window.MetabrowserInertHtml ?? null),
      mb.repository ? mb.loadRepositoryLinks() : null,
    ]).then(
      ([inert, links]) => {
        repositoryLinks = links;
        return inert;
      },
      () => null,
    );
    const prose = inertReady;
    const view = mountGuidedReview(host, null, subject, {
      open: (path) => open({ number, tab: "changes", file: path, stack: true }),
      openPull: (target, path) =>
        open(
          path === null
            ? { number: target, tab: "" }
            : { number: target, tab: "files", file: path },
        ),
      // A pull request's page's age, in its freshness ink.
      age: (iso) => pullAge(mb, iso),
      shortCommit: (sha) => mb.shortCommit(sha),
      // A cited pull request's title and author, as a stack menu's member draws them, and
      // the Layers glyph that names a stack other than the guide's.
      titleNodes: mb.titleNodes,
      stackGlyph: () => (layers === null ? null : document.importNode(layers, true)),
      identity: (login, avatar) =>
        authorLabel(mb, login, avatar, "github-pull-stack-member-author", {
          placeholder: false,
        }),
      loadStyles: (assets) =>
        Promise.all([
          mb.loadKpressAssets(
            /** @type {Parameters<MetabrowserPublicSdk["loadKpressAssets"]>[0]} */ (assets),
          ),
          mb.ensureKindAssets("diff"),
        ]),
      loadDrawPatch: async () => {
        const diff = await mb.plugins.load("diff");
        return diff.guidePatchDrawer();
      },
      loadDrawDocument: async () => {
        const diff = await mb.plugins.load("diff");
        /**
         * @param {{merge_base: string | null, head: string, route?: string,
         *   image_route?: string, rendered_route?: string}} pins
         */
        const at = (pins) =>
          citedPullComparison(pins) ??
          (comparison.left === pins.merge_base && comparison.right === pins.head
            ? diffComparison(comparison)
            : null);
        return {
          draws: (pins) => at(pins) !== null,
          source(path, pins) {
            const shown = at(pins);
            return shown === null
              ? null
              : {
                  path,
                  load: (signal) => diff.loadFullSource(shown, path, signal),
                };
          },
          mount(body, path, format, pins) {
            const shown = at(pins);
            if (shown === null) {
              return { settled: Promise.resolve(false), dispose() {} };
            }
            return diff.mountRenderedFile(body, shown, path, {
              ...(format === "markdown" ? DOCS_DRAWING : CHANGES_DRAWING),
              // Rendered waits with Source hidden for as long as the rendered route can
              // take; a document not drawn by then shows Source and keeps it, so the step
              // never moves.
              markdownHoldMs: GUIDE_DOCUMENT_HOLD_MS,
            });
          },
        };
      },
      loadDrawProse: async () => {
        const inert = await prose;
        if (inert === null) {
          throw new Error("the inert HTML allowlist did not load");
        }
        // A note's links were made absolute against the member that carries the guide,
        // whose page the step names. A link into the repository opens its page here, and a
        // path-relative reference names the stack's head's file, the commit the guide reads:
        // in the stack's Changes when the comparison changes it (`noteText`), and on
        // github.com otherwise (static/repository-links.js); an outside link is marked as a
        // description's is.
        return (html, base) => {
          const prose = inert.kpressProse(
            inert.sanitizeHtml(html, base ?? envelope?.github_url ?? "https://github.com/", true),
            document,
          );
          noteProses.set(prose, comparison);
          linkNote(prose, noteText(comparison));
          return prose;
        };
      },
      refusalNote: textRefusalNote,
      // The comparison drawn has moved, and may be gone: the stack is read now, so the
      // page draws its own comparison in its place or offers it (`answerAction`).
      moved: () => void controller.start(),
      // A step's neighbors are read when the page is idle, after what it shows.
      ahead: (run) => mb.whenIdle(run, { timeout: PREFETCH_IDLE_TIMEOUT_MS }),
    });
    return view;
  }

  /**
   * The revision of the guide that Guided Review reads at the comparison drawn, or null when
   * it reads none there: once the stack has moved past that comparison (`drawnCurrent`), only
   * the guide read there before (`behind` in guided-review.js, as `paintBody` tells it).
   *
   * @returns {string | null}
   */
  function guideReadAt() {
    if (guide === null) {
      return null;
    }
    if (drawnCurrent(shown, envelope) !== false) {
      return guide.revision;
    }
    return guideRead === null || guideRead === guide.revision ? guide.revision : null;
  }

  /** The comparison and guide revision read ahead, so each is read once (`readGuideAhead`). */
  let guideAhead = "";
  /** @type {(() => void) | null} */
  let cancelGuideAhead = null;

  /**
   * Read the guide ahead of the reader: while Docs or Changes shows a comparison and the
   * stack has a guide, its module and its first step at that comparison, when the page is
   * idle, so Guided Review draws whole the moment it is opened (guide-reads.js has the cost).
   * Guided Review's own tab reads its first step as it starts to import the module
   * (`paintGuided`).
   */
  function readGuideAhead() {
    const drawn = shown.drawn;
    const revision = drawn === null ? null : guideReadAt();
    if (tab === "guided" || drawn === null || revision === null) {
      return;
    }
    const key = JSON.stringify([drawn.key, revision]);
    if (guideAhead === key) {
      return;
    }
    guideAhead = key;
    cancelGuideAhead?.();
    /** @type {import("./guided-review.js").GuideSubject} */
    const subject = {
      kind: "stack",
      number,
      at: { left: drawn.left, right: drawn.right, key: drawn.key },
    };
    cancelGuideAhead = mb.whenIdle(
      () => {
        cancelGuideAhead = null;
        if (listening.signal.aborted) {
          return;
        }
        guideReads.prefetch(guideAsks(subject), 1, revision, false);
        void import("./guided-review.js").catch(() => {});
      },
      { timeout: PREFETCH_IDLE_TIMEOUT_MS },
    );
  }

  /**
   * Docs or Changes, drawn as a pull request's page draws its own (`mountDiff` in
   * pull-page.js) and held as it holds them (`holdDiff`): out of sight from its first draw
   * until its first screen's Markdown waits no more, with the shell's delayed loading block
   * below it, so the first screen the reader sees is the one that stays. Changes's read is
   * the Diff summary's, which a summary whose draw failed is drawn again from.
   *
   * @param {"docs" | "changes"} which
   * @param {StackComparison} comparison
   * @param {() => boolean} owns
   * @param {(mounted: {dispose?: () => void, scrollToFile?: (path: string) => unknown} | null) => void} adopt
   */
  async function paintDiff(which, comparison, owns, adopt) {
    const held = holdDiff(body);
    const { host, loading } = held;
    const docs = which === "docs";
    /** A view the diff drew and the page has not adopted yet, which a failure disposes.
     * @type {{dispose?: () => void} | null} */
    let unadopted = null;
    if (!docs) {
      summaryReading(comparison);
    }
    try {
      await mb.ensureKindAssets("diff");
      const view = /** @type {any} */ (mb.getRegisteredView("diff", "diff"));
      if (!owns()) {
        return;
      }
      if (!view) {
        loading.remove();
        host.textContent = "Changes could not be shown. Reload the page to try again.";
        return;
      }
      const raw =
        docs || typeof view.prefetch !== "function"
          ? undefined
          : await readComparison(view, comparison).catch(() => undefined);
      if (!owns()) {
        return;
      }
      held.hold();
      let emptied = false;
      const mounted = await view.render(
        host,
        diffDrawing(which, comparison, {
          signal: listening.signal,
          ...(raw === undefined ? {} : { raw }),
          ...(docs
            ? {
                onDocument: (/** @type {unknown} */ document_) => {
                  emptied = noFiles(document_);
                },
              }
            : {
                types: diffTypes,
                onTypes: (/** @type {string[] | null} */ types) => {
                  diffTypes = types;
                },
              }),
        }),
      );
      if (!owns()) {
        loading.remove();
        mounted?.dispose?.();
        return;
      }
      unadopted = mounted;
      if (emptied) {
        host
          .querySelector(".diff-type-empty")
          ?.append(
            " ",
            link({ number, tab: "changes", stack: true }, `/stack/${number}/changes`, "", [
              "Show every change",
            ]),
          );
      }
      // Landed before the wait, so the first screen the Markdown layer reports is the one
      // the reader lands on: a file the address names, not the top of the diff.
      adopt(mounted);
      unadopted = null;
      await held.firstScreen(mounted);
      if (owns()) {
        held.release();
      } else {
        loading.remove();
      }
    } catch (failure) {
      unadopted?.dispose?.();
      if (owns()) {
        console.error("metabrowser github: the stack's diff could not load", failure);
        held.release();
        // A pull request's error notice and its Retry, in its words (`mountDiff` in
        // pull-page.js), not a bare sentence in the diff's host. Retry disposes what the
        // failed draw adopted before it draws again, as `paintBody` does before every draw.
        const retry = h("button", { type: "button", class: "btn" }, ["Retry"]);
        retry.addEventListener(
          "click",
          () => {
            if (owns()) {
              disposeBody();
              void paintDiff(which, comparison, owns, adopt);
            }
          },
          { signal: listening.signal },
        );
        host.replaceChildren(
          h("div", { class: "notice github-pull-notice", "data-severity": "error" }, [
            docs ? "Docs could not load. " : "Changes could not load. ",
            retry,
          ]),
        );
      }
    }
  }

  async function paintBody() {
    const plan = bodyPlan(shown, envelope, tab, failed);
    shown = plan.body;
    const action = plan.action;
    body.classList.toggle("page-reading-column", bodyInColumn(shown, tab));
    readGuideAhead();
    if (shown.drawn !== null) {
      void showSummary(shown.drawn);
    }
    if (action.do === "keep") {
      // An edit of the description that carries the guide is read again while the
      // comparison drawn is the stack's current one, or looks the same (`drawnCurrent`). A
      // new comparison is offered, not swapped in: until the reader takes it, the guide
      // stays as it was read at the drawn one, as Docs and Changes stay, and a guide its
      // carrier's move changed is not read there (`behind` in guided-review.js).
      const current = drawnCurrent(shown, envelope);
      if (current === true) {
        guidedView?.behind(null);
        if (guide !== null) {
          guideRead = guide.revision;
          guidedView?.show(guide.revision, false);
        }
      } else if (current === false) {
        guidedView?.behind(guideRead);
      }
      return;
    }
    if (action.do === "wait") {
      return;
    }
    if (action.do === "scroll") {
      handle?.scrollToFile?.(action.file);
      return;
    }
    if (action.do === "notice") {
      disposeBody();
      body.replaceChildren(noticeNode(action.text, action.retry));
      return;
    }
    const key = action.key;
    disposeBody();
    const owns = () => !listening.signal.aborted && shown.shown === key;
    /** @param {{dispose?: () => void, scrollToFile?: (path: string) => unknown} | null} mounted */
    const adopt = (mounted) => {
      if (!owns()) {
        mounted?.dispose?.();
        return;
      }
      handle = mounted;
      const done = bodyMounted(shown, key);
      shown = done.body;
      if (done.scroll !== null) {
        handle?.scrollToFile?.(done.scroll);
      }
    };
    if (action.tab === "guided") {
      const carried = guide;
      if (carried === null) {
        return;
      }
      try {
        const view = await paintGuided(action.comparison, owns);
        adopt(view);
        if (view !== null && handle === view) {
          guidedView = view;
          // An answer that came while the guide was imported may name a newer revision,
          // which the keep path could not tell a view not yet mounted.
          const revision = (guide ?? carried).revision;
          if (drawnCurrent(shown, envelope) === false) {
            // Back on the tab while the stack has moved past the comparison drawn: the guide
            // is read there only if it is the one read there before.
            view.behind(guideRead ?? revision);
          } else {
            guideRead = revision;
          }
          view.show(revision, false);
        }
      } catch (failure) {
        if (owns()) {
          console.error("metabrowser github: the stack's guide could not load", failure);
          body.replaceChildren(
            h("p", { class: "github-pull-quiet", role: "status" }, [
              "Could not load Guided Review.",
            ]),
          );
        }
      }
      return;
    }
    await paintDiff(action.tab, action.comparison, owns, adopt);
  }

  const controller = createStackController(
    {
      async request(method, route, options) {
        /** @type {Record<string, string>} */
        const headers = {};
        if (method === "GET" && options.etag) {
          headers["if-none-match"] = options.etag;
        }
        if (method === "POST") {
          headers["content-type"] = "application/json";
        }
        const response = await fetch(route, {
          method,
          headers,
          cache: "no-store",
          body: method === "POST" ? JSON.stringify(options.body ?? {}) : undefined,
          signal: listening.signal,
        });
        let decoded = null;
        if (response.status !== 304) {
          try {
            decoded = await response.json();
          } catch {
            decoded = null;
          }
        }
        return { status: response.status, etag: response.headers.get("etag"), body: decoded };
      },
      schedule: (callback, delayMs) => window.setTimeout(callback, delayMs),
      cancel: (timer) => window.clearTimeout(/** @type {number} */ (timer)),
      now: () => Date.now(),
      isVisible: () => document.visibilityState === "visible",
      since: () => shown.drawn?.key ?? null,
      render(model) {
        envelope = model.envelope;
        error = model.error;
        failed = model.failed;
        shown = bodyAnswered(shown, envelope, interacted, failed);
        guide = guideShown(guide, envelope);
        tab = shownTab(routeTab, envelope, guide);
        paintHeader();
        paintTabs();
        void paintBody();
        resolveReady();
      },
    },
    { number },
  );
  // The stack as the Pulls tab knows it, which the first paint lists its members from; told
  // synchronously, so the first paint below has it.
  const stacks = watchStacks((index) => {
    known = knownStack(index, number);
    knownSource = index.source;
    if (!listening.signal.aborted) {
      paintHeader();
    }
  });
  paintHeader();
  paintTabs();
  void controller.start().finally(resolveReady);
  const onVisible = () => {
    if (document.visibilityState === "visible") {
      void controller.start();
    }
  };
  document.addEventListener("visibilitychange", onVisible, { signal: listening.signal });
  // The browser's network came or went: the freshness note says "Offline" while a member's
  // record is behind and none can be refreshed, as a pull request's page does. The
  // browserless sessions' window has no event target; a browser's always does.
  for (const type of ["online", "offline"]) {
    window.addEventListener?.(
      type,
      () => {
        if (!listening.signal.aborted) {
          paintHeader();
        }
      },
      { signal: listening.signal },
    );
  }

  /** @param {string} next */
  function setTab(next) {
    routeTab = next;
    const before = tab;
    tab = shownTab(next, envelope, guide);
    // Another tab is the reader's: the shell lands the page on its own route's too.
    interacted ||= tab !== before && before !== "";
    shown = bodyOpened(shown, "");
    paintTabs();
    void paintBody();
  }

  /** @param {string} path */
  function showFile(path) {
    interacted = true;
    routeTab = "changes";
    tab = "changes";
    shown = bodyOpened(shown, path);
    paintTabs();
    void paintBody();
  }

  function stop() {
    listening.abort();
    cancelGuideAhead?.();
    cancelGuideAhead = null;
    controller.dispose();
    stacks.dispose();
  }

  return {
    ready,
    setTab,
    /** @param {{tab: string, file?: string}} route */
    land(route) {
      if (route.file) {
        showFile(route.file);
      } else {
        setTab(route.tab);
      }
    },
    showFile,
    flush() {},
    cancelPending: stop,
    dispose() {
      stop();
      disposeBody();
      summary.handle?.dispose();
    },
  };
}

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
// A comparison drawn stays drawn while the stack moves: one that changes is offered, not
// swapped in, and while a new member is fetched or the stack cannot be shown, the drawn
// one stays under the status line, since the server keeps answering a pair it gave
// (pull_stack_retained.py). `bodyPlan` decides what the body does with each answer, and a
// file is scrolled to once, when the reader opens it, never again by a later answer.
// Guided Review stays with it (`guideShown`): the guide is read again when the reader takes
// the comparison offered, or when the description that carries it changes.
//
// tests/dom/github-stack-page-session.js runs the pure parts and the controller here from
// the command line.

import { CHANGES_DRAWING, citedPullComparison, DOCS_DRAWING, DOCS_GROUP } from "./diff-drawing.js";
import {
  attachTabKeys,
  authorLabel,
  CHANGES_FIRST_SCREEN_MS,
  changesDocuments,
  FAST_POLL_MS,
  h,
  holdDiff,
  isPlainClick,
  manifestFiles,
  noFiles,
  numberHeaderControls,
  pageHeaderParts,
  pullAge,
  SLOW_POLL_MS,
  stackMemberAuthor,
  stackMemberIdentity,
  statusLine,
  summaryPlaceholders,
  textRefusalNote,
  titleHeading,
} from "./pull-page.js";
import { stackLabel, stackMenuOrder, stackPosition, watchStacks } from "./pull-stacks.js";
import { listedState } from "./pull-state.js";
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
 *   comparison: StackComparison | null,
 *   totals: {files: number, additions: number | null, deletions: number | null, exact: boolean} | null,
 *   truncated: boolean,
 *   files: StackFile[],
 *   guide: {number: number, revision: string} | null,
 *   github_url: string | null,
 *   probe: {number: number, held: string | null, every_s: number} | null,
 * }} StackEnvelope
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
 * What a new answer does to the comparison the page shows: `wait` while there is none to
 * show, `show` the first, `keep` the same, and `offer` another, which the reader takes.
 *
 * @param {string | null} shownKey The key of the comparison shown, or null.
 * @param {StackEnvelope | null} envelope
 * @returns {"wait" | "show" | "keep" | "offer"}
 */
export function comparisonAction(shownKey, envelope) {
  const next = envelope?.state === "current" ? (envelope.comparison?.key ?? null) : null;
  if (next === null) {
    return shownKey === null ? "wait" : "keep";
  }
  if (shownKey === null) {
    return "show";
  }
  return next === shownKey ? "keep" : "offer";
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
  const all = numbers.map((number) => `#${number}`);
  return all.length === 1
    ? all[0]
    : `${all.slice(0, -1).join(", ")}${all.length > 2 ? "," : ""} and ${all.at(-1)}`;
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
 * the stack since the drawn comparison, the members its top lacks, and its members'
 * fetches. With nothing drawn, the body says why itself (`bodyPlan`).
 *
 * @param {StackEnvelope | null} envelope
 * @param {string | null} drawnKey The key of the comparison drawn, or null.
 * @param {string | null} error
 * @param {number[]} failed The members whose fetch ended without a usable record.
 * @returns {StackNotice[]}
 */
export function statusNotices(envelope, drawnKey, error, failed) {
  /** @type {StackNotice[]} */
  const notices = [];
  if (error !== null) {
    // A failed read keeps the last answer drawn, so it is a warning; with none, an error.
    notices.push({ text: error, severity: envelope === null ? "error" : "warning", action: null });
  }
  if (envelope === null || drawnKey === null) {
    return notices;
  }
  if (comparisonAction(drawnKey, envelope) === "offer") {
    notices.push({
      text: "This stack has changed since its comparison was drawn.",
      severity: null,
      action: "take",
    });
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
    envelope.state === "pending" ? waiting : [],
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
 * What the body shows and has shown: the comparison drawn, the key of what is mounted
 * ("" for nothing or a notice), whether that mount has finished, and a file to scroll to
 * once, which the reader's opening a file sets and the scroll clears.
 *
 * @typedef {{drawn: StackComparison | null, shown: string, ready: boolean, jump: string | null}} StackBody
 */

/** The body before any answer. @type {StackBody} */
export const NO_BODY = Object.freeze({ drawn: null, shown: "", ready: false, jump: null });

/**
 * The body after a new answer: its first comparison is drawn; any later one waits for the
 * reader to take it, and the drawn one stays while the stack is pending or absent.
 *
 * @param {StackBody} body
 * @param {StackEnvelope | null} envelope
 * @returns {StackBody}
 */
export function bodyAnswered(body, envelope) {
  return comparisonAction(body.drawn?.key ?? null, envelope) === "show"
    ? { ...body, drawn: envelope?.comparison ?? null }
    : body;
}

/**
 * The body after the reader takes the comparison offered.
 *
 * @param {StackBody} body
 * @param {StackEnvelope | null} envelope
 * @returns {StackBody}
 */
export function bodyTaken(body, envelope) {
  return comparisonAction(body.drawn?.key ?? null, envelope) === "offer"
    ? { ...body, drawn: envelope?.comparison ?? null }
    : body;
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
 * mounts again when the reader takes another), `scroll` to a file the reader opened once the mount is ready, and otherwise
 * `keep`, so an answer that changes nothing the body shows leaves the reader where they
 * are.
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
 *   render(model: {envelope: StackEnvelope | null, error: string | null, failed: number[]}): void,
 * }} StackDependencies
 */

/**
 * The poll and the asks of one stack's page. It reads the stack route while the page is in
 * sight, one read at a time, asks for each pending member and again for one refused, sends
 * the top member's automatic ask at its interval, and renders each answer that changed and
 * each change in which members it could not fetch.
 *
 * @param {StackDependencies} deps
 * @param {{number: number}} options
 */
export function createStackController(deps, options) {
  const route = `${STACK_ROUTE}?number=${options.number}`;
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
 * The header a paint draws, row by row, a pull request's page's header made of the parts a
 * stack has (docs/design-system.md, "Stacks", "The Stack Page"): its title, the View on
 * GitHub corner, the members, the merge the stack makes, the status line, the size line,
 * and the Diff summary. *rows* names them in order; `members` and `merge` are what those
 * rows hold, `status` the status line's notices, there only while it has something to say,
 * and `comparison` whether the size line and the Diff summary hold the comparison's
 * pending placeholder (`pending`), their lines (`drawn`), or are not there (`none`), for a
 * stack that cannot be shown as one comparison and has none drawn.
 *
 * Every row but the status line is decided at first paint, from what the Pulls tab knows of
 * the stack: the members, and the merge's row held a line tall until the answer names the
 * top member's head. So the answer lands moving nothing under the title, as a pull request's
 * record does. With neither the answer nor the Pulls tab naming a member, the page is
 * `cold`, held out of sight for the quiet period as a pull request's page with no record in
 * hand is (`.github-pull-cold`).
 *
 * @param {StackEnvelope | null} envelope
 * @param {NativeStack | null} known
 * @param {(number: number) => ListedPull} listed
 * @param {StackNotice[]} status
 * @param {boolean} drawn Whether a comparison is drawn.
 */
export function stackHeader(envelope, known, listed, status, drawn) {
  const members = memberLines(envelope, known, listed);
  const base = envelope?.base_ref ?? known?.base_ref ?? null;
  const head = envelope?.head_ref ?? null;
  /** @type {"pending" | "drawn" | "none"} */
  const comparison = drawn
    ? "drawn"
    : envelope === null || envelope.state !== "absent"
      ? "pending"
      : "none";
  return {
    cold: envelope === null && members === null,
    rows: [
      "title",
      "corner",
      ...(members === null ? [] : ["members"]),
      "merge",
      ...(status.length === 0 ? [] : ["status"]),
      ...(comparison === "none" ? [] : ["size", "summary"]),
    ],
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
    branches: branchesRow,
    status,
    size: sizeRow,
    summary: summaryRow,
  } = pageHeaderParts();
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
  // it does under a pull request's stack button, in a page card, as every card on a pull
  // request's page is. No member is this page, so none is marked.
  const memberList = h("ol", {
    class: "github-pull-stack-members page-card",
    "aria-label": `Pull requests in ${stackLabel(number)}`,
  });
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
  let statusKey = "";
  /** The comparison read once for the Diff summary and Changes, by its key.
   * @type {{key: string, read: Promise<unknown>} | null} */
  let comparisonRead = null;
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
   * Hold the header and the tab bar out of sight for the quiet period while nothing names a
   * member, and show them at once with the first paint that does, or with the answer.
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
    const notices = statusNotices(envelope, shown.drawn?.key ?? null, error, failed);
    const model = stackHeader(envelope, known, listed, notices, shown.drawn !== null);
    holdCold(model.cold);
    paintMembers(model.members);
    paintMerge(model.merge);
    paintStatus(model.status);
    paintSummaryWait(model.comparison);
    /** @type {Record<string, HTMLElement>} */
    const rows = {
      title,
      corner,
      members: memberList,
      merge: branchesRow,
      status,
      size: sizeRow,
      summary: summaryRow,
    };
    // The status line stays in the header while hidden, as a pull request's does.
    const names = model.rows.includes("status")
      ? model.rows
      : model.rows.flatMap((name) => (name === "merge" ? [name, "status"] : [name]));
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

  /** The size line once the summary is drawn: its file count, "3 files changed". */
  function paintSize() {
    if (
      summary.handle === null ||
      typeof mb.changeSizeLine !== "function" ||
      typeof mb.changeSizeLineNodes !== "function"
    ) {
      return;
    }
    sizeRow.replaceChildren(...mb.changeSizeLineNodes(mb.changeSizeLine({ files: summary.files })));
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
      // A read that failed is not kept, so the next asks again.
      read.catch(() => {
        if (comparisonRead?.read === read) {
          comparisonRead = null;
        }
      });
      comparisonRead = { key: comparison.key, read };
    }
    return comparisonRead.read;
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
    inertReady ??= mb
      .ensureAsset("inert-html")
      .then(() => window.MetabrowserInertHtml ?? null)
      .catch(() => null);
    const prose = inertReady;
    const view = mountGuidedReview(
      host,
      null,
      {
        kind: "stack",
        number,
        at: { left: comparison.left, right: comparison.right, key: comparison.key },
      },
      {
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
          return (body, change, patch) => diff.mountFilePatch(body, change, patch, mb);
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
            mount(body, path, format, pins) {
              const shown = at(pins);
              if (shown === null) {
                return { settled: Promise.resolve(false), dispose() {} };
              }
              return diff.mountRenderedFile(body, shown, path, {
                ...(format === "markdown" ? DOCS_DRAWING : CHANGES_DRAWING),
                markdownHoldMs: CHANGES_FIRST_SCREEN_MS,
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
          // whose page the step names; an outside link is marked as a description's is.
          return (html, base) => {
            const prose = inert.kpressProse(
              inert.sanitizeHtml(html, base ?? envelope?.github_url ?? "https://github.com/"),
              document,
            );
            for (const anchor of prose.querySelectorAll("a[href]")) {
              mb.decorateExternalLink(/** @type {HTMLElement} */ (anchor), {});
            }
            return prose;
          };
        },
        refusalNote: textRefusalNote,
      },
    );
    return view;
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
    if (shown.drawn !== null) {
      void showSummary(shown.drawn);
    }
    if (action.do === "keep") {
      // An edit of the description that carries the guide is read again while the
      // comparison drawn is the stack's current one. A new comparison is offered, not
      // swapped in: until the reader takes it, the guide stays as it was read at the drawn
      // one, as Docs and Changes stay, and a guide its carrier's move changed is not read
      // there (`behind` in guided-review.js).
      const current = envelope?.state === "current" ? (envelope.comparison?.key ?? null) : null;
      if (current !== null && current === shown.drawn?.key) {
        guidedView?.behind(null);
        if (guide !== null) {
          guideRead = guide.revision;
          guidedView?.show(guide.revision, false);
        }
      } else if (current !== null) {
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
          const current = envelope?.state === "current" ? (envelope.comparison?.key ?? null) : null;
          if (current !== null && current !== action.comparison.key) {
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
      render(model) {
        envelope = model.envelope;
        error = model.error;
        failed = model.failed;
        shown = bodyAnswered(shown, envelope);
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

  /** @param {string} next */
  function setTab(next) {
    routeTab = next;
    tab = shownTab(next, envelope, guide);
    shown = bodyOpened(shown, "");
    paintTabs();
    void paintBody();
  }

  /** @param {string} path */
  function showFile(path) {
    routeTab = "changes";
    tab = "changes";
    shown = bodyOpened(shown, path);
    paintTabs();
    void paintBody();
  }

  function stop() {
    listening.abort();
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

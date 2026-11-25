// A native stack's page at /stack/<n>: the whole stack as one comparison.
//
// The stack route (`GET stack`, pull_stack.py) answers the stack's members and its combined
// comparison: from the bottom member's merge base to the top member's head, restricted to
// the files some layer changes, with each file's layers. The page draws it with the diff
// plugin's views, as a pull request's page does, in three tabs, and in a fourth when a
// member's description carries the stack's guide:
//
// - **Guided Review** (`/stack/<n>/guided`), the front page when the stack has a guide: the
//   guide's steps (guided-review.js), read against the stack's comparison
//   (`guided-review?stack=`), opening on its first step, since no member's description
//   introduces the stack.
// - **Files** (`/stack/<n>/files`), the front page otherwise: every file in the shell's
//   changed-files tree, the Diff summary drawn open, each row with its layers. A file opens
//   Changes there.
// - **Docs** (`/stack/<n>/docs`): the documents alone, drawn as a pull request's Docs draws
//   them (`DOCS_DRAWING`, diff-drawing.js).
// - **Changes** (`/stack/<n>/changes[/<path>]`): every file, as a pull request's Changes.
//
// Each file's bar and row carries a mark for each layer that changes it, "2/4", which
// opens the file in that layer's own Changes (`/pull/<n>/files/<path>`).
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
// one stays beneath the status line, since the server keeps answering a pair it gave
// (pull_stack_retained.py). `bodyPlan` decides what the body does with each answer, and a
// file is scrolled to once, when the reader opens it, never again by a later answer.
// Guided Review stays with it (`guideShown`): the guide is read again when the reader takes
// the comparison offered, or when the description that carries it changes.
//
// tests/dom/github-stack-page-session.js runs the pure parts and the controller here from
// the command line.

import { CHANGES_DRAWING, citedPullComparison, DOCS_DRAWING, DOCS_GROUP } from "./diff-drawing.js";
import { FAST_POLL_MS, h, isPlainClick, SLOW_POLL_MS, textRefusalNote } from "./pull-page.js";
import { stackLabel, stackMenuOrder, stackPosition } from "./pull-stacks.js";
import { pullStateIcon } from "./pull-state.js";

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
 * Review shows only for a stack with a guide, and leads, as the author's reading order. */
export const STACK_TABS = Object.freeze([
  Object.freeze({ id: "guided", label: "Guided Review" }),
  Object.freeze({ id: "files", label: "Files" }),
  Object.freeze({ id: "docs", label: "Docs" }),
  Object.freeze({ id: "changes", label: "Changes" }),
]);

/**
 * @typedef {{number: number, place: number, title: string | null, state: "open" | "draft" | "merged" | "closed" | null, base: string | null, head: string | null, in_top: boolean | null, pending: boolean, fetching?: boolean}} StackMember
 * @typedef {{left: string, right: string, key: string, route: string, image_route: string, rendered_route: string}} StackComparison
 * @typedef {{path: string, layers: Array<{number: number, place: number, path: string}>}} StackFile
 * @typedef {{
 *   state: "absent" | "pending" | "current",
 *   reason: string | null,
 *   number: number,
 *   base_ref: string | null,
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
 * description carries the stack's guide (`guideShown`) and Files otherwise. Before the
 * stack is read, the front page shows none, so no tab is marked that the answer then moves
 * from; Guided Review's own address shows Files for a stack with no guide.
 *
 * @param {string} tab The route's tab, "" for the front page.
 * @param {StackEnvelope | null} envelope
 * @param {StackGuide | null} guide
 * @returns {StackTab}
 */
export function shownTab(tab, envelope, guide) {
  if (tab === "docs" || tab === "changes" || tab === "files") {
    return tab;
  }
  if (envelope === null) {
    return tab === "guided" ? "guided" : "";
  }
  return guide === null ? "files" : "guided";
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
 * A file's marks: one for each layer that changes it, by its place, "2/4", which opens the
 * file in that layer's Changes.
 *
 * @param {StackEnvelope | null} envelope
 * @param {string} path
 * @param {(number: number, path: string) => string} href
 * @returns {Array<{number: number, path: string, text: string, label: string, href: string}>}
 */
export function layerMarks(envelope, path, href) {
  const file = envelope?.files.find((entry) => entry.path === path);
  if (envelope === null || file === undefined) {
    return [];
  }
  const count = envelope.members.length;
  return file.layers.map((layer) => ({
    number: layer.number,
    path: layer.path,
    text: stackPosition(layer.place - 1, count),
    label: `Layer ${layer.place} of ${count}, #${layer.number}: this file’s changes there`,
    href: href(layer.number, layer.path),
  }));
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
 * A notice the page shows above the body: a failed read, a comparison it offers, the stack
 * moving or ceasing to be one comparison while one stays drawn, or members it could not
 * fetch. `take` shows the new comparison; `retry` asks again for the members named.
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
 * The notices above the body, in order: the read's failure, then what became of the stack
 * since the drawn comparison. With nothing drawn, the body says why itself (`bodyPlan`).
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
 * @typedef {{do: "wait"} | {do: "notice", text: string, retry: boolean} | {do: "keep"} | {do: "scroll", file: string} | {do: "mount", key: string, tab: "guided" | "files" | "docs" | "changes", comparison: StackComparison}} BodyAction
 * @typedef {"" | "guided" | "files" | "docs" | "changes"} StackTab The tab the page shows, ""
 * while the front page waits for the stack's answer to choose one.
 */

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
 * The diff view's comparison for the stack's: direct, since the bottom's merge base is an
 * ancestor of the top's head, at the routes the answer names, and with no View file controls,
 * since no one branch holds a stack.
 *
 * @param {StackComparison} comparison
 */
function diffComparison(comparison) {
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

/** How long the first screen's Markdown waits for Rendered, as a pull request's Changes. */
const FIRST_SCREEN_MS = 300;

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
  const header = h("div", { class: "github-pull-header page-header page-reading-column" });
  const status = h("div", { class: "github-pull-stack-page-status" });
  const tabBar = h("div", { class: "tab-bar", role: "tablist", "aria-label": "Stack" });
  const body = h("div", { class: "github-pull-body github-pull-stack-page-body" });
  container.replaceChildren(
    header,
    status,
    h("div", { class: "page-reading-column" }, [tabBar]),
    body,
  );
  container.classList.add("github-pull-stack-page");

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
  /** What the body shows (`bodyPlan`). @type {StackBody} */
  let shown = NO_BODY;
  /** @type {{dispose?: () => void, scrollToFile?: (path: string) => unknown} | null} */
  let handle = null;
  /** The guide's view while Guided Review is drawn, told each revision of the description
   * that carries the guide. @type {{show: (revision: string | null, moved: boolean) => void} | null} */
  let guidedView = null;
  /** The allowlist a guide's notes are inserted through, loaded with the first guide.
   * @type {Promise<MetabrowserInertHtmlRuntime | null> | null} */
  let inertReady = null;
  let resolveReady = () => {};
  /** @type {Promise<void>} */
  const ready = new Promise((resolve) => {
    resolveReady = () => resolve(undefined);
  });

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
   * @param {string} label
   * @param {() => void} action
   */
  function button(label, action) {
    const node = h("button", { type: "button", class: "btn github-pull-stack-page-take" }, [label]);
    node.addEventListener("click", action, { signal: listening.signal });
    return node;
  }

  /** @param {number} member @param {string} path */
  function memberFileHref(member, path) {
    try {
      return (
        window.MetabrowserPullRoute?.pullHref(member, "files", path) ?? `/pull/${member}/files`
      );
    } catch {
      return `/pull/${member}/files`;
    }
  }

  /** @param {string} path */
  function marksFor(path) {
    return layerMarks(envelope, path, memberFileHref).map((mark) => ({
      ...mark,
      open: () => open({ number: mark.number, tab: "files", file: mark.path }),
    }));
  }

  const tabLinks = STACK_TABS.map(({ id, label }) => {
    const anchor = link({ number, tab: id, stack: true }, `/stack/${number}/${id}`, "tab-btn", [
      label,
    ]);
    anchor.setAttribute("role", "tab");
    tabBar.append(anchor);
    return { id, anchor };
  });

  function paintTabs() {
    for (const { id, anchor } of tabLinks) {
      anchor.hidden = id === "guided" && guide === null;
      anchor.classList.toggle("active", tab === id);
      anchor.setAttribute("aria-selected", String(tab === id));
    }
  }

  function paintHeader() {
    const title = h("h1", { class: "page-heading github-pull-title" }, [
      stackLabel(number),
      ...(envelope?.base_ref
        ? [h("span", { class: "github-pull-stack-page-base" }, [` into ${envelope.base_ref}`])]
        : []),
    ]);
    const count = envelope?.members.length ?? 0;
    const members = h("ol", { class: "github-pull-stack-page-members", reversed: "" });
    for (const member of topFirst(envelope)) {
      members.append(
        h("li", { class: "github-pull-stack-page-member" }, [
          h("span", { class: "github-pull-stack-position" }, [
            stackPosition(member.place - 1, count),
          ]),
          ...(member.state === null ? [] : [pullStateIcon(member.state)]),
          link(
            { number: member.number, tab: "" },
            `/pull/${member.number}`,
            "github-pull-number github-pull-stack-page-link",
            [`#${member.number}`],
          ),
          h("span", { class: "github-pull-stack-page-member-title" }, [
            ...(member.title === null ? ["Not fetched yet"] : mb.titleNodes(member.title)),
          ]),
          ...(member.in_top === false
            ? [h("span", { class: "github-pull-stack-page-note" }, ["not in the top"])]
            : failed.includes(member.number)
              ? [h("span", { class: "github-pull-stack-page-note" }, ["could not fetch"])]
              : member.pending
                ? [h("span", { class: "github-pull-stack-page-note" }, ["fetching"])]
                : []),
        ]),
      );
    }
    const totals = envelope?.totals ?? null;
    const lines = [
      h("div", { class: "page-header-line github-pull-stack-page-line" }, [
        `${count} pull request${count === 1 ? "" : "s"}`,
        ...(totals === null
          ? []
          : [
              " · ",
              `${totals.files} file${totals.files === 1 ? "" : "s"} changed`,
              ...(totals.additions === null
                ? []
                : [" ", h("span", { class: "diff-stat-add" }, [`+${totals.additions}`])]),
              ...(totals.deletions === null
                ? []
                : [" ", h("span", { class: "diff-stat-del" }, [`−${totals.deletions}`])]),
            ]),
        ...(envelope?.github_url
          ? [
              " · ",
              h(
                "a",
                {
                  href: envelope.github_url,
                  class: "github-pull-stack-page-github",
                  target: "_blank",
                  rel: "noopener noreferrer",
                },
                ["View on GitHub"],
              ),
            ]
          : []),
      ]),
    ];
    const lacking = lackingText(envelope);
    if (lacking !== null) {
      lines.push(h("div", { class: "page-header-line github-pull-stack-page-lacking" }, [lacking]));
    }
    header.replaceChildren(title, ...lines, members);
  }

  /**
   * A notice as the page draws it, with its action's button.
   *
   * @param {StackNotice} notice
   */
  function noticeNode(notice) {
    const severity = notice.severity;
    return h(
      "div",
      {
        class: "notice github-pull-notice",
        ...(severity === null
          ? {}
          : { "data-severity": severity, role: severity === "error" ? "alert" : "status" }),
      },
      [
        notice.text,
        ...(notice.action === "take"
          ? [" ", button("Show the new comparison", take)]
          : notice.action === "retry"
            ? [" ", button("Retry", retry)]
            : []),
      ],
    );
  }

  function paintStatus() {
    status.replaceChildren(
      ...statusNotices(envelope, shown.drawn?.key ?? null, error, failed).map(noticeNode),
    );
  }

  function take() {
    shown = bodyTaken(shown, envelope);
    paintStatus();
    void paintBody();
  }

  function retry() {
    void controller.retry();
  }

  function disposeBody() {
    handle?.dispose?.();
    handle = null;
    guidedView = null;
  }

  /**
   * The stack's guide (guided-review.js): its steps, read against the stack's comparison
   * (`guided-review?stack=`). A file a step cites opens in this page's Changes, and another
   * pull request, or a file of it, in that pull request's page. A file the rendered route
   * renders is drawn whole from *comparison*, the one this page drew, while that is the one
   * the step was read at, or, a file of another pull request, from that one's.
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
      { kind: "stack", number },
      {
        open: (path) => open({ number, tab: "changes", file: path, stack: true }),
        openPull: (target, path) =>
          open(
            path === null
              ? { number: target, tab: "" }
              : { number: target, tab: "files", file: path },
          ),
        age: (iso) => {
          const at = Date.parse(iso);
          if (!Number.isFinite(at)) {
            return h("span", {}, [iso]);
          }
          const { label, className } = mb.formatAge(at / 1000, { style: "relative" });
          return h(
            "span",
            {
              class: `github-pull-age ${className}`,
              "data-tip-text": mb.formatTimestamp(at / 1000),
              "data-age-at": String(at),
            },
            [label],
          );
        },
        shortCommit: (sha) => mb.shortCommit(sha),
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
                markdownHoldMs: FIRST_SCREEN_MS,
              });
            },
          };
        },
        loadDrawProse: async () => {
          const inert = await prose;
          if (inert === null) {
            throw new Error("the inert HTML allowlist did not load");
          }
          // A note's links were made absolute against the member that carries the guide.
          const base = envelope?.github_url ?? "https://github.com/";
          return (html) => inert.kpressProse(inert.sanitizeHtml(html, base), document);
        },
        refusalNote: textRefusalNote,
      },
    );
    return view;
  }

  async function paintBody() {
    const plan = bodyPlan(shown, envelope, tab, failed);
    shown = plan.body;
    const action = plan.action;
    if (action.do === "keep") {
      // An edit of the description that carries the guide is read again.
      if (guide !== null) {
        guidedView?.show(guide.revision, false);
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
      body.replaceChildren(
        noticeNode({
          text: action.text,
          severity: action.retry ? "warning" : null,
          action: action.retry ? "retry" : null,
        }),
      );
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
          view.show(carried.revision, false);
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
    const host = h("div", { class: "github-pull-diff metabrowser-diff-host" });
    body.replaceChildren(host);
    try {
      await mb.ensureKindAssets("diff");
      const view = /** @type {any} */ (mb.getRegisteredView("diff", "diff"));
      if (!owns()) {
        return;
      }
      if (!view) {
        host.textContent = "Changes could not be shown. Reload the page to try again.";
        return;
      }
      const comparison = diffComparison(action.comparison);
      if (action.tab === "files") {
        const raw = await view.prefetch(comparison, listening.signal);
        if (!owns()) {
          return;
        }
        host.classList.add("github-pull-summary");
        adopt(
          await view.summary(host, {
            raw,
            open: true,
            fileMarks: marksFor,
            openFile: (/** @type {string} */ path) =>
              open({ number, tab: "changes", file: path, stack: true }),
          }),
        );
        return;
      }
      const docs = action.tab === "docs";
      adopt(
        await view.render(host, {
          comparisonSignal: listening.signal,
          comparison,
          summary: false,
          fileMarks: marksFor,
          markdownHoldMs: FIRST_SCREEN_MS,
          ...(docs
            ? {
                group: DOCS_GROUP,
                ...DOCS_DRAWING,
                emptyText: "No documents changed in this stack.",
              }
            : {
                ...CHANGES_DRAWING,
                openFile: (/** @type {string} */ path) =>
                  open({ number, tab: "changes", file: path, stack: true }),
              }),
        }),
      );
    } catch (failure) {
      if (owns()) {
        console.error("metabrowser github: the stack's diff could not load", failure);
        host.textContent = "Could not load this stack’s changes. Reload the page to try again.";
      }
    }
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
        paintStatus();
        void paintBody();
        resolveReady();
      },
    },
    { number },
  );
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
    cancelPending() {
      listening.abort();
      controller.dispose();
    },
    dispose() {
      listening.abort();
      controller.dispose();
      disposeBody();
    },
  };
}

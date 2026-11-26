// Optional repository-wide native stack metadata. One shared, visible-reader poller serves
// the panel and page; core PR data never waits for it and no row starts a request.
//
// Every surface that names a stack names it here, so the page's stack button and menu, a
// Pulls row's place, a guide's pull request row's place, and the Pulls tab's stack groups
// say one thing one way (docs/design-system.md, "Stacks"): `stackLabel` is the "Stack #N"
// every heading, menu and tip reads; `stackPosition` is the bold "2/4" of a badge and a
// member row, and `namedStackPosition` the "300 2/2" of a place that names its stack, which
// `namedStackPositionNodes` draws after the Layers glyph; `stackPositionHint` is the tip
// that names both, which `stackPlaceHint` writes from a stack's number and length, as the
// guide's row has them; `stackMenuOrder` is the one member order, top of the stack first;
// and `stackEntries` is the one order of a stack's rows, its Whole stack row first, then its
// members, in the stack menu and under an open stack in the Pulls tab alike. `groupByStack`
// is the Pulls tab's grouping of its rows, `stackPullsCount` the count its stack's heading
// shows, `stackUpdatedAt` the time its age tells, and `wholeStackHint` its Whole stack row's
// accessible name.

/** @typedef {{source: string | null, reader: string | null}} StackIdentity */
/** @typedef {{number: number, base_ref: string, open: boolean, pulls: number[], titles: (string | null)[], authors: (string | null)[], avatars: (string | null)[], labels: (string[] | null)[]}} NativeStack */
/** @typedef {{
 * state: "absent" | "current" | "stale", reason: string | null,
 * source: string | null, reader: string | null, fetched_at: string | null,
 * fresh_for_s: number, refreshing: boolean, complete: boolean,
 * last_refresh: {outcome: string, at: string, reset_at: string | null} | null,
 * stacks: NativeStack[],
 * }} StackEnvelope */
/**
 * A badge's positions, its own stack's first. A part with a `stack` names another stack,
 * drawn as the Layers glyph before its number; `text` is what the badge's letters read,
 * the glyph aside ("4/4 · 300 2/2"), and `hint` its accessible name.
 *
 * @typedef {{position: string, stack: number | null}} StackCaptionPart
 * @typedef {{text: string, hint: string, parts: StackCaptionPart[]}} StackCaption
 */
/** @typedef {{
 * known: boolean, reason: string | null,
 * source: string | null, reader: string | null,
 * byPull: Map<number, NativeStack[]>, labels: Map<number, StackCaption>,
 * }} StackIndex */

/**
 * How long the stacks snapshot's poller waits between its reads while the Pulls tab is shown:
 * a second while the snapshot is being refreshed, and thirty seconds otherwise, the Pulls
 * tab's own intervals (`FAST_POLL_MS` and `SLOW_POLL_MS` in pull-page.js, measured with the
 * freshness row's). A link card reuses one read of the snapshot as long
 * (static/link-preview-providers.js, which tests/test_link_preview_providers_session.py holds
 * equal).
 */
export const STACKS_POLL_MS = 30000;
export const STACKS_REFRESHING_POLL_MS = 1000;

/** A stack's one name, wherever a surface names it. @param {number} number */
export function stackLabel(number) {
  return `Stack #${number}`;
}

/** The words of the row that opens a stack's own page, the first of a stack's rows in the
 * stack menu and under an open stack in the Pulls tab (`stackEntries`; docs/design-system.md,
 * "Stacks"). */
export const WHOLE_STACK = "Whole stack";

/** A member's place in its stack, as GitHub numbers it from the base: "2/4".
 * @param {number} at The member's index in `pulls`, base first.
 * @param {number} length
 */
export function stackPosition(at, length) {
  return `${at + 1}/${length}`;
}

/** A position as a badge reads it where it must say which stack it is in: the stack's
 * number before it, "300 2/2", drawn after the Layers glyph. A position whose stack goes
 * without saying, its pull request's only one or the one its row sits under, is bare.
 * @param {string} position @param {number | null} stack The stack to name, or null.
 */
export function namedStackPosition(position, stack) {
  return stack === null ? position : `${stack} ${position}`;
}

/** `namedStackPosition` as a row draws it: the position bare, or after the Layers glyph and
 * the stack's number, the glyph hidden from assistive technology, so the words read as the
 * text does, "300 2/2".
 * @param {string} position @param {number | null} stack The stack to name, or null.
 * @param {() => Node | null} glyph A new copy of the Layers glyph, or null where there is none.
 * @returns {Array<Node | string>}
 */
export function namedStackPositionNodes(position, stack, glyph) {
  if (stack === null) {
    return [position];
  }
  const mark = document.createElement("span");
  mark.setAttribute("class", "github-pull-stack-other");
  mark.setAttribute("aria-hidden", "true");
  const drawn = glyph();
  if (drawn !== null) {
    mark.append(drawn);
  }
  return [mark, `${stack} `, position];
}

/** The tip that names a member's stack and place: "Stack #286, position 2 of 4".
 * @param {NativeStack} stack @param {number} at
 */
export function stackPositionHint(stack, at) {
  return stackPlaceHint(stack.number, at, stack.pulls.length);
}

/** The same tip from a stack's number and length alone, for a surface that has a
 * member's place and not the stack's list, as a guide's pull request row does.
 * @param {number} number @param {number} at The member's index, base first.
 * @param {number} length
 */
export function stackPlaceHint(number, at, length) {
  return `${stackLabel(number)}, position ${at + 1} of ${length}`;
}

/** The order every surface lists a stack's members in: the top of the stack first.
 * @param {Pick<NativeStack, "pulls">} stack @returns {number[]}
 */
export function stackMenuOrder(stack) {
  return stack.pulls.slice().reverse();
}

/** A stack's rows in the one order every surface that lists them draws: its Whole stack row,
 * null here, which opens the stack's own page, then *members*. The stack menu and an open
 * stack's rows in the Pulls tab both take their order from it, so the Whole stack row has one
 * place in both, first, above the members, and the stack's set counts it
 * (docs/design-system.md, "Stacks").
 * @param {number[]} members The members to list, in `stackMenuOrder`.
 * @returns {Array<number | null>}
 */
export function stackEntries(members) {
  return [null, ...members];
}

/**
 * A badge's parts and accessible name for a pull request's stacks, *first* first. The first
 * position is bare, since the row's own stack needs no name, its only one or the one it is
 * grouped under; each other stack's position is named by the Layers glyph and its number,
 * so a badge never holds two positions a reader cannot tell apart, and never a number that
 * reads as a pull request's "#N" beside the row's own.
 *
 * @param {NativeStack[]} memberships @param {number} number @param {number | null} [first]
 * @returns {StackCaption | null}
 */
function caption(memberships, number, first = null) {
  const ordered =
    first === null
      ? memberships
      : [
          ...memberships.filter((stack) => stack.number === first),
          ...memberships.filter((stack) => stack.number !== first),
        ];
  if (ordered.length === 0) {
    return null;
  }
  const places = ordered.map((stack) => ({ stack, at: stack.pulls.indexOf(number) }));
  /** @type {StackCaptionPart[]} */
  const parts = places.map(({ stack, at }, index) => ({
    position: stackPosition(at, stack.pulls.length),
    stack: index === 0 ? null : stack.number,
  }));
  return {
    text: parts.map((part) => namedStackPosition(part.position, part.stack)).join(" · "),
    hint: places.map(({ stack, at }) => stackPositionHint(stack, at)).join("; "),
    parts,
  };
}

/** @param {StackEnvelope | null} envelope @returns {StackIndex} */
export function createStackIndex(envelope) {
  /** @type {Map<number, NativeStack[]>} */
  const byPull = new Map();
  for (const stack of envelope?.stacks ?? []) {
    for (const number of stack.pulls) {
      const membership = byPull.get(number) ?? [];
      membership.push(stack);
      byPull.set(number, membership);
    }
  }
  /** @type {Map<number, StackCaption>} */
  const labels = new Map();
  for (const [number, memberships] of byPull) {
    labels.set(number, /** @type {StackCaption} */ (caption(memberships, number)));
  }
  return {
    known: envelope !== null,
    reason: envelope?.reason ?? null,
    source: envelope?.source ?? null,
    reader: envelope?.reader ?? null,
    byPull,
    labels,
  };
}

/** Whether *index* is the stacks of the reader and repository the core data is.
 * @param {StackIndex} index @param {StackIdentity | null} identity
 */
function sameIdentity(index, identity) {
  return Boolean(
    identity?.source &&
      identity.reader &&
      index.source === identity.source &&
      index.reader === identity.reader,
  );
}

/** Positive membership belongs to the same source and reader as the core data.
 * @param {StackIndex} index @param {StackIdentity | null} identity @param {number} number
 */
export function stackMembership(index, identity, number) {
  return sameIdentity(index, identity) ? (index.byPull.get(number) ?? []) : [];
}

/** A row's caption, precomputed for every row but one grouped under a stack other than its
 * first, which is built when painted: that is rare, a pull request in two stacks. A row
 * grouped under one of its stacks (*under*) has that stack's position first, bare.
 * @param {StackIndex} index @param {StackIdentity | null} identity @param {number} number
 * @param {number | null} [under]
 */
export function stackCaption(index, identity, number, under = null) {
  if (!sameIdentity(index, identity)) {
    return null;
  }
  const memberships = index.byPull.get(number) ?? [];
  return under === null || memberships.length < 2 || memberships[0].number === under
    ? (index.labels.get(number) ?? null)
    : caption(memberships, number, under);
}

/** The row key of a stack's group row in the Pulls list. A pull request's row is keyed by
 * its number, always positive, so one number space keys every row and none collides.
 * @param {number} number
 */
export function stackRowKey(number) {
  return -number;
}

/** The row key of a stack's Whole stack row in the Pulls list: half a step past its stack's
 * row's key, so it collides with no stack's row and no pull request's, and it is negative,
 * as every row that is not a pull request's is (docs/design-system.md, "Stack Groups in the
 * Pulls Tab").
 * @param {number} number
 */
export function wholeStackRowKey(number) {
  return -number - 0.5;
}

/** The stack whose Whole stack row *key* is, or null for any other row's key.
 * @param {number} key
 */
export function wholeStackOfKey(key) {
  return key < 0 && !Number.isInteger(key) ? -(key + 0.5) : null;
}

/**
 * @typedef {{
 *   kind: "stack", key: number, stack: NativeStack, label: string, hint: string,
 *   members: number[], expanded: boolean, level: 1, posinset: number, setsize: number,
 *   shown: number, elsewhere: ReadonlyMap<number, number>, updatedAt: string | null,
 * }} StackGroupRow A stack's row. `updatedAt` is the time its heading's age tells
 *   (`stackUpdatedAt`), or null where the list has none for its pull requests.
 * @typedef {{
 *   kind: "pull", key: number, number: number, level: 1 | 2, stack: number | null,
 *   posinset: number, setsize: number,
 * }} PullGroupRow
 * @typedef {{
 *   kind: "whole", key: number, stack: number, level: 2, posinset: number, setsize: number,
 * }} WholeStackRow A stack's Whole stack row, the first under its open stack, which opens the
 *   stack's own page; its children are the stack's changed files, as a pull request's row's
 *   are its own.
 * @typedef {StackGroupRow | PullGroupRow | WholeStackRow} GroupedRow
 */

/**
 * The Pulls list grouped by stack. Pure.
 *
 * *numbers* are the list's pull requests in its own order. Each stack with a pull request
 * among them has a row, "Stack #N", open unless *collapsed* names it, and under it its
 * pull requests in the list, in `stackMenuOrder`. The stacks come in the order of their
 * first pull request in the list, so the list's own order still decides which comes
 * first; a tie, two stacks first listed at one shared member, keeps the envelope's order.
 * A pull request in more than one stack sits once, under the first of them in that order;
 * a stack whose listed pull requests all sit under earlier stacks has no row; their
 * places name it. Pull requests in no stack follow the stacks, in the list's order.
 *
 * An open stack's rows under it, at one level, are its Whole stack row and its pull requests,
 * in `stackEntries`' order, the stack menu's: the Whole stack row, which opens the stack's own
 * page (`/stack/<n>`, stack-page.js), is one of the stack's rows, so they count it in their
 * set, "1/4" under a stack of three (docs/design-system.md, "Stack Groups in the Pulls
 * Tab"). No pull request is ever under the Whole stack row.
 *
 * *setSize* is how many pull requests the list has, which may be more than it holds: the
 * list's first level is the stacks and every pull request in none, so its size is that
 * less the pull requests placed under stacks. *updatedAt* is when the list says a pull
 * request it holds was last updated, which a stack's heading tells the newest of
 * (`stackUpdatedAt`).
 *
 * @param {number[]} numbers
 * @param {StackIndex} index
 * @param {StackIdentity | null} identity
 * @param {{
 *   collapsed?: ReadonlySet<number>, setSize?: number,
 *   updatedAt?: (number: number) => string | null,
 * }} [options]
 * @returns {{stacks: number, placed: number, rows: GroupedRow[]}}
 */
export function groupByStack(numbers, index, identity, options = {}) {
  const collapsed = options.collapsed ?? new Set();
  const listed = new Set(numbers);
  /** @type {Map<number, NativeStack>} */
  const order = new Map();
  for (const number of numbers) {
    for (const stack of stackMembership(index, identity, number)) {
      if (!order.has(stack.number)) {
        order.set(stack.number, stack);
      }
    }
  }
  /** The stack each placed pull request sits under. @type {Map<number, number>} */
  const placed = new Map();
  /** @type {{stack: NativeStack, members: number[], listed: number, elsewhere: Map<number, number>}[]} */
  const groups = [];
  /** Each drawn stack's pull requests the list holds, under it or an earlier stack.
   * @type {Map<number, number[]>} */
  const listedOf = new Map();
  for (const stack of order.values()) {
    const listedMembers = stackMenuOrder(stack).filter((number) => listed.has(number));
    const members = listedMembers.filter((number) => !placed.has(number));
    if (members.length === 0) {
      continue;
    }
    // Its listed pull requests under earlier stacks, by the stack each sits under.
    /** @type {Map<number, number>} */
    const elsewhere = new Map();
    for (const number of listedMembers) {
      const under = placed.get(number);
      if (under !== undefined) {
        elsewhere.set(under, (elsewhere.get(under) ?? 0) + 1);
      }
    }
    for (const number of members) {
      placed.set(number, stack.number);
    }
    groups.push({ stack, members, listed: listedMembers.length, elsewhere });
    listedOf.set(stack.number, listedMembers);
  }
  const rest = numbers.filter((number) => !placed.has(number));
  const firstLevel =
    groups.length + Math.max(rest.length, (options.setSize ?? numbers.length) - placed.size);
  /** @type {GroupedRow[]} */
  const rows = [];
  for (const [at, { stack, members, listed: shown, elsewhere }] of groups.entries()) {
    const expanded = !collapsed.has(stack.number);
    rows.push({
      kind: "stack",
      key: stackRowKey(stack.number),
      stack,
      label: stackLabel(stack.number),
      hint: stackGroupHint(stack, shown, elsewhere),
      members,
      expanded,
      level: 1,
      posinset: at + 1,
      setsize: firstLevel,
      // What its accessible name counts.
      shown,
      elsewhere,
      updatedAt: stackUpdatedAt(listedOf.get(stack.number) ?? [], options.updatedAt),
    });
    if (expanded) {
      const entries = stackEntries(members);
      for (const [place, number] of entries.entries()) {
        rows.push(
          number === null
            ? {
                kind: "whole",
                key: wholeStackRowKey(stack.number),
                stack: stack.number,
                level: 2,
                posinset: place + 1,
                setsize: entries.length,
              }
            : {
                kind: "pull",
                key: number,
                number,
                level: 2,
                stack: stack.number,
                posinset: place + 1,
                setsize: entries.length,
              },
        );
      }
    }
  }
  for (const [at, number] of rest.entries()) {
    rows.push({
      kind: "pull",
      key: number,
      number,
      level: 1,
      stack: null,
      posinset: groups.length + at + 1,
      setsize: firstLevel,
    });
  }
  return { stacks: groups.length, placed: placed.size, rows };
}

/** How many pull requests a stack has: the count its Pulls heading shows, "Stack #286 · 4
 * pulls", and the one its accessible name says first (`stackGroupHint`), so the two cannot
 * differ. It is the stack's size, not how many the list holds, which the name says after it.
 * @param {Pick<NativeStack, "pulls">} stack
 */
export function stackPullsCount(stack) {
  return stack.pulls.length;
}

/**
 * The time a stack's heading tells the age of: the newest `updated_at` of its pull requests
 * the list holds, or null where it has none. GitHub moves a pull request's `updated_at` on a
 * push, a review, a comment, and a change of state, base, or title, so the newest of them is
 * the stack's most recent change of any kind, and it is the time each row under the heading
 * tells its own age from: the heading's age is the freshest of its rows', never older than
 * one of them. The stack snapshot holds no times, and the list's rows are read already, so
 * the heading waits on nothing. A member the list does not hold, a merged one in the Open
 * list, has no time here, as it has no row.
 *
 * @param {number[]} listed The stack's pull requests the list holds.
 * @param {((number: number) => string | null) | undefined} updatedAt
 * @returns {string | null}
 */
export function stackUpdatedAt(listed, updatedAt) {
  /** @type {string | null} */
  let newest = null;
  let newestAt = Number.NEGATIVE_INFINITY;
  for (const number of listed) {
    const said = updatedAt?.(number) ?? null;
    const at = said === null ? Number.NaN : Date.parse(said);
    if (at > newestAt) {
      newest = said;
      newestAt = at;
    }
  }
  return newest;
}

/**
 * A stack row's accessible name, since the Pulls column shows no tooltips: its label, its
 * size, the count its heading shows (`stackPullsCount`), how many of its pull requests the
 * list holds, and where those under an earlier stack sit, so a count of listed pull
 * requests that is more than the rows under it says why: "Stack #286, 4 pull requests, 3 in
 * this list". The lines the stack changes are its Whole stack row's to say
 * (`wholeStackHint`).
 *
 * @param {NativeStack} stack
 * @param {number} shown How many of its pull requests the list holds.
 * @param {ReadonlyMap<number, number>} [elsewhere] How many sit under each earlier stack.
 */
export function stackGroupHint(stack, shown, elsewhere = new Map()) {
  const total = stackPullsCount(stack);
  const parts = [`${total} pull request${total === 1 ? "" : "s"}`];
  if (shown < total) {
    parts.push(`${shown} in this list`);
  }
  for (const [under, count] of elsewhere) {
    parts.push(`${count} under ${stackLabel(under)}`);
  }
  return [stackLabel(stack.number), ...parts].join(", ");
}

/**
 * A Whole stack row's accessible name in the Pulls tab: its words and its stack, then the
 * brief change line the row shows (stack-lines.js) in words, as the Diff summary's name says
 * its own: "Whole stack, Stack #286: 1,234 lines added, 567 deleted", or "change pending"
 * while the line is read.
 *
 * @param {number} stack
 * @param {string | null} [change] The change line's words, when the row shows it or waits.
 */
export function wholeStackHint(stack, change = null) {
  const name = `${WHOLE_STACK}, ${stackLabel(stack)}`;
  return change === null ? name : `${name}: ${change}`;
}

/** A member selection has the same explicit-reader fetch intent as a catalog click.
 * @param {number} number @param {string} tab
 * @returns {{number: number, tab: string, reader: {fetchAfterMs: number, initial: null}}}
 */
export function memberRoute(number, tab) {
  return { number, tab, reader: { fetchAfterMs: 0, initial: null } };
}

/** @param {unknown} value @returns {value is StackEnvelope} */
function isEnvelope(value) {
  if (value === null || typeof value !== "object") {
    return false;
  }
  const body = /** @type {Partial<StackEnvelope>} */ (value);
  let members = 0;
  return (
    ["absent", "current", "stale"].includes(body.state ?? "") &&
    typeof body.refreshing === "boolean" &&
    Number.isFinite(body.fresh_for_s) &&
    (body.source === null || typeof body.source === "string") &&
    (body.reader === null || typeof body.reader === "string") &&
    // Match the bounded repository snapshot protocol in pull_stacks.py. The server
    // validates too; a malformed optional response cannot create an unbounded index.
    Array.isArray(body.stacks) &&
    body.stacks.length <= 1000 &&
    body.stacks.every((stack) => {
      if (
        !Number.isSafeInteger(stack.number) ||
        stack.number <= 0 ||
        !Array.isArray(stack.pulls) ||
        stack.pulls.length === 0 ||
        stack.pulls.length > 1000 ||
        !Array.isArray(stack.titles) ||
        stack.titles.length !== stack.pulls.length ||
        stack.titles.some(
          (title) => title !== null && (typeof title !== "string" || title.length > 2048),
        ) ||
        // Each member's author and the author's avatar, from the same cached row as its
        // title (pull_stacks_route.py), which the page's stack menu draws.
        ![stack.authors, stack.avatars].every(
          (values) =>
            Array.isArray(values) &&
            values.length === stack.pulls.length &&
            values.every(
              (value) => value === null || (typeof value === "string" && value.length <= 2048),
            ),
        )
      ) {
        return false;
      }
      members += stack.pulls.length;
      return (
        members <= 10000 &&
        stack.pulls.every((number) => Number.isSafeInteger(number) && number > 0)
      );
    })
  );
}

/**
 * @param {{
 * request(method: "GET" | "POST", route: string, options: {etag?: string | null, body?: unknown, signal: AbortSignal}): Promise<{status: number, body: unknown, etag: string | null}>,
 * now(): number, schedule(callback: () => void, delay: number): unknown,
 * cancel(timer: unknown): void, isVisible(): boolean,
 * }} deps
 */
export function createStackController(deps) {
  /** @type {StackEnvelope | null} */
  let envelope = null;
  let index = createStackIndex(null);
  /** @type {string | null} */
  let content = null;
  /** @type {string | null} */
  let etag = null;
  /** @type {unknown} */
  let timer = null;
  /** @type {AbortController | null} */
  let owner = null;
  let epoch = 0;
  let askedAt = Number.NEGATIVE_INFINITY;
  let freshUntil = 0;
  /** @type {Set<{shown: boolean, notify(index: StackIndex): void}>} */
  const readers = new Set();
  const live = () => deps.isVisible() && [...readers].some((reader) => reader.shown);

  function clearTimer() {
    if (timer !== null) {
      deps.cancel(timer);
    }
    timer = null;
  }
  function pause() {
    epoch += 1;
    owner?.abort();
    owner = null;
    clearTimer();
  }
  /** @param {StackEnvelope} next */
  function hold(next) {
    envelope = next;
    freshUntil = deps.now() + Math.max(0, next.fresh_for_s) * 1000;
    // Count/freshness polling does not rebuild the membership index or row DOM. Why there
    // is no snapshot, its `reason`, is part of what the index says: the Pulls tab's stack
    // option tells it (pulls-panel.js, `describeStackGrouping`).
    const key = JSON.stringify([next.source, next.reader, next.stacks, next.reason]);
    if (content !== key) {
      content = key;
      index = createStackIndex(next);
      for (const reader of readers) {
        reader.notify(index);
      }
    }
  }
  function due() {
    if (
      envelope === null ||
      envelope.refreshing ||
      envelope.reason === "not_github" ||
      deps.now() < freshUntil
    ) {
      return false;
    }
    const reset = Date.parse(envelope.last_refresh?.reset_at ?? "");
    if (Number.isFinite(reset) && reset > deps.now()) {
      return false;
    }
    const attempt = Date.parse(envelope.last_refresh?.at ?? "");
    if (
      envelope.last_refresh &&
      envelope.last_refresh.outcome !== "succeeded" &&
      Number.isFinite(attempt) &&
      deps.now() - attempt < 300000
    ) {
      return false;
    }
    return (
      deps.now() - askedAt >= 300000 && (envelope.state !== "current" || deps.now() >= freshUntil)
    );
  }
  function schedule() {
    clearTimer();
    if (live() && !["not_github", "gh_stack_missing"].includes(envelope?.reason ?? "")) {
      timer = deps.schedule(
        () => {
          timer = null;
          void read();
        },
        envelope?.refreshing ? STACKS_REFRESHING_POLL_MS : STACKS_POLL_MS,
      );
    }
  }
  async function read() {
    if (!live() || owner !== null) {
      return;
    }
    const mine = new AbortController();
    const ticket = epoch;
    owner = mine;
    try {
      const answer = await deps.request("GET", "/api/plugin/github/stacks", {
        etag,
        signal: mine.signal,
      });
      if (ticket !== epoch || mine.signal.aborted || !live()) {
        return;
      }
      if (answer.status === 200 && isEnvelope(answer.body)) {
        etag = answer.etag;
        hold(answer.body);
      }
      if (due()) {
        askedAt = deps.now();
        const response = await deps.request("POST", "/api/plugin/github/stacks-refresh", {
          body: {},
          signal: mine.signal,
        });
        if (ticket !== epoch || mine.signal.aborted || !live()) {
          return;
        }
        const body = /** @type {{stacks?: unknown} | null} */ (response.body);
        if ((response.status === 200 || response.status === 202) && isEnvelope(body?.stacks)) {
          hold(body.stacks);
        }
      }
    } catch {
      // Enrichment failure never replaces core PR data or a retained positive snapshot.
    } finally {
      if (owner === mine) {
        owner = null;
        schedule();
      }
    }
  }
  function visibilityChanged() {
    if (live()) {
      void read();
    } else {
      pause();
    }
  }
  return Object.freeze({
    /** @param {(index: StackIndex) => void} notify @param {boolean} [shown] */
    watch(notify, shown = true) {
      const reader = { shown, notify };
      readers.add(reader);
      notify(index);
      void read();
      return Object.freeze({
        /** @param {boolean} shown */
        setShown(shown) {
          reader.shown = shown;
          visibilityChanged();
        },
        dispose() {
          readers.delete(reader);
          if (!live()) {
            pause();
          }
        },
      });
    },
    visibilityChanged,
    snapshot: () => envelope,
  });
}

/** @type {ReturnType<typeof createStackController> | null} */
let shared = null;
let watching = 0;
/** @type {(() => void) | null} */
let unwatch = null;

/** Browser adapter, shared by every page/panel in this repository's shell.
 * @param {(index: StackIndex) => void} notify
 * @param {boolean} [shown]
 */
export function watchStacks(notify, shown = true) {
  shared ??= createStackController({
    async request(method, route, options) {
      const response = await fetch(route, {
        method,
        cache: "no-store",
        signal: options.signal,
        headers:
          method === "POST"
            ? { "content-type": "application/json" }
            : options.etag
              ? { "if-none-match": options.etag }
              : {},
        body: method === "POST" ? JSON.stringify(options.body) : undefined,
      });
      return {
        status: response.status,
        etag: response.headers.get("etag"),
        body: response.status === 304 ? null : await response.json(),
      };
    },
    now: () => Date.now(),
    schedule: (callback, delay) => window.setTimeout(callback, delay),
    cancel: (timer) => window.clearTimeout(/** @type {number} */ (timer)),
    isVisible: () => document.visibilityState === "visible",
  });
  if (watching++ === 0) {
    const changed = () => shared?.visibilityChanged();
    document.addEventListener("visibilitychange", changed);
    unwatch = () => document.removeEventListener?.("visibilitychange", changed);
  }
  const reader = shared.watch(notify, shown);
  let disposed = false;
  return Object.freeze({
    setShown: reader.setShown,
    dispose() {
      if (disposed) {
        return;
      }
      disposed = true;
      reader.dispose();
      if (--watching === 0) {
        unwatch?.();
        unwatch = null;
      }
    },
  });
}

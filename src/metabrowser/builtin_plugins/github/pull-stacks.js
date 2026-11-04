// Optional repository-wide native stack metadata. One shared, visible-reader poller serves
// the panel and page; core PR data never waits for it and no row starts a request.

/** @typedef {{source: string | null, reader: string | null}} StackIdentity */
/** @typedef {{number: number, base_ref: string, open: boolean, pulls: number[]}} NativeStack */
/** @typedef {{
 * state: "absent" | "current" | "stale", reason: string | null,
 * source: string | null, reader: string | null, fetched_at: string | null,
 * fresh_for_s: number, refreshing: boolean, complete: boolean,
 * last_refresh: {outcome: string, at: string, reset_at: string | null} | null,
 * stacks: NativeStack[],
 * }} StackEnvelope */
/** @typedef {{source: string | null, reader: string | null, byPull: Map<number, NativeStack[]>, labels: Map<number, string>}} StackIndex */

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
  const labels = new Map(
    [...byPull].map(([number, stacks]) => [
      number,
      stacks.map((stack) => ` · Stack #${stack.number}`).join(""),
    ]),
  );
  return { source: envelope?.source ?? null, reader: envelope?.reader ?? null, byPull, labels };
}

/** Positive membership belongs to the same source and reader as the core data.
 * @param {StackIndex} index @param {StackIdentity | null} identity @param {number} number
 */
export function stackMembership(index, identity, number) {
  return identity?.source &&
    identity.reader &&
    index.source === identity.source &&
    index.reader === identity.reader
    ? (index.byPull.get(number) ?? [])
    : [];
}

/** A precomputed row caption: no membership traversal on viewport paint.
 * @param {StackIndex} index @param {StackIdentity | null} identity @param {number} number
 */
export function stackCaption(index, identity, number) {
  return identity?.source &&
    identity.reader &&
    index.source === identity.source &&
    index.reader === identity.reader
    ? (index.labels.get(number) ?? "")
    : "";
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
        stack.pulls.length > 1000
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
    // Count/freshness polling does not rebuild the membership index or row DOM.
    const key = JSON.stringify([next.source, next.reader, next.stacks]);
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
        envelope?.refreshing ? 1000 : 30000,
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

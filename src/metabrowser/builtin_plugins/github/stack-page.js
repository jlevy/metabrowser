// A native stack's page at /stack/<n>: the whole stack as one comparison.
//
// The stack route (`GET stack`, pull_stack.py) answers the stack's members and its combined
// comparison: from the bottom member's merge base to the top member's head, restricted to
// the files some layer changes, with each file's layers. The page draws it with the diff
// plugin's views, as a pull request's page does, in three tabs:
//
// - **Files** (`/stack/<n>/files`), the front page until a stack has a guide: every file
//   in the shell's changed-files tree, the Diff summary drawn open, each row with its
//   layers. A file opens Changes there.
// - **Docs** (`/stack/<n>/docs`): the documents alone, drawn as a pull request's Docs draws
//   them (`DOCS_DRAWING`, diff-drawing.js).
// - **Changes** (`/stack/<n>/changes[/<path>]`): every file, as a pull request's Changes.
//
// Each file's bar and row carries a mark for each layer that changes it, "2/4", which
// opens the file in that layer's own Changes (`/pull/<n>/files/<path>`).
//
// The page reads the stack route on a poll, as a pull request's page reads its own, and
// asks `pull-refresh` once for each member it names as pending at that member's head. While
// it is open it sends the top member's automatic ask, which keeps the repository's list
// probed so that the catalog keeps reporting every member's head
// (docs/project/specs/active/plan-2026-11-24-stack-review.md, "Staying Current"). A
// comparison that changes while the reader reads is offered, not swapped in.
//
// tests/dom/github-stack-page-session.js runs the pure parts and the controller here from
// the command line.

import { CHANGES_DRAWING, DOCS_DRAWING, DOCS_GROUP } from "./diff-drawing.js";
import { h, isPlainClick } from "./pull-page.js";
import { stackLabel, stackMenuOrder, stackPosition } from "./pull-stacks.js";
import { pullStateIcon } from "./pull-state.js";

export const STACK_ROUTE = "/api/plugin/github/stack";
const REFRESH_ROUTE = "/api/plugin/github/pull-refresh";
// The poll while a member is still to arrive, and while the page is out of sight: the pull
// request page's (`FAST_POLL_MS` and `SLOW_POLL_MS` in pull-page.js), so a stack's page adds
// no cadence of its own.
export const PENDING_POLL_MS = 1000;
export const HIDDEN_POLL_MS = 30000;
// What the page says while the stack route cannot be read. The poll keeps asking, so it offers
// no remedy, and the last answer read stays drawn beneath it.
export const UNREADABLE = "Could not read this stack.";

/** The tabs, in the order the bar shows them; their ids are the route's segments. */
export const STACK_TABS = Object.freeze([
  Object.freeze({ id: "files", label: "Files" }),
  Object.freeze({ id: "docs", label: "Docs" }),
  Object.freeze({ id: "changes", label: "Changes" }),
]);

/**
 * @typedef {{number: number, place: number, title: string | null, state: "open" | "draft" | "merged" | "closed" | null, base: string | null, head: string | null, in_top: boolean | null, pending: boolean}} StackMember
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
 *   guide: number | null,
 *   github_url: string | null,
 *   probe: {number: number, held: string | null, every_s: number} | null,
 * }} StackEnvelope
 */

/**
 * The tab a route shows: its own, or the front page's, Files, since the page draws no
 * stack's Guided Review yet.
 *
 * @param {string} tab The route's tab, "" for the front page.
 * @param {StackEnvelope | null} _envelope
 * @returns {"files" | "docs" | "changes"}
 */
export function shownTab(tab, _envelope) {
  return tab === "docs" || tab === "changes" ? tab : "files";
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
 * The members to ask `pull-refresh` for: each that the answer names as pending, once for
 * the head its record has (none, for a member with no record). *asked* holds what was
 * asked; the answer is what to ask now, each with its key to add.
 *
 * @param {StackEnvelope | null} envelope
 * @param {ReadonlySet<string>} asked
 * @returns {Array<{number: number, key: string}>}
 */
export function refreshAsks(envelope, asked) {
  if (envelope === null || envelope.state === "absent") {
    return [];
  }
  return envelope.members
    .filter((member) => member.pending)
    .map((member) => ({ number: member.number, key: `${member.number}:${member.head ?? ""}` }))
    .filter((ask) => !asked.has(ask.key));
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
  const named = lacking.map((number) => `#${number}`);
  const list =
    named.length === 1
      ? named[0]
      : `${named.slice(0, -1).join(", ")}${named.length > 2 ? "," : ""} and ${named.at(-1)}`;
  const which = named.length === 1 ? "its changes" : "each one’s changes";
  return `The top of this stack does not contain ${list}, so this view leaves out ${which}. Open ${named.length === 1 ? "it" : "each"} to see them.`;
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
 * The poll's next delay: soon while a member is still to arrive, at the top member's probe
 * interval while the page is in sight, and slowly out of sight.
 *
 * @param {StackEnvelope | null} envelope
 * @param {boolean} visible
 */
export function pollDelay(envelope, visible) {
  if (!visible) {
    return HIDDEN_POLL_MS;
  }
  if (envelope === null || envelope.state === "pending" || envelope.pending.length > 0) {
    return PENDING_POLL_MS;
  }
  return envelope.probe === null ? HIDDEN_POLL_MS : envelope.probe.every_s * 1000;
}

/**
 * @typedef {{status: number, etag: string | null, body: unknown}} StackResponse
 * @typedef {{
 *   request(method: "GET" | "POST", route: string, options: {etag?: string | null, body?: unknown}): Promise<StackResponse>,
 *   schedule(callback: () => void, delayMs: number): unknown,
 *   cancel(handle: unknown): void,
 *   now(): number,
 *   isVisible(): boolean,
 *   render(model: {envelope: StackEnvelope | null, error: string | null}): void,
 * }} StackDependencies
 */

/**
 * The poll and the asks of one stack's page. It reads the stack route, asks for each pending
 * member once at its head, sends the top member's automatic ask at its interval while the
 * page is in sight, and renders each answer that changed.
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
  /** @type {Set<string>} */
  const asked = new Set();
  /** When the top member was last asked for, by `deps.now()`. @type {number | null} */
  let probedAt = null;
  /** @type {unknown} */
  let timer = null;
  let disposed = false;

  /** @param {number} number @param {string | null} held */
  async function ask(number, held) {
    try {
      await deps.request("POST", REFRESH_ROUTE, {
        body: { number, ...(held === null ? {} : { held }) },
      });
    } catch {
      // The next poll says what came of it; an ask that did not reach the server is asked
      // again only at the member's next head, as its own page would not retry either.
    }
  }

  function askWhatIsDue() {
    for (const due of refreshAsks(envelope, asked)) {
      asked.add(due.key);
      void ask(due.number, null);
    }
    const probe = envelope?.probe ?? null;
    if (
      probe !== null &&
      deps.isVisible() &&
      (probedAt === null || deps.now() - probedAt >= probe.every_s * 1000)
    ) {
      probedAt = deps.now();
      void ask(probe.number, probe.held);
    }
  }

  async function poll() {
    timer = null;
    if (disposed) {
      return;
    }
    let changed = false;
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
      } else if (response.status === 304) {
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
    }
    if (changed) {
      deps.render({ envelope, error });
    }
    askWhatIsDue();
    timer = deps.schedule(() => void poll(), pollDelay(envelope, deps.isVisible()));
  }

  return Object.freeze({
    /** Read the stack now, as the first read and a visible page's return do. */
    start() {
      if (timer !== null) {
        deps.cancel(timer);
        timer = null;
      }
      return poll();
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
  let tab = shownTab(routeTab, null);
  /** @type {string} */
  let file = "";
  /** @type {StackEnvelope | null} */
  let envelope = null;
  /** The comparison drawn, which a later one is offered beside. @type {StackComparison | null} */
  let drawn = null;
  /** What the body shows: the tab and the comparison's key. */
  let bodyKey = "";
  /** @type {{dispose?: () => void, scrollToFile?: (path: string) => unknown} | null} */
  let handle = null;
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

  /** @param {string | null} message */
  function paintStatus(message) {
    const action = comparisonAction(drawn?.key ?? null, envelope);
    const nodes = [];
    if (message !== null) {
      // A failed read keeps the last answer drawn, so it is a warning; with none, an error.
      const severity = envelope === null ? "error" : "warning";
      nodes.push(
        h(
          "div",
          {
            class: "notice github-pull-notice",
            "data-severity": severity,
            role: severity === "error" ? "alert" : "status",
          },
          [message],
        ),
      );
    }
    if (action === "offer") {
      const take = h("button", { type: "button", class: "btn github-pull-stack-page-take" }, [
        "Show the new comparison",
      ]);
      take.addEventListener(
        "click",
        () => {
          drawn = envelope?.comparison ?? null;
          paintStatus(null);
          void paintBody(true);
        },
        { signal: listening.signal },
      );
      nodes.push(
        h("div", { class: "notice github-pull-notice" }, [
          "This stack has changed since its comparison was drawn. ",
          take,
        ]),
      );
    }
    status.replaceChildren(...nodes);
  }

  function disposeBody() {
    handle?.dispose?.();
    handle = null;
  }

  /** @param {boolean} [force] */
  async function paintBody(force = false) {
    if (envelope === null) {
      return;
    }
    if (envelope.state !== "current" || drawn === null) {
      disposeBody();
      bodyKey = "";
      body.replaceChildren(
        h("div", { class: "notice github-pull-notice" }, [
          envelope.state === "pending"
            ? `Fetching ${envelope.pending.map((member) => `#${member}`).join(", ")} before the stack can be shown.`
            : absentText(envelope.reason),
        ]),
      );
      return;
    }
    const key = JSON.stringify([tab, drawn.key]);
    if (!force && key === bodyKey) {
      if (tab === "changes" && file) {
        handle?.scrollToFile?.(file);
      }
      return;
    }
    bodyKey = key;
    disposeBody();
    const comparison = drawn;
    const host = h("div", { class: "github-pull-diff metabrowser-diff-host" });
    body.replaceChildren(host);
    const owns = () => !listening.signal.aborted && bodyKey === key;
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
      const shown = diffComparison(comparison);
      if (tab === "files") {
        const raw = await view.prefetch(shown, listening.signal);
        if (!owns()) {
          return;
        }
        host.classList.add("github-pull-summary");
        handle = await view.summary(host, {
          raw,
          open: true,
          fileMarks: marksFor,
          openFile: (/** @type {string} */ path) =>
            open({ number, tab: "changes", file: path, stack: true }),
        });
        return;
      }
      const docs = tab === "docs";
      const mounted = await view.render(host, {
        comparisonSignal: listening.signal,
        comparison: shown,
        summary: false,
        fileMarks: marksFor,
        markdownHoldMs: FIRST_SCREEN_MS,
        ...(docs
          ? { group: DOCS_GROUP, ...DOCS_DRAWING, emptyText: "No documents changed in this stack." }
          : {
              ...CHANGES_DRAWING,
              openFile: (/** @type {string} */ path) =>
                open({ number, tab: "changes", file: path, stack: true }),
            }),
      });
      if (!owns()) {
        mounted?.dispose?.();
        return;
      }
      handle = mounted;
      if (tab === "changes" && file) {
        handle?.scrollToFile?.(file);
      }
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
        if (comparisonAction(drawn?.key ?? null, envelope) === "show") {
          drawn = envelope?.comparison ?? null;
        }
        tab = shownTab(routeTab, envelope);
        paintHeader();
        paintTabs();
        paintStatus(model.error);
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
    tab = shownTab(next, envelope);
    file = "";
    paintTabs();
    void paintBody();
  }

  /** @param {string} path */
  function showFile(path) {
    routeTab = "changes";
    tab = "changes";
    file = path;
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

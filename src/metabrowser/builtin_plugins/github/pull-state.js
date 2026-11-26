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
 * The states in the order a stack's members run from its top to its base: drafts at the top,
 * still being written, then open ones, then merged ones at the base, then closed ones, which
 * left it. A stack's tally counts them in this order, "5 Pulls Draft · 2 Pulls Open · 2 Pulls
 * Merged", the owner's (docs/design-system.md, "The Stack Page").
 *
 * @type {ReadonlyArray<PullState>}
 */
export const STACK_STATE_ORDER = Object.freeze(
  /** @type {PullState[]} */ (["draft", "open", "merged", "closed"]),
);

// The four shapes, Lucide v1.17.0 (ISC; https://lucide.dev), by Lucide id. Only a GitHub
// repository's page draws them, so they arrive with this code: in static/icons.js they were 251
// compressed bytes of every folder's startup scripts (check_startup_scripts, 2026-11-03).
const STROKE =
  'viewBox="0 0 24 24" fill="none" stroke="currentColor" ' +
  'stroke-width="2" stroke-linecap="round" stroke-linejoin="round"';
/** @type {Readonly<Record<string, string>>} */
const GLYPHS = Object.freeze({
  gitPullRequest: // Lucide `git-pull-request`
  `<svg ${STROKE}><circle cx="18" cy="18" r="3"/><circle cx="6" cy="6" r="3"/><path d="M13 6h3a2 2 0 0 1 2 2v7"/><line x1="6" x2="6" y1="9" y2="21"/></svg>`,
  gitPullRequestDraft: // Lucide `git-pull-request-draft`
  `<svg ${STROKE}><circle cx="18" cy="18" r="3"/><circle cx="6" cy="6" r="3"/><path d="M18 6V5"/><path d="M18 11v-1"/><line x1="6" x2="6" y1="9" y2="21"/></svg>`,
  gitMerge: // Lucide `git-merge`
  `<svg ${STROKE}><circle cx="18" cy="18" r="3"/><circle cx="6" cy="6" r="3"/><path d="M6 21V9a9 9 0 0 0 9 9"/></svg>`,
  gitPullRequestClosed: // Lucide `git-pull-request-closed`
  `<svg ${STROKE}><circle cx="6" cy="6" r="3"/><path d="M6 9v12"/><path d="m21 3-6 6"/><path d="m21 9-6-6"/><path d="M18 11.5V15"/><circle cx="18" cy="18" r="3"/></svg>`,
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

/**
 * What the repository's lists of pull requests last said of each row, by source and number:
 * its state, when GitHub last updated it, and its title. The Pulls tab writes it as rows
 * arrive, and a page writes its own record back over it when the record is fresher
 * (`noteRecord`); a page reads it, so a cached record older than the list paints the list's
 * state at once, a page with no record yet titles its cold header as the record will be
 * titled, and a stack menu draws each member's state.
 *
 * An answer takes back what the entries claim of the rows it no longer holds and would hold
 * in that state (`listHolds`): a pull request the Open list noted open and then left out, as
 * it does once the pull request merges or closes, is forgotten, where it had stayed open and a
 * stack menu drew it with the Open icon and named it "Open" (mb-as06). A row the list's
 * prefix only scrolled past is forgotten too, which costs its cold title and nothing a reader
 * sees as wrong. A merged entry stays, since a merge is never undone.
 *
 * @type {Map<string, Map<number, {state: PullState, updatedAt: string, title: string | null}>>}
 */
const listedStates = new Map();
// A source is a served repository: a page has one, and a few at most across a session.
const LISTED_SOURCES = 4;

/** The entries of *source*, made, letting the oldest source go, when it has none.
 * @param {string} source */
function heldFor(source) {
  let held = listedStates.get(source);
  if (held === undefined) {
    held = new Map();
    listedStates.set(source, held);
    for (const oldest of listedStates.keys()) {
      if (listedStates.size <= LISTED_SOURCES) {
        break;
      }
      listedStates.delete(oldest);
    }
  }
  return held;
}

/**
 * Whether *list* holds a pull request in *state*: the filters of `pull_list_refresh.py`'s
 * `_FILTERS`, where Open holds open and draft ones, Closed closed and merged ones, and All
 * every one.
 *
 * @param {string} list
 * @param {PullState} state
 */
function listHolds(list, state) {
  if (list === "open") {
    return state === "open" || state === "draft";
  }
  return list === "all" || (list === "closed" && (state === "closed" || state === "merged"));
}

/**
 * Note *list*'s answer for *source*: its rows, each replacing what an older answer said of
 * it, and the end of every entry, merged ones aside, whose state *list* would hold but whose
 * row this answer does not. A row GitHub updated before its entry was is older news, and
 * replaces nothing.
 *
 * @param {string} source
 * @param {string} list The filter the answer is for: "open", "closed", or "all".
 * @param {{number: number, state: PullState, updatedAt: string | null, title?: string}[]} rows
 */
export function noteListed(source, list, rows) {
  const held = heldFor(source);
  const holds = new Set();
  for (const row of rows) {
    holds.add(row.number);
    const entry = held.get(row.number);
    if (row.updatedAt === null || (entry !== undefined && entry.updatedAt > row.updatedAt)) {
      continue;
    }
    held.set(row.number, {
      state: row.state,
      updatedAt: row.updatedAt,
      title: typeof row.title === "string" && row.title !== "" ? row.title : null,
    });
  }
  for (const [number, entry] of held) {
    if (entry.state !== "merged" && !holds.has(number) && listHolds(list, entry.state)) {
      held.delete(number);
    }
  }
}

/**
 * Note a page's own record of a pull request back over what a list said of it, when the
 * record is fresher, so a stack menu on another page draws the state the record holds. A
 * merged record is noted where no list has said anything, since nothing can make it stale;
 * any other is not, as only a list's answer can take an entry back once it goes stale.
 *
 * @param {string} source
 * @param {Record<string, any>} pull GitHub's pull request, as a record holds it.
 */
export function noteRecord(source, pull) {
  if (!Number.isInteger(pull.number) || typeof pull.updated_at !== "string") {
    return;
  }
  const state = displayState(pull);
  const entry = listedStates.get(source)?.get(pull.number);
  if (entry === undefined ? state !== "merged" : !(pull.updated_at > entry.updatedAt)) {
    return;
  }
  heldFor(source).set(pull.number, {
    state,
    updatedAt: pull.updated_at,
    title:
      typeof pull.title === "string" && pull.title !== "" ? pull.title : (entry?.title ?? null),
  });
}

/**
 * What the list said of *number*, or null.
 *
 * @param {string | null} source
 * @param {number} number
 */
export function listedState(source, number) {
  return source === null ? null : (listedStates.get(source)?.get(number) ?? null);
}

/**
 * What the lists said of *number* for a page that does not know its source yet, as a page
 * with no record does not: the row of the one source that lists it, or null where none does
 * or more than one does, since a number names a pull request only within its repository.
 *
 * @param {number} number
 */
export function listedAnywhere(number) {
  /** @type {{state: PullState, updatedAt: string, title: string | null} | null} */
  let found = null;
  for (const held of listedStates.values()) {
    const row = held.get(number);
    if (row === undefined) {
      continue;
    }
    if (found !== null) {
      return null;
    }
    found = row;
  }
  return found;
}

/**
 * *pull* with the list's state when the list saw a later update than *pull* did, so the
 * state shown is the fresher of the two. GitHub's `updated_at` and the list's
 * `updatedAt` are the same timestamp (pull_freshness.py). Pure.
 *
 * @param {Record<string, any>} pull
 * @param {{state: PullState, updatedAt: string} | null | undefined} listed
 * @returns {Record<string, any>}
 */
export function withListedState(pull, listed) {
  if (
    listed == null ||
    typeof pull.updated_at !== "string" ||
    !(listed.updatedAt > pull.updated_at)
  ) {
    return pull;
  }
  return {
    ...pull,
    state: listed.state === "open" || listed.state === "draft" ? "open" : "closed",
    draft: listed.state === "draft",
    merged: listed.state === "merged",
  };
}

/** The glyphs, each parsed once: a list has a thousand rows and four shapes. */
/** @type {Map<string, Element | null>} */
const glyphs = new Map();

/** @param {PullState} state */
function glyph(state) {
  let shape = glyphs.get(state);
  if (shape === undefined) {
    const markup = GLYPHS[PULL_STATES[state].icon] ?? "";
    shape = new DOMParser().parseFromString(markup, "text/html").body.firstElementChild;
    glyphs.set(state, shape);
  }
  return shape === null ? null : document.importNode(shape, true);
}

/**
 * The state's icon: this module's constant, not the pull request's text. Browser only.
 *
 * Named by default, for a row, where nothing else says the state: its accessible name, and
 * no tooltip, since the Pulls column has none (docs/design-system.md, "Tooltips Add
 * Information"). A badge passes `named: false`, as its own text is the name.
 *
 * @param {PullState} state
 * @param {{named?: boolean}} [options]
 */
export function pullStateIcon(state, options = {}) {
  const icon = document.createElement("span");
  icon.className = "github-pull-state-icon";
  icon.dataset.state = state;
  if (options.named === false) {
    icon.setAttribute("aria-hidden", "true");
  } else {
    icon.setAttribute("role", "img");
    icon.setAttribute("aria-label", PULL_STATES[state].label);
  }
  const shape = glyph(state);
  if (shape !== null) {
    icon.append(shape);
  }
  return icon;
}

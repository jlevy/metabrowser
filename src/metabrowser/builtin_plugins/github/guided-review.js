// Loaded when Guided Review opens. Only the visible step asks for excerpts.

/**
 * @typedef {{op: "add" | "del" | "context", text: string}} Line
 * @typedef {{old_start: number, old_count: number, new_start: number, new_count: number,
 *   heading: string | null, lines: Line[]}} Hunk
 * @typedef {{path: string, state: string, href: string | null, hunks: Hunk[],
 *   truncated: boolean}} Reference
 * @typedef {(body: HTMLElement, change: Record<string, unknown>,
 *   patch: {hunks: Hunk[], truncated: boolean}) => {dispose: () => void}} DrawPatch
 *   The diff plugin's `mountFilePatch`, bound to the SDK: a file's hunks as Changes draws
 *   them.
 * @typedef {{merge_base: string | null, head: string}} Pins
 * @typedef {{guide: Pins, current: Pins, github_newer: boolean,
 *   history: "ahead" | "rewritten" | "unavailable", commit_count: number | null,
 *   commits: {sha: string, subject: string}[], changed_paths: string[] | null,
 *   changed_steps: number[] | null}} Staleness What a stale guide was written for and what
 *   changed since (`_staleness` in guided_review.py). The page says only whether its steps
 *   may not match; the rest is for an agent that brings the guide up to date.
 * @typedef {{state: "ready" | "stale", record_revision: string, step: number,
 *   step_count: number, titles: string[], title: string, note: string, references: Reference[],
 *   stale?: Staleness, assets?: unknown}} Step
 * @typedef {{state: "absent" | "invalid" | "comparison_unavailable" |
 *   "description_truncated" | "step_not_found" | "not_cached", record_revision: string | null,
 *   message?: string, stale?: Staleness}} Refusal
 * @typedef {"unchanged" | "changed" | "unknown"} Change Whether a reference's file changed
 *   since the guide was written: "unknown" when the guide is out of date and what changed
 *   could not be read.
 * @typedef {Step | Refusal | {state: "loading" | "preview" | "error" | "updated"}} GuideState
 */

/**
 * The guide's place and its reads. Step 0 is the overview, the description the page
 * draws itself; steps 1 to `step_count` are the guide's. The overview shows the answer
 * for step 1, whose step titles list the guide, so the first step the reader moves to is
 * already in hand. Answers with a step are kept for the record revision they were read for.
 * A step whose read was refused or failed keeps the guide's steps, from the last answer that
 * had them, so the reader can still move, and is read again when the reader returns to it.
 *
 * @param {{
 *   read(step: number, signal: AbortSignal): Promise<Step | Refusal>,
 *   render(state: GuideState, at: number, steps: number): void,
 * }} deps *render* is told the guide's step count, 0 while no answer has had a step.
 */
export function createGuideNavigation(deps) {
  /** @type {string | null | undefined} */
  let revision;
  let headMoved = false;
  let selected = 0;
  /** The step count of the last answer of this revision that had a step, which bounds a move. */
  let count = 0;
  /** @type {Map<number, Step | Refusal>} */
  let answers = new Map();
  /** @type {AbortController | null} */
  let pending = null;
  let disposed = false;

  /** @param {string} expected */
  async function load(expected) {
    pending?.abort();
    const at = selected;
    const asked = Math.max(at, 1);
    const kept = answers.get(asked);
    if (kept !== undefined) {
      pending = null;
      deps.render(kept, at, count);
      return;
    }
    const request = new AbortController();
    pending = request;
    deps.render({ state: "loading" }, at, count);
    try {
      let result = await deps.read(asked, request.signal);
      if (request.signal.aborted) {
        return;
      }
      if (result.record_revision === expected && result.state === "step_not_found" && asked > 1) {
        selected = 1;
        result = await deps.read(1, request.signal);
      }
      if (request.signal.aborted) {
        return;
      }
      if (result.record_revision !== expected) {
        deps.render({ state: "updated" }, selected, count);
        return;
      }
      if ("step" in result) {
        answers.set(Math.max(selected, 1), result);
        count = result.step_count;
      }
      deps.render(result, selected, count);
    } catch {
      if (!request.signal.aborted) {
        deps.render({ state: "error" }, selected, count);
      }
    } finally {
      if (pending === request) {
        pending = null;
      }
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
    if (target >= 0 && target <= count) {
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
      // A head GitHub reports past the record's is the server's to read: it answers the
      // guide's steps with what is out of date.
      void load(nextRevision);
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
  description_truncated: "The cached description is incomplete and contains no complete guide.",
  step_not_found: "This review step is unavailable.",
  not_cached: "The full pull request is unavailable.",
  preview: "The guide needs the full pull request.",
  updated: "The pull request updated. Reopen the guide to read the new version.",
  error: "Could not load the guide. Reopen the tab to try again.",
});

// One step of a guide whose other steps read: the reader can move on, and a step whose read
// was refused or failed is read again when chosen again.
const STEP_MESSAGES = Object.freeze({
  refused: "This step could not be read. Choose it again to retry.",
  error: "Could not load this step. Choose it again to retry.",
});

const REFERENCE_MESSAGES = Object.freeze({
  manifest_truncated: "This path is outside the available changed-file list.",
  path_not_changed: "This path is not in the comparison.",
  diff_unavailable: "This file's diff is unavailable.",
  range_unavailable: "This range is not within a single available diff hunk.",
  excerpt_too_large: "This excerpt is too large to show here.",
  // Past a step's budget for whole files (MAX_STEP_PATCH_BYTES in guided_review.py), or past
  // what the diff source reads in one run beside the step's other files.
  patch_too_large: "This file's diff is too large to show in this step.",
});

// A reference of an out-of-date guide, read at the pull request's current head, whose file
// changed since the guide was written: a note in its place when it no longer resolves, and
// above its excerpt when it does. One whose change is unknown says only what may be so.
const CHANGED_REFERENCE_MESSAGES = Object.freeze({
  ready: "This file changed after the guide was written.",
  range_unavailable: "These lines changed after the guide was written.",
  path_not_changed: "This file is no longer in the pull request's changes.",
});
const UNKNOWN_REFERENCE_MESSAGES = Object.freeze({
  range_unavailable: "These lines may have changed since the guide was written.",
  path_not_changed: "This file is no longer in the pull request's changes.",
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
 * (docs/design-system.md, "Serif Is for Documents"). The text is the author's, set as text.
 *
 * @param {HTMLElement} prose The `.kpress-prose` element the caller fills.
 */
function proseHost(prose) {
  const article = element("article", "", "kpress kpress-inert");
  article.append(prose);
  const host = element("div", "", "metabrowser-kpress-host");
  host.append(article);
  // A text in a card, as the page sets a description's: its inset and edge margins are
  // `.github-pull-text`'s (styles.css).
  const text = element("div", "", "github-pull-text github-pull-guide-prose chrome-prose");
  text.append(host);
  return text;
}

/**
 * One reference as Changes draws a changed file: the diff plugin's card and bar, and its
 * hunks drawn by the diff plugin itself (`mountFilePatch`), each under its header bar with
 * its long changed runs behind fold bars, in the plugin's type, gutter, change fills, and
 * syntax (docs/design-system.md, "Diffs"). A range is one hunk of its own lines; a file
 * named alone is its whole patch.
 *
 * @param {Reference} reference @param {(path: string) => void} open
 * @param {Change} change Whether the file changed after the guide was written.
 * @param {DrawPatch | null} drawPatch Null when the diff plugin did not load.
 * @param {Array<{dispose: () => void}>} drawn Where each drawn patch is kept for disposal.
 */
function renderReference(reference, open, change, drawPatch, drawn) {
  const section = element("section", "", "diff-file github-pull-guide-reference");
  const bar = element("div", "", "diff-file-bar github-pull-guide-reference-header");
  const name = element("span", "", "diff-file-toggle");
  name.append(element("span", reference.path, "diff-file-path"));
  bar.append(name);
  if (reference.href !== null) {
    const full = document.createElement("a");
    full.className = "diff-file-view";
    full.href = reference.href;
    full.textContent = "Open full diff";
    full.setAttribute("aria-label", `Open full diff for ${reference.path}`);
    full.addEventListener("click", (event) => {
      if (
        event.button === 0 &&
        !event.metaKey &&
        !event.ctrlKey &&
        !event.shiftKey &&
        !event.altKey
      ) {
        event.preventDefault();
        open(reference.path);
      }
    });
    bar.append(full);
  }
  section.append(bar);
  if (reference.state === "ready" && change === "changed") {
    section.append(
      element("p", CHANGED_REFERENCE_MESSAGES.ready, "github-pull-quiet github-pull-guide-changed"),
    );
  }
  if (reference.state === "ready" && reference.hunks.length === 0) {
    // A rename, a mode change, or a binary file: a change with no text to show.
    section.append(element("p", "This file has no text changes to show.", "github-pull-quiet"));
  } else if (reference.state === "ready" && drawPatch !== null) {
    const body = element("div", "", "diff-file-body github-pull-guide-excerpt");
    body.setAttribute("role", "group");
    body.setAttribute("aria-label", `Diff excerpt for ${reference.path}`);
    section.append(body);
    const side = { path: reference.path };
    drawn.push(
      drawPatch(
        body,
        { id: reference.path, old: side, new: side },
        { hunks: reference.hunks, truncated: reference.truncated },
      ),
    );
  } else {
    /** @type {Readonly<Record<string, string | undefined>>} */
    const said =
      change === "changed"
        ? CHANGED_REFERENCE_MESSAGES
        : change === "unknown"
          ? UNKNOWN_REFERENCE_MESSAGES
          : {};
    /** @type {Readonly<Record<string, string | undefined>>} */
    const ordinary = REFERENCE_MESSAGES;
    const message =
      reference.state === "ready"
        ? REFERENCE_MESSAGES.diff_unavailable
        : (said[reference.state] ?? ordinary[reference.state]);
    section.append(element("p", message ?? "This excerpt is unavailable.", "github-pull-quiet"));
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
 * Whether *path*, which a step cites, changed since a stale guide was written.
 *
 * @param {Staleness | null | undefined} stale @param {string} path
 * @returns {Change}
 */
function changeOf(stale, path) {
  if (!outdated(stale)) {
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
 * @returns {HTMLElement | null}
 */
export function staleNotice(stale) {
  if (!outdated(stale)) {
    return null;
  }
  if (stale.changed_steps !== null && stale.changed_steps.length === 0) {
    const line = element("p", OUTDATED.unchanged, "github-pull-quiet github-pull-guide-stale");
    line.setAttribute("role", "status");
    return line;
  }
  const warning = stale.changed_steps === null ? OUTDATED.unknown : OUTDATED.marked;
  const box = element(
    "div",
    `${warning} ${OUTDATED.remedy}`,
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

/**
 * @param {HTMLElement} host
 * @param {HTMLElement} introduction The description's card, which the page draws and keeps
 *   current: the guide's step 0, shown while it is the step and while no step can be.
 * @param {number} number
 * @param {{
 *   open: (path: string) => void,
 *   loadStyles: (assets: unknown) => Promise<unknown>,
 *   loadDrawPatch: () => Promise<DrawPatch>,
 * }} deps *open* goes to a file's Changes address. *loadStyles* loads the stylesheets the
 *   guide is drawn in: KPress's, from the manifest a ready step carries, and the diff
 *   plugin's; the guide waits for them, as a description does. *loadDrawPatch* loads the
 *   diff plugin's file renderer, which draws the excerpts.
 */
export function mountGuidedReview(host, introduction, number, deps) {
  const { open, loadStyles, loadDrawPatch } = deps;
  /** @type {Promise<unknown> | null} */
  let styles = null;
  /** @type {Promise<DrawPatch | null> | null} */
  let drawer = null;
  /** @type {DrawPatch | null} */
  let drawPatch = null;
  /** The patches the shown step drew, disposed when another is drawn or the guide ends. */
  /** @type {Array<{dispose: () => void}>} */
  let drawn = [];
  const undraw = () => {
    for (const patch of drawn) {
      patch.dispose();
    }
    drawn = [];
  };
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
  const arrows = element("span", "", "github-pull-guide-arrows");
  arrows.append(previous, status, next);
  outlineHead.append(badge, arrows);
  const list = element("ol", "", "github-pull-guide-steps");
  outline.append(outlineHead, list);
  outline.hidden = true;
  const detail = element("section", "", "github-pull-guide-step");
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
  host.replaceChildren(outdatedNote, outline, introduction, detail, notice, pager);
  /** @param {Staleness | null | undefined} stale */
  const showStale = (stale) => {
    const said = stale ? staleNotice(stale) : null;
    outdatedNote.hidden = said === null;
    outdatedNote.replaceChildren(...(said === null ? [] : [said]));
  };
  /** @type {string[]} */
  let titles = [];
  /** @type {number[]} */
  let changedSteps = [];
  /** @param {number} at */
  const nameOf = (at) => stepName(at, titles[at - 1] ?? "");
  /**
   * The step list's rows, built once for each list of titles and updated in place, so the
   * row a reader activated keeps focus, as the tab bar keeps its links across paints.
   *
   * @type {{key: string | null, rows: {link: HTMLButtonElement, mark: HTMLElement}[]}}
   */
  let built = { key: null, rows: [] };

  /** @param {number} at */
  function paintOutline(at) {
    outline.hidden = titles.length === 0;
    const count = titles.length;
    // What is shown, by name: the overview, or a step and how many there are.
    status.textContent = placeName(at, count);
    previous.disabled = at <= 0;
    next.disabled = at >= count;
    const key = JSON.stringify(titles);
    if (built.key !== key) {
      built = {
        key,
        rows: [OVERVIEW, ...titles].map((title, index) => {
          const link = document.createElement("button");
          link.type = "button";
          link.className = "github-pull-guide-steps-link";
          link.append(
            element("span", index === 0 ? "" : String(index), "github-pull-guide-steps-number"),
            element("span", title, "github-pull-guide-steps-title"),
          );
          link.addEventListener("click", () => navigation.go(index));
          return { link, mark: changedMark() };
        }),
      };
      list.replaceChildren(
        ...built.rows.map(({ link }) => {
          const item = element("li", "", "github-pull-guide-steps-item");
          item.append(link);
          return item;
        }),
      );
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
    back.hidden = at <= 0;
    onward.hidden = at >= count;
    backLabel.textContent = at > 0 ? nameOf(at - 1) : "";
    onwardLabel.textContent = at < count ? nameOf(at + 1) : "";
    // The arrows say where they go when pointed at, in the same words as the way on and back.
    previous.dataset.tipText = at > 0 ? `Previous: ${nameOf(at - 1)}` : "Previous step";
    next.dataset.tipText = at < count ? `Next: ${nameOf(at + 1)}` : "Next step";
  }

  const navigation = createGuideNavigation({
    async read(step, signal) {
      const response = await fetch(
        `/api/plugin/github/guided-review?number=${number}&step=${step}`,
        {
          signal,
          cache: "no-store",
        },
      );
      if (!response.ok) {
        throw new Error("Could not read the guide");
      }
      const result = await response.json();
      if ("step" in result) {
        // A failed stylesheet leaves the text readable in the page's own type.
        if (result.assets !== undefined) {
          styles ??= loadStyles(result.assets).catch((error) => {
            console.warn("metabrowser github: the guide's text styles did not load", error);
          });
        }
        // Without the diff plugin a step still reads, and says its excerpts are unavailable.
        drawer ??= loadDrawPatch().catch((error) => {
          console.warn("metabrowser github: the diff plugin did not load for the guide", error);
          return null;
        });
        const [, loaded] = await Promise.all([styles, drawer]);
        drawPatch = loaded;
      }
      return result;
    },
    render(state, at, steps) {
      undraw();
      if (state.state === "loading") {
        // The overview is the page's own, so it shows at once; a step waits for its read.
        introduction.hidden = at !== 0;
        pager.hidden = true;
        previous.disabled = next.disabled = true;
        notice.hidden = true;
        if (at === 0) {
          detail.replaceChildren();
          return;
        }
        const wait = element("div", "", "mb-delayed-loading");
        wait.setAttribute("role", "status");
        wait.setAttribute("aria-label", "Loading the review step");
        const skeleton = element("div", "", "recent-loading github-pull-loading");
        skeleton.setAttribute("aria-hidden", "true");
        wait.append(skeleton);
        detail.replaceChildren(wait);
        return;
      }
      const available = "step" in state;
      if (!available && steps > 0 && state.state !== "updated") {
        // One step's read was refused or failed: the guide keeps its steps and the notice
        // the last answer drew, and the refusal takes the step's place, under the list.
        // The step is read again when the reader returns to it.
        paintOutline(at);
        pager.hidden = false;
        introduction.hidden = at !== 0;
        detail.replaceChildren();
        notice.hidden = false;
        notice.textContent =
          state.state === "invalid"
            ? (state.message ?? "This guide is invalid.")
            : state.state === "error"
              ? STEP_MESSAGES.error
              : STEP_MESSAGES.refused;
        return;
      }
      // A refusal says one thing, its own reason, whatever a stale guide's answer carries.
      showStale(available ? state.stale : null);
      if (!available) {
        titles = [];
        changedSteps = [];
        paintOutline(0);
        introduction.hidden = false;
        pager.hidden = true;
        detail.replaceChildren();
        notice.hidden = false;
        notice.textContent =
          state.state === "invalid"
            ? (state.message ?? "This guide is invalid.")
            : MESSAGES[state.state];
        return;
      }
      notice.hidden = true;
      titles = state.titles;
      changedSteps = outdated(state.stale) ? (state.stale.changed_steps ?? []) : [];
      paintOutline(at);
      pager.hidden = false;
      introduction.hidden = at !== 0;
      if (at === 0) {
        detail.replaceChildren();
        return;
      }
      const step = element("div", "", "kpress-prose");
      step.append(
        element("h2", state.title, "github-pull-guide-title"),
        element("p", state.note, "github-pull-guide-commentary"),
      );
      const stale = state.stale;
      const references = element("div", "", "metabrowser-diff-host github-pull-guide-references");
      references.append(
        ...state.references.map((reference) =>
          renderReference(reference, open, changeOf(stale, reference.path), drawPatch, drawn),
        ),
      );
      // A step is a card, as Conversation draws a comment, headed as the author's guided
      // review so it reads apart from the discussion.
      const head = element("div", "", "github-pull-card-head github-pull-guide-card-head");
      // The badge leads its label as a page header's state badge leads its line, a gap
      // apart (`.github-pull-guide-card-head`), never a space's width.
      const place = element("span", placeName(state.step, state.step_count));
      if (changedSteps.includes(state.step)) {
        place.append(" · ", changedMark());
      }
      head.append(guideBadge(), place);
      const card = element(
        "section",
        "",
        "page-card github-pull-card github-pull-event github-pull-guide-card",
      );
      card.append(head, proseHost(step), references);
      detail.replaceChildren(card);
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
      undraw();
    },
  };
}

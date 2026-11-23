// Loaded when Guided PR opens. Only the visible step asks for excerpts.

/**
 * @typedef {{old: number | null, new: number | null, op: "add" | "del" | "context", text: string}} Row
 * @typedef {{path: string, state: string, href: string | null, rows: Row[]}} Reference
 * @typedef {{state: "ready", record_revision: string, summary: string, overview: string,
 *   step: number, step_count: number, title: string, note: string,
 *   references: Reference[]}} Step
 * @typedef {{state: "absent" | "invalid" | "stale" | "comparison_unavailable" |
 *   "description_truncated" | "step_not_found" | "not_cached", record_revision: string | null,
 *   message?: string}} Refusal
 * @typedef {Step | Refusal | {state: "loading" | "preview" | "error" | "updated"}} GuideState
 */

/**
 * @param {{
 *   read(step: number, signal: AbortSignal): Promise<Step | Refusal>,
 *   render(state: GuideState): void,
 * }} deps
 */
export function createGuideNavigation(deps) {
  /** @type {string | null | undefined} */
  let revision;
  let headMoved = false;
  let selected = 1;
  /** @type {Step | null} */
  let ready = null;
  /** @type {AbortController | null} */
  let pending = null;
  let disposed = false;

  /** @param {string} expected */
  async function load(expected) {
    pending?.abort();
    const request = new AbortController();
    pending = request;
    ready = null;
    deps.render({ state: "loading" });
    try {
      let result = await deps.read(selected, request.signal);
      if (request.signal.aborted) {
        return;
      }
      if (
        result.record_revision === expected &&
        result.state === "step_not_found" &&
        selected > 1
      ) {
        selected = 1;
        result = await deps.read(selected, request.signal);
      }
      if (request.signal.aborted) {
        return;
      }
      if (result.record_revision !== expected) {
        deps.render({ state: "updated" });
        return;
      }
      ready = result.state === "ready" ? result : null;
      deps.render(result);
    } catch {
      if (!request.signal.aborted) {
        deps.render({ state: "error" });
      }
    } finally {
      if (pending === request) {
        pending = null;
      }
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
      if (nextRevision === null || moved) {
        pending?.abort();
        ready = null;
        deps.render(
          moved ? { state: "stale", record_revision: nextRevision } : { state: "preview" },
        );
        return;
      }
      void load(nextRevision);
    },
    /** @param {-1 | 1} by */
    move(by) {
      if (ready === null || !revision) {
        return;
      }
      const target = ready.step + by;
      if (target >= 1 && target <= ready.step_count) {
        selected = target;
        void load(revision);
      }
    },
    dispose() {
      disposed = true;
      pending?.abort();
      ready = null;
    },
  };
}

const MESSAGES = Object.freeze({
  absent: "This pull request has no guide.",
  stale: "This guide is out of date. Its author needs to update it for the current comparison.",
  comparison_unavailable:
    "The comparison is unavailable. Fetch it from Changes, then reopen the guide.",
  description_truncated: "The cached description is incomplete and contains no complete guide.",
  step_not_found: "This review step is unavailable.",
  not_cached: "The full pull request is unavailable.",
  preview: "The guide needs the full pull request.",
  updated: "The pull request updated. Reopen the guide to read the new version.",
  error: "Could not load the guide. Reopen the tab to try again.",
});

const REFERENCE_MESSAGES = Object.freeze({
  manifest_truncated: "This path is outside the available changed-file list.",
  path_not_changed: "This path is not in the comparison.",
  diff_unavailable: "The diff for this range is unavailable.",
  range_unavailable: "This range is not within a single available diff hunk.",
  excerpt_too_large: "This excerpt is too large to show here.",
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

/** @param {Reference} reference @param {(path: string) => void} open */
function renderReference(reference, open) {
  const section = element("section", "", "github-pull-guide-reference");
  const header = element("div", "", "github-pull-guide-reference-header");
  header.append(element("code", reference.path));
  if (reference.href !== null) {
    const full = document.createElement("a");
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
    header.append(full);
  }
  section.append(header);
  if (reference.state === "ready") {
    const excerpt = element("pre", "", "github-pull-guide-excerpt");
    excerpt.tabIndex = 0;
    excerpt.setAttribute("aria-label", `Diff excerpt for ${reference.path}`);
    for (const row of reference.rows) {
      const line = element("span", "", "github-pull-guide-line");
      line.dataset.op = row.op;
      line.append(
        element("span", String(row.old ?? ""), "github-pull-guide-line-number"),
        element("span", String(row.new ?? ""), "github-pull-guide-line-number"),
        element("span", row.op === "add" ? "+" : row.op === "del" ? "−" : " "),
        // A row is one line of someone's code, and the shell's highlighter would take it for
        // a snippet in some language and paint a block of its own into the row. The row owns
        // its tint, and `no-highlight` is the shell's opt-out (`highlightCode` in app.js).
        element("code", row.text, "no-highlight"),
      );
      excerpt.append(line);
    }
    section.append(excerpt);
  } else if (reference.state !== "file") {
    const message =
      REFERENCE_MESSAGES[/** @type {keyof typeof REFERENCE_MESSAGES} */ (reference.state)];
    section.append(element("p", message ?? "This excerpt is unavailable.", "github-pull-quiet"));
  }
  return section;
}

/**
 * @param {HTMLElement} host
 * @param {number} number
 * @param {(path: string) => void} open
 */
export function mountGuidedPR(host, number, open) {
  const overview = element("div", "", "github-pull-guide-overview");
  const feature = element("p");
  const architecture = element("p");
  overview.append(
    element("h2", "What this changes", "section-heading"),
    feature,
    element("h2", "Architecture", "section-heading"),
    architecture,
  );
  const controls = element("div", "", "github-pull-guide-controls");
  const previous = document.createElement("button");
  const next = document.createElement("button");
  previous.type = next.type = "button";
  previous.className = next.className = "btn";
  previous.textContent = "Previous";
  next.textContent = "Next";
  const status = element("span", "", "github-pull-quiet");
  status.setAttribute("role", "status");
  controls.append(previous, status, next);
  const detail = element("section", "", "github-pull-guide-step");
  const notice = element("p", "", "github-pull-quiet");
  notice.setAttribute("role", "status");
  host.append(overview, controls, detail, notice);

  const navigation = createGuideNavigation({
    async read(step, signal) {
      const response = await fetch(`/api/plugin/github/guided-pr?number=${number}&step=${step}`, {
        signal,
        cache: "no-store",
      });
      if (!response.ok) {
        throw new Error("Could not read the guide");
      }
      return response.json();
    },
    render(state) {
      if (state.state === "loading") {
        previous.disabled = next.disabled = true;
        notice.hidden = true;
        const wait = element("div", "", "mb-delayed-loading");
        wait.setAttribute("role", "status");
        wait.setAttribute("aria-label", "Loading the review step");
        const skeleton = element("div", "", "recent-loading github-pull-loading");
        skeleton.setAttribute("aria-hidden", "true");
        wait.append(skeleton);
        detail.replaceChildren(wait);
        return;
      }
      const available = state.state === "ready";
      overview.hidden = controls.hidden = !available;
      if (!available) {
        previous.disabled = next.disabled = true;
        detail.replaceChildren();
        notice.hidden = false;
        notice.textContent =
          state.state === "invalid"
            ? (state.message ?? "This guide is invalid.")
            : MESSAGES[state.state];
        return;
      }
      notice.hidden = true;
      feature.textContent = state.summary;
      architecture.textContent = state.overview;
      status.textContent = `Step ${state.step} of ${state.step_count}`;
      previous.disabled = state.step <= 1;
      next.disabled = state.step >= state.step_count;
      detail.replaceChildren(
        element("h2", state.title, "section-heading"),
        element("p", state.note, "github-pull-guide-commentary"),
        ...state.references.map((reference) => renderReference(reference, open)),
      );
    },
  });
  overview.hidden = controls.hidden = true;
  previous.addEventListener("click", () => navigation.move(-1));
  next.addEventListener("click", () => navigation.move(1));
  return navigation;
}

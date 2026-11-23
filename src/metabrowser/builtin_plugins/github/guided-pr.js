// Loaded when Guided PR opens. Only the visible step asks for excerpts.

/**
 * @typedef {{old: number | null, new: number | null, op: "add" | "del" | "context", text: string}} Row
 * @typedef {{path: string, state: string, href: string | null, rows: Row[]}} Reference
 * @typedef {{state: "ready", record_revision: string, step: number, step_count: number,
 *   title: string, note: string, references: Reference[], assets?: unknown}} Step
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
  const text = element("div", "", "github-pull-guide-prose chrome-prose");
  text.append(host);
  return text;
}

/**
 * One reference as the diff plugin draws a changed file (`renderFileSection` and
 * `renderUnifiedLine` in builtin_plugins/diff/diff-view.js): its card, bar, and unified rows,
 * in the plugin's own classes inside `.metabrowser-diff-host`, so an excerpt has the same
 * type, row height, gutter, and change fills as Changes (docs/design-system.md, "Diffs").
 * Rows are text in spans, not `pre code`, which the shell's highlighter would take for a
 * snippet; the excerpt shows the author's selection, not the plugin's syntax tokens.
 *
 * @param {Reference} reference @param {(path: string) => void} open
 */
function renderReference(reference, open) {
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
  if (reference.state === "ready") {
    const body = element("div", "", "diff-file-body github-pull-guide-excerpt");
    body.setAttribute("role", "group");
    body.setAttribute("aria-label", `Diff excerpt for ${reference.path}`);
    for (const row of reference.rows) {
      const line = element("div", "", `diff-line diff-line-${row.op} github-pull-guide-line`);
      line.dataset.op = row.op;
      line.append(
        element("span", String(row.old ?? ""), "diff-line-number"),
        element("span", String(row.new ?? ""), "diff-line-number"),
        element("span", row.op === "add" ? "+" : row.op === "del" ? "-" : " ", "diff-line-marker"),
        element("span", row.text, "diff-line-text"),
      );
      body.append(line);
    }
    section.append(body);
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
 * @param {(assets: unknown) => Promise<unknown>} loadStyles The stylesheets the guide is
 *   drawn in: KPress's, from the manifest a ready step carries, and the diff plugin's. The
 *   guide waits for them, as a description does.
 */
export function mountGuidedPR(host, number, open, loadStyles) {
  /** @type {Promise<unknown> | null} */
  let styles = null;
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
  host.append(controls, detail, notice);

  const navigation = createGuideNavigation({
    async read(step, signal) {
      const response = await fetch(`/api/plugin/github/guided-pr?number=${number}&step=${step}`, {
        signal,
        cache: "no-store",
      });
      if (!response.ok) {
        throw new Error("Could not read the guide");
      }
      const result = await response.json();
      if (result.state === "ready" && result.assets !== undefined) {
        // A failed stylesheet leaves the text readable in the page's own type.
        styles ??= loadStyles(result.assets).catch((error) => {
          console.warn("metabrowser github: the guide's text styles did not load", error);
        });
        await styles;
      }
      return result;
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
      controls.hidden = !available;
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
      status.textContent = `Step ${state.step} of ${state.step_count}`;
      previous.disabled = state.step <= 1;
      next.disabled = state.step >= state.step_count;
      const step = element("div", "", "kpress-prose");
      step.append(
        element("h2", state.title, "github-pull-guide-title"),
        element("p", state.note, "github-pull-guide-commentary"),
      );
      const references = element("div", "", "metabrowser-diff-host github-pull-guide-references");
      references.append(...state.references.map((reference) => renderReference(reference, open)));
      detail.replaceChildren(proseHost(step), references);
    },
  });
  controls.hidden = true;
  previous.addEventListener("click", () => navigation.move(-1));
  next.addEventListener("click", () => navigation.move(1));
  return navigation;
}

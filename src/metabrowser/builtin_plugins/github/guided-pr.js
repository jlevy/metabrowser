// Loaded when Guided PR opens. Only the visible step asks for excerpts.

/**
 * @typedef {{old: number | null, new: number | null, op: "add" | "del" | "context", text: string}} Row
 * @typedef {{path: string, state: string, href: string | null, rows: Row[]}} Reference
 * @typedef {{merge_base: string | null, head: string}} Pins
 * @typedef {{guide: Pins, current: Pins, github_newer: boolean,
 *   history: "ahead" | "rewritten" | "unavailable", commit_count: number | null,
 *   commits: {sha: string, subject: string}[], changed_paths: string[] | null,
 *   changed_steps: number[] | null}} Staleness
 * @typedef {{state: "ready" | "stale", record_revision: string, step: number,
 *   step_count: number, title: string, note: string, references: Reference[],
 *   stale?: Staleness, assets?: unknown}} Step
 * @typedef {{state: "absent" | "invalid" | "stale" | "comparison_unavailable" |
 *   "description_truncated" | "step_not_found" | "not_cached", record_revision: string | null,
 *   message?: string, stale?: Staleness | null}} Refusal
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
      ready = "step" in result ? result : null;
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
      if (nextRevision === null) {
        pending?.abort();
        ready = null;
        deps.render({ state: "preview" });
        return;
      }
      // A head GitHub reports past the record's is the server's to read: it answers the
      // guide's steps with what is out of date.
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
  stale:
    "This guide was written for an earlier version of this pull request, which the local copy does not have, so its steps cannot be shown.",
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
 * @param {boolean} changed Whether the file changed after the guide was written.
 */
function renderReference(reference, open, changed) {
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
  if (changed) {
    section.append(
      element(
        "p",
        "This file changed after the guide was written. The excerpt is from the guide's revision.",
        "github-pull-quiet github-pull-guide-changed",
      ),
    );
  }
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

/** @param {string} sha */
const short = (sha) => element("code", sha.slice(0, 7));

/** @param {number} count @param {string} one */
const plural = (count, one) => `${count} ${one}${count === 1 ? "" : "s"}`;

/** @param {number[]} steps */
function stepList(steps) {
  const named = steps.map(String);
  const last = named.pop();
  return `${steps.length === 1 ? "Step" : "Steps"} ${named.length > 0 ? `${named.join(", ")} and ${last}` : last}`;
}

/**
 * What a stale guide was written for, what the pull request is now, and what changed
 * between them, as the route answers it (`_staleness` in guided_pr.py).
 *
 * @param {Staleness} stale
 * @param {number | null} stepCount
 */
export function staleNotice(stale, stepCount) {
  const box = element("div", "", "notice github-pull-notice github-pull-guide-stale");
  box.dataset.severity = "warning";
  box.setAttribute("role", "status");
  /** @param {Array<Node | string>} parts */
  const say = (parts) => {
    const paragraph = element("p");
    paragraph.append(...parts);
    box.append(paragraph);
  };
  box.append(element("p", "This guide is out of date.", "github-pull-guide-stale-title"));
  const baseMoved =
    stale.current.merge_base !== null && stale.current.merge_base !== stale.guide.merge_base;
  const headMoved = stale.current.head !== stale.guide.head;
  /** @param {Pins} pins */
  const pinned = (pins) =>
    baseMoved && pins.merge_base !== null
      ? ["head ", short(pins.head), " on merge base ", short(pins.merge_base)]
      : ["head ", short(pins.head)];
  if (headMoved || baseMoved) {
    say([
      "It was written for ",
      ...pinned(stale.guide),
      ". The pull request is now at ",
      ...pinned(stale.current),
      ".",
    ]);
  }
  if (stale.github_newer) {
    say([
      "GitHub reports a newer head than this copy of the pull request. Reload it to compare the guide with the newest commits.",
    ]);
  }
  if (headMoved && stale.history === "unavailable") {
    say(["The local copy does not have the guide's head, so the commits since are unknown."]);
  } else if (headMoved) {
    const count = stale.commit_count ?? 0;
    say([
      stale.history === "rewritten"
        ? `The guide's head is no longer in the branch's history, as after a rebase or force push. The branch has ${plural(count, "commit")} the guide's head does not:`
        : `${plural(count, "commit")} since the guide:`,
    ]);
    const list = element("ul", "", "github-pull-guide-commits");
    for (const commit of stale.commits) {
      const item = element("li");
      item.append(short(commit.sha), " ", commit.subject);
      list.append(item);
    }
    if (count > stale.commits.length) {
      list.append(element("li", `and ${plural(count - stale.commits.length, "earlier commit")}`));
    }
    box.append(list);
  }
  if (baseMoved) {
    say(["Its merge base moved, as when the base branch is merged in or the branch is rebased."]);
  }
  /** @type {Array<Node | string>} */
  const verdict = [];
  if (stale.changed_steps === null || stale.changed_paths === null) {
    verdict.push("Whether its steps still match the pull request is unknown.");
  } else if (stale.changed_steps.length === 0) {
    verdict.push("None of the files its steps cite changed, so every step still matches.");
  } else {
    const all = stepCount !== null && stale.changed_steps.length === stepCount;
    verdict.push(
      `${stepList(stale.changed_steps)} ${stale.changed_steps.length === 1 ? "cites" : "cite"} ${plural(stale.changed_paths.length, "file")} changed since: `,
    );
    stale.changed_paths.forEach((path, at) => {
      verdict.push(...(at > 0 ? [", "] : []), element("code", path));
    });
    verdict.push(
      all
        ? ". Their excerpts are from the guide's revision."
        : ". The other steps still match; the changed ones are marked.",
    );
  }
  say([...verdict, " Its author can update the guide's pins and ranges in the description."]);
  return box;
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
  // What a stale guide is out of date with leads the page, above its introduction.
  const outdated = element("div", "", "github-pull-guide-outdated");
  outdated.hidden = true;
  host.prepend(outdated);
  /** @param {Staleness | null | undefined} stale @param {number | null} count */
  const showStale = (stale, count) => {
    outdated.hidden = !stale;
    outdated.replaceChildren(...(stale ? [staleNotice(stale, count)] : []));
  };

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
      if ("step" in result && result.assets !== undefined) {
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
      const available = "step" in state;
      showStale(
        "stale" in state ? state.stale : null,
        available ? /** @type {Step} */ (state).step_count : null,
      );
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
      const changed = new Set(state.stale?.changed_paths ?? []);
      const references = element("div", "", "metabrowser-diff-host github-pull-guide-references");
      references.append(
        ...state.references.map((reference) =>
          renderReference(reference, open, changed.has(reference.path)),
        ),
      );
      // A step is a card, as Conversation draws a comment, headed as the author's guided
      // review so it reads apart from the discussion.
      const head = element("div", "", "github-pull-card-head github-pull-guide-card-head");
      head.append(
        element(
          "span",
          "Guided review",
          "file-header-badge github-pull-badge github-pull-guide-badge",
        ),
        ` Step ${state.step} of ${state.step_count}`,
      );
      if (state.stale?.changed_steps?.includes(state.step)) {
        head.append(
          " · ",
          element("span", "cites files changed since the guide", "github-pull-guide-step-changed"),
        );
      }
      const card = element(
        "section",
        "",
        "page-card github-pull-card github-pull-event github-pull-guide-card",
      );
      card.append(head, proseHost(step), references);
      detail.replaceChildren(card);
    },
  });
  controls.hidden = true;
  previous.addEventListener("click", () => navigation.move(-1));
  next.addEventListener("click", () => navigation.move(1));
  return navigation;
}

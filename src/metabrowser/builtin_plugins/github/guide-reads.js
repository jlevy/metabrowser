// A guide's step answers, read once and kept for the document, so a step a reader has seen,
// or one read ahead of them, paints with no request and no wait.
//
// A pull request's page and a stack's page read their guide's first step before the reader
// opens Guided Review, and the guide reads the steps next to the one shown
// (`createGuideNavigation`'s *prefetch*), so the step a press or an arrow goes to is in hand.
// What was read is kept for the document, not for one mount of the guide, as a comparison is
// (comparison-prefetch.js): a guide is mounted again each time its tab is drawn, and a reader
// who leaves the tab and comes back finds the steps they read where they left them.
//
// The cost, measured 2026-11-25 on this repository's pull request #845, whose guide has 18
// steps, served from a local server at a load average near 110 on 10 cores: one step's read
// took 55 to 220 ms in all, 51 to 130 ms of it the diff source's one hydrate run of the files
// the step cites, and the 18 answers were 7 to 65 KB of JSON each, 462 KB together. So a
// step shown reads at most two more, its neighbors, each one run of the diff source, and
// `GUIDE_KEPT_CHARS` holds every step of about four guides of that size, the oldest let go
// first.

/** @typedef {import("./guided-review.js").Step} Step */
/** @typedef {import("./guided-review.js").Refusal} Refusal */
/** @typedef {import("./guided-review.js").GuideSubject} GuideSubject */

// How much of the answers' JSON the document keeps across its guides, counted as that JSON
// text's characters (UTF-16 code units, the answer's `text.length` as read), which is what
// the cost above was measured in. It is not the heap the parsed answers take, which this does
// not measure.
export const GUIDE_KEPT_CHARS = 2_000_000;

// How long a document a step cites whole waits, out of sight, for its rendered layer before
// the step shows without it (the diff view's `markdownHoldMs`). A step is shown once its
// documents are drawn as they stay, so a hold shorter than the render would show the step
// with a document's bar alone and then add the rendering, a change of height under the
// reader. The rendered route answers, or refuses, within the Markdown child's render
// deadline (`INERT_RENDER_DEADLINE_MS` in diff/markdown_projection_worker.py), so this is
// that deadline and a second more for the request around it; the documents of #845's guide
// rendered in 12 to 120 ms each once the child was warm, measured with the step reads above.
export const GUIDE_DOCUMENT_HOLD_MS = 6_000;

// How long Guided Review's overview waits, out of sight, for the description it shows above
// the guide to show as it will stay (`introductionReady` in pull-page.js), before it shows with
// the description's placeholder instead, which the render replaces when it comes. The
// description renders in the same Markdown child, under the same deadline, as a document's
// rendered layer, so this is that hold: by then its render has answered or been refused, and
// a shorter one would show the overview and then move it as the render lands. It bounds a
// render that never ends. Measured 2026-11-25 in eight cold page loads on the stand-in's pull
// request 7's Guided Review (tests/dom/github-guided-review-motion-chrome.mjs's recordings):
// the description's Markdown answered before the guide's first step every time, and the
// overview showed 6 to 151 ms after that step's answer.
export const GUIDE_INTRODUCTION_HOLD_MS = GUIDE_DOCUMENT_HOLD_MS;

// What a step's later read can answer otherwise. A note's renderer that was busy or could not
// start renders it next time (`_rendered_note` in guided_review.py). A reference to another
// pull request this copy had not read (`not_cached`), or whose comparison it could not read
// then (`comparison_unavailable`), is filled in once the reader opens that pull request, and
// a file whose diff the diff source could not read then (`diff_unavailable`) once it can
// (`_references` in guided_review.py).
const RETRIED_NOTES = new Set(["renderer_busy", "renderer_unavailable"]);
const RETRIED_REFERENCES = new Set(["not_cached", "comparison_unavailable", "diff_unavailable"]);

/**
 * Whether *step*'s answer holds something its next read can answer otherwise: a note, or
 * its group's, that a busy renderer refused, or a reference not read yet. Such an answer is
 * never kept, so its step is read again when the reader returns to it.
 *
 * @param {Step} step
 */
export const retryable = (step) =>
  [step.note_refusal, step.group_note_refusal].some(
    (code) => code !== undefined && code !== null && RETRIED_NOTES.has(code),
  ) || step.references.some((reference) => RETRIED_REFERENCES.has(reference.state));

/**
 * The guided-review route's query for *subject*, without its step: a pull request's guide,
 * or a stack's, read at the comparison its page draws when *at* names one.
 *
 * @param {GuideSubject} subject
 */
export function guideAsks(subject) {
  const at = subject.at;
  return `${subject.kind === "stack" ? "stack" : "number"}=${subject.number}${
    at === undefined ? "" : `&left=${at.left}&right=${at.right}&key=${at.key}`
  }`;
}

/**
 * The document's keep of step answers. An answer is kept by its query and step, for the
 * record revision it names and for whether the head had moved past that record when it was
 * asked for (*moved*): GitHub can report a newer head without a new record, and the server
 * then answers the guide's steps as out of date, so an answer read before is not that step's
 * any more. It is kept only while it holds nothing a later read can answer otherwise
 * (`retryable`): a refusal, a failure, a note a busy renderer refused, or a reference not read
 * yet is read again when asked again. A read in flight is shared by everyone who asks for
 * that step at the revision, and the *moved*, it was asked at; one asked at another does not
 * wait on it, since its answer may be for a pull request the asker has moved past.
 *
 * @param {{
 *   fetch?: (url: string, signal: AbortSignal) => Promise<{ok: boolean, text: () => Promise<string>}>,
 *   maxChars?: number,
 * }} [options]
 */
export function createGuideReads(options = {}) {
  const fetcher =
    options.fetch ??
    ((/** @type {string} */ url, /** @type {AbortSignal} */ signal) =>
      globalThis.fetch(url, { cache: "no-store", signal }));
  const maxChars = options.maxChars ?? GUIDE_KEPT_CHARS;
  /** @type {Map<string, {answer: Step, moved: boolean, chars: number}>} */
  const kept = new Map();
  /**
   * @type {Map<string, {revision: string | null, moved: boolean,
   *   promise: Promise<Step | Refusal>, controller: AbortController}>}
   */
  const flights = new Map();
  let chars = 0;
  // Bumped by `clear`, so an answer on its way then is not kept.
  let generation = 0;
  // The files a reader folded, by guide: a guide's query, the head it was read at, and the
  // folded files' keys. An entry is made by a guide's first fold and goes with its last,
  // so the map holds only guides with a file folded.
  /** @type {Map<string, {head: string, folded: Set<string>}>} */
  const folds = new Map();

  /** @param {string} key */
  function drop(key) {
    const entry = kept.get(key);
    if (entry !== undefined) {
      kept.delete(key);
      chars -= entry.chars;
    }
  }

  /** @param {string} key @param {Step} answer @param {boolean} moved @param {number} size */
  function keep(key, answer, moved, size) {
    drop(key);
    if (size > maxChars) {
      return;
    }
    kept.set(key, { answer, moved, chars: size });
    chars += size;
    for (const [oldest, entry] of kept) {
      if (chars <= maxChars) {
        break;
      }
      kept.delete(oldest);
      chars -= entry.chars;
    }
  }

  /**
   * The kept answer for *step* of the guide *asks* names at *revision*, asked for with the
   * head *moved* past that record or not, or undefined.
   *
   * @param {string} asks @param {number} step @param {string | null} revision
   * @param {boolean} moved
   * @returns {Step | undefined}
   */
  function peek(asks, step, revision, moved) {
    const key = `${asks}&step=${step}`;
    const entry = kept.get(key);
    if (entry === undefined) {
      return undefined;
    }
    if (entry.answer.record_revision !== revision || entry.moved !== moved) {
      drop(key);
      return undefined;
    }
    // Read again, so it is let go last.
    kept.delete(key);
    kept.set(key, entry);
    return entry.answer;
  }

  /**
   * *step* of the guide *asks* names, as read for *revision* with the head *moved* past it
   * or not: kept, on its way, or read now. Rejects when the route answers with an error
   * status or the read fails.
   *
   * @param {string} asks @param {number} step @param {string | null} revision
   * @param {boolean} moved
   * @returns {Promise<Step | Refusal>}
   */
  function read(asks, step, revision, moved) {
    const kept = peek(asks, step, revision, moved);
    if (kept !== undefined) {
      return Promise.resolve(kept);
    }
    const key = `${asks}&step=${step}`;
    const flight = flights.get(key);
    if (flight !== undefined && flight.revision === revision && flight.moved === moved) {
      return flight.promise;
    }
    const controller = new AbortController();
    const asked = generation;
    const promise = (async () => {
      const response = await fetcher(`/api/plugin/github/guided-review?${key}`, controller.signal);
      if (!response.ok) {
        throw new Error("Could not read the guide");
      }
      const text = await response.text();
      /** @type {Step | Refusal} */
      const answer = JSON.parse(text);
      if (
        asked === generation &&
        "step" in answer &&
        !retryable(answer) &&
        answer.record_revision === revision
      ) {
        keep(key, answer, moved, text.length);
      }
      return answer;
    })();
    const entry = { revision, moved, promise, controller };
    flights.set(key, entry);
    const done = () => {
      if (flights.get(key) === entry) {
        flights.delete(key);
      }
    };
    promise.then(done, done);
    return promise;
  }

  return {
    peek,
    read,
    /**
     * Read *step* ahead of the reader, unless it is kept or on its way. Its failure is the
     * reader's to meet when they ask for it.
     *
     * @param {string} asks @param {number} step @param {string | null} revision
     * @param {boolean} moved
     */
    prefetch(asks, step, revision, moved) {
      void read(asks, step, revision, moved).catch(() => {});
    },
    /**
     * The files a reader folded in the guide *asks* names, as read at *head*. They are kept
     * for the document, as the answers are, so a fold lasts while the reader moves between
     * steps, leaves the tab and comes back, or a poll draws the step again. A guide read at
     * another head starts with nothing folded, since a new head can change its files: the
     * head check here drops the folds of the head before, and nothing else needs to.
     *
     * @param {string} asks @param {string} head
     * @returns {{has: (key: string) => boolean, set: (key: string, folded: boolean) => void}}
     */
    folds(asks, head) {
      if (folds.get(asks)?.head !== head) {
        folds.delete(asks);
      }
      return {
        has: (key) => folds.get(asks)?.folded.has(key) ?? false,
        set(key, isFolded) {
          let entry = folds.get(asks);
          if (isFolded) {
            if (entry === undefined) {
              entry = { head, folded: new Set() };
              folds.set(asks, entry);
            }
            entry.folded.add(key);
          } else if (entry?.folded.delete(key) && entry.folded.size === 0) {
            folds.delete(asks);
          }
        },
      };
    },
    /** Forget every answer and every fold, and end every read on its way. No page calls
     * it for a new head: the answers are kept by record revision, the folds by head. */
    clear() {
      generation += 1;
      folds.clear();
      kept.clear();
      chars = 0;
      for (const flight of flights.values()) {
        flight.controller.abort();
      }
      flights.clear();
    },
  };
}

/** The document's one keep, which every page and mount of a guide reads through. */
export const guideReads = createGuideReads();

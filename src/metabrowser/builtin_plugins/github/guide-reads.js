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

// UTF-16 code units of the answers' JSON kept across the document's guides, 4 MB at most.
export const GUIDE_KEPT_CHARS = 2_000_000;

// How long a document a step cites whole waits, out of sight, for its rendered layer before
// it shows its source instead (the diff view's `markdownHoldMs`). A step is shown once its
// documents are drawn as they stay, so a hold shorter than the render would show the step
// with a document's source and then swap it for the rendering, a change of height under the
// reader. The rendered route answers, or refuses, within the Markdown child's render
// deadline (`INERT_RENDER_DEADLINE_MS` in diff/markdown_projection_worker.py), so this is
// that deadline and a second more for the request around it; the documents of #845's guide
// rendered in 12 to 120 ms each once the child was warm, measured with the step reads above.
export const GUIDE_DOCUMENT_HOLD_MS = 6_000;

/**
 * Whether *step*'s note, or its group's, was refused by a renderer that was busy or could
 * not start, which the step's next read can render (`_rendered_note` in guided_review.py):
 * such an answer is never kept, so its step is read again.
 *
 * @param {Step} step
 */
export const renderRetried = (step) =>
  [step.note_refusal, step.group_note_refusal].some(
    (code) => code === "renderer_busy" || code === "renderer_unavailable",
  );

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
 * record revision it names, and only while it is a step whose note rendered or was refused
 * for good: a refusal, a failure, or a note a busy renderer refused is read again when asked
 * again. A read in flight is shared by everyone who asks for that step at the revision it was
 * asked at; one asked at another revision does not wait on it, since its answer may name the
 * revision the asker has moved past.
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
  /** @type {Map<string, {answer: Step, chars: number}>} */
  const kept = new Map();
  /**
   * @type {Map<string, {revision: string | null, promise: Promise<Step | Refusal>,
   *   controller: AbortController}>}
   */
  const flights = new Map();
  let chars = 0;
  // Bumped by `clear`, so an answer on its way then is not kept.
  let generation = 0;

  /** @param {string} key */
  function drop(key) {
    const entry = kept.get(key);
    if (entry !== undefined) {
      kept.delete(key);
      chars -= entry.chars;
    }
  }

  /** @param {string} key @param {Step} answer @param {number} size */
  function keep(key, answer, size) {
    drop(key);
    if (size > maxChars) {
      return;
    }
    kept.set(key, { answer, chars: size });
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
   * The kept answer for *step* of the guide *asks* names at *revision*, or undefined.
   *
   * @param {string} asks @param {number} step @param {string | null} revision
   * @returns {Step | undefined}
   */
  function peek(asks, step, revision) {
    const key = `${asks}&step=${step}`;
    const entry = kept.get(key);
    if (entry === undefined) {
      return undefined;
    }
    if (entry.answer.record_revision !== revision) {
      drop(key);
      return undefined;
    }
    // Read again, so it is let go last.
    kept.delete(key);
    kept.set(key, entry);
    return entry.answer;
  }

  /**
   * *step* of the guide *asks* names, as read for *revision*: kept, on its way, or read now.
   * Rejects when the route answers with an error status or the read fails.
   *
   * @param {string} asks @param {number} step @param {string | null} revision
   * @returns {Promise<Step | Refusal>}
   */
  function read(asks, step, revision) {
    const kept = peek(asks, step, revision);
    if (kept !== undefined) {
      return Promise.resolve(kept);
    }
    const key = `${asks}&step=${step}`;
    const flight = flights.get(key);
    if (flight !== undefined && flight.revision === revision) {
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
        !renderRetried(answer) &&
        answer.record_revision === revision
      ) {
        keep(key, answer, text.length);
      }
      return answer;
    })();
    const entry = { revision, promise, controller };
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
     */
    prefetch(asks, step, revision) {
      void read(asks, step, revision).catch(() => {});
    },
    /** Forget every answer, and end every read on its way. */
    clear() {
      generation += 1;
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

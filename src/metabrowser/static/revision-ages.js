// A Git revision's page while its files' ages are being read, and when they could not all be.
//
// The server reads each file's last-commit time in the background (docs/project/
// architecture/arch-git.md, "File Ages") and never makes a page wait for it: a tree, a
// grouped tree, or a Recent list asked for before the answer lands carries an `ages` state
// of `dating`, with every file undated. This module watches for that state. While a
// response says `dating` it asks /api/index/progress, which carries the same state, every
// `GIT_AGES_POLL_MS`; when the answer lands, or the read fails, it asks the shell to draw
// again, once, so the rows that had no age get one without the reader doing anything. It also
// says in the Files band what the state is when it is not "all dated": reading, failed, or
// some files that could not be dated.
//
// The shell loads this on demand (the `revision-ages` bundle), the first time a response says
// anything but `ready`: a page whose Git has no file ages never gets an `ages` key, and one
// whose answer was whole at its first request never asks for the script.
//
// The controller is the whole decision and takes its fetch, timers, and landing callback
// as dependencies, so tests/dom/revision-ages-session.js runs it from the command line;
// `mount` is the browser glue that supplies the real ones.

/** @param {Window} global */
((global) => {
  const PROGRESS_ROUTE = "/api/index/progress";
  // A poll that fails (the server restarting, a dropped connection) is asked again, a few
  // times in a row, before the watch gives up: it has no other way to learn that the answer
  // landed, and the page has no ages until it is reloaded.
  const POLL_FAILURES_ALLOWED = 3;
  // Where the settings do not say (GIT_AGES_WATCH_GIVE_UP_MS in settings.py, a multiple of
  // the server's own budget for a read), a watch this long has lost the answer.
  const GIVE_UP_AFTER_MS = 180_000;

  /**
   * @param {{
   *   fetchState: () => Promise<{state: string} | null>,
   *   landed: (state: {state: string}) => void,
   *   setTimer: (run: () => void, ms: number) => unknown,
   *   clearTimer: (timer: unknown) => void,
   *   now: () => number,
   *   pollMs: number,
   *   giveUpMs?: number,
   * }} deps
   */
  function createController(deps) {
    /** @type {unknown} */
    let timer = null;
    let watching = false;
    let startedAt = 0;
    let failures = 0;
    let generation = 0;

    function stop() {
      generation += 1;
      watching = false;
      if (timer !== null) {
        deps.clearTimer(timer);
        timer = null;
      }
    }

    function schedule() {
      timer = deps.setTimer(() => {
        timer = null;
        void poll();
      }, deps.pollMs);
    }

    async function poll() {
      const mine = generation;
      /** @type {{state: string} | null} */
      let state = null;
      try {
        state = await deps.fetchState();
      } catch {
        state = null;
      }
      if (mine !== generation) {
        return;
      }
      if (state === null) {
        failures += 1;
        if (failures > POLL_FAILURES_ALLOWED) {
          stop();
          return;
        }
        schedule();
        return;
      }
      failures = 0;
      if (state.state === "dating") {
        if (deps.now() - startedAt >= (deps.giveUpMs ?? GIVE_UP_AFTER_MS)) {
          stop();
          return;
        }
        schedule();
        return;
      }
      stop();
      deps.landed(state);
    }

    /**
     * Look at the `ages` of a response. `dating` starts a watch, unless one is running. Any
     * other state ends a watch that is running, as the landing it is: the response that says
     * so may be the root's alone, and the folders opened since and the Recent list were
     * drawn before it. A response with no `ages` is not about file ages.
     *
     * @param {{state?: string} | null | undefined} ages
     */
    function observe(ages) {
      if (ages === null || ages === undefined || typeof ages.state !== "string") {
        return;
      }
      if (ages.state === "dating") {
        if (!watching) {
          watching = true;
          startedAt = deps.now();
          failures = 0;
          schedule();
        }
        return;
      }
      if (watching) {
        stop();
        deps.landed({ state: ages.state });
      }
    }

    return Object.freeze({
      observe,
      stop,
      isWatching: () => watching,
    });
  }

  /**
   * The controller on the page: real fetch and timers, and the shell's own redraw.
   *
   * @param {{ reload: (state: {state: string}) => void, pollMs?: number, giveUpMs?: number }} options
   */
  function mount(options) {
    const settings = global.METABROWSER_SETTINGS;
    return createController({
      fetchState: async () => {
        const response = await global.fetch(PROGRESS_ROUTE, { cache: "no-store" });
        if (!response.ok) {
          return null;
        }
        const body = await response.json();
        return body && typeof body.ages === "object" && body.ages ? body.ages : null;
      },
      landed: options.reload,
      setTimer: (run, ms) => global.setTimeout(run, ms),
      clearTimer: (timer) => global.clearTimeout(/** @type {number} */ (timer)),
      now: () => Date.now(),
      pollMs: options.pollMs ?? settings?.GIT_AGES_POLL_MS ?? 500,
      giveUpMs: options.giveUpMs ?? settings?.GIT_AGES_WATCH_GIVE_UP_MS ?? GIVE_UP_AFTER_MS,
    });
  }

  // What the server says went wrong (`ages.reason`), as a sentence.
  /** @type {Record<string, string>} */
  const REASONS = {
    git_failed: "Git could not read this revision's file ages.",
    too_many_files: "This revision has too many files to read their ages.",
    boundary: "The shallow boundary could not be read, so file ages are unknown.",
  };

  /**
   * The sentence about the state of a revision's ages, or null when they are all there: what
   * the Files band says while they are read, when the read failed, and when some files could
   * not be dated (a shallow clone, or a read that ran out of time).
   *
   * @param {{state?: string, reason?: string, files?: number, dated?: number,
   *   older_than?: number | null, stop?: string} | null | undefined} ages
   * @param {number | null | undefined} undated the files a filtered list could not date, when
   *   the response counts them
   * @returns {string | null}
   */
  function noteText(ages, undated) {
    if (!ages) {
      return null;
    }
    if (ages.state === "dating") {
      return "Reading file ages…";
    }
    if (ages.state === "failed") {
      const why = (ages.reason && REASONS[ages.reason]) || "File ages could not be read.";
      return `${why} Files show no age.`;
    }
    if (ages.state !== "partial") {
      return null;
    }
    const count = undated ?? Math.max((ages.files ?? 0) - (ages.dated ?? 0), 0);
    if (count === 0) {
      return null;
    }
    const why = ages.stop === "budget" ? "reading stopped at its time limit" : "a shallow history";
    const bound =
      typeof ages.older_than === "number"
        ? `, older than ${new Date(ages.older_than * 1000).toISOString().slice(0, 10)}`
        : "";
    return `${count.toLocaleString()} ${count === 1 ? "file" : "files"} could not be dated (${why}${bound}).`;
  }

  // The note's own line in the Files band, which the totals and their remarks stand in and
  // which a redraw of the tree leaves as it is.
  /**
   * @param {Parameters<typeof noteText>[0]} ages
   * @param {number | null | undefined} undated
   */
  function showNote(ages, undated) {
    const band = global.document?.getElementById("nav-metadata-files");
    if (!band) {
      return;
    }
    const text = noteText(ages, undated);
    let note = band.querySelector(".file-ages-note");
    if (text === null) {
      note?.remove();
      return;
    }
    if (!note) {
      note = global.document.createElement("div");
      note.className = "file-ages-note nav-metadata nav-metadata-note";
      note.setAttribute("role", "status");
      band.append(note);
    }
    note.textContent = text;
  }

  /** @type {ReturnType<typeof createController> | null} */
  let shared = null;

  /**
   * The page's one watch: the shell hands it every `ages` a response carries (and, from a
   * Recent list, how many files it could not date), and hears of the answer as a
   * `metabrowser:file-ages-landed` event on the window.
   *
   * @param {{state?: string} | null | undefined} ages
   * @param {number | null | undefined} [undated]
   */
  function track(ages, undated) {
    shared ??= mount({
      reload: (state) =>
        global.dispatchEvent(
          new global.CustomEvent("metabrowser:file-ages-landed", { detail: state }),
        ),
    });
    shared.observe(ages);
    if (ages) {
      showNote(ages, undated);
    }
  }

  global.MetabrowserRevisionAges = Object.freeze({
    createController,
    mount,
    noteText,
    showNote,
    track,
  });
})(window);

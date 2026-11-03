// Browserless session: going to a file of a large diff, through the production browser code.
//
// builtin_plugins/diff/diff-view.js loads whole, as the plugin loads it, and mounts a comparison of ten files, eight of them deferred, into a small element tree that
// lays itself out: a bar's height, a body's height from the rows it holds or the height it
// reserves, one after another, in a pane with a scroll position. Time, frames and the browser's
// IntersectionObserver are driven by the steps. Each step prints what the jump answered, the
// file at the top of the pane, what was asked of the server, and how far the jump's file is from
// the pane's top, which is the drift the reader would see.
//
// It asserts, and so prints nothing for, the same budgets at each step of a held key: requests
// in flight, one file per frame, and the target's place.

const fs = require("node:fs");
const path = require("node:path");
const { pathToFileURL } = require("node:url");

const repoRoot = path.resolve(__dirname, "../..");

function assert(condition, message) {
  if (!condition) {
    throw new Error(message);
  }
}

const BAR_PX = 30;
const ROW_PX = 20;
const PANE_PX = 400;

let clock = 1000;
const timers = [];
const frames = [];

function runDue() {
  for (;;) {
    const due = timers.filter((timer) => timer.at <= clock).sort((a, b) => a.at - b.at)[0];
    if (!due) {
      return;
    }
    timers.splice(timers.indexOf(due), 1);
    due.callback();
  }
}

const nextTask = () => new Promise((resolve) => setImmediate(resolve));

class LaidOutElement {
  constructor(tag) {
    this.tagName = tag.toUpperCase();
    this.className = "";
    this.textContent = "";
    this.innerHTML = "";
    this.dataset = {};
    this.hidden = false;
    this.style = {};
    this.children = [];
    this.parentNode = null;
    this.attributes = new Map();
    this.listeners = new Map();
    const owner = this;
    this.classList = {
      contains: (name) => owner.className.split(" ").includes(name),
      toggle(name, force) {
        const names = new Set(owner.className.split(" ").filter(Boolean));
        const want = force === undefined ? !names.has(name) : force;
        if (want) {
          names.add(name);
        } else {
          names.delete(name);
        }
        owner.className = [...names].join(" ");
        return want;
      },
    };
  }

  append(...nodes) {
    for (const node of nodes) {
      node.remove();
      node.parentNode = this;
      this.children.push(node);
    }
  }

  replaceChildren(...nodes) {
    for (const child of this.children) {
      child.parentNode = null;
    }
    this.children = [];
    this.textContent = "";
    this.append(...nodes);
  }

  remove() {
    if (this.parentNode) {
      this.parentNode.children = this.parentNode.children.filter((child) => child !== this);
      this.parentNode = null;
    }
  }

  setAttribute(name, value) {
    this.attributes.set(name, String(value));
  }

  getAttribute(name) {
    return this.attributes.has(name) ? this.attributes.get(name) : null;
  }

  addEventListener(type, handler, options) {
    this.listeners.set(type, [...(this.listeners.get(type) ?? []), handler]);
    options?.signal?.addEventListener("abort", () => this.removeEventListener(type, handler));
  }

  removeEventListener(type, handler) {
    this.listeners.set(
      type,
      (this.listeners.get(type) ?? []).filter((candidate) => candidate !== handler),
    );
  }

  dispatch(type, fields = {}) {
    for (const handler of this.listeners.get(type) ?? []) {
      handler({ type, target: this, ...fields });
    }
  }

  closest(selector) {
    for (let node = this; node; node = node.parentNode) {
      if (
        selector === "[data-kpress-viewport]"
          ? node.isPane
          : node.classList.contains(selector.slice(1))
      ) {
        return node;
      }
    }
    return null;
  }

  querySelector(selector) {
    return this.find(selector.slice(1))[0] ?? null;
  }

  *walk() {
    yield this;
    for (const child of this.children) {
      yield* child.walk();
    }
  }

  find(className) {
    return [...this.walk()].filter((node) => node.classList.contains(className));
  }

  /** This element's own height in the fixture's layout. */
  layoutHeight() {
    if (this.classList.contains("diff-end-spacer")) {
      return Number.parseFloat(this.style.height ?? "0") || 0;
    }
    if (this.classList.contains("diff-file-bar")) {
      return BAR_PX;
    }
    if (this.classList.contains("diff-split-row")) {
      return ROW_PX;
    }
    if (this.classList.contains("diff-file-body-collapsed")) {
      return 0;
    }
    const content = this.children.reduce((total, child) => total + child.layoutHeight(), 0);
    const reserved = /calc\((\d+) /.exec(this.style.minHeight ?? "");
    return Math.max(content, reserved ? Number(reserved[1]) * ROW_PX : 0);
  }

  getBoundingClientRect() {
    const pane = this.closest("[data-kpress-viewport]");
    if (this === pane) {
      return { top: 0, bottom: PANE_PX, height: PANE_PX };
    }
    let top = -pane.scrollTop;
    for (let node = this; node.parentNode; node = node.parentNode) {
      for (const sibling of node.parentNode.children) {
        if (sibling === node) {
          break;
        }
        top += sibling.layoutHeight();
      }
    }
    const height = this.layoutHeight();
    return { top, bottom: top + height, height };
  }
}

class ScriptedObserver {
  static all = [];

  constructor(callback) {
    this.callback = callback;
    this.observed = new Set();
    this.shown = new Set();
    ScriptedObserver.all.push(this);
  }

  observe(target) {
    this.observed.add(target);
  }

  unobserve(target) {
    this.observed.delete(target);
    this.shown.delete(target);
  }

  disconnect() {
    this.observed.clear();
    this.shown.clear();
  }

  /** What the browser does after layout: report the sections that crossed the pane's edges. */
  report(pane) {
    const entries = [];
    for (const target of this.observed) {
      const rect = target.getBoundingClientRect();
      const isIntersecting = rect.bottom > 0 && rect.top < PANE_PX;
      if (isIntersecting !== this.shown.has(target)) {
        entries.push({ target, isIntersecting });
        if (isIntersecting) {
          this.shown.add(target);
        } else {
          this.shown.delete(target);
        }
      }
    }
    if (entries.length > 0) {
      this.callback(entries, this);
    }
    return pane;
  }
}

function side(name) {
  return { path: name, entry_type: "file", mode: "100644", content: { kind: "empty" } };
}

function change(id, name, overrides = {}) {
  return {
    id,
    kind: "modified",
    old: side(name),
    new: side(name),
    binary: false,
    availability: "deferred",
    additions: 2,
    deletions: 1,
    ...overrides,
  };
}

function patchOf(id, rows) {
  const lines = Array.from({ length: rows }, (_, index) => ({ op: "add", text: `${id} ${index}` }));
  return {
    file_id: id,
    truncated: false,
    hunks: [{ old_start: 0, old_count: 0, new_start: 1, new_count: rows, lines }],
  };
}

function comparison() {
  const files = [
    change("f1", "first.py", { availability: "ready" }),
    change("f2", "gone.bin", {
      availability: "binary",
      binary: true,
      additions: null,
      deletions: null,
    }),
    change("f3", "src/a.py"),
    change("f4", "src/moved.py", { kind: "renamed", old: side("src/was.py"), similarity: 90 }),
    change("f5", "src/gone.py", { kind: "deleted", new: undefined, additions: 0, deletions: 3 }),
    change("f6", "src/f.py"),
    change("f7", "src/g.py"),
    change("f8", "src/h.py"),
    change("f9", "src/i.py"),
    change("f10", "src/last.py"),
  ];
  for (const file of files) {
    if (file.new === undefined) {
      delete file.new;
    }
  }
  return {
    schema: "file-diff-v1",
    schema_version: 1,
    resolved: {
      comparison_id: "session",
      source: { name: "session" },
      kind: "content",
      base_policy: "merge_base",
      left: { kind: "commit" },
      right: { kind: "commit" },
      options: { context: 3, rename_detection: true, rename_similarity: 50 },
    },
    manifest: {
      files,
      totals: { files: files.length, additions: 16, deletions: 10, exact: true },
      truncated: false,
    },
    patches: { f1: patchOf("f1", 3) },
    __revision: "left...right",
  };
}

async function main() {
  globalThis.document = {
    createElement: (tag) => new LaidOutElement(tag),
    addEventListener() {},
    removeEventListener() {},
  };
  globalThis.IntersectionObserver = ScriptedObserver;
  globalThis.requestAnimationFrame = (callback) => {
    frames.push(callback);
    return callback;
  };
  globalThis.cancelAnimationFrame = (handle) => {
    const at = frames.indexOf(handle);
    if (at >= 0) {
      frames.splice(at, 1);
    }
  };
  const realSetTimeout = globalThis.setTimeout;
  const realClearTimeout = globalThis.clearTimeout;
  globalThis.setTimeout = (callback, delay = 0) => {
    const timer = { callback, at: clock + delay };
    timers.push(timer);
    return timer;
  };
  globalThis.clearTimeout = (timer) => {
    const at = timers.indexOf(timer);
    if (at >= 0) {
      timers.splice(at, 1);
    }
  };
  const realNow = Date.now;
  Date.now = () => clock;

  const view = await import(
    pathToFileURL(path.join(repoRoot, "src/metabrowser/builtin_plugins/diff/diff-view.js")).href
  );

  /** The loader is the plugin's, one per page, so one page's requests are on at a time. */
  let open = null;

  function mount(document_ = comparison()) {
    open?.handle.dispose();
    const pane = new LaidOutElement("div");
    pane.isPane = true;
    pane.scrollTop = 0;
    pane.clientHeight = PANE_PX;
    pane.getBoundingClientRect = () => ({ top: 0, bottom: PANE_PX, height: PANE_PX });
    // The window a key press reaches, which the view listens to through the pane's document.
    const window_ = new LaidOutElement("window");
    pane.ownerDocument = { defaultView: window_ };
    const requests = [];
    view.setChangeLoader((_revision, file, options) => {
      const request = { file, signal: options?.signal, answered: false };
      request.promise = new Promise((resolve, reject) => {
        request.resolve = resolve;
        request.reject = reject;
        options?.signal?.addEventListener("abort", () =>
          reject(new DOMException("gone", "AbortError")),
        );
      });
      requests.push(request);
      return request.promise;
    });
    const handle = view.mountDiffView(pane, document_, {
      highlightSyntax: async () => null,
      isLargeTextPreview: () => true,
      langForPath: () => "",
    });
    const observer = ScriptedObserver.all.at(-1);
    const sectionOf = (file) =>
      pane
        .find("diff-file")
        .find((section) => section.find("diff-file-path")[0].textContent.endsWith(file));
    open = {
      pane,
      window: window_,
      handle,
      requests,
      observer,
      sectionOf,
      inFlight: () => requests.filter((r) => !r.answered && !r.signal.aborted),
      /** One browser turn: layout reports, a frame runs, and promises settle. */
      async turn() {
        observer.report(pane);
        await nextTask();
        runDue();
        const running = frames.splice(0);
        for (const frame of running) {
          frame(clock);
        }
        observer.report(pane);
        await nextTask();
        return running.length;
      },
      answer(file, rows = 3) {
        const request = requests.find((r) => r.file === file && !r.answered && !r.signal.aborted);
        assert(request, `no live request for ${file}`);
        request.answered = true;
        const { __revision: _revision, ...document_ } = comparison();
        const only = document_.manifest.files.find((f) => (f.new ?? f.old).path === file);
        request.resolve({
          ...document_,
          manifest: {
            files: [{ ...only, availability: "ready" }],
            totals: { files: 1, additions: 2, deletions: 1, exact: true },
            truncated: false,
          },
          patches: { [only.id]: patchOf(only.id, rows) },
        });
      },
      refuse(file) {
        const request = requests.find((r) => r.file === file && !r.answered && !r.signal.aborted);
        request.answered = true;
        request.reject(new Error("refused"));
      },
      /** An answer whose patch is whatever the step says, malformed included. */
      answerWith(file, patch) {
        const request = requests.find((r) => r.file === file && !r.answered && !r.signal.aborted);
        assert(request, `no live request for ${file}`);
        request.answered = true;
        const { __revision: _revision, ...document_ } = comparison();
        const only = document_.manifest.files.find((f) => (f.new ?? f.old).path === file);
        request.resolve({
          ...document_,
          manifest: {
            files: [{ ...only, availability: "ready" }],
            totals: { files: 1, additions: 2, deletions: 1, exact: true },
            truncated: false,
          },
          patches: { [only.id]: { ...patch, file_id: only.id } },
        });
      },
      line(jump) {
        return {
          answer: jump && { ...jump, lines: undefined },
          atTop: this.topFile(),
          asked: requests.map(
            (r) => `${r.file}${r.signal.aborted ? " (cancelled)" : r.answered ? "" : " (waiting)"}`,
          ),
          partial: pane.find("diff-partial-note")[0]?.hidden
            ? null
            : (pane.find("diff-partial-note")[0]?.textContent ?? null),
        };
      },
      topFile() {
        const sections = pane.find("diff-file");
        const top = sections.find((section) => section.getBoundingClientRect().bottom > 0);
        return top ? top.find("diff-file-path")[0].textContent : null;
      },
    };
    return open;
  }

  const steps = [];
  const say = (name, page, jump, extra = {}) =>
    steps.push({ step: name, ...(page ? page.line(jump) : {}), ...extra });

  /**
   * The scheduler alone, under scripted loads and frames, for the sequences a page cannot
   * time: a request's late rejection, an answer in hand, a render that throws.
   */
  function schedulerUnderScript({ throwOn = null } = {}) {
    const loads = [];
    const log = [];
    const pendingFrames = [];
    const scheduler = view.createHydrationScheduler({
      load(id, signal) {
        const load = { id, signal };
        load.promise = new Promise((resolve, reject) => {
          load.resolve = resolve;
          load.reject = reject;
        });
        loads.push(load);
        return load.promise;
      },
      render(id) {
        if (id === throwOn) {
          throw new Error(`render of ${id} threw`);
        }
        log.push(`render ${id}`);
        return "painted";
      },
      fail: (id) => log.push(`fail ${id}`),
      abandon: () => {},
      frame: (callback) => pendingFrames.push(callback) && callback,
      cancelFrame(handle) {
        const at = pendingFrames.indexOf(handle);
        if (at >= 0) {
          pendingFrames.splice(at, 1);
        }
      },
      after: () => null,
      cancelAfter: () => {},
      now: () => clock,
    });
    const run = () => {
      for (const frame of pendingFrames.splice(0)) {
        frame();
      }
    };
    return { scheduler, loads, log, run };
  }

  // ── A path, in every shape a list can give it ─────────────────
  const paths = mount();
  await paths.turn();
  say("mounted: the first file's lines, no request past what is on screen", paths);
  const fromRename = paths.handle.fileForPath("src/moved.py");
  const fromOld = paths.handle.fileForPath("src/was.py");
  const fromDeleted = paths.handle.fileForPath("src/gone.py");
  const fromElsewhere = paths.handle.fileForPath("only/on/github.py");
  steps.push({
    step: "fileForPath: a rename's new path, its old path, a deleted file's, and one it lacks",
    answers: [fromRename, fromOld, fromDeleted, fromElsewhere],
  });

  const absent = paths.handle.scrollToFile("only/on/github.py");
  const topBefore = paths.pane.scrollTop;
  say("a path this comparison does not hold is an answer, and nothing moves", paths, absent, {
    moved: paths.pane.scrollTop !== topBefore,
  });
  const truncated = comparison();
  truncated.manifest.truncated = true;
  truncated.manifest.cursor = "manifest-cap";
  const capped = mount(truncated);
  const pastCap = capped.handle.scrollToFile("past/the/cap.py");
  say("the same in a list that stopped at its bound says so", capped, pastCap);
  capped.handle.dispose();

  // ── One jump ──────────────────────────────────────────────────
  const one = mount();
  await one.turn();
  clock += 1000;
  const jump = one.handle.scrollToFile("src/h.py");
  say("a jump after a quiet moment: at the top at once, and asked for at once", one, jump, {
    targetTop: one.sectionOf("src/h.py").getBoundingClientRect().top,
  });
  assert(one.inFlight().length === 1, "a jump asked for more than its file");
  one.answer("src/h.py", 3);
  await nextTask();
  const framesRun = await one.turn();
  assert(framesRun >= 1, "the answer was not rendered in a frame");
  assert((await jump.lines) === "painted", "the jump's lines were not painted");
  say("its lines are in the page, in a frame of their own", one, undefined, {
    lines: "painted",
    targetTop: one.sectionOf("src/h.py").getBoundingClientRect().top,
    lineRows: one.sectionOf("src/h.py").find("diff-split-row").length,
  });

  // Files above it fill in: its place does not move.
  clock += 100;
  await one.turn();
  say(
    "neighbours on screen follow, one at a time, once the jump has what it asked for",
    one,
    undefined,
    {
      targetTop: one.sectionOf("src/h.py").getBoundingClientRect().top,
    },
  );
  while (one.inFlight().length > 0) {
    const asked = one.inFlight()[0];
    assert(one.inFlight().length === 1, "two requests in flight");
    one.answer(asked.file, 40);
    await one.turn();
    clock += 20;
    await one.turn();
    assert(
      Math.abs(one.sectionOf("src/h.py").getBoundingClientRect().top) < 0.5,
      "the jump's file moved as a neighbour filled in",
    );
  }
  say("everything on screen has arrived, and the file has not moved", one, undefined, {
    targetTop: one.sectionOf("src/h.py").getBoundingClientRect().top,
  });

  // ── A file near the end: room past the last file ──────────────
  const last = mount();
  await last.turn();
  clock += 1000;
  const toLast = last.handle.scrollToFile("src/last.py");
  say("the last file reaches the top: room past the end, which is what it takes", last, toLast, {
    targetTop: last.sectionOf("src/last.py").getBoundingClientRect().top,
    roomPastTheEnd: last.pane.find("diff-end-spacer")[0].style.height,
  });
  last.answer("src/last.py", 2);
  await nextTask();
  await last.turn();
  say("with its lines there is less room to add, and it is still at the top", last, undefined, {
    targetTop: last.sectionOf("src/last.py").getBoundingClientRect().top,
    roomPastTheEnd: last.pane.find("diff-end-spacer")[0].style.height,
  });

  // ── A held key ────────────────────────────────────────────────
  const held = mount();
  await held.turn();
  clock += 1000;
  const walk = [
    "src/a.py",
    "src/moved.py",
    "src/gone.py",
    "src/f.py",
    "src/g.py",
    "src/h.py",
    "src/i.py",
  ];
  const jumps = [];
  for (const file of walk) {
    jumps.push(held.handle.scrollToFile(file));
    assert(
      Math.abs(held.sectionOf(file).getBoundingClientRect().top) < 0.5,
      `the bar of ${file} was not at the top at once`,
    );
    assert(held.inFlight().length <= 1, "a held key had two requests in flight");
    clock += 33;
    await held.turn();
  }
  say("a key held through seven files: at most the first request and none since", held, undefined, {
    outcomes: await Promise.all(jumps.slice(0, -1).map((step) => step.lines)),
  });
  clock += view.JUMP_QUIET_MS;
  await held.turn();
  say("the key comes up: after the quiet moment, the file it rests on", held);
  held.answer("src/i.py", 3);
  await nextTask();
  await held.turn();
  assert((await jumps.at(-1).lines) === "painted", "the resting file's lines were not painted");

  // A file that fails, and a jump to a file with nothing to ask for.
  const failing = mount();
  await failing.turn();
  clock += 1000;
  const refused = failing.handle.scrollToFile("src/f.py");
  // A failed file is reported to the console too, which a transcript of this session is not.
  const realError = console.error;
  console.error = () => {};
  failing.refuse("src/f.py");
  await nextTask();
  await failing.turn();
  console.error = realError;
  say(
    "a file the server refuses: an answer, and it says so where the lines would be",
    failing,
    undefined,
    {
      lines: await refused.lines,
      body: failing.sectionOf("src/f.py").find("diff-availability")[0].textContent,
    },
  );
  clock += 1000;
  const binary = failing.handle.scrollToFile("gone.bin");
  say("a binary file has no lines to ask for", failing, binary, { lines: await binary.lines });
  const ready = failing.handle.scrollToFile("first.py");
  say("a file already here", failing, ready, { lines: await ready.lines });

  // ── The key that caused a jump does not release its pin ───────
  // A list jumps on a key; its handler may run before or after the view's own, which
  // releases the pin on any key. The event is older than the pin either way.
  const keyed = mount();
  await keyed.turn();
  clock += 1000;
  const pressedAt = performance.now();
  keyed.handle.scrollToFile("src/h.py");
  keyed.window.dispatch("keydown", { key: "ArrowDown", timeStamp: pressedAt });
  keyed.answer("src/h.py", 3);
  await nextTask();
  await keyed.turn();
  assert(
    Math.abs(keyed.sectionOf("src/h.py").getBoundingClientRect().top) < 0.5,
    "the key that caused a jump released its pin",
  );
  keyed.window.dispatch("keydown", { key: "ArrowDown", timeStamp: performance.now() });
  keyed.pane.scrollTop += 50;
  clock += 1000;
  await keyed.turn();
  const nextAsked = keyed.inFlight()[0];
  assert(nextAsked, "no file was asked for after the reader moved");
  keyed.answer(nextAsked.file, 40);
  await nextTask();
  await keyed.turn();
  assert(
    Math.abs(keyed.sectionOf("src/h.py").getBoundingClientRect().top + 50) < 0.5,
    "a key pressed after the jump did not hand the place back to the reader",
  );
  keyed.window.dispatch("keydown", { key: "ArrowDown" });
  assert(keyed.handle.scrollToFile("src/f.py").kind === "jumped", "a key with no clock jumps");

  // ── The scheduler: a request's answer is the request's, not the file's ──
  {
    const scripted = schedulerUnderScript();
    const { scheduler, loads, log, run } = scripted;
    scheduler.add("f7", 7);
    scheduler.setVisible("f7", true); // load #1
    scheduler.setVisible("f7", false); // abandoned: #1 aborted, f7 pending again
    scheduler.setVisible("f7", true); // load #2
    assert(loads.length === 2 && loads[0].signal.aborted, "the first request was not cancelled");
    loads[0].reject(new DOMException("The user aborted a request.", "AbortError"));
    await nextTask();
    assert(
      !log.some((line) => line.startsWith("fail")),
      "an abandoned request's rejection failed its file",
    );
    loads[1].resolve({ lines: "f7" });
    await nextTask();
    run();
    assert(log.includes("render f7"), "the fresh request's answer was dropped");
    say("an abandoned request's late rejection is not its file's answer", undefined, undefined, {
      scheduler: log,
    });
  }
  {
    // An answer already in hand is rendered when its file leaves the viewport: the frame it
    // costs is less than asking again.
    const { scheduler, loads, log, run } = schedulerUnderScript();
    scheduler.add("f1", 1);
    scheduler.setVisible("f1", true);
    loads[0].resolve({ lines: "f1" });
    await nextTask();
    scheduler.setVisible("f1", false);
    run();
    assert(log.includes("render f1") && loads.length === 1, "an arrived answer was thrown away");
  }
  {
    // One file's render throwing is that file's failure, and the next file is still asked for.
    const { scheduler, loads, log, run } = schedulerUnderScript({ throwOn: "f1" });
    scheduler.add("f1", 1);
    scheduler.add("f2", 2);
    scheduler.setVisible("f1", true);
    scheduler.setVisible("f2", true);
    const lines = scheduler.jump("f1");
    loads[0].resolve({ lines: "f1" });
    await nextTask();
    clock += 1000; // past the jump's quiet moment, so the next file is asked for at once
    run();
    assert((await lines) === "failed", "a throwing render did not settle the jump");
    assert(log.includes("fail f1"), "a throwing render was not reported as the file's failure");
    assert(loads.length === 2 && loads[1].id === "f2", "a throwing render stopped the scheduler");
  }

  // ── A render that throws after its file is settled ─────────────
  // The production render settles the file before it builds its rows, so a throw there
  // reaches the scheduler's failure path with a file the view no longer holds (review of
  // #284, D4): the file says it failed where its lines would be, is counted apart from the
  // loaded ones, and the frame it ran in ends clean, so the next file is still asked for.
  {
    const broken = mount();
    await broken.turn();
    clock += 1000;
    const jump = broken.handle.scrollToFile("src/h.py");
    const realError = console.error;
    console.error = () => {};
    // A malformed answer: a hunk the render cannot read.
    broken.answerWith("src/h.py", { truncated: false, hunks: [null] });
    await nextTask();
    await broken.turn();
    console.error = realError;
    say(
      "a render that throws after its file is settled: said, counted, the frame clean",
      broken,
      undefined,
      {
        lines: await jump.lines,
        body: broken.sectionOf("src/h.py").find("diff-availability")[0]?.textContent ?? null,
      },
    );
    clock += 1000;
    await broken.turn();
    assert(broken.inFlight().length === 1, "the next file on screen was not asked for");

    // The worst case: the body refuses even the failure message, so the throw reaches the
    // scheduler, whose failure path finds no file to settle and settles nothing twice.
    const refusing = mount();
    await refusing.turn();
    clock += 1000;
    const stuck = refusing.handle.scrollToFile("src/h.py");
    refusing.sectionOf("src/h.py").find("diff-file-body")[0].append = () => {
      throw new Error("the body refuses");
    };
    console.error = () => {};
    refusing.answer("src/h.py", 3);
    await nextTask();
    await refusing.turn();
    console.error = realError;
    assert((await stuck.lines) === "failed", "a refused render did not settle the jump");
    assert(
      refusing.pane.find("diff-partial-note")[0].textContent.includes("1 could not be loaded"),
      "a refused render was not counted",
    );
    clock += 1000;
    await refusing.turn();
    assert(refusing.inFlight().length === 1, "a refused render stopped the scheduler");
  }

  // A collapsed file opens when it is gone to.
  const collapsed = mount();
  const bar = collapsed.sectionOf("first.py").find("diff-file-bar")[0];
  bar.dispatch("click");
  assert(collapsed.sectionOf("first.py").classList.contains("diff-file-collapsed"), "no collapse");
  collapsed.handle.scrollToFile("first.py");
  assert(
    !collapsed.sectionOf("first.py").classList.contains("diff-file-collapsed"),
    "going to a collapsed file left it collapsed",
  );

  // ── From the reader's own move, the place is theirs ───────────
  const moved = mount();
  await moved.turn();
  clock += 1000;
  moved.handle.scrollToFile("src/h.py");
  moved.pane.dispatch("wheel");
  moved.pane.scrollTop += 50;
  moved.answer("src/h.py", 40);
  await nextTask();
  await moved.turn();
  assert(
    Math.abs(moved.sectionOf("src/h.py").getBoundingClientRect().top + 50) < 0.5,
    "a wheel did not hand the place back to the reader",
  );

  // ── Ordinary scrolling keeps what is at the top ───────────────
  const reading = mount();
  await reading.turn();
  reading.pane.scrollTop =
    reading.sectionOf("src/f.py").getBoundingClientRect().top + reading.pane.scrollTop;
  clock += 1000;
  await reading.turn();
  const atTop = reading.topFile();
  say("the reader scrolls: the topmost file on screen is asked for, not all of them", reading);
  while (reading.inFlight().length > 0) {
    const asked = reading.inFlight()[0];
    reading.answer(asked.file, 40);
    await nextTask();
    await reading.turn();
    await reading.turn();
    assert(reading.topFile() === atTop, "a file filling in moved the file at the top");
  }
  say("as they fill in, the file at the top stays", reading, undefined, {
    top: reading.sectionOf(atTop).getBoundingClientRect().top,
  });
  reading.pane.scrollTop += 2000;
  await reading.turn();
  const passed = reading.inFlight()[0]?.file;
  reading.pane.scrollTop += 2000;
  await reading.turn();
  if (passed !== undefined) {
    say("a file the reader scrolled past is no longer asked for", reading);
  }

  // ── Bounds, in the fixture's own arithmetic ───────────────────
  const reservations = [
    [{ additions: 10, deletions: 0 }, "unified"],
    [{ additions: 10, deletions: 5 }, "unified"],
    [{ additions: 10, deletions: 5 }, "split"],
    [{ additions: 5000, deletions: 0 }, "unified"],
  ].map(
    ([counts, layout]) =>
      `+${counts.additions} -${counts.deletions} in ${layout}: ${view.reservedRows(counts, layout)} rows`,
  );
  const placements = [
    { paneTop: 0, paneHeight: 400, scrollTop: 100, targetTop: 300, contentBottom: 2000 },
    { paneTop: 0, paneHeight: 400, scrollTop: 100, targetTop: 300, contentBottom: 500 },
    { paneTop: 40, paneHeight: 400, scrollTop: 0, targetTop: 40, contentBottom: 70 },
  ].map((geometry) => view.jumpPlacement(geometry));

  // ── Disposal ──────────────────────────────────────────────────
  const leaving = mount();
  await leaving.turn();
  clock += 1000;
  const going = leaving.handle.scrollToFile("src/f.py");
  leaving.handle.dispose();
  assert((await going.lines) === "superseded", "a jump outlived its view");
  assert(leaving.requests[0].signal.aborted, "a dispose left a request running");
  const afterwards = leaving.handle.scrollToFile("src/f.py");
  assert(afterwards.kind === "disposed", "a disposed view jumped");
  assert(leaving.pane.children.length === 0, "a disposed view left its root");
  assert(leaving.pane.listeners.get("wheel")?.length === 0, "a dispose left a listener");

  globalThis.setTimeout = realSetTimeout;
  globalThis.clearTimeout = realClearTimeout;
  Date.now = realNow;
  fs.writeSync(1, `${JSON.stringify({ steps, reservations, placements }, null, 2)}\n`);
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});

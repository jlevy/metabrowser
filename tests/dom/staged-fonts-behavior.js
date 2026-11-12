// Behavioral check for the staged view's wait on the faces its text is set in.
//
// A face the stage's text uses (PT Serif, on the first document after a cold load) has to
// land before the stage is shown, or the document swaps faces under the reader. The
// production view-composition.js runs here against a document whose font set says which
// faces are loaded, with the page's timers replaced so the cap elapses when a scenario says
// it does. The wait asks for the faces by name: a renderer that writes its DOM without
// yielding leaves the stage unlaid, so no face has been requested yet and
// `document.fonts.status` still reads "loaded" (PR 370 review A2). Whether a real engine
// lays the faces out as the computed style says is the browser's; this pins what the shell
// asks for and how long it holds the stage.

const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const repoRoot = path.resolve(__dirname, "../..");
const staticDir = path.join(repoRoot, "src/metabrowser/static");
const compositionSource = fs.readFileSync(path.join(staticDir, "view-composition.js"), "utf-8");
const appSource = fs.readFileSync(path.join(staticDir, "app.js"), "utf-8");
const failures = [];

function check(label, condition, detail = "") {
  if (!condition) {
    failures.push(`${label}${detail ? `: ${detail}` : ""}`);
  }
}

const PROSE = '"PT Serif", Georgia, serif';
const MONO = '"Source Code Pro", monospace';

/** An element whose computed face is *face*, with *children* found by selector. */
function element(face, children = {}) {
  return {
    face,
    querySelector(selector) {
      return children[selector] ?? null;
    },
  };
}

/**
 * A compositor whose document's font set loads a face when asked; a face in *slow* never
 * lands, and *loaded* faces are there already. `check` always says a face is there, as
 * Chrome 152's did for PT Serif while it was unloaded and while it loaded. Returns the
 * module, its timers, the faces asked for, and how many computed styles were read.
 */
function compositorWith({
  loaded = new Set(),
  slow = new Set(),
  fonts = true,
  throwing = false,
  allLoaded = false,
} = {}) {
  const timers = [];
  const cleared = [];
  const requested = [];
  const reads = { styles: 0 };
  /** @type {Map<string, () => void>} */
  const arrivals = new Map();
  const fontSet = {
    status: "loaded",
    ready: Promise.resolve(),
    check: () => true,
    *[Symbol.iterator]() {
      yield { status: "loaded" };
      yield { status: allLoaded ? "loaded" : "unloaded" };
    },
    load(font, text) {
      if (throwing) {
        throw new SyntaxError(`cannot parse ${font}`);
      }
      // A space is not text a face is chosen for: the prose stack's first family is a
      // local face for quotation marks.
      if (text === undefined || text === " ") {
        return Promise.resolve([]);
      }
      requested.push(font);
      if (loaded.has(font)) {
        return Promise.resolve([]);
      }
      if (slow.has(font)) {
        return new Promise(() => {});
      }
      return new Promise((resolve) => {
        arrivals.set(font, () => {
          loaded.add(font);
          resolve([]);
        });
      });
    },
  };
  const sandbox = {
    Array,
    Promise,
    console,
    document: fonts ? { fonts: fontSet } : {},
    getComputedStyle(node) {
      reads.styles += 1;
      const [fontStyle, fontWeight] = node.face.style;
      return { fontFamily: node.face.family, fontStyle, fontWeight };
    },
    setTimeout(callback, delay) {
      timers.push({ callback, delay });
      return timers.length;
    },
    clearTimeout(id) {
      cleared.push(id);
    },
  };
  sandbox.window = sandbox;
  vm.createContext(sandbox);
  vm.runInContext(compositionSource, sandbox, { filename: "view-composition.js" });
  return {
    arrivals,
    cleared,
    composition: sandbox.MetabrowserViewComposition,
    reads,
    requested,
    timers,
  };
}

const font = (face) => `${face.style[0]} ${face.style[1]} 16px ${face.family}`;
const regular = { family: PROSE, style: ["normal", "400"] };
const bold = { family: PROSE, style: ["normal", "700"] };
const italic = { family: PROSE, style: ["italic", "400"] };
const code = { family: MONO, style: ["normal", "400"] };

/** A Markdown document: prose paragraphs, a bold run, an italic run, and code. */
function proseDocument() {
  return element(regular, {
    p: element(regular),
    "strong, b": element(bold),
    "em, i": element(italic),
    "code, pre": element(code),
  });
}

async function settledWithin(promise) {
  let done = false;
  void promise.then(() => {
    done = true;
  });
  await new Promise((resolve) => setImmediate(resolve));
  return done;
}

async function main() {
  const cold = compositorWith();
  check(
    "the compositor exports the face wait",
    typeof cold.composition?.settleFaces === "function",
  );
  if (typeof cold.composition?.settleFaces !== "function") {
    return;
  }

  // The A2 case: nothing has laid the stage out, so the font set reads "loaded" and no face
  // is loading, but the stage's faces are not there.
  const waiting = cold.composition.settleFaces(proseDocument(), "markdown:rendered");
  check("faces the stage's text needs hold it although nothing is loading yet", waiting !== null);
  check("the stage stays held while its faces load", !(await settledWithin(waiting)));
  check(
    "each face the document uses is asked for once, and no other",
    JSON.stringify([...cold.requested].sort()) ===
      JSON.stringify([font(regular), font(bold), font(italic), font(code)].sort()),
    JSON.stringify(cold.requested),
  );
  for (const [requested, arrive] of cold.arrivals) {
    if (requested !== font(code)) {
      arrive();
    }
  }
  check("the stage waits for every face it asked for", !(await settledWithin(waiting)));
  cold.arrivals.get(font(code))?.();
  check("the stage is shown once its faces land", await settledWithin(waiting));
  check(
    "the wait is capped at FACE_WAIT_MS, and its timer is cleared when the faces land first",
    cold.timers.length === 1 &&
      cold.timers[0].delay === cold.composition.FACE_WAIT_MS &&
      JSON.stringify(cold.cleared) === "[1]",
    JSON.stringify({ cleared: cold.cleared, timers: cold.timers.map((timer) => timer.delay) }),
  );

  // A later stage of the same view asks for the faces it was set in, without reading the
  // stage's style again: that read recalculated a large document's style twice.
  const readsBefore = cold.reads.styles;
  const requestedBefore = cold.requested.length;
  const again = cold.composition.settleFaces(proseDocument(), "markdown:rendered");
  check(
    "a later stage of a view reads no style and asks for the same faces",
    cold.reads.styles === readsBefore && cold.requested.length === requestedBefore + 4,
    JSON.stringify({
      reads: cold.reads.styles - readsBefore,
      asked: cold.requested.length - requestedBefore,
    }),
  );
  check("faces that are there show a later stage at once", await settledWithin(again));
  cold.composition.settleFaces(element(code, {}), "source:rendered");
  check("another view reads its own faces", cold.reads.styles === readsBefore + 1);

  const warm = compositorWith({ allLoaded: true });
  check(
    "a stage whose document's faces are all there is shown without waiting or asking",
    warm.composition.settleFaces(proseDocument()) === null &&
      warm.timers.length === 0 &&
      warm.requested.length === 0 &&
      warm.reads.styles === 0,
  );

  const plain = compositorWith({ loaded: new Set([font(regular)]) });
  const plainWait = plain.composition.settleFaces(element(regular, { p: element(regular) }));
  check(
    "a document that uses no bold, italic, or code fetches none of those faces",
    JSON.stringify(plain.requested) === JSON.stringify([font(regular)]),
    JSON.stringify(plain.requested),
  );
  check("a face that is there holds nothing", await settledWithin(plainWait));

  const slow = compositorWith({ slow: new Set([font(regular)]) });
  const slowWait = slow.composition.settleFaces(element(regular));
  check("a slow face holds the stage until the cap", !(await settledWithin(slowWait)));
  slow.timers[0].callback();
  check("the stage is shown when the cap elapses", await settledWithin(slowWait));
  check(
    "the cap is short",
    slow.composition.FACE_WAIT_MS > 0 && slow.composition.FACE_WAIT_MS <= 100,
    String(slow.composition.FACE_WAIT_MS),
  );

  check(
    "an engine without a font set shows the stage without waiting",
    compositorWith({ fonts: false }).composition.settleFaces(proseDocument()) === null,
  );
  const unreadable = compositorWith({ throwing: true }).composition.settleFaces(proseDocument());
  check("a face the engine cannot load is not waited for", await settledWithin(unreadable));
  check("no stage, no wait", cold.composition.settleFaces(null) === null);

  // The wait sits between the active view's render and the commit that moves the stage
  // into the pane, it is given the staged view, and the claim is checked again after it.
  const renderFile = appSource.slice(appSource.indexOf("async function renderFile("));
  const mounted = renderFile.indexOf('"fileNavigation:activeView"');
  // Given the staged view, and keyed by the view's kind and id, so its faces are read once.
  const asked = renderFile.search(
    /viewComposition\.composition\.settleFaces\(\s*arrivalContent \?\? stage,\s*`\$\{compositionKind\}:\$\{initialActiveView\?\.id\}`,?\s*\)/,
  );
  const waited = renderFile.indexOf("await facesSettled;");
  const rechecked = renderFile.indexOf("if (!renderIsCurrent())", waited);
  const committed = renderFile.indexOf("stagedPluginLifecycle.commit(");
  check(
    "renderFile waits for the staged view's faces after it renders and before the commit",
    mounted > 0 && asked > mounted && waited > asked && rechecked > waited && committed > rechecked,
    JSON.stringify({ asked, committed, mounted, rechecked, waited }),
  );
  check(
    "the shell no longer infers the faces from the font set's status",
    !appSource.includes("stagedFontsSettled") && !appSource.includes("fonts?.status"),
  );
}

main()
  .catch((error) => {
    failures.push(`staged font session threw: ${error?.stack || error}`);
  })
  .then(() => {
    if (failures.length > 0) {
      console.error(failures.join("\n"));
      process.exitCode = 1;
    } else {
      console.log("OK staged fonts");
    }
  });

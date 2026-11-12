// Behavioral check for the staged file's font wait in app.js.
//
// A face the stage's layout started loading (PT Serif, on the first document
// after a cold load) has to land before the stage is shown, or the document
// swaps faces under the reader. The wait is extracted verbatim from app.js and
// run against a document whose font set says what is loading, with the page's
// timers replaced so the cap elapses when a scenario says it does. Whether a
// real engine reports a face as loading once the stage is laid out is the
// browser's; this pins what the shell does with that report.

const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const repoRoot = path.resolve(__dirname, "../..");
const appSource = fs.readFileSync(path.join(repoRoot, "src/metabrowser/static/app.js"), "utf-8");
const failures = [];

function check(label, condition, detail = "") {
  if (!condition) {
    failures.push(`${label}${detail ? `: ${detail}` : ""}`);
  }
}

const cap = appSource.match(/^var FONT_WAIT_MS = \d+;$/m);
const wait = appSource.match(/^function stagedFontsSettled\(\) \{[\s\S]*?^\}$/m);
check("app.js declares the font wait's cap", Boolean(cap));
check("app.js declares the staged font wait", Boolean(wait));

/** A shell with *fonts* as its document's font set; returns the wait and its timers. */
function shellWith(fonts) {
  const timers = [];
  const sandbox = {
    Promise,
    document: fonts === undefined ? {} : { fonts },
    setTimeout: (callback, delay) => {
      timers.push({ callback, delay });
      return timers.length;
    },
  };
  vm.createContext(sandbox);
  vm.runInContext(`${cap?.[0] ?? ""}\n${wait?.[0] ?? ""}`, sandbox, {
    filename: "app.js (staged font wait)",
  });
  return { sandbox, timers };
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
  if (!cap || !wait) {
    return;
  }
  const loaded = shellWith({ ready: new Promise(() => {}), status: "loaded" });
  check(
    "nothing loading shows the stage without waiting",
    loaded.sandbox.stagedFontsSettled() === null && loaded.timers.length === 0,
  );

  const noFontSet = shellWith(undefined);
  check(
    "an engine without a font set shows the stage without waiting",
    noFontSet.sandbox.stagedFontsSettled() === null,
  );

  let arrive = () => {};
  const arriving = shellWith({
    ready: new Promise((resolve) => {
      arrive = resolve;
    }),
    status: "loading",
  });
  const waitForFace = arriving.sandbox.stagedFontsSettled();
  check("a loading face holds the stage", waitForFace !== null);
  check("the stage stays held while the face loads", !(await settledWithin(waitForFace)));
  arrive();
  check("the stage is shown once the face lands", await settledWithin(waitForFace));
  check(
    "the wait is capped at FONT_WAIT_MS",
    arriving.timers.length === 1 && arriving.timers[0].delay === arriving.sandbox.FONT_WAIT_MS,
    JSON.stringify(arriving.timers.map((timer) => timer.delay)),
  );

  const slow = shellWith({ ready: new Promise(() => {}), status: "loading" });
  const waitForSlowFace = slow.sandbox.stagedFontsSettled();
  check("a slow face holds the stage until the cap", !(await settledWithin(waitForSlowFace)));
  slow.timers[0].callback();
  check("the stage is shown when the cap elapses", await settledWithin(waitForSlowFace));
  check(
    "the cap is short",
    slow.sandbox.FONT_WAIT_MS > 0 && slow.sandbox.FONT_WAIT_MS <= 100,
    String(slow.sandbox.FONT_WAIT_MS),
  );

  // The wait sits between the active view's render and the commit that moves
  // the stage into the pane, and the claim is checked again after it.
  const renderFile = appSource.slice(appSource.indexOf("async function renderFile("));
  const mounted = renderFile.indexOf('"fileNavigation:activeView"');
  const waited = renderFile.indexOf("await fontsSettled;");
  const rechecked = renderFile.indexOf("if (!renderIsCurrent())", waited);
  const committed = renderFile.indexOf("stagedPluginLifecycle.commit(");
  check(
    "renderFile waits for the stage's faces after the view renders and before the commit",
    mounted > 0 && waited > mounted && rechecked > waited && committed > rechecked,
    JSON.stringify({ committed, mounted, rechecked, waited }),
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

// The transition recorder in a real headless Chrome, on synthetic pages built to make each
// of its definitions fail if it were wrong: readiness before the input, DOM work after the
// subject is shown, a stall after the ready frame, a long ready frame, content that is in
// the DOM but not on screen, blank and placeholder frames after ready, region movement,
// input fidelity, cache disposition against a server that logs its 304s, and the
// journeys' Commits landing (revision 5) on a page that lands on the prompt, on the newest
// commit, or on another commit.
//
//   node tests/dom/transitions-recorder-chrome.mjs frames|frames2|content|network|landing \
//     <profile dir>
//
// The profile directory is the caller's: tests/test_transitions_instrument.py creates it,
// runs this in a process group of its own, stops that whole group however the run ends,
// Chrome included, and removes the profile.
//
// Paint and the frame clock are the behavior under test, so this needs a browser; the
// pure accounting is tested browserless in transitions-instrument-behavior.mjs.
import assert from "node:assert/strict";
import http from "node:http";
import path from "node:path";

const HERE = import.meta.dirname;
const { launchBrowser, driver, sleep } = await import(
  path.resolve(HERE, "../../explorations/performance-loop/transitions-recorder.mjs")
);
const { COMMITS_LANDING } = await import(
  path.resolve(HERE, "../../explorations/performance-loop/transitions-journeys.mjs")
);

const [group, profileDir] = process.argv.slice(2);
if (!profileDir) {
  throw new Error("usage: transitions-recorder-chrome.mjs <group> <profile dir>");
}

// The main tabs as the journeys' predicates read them: a Files and a Commits tab, the
// Commits list, and the preview. A click on Commits does what `window.mode` says: show the
// tab's prompt (`empty`, builds before main's 19a36c5b); select and show the newest commit
// on its own address, 60 ms later (`newest`, since 19a36c5b); the older commit (`older`,
// the commit read before, or any commit that is not the newest); or the newest commit's
// view with the older row selected (`unselected`).
const NEWEST = "1".repeat(40);
const OLDER = "2".repeat(40);
const LANDING_PAGE = `<!doctype html><html><head><meta charset="utf-8"><title>landing probe</title>
<style>
  body { margin: 0; font: 14px sans-serif; }
  .nav-tab-bar .tab-btn { width: 120px; height: 30px; }
  #tab-git { display: none; }
  #tab-git.shown { display: block; }
  .git-graph-row { height: 24px; }
  #preview-pane { min-height: 400px; }
</style></head><body>
<div class="nav-tab-bar"><button class="tab-btn active" data-tab="files" id="to-files">Files</button><button class="tab-btn" data-tab="git" id="to-git">Commits</button></div>
<div id="tree-content"><div id="tab-files" data-tab-content="files">a file list</div><div id="tab-git" data-tab-content="git"><div class="git-graph-row" data-revision="${NEWEST}">the newest commit</div><div class="git-graph-row" data-revision="${OLDER}">an older commit</div></div></div>
<div id="preview-pane"><div data-active-view="true">a file</div></div>
<script>
const pane = document.getElementById("preview-pane");
const git = document.getElementById("tab-git");
const files = document.getElementById("tab-files");
window.mode = "empty";
const activate = (tab) => {
  for (const b of document.querySelectorAll(".nav-tab-bar .tab-btn")) { b.classList.toggle("active", b.dataset.tab === tab); }
  git.classList.toggle("shown", tab === "git");
  files.style.display = tab === "files" ? "" : "none";
};
const select = (rev) => { for (const r of git.querySelectorAll(".git-graph-row")) { r.classList.toggle("selected", r.dataset.revision === rev); } };
const ROWS = git.innerHTML;
const prompt = (text) => { pane.innerHTML = '<div class="preview-empty">' + text + '</div>'; };
const showCommit = (rev, diff = "<pre>+ a line added</pre>") => {
  history.replaceState(null, "", "/commit/" + rev);
  pane.innerHTML = '<div class="git-commit-stage"><div class="git-commit-view" data-revision="' + rev + '"><p>commit ' + rev.slice(0, 8) + '</p><div class="git-commit-diff">' + diff + '</div></div></div>';
};
document.getElementById("to-files").addEventListener("click", () => {
  activate("files"); git.innerHTML = ROWS; select(null); history.replaceState(null, "", "/view/landing");
  pane.innerHTML = '<div data-active-view="true">a file</div>';
});
// Modes after review A of #417: \`flash\` paints the prompt at once and the newest commit
// 400 ms later; \`staleflash\` the commit read before at once and the newest 400 ms later;
// \`detailfail\` selects the newest and fails its detail, as git-panel.js renders that;
// \`emptyhistory\` and \`failedhistory\` leave no rows; \`slowdetail\` keeps the pane, mounts
// the commit with a loading diff at 150 ms, and fills it at 500 ms.
document.getElementById("to-git").addEventListener("click", () => {
  activate("git");
  const mode = window.mode;
  if (mode === "empty") { select(null); prompt("Select a commit to preview"); return; }
  if (mode === "flash") {
    prompt("Select a commit to preview");
    setTimeout(() => { select("${NEWEST}"); showCommit("${NEWEST}"); }, 400);
    return;
  }
  if (mode === "staleflash") {
    select("${OLDER}"); showCommit("${OLDER}");
    setTimeout(() => { select("${NEWEST}"); showCommit("${NEWEST}"); }, 400);
    return;
  }
  if (mode === "emptyhistory" || mode === "failedhistory") {
    git.innerHTML = "";
    prompt(mode === "emptyhistory" ? "No commits yet." : "Could not load the commit history.");
    return;
  }
  if (mode === "slowdetail") {
    setTimeout(() => { select("${NEWEST}"); showCommit("${NEWEST}", '<div class="loading">Loading diff</div>'); }, 150);
    setTimeout(() => { showCommit("${NEWEST}"); }, 500);
    return;
  }
  setTimeout(() => {
    if (mode === "newest") { select("${NEWEST}"); showCommit("${NEWEST}"); }
    else if (mode === "older") { select("${OLDER}"); showCommit("${OLDER}"); }
    else if (mode === "unselected") { select("${OLDER}"); showCommit("${NEWEST}"); }
    else if (mode === "detailfail") { select("${NEWEST}"); history.replaceState(null, "", "/commit/${NEWEST}"); prompt("Could not load this commit."); }
  }, 60);
});
</script></body></html>`;

const PAGE = `<!doctype html><html><head><meta charset="utf-8"><title>recorder probe</title>
<style>
  body { margin: 0; font: 14px sans-serif; }
  button { display: block; width: 220px; height: 30px; }
  #preview-pane { min-height: 500px; }
  .loading { display: block; width: 300px; height: 40px; background: #ccc; }
  .fade { opacity: 0; }
  .closed { height: 0; overflow: hidden; }
</style></head><body>
<div id="buttons"></div>
<div id="tree-content"></div>
<div id="preview-pane"><div data-active-view="true" id="view"></div></div>
<script>
const view = document.getElementById("view");
const pane = document.getElementById("preview-pane");
const nav = document.getElementById("tree-content");
const spin = (ms) => { const t = performance.now(); while (performance.now() - t < ms) {} };
const show = (name, text) => { view.replaceChildren(document.createTextNode(text ?? name + " subject")); view.dataset.subject = name; };
// A pull request page: its header, of a given height, and the tab bar below it.
const pullHost = (n, height) => {
  const host = document.createElement("div");
  host.className = "pull-request-host";
  host.dataset.number = String(n);
  host.innerHTML = '<div class="github-pull-header" style="height:' + height + 'px">#' + n + '</div><div class="tab-bar">Conversation</div><div class="github-pull-body">body of #' + n + '</div>';
  return host;
};
const actions = {
  reset: () => { view.replaceChildren(); delete view.dataset.subject; pane.style.marginTop = "0px"; for (const h of pane.querySelectorAll(".pull-request-host")) { h.remove(); } },
  prA: () => { pane.prepend(pullHost(353, 137)); },
  // The next pull request replaces the page: the old host goes, and 50 ms later the new
  // one, with a taller header, takes its place.
  prB: () => { pane.querySelector(".pull-request-host").remove(); setTimeout(() => pane.prepend(pullHost(351, 203)), 50); },
  // A build that retains surfaces: the old page stays mounted, hidden, ahead of the new one.
  prRetain: () => { pane.querySelector(".pull-request-host").style.display = "none"; pane.querySelector(".pull-request-host").after(pullHost(351, 203)); },
  // 500 text nodes that are not displayed, ahead of the one that is.
  hiddenAhead: () => { const w = document.createElement("div"); for (let i = 0; i < 500; i++) { const s = document.createElement("span"); s.style.display = "none"; s.textContent = "hidden " + i; w.appendChild(s); } const p = document.createElement("p"); p.textContent = "the visible subject"; w.appendChild(p); view.replaceChildren(w); view.dataset.subject = "hiddenAhead"; },
  late: () => setTimeout(() => show("late"), 300),
  rafLoop: () => { show("rafLoop"); const end = performance.now() + 600; const loop = () => { spin(2); nav.appendChild(document.createElement("i")); if (performance.now() < end) { requestAnimationFrame(loop); } }; requestAnimationFrame(loop); },
  taskLoop: () => { show("taskLoop"); const end = performance.now() + 600; const ch = new MessageChannel(); ch.port1.onmessage = () => { spin(2); nav.appendChild(document.createElement("i")); if (performance.now() < end) { ch.port2.postMessage(0); } }; ch.port2.postMessage(0); },
  stall: () => { show("stall"); requestAnimationFrame(() => setTimeout(() => spin(300), 0)); },
  // A long ready frame whose own rendering runs 40 ms past the recorder's post-layout read,
  // as paint and commit do: a ResizeObserver created after the recorder's is called after
  // its read, in the same frame.
  heavy: () => { const f = document.createDocumentFragment(); for (let i = 0; i < 40000; i++) { const d = document.createElement("div"); d.textContent = "row " + i; f.appendChild(d); } view.replaceChildren(f); view.dataset.subject = "heavy"; requestAnimationFrame(() => { const ro = new ResizeObserver(() => { ro.disconnect(); spin(40); }); ro.observe(document.documentElement); }); },
  flicker: () => { show("flicker"); setTimeout(() => { const l = document.createElement("div"); l.className = "loading"; view.replaceChildren(l); setTimeout(() => show("flicker", "flicker subject again"), 150); }, 100); },
  prompt: () => { const p = document.createElement("div"); p.className = "preview-empty"; p.textContent = "Select something."; view.replaceChildren(p); view.dataset.subject = "prompt"; },
  image: () => { const img = new Image(); img.width = 300; img.height = 200; img.src = "/slow.png?" + Math.random(); view.replaceChildren(img); view.dataset.subject = "image"; },
  faded: () => { const w = document.createElement("div"); w.className = "fade"; w.textContent = "faded subject"; view.replaceChildren(w); view.dataset.subject = "faded"; setTimeout(() => { w.className = ""; }, 300); },
  hiddenText: () => { const w = document.createElement("div"); w.style.visibility = "hidden"; w.textContent = "hidden subject"; view.replaceChildren(w); view.dataset.subject = "hiddenText"; setTimeout(() => { w.style.visibility = ""; }, 300); },
  clipped: () => { const w = document.createElement("div"); w.className = "closed"; const t = document.createElement("div"); t.textContent = "clipped subject"; w.appendChild(t); view.replaceChildren(w); view.dataset.subject = "clipped"; setTimeout(() => { w.className = ""; }, 300); },
  move: () => { show("move"); requestAnimationFrame(() => { pane.style.marginTop = "18px"; requestAnimationFrame(() => { pane.style.marginTop = "37px"; }); }); },
  fetch: async () => {
    await fetch("/static/revalidate.js").then((r) => r.text());
    await fetch("/static/fresh.js").then((r) => r.text());
    const r = await fetch("/api/data", { headers: window.etag ? { "If-None-Match": window.etag } : {} });
    window.etag = r.headers.get("etag") || window.etag; await r.text();
    window.fetched = (window.fetched || 0) + 1; show("fetch" + window.fetched);
  },
  // A module worker that imports a module and fetches a file, all revalidated on a revisit.
  worker: () => {
    const w = new Worker("/worker.js", { type: "module" });
    w.onmessage = () => { window.workers = (window.workers || 0) + 1; show("worker" + window.workers); w.terminate(); };
  },
};
const buttons = document.getElementById("buttons");
// Each action runs from a click. Where its handler started is kept for the checks as a
// position in the recorder's frame log (the array a debug measure returns as raw.frames):
// on this one thread, every entry before it was logged before the handler, and every one
// at or after it, after.
for (const [name, fn] of Object.entries(actions)) {
  const b = document.createElement("button"); b.id = "go-" + name; b.textContent = name; b.addEventListener("click", () => { window.clickFrameMark = window.__tr.frames.length; fn(); }); buttons.appendChild(b);
}
// A synthetic pointerdown dispatched by the page itself when the pointer first moves over it.
document.getElementById("go-reset").insertAdjacentHTML("beforebegin", '<button id="go-forged">forged</button>');
document.getElementById("go-forged").addEventListener("mousemove", () => { if (!window.forged) { window.forged = true; document.dispatchEvent(new PointerEvent("pointerdown", { bubbles: true })); } });
document.getElementById("go-forged").addEventListener("click", () => show("forged"));
// The subject shows while the pointer hovers, before the press that starts the transition.
document.getElementById("go-reset").insertAdjacentHTML("beforebegin", '<button id="go-hoverShow">hover shows</button>');
document.getElementById("go-hoverShow").addEventListener("mouseenter", () => show("hoverShow"));
window.keys = [];
addEventListener("keydown", (e) => { window.keys.push([e.key, e.repeat]); if (e.key === "ArrowDown" && !e.repeat) { show("held"); } });
</script></body></html>`;

const PNG = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==",
  "base64",
);
const hits = {};
// Served with an ETag and no-cache, so a second read is a 304 on the wire.
const REVALIDATED = {
  "/static/revalidate.js": `/* body */${"x".repeat(2000)}`,
  "/api/data": `/* body */${"x".repeat(2000)}`,
  "/worker.js": `import "./worker-dep.js";\nconst r = await fetch("/static/worker-data.js");\nawait r.text();\npostMessage("done");\n`,
  "/worker-dep.js": `/* a dependency ${"z".repeat(2000)} */`,
  "/static/worker-data.js": `/* worker data */${"w".repeat(2000)}`,
};
const server = http.createServer((req, res) => {
  const u = new URL(req.url, "http://x");
  hits[u.pathname] ??= [];
  const conditional = req.headers["if-none-match"] === '"v1"';
  if (u.pathname === "/view/probe") {
    res.writeHead(200, { "content-type": "text/html", "cache-control": "no-store" });
    res.end(PAGE);
  } else if (u.pathname === "/view/landing") {
    res.writeHead(200, { "content-type": "text/html", "cache-control": "no-store" });
    res.end(LANDING_PAGE);
  } else if (u.pathname === "/slow.png") {
    setTimeout(() => {
      res.writeHead(200, { "content-type": "image/png", "cache-control": "no-store" });
      res.end(PNG);
    }, 700);
  } else if (REVALIDATED[u.pathname] !== undefined) {
    hits[u.pathname].push(conditional ? 304 : 200);
    if (conditional) {
      res.writeHead(304, { etag: '"v1"', "cache-control": "no-cache" });
      res.end();
    } else {
      res.writeHead(200, {
        "content-type": "text/javascript",
        etag: '"v1"',
        "cache-control": "no-cache",
      });
      res.end(REVALIDATED[u.pathname]);
    }
  } else if (u.pathname === "/static/fresh.js") {
    hits[u.pathname].push(200);
    res.writeHead(200, { "content-type": "text/javascript", "cache-control": "max-age=3600" });
    res.end(`/* fresh */${"y".repeat(2000)}`);
  } else {
    res.writeHead(404);
    res.end();
  }
});
await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
const base = `http://127.0.0.1:${server.address().port}`;
const browser = await launchBrowser({
  profileDir,
  extraArgs: process.platform === "linux" ? ["--no-sandbox"] : [],
});
const d = driver(browser);
let checks = 0;

// The recorder refuses a window whose median frame step is over 50 ms (`frame_clock`): a
// machine too busy to draw at the display rate, which says nothing about whether the
// recorder measures right. A CI runner has been that busy for one measurement while every
// other check in the job took its usual time: the heavy page's frames stepped 366.6 and
// 416.6 ms there. On a 10-core Mac it passed 15 runs of 15 with ten busy loops beside
// it, and stepped 16.7 to 33.3 ms with Chrome's CPU throttled up to sevenfold. Throttled
// eightfold, its first measurement was refused in 10 runs of 10 and its second passed in
// 6 of 6; twelvefold, all three attempts were refused in 2 runs of 3.
// So `check` takes an attempt again when it failed while a measurement in it was refused
// for its frame clock alone, up to FRAME_CLOCK_ATTEMPTS in all, and says so on stderr in a
// `retry:` line, which tests/test_transitions_instrument.py surfaces. An attempt that
// failed any other way, and the last attempt, fail the check as before, so a wrong
// measurement fails and a machine that cannot measure at all still fails.
const FRAME_CLOCK_ATTEMPTS = 3;
let frameClockRefusals = [];
// Every measurement goes through here, so a check knows which of its attempts' windows the
// recorder refused for the frame clock alone.
async function take(spec) {
  const r = await d.measure(spec);
  if (r.refusals.length > 0 && r.refusals.every(([guard]) => guard === "frame_clock")) {
    frameClockRefusals.push(`${spec.id}: ${r.refusals[0][1]}`);
  }
  return r;
}

const subjectReady = (name) =>
  `() => document.getElementById("view").dataset.subject === ${JSON.stringify(name)} && window.__tr.hasUseful(document.getElementById("view"))`;
async function measure(name, extra = {}) {
  await d.click("#go-reset");
  await sleep(300);
  const r = await take({
    id: name,
    subject: name,
    input: { kind: "click", selector: `#go-${name}` },
    ready: subjectReady(name),
    converged: `() => ""`,
    settleMs: 400,
    timeoutMs: 10000,
    debug: true,
    ...extra,
  });
  await sleep(300);
  return r;
}
// The press that starts the recorder's clock, on the page clock.
const pressAt = (r) =>
  r.raw.inputs.find(([type]) => type === "pointerdown" || type === "mousedown")[1];
// The press and the release that makes the click are separate CDP calls, so a busy machine
// can draw a frame between them: under 12 extra busy loops on a 10-core machine the click
// reached the page up to 22 ms after the press, and in 2 of 15 rafLoop transitions a frame
// fell between them. That frame shows the page before the click handler ran, and the
// recorder counts it from the press, as it should: one more frame to ready, blank on these
// pages.
// Frames are ordered against the click by their position in the frame log, not by clock:
// the log keeps a read's time rounded to 0.1 ms, which a read just before the handler can
// share with the handler's own time. The recorder appends a frame to the log as it reads
// it, so position orders each read against the handler exactly. A frame whose observation
// never arrived is appended at the next frame instead, so it is left out.
const readsAroundClick = async (r) => {
  const mark = await d.evaluate("window.clickFrameMark");
  const reads = r.raw.frames.map((f, i) => ({ f, i })).filter(({ f }) => f[1] !== null);
  return { before: reads.filter(({ i }) => i < mark), after: reads.filter(({ i }) => i >= mark) };
};
// The frames read after the press and before the click handler started.
async function framesBeforeClick(r) {
  const { before } = await readsAroundClick(r);
  return before.filter(({ f }) => f[0] >= pressAt(r)).length;
}
// The ready frame is the first frame read after the click handler started. This is
// checked on the frames themselves rather than through `framesToReady`, which counts
// frames by their begin time from the press, and reads 0 when Chrome begins the ready
// frame before the press's own time stamp (README, "Limits").
async function assertReadyInFirstFrameAfterClick(r) {
  const { after } = await readsAroundClick(r);
  const first = after[0]?.f;
  assert.ok(
    first && first[0] === r.raw.readyAt && first[2] === Math.round(r.raw.readyRead * 10) / 10,
    `the first frame read after the click, ${JSON.stringify(first)}, is not the ready frame at ${r.raw.readyAt}: ${JSON.stringify(r.frameStates)}`,
  );
}
// Painted ready against Chrome's presentation of the click's next paint (Event Timing),
// which is the ready frame only where the click handler itself shows the subject, as on
// every page that calls this; on the image page it is not. Chrome presents a frame after
// its main-thread rendering ends, and painted ready is the first frame boundary after that
// end, so painted ready is never more than a frame after the presentation. The 9 ms
// covers Chrome's rounding of that time to 8 ms and the recorder's to 0.1 ms. An entry
// Chrome leaves out was presented within its 16 ms threshold of the click.
// The bound has one side. The presentation also includes compositor, raster, and GPU work
// after the main thread, which painted ready leaves out (README, "Limits"), so it can come
// later than painted ready by that much: for the long frame below, by 9 to 12 ms in five
// CI runs and 23 to 43 ms with the renderer's CPU throttled fourfold.
function assertPaintedByPresentation(r) {
  const click = r.raw.inputs.find(([type]) => type === "click");
  const presented = r.eventPresentedMs.click ?? click[1] - pressAt(r) + 16;
  assert.ok(
    r.paintedReadyMs <= presented + r.frameIntervalMs + 9,
    `painted ready ${r.paintedReadyMs}, presented by ${presented}`,
  );
}
// TRANSITIONS_PROBE_ALL=1 runs every check and lists each failure, to show a recorder
// failing them all; by default the first failure ends the run.
const failures = [];
// `retryable: false` is for a check whose second attempt cannot repeat its first, as when
// it counts what the server answered.
async function check(name, fn, { retryable = true } = {}) {
  // Progress on stderr, so a run cut off by its timeout says where it was.
  process.stderr.write(`check: ${name}\n`);
  for (let attempt = 1; ; attempt++) {
    frameClockRefusals = [];
    try {
      await fn();
      break;
    } catch (error) {
      if (retryable && frameClockRefusals.length > 0 && attempt < FRAME_CLOCK_ATTEMPTS) {
        process.stderr.write(
          `retry: ${name}: attempt ${attempt} of ${FRAME_CLOCK_ATTEMPTS} was refused for its ` +
            `frame clock alone (${frameClockRefusals.join("; ")})\n`,
        );
        await sleep(1000);
        continue;
      }
      if (process.env.TRANSITIONS_PROBE_ALL !== "1") {
        throw new Error(`${name}: ${error.message}`, { cause: error });
      }
      failures.push(`${name}: ${error.message.split("\n")[0]}`);
      return;
    }
  }
  checks += 1;
}

try {
  const landingGroup = group === "landing";
  await d.navigate(`${base}/view/${landingGroup ? "landing" : "probe"}`);
  assert.ok(
    await d.waitFor(
      `!!window.__tr && !!document.getElementById(${JSON.stringify(landingGroup ? "to-git" : "go-reset")})`,
      20000,
    ),
  );
  await sleep(500);

  if (group === "frames") {
    await check("a subject shown during the hover, before the press, refuses", async () => {
      await d.click("#go-reset");
      await sleep(200);
      const r = await take({
        id: "hoverShow",
        subject: "hoverShow",
        input: { kind: "hover-click", selector: "#go-hoverShow", hoverMs: 200 },
        ready: subjectReady("hoverShow"),
        converged: `() => ""`,
        timeoutMs: 5000,
      });
      assert.ok(
        r.refusals.some(([g, m]) => g === "ready_before_input" && /frame before the input/.test(m)),
        JSON.stringify(r.refusals),
      );
      await d.park();
      await sleep(300);
    });
    await check("a predicate that holds before the input refuses", async () => {
      await d.click("#go-reset");
      await sleep(200);
      await d.evaluate(`document.getElementById("view").textContent = "already here"`);
      const r = await take({
        id: "late",
        subject: "late",
        input: { kind: "click", selector: "#go-late" },
        ready: `() => window.__tr.hasUseful(document.getElementById("view"))`,
        converged: `() => ""`,
      });
      assert.equal(r.ok, false);
      assert.ok(
        r.refusals.some(([g]) => g === "ready_before_input"),
        JSON.stringify(r.refusals),
      );
      await sleep(400);
    });
    for (const name of ["rafLoop", "taskLoop"]) {
      await check(
        `DOM work after the subject (${name}) is settle time, not readiness`,
        async () => {
          const r = await measure(name, { settleMs: 800 });
          assert.equal(r.ok, true, JSON.stringify(r.refusals));
          // Ready in the first frame read after the click showed the subject, and painted
          // ready is that frame's presentation, not the end of the 600 ms of DOM work after
          // it. A busy machine can be slow to draw that frame (CI once read 198.7 ms here),
          // so the bound is Chrome's presentation of it, not a fixed time.
          await assertReadyInFirstFrameAfterClick(r);
          assert.equal(r.blankFrames, await framesBeforeClick(r), JSON.stringify(r.frameStates));
          assert.equal(r.uncreditedFrames, 0);
          assertPaintedByPresentation(r);
          assert.ok(r.navSettledMs > 400, `nav settled ${r.navSettledMs}`);
        },
      );
    }
    // Chrome reports the frame after this stall on the frame grid, so this page cannot tell
    // painted ready from the next frame's begin time; the browserless presentedAt checks
    // are the ones that do.
    await check("a long task after the ready frame is not counted", async () => {
      const r = await measure("stall");
      assert.equal(r.ok, true, JSON.stringify(r.refusals));
      assert.ok(r.paintedReadyMs >= r.readyMs);
      // The 300 ms task runs after the ready frame, so counting it would put painted ready
      // far more than a frame past Chrome's presentation of that frame.
      assertPaintedByPresentation(r);
    });
  } else if (group === "frames2") {
    await check("a long ready frame counts its own rendering", async () => {
      const r = await measure("heavy", { settleMs: 400 });
      assert.equal(r.ok, true, JSON.stringify(r.refusals));
      const presented = r.eventPresentedMs.click;
      assert.ok(presented > 30, `the heavy frame was presented at ${presented}`);
      // Chrome's Long Animation Frame entry for the ready frame, the one that spans its
      // read, ends when the frame's main-thread rendering did. The page's work after the
      // read puts that more than a frame past the read, so a painted ready taken from the
      // read alone, or from the frame's begin time, falls short of it.
      const read = r.raw.readyRead;
      const loaf = r.raw.loafs.find(
        ([start, duration, , renderStart]) =>
          renderStart > 0 && start <= read && start + duration >= read,
      );
      assert.ok(loaf, `no Long Animation Frame spans the read: ${JSON.stringify(r.raw.loafs)}`);
      const renderedMs = loaf[0] + loaf[1] - pressAt(r);
      assert.ok(
        renderedMs - r.readyMs > r.frameIntervalMs,
        `read at ${r.readyMs}, rendering ended at ${renderedMs}`,
      );
      // Painted ready is the first frame boundary after that end, to the recorder's 0.1 ms.
      assert.ok(
        r.paintedReadyMs >= renderedMs - 0.1 &&
          r.paintedReadyMs <= renderedMs + r.frameIntervalMs + 0.1,
        `painted ready ${r.paintedReadyMs}, rendering ended at ${renderedMs}`,
      );
      assertPaintedByPresentation(r);
    });
    await check("blank and placeholder frames after ready are counted", async () => {
      const r = await measure("flicker");
      assert.equal(r.ok, true, JSON.stringify(r.refusals));
      assert.equal(r.blankFramesBeforeReady, await framesBeforeClick(r));
      assert.ok(r.placeholderVisibleFramesAfterReady >= 3, JSON.stringify(r.frameStates));
      assert.ok(r.blankFramesAfterReady >= 3, JSON.stringify(r.frameStates));
      assert.ok(r.blankMs >= 50, `blank ms ${r.blankMs}`);
    });
    await check("a declared prompt is not blank", async () => {
      const ready = `() => !!document.querySelector("#view .preview-empty")`;
      const declared = await measure("prompt", { ready, emptyState: true });
      assert.equal(declared.ok, true, JSON.stringify(declared.refusals));
      assert.equal(declared.blankFrames, await framesBeforeClick(declared));
      const undeclared = await measure("prompt", { ready });
      assert.ok(undeclared.blankFrames > (await framesBeforeClick(undeclared)));
    });
  } else if (group === "content") {
    await check("an image counts once its bytes have arrived and decoded", async () => {
      const r = await measure("image", { settleMs: 400 });
      assert.equal(r.ok, true, JSON.stringify(r.refusals));
      assert.ok(r.paintedReadyMs >= 650, `painted ready ${r.paintedReadyMs}`);
      assert.ok(r.blankFrames >= 20);
    });
    for (const name of ["faded", "hiddenText", "clipped"]) {
      await check(`text that is not on screen (${name}) is not useful`, async () => {
        const r = await measure(name, { settleMs: 400 });
        assert.equal(r.ok, true, JSON.stringify(r.refusals));
        assert.ok(r.paintedReadyMs >= 250, `painted ready ${r.paintedReadyMs}`);
      });
    }
    await check("movement over two frames reports its net and path", async () => {
      const r = await measure("move", { settleMs: 400 });
      assert.equal(r.ok, true, JSON.stringify(r.refusals));
      assert.equal(r.movementNetPx, 37);
      assert.equal(r.movementPathPx, 37);
      assert.ok(r.movementPx <= 19, `largest step ${r.movementPx}`);
    });
    await check("content behind 500 hidden text nodes is found", async () => {
      const r = await measure("hiddenAhead", { timeoutMs: 5000 });
      assert.equal(r.ok, true, JSON.stringify(r.refusals));
      // Found in the first frame read after the click.
      await assertReadyInFirstFrameAfterClick(r);
      assert.equal(r.blankFrames, await framesBeforeClick(r), JSON.stringify(r.frameStates));
    });
    await check("a hidden retained page is not taken for the one on screen", async () => {
      await d.click("#go-reset");
      await sleep(200);
      await d.click("#go-prA");
      await sleep(300);
      const r = await take({
        id: "prRetain",
        subject: "#351",
        input: { kind: "click", selector: "#go-prRetain" },
        ready: `() => { const h = document.querySelector('#preview-pane > .pull-request-host[data-number="351"]'); return !!h && window.__tr.hasUseful(h); }`,
        converged: `() => ""`,
        settleMs: 400,
        timeoutMs: 5000,
      });
      assert.equal(r.ok, true, JSON.stringify(r.refusals));
      assert.deepEqual(r.regions.prTabs.present, [true, true]);
      assert.deepEqual(r.regions.prTabs.net, [0, 66, 0, 0]);
      await sleep(300);
    });
    await check("a replaced page with a taller header moves the tab bar below it", async () => {
      await d.click("#go-reset");
      await sleep(200);
      await d.click("#go-prA");
      await sleep(300);
      const r = await take({
        id: "prB",
        subject: "#351",
        input: { kind: "click", selector: "#go-prB" },
        ready: `() => { const h = document.querySelector('#preview-pane > .pull-request-host[data-number="351"]'); return !!h && window.__tr.hasUseful(h); }`,
        converged: `() => ""`,
        settleMs: 400,
      });
      assert.equal(r.ok, true, JSON.stringify(r.refusals));
      assert.deepEqual(r.regions.prTabs.net, [0, 66, 0, 0]);
      assert.equal(r.regions.prTabs.path[1], 66, JSON.stringify(r.regions.prTabs));
      assert.equal(r.regions.prHeader.net[3], 66);
      assert.ok(r.movementNetPx >= 66, `net ${r.movementNetPx}`);
      assert.ok(r.movementPathPx >= 66, `path ${r.movementPathPx}`);
      await sleep(300);
    });
    await check("an untrusted start event refuses", async () => {
      await d.click("#go-reset");
      await sleep(300);
      const r = await take({
        id: "forged",
        subject: "forged",
        input: { kind: "hover-click", selector: "#go-forged", hoverMs: 150 },
        ready: subjectReady("forged"),
        converged: `() => ""`,
      });
      assert.ok(
        r.refusals.some(([g, m]) => g === "input_observed" && /not trusted/.test(m)),
        JSON.stringify(r.refusals),
      );
      await sleep(300);
    });
    await check("a held key starts with a keyDown that is not a repeat", async () => {
      await d.click("#go-reset");
      await sleep(300);
      await d.evaluate("window.keys = []");
      const r = await take({
        id: "held",
        subject: "held",
        input: { kind: "key-repeat", key: "ArrowDown", count: 4, intervalMs: 40 },
        ready: subjectReady("held"),
        converged: `() => ""`,
      });
      assert.equal(r.ok, true, JSON.stringify(r.refusals));
      const keys = await d.evaluate("window.keys");
      assert.deepEqual(
        keys.map((k) => k[1]),
        [false, true, true, true],
      );
      assert.ok(r.inputSpanMs >= 100, `input span ${r.inputSpanMs}`);
    });
  } else if (group === "network") {
    // Both count what the server answered over two measurements in a fresh browser cache,
    // so a second attempt could not repeat the first and they are not taken again.
    await check(
      "cache disposition matches what the server answered",
      async () => {
        const spec = (n) => ({
          input: { kind: "click", selector: "#go-fetch" },
          ready: subjectReady(`fetch${n}`),
        });
        const first = await take({ id: "f1", subject: "f", converged: `() => ""`, ...spec(1) });
        assert.equal(first.ok, true, JSON.stringify(first.refusals));
        await sleep(300);
        const second = await take({ id: "f2", subject: "f", converged: `() => ""`, ...spec(2) });
        assert.equal(second.ok, true, JSON.stringify(second.refusals));
        const by = Object.fromEntries(second.requests.list.map((x) => [x.u, x.d]));
        // The server answered 200 then 304 to both conditional routes and once to the
        // max-age file, which the browser then served from its own cache.
        assert.deepEqual(hits["/static/revalidate.js"], [200, 304]);
        assert.deepEqual(hits["/api/data"], [200, 304]);
        assert.deepEqual(hits["/static/fresh.js"], [200]);
        assert.deepEqual(by, {
          "/static/revalidate.js": "revalidated",
          "/static/fresh.js": "cache",
          "/api/data": "revalidated",
        });
        assert.deepEqual(second.requests.byFamily.static, { revalidated: 1, cache: 1 });
      },
      { retryable: false },
    );
    await check(
      "a worker's requests answered by a 304 are revalidated",
      async () => {
        const spec = (n) => ({
          id: `w${n}`,
          subject: "w",
          input: { kind: "click", selector: "#go-worker" },
          ready: subjectReady(`worker${n}`),
          converged: `() => ""`,
          timeoutMs: 10000,
        });
        const first = await take(spec(1));
        assert.equal(first.ok, true, JSON.stringify(first.refusals));
        await sleep(300);
        const second = await take(spec(2));
        assert.equal(second.ok, true, JSON.stringify(second.refusals));
        for (const p of ["/worker.js", "/worker-dep.js", "/static/worker-data.js"]) {
          assert.deepEqual(hits[p], [200, 304], `${p} answered ${hits[p]}`);
        }
        const by = Object.fromEntries(
          second.requests.list.map((x) => [x.u, `${x.k ?? "page"} ${x.d}`]),
        );
        assert.deepEqual(by, {
          "/worker.js": "page revalidated",
          "/worker-dep.js": "w revalidated",
          "/static/worker-data.js": "w revalidated",
        });
      },
      { retryable: false },
    );
  } else if (group === "landing") {
    const L = COMMITS_LANDING;
    // A switch from Files to Commits on the page in `mode`, measured with `spec`.
    const landOn = async (mode, spec) => {
      await d.click("#to-files");
      await sleep(300);
      await d.evaluate(`window.mode = ${JSON.stringify(mode)}`);
      const r = await take({
        id: `landing.${mode}`,
        subject: "Commits",
        input: { kind: "click", selector: "#to-git" },
        settleMs: 400,
        timeoutMs: 5000,
        ...spec,
      });
      await sleep(200);
      return r;
    };
    const toList = {
      ready: L.ready(NEWEST),
      converged: L.converged(NEWEST),
      landing: L.kind(NEWEST),
      emptyState: true,
    };
    const notReady = (r) =>
      r.refusals.some(([guard, detail]) => guard === "converged" && /not ready/.test(detail));
    await check("a switch to Commits that shows the prompt is the empty landing", async () => {
      const r = await landOn("empty", toList);
      assert.equal(r.ok, true, JSON.stringify(r.refusals));
      assert.equal(r.landing, "empty");
    });
    await check(
      "a switch to Commits that shows the newest commit is the newest landing",
      async () => {
        const r = await landOn("newest", toList);
        assert.equal(r.ok, true, JSON.stringify(r.refusals));
        assert.equal(r.landing, "newest");
      },
    );
    await check("the prompt alone, revision 4's test, refuses the newest landing", async () => {
      const r = await landOn("newest", { ready: L.prompt, converged: `() => ""`, timeoutMs: 1500 });
      assert.ok(notReady(r), JSON.stringify(r.refusals));
    });
    await check("a switch to Commits that shows another commit is neither landing", async () => {
      const r = await landOn("older", { ...toList, timeoutMs: 1500 });
      assert.ok(notReady(r), JSON.stringify(r.refusals));
      assert.equal(r.landing, null);
    });
    await check("the newest landing converges only with the newest row selected", async () => {
      const r = await landOn("unselected", toList);
      assert.ok(
        r.refusals.some(([guard, detail]) => guard === "converged" && /selected/.test(detail)),
        JSON.stringify(r.refusals),
      );
    });
    await check(
      "a switch back to Commits lands on the commit read before or the newest",
      async () => {
        const spec = {
          ready: L.subjectReady(OLDER, NEWEST),
          converged: L.subjectConverged(OLDER, NEWEST),
          landing: L.kind(NEWEST, OLDER),
        };
        const restored = await landOn("older", spec);
        assert.equal(restored.ok, true, JSON.stringify(restored.refusals));
        assert.equal(restored.landing, "restored");
        const newest = await landOn("newest", spec);
        assert.equal(newest.ok, true, JSON.stringify(newest.refusals));
        assert.equal(newest.landing, "newest");
      },
    );
    // Review A of #417.
    const movedOn = (r, from, to) =>
      r.refusals.some(
        ([guard, detail]) =>
          guard === "converged" && detail.includes(`ready on ${from}, converged on ${to}`),
      );
    await check("a prompt painted before the newest commit is refused, not timed", async () => {
      const r = await landOn("flash", toList);
      assert.ok(movedOn(r, "empty", "newest"), JSON.stringify(r.refusals));
      assert.equal(r.landingAtReady, "empty");
      assert.equal(r.landing, "newest");
    });
    await check("the commit read before, painted before the newest, is refused", async () => {
      const r = await landOn("staleflash", {
        ready: L.subjectReady(OLDER, NEWEST),
        converged: L.subjectConverged(OLDER, NEWEST),
        landing: L.kind(NEWEST, OLDER),
      });
      assert.ok(movedOn(r, "restored", "newest"), JSON.stringify(r.refusals));
    });
    await check("the newest commit's failed detail is not the prompt", async () => {
      const r = await landOn("detailfail", { ...toList, timeoutMs: 1500 });
      assert.ok(notReady(r), JSON.stringify(r.refusals));
      assert.match(await d.evaluate(`(${L.kind(NEWEST)})()`), /^other \/commit\//);
    });
    await check("an empty or failed history is never ready", async () => {
      for (const mode of ["emptyhistory", "failedhistory"]) {
        const r = await landOn(mode, { ...toList, timeoutMs: 1500 });
        assert.ok(notReady(r), `${mode}: ${JSON.stringify(r.refusals)}`);
      }
    });
    await check("a slow detail is ready when its diff has text, not when it mounts", async () => {
      const r = await landOn("slowdetail", toList);
      assert.equal(r.ok, true, JSON.stringify(r.refusals));
      assert.equal(r.landing, "newest");
      assert.ok(r.readyMs >= 450, `ready ${r.readyMs}`);
    });
  } else {
    throw new Error(`unknown group ${group}; frames, frames2, content, network, or landing`);
  }
} finally {
  // Stops every Chrome process of the profile, then removes the profile.
  await browser.close();
  server.close();
}
if (failures.length) {
  console.log(failures.map((f) => `FAILED ${f}`).join("\n"));
  process.exitCode = 1;
}
console.log(`transitions recorder ${group}: ${checks} checks passed`);

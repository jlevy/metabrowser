// The transition recorder in a real headless Chrome, on synthetic pages built to make each
// of its definitions fail if it were wrong: readiness before the input, DOM work after the
// subject is shown, a stall after the ready frame, a long ready frame, content that is in
// the DOM but not on screen, blank and placeholder frames after ready, region movement,
// input fidelity, and cache disposition against a server that logs its 304s.
//
//   node tests/dom/transitions-recorder-chrome.mjs frames|frames2|content|network
//
// Paint and the frame clock are the behavior under test, so this needs a browser; the
// pure accounting is tested browserless in transitions-instrument-behavior.mjs.
import assert from "node:assert/strict";
import fs from "node:fs";
import http from "node:http";
import os from "node:os";
import path from "node:path";

const HERE = import.meta.dirname;
const { launchBrowser, driver, sleep } = await import(
  path.resolve(HERE, "../../explorations/performance-loop/transitions-recorder.mjs")
);

const group = process.argv[2];

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
  late: () => setTimeout(() => show("late"), 300),
  rafLoop: () => { show("rafLoop"); const end = performance.now() + 600; const loop = () => { spin(2); nav.appendChild(document.createElement("i")); if (performance.now() < end) { requestAnimationFrame(loop); } }; requestAnimationFrame(loop); },
  taskLoop: () => { show("taskLoop"); const end = performance.now() + 600; const ch = new MessageChannel(); ch.port1.onmessage = () => { spin(2); nav.appendChild(document.createElement("i")); if (performance.now() < end) { ch.port2.postMessage(0); } }; ch.port2.postMessage(0); },
  stall: () => { show("stall"); requestAnimationFrame(() => setTimeout(() => spin(300), 0)); },
  heavy: () => { const f = document.createDocumentFragment(); for (let i = 0; i < 40000; i++) { const d = document.createElement("div"); d.textContent = "row " + i; f.appendChild(d); } view.replaceChildren(f); view.dataset.subject = "heavy"; },
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
};
const buttons = document.getElementById("buttons");
for (const [name, fn] of Object.entries(actions)) {
  const b = document.createElement("button"); b.id = "go-" + name; b.textContent = name; b.addEventListener("click", fn); buttons.appendChild(b);
}
// A synthetic pointerdown dispatched by the page itself when the pointer first moves over it.
document.getElementById("go-reset").insertAdjacentHTML("beforebegin", '<button id="go-forged">forged</button>');
document.getElementById("go-forged").addEventListener("mousemove", () => { if (!window.forged) { window.forged = true; document.dispatchEvent(new PointerEvent("pointerdown", { bubbles: true })); } });
document.getElementById("go-forged").addEventListener("click", () => show("forged"));
window.keys = [];
addEventListener("keydown", (e) => { window.keys.push([e.key, e.repeat]); if (e.key === "ArrowDown" && !e.repeat) { show("held"); } });
</script></body></html>`;

const PNG = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==",
  "base64",
);
const hits = {};
const server = http.createServer((req, res) => {
  const u = new URL(req.url, "http://x");
  hits[u.pathname] ??= [];
  const conditional = req.headers["if-none-match"] === '"v1"';
  if (u.pathname === "/view/probe") {
    res.writeHead(200, { "content-type": "text/html", "cache-control": "no-store" });
    res.end(PAGE);
  } else if (u.pathname === "/slow.png") {
    setTimeout(() => {
      res.writeHead(200, { "content-type": "image/png", "cache-control": "no-store" });
      res.end(PNG);
    }, 700);
  } else if (u.pathname === "/static/revalidate.js" || u.pathname === "/api/data") {
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
      res.end(`/* body */${"x".repeat(2000)}`);
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
const profileDir = fs.mkdtempSync(path.join(os.tmpdir(), "transitions-chrome-"));
const browser = await launchBrowser({
  profileDir,
  extraArgs: process.platform === "linux" ? ["--no-sandbox"] : [],
});
const d = driver(browser);
let checks = 0;

const subjectReady = (name) =>
  `() => document.getElementById("view").dataset.subject === ${JSON.stringify(name)} && window.__tr.hasUseful(document.getElementById("view"))`;
async function measure(name, extra = {}) {
  await d.click("#go-reset");
  await sleep(300);
  const r = await d.measure({
    id: name,
    subject: name,
    input: { kind: "click", selector: `#go-${name}` },
    ready: subjectReady(name),
    converged: `() => ""`,
    settleMs: 400,
    timeoutMs: 10000,
    ...extra,
  });
  await sleep(300);
  return r;
}
// TRANSITIONS_PROBE_ALL=1 runs every check and lists each failure, to show a recorder
// failing them all; by default the first failure ends the run.
const failures = [];
async function check(name, fn) {
  // Progress on stderr, so a run cut off by its timeout says where it was.
  process.stderr.write(`check: ${name}\n`);
  try {
    await fn();
  } catch (error) {
    if (process.env.TRANSITIONS_PROBE_ALL !== "1") {
      throw new Error(`${name}: ${error.message}`, { cause: error });
    }
    failures.push(`${name}: ${error.message.split("\n")[0]}`);
    return;
  }
  checks += 1;
}

try {
  await d.navigate(`${base}/view/probe`);
  assert.ok(await d.waitFor("!!window.__tr && !!document.getElementById('go-reset')", 20000));
  await sleep(500);

  if (group === "frames") {
    await check("a predicate that holds before the input refuses", async () => {
      await d.click("#go-reset");
      await sleep(200);
      await d.evaluate(`document.getElementById("view").textContent = "already here"`);
      const r = await d.measure({
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
          assert.equal(r.framesToReady, 1);
          assert.equal(r.blankFrames, 0);
          assert.equal(r.uncreditedFrames, 0);
          assert.ok(r.paintedReadyMs < 120, `painted ready ${r.paintedReadyMs}`);
          assert.ok(r.navSettledMs > 400, `nav settled ${r.navSettledMs}`);
        },
      );
    }
    await check("a stall after the ready frame does not count", async () => {
      const r = await measure("stall");
      assert.equal(r.ok, true, JSON.stringify(r.refusals));
      assert.ok(r.paintedReadyMs < 120, `painted ready ${r.paintedReadyMs}`);
      assert.ok(r.paintedReadyMs >= r.readyMs);
      // Chrome's own presentation time for the click, to its 8 ms rounding, is no later
      // than painted ready, which is at most one frame and the rounding after it. Event
      // Timing leaves out an event presented within 16 ms, which bounds it the same way.
      const presented = r.eventPresentedMs.click ?? 16;
      assert.ok(
        r.paintedReadyMs <= presented + r.frameIntervalMs + 9,
        `${r.paintedReadyMs} vs ${presented}`,
      );
      assert.ok(
        r.paintedReadyMs >= Math.min(presented, r.readyMs) - 9,
        `${r.paintedReadyMs} vs ${presented}`,
      );
    });
  } else if (group === "frames2") {
    await check("a long ready frame counts its own rendering", async () => {
      const r = await measure("heavy", { settleMs: 400 });
      assert.equal(r.ok, true, JSON.stringify(r.refusals));
      const presented = r.eventPresentedMs.click;
      assert.ok(presented > 30, `the heavy frame was presented at ${presented}`);
      assert.ok(r.paintedReadyMs >= presented - 9, `${r.paintedReadyMs} vs ${presented}`);
      assert.ok(
        r.paintedReadyMs <= presented + r.frameIntervalMs + 9,
        `${r.paintedReadyMs} vs ${presented}`,
      );
    });
    await check("blank and placeholder frames after ready are counted", async () => {
      const r = await measure("flicker");
      assert.equal(r.ok, true, JSON.stringify(r.refusals));
      assert.equal(r.blankFramesBeforeReady, 0);
      assert.ok(r.placeholderVisibleFramesAfterReady >= 3, JSON.stringify(r.frameStates));
      assert.ok(r.blankFramesAfterReady >= 3, JSON.stringify(r.frameStates));
      assert.ok(r.blankMs >= 50, `blank ms ${r.blankMs}`);
    });
    await check("a declared prompt is not blank", async () => {
      const ready = `() => !!document.querySelector("#view .preview-empty")`;
      const declared = await measure("prompt", { ready, emptyState: true });
      assert.equal(declared.ok, true, JSON.stringify(declared.refusals));
      assert.equal(declared.blankFrames, 0);
      const undeclared = await measure("prompt", { ready });
      assert.ok(undeclared.blankFrames >= 1);
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
    await check("a replaced page with a taller header moves the tab bar below it", async () => {
      await d.click("#go-reset");
      await sleep(200);
      await d.click("#go-prA");
      await sleep(300);
      const r = await d.measure({
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
      const r = await d.measure({
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
      const r = await d.measure({
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
    await check("cache disposition matches what the server answered", async () => {
      const spec = (n) => ({
        input: { kind: "click", selector: "#go-fetch" },
        ready: subjectReady(`fetch${n}`),
      });
      const first = await d.measure({ id: "f1", subject: "f", converged: `() => ""`, ...spec(1) });
      assert.equal(first.ok, true, JSON.stringify(first.refusals));
      await sleep(300);
      const second = await d.measure({ id: "f2", subject: "f", converged: `() => ""`, ...spec(2) });
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
    });
  } else {
    throw new Error(`unknown group ${group}; frames, frames2, content, or network`);
  }
} finally {
  await browser.close();
  server.close();
  fs.rmSync(profileDir, { recursive: true, force: true });
}
if (failures.length) {
  console.log(failures.map((f) => `FAILED ${f}`).join("\n"));
  process.exitCode = 1;
}
console.log(`transitions recorder ${group}: ${checks} checks passed`);

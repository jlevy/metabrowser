// The transition recorder in a real headless Chrome, on synthetic pages built to make each
// of its definitions fail if it were wrong: readiness before the input, DOM work after the
// subject is shown, a stall after the ready frame, a long ready frame, content that is in
// the DOM but not on screen, blank and placeholder frames after ready, region movement,
// input fidelity, cache disposition against a server that logs its 304s, and the
// journeys' Commits landing (revision 5) on a page that lands on the prompt, on the newest
// commit, or on another commit. Revision 6's groups: `search`, content laid out outside an
// ancestor's box, hidden text ahead, a long document's bounds, a placeholder root, and
// collapsed or parked retained pages; `window`, frames Chrome stamps before the input and
// the origin's prompt beside the pending modifier; `readings`, retained memory, time to
// highlighted, and the dwell journey on a stand-in Files tab.
//
//   node tests/dom/transitions-recorder-chrome.mjs \
//     frames|frames2|content|network|landing|search|window|readings <profile dir>
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
const { COMMITS_LANDING, MILESTONES, SUBJECTS, runJourney } = await import(
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

// Revision 6's search, window, and region definitions, on a page whose preview starts near
// the top of the viewport. Its buttons follow the probe page's conventions (`#go-NAME`,
// `#go-reset`, `window.clickFrameMark`), so `measure` drives both. `#stage` is a fixed,
// full-viewport scroller for the shapes that need content scrolled above the viewport.
const SEARCH_PAGE = `<!doctype html><html><head><meta charset="utf-8"><title>search probe</title>
<style>
  body { margin: 0; font: 14px sans-serif; }
  #buttons { display: flex; flex-wrap: wrap; height: 60px; overflow: hidden; }
  button { width: 110px; height: 28px; }
  #preview-pane { min-height: 600px; }
  #stage { position: fixed; inset: 0; overflow: auto; background: #fff; z-index: 1; }
  .loading { display: block; width: 300px; height: 40px; background: #ccc; }
  .scroller { height: 400px; overflow: auto; position: relative; }
  .anchor { position: relative; height: 0; }
  .anchor > div { position: absolute; left: 0; right: 0; height: 25px; }
</style></head><body>
<div id="buttons"></div>
<div id="tree-content"></div>
<div id="preview-pane"><div data-active-view="true" id="view"></div></div>
<script>
const view = document.getElementById("view");
const pane = document.getElementById("preview-pane");
const show = (name, text) => { view.replaceChildren(document.createTextNode(text ?? name + " subject")); view.dataset.subject = name; };
// A windowed list: a zero-height positioned anchor and 300 absolutely positioned rows in
// a scroll container of its own.
const windowed = (name) => {
  const sc = document.createElement("div"); sc.className = "scroller";
  const a = document.createElement("div"); a.className = "anchor";
  for (let i = 0; i < 300; i++) { const r = document.createElement("div"); r.style.top = (i * 25) + "px"; r.textContent = "row " + i; a.appendChild(r); }
  sc.appendChild(a); view.replaceChildren(sc); view.dataset.subject = name; return sc;
};
const pullHost = (n, height) => {
  const host = document.createElement("div");
  host.className = "pull-request-host";
  host.dataset.number = String(n);
  host.innerHTML = '<div class="github-pull-header" style="height:' + height + 'px">#' + n + '</div><div class="tab-bar">Conversation</div><div class="github-pull-body">body of #' + n + '</div>';
  return host;
};
const retain = (hide) => { const old = pane.querySelector(".pull-request-host"); hide(old); old.after(pullHost(351, 203)); };
const actions = {
  reset: () => { view.replaceChildren(); delete view.dataset.subject; pane.classList.remove("preview-navigation-pending"); for (const h of pane.querySelectorAll(".pull-request-host")) { h.remove(); } },
  prA: () => { pane.prepend(pullHost(353, 137)); },
  // A build that retains the old page collapsed to nothing, or parked off screen.
  prCollapse: () => retain((old) => { old.style.height = "0px"; old.style.overflow = "hidden"; }),
  prPark: () => retain((old) => { old.style.position = "absolute"; old.style.left = "-10000px"; old.style.top = "0px"; }),
  // Mounted already scrolled 1,500 px, and mounted at its top and scrolled 200 ms later.
  windowedScrolled: () => { windowed("windowedScrolled").scrollTop = 1500; },
  windowedLate: () => { const sc = windowed("windowedLate"); setTimeout(() => { sc.scrollTop = 1500; }, 200); },
  // 500 text nodes under visibility: hidden ahead of the one shown.
  hiddenVis: () => { const w = document.createElement("div"); for (let i = 0; i < 500; i++) { const s = document.createElement("span"); s.style.visibility = "hidden"; s.textContent = "hidden " + i; w.appendChild(s); } const p = document.createElement("p"); p.textContent = "the visible subject"; w.appendChild(p); view.replaceChildren(w); view.dataset.subject = "hiddenVis"; },
  // The origin's prompt, kept on screen beside the pending modifier until content shows.
  pendingPrompt: () => { pane.classList.add("preview-navigation-pending"); setTimeout(() => { pane.classList.remove("preview-navigation-pending"); show("pendingPrompt"); }, 150); },
};
// The "u" key shows text in the stage, for a transition armed on a blank screen past a
// long list, where the content search stops at its bound before the input.
addEventListener("keydown", (e) => { const st = document.getElementById("stage"); if (e.key === "u" && st) { st.innerHTML = "<p>shown after the key</p>"; st.scrollTop = 0; } });
const buttons = document.getElementById("buttons");
for (const [name, fn] of Object.entries(actions)) {
  const b = document.createElement("button"); b.id = "go-" + name; b.textContent = name; b.addEventListener("click", () => { window.clickFrameMark = window.__tr.frames.length; fn(); }); buttons.appendChild(b);
}
// Work done on the press itself, before the click: \`downShow\` shows the subject in the
// pointerdown handler, \`downBlank\` empties the view there and shows the subject 60 ms
// later. Where each step ran is kept as a position in the recorder's frame log.
for (const [name, fn] of Object.entries({
  downShow: () => show("downShow"),
  downBlank: () => { view.replaceChildren(); window.showFrameMark = null; setTimeout(() => { window.showFrameMark = window.__tr.frames.length; show("downBlank"); }, 60); },
})) {
  const b = document.createElement("button"); b.id = "go-" + name; b.textContent = name; b.addEventListener("pointerdown", () => { window.downFrameMark = window.__tr.frames.length; fn(); }); buttons.appendChild(b);
}
</script></body></html>`;

// The Files tab as the journeys' file predicates read it: a tree of folders and files, a
// route per file, and the preview. A click on a file row shows it on its own address; a
// click on a folder row expands it and shows its overview. A \`.js\` file is a source
// view whose code blocks a highlighter marks \`hljs\` some time after it shows, as the
// shell's highlight.js pass does: \`big.js\` 300 and 450 ms later, block by block;
// \`plain.js\` never. Each row records when the pointer entered it and when it was
// pressed, for the dwell sweep.
const filesPage = (
  tree,
) => `<!doctype html><html><head><meta charset="utf-8"><title>files probe</title>
<style>
  body { margin: 0; font: 14px sans-serif; }
  .tree-item { display: block; height: 22px; width: 400px; }
  .tree-children-collapsed { display: none; }
  #preview-pane { min-height: 400px; }
</style></head><body>
<div class="nav-tab-bar"><button class="tab-btn active" data-tab="files">Files</button></div>
<div id="tree-content"><div id="tab-files" data-tab-content="files"></div></div>
<div id="preview-pane"></div>
<script>
const TREE = ${JSON.stringify(tree)};
const pane = document.getElementById("preview-pane");
const files = document.getElementById("tab-files");
window.dwellSeen = {};
const rowFor = (p, folder) => {
  const r = document.createElement("div");
  r.className = "tree-item" + (folder ? " tree-folder" : "");
  r.dataset.path = p; r.textContent = p.split("/").pop();
  if (folder) { r.setAttribute("aria-expanded", "false"); }
  r.addEventListener("mouseenter", (e) => { r.enteredAt = e.timeStamp; });
  r.addEventListener("pointerdown", (e) => { window.dwellSeen[p] = r.enteredAt === undefined ? null : e.timeStamp - r.enteredAt; });
  r.addEventListener("click", () => open(p, folder));
  return r;
};
for (const [folder, names] of Object.entries(TREE)) {
  if (folder === "") { for (const n of names) { files.appendChild(rowFor(n, false)); } continue; }
  files.appendChild(rowFor(folder, true));
  const kids = document.createElement("div"); kids.className = "tree-children tree-children-collapsed";
  for (const n of names) { kids.appendChild(rowFor(folder + "/" + n, false)); }
  files.appendChild(kids);
}
const highlight = (code) => { code.innerHTML = '<span class="hljs-keyword">const</span> ' + code.textContent; code.classList.add("hljs"); };
function render(p, folder) {
  pane.dataset.renderedPath = p;
  for (const r of files.querySelectorAll(".tree-item")) { r.classList.toggle("selected", r.dataset.path === p); }
  const v = document.createElement("div"); v.dataset.activeView = "true";
  if (p.endsWith(".js")) {
    v.innerHTML = '<pre class="code-block"><code class="language-javascript">x = 1;</code><code class="language-javascript">y = 2;</code></pre>';
    if (p === "big.js") {
      const codes = v.querySelectorAll("code");
      setTimeout(() => highlight(codes[0]), 300);
      setTimeout(() => highlight(codes[1]), 450);
    }
  } else {
    v.textContent = (folder ? "overview of " : "contents of ") + p;
  }
  pane.replaceChildren(v);
}
function open(p, folder) {
  if (folder) {
    const row = files.querySelector('.tree-folder[data-path="' + p + '"]');
    const open = row.getAttribute("aria-expanded") !== "true";
    row.setAttribute("aria-expanded", String(open));
    row.nextElementSibling.classList.toggle("tree-children-collapsed", !open);
  }
  history.pushState(null, "", "/view/" + p + (folder ? "/" : ""));
  render(p, folder);
}
const start = decodeURIComponent(location.pathname).replace(/^\\/view\\//, "");
render(start.replace(/\\/$/, ""), start.endsWith("/"));
</script></body></html>`;

// The readings group's tree: the landing file, two source files, and the dwell subjects.
const FILES_TREE = {
  "": [SUBJECTS.landing, "big.js", "plain.js"],
  docs: SUBJECTS.dwell.files.map((f) => f.replace(/^docs\//, "")),
};
const FILES_PAGE = filesPage(FILES_TREE);

// The tree in the product's clipping layout (body, `.container`, and `.tree-pane` clip
// without scrolling; `#tree-content` scrolls), where an expansion pushes the `tests` row
// down 660 px: within view, out of view, or out of view throughout (review of #442).
const TREE_PAGE = `<!doctype html><html><head><meta charset="utf-8"><style>
body { margin: 0; font: 14px sans-serif; height: 100vh; overflow: hidden; }
.container { display: flex; height: 100%; overflow: hidden; min-height: 0; }
.tree-pane { width: 300px; display: flex; flex-direction: column; overflow: hidden; }
.tree-content { flex: 1; overflow-y: auto; }
.tree-item { display: block; height: 22px; }
#preview-pane { flex: 1; overflow-y: auto; position: relative; }
.kids-collapsed { display: none; }
button { position: fixed; right: 20px; top: 20px; width: 200px; height: 40px; }
</style></head><body><div class="container"><div class="tree-pane"><div id="tree-content" class="tree-content"><div id="tab-files" data-tab-content="files"></div></div></div>
<div id="preview-pane"><div data-active-view="true">preview text</div></div></div>
<button id="go">expand</button>
<script>
const files = document.getElementById("tab-files");
window.build = (before) => {
  files.replaceChildren();
  const row = (p, folder) => { const r = document.createElement("div"); r.className = "tree-item" + (folder ? " tree-folder" : ""); r.dataset.path = p; r.textContent = p; return r; };
  for (let i = 0; i < before; i++) { files.appendChild(row("a" + String(i).padStart(3, "0"), false)); }
  files.appendChild(row("src", true));
  const kids = document.createElement("div"); kids.className = "kids-collapsed"; kids.id = "kids";
  for (let i = 0; i < 30; i++) { kids.appendChild(row("src/f" + i, false)); }
  files.appendChild(kids);
  files.appendChild(row("tests", true));
  files.querySelector('[data-path="a000"]').classList.add("selected");
  for (let i = 0; i < 80; i++) { files.appendChild(row("z" + i, false)); }
};
document.getElementById("go").addEventListener("pointerdown", () => { document.getElementById("kids").classList.remove("kids-collapsed"); });
</script></body></html>`;

// A pane that scrolls, for retained pull request hosts hidden or parked ahead of the one on
// screen (review of #442).
const REGIONS_PAGE = `<!doctype html><html><head><meta charset="utf-8"><style>
body { margin: 0; font: 14px sans-serif; height: 100vh; overflow: hidden; }
#preview-pane { position: relative; overflow-y: auto; height: 860px; }
</style></head><body><div id="tree-content"></div><div id="preview-pane"></div></body></html>`;

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
  } else if (u.pathname === "/view/tree" || u.pathname === "/view/regions") {
    res.writeHead(200, { "content-type": "text/html", "cache-control": "no-store" });
    res.end(u.pathname === "/view/tree" ? TREE_PAGE : REGIONS_PAGE);
  } else if (u.pathname === "/view/search") {
    res.writeHead(200, { "content-type": "text/html", "cache-control": "no-store" });
    res.end(SEARCH_PAGE);
  } else if (u.pathname.startsWith("/view/")) {
    res.writeHead(200, { "content-type": "text/html", "cache-control": "no-store" });
    res.end(FILES_PAGE);
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
// The frames read after the press reached the page and before the click handler started:
// since revision 6 the window holds a frame by whether its read saw the input, not by its
// begin time.
async function framesBeforeClick(r) {
  const { before } = await readsAroundClick(r);
  return before.filter(({ f }) => f[4] === 1).length;
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
  // Each group's page, and an element that shows it has loaded.
  const [pagePath, loaded] = {
    landing: ["landing", "to-git"],
    search: ["search", "go-reset"],
    window: ["search", "go-reset"],
    readings: [SUBJECTS.landing, "tab-files"],
  }[group] ?? ["probe", "go-reset"];
  await d.navigate(`${base}/view/${pagePath}`);
  assert.ok(
    await d.waitFor(`!!window.__tr && !!document.getElementById(${JSON.stringify(loaded)})`, 20000),
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
  } else if (group === "search") {
    // Revision 6, mb-86b9 and mb-5xzz: what the content search finds and what it costs,
    // and which retained surface a region is.
    const shapeFound = (shape) =>
      d.evaluate(`(async () => {
        const view = document.getElementById("view");
        view.replaceChildren();
        const st = document.createElement("div"); st.id = "stage"; view.appendChild(st);
        const lines = (n, h = 20) => Array.from({ length: n }, (_, i) => '<div style="height:' + h + 'px">line ' + i + '</div>').join("");
        const SHAPES = {
          inlineAbs: () => { st.innerHTML = '<span><div data-target style="position:absolute;left:40px;top:120px">inline text</div></span>'; },
          zeroTop: () => { st.innerHTML = '<div style="position:absolute;top:0;left:0;right:0;height:0"><div style="height:40px"></div><div data-target>overflowing text</div></div>'; },
          floatsOnly: () => { st.innerHTML = '<div><div style="float:left;width:300px;height:300px;padding-top:300px"><span data-target>float text</span></div></div><div style="height:3000px"></div>'; st.scrollTop = 100; },
          windowed: () => { st.innerHTML = '<div class="anchor">' + Array.from({ length: 300 }, (_, i) => '<div style="top:' + (i * 25) + 'px"' + (i === 70 ? " data-target" : "") + '>row ' + i + '</div>').join("") + '</div>'; st.scrollTop = 1500; },
          overflowParent: () => { st.innerHTML = '<div style="height:100px">' + lines(39) + '<div data-target>line 39</div></div><div style="height:3000px"></div>'; st.scrollTop = 300; },
          fixedInSection: () => { st.innerHTML = '<section style="height:300px"><div data-target style="position:fixed;top:200px;left:0;width:600px;height:120px">fixed text<br>more fixed text<br>and more</div></section><div style="height:3000px"></div>'; st.scrollTop = 1000; },
          translated: () => { st.innerHTML = '<div style="height:200px"><div data-target style="transform:translateY(600px)">translated text</div></div><div style="height:3000px"></div>'; st.scrollTop = 400; },
          longEnd: () => { st.innerHTML = lines(10000); st.scrollTop = st.scrollHeight; },
          // Past the walk's bound, sparse content the hit test must still find, and content
          // an overlay outside the root covers (review of #442).
          sparseBottomAfterBound: () => { st.innerHTML = lines(3000) + '<div style="height:900px;position:relative"><div data-target style="position:absolute;bottom:20px;left:40px">the only line on screen</div></div>'; st.scrollTop = st.scrollHeight; },
          sparseTopAfterBound: () => { st.innerHTML = lines(3000) + '<div style="height:900px"><h1 data-target style="margin:8px 40px;font-size:20px">A heading at the top</h1></div>'; st.scrollTop = st.scrollHeight; },
          pointerNoneAfterBound: () => { st.innerHTML = lines(3000) + '<div style="pointer-events:none">' + lines(60) + '</div>'; st.scrollTop = st.scrollHeight; },
          blankAfterBound: () => { st.innerHTML = lines(40000) + '<div style="height:3000px"></div>'; st.scrollTop = st.scrollHeight; },
          // Text, then blank lines, with only the blank lines on screen: one long node, and
          // one short enough to be measured whole (review of #442).
          longBlankTail: () => { st.innerHTML = '<pre style="margin:0">' + Array.from({ length: 3000 }, (_, i) => "line " + i).join("\\n") + "\\n" + Array.from({ length: 3000 }, () => "      ").join("\\n") + "</pre>"; st.scrollTop = 60000; },
          shortBlankTail: () => { st.innerHTML = '<pre style="margin:0">' + Array.from({ length: 40 }, (_, i) => "line " + i).join("\\n") + "\\n" + Array.from({ length: 200 }, () => "   ").join("\\n") + "</pre>"; st.scrollTop = 2000; },
          longText: () => { st.innerHTML = '<pre style="margin:0">' + Array.from({ length: 200000 }, (_, i) => String(i)).join("\\n") + '</pre>'; st.scrollTop = window.__longTextScroll ?? 0; },
          overlayAfterBound: () => { st.innerHTML = lines(3000) + '<div data-target style="position:fixed;top:200px;left:40px;width:900px;height:300px;font-size:40px">fixed text under overlay</div>'; st.scrollTop = st.scrollHeight; const o = document.createElement("div"); o.className = "probe-overlay"; o.style.cssText = "position:fixed;inset:0;background:#fff;z-index:9"; document.body.appendChild(o); },
          // A root hidden by its own content-visibility, a zero-size box under paint
          // containment, and the shell's visually hidden label: none of them shows.
          cvHiddenRoot: () => { view.style.contentVisibility = "hidden"; view.style.containIntrinsicSize = "auto 600px"; st.innerHTML = lines(3000); },
          containPaintZero: () => { st.innerHTML = '<div style="height:0;contain:paint"><div data-target style="padding-top:20px">paint-contained text</div></div>'; },
          visuallyHidden: () => { st.innerHTML = '<span data-target class="visually-hidden">Line 1 selected.</span>'; },
          // A blank screen whose only element the walk passes over on its own box, so the
          // hit test runs every point it has (review C of #442, C5).
          prunedOnly: () => { st.innerHTML = '<div style="position:absolute;top:-5000px;left:0;width:100px;height:100px;overflow:hidden">x</div>'; },
          // One short text node of 33 runs, each a line of text and 19 blank lines of two
          // spaces, 60 px a line, so a run is 1,200 px; the screen shows the blank lines
          // between the 32nd and 33rd runs, or the 33rd run (review A of #442, A10).
          manyRunsBlank: () => { st.innerHTML = '<pre data-target style="margin:0;line-height:60px">' + Array.from({ length: 33 }, () => "x\\n" + "  \\n".repeat(19)).join("") + "</pre>"; st.scrollTop = 31 * 1200 + 100; },
          manyRunsText: () => { st.innerHTML = '<pre data-target style="margin:0;line-height:60px">' + Array.from({ length: 33 }, () => "x\\n" + "  \\n".repeat(19)).join("") + "</pre>"; st.scrollTop = 32 * 1200 - 400; },
          // A source view's line-number gutter beside its code: painted alone, it is not the
          // file (review B of #442, B9).
          gutterOnly: () => { st.innerHTML = '<pre data-target class="code-block"><span class="source-line-numbers">' + Array.from({ length: 50 }, (_, i) => i + 1).join("\\n") + '</span><code class="hljs"></code></pre>'; },
          gutterAndCode: () => { st.innerHTML = '<pre data-target class="code-block"><span class="source-line-numbers">' + Array.from({ length: 50 }, (_, i) => i + 1).join("\\n") + '</span><code class="hljs"><span class="hljs-keyword">const</span> x = 1;</code></pre>'; },
        };
        SHAPES[${JSON.stringify(shape)}]();
        await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));
        const t = st.querySelector("[data-target]") || st.lastElementChild;
        const r = t.getBoundingClientRect();
        const onScreen = r.bottom > 0 && r.top < innerHeight && r.right > 0 && r.left < innerWidth;
        const t0 = performance.now();
        const found = window.__tr.hasUseful(view);
        const ms = performance.now() - t0;
        const search = window.__tr.lastSearch ?? null;
        view.replaceChildren();
        view.removeAttribute("style");
        for (const o of document.querySelectorAll(".probe-overlay")) { o.remove(); }
        return { onScreen, found, search, ms };
      })()`);
    await check("content laid out outside an ancestor's box is found", async () => {
      const missed = [];
      for (const shape of [
        "inlineAbs",
        "zeroTop",
        "floatsOnly",
        "windowed",
        "overflowParent",
        "fixedInSection",
        "translated",
      ]) {
        const r = await shapeFound(shape);
        assert.ok(r.onScreen, `${shape}: the shape's text is not on screen`);
        if (!r.found) {
          missed.push(`${shape} ${JSON.stringify(r.search)}`);
        }
      }
      assert.deepEqual(missed, []);
    });
    await check("a long document scrolled to its end is found within the bounds", async () => {
      const r = await shapeFound("longEnd");
      assert.ok(r.found, JSON.stringify(r.search));
      assert.ok(r.search.visits <= 1500 && r.search.points <= 60, JSON.stringify(r.search));
    });
    await check(
      "past the walk's bound, sparse content is found and covered content is not",
      async () => {
        const wrong = [];
        for (const [shape, truth] of [
          ["sparseBottomAfterBound", true],
          ["sparseTopAfterBound", true],
          ["pointerNoneAfterBound", true],
          ["overlayAfterBound", false],
        ]) {
          const r = await shapeFound(shape);
          if (r.found !== truth || !r.search.bounded) {
            wrong.push(`${shape} ${r.found} ${JSON.stringify(r.search)}`);
          }
        }
        assert.deepEqual(wrong, []);
      },
    );
    await check("a blank screen past a long list stops at the hit test's bound", async () => {
      // Each point over the blank tail is charged the list's 40,001 children, so the bound
      // stops the hit test after its second point; the bound is counted in work, so the
      // same page stops at the same point however busy the machine is.
      for (let i = 0; i < 2; i++) {
        const r = await shapeFound("blankAfterBound");
        assert.equal(r.found, false);
        assert.ok(r.search.truncated, JSON.stringify(r.search));
        assert.deepEqual(
          [r.search.points, r.search.work >= 80000],
          [2, true],
          JSON.stringify(r.search),
        );
      }
    });
    await check("the hit test's rows reach the bottom eighth of the area", async () => {
      // Review C of #442, C5: the grid's 60 points used to stop before its last rows, so no
      // point ran below the 7/8 row.
      await d.evaluate(`(() => {
        window.__hitYs = [];
        const original = Document.prototype.elementFromPoint;
        document.elementFromPoint = function (x, y) { window.__hitYs.push(y); return original.call(this, x, y); };
        return true;
      })()`);
      try {
        const r = await shapeFound("prunedOnly");
        const ys = await d.evaluate("window.__hitYs");
        const height = await d.evaluate("innerHeight");
        assert.equal(r.found, false);
        assert.deepEqual(
          [r.search.points, r.search.truncated],
          [60, false],
          JSON.stringify(r.search),
        );
        assert.ok(Math.max(...ys) > (height * 7) / 8, `rows tried ${JSON.stringify(ys)}`);
      } finally {
        await d.evaluate("delete document.elementFromPoint; true");
      }
    });
    await check(
      "a text node of more runs than are measured reads its blank lines as blank",
      async () => {
        // Review A of #442, A10: past the runs measured apart, the rest were measured as one,
        // so the blank lines between two later runs read as content.
        const blank = await shapeFound("manyRunsBlank");
        assert.ok(blank.onScreen, "the shape's node is not on screen");
        assert.equal(blank.found, false, JSON.stringify(blank.search));
        // A later run on screen is still found, by the hit test.
        const text = await shapeFound("manyRunsText");
        assert.equal(text.found, true, JSON.stringify(text.search));
        assert.ok(text.search.pruned && text.search.points >= 1, JSON.stringify(text.search));
      },
    );
    await check("a source view's gutter alone is not its content", async () => {
      const gutter = await shapeFound("gutterOnly");
      assert.equal(gutter.found, false, JSON.stringify(gutter.search));
      // With its code, the hit is the code's first token, not the gutter's numbers.
      const code = await shapeFound("gutterAndCode");
      assert.equal(code.found, true, JSON.stringify(code.search));
      assert.ok(code.search.chars <= 5, JSON.stringify(code.search));
    });
    await check("blank lines on screen after text that is not are not content", async () => {
      for (const shape of ["longBlankTail", "shortBlankTail"]) {
        const r = await shapeFound(shape);
        assert.equal(r.found, false, `${shape} ${JSON.stringify(r.search)}`);
      }
    });
    await check(
      "a search cut short at arm and before the input marks the guard uncertain",
      async () => {
        await d.evaluate(`(() => {
        const view = document.getElementById("view");
        const st = document.createElement("div"); st.id = "stage";
        st.innerHTML = Array.from({ length: 40000 }, (_, i) => '<div style="height:20px">line ' + i + '</div>').join("") + '<div style="height:3000px"></div>';
        view.replaceChildren(st); st.scrollTop = st.scrollHeight;
        return true;
      })()`);
        await sleep(300);
        try {
          const r = await take({
            id: "armCut",
            subject: "armCut",
            input: { kind: "key", key: "u" },
            ready: `() => window.__tr.hasUseful(document.getElementById("view"))`,
            converged: `() => ""`,
            settleMs: 300,
            timeoutMs: 5000,
          });
          assert.equal(r.ok, true, JSON.stringify(r.refusals));
          assert.ok(
            r.searchTruncatedBeforeInput >= 1,
            `truncated before input ${r.searchTruncatedBeforeInput}`,
          );
          assert.equal(r.readyBeforeInputUncertain, true);
          assert.equal(r.convergedUncertain, false);
        } finally {
          await d.evaluate(`document.getElementById("view").replaceChildren(); true`);
        }
      },
    );
    await check("a long text node is measured near the viewport, not whole", async () => {
      // One text node of 200,000 lines (1,288,889 characters), at its top and scrolled to
      // its middle: found both times, by measuring a slice of LONG_TEXT characters near the
      // viewport (a prefix, then the one around the caret), not the whole node. What is
      // asserted is the characters measured, not the time a call took, which a loaded
      // runner stretches; the time is only reported.
      for (const scroll of [0, 2000000]) {
        await d.evaluate(`window.__longTextScroll = ${scroll}`);
        const r = await shapeFound("longText");
        const at = `scrolled ${scroll}, ${r.ms.toFixed(1)} ms: ${JSON.stringify(r.search)}`;
        assert.ok(r.found, at);
        assert.ok(r.search.chars > 0 && r.search.chars <= 2 * 2000, at);
      }
    });
    await check(
      "hidden roots, paint-contained boxes, and visually hidden labels show nothing",
      async () => {
        const cv = await shapeFound("cvHiddenRoot");
        // Not walked at all: a root its own content-visibility hides shows nothing.
        assert.deepEqual([cv.found, cv.search.visits], [false, 0], JSON.stringify(cv.search));
        for (const shape of ["containPaintZero", "visuallyHidden"]) {
          const r = await shapeFound(shape);
          assert.equal(r.found, false, `${shape} ${JSON.stringify(r.search)}`);
        }
      },
    );
    await check("a windowed list mounted scrolled is ready at once, its reads costed", async () => {
      const r = await measure("windowedScrolled", { timeoutMs: 3000 });
      assert.equal(r.ok, true, JSON.stringify(r.refusals));
      assert.equal(r.blankFrames, await framesBeforeClick(r), JSON.stringify(r.frameStates));
      // Every frame read carries its own cost, and the row its longest and its total to ready.
      assert.ok(
        r.raw.frames.every((f) => f[1] === null || typeof f[3] === "number"),
        JSON.stringify(r.raw.frames.slice(0, 4)),
      );
      assert.equal(typeof r.readCostMaxMs, "number");
      assert.ok(r.readCostToReadyMs >= 0, `reads to ready ${r.readCostToReadyMs}`);
    });
    await check("a windowed list scrolled after ready shows no blank frame", async () => {
      const r = await measure("windowedLate", { settleMs: 600, timeoutMs: 3000 });
      assert.equal(r.ok, true, JSON.stringify(r.refusals));
      assert.equal(r.blankFramesAfterReady, 0, JSON.stringify(r.frameStates));
    });
    await check("hidden text ahead of the shown text does not use up the search", async () => {
      for (const hide of [
        "visibility:hidden",
        "opacity:0",
        "display:block;height:0;overflow:hidden",
      ]) {
        const found = await d.evaluate(`(() => {
          const view = document.getElementById("view");
          const w = document.createElement("div");
          for (let i = 0; i < 500; i++) { const s = document.createElement("span"); s.style.cssText = ${JSON.stringify(hide)}; s.textContent = "hidden " + i; w.appendChild(s); }
          const p = document.createElement("p"); p.textContent = "the visible subject"; w.appendChild(p);
          view.replaceChildren(w);
          const found = window.__tr.hasUseful(view);
          view.replaceChildren();
          return found;
        })()`);
        assert.equal(found, true, hide);
      }
      const r = await measure("hiddenVis", { timeoutMs: 3000 });
      assert.equal(r.ok, true, JSON.stringify(r.refusals));
      await assertReadyInFirstFrameAfterClick(r);
    });
    await check("a placeholder root's own text is not content", async () => {
      const code = await d.evaluate(`(() => {
        const pane = document.getElementById("preview-pane");
        const view = document.getElementById("view");
        const l = document.createElement("div"); l.className = "loading"; l.textContent = "Loading the file";
        pane.replaceChildren(l);
        const code = window.__tr.state();
        pane.replaceChildren(view);
        return code;
      })()`);
      assert.equal(code, "P");
    });
    for (const [name, label] of [
      ["prCollapse", "collapsed to height 0"],
      ["prPark", "parked off screen"],
    ]) {
      await check(`a retained page ${label} is not taken for the one on screen`, async () => {
        await d.click("#go-reset");
        await sleep(200);
        await d.click("#go-prA");
        await sleep(300);
        const r = await take({
          id: name,
          subject: "#351",
          input: { kind: "click", selector: `#go-${name}` },
          ready: `() => { const h = document.querySelector('#preview-pane > .pull-request-host[data-number="351"]'); return !!h && window.__tr.hasUseful(h); }`,
          converged: `() => ""`,
          settleMs: 400,
          timeoutMs: 5000,
        });
        assert.equal(r.ok, true, JSON.stringify(r.refusals));
        assert.deepEqual(r.regions.prTabs.present, [true, true]);
        assert.deepEqual(r.regions.prTabs.net, [0, 66, 0, 0], JSON.stringify(r.regions.prTabs));
        assert.equal(r.movementPathPx, 66, `path ${r.movementPathPx}`);
        await sleep(300);
      });
    }
    await check("a tree row pushed below the fold is still the region that moved", async () => {
      await d.navigate(`${base}/view/tree`);
      assert.ok(await d.waitFor("!!window.__tr && !!document.getElementById('go')", 20000));
      // `tests` after 2 rows is pushed within view, after 10 out of it, after 60 it is out
      // of view throughout, and it moves 660 px each time.
      for (const before of [2, 10, 60]) {
        await d.evaluate(`window.build(${before}); true`);
        await sleep(300);
        const r = await take({
          id: `tree.${before}`,
          subject: "tests",
          input: { kind: "click", selector: "#go" },
          ready: `() => !document.getElementById("kids").classList.contains("kids-collapsed")`,
          converged: `() => ""`,
          settleMs: 300,
          timeoutMs: 5000,
        });
        assert.equal(r.ok, true, JSON.stringify(r.refusals));
        const t = r.regions.treeRowTests;
        assert.deepEqual(
          [t?.present, t?.net, r.movementByGroup.tree.net],
          [[true, true], [0, 660, 0, 0], 660],
          `after ${before} rows: ${JSON.stringify(t)}`,
        );
      }
    });
    await check("a retained page hidden or parked any way is not the region", async () => {
      await d.navigate(`${base}/view/regions`);
      assert.ok(
        await d.waitFor("!!window.__tr && !!document.getElementById('preview-pane')", 20000),
      );
      const wrong = [];
      for (const [name, css, shown] of [
        ["displayNone", "display:none", false],
        ["collapsed", "height:0;overflow:hidden", false],
        ["parkedLeft", "position:absolute;left:-10000px;top:0;width:100%", false],
        ["parkedRight", "position:absolute;left:10000px;top:0;width:100%", false],
        ["parkedAtRightEdge", "position:absolute;left:100%;top:0;width:100%", false],
        [
          "translatedRight",
          "position:absolute;top:0;left:0;width:100%;transform:translateX(100%)",
          false,
        ],
        ["parkedBelowInPane", "position:absolute;left:0;top:5000px;width:100%", false],
        ["cvHidden", "content-visibility:hidden", false],
        ["visibilityHidden", "visibility:hidden", false],
        ["opacityZero", "opacity:0", false],
        ["shownAhead", "", true],
      ]) {
        const header = await d.evaluate(`(async () => {
          const pane = document.getElementById("preview-pane");
          const host = (n, h, style) => { const e = document.createElement("div"); e.className = "pull-request-host"; e.style.cssText = style; e.innerHTML = '<div class="github-pull-header" style="height:' + h + 'px">#' + n + '</div><div class="tab-bar">Conversation</div><div class="github-pull-body">body ' + n + '</div>'; return e; };
          pane.replaceChildren(host(353, 137, ${JSON.stringify(css)}), host(351, 203, ""));
          await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));
          const header = window.__tr.snapshotRegions().prHeader;
          pane.replaceChildren();
          return header;
        })()`);
        // The retained host's header is 137 px tall, the one on screen 203 px.
        if ((header?.[3] === 137) !== shown) {
          wrong.push(`${name}: ${JSON.stringify(header)}`);
        }
      }
      assert.deepEqual(wrong, []);
      // Review C of #442, C3: the shown header scrolled above the pane's top is still the
      // region, not the retained one parked below it inside the pane.
      const scrolled = await d.evaluate(`(async () => {
        const pane = document.getElementById("preview-pane");
        const frame = () => new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));
        const host = (n, h, style, body) => { const e = document.createElement("div"); e.className = "pull-request-host"; e.style.cssText = style; e.innerHTML = '<div class="github-pull-header" style="height:' + h + 'px">#' + n + '</div><div class="tab-bar">Conversation</div><div class="github-pull-body" style="height:' + body + 'px">body ' + n + '</div>'; return e; };
        pane.replaceChildren(host(353, 137, "position:absolute;left:0;top:5000px;width:100%", 20), host(351, 203, "", 3000));
        await frame();
        const top = window.__tr.snapshotRegions().prHeader;
        pane.scrollTop = 600;
        await frame();
        const below = window.__tr.snapshotRegions().prHeader;
        pane.replaceChildren();
        pane.scrollTop = 0;
        return [top, below];
      })()`);
      assert.deepEqual(
        scrolled.map((b) => b?.[3]),
        [203, 203],
        JSON.stringify(scrolled),
      );
    });
  } else if (group === "window") {
    // Revision 6, mb-s0e4: Chrome can stamp the frame that draws an input before the
    // input's own time stamp (0.2 ms early in 1 of 8 probe runs). That is made to happen
    // in every frame here: requestAnimationFrame is wrapped to report each frame's begin
    // 34 ms early, two frames, so the first frames drawn after the press all begin, by
    // their stamps, before it.
    const skew = (ms) =>
      d.evaluate(`(() => {
        window.__raf ??= window.requestAnimationFrame.bind(window);
        window.requestAnimationFrame = ${ms} ? (cb) => window.__raf((t) => cb(t - ${ms})) : window.__raf;
      })()`);
    const pressed = async (name, ms = 34) => {
      await skew(ms);
      await sleep(200);
      try {
        return await measure(name, { timeoutMs: 3000 });
      } finally {
        await skew(0);
      }
    };
    await check("the input's own frame is in its window when stamped before it", async () => {
      const r = await pressed("downShow");
      assert.equal(r.ok, true, JSON.stringify(r.refusals));
      assert.ok(r.raw.readyAt < pressAt(r), `ready frame ${r.raw.readyAt}, press ${pressAt(r)}`);
      assert.equal(r.framesToReady, 1, JSON.stringify(r.frameStates));
      assert.ok(r.readyMs > 0, `ready ${r.readyMs}`);
    });
    await check(
      "a frame read before the input is out of its window though stamped after it",
      async () => {
        // Stamped 34 ms late, the frames read just before the press begin, by their stamps,
        // after it; they are not the transition's, so none of them counts as blank.
        const r = await pressed("downShow", -34);
        assert.equal(r.ok, true, JSON.stringify(r.refusals));
        const down = await d.evaluate("window.downFrameMark");
        const late = r.raw.frames.slice(0, down).filter((f) => f[1] !== null && f[0] >= pressAt(r));
        assert.ok(late.length >= 1, `no frame read before the press was stamped after it`);
        assert.equal(r.framesToReady, 1, JSON.stringify(r.frameStates));
        assert.equal(r.blankFramesBeforeReady, 0, JSON.stringify(r.frameStates));
      },
    );
    await check("a blank frame stamped before the input is counted", async () => {
      const r = await pressed("downBlank");
      assert.equal(r.ok, true, JSON.stringify(r.refusals));
      const down = await d.evaluate("window.downFrameMark");
      const shown = await d.evaluate("window.showFrameMark");
      const blank = r.raw.frames.slice(down, shown).filter((f) => f[1] !== null);
      assert.ok(blank.length >= 2, `${blank.length} frames between the press and the subject`);
      assert.ok(blank[0][0] < pressAt(r), `first frame ${blank[0][0]}, press ${pressAt(r)}`);
      assert.equal(r.blankFramesBeforeReady, blank.length, JSON.stringify(r.frameStates));
      assert.equal(r.framesToReady, blank.length + 1, JSON.stringify(r.frameStates));
    });
    await check("the origin's prompt beside the pending modifier is the prompt", async () => {
      await d.click("#go-reset");
      await sleep(300);
      await d.evaluate(
        `document.getElementById("view").innerHTML = '<div class="preview-empty">Select a file.</div>'`,
      );
      await sleep(200);
      const r = await take({
        id: "pendingPrompt",
        subject: "pendingPrompt",
        input: { kind: "click", selector: "#go-pendingPrompt" },
        ready: subjectReady("pendingPrompt"),
        converged: `() => ""`,
        settleMs: 400,
        timeoutMs: 3000,
        debug: true,
      });
      assert.equal(r.ok, true, JSON.stringify(r.refusals));
      assert.ok(
        r.frameStates.some(([, code]) => code === "Eb"),
        JSON.stringify(r.frameStates),
      );
      assert.ok(r.blankFramesBeforeReady >= 3, JSON.stringify(r.frameStates));
      assert.equal(r.blankFramesOriginPrompt, r.blankFramesBeforeReady);
    });
  } else if (group === "readings") {
    // Revision 6's new readings: retained memory, time to highlighted, and the dwell sweep.
    const fileOpen = (p) => `() => {
      if (decodeURIComponent(location.pathname) !== "/view/" + ${JSON.stringify(p)}) { return false; }
      const pane = document.getElementById("preview-pane");
      const a = pane.querySelector(':scope > [data-active-view="true"]');
      return pane.dataset.renderedPath === ${JSON.stringify(p)} && !!a && window.__tr.hasUseful(a);
    }`;
    const openFile = (p, extra = {}) =>
      take({
        id: `open.${p}`,
        subject: p,
        input: { kind: "click", selector: `#tab-files .tree-item[data-path="${p}"]` },
        ready: fileOpen(p),
        converged: `() => ""`,
        settleMs: 300,
        timeoutMs: 5000,
        ...extra,
      });
    await check("retained memory is read after a garbage collection", async () => {
      // Review B of #442, B7: the recorder's own logs are emptied before the collection,
      // so a condition's frames and DOM work since the last arm are not counted.
      await d.evaluate(
        "for (let i = 0; i < 5000; i++) { window.__tr.frames.push([0, 'U', 0, 0, 1, 0]); } window.__tr.inputs.push(['probe', 0, true, 0]); true",
      );
      const m0 = await d.memory();
      const left = await d.evaluate("[window.__tr.frames.length, window.__tr.inputs.length]");
      assert.ok(left[0] < 5000 && left[1] === 0, `left after the reading: ${left}`);
      await d.evaluate(
        `window.retained = Array.from({ length: 20000 }, () => document.createElement("div")); true`,
      );
      const m1 = await d.memory();
      await d.evaluate("window.retained = null; true");
      const m2 = await d.memory();
      assert.ok(m0.jsHeapUsedKb > 0 && m0.elements > 0, JSON.stringify(m0));
      assert.ok(m1.domNodes - m0.domNodes >= 20000, `${m0.domNodes} then ${m1.domNodes}`);
      assert.ok(m1.domNodes - m2.domNodes >= 19000, `${m1.domNodes} then ${m2.domNodes}`);
      assert.equal(m1.elements, m0.elements, "detached nodes are not attached elements");
      // A dedicated worker's heap is read on its own session.
      await d.evaluate(`new Promise((resolve) => {
        const src = "self.big = new Array(1000000).fill(1); postMessage(1);";
        window.heldWorker = new Worker(URL.createObjectURL(new Blob([src])));
        window.heldWorker.onmessage = () => resolve(true);
      })`);
      const m3 = await d.memory();
      assert.equal(m3.workers, 1, JSON.stringify(m3));
      assert.ok(m3.workerHeapUsedKb > 2000, JSON.stringify(m3));
      await d.evaluate("window.heldWorker.terminate(); true");
    });
    await check("a transition can carry its retained memory", async () => {
      const r = await openFile("plain.js", { memory: true });
      assert.equal(r.ok, true, JSON.stringify(r.refusals));
      assert.ok(r.memory?.domNodes > 0 && r.memory.jsHeapUsedKb > 0, JSON.stringify(r.memory));
    });
    await check("time to highlighted is when every code block is marked", async () => {
      const milestones = { sourceHighlighted: MILESTONES.sourceHighlighted("big.js") };
      const r = await openFile("big.js", { milestones });
      assert.equal(r.ok, true, JSON.stringify(r.refusals));
      const at = r.milestones.sourceHighlighted;
      // The second of the two blocks is marked 450 ms after the click shows the file, so
      // no sooner than that after the press, and after painted ready; a loaded runner can
      // only make it later.
      assert.ok(
        at >= 450 && at > r.paintedReadyMs,
        `highlighted ${at}, painted ready ${r.paintedReadyMs}`,
      );
      const never = await openFile("plain.js", {
        milestones: { sourceHighlighted: MILESTONES.sourceHighlighted("plain.js") },
        milestoneTimeoutMs: 1500,
      });
      assert.equal(never.ok, true, JSON.stringify(never.refusals));
      assert.equal(never.milestones.sourceHighlighted, null);
      assert.deepEqual(never.milestonesMissing, ["sourceHighlighted"]);
    });
    await check("the dwell journey rests on each row the registered time", async () => {
      const rows = [];
      await runJourney("dwell", d, base, rows, {});
      const D = SUBJECTS.dwell;
      assert.deepEqual(
        rows.map((r) => [r.id, r.subject, r.ok]),
        D.ms.map((ms, i) => [`dwell.hover_click.${ms}`, D.files[i], true]),
        JSON.stringify(rows.map((r) => r.refusals)),
      );
      const seen = await d.evaluate("window.dwellSeen");
      for (const [i, ms] of D.ms.entries()) {
        const rested = seen[D.files[i]];
        // The driver sleeps the dwell, so it rests at least that long; how much longer
        // depends on the runner, and the bound above it only catches a dwell gone wrong.
        assert.ok(rested >= ms - 2 && rested < ms + 5000, `${ms} ms dwell rested ${rested} ms`);
        // The row records the realized dwell, the pointer's arrival to the press.
        assert.ok(
          Math.abs(rows[i].hoverDwellMs - rested) <= 1,
          `${ms} ms dwell: the row says ${rows[i].hoverDwellMs} ms, the page saw ${rested} ms`,
        );
      }
    });
    await check("Changes hunk requires text on the visible, selected pull request", async () => {
      await d.evaluate(
        `(() => {
        history.replaceState(null, "", "/pull/353/files");
        document.body.innerHTML = ` +
          JSON.stringify(
            '<div class="nav-tab-bar"><button class="tab-btn active" data-tab="pulls">Pulls</button></div><div id="preview-pane"><div class="pull-request-host" data-core-preview="false"><h1 class="github-pull-title">#353</h1><div class="tab-bar"><a class="tab-btn active" href="/pull/353/files">Changes</a></div><div class="github-pull-body"><div class="diff-root"><section class="diff-file"><header>example.js</header></section></div></div></div></div>',
          ) +
          `; return true; })()`,
      );
      const hunkReady = `(${MILESTONES.prChangesHunk(353)})()`;
      assert.equal(await d.evaluate(hunkReady), false, "a file header alone has no hunk");
      await d.evaluate(`(() => {
        const hunk = document.createElement("div");
        hunk.className = "diff-hunk";
        hunk.style.visibility = "hidden";
        hunk.innerHTML = '<span class="diff-line-text">let ready = true;</span>';
        document.querySelector(".diff-file").append(hunk);
        return true;
      })()`);
      assert.equal(await d.evaluate(hunkReady), false, "a hidden hunk does not count");
      await d.evaluate('document.querySelector(".diff-hunk").style.visibility = "visible"; true');
      assert.equal(
        await d.evaluate(hunkReady),
        true,
        "the named pull request has visible hunk text",
      );
      assert.equal(await d.evaluate(`(${MILESTONES.prChangesHunk(351)})()`), false);
    });
  } else {
    throw new Error(
      `unknown group ${group}; frames, frames2, content, network, landing, search, window, or readings`,
    );
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

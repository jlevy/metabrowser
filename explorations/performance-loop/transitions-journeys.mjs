// Journeys and readiness predicates for the transition-navigation/v1 scenario.
//
// Every subject is named by identity (a path, a full commit ID, a pull request number),
// never by list position, because the Commits list follows the shared checkout's trunk
// refs and the Pulls list follows GitHub: both move while the corpus files stay frozen.
// A subject that cannot be found refuses the run rather than measuring a neighbor.
import { Refusal, sleep } from "./transitions-recorder.mjs";

const J = JSON.stringify;

export const SCENARIO = "transition-navigation/v1";

export const SUBJECTS = {
  landing: "README.md",
  files: {
    markdown_small: "README.md",
    markdown_large: "docs/design-system.md",
    markdown_mid: "docs/architecture.md",
    markdown_hover: "docs/development.md",
    source_large: "src/metabrowser/static/app.js",
    source_small: "pyproject.toml",
    json: "package-lock.json",
    diff: "tests/manual-fixtures/syntax-layouts.diff",
    image: "images/metabrowser-overview.jpg",
    binary: "tests/manual-fixtures/opaque.bin",
  },
  // Folders opened before the file clicks so every subject row is on screen.
  filesExpand: [
    "docs",
    "images",
    "src",
    "src/metabrowser",
    "src/metabrowser/static",
    "tests",
    "tests/manual-fixtures",
  ],
  keyboardStart: "CHANGELOG.md",
  keyboardDown: ["CLAUDE.md", "CONTRIBUTING.md", "LICENSE"],
  keyboardUp: ["CONTRIBUTING.md", "CLAUDE.md"],
  viewsMarkdown: "README.md",
  viewsJson: "package-lock.json",
  viewsFolder: "docs",
  mainTabsFile: "docs/architecture.md",
  mainTabsCommit: "3669a358eb15743e45e004961f35f4cf4dae0003",
  mainTabsPull: 353,
  commits: {
    cold: [
      "3669a358eb15743e45e004961f35f4cf4dae0003",
      "5136540f2ea228029b3454b7ba522718094a6eec",
      "083af6f8bdfb5c18cd870d173d706a12d3baf2f0",
    ],
    hover: "dbfd82b9407a6264405ded1e3f4b0e864fe1fc9b",
  },
  // Merged pull requests, listed under the Closed filter by number.
  pulls: { first: 353, second: 351, third: 349, fourth: 348 },
  tree: ["docs", "src", "src/metabrowser"],
};

// ---------------------------------------------------------------------------
// In-page predicates. `ready` sources are `() => boolean`, evaluated in a credited
// frame; `converged` sources are `() => string`, "" when everything agrees.

const fileRow = (p) => `#tab-files .tree-item[data-path=${J(p)}]`;
const folderRow = (p) => `#tab-files .tree-item.tree-folder[data-path=${J(p)}]`;
const navTab = (id) => `.nav-tab-bar .tab-btn[data-tab="${id}"]`;
const viewTab = (v) => `#preview-pane > .tab-bar > .tab-btn[data-tab="${v}"]`;
const commitRow = (rev) => `#tab-git .git-graph-row[data-revision="${rev}"]`;
const pullRow = (n) => `#tab-pulls a.github-pulls-row[data-number="${n}"]`;
const pullTab = (n, tab) =>
  `#preview-pane > .pull-request-host .tab-bar a.tab-btn[href="/pull/${n}${tab ? `/${tab}` : ""}"]`;

const activeNav = `(document.querySelector(".nav-tab-bar .tab-btn.active") || {}).dataset?.tab`;

const fileReady = (p) => `() => {
  const pane = document.getElementById("preview-pane");
  if (!pane || pane.dataset.renderedPath !== ${J(p)}) { return false; }
  const a = pane.querySelector(':scope > [data-active-view="true"]');
  return !!a && !window.__tr.hasPlaceholder(a) && window.__tr.hasUseful(a);
}`;

const fileConverged = (p, folder = false) => `() => {
  const issues = [];
  const pane = document.getElementById("preview-pane");
  if (!(${fileReady(p)})()) { issues.push("content not ready"); }
  if (pane.classList.contains("preview-navigation-pending")) { issues.push("pending"); }
  const route = decodeURIComponent(location.pathname);
  const want = "/view/" + ${J(p)} + (${folder} ? "/" : "");
  if (route !== want) { issues.push("route " + route); }
  const selected = Array.from(document.querySelectorAll("#tab-files .tree-item.selected")).map((r) => r.dataset.path);
  if (selected.length !== 1 || selected[0] !== ${J(p)}) { issues.push("selected " + selected.join(",")); }
  if (${activeNav} !== "files") { issues.push("main tab " + ${activeNav}); }
  const owners = pane.querySelectorAll(':scope > [data-active-view="true"]').length;
  if (owners !== 1) { issues.push("active views " + owners); }
  if (pane.querySelector(":scope > .preview-file-stage")) { issues.push("a staged surface remains"); }
  return issues.join("; ");
}`;

const viewReady = (v) => `() => {
  const pane = document.getElementById("preview-pane");
  const a = pane && pane.querySelector(':scope > [data-tab-content="${v}"]');
  if (!a || a.dataset.activeView !== "true" || getComputedStyle(a).display === "none") { return false; }
  return !window.__tr.hasPlaceholder(a) && window.__tr.hasUseful(a);
}`;

const viewConverged = (v, p) => `() => {
  const issues = [];
  const pane = document.getElementById("preview-pane");
  if (!(${viewReady(v)})()) { issues.push("view not ready"); }
  if (pane.dataset.renderedPath !== ${J(p)}) { issues.push("rendered " + pane.dataset.renderedPath); }
  const btn = document.querySelector(${J(viewTab(v))});
  if (!btn || !btn.classList.contains("active")) { issues.push("tab button not active"); }
  const shown = Array.from(pane.querySelectorAll(":scope > [data-tab-content]")).filter((c) => getComputedStyle(c).display !== "none").map((c) => c.dataset.tabContent);
  if (shown.length !== 1 || shown[0] !== ${J(v)}) { issues.push("shown views " + shown.join(",")); }
  return issues.join("; ");
}`;

// A main tab with nothing selected: its list is the subject and the preview shows the
// tab's prompt by design.
const listReady = (tab, rowSelector, promptSelector) => `() => {
  const panel = document.querySelector('#tree-content > [data-tab-content="${tab}"]');
  if (!panel || getComputedStyle(panel).display === "none") { return false; }
  if (panel.querySelectorAll(${J(rowSelector)}).length === 0) { return false; }
  if (${activeNav} !== ${J(tab)}) { return false; }
  const pane = document.getElementById("preview-pane");
  return !!pane.querySelector(${J(promptSelector)}) && !window.__tr.hasPlaceholder(panel);
}`;

const listConverged = (tab, rowSelector, promptSelector, subjectSelector) => `() => {
  const issues = [];
  if (!(${listReady(tab, rowSelector, promptSelector)})()) { issues.push("list or prompt not shown"); }
  const pane = document.getElementById("preview-pane");
  if (pane.querySelector(${J(subjectSelector)})) { issues.push("a subject is still mounted"); }
  return issues.join("; ");
}`;

const commitReady = (rev) => `() => {
  const pane = document.getElementById("preview-pane");
  const v = pane && pane.querySelector(":scope > .git-commit-stage > .git-commit-view");
  if (!v || v.dataset.revision !== ${J(rev)}) { return false; }
  const diff = v.querySelector(".git-commit-diff");
  return !!diff && diff.childElementCount > 0 && !window.__tr.hasPlaceholder(v) && window.__tr.hasUseful(diff);
}`;

const commitConverged = (rev) => `() => {
  const issues = [];
  if (!(${commitReady(rev)})()) { issues.push("commit not ready"); }
  if (location.pathname !== "/commit/" + ${J(rev)}) { issues.push("route " + location.pathname); }
  const selected = Array.from(document.querySelectorAll("#tab-git .git-graph-row.selected")).map((r) => r.dataset.revision);
  if (selected.length !== 1 || selected[0] !== ${J(rev)}) { issues.push("selected " + selected.join(",").slice(0, 60)); }
  if (${activeNav} !== "git") { issues.push("main tab " + ${activeNav}); }
  if (document.querySelectorAll("#preview-pane .git-commit-view").length !== 1) { issues.push("commit views " + document.querySelectorAll("#preview-pane .git-commit-view").length); }
  return issues.join("; ");
}`;

const pullPath = (n, tab) => `/pull/${n}${tab ? `/${tab}` : ""}`;

const pullReady = (n, tab = "") => `() => {
  if (location.pathname !== ${J(pullPath(n, tab))}) { return false; }
  const pane = document.getElementById("preview-pane");
  const host = pane && pane.querySelector(":scope > .pull-request-host");
  if (!host || host.dataset.corePreview !== "false") { return false; }
  const title = host.querySelector(".github-pull-title");
  if (!title || !/#${n}\\b/.test(title.textContent || "")) { return false; }
  const active = host.querySelector(".tab-bar .tab-btn.active");
  if (!active || active.getAttribute("href") !== ${J(pullPath(n, tab))}) { return false; }
  const body = host.querySelector(":scope > .github-pull-body");
  if (!body || body.childElementCount === 0) { return false; }
  if (${J(tab)} === "files" && !body.querySelector(".diff-root section.diff-file")) { return false; }
  if (${J(tab)} === "checks" && !body.querySelector(".github-pull-section")) { return false; }
  return !window.__tr.hasPlaceholder(host) && window.__tr.hasUseful(body);
}`;

const pullConverged = (n, tab = "") => `() => {
  const issues = [];
  if (!(${pullReady(n, tab)})()) { issues.push("pull request not ready"); }
  const pane = document.getElementById("preview-pane");
  if (pane.classList.contains("preview-navigation-pending")) { issues.push("pending"); }
  const hosts = pane.querySelectorAll(":scope > .pull-request-host").length;
  if (hosts !== 1) { issues.push("hosts " + hosts); }
  if (${activeNav} !== "pulls") { issues.push("main tab " + ${activeNav}); }
  const selected = Array.from(document.querySelectorAll("#tab-pulls a.github-pulls-row.selected")).map((r) => r.dataset.number);
  if (selected.length !== 1 || selected[0] !== ${J(String(n))}) { issues.push("selected " + selected.join(",")); }
  return issues.join("; ");
}`;

const folderExpandedReady = (p, expanded) => `() => {
  const row = document.querySelector(${J(folderRow(p))});
  if (!row) { return false; }
  if (${expanded}) {
    const kids = row.getAttribute("aria-owns") ? document.getElementById(row.getAttribute("aria-owns")) : row.nextElementSibling;
    if (row.getAttribute("aria-expanded") !== "true" || !kids || kids.classList.contains("tree-children-collapsed") || kids.querySelectorAll(":scope > .tree-item").length === 0) { return false; }
  } else if (row.getAttribute("aria-expanded") === "true") {
    return false;
  }
  return (${fileReady(p)})();
}`;

const folderConverged = (p, expanded) => `() => {
  const issues = [];
  if (!(${folderExpandedReady(p, expanded)})()) { issues.push("folder state or Overview not ready"); }
  const rest = (${fileConverged(p, true)})();
  if (rest) { issues.push(rest); }
  return issues.join("; ");
}`;

const escapeRe = (s) => s.replace(/[.*+?^$()|[\]\\{}]/g, "\\$&");
const fileRequest = (p) => `^/api/file\\?path=${escapeRe(encodeURIComponent(p))}(&|$)`;
const pullRequest = (n) => `^/api/plugin/github/pull\\?number=${n}(&|$)`;
// The first-parent comparison and the commit detail, each requested once when cold.
const commitRequest = (rev) => [
  `^/api/plugin/diff/comparison\\?revision=${rev}(&|$)`,
  `^/api/git/commit/${rev}($|\\?)`,
];

// ---------------------------------------------------------------------------
// Journey plumbing.

/** Wrap a driver so each measurement lands in `rows` with its journey name. */
function context(d, base, journey, rows, options) {
  const measure = async (spec) => {
    const row = await d.measure({ journey, ...spec });
    rows.push(row);
    if (options.log) {
      options.log(row);
    }
    await d.park();
    await sleep(spec.gapMs ?? 700);
    return row;
  };
  const setupClick = async (selector, readySource, what, timeoutMs = 30000) => {
    await d.click(selector);
    const ok = await d.waitFor(`(${readySource})()`, timeoutMs);
    if (!ok) {
      throw new Refusal("setup", `${what} did not become ready`);
    }
    await d.park();
    await sleep(900);
  };
  const land = async (p, settleMs = 2500) => {
    await d.navigate(`${base}/view/${p}`);
    const ok = await d.waitFor(`!!window.__tr && (${fileReady(p.replace(/\/$/, ""))})()`, 60000);
    if (!ok) {
      throw new Refusal("setup", `landing on ${p} did not become ready`);
    }
    await d.park();
    await sleep(settleMs);
  };
  const requireRow = async (selector, what) => {
    const found = await d.waitFor(`!!document.querySelector(${J(selector)})`, 20000);
    if (!found) {
      throw new Refusal("subject_missing", `${what} is not listed`);
    }
  };
  return { d, base, measure, setupClick, land, requireRow };
}

const click = (selector) => ({ kind: "click", selector });
const hoverClick = (selector, hoverMs = 400) => ({ kind: "hover-click", selector, hoverMs });

async function expandFolders(ctx, folders) {
  for (const f of folders) {
    await ctx.requireRow(folderRow(f), `folder ${f}`);
    const expanded = await ctx.d.evaluate(
      `document.querySelector(${J(folderRow(f))}).getAttribute("aria-expanded") === "true"`,
    );
    if (!expanded) {
      await ctx.setupClick(folderRow(f), folderExpandedReady(f, true), `expanding ${f}`);
    }
  }
}

// ---------------------------------------------------------------------------
// Journeys. Each opens its own fresh browser profile; see transitions.mjs.

async function landing(ctx) {
  const p = SUBJECTS.landing;
  await ctx.measure({
    id: "landing.cold_markdown",
    subject: p,
    input: { kind: "navigate", url: `${ctx.base}/view/${p}` },
    ready: fileReady(p),
    converged: fileConverged(p),
    subjectRequest: fileRequest(p),
    settleMs: 1500,
    timeoutMs: 60000,
  });
  await sleep(2000);
  await ctx.measure({
    id: "landing.reload",
    subject: p,
    input: { kind: "reload" },
    ready: fileReady(p),
    converged: fileConverged(p),
    subjectRequest: fileRequest(p),
    settleMs: 1500,
    timeoutMs: 60000,
  });
}

async function files(ctx) {
  const F = SUBJECTS.files;
  await ctx.land(F.markdown_small);
  await expandFolders(ctx, SUBJECTS.filesExpand);
  await ctx.setupClick(fileRow(F.markdown_small), fileReady(F.markdown_small), "README.md");
  await sleep(1500);
  const visit = (id, p, input = click(fileRow(p)), extra = {}) =>
    ctx.measure({
      id,
      subject: p,
      input,
      ready: fileReady(p),
      converged: fileConverged(p),
      subjectRequest: fileRequest(p),
      ...extra,
    });
  for (const k of [
    "markdown_large",
    "markdown_mid",
    "source_large",
    "source_small",
    "json",
    "diff",
    "image",
    "binary",
  ]) {
    await visit(`files.cold.${k}`, F[k]);
  }
  for (const k of ["source_large", "json", "markdown_small", "markdown_large"]) {
    await visit(`files.revisit.${k}`, F[k]);
  }
  await visit("files.history_back", F.markdown_small, { kind: "history", delta: -1 });
  await visit("files.history_forward", F.markdown_large, { kind: "history", delta: 1 });
  await visit(
    "files.hover_click.markdown",
    F.markdown_hover,
    hoverClick(fileRow(F.markdown_hover)),
  );
}

async function keyboard(ctx) {
  const start = SUBJECTS.keyboardStart;
  await ctx.land(start);
  // A real click on the selected row gives the tree keyboard focus.
  await ctx.setupClick(fileRow(start), fileReady(start), start);
  const neighbor = (delta) =>
    ctx.d.evaluate(`(() => {
      const rows = Array.from(document.querySelectorAll("#tab-files .tree-item")).filter((r) => r.offsetParent !== null);
      const i = rows.findIndex((r) => r.classList.contains("selected"));
      const n = rows[i + ${delta}];
      return n ? n.dataset.path : null;
    })()`);
  const step = async (id, keyName, delta, expected) => {
    const p = await neighbor(delta);
    if (p !== expected) {
      throw new Refusal("subject_missing", `${keyName} would open ${p}, expected ${expected}`);
    }
    await ctx.measure({
      id,
      subject: p,
      input: { kind: "key", key: keyName },
      ready: fileReady(p),
      converged: fileConverged(p),
      subjectRequest: fileRequest(p),
    });
  };
  let i = 0;
  for (const p of SUBJECTS.keyboardDown) {
    i += 1;
    await step(`keyboard.down_cold.${i}`, "ArrowDown", 1, p);
  }
  i = 0;
  for (const p of SUBJECTS.keyboardUp) {
    i += 1;
    await step(`keyboard.up_revisit.${i}`, "ArrowUp", -1, p);
  }
}

async function views(ctx) {
  const tabs = () =>
    ctx.d.evaluate(
      `Array.from(document.querySelectorAll("#preview-pane > .tab-bar > .tab-btn")).map((b) => b.dataset.tab)`,
    );
  const cycle = async (label, p) => {
    const names = await tabs();
    if (names.length < 2) {
      throw new Refusal("subject_missing", `${p} offers views ${names.join(",")}`);
    }
    const [a, b] = names;
    const go = (id, v, settleMs) =>
      ctx.measure({
        id,
        subject: `${p} ${v}`,
        input: click(viewTab(v)),
        ready: viewReady(v),
        converged: viewConverged(v, p),
        settleMs,
      });
    await go(`views.${label}.first`, b, 700);
    await go(`views.${label}.revisit`, a);
    await go(`views.${label}.revisit_2`, b);
  };
  await ctx.land(SUBJECTS.viewsMarkdown);
  await cycle("markdown", SUBJECTS.viewsMarkdown);
  await ctx.setupClick(fileRow(SUBJECTS.viewsJson), fileReady(SUBJECTS.viewsJson), "JSON file");
  await sleep(1000);
  await cycle("json", SUBJECTS.viewsJson);
  const folder = SUBJECTS.viewsFolder;
  await ctx.setupClick(folderRow(folder), folderExpandedReady(folder, true), `${folder}/`);
  await sleep(1500);
  await cycle("folder", folder);
}

const commitsList = listReady("git", ".git-graph-row", ":scope > .preview-empty");
const commitsListConverged = listConverged(
  "git",
  ".git-graph-row",
  ":scope > .preview-empty",
  ".git-commit-view",
);
const pullsList = listReady("pulls", "a.github-pulls-row", ":scope > .pull-request-list-host");
const pullsListConverged = listConverged(
  "pulls",
  "a.github-pulls-row",
  ":scope > .pull-request-list-host",
  ".pull-request-host",
);

async function closedPulls(ctx, numbers) {
  await ctx.setupClick(
    '#tab-pulls .chip[data-chip-value="closed"]',
    `() => document.querySelectorAll("#tab-pulls a.github-pulls-row").length > 4 && document.querySelector('#tab-pulls ul.github-pulls-list[data-filter="closed"]') !== null`,
    "Closed pull requests",
  );
  for (const n of numbers) {
    await ctx.requireRow(pullRow(n), `pull request #${n}`);
  }
  await sleep(1500);
}

async function mainTabs(ctx) {
  const file = SUBJECTS.mainTabsFile;
  const rev = SUBJECTS.mainTabsCommit;
  const pr = SUBJECTS.mainTabsPull;
  await ctx.land(file);
  await ctx.requireRow(navTab("pulls"), "the Pulls tab");
  const toFiles = (id) =>
    ctx.measure({
      id,
      subject: file,
      input: click(navTab("files")),
      ready: fileReady(file),
      converged: fileConverged(file),
      subjectRequest: fileRequest(file),
    });
  const toCommits = (id, settleMs) =>
    ctx.measure({
      id,
      subject: "Commits list",
      input: click(navTab("git")),
      ready: commitsList,
      converged: commitsListConverged,
      settleMs,
      timeoutMs: 30000,
    });
  const toPulls = (id, settleMs) =>
    ctx.measure({
      id,
      subject: "Pulls list",
      input: click(navTab("pulls")),
      ready: pullsList,
      converged: pullsListConverged,
      settleMs,
      timeoutMs: 30000,
    });
  await toCommits("main.files_to_commits.first", 900);
  await toFiles("main.commits_to_files.first");
  await toCommits("main.files_to_commits.again");
  await toFiles("main.commits_to_files.again");
  await toPulls("main.files_to_pulls.first", 1500);
  await toFiles("main.pulls_to_files.first");
  await toPulls("main.files_to_pulls.again");
  await toCommits("main.pulls_to_commits");
  await toPulls("main.commits_to_pulls");
  await toFiles("main.pulls_to_files.again");

  // Give Commits and Pulls a selected subject, then repeat the round trip.
  await ctx.setupClick(navTab("git"), commitsList, "Commits");
  await ctx.requireRow(commitRow(rev), `commit ${rev.slice(0, 8)}`);
  await ctx.setupClick(commitRow(rev), commitReady(rev), `commit ${rev.slice(0, 8)}`);
  await ctx.setupClick(navTab("pulls"), pullsList, "Pulls");
  await closedPulls(ctx, [pr]);
  await ctx.setupClick(pullRow(pr), pullReady(pr), `pull request #${pr}`, 60000);
  await sleep(1500);
  await ctx.setupClick(navTab("files"), fileReady(file), file);
  const subjectCommit = (id) =>
    ctx.measure({
      id,
      subject: rev,
      input: click(navTab("git")),
      ready: commitReady(rev),
      converged: commitConverged(rev),
      subjectRequest: commitRequest(rev),
      settleMs: 800,
      timeoutMs: 30000,
    });
  const subjectPull = (id) =>
    ctx.measure({
      id,
      subject: `#${pr}`,
      input: click(navTab("pulls")),
      ready: pullReady(pr),
      converged: pullConverged(pr),
      subjectRequest: pullRequest(pr),
      settleMs: 1200,
      timeoutMs: 30000,
    });
  await subjectCommit("main_subject.files_to_commits");
  await subjectPull("main_subject.commits_to_pulls");
  await toFiles("main_subject.pulls_to_files");
  await subjectPull("main_subject.files_to_pulls");
  await subjectCommit("main_subject.pulls_to_commits");
  await toFiles("main_subject.commits_to_files");
}

async function commits(ctx) {
  const C = SUBJECTS.commits;
  await ctx.land(SUBJECTS.landing);
  await ctx.requireRow(navTab("git"), "the Commits tab");
  await ctx.measure({
    id: "commits.first_show",
    subject: "Commits list",
    input: click(navTab("git")),
    ready: commitsList,
    converged: commitsListConverged,
    settleMs: 900,
    timeoutMs: 30000,
  });
  await sleep(1500);
  for (const rev of [...C.cold, C.hover]) {
    await ctx.requireRow(commitRow(rev), `commit ${rev.slice(0, 8)}`);
  }
  const visit = (id, rev, input = click(commitRow(rev))) =>
    ctx.measure({
      id,
      subject: rev,
      input,
      ready: commitReady(rev),
      converged: commitConverged(rev),
      subjectRequest: commitRequest(rev),
      settleMs: 800,
      timeoutMs: 30000,
    });
  let i = 0;
  for (const rev of C.cold) {
    i += 1;
    await visit(`commits.cold.${i}`, rev);
  }
  await visit("commits.revisit.1", C.cold[0]);
  await visit("commits.revisit.2", C.cold[1]);
  await visit("commits.hover_click", C.hover, hoverClick(commitRow(C.hover)));
}

async function pulls(ctx) {
  const P = SUBJECTS.pulls;
  await ctx.land(SUBJECTS.landing);
  await ctx.requireRow(navTab("pulls"), "the Pulls tab");
  await ctx.measure({
    id: "pulls.first_show",
    subject: "Pulls list",
    input: click(navTab("pulls")),
    ready: pullsList,
    converged: pullsListConverged,
    settleMs: 1500,
    timeoutMs: 30000,
  });
  await sleep(1500);
  await closedPulls(ctx, [P.first, P.second, P.third, P.fourth]);
  const open = (id, n, input, tab = "", settleMs = 1500) =>
    ctx.measure({
      id,
      subject: `#${n}${tab ? `/${tab}` : ""}`,
      input,
      ready: pullReady(n, tab),
      converged: pullConverged(n, tab),
      subjectRequest: pullRequest(n),
      settleMs,
      timeoutMs: 60000,
      gapMs: 1500,
    });
  await open("pulls.list_to_pr.cold", P.first, click(pullRow(P.first)), "", 2500);
  await open("pulls.tab.changes_first", P.first, click(pullTab(P.first, "files")), "files", 2500);
  await open("pulls.tab.checks_first", P.first, click(pullTab(P.first, "checks")), "checks");
  await open("pulls.tab.conversation_revisit", P.first, click(pullTab(P.first, "")));
  await open("pulls.tab.changes_revisit", P.first, click(pullTab(P.first, "files")), "files");
  await open("pulls.tab.conversation_revisit_2", P.first, click(pullTab(P.first, "")));
  await open("pulls.pr_to_pr.cold", P.second, click(pullRow(P.second)), "", 2500);
  await open("pulls.pr_to_pr.revisit", P.first, click(pullRow(P.first)));
  await open("pulls.pr_to_pr.hover_click", P.third, hoverClick(pullRow(P.third)), "", 2500);
  await open("pulls.tab.changes_first_2", P.third, click(pullTab(P.third, "files")), "files", 2500);
  await open("pulls.history_back", P.third, { kind: "history", delta: -1 });
  await open("pulls.tab.changes_revisit_2", P.third, click(pullTab(P.third, "files")), "files");
  // A row link opens the other pull request on its Conversation tab.
  await open("pulls.pr_changes_to_pr", P.fourth, click(pullRow(P.fourth)), "", 2500);
}

async function tree(ctx) {
  await ctx.land(SUBJECTS.landing);
  const [docs, src, nested] = SUBJECTS.tree;
  const toggle = (id, p, expanded) =>
    ctx.measure({
      id,
      subject: `${p}/`,
      input: click(folderRow(p)),
      ready: folderExpandedReady(p, expanded),
      converged: folderConverged(p, expanded),
      subjectRequest: fileRequest(p),
      settleMs: 900,
      gapMs: 1200,
    });
  await toggle("tree.expand.docs", docs, true);
  await toggle("tree.expand.src", src, true);
  await toggle("tree.collapse.src", src, false);
  await toggle("tree.reexpand.src", src, true);
  await toggle("tree.expand_nested.src_metabrowser", nested, true);
}

export const JOURNEYS = {
  landing,
  files,
  keyboard,
  views,
  maintabs: mainTabs,
  commits,
  pulls,
  tree,
};

/** Run one journey on an open browser; transition rows are appended to `rows`. */
export async function runJourney(name, d, base, rows, options = {}) {
  const fn = JOURNEYS[name];
  if (!fn) {
    throw new Error(`unknown journey ${name}`);
  }
  await fn(context(d, base, name, rows, options));
}

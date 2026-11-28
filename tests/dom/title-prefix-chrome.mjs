// A commit's or pull request's title with a conventional-commit prefix, drawn by a real
// engine on every surface that shows one: the production modules and stylesheets, mounted
// on recorded records in headless Chrome.
//
//   CHROME_BIN=/path/to/chrome KPRESS_STATIC=/dir/with/css/and/fonts \
//     CHROME_PROFILES=/dir/the/caller/removes \
//     node tests/dom/title-prefix-chrome.mjs
//
// CHROME_PROFILES is where Chrome's profile goes (tests/dom/chrome-session.mjs);
// tests/test_title_prefix_chrome.py owns it, copies KPress's tokens and faces into
// KPRESS_STATIC, and runs this in a process group of its own.
//
// Which part of a title is its prefix, and the markup each surface draws from it, are
// browserless (tests/dom/title-prefix-session.js). What only a browser can tell is the
// cascade: that inside each surface's title, under the shell's and the GitHub plugin's
// stylesheets, the prefix computes to regular weight and the rest to the title's own, and
// that the prefix keeps the title's face, size, and ink (docs/design-system.md, "Titles").
// Each surface is drawn by its own production code:
//
// - a Pulls row, by mountPullsPanel over a recorded list whose first two titles are set;
// - the pull request page's title and its Conversation's commits, by mountPullPage over a
//   recorded record and a timeline projection of two commits;
// - a stack menu's members, by createStackMenu, opened;
// - Quick Search's pull requests, by the search palette over the production controller and
//   pull provider, its query typed;
// - the Commits tab's rows, by the Git panel's own rendering of a history page;
// - a commit's page and its tooltip, by renderCommitSummary and renderCommitTooltip.
//
// On each, a title with a prefix and one with none are read, and a title cut short keeps
// all of itself: a Pulls row's and a Commits tab row's end in an ellipsis with the whole
// title their text, the Commits tab row still 22 px tall, and the pull request's heading
// clamped at two lines carries the whole title in its tooltip.
import fs from "node:fs";
import http from "node:http";
import { createRequire } from "node:module";
import path from "node:path";
import { launchChrome } from "./chrome-session.mjs";

// The SDK's age builder over the ages a fake plays (sdk-ref-fixture.js), its source
// interpolated into a page script, so a page draws the labels the session chose.
const { agesFrom } = createRequire(import.meta.url)("./sdk-ref-fixture.js");

const root = path.resolve(import.meta.dirname, "../..");
const STATIC = path.join(root, "src/metabrowser/static");
const GITHUB = path.join(root, "src/metabrowser/builtin_plugins/github");
const FIXTURES = {
  "/fixtures/page.json": path.join(root, "tests/fixtures/github-pull-page-responses.json"),
  "/fixtures/pulls.json": path.join(root, "tests/fixtures/github-pulls-panel-responses.json"),
};
const KPRESS = process.env.KPRESS_STATIC ? path.resolve(process.env.KPRESS_STATIC) : null;
const failures = [];
let checks = 0;
const check = (label, ok, detail = "") => {
  checks += 1;
  if (!ok) {
    failures.push(`${label}${detail ? `: ${detail}` : ""}`);
  }
};

// The shell's startup scripts the surfaces need, in the shell's order, then the Quick Search
// bundle's and the Git panel's.
const SCRIPTS = [
  "request-error.js",
  "formatters.js",
  "inventory-scope.js",
  "resource-context.js",
  "view-state.js",
  "navigation.js",
  "inert-html.js",
  "plugin-sdk.js",
  // `metabrowser.menus`, the closing every menu has, which the stack menu and the
  // views' menus use, and the shell tool it forwards to.
  "filter-controls.js",
  "menus.js",
  "plugin-sdk-views.js",
  "file-fuzzy-match.js",
  "known-file-catalog.js",
  "search-controller.js",
  "keyboard-shortcuts.js",
  "overlay-layer.js",
  "search-palette.js",
  "git-graph.js",
  "git-history-window.js",
  "git-panel.js",
];
const PAGE = `<!doctype html><html><head><meta charset="utf-8"><title>title prefix</title>
<link rel="stylesheet" href="/kpress/css/style-tokens.css">
<link rel="stylesheet" href="/static/styles.css">
<link rel="stylesheet" href="/github/styles.css">
<script>
  window.METABROWSER_SETTINGS = { SYNTAX_HIGHLIGHT_MAX_BYTES: 524288, SYNTAX_LANGUAGE_BY_BASENAME: {}, SYNTAX_LANGUAGE_BY_EXTENSION: {} };
  window.MetabrowserIcons = { copy: '<svg data-icon="copy"></svg>' };
</script>
${SCRIPTS.map((name) => `<script src="/static/${name}"></script>`).join("\n")}
</head><body><div id="tree-content"><div id="tab-git"></div></div><div id="preview-pane" class="preview-pane"></div></body></html>`;

const TYPES = {
  ".css": "text/css",
  ".js": "text/javascript",
  ".json": "application/json",
  ".woff2": "font/woff2",
};
function serve() {
  const server = http.createServer((request, response) => {
    const url = new URL(request.url ?? "/", "http://localhost");
    let file = null;
    if (url.pathname === "/" || url.pathname.startsWith("/pull/")) {
      response.writeHead(200, { "content-type": "text/html" });
      response.end(PAGE);
      return;
    }
    if (url.pathname in FIXTURES) {
      file = FIXTURES[url.pathname];
    } else if (url.pathname.startsWith("/static/")) {
      file = path.join(STATIC, url.pathname.slice(8));
    } else if (url.pathname.startsWith("/github/")) {
      file = path.join(GITHUB, url.pathname.slice(8));
    } else if (KPRESS && url.pathname.startsWith("/kpress/")) {
      file = path.join(KPRESS, url.pathname.slice(8));
    }
    const within = [root, KPRESS].filter(Boolean).some((dir) => file?.startsWith(dir + path.sep));
    if (!file || !within || !fs.existsSync(file)) {
      response.writeHead(404);
      response.end();
      return;
    }
    response.writeHead(200, { "content-type": TYPES[path.extname(file)] ?? "text/plain" });
    fs.createReadStream(file).pipe(response);
  });
  return new Promise((resolve) => server.listen(0, "127.0.0.1", () => resolve(server)));
}

// The titles every surface is read with: the request's example, a commit's, and one of
// each with no prefix, a revert's among them.
const PULL = "feat(ledger): chart strategies, range bands and Extended default (valuation, WIP)";
const PULL_PLAIN = "Merge the stack keys into the shell's keymap";
const COMMIT = "fix(git): keep the scroller rule and the Tab stop of a lost landing";
const COMMIT_PLAIN = 'Revert "fix(git): keep the scroller rule"';

// In the page: draw every surface with the production code and read, for each title, the
// computed style of its element (the rest) and of its prefix, if it has one.
const MEASURE = `async (titles) => {
  const { PULL, PULL_PLAIN, COMMIT, COMMIT_PLAIN } = titles;
  const mb = window.metabrowser;
  const pageModule = await import("/github/pull-page.js");
  const panelModule = await import("/github/pulls-panel.js");
  const pageRecords = await (await fetch("/fixtures/page.json")).json();
  const pullsRecords = await (await fetch("/fixtures/pulls.json")).json();
  const realFetch = window.fetch.bind(window);
  const frames = () => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
  const until = async (test, what) => {
    const deadline = performance.now() + 20000;
    while (performance.now() < deadline) {
      if (test()) return;
      await new Promise((resolve) => setTimeout(resolve, 10));
    }
    throw new Error("timed out waiting for " + what);
  };
  const json = (body, headers = {}) =>
    new Response(JSON.stringify(body), { status: 200, headers: { "content-type": "application/json", ...headers } });
  const style = (node) => {
    const computed = getComputedStyle(node);
    return {
      weight: computed.fontWeight,
      family: computed.fontFamily,
      size: computed.fontSize,
      color: computed.color,
    };
  };
  // One title element: its text, its own style (the rest's), and its prefix's, if any.
  const read = (element) => {
    if (!element) return null;
    const prefix = element.querySelector(":scope > .title-prefix");
    return {
      text: element.textContent,
      prefixText: prefix?.textContent ?? null,
      prefixes: element.querySelectorAll(".title-prefix").length,
      rest: style(element),
      prefix: prefix ? style(prefix) : null,
      clipped: element.scrollWidth > element.clientWidth,
      overflow: getComputedStyle(element).textOverflow,
    };
  };
  const pane = document.getElementById("preview-pane");
  const out = {};

  // ── A Pulls row, drawn by mountPullsPanel. The recorded rows are JSON text.
  {
    const body = structuredClone(pullsRecords.current.body);
    const rows = body.rows.slice(0, 2).map((row) => (typeof row === "string" ? JSON.parse(row) : row));
    rows[0].title = PULL;
    rows[1].title = PULL_PLAIN;
    // A list of these two alone, whole.
    Object.assign(body, { rows, total: 2, repository_total: 2, catalog_fetched: 2, fetched: 2, next_after: null });
    body.filter_totals = { all: 2, open: 2, closed: 0 };
    window.fetch = async (route) => {
      const url = new URL(String(route), location.href);
      if (url.pathname === "/api/plugin/github/pulls") {
        return json(body, { etag: pullsRecords.current.etag });
      }
      return new Response("{}", { status: 404, headers: { "content-type": "application/json" } });
    };
    const nav = document.createElement("div");
    // Narrow enough that the long title runs past its two lines: at 300 px it fits them.
    nav.style.width = "200px";
    pane.replaceChildren(nav);
    const handle = panelModule.mountPullsPanel(
      nav,
      {
        kind: "pull-request-list",
        pullsNav: {
          filter: "all",
          current: null,
          shown: true,
          refreshAhead: false,
          scrollRoot: null,
          open() {},
          file: null,
          fileHref: () => null,
          pageFor: () => null,
          onPageChange: () => () => {},
          filterChanged() {},
        },
      },
      {
        ...mb,
        perf: { measure: (_label, work) => work(), measureAsync: (_label, work) => work() },
        filterControls: { groupHtml: () => "<div></div>", bind: () => () => {} },
      },
    );
    const title = (number) => nav.querySelector('a.github-pulls-row[data-number="' + number + '"] .github-pulls-title');
    await until(() => title(rows[0].number) && title(rows[1].number), "the Pulls rows");
    await document.fonts.ready;
    await frames();
    out.pullsRow = { prefixed: read(title(rows[0].number)), plain: read(title(rows[1].number)) };
    // The row's run (mb-pw8t, mb-rb3n): the title, the number, and the author, wrapping in as
    // many lines as they take, never cut short.
    const heading = title(rows[0].number).closest(".github-pulls-heading");
    const lineHeight = parseFloat(getComputedStyle(heading).lineHeight);
    out.pullsHeading = {
      clamped: heading.scrollHeight > heading.clientHeight + 1,
      lineClamp: getComputedStyle(heading).webkitLineClamp,
      lines: Math.round((heading.getBoundingClientRect().height / lineHeight) * 100) / 100,
    };
    handle?.dispose?.();
  }

  // ── The pull request page's title and its Conversation's commits, by mountPullPage.
  const mountPage = async (pullTitle, width) => {
    const envelope = structuredClone(pageRecords.current.body);
    envelope.comparison_route = null;
    envelope.record.comparison = null;
    envelope.record.unavailable.comparison = "no_store";
    envelope.record.pull.title = pullTitle;
    const events = [
      { kind: "commit", oid: "3c4a8f1b2d6e09a7c5b3f1e8d2a6c4b0e9f7a5d3", subject: COMMIT, committed_at: "2026-09-16T11:02:00Z" },
      { kind: "commit", oid: envelope.record.pull.head.sha, subject: COMMIT_PLAIN, committed_at: "2026-09-16T11:40:00Z" },
    ];
    window.fetch = async (route) => {
      const url = new URL(String(route), location.href);
      if (url.pathname === "/api/plugin/github/pull-timeline") {
        return json({ record_revision: envelope.record_revision, state: "complete", events });
      }
      if (url.pathname === "/api/plugin/github/pull") {
        return json(envelope);
      }
      return new Response(null, { status: 304 });
    };
    history.replaceState(null, "", "/pull/7");
    pane.style.width = width + "px";
    const container = document.createElement("div");
    pane.replaceChildren(container);
    const handle = pageModule.mountPullPage(
      container,
      { number: 7, tab: "", reader: { initial: { etag: null, body: envelope }, fetchAfterMs: 0 } },
      {
        perf: { measure: (_label, work) => work(), measureAsync: (_label, work) => work() },
        ensureAsset: async () => {},
        loadKpressAssets: async () => {},
        whenIdle: mb.whenIdle,
        ensureKindAssets: async () => {},
        decorateExternalLink: mb.decorateExternalLink,
        // The link card's SDK methods, which the page calls as it draws, replaces, and puts
        // away its texts (static/plugin-sdk-views.js).
        previewLink: mb.previewLink,
        forgetPreview: mb.forgetPreview,
        disposePreviews: mb.disposePreviews,
        refChip: mb.refChip,
        refChipHtml: mb.refChipHtml,
        mergeRefs: mb.mergeRefs,
        mountRefMenus: mb.mountRefMenus,
        actorIdentity: mb.actorIdentity,
        titleNodes: mb.titleNodes,
        shortCommit: mb.shortCommit,
        countPartsNodes: mb.countPartsNodes,
        formatInteger: mb.formatInteger,
        ...(${agesFrom})(document, () => ({ label: "2mo ago", className: "age-old" })),
        formatTimestamp: (seconds) => new Date(seconds * 1000).toISOString(),
        navigation: { href: () => "/view/" },
        sourceKind: () => "filesystem",
        icons: { toggle: "" },
      },
    );
    await handle.ready;
    handle.activate();
    await until(() => container.querySelectorAll(".github-pull-commit-subject").length === 2, "the commits");
    await document.fonts.ready;
    await frames();
    return { container, handle };
  };
  {
    const { container, handle } = await mountPage(PULL, 760);
    const subjects = [...container.querySelectorAll(".github-pull-commit-subject")];
    out.pullTitle = { prefixed: read(container.querySelector(".github-pull-title-text")) };
    out.timelineCommit = { prefixed: read(subjects[0]), plain: read(subjects[1]) };
    handle.dispose();
  }
  {
    const { container, handle } = await mountPage(PULL_PLAIN, 760);
    out.pullTitle.plain = read(container.querySelector(".github-pull-title-text"));
    handle.dispose();
  }
  {
    // Clamped at two lines in a narrow pane: the heading's tooltip is the whole title.
    const { container, handle } = await mountPage(PULL + ", and more words, so that it wraps past two lines", 320);
    const text = container.querySelector(".github-pull-title-text");
    text.closest("h1").dispatchEvent(new PointerEvent("pointerenter"));
    await frames();
    out.pullTitleClamped = {
      clamped: text.scrollHeight - text.clientHeight > 4,
      tip: text.closest("h1").dataset.tipText ?? null,
      text: text.textContent,
    };
    handle.dispose();
  }

  // ── A stack menu's members, by createStackMenu, opened.
  {
    const menu = pageModule.createStackMenu(
      { number: 286, base_ref: "main", open: true, pulls: [6, 7, 8], titles: [PULL, PULL_PLAIN, null] },
      7,
      { link: () => document.createElement("a"), icon: null, currentTitle: PULL_PLAIN, titleNodes: mb.titleNodes, onOpen() {}, menus: mb.menus },
    );
    const holder = document.createElement("div");
    holder.className = "github-pull-stacks";
    holder.style.position = "relative";
    pane.replaceChildren(holder);
    holder.append(menu.element);
    menu.element.open = true;
    await until(() => holder.querySelectorAll(".github-pull-stack-member-title").length === 3, "the stack's members");
    await frames();
    const members = [...holder.querySelectorAll(".github-pull-stack-member")];
    const member = (title) => members.map((link) => link.querySelector(".github-pull-stack-member-title")).find((node) => node.textContent === title);
    out.stackMember = { prefixed: read(member(PULL)), plain: read(member(PULL_PLAIN)) };
    // Each member's line and the shell's tip (mb-as06): one line, the long title cut short
    // before the number, which stays whole at the line's end (mb-1kzu), and the whole title
    // in the member's tip, which the shell shows only while it is cut.
    out.stackMemberLines = members.map((link) => {
      const title = link.querySelector(".github-pull-stack-member-title");
      const number = link.querySelector(".github-pull-stack-member-number");
      const copy = link.querySelector(".github-pull-row-copy");
      return {
        height: Math.round(link.getBoundingClientRect().height * 100) / 100,
        title: title.textContent,
        tip: link.dataset.tipText ?? null,
        wrapped: title.getClientRects().length > 1,
        number: number === null ? null : {
          text: number.textContent,
          whole: number.scrollWidth <= number.clientWidth,
          afterTitle: copy.lastElementChild?.contains(number) === true,
          endGap: Math.round((copy.getBoundingClientRect().right - number.getBoundingClientRect().right) * 100) / 100,
        },
      };
    });
    menu.dispose();
  }

  // ── Quick Search's pull requests, by the palette over the production controller and
  // pull provider: "#" lists recent pull requests, and "#ledger" matches in the prefix.
  {
    const rows = [
      { number: 455, title: PULL, state: "open" },
      { number: 454, title: PULL_PLAIN, state: "merged" },
    ];
    const search = window.MetabrowserSearch;
    const controller = search.createController();
    controller.registerProvider(
      search.createPullProvider({
        fetch: async (route) => {
          const query = new URL(String(route), location.href).searchParams.get("q");
          const shown = query === "#ledger" ? rows.slice(0, 1) : rows;
          return json({ complete: true, limited: false, refreshing: false, rows: shown, truncated: false });
        },
      }),
    );
    const palette = window.MetabrowserSearchPalette.create({
      controller,
      document,
      describeOpenFailure: window.MetabrowserNavigationRoute.openFailureOutcome,
      getCatalogSnapshot: () => ({ complete: true, observedCount: 0, truncated: false }),
      openFile: () => ({ status: "opened" }),
      openPull: () => ({ status: "opened" }),
      overlay: window.MetabrowserOverlay,
      shortcuts: window.MetabrowserKeyboardShortcuts.create({ document }),
    });
    palette.open();
    const input = palette.element.querySelector('[role="combobox"]');
    const labels = () => [...palette.element.querySelectorAll(".search-palette-option-pull .search-palette-label")];
    const type = async (query, count) => {
      input.value = query;
      input.dispatchEvent(new Event("input", { bubbles: true }));
      await until(() => labels().length === count, "pull results for " + query);
      await frames();
    };
    await type("#", 2);
    const label = (title) => labels().find((node) => node.textContent === title);
    out.quickSearch = { prefixed: read(label(PULL)), plain: read(label(PULL_PLAIN)) };
    await type("#ledger", 1);
    const matched = labels()[0];
    const mark = matched.querySelector(".title-prefix > mark");
    out.quickSearchMatch = {
      ...read(matched),
      mark: mark ? { text: mark.textContent, ...style(mark) } : null,
      marks: [...matched.querySelectorAll("mark")].map((node) => node.textContent),
    };
    palette.close?.();
    palette.dispose?.();
  }

  // ── The Commits tab's rows, by the Git panel's own rendering of one history page.
  const commit = (id, parents, subject) => ({
    id,
    short_id: id.slice(0, 7),
    parent_ids: parents,
    author: { name: "Author", email: "a@example.invalid" },
    authored_at: Date.now() / 1000 - 3600,
    committed_at: Date.now() / 1000 - 3600,
    subject,
  });
  {
    const internals = window.MetabrowserGitPanel._internals;
    const commits = [commit("a".repeat(40), ["b".repeat(40)], COMMIT), commit("b".repeat(40), [], COMMIT_PLAIN)];
    internals.setStateForTests(internals.emptyState());
    internals.appendPage(commits, null, {
      is_repo: true,
      page: 0,
      commits,
      cursor: null,
      has_more: false,
      page_cursor: "test:0",
      previous_cursor: null,
      scope: "all",
      scope_refs: [],
      scope_fingerprint: "title-prefix",
      // The panel's own HEAD, which an empty state has not read.
      graph_checkpoint: { version: 1, prior_swimlanes: [], color_index: -1, head_revision: internals.stateForTests().headRevision, scope_fingerprint: "title-prefix" },
    });
    const tab = document.getElementById("tab-git");
    tab.style.width = "420px";
    internals.renderPanel();
    await until(() => tab.querySelectorAll(".git-graph-subject").length === 2, "the history rows");
    await frames();
    const subjects = [...tab.querySelectorAll(".git-graph-subject")];
    // Each subject with its row's box and its own: a bold subject is wider than a regular
    // one, so it is cut short sooner, but the row keeps its height and the subject its line.
    const fit = (node) => {
      if (!node) return null;
      const text = document.createRange();
      text.selectNodeContents(node);
      return {
        ...read(node),
        rowHeight: node.closest(".git-graph-row").getBoundingClientRect().height,
        lineHeight: node.getBoundingClientRect().height,
        width: node.clientWidth,
        textWidth: text.getBoundingClientRect().width,
      };
    };
    out.commitsRow = {
      prefixed: fit(subjects.find((node) => node.textContent === COMMIT)),
      plain: fit(subjects.find((node) => node.textContent === COMMIT_PLAIN)),
    };
    tab.replaceChildren();
  }

  // ── A commit's page and its tooltip, by renderCommitSummary and renderCommitTooltip.
  {
    const internals = window.MetabrowserGitPanel._internals;
    const detail = (subject) => ({
      commit: { ...commit("c".repeat(40), [], subject), refs: [] },
      stats: { files_changed: 1, additions: 2, deletions: 1 },
      body: "",
    });
    const view = document.createElement("div");
    view.className = "git-commit-view";
    const tip = document.createElement("div");
    tip.className = "custom-tooltip";
    pane.style.width = "760px";
    pane.replaceChildren(view, tip);
    const summary = (subject, compact) => {
      const host = compact ? tip : view;
      host.innerHTML = compact ? internals.renderCommitTooltip(detail(subject)) : internals.renderCommitSummary(detail(subject));
      return read(host.querySelector(".git-commit-subject"));
    };
    await document.fonts.ready;
    out.commitPage = { prefixed: summary(COMMIT, false), plain: summary(COMMIT_PLAIN, false) };
    out.commitTooltip = { prefixed: summary(COMMIT, true), plain: summary(COMMIT_PLAIN, true) };
    pane.replaceChildren();
  }
  window.fetch = realFetch;
  return out;
}`;

// Each surface, the prefix each of its titles has, and the weight its rest keeps: bold, as a
// title is wherever it appears.
const SURFACES = [
  ["pullsRow", "a Pulls row", PULL, PULL_PLAIN, "feat(ledger):", "700"],
  ["pullTitle", "the pull request page's title", PULL, PULL_PLAIN, "feat(ledger):", "700"],
  ["stackMember", "a stack menu's member", PULL, PULL_PLAIN, "feat(ledger):", "700"],
  ["timelineCommit", "a Conversation commit", COMMIT, COMMIT_PLAIN, "fix(git):", "700"],
  ["quickSearch", "a Quick Search pull request", PULL, PULL_PLAIN, "feat(ledger):", "700"],
  ["commitsRow", "a Commits tab row", COMMIT, COMMIT_PLAIN, "fix(git):", "700"],
  ["commitPage", "a commit's page", COMMIT, COMMIT_PLAIN, "fix(git):", "700"],
  ["commitTooltip", "a commit's tooltip", COMMIT, COMMIT_PLAIN, "fix(git):", "700"],
];

async function main() {
  const bin = process.env.CHROME_BIN;
  if (!bin) {
    throw new Error("CHROME_BIN names no Chrome");
  }
  if (!KPRESS || !fs.existsSync(path.join(KPRESS, "css/style-tokens.css"))) {
    throw new Error("KPRESS_STATIC holds no css/style-tokens.css");
  }
  const profiles = process.env.CHROME_PROFILES;
  if (!profiles) {
    throw new Error("CHROME_PROFILES names no directory for Chrome's profile");
  }
  const began = performance.now();
  const lap = (step) =>
    process.stderr.write(`${step} at ${Math.round(performance.now() - began)} ms\n`);
  const server = await serve();
  try {
    const browser = await launchChrome(bin, { profiles });
    lap("Chrome started");
    try {
      await browser.send("Page.enable");
      await browser.send("Page.navigate", { url: `http://127.0.0.1:${server.address().port}/` });
      await browser.waitFor(
        `document.readyState === "complete" && Boolean(window.metabrowser?.titleNodes) && Boolean(window.MetabrowserGitPanel)`,
      );
      lap("the page loaded");
      const measured = await browser.evaluate(
        `(${MEASURE})(${JSON.stringify({ PULL, PULL_PLAIN, COMMIT, COMMIT_PLAIN })})`,
      );
      lap("every surface drawn");
      for (const [key, where, prefixed, plain, prefix, weight] of SURFACES) {
        const surface = measured[key];
        const titled = surface?.prefixed;
        const bare = surface?.plain;
        check(`${where}: both titles are drawn`, Boolean(titled && bare), JSON.stringify(surface));
        if (!titled || !bare) {
          continue;
        }
        check(`${where}: the element holds the whole title`, titled.text === prefixed, titled.text);
        check(
          `${where}: the prefix is ${prefix}`,
          titled.prefixText === prefix,
          String(titled.prefixText),
        );
        check(
          `${where}: the prefix is regular`,
          titled.prefix?.weight === "400",
          titled.prefix?.weight,
        );
        check(
          `${where}: the rest keeps the title's ${weight}`,
          titled.rest.weight === weight,
          titled.rest.weight,
        );
        for (const property of ["family", "size", "color"]) {
          check(
            `${where}: the prefix keeps the title's ${property}`,
            titled.prefix?.[property] === titled.rest[property],
            `${titled.prefix?.[property]} against ${titled.rest[property]}`,
          );
        }
        check(
          `${where}: a title with no prefix draws none`,
          bare.prefixes === 0 && bare.text === plain,
          JSON.stringify(bare),
        );
        check(
          `${where}: a title with no prefix keeps the title's ${weight}`,
          bare.rest.weight === weight,
          bare.rest.weight,
        );
      }
      // A Pulls row's long title wraps in its run and is never cut short, all of its title its
      // text (mb-pw8t): it was one line, cut short by text-overflow, and then two, cut short
      // by a line clamp's ellipsis (mb-85op).
      const row = measured.pullsRow?.prefixed;
      const heading = measured.pullsHeading;
      check(
        "a Pulls row's long title wraps in its run, never cut short, whole in its text",
        heading?.clamped === false &&
          heading.lineClamp === "none" &&
          heading.lines >= 2 &&
          Math.abs(heading.lines - Math.round(heading.lines)) < 0.01 &&
          row?.text === PULL,
        JSON.stringify({ row, heading }),
      );
      const member = measured.stackMember?.prefixed;
      const memberLines = measured.stackMemberLines ?? [];
      check(
        "a stack member's long title wraps and its tooltip holds the entire title",
        member?.text === PULL &&
          memberLines.length === 3 &&
          memberLines.every((line) => line.tip === line.title) &&
          memberLines.find((line) => line.title === PULL)?.wrapped === true,
        JSON.stringify({ member, memberLines }),
      );
      // Its number is never cut (mb-1kzu): whole at the line's end, after the title, the long
      // title's too, which is cut short before it.
      check(
        "a stack member's number stays whole at the line's end, the long title cut short before it",
        memberLines.length === 3 &&
          memberLines.every(
            (line) =>
              /^#\d+$/.test(line.number?.text ?? "") &&
              line.number.whole &&
              line.number.afterTitle &&
              Math.abs(line.number.endGap) <= 0.5,
          ),
        JSON.stringify(memberLines),
      );
      // The pull request's heading, clamped at two lines, carries the whole title in its tip.
      const clamped = measured.pullTitleClamped;
      check(
        "a clamped pull request title keeps the whole title in its tooltip",
        clamped?.clamped === true &&
          clamped.tip?.startsWith(clamped.text) &&
          clamped.tip === `${clamped.text} #7`,
        JSON.stringify(clamped),
      );
      // A Commits tab row's bold subject keeps the row's height and its one line, and a
      // subject too long for the row is still cut short with an ellipsis.
      const rows = measured.commitsRow;
      check(
        "a Commits tab row keeps its 22 px and its subject one line",
        [rows?.prefixed, rows?.plain].every(
          (subject) => subject?.rowHeight === 22 && subject.lineHeight <= subject.rowHeight,
        ),
        JSON.stringify(rows),
      );
      check(
        "a Commits tab row's long subject is cut short with an ellipsis, whole in its text",
        rows?.prefixed?.clipped === true &&
          rows.prefixed.overflow === "ellipsis" &&
          rows.prefixed.text === COMMIT,
        JSON.stringify(rows?.prefixed),
      );
      // A Quick Search match in the prefix is marked there, as a match in a path is: bold.
      // It is the title's one match, so the rest holds no mark: one there means a part's
      // matches were placed from the wrong offset.
      const matched = measured.quickSearchMatch;
      check(
        "a Quick Search match in the prefix is marked in it, and the rest of the prefix is regular",
        matched?.prefixText === "feat(ledger):" &&
          matched.prefix?.weight === "400" &&
          matched.mark?.text === "ledger" &&
          matched.mark.weight === "700" &&
          matched.text === PULL,
        JSON.stringify(matched),
      );
      check(
        "a Quick Search title's only marks are its matches",
        JSON.stringify(matched?.marks) === JSON.stringify(["ledger"]),
        JSON.stringify(matched?.marks),
      );
      if (process.env.MEASURE_OUT) {
        fs.writeFileSync(process.env.MEASURE_OUT, JSON.stringify(measured, null, 2));
      }
    } finally {
      await browser.close();
    }
  } finally {
    server.close();
  }
  if (failures.length) {
    console.error(failures.join("\n"));
    process.exitCode = 1;
    return;
  }
  console.log(`title prefix in Chrome: ${checks} checks passed`);
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});

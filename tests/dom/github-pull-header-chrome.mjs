// The pull request header's box, laid out by a real engine: the production page module
// and its stylesheets, mounted on recorded records in headless Chrome.
//
//   CHROME_BIN=/path/to/chrome KPRESS_STATIC=/dir/with/css/and/fonts \
//     CHROME_PROFILES=/dir/the/caller/removes \
//     node tests/dom/github-pull-header-chrome.mjs [--part NAME]
//
// CHROME_PROFILES is where Chrome's profile goes (tests/dom/chrome-session.mjs);
// tests/test_github_pull_header_chrome.py owns it and removes it.
//
// The session runs in parts, each its own browser and its own pytest case with its own
// bound, since all of it ran past one test's 45 s on a CI runner. `launch` starts Chrome,
// loads the page, and loads every face it declares, and nothing else, so the first Chrome
// start of a CI job, the slowest there, has a case of its own. Then the header at its widest
// two widths, its middle two, and its narrowest two (`header-wide`, `header-middle`,
// `header-narrow`), the offers the status row draws (`offers`), the Pulls rows (`pulls`),
// the run badge (`badges`), the label chips' colors in both themes (`labels`), the Diff
// summary's row while its comparison is read, as it arrives, as it fails, and as the same
// pull request is opened again in the document (`summary-wait`), a page mounted with no
// record in hand as its record lands (`cold-landing`), and the View on GitHub button in the
// header's corner (`corner`). With no part it runs every one. Each part writes how long
// each of its steps took to stderr.
//
// KPRESS_STATIC holds KPress's style-tokens.css and the faces it names, which
// tests/test_github_pull_header_chrome.py copies out of the installed package, so the
// header is set in the faces the shell uses.
//
// The header is reserved at first paint, so a record that has not arrived and every
// loaded record with labels and nothing to say on its status line lay out to one height on
// every tab, row by row, and the tab bar under it starts at one place; a record with no
// labels has no labels row, and lays out to that height less the row and its gap (mb-2u08).
// The status line is there only while it has something to say, here an offer, and is then
// a metadata line, as tall as the author's row above it, one line and one gap more; a rate
// limit's hold is said in the freshness note's place and adds none (mb-ne91). The note is
// whole beside the author's sentence or out of view, and the sentence whole while it shows;
// a hold is never out of view, cut short instead. That is layout, which no browserless DOM
// can compute: the stylesheet text passed with a state badge whose first flex item was a
// zero-height sizer, which hung the badge below the line and made the loaded header 5.6 px
// taller than the empty one. And no record's row may end past the header: an offer kept
// whole ran 262 px past it in a 360 px pane, and the pane scrolled sideways. The row
// structure itself is pinned browserless in github-pull-page-mount-behavior.js.
//
// The session also lays out Pulls rows as their stack places arrive, and the file
// header as a run's status badge changes its label in place (RUN_BADGE below).
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
const DIFF = path.join(root, "src/metabrowser/builtin_plugins/diff");
const FIXTURES = path.join(root, "tests/fixtures/github-pull-page-responses.json");
const LABEL_COLORS = path.join(root, "tests/fixtures/github-label-colors.json");
const KPRESS = process.env.KPRESS_STATIC ? path.resolve(process.env.KPRESS_STATIC) : null;
const failures = [];
let checks = 0;
const check = (label, ok, detail = "") => {
  checks += 1;
  if (!ok) {
    failures.push(`${label}${detail ? `: ${detail}` : ""}`);
  }
};
// A record's title is as tall as its own lines, one or two, and the cold header's holds two
// (mb-wcbc, github/styles.css): how much shorter a header is than the cold one for its
// title, and whether that is nothing or the one line a one-line title gives back.
const titleGivesBack = (shape, cold) => {
  const title = (measured) =>
    measured.rows.find((row) => row.row === "title")?.height ?? Number.NaN;
  const delta = Math.round((title(shape) - title(cold)) * 100) / 100;
  return { delta, title: title(shape), ok: delta === 0 || delta === -title(cold) / 2 };
};

// The scripts the SDK's ref helpers need, in the order tests/dom/sdk-sandbox.js loads them.
const SDK = [
  "request-error.js",
  "formatters.js",
  "inventory-scope.js",
  "resource-context.js",
  "view-state.js",
  "navigation.js",
  "plugin-sdk.js",
  // `metabrowser.menus`, the closing every menu has, which the stack menu and the
  // views' menus use, and the shell tool it forwards to.
  "filter-controls.js",
  "menus.js",
  "plugin-sdk-views.js",
];
const PAGE = `<!doctype html><html><head><meta charset="utf-8"><title>pull header</title>
<link rel="stylesheet" href="/kpress/css/style-tokens.css">
<link rel="stylesheet" href="/static/styles.css">
<link rel="stylesheet" href="/github/styles.css">
<link rel="stylesheet" href="/diff/styles.css">
<script>
  window.METABROWSER_SETTINGS = { SYNTAX_HIGHLIGHT_MAX_BYTES: 524288, SYNTAX_LANGUAGE_BY_BASENAME: {}, SYNTAX_LANGUAGE_BY_EXTENSION: {} };
  window.MetabrowserIcons = { copy: '<svg data-icon="copy"></svg>' };
</script>
<script src="/static/changed-files-tree.js"></script>
${SDK.map((name) => `<script src="/static/${name}"></script>`).join("\n")}
</head><body><div id="preview-pane" class="preview-pane"></div></body></html>`;

const TYPES = {
  ".css": "text/css",
  ".js": "text/javascript",
  ".json": "application/json",
  ".woff2": "font/woff2",
};
function serve() {
  const server = http.createServer((request, response) => {
    const url = new URL(request.url, "http://localhost");
    let file = null;
    if (url.pathname === "/" || url.pathname.startsWith("/pull/")) {
      response.writeHead(200, { "content-type": "text/html" });
      response.end(PAGE);
      return;
    }
    if (url.pathname === "/fixtures.json") {
      file = FIXTURES;
    } else if (url.pathname.startsWith("/static/")) {
      file = path.join(STATIC, url.pathname.slice(8));
    } else if (url.pathname.startsWith("/github/")) {
      file = path.join(GITHUB, url.pathname.slice(8));
    } else if (url.pathname.startsWith("/diff/")) {
      file = path.join(DIFF, url.pathname.slice(6));
    } else if (KPRESS && url.pathname.startsWith("/kpress/")) {
      file = path.join(KPRESS, url.pathname.slice(8));
    }
    const within = [root, KPRESS].filter(Boolean).some((dir) => file?.startsWith(dir));
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

// In the page: a change set five folders deep, and a function that opens the Diff summary
// drawn in a place and reads where its header and every row of its tree start, once its
// travel is over (docs/design-system.md, "Diff Summary": the tree's first level starts one
// --tree-indent in from the header, and each level one more).
const NESTED_SUMMARY = `(() => {
  const paths = ["top.py", "a/f.py", "a/b/f.py", "a/b/c/f.py", "a/b/c/d/f.py", "a/b/c/d/g.py"];
  const files = paths.map((path) => ({ kind: "modified", old: { path }, new: { path }, additions: 1, deletions: 0 }));
  return { manifest: { totals: { files: paths.length, additions: paths.length, deletions: 0, exact: true }, files } };
})()`;
const SUMMARY_INDENT = `async (place) => {
  const frames = () => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
  const toggle = place.querySelector(".diff-summary-toggle");
  toggle.click();
  const deadline = performance.now() + 10000;
  const open = () => {
    const body = place.querySelector(".diff-summary-body");
    return body && !body.classList.contains("diff-summary-body-collapsed") && body.querySelector('[role="treeitem"]');
  };
  while (!open() && performance.now() < deadline) {
    await new Promise((resolve) => setTimeout(resolve, 10));
  }
  // The box travels open in --transition-fast: wait for that travel itself, and for one that
  // replaced it, as a travel retargeted when the box's height changes is.
  const travels = () => place.querySelector(".diff-summary-body")?.getAnimations() ?? [];
  while (travels().length > 0 && performance.now() < deadline) {
    await Promise.allSettled(travels().map((travel) => travel.finished));
  }
  await frames();
  const left = (node) => Math.round(node.getBoundingClientRect().left * 100) / 100;
  return {
    step: parseFloat(getComputedStyle(document.documentElement).getPropertyValue("--tree-indent")),
    chevron: left(toggle.querySelector(".diff-summary-chevron")),
    words: left(toggle.querySelector(".change-line")),
    rows: [...place.querySelectorAll('.diff-summary-body [role="treeitem"]')].map((row) => ({
      id: row.dataset.id,
      level: Number(row.getAttribute("aria-level")),
      lead: left(row.children[0]),
      name: left(row.children[1]),
    })),
  };
}`;
/**
 * The rows of a measured tree that do not start one step per level in from its header: a
 * row's leading glyph, a folder's chevron or a file's letter, is a level's step past the
 * header's words, which start the header, its chevron after them (mb-hi4l, mb-f0pz).
 */
const offStep = (indent) =>
  indent === null
    ? ["not measured"]
    : indent.rows.filter(
        (row) =>
          Math.abs(row.lead - indent.words - indent.step * row.level) > 0.5 ||
          indent.chevron <= indent.words,
      );

// In the page: mount one record on one tab in a pane of one width and read the header's
// rows. The page's API is the one github-pull-page-mount-behavior.js mounts with, its ref
// helpers the production SDK's, and every request it makes answers 304.
const MEASURE = `async (name, change, tab, width) => {
  const recorded = window.__recorded ??= await (await fetch("/fixtures.json")).json();
  const page = window.__page ??= await import("/github/pull-page.js");
  const body = structuredClone(recorded[name].body);
  for (const envelope of [body, body.pull]) {
    const holder = envelope?.record?.same_as;
    if (holder !== undefined) {
      envelope.record = structuredClone(recorded[holder].body.record);
    }
  }
  // A checkout, which has no pin, at the pull request's head draws the offer to browse it.
  if (change.checkoutAtHead) {
    body.pin = null;
    body.pin_ref = null;
  }
  // A title of two lines and more, cut short at two.
  if (change.longTitle) {
    body.record.pull.title = "Decide every region's box at first paint, so nothing that arrives later moves the tab bar, a stack, a label, or a Refresh";
  }
  if (change.lastRefresh) {
    body.state = "stale";
    body.last_refresh = change.lastRefresh;
  }
  // A hold that lifts in half an hour, today on most clocks, which the page says as a time of
  // day; the other lifts in 2099, which it says as a short date and time.
  if (change.liftSoon) {
    body.last_refresh = { ...change.lastRefresh, reset_at: new Date(Date.now() + 30 * 60_000).toISOString() };
  }
  // A pull request with no labels, which has no labels row (mb-2u08).
  if (change.noLabels) {
    body.record.pull.labels = [];
  }
  // Labels of each color the label part checks, in the theme it names.
  if (change.labels && body.record) {
    body.record.pull.labels = change.labels;
    body.repository_labels = change.repositoryLabels ?? [];
  }
  if (change.theme) {
    document.documentElement.dataset.theme = change.theme;
  }
  // A long login and long branch names, the head in a fork: the author gives way to the
  // merge, which stays whole.
  if (change.longNames) {
    const pull = body.record.pull;
    pull.author = "a-thirty-nine-character-github-login-x";
    pull.merged_by = "a-thirty-nine-character-github-login-y";
    pull.head = { ...pull.head, ref: "feature/a-rather-long-branch-name-for-the-header-row", repository: "someorganization/demo" };
    pull.base = { ...pull.base, ref: "release/2026-11-long-base-branch", repository: "octo/demo" };
  }
  window.fetch = async () => new Response(null, { status: 304 });
  history.replaceState(null, "", "/pull/" + body.number + (tab ? "/" + tab : ""));
  const pane = document.getElementById("preview-pane");
  pane.style.width = width + "px";
  const container = document.createElement("div");
  pane.replaceChildren(container);
  const mb = window.metabrowser;
  const handle = page.mountPullPage(
    container,
    { number: body.number, tab, reader: { initial: { etag: null, body }, fetchAfterMs: 60000 } },
    {
      perf: { measure: (_label, work) => work(), measureAsync: (_label, work) => work() },
      ensureAsset: async () => {},
      whenIdle: mb.whenIdle,
      ensureKindAssets: async () => {},
      decorateExternalLink: mb.decorateExternalLink,
      refChip: mb.refChip,
      refChipHtml: mb.refChipHtml,
      mergeRefs: mb.mergeRefs,
      mountRefMenus: mb.mountRefMenus,
      actorIdentity: mb.actorIdentity,
      titleNodes: mb.titleNodes,
      shortCommit: mb.shortCommit,
      countPartsNodes: mb.countPartsNodes,
      // Ages of the lengths a record's have, one per time in the order the page asks, so no
      // two read the same and the row of ages is as long as a real one: "now" for all of them
      // made a 275 px row, whole to 480 px, that never reached the links (B4 of review B on
      // #506).
      ...(${agesFrom})(
        document,
        (() => {
          const labels = ["12d ago", "5h ago", "3d ago"];
          const given = new Map();
          return (seconds) => {
            if (!given.has(seconds)) given.set(seconds, labels[given.size % labels.length]);
            return { label: given.get(seconds), className: "age" };
          };
        })(),
      ),
      formatTimestamp: (seconds) => new Date(seconds * 1000).toISOString(),
      formatInteger: (value) => Number(value).toLocaleString("en-US"),
      navigation: { href: () => "/view/" },
      sourceKind: () => "filesystem",
      repository: change.checkoutAtHead ? { revision: body.record?.pull?.head?.sha } : undefined,
      // A page with a repository's identity asks for the link resolver; the header reads no
      // text's links, so it answers as the SDK's loader does when the bundle cannot load.
      loadRepositoryLinks: async () => null,
      icons: { toggle: "" },
    },
  );
  await document.fonts.ready;
  const frames = () => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
  await frames();
  // An avatar in the box the shell's identity draws, in the person glyph's place, without a
  // request: no fixture names an avatar the page may load, and most authors have one.
  if (change.avatar) {
    for (const box of container.querySelectorAll(".github-pull-meta .actor-avatar")) {
      const image = document.createElement("img");
      image.className = "actor-avatar-image";
      image.alt = "";
      image.width = 18;
      image.height = 18;
      box.replaceChildren(image);
    }
    await frames();
  }
  const header = container.querySelector(".github-pull-header");
  const box = (node) => node?.getBoundingClientRect();
  // How much of an element's width shows: what every box with an overflow between it and
  // the header leaves of it, so a part a clipping box cuts away counts as not shown.
  const shown = (node) => {
    const own = box(node);
    let left = own.left;
    let right = own.right;
    for (let up = node.parentElement; up && up !== header.parentElement; up = up.parentElement) {
      if (getComputedStyle(up).overflowX !== "visible") {
        left = Math.max(left, box(up).left);
        right = Math.min(right, box(up).right);
      }
    }
    return own.width > 0 ? Math.max(0, right - left) / own.width : 0;
  };
  const group = header.querySelector(".github-pull-branches .merge-refs");
  const mergeShown = group
    ? Math.min(
        ...[".merge-refs-source", ".merge-refs-arrow", ".merge-refs-target"].map((part) =>
          shown(group.querySelector(part)),
        ),
      )
    : null;
  // Where the rows' parts and the labels are, and every row's height: the row of ages' badge,
  // ages, and Browse code, the author's sentence, and the branches.
  const places = () => ({
    parts: [".github-pull-badge", ".github-pull-ages", ".github-pull-ages-links", ".github-pull-action", ".github-pull-identity", ".merge-refs-source", ".merge-refs-arrow", ".merge-refs-target", ".github-pull-label"].flatMap((selector) =>
      [...header.querySelectorAll(selector)].map((node) => [selector, Math.round(box(node).left * 100) / 100, Math.round(box(node).width * 100) / 100]),
    ),
    rows: [...header.children].map((row) => Math.round(box(row).height * 100) / 100),
    tabBar: Math.round((box(container.querySelector(".tab-bar")).top - box(header).top) * 100) / 100,
  });
  // The pull request's Diff summary arrives with its comparison, in the header's last row,
  // held from first paint (mb-pb35). It is drawn by the diff plugin's own mountDiffSummary,
  // on a change set whose breakdown names five statuses, "2 A, 3 D, 30 M, 12 R, 12 C ·
  // +1,234 −3,423", its file count on the size line above ("Change Size Line"), so its
  // breakdown is cut short at the narrowest width: it moves nothing, keeps its row's height,
  // and starts on the header's
  // content edge. While its breakdown is cut short, its header's tooltip is its whole words,
  // and while it is whole there is none (A7 of review A on #470). It is measured on every
  // tab, by a flag of its own (A11 of review A on #470).
  let summaryMoves = null;
  const slot = header.querySelector(".github-pull-summary");
  if (change.summary && slot !== null) {
    const before = places();
    const rowBefore = Math.round(box(slot).height * 100) / 100;
    const diff = (window.__diff ??= await import("/diff/diff-view.js"));
    const kinds = [
      ...Array(2).fill("added"),
      ...Array(3).fill("deleted"),
      ...Array(30).fill("modified"),
      ...Array(12).fill("renamed"),
      ...Array(12).fill("copied"),
    ];
    const files = kinds.map((kind, at) => ({
      kind,
      ...(kind === "added"
        ? {}
        : { old: { path: (kind === "renamed" || kind === "copied" ? "old/f" : "src/f") + at + ".py" } }),
      ...(kind === "deleted" ? {} : { new: { path: "src/f" + at + ".py" } }),
      additions: 30,
      deletions: 90,
    }));
    const summary = diff.mountDiffSummary(
      slot,
      { manifest: { totals: { files: 59, additions: 1234, deletions: 3423, exact: true }, files } },
      mb,
      { changedFiles: window.MetabrowserChangedFilesTree, openFile() {} },
    );
    await frames();
    const after = places();
    const rows = (shape) => JSON.stringify({ rows: shape.rows, tabBar: shape.tabBar });
    const headerLeft = box(header).left + parseFloat(getComputedStyle(header).paddingLeft);
    const toggle = slot.querySelector(".diff-summary");
    const breakdown = slot.querySelector(".change-line-statuses");
    toggle?.dispatchEvent(new Event("pointerenter"));
    summaryMoves = {
      moved: rows(before) === rows(after) ? null : { before, after },
      rowBefore,
      rowAfter: Math.round(box(slot).height * 100) / 100,
      toggleHeight: toggle ? Math.round(box(toggle).height * 100) / 100 : null,
      left: Math.round((box(slot).left - headerLeft) * 100) / 100,
      text: toggle?.textContent ?? null,
      cut: breakdown !== null && breakdown.scrollWidth > breakdown.clientWidth,
      tip: toggle?.dataset.tipText ?? null,
    };
    summary.dispose();
    // Once a width: a change set five folders deep, opened in the header's last row, where
    // the tree steps in from its header one level at a time (mb-hi4l).
    window.__summaryIndentWidths ??= new Set();
    if (!window.__summaryIndentWidths.has(width)) {
      window.__summaryIndentWidths.add(width);
      const nested = diff.mountDiffSummary(slot, ${NESTED_SUMMARY}, mb, {
        changedFiles: window.MetabrowserChangedFilesTree,
        openFile() {},
      });
      await frames();
      summaryMoves.indent = await (${SUMMARY_INDENT})(slot);
      nested.dispose();
    }
  }
  // A stack's chip arrives late, from its own answer, through the page's own builder, at
  // the right end of the row of ages, ending it at the content edge, under the end of the
  // title's number where the title leaves the corner no room (mb-646g, mb-dwha, mb-ablv): one stack, "⧉2/3", or two, "⧉286 4/4" and "⧉300 2/2", each named by its
  // stack, as the page names a chip in more than one stack. Its Layers glyph is a bare svg at
  // the glyph's size, so the chip is as wide as the page's. The strut that holds the row of
  // ages at a chip's height, read before a chip replaces it.
  const heldBy = header.querySelector(".github-pull-opened > .github-pull-stacks > .github-pull-stack-strut");
  const strutHeight = heldBy ? Math.round(box(heldBy).height * 100) / 100 : null;
  let chipMoves = null;
  if (change.stackChip && group) {
    const before = places();
    const layers = () => document.createElementNS("http://www.w3.org/2000/svg", "svg");
    const stacks =
      change.stackChip === 2
        ? [
            { number: 286, pulls: [body.number - 3, body.number - 2, body.number - 1, body.number] },
            { number: 300, pulls: [body.number - 1, body.number] },
          ]
        : [{ number: 286, pulls: [body.number - 1, body.number, body.number + 1] }];
    const menus = stacks.map((stack) =>
      page.createStackMenu(stack, body.number, {
        link: () => document.createElement("a"),
        icon: layers(),
        currentTitle: "",
        named: change.stackChip === 2,
        titleNodes: mb.titleNodes,
        shortCommit: mb.shortCommit,
        onOpen() {},
        menus: mb.menus,
      }),
    );
    const column = header.querySelector(".github-pull-stacks");
    column.replaceChildren(...menus.map((menu) => menu.element));
    await frames();
    const after = places();
    // Nothing moves: every part keeps its start, every row its height, the tab bar its place.
    // The ages alone may give up width at their end where the row has none left, and Browse
    // code after them, kept whole while any age shows (B4 of review B on #506), follows their
    // end, as the action followed a shorter author on the author's row (mb-cf0l).
    const follows = new Set([".github-pull-ages-links"]);
    const kept = (shape) => ({
      parts: shape.parts.map(([selector, left, width]) => [
        selector,
        follows.has(selector) ? null : left,
        selector === ".github-pull-ages" ? null : width,
      ]),
      rows: shape.rows,
      tabBar: shape.tabBar,
    });
    const agesWidth = (shape) =>
      shape.parts.find(([selector]) => selector === ".github-pull-ages")?.[2] ?? 0;
    const row = header.querySelector(".github-pull-opened");
    const quiet = row.querySelector(":scope > .github-pull-quiet");
    const ages = quiet.querySelector(".github-pull-ages");
    const links = quiet.querySelector(".github-pull-ages-links");
    const r = (value) => Math.round(value * 100) / 100;
    // Where the chip's end is against the title's number's and the header's content edge
    // (mb-dwha): nothing follows it on the row, since the page has no Refresh (mb-ablv).
    const numberRange = document.createRange();
    numberRange.selectNodeContents(header.querySelector(".github-pull-title-with-state .github-pull-number"));
    const numberEnd = numberRange.getBoundingClientRect().right;
    const contentEnd = box(header).right - parseFloat(getComputedStyle(header).paddingRight);
    const titleRoom = parseFloat(getComputedStyle(header.querySelector(".github-pull-title")).paddingInlineEnd);
    const chipEnd = () => Math.max(...menus.map((menu) => box(menu.element).right));
    const ends = { number: r(chipEnd() - numberEnd), content: r(chipEnd() - contentEnd) };
    chipMoves = {
      chips: stacks.length,
      moved: JSON.stringify(kept(before)) === JSON.stringify(kept(after)) ? null : { before, after },
      // How much of the ages' width the chip took.
      cut: r(agesWidth(before) - agesWidth(after)),
      chipShown: Math.min(...menus.map((menu) => shown(menu.element))),
      // The slot is the row of ages' own, ending the row, and the chip sits on that row's
      // line.
      onAgesRow:
        column.parentElement === row &&
        column === row.lastElementChild &&
        menus.every((menu) => {
          const chip = box(menu.element);
          return chip.top >= box(row).top - 0.5 && chip.bottom <= box(row).bottom + 0.5;
        }),
      overlap: r(box(quiet).right - box(column).left),
      rowGap: parseFloat(getComputedStyle(row).columnGap),
      titleRoom: r(titleRoom),
      contentEnd: r(contentEnd),
      ends,
      chipWidth: r(box(column).width),
      // A chip's position cut short, and whether the ages and Browse code had any width left
      // when it was.
      positionCut: menus.some((menu) => {
        const position = menu.element.querySelector(".github-pull-stack-trigger > .github-pull-stack-position");
        return position !== null && position.scrollWidth > position.clientWidth;
      }),
      textLeft: r(box(ages).width) >= 1 || (links !== null && shown(links) > 0.01),
    };
    // Its member menu heads its rows with the host's menu group, whose heading starts
    // on the rows' inset (docs/design-system.md, "Groups in a Menu"). A second menu of
    // the same stack is opened outside the header, through its disclosure, which
    // populates it on its toggle event, and removed again: the header's own menu stays
    // lazy, as the checks below expect.
    const probe = page.createStackMenu(
      { number: 286, pulls: [body.number - 1, body.number, body.number + 1] },
      body.number,
      { link: () => document.createElement("a"), icon: null, currentTitle: "", titleNodes: mb.titleNodes, onOpen() {}, menus: mb.menus },
    );
    const holder = document.createElement("div");
    holder.className = "github-pull-stacks";
    holder.style.position = "relative";
    document.body.append(holder);
    holder.append(probe.element);
    probe.element.open = true;
    await frames();
    const heading = probe.element.querySelector(".group-heading");
    const member = probe.element.querySelector(".github-pull-stack-member");
    const textLeft = (node) => {
      const range = document.createRange();
      range.selectNodeContents(node);
      return range.getBoundingClientRect().left;
    };
    chipMoves.headingInset =
      heading && member
        ? Math.round(
            (textLeft(heading) - box(member).left - parseFloat(getComputedStyle(member).paddingLeft)) * 100,
          ) / 100
        : null;
    // A menu of one group: its heading names the menu, once, over its members.
    const menuElement = probe.element.querySelector(".github-pull-stack-menu");
    chipMoves.headingNamesMenu =
      heading !== null &&
      menuElement?.getAttribute("aria-labelledby") === heading.id &&
      !menuElement.hasAttribute("aria-label") &&
      !heading.parentElement.hasAttribute("role") &&
      heading.parentElement.contains(member);
    probe.dispose();
    holder.remove();
  }
  // The header's rows: its children but the corner, the View on GitHub button's, which is
  // placed in the page's upper right out of their flow (mb-4wqh).
  const headerRows = [...header.children].filter((row) => !row.matches(".view-header-end"));
  const rows = headerRows.map((row) => ({
    row: row.tagName === "H1" ? "title" : [...row.classList].find((c) => c.startsWith("github-pull-")).slice(12),
    height: Math.round(box(row).height * 100) / 100,
  }));
  const meta = header.querySelector(".github-pull-meta");
  // The state badge leads the row of ages (mb-4ydo).
  const opened = header.querySelector(".github-pull-opened");
  const badge = opened?.querySelector(".github-pull-badge");
  const centre = (r) => r.top + r.height / 2;
  // The title's icon and text start at the header's left edge and its number ends on the
  // right one, over the end of the row of ages, which the stack's chip ends (mb-z416,
  // mb-646g, mb-ablv).
  const heading = header.querySelector(".github-pull-title-with-state");
  const edges = (() => {
    if (!heading) return null;
    const left = box(header).left + parseFloat(getComputedStyle(header).paddingLeft);
    const right = box(header).right - parseFloat(getComputedStyle(header).paddingRight);
    const icon = box(heading.querySelector(".github-pull-state-icon"));
    const range = document.createRange();
    range.selectNodeContents(heading.querySelector(".github-pull-title-text"));
    const text = range.getBoundingClientRect();
    const numberRange = document.createRange();
    numberRange.selectNodeContents(heading.querySelector(".github-pull-number"));
    const number = numberRange.getBoundingClientRect();
    const r = (v) => Math.round(v * 100) / 100;
    // The room the title leaves the corner's button where the reading column reaches it
    // (github/styles.css), which its number ends short of.
    const room = parseFloat(getComputedStyle(heading).paddingInlineEnd);
    return {
      iconLeft: r(icon.left - left),
      textAfterIcon: r(text.left - icon.right),
      gap: r(parseFloat(getComputedStyle(heading).columnGap)),
      room: r(room),
      numberRight: r(number.right + room - right),
      numberOverRow: opened ? r(number.right + room - box(opened).right) : null,
      numberBelowText: r(number.bottom - text.bottom),
    };
  })();
  // Where each row shown starts and ends, from the header's top, and the header's one gap
  // between rows: the status line, while it has something to say, is one of the metadata
  // lines under the title, as tall as the author's row and one gap under the row before it,
  // with no empty labels row between (mb-2u08); with nothing to say it is not there (mb-ne91).
  const lines = headerRows
    .map((row, at) => ({
      row: rows[at].row,
      shown: !row.hidden,
      top: Math.round((box(row).top - box(header).top) * 100) / 100,
      bottom: Math.round((box(row).bottom - box(header).top) * 100) / 100,
    }))
    .filter((each) => each.shown)
    .map(({ shown, ...each }) => each);
  const r2 = (value) => Math.round(value * 100) / 100;
  // The status line's remedy, Retry or Fetch, first among its offers, a line tall (mb-ablv).
  const remedy = header.querySelector(".github-pull-status-end > .github-pull-remedy");
  const contentEdge = box(header).right - parseFloat(getComputedStyle(header).paddingRight);
  // The freshness note ends the author's row's lead (mb-ne91). Its slot is as wide as its
  // widest age, so the age ticking from "just now" to "59 min ago" changes its width not at
  // all: the slot's width at each, then the note put back.
  const lead = header.querySelector(".github-pull-meta-lead");
  const note = header.querySelector(".github-pull-note");
  const noteText = note?.querySelector(".github-pull-freshness") ?? null;
  const ageWidens = (() => {
    if (noteText === null || note.hidden || !/^Fetched .+ via GitHub CLI$/.test(noteText.textContent)) return null;
    const slot = note.querySelector(".github-pull-freshness-slot");
    const was = noteText.textContent;
    const at = (text) => {
      noteText.textContent = text;
      return box(slot).width;
    };
    const widened = Math.abs(at("Fetched just now via GitHub CLI") - at("Fetched 59 min ago via GitHub CLI"));
    noteText.textContent = was;
    return r2(widened);
  })();
  // Beside the sentence the note is whole or out of view, dot and all, and while it is in
  // view the login and the sentence keep their natural widths: the width each lays out to
  // alone, at max-content, beside the width it has (A2 of review A on #506).
  const natural = (node) => {
    const probe = node.cloneNode(true);
    probe.style.cssText = "position: absolute; visibility: hidden; width: max-content; min-width: 0; max-width: none";
    node.parentElement.append(probe);
    const width = box(probe).width;
    probe.remove();
    return r2(width);
  };
  const inView = (node) =>
    node !== null && lead !== null && !node.hidden && box(node).height > 0 &&
    box(node).top < box(lead).bottom - 0.5 && box(node).bottom > box(lead).top + 0.5 && shown(node) > 0;
  const login = header.querySelector(".github-pull-meta-details .github-pull-author");
  const action = header.querySelector(".github-pull-meta-details > .github-pull-action");
  const sep = header.querySelector(".github-pull-note-sep");
  const leadShape = lead === null ? null : {
    said: noteText?.textContent ?? null,
    held: noteText?.classList.contains("github-pull-freshness-held") ?? false,
    // The width "GitHub rate limit" takes in the note's own type: a cut hold keeps at least
    // that much of its text (C4 of review C on #506).
    holdFloor: (() => {
      if (noteText === null) return null;
      const probe = noteText.cloneNode(false);
      probe.style.cssText = "position: absolute; visibility: hidden; width: max-content";
      probe.textContent = "GitHub rate limit";
      noteText.parentElement.append(probe);
      const width = box(probe).width;
      probe.remove();
      return r2(width);
    })(),
    inView: inView(note),
    dotInView: sep !== null && inView(sep),
    textWidth: noteText ? r2(box(noteText).width) : null,
    cut: noteText !== null && noteText.scrollWidth > noteText.clientWidth,
    tip: (() => {
      if (noteText === null) return null;
      noteText.dispatchEvent(new Event("pointerenter"));
      return noteText.dataset.tipText ?? null;
    })(),
    sentence: action !== null && action.offsetParent !== null,
    login: login ? { width: r2(box(login).width), natural: natural(login) } : null,
    action: action ? { width: r2(box(action).width), natural: natural(action) } : null,
  };
  // The row of ages: its ages give way first, and Browse code after them stays whole (B4 of
  // review B on #506). How much of the link shows, all of it where there is none, and how
  // wide the ages are drawn against their own width.
  const agesText = header.querySelector(".github-pull-opened .github-pull-ages");
  const agesLinks = header.querySelector(".github-pull-opened .github-pull-ages-links");
  const agesRow = agesText === null
    ? null
    : {
        linksShown: agesLinks === null ? 1 : Math.round(shown(agesLinks) * 1000) / 1000,
        links: agesLinks === null
          ? []
          : [...agesLinks.querySelectorAll("a, button")].map((node) => node.textContent.trim()),
        agesWidth: r2(box(agesText).width),
        agesNatural: r2(agesText.scrollWidth),
        text: agesText.textContent,
      };
  const result = {
    edges,
    agesRow,
    header: Math.round(box(header).height * 100) / 100,
    tabBar: Math.round(box(container.querySelector(".tab-bar")).top - box(header).top),
    rows,
    lines,
    rowGap: parseFloat(getComputedStyle(header).rowGap),
    bottomPadding: parseFloat(getComputedStyle(header).paddingBottom),
    contentPadding: parseFloat(getComputedStyle(header).getPropertyValue("--content-padding-y")),
    // The page's one gap under a title, before its first metadata line (mb-wcbc).
    titleGap: parseFloat(getComputedStyle(header).getPropertyValue("--page-title-gap")),
    // How many labels the record names, or null while there is no record.
    recordLabels: body.record ? body.record.pull.labels.length : null,
    // No Refresh of the page's own on the row of ages or anywhere in the header (mb-ablv).
    pageRefresh: header.querySelector(".github-pull-refresh") !== null,
    remedy: remedy
      ? {
          label: remedy.textContent,
          height: r2(box(remedy).height),
          first: remedy === remedy.parentElement.firstElementChild,
          // Whole, and inside the content edge.
          whole: remedy.scrollWidth <= remedy.clientWidth + 0.5,
          rightEdge: r2(box(remedy).right - contentEdge),
          statusHeight: r2(box(remedy.closest(".github-pull-status")).height),
        }
      : null,
    ageWidens,
    lead: leadShape,
    statusShown: !header.querySelector(".github-pull-status").hidden,
    meta: meta ? Math.round(box(meta).height * 100) / 100 : null,
    // The author's row is its lead alone, a line tall (mb-646g).
    metaLead: lead ? Math.round(box(lead).height * 100) / 100 : null,
    agesRowHeight: opened ? Math.round(box(opened).height * 100) / 100 : null,
    strut: strutHeight,
    badgeOffset: badge ? Math.round((centre(box(badge)) - centre(box(opened))) * 100) / 100 : null,
    // The offers drawn where a reader sees them: laid out, with some of each in view.
    offers: [...header.querySelectorAll(".github-pull-offer")].filter(
      (offer) => box(offer).height > 0 && shown(offer) > 0,
    ).length,
    mergeShown,
    chipMoves,
    summaryMoves,
    // How far any of the header's content ends past its content box, where it is not
    // clipped by a box that cuts it short, and which element it is; and the pane's own
    // sideways scroll.
    ...(() => {
      const edge = box(header).right - parseFloat(getComputedStyle(header).paddingRight);
      let past = 0;
      let culprit = null;
      for (const node of header.querySelectorAll("*")) {
        let right = box(node).right;
        for (let up = node.parentElement; up && up !== header; up = up.parentElement) {
          if (getComputedStyle(up).overflowX !== "visible") {
            right = Math.min(right, box(up).right);
          }
        }
        if (right - edge > past) {
          past = right - edge;
          culprit = node.className || node.tagName;
        }
      }
      return { pastHeader: Math.round(past * 100) / 100, culprit };
    })(),
    paneScrolls: pane.scrollWidth > pane.clientWidth,
    // Each label chip's computed colors and box, and the neutral chip's tokens in this
    // theme: --muted and --border, read from a probe that is painted with them.
    branchChipHeights: [...header.querySelectorAll(".merge-refs .git-ref")].map(
      (chip) => box(chip).height,
    ),
    statusBadgeHeight: badge ? box(badge).height : null,
    labels: [...header.querySelectorAll(".github-pull-label")].map((chip) => {
      const style = getComputedStyle(chip);
      // A baseline-aligned marker measures the capital band independently of its line box.
      const cap = document.createElement("span");
      cap.style.cssText = "display:inline-block;width:0;height:1cap;vertical-align:baseline";
      chip.append(cap);
      const capOffset = centre(box(cap)) - centre(box(chip));
      cap.remove();
      return {
        name: chip.textContent,
        color: chip.dataset.color ?? null,
        properties: chip.getAttribute("style"),
        tip: chip.getAttribute("data-tip-text"),
        background: style.backgroundColor,
        text: style.color,
        border: style.borderTopColor,
        box: [
          style.fontSize, style.paddingTop, style.paddingRight, style.paddingBottom, style.paddingLeft,
          style.borderTopWidth, style.borderTopLeftRadius, Math.round(box(chip).height * 100) / 100,
        ].join(" "),
        height: box(chip).height,
        capOffset,
        left: Math.round(box(chip).left * 100) / 100,
        width: Math.round(box(chip).width * 100) / 100,
      };
    }),
    neutral: (() => {
      const probe = document.createElement("span");
      probe.style.color = "var(--muted)";
      probe.style.border = "1px solid var(--border)";
      header.append(probe);
      const style = getComputedStyle(probe);
      const tokens = { text: style.color, border: style.borderTopColor };
      probe.remove();
      return tokens;
    })(),
  };
  handle.dispose();
  delete document.documentElement.dataset.theme;
  return result;
}`;

// A record that has not arrived, records still loading, loaded, merged, closed, stale, with
// the checkout on its head, with each offer the status row can draw, and held by a rate
// limit, and a loaded one with no labels, as the merged record has none. A failure is let
// wrap its status row, so it is not among them.
const RATE_LIMITED = {
  outcome: "rate_limited",
  message: null,
  reset_at: "2099-01-01T00:00:00Z",
  at: "2026-09-17T12:30:00Z",
};
const RECORDS = [
  ["absent", {}],
  ["pending", {}],
  ["current", {}],
  ["merged", {}],
  ["closed", {}],
  ["stale", {}],
  ["on_head", {}],
  ["followed_head", {}],
  ["on_head", { checkoutAtHead: true }],
  ["current", { lastRefresh: RATE_LIMITED }],
  ["current", { lastRefresh: RATE_LIMITED, liftSoon: true }],
  ["current", { avatar: true }],
  ["current", { longTitle: true }],
  ["current", { longNames: true }],
  ["current", { longNames: true, avatar: true }],
  ["merged", { longNames: true, avatar: true }],
  ["current", { noLabels: true }],
];
// In the page: the Diff summary's row while the page waits for its comparison, and as it
// arrives or fails (mb-onr2). The page is the production one, its diff view a stand-in whose
// prefetch is a read the session answers and whose summary is the diff plugin's own
// mountDiffSummary, as the plugin's summary draws it. The row holds the shell's pending
// placeholder, `.tally-pending`, after the quiet period, and the summary takes its place
// moving nothing; a read that fails leaves the row empty, at its height.
const SUMMARY_WAIT = `async (width, theme, outcome, change = null) => {
  const recorded = window.__recorded ??= await (await fetch("/fixtures.json")).json();
  const page = window.__page ??= await import("/github/pull-page.js");
  const diff = (window.__diff ??= await import("/diff/diff-view.js"));
  const body = structuredClone(recorded.current.body);
  // Each run reads a comparison of its own. The page keeps what it read of a comparison for
  // the document, by its route (comparison-prefetch.js, documentComparisons), so a run
  // under an earlier run's route would draw that run's summary at once, with no wait.
  window.__summaryRuns = (window.__summaryRuns ?? 0) + 1;
  body.comparison_route = "/summary-wait/" + window.__summaryRuns;
  document.documentElement.dataset.theme = theme;
  window.fetch = async () => new Response(null, { status: 304 });
  history.replaceState(null, "", "/pull/" + body.number);
  const pane = document.getElementById("preview-pane");
  pane.style.width = width + "px";
  const container = document.createElement("div");
  pane.replaceChildren(container);
  const mb = window.metabrowser;
  let answer = null;
  const read = new Promise((resolve, reject) => {
    answer = { resolve, reject };
  });
  // The change set: by default, the reader's three statuses; *change* names others, as
  // [[kind, files], ...] and its line totals.
  const statuses = change?.kinds ?? [["added", 2], ["deleted", 3], ["modified", 30]];
  const kinds = statuses.flatMap(([kind, many]) => Array(many).fill(kind));
  const files = kinds.map((kind, at) => ({
    kind,
    ...(kind === "added" ? {} : { old: { path: "src/f" + at + ".py" } }),
    ...(kind === "deleted" ? {} : { new: { path: "src/f" + at + ".py" } }),
    additions: 30,
    deletions: 90,
  }));
  const lines = change?.lines ?? [1234, 3423];
  const comparison = { manifest: { totals: { files: kinds.length, additions: lines[0], deletions: lines[1], exact: true }, files } };
  // For "brief", the cached changed-files list of the same change set, which the page draws
  // as the brief line in the row while the comparison is read (mb-z8ea).
  if (outcome === "brief") {
    const summary = {
      number: body.number,
      state: "listed",
      reason: null,
      listing: false,
      listed_from: "comparison",
      generation: "brief-" + window.__summaryRuns,
      head: body.record.comparison.head,
      base: body.record.comparison.base,
      base_ref: null,
      files: kinds.length,
      additions: lines[0],
      deletions: lines[1],
      exact: true,
      // In a pull request's words, which the list is kept in: GitHub's "removed".
      statuses: statuses.map(([status, count]) => ({ status: status === "deleted" ? "removed" : status, count })),
    };
    window.fetch = async (route) =>
      String(route).startsWith("/api/plugin/github/pull-files-summary?")
        ? new Response(JSON.stringify({ source: body.source, rows: [summary] }), { status: 200, headers: { "content-type": "application/json" } })
        : new Response(null, { status: 304 });
  }
  const view = {
    prefetch: () => read,
    summary: async (slot, ctx) =>
      diff.mountDiffSummary(slot, ctx.raw, mb, { changedFiles: window.MetabrowserChangedFilesTree, openFile() {} }),
  };

  // A revisit opens the pull request whose comparison last arrived again, in this document
  // (mb-neg9): the page draws its summary from the comparison it kept, and reads nothing.
  // Its summary waits for the shared tree as the diff plugin's own does, which a loaded
  // bundle answers from a resolved promise (asset-loader.js, ensureAsset). Each frame from
  // the mount until the record's title is painted says what the row held, and the row's
  // mutations say whether the placeholder was put in it at all.
  if (outcome === "arrives") {
    window.__summaryArrived = body.comparison_route;
  } else if (outcome === "revisit") {
    body.comparison_route = window.__summaryArrived;
    const drawSummary = view.summary;
    view.summary = async (slot, ctx) => {
      await Promise.resolve().then(() => window.MetabrowserChangedFilesTree);
      return drawSummary(slot, ctx);
    };
  }
  let reads = 0;
  const readOnce = view.prefetch;
  view.prefetch = () => {
    reads += 1;
    return readOnce();
  };
  let placeholderPlaced = false;
  const placements = new MutationObserver((records) => {
    for (const record of records) {
      for (const node of record.addedNodes) {
        if (node.nodeType === 1 && (node.matches(".github-pull-summary-pending, .tally-pending") || node.querySelector(".tally-pending"))) {
          placeholderPlaced = true;
        }
      }
    }
  });
  placements.observe(container, { childList: true, subtree: true });
  const seenFrames = [];
  const recordPainted = new Promise((resolve) => {
    const look = () => {
      const row = container.querySelector(".github-pull-summary");
      const title = container.querySelector(".github-pull-header h1")?.textContent?.trim() ?? "";
      seenFrames.push({
        title: title !== "",
        summary: row?.querySelector(".diff-summary") != null,
        placeholder: row?.querySelector(".tally-pending") != null,
      });
      if (title !== "" || seenFrames.length >= 30) {
        resolve(seenFrames);
      } else {
        requestAnimationFrame(look);
      }
    };
    requestAnimationFrame(look);
  });
  const handle = page.mountPullPage(
    container,
    { number: body.number, tab: "", reader: { initial: { etag: null, body }, fetchAfterMs: 60000 } },
    {
      perf: { measure: (_label, work) => work(), measureAsync: (_label, work) => work() },
      ensureAsset: async () => {},
      whenIdle: (callback) => {
        const id = setTimeout(callback, 0);
        return () => clearTimeout(id);
      },
      ensureKindAssets: async () => {},
      loadChangedFilesTree: async () => window.MetabrowserChangedFilesTree,
      getRegisteredView: () => view,
      decorateExternalLink: mb.decorateExternalLink,
      refChip: mb.refChip,
      refChipHtml: mb.refChipHtml,
      mergeRefs: mb.mergeRefs,
      mountRefMenus: mb.mountRefMenus,
      actorIdentity: mb.actorIdentity,
      titleNodes: mb.titleNodes,
      shortCommit: mb.shortCommit,
      countPartsNodes: mb.countPartsNodes,
      changeLine: mb.changeLine,
      changeLineNodes: mb.changeLineNodes,
      formatInteger: mb.formatInteger,
      ...(${agesFrom})(document, () => ({ label: "now", className: "age" })),
      formatTimestamp: (seconds) => new Date(seconds * 1000).toISOString(),
      formatInteger: (value) => Number(value).toLocaleString("en-US"),
      navigation: { href: () => "/view/" },
      sourceKind: () => "filesystem",
      icons: { toggle: "" },
    },
  );
  await Promise.resolve();
  if (outcome === "revisit") {
    const painted = await recordPainted;
    placements.disconnect();
    handle.dispose();
    delete document.documentElement.dataset.theme;
    return { revisit: { frames: painted, reads, placeholderPlaced } };
  }
  placements.disconnect();
  const header = container.querySelector(".github-pull-header");
  const row = header.querySelector(".github-pull-summary");
  const round = (value) => Math.round(value * 100) / 100;
  const box = (node) => node.getBoundingClientRect();
  const wrapper = () => row.querySelector(".github-pull-summary-pending");
  // The text a line shows: without the words only a screen reader is told.
  const seenText = (node) => {
    const copy = node.cloneNode(true);
    for (const hidden of copy.querySelectorAll(".visually-hidden, .diff-summary-chevron")) hidden.remove();
    return copy.textContent;
  };
  // Inside the quiet period: the placeholder is in the row and not yet seen.
  const quiet = wrapper() ? getComputedStyle(wrapper()).visibility : null;
  await document.fonts.ready;
  const frames = () => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
  const delay = parseFloat(getComputedStyle(document.documentElement).getPropertyValue("--loading-state-delay"));
  await new Promise((resolve) => setTimeout(resolve, delay * 2));
  await frames();
  const contentLeft = box(header).left + parseFloat(getComputedStyle(header).paddingLeft);
  // The header's rows, but not the corner, which is out of their flow (mb-4wqh).
  const places = () => ({
    rows: [...header.children].filter((child) => !child.matches(".view-header-end")).map((child) => [
      child.tagName === "H1" ? "title" : [...child.classList].find((c) => c.startsWith("github-pull-")).slice(12),
      round(box(child).top - box(header).top),
      round(box(child).height),
    ]),
    tabBar: round(box(container.querySelector(".tab-bar")).top - box(header).top),
  });
  const block = row.querySelector(".tally-pending");
  const probe = document.createElement("span");
  probe.style.background = "var(--tally-skeleton-bg)";
  header.append(probe);
  const skeleton = getComputedStyle(probe).backgroundColor;
  probe.remove();
  const waiting = {
    quiet,
    shown: block ? getComputedStyle(block).visibility : null,
    pulse: block ? getComputedStyle(block).animationName : null,
    ground: block ? getComputedStyle(block).backgroundColor === skeleton : false,
    left: block ? round(box(block).left - contentLeft) : null,
    width: block ? round(box(block).width) : null,
    height: block ? round(box(block).height) : null,
    em: block ? round(parseFloat(getComputedStyle(block).fontSize)) : null,
    centre: block ? round((box(block).top + box(block).bottom) / 2 - (box(row).top + box(row).bottom) / 2) : null,
    row: round(box(row).height),
    places: places(),
    brief: (() => {
      const line = row.querySelector(".github-pull-summary-brief");
      const words = line?.querySelector(".change-line");
      if (!line || !words) return null;
      const range = document.createRange();
      range.selectNodeContents(line);
      return {
        text: seenText(line),
        wordsLeft: round(box(words).left - contentLeft),
        wordsTop: round(box(words).top - box(row).top),
        textRight: round(range.getBoundingClientRect().right - contentLeft),
        em: round(parseFloat(getComputedStyle(line).fontSize)),
      };
    })(),
  };
  if (outcome === "fails") {
    answer.reject(new Error("refused"));
  } else {
    answer.resolve(comparison);
  }
  const deadline = performance.now() + 5000;
  const settled = () =>
    outcome === "fails" ? row.querySelector(".tally-pending") === null : row.querySelector(".diff-summary") !== null;
  while (!settled() && performance.now() < deadline) {
    await new Promise((resolve) => setTimeout(resolve, 10));
  }
  await frames();
  const summary = row.querySelector(".diff-summary");
  const chevron = row.querySelector(".diff-summary-chevron svg, .diff-summary-chevron");
  const words = row.querySelector(".change-line");
  const arrived = {
    placeholder: row.querySelector(".tally-pending") !== null,
    summary: summary !== null,
    children: row.children.length,
    row: round(box(row).height),
    places: places(),
    toggleLeft: summary ? round(box(summary).left - contentLeft) : null,
    chevronLeft: chevron ? round(box(chevron).left - contentLeft) : null,
    wordsLeft: words ? round(box(words).left - contentLeft) : null,
    wordsTop: words ? round(box(words).top - box(row).top) : null,
    text: summary ? seenText(summary) : null,
    width: summary ? round(box(summary).width) : null,
    em: summary ? round(parseFloat(getComputedStyle(summary).fontSize)) : null,
    label: summary ? summary.getAttribute("aria-label") : null,
    textRight: (() => {
      if (!summary) return null;
      const range = document.createRange();
      range.selectNodeContents(summary);
      return round(range.getBoundingClientRect().right - contentLeft);
    })(),
  };
  handle.dispose();
  delete document.documentElement.dataset.theme;
  return { waiting, arrived };
}`;
// Change sets of one status, from the shortest summary to a longer one, which the pending
// placeholder is sized from (`.github-pull-summary-pending` in github/styles.css; mb-vb51).
const ONE_STATUS = [
  { kinds: [["modified", 1]], lines: [3, 1] },
  { kinds: [["modified", 8]], lines: [120, 30] },
];
// The placeholder's width in em of its type, as its rule sets it, `min(100%, 7em)`.
const PENDING_EM = 7;

// In the page: a pull request page mounted with no record in hand, as a direct load or a
// reload mounts it, whose pull read the session answers (docs/design-system.md, "Layout").
// The quiet period is set long, so where it ends is the session's to say: it finishes the
// hold's animation itself before the read for `slow`. For `held` the description's Markdown
// never answers, so the conversation's first paint stays held while the header lands with
// its record. Every frame from the mount to the landing is read: whether the header and the
// tab column show, the cold header or the record's, where the tab bar is against the same
// record mounted in hand, and what the Diff summary's row holds. Its placeholder's own
// reveal, the same quiet period's (`.mb-delayed-loading`), ends with it. A `seeded` page
// has the Pulls tab's row for its pull request in hand, as the list notes it
// (`noteListed`), so its cold header is titled as the record will be; the note outlives the
// mount, so the seeded landings run last.
const COLD_LANDING = `async (width, labelled, outcome, seeded) => {
  const recorded = window.__recorded ??= await (await fetch("/fixtures.json")).json();
  const page = window.__page ??= await import("/github/pull-page.js");
  const states = window.__states ??= await import("/github/pull-state.js");
  const body = structuredClone(recorded.current.body);
  const holder = body.record?.same_as;
  if (holder !== undefined) {
    body.record = structuredClone(recorded[holder].body.record);
  }
  if (!labelled) {
    body.record.pull.labels = [];
  }
  if (seeded) {
    const pull = body.record.pull;
    states.noteListed("https://github.com/octo/demo", "all", [
      { number: body.number, state: states.displayState(pull), updatedAt: pull.updated_at, title: pull.title },
    ]);
  }
  const realFetch = window.__realFetch ??= window.fetch;
  const pane = document.getElementById("preview-pane");
  pane.style.width = width + "px";
  const mb = window.metabrowser;
  const deps = {
    perf: { measure: (_label, work) => work(), measureAsync: (_label, work) => work() },
    ensureAsset: async () => {},
    whenIdle: mb.whenIdle,
    ensureKindAssets: async () => {},
    loadChangedFilesTree: async () => {},
    getRegisteredView: () => null,
    decorateExternalLink: mb.decorateExternalLink,
    refChip: mb.refChip,
    refChipHtml: mb.refChipHtml,
    mergeRefs: mb.mergeRefs,
    mountRefMenus: mb.mountRefMenus,
    actorIdentity: mb.actorIdentity,
    titleNodes: mb.titleNodes,
    shortCommit: mb.shortCommit,
    countPartsNodes: mb.countPartsNodes,
    ...(${agesFrom})(document, () => ({ label: "now", className: "age" })),
    formatTimestamp: (seconds) => new Date(seconds * 1000).toISOString(),
    formatInteger: (value) => Number(value).toLocaleString("en-US"),
    navigation: { href: () => "/view/" },
    sourceKind: () => "filesystem",
    icons: { toggle: "" },
  };
  const frames = () => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
  const round = (value) => Math.round(value * 100) / 100;
  const tabBarOf = (container) =>
    round(container.querySelector(".tab-bar").getBoundingClientRect().top - container.getBoundingClientRect().top);
  history.replaceState(null, "", "/pull/" + body.number);
  window.fetch = async () => new Response(null, { status: 304 });
  // The same record mounted in hand: where its tab bar is.
  const inHand = document.createElement("div");
  pane.replaceChildren(inHand);
  const opened = page.mountPullPage(inHand, { number: body.number, tab: "", reader: { initial: { etag: null, body }, fetchAfterMs: 60000 } }, deps);
  await document.fonts.ready;
  await frames();
  const landsAt = tabBarOf(inHand);
  const inHandTitle = round(inHand.querySelector(".github-pull-header > h1").getBoundingClientRect().height);
  opened.dispose();
  document.documentElement.style.setProperty("--loading-state-delay", "60s");
  let answer = null;
  const read = new Promise((resolve) => {
    answer = resolve;
  });
  window.fetch = async (route) => {
    const url = String(route);
    if (url.startsWith("/api/plugin/github/pull?")) {
      await read;
      return new Response(JSON.stringify(body), { status: 200, headers: { "content-type": "application/json" } });
    }
    if (outcome === "held" && url.startsWith("/api/plugin/github/pull-markdown")) {
      return new Promise(() => {});
    }
    return new Response(null, { status: 304 });
  };
  const container = document.createElement("div");
  pane.replaceChildren(container);
  const handle = page.mountPullPage(container, { number: body.number, tab: "", reader: null }, deps);
  const header = container.querySelector(".github-pull-header");
  const column = () => container.querySelector(".tab-bar")?.parentElement ?? null;
  const seen = [];
  const look = (step) => {
    const tabColumn = column();
    const state = {
      step,
      header: getComputedStyle(header).opacity,
      column: tabColumn ? getComputedStyle(tabColumn).opacity : null,
      cold: header.classList.contains("github-pull-cold"),
      // The cold title the Pulls tab's row titles, the record's shape, or "Pull request #7".
      seeded: header.querySelector("h1")?.classList.contains("github-pull-title-with-state") ?? false,
      title: round(header.querySelector("h1")?.getBoundingClientRect().height ?? 0),
      tabBar: tabColumn ? tabBarOf(container) : null,
      live: tabColumn ? [...tabColumn.querySelectorAll(".tab-btn")].map((link) => link.checkVisibility({ visibilityProperty: true }) && !link.closest("[inert]")) : [],
      // The Diff summary's row: its pending placeholder from first paint (mb-30dz), and
      // whether its quiet period is over.
      pending: (() => {
        const placeholder = header.querySelector(".github-pull-summary > .github-pull-summary-pending");
        return placeholder === null ? "none" : getComputedStyle(placeholder).visibility;
      })(),
    };
    seen.push(state);
    return state;
  };
  // The quiet period's end: the hold's animation, run to its end.
  const quietEnds = () => {
    const placeholder = header.querySelector(".github-pull-summary-pending");
    for (const part of [header, column(), placeholder]) {
      for (const animation of part?.getAnimations() ?? []) {
        animation.finish();
      }
    }
  };
  let sampling = true;
  const sample = () => {
    if (sampling) {
      look("frame");
      requestAnimationFrame(sample);
    }
  };
  requestAnimationFrame(sample);
  await frames();
  const before = look("before the read");
  if (outcome === "slow") {
    quietEnds();
    await frames();
  }
  const shownCold = look("the read on its way");
  answer();
  const deadline = performance.now() + 5000;
  while (performance.now() < deadline) {
    await new Promise((resolve) => setTimeout(resolve, 5));
    if (!look("landing").cold) {
      break;
    }
  }
  await frames();
  sampling = false;
  const landed = look("landed");
  // A held landing's conversation is still out of sight, waiting for its Markdown.
  const bodyHeld =
    container.querySelector(".github-pull-body")?.classList.contains("github-pull-body-holding") ?? null;
  // Whether the record's title keeps the cold title's two lines (the held class).
  const held = header.classList.contains("github-pull-title-held");
  handle.dispose();
  document.documentElement.style.removeProperty("--loading-state-delay");
  window.fetch = realFetch;
  return {
    landsAt,
    inHandTitle,
    held,
    before,
    shownCold,
    landed,
    bodyHeld,
    coldShown: seen.filter((state) => state.cold && Number(state.header) > 0).length,
    halfShown: seen.filter((state) => state.header !== state.column && state.column !== null).length,
    tabBarsShown: [...new Set(seen.filter((state) => Number(state.header) > 0).map((state) => state.tabBar))],
  };
}`;
// The baselines of the title's first line and of the corner's button label, which the
// corner sets on one line (mb-tatf; docs/design-system.md, "View on GitHub"): a probe of no
// size before each one's first text rests on its first line's baseline. The title's text
// is a clamped box and the label a flex item, so each text is wrapped in an inline span
// with its probe for the read, and put back.
const CORNER_BASELINE = `(title, label) => {
  const first = (node) => {
    const walker = document.createTreeWalker(node, NodeFilter.SHOW_TEXT, {
      acceptNode: (text) => (text.textContent.trim() ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_SKIP),
    });
    const text = walker.nextNode();
    if (!text) return null;
    const probe = document.createElement("span");
    probe.style.cssText = "display:inline-block;width:0;height:0;vertical-align:baseline";
    const wrap = document.createElement("span");
    text.parentNode.insertBefore(wrap, text);
    wrap.append(probe, text);
    const y = probe.getBoundingClientRect().top;
    wrap.replaceWith(text);
    return Math.round(y * 100) / 100;
  };
  return { title: first(title), label: label ? first(label) : null };
}`;

// The View on GitHub button in the pull request header's corner (mb-4wqh;
// docs/design-system.md, "View on GitHub"), drawn by the SDK's `mountCounterpart` from what
// `GET /api/counterpart` answers, here a stand-in answer for the page's address, which
// tests/golden/cli-api-counterpart.tryscript.md pins. Read: where the button is in the page,
// its label's baseline and the title's first one (CORNER_BASELINE), its size, where the
// title's text and number end, the title's room for it, and the inks and fills of its parts
// and frame, beside the tokens each should resolve to in this theme, read from a probe
// painted with them. The reading column is the width the server gives a page by
// default, *maxChars* characters (`--doc-max-chars`), so a wide pane's column ends short of
// the button. The page stays mounted, in `window.__corner`, so the pointer can be put on the
// chevron; CORNER_HOVERED reads it there and CORNER_DONE unmounts it.
const CORNER = `async (width, theme, longTitle, maxChars) => {
  const recorded = window.__recorded ??= await (await fetch("/fixtures.json")).json();
  const page = window.__page ??= await import("/github/pull-page.js");
  const body = structuredClone(recorded.current.body);
  const holder = body.record?.same_as;
  if (holder !== undefined) {
    body.record = structuredClone(recorded[holder].body.record);
  }
  // A title of two lines and more, cut short at two.
  if (longTitle) {
    body.record.pull.title = "Decide every region's box at first paint, so nothing that arrives later moves the tab bar, a stack, a label, or a Refresh";
  }
  document.documentElement.dataset.theme = theme;
  document.documentElement.style.setProperty("--doc-max-chars", String(maxChars));
  const url = "https://github.com/octo/demo/pull/" + body.number;
  window.fetch = async (address) =>
    String(address).startsWith("/api/counterpart?")
      ? Response.json({
          page: "/pull/" + body.number,
          counterpart: { provider: "github", label: "View on GitHub", url },
          reason: null,
        })
      : new Response(null, { status: 304 });
  history.replaceState(null, "", "/pull/" + body.number);
  const pane = document.getElementById("preview-pane");
  pane.style.width = width + "px";
  const container = document.createElement("div");
  pane.replaceChildren(container);
  const mb = window.metabrowser;
  const handle = page.mountPullPage(
    container,
    { number: body.number, tab: "", reader: { initial: { etag: null, body }, fetchAfterMs: 60000 } },
    {
      perf: { measure: (_label, work) => work(), measureAsync: (_label, work) => work() },
      ensureAsset: async () => {},
      whenIdle: mb.whenIdle,
      ensureKindAssets: async () => {},
      loadChangedFilesTree: async () => {},
      getRegisteredView: () => null,
      decorateExternalLink: mb.decorateExternalLink,
      refChip: mb.refChip,
      refChipHtml: mb.refChipHtml,
      mergeRefs: mb.mergeRefs,
      mountRefMenus: mb.mountRefMenus,
      actorIdentity: mb.actorIdentity,
      titleNodes: mb.titleNodes,
      shortCommit: mb.shortCommit,
      countPartsNodes: mb.countPartsNodes,
      ...(${agesFrom})(document, () => ({ label: "now", className: "age" })),
      formatTimestamp: (seconds) => new Date(seconds * 1000).toISOString(),
      formatInteger: (value) => Number(value).toLocaleString("en-US"),
      navigation: { href: () => "/view/" },
      sourceKind: () => "filesystem",
      icons: { toggle: "" },
      mountCounterpart: mb.mountCounterpart,
    },
  );
  window.__corner = handle;
  await document.fonts.ready;
  const header = container.querySelector(".github-pull-header");
  const corner = header.querySelector(":scope > .view-header-end");
  for (let frame = 0; frame < 20 && !corner?.querySelector(".counterpart"); frame += 1) {
    await new Promise((resolve) => requestAnimationFrame(resolve));
  }
  await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
  const round = (value) => Math.round(value * 100) / 100;
  const box = (node) => node.getBoundingClientRect();
  const button = corner?.querySelector(":scope > .counterpart") ?? null;
  if (button === null) {
    return { button: null, corner: corner !== null, marked: corner?.hasAttribute("data-counterpart") ?? false };
  }
  // A token as the engine resolves it: a length as a probe's width, a color as its ink.
  const resolved = (property, value) => {
    const probe = document.createElement("span");
    probe.style.position = "absolute";
    probe.style[property] = value;
    container.append(probe);
    const out = property === "width" ? round(box(probe).width) : getComputedStyle(probe)[property];
    probe.remove();
    return out;
  };
  const paint = (node) => {
    const style = getComputedStyle(node);
    return { ink: style.color, fill: style.backgroundColor };
  };
  const title = header.querySelector(".github-pull-title");
  const group = button.querySelector(".counterpart-group");
  const open = button.querySelector('[data-web-view="open"]');
  const external = button.querySelector('[data-web-view="external"]');
  const more = button.querySelector(".counterpart-more");
  const frame = getComputedStyle(group);
  const at = box(container);
  const placed = box(group);
  const chevron = box(more);
  return {
    button: {
      top: round(placed.top - at.top),
      end: round(at.right - placed.right),
      start: round(placed.left),
      height: round(placed.height),
      width: round(placed.width),
    },
    afterTitle: corner.previousElementSibling === title,
    baselines: (${CORNER_BASELINE})(title.querySelector(".github-pull-title-text"), button.querySelector(".counterpart-label")),
    marked: corner.hasAttribute("data-counterpart"),
    hooks: {
      root: button.hasAttribute("data-view-on-github"),
      open: open?.getAttribute("href") ?? null,
      openTarget: open?.getAttribute("target") ?? null,
      external: external?.getAttribute("href") ?? null,
      externalTarget: external?.getAttribute("target") ?? null,
      externalRel: external?.getAttribute("rel") ?? null,
    },
    label: open.textContent,
    textEnd: round(box(title.querySelector(".github-pull-title-text")).right),
    numberEnd: round(box(title.querySelector(".github-pull-number")).right),
    titleRoom: round(Number.parseFloat(getComputedStyle(title).paddingInlineEnd)),
    column: round(box(header).width),
    page: round(at.width),
    paneScrolls: pane.scrollWidth > pane.clientWidth,
    tokens: {
      insetTop: resolved("width", "var(--view-header-corner-inset-top)"),
      insetEnd: resolved("width", "var(--view-header-corner-inset-end)"),
      height: resolved("width", "var(--view-header-corner-height)"),
      room: resolved("width", "var(--view-header-corner-room)"),
    },
    states: {
      open: paint(open),
      more: paint(more),
      frame: { border: frame.borderTopColor, ground: frame.backgroundColor, radius: frame.borderTopLeftRadius },
    },
    want: {
      muted: resolved("color", "var(--muted)"),
      text: resolved("color", "var(--text)"),
      hover: resolved("backgroundColor", "var(--hover-bg)"),
      border: resolved("borderTopColor", "var(--viz-border)"),
      surface: resolved("backgroundColor", "var(--viz-surface)"),
      radius: resolved("borderTopLeftRadius", "var(--radius-pill)"),
    },
    url,
    chevron: { x: chevron.left + chevron.width / 2, y: chevron.top + chevron.height / 2 },
  };
}`;
// The chevron's ink and fill once every transition on it has ended.
const CORNER_HOVERED = `(async () => {
  const more = document.querySelector("#preview-pane .github-pull-header .counterpart-more");
  await Promise.all(more.getAnimations().map((motion) => motion.finished));
  await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
  const style = getComputedStyle(more);
  return { ink: style.color, fill: style.backgroundColor, hovered: more.matches(":hover") };
})()`;
const CORNER_DONE = `(() => {
  window.__corner?.dispose();
  window.__corner = null;
  delete document.documentElement.dataset.theme;
  document.documentElement.style.removeProperty("--doc-max-chars");
  return true;
})()`;

// Pulls rows built as pulls-panel.js#buildRow builds them, whose order
// github-pulls-panel-session.js pins (mb-pw8t, mb-rb3n): the row's link, its run, one flow of
// the state icon in the row's one slot, the title, a stack member's place after a dot, the
// number after a dot, and the author after a dot, every line of it in the text column; then
// its last line, the lines and the chevron in the text column, here with no lines yet, and the
// age at the row's end. Each row is a member, a level in under its stack's row.
// The icon and the title's first box are read, from the row's top, before and after each
// row's place arrives: the place is after the title, so nothing before it moves, and the
// number and the toggle after it move along the run, to a next line where it takes one, which
// the row grows by (`grew`), and the item by that alone (`itemGrew`).
const PULLS_ROWS = `async (rows, width) => {
  const mb = window.metabrowser;
  const page = window.__page ??= await import("/github/pull-page.js");
  const state = window.__state ??= await import("/github/pull-state.js");
  const h = (tag, attributes = {}, children = []) => {
    const node = document.createElement(tag);
    for (const [key, value] of Object.entries(attributes)) node.setAttribute(key, value);
    node.append(...children);
    return node;
  };
  // The panel's own container, as pulls-panel.js#mountPullsPanel marks it. The avatar's size
  // and gap are the shell's, --actor-avatar-size and --actor-identity-gap, on its root.
  const nav = h("div", { class: "github-pulls" });
  nav.style.width = width + "px";
  const list = h("ul", { class: "github-pulls-list", role: "tree" });
  nav.append(list);
  document.getElementById("preview-pane").replaceChildren(nav);
  // The run's dot, as pulls-panel.js#separator draws it: kept to the part before it, and a
  // break after it.
  const separator = () =>
    h("span", { class: "github-pulls-sep", "aria-hidden": "true" }, [
      "\u00a0",
      h("span", { class: "github-pull-stack-dot" }, ["·"]),
      " ",
    ]);
  const built = rows.map((row) => {
    const identity = page.authorLabel(mb, row.author, null, "github-pulls-author", {
      placeholder: false,
    });
    if (row.avatar) {
      // The box authorLabel draws for an avatar, with its image, without a request.
      identity.prepend(
        h("span", { class: "actor-avatar", "aria-hidden": "true" }, [
          h("img", { class: "actor-avatar-image", alt: "", width: "18", height: "18" }),
        ]),
      );
    }
    const icon = state.pullStateIcon("open");
    const title = h("span", { class: "github-pulls-title" }, mb.titleNodes(row.title));
    const place = h("span", { class: "github-pulls-place", role: "img", hidden: "" });
    const number = h("span", { class: "github-pulls-number", "aria-hidden": "true" }, ["#" + row.number]);
    // The registry's chevron is the shell's .toggle-chevron, which sizes it; its drawing is
    // not read here.
    const chevron = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    chevron.setAttribute("class", "toggle-chevron");
    chevron.setAttribute("viewBox", "0 0 24 24");
    const toggle = h("span", { class: "github-pulls-toggle", "aria-hidden": "true" }, [chevron]);
    const change = h("span", { class: "github-pulls-change disclosure-toggle collapsed", "aria-hidden": "true" }, [
      h("span", { class: "github-pulls-change-line" }),
      toggle,
      h("span", { class: "github-pulls-change-words", hidden: "" }),
    ]);
    const age = h("span", { class: "github-pulls-age", "aria-hidden": "true" }, ["12mo"]);
    const tail = h("span", { class: "github-pulls-tail" }, [change, age]);
    const by = h("span", { class: "github-pulls-by", "aria-hidden": "true" }, [identity]);
    const heading = h("span", { class: "github-pulls-heading" }, [
      icon,
      title,
      place,
      separator(),
      number,
      separator(),
      by,
    ]);
    // As pulls-panel.js#buildRow draws a pull request's item, its run and its last line in
    // its link (mb-1z7j, mb-pw8t, mb-rb3n).
    const anchor = h("a", { class: "github-pulls-row", href: "#", role: "treeitem", "aria-expanded": "false" }, [
      heading,
      tail,
      h("span", { class: "sr-only" }, ["#" + row.number + " · " + row.author + " · 12mo"]),
    ]);
    const item = h("li", { class: "github-pulls-item", role: "none", "data-level": "2" }, [
      h("div", { class: "github-pulls-entry" }, [anchor]),
    ]);
    list.append(item);
    return { item, anchor, heading, toggle, change, icon, by, place, number, title, tail, age, row };
  });
  await document.fonts.ready;
  const frames = () => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
  await frames();
  const round = (value) => Math.round(value * 100) / 100;
  // What comes before the place, read from its row's top: the icon, and the title's first box.
  const firstBox = (node) => node.getClientRects()[0] ?? node.getBoundingClientRect();
  const read = () =>
    built.map(({ item, icon, title }) => {
      const top = item.getBoundingClientRect().top;
      return [icon, title].map((node) => {
        const r = firstBox(node);
        return [r.left, r.top - top, r.width, r.height].map(round);
      });
    });
  const before = read();
  const heights = built.map(({ anchor }) => anchor.getBoundingClientRect().height);
  const itemHeights = built.map(({ item }) => item.getBoundingClientRect().height);
  for (const { place, row } of built) {
    place.hidden = false;
    // As pulls-panel.js#paintPlace draws it: the stack menu's dot, after a no-break space,
    // then the position; another stack is the Layers glyph before its number, written here
    // as "#N".
    place.append(
      "\u00a0",
      h("span", { class: "github-pull-stack-dot", "aria-hidden": "true" }, ["·"]),
      " ",
      h(
        "span",
        { class: "github-pull-stack-position" },
        row.stack.split(" · ").flatMap((part, at) => {
          const named = /^#([0-9]+) (.+)$/.exec(part);
          return [
            ...(at === 0 ? [] : [" · "]),
            ...(named === null
              ? [part]
              : [
                  h("span", { class: "github-pull-stack-other", "aria-hidden": "true" }),
                  named[1] + " " + named[2],
                ]),
          ];
        }),
      ),
    );
  }
  await frames();
  const after = read();
  return built.map(({ item, anchor, heading, toggle, change, icon, by, place, number, title, tail, age, row }, at) => {
    const moved = ["icon", "title"].flatMap((name, index) =>
      JSON.stringify(before[at][index]) === JSON.stringify(after[at][index])
        ? []
        : [[name, before[at][index], after[at][index]]],
    );
    const p = place.querySelector(".github-pull-stack-position").getBoundingClientRect();
    const dot = place.querySelector(".github-pull-stack-dot").getBoundingClientRect();
    const n = number.getBoundingClientRect();
    const box = anchor.getBoundingClientRect();
    const end = box.right - parseFloat(getComputedStyle(anchor).paddingRight) + 0.5;
    const hd = heading.getBoundingClientRect();
    const runStyle = getComputedStyle(heading);
    const lh = parseFloat(runStyle.lineHeight);
    const column = hd.left + parseFloat(runStyle.paddingInlineStart);
    const style = getComputedStyle(anchor);
    const inset = box.left + parseFloat(style.borderLeftWidth) + parseFloat(style.paddingLeft);
    const i = icon.getBoundingClientRect();
    const t = toggle.getBoundingClientRect();
    const b = by.getBoundingClientRect();
    const a = age.getBoundingClientRect();
    const name = by.querySelector(".github-pulls-author").getBoundingClientRect();
    // The line of the run a box is on, by its middle.
    const lineOf = (r) => Math.floor((r.top + r.height / 2 - hd.top) / lh);
    // The run's lines, from its parts' fragments: a line's start is its first fragment's.
    const lines = [];
    for (const piece of [title, place, number, by]) {
      for (const r of piece.getClientRects()) {
        if (r.width === 0) continue;
        const k = lineOf(r);
        lines[k] = lines[k] ? Math.min(lines[k], r.left) : r.left;
      }
    }
    const starts = Array.from(lines, (left) => (left === undefined ? null : round(left - column)));
    const titleBoxes = [...title.getClientRects()].filter((r) => r.width > 0);
    const titleEnd = titleBoxes.at(-1) ?? null;
    return {
      number: row.number,
      moved,
      // The place follows the title: its dot after the title's last box, on its line or the
      // next, the position after the dot on its line or, a line breaking after a dot as after
      // a word, first on the next; and the number follows the place.
      placeAfter:
        p.width > 0 &&
        titleEnd !== null &&
        (lineOf(dot) > lineOf(titleEnd) || dot.left >= titleEnd.right - 0.5) &&
        (lineOf(p) === lineOf(dot) ? p.left >= dot.right - 0.5 : lineOf(p) === lineOf(dot) + 1) &&
        (lineOf(n) > lineOf(p) || n.left >= p.right - 0.5),
      placeLines: [titleEnd === null ? null : lineOf(titleEnd), lineOf(dot), lineOf(p), lineOf(n)],
      // Where each line of the run starts, from the text column.
      starts,
      columnFrom: round(column - inset),
      // The number shows whole, inside the row.
      whole: number.scrollWidth <= Math.ceil(n.width) && n.right <= end,
      // Nothing of the row ends past its padding box, and the pane does not scroll sideways.
      inside:
        [age, number, tail].every((node) => node.getBoundingClientRect().right <= end) &&
        hd.right <= end &&
        nav.scrollWidth <= nav.clientWidth,
      cut: p.right > hd.right + 0.5,
      grew: round(box.height - heights[at]),
      itemGrew: round(item.getBoundingClientRect().height - itemHeights[at]),
      height: round(box.height),
      itemHeight: round(item.getBoundingClientRect().height),
      // The run is as tall as its lines, and ends with the author on its last line; the last
      // line follows it, the chevron on it and the age at its end, past the chevron, and the
      // closed item is its link.
      headingHeight: round(hd.height),
      lineHeight: round(lh),
      drawnLines: lines.length,
      endsWithAuthor: heading.lastElementChild === by && lineOf(b) === lines.length - 1,
      lastLine:
        Math.abs(tail.getBoundingClientRect().top - hd.bottom) < 0.5 &&
        t.top >= hd.bottom - 0.5 &&
        a.top >= hd.bottom - 0.5 &&
        Math.abs(a.right - (box.right - parseFloat(getComputedStyle(anchor).paddingRight))) < 0.5 &&
        t.right <= a.left + 0.5 &&
        Math.abs(item.getBoundingClientRect().height - box.height) < 0.5,
      tailFrom: round(change.getBoundingClientRect().left - inset),
      textColumn: round(parseFloat(style.getPropertyValue("--tree-icon-slot")) + parseFloat(style.columnGap)),
      // The icon is the run's first line's start, one line tall, on the row's inset (mb-3vil).
      iconOnFirst: i.height > 0 && Math.abs(i.top - hd.top) < 0.5 && Math.abs(i.height - lh) < 0.5,
      iconFrom: round(i.left - inset),
      // The author follows the number, after its dot, and its name, one line, cut short only
      // where it is wider than a line and never broken after a hyphen, ends the run.
      byAfter: lineOf(b) > lineOf(n) || b.left >= n.right - 0.5,
      authorEnds:
        name.left < name.right &&
        name.right <= hd.right + 0.5 &&
        name.height < 1.5 * lh &&
        lineOf(name) === lines.length - 1,
      authorAt: { left: round(name.left), right: round(name.right), runRight: round(hd.right), line: lineOf(name), top: round(name.top - hd.top), height: round(name.height) },
      title: Math.round(titleBoxes.reduce((sum, r) => sum + r.width, 0) * 10) / 10,
    };
  });
}`;
// A pull request's number in the shell's two surfaces that show one, Quick Search's result
// and the ref selector on a pull request's head, built as search-palette.js#appendPullResult
// and source-ref-selector.js#paint build them, over the shell's own stylesheet: their
// computed weights, and a stack's position's (mb-vrvs). The GitHub plugin's three surfaces
// are read where they are drawn, in github-pulls-stacks-chrome.mjs.
const NUMBERS = `(() => {
  const h = (tag, attributes = {}, children = []) => {
    const node = document.createElement(tag);
    for (const [key, value] of Object.entries(attributes)) node.setAttribute(key, value);
    node.append(...children);
    return node;
  };
  const palette = h("span", { class: "search-palette-pull-number" }, ["#455"]);
  const selector = h("span", { class: "source-ref-selector-pull-number" }, ["#455"]);
  const position = h("span", { class: "github-pull-stack-position" }, ["1/6"]);
  document.getElementById("preview-pane").replaceChildren(
    h("div", { class: "search-palette-option search-palette-option-pull" }, [
      h("span", { class: "search-palette-option-text" }, [
        h("span", { class: "search-palette-description" }, [palette, " · Open"]),
      ]),
    ]),
    h("button", { class: "chip-menu-trigger source-ref-selector-toggle" }, [
      h("span", { class: "source-ref-selector-label" }, ["Pull request: ", selector]),
    ]),
    position,
  );
  const weight = (node) => getComputedStyle(node).fontWeight;
  return { palette: weight(palette), selector: weight(selector), position: weight(position) };
})()`;
const PULLS = [
  {
    number: 370,
    title: "perf: decide every region's box at first paint",
    author: "jlevy",
    avatar: true,
    stack: "2/3",
  },
  {
    number: 12345,
    title: "A five-digit pull request",
    author: "a-thirty-nine-character-github-login-x",
    avatar: true,
    stack: "3/3 · #900 1/2",
  },
  {
    number: 7,
    title: "Short",
    author: "octo",
    avatar: false,
    stack: "1/2",
  },
  // Two stacks and three: wider than a narrow pane's muted line, the place is cut short.
  {
    number: 4242,
    title: "Two stacks, two digits each",
    author: "octo",
    avatar: true,
    stack: "12/23 · #901 10/14",
  },
  {
    number: 4243,
    title: "Three stacks",
    author: "octo",
    avatar: false,
    stack: "3/3 · #900 1/2 · #902 4/7",
  },
];
const PULLS_WIDTHS = [420, 360, 300, 240, 180];
// The file header of a run's log: renderBadges and its RUN_STATUS_SIZERS are the view
// header's own (view-header.js), read from the served file and made here with the two
// helpers they use, and flagRunEndedBadge is app.js's own, read from the served file. The
// header is the one renderFile draws around them: the path, the badges, and the size. A
// live run ends, and a running one turns live, as app.js
// changes them in place (flagRunEndedBadge, and _mirrorActiveFromFsEntry's two lines), and
// every box of the header is read before and after.
const RUN_BADGE = `async (live, width) => {
  // Read with XMLHttpRequest: the header's measurements stand in for window.fetch.
  const served = (file) =>
    new Promise((resolve, reject) => {
      const request = new XMLHttpRequest();
      request.open("GET", "/static/" + file);
      request.onload = () => resolve(request.responseText);
      request.onerror = reject;
      request.send();
    });
  const source = await served("app.js");
  const take = (start, end) => {
    const at = source.indexOf(start);
    if (at < 0) {
      throw new Error("app.js has no " + start);
    }
    return source.slice(at, source.indexOf(end, at) + end.length);
  };
  const flagRunEndedBadge = new Function(
    take("function flagRunEndedBadge() {", "\\n}\\n") + "\\nreturn flagRunEndedBadge;",
  )();
  if (!window.MetabrowserViewHeader) {
    new Function(await served("view-header.js"))();
  }
  const esc = (text) => String(text).replace(/[&<>"]/g, (c) => "&#" + c.charCodeAt(0) + ";");
  const activeFiles = new Map(live ? [["logs/session.jsonl", {}]] : []);
  const notDrawnHere = () => {
    throw new Error("this header draws only its badges and a size");
  };
  const builders = window.MetabrowserViewHeader.create({
    esc,
    servedRoot: notDrawnHere,
    pathBaseName: notDrawnHere,
    ownedControlAttr: notDrawnHere,
    mirrorHeading: notDrawnHere,
    getFileIcon: notDrawnHere,
    getLogicalName: notDrawnHere,
    sizeHtml: notDrawnHere,
    countHtml: notDrawnHere,
    formatAge: notDrawnHere,
    activeFiles,
  });
  const app = { ...builders, flagRunEndedBadge };
  const pane = document.getElementById("preview-pane");
  pane.style.width = width + "px";
  // A file's view header, through the view header's own builder (renderFileHeader): the
  // badges lead its metadata line.
  pane.innerHTML = app.viewHeaderHtml({
    eyebrow: "",
    iconHtml: "",
    title: "session.jsonl",
    end: "",
    line:
      app.renderBadges({ type: "jsonl", kind: "agent-log", path: "logs/session.jsonl", summary: { adapter: "claude", is_done: false } }) +
      app.viewHeaderItemsHtml(['<span class="size file-header-size">1.2 MB</span>']),
  });
  await document.fonts.ready;
  const frames = () => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
  await frames();
  const header = pane.querySelector(".file-header");
  const read = () =>
    [header, ...header.querySelectorAll("*")].map((node) => {
      const r = node.getBoundingClientRect();
      return [node.className, ...[r.left, r.top, r.width, r.height].map((v) => Math.round(v * 100) / 100)];
    });
  const before = read();
  const badge = pane.querySelector(".badge-live, .badge-running");
  const labelBefore = badge.textContent;
  if (live) {
    app.flagRunEndedBadge();
  } else {
    // _mirrorActiveFromFsEntry, as a running log turns live.
    const running = document.querySelector(".file-header-badge.badge-running");
    running.className = "file-header-badge badge-live";
    running.textContent = "Live";
  }
  await frames();
  const after = read();
  const moved = before.flatMap((box, at) =>
    JSON.stringify(box.slice(1)) === JSON.stringify(after[at].slice(1)) ? [] : [[box, after[at]]],
  );
  return { from: labelBefore, to: badge.textContent, width: Math.round(badge.getBoundingClientRect().width * 10) / 10, moved };
}`;
// The record whose status row draws an offer: to browse the checkout at the head. Code
// served on the pull request's head follows it, so no record offers a switch to it.
const OFFER_RECORDS = [["on_head", { checkoutAtHead: true }]];
// The same records by the labels the header parts give them.
const OFFERED = new Set(
  OFFER_RECORDS.map(
    ([name, change]) =>
      `${name}${Object.keys(change).length ? ` ${Object.keys(change).join(" ")}` : ""}`,
  ),
);
const TABS = ["", "files", "checks"];
const WIDTHS = [980, 760, 560, 420, 360, 320];
// Each part's header widths; together they are WIDTHS. The offers are counted in the part
// that lays out the widest pane.
const HEADER_PARTS = {
  "header-wide": [980, 760],
  "header-middle": [560, 420],
  "header-narrow": [360, 320],
};
// The label part's chips: a pale label with a description, a dark one, a very pale one
// whose border shows, white in upper case, two more of github.com's colors, one GitHub gave
// no color, and one whose color is not six hex digits; the last two are drawn neutral.
// github.com's own stylesheet computed each of the six colors in both themes
// (tests/fixtures/github-label-colors.json), and each chip is held to what it computed
// and to the formula, worked out below apart from any stylesheet.
const LABEL_CASES = [
  { name: "pale", color: "a2eeef", description: "New feature or request" },
  { name: "dark", color: "d73a4a", description: null },
  { name: "very pale", color: "f4f6f8", description: null },
  { name: "white", color: "FFFFFF", description: null },
  { name: "indigo", color: "2700af", description: null },
  { name: "gray", color: "ededed", description: null },
  { name: "no color", color: null, description: "GitHub gave it none" },
  { name: "not a color", color: "#d73a4", description: null },
];
// An hsl() color as sRGB channels, 0 to 255, its lightness clamped as CSS clamps it.
const hslChannels = (hue, saturation, lightness) => {
  const s = saturation / 100;
  const l = Math.min(100, Math.max(0, lightness)) / 100;
  const k = (n) => (n + hue / 30) % 12;
  const a = s * Math.min(l, 1 - l);
  const f = (n) => l - a * Math.max(-1, Math.min(k(n) - 3, 9 - k(n), 1));
  return [f(0), f(8), f(4)].map((value) => value * 255);
};
// GitHub's label formula (github/styles.css), as [red, green, blue, alpha] for the ground,
// the text, and the border of a label of *hex* whose properties are *hsl*, in *theme*.
const labelFormula = (hex, [hue, saturation, lightness], theme) => {
  const [r, g, b] = [0, 2, 4].map((at) => Number.parseInt(hex.slice(at, at + 2), 16));
  const perceived = (r * 0.2126 + g * 0.7152 + b * 0.0722) / 255;
  if (theme === "light") {
    return {
      background: [r, g, b, 1],
      text: perceived > 0.453 ? [0, 0, 0, 1] : [255, 255, 255, 1],
      border: [
        ...hslChannels(hue, saturation, lightness - 25),
        Math.max(0, Math.min((perceived - 0.96) * 100, 1)),
      ],
    };
  }
  const lighten = perceived < 0.6 ? (0.6 - perceived) * 100 : 0;
  const text = hslChannels(hue, saturation, lightness + lighten);
  return { background: [r, g, b, 0.18], text: [...text, 1], border: [...text, 0.3] };
};
const channels = (value) => {
  const found = /^rgba?\(([^)]+)\)$/.exec(value);
  const parts = found ? found[1].split(",").map(Number) : [];
  return parts.length === 3 ? [...parts, 1] : parts.length === 4 ? parts : null;
};
// A computed color within a unit of each channel the formula gives, and its alpha within
// the half of a hundredth Chrome rounds an alpha to.
const nearColor = (value, wanted) =>
  channels(value)?.every(
    (channel, at) => Math.abs(channel - wanted[at]) <= (at === 3 ? 0.005 : 1),
  ) ?? false;
const PARTS = [
  "launch",
  ...Object.keys(HEADER_PARTS),
  "offers",
  "pulls",
  "badges",
  "labels",
  "summary-wait",
  "cold-landing",
  "corner",
];
const PART = (() => {
  const at = process.argv.indexOf("--part");
  const name = at < 0 ? "all" : process.argv[at + 1];
  if (name !== "all" && !PARTS.includes(name)) {
    throw new Error(`--part takes one of ${PARTS.join(", ")}, not ${name}`);
  }
  return name;
})();
const runs = (part) => PART === "all" || PART === part;
// How long each step of the part took, on stderr, so a CI log shows where its time went.
const began = performance.now();
let lapAt = began;
const lap = (step) => {
  const now = performance.now();
  process.stderr.write(
    `${PART}: ${step} in ${Math.round(now - lapAt)} ms (${Math.round(now - began)} ms in all)\n`,
  );
  lapAt = now;
};

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
  const server = await serve();
  try {
    const browser = await launchChrome(bin, { profiles });
    lap("Chrome started");
    try {
      await browser.send("Page.enable");
      await browser.send("Page.navigate", { url: `http://127.0.0.1:${server.address().port}/` });
      await browser.waitFor(
        `document.readyState === "complete" && Boolean(window.metabrowser?.refChip)`,
      );
      lap("the page loaded");
      if (runs("launch")) {
        // Every face the page declares, loaded before any part lays text out in it.
        const faces = await browser.evaluate(`(async () => {
          await Promise.all([...document.fonts].map((face) => face.load().catch(() => null)));
          await document.fonts.ready;
          return [...document.fonts].map((face) => face.status);
        })()`);
        check(
          "the page, its SDK, and every face it declares load",
          faces.length > 0 && faces.every((status) => status === "loaded" || status === "error"),
          JSON.stringify(faces),
        );
        lap(`${faces.length} faces loaded`);
      }
      const offersDrawn = new Set();
      const summaryWaits = [];
      const revisits = [];
      const briefs = [];
      const widths = PART === "all" ? WIDTHS : (HEADER_PARTS[PART] ?? []);
      for (const width of widths) {
        const seen = {};
        for (const [name, change] of RECORDS) {
          const label = `${name}${Object.keys(change).length ? ` ${Object.keys(change).join(" ")}` : ""}`;
          for (const tab of TABS) {
            // The row of ages is the same on every tab, and its stack chip arrives on each:
            // one stack, and two for the records with an avatar, the longest rows (mb-646g,
            // mb-dwha). The Diff
            // summary is the header's last row on every tab, so it is measured on each.
            const measured = {
              ...change,
              stackChip: change.avatar ? 2 : 1,
              summary: true,
            };
            const shape = await browser.evaluate(
              `(${MEASURE})(${JSON.stringify(name)}, ${JSON.stringify(measured)}, ${JSON.stringify(tab)}, ${width})`,
            );
            const where = `${width} px, ${label} ${tab || "conversation"}`;
            check(`${where}: the Diff summary is measured`, shape.summaryMoves !== null);
            if (shape.mergeShown !== null) {
              check(
                `${where}: the merge's chips and arrow show whole on their line`,
                shape.mergeShown >= 0.99,
                String(shape.mergeShown),
              );
            }
            if (shape.summaryMoves !== null) {
              const moves = shape.summaryMoves;
              check(
                `${where}: the Diff summary arriving moves nothing in the header`,
                moves.moved === null,
                JSON.stringify(moves.moved),
              );
              check(
                `${where}: the Diff summary keeps its row's height, on one line`,
                Math.abs(moves.rowBefore - moves.rowAfter) <= 0.5 &&
                  moves.toggleHeight !== null &&
                  moves.toggleHeight <= moves.rowBefore + 0.5,
                JSON.stringify(moves),
              );
              check(
                `${where}: the Diff summary starts on the header's content edge`,
                Math.abs(moves.left) <= 0.5,
                JSON.stringify(moves),
              );
              check(
                `${where}: the Diff summary's tooltip is its whole words only while cut short`,
                moves.cut
                  ? moves.tip === "2 A, 3 D, 30 M, 12 R, 12 C · +1,234 −3,423"
                  : moves.tip === null,
                JSON.stringify({ cut: moves.cut, tip: moves.tip }),
              );
              if (width === 320) {
                check(
                  `${where}: at the narrowest width the breakdown is cut short`,
                  moves.cut,
                  JSON.stringify(moves),
                );
              }
              if (moves.indent !== undefined) {
                check(
                  `${where}: the Diff summary's tree steps in from its header one level at a time`,
                  offStep(moves.indent).length === 0 &&
                    new Set(moves.indent.rows.map((row) => row.level)).size === 5,
                  JSON.stringify(moves.indent),
                );
              }
            }
            if (shape.chipMoves !== null) {
              const chip = shape.chipMoves;
              check(
                `${where}: a late stack chip moves nothing in the header but the ages' end, and every row keeps its height`,
                chip.moved === null,
                JSON.stringify(chip.moved),
              );
              // The chip ends on the content column's edge, which is the end of the title's
              // number less the room the title leaves the corner's button: under the number
              // where the title leaves it none (mb-dwha, mb-ablv).
              check(
                `${where}: the stack chip ends on the content column's edge, the title's room past the title's number`,
                Math.abs(chip.ends.content) <= 0.5 &&
                  Math.abs(chip.ends.number - chip.titleRoom) <= 0.5,
                JSON.stringify({ ends: chip.ends, titleRoom: chip.titleRoom }),
              );
              check(
                `${where}: a late stack chip shows whole`,
                chip.chipShown >= 0.99,
                String(chip.chipShown),
              );
              // On the row of ages, at its end (mb-646g, mb-dwha).
              check(
                `${where}: the stack chip ends the row of ages`,
                chip.onAgesRow,
                JSON.stringify(chip),
              );
              check(
                `${where}: the stack chip and the ages do not overlap`,
                chip.overlap <= 0.5,
                String(chip.overlap),
              );
              // The ages and Browse code give way before a chip does: its position is cut
              // short only where they have no width left, as two stacks' named chips at
              // 320 px are.
              check(
                `${where}: a chip's position is cut short only once the ages and Browse code have no width left`,
                !chip.positionCut || !chip.textLeft,
                JSON.stringify(chip),
              );
              check(
                `${where}: the stack menu's heading starts on its rows' inset`,
                shape.chipMoves.headingInset !== null &&
                  Math.abs(shape.chipMoves.headingInset) <= 0.5,
                String(shape.chipMoves.headingInset),
              );
              check(
                `${where}: the stack menu's heading names the menu, once`,
                shape.chipMoves.headingNamesMenu === true,
                String(shape.chipMoves.headingNamesMenu),
              );
            }
            seen[`${label} ${tab || "conversation"}`] = { ...shape, label };
            if (shape.offers > 0) {
              offersDrawn.add(label);
            }
            // The status line is there exactly while it has something to say, here an offer,
            // each drawn where it is seen; a rate limit's hold is said in the note's place and
            // adds no line (A3, A4 of review A on #506).
            check(
              `${where}: the status line is there exactly while it draws an offer`,
              shape.statusShown === OFFERED.has(label) &&
                shape.offers === (OFFERED.has(label) ? 1 : 0),
              JSON.stringify({ statusShown: shape.statusShown, offers: shape.offers }),
            );
            const lead = shape.lead;
            if (change.lastRefresh?.outcome === "rate_limited") {
              // At every width: where it cannot be whole it is cut short, with its text as a
              // tooltip, and never leaves the line as an age does; it is said in the page's
              // own time form, a time of day today and a short date and time otherwise (B3 of
              // review B on #506). Leaving the line, the page's whole timestamp put it out of
              // view from 640 px down.
              check(
                `${where}: a rate limit's hold is said in the note's place, in the failure's ink, in view at every width`,
                lead !== null &&
                  /^GitHub rate limit reached\. Next attempt after /.test(lead.said) &&
                  !/:\d\d:\d\d/.test(lead.said) &&
                  lead.held &&
                  lead.inView &&
                  lead.textWidth >= lead.holdFloor - 0.5,
                JSON.stringify(lead),
              );
            }
            if (lead?.sentence && !lead.held) {
              // Beside the sentence the note is whole or out of view, and while it is in view
              // the login and the sentence keep their natural widths (A2 of review A on #506).
              check(
                `${where}: the note beside the sentence is whole or out of view, the login and the sentence whole while it shows`,
                !lead.inView ||
                  (!lead.cut &&
                    (lead.login === null || lead.login.width >= lead.login.natural - 0.05) &&
                    lead.action.width >= lead.action.natural - 0.05),
                JSON.stringify(lead),
              );
              if (width >= 760 && !change.longNames) {
                check(
                  `${where}: in a wide pane the note shows whole`,
                  lead.inView && !lead.cut,
                  JSON.stringify(lead),
                );
              }
            }
            if (shape.agesRow !== null) {
              // The ages give way first, cut short at their end, and the links after them stay
              // whole while any of the ages shows (B4 of review B on #506).
              check(
                `${where}: the ages give way before Browse code, which shows whole while any age does`,
                shape.agesRow.linksShown >= 0.99 || shape.agesRow.agesWidth < 1,
                JSON.stringify(shape.agesRow),
              );
              // Two stacks' named chips, 156.31 px, leave Browse code whole down to 560 px; one
              // stack's chip, 54.75 px, down to 420 px, as no chip does (mb-646g).
              if (width >= (shape.chipMoves?.chips === 2 ? 560 : 420)) {
                check(
                  `${where}: Browse code shows whole`,
                  shape.agesRow.linksShown >= 0.99,
                  JSON.stringify(shape.agesRow),
                );
              }
            }
            if (lead !== null) {
              check(
                `${where}: no dot shows beside a note of no width`,
                !lead.dotInView || (lead.inView && lead.textWidth >= 1),
                JSON.stringify(lead),
              );
              check(
                `${where}: a note cut short carries its whole text as its tooltip, and only then`,
                lead.cut ? lead.tip === lead.said : lead.tip === null,
                JSON.stringify(lead),
              );
            }
            if (shape.badgeOffset !== null) {
              check(
                `${where}: the state badge is centred on its row`,
                Math.abs(shape.badgeOffset) <= 1,
                String(shape.badgeOffset),
              );
            }
            if (shape.edges !== null) {
              const { iconLeft, textAfterIcon, gap, numberRight, numberOverRow } = shape.edges;
              check(
                `${where}: the title's icon starts on the header's left edge, its text just after it`,
                Math.abs(iconLeft) <= 0.5 && Math.abs(textAfterIcon - gap) <= 1,
                JSON.stringify(shape.edges),
              );
              check(
                `${where}: the title's number ends on the header's right edge, over the end of the row of ages, less the room it leaves the corner's button`,
                Math.abs(numberRight) <= 0.5 &&
                  numberOverRow !== null &&
                  Math.abs(numberOverRow) <= 0.5,
                JSON.stringify(shape.edges),
              );
            }
            // The stack's strut holds the row of ages at a chip's height, so a chip arriving
            // changes no row's height; the author's row is its lead, a line (mb-646g).
            check(
              `${where}: the row of ages is as tall as the stack strut, and the author's row one line`,
              shape.strut !== null &&
                Math.abs(shape.agesRowHeight - shape.strut) <= 0.5 &&
                shape.metaLead !== null &&
                Math.abs(shape.meta - shape.metaLead) <= 0.5,
              JSON.stringify({
                agesRow: shape.agesRowHeight,
                strut: shape.strut,
                meta: shape.meta,
                lead: shape.metaLead,
              }),
            );
            check(
              `${where}: nothing ends past the header, and the pane does not scroll sideways`,
              shape.pastHeader <= 0.5 && !shape.paneScrolls,
              JSON.stringify({
                culprit: shape.culprit,
                pastHeader: shape.pastHeader,
                paneScrolls: shape.paneScrolls,
              }),
            );
            // The status line is one of the header's metadata lines (mb-2u08), there only
            // while it has something to say: a line tall, as the author's row above it is, and
            // every row one gap under the row before it. As a bordered .btn, the page's
            // Refresh made its line 26 px against the row of ages' 18, and an empty labels row
            // stood between them. The row of ages is a chip's height since the stack's slot
            // came to it (mb-646g), so the line the status line matches is the author's.
            const line = (row) => shape.lines.find((each) => each.row === row);
            const author = line("meta");
            const statusLine = line("status");
            const tall = (each) => Math.round((each.bottom - each.top) * 100) / 100;
            check(
              `${where}: the status line, when there, is as tall as the author's row, a line`,
              author !== undefined &&
                (statusLine === undefined || Math.abs(tall(statusLine) - tall(author)) <= 0.5),
              JSON.stringify(shape.lines),
            );
            check(
              `${where}: the note's age ticking from "just now" to "59 min ago" widens its slot not at all`,
              shape.ageWidens === null || shape.ageWidens <= 0.5,
              JSON.stringify({ ageWidens: shape.ageWidens }),
            );
            // The page has no Refresh of its own (mb-ablv). Where the status line offers Retry
            // or Fetch, the remedy is its first offer, whole, inside the content edge, and no
            // taller than the line.
            check(
              `${where}: the page has no Refresh of its own`,
              shape.pageRefresh === false,
              String(shape.pageRefresh),
            );
            check(
              `${where}: the status line's remedy, where offered, is its first offer, whole, and a line tall`,
              shape.remedy === null ||
                (shape.remedy.first &&
                  shape.remedy.whole &&
                  shape.remedy.rightEdge <= 0.5 &&
                  statusLine !== undefined &&
                  Math.abs(shape.remedy.statusHeight - tall(statusLine)) <= 0.5 &&
                  shape.remedy.height <= tall(statusLine) + 0.5),
              JSON.stringify({ remedy: shape.remedy, lines: shape.lines }),
            );
            // The title has the shared gap; both sides of the size line get an extra
            // half-gap. The bottom padding gives that space back.
            const gapBetween = (before, after) =>
              before.row === "title"
                ? shape.titleGap
                : shape.rowGap * (before.row === "size" || after.row === "size" ? 1.5 : 1);
            check(
              `${where}: the title, the size line and surrounding rows keep their gaps`,
              shape.titleGap > shape.rowGap &&
                shape.lines[0]?.row === "title" &&
                shape.lines.every(
                  (each, at) =>
                    at === 0 ||
                    Math.abs(
                      each.top - shape.lines[at - 1].bottom - gapBetween(shape.lines[at - 1], each),
                    ) <= 0.5,
                ),
              JSON.stringify({
                rowGap: shape.rowGap,
                titleGap: shape.titleGap,
                lines: shape.lines,
              }),
            );
            check(
              `${where}: the state and ages come first, then the author and the branches`,
              shape.lines
                .slice(0, 4)
                .map((row) => row.row)
                .join(" ") === "title opened meta branches",
              JSON.stringify(shape.lines),
            );
            check(
              `${where}: the padding below the Diff summary gives the space around the size line back`,
              Math.abs(shape.bottomPadding - (shape.contentPadding - shape.rowGap)) <= 0.5,
              JSON.stringify([shape.bottomPadding, shape.contentPadding, shape.rowGap]),
            );
            if (shape.recordLabels === 0) {
              const branchesAt = shape.lines.findIndex((each) => each.row === "branches");
              const branches = shape.lines[branchesAt];
              const next = shape.lines[branchesAt + 1];
              check(
                `${where}: a pull request with no labels has no labels row or gap after the branches`,
                line("labels") === undefined &&
                  branches !== undefined &&
                  next !== undefined &&
                  Math.abs(next.top - branches.bottom - gapBetween(branches, next)) <= 0.5,
                JSON.stringify(shape.lines),
              );
            }
          }
        }
        lap(`the header at ${width} px`);
        // While the record is on its way the labels row is held, since the record may bring
        // labels: a record with labels lands moving nothing, row by row. One with none lands
        // without that row and the gap before it, and moves nothing above it (mb-2u08).
        const reference = seen["absent conversation"];
        const labelsRow = reference.rows.find((row) => row.row === "labels");
        const labelsSpace = (labelsRow?.height ?? Number.NaN) + reference.rowGap;
        const unlabelled = {
          header: reference.header - labelsSpace,
          tabBar: reference.tabBar - labelsSpace,
          rows: reference.rows.filter((row) => row.row !== "labels"),
        };
        // The status line is there only while it has something to say (mb-ne91), here an
        // offer: then it is one metadata line, as tall as the author's row, and one gap more,
        // and moves nothing above it. Without one it is not there, a hold included. The
        // expectation is the empty record's author's row, never the line measured (A4 of
        // review A on #506); the row of ages is a chip's height, the stack's strut's (mb-646g).
        const lineHeight = reference.rows.find((row) => row.row === "meta").height;
        for (const [key, shape] of Object.entries(seen)) {
          const none = shape.recordLabels === 0;
          const base = none ? unlabelled : reference;
          const offered = OFFERED.has(shape.label);
          const extra = offered ? lineHeight + shape.rowGap : 0;
          // A record's one-line title gives back the second line the cold title holds, and
          // moves the rows under it up by that line (mb-wcbc).
          const title = titleGivesBack(shape, reference);
          const expected = {
            header: base.header + extra + title.delta,
            tabBar: base.tabBar + extra + title.delta,
            rows: base.rows.map((row) => {
              if (row.row === "status") {
                return { ...row, height: offered ? lineHeight : 0 };
              }
              if (row.row === "title") {
                return { ...row, height: title.title };
              }
              return row;
            }),
          };
          check(
            `${width} px, ${key}: the header lays out to the empty record's height${none ? " less its labels row and that row's gap" : ""}${title.delta < 0 ? " less its title's second line" : ""}${extra > 0 ? ", with its status line" : ""}, row by row`,
            title.ok &&
              Math.abs(shape.header - expected.header) <= (none ? 0.5 : 0) &&
              Math.abs(shape.tabBar - expected.tabBar) <= (none ? 0.5 : 0) &&
              JSON.stringify(shape.rows) === JSON.stringify(expected.rows),
            JSON.stringify({ expected, [key]: shape }),
          );
        }
      }
      for (const width of runs("badges") ? [980, 360] : []) {
        for (const live of [true, false]) {
          const run = await browser.evaluate(`(${RUN_BADGE})(${live}, ${width})`);
          check(
            `${width} px, a run's badge from ${run.from} to ${run.to}: nothing in the file header moves`,
            run.moved.length === 0 && run.from !== run.to,
            JSON.stringify(run),
          );
        }
      }
      if (runs("badges")) {
        lap("the run badge");
      }
      if (runs("summary-wait")) {
        for (const theme of ["light", "dark"]) {
          for (const width of [560, 420, 360]) {
            const where = `${theme}, ${width} px`;
            const drawn = await browser.evaluate(
              `(${SUMMARY_WAIT})(${width}, ${JSON.stringify(theme)}, "arrives")`,
            );
            const { waiting, arrived } = drawn;
            check(
              `${where}: while the comparison is read, the Diff summary's row holds the pending placeholder, unseen in the quiet period`,
              waiting.quiet === "hidden" &&
                waiting.shown === "visible" &&
                waiting.pulse === "tally-pending-pulse" &&
                waiting.ground === true,
              JSON.stringify(waiting),
            );
            check(
              `${where}: the placeholder is on the row's line, from the row's start, as wide as a summary of one status`,
              waiting.left !== null &&
                Math.abs(waiting.left) <= 0.5 &&
                Math.abs(waiting.centre) <= 0.5 &&
                Math.abs(waiting.width - PENDING_EM * waiting.em) <= 0.5 &&
                Math.abs(waiting.height - 0.85 * waiting.em) <= 0.5 &&
                Math.abs(waiting.row - 24) <= 0.5,
              JSON.stringify(waiting),
            );
            check(
              `${where}: the summary takes the placeholder's place, and nothing in the header or under it moves`,
              !arrived.placeholder &&
                arrived.summary &&
                arrived.children === 1 &&
                Math.abs(arrived.row - waiting.row) <= 0.5 &&
                JSON.stringify(arrived.places) === JSON.stringify(waiting.places),
              JSON.stringify({ waiting, arrived }),
            );
            // The cached list's brief line in the placeholder's place (mb-z8ea): the summary's
            // words, where the summary's will be, which replaces it moving nothing.
            const briefed = await browser.evaluate(
              `(${SUMMARY_WAIT})(${width}, ${JSON.stringify(theme)}, "brief")`,
            );
            const { brief } = briefed.waiting;
            check(
              `${where}: while the comparison is read, the row holds the cached list's brief line, saying what the summary will`,
              brief !== null &&
                briefed.waiting.shown === null &&
                brief.text === briefed.arrived.text &&
                Math.abs(briefed.waiting.row - 24) <= 0.5,
              JSON.stringify(briefed),
            );
            check(
              `${where}: the summary replaces the brief line with its words in the same place, and nothing in the header or under it moves`,
              brief !== null &&
                briefed.arrived.summary &&
                briefed.arrived.children === 1 &&
                Math.abs(brief.wordsLeft - briefed.arrived.wordsLeft) <= 0.5 &&
                Math.abs(brief.wordsTop - briefed.arrived.wordsTop) <= 0.5 &&
                Math.abs(brief.textRight - briefed.arrived.textRight) <= 0.5 &&
                Math.abs(briefed.arrived.row - briefed.waiting.row) <= 0.5 &&
                JSON.stringify(briefed.arrived.places) === JSON.stringify(briefed.waiting.places),
              JSON.stringify(briefed),
            );
            briefs.push({
              where,
              brief,
              summary: [
                briefed.arrived.wordsLeft,
                briefed.arrived.wordsTop,
                briefed.arrived.textRight,
              ],
              row: [briefed.waiting.row, briefed.arrived.row],
            });
            const failed = await browser.evaluate(
              `(${SUMMARY_WAIT})(${width}, ${JSON.stringify(theme)}, "fails")`,
            );
            check(
              `${where}: a read that fails leaves the row empty, at its height, and moves nothing`,
              failed.waiting.shown === "visible" &&
                !failed.arrived.placeholder &&
                !failed.arrived.summary &&
                failed.arrived.children === 0 &&
                JSON.stringify(failed.arrived.places) === JSON.stringify(failed.waiting.places),
              JSON.stringify(failed),
            );
            // The pull request whose comparison arrived, opened again in this document: its
            // summary is in the first frame that paints its record, no frame shows the
            // placeholder, and nothing is read (mb-neg9).
            const { revisit } = await browser.evaluate(
              `(${SUMMARY_WAIT})(${width}, ${JSON.stringify(theme)}, "revisit")`,
            );
            const painted = revisit.frames.at(-1);
            check(
              `${where}: opened again, the summary is drawn in the frame that paints the record, with no placeholder in any frame and no read`,
              painted?.title === true &&
                painted.summary &&
                revisit.frames.every((frame) => !frame.placeholder) &&
                revisit.reads === 0,
              JSON.stringify(revisit),
            );
            revisits.push({ where, ...revisit });
            summaryWaits.push({ where, waiting, arrived });
          }
        }
        process.stderr.write(`summary-revisit: ${JSON.stringify(revisits)}\n`);
        process.stderr.write(`summary-brief: ${JSON.stringify(briefs)}\n`);
        process.stderr.write(
          `summary-wait: ${JSON.stringify(summaryWaits.map(({ where, waiting, arrived }) => ({ where, block: [waiting.left, waiting.width, waiting.height, waiting.centre], row: [waiting.row, arrived.row], tabBar: [waiting.places.tabBar, arrived.places.tabBar], summary: [arrived.chevronLeft, arrived.wordsLeft, arrived.textRight] })))}\n`,
        );
        // The placeholder is as wide as a summary of one status, "1 M · +3 −1" to "8 M · +120
        // −30", its file count on the size line above, as each arrives in the row: it ends no
        // sooner than the shortest one's text and no later than the longest one's header,
        // from the row's start, in em of the header's type, in both themes (mb-vb51).
        const sizes = [];
        for (const theme of ["light", "dark"]) {
          const arrivals = [];
          for (const change of ONE_STATUS) {
            arrivals.push(
              await browser.evaluate(
                `(${SUMMARY_WAIT})(560, ${JSON.stringify(theme)}, "arrives", ${JSON.stringify(change)})`,
              ),
            );
          }
          const em = (value, of) => Math.round((value / of) * 100) / 100;
          const block = em(arrivals[0].waiting.width, arrivals[0].waiting.em);
          const ends = arrivals.map(({ arrived }) => ({
            label: arrived.label,
            text: em(arrived.textRight, arrived.em),
            header: em(arrived.toggleLeft + arrived.width, arrived.em),
          }));
          check(
            `${theme}: the pending placeholder is as wide as a summary of one status`,
            ends.length === ONE_STATUS.length &&
              block >= Math.min(...ends.map((end) => end.text)) &&
              block <= Math.max(...ends.map((end) => end.header)),
            JSON.stringify({ block, ends }),
          );
          const three = summaryWaits.find(({ where }) => where.startsWith(theme))?.arrived;
          sizes.push({
            theme,
            block,
            ends,
            three: three ? em(three.textRight, three.em) : null,
          });
        }
        process.stderr.write(`summary-widths: ${JSON.stringify(sizes)}\n`);
        lap("the Diff summary's wait");
      }
      if (runs("cold-landing")) {
        const landings = [];
        for (const [seeded, outcomes] of [
          [false, ["quiet", "held", "slow"]],
          [true, ["quiet", "slow"]],
        ]) {
          for (const width of [560, 360]) {
            for (const labelled of [false, true]) {
              const kind = labelled ? "a labelled pull request" : "an unlabelled pull request";
              for (const outcome of outcomes) {
                const where = `${width} px, ${kind}, ${outcome}${seeded ? ", its Pulls row in hand" : ""}`;
                const run = await browser.evaluate(
                  `(${COLD_LANDING})(${width}, ${labelled}, ${JSON.stringify(outcome)}, ${seeded})`,
                );
                landings.push({ where, run });
                const { before, shownCold, landed } = run;
                check(
                  `${where}: the cold page's Diff summary row holds the placeholder from first paint, in its quiet period`,
                  before.pending === "hidden",
                  JSON.stringify(before),
                );
                check(
                  `${where}: the cold page is held unseen in the quiet period, its tab keys live`,
                  before.cold &&
                    before.header === "0" &&
                    before.column === "0" &&
                    before.live.length === 4 &&
                    before.live.every(Boolean),
                  JSON.stringify(before),
                );
                check(
                  `${where}: the cold title is ${seeded ? "the Pulls row's, the record's shape" : '"Pull request #", held at two lines'}`,
                  before.seeded === seeded &&
                    (seeded ||
                      before.title === 2 * run.inHandTitle ||
                      before.title === run.inHandTitle),
                  JSON.stringify({ before, inHandTitle: run.inHandTitle }),
                );
                // A record seen landing on a cold title held at two lines keeps them, so it
                // lands moving nothing; one that lands unseen, or under its row's title, has its
                // own lines, where it lands in hand.
                const keeps = outcome === "slow" && !seeded;
                const kept = landed.title - run.inHandTitle;
                check(
                  `${where}: the record lands where it lands in hand${keeps ? ", but for its title keeping the cold title's two lines" : ""}, the header and tab column shown together`,
                  !landed.cold &&
                    landed.header === "1" &&
                    landed.column === "1" &&
                    run.held === keeps &&
                    (keeps ? kept === 0 || kept === run.inHandTitle : kept === 0) &&
                    landed.tabBar === run.landsAt + kept &&
                    run.halfShown === 0,
                  JSON.stringify({
                    landsAt: run.landsAt,
                    inHandTitle: run.inHandTitle,
                    held: run.held,
                    landed,
                    halfShown: run.halfShown,
                  }),
                );
                if (outcome === "slow") {
                  // A read slower than the quiet period shows the cold header, rows held, its
                  // title the Pulls row's or two lines the record keeps: one with labels lands
                  // moving nothing, and one with none moves the tab bar up by the labels row
                  // and its gap (mb-2u08; review A on #608).
                  check(
                    `${where}: after the quiet period the cold header shows, rows held`,
                    shownCold.cold && shownCold.header === "1" && shownCold.column === "1",
                    JSON.stringify(shownCold),
                  );
                  check(
                    `${where}: the placeholder shows with the cold header, so its row is never seen empty`,
                    shownCold.pending === "visible",
                    JSON.stringify(shownCold),
                  );
                  check(
                    `${where}: ${labelled ? "the record lands moving nothing" : "the record lands moving the tab bar up by the labels row and its gap"}`,
                    labelled
                      ? shownCold.tabBar === landed.tabBar
                      : shownCold.tabBar > landed.tabBar,
                    JSON.stringify({ shownCold, landed }),
                  );
                } else {
                  check(
                    `${where}: the cold header never shows, so the tab bar never moves`,
                    run.coldShown === 0 && run.tabBarsShown.length === 1,
                    JSON.stringify({ coldShown: run.coldShown, tabBarsShown: run.tabBarsShown }),
                  );
                }
                if (outcome === "held") {
                  check(
                    `${where}: a record that lands in the quiet period shows its header while the conversation still waits for its Markdown`,
                    !landed.cold && landed.header === "1" && run.bodyHeld === true,
                    JSON.stringify({ landed, bodyHeld: run.bodyHeld }),
                  );
                }
              }
            }
          }
        }
        process.stderr.write(
          `cold-landing: ${JSON.stringify(landings.map(({ where, run }) => ({ where, landsAt: run.landsAt, cold: run.shownCold.tabBar, landed: run.landed.tabBar, held: run.held, coldShown: run.coldShown })))}\n`,
        );
        lap("the cold landings");
      }
      // The View on GitHub button in the header's corner (mb-4wqh): at a pane where the
      // reading column ends short of the button and two where it reaches it, in both themes,
      // with a title of one line and one cut short at two. At the middle width the pointer is
      // put on the chevron, then moved away.
      if (runs("corner")) {
        // The server's default reading width, which the caller passes from settings.py.
        const maxChars = Number(process.env.METABROWSER_DOC_MAX_CHARS_DEFAULT);
        if (!Number.isFinite(maxChars) || maxChars <= 0) {
          throw new Error("METABROWSER_DOC_MAX_CHARS_DEFAULT names no reading width");
        }
        const tops = new Map();
        const widths = new Set();
        for (const theme of ["light", "dark"]) {
          for (const width of [980, 560, 360]) {
            for (const longTitle of [false, true]) {
              const where = `${width} px, ${theme}, a ${longTitle ? "long" : "short"} title`;
              const read = await browser.evaluate(
                `(${CORNER})(${width}, ${JSON.stringify(theme)}, ${longTitle}, ${maxChars})`,
              );
              const near = (a, b) => Math.abs(a - b) <= 0.5;
              check(
                `${where}: the button is drawn in the header's corner, after the title, the corner marked for its room`,
                read.button !== null && read.afterTitle && read.marked,
                JSON.stringify(read),
              );
              if (read.button === null) {
                await browser.evaluate(CORNER_DONE);
                continue;
              }
              const { button, tokens, states, want, hooks } = read;
              check(
                `${where}: the button links to the pull request's page on GitHub through the app's hooks`,
                read.label === "View on GitHub" &&
                  hooks.root &&
                  hooks.open === read.url &&
                  hooks.openTarget === "_blank" &&
                  hooks.external === read.url &&
                  hooks.externalTarget === "_blank" &&
                  hooks.externalRel === "noopener",
                JSON.stringify({ label: read.label, hooks, url: read.url }),
              );
              // On the title's first line, at the corner's end inset, its label on the
              // title's baseline (mb-tatf), as a file's and a folder's is on theirs.
              check(
                `${where}: the button is at the corner's end inset, its label on the title's first baseline`,
                near(button.end, tokens.insetEnd) &&
                  read.baselines.label !== null &&
                  read.baselines.label === read.baselines.title,
                JSON.stringify({ button, tokens, baselines: read.baselines }),
              );
              check(
                `${where}: the button is the corner's height`,
                near(button.height, tokens.height),
                JSON.stringify({ button, tokens }),
              );
              widths.add(button.width);
              check(
                `${where}: the corner's room holds the button and the 8 px gap before it`,
                button.width + 8 <= tokens.room + 0.5,
                JSON.stringify({ button, tokens }),
              );
              const key = `${width} ${theme}`;
              if (tops.has(key)) {
                check(
                  `${where}: the button is where it is with a title of one line`,
                  near(button.top, tops.get(key)),
                  JSON.stringify({ top: button.top, short: tops.get(key) }),
                );
              } else {
                tops.set(key, button.top);
              }
              const clear = button.start - 8;
              check(
                `${where}: the title's text and number end the gap clear of the button`,
                read.textEnd <= clear + 0.5 && read.numberEnd <= clear + 0.5,
                JSON.stringify({ textEnd: read.textEnd, numberEnd: read.numberEnd, clear }),
              );
              check(
                width === 980
                  ? `${where}: the reading column ends short of the button, so the title keeps its width`
                  : `${where}: the reading column reaches the button, so the title leaves it its room`,
                width === 980 ? read.titleRoom === 0 : near(read.titleRoom, tokens.room),
                JSON.stringify({
                  titleRoom: read.titleRoom,
                  room: tokens.room,
                  column: read.column,
                  page: read.page,
                }),
              );
              check(`${where}: the pane does not scroll sideways`, !read.paneScrolls);
              check(
                `${where}: the link is in the text ink and the chevron muted, neither filled at rest`,
                states.open.ink === want.text &&
                  states.more.ink === want.muted &&
                  states.open.fill === "rgba(0, 0, 0, 0)" &&
                  states.more.fill === "rgba(0, 0, 0, 0)",
                JSON.stringify({ states, want }),
              );
              check(
                `${where}: the button has the joined chip group's frame`,
                states.frame.border === want.border &&
                  states.frame.ground === want.surface &&
                  states.frame.radius === want.radius,
                JSON.stringify({ frame: states.frame, want }),
              );
              if (width === 560 && !longTitle) {
                await browser.send("Input.dispatchMouseEvent", {
                  type: "mouseMoved",
                  x: read.chevron.x,
                  y: read.chevron.y,
                });
                const hovered = await browser.evaluate(CORNER_HOVERED);
                check(
                  `${where}: the chevron under the pointer is in the text ink on the hover fill`,
                  hovered.hovered && hovered.ink === want.text && hovered.fill === want.hover,
                  JSON.stringify({ hovered, want }),
                );
                await browser.send("Input.dispatchMouseEvent", {
                  type: "mouseMoved",
                  x: 1,
                  y: 899,
                });
              }
              await browser.evaluate(CORNER_DONE);
            }
          }
        }
        // The widths the button was drawn at, for the room's token (static/styles.css).
        process.stderr.write(`corner: the button's widths ${[...widths].join(", ")} px\n`);
        lap("the corner");
      }
      if (runs("labels")) {
        const github = JSON.parse(fs.readFileSync(LABEL_COLORS, "utf8"));
        for (const theme of ["light", "dark"]) {
          const empty = await browser.evaluate(
            `(${MEASURE})("absent", ${JSON.stringify({ theme })}, "", 980)`,
          );
          const shape = await browser.evaluate(
            `(${MEASURE})("current", ${JSON.stringify({ labels: LABEL_CASES, theme })}, "", 980)`,
          );
          check(
            `${theme}: every label is drawn, in order`,
            JSON.stringify(shape.labels.map((chip) => chip.name)) ===
              JSON.stringify(LABEL_CASES.map((label) => label.name)),
            JSON.stringify(shape.labels),
          );
          const chipHeight = shape.branchChipHeights[0];
          check(
            `${theme}: branch chips and labels have the same outer height, below the state badge`,
            shape.branchChipHeights.length === 2 &&
              shape.branchChipHeights.every((height) => height === chipHeight) &&
              shape.labels.every((chip) => chip.height === chipHeight) &&
              shape.statusBadgeHeight > chipHeight,
            JSON.stringify({
              branches: shape.branchChipHeights,
              labels: shape.labels.map((chip) => chip.height),
              badge: shape.statusBadgeHeight,
            }),
          );
          check(
            `${theme}: label capitals center inside the compact chip`,
            shape.labels.every((chip) => Math.abs(chip.capOffset) <= 0.5),
            JSON.stringify(shape.labels.map(({ name, capOffset }) => ({ name, capOffset }))),
          );
          const neutralBox = shape.labels.find((chip) => chip.name === "no color")?.box;
          for (const chip of shape.labels) {
            const label = LABEL_CASES.find((each) => each.name === chip.name);
            const where = `${theme}, the ${chip.name} label`;
            const hex = /^[0-9a-fA-F]{6}$/.test(label?.color ?? "")
              ? label.color.toLowerCase()
              : null;
            check(
              `${where}: carries GitHub's color, or none`,
              chip.color === hex,
              JSON.stringify(chip),
            );
            check(
              `${where}: its description is its tooltip, and no description no tooltip`,
              chip.tip === label?.description,
              JSON.stringify(chip),
            );
            check(
              `${where}: keeps the chip's font size, padding, border, corner, and height`,
              neutralBox !== undefined && chip.box === neutralBox,
              JSON.stringify({ chip: chip.box, neutral: neutralBox }),
            );
            if (hex === null) {
              check(
                `${where}: is the neutral chip, --muted on no ground in a --border box`,
                chip.background === "rgba(0, 0, 0, 0)" &&
                  chip.text === shape.neutral.text &&
                  chip.border === shape.neutral.border &&
                  chip.properties === null,
                JSON.stringify({ chip, neutral: shape.neutral }),
              );
              continue;
            }
            const computed = github.computed[theme][hex];
            const [r, g, b] = [0, 2, 4].map((at) => Number.parseInt(hex.slice(at, at + 2), 16));
            const [h, s, l] = computed.properties;
            check(
              `${where}: carries the properties github.com gave this color`,
              chip.properties ===
                `--github-label-r:${r};--github-label-g:${g};--github-label-b:${b};--github-label-h:${h};--github-label-s:${s};--github-label-l:${l}`,
              JSON.stringify(chip),
            );
            const formula = labelFormula(hex, computed.properties, theme);
            check(
              `${where}: its ground, text, and border are GitHub's formula's`,
              nearColor(chip.background, formula.background) &&
                nearColor(chip.text, formula.text) &&
                nearColor(chip.border, formula.border),
              JSON.stringify({ chip, formula }),
            );
            check(
              `${where}: its ground, text, and border are what github.com computed for it`,
              chip.background === computed.background &&
                chip.text === computed.color &&
                chip.border === computed.border,
              JSON.stringify({ chip, github: computed }),
            );
          }
          // A label an earlier cache names alone, without a color or a description, as a core
          // or record cached before label colors draws it, until the record that colors it
          // arrives: each chip starts and ends where the colored one does, and the rows hold.
          const bare = await browser.evaluate(
            `(${MEASURE})("current", ${JSON.stringify({
              labels: LABEL_CASES.map(({ name }) => ({ name, color: null, description: null })),
              theme,
            })}, "", 980)`,
          );
          const places = (measured) =>
            measured.labels.map((chip) => [chip.name, chip.left, chip.width]);
          check(
            `${theme}: a label's color and tooltip arriving move no chip and no row`,
            bare.labels.every((chip) => chip.color === null && chip.tip === null) &&
              JSON.stringify(places(bare)) === JSON.stringify(places(shape)) &&
              JSON.stringify(bare.rows) === JSON.stringify(shape.rows) &&
              bare.tabBar === shape.tabBar,
            JSON.stringify({
              bare: places(bare),
              colored: places(shape),
              rows: [bare.rows, shape.rows],
            }),
          );
          // The same labels named alone, with the repository's cached set in the envelope, as
          // a page first paints a record cached before label colors once the set is cached
          // (mb-varu): every chip is colored and titled as the record's own colors draw it.
          const known = await browser.evaluate(
            `(${MEASURE})("current", ${JSON.stringify({
              labels: LABEL_CASES.map(({ name }) => ({ name, color: null, description: null })),
              repositoryLabels: LABEL_CASES.filter(({ color }) =>
                /^[0-9a-fA-F]{6}$/.test(color ?? ""),
              ).map(({ name, color, description }) => ({ name, color, description })),
              theme,
            })}, "", 980)`,
          );
          // A label the set holds is drawn as its own color draws it; one it does not hold, or
          // holds without six hex digits, stays the neutral chip, with no tooltip.
          const held = new Set(
            LABEL_CASES.filter(({ color }) => /^[0-9a-fA-F]{6}$/.test(color ?? "")).map(
              ({ name }) => name,
            ),
          );
          const paint = (measured) =>
            measured.labels
              .filter((chip) => held.has(chip.name))
              .map((chip) => [
                chip.name,
                chip.color,
                chip.properties,
                chip.tip,
                chip.background,
                chip.text,
                chip.border,
              ]);
          check(
            `${theme}: a label named alone takes the repository's color and tooltip on first paint`,
            JSON.stringify(paint(known)) === JSON.stringify(paint(shape)) &&
              paint(known).length === held.size &&
              known.labels
                .filter((chip) => !held.has(chip.name))
                .every((chip) => chip.color === null && chip.tip === null),
            JSON.stringify({ known: paint(known), own: paint(shape) }),
          );
          // Less the second line the cold title holds, where the record's title is one line
          // (mb-wcbc).
          const title = titleGivesBack(shape, empty);
          check(
            `${theme}: a header with labels of every color lays out to the empty record's height${title.delta < 0 ? " less its title's second line" : ""}, row by row`,
            title.ok &&
              shape.header === empty.header + title.delta &&
              shape.tabBar === empty.tabBar + title.delta &&
              JSON.stringify(shape.rows) ===
                JSON.stringify(
                  empty.rows.map((row) =>
                    row.row === "title" ? { ...row, height: title.title } : row,
                  ),
                ),
            JSON.stringify({ empty: empty.rows, labels: shape.rows, title }),
          );
        }
        lap("the labels in both themes");
      }
      if (runs("pulls")) {
        const numbers = await browser.evaluate(NUMBERS);
        check(
          "a pull request's number is bold in Quick Search and the ref selector, as a stack's position is",
          numbers.palette === "700" && numbers.selector === "700" && numbers.position === "700",
          JSON.stringify(numbers),
        );
      }
      for (const width of runs("pulls") ? PULLS_WIDTHS : []) {
        const rows = await browser.evaluate(`(${PULLS_ROWS})(${JSON.stringify(PULLS)}, ${width})`);
        for (const row of rows) {
          const where = `${width} px, Pulls row #${row.number}`;
          // The place is after the title (mb-pw8t): nothing before it moves when it arrives, and
          // the number and the toggle after it move along the run, the row growing by whole
          // lines where the place takes one, and the item by that alone. Before, the place led
          // the title, which moved after it (mb-vkhd, mb-zuy0).
          check(
            `${where}: a late stack place moves nothing before it, and the row grows by whole lines alone`,
            row.moved.length === 0 &&
              Math.abs(row.grew / row.lineHeight - Math.round(row.grew / row.lineHeight)) < 0.03 &&
              row.itemGrew === row.grew,
            JSON.stringify({ moved: row.moved, grew: row.grew, itemGrew: row.itemGrew }),
          );
          // The place follows the title, after the stack menu's dot, and the number follows
          // it, as the stack menu's member line has them (mb-pw8t).
          check(
            `${where}: the stack place follows the title after its dot, and the number follows it`,
            row.placeAfter,
            JSON.stringify(row),
          );
          check(`${where}: the number shows whole`, row.whole, JSON.stringify(row));
          check(
            `${where}: the title, the number, the toggle, and the age end inside the row, and nothing scrolls sideways`,
            row.inside,
            JSON.stringify(row),
          );
          const oneStack = !PULLS.find((pull) => pull.number === row.number).stack.includes(" · ");
          check(
            `${where}: one stack's place shows whole`,
            !row.cut || !oneStack,
            JSON.stringify(row),
          );
          // The run is as tall as its lines, never cut short, every line of it in the text
          // column, and it ends with the author; the last line follows it, the toggle on it in
          // the text column and the age at its end (mb-pw8t, mb-rb3n).
          check(
            `${where}: the run is as tall as its lines, each in the text column, and ends with the author, the last line under it, the toggle and then the age at the row's end`,
            Math.abs(row.headingHeight - row.drawnLines * row.lineHeight) < 0.5 &&
              row.starts.every((start) => start !== null && Math.abs(start) < 0.5) &&
              Math.abs(row.columnFrom - row.textColumn) < 0.5 &&
              row.endsWithAuthor &&
              row.lastLine &&
              Math.abs(row.tailFrom - row.textColumn) < 0.5,
            JSON.stringify(row),
          );
          // The icon leads the run's first line, in its slot, on the row's inset (mb-3vil).
          check(
            `${where}: the icon leads the run's first line on the row's inset`,
            row.iconOnFirst && Math.abs(row.iconFrom) < 0.5,
            JSON.stringify(row),
          );
          check(
            `${where}: the author follows the number, and its name ends the run inside the row`,
            row.byAfter && row.authorEnds,
            JSON.stringify(row),
          );
          check(
            `${where}: the title keeps a share of its lines`,
            row.title >= 20,
            JSON.stringify(row),
          );
        }
        if (process.env.METABROWSER_PULLS_HEADER_MEASURE) {
          console.error(JSON.stringify({ width, rows }));
        }
        lap(`the Pulls rows at ${width} px`);
      }
      // The records that carry an offer, mounted for the offers alone; in the header parts
      // they are measured with every other record.
      if (runs("offers")) {
        for (const [name, change] of OFFER_RECORDS) {
          const shape = await browser.evaluate(
            `(${MEASURE})(${JSON.stringify(name)}, ${JSON.stringify(change)}, "", 980)`,
          );
          if (shape.offers > 0) {
            offersDrawn.add(
              `${name}${Object.keys(change).length ? ` ${Object.keys(change).join(" ")}` : ""}`,
            );
          }
        }
        check(
          "the offer is drawn by the record that carries it",
          offersDrawn.has("on_head checkoutAtHead"),
          JSON.stringify([...offersDrawn]),
        );
        lap("the offers");
      }
    } finally {
      await browser.close();
    }
    lap("Chrome closed");
  } finally {
    server.close();
  }
}

main()
  .catch((error) => {
    failures.push(`pull header session threw: ${error?.stack || error}`);
  })
  .then(() => {
    if (failures.length > 0) {
      console.error(failures.join("\n"));
      process.exitCode = 1;
    } else {
      console.log(`pull header in Chrome, ${PART}: ${checks} checks passed`);
    }
  });

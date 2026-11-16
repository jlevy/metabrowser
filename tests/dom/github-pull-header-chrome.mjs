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
// the run badge (`badges`), and the label chips' colors in both themes (`labels`). With no
// part it runs every one. Each part writes how long
// each of its steps took to stderr.
//
// KPRESS_STATIC holds KPress's style-tokens.css and the faces it names, which
// tests/test_github_pull_header_chrome.py copies out of the installed package, so the
// header is set in the faces the shell uses.
//
// The header is reserved at first paint, so a record that has not arrived and every
// loaded record lay out to one height on every tab, row by row, and the tab bar under it
// starts at one place. That is layout, which no browserless DOM can compute: the
// stylesheet text passed with a state badge whose first flex item was a zero-height sizer,
// which hung the badge below the line and made the loaded header 5.6 px taller than the
// empty one. And no record's row may end past the header: an offer kept whole ran 262 px
// past it in a 360 px pane, and the pane scrolled sideways. The row structure itself is
// pinned browserless in github-pull-page-mount-behavior.js.
//
// The session also lays out Pulls rows as their stack places arrive, and the file
// header as a run's status badge changes its label in place (RUN_BADGE below).
import fs from "node:fs";
import http from "node:http";
import path from "node:path";
import { launchChrome } from "./chrome-session.mjs";

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

// The scripts the SDK's ref helpers need, in the order tests/dom/sdk-sandbox.js loads them.
const SDK = [
  "request-error.js",
  "formatters.js",
  "inventory-scope.js",
  "resource-context.js",
  "view-state.js",
  "navigation.js",
  "plugin-sdk.js",
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
  await new Promise((resolve) => setTimeout(resolve, 300));
  await frames();
  const left = (node) => Math.round(node.getBoundingClientRect().left * 100) / 100;
  return {
    step: parseFloat(getComputedStyle(document.documentElement).getPropertyValue("--tree-indent")),
    chevron: left(toggle.querySelector(".diff-summary-chevron")),
    words: left(toggle.querySelector(".diff-summary-files")),
    rows: [...place.querySelectorAll('.diff-summary-body [role="treeitem"]')].map((row) => ({
      id: row.dataset.id,
      level: Number(row.getAttribute("aria-level")),
      lead: left(row.children[0]),
      name: left(row.children[1]),
    })),
  };
}`;
/** The rows of a measured tree that do not start one step per level in from its header. */
const offStep = (indent) =>
  indent === null
    ? ["not measured"]
    : indent.rows.filter(
        (row) =>
          Math.abs(row.lead - indent.chevron - indent.step * row.level) > 0.5 ||
          Math.abs(row.name - indent.words - indent.step * row.level) > 0.5,
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
  // A pin behind the pull request's head draws the offer to switch to it.
  if (change.pinBehind) {
    body.pin = "1".repeat(40);
    body.pin_ref = "refs/pull/" + body.number + "/head";
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
      mountRefCopies: mb.mountRefCopies,
      titleNodes: mb.titleNodes,
      formatAge: () => ({ label: "now", className: "age" }),
      formatTimestamp: (seconds) => new Date(seconds * 1000).toISOString(),
      navigation: { href: () => "/view/" },
      sourceKind: () => "filesystem",
      repository: change.checkoutAtHead ? { revision: body.record?.pull?.head?.sha } : undefined,
      icons: { toggle: "" },
    },
  );
  await document.fonts.ready;
  const frames = () => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
  await frames();
  // The avatar slot authorLabel draws, without a request: no fixture names an avatar the
  // page may load, and most authors have one.
  if (change.avatar) {
    for (const identity of container.querySelectorAll(".github-pull-meta .github-pull-identity")) {
      const image = document.createElement("img");
      image.className = "github-pull-avatar";
      image.alt = "";
      image.width = 18;
      image.height = 18;
      identity.prepend(image);
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
  // Where the state row's parts and the labels are, and every row's height.
  const places = () => ({
    parts: [".github-pull-badge", ".github-pull-action", ".github-pull-identity", ".merge-refs-source", ".merge-refs-arrow", ".merge-refs-target", ".github-pull-label"].flatMap((selector) =>
      [...header.querySelectorAll(selector)].map((node) => [selector, Math.round(box(node).left * 100) / 100, Math.round(box(node).width * 100) / 100]),
    ),
    rows: [...header.children].map((row) => Math.round(box(row).height * 100) / 100),
    tabBar: Math.round((box(container.querySelector(".tab-bar")).top - box(header).top) * 100) / 100,
  });
  // The pull request's Diff summary arrives with its comparison, in the header's last row,
  // held from first paint (mb-pb35). It is drawn by the diff plugin's own mountDiffSummary,
  // on a change set whose breakdown names three statuses, "35 changed files (2 added,
  // 3 removed, 30 modified) +1,234 −3,423": it moves nothing, keeps its row's height, and
  // starts on the header's content edge.
  let summaryMoves = null;
  if (change.stackChip) {
    const slot = header.querySelector(".github-pull-summary");
    const before = places();
    const rowBefore = Math.round(box(slot).height * 100) / 100;
    const diff = (window.__diff ??= await import("/diff/diff-view.js"));
    const kinds = [
      ...Array(2).fill("added"),
      ...Array(3).fill("deleted"),
      ...Array(30).fill("modified"),
    ];
    const files = kinds.map((kind, at) => ({
      kind,
      ...(kind === "added" ? {} : { old: { path: "src/f" + at + ".py" } }),
      ...(kind === "deleted" ? {} : { new: { path: "src/f" + at + ".py" } }),
      additions: 30,
      deletions: 90,
    }));
    const summary = diff.mountDiffSummary(
      slot,
      { manifest: { totals: { files: 35, additions: 1234, deletions: 3423, exact: true }, files } },
      mb,
      { changedFiles: window.MetabrowserChangedFilesTree, openFile() {} },
    );
    await frames();
    const after = places();
    const rows = (shape) => JSON.stringify({ rows: shape.rows, tabBar: shape.tabBar });
    const headerLeft = box(header).left + parseFloat(getComputedStyle(header).paddingLeft);
    const toggle = slot.querySelector(".diff-summary");
    summaryMoves = {
      moved: rows(before) === rows(after) ? null : { before, after },
      rowBefore,
      rowAfter: Math.round(box(slot).height * 100) / 100,
      toggleHeight: toggle ? Math.round(box(toggle).height * 100) / 100 : null,
      left: Math.round((box(slot).left - headerLeft) * 100) / 100,
      text: toggle?.textContent ?? null,
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
  // the right end of the author's row (mb-cf0l): one stack, "2/3", or two, "4/4" and "2/2".
  // Its Layers glyph is a bare svg at the glyph's size, so the chip is as wide as the page's.
  // The strut that holds the author's row at a chip's height, read before a chip replaces it.
  const heldBy = header.querySelector(".github-pull-meta .github-pull-stack-strut");
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
        titleNodes: mb.titleNodes,
        onOpen() {},
      }),
    );
    const column = header.querySelector(".github-pull-stacks");
    column.replaceChildren(...menus.map((menu) => menu.element));
    await frames();
    const after = places();
    // Nothing moves: every part keeps its start, every row its height, the tab bar its place.
    // The sentence alone, the author then the action, may give up width at its end where the
    // row has none left: the action is cut first, to nothing, and then the author, so the
    // sentence keeps its start and only the action's start, past a shorter name, moves.
    const sentence = new Set([".github-pull-action", ".github-pull-identity"]);
    const kept = (shape) => ({
      parts: shape.parts.map(([selector, left, width]) => [
        selector,
        selector === ".github-pull-action" ? null : left,
        sentence.has(selector) ? null : width,
      ]),
      rows: shape.rows,
      tabBar: shape.tabBar,
    });
    const details = header.querySelector(".github-pull-meta-details");
    const contentRight = box(header).right - parseFloat(getComputedStyle(header).paddingRight);
    chipMoves = {
      chips: stacks.length,
      moved: JSON.stringify(kept(before)) === JSON.stringify(kept(after)) ? null : { before, after },
      cut:
        Math.round(
          before.parts
            .filter(([selector]) => sentence.has(selector))
            .reduce((sum, [, , width], at) => sum + width - after.parts.filter(([s]) => sentence.has(s))[at][2], 0) *
            100,
        ) / 100,
      chipShown: Math.min(...menus.map((menu) => shown(menu.element))),
      overlap: Math.round((box(details).right - box(column).left) * 100) / 100,
      rightEdge: Math.round((box(column).right - contentRight) * 100) / 100,
      chipWidth: Math.round(box(column).width * 100) / 100,
    };
    // Its member menu heads its rows with the host's menu group, whose heading starts
    // on the rows' inset (docs/design-system.md, "Groups in a Menu"). A second menu of
    // the same stack is opened outside the header, through its disclosure, which
    // populates it on its toggle event, and removed again: the header's own menu stays
    // lazy, as the checks below expect.
    const probe = page.createStackMenu(
      { number: 286, pulls: [body.number - 1, body.number, body.number + 1] },
      body.number,
      { link: () => document.createElement("a"), icon: null, currentTitle: "", titleNodes: mb.titleNodes, onOpen() {} },
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
  const rows = [...header.children].map((row) => ({
    row: row.tagName === "H1" ? "title" : [...row.classList].find((c) => c.startsWith("github-pull-")).slice(12),
    height: Math.round(box(row).height * 100) / 100,
  }));
  const meta = header.querySelector(".github-pull-meta");
  // The state badge leads the row of ages (mb-4ydo).
  const opened = header.querySelector(".github-pull-opened");
  const badge = opened?.querySelector(".github-pull-badge");
  const centre = (r) => r.top + r.height / 2;
  // The title's icon and text start at the header's left edge and its number ends on the
  // right one, over the stack's slot that ends the author's row (mb-z416).
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
    const slot = header.querySelector(".github-pull-meta .github-pull-stacks");
    const r = (v) => Math.round(v * 100) / 100;
    return {
      iconLeft: r(icon.left - left),
      textAfterIcon: r(text.left - icon.right),
      gap: r(parseFloat(getComputedStyle(heading).columnGap)),
      numberRight: r(number.right - right),
      numberOverSlot: slot ? r(number.right - box(slot).right) : null,
      numberBelowText: r(number.bottom - text.bottom),
    };
  })();
  const result = {
    edges,
    header: Math.round(box(header).height * 100) / 100,
    tabBar: Math.round(box(container.querySelector(".tab-bar")).top - box(header).top),
    rows,
    meta: meta ? Math.round(box(meta).height * 100) / 100 : null,
    strut: strutHeight,
    badgeOffset: badge ? Math.round((centre(box(badge)) - centre(box(opened))) * 100) / 100 : null,
    offers: header.querySelectorAll(".github-pull-offer").length,
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
    labels: [...header.querySelectorAll(".github-pull-label")].map((chip) => {
      const style = getComputedStyle(chip);
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
// limit. A failure is let wrap its status row, so it is not among them.
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
  ["behind_head", {}],
  ["current", { pinBehind: true }],
  ["on_head", { checkoutAtHead: true }],
  ["current", { lastRefresh: RATE_LIMITED }],
  ["current", { avatar: true }],
  ["current", { longTitle: true }],
  ["current", { longNames: true }],
  ["current", { longNames: true, avatar: true }],
  ["merged", { longNames: true, avatar: true }],
];
// Pulls rows built as pulls-panel.js#buildRow and #rowMeta build them, whose order
// github-pulls-panel-session.js pins: the toggle, the state icon, the title, the age, and
// the number's line, which the stylesheet lays out as two lines (mb-lkkt): the number's
// line, where a stack member's place comes before its number (mb-dzsi), and the age;
// then the chevron, the icon, and the title, to the row's end. Each row is a member, a
// level in under its stack's row. The age, the chevron, the icon, and the title are read,
// from the row's top, before and after each row's place arrives, the title's width with
// them: the place is on the number's line, which stays one line, so nothing else moves
// and the row keeps its two lines (`grew`).
const PULLS_ROWS = `async (rows, width) => {
  const page = window.__page ??= await import("/github/pull-page.js");
  const state = window.__state ??= await import("/github/pull-state.js");
  const h = (tag, attributes = {}, children = []) => {
    const node = document.createElement(tag);
    for (const [key, value] of Object.entries(attributes)) node.setAttribute(key, value);
    node.append(...children);
    return node;
  };
  // The panel's own container, as pulls-panel.js#mountPullsPanel marks it: it carries the
  // avatar's size and gap, without which an avatar had no size here and an author no floor.
  const nav = h("div", { class: "github-pulls" });
  nav.style.width = width + "px";
  const list = h("ul", { class: "github-pulls-list", role: "tree" });
  nav.append(list);
  document.getElementById("preview-pane").replaceChildren(nav);
  const built = rows.map((row) => {
    const identity = page.authorLabel(row.author, null, "github-pulls-author");
    if (row.avatar) {
      // The slot authorLabel draws for an avatar, without a request.
      identity.prepend(h("img", { class: "github-pull-avatar", alt: "", width: "18", height: "18" }));
    }
    const separator = () => h("span", { class: "github-pulls-sep" }, [" · "]);
    const place = h("span", { class: "github-pulls-place", role: "img", hidden: "" });
    const number = h("span", { class: "github-pulls-number" }, ["#" + row.number]);
    const title = h("span", { class: "github-pulls-title" }, [row.title]);
    const age = h("span", { class: "github-pulls-age" }, ["12mo"]);
    const anchor = h("a", { class: "github-pulls-row collapsed", href: "#", role: "treeitem" }, [
      h("span", { class: "github-pulls-toggle", "aria-hidden": "true" }),
      state.pullStateIcon("open"),
      title,
      age,
      h("span", { class: "github-pulls-meta" }, [
        h("span", { class: "github-pulls-line" }, [
          h("span", { class: "github-pulls-id" }, [place, number]),
          h("span", { class: "github-pulls-by" }, [separator(), identity]),
        ]),
      ]),
    ]);
    list.append(h("li", { class: "github-pulls-item", role: "none", "data-level": "2" }, [anchor]));
    return { anchor, place, number, title, age, row };
  });
  await document.fonts.ready;
  const frames = () => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
  await frames();
  // Each row's age and title line, the title's width with them, read from its row's top.
  const titleLine = built.map(({ anchor, title, age }) => [anchor.querySelector(".github-pulls-toggle"), anchor.querySelector(".github-pull-state-icon"), title, age]);
  const read = () =>
    titleLine.map((nodes, at) => {
      const top = built[at].anchor.getBoundingClientRect().top;
      return nodes.map((node) => {
        const r = node.getBoundingClientRect();
        return [r.left, r.top - top, r.width, r.height].map((value) => Math.round(value * 100) / 100);
      });
    });
  const before = read();
  const heights = built.map(({ anchor }) => anchor.getBoundingClientRect().height);
  for (const { place, row } of built) {
    place.hidden = false;
    // As pulls-panel.js#paintPlace draws it: another stack is the Layers glyph before its
    // number, written here as "#N", and a separator ends the place.
    place.append(
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
      h("span", { class: "github-pulls-sep" }, [" · "]),
    );
  }
  await frames();
  const after = read();
  return built.map(({ anchor, place, number, title, age, row }, at) => {
    const moved = titleLine[at].flatMap((node, index) =>
      JSON.stringify(before[at][index]) === JSON.stringify(after[at][index])
        ? []
        : [[node.className.baseVal ?? node.className, before[at][index], after[at][index]]],
    );
    const position = place.querySelector(".github-pull-stack-position");
    const p = position.getBoundingClientRect();
    const n = number.getBoundingClientRect();
    const box = anchor.getBoundingClientRect();
    const end = box.right - parseFloat(getComputedStyle(anchor).paddingRight) + 0.5;
    const metaBox = anchor.querySelector(".github-pulls-meta");
    const meta = metaBox.getBoundingClientRect();
    const by = anchor.querySelector(".github-pulls-by");
    const b = by.getBoundingClientRect();
    const t = title.getBoundingClientRect();
    return {
      number: row.number,
      moved,
      // Before the number, on its line, in its type: the same top in the same size.
      before: p.width > 0 && place.getBoundingClientRect().right <= n.left + 0.5 && Math.abs(p.top - n.top) < 0.5,
      // The number shows whole, inside the muted line's clip.
      whole: n.left >= meta.left - 0.5 && n.right <= meta.right + 0.5 && number.scrollWidth <= Math.ceil(n.width),
      // Nothing of the row ends past its padding box, and the pane does not scroll sideways.
      inside: [age, number, place].every((node) => node.getBoundingClientRect().right <= end) && nav.scrollWidth <= nav.clientWidth,
      cut: position.scrollWidth > position.clientWidth,
      grew: Math.round((box.height - heights[at]) * 100) / 100,
      height: Math.round(box.height * 100) / 100,
      // The number's line is one line of the number's type.
      oneLine: Math.abs(meta.height - parseFloat(getComputedStyle(metaBox).lineHeight)) < 0.5,
      // The title runs to the row's end, under the age.
      titleEnd: Math.abs(t.right - (end - 0.5)) < 0.5 && t.top > age.getBoundingClientRect().bottom - 0.5,
      // The author on the number's line, at its floor or wider, or off it, whole.
      author: b.top < meta.bottom - 0.5 ? (b.width + 0.5 >= parseFloat(getComputedStyle(by).minWidth) ? "shown" : "squeezed") : "off",
      authorWidth: Math.round(b.width * 10) / 10,
      authorFloor: getComputedStyle(by).minWidth,
      title: Math.round(t.width * 10) / 10,
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
// The shell's tooltip rule on three anchors, over its own stylesheet: a tip that is its
// button's whole text, the same tip on text cut short by an ellipsis, and a glyph-only
// control's name. tipAddsInformation and the two it calls are app.js's own, read from the
// served file, as RUN_BADGE reads its functions: whether each tip would show (mb-8mpo,
// docs/design-system.md, "Tooltips Add Information").
const TIPS = `(async () => {
  const source = await new Promise((resolve, reject) => {
    const request = new XMLHttpRequest();
    request.open("GET", "/static/app.js");
    request.onload = () => resolve(request.responseText);
    request.onerror = reject;
    request.send();
  });
  const take = (start) => {
    const at = source.indexOf(start);
    if (at < 0) {
      throw new Error("app.js has no " + start);
    }
    return source.slice(at, source.indexOf("\\n}\\n", at) + 3);
  };
  const code = [
    take("function tipComparable(text) {"),
    take("function tipAnchorIsCut(anchor) {"),
    take("function tipAddsInformation(anchor) {"),
  ].join("\\n");
  const tipAddsInformation = new Function(code + "\\nreturn tipAddsInformation;")();
  const h = (tag, attributes = {}, children = []) => {
    const node = document.createElement(tag);
    for (const [key, value] of Object.entries(attributes)) node.setAttribute(key, value);
    node.append(...children);
    return node;
  };
  const long = "A pull request title far longer than the box it is drawn in";
  const anchors = {
    whole: h("button", { type: "button", "data-tip-text": "Reload" }, ["Reload"]),
    wholeSpaced: h("span", { "data-tip-text": "stack #286" }, ["  Stack   #286 "]),
    cut: h("span", { "data-tip-text": long, style: "display: block; width: 80px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap" }, [long]),
    glyph: h("button", { type: "button", "data-tip-text": "Copy path", "aria-label": "Copy path" }, ["↑"]),
  };
  document.getElementById("preview-pane").replaceChildren(...Object.values(anchors));
  return Object.fromEntries(Object.entries(anchors).map(([name, anchor]) => [name, tipAddsInformation(anchor)]));
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
// The file header of a run's log: renderBadges, RUN_STATUS_SIZERS, and flagRunEndedBadge
// are app.js's own, read from the served file and run here with the two names they use.
// The header is the one renderFile draws around them: the path, the badges, the size, and
// the print button's held slot. A live run ends, and a running one turns live, as app.js
// changes them in place (flagRunEndedBadge, and _mirrorActiveFromFsEntry's two lines), and
// every box of the header is read before and after.
const RUN_BADGE = `async (live, width) => {
  // Read with XMLHttpRequest: the header's measurements stand in for window.fetch.
  const source = await new Promise((resolve, reject) => {
    const request = new XMLHttpRequest();
    request.open("GET", "/static/app.js");
    request.onload = () => resolve(request.responseText);
    request.onerror = reject;
    request.send();
  });
  const take = (start, end) => {
    const at = source.indexOf(start);
    if (at < 0) {
      throw new Error("app.js has no " + start);
    }
    return source.slice(at, source.indexOf(end, at) + end.length);
  };
  const code = [
    take("const RUN_STATUS_SIZERS = ", '.join("");'),
    take("function renderBadges(data) {", "\\n}\\n"),
    take("function flagRunEndedBadge() {", "\\n}\\n"),
  ].join("\\n");
  const esc = (text) => String(text).replace(/[&<>"]/g, (c) => "&#" + c.charCodeAt(0) + ";");
  const activeFiles = new Map(live ? [["logs/session.jsonl", {}]] : []);
  const app = new Function("esc", "activeFiles", code + "\\nreturn { renderBadges, flagRunEndedBadge };")(esc, activeFiles);
  const pane = document.getElementById("preview-pane");
  pane.style.width = width + "px";
  pane.innerHTML =
    '<div class="file-header" data-kbd-badge-anchor><span class="file-header-path folder-breadcrumb">logs/session.jsonl</span>' +
    app.renderBadges({ type: "jsonl", kind: "agent-log", path: "logs/session.jsonl", summary: { adapter: "claude", is_done: false } }) +
    '<span class="size file-header-size">1.2 MB</span><button class="icon-btn file-header-icon file-header-print" type="button" hidden></button></div>';
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
// The records whose status row draws an offer: to switch to the head, and to browse it.
const OFFER_RECORDS = [
  ["behind_head", {}],
  ["current", { pinBehind: true }],
  ["on_head", { checkoutAtHead: true }],
];
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
const PARTS = ["launch", ...Object.keys(HEADER_PARTS), "offers", "pulls", "badges", "labels"];
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
      const widths = PART === "all" ? WIDTHS : (HEADER_PARTS[PART] ?? []);
      for (const width of widths) {
        const seen = {};
        for (const [name, change] of RECORDS) {
          const label = `${name}${Object.keys(change).length ? ` ${Object.keys(change).join(" ")}` : ""}`;
          for (const tab of TABS) {
            // The author's row is the same on every tab, so its stack chip arrives on one: one
            // stack, and two for the records with an avatar, the longest rows.
            const measured = tab === "" ? { ...change, stackChip: change.avatar ? 2 : 1 } : change;
            const shape = await browser.evaluate(
              `(${MEASURE})(${JSON.stringify(name)}, ${JSON.stringify(measured)}, ${JSON.stringify(tab)}, ${width})`,
            );
            const where = `${width} px, ${label} ${tab || "conversation"}`;
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
              check(
                `${where}: a late stack chip moves nothing in the header`,
                shape.chipMoves.moved === null,
                JSON.stringify(shape.chipMoves.moved),
              );
              check(
                `${where}: a late stack chip shows whole`,
                shape.chipMoves.chipShown >= 0.99,
                String(shape.chipMoves.chipShown),
              );
              check(
                `${where}: the stack chip ends on the header's content edge`,
                Math.abs(shape.chipMoves.rightEdge) <= 0.5,
                String(shape.chipMoves.rightEdge),
              );
              check(
                `${where}: the stack chip and the sentence do not overlap`,
                shape.chipMoves.overlap <= 0.5,
                String(shape.chipMoves.overlap),
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
            seen[`${label} ${tab || "conversation"}`] = shape;
            if (shape.offers > 0) {
              offersDrawn.add(label);
            }
            if (shape.badgeOffset !== null) {
              check(
                `${where}: the state badge is centred on its row`,
                Math.abs(shape.badgeOffset) <= 1,
                String(shape.badgeOffset),
              );
            }
            if (shape.edges !== null) {
              const { iconLeft, textAfterIcon, gap, numberRight, numberOverSlot } = shape.edges;
              check(
                `${where}: the title's icon starts on the header's left edge, its text just after it`,
                Math.abs(iconLeft) <= 0.5 && Math.abs(textAfterIcon - gap) <= 1,
                JSON.stringify(shape.edges),
              );
              check(
                `${where}: the title's number ends on the header's right edge, over the stack slot's end`,
                Math.abs(numberRight) <= 0.5 &&
                  numberOverSlot !== null &&
                  Math.abs(numberOverSlot) <= 0.5,
                JSON.stringify(shape.edges),
              );
            }
            check(
              `${where}: the state row is as tall as the stack strut`,
              shape.strut !== null && Math.abs(shape.meta - shape.strut) <= 0.5,
              JSON.stringify({ meta: shape.meta, strut: shape.strut }),
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
          }
        }
        lap(`the header at ${width} px`);
        const reference = seen["absent conversation"];
        for (const [key, shape] of Object.entries(seen)) {
          check(
            `${width} px, ${key}: the header lays out to the empty record's height, row by row`,
            shape.header === reference.header &&
              shape.tabBar === reference.tabBar &&
              JSON.stringify(shape.rows) === JSON.stringify(reference.rows),
            JSON.stringify({ empty: reference, [key]: shape }),
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
          check(
            `${theme}: a header with labels of every color lays out to the empty record's height, row by row`,
            shape.header === empty.header &&
              shape.tabBar === empty.tabBar &&
              JSON.stringify(shape.rows) === JSON.stringify(empty.rows),
            JSON.stringify({ empty: empty.rows, labels: shape.rows }),
          );
        }
        lap("the labels in both themes");
      }
      if (runs("pulls")) {
        const tips = await browser.evaluate(TIPS);
        check(
          "a tip that is its element's whole text, in any case or spacing, does not show, and shows while the text is cut short",
          tips.whole === false && tips.wholeSpaced === false && tips.cut === true,
          JSON.stringify(tips),
        );
        check("a glyph-only control's tip shows", tips.glyph === true, JSON.stringify(tips));
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
          check(
            `${where}: a late stack place moves nothing else in its row: not the age, the chevron, the icon, or the title`,
            row.moved.length === 0,
            JSON.stringify(row.moved),
          );
          check(
            `${where}: the stack place sits before the number, on its line`,
            row.before,
            JSON.stringify(row),
          );
          check(`${where}: the number shows whole`, row.whole, JSON.stringify(row));
          check(
            `${where}: the place, the number, and the age end inside the row, and nothing scrolls sideways`,
            row.inside,
            JSON.stringify(row),
          );
          const oneStack = !PULLS.find((pull) => pull.number === row.number).stack.includes(" · ");
          check(
            `${where}: one stack's place shows whole`,
            !row.cut || !oneStack,
            JSON.stringify(row),
          );
          // The number's line is one line at every width, so the row is always two (mb-lkkt):
          // before, three stacks took a third line at 300 px and one stack at 180 px.
          check(
            `${where}: the number's line stays one line, and the row two`,
            row.oneLine && row.grew === 0,
            JSON.stringify(row),
          );
          check(
            `${where}: the title runs to the row's end, under the age`,
            row.titleEnd,
            JSON.stringify(row),
          );
          check(
            `${where}: the author shows at its floor or wider, or leaves the line whole`,
            row.author !== "squeezed",
            JSON.stringify(row),
          );
          check(
            `${where}: the title keeps a share of its line`,
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
          "both offers are drawn by the records that carry them",
          offersDrawn.has("behind_head") &&
            offersDrawn.has("current pinBehind") &&
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

// The pull request header's box, laid out by a real engine: the production page module
// and its stylesheets, mounted on recorded records in headless Chrome.
//
//   CHROME_BIN=/path/to/chrome KPRESS_STATIC=/dir/with/css/and/fonts \
//     node tests/dom/github-pull-header-chrome.mjs [--part NAME]
//
// The session runs in parts, each its own browser and its own pytest case with its own
// bound, since all of it ran past one test's 45 s on a CI runner. `launch` starts Chrome,
// loads the page, and loads every face it declares, and nothing else, so the first Chrome
// start of a CI job, the slowest there, has a case of its own. Then the header at its widest
// two widths, its middle two, and its narrowest two (`header-wide`, `header-middle`,
// `header-narrow`), the offers the status row draws (`offers`), the Pulls rows (`pulls`),
// and the run badge (`badges`). With no part it runs every one. Each part writes how long
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
// The session also lays out Pulls rows as their stack positions arrive, and the file
// header as a run's status badge changes its label in place (RUN_BADGE below).
import fs from "node:fs";
import http from "node:http";
import path from "node:path";
import { launchChrome } from "./chrome-session.mjs";

const root = path.resolve(import.meta.dirname, "../..");
const STATIC = path.join(root, "src/metabrowser/static");
const GITHUB = path.join(root, "src/metabrowser/builtin_plugins/github");
const FIXTURES = path.join(root, "tests/fixtures/github-pull-page-responses.json");
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
<script>
  window.METABROWSER_SETTINGS = { SYNTAX_HIGHLIGHT_MAX_BYTES: 524288, SYNTAX_LANGUAGE_BY_BASENAME: {}, SYNTAX_LANGUAGE_BY_EXTENSION: {} };
  window.MetabrowserIcons = { copy: '<svg data-icon="copy"></svg>' };
</script>
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
  if (change.lastRefresh) {
    body.state = "stale";
    body.last_refresh = change.lastRefresh;
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
      ensureKindAssets: async () => {},
      decorateExternalLink: mb.decorateExternalLink,
      refChip: mb.refChip,
      refChipHtml: mb.refChipHtml,
      mergeRefs: mb.mergeRefs,
      mountRefCopies: mb.mountRefCopies,
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
  const group = header.querySelector(".github-pull-meta .merge-refs");
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
  // A stack's chip arrives late, from its own answer, through the page's own builder.
  let chipMoves = null;
  if (change.stackChip && group) {
    const before = places();
    const menu = page.createStackMenu(
      { number: 286, pulls: [body.number - 1, body.number, body.number + 1] },
      body.number,
      { link: () => document.createElement("a"), icon: null, currentTitle: "", onOpen() {} },
    );
    header.querySelector(".github-pull-stacks").replaceChildren(menu.element);
    await frames();
    const after = places();
    chipMoves = {
      moved: JSON.stringify(before) === JSON.stringify(after) ? null : { before, after },
      chipShown: shown(menu.element),
    };
  }
  const rows = [...header.children].map((row) => ({
    row: row.tagName === "H1" ? "title" : [...row.classList].find((c) => c.startsWith("github-pull-")).slice(12),
    height: Math.round(box(row).height * 100) / 100,
  }));
  const meta = header.querySelector(".github-pull-meta");
  const badge = meta?.querySelector(".github-pull-badge");
  const strut = meta?.querySelector(".github-pull-stack-strut");
  const centre = (r) => r.top + r.height / 2;
  const result = {
    header: Math.round(box(header).height * 100) / 100,
    tabBar: Math.round(box(container.querySelector(".tab-bar")).top - box(header).top),
    rows,
    meta: meta ? Math.round(box(meta).height * 100) / 100 : null,
    strut: strut ? Math.round(box(strut).height * 100) / 100 : null,
    badgeOffset: badge ? Math.round((centre(box(badge)) - centre(box(meta))) * 100) / 100 : null,
    offers: header.querySelectorAll(".github-pull-offer").length,
    mergeShown,
    chipMoves,
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
  };
  handle.dispose();
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
  ["current", { longNames: true }],
  ["current", { longNames: true, avatar: true }],
  ["merged", { longNames: true, avatar: true }],
];
// Pulls rows built as pulls-panel.js#buildRow and #rowMeta build them, whose order
// github-pulls-panel-session.js pins: the toggle, the state icon, the title, the stack
// position, the age, and the muted line. Every row's parts are read before and after each
// row's stack position arrives, and only the title's width may change, where it is cut.
const PULLS_ROWS = `async (rows, width) => {
  const page = window.__page ??= await import("/github/pull-page.js");
  const state = window.__state ??= await import("/github/pull-state.js");
  const mb = window.metabrowser;
  const h = (tag, attributes = {}, children = []) => {
    const node = document.createElement(tag);
    for (const [key, value] of Object.entries(attributes)) node.setAttribute(key, value);
    node.append(...children);
    return node;
  };
  const nav = document.createElement("div");
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
    const stack = h("span", { class: "github-pulls-stack", role: "img", hidden: "" });
    const title = h("span", { class: "github-pulls-title" }, [row.title]);
    const anchor = h("a", { class: "github-pulls-row collapsed", href: "#", role: "treeitem" }, [
      h("span", { class: "github-pulls-toggle", "aria-hidden": "true" }),
      state.pullStateIcon("open"),
      title,
      stack,
      h("span", { class: "github-pulls-age" }, ["12mo"]),
      h("span", { class: "github-pulls-meta" }, [
        h("span", { class: "github-pulls-line" }, [
          h("span", { class: "github-pulls-number" }, ["#" + row.number]),
          h("span", { class: "github-pulls-by" }, [separator(), identity]),
          h("span", { class: "github-pulls-merge" }, [
            separator(),
            mb.mergeRefs({ name: row.head, label: row.headLabel }, { name: row.base }, { kind: "remote", copy: "sibling" }),
          ]),
        ]),
      ]),
    ]);
    list.append(h("li", { class: "github-pulls-item", role: "none" }, [anchor]));
    return { anchor, stack, title, row };
  });
  await document.fonts.ready;
  const frames = () => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
  await frames();
  // Each row's own boxes and all it holds but the position itself, read as they were drawn.
  const watched = built.map(({ anchor, stack }) =>
    [anchor, ...anchor.querySelectorAll("*")].filter((node) => node !== stack),
  );
  const read = () =>
    built.map(({ title }, at) =>
      watched[at].map((node) => {
        const r = node.getBoundingClientRect();
        // The title's width is where it is cut, which the position's arrival may change.
        return [r.left, r.top, node === title ? 0 : r.width, r.height].map((value) => Math.round(value * 100) / 100);
      }),
    );
  const before = read();
  for (const { stack, row } of built) {
    stack.hidden = false;
    stack.append(
      h("span", { class: "github-pull-stack-icon", "aria-hidden": "true" }),
      h("span", { class: "github-pull-stack-position" }, [row.stack]),
    );
  }
  await frames();
  const after = read();
  return built.map(({ anchor, stack, title, row }, at) => {
    const moved = watched[at].flatMap((node, index) =>
      JSON.stringify(before[at][index]) === JSON.stringify(after[at][index])
        ? []
        : [[node.className || node.tagName, before[at][index], after[at][index]]],
    );
    const s = stack.getBoundingClientRect();
    return {
      number: row.number,
      moved,
      between: s.width > 0 && s.left >= title.getBoundingClientRect().right - 0.5 && s.right <= anchor.querySelector(".github-pulls-age").getBoundingClientRect().left + 0.5,
      // Nothing of the row ends past its padding box, and the pane does not scroll sideways.
      inside:
        [...anchor.querySelectorAll(".github-pulls-age, .github-pulls-stack")].every(
          (node) => node.getBoundingClientRect().right <= anchor.getBoundingClientRect().right - parseFloat(getComputedStyle(anchor).paddingRight) + 0.5,
        ) && nav.scrollWidth <= nav.clientWidth,
      title: Math.round(title.getBoundingClientRect().width * 10) / 10,
    };
  });
}`;
const PULLS = [
  {
    number: 370,
    title: "perf: decide every region's box at first paint",
    author: "jlevy",
    avatar: true,
    head: "claude/perf-layout",
    headLabel: "claude/perf-layout",
    base: "main",
    stack: "2/3",
  },
  {
    number: 12345,
    title: "A five-digit pull request",
    author: "a-thirty-nine-character-github-login-x",
    avatar: true,
    head: "feature/some-long-branch",
    headLabel: "fork:feature/some-long-branch",
    base: "release/2026-11",
    stack: "3/3 · 1/2",
  },
  {
    number: 7,
    title: "Short",
    author: "octo",
    avatar: false,
    head: "wip",
    headLabel: "wip",
    base: "topic",
    stack: "1/2",
  },
  // Wider than half of what the title and the position share in a 180 px pane: cut short.
  {
    number: 4242,
    title: "Two stacks, two digits each",
    author: "octo",
    avatar: true,
    head: "stack/part",
    headLabel: "stack/part",
    base: "main",
    stack: "12/23 · 10/14",
  },
  {
    number: 4243,
    title: "Three stacks",
    author: "octo",
    avatar: false,
    head: "x",
    headLabel: "x",
    base: "main",
    stack: "3/3 · 1/2 · 4/7",
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
const PARTS = ["launch", ...Object.keys(HEADER_PARTS), "offers", "pulls", "badges"];
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
  const server = await serve();
  try {
    const browser = await launchChrome(bin);
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
            // The state row is the same on every tab, so its stack chip arrives on one.
            const measured = tab === "" ? { ...change, stackChip: true } : change;
            const shape = await browser.evaluate(
              `(${MEASURE})(${JSON.stringify(name)}, ${JSON.stringify(measured)}, ${JSON.stringify(tab)}, ${width})`,
            );
            const where = `${width} px, ${label} ${tab || "conversation"}`;
            if (shape.mergeShown !== null) {
              check(
                `${where}: the merge's chips and arrow show whole in the state row`,
                shape.mergeShown >= 0.99,
                String(shape.mergeShown),
              );
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
      for (const width of runs("pulls") ? PULLS_WIDTHS : []) {
        const rows = await browser.evaluate(`(${PULLS_ROWS})(${JSON.stringify(PULLS)}, ${width})`);
        for (const row of rows) {
          const where = `${width} px, Pulls row #${row.number}`;
          check(
            `${where}: a late stack position moves nothing, here or below`,
            row.moved.length === 0,
            JSON.stringify(row.moved),
          );
          check(
            `${where}: the stack position sits between the title and the age`,
            row.between,
            JSON.stringify(row),
          );
          check(
            `${where}: the position and the age end inside the row, and nothing scrolls sideways`,
            row.inside,
            JSON.stringify(row),
          );
          check(
            `${where}: the title keeps a share of its line`,
            row.title >= 20,
            JSON.stringify(row),
          );
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

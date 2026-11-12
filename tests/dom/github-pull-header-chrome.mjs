// The pull request header's box, laid out by a real engine: the production page module
// and its stylesheets, mounted on recorded records in headless Chrome.
//
//   CHROME_BIN=/path/to/chrome KPRESS_STATIC=/dir/with/css/and/fonts \
//     node tests/dom/github-pull-header-chrome.mjs
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
  await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
  const header = container.querySelector(".github-pull-header");
  const box = (node) => node?.getBoundingClientRect();
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
];
const TABS = ["", "files", "checks"];
const WIDTHS = [980, 760, 560, 420, 360];

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
    try {
      await browser.send("Page.enable");
      await browser.send("Page.navigate", { url: `http://127.0.0.1:${server.address().port}/` });
      await browser.waitFor(
        `document.readyState === "complete" && Boolean(window.metabrowser?.refChip)`,
      );
      const offersDrawn = new Set();
      for (const width of WIDTHS) {
        const seen = {};
        for (const [name, change] of RECORDS) {
          const label = `${name}${Object.keys(change).length ? ` ${Object.keys(change).join(" ")}` : ""}`;
          for (const tab of TABS) {
            const shape = await browser.evaluate(
              `(${MEASURE})(${JSON.stringify(name)}, ${JSON.stringify(change)}, ${JSON.stringify(tab)}, ${width})`,
            );
            const where = `${width} px, ${label} ${tab || "conversation"}`;
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
      check(
        "both offers are drawn by the records that carry them",
        offersDrawn.has("behind_head") &&
          offersDrawn.has("current pinBehind") &&
          offersDrawn.has("on_head checkoutAtHead"),
        JSON.stringify([...offersDrawn]),
      );
    } finally {
      await browser.close();
    }
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
      console.log(`pull header in Chrome: ${checks} checks passed`);
    }
  });

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
// empty one (PR 370 review A3). The row structure itself is pinned browserless in
// github-pull-page-mount-behavior.js.
import { spawn } from "node:child_process";
import fs from "node:fs";
import http from "node:http";
import os from "node:os";
import path from "node:path";

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

async function launch(bin) {
  const profile = fs.mkdtempSync(path.join(os.tmpdir(), "mb-pull-header-"));
  const chrome = spawn(
    bin,
    [
      "--headless=new",
      "--remote-debugging-port=0",
      "--no-first-run",
      "--no-default-browser-check",
      "--force-device-scale-factor=1",
      "--window-size=1280,900",
      `--user-data-dir=${profile}`,
      "about:blank",
    ],
    { stdio: ["ignore", "ignore", "pipe"] },
  );
  chrome.stderr.on("data", () => {});
  const portFile = path.join(profile, "DevToolsActivePort");
  for (let attempt = 0; attempt < 200 && !fs.existsSync(portFile); attempt += 1) {
    await new Promise((resolve) => setTimeout(resolve, 50));
  }
  const port = fs.readFileSync(portFile, "utf8").split("\n")[0];
  const targets = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();
  const socket = new WebSocket(
    targets.find((target) => target.type === "page").webSocketDebuggerUrl,
  );
  await new Promise((resolve, reject) => {
    socket.onopen = resolve;
    socket.onerror = reject;
  });
  let next = 0;
  const pending = new Map();
  socket.onmessage = (event) => {
    const message = JSON.parse(event.data);
    pending.get(message.id)?.(message);
    pending.delete(message.id);
  };
  const send = (method, params = {}) =>
    new Promise((resolve, reject) => {
      next += 1;
      pending.set(next, (message) =>
        message.error
          ? reject(new Error(`${method}: ${message.error.message}`))
          : resolve(message.result),
      );
      socket.send(JSON.stringify({ id: next, method, params }));
    });
  const evaluate = async (expression) => {
    const result = await send("Runtime.evaluate", {
      expression,
      awaitPromise: true,
      returnByValue: true,
    });
    if (result.exceptionDetails) {
      throw new Error(JSON.stringify(result.exceptionDetails).slice(0, 800));
    }
    return result.result.value;
  };
  const close = () => {
    socket.close();
    chrome.kill();
    fs.rmSync(profile, { force: true, recursive: true });
  };
  return { close, evaluate, send };
}

// In the page: mount one record on one tab in a pane of one width and read the header's
// rows. The page's API is the one github-pull-page-mount-behavior.js mounts with, its ref
// helpers the production SDK's, and every request it makes answers 304.
const MEASURE = `async (name, tab, width) => {
  const recorded = window.__recorded ??= await (await fetch("/fixtures.json")).json();
  const page = window.__page ??= await import("/github/pull-page.js");
  const body = structuredClone(recorded[name].body);
  for (const envelope of [body, body.pull]) {
    const holder = envelope?.record?.same_as;
    if (holder !== undefined) {
      envelope.record = recorded[holder].body.record;
    }
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
  };
  handle.dispose();
  return result;
}`;

// A record that has not arrived, records still loading, loaded, merged, closed, stale, and
// with the checkout on its head. A failure is let wrap its status row (review A6), so it
// is not among them.
const RECORDS = ["absent", "pending", "current", "merged", "closed", "stale", "on_head"];
const TABS = ["", "files", "checks"];
const WIDTHS = [960, 560];

async function main() {
  const bin = process.env.CHROME_BIN;
  if (!bin) {
    throw new Error("CHROME_BIN names no Chrome");
  }
  if (!KPRESS || !fs.existsSync(path.join(KPRESS, "css/style-tokens.css"))) {
    throw new Error("KPRESS_STATIC holds no css/style-tokens.css");
  }
  const server = await serve();
  const browser = await launch(bin);
  try {
    await browser.send("Page.enable");
    await browser.send("Page.navigate", { url: `http://127.0.0.1:${server.address().port}/` });
    for (let attempt = 0; attempt < 100; attempt += 1) {
      if (
        await browser.evaluate(
          `document.readyState === "complete" && Boolean(window.metabrowser?.refChip)`,
        )
      ) {
        break;
      }
      await new Promise((resolve) => setTimeout(resolve, 50));
    }
    for (const width of WIDTHS) {
      const seen = {};
      for (const name of RECORDS) {
        for (const tab of TABS) {
          const shape = await browser.evaluate(
            `(${MEASURE})(${JSON.stringify(name)}, ${JSON.stringify(tab)}, ${width})`,
          );
          seen[`${name} ${tab || "conversation"}`] = shape;
          if (shape.badgeOffset !== null) {
            check(
              `${width} px, ${name} ${tab || "conversation"}: the state badge is centred on its row`,
              Math.abs(shape.badgeOffset) <= 1,
              String(shape.badgeOffset),
            );
          }
          check(
            `${width} px, ${name} ${tab || "conversation"}: the state row is as tall as the stack strut`,
            shape.strut !== null && Math.abs(shape.meta - shape.strut) <= 0.5,
            JSON.stringify({ meta: shape.meta, strut: shape.strut }),
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
  } finally {
    browser.close();
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

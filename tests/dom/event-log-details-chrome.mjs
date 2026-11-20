// A Diff summary that never arrives, in headless Chrome: the page says so at the late
// threshold, offers Details a keyboard reaches and opens, and reports the wait to the
// event log, and its end as never completed when the page is left (mb-9zp5).
//
//   CHROME_BIN=/path/to/chrome CHROME_PROFILES=/dir/the/caller/removes \
//     KPRESS_STATIC=/dir/with/style-tokens.css \
//     node tests/dom/event-log-details-chrome.mjs
//
// The page is the production pull request page (builtin_plugins/github/pull-page.js) with
// the shell's stylesheets and SDK, mounted on a recorded record whose comparison read never
// answers: the stand-in for a refresh job that never ends. The reporter
// (static/event-reports.js) arrives as the page asks for it, as an on-demand bundle does,
// and wraps the real `fetch`. This server answers what the page asks: the event log's
// routes with a job still running under one of the page's requests, and
// POST /api/event-log/client, whose bodies it keeps. So what is checked here is the real
// browser's: the header on each request, the late line and its Details painted and reached
// by the keyboard, the panel's tokens, and the report that leaves with the page when it is
// navigated away, which only `keepalive` delivers.
//
// The same behavior runs browserless in tests/dom/github-pull-page-mount-behavior.js
// (`eventLogDetails`) and tests/dom/event-reports-session.js. Prints one line of checks.
import fs from "node:fs";
import http from "node:http";
import path from "node:path";
import { launchChrome } from "./chrome-session.mjs";

const root = path.resolve(import.meta.dirname, "../..");
const STATIC = path.join(root, "src/metabrowser/static");
const GITHUB = path.join(root, "src/metabrowser/builtin_plugins/github");
const DIFF = path.join(root, "src/metabrowser/builtin_plugins/diff");
const FIXTURES = path.join(root, "tests/fixtures/github-pull-page-responses.json");
const KPRESS = process.env.KPRESS_STATIC ? path.resolve(process.env.KPRESS_STATIC) : null;
// The late threshold here: short, so the session is quick; the server's is
// event_log_reports.WAIT_LATE_MS.
const LATE_MS = 600;
const failures = [];
let checks = 0;
const check = (label, ok, detail = "") => {
  checks += 1;
  if (!ok) {
    failures.push(
      `${label}${detail ? `: ${typeof detail === "string" ? detail : JSON.stringify(detail)}` : ""}`,
    );
  }
};
const began = Date.now();
const step = (name) =>
  process.stderr.write(`${((Date.now() - began) / 1000).toFixed(1)} s ${name}\n`);

const SETTINGS = {
  log: true,
  route: "/api/event-log/client",
  header: "x-metabrowser-client",
  slow_ms: 2000,
  freeze_ms: 500,
  late_ms: LATE_MS,
  flush_ms: 200,
  max_batch: 20,
  per_minute: 30,
  long_lived: ["/api/events", "/api/tail", "/api/stream"],
  failure_window_s: 3600,
};
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
const PAGE = `<!doctype html><html><head><meta charset="utf-8"><title>event log details</title>
${KPRESS ? '<link rel="stylesheet" href="/kpress/css/style-tokens.css">' : ""}
<link rel="stylesheet" href="/static/styles.css">
<link rel="stylesheet" href="/github/styles.css">
<link rel="stylesheet" href="/diff/styles.css">
<script>
  window.METABROWSER_SETTINGS = { SYNTAX_HIGHLIGHT_MAX_BYTES: 524288, SYNTAX_LANGUAGE_BY_BASENAME: {}, SYNTAX_LANGUAGE_BY_EXTENSION: {}, EVENT_REPORTS: ${JSON.stringify(SETTINGS)} };
  window.MetabrowserIcons = { copy: '<svg data-icon="copy"></svg>' };
</script>
<script src="/static/changed-files-tree.js"></script>
${SDK.map((name) => `<script src="/static/${name}"></script>`).join("\n")}
</head><body><div id="preview-pane" class="preview-pane" style="width: 760px"></div></body></html>`;

const TYPES = {
  ".css": "text/css",
  ".js": "text/javascript",
  ".json": "application/json",
  ".woff2": "font/woff2",
};
// What the server saw: each request to /api/ with its client header, and each report body.
const seen = { requests: [], reports: [] };

/** The event log's answers for *client*: its job still running, and GitHub unreachable. */
function answer(url) {
  const client = url.searchParams.get("client") ?? "";
  if (url.pathname === "/api/event-log/failures") {
    return {
      state: "present",
      since: url.searchParams.get("since"),
      failures: 1,
      causes: [
        {
          cause: "connect_timeout",
          count: 1,
          last: "2026-11-19T21:41:10.502Z",
          message:
            "GitHub could not be reached because the connection to api.github.com at 20.172.24.160 timed out",
          addresses: ["20.172.24.160"],
          examples: [
            {
              ts: "2026-11-19T21:41:10.502Z",
              kind: "subprocess",
              name: "gh api",
              outcome: "timeout",
              dur_ms: 15011.9,
            },
          ],
        },
      ],
      probe: null,
    };
  }
  return {
    state: "present",
    open: [{ kind: "job", name: "checkout._pull_job", age_ms: 61004, client: `${client}-3` }],
    events: seen.reports
      .filter((body) => body.page === client)
      .flatMap((body) => body.reports)
      .map((report) => ({
        ...report,
        kind: "browser",
        name: `${report.type} ${report.name}`,
        ts: "2026-11-19T21:41:30.000Z",
      }))
      .reverse(),
  };
}

function serve() {
  const server = http.createServer((request, response) => {
    const url = new URL(request.url, "http://localhost");
    if (url.pathname.startsWith("/api/")) {
      seen.requests.push({
        method: request.method,
        path: url.pathname,
        client: request.headers["x-metabrowser-client"] ?? null,
        type: request.headers["content-type"] ?? null,
      });
      if (url.pathname === SETTINGS.route && request.method === "POST") {
        let body = "";
        request.on("data", (chunk) => {
          body += chunk;
        });
        request.on("end", () => {
          seen.reports.push(JSON.parse(body));
          response.writeHead(200, { "content-type": "application/json" });
          response.end("{}");
        });
        return;
      }
      if (url.pathname.startsWith("/api/event-log")) {
        response.writeHead(200, { "content-type": "application/json" });
        response.end(JSON.stringify(answer(url)));
        return;
      }
      response.writeHead(304);
      response.end();
      return;
    }
    if (
      url.pathname === "/" ||
      url.pathname.startsWith("/pull/") ||
      url.pathname === "/elsewhere"
    ) {
      response.writeHead(200, { "content-type": "text/html" });
      response.end(
        url.pathname === "/elsewhere" ? "<!doctype html><title>elsewhere</title>" : PAGE,
      );
      return;
    }
    let file = null;
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

// In the page: the recorded record, mounted on Conversation, whose comparison read never
// answers. The SDK is the production one; the reporter is loaded when the page asks for it.
const MOUNT = `(async () => {
  const recorded = await (await fetch("/fixtures.json")).json();
  const page = await import("/github/pull-page.js");
  const body = structuredClone(recorded.current.body);
  body.comparison_route = "/never-answers";
  const sdk = Object.create(window.metabrowser);
  Object.assign(sdk, {
    perf: { measure: (_label, work) => work(), measureAsync: (_label, work) => work() },
    ensureAsset: (name) =>
      name !== "event-reports"
        ? Promise.resolve()
        : (window.__reporterLoad ??= new Promise((resolve, reject) => {
            const script = document.createElement("script");
            script.src = "/static/event-reports.js";
            script.onload = resolve;
            script.onerror = reject;
            document.head.append(script);
          })),
    ensureKindAssets: async () => {},
    loadChangedFilesTree: async () => window.MetabrowserChangedFilesTree,
    getRegisteredView: () => ({ prefetch: () => new Promise(() => {}) }),
    formatAge: () => ({ label: "now", className: "age" }),
    formatTimestamp: (seconds) => new Date(seconds * 1000).toISOString(),
    navigation: { href: () => "/view/", async open() {} },
    sourceKind: () => "filesystem",
    icons: { toggle: "" },
  });
  const container = document.createElement("div");
  document.getElementById("preview-pane").replaceChildren(container);
  window.__handle = page.mountPullPage(
    container,
    { number: body.number, tab: "", reader: { initial: { etag: null, body }, fetchAfterMs: 600000 } },
    sdk,
  );
  return body.number;
})()`;

const READ = `(() => {
  const late = document.querySelector(".github-pull-summary-late");
  const button = late?.querySelector(".github-pull-details-toggle") ?? null;
  const panel = document.querySelector(".event-log-details");
  const box = (node) => node ? node.getBoundingClientRect() : null;
  return {
    late: late?.textContent ?? null,
    lateRole: late?.getAttribute("role") ?? null,
    lateShown: Boolean(late && box(late).height > 0),
    button: button ? { text: button.textContent, expanded: button.getAttribute("aria-expanded"), controls: button.getAttribute("aria-controls"), focused: document.activeElement === button, tabIndex: button.tabIndex } : null,
    panel: panel ? {
      id: panel.id,
      role: panel.getAttribute("role"),
      label: panel.getAttribute("aria-label"),
      lastInHeader: panel.parentElement?.lastElementChild === panel && panel.parentElement.classList.contains("github-pull-header"),
      headings: [...panel.querySelectorAll(".event-log-details-heading")].map((node) => node.textContent),
      items: [...panel.querySelectorAll(".event-log-details-items li")].map((node) => node.textContent),
      links: [...panel.querySelectorAll("a")].map((node) => [node.textContent, node.getAttribute("href"), node.target, node.rel]),
      note: panel.querySelector(".event-log-details-note")?.textContent ?? null,
      shown: box(panel).height > 0,
    } : null,
    page: window.metabrowser.eventReports?.page ?? null,
  };
})()`;

// The panel's colors are the design tokens': its rule's color is what --border resolves to.
const TOKENS = `(() => {
  const panel = document.querySelector(".event-log-details");
  const probe = document.createElement("span");
  probe.style.color = "var(--border)";
  document.body.append(probe);
  const border = getComputedStyle(probe).color;
  probe.style.color = "var(--link)";
  const link = getComputedStyle(probe).color;
  probe.remove();
  return {
    rule: getComputedStyle(panel).borderLeftColor,
    border,
    link: getComputedStyle(panel.querySelector("a")).color,
    linkToken: link,
  };
})()`;

/** Wait for *expression*, at most *ms*; whether it came true, so a check can say what was there. */
async function waitFor(chrome, expression, ms = 10000) {
  try {
    await chrome.waitFor(expression, ms);
    return true;
  } catch {
    return false;
  }
}

async function key(chrome, name, code, keyCode) {
  for (const type of ["keyDown", "keyUp"]) {
    await chrome.send("Input.dispatchKeyEvent", {
      type,
      key: name,
      code,
      windowsVirtualKeyCode: keyCode,
      ...(type === "keyDown" && name === "Enter" ? { text: "\r" } : {}),
    });
  }
}

const profiles = process.env.CHROME_PROFILES;
if (!process.env.CHROME_BIN || !profiles) {
  throw new Error("CHROME_BIN and CHROME_PROFILES are required");
}
const server = await serve();
const base = `http://127.0.0.1:${server.address().port}`;
const chrome = await launchChrome(process.env.CHROME_BIN, { profiles, width: 900, height: 900 });
step("launched");
try {
  await chrome.send("Page.enable");
  await chrome.send("Page.navigate", { url: `${base}/pull/7` });
  await chrome.waitFor("Boolean(window.metabrowser?.registerView)");
  const number = await chrome.evaluate(MOUNT);
  step("mounted");
  // Before the late threshold the placeholder pulses, and nothing is reported.
  const early = await chrome.evaluate(READ);
  check("before the threshold, no late line", early.late === null, early);
  await chrome.waitFor(`Boolean(document.querySelector(".github-pull-summary-late"))`, 10000);
  step("late");
  const late = await chrome.evaluate(READ);
  check(
    "the late line says how long",
    /^The summary of changes has not arrived after \d+ s\. Details$/.test(late.late ?? ""),
    late.late,
  );
  check("the late line is a status and shown", late.lateRole === "status" && late.lateShown, late);
  check(
    "Details is a closed button for the panel",
    late.button?.expanded === "false" &&
      late.button.controls === `github-pull-details-${number}` &&
      late.button.tabIndex === 0,
    late.button,
  );
  // The keyboard reaches Details: Tab, from the top of the page, lands on it.
  await chrome.evaluate("document.activeElement?.blur()");
  let tabs = 0;
  let reached = await chrome.evaluate(READ);
  while (!reached.button?.focused && tabs < 80) {
    await key(chrome, "Tab", "Tab", 9);
    tabs += 1;
    reached = await chrome.evaluate(READ);
  }
  check("Tab reaches Details", reached.button?.focused === true, { tabs, button: reached.button });
  const ring = await chrome.evaluate(
    `getComputedStyle(document.querySelector(".github-pull-details-toggle"), ":focus-visible") && document.querySelector(".github-pull-details-toggle").matches(":focus-visible")`,
  );
  check("the keyboard's focus is visible on it", ring === true);
  // Enter opens the panel, which reads this page's records and the failures.
  await key(chrome, "Enter", "Enter", 13);
  await waitFor(chrome, `Boolean(document.querySelector(".event-log-details-part"))`);
  step("details open");
  const open = await chrome.evaluate(READ);
  check("Enter opens Details", open.button?.expanded === "true", open.button);
  check(
    "the panel is a labelled region, the header's last row",
    open.panel?.role === "region" &&
      open.panel.label === "Event log details" &&
      open.panel.id === `github-pull-details-${number}` &&
      open.panel.lastInHeader &&
      open.panel.shown,
    open.panel,
  );
  check(
    "it shows the job still running under this page's request",
    open.panel?.headings[0] === "Still running" &&
      open.panel.items[0] === "checkout._pull_job · for 61.0 s",
    open.panel,
  );
  check(
    "and the failures by cause, with the address",
    open.panel?.headings.includes("connect timeout: 1 in the window") &&
      open.panel.items.includes("Addresses: 20.172.24.160"),
    open.panel,
  );
  check(
    "and the page's own late wait",
    open.panel?.headings.includes("This page's slow or unfinished work") &&
      open.panel.items.some((item) =>
        item.startsWith("wait githubPull:diffSummary · still running"),
      ),
    open.panel,
  );
  check(
    "with the records as JSON, in a new tab",
    open.panel?.links.length === 2 &&
      open.panel.links.every(
        ([, href, target, rel]) =>
          href.startsWith("/api/event-log") && target === "_blank" && rel === "noopener",
      ) &&
      open.panel.links[1][1] === `/api/event-log?client=${open.page}&limit=200`,
    open.panel?.links,
  );
  const tokens = open.panel === null ? null : await chrome.evaluate(TOKENS);
  check(
    "the panel's rule is the --border token",
    tokens !== null && tokens.rule === tokens.border,
    tokens,
  );
  check(
    "its links are the --link token",
    tokens !== null && tokens.link === tokens.linkToken,
    tokens,
  );
  // Enter again closes it, and focus stays on Details.
  await key(chrome, "Enter", "Enter", 13);
  const closed = await chrome.evaluate(READ);
  check(
    "Enter closes Details",
    closed.button?.expanded === "false" && closed.panel === null && closed.button.focused,
    closed,
  );
  // The page's requests carried its ID; the reports were the JSON the guard requires.
  const page = closed.page;
  const tagged = seen.requests.filter(
    (request) => request.path.startsWith("/api/event-log") && request.method === "GET",
  );
  check(
    "the Details' reads carry the page's request IDs",
    tagged.length === 2 && tagged.every((request) => request.client?.startsWith(`${page}-`)),
    tagged,
  );
  await chrome.waitFor(`true`);
  const reported = () =>
    seen.reports.flatMap((body) =>
      body.reports.map((report) =>
        `${report.type} ${report.event} ${report.name} ${report.outcome ?? ""}`.trim(),
      ),
    );
  check(
    "the wait was reported open at the threshold",
    reported().includes("wait open githubPull:diffSummary"),
    reported(),
  );
  check(
    "each report was a same-origin JSON POST",
    seen.requests
      .filter((request) => request.path === SETTINGS.route)
      .every(
        (request) =>
          request.method === "POST" &&
          request.type === "application/json" &&
          request.client === null,
      ),
    seen.requests.filter((request) => request.path === SETTINGS.route),
  );
  // Leaving the page ends the wait as never completed, and the report leaves with it.
  const before = seen.reports.length;
  await chrome.send("Page.navigate", { url: `${base}/elsewhere` });
  const deadline = Date.now() + 10000;
  while (seen.reports.length === before && Date.now() < deadline) {
    await new Promise((resolve) => setTimeout(resolve, 20));
  }
  step("left");
  const last = seen.reports.slice(before).flatMap((body) => body.reports);
  check(
    "leaving reports the wait never completed",
    last.some(
      (report) =>
        report.type === "wait" &&
        report.event === "end" &&
        report.outcome === "never_completed" &&
        report.name === "githubPull:diffSummary",
    ),
    last,
  );
  check(
    "from the page it left",
    seen.reports.at(-1)?.page === page && seen.reports.at(-1)?.path === `/pull/${number}`,
    seen.reports.at(-1),
  );
} finally {
  await chrome.close();
  server.close();
}
if (failures.length > 0) {
  process.stderr.write(`${failures.join("\n")}\n`);
  process.exitCode = 1;
} else {
  process.stdout.write(`event log details in Chrome: ${checks} checks passed\n`);
}

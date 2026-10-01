// Measure what a tab's earlier pages cost the page a reader is on, in stock Chrome.
//
// A page left by a full page load goes into the back/forward cache with its open
// requests. This loads a sequence of addresses as new documents in one tab, over the
// DevTools protocol, headless and with a throwaway profile, and reports for each page:
// the time until its preview and tree are in the page, the longest any of its requests
// waited before it was sent, the event streams the page's own script opened and
// closed, and the TCP connections open to the server, counted by lsof. Chrome is
// expected to be the server's only client.
//
//   node explorations/page-connections/measure.mjs <scenario> <origin> [options]
//
//   walk    --paths a,b,c   Load /view/<path> for each, by Page.navigate.
//   back    --paths a,b,c   The same walk, then Back through all of it. Reports each
//                           landing's pageshow, scroll position, requests, and what
//                           the restored page changed in its tree.
//   mirror  --commit <id>   On a served mirror: open /commit/<id>, then each round
//                           click a View file link and come Back.
//
//   --no-bfcache     Start Chrome with the back/forward cache off.
//   --netlog <file>  Write Chrome's net log, for net-log.mjs.
//   --away <ms>      How long to stay on the last page before Back (default 400).
//   --touch <file>   Create this file after the first Back: a live change the restored
//                    page's tree should show, and so should each page restored later.
//   --rounds <n>     Rounds of the mirror scenario (default 8).
//   --settle <ms>    How long each page is left to go quiet (default 600).
//   --profile <dir>  Chrome's profile directory (default: a new temporary one).
//   --chrome <path>  The Chrome binary.
//
// It prints a JSON report on stdout and a table of it on stderr.

import { execFileSync, spawn } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

const args = process.argv.slice(2);
function option(name, fallback) {
  const at = args.indexOf(name);
  if (at < 0) {
    return fallback;
  }
  const [, value] = args.splice(at, 2);
  return value;
}
function flag(name) {
  const at = args.indexOf(name);
  if (at < 0) {
    return false;
  }
  args.splice(at, 1);
  return true;
}
const noBfcache = flag("--no-bfcache");
const netlog = option("--netlog", "");
const profile = option("--profile", "") || fs.mkdtempSync(path.join(os.tmpdir(), "mb-pages-"));
const settleMs = Number(option("--settle", "600"));
const awayMs = Number(option("--away", "400"));
const rounds = Number(option("--rounds", "8"));
const label = option("--label", "");
const paths = option("--paths", "").split(",").filter(Boolean);
const commit = option("--commit", "");
const touch = option("--touch", "");
const chrome = option("--chrome", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome");
const [scenario, origin] = args;
if (!["walk", "back", "mirror"].includes(scenario) || !origin) {
  console.error("usage: measure.mjs <walk|back|mirror> <origin> [options]");
  process.exit(2);
}
const serverPort = new URL(origin).port;
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
const loadAverage = () => os.loadavg()[0].toFixed(0);

/** A DevTools protocol session over one WebSocket. */
function connect(url) {
  const socket = new WebSocket(url);
  const pending = new Map();
  const listeners = new Set();
  let next = 1;
  socket.addEventListener("message", (event) => {
    const message = JSON.parse(event.data);
    if (message.id !== undefined) {
      const waiter = pending.get(message.id);
      pending.delete(message.id);
      if (message.error) {
        waiter.reject(new Error(message.error.message));
      } else {
        waiter.resolve(message.result);
      }
      return;
    }
    for (const listener of listeners) {
      listener(message);
    }
  });
  return new Promise((resolve, reject) => {
    socket.addEventListener("error", () => reject(new Error("DevTools socket failed")));
    socket.addEventListener("open", () =>
      resolve({
        send(method, params = {}) {
          const id = next++;
          socket.send(JSON.stringify({ id, method, params }));
          return new Promise((res, rej) => pending.set(id, { resolve: res, reject: rej }));
        },
        on(listener) {
          listeners.add(listener);
        },
        close: () => socket.close(),
      }),
    );
  });
}

// Runs in every new document, before its own scripts. A page restored from the
// back/forward cache keeps its heap, so these records outlive the time it was away.
const PROBE = `(() => {
  window.__mbLifecycle = [];
  const note = (name, extra) => window.__mbLifecycle.push({ name, ...extra });
  addEventListener("pagehide", (event) => note("pagehide", { persisted: event.persisted }), true);
  addEventListener("pageshow", (event) => {
    const left = Number(sessionStorage.getItem("mb-left-at"));
    const entry = performance.getEntriesByType("navigation")[0];
    note("pageshow", {
      persisted: event.persisted,
      sinceBackMs: left ? Date.now() - left : null,
      notRestored: entry && entry.notRestoredReasons
        ? entry.notRestoredReasons.reasons.map((reason) => reason.reason) : null,
    });
    if (!event.persisted) {
      return;
    }
    // What the restored page changes once it is shown.
    const tree = document.getElementById("tree-pane");
    window.__mbAtShow = { tree: tree ? tree.innerHTML : null, page: document.body.innerHTML };
    window.__mbTreeMutations = 0;
    window.__mbLayoutShift = 0;
    if (tree) {
      new MutationObserver((records) => { window.__mbTreeMutations += records.length; })
        .observe(tree, { attributes: true, childList: true, subtree: true, characterData: true });
    }
    new PerformanceObserver((list) => {
      for (const item of list.getEntries()) { window.__mbLayoutShift += item.value; }
    }).observe({ type: "layout-shift" });
  }, true);
  document.addEventListener("visibilitychange",
    () => note("visibilitychange", { state: document.visibilityState }), true);
  document.addEventListener("freeze", () => note("freeze"), true);
  document.addEventListener("resume", () => note("resume"), true);
  // Every event stream the page's script opens, and whether the script closed it.
  window.__mbStreams = [];
  const Native = window.EventSource;
  window.EventSource = class extends Native {
    constructor(url, init) {
      super(url, init);
      const record = { url: String(url), closedByPage: false, events: 0, source: this };
      window.__mbStreams.push(record);
      for (const type of ["fs.snapshot", "fs.change", "catalog.change", "append"]) {
        this.addEventListener(type, () => { record.events += 1; });
      }
    }
    close() {
      const record = window.__mbStreams.find((item) => item.source === this);
      if (record) { record.closedByPage = true; }
      super.close();
    }
  };
})();`;

const READY = `(() => {
  const pane = document.getElementById("preview-pane");
  return document.readyState === "complete" && !!pane &&
    typeof pane.dataset.renderedPath === "string" &&
    !/Loading preview/.test(pane.textContent) &&
    document.querySelectorAll("#tree-pane .tree-item").length > 0;
})()`;
const STREAMS = `window.__mbStreams.map((item) =>
  new URL(item.url, location.href).pathname + " " +
  (item.closedByPage ? "closed" : ["connecting", "open", "closed"][item.source.readyState]) +
  ", " + item.events + " events")`;
const LIFECYCLE = `window.__mbLifecycle.map((item) => item.name +
  (item.persisted === undefined ? "" : " persisted=" + item.persisted) +
  (item.state ? " " + item.state : ""))`;
const SCROLLER = 'document.getElementById("preview-pane")';

/** Established TCP connections to the server's port, counted at their client end. */
function connectionsToServer() {
  let text = "";
  try {
    text = execFileSync("lsof", ["-nP", `-iTCP:${serverPort}`, "-sTCP:ESTABLISHED"], {
      stdio: ["ignore", "pipe", "ignore"],
    }).toString();
  } catch (error) {
    // lsof exits 1 when nothing matches.
    text = error.stdout ? error.stdout.toString() : "";
  }
  return text.split("\n").filter((line) => line.includes(`:${serverPort} (ESTABLISHED)`)).length;
}

async function main() {
  const flags = [
    "--headless=new",
    "--remote-debugging-port=0",
    `--user-data-dir=${profile}`,
    "--no-first-run",
    "--no-default-browser-check",
    "--window-size=1400,900",
    ...(noBfcache ? ["--disable-features=BackForwardCache"] : []),
    ...(netlog ? [`--log-net-log=${netlog}`, "--net-log-capture-mode=Default"] : []),
    "about:blank",
  ];
  fs.mkdirSync(profile, { recursive: true });
  const browser = spawn(chrome, flags, { stdio: "ignore" });
  try {
    const portFile = path.join(profile, "DevToolsActivePort");
    for (let tries = 0; !fs.existsSync(portFile); tries += 1) {
      if (tries > 600) {
        throw new Error("Chrome did not start");
      }
      await sleep(50);
    }
    const [port, browserPath] = fs.readFileSync(portFile, "utf8").split("\n");
    const version = await (await fetch(`http://127.0.0.1:${port}/json/version`)).json();
    const targets = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();
    const root = await connect(`ws://127.0.0.1:${port}${browserPath}`);
    const page = await connect(
      targets.find((target) => target.type === "page").webSocketDebuggerUrl,
    );

    /** requestId -> what the DevTools Network domain said of it. */
    const requests = new Map();
    const consoleErrors = [];
    const notUsed = [];
    let documents = 0;
    let sequence = 0;
    page.on((message) => {
      const p = message.params;
      if (message.method === "Network.requestWillBeSent") {
        if (p.type === "Document") {
          documents += 1;
        }
        sequence += 1;
        requests.set(p.requestId, {
          url: p.request.url.replace(origin, "").replace(/\?v=.*/, ""),
          seq: sequence,
          page: p.documentURL.replace(origin, ""),
          asked: p.timestamp,
          beforeSendMs: null,
        });
      } else if (message.method === "Network.responseReceived") {
        const record = requests.get(p.requestId);
        const timing = p.response.timing;
        if (record && timing && !p.response.fromDiskCache) {
          // From the page asking to the request leaving: the wait for a connection.
          record.beforeSendMs = Math.round(
            (timing.requestTime - record.asked) * 1000 + Math.max(0, timing.sendStart),
          );
        }
      } else if (message.method === "Runtime.consoleAPICalled" && p.type === "error") {
        consoleErrors.push(
          p.args
            .map((arg) => arg.value ?? arg.description ?? "")
            .join(" ")
            .slice(0, 200),
        );
      } else if (message.method === "Page.backForwardCacheNotUsed") {
        notUsed.push(p.notRestoredExplanations.map((item) => item.reason).join(","));
      }
    });
    await page.send("Page.enable");
    await page.send("Network.enable");
    await page.send("Runtime.enable");
    await page.send("Page.addScriptToEvaluateOnNewDocument", { source: PROBE });

    const evaluate = async (expression) => {
      const result = await Promise.race([
        page.send("Runtime.evaluate", { expression, awaitPromise: true, returnByValue: true }),
        sleep(5000).then(() => {
          throw new Error("the page did not answer in 5 s");
        }),
      ]);
      if (result.exceptionDetails) {
        throw new Error(result.exceptionDetails.exception?.description ?? "evaluation failed");
      }
      return result.result.value;
    };
    // 75 s: longer than Chrome keeps a cached page's open request, so a page that
    // waits for a connection is still seen to become ready.
    const until = async (expression) => {
      const started = Date.now();
      while (Date.now() - started < 75_000) {
        try {
          if (await evaluate(expression)) {
            return true;
          }
        } catch {
          // The document is being replaced; ask again.
        }
        await sleep(20);
      }
      return false;
    };
    const requestedSince = (mark) =>
      [...requests.values()].filter((record) => record.seq > mark).map((record) => record.url);
    /** The longest wait before sending among the requests of the page at *address*. */
    const waits = (address) => {
      const sent = [...requests.values()]
        .filter((record) => record.page === address && record.beforeSendMs !== null)
        .sort((a, b) => b.beforeSendMs - a.beforeSendMs);
      return {
        longestWaitMs: sent.length ? sent[0].beforeSendMs : 0,
        waitedOver100Ms: sent
          .filter((record) => record.beforeSendMs > 100)
          .map((record) => `${record.url} ${record.beforeSendMs}`),
      };
    };

    const report = {
      label,
      chrome: version.Browser,
      backForwardCache: !noBfcache,
      loadAverage: { start: loadAverage(), end: null },
      pages: [],
    };

    /** Load one address as a new document and report it. */
    const loadPage = async (address, how) => {
      const before = documents;
      const started = Date.now();
      await how();
      const ready = await until(
        `location.pathname + location.search === ${JSON.stringify(address)} && ${READY}`,
      );
      const readyMs = Date.now() - started;
      await sleep(settleMs);
      const scrolled =
        scenario === "back"
          ? await evaluate(
              `(() => { ${SCROLLER}.scrollTop = 120; return ${SCROLLER}.scrollTop; })()`,
            )
          : null;
      const step = {
        address,
        ready,
        readyMs,
        documents: documents - before,
        ...waits(address),
        scrolled,
        streams: await evaluate(STREAMS),
        connections: connectionsToServer(),
      };
      report.pages.push(step);
      return step;
    };
    /** Go Back to *address* and report the landing. */
    const goBack = async (address, readyExpression, left) => {
      const before = documents;
      const mark = sequence;
      await evaluate('sessionStorage.setItem("mb-left-at", String(Date.now())); history.back()');
      const landed = await until(
        `location.pathname === ${JSON.stringify(address)} && window.__mbLifecycle.some((item) => item.name === "pageshow" && item.sinceBackMs !== null) && ${readyExpression}`,
      );
      const shown = await evaluate(
        'window.__mbLifecycle.filter((item) => item.name === "pageshow").at(-1)',
      );
      if (left.touchNow) {
        fs.writeFileSync(touch, "a live change\n");
      }
      await sleep(settleMs);
      const landing = {
        address,
        landed,
        persisted: shown.persisted,
        backToPageshowMs: shown.sinceBackMs,
        notRestored: shown.notRestored,
        documents: documents - before,
        scroll: { left: left.scrolled, back: await evaluate(`${SCROLLER}?.scrollTop ?? null`) },
        requests: requestedSince(mark),
        streams: await evaluate(STREAMS),
        treeMutations: await evaluate("window.__mbTreeMutations ?? null"),
        layoutShift: await evaluate("window.__mbLayoutShift ?? null"),
        treeUnchanged: await evaluate(
          'window.__mbAtShow ? document.getElementById("tree-pane")?.innerHTML === window.__mbAtShow.tree : null',
        ),
        pageUnchanged: await evaluate(
          "window.__mbAtShow ? document.body.innerHTML === window.__mbAtShow.page : null",
        ),
        // On the first landing the file appears after the page is back; on the later
        // ones it appeared while the page was away.
        touchedRow: touch
          ? await evaluate(
              `!!document.querySelector('.tree-item[data-path="${path.basename(touch)}"]')`,
            )
          : null,
        lifecycle: await evaluate(LIFECYCLE),
        connections: connectionsToServer(),
      };
      await evaluate('sessionStorage.removeItem("mb-left-at")');
      return landing;
    };

    if (scenario === "walk" || scenario === "back") {
      for (const item of paths) {
        const address = `/view/${item}`;
        await loadPage(address, () => page.send("Page.navigate", { url: origin + address }));
      }
    }
    if (scenario === "back") {
      report.landings = [];
      await sleep(awayMs);
      for (let index = paths.length - 2; index >= 0; index -= 1) {
        report.landings.push(
          await goBack(`/view/${paths[index].split("?")[0]}`, READY, {
            scrolled: report.pages[index].scrolled,
            touchNow: touch !== "" && index === paths.length - 2,
          }),
        );
      }
    }
    if (scenario === "mirror") {
      const diffAddress = `/commit/${commit}`;
      const diffReady = 'document.querySelectorAll(".diff-file-bar").length > 0';
      await page.send("Page.navigate", { url: origin + diffAddress });
      await until(diffReady);
      await sleep(settleMs);
      report.landings = [];
      for (let round = 0; round < rounds; round += 1) {
        const links = await evaluate(
          'Array.from(document.querySelectorAll("a.diff-file-view"), (a) => a.getAttribute("href"))',
        );
        const href = links[round % links.length];
        await loadPage(href, () =>
          evaluate(
            `document.querySelector('a.diff-file-view[href=${JSON.stringify(href)}]').click()`,
          ),
        );
        await sleep(awayMs);
        report.landings.push(
          await goBack(diffAddress, diffReady, { scrolled: null, touchNow: false }),
        );
      }
    }
    report.consoleErrors = consoleErrors;
    report.backForwardCacheNotUsed = notUsed;
    report.loadAverage.end = loadAverage();
    console.log(JSON.stringify(report, null, 2));
    summarize(report);
    page.close();
    // A clean exit completes the net log. Chrome is given ten seconds for it; a log it
    // did not finish is still readable (net-log.mjs).
    root.send("Browser.close").catch(() => {});
    for (let tries = 0; browser.exitCode === null && tries < 100; tries += 1) {
      await sleep(100);
    }
    root.close();
  } finally {
    // The profile is thrown away, so a Chrome that has not left by now is not asked again.
    if (browser.exitCode === null) {
      browser.kill("SIGKILL");
    }
  }
}

/** Each distinct request with how many times it was made. */
function tally(urls) {
  const counts = new Map();
  for (const url of urls) {
    counts.set(url, (counts.get(url) ?? 0) + 1);
  }
  return [...counts].map(([url, count]) => (count > 1 ? `${url} x${count}` : url));
}

function summarize(report) {
  const out = (line) => process.stderr.write(`${line}\n`);
  out(
    `${report.label || scenario}: ${report.chrome}, back/forward cache ${report.backForwardCache ? "on" : "off"}, load average ${report.loadAverage.start} to ${report.loadAverage.end}`,
  );
  for (const step of report.pages) {
    out(
      `  ${step.address.padEnd(36)} ready ${String(step.ready ? step.readyMs : "never").padStart(6)} ms  longest wait ${String(step.longestWaitMs).padStart(6)} ms  connections ${step.connections}  streams [${step.streams.join("; ")}]`,
    );
  }
  for (const landing of report.landings ?? []) {
    out(
      `  Back to ${landing.address.slice(0, 28).padEnd(28)} persisted ${landing.persisted}  pageshow ${landing.backToPageshowMs} ms  documents ${landing.documents}  scroll ${landing.scroll.left} -> ${landing.scroll.back}  requests ${landing.documents > 0 ? `${landing.requests.length} (the page was loaded again)` : JSON.stringify(tally(landing.requests))}  streams [${landing.streams.join("; ")}]  tree mutations ${landing.treeMutations}, unchanged ${landing.treeUnchanged}, page unchanged ${landing.pageUnchanged}, layout shift ${landing.layoutShift}${landing.touchedRow === null ? "" : `  touched row shown ${landing.touchedRow}`}  connections ${landing.connections}`,
    );
  }
  if (report.consoleErrors.length) {
    out(`  console errors: ${JSON.stringify(report.consoleErrors)}`);
  }
  if (report.backForwardCacheNotUsed.length) {
    out(`  back/forward cache not used: ${JSON.stringify(report.backForwardCacheNotUsed)}`);
  }
}

main().then(
  () => process.exit(0),
  (error) => {
    console.error(error);
    process.exit(1);
  },
);

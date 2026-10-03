// Measure what Back does to a pin's page in stock Chrome, with and without a pin switch.
//
// A page on a pinned revision names the commit it was rendered for. Back brings it back
// from the back/forward cache, or loads it again from the HTTP cache, without asking
// the server, so after a pin switch it can name a commit the server stopped serving.
// static/source-pin-guard.js asks the status route once on such a landing and reloads
// if another commit is served. This drives an installed Chrome over the DevTools
// protocol, headless and with a throwaway profile, and prints:
//
// - unchanged: a diff, scrolled; View file (a link) to the file; Back. The page should
//   come back from the back/forward cache (`persisted`), at its scroll position, having
//   asked the status route once and not reloaded.
// - switched: the same diff; View at parent (a pin switch) to the file; Back. The page
//   should reload once and render the diff for the pin served now.
//
// Usage, against a server on a mirror whose pinned commit changes files:
//
//   node explorations/history-landing/measure.mjs <origin> <commit> [--no-bfcache]
//       [--chrome <binary>] [--profile <directory>] [--rounds <n>]
//
// `--no-bfcache` starts Chrome with the back/forward cache off, so Back loads the page
// from the HTTP cache instead: the path a browser takes when a page is not eligible.

import { spawn } from "node:child_process";
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
const noBfcache = args.includes("--no-bfcache");
if (noBfcache) {
  args.splice(args.indexOf("--no-bfcache"), 1);
}
const chrome = option("--chrome", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome");
const profile = option("--profile", fs.mkdtempSync(path.join(os.tmpdir(), "mb-history-")));
const rounds = Number(option("--rounds", "5"));
const [origin, commit] = args;
if (!origin || !commit) {
  console.error("usage: measure.mjs <origin> <commit> [--no-bfcache] [--chrome <binary>]");
  process.exit(2);
}

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

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
// back/forward cache keeps its heap, so these listeners see its `pageshow` too. The
// records live in sessionStorage, which outlasts a reload of the page.
const PROBE = `(() => {
  const save = (change) => {
    const landings = JSON.parse(sessionStorage.getItem("mb-landings") || "[]");
    change(landings);
    sessionStorage.setItem("mb-landings", JSON.stringify(landings));
  };
  addEventListener("pageshow", (event) => {
    const left = Number(sessionStorage.getItem("mb-left-at"));
    if (!left) {
      return;
    }
    const entry = performance.getEntriesByType("navigation")[0];
    let at = -1;
    save((landings) => {
      at = landings.length;
      landings.push({
        persisted: event.persisted,
        type: entry ? entry.type : null,
        pin: window.METABROWSER_SOURCE_PIN ? window.METABROWSER_SOURCE_PIN.pin.slice(0, 12) : null,
        pageshowMs: Date.now() - left,
        diffMs: null,
        notRestored:
          entry && entry.notRestoredReasons
            ? entry.notRestoredReasons.reasons.map((reason) => reason.reason)
            : null,
      });
    });
    const look = () => {
      if (document.querySelector(".diff-file-bar")) {
        save((landings) => {
          landings[at].diffMs = Date.now() - left;
        });
      } else {
        requestAnimationFrame(look);
      }
    };
    look();
  });
})();`;

async function main() {
  const flags = [
    "--headless=new",
    "--remote-debugging-port=0",
    `--user-data-dir=${profile}`,
    "--no-first-run",
    "--no-default-browser-check",
    "--window-size=1000,420",
    ...(noBfcache ? ["--disable-features=BackForwardCache"] : []),
    "about:blank",
  ];
  const browser = spawn(chrome, flags, { stdio: "ignore" });
  try {
    const portFile = path.join(profile, "DevToolsActivePort");
    for (let tries = 0; !fs.existsSync(portFile); tries += 1) {
      if (tries > 200) {
        throw new Error("Chrome did not start");
      }
      await sleep(50);
    }
    const port = fs.readFileSync(portFile, "utf8").split("\n")[0];
    const version = await (await fetch(`http://127.0.0.1:${port}/json/version`)).json();
    const targets = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();
    const page = await connect(
      targets.find((target) => target.type === "page").webSocketDebuggerUrl,
    );
    const statusRequests = [];
    let documents = 0;
    page.on((message) => {
      if (message.method !== "Network.requestWillBeSent") {
        return;
      }
      const { request, type, initiator } = message.params;
      if (request.url.endsWith("/api/source/status")) {
        // Who asked. The freshness row polls the same route from
        // static/source-freshness.js; the landing guard is the page's inline script.
        const frames = [];
        for (let stack = initiator?.stack; stack; stack = stack.parent) {
          frames.push(...stack.callFrames);
        }
        const freshness = frames.some((frame) => frame.url.includes("source-freshness"));
        statusRequests.push(freshness ? "freshness row" : "landing guard");
      }
      if (type === "Document") {
        documents += 1;
      }
    });
    await page.send("Page.enable");
    await page.send("Network.enable");
    await page.send("Runtime.enable");
    await page.send("Page.addScriptToEvaluateOnNewDocument", { source: PROBE });

    const evaluate = async (expression) => {
      const result = await page.send("Runtime.evaluate", {
        expression,
        awaitPromise: true,
        returnByValue: true,
      });
      if (result.exceptionDetails) {
        throw new Error(result.exceptionDetails.exception?.description ?? "evaluation failed");
      }
      return result.result.value;
    };
    const until = async (expression, what) => {
      for (let tries = 0; tries < 400; tries += 1) {
        try {
          if (await evaluate(expression)) {
            return;
          }
        } catch {
          // The document is being replaced; ask again.
        }
        await sleep(25);
      }
      throw new Error(`timed out waiting for ${what}`);
    };
    const diffAddress = `${origin}/commit/${commit}`;
    const scroller = `(() => {
      let node = document.querySelector(".diff-root");
      while (node && node.scrollHeight <= node.clientHeight + 1) node = node.parentElement;
      return node || document.scrollingElement;
    })()`;
    const pin = () => evaluate("window.METABROWSER_SOURCE_PIN.pin");
    const openDiff = async () => {
      await page.send("Page.navigate", { url: diffAddress });
      await until('document.querySelectorAll(".diff-file-bar").length > 0', "the diff");
      // Let the page go quiet, as a reader's page is when they leave it.
      await sleep(600);
    };
    /** Leave by one View file control, then come Back; report the landings. */
    const leaveAndReturn = async (selector) => {
      await evaluate(`${scroller}.scrollTop = 150`);
      const scrolled = await evaluate(`${scroller}.scrollTop`);
      const before = await pin();
      await evaluate(`document.querySelector(${JSON.stringify(selector)}).click()`);
      await until(
        'location.pathname.startsWith("/view/") && document.readyState === "complete"',
        "the file",
      );
      await sleep(400);
      statusRequests.length = 0;
      const documentsBefore = documents;
      await evaluate(
        'sessionStorage.setItem("mb-landings", "[]"); sessionStorage.setItem("mb-left-at", String(Date.now())); history.back()',
      );
      const landings = 'JSON.parse(sessionStorage.getItem("mb-landings") || "[]")';
      await until(
        `location.pathname.startsWith("/commit/") && ${landings}.length > 0 && ${landings}.at(-1).diffMs !== null`,
        "the diff after Back",
      );
      // Long enough for a second reload to show itself.
      await sleep(700);
      const asked = statusRequests.length;
      const result = {
        landings: await evaluate(landings),
        scrollTop: { left: scrolled, back: await evaluate(`${scroller}.scrollTop`) },
        pin: { left: before.slice(0, 12), back: (await pin()).slice(0, 12) },
        served: (await evaluate('fetch("/api/source/status").then((r) => r.json())')).pin.slice(
          0,
          12,
        ),
        statusRequests: statusRequests.slice(0, asked),
        documentsLoaded: documents - documentsBefore,
        failed: await evaluate('document.body.innerText.includes("Could not load")'),
      };
      await evaluate('sessionStorage.removeItem("mb-left-at")');
      return result;
    };

    const report = { chrome: version.Browser, bfcache: !noBfcache, unchanged: [], switched: [] };
    await openDiff();
    for (let round = 0; round < rounds; round += 1) {
      report.unchanged.push(await leaveAndReturn("a.diff-file-view"));
    }
    for (let round = 0; round < rounds; round += 1) {
      // Each round switches the pin: to the other side of the diff the page shows.
      report.switched.push(await leaveAndReturn("button.diff-file-view"));
    }
    console.log(JSON.stringify(report, null, 2));
    page.close();
  } finally {
    browser.kill();
  }
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});

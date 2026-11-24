// A PDF's view in Chrome: the browser's own viewer inline under either trust profile, and
// in a top-level tab.
//
// Serves ROOT, a folder holding PDF_PATH, with FLAGS (`--untrusted` or none), opens the
// file's view, and reads what the plugin drew: the `<embed>`, the actions' text, and any
// Content-Security-Policy violation the page reported. Whether Chrome's PDF viewer
// loaded is read from the frame tree, where it is a frame of the viewer extension's
// origin (the viewer's toolbar and pages are the extension's, which no page script
// reads). Then it embeds another address of this origin, which only `/raw` may be under
// the untrusted policy, and reads the violations that adds. Then opens the file's `/raw`
// address as a top-level tab, as Open in new tab does, and reads the same. Prints one
// JSON line.
//
// Usage: node pdf-preview-chrome.mjs METAB ROOT PORT STATE_DIR PDF_PATH [FLAGS...], with
// CHROME_BIN and CHROME_PROFILES set (tests/dom/chrome-session.mjs). SCREENSHOTS, when
// set, names a directory each page's capture is written to.
// tests/test_pdf_preview_chrome.py runs it in a process group of its own, which Chrome
// and the server join, stopped however the session ends.
import { spawn } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { launchChrome } from "./chrome-session.mjs";

const [metab, root, port, state, pdfPath, ...flags] = process.argv.slice(2);
const base = `http://127.0.0.1:${port}`;
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
// Chrome's PDF viewer is a component extension with this fixed identifier.
const VIEWER_ORIGIN = "chrome-extension://mhjfbmdgcfjbbpaeojofohoefgiehjai";
// How long the viewer is waited for: it starts in about a second on a Mac; a loaded CI
// machine gets more.
const VIEWER_WAIT_MS = 20000;

async function serve() {
  const server = spawn(
    metab,
    [
      root,
      "--no-open",
      "--port",
      port,
      "--cache-dir",
      path.join(state, "cache"),
      "--config-dir",
      path.join(state, "config"),
      ...flags,
    ],
    {
      stdio: ["ignore", "pipe", "pipe"],
      env: { ...process.env, METABROWSER_LOG_LEVEL: "WARNING" },
    },
  );
  const exited = new Promise((resolve) => server.once("exit", resolve));
  let output = "";
  await new Promise((resolve, reject) => {
    const bound = setTimeout(() => reject(new Error(`no server: ${output}`)), 60000);
    const read = (chunk) => {
      output += chunk;
      if (output.includes("Serving ") && output.includes(base)) {
        clearTimeout(bound);
        resolve();
      }
    };
    server.stdout.on("data", read);
    server.stderr.on("data", read);
    server.once("exit", () => reject(new Error(`server exited: ${output}`)));
  });
  return {
    async stop() {
      server.kill("SIGTERM");
      await Promise.race([exited, sleep(20000)]);
      if (server.exitCode === null) {
        server.kill("SIGKILL");
        await exited;
      }
    },
  };
}

const READ = `(() => {
  const pane = document.querySelector("#preview-pane");
  const viewer = pane?.querySelector(".metabrowser-pdf-host embed.pdf-viewer");
  return {
    embed: viewer ? {type: viewer.getAttribute("type"), src: viewer.getAttribute("src"),
      height: Math.round(viewer.getBoundingClientRect().height)} : null,
    actions: Array.from(pane?.querySelectorAll(".metabrowser-pdf-host .pdf-action") ?? [],
      (a) => a.textContent),
    violations: window.__pdfViolations ?? [],
  };
})()`;

// An object of this origin that is not `/raw`: the file's own envelope. The untrusted
// policy's `object-src` names `/raw` alone, so Chrome refuses it and reports `object-src`;
// a trusted page has no policy and reports nothing.
const PROBE = (filePath) => `(async () => {
  const before = window.__pdfViolations.length;
  const probe = document.createElement("embed");
  probe.setAttribute("type", "application/pdf");
  probe.setAttribute("src", "/api/file?path=" + encodeURIComponent(${JSON.stringify(filePath)}));
  document.body.append(probe);
  await new Promise((resolve) => setTimeout(resolve, 1500));
  probe.remove();
  return window.__pdfViolations.slice(before);
})()`;

/** Every frame's URL in the page's frame tree. */
async function frameUrls(chrome) {
  const { frameTree } = await chrome.send("Page.getFrameTree");
  const urls = [];
  const walk = (node) => {
    urls.push(node.frame.url);
    for (const child of node.childFrames ?? []) {
      walk(child);
    }
  };
  walk(frameTree);
  return urls;
}

/** Every target's URL Chrome reports: the viewer runs as a target of its own. */
async function targetUrls(chrome) {
  const { targetInfos } = await chrome.send("Target.getTargets");
  return targetInfos.map((info) => info.url);
}

/**
 * Whether the PDF viewer appears, waited for up to VIEWER_WAIT_MS: as a frame of the page,
 * or, as Chrome runs an `<embed>`'s viewer, as a target of its own.
 */
async function viewerLoaded(chrome) {
  const deadline = Date.now() + VIEWER_WAIT_MS;
  while (Date.now() < deadline) {
    const urls = [...(await frameUrls(chrome)), ...(await targetUrls(chrome))];
    if (urls.some((url) => url.startsWith(VIEWER_ORIGIN))) {
      return true;
    }
    await sleep(250);
  }
  return false;
}

const profiles = process.env.CHROME_PROFILES;
if (!process.env.CHROME_BIN || !profiles) {
  throw new Error("CHROME_BIN and CHROME_PROFILES are required");
}
const shots = process.env.SCREENSHOTS || null;
const chrome = await launchChrome(process.env.CHROME_BIN, { profiles, width: 1280, height: 900 });
let server = null;
const record = {};

async function capture(name) {
  if (shots) {
    const { data } = await chrome.send("Page.captureScreenshot", { format: "png" });
    fs.writeFileSync(path.join(shots, `${name}.png`), Buffer.from(data, "base64"));
  }
}

try {
  await chrome.send("Page.enable");
  // Collects the page's policy violations from its first script on.
  await chrome.send("Page.addScriptToEvaluateOnNewDocument", {
    source: `window.__pdfViolations = [];
      document.addEventListener("securitypolicyviolation", (event) =>
        window.__pdfViolations.push(event.effectiveDirective));`,
  });
  server = await serve();
  await chrome.send("Page.navigate", { url: `${base}/view/${pdfPath}` });
  await chrome.waitFor(
    `Boolean(document.querySelector("#preview-pane .metabrowser-pdf-host .pdf-bar"))`,
    60000,
  );
  const inline = await viewerLoaded(chrome);
  record.view = { ...(await chrome.evaluate(READ)), viewerLoaded: inline };
  await capture("view");
  record.otherObject = { violations: await chrome.evaluate(PROBE(pdfPath)) };
  const raw = await chrome.evaluate(
    `document.querySelector("#preview-pane .pdf-action[target=_blank]")?.getAttribute("href") ?? null`,
  );
  record.newTabHref = raw;
  await chrome.send("Page.navigate", { url: `${base}${raw}` });
  record.topLevel = { viewerLoaded: await viewerLoaded(chrome) };
  await capture("top-level");
} finally {
  await chrome.close();
  await server?.stop();
}
console.log(JSON.stringify(record));

// A Markdown document the server refuses to render shows its source and why, in Chrome.
//
// Serves SOURCE, a folder (with --untrusted) or a pinned repository URL, whose README and
// SLOW_PATH each take KPress far past the render deadline, with a fine document beside
// them. Opens the root, whose folder Overview shows the README panel, and then SLOW_PATH's
// Document tab, and reads what each drew: the refusal notice's text and severity, the
// source view in the render's place and the text it shows, and whether a render-error box
// or a KPress document is on the page. Then reloads SLOW_PATH, which the server refuses
// from memory, and opens the fine document, which renders. Prints one JSON line.
//
// Usage: node inert-render-refusal-chrome.mjs METAB SOURCE PORT STATE_DIR SLOW_PATH
// FINE_PATH [FLAGS...], with CHROME_BIN and CHROME_PROFILES set
// (tests/dom/chrome-session.mjs); METABROWSER_INERT_RENDER_DEADLINE_MS, when set, reaches
// the server. SCREENSHOTS, when set, names a directory each page's capture is written to.
// tests/test_inert_render_refusal_chrome.py runs it in a process group of its own, which
// Chrome and the server join, stopped however the session ends.
import { spawn } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { launchChrome } from "./chrome-session.mjs";

const [metab, source, port, state, slowPath, finePath, ...flags] = process.argv.slice(2);
const base = `http://127.0.0.1:${port}`;
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
const pinned = /^[a-z]+:\/\//.test(source);

/** A display path as the address a pin's page names it by: a GitPath wire. */
function address(display) {
  if (!pinned) {
    return display;
  }
  return display
    .split("/")
    .map((segment) => `g1-${Buffer.from(segment).toString("base64url")}`)
    .join("/");
}

async function serve() {
  const server = spawn(
    metab,
    [
      source,
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

// What the page drew in its active view: the notice, the source in the render's place,
// and anything that says the document rendered or failed.
const READ = `(() => {
  const pane = document.querySelector("#preview-pane");
  const notice = pane?.querySelector(".metabrowser-render-refused");
  const box = pane?.querySelector(".metabrowser-render-refused-source");
  const code = box?.querySelector("pre.metabrowser-source-lines code:not([data-mb-copy-payload])");
  const style = notice ? getComputedStyle(notice) : null;
  return {
    notice: notice?.textContent.trim() ?? null,
    code: notice?.getAttribute("data-refusal") ?? null,
    severity: notice?.getAttribute("data-severity") ?? null,
    border: style?.borderTopColor ?? null,
    link: notice?.querySelector("a")?.getAttribute("href") ?? null,
    inReadmePanel: Boolean(notice?.closest(".folder-overview-panel")),
    panelError: Boolean(pane?.querySelector(".folder-overview-panel-error")),
    sourceLines: box?.querySelectorAll("pre.metabrowser-source-lines").length ?? 0,
    sourceStart: code?.textContent.slice(0, 24) ?? null,
    renderError: Boolean(pane?.querySelector(".metabrowser-kpress-render-error")),
    kpressDocument: Boolean(pane?.querySelector("article.kpress-inert")),
  };
})()`;

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

/** Open *href*, wait for *ready*, and read the page; with the milliseconds it took. */
async function open(href, ready, timeoutMs = 60000) {
  // Marks the page being left, so what is waited for is the next page's.
  await chrome.evaluate("window.__refusalLeft = true");
  const began = Date.now();
  await chrome.send("Page.navigate", { url: `${base}${href}` });
  await chrome.waitFor(`!window.__refusalLeft && (${ready})`, timeoutMs);
  return { ...(await chrome.evaluate(READ)), ms: Date.now() - began };
}

try {
  await chrome.send("Page.enable");
  server = await serve();
  const refused = `Boolean(document.querySelector("#preview-pane .metabrowser-render-refused-source pre.metabrowser-source-lines"))`;
  record.readme = await open("/view/", refused);
  await capture("overview-readme");
  record.slow = await open(`/view/${address(slowPath)}`, refused);
  await capture("slow-document");
  record.reload = await open(`/view/${address(slowPath)}`, refused);
  record.fine = await open(
    `/view/${address(finePath)}`,
    `Boolean(document.querySelector("#preview-pane article.kpress-inert h1"))`,
  );
  record.fine = {
    ...record.fine,
    heading: await chrome.evaluate(
      `document.querySelector("#preview-pane article.kpress-inert h1")?.textContent ?? null`,
    ),
  };
} finally {
  await chrome.close();
  await server?.stop();
}
console.log(JSON.stringify(record));

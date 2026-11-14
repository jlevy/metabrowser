// A versioned /raw answer kept by Chrome under the trusted profile must not answer, with
// the trusted profile's `allow-scripts`, a link to it followed after the same origin is
// served `--untrusted` (reviews A and B of #426, A1 and B1).
//
// One Chrome, and so one HTTP cache, across two servers on one port. The first serves a
// folder with the trusted profile: its Markdown document embeds an SVG whose script loads
// a beacon image from this session, and a PNG, and both are opened as documents at the
// versioned addresses the page gave them, which primes the cache and shows the SVG's
// script runs there. The second serves the same folder `--untrusted`, with a document that
// links to those addresses absolutely, as an untrusted document may: the link is read from
// its inert render and followed. Prints what each answer was: whether it came from the
// cache, its Cache-Control and Content-Security-Policy, and how often the SVG's script ran.
//
// Usage: node raw-profile-cache-chrome.mjs METAB ROOT PORT STATE_DIR, with CHROME_BIN set,
// and CHROME_PROFILES naming where Chrome's profile goes (tests/dom/chrome-session.mjs).
// tests/test_raw_profile_cache_chrome.py owns that directory and removes it, and runs this
// in a process group of its own, which Chrome and both servers join, stopped however the
// session ends.
import { spawn } from "node:child_process";
import fs from "node:fs";
import http from "node:http";
import path from "node:path";
import { launchChrome } from "./chrome-session.mjs";

const [metab, root, port, state] = process.argv.slice(2);
const base = `http://127.0.0.1:${port}`;
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
// A 1x1 PNG.
const PNG = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==",
  "base64",
);

let beaconHits = 0;
const beacon = http.createServer((_request, response) => {
  beaconHits += 1;
  response.writeHead(200, { "content-type": "image/png", "cache-control": "no-store" });
  response.end(PNG);
});
await new Promise((resolve) => beacon.listen(0, "127.0.0.1", resolve));
const beaconUrl = `http://127.0.0.1:${beacon.address().port}/ran`;

fs.writeFileSync(
  path.join(root, "pic.svg"),
  `<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"><rect width="10" height="10"/>` +
    `<script>new Image().src = ${JSON.stringify(beaconUrl)} + "?" + Date.now();</script></svg>`,
);
fs.writeFileSync(path.join(root, "pic.png"), PNG);
fs.writeFileSync(path.join(root, "doc.md"), "# Doc\n\n![svg](pic.svg) ![png](pic.png)\n");

/** Start a server on the port, with *flags*, and resolve once it says where it serves. */
async function serve(flags) {
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
    const bound = setTimeout(() => reject(new Error(`no server: ${output}`)), 30000);
    const read = (chunk) => {
      output += chunk;
      if (output.includes(`Serving `) && output.includes(base)) {
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

const profiles = process.env.CHROME_PROFILES;
if (!process.env.CHROME_BIN || !profiles) {
  throw new Error("CHROME_BIN and CHROME_PROFILES are required");
}
const chrome = await launchChrome(process.env.CHROME_BIN, { profiles });
/** @type {Map<string, any>} */
const responses = new Map();
chrome.on("Network.responseReceived", ({ response }) => {
  responses.set(response.url, response);
});
let server = null;
try {
  await chrome.send("Network.enable");
  await chrome.send("Page.enable");
  server = await serve([]);
  await chrome.send("Page.navigate", { url: `${base}/view/doc.md` });
  const ACTIVE = '#preview-pane [data-tab-content][data-active-view="true"]';
  await chrome.waitFor(
    `["svg", "png"].every((alt) => { const image = document.querySelector('${ACTIVE} img[alt="' + alt + '"]'); return image && image.complete && image.naturalWidth > 0 && image.getAttribute("src").includes("&v="); })`,
  );
  const [svgUrl, pngUrl] = await chrome.evaluate(
    `["svg", "png"].map((alt) => document.querySelector('${ACTIVE} img[alt="' + alt + '"]').src)`,
  );

  /** Open *url* as a document, and report its answer and the SVG's runs since. */
  async function open(url) {
    responses.delete(url);
    const before = beaconHits;
    await chrome.send("Page.navigate", { url });
    const deadline = Date.now() + 10000;
    while (!responses.has(url) && Date.now() < deadline) {
      await sleep(25);
    }
    // Long enough for the script, if it runs, to load the beacon from this machine.
    await sleep(1000);
    const response = responses.get(url);
    const header = (name) =>
      Object.entries(response?.headers ?? {}).find(([key]) => key.toLowerCase() === name)?.[1] ??
      null;
    return {
      status: response?.status ?? null,
      fromCache: Boolean(response?.fromDiskCache || response?.fromMemoryCache),
      cacheControl: header("cache-control"),
      sandbox: header("content-security-policy"),
      scriptRuns: beaconHits - before,
    };
  }

  const trusted = { svg: await open(svgUrl), png: await open(pngUrl) };
  await server.stop();
  server = null;

  fs.writeFileSync(
    path.join(root, "links.md"),
    `# Links\n\n[the svg](${svgUrl}) and [the png](${pngUrl})\n`,
  );
  server = await serve(["--untrusted"]);
  await chrome.send("Page.navigate", { url: `${base}/view/links.md` });
  await chrome.waitFor(`document.querySelectorAll('${ACTIVE} a[href*="/raw?path="]').length === 2`);
  const links = await chrome.evaluate(
    `Array.from(document.querySelectorAll('${ACTIVE} a[href*="/raw?path="]'), (link) => link.href)`,
  );
  const untrusted = { svg: await open(links[0]), png: await open(links[1]) };
  console.log(
    JSON.stringify({ linksKept: links[0] === svgUrl && links[1] === pngUrl, trusted, untrusted }),
  );
} finally {
  await server?.stop();
  await chrome.close();
  beacon.close();
}

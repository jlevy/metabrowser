// A checkout's branch and tag selector in a real engine (mb-8ob8): the working tree and
// the revisions of one served folder, switched from the page, and what each page is.
//
// The selector's decisions are browserless (tests/dom/source-ref-selector-session.js).
// What needs a browser is that the page a real server writes for a checkout mounts it,
// that a click reaches the pin route and the document that comes back is the other
// subject's, drawn under that subject's Content-Security-Policy, and where its panel
// sits. So this serves a fixture checkout with `metab`, as a reader does, and in one
// headless Chrome:
//
//   1. loads the working tree's page and reads its button, its bundle, and its panel:
//      the Working tree row, the three lists, the checked-out branch's badge;
//   2. chooses a branch, and reads the revision's page: the button and heading that name
//      it, the committed file where the working tree's edit was, a tree with no untracked
//      file, and the document's policy;
//   3. reads each list there, with the served branch marked;
//   4. switches the server back from outside the page, as another tab would, asks the page
//      for data, and reads the offer to reload that the selector then makes;
//   5. reloads, which lands on the working tree through the server's translation of the
//      revision's address, and chooses the Working tree row from a revision again;
//   6. goes Back onto the revision's address while the working tree is served.
//
// It times each switch from the click to the new document's first tree rows and to its
// selector being mounted, and the working tree's page from navigation to its selector.
//
// Usage: node checkout-ref-selector-chrome.mjs METAB CHECKOUT PORT STATE, with CHROME_BIN
// set and CHROME_PROFILES naming where Chrome's profile goes (tests/dom/chrome-session.mjs).
// SHOTS, when set, names a directory that gets a PNG of each step, for a person to look at.
// tests/test_checkout_ref_selector_chrome.py owns the directories, runs this in a process
// group of its own, which Chrome and the server join, and compares the checkout's every
// byte before and after.
import { spawn } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { launchChrome } from "./chrome-session.mjs";

const [metab, checkout, port, state] = process.argv.slice(2);
const profiles = process.env.CHROME_PROFILES;
if (!process.env.CHROME_BIN || !profiles || !state) {
  throw new Error("CHROME_BIN, CHROME_PROFILES, and four arguments are required");
}
const shots = process.env.SHOTS || null;
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
// The server's first line names the port it took, which a port in use moves.
const SERVING = /Serving .* at http:\/\/127\.0\.0\.1:(\d+)\/view\//;

/** Start the server searching from *at*, resolving once it says where it serves. */
async function serve(root, at, dir) {
  const server = spawn(
    metab,
    [
      root,
      "--no-open",
      "--port",
      String(at),
      "--cache-dir",
      path.join(dir, "cache"),
      "--config-dir",
      path.join(dir, "config"),
    ],
    {
      stdio: ["ignore", "pipe", "pipe"],
      env: { ...process.env, METABROWSER_LOG_LEVEL: "WARNING" },
    },
  );
  const exited = new Promise((resolve) => server.once("exit", resolve));
  let output = "";
  const took = await new Promise((resolve, reject) => {
    const bound = setTimeout(() => reject(new Error(`no server: ${output}`)), 30000);
    const read = (chunk) => {
      output += chunk;
      const serving = SERVING.exec(output);
      if (serving) {
        clearTimeout(bound);
        resolve(Number(serving[1]));
      }
    };
    server.stdout.on("data", read);
    server.stderr.on("data", read);
    server.once("exit", () => reject(new Error(`server exited: ${output}`)));
  });
  return {
    base: `http://127.0.0.1:${took}`,
    async stop() {
      server.kill("SIGTERM");
      await Promise.race([exited, sleep(20000)]);
    },
  };
}

const server = await serve(checkout, Number(port), state);
const chrome = await launchChrome(process.env.CHROME_BIN, { profiles });

// The policy each document was served under, by its address: the trust profile in effect.
/** @type {Array<{url: string, status: number, csp: boolean}>} */
const documents = [];
chrome.on("Network.responseReceived", ({ type, response }) => {
  if (type === "Document") {
    const headers = Object.fromEntries(
      Object.entries(response.headers).map(([name, value]) => [name.toLowerCase(), value]),
    );
    documents.push({
      url: new URL(response.url).pathname,
      status: response.status,
      csp: typeof headers["content-security-policy"] === "string",
    });
  }
});

let shot = 0;
async function capture(name) {
  if (!shots) {
    return;
  }
  shot += 1;
  const { data } = await chrome.send("Page.captureScreenshot", { format: "png" });
  fs.writeFileSync(
    path.join(shots, `${String(shot).padStart(2, "0")}-${name}.png`),
    Buffer.from(data, "base64"),
  );
}

const SELECTOR = `document.querySelector("#source-ref-selector .source-ref-selector-toggle")`;
const ROWS = `[...document.querySelectorAll("#tree-content .tree-item")]`;

/** What the page shows of itself and its selector. */
const PAGE = `(() => {
  const toggle = ${SELECTOR};
  const heading = document.querySelector(".header-path");
  const stale = document.querySelector(".source-ref-selector-stale");
  return {
    path: location.pathname,
    title: document.title,
    kind: window.METABROWSER_SOURCE_KIND,
    checkout: window.METABROWSER_SOURCE_CHECKOUT ?? null,
    pin: window.METABROWSER_SOURCE_PIN ?? null,
    button: toggle ? toggle.textContent.trim() : null,
    heading: heading ? heading.textContent.replace(/\\s+/g, " ").trim() : null,
    guard: typeof window.MetabrowserSourcePinGuard?.guardFetch === "function",
    capabilities: window.METABROWSER_SETTINGS?.CAPABILITIES ?? null,
    stale: stale && !stale.hidden ? stale.textContent.trim() : null,
    tree: [...document.querySelectorAll("#tree-content .tree-item-name")]
      .map((node) => node.textContent.trim())
      .filter(Boolean),
    preview: (document.querySelector("#preview-pane")?.innerText ?? "").slice(0, 400),
  };
})()`;

/** The open panel: its rows, its lists, and where it sits in the navigation pane. */
const PANEL = `(() => {
  const root = document.getElementById("source-ref-selector");
  const panel = root.querySelector(".source-ref-selector-panel");
  const tree = root.querySelector(".source-ref-selector-working-tree");
  const pane = document.querySelector(".tree-pane").getBoundingClientRect();
  const box = panel.getBoundingClientRect();
  const row = (button) => ({
    text: button.innerText.replace(/\\s+/g, " ").trim(),
    current: button.getAttribute("aria-current") === "true",
    chip: button.querySelector(".git-ref")?.className.match(/git-ref-(local|remote|tag)/)?.[1] ?? null,
  });
  return {
    open: !panel.hidden,
    focused: document.activeElement === root.querySelector(".source-ref-selector-filter"),
    workingTree: tree.hidden ? null : row(tree),
    lists: [...root.querySelectorAll(".source-ref-selector-kinds button")].map((button) => ({
      label: button.textContent.trim(),
      chosen: button.getAttribute("aria-checked") === "true",
    })),
    rows: [...root.querySelectorAll(".source-ref-selector-list button")].map(row),
    note: root.querySelector(".source-ref-selector-note").textContent,
    error: root.querySelector(".source-ref-selector-error").textContent,
    // The panel is inside the navigation pane, and no row is wider than it.
    inside: box.left >= pane.left - 0.5 && box.right <= pane.right + 0.5 && box.width > 0,
    overflowing: [...panel.querySelectorAll("button.menu-item")]
      .filter((button) => !button.hidden && button.getBoundingClientRect().right > box.right + 0.5)
      .length,
  };
})()`;

async function load(address) {
  const before = Date.now();
  await chrome.evaluate("window.__left = true; true").catch(() => {});
  await chrome.send("Page.navigate", { url: `${server.base}${address}` });
  await chrome.waitFor(`!window.__left && ${SELECTOR} !== null && ${ROWS}.length > 0`);
  return Date.now() - before;
}

async function openPanel(list = null) {
  await chrome.evaluate(`${SELECTOR}.click(); true`);
  await chrome.waitFor(
    `document.querySelector(".source-ref-selector-list").getAttribute("aria-busy") === "false" &&
      (document.querySelectorAll(".source-ref-selector-list button").length > 0 ||
        document.querySelector(".source-ref-selector-note").textContent !== "")`,
  );
  if (list !== null) {
    await chrome.evaluate(
      `[...document.querySelectorAll(".source-ref-selector-kinds button")]
        .find((button) => button.textContent.trim() === ${JSON.stringify(list)}).click(); true`,
    );
    await chrome.waitFor(
      `[...document.querySelectorAll(".source-ref-selector-kinds button")]
        .find((button) => button.textContent.trim() === ${JSON.stringify(list)})
        .getAttribute("aria-checked") === "true" &&
        document.querySelector(".source-ref-selector-list").getAttribute("aria-busy") === "false"`,
    );
  }
  return chrome.evaluate(PANEL);
}

async function closePanel() {
  await chrome.evaluate(
    `if (${SELECTOR}.getAttribute("aria-expanded") === "true") ${SELECTOR}.click(); true`,
  );
}

/** Click what *pick* finds in the open panel, and time the document that comes back. */
async function switchBy(pick) {
  await chrome.evaluate("window.__left = true; true");
  const clicked = Date.now();
  await chrome.evaluate(`(${pick}).click(); true`);
  await chrome.waitFor(`!window.__left && ${ROWS}.length > 0`);
  const rows = Date.now() - clicked;
  await chrome.waitFor(`${SELECTOR} !== null`);
  return { rowsMs: rows, selectorMs: Date.now() - clicked };
}

const rowNamed = (name) =>
  `[...document.querySelectorAll(".source-ref-selector-list button")]
    .find((button) => button.querySelector(".git-ref-label")?.textContent === ${JSON.stringify(name)})`;

const result = {};
try {
  await chrome.send("Page.enable");
  await chrome.send("Network.enable");

  // 1. The working tree's page.
  result.workingTreeLoadMs = await load("/view/README.md");
  result.workingTree = await chrome.evaluate(PAGE);
  await capture("working-tree");
  result.workingTreePanel = await openPanel();
  await capture("working-tree-panel");
  result.workingTreeRemotes = await openPanelList("Remotes");
  result.workingTreeTags = await openPanelList("Tags");
  await openPanelList("Branches");

  // 2. A branch: the revision's page.
  result.toBranch = await switchBy(rowNamed("feature"));
  result.branch = await chrome.evaluate(PAGE);
  await capture("revision");

  // 3. Its lists.
  result.branchPanel = await openPanel();
  await capture("revision-panel");
  await closePanel();

  // 4. Another tab switches the server back; this page is told when it next asks.
  result.switchedOutside = await chrome.evaluate(`fetch("/api/source/pin", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ working_tree: true }),
  }).then((response) => response.status)`);
  result.refused = await chrome.evaluate(
    `fetch("/api/tree?depth=1").then((response) => response.status)`,
  );
  await chrome.waitFor(`!document.querySelector(".source-ref-selector-stale").hidden`);
  result.stale = await chrome.evaluate(PAGE);
  await capture("stale");

  // 5. Reload lands on the working tree, through the server's translation of the address.
  await chrome.evaluate("window.__left = true; true");
  await chrome.evaluate(`document.querySelector(".source-ref-selector-reload").click(); true`);
  await chrome.waitFor(`!window.__left && ${SELECTOR} !== null && ${ROWS}.length > 0`);
  result.reloaded = await chrome.evaluate(PAGE);

  // To a tag, then back by the Working tree row.
  await openPanel("Tags");
  result.toTag = await switchBy(rowNamed("v1"));
  result.tag = await chrome.evaluate(PAGE);
  await openPanel();
  result.toWorkingTree = await switchBy(
    `document.querySelector(".source-ref-selector-working-tree")`,
  );
  result.back = await chrome.evaluate(PAGE);
  await capture("working-tree-again");

  // 6. Back, onto the tag's address, while the working tree is served.
  await chrome.evaluate("window.__left = true; true");
  await chrome.evaluate("history.back(); true");
  await chrome.waitFor(`!window.__left && ${SELECTOR} !== null && ${ROWS}.length > 0`, 30000);
  // The landing may be a restored page that then reloads itself; wait for it to be the
  // working tree's, which is what the server serves.
  await chrome.waitFor(
    `window.METABROWSER_SOURCE_KIND === "filesystem" && ${SELECTOR} !== null`,
    30000,
  );
  result.afterBack = await chrome.evaluate(PAGE);
  result.served = await chrome.evaluate(
    `fetch("/api/source/status").then((response) => response.json())`,
  );
  result.documents = documents;
  console.log(JSON.stringify(result));
} finally {
  await chrome.close();
  await server.stop();
}

/** Choose a list in the already open panel and read it. */
async function openPanelList(list) {
  await chrome.evaluate(
    `[...document.querySelectorAll(".source-ref-selector-kinds button")]
      .find((button) => button.textContent.trim() === ${JSON.stringify(list)}).click(); true`,
  );
  await chrome.waitFor(
    `[...document.querySelectorAll(".source-ref-selector-kinds button")]
      .find((button) => button.textContent.trim() === ${JSON.stringify(list)})
      .getAttribute("aria-checked") === "true" &&
      document.querySelector(".source-ref-selector-list").getAttribute("aria-busy") === "false"`,
  );
  return chrome.evaluate(PANEL);
}

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
//   1. loads the working tree's page and reads its button, which leads the Files tab's
//      toolbar, its bundle, and its panel: the Working tree row and the folder it names,
//      the three lists, each ref's short commit ID and age, the checked-out branch's badge;
//   2. chooses a branch, and reads the revision's page: the button and heading that name
//      it, the committed file where the working tree's edit was, a tree with no untracked
//      file, and the document's policy;
//   3. reads each list there, with the served branch marked;
//   4. switches the server back from outside the page, as another tab would, asks the page
//      for data, and reads the offer to reload that the selector then makes;
//   5. reloads, which lands on the working tree through the server's translation of the
//      revision's address, and chooses the Working tree row from a revision again;
//   6. goes Back onto the revision's address while the working tree is served;
//   7. browses a revision's page, a file and its history, and reads how every data
//      request of each page was answered: none of a current page's is refused. Its
//      Commits tab is the checkout's, and hides the button with the Files toolbar.
//
// It times each switch from the click to the new document's first tree rows and to its
// selector being mounted, and the working tree's page from navigation to its selector.
//
// Usage: node checkout-ref-selector-chrome.mjs METAB CHECKOUT PORT STATE, with CHROME_BIN
// set and CHROME_PROFILES naming where Chrome's profile goes (tests/dom/chrome-session.mjs).
// SHOTS, when set, names a directory that gets a PNG of each step, for a person to look at.
// tests/test_checkout_ref_selector_chrome.py owns the directories, runs this in a process
// group of its own, which Chrome and the server join, and compares the checkout's every
// byte before and after. This script starts `metab` and Chrome and builds no repository:
// the fixture is the test's, and tests/test_git_hook_environment.py holds every script
// here to that.
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

// Every data request a page made, and how it was answered: a page that shows what the
// server serves is never refused as a page left behind (`pin_changed`, 409).
/** @type {Array<{url: string, status: number}>} */
let dataRequests = [];
chrome.on("Network.responseReceived", ({ response }) => {
  const url = new URL(response.url);
  if (url.pathname.startsWith("/api/")) {
    dataRequests.push({ url: url.pathname, status: response.status });
  }
});
/** The data requests since the last call, by status, with the addresses of any refused. */
function takeDataRequests() {
  const taken = dataRequests;
  dataRequests = [];
  return {
    asked: taken.length,
    refused: taken.filter((entry) => entry.status === 409).map((entry) => entry.url),
  };
}

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
// The server draws a checkout's row with its button, so the button alone does not say the
// selector is there: its panel does, which only the mounted module builds.
const MOUNTED = `(document.querySelector("#source-ref-selector .source-ref-selector-panel") !== null)`;
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
    // The button leads the Files tab's toolbar, since it chooses only what that tab shows.
    inFilesToolbar: toggle?.closest('#nav-filter-bar[data-nav-toolbar="files"]') != null,
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
  // A row's text leaves out its age, which the clock moves; the age is read on its own.
  const row = (button) => {
    const age = button.querySelector(".source-ref-selector-age");
    return {
      text: [...button.children]
        .filter((child) => child !== age)
        .map((child) => child.innerText)
        .join(" ")
        .replace(/\\s+/g, " ")
        .trim(),
      current: button.getAttribute("aria-current") === "true",
      // The chip is the name's one element, and its class says which kind it is drawn as.
      chip:
        button
          .querySelector(".source-ref-selector-name > span")
          ?.className.match(/-ref-(local|remote|tag)/)?.[1] ?? null,
      // A commit's ID is in the commit-ID face, and its age in a tier, with its date as the
      // tooltip. Class names are matched by their ends here, as the history's rows are
      // below, so this script never names the program (tests/test_git_hook_environment.py).
      commitFace:
        button.querySelector(".source-ref-selector-commit")?.matches('[class*="-commit-sha"]') ??
        null,
      age: age
        ? {
            text: age.textContent,
            tier: /\\bage-/.test(age.className),
            tip: age.dataset.tipText ?? "",
          }
        : null,
    };
  };
  // The folder the Working tree row names, and whether its own name is shown whole.
  const location = tree.querySelector(".source-ref-selector-location");
  const base = location?.querySelector(".path-base");
  // The ages end the rows in one column, so the IDs line up: the widest compact age,
  // "12mo", takes no more room than the narrowest, in the list's own face and weights.
  const list = root.querySelector(".source-ref-selector-list");
  const ageWidth = (text, tier) => {
    const probe = document.createElement("span");
    probe.className = \`source-ref-selector-age \${tier}\`;
    probe.style.position = "absolute";
    probe.textContent = text;
    list.append(probe);
    const width = probe.getBoundingClientRect().width;
    probe.remove();
    return Math.round(width * 100) / 100;
  };
  const commitLefts = [...root.querySelectorAll(".source-ref-selector-list .source-ref-selector-commit")]
    .map((commit) => Math.round(commit.getBoundingClientRect().left * 2) / 2);
  return {
    open: !panel.hidden,
    focused: document.activeElement === root.querySelector(".source-ref-selector-filter"),
    workingTree: tree.hidden ? null : row(tree),
    location: location?.textContent ?? null,
    folderWhole: base ? base.scrollWidth <= base.clientWidth : null,
    lists: [...root.querySelectorAll(".source-ref-selector-kinds button")].map((button) => ({
      label: button.textContent.trim(),
      chosen: button.getAttribute("aria-checked") === "true",
    })),
    rows: [...root.querySelectorAll(".source-ref-selector-list button")].map(row),
    ageColumn: [ageWidth("12mo", "age-old"), ageWidth("60m", "age-min"), ageWidth("7d", "age-day")],
    commitColumns: new Set(commitLefts).size,
    note: root.querySelector(".source-ref-selector-note").textContent,
    error: root.querySelector(".source-ref-selector-error").textContent,
    // The panel is inside the navigation pane, and no row is wider than it.
    inside: box.left >= pane.left - 0.5 && box.right <= pane.right + 0.5 && box.width > 0,
    // It spans the toolbar it opens under, on a ref's page, whose chip has a copy
    // control, as on the working tree's.
    spansToolbar: (() => {
      const bar = root.closest("[data-nav-toolbar]");
      const inset = parseFloat(getComputedStyle(bar).paddingLeft);
      const across = bar.getBoundingClientRect();
      return Math.abs(box.left - (across.left + inset)) < 1 && Math.abs(box.right - (across.right - inset)) < 1;
    })(),
    overflowing: [...panel.querySelectorAll("button.menu-item")]
      .filter((button) => !button.hidden && button.getBoundingClientRect().right > box.right + 0.5)
      .length,
  };
})()`;

async function load(address) {
  const before = Date.now();
  await chrome.evaluate("window.__left = true; true").catch(() => {});
  await chrome.send("Page.navigate", { url: `${server.base}${address}` });
  await chrome.waitFor(`!window.__left && ${MOUNTED} && ${ROWS}.length > 0`);
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
  await chrome.waitFor(`${MOUNTED}`);
  return { rowsMs: rows, selectorMs: Date.now() - clicked };
}

const rowNamed = (name) =>
  `[...document.querySelectorAll(".source-ref-selector-list button")]
    .find((button) => button.querySelector(".source-ref-selector-name")?.textContent === ${JSON.stringify(name)})`;

// From each document's start: every distinct height of the selector and every distinct
// top of the tree's first row, frame by frame. The selector is drawn by the server with its
// button, leading the Files toolbar, so mounting it moves nothing below it. The first toggle the
// parser adds is the server's, kept to ask afterwards whether the module adopted it.
const TOGGLE = "#source-ref-selector button.source-ref-selector-toggle";
const LAYOUT_PROBE = `(() => {
  window.__rowHeights = [];
  window.__treeTops = [];
  const parsed = new MutationObserver(() => {
    window.__firstToggle = document.querySelector(${JSON.stringify(TOGGLE)});
    if (window.__firstToggle !== null) {
      parsed.disconnect();
    }
  });
  parsed.observe(document, { childList: true, subtree: true });
  const note = (list, value) => {
    if (value !== null && list[list.length - 1] !== value) {
      list.push(value);
    }
  };
  const frame = () => {
    const row = document.getElementById("source-ref-selector");
    const first = document.querySelector("#tree-content .tree-item");
    note(window.__rowHeights, row ? Math.round(row.getBoundingClientRect().height * 10) / 10 : null);
    note(window.__treeTops, first ? Math.round(first.getBoundingClientRect().top * 10) / 10 : null);
    requestAnimationFrame(frame);
  };
  requestAnimationFrame(frame);
})()`;
const LAYOUT = `({
  rowHeights: window.__rowHeights,
  treeTops: window.__treeTops,
  toggles: document.querySelectorAll(${JSON.stringify(TOGGLE)}).length,
  adopted: window.__firstToggle != null
    && window.__firstToggle === document.querySelector(${JSON.stringify(TOGGLE)})
    && window.__firstToggle.closest("#source-ref-selector")?.querySelector(".source-ref-selector-panel") != null,
})`;

const result = {};
try {
  await chrome.send("Page.enable");
  await chrome.send("Network.enable");
  await chrome.send("Page.addScriptToEvaluateOnNewDocument", { source: LAYOUT_PROBE });

  // 1. The working tree's page.
  result.workingTreeLoadMs = await load("/view/README.md");
  takeDataRequests();
  result.workingTree = await chrome.evaluate(PAGE);
  result.workingTreeLayout = await chrome.evaluate(LAYOUT);
  // What the selector's bundle cost this page: the guard and the selector, on demand.
  result.bundle = await chrome.evaluate(`performance.getEntriesByType("resource")
    .filter((entry) => /source-(pin-guard|ref-selector)\\.js/.test(entry.name))
    .map((entry) => ({
      name: new URL(entry.name).pathname.split("/").pop(),
      encoded: entry.encodedBodySize,
      ms: Math.round(entry.duration * 10) / 10,
      startMs: Math.round(entry.startTime),
    }))`);
  await capture("working-tree");
  result.workingTreePanel = await openPanel();
  await capture("working-tree-panel");
  result.workingTreeRemotes = await openPanelList("Remotes");
  result.workingTreeTags = await openPanelList("Tags");
  await openPanelList("Branches");

  // 2. A branch: the revision's page.
  result.workingTreeBrowsing = takeDataRequests();
  result.toBranch = await switchBy(rowNamed("feature"));
  result.branch = await chrome.evaluate(PAGE);
  result.branchLayout = await chrome.evaluate(LAYOUT);
  await capture("revision");

  // 3. Its lists.
  result.branchPanel = await openPanel();
  await capture("revision-panel");
  await closePanel();
  result.revisionRequests = takeDataRequests();

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
  await chrome.waitFor(`!window.__left && ${MOUNTED} && ${ROWS}.length > 0`);
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
  await chrome.waitFor(`!window.__left && ${MOUNTED} && ${ROWS}.length > 0`, 30000);
  // The landing may be a restored page that then reloads itself; wait for it to be the
  // working tree's, which is what the server serves.
  await chrome.waitFor(`window.METABROWSER_SOURCE_KIND === "filesystem" && ${MOUNTED}`, 30000);
  result.afterBack = await chrome.evaluate(PAGE);
  result.served = await chrome.evaluate(
    `fetch("/api/source/status").then((response) => response.json())`,
  );

  // 7. A revision's own page browses as any page does: a file, and its history. None of
  // its requests is refused, since each names the commit the server serves. Last, since
  // the Commits tab adds entries to the history that step 6 walks.
  await openPanel();
  await switchBy(rowNamed("feature"));
  takeDataRequests();
  await chrome.evaluate(
    `[...document.querySelectorAll("#tree-content .tree-item")]
      .find((row) => row.textContent.includes("FEATURE.md")).click(); true`,
  );
  await chrome.waitFor(`location.pathname !== ${JSON.stringify("/view/g1-UkVBRE1FLm1k")}`);
  await chrome.waitFor(
    `(document.querySelector("#preview-pane")?.innerText ?? "").includes("Only on feature")`,
  );
  await chrome.evaluate(
    `[...document.querySelectorAll(".tab-btn")]
      .find((tab) => tab.textContent.trim() === "Commits").click(); true`,
  );
  await chrome.waitFor(`document.querySelectorAll('[class$="graph-row"]').length > 0`);
  result.revisionBrowsing = takeDataRequests();
  // The Commits tab does not follow the Files tab: its history is the checkout's, whose
  // HEAD chip is on the checked-out branch, and the button went with the Files toolbar.
  result.revisionCommits = await chrome.evaluate(`({
    head: document.querySelector('[class*="-ref-head"]')?.textContent.trim() ?? null,
    button: document.getElementById("source-ref-selector")?.checkVisibility() ?? null,
  })`);

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

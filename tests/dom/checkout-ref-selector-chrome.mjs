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
//   2. chooses a branch, while the working tree's page asks for its root's tallies, as its
//      own refresh of them can, and reads the revision's page: the button that names it,
//      the heading, which is the folder's name alone, the committed file where the working
//      tree's edit was, a tree with no untracked file, and the document's policy;
//   3. reads each list there, with the served branch marked;
//   4. switches the server back from outside the page, as another tab would, asks the page
//      for data, and reads the offer to reload that the selector then makes, and where
//      it sits: at the pane's foot, under the tree and the Files toolbar's band;
//   5. reloads, which lands on the working tree through the server's translation of the
//      revision's address, and chooses the Working tree row from a revision again, and
//      later the row's own button back from the checked-out branch's revision;
//   6. goes Back onto the revision's address while the working tree is served;
//   7. browses a revision's page, a file and its history, and reads how every data
//      request of each page was answered: none of a current page's is refused, and the
//      page that switched sent none after it asked. Its Commits tab is the checkout's, and
//      hides the button with the Files toolbar; when another tab switches the server
//      there, its history still answers and the offer to reload shows on that tab.
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
// server serves is never refused as a page left behind (`pin_changed`, 409). Each request
// keeps what says whose it was and when, so a refusal says which page it was: the
// document that made it, by its loader, and whether that is the one shown now; its method
// and full address; the commit it named; the first caller outside the fetch wrappers; and
// when it was sent, in milliseconds from the answer to the last switch.
/** @type {Map<string, {loader: string, type: string, request: string, pin: string | null, initiator: string | null, at: number}>} */
const sent = new Map();
/** @type {Map<string, string>} Each document's address, by its loader. */
const loaders = new Map();
/** @type {Array<{requestId: string, status: number}>} */
let answered = [];
// The main frame's document now, and when the last switch was asked for and answered,
// in seconds on the protocol's clock.
let currentLoader = null;
let switchAsked = null;
let switchAnswered = null;
// Frames of the wrappers every request passes through, which name no caller.
const WRAPPERS = /\/static\/(perf|source-pin-guard)\.js$/;
chrome.on("Page.frameNavigated", ({ frame }) => {
  if (!frame.parentId) {
    currentLoader = frame.loaderId;
  }
});
chrome.on(
  "Network.requestWillBeSent",
  ({ requestId, loaderId, request, initiator, timestamp, type }) => {
    const url = new URL(request.url);
    if (type === "Document") {
      loaders.set(loaderId, url.pathname);
    }
    if (!url.pathname.startsWith("/api/")) {
      return;
    }
    if (url.pathname === "/api/source/pin") {
      switchAsked = timestamp;
    }
    const frames = [];
    for (let stack = initiator?.stack; stack; stack = stack.parent) {
      frames.push(...stack.callFrames);
    }
    const caller = frames.find((frame) => !WRAPPERS.test(new URL(frame.url, server.base).pathname));
    sent.set(requestId, {
      loader: loaderId,
      type,
      request: `${request.method} ${url.pathname}${url.search}`,
      pin: request.headers["x-metabrowser-pin"] ?? null,
      initiator: caller
        ? `${caller.functionName || "(anonymous)"} ${new URL(caller.url, server.base).pathname}:${caller.lineNumber + 1}`
        : (initiator?.type ?? null),
      at: timestamp,
    });
  },
);
chrome.on("Network.responseReceived", ({ requestId, response, timestamp }) => {
  const url = new URL(response.url);
  if (url.pathname === "/api/source/pin") {
    switchAnswered = timestamp;
  }
  if (url.pathname.startsWith("/api/")) {
    answered.push({ requestId, status: response.status });
  }
});
/** @param {number} at */
const sinceSwitch = (at) =>
  switchAnswered === null ? null : Math.round((at - switchAnswered) * 1000);
/** @param {string} requestId What a report says of one request. */
function described(requestId) {
  const asked = sent.get(requestId);
  return {
    request: asked.request,
    document: loaders.get(asked.loader) ?? asked.loader,
    current: asked.loader === currentLoader,
    pin: asked.pin,
    initiator: asked.initiator,
    sentMs: sinceSwitch(asked.at),
  };
}
/** The data requests answered since the last call, and what each refused one was. */
function takeDataRequests() {
  const taken = answered;
  answered = [];
  return {
    asked: taken.length,
    refused: taken
      .filter((entry) => entry.status === 409)
      .map((entry) => described(entry.requestId)),
  };
}
/**
 * The page's own data requests that the document *leaving* sent after it asked the server
 * to switch, at *since*: none, since they wait for the answer and then go with the page.
 *
 * @param {string} leaving @param {number} since
 */
function leftBehind(leaving, since) {
  return [...sent.entries()]
    .filter(
      ([, asked]) =>
        asked.loader === leaving &&
        asked.type === "Fetch" &&
        asked.at > since &&
        !asked.request.includes(" /api/source/"),
    )
    .map(([requestId]) => described(requestId));
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

// Every short commit ID the page shows, and what the commit-ID face resolves to here: each
// is one length, in the mono face, and in the muted gray, whatever the line around it is in
// (docs/design-system.md, "Short Commit IDs"). Matched by the class's end, as below.
const COMMIT_IDS = `(() => {
  const probe = document.createElement("span");
  probe.style.color = "var(--muted)";
  probe.style.fontFamily = "var(--font-mono)";
  document.body.append(probe);
  const face = { color: getComputedStyle(probe).color, font: getComputedStyle(probe).fontFamily };
  probe.remove();
  const ids = [...document.querySelectorAll('[class*="-commit-sha"]')]
    .filter((node) => node.checkVisibility())
    .map((node) => {
      const style = getComputedStyle(node);
      return { text: node.textContent, color: style.color, font: style.fontFamily };
    });
  return { face, ids };
})()`;

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
    button: toggle?.parentElement.querySelector(".source-ref-selector-label")?.textContent.trim() ?? null,
    // Which view the row says the page shows, and its button back to the working tree:
    // its words and whether it shows, in the Files row beside the chooser.
    view: document.getElementById("source-ref-selector")?.dataset.view ?? null,
    back: (() => {
      const back = document.querySelector("#source-ref-selector .source-ref-selector-back");
      return back && back.checkVisibility()
        ? { text: back.textContent, name: back.getAttribute("aria-label"), btn: back.matches(".btn") }
        : null;
    })(),
    inFilesRow:
      toggle?.closest("#nav-files-ref")?.previousElementSibling.matches(".nav-tab-bar") === true &&
      toggle.closest("#nav-files-ref").nextElementSibling.id === "nav-filter-bar",
    heading: heading ? heading.textContent.replace(/\\s+/g, " ").trim() : null,
    commitIds: ${COMMIT_IDS},
    guard: typeof window.MetabrowserSourcePinGuard?.guardFetch === "function",
    capabilities: window.METABROWSER_SETTINGS?.CAPABILITIES ?? null,
    stale: stale && !stale.hidden ? stale.textContent.trim() : null,
    tree: [...document.querySelectorAll("#tree-content .tree-item-name")]
      .map((node) => node.textContent.trim())
      .filter(Boolean),
    preview: (document.querySelector("#preview-pane")?.innerText ?? "").slice(0, 400),
  };
})()`;

/**
 * Where the offer to reload sits: at the pane's foot after the indexing row, under the
 * tree, and outside every tab's toolbar and the metadata band under it, which hide while
 * another tab is in front, so it shows whichever tab is.
 */
const STALE_AT = `(() => {
  const stale = document.querySelector(".source-ref-selector-stale");
  const box = stale.getBoundingClientRect();
  const tree = document.getElementById("tree-content").getBoundingClientRect();
  const pane = document.querySelector(".tree-pane").getBoundingClientRect();
  // Reload page is two words, and its label stays on one line beside the sentence.
  const label = document.createRange();
  label.selectNodeContents(stale.querySelector(".source-ref-selector-reload"));
  return {
    buttonLines: label.getClientRects().length,
    after: stale.previousElementSibling?.id ?? null,
    inToolbarOrBand: stale.closest("[data-nav-toolbar], .nav-metadata-band") !== null,
    shown: stale.checkVisibility() && box.height > 0,
    underTree: box.top >= tree.bottom - 0.5,
    inPane: box.bottom <= pane.bottom + 0.5,
    front: document.querySelector(".tab-btn.active")?.dataset.tab ?? null,
  };
})()`;

/** The open panel: its rows, its lists, and where it sits in the navigation pane. */
const PANEL = `(() => {
  const root = document.getElementById("source-ref-selector");
  const panel = root.querySelector(".source-ref-selector-panel");
  const tree = root.querySelector(".source-ref-selector-working-tree");
  const pane = document.querySelector(".tree-pane").getBoundingClientRect();
  const box = panel.getBoundingClientRect();
  // A row's text leaves out its age, which the clock moves; the age is read on its own. A
  // ref's row holds its own line, and a pull request's line under it when it has one.
  const row = (button) => {
    const age = button.querySelector(".source-ref-selector-age");
    return {
      text: [...(button.querySelector(":scope > .source-ref-selector-main") ?? button).children]
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
    commitIds: ${COMMIT_IDS},
    note: root.querySelector(".source-ref-selector-note").textContent,
    error: root.querySelector(".source-ref-selector-error").textContent,
    // The panel is inside the navigation pane, and no row is wider than it.
    inside: box.left >= pane.left - 0.5 && box.right <= pane.right + 0.5 && box.width > 0,
    // The chooser aligns to the same horizontal pane insets as the Files filters.
    spansToolbar: (() => {
      const bar = document.getElementById("nav-filter-bar");
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

// How often a page asks for its root's tallies while it switches, in milliseconds: often
// enough that some fall after the server has switched and before the page has gone.
// Measured 2026-11-18 in headless Chrome 152 on a 10-core Mac at a load average of 90,
// before the page held them: two a run were refused, sent 2 to 14 ms after the switch's
// answer, in each of three runs.
const ASK_EVERY_MS = 10;

/**
 * Click what *pick* finds in the open panel, and time the document that comes back.
 *
 * With *askMeanwhile*, the page asks for its root's tallies every ASK_EVERY_MS from the
 * click until it goes, as its own refresh of them can: that refresh waits half a second
 * after the first rows (fetchRootSummary in app.js), and on CI a switch made that long
 * after the page loaded was refused it (mb-bio7). A page that asked to switch away sends
 * none of these.
 */
async function switchBy(pick, askMeanwhile = false) {
  await chrome.evaluate("window.__left = true; true");
  const clicked = Date.now();
  const asking = askMeanwhile
    ? `setInterval(() => void fetch("/api/tree?depth=0").catch(() => {}), ${ASK_EVERY_MS});`
    : "";
  await chrome.evaluate(`(${pick}).click(); ${asking} true`);
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

// The layout sampled so far, read once a frame has run since the wait before it. The waits
// ask the DOM, which can hold the tree's rows before any frame has drawn them: on a loaded
// runner a new document's first frame can come after the wait answers, and a read then
// finds no top for the tree at all (mb-hujg). A frame's callbacks run in the order they
// were asked for, so the sampler's, asked for in the frame before, runs ahead of this one.
async function sampledLayout() {
  await chrome.evaluate(
    "new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(() => resolve(true))))",
  );
  return chrome.evaluate(LAYOUT);
}

async function clickRefChip(selector) {
  const point = await chrome.evaluate(`(() => {
    const box = document.querySelector(${JSON.stringify(selector)}).getBoundingClientRect();
    return {x: box.left + box.width / 2, y: box.top + box.height / 2};
  })()`);
  await chrome.send("Input.dispatchMouseEvent", { ...point, type: "mouseMoved" });
  const sourceHit = await chrome.evaluate(
    `document.elementFromPoint(${point.x}, ${point.y})?.closest("[data-ref-menu]") ===
     document.querySelector(${JSON.stringify(selector)})`,
  );
  for (const type of ["mousePressed", "mouseReleased"]) {
    await chrome.send("Input.dispatchMouseEvent", {
      ...point,
      type,
      button: "left",
      clickCount: 1,
    });
  }
  return sourceHit;
}

const TAG_CHIP = ".source-ref-selector-label button[data-ref-menu]";
const REF_MENU = "[data-ref-action-menu]";
const result = {};
try {
  await chrome.send("Page.enable");
  await chrome.send("Network.enable");
  // So a request's initiator carries its script's stack, and names its caller.
  await chrome.send("Runtime.enable");
  await chrome.send("Page.addScriptToEvaluateOnNewDocument", { source: LAYOUT_PROBE });

  // 1. The working tree's page.
  result.workingTreeLoadMs = await load("/view/README.md");
  takeDataRequests();
  result.workingTree = await chrome.evaluate(PAGE);
  result.workingTreeLayout = await sampledLayout();
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
  await chrome.evaluate('document.querySelector(".source-ref-selector-kinds button").focus()');
  for (const type of ["keyDown", "keyUp"]) {
    await chrome.send("Input.dispatchKeyEvent", {
      type,
      key: "ArrowRight",
      code: "ArrowRight",
      windowsVirtualKeyCode: 39,
    });
  }
  await chrome.waitFor(
    'document.activeElement.dataset.chipValue === "remote" && document.activeElement.getAttribute("aria-checked") === "true" && document.querySelector(".source-ref-selector-list").getAttribute("aria-busy") === "false"',
  );
  result.workingTreeRemotes = await chrome.evaluate(PANEL);
  result.workingTreeTags = await openPanelList("Tags");
  await openPanelList("Branches");

  // 2. A branch: the revision's page.
  result.workingTreeBrowsing = takeDataRequests();
  const leaving = currentLoader;
  result.toBranch = await switchBy(rowNamed("feature"), true);
  const switched = switchAsked;
  result.branch = await chrome.evaluate(PAGE);
  result.branchLayout = await sampledLayout();
  await capture("revision");

  // 3. Its lists.
  result.branchPanel = await openPanel();
  await capture("revision-panel");
  await closePanel();
  result.revisionRequests = takeDataRequests();
  result.leftBehind = leftBehind(leaving, switched);

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
  result.staleAt = await chrome.evaluate(STALE_AT);
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
  result.tagMenu = await chrome.evaluate(`(async () => {
    const chip = document.querySelector(".source-ref-selector-label [data-ref-menu]");
    const before = chip.getBoundingClientRect().width;
    chip.closest("button").focus();
    const modifiedArrow = new KeyboardEvent("keydown", {
      key: "ArrowDown", bubbles: true, cancelable: true, metaKey: true,
    });
    const arrowLeftAlone = chip.dispatchEvent(modifiedArrow) &&
      document.querySelector("[data-ref-action-menu]") === null;
    chip.click();
    const menu = document.querySelector("[data-ref-action-menu]");
    const copy = menu.querySelector("button");
    let copied;
    Object.defineProperty(navigator, "clipboard", {
      configurable: true, value: { writeText: async (name) => { copied = name; } },
    });
    copy.click();
    await Promise.resolve();
    delete navigator.clipboard;
    const answer = {
      context: menu.getAttribute("aria-label"),
      items: [...menu.querySelectorAll(".menu-item")].map(item => item.textContent),
      copied,
      widthChanged: chip.getBoundingClientRect().width !== before,
      caret: getComputedStyle(chip.querySelector(".git-ref-menu-caret")).display,
      chooserClosed: document.querySelector(".source-ref-selector-panel").hidden,
    };
    const modifiedEscape = new KeyboardEvent("keydown", {
      key: "Escape", bubbles: true, cancelable: true, metaKey: true,
    });
    answer.chordsLeftAlone = arrowLeftAlone && copy.dispatchEvent(modifiedEscape) && menu.isConnected;
    copy.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
    answer.dismissed = document.querySelector("[data-ref-action-menu]") === null;

    const fork = window.metabrowser.refChip("topic/nested", {
      label: "forker:topic/nested", kind: "remote", repository: "forker/demo",
      ref: "refs/remotes/origin/topic/nested",
    });
    fork.id = "test-inline-ref";
    document.querySelector(".header-path").after(fork);
    return answer;
  })()`);
  await clickRefChip("#test-inline-ref");
  result.tagMenu.fork = await chrome.evaluate(`(() => {
    const menu = document.querySelector(${JSON.stringify(REF_MENU)});
    return {
      context: menu.getAttribute("aria-label"),
      url: menu.querySelector("a").href,
      actions: [...menu.querySelectorAll(".menu-item")].map(item => item.textContent),
      focused: menu.contains(document.activeElement),
    };
  })()`);
  await clickRefChip("#test-inline-ref");
  result.tagMenu.fork.repeatClosed = await chrome.evaluate(`
    !document.querySelector(${JSON.stringify(REF_MENU)}) &&
    document.activeElement.id === "test-inline-ref"`);
  await chrome.evaluate('document.getElementById("test-inline-ref").remove()');

  const direct = await clickRefChip(TAG_CHIP);
  const opened = await chrome.evaluate(`
    document.querySelector(${JSON.stringify(REF_MENU)})?.contains(document.activeElement) === true`);
  await clickRefChip(TAG_CHIP);
  const closed = await chrome.evaluate(`!document.querySelector(${JSON.stringify(REF_MENU)}) &&
    document.activeElement.matches(${JSON.stringify(TAG_CHIP)})`);
  result.tagMenu.repeatClick = { direct, opened, closed };
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
  await switchBy(rowNamed("topic"));
  result.checkedOutBranch = await chrome.evaluate(PAGE);
  // The row's own way back, one click from the checked-out branch's revision (mb-cxpq).
  result.toWorkingTreeByButton = await switchBy(
    `document.querySelector("#source-ref-selector .source-ref-selector-back")`,
  );
  result.backByButton = await chrome.evaluate(PAGE);
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
  // Another tab switches the server while Commits is in front: the tab's history still
  // answers, since it is the checkout's whichever revision is served, and the Files
  // tree's is refused, and the offer to reload shows on this tab. The history request is
  // the one the tab itself made for its list, the route's `/log` under `/api/`, asked
  // again as the tab's next page would ask it.
  await chrome.evaluate(`fetch("/api/source/pin", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ working_tree: true }),
  }).then((response) => response.status)`);
  const statuses = await chrome.evaluate(`(() => {
    const history = performance
      .getEntriesByType("resource")
      .map((entry) => new URL(entry.name))
      .find((url) => {
        const [, api, , route] = url.pathname.split("/");
        return api === "api" && route === "log";
      });
    return Promise.all([fetch("/api/tree?depth=1"), fetch(history.pathname + history.search)])
      .then((answers) => answers.map((answer) => answer.status));
  })()`);
  await chrome.waitFor(`!document.querySelector(".source-ref-selector-stale").hidden`);
  result.commitsSwitched = { statuses, at: await chrome.evaluate(STALE_AT) };
  await capture("commits-stale");

  result.documents = documents.slice();
  // The history chip selects its exact ref using the same source route as the chooser.
  await chrome.evaluate(`[...document.querySelectorAll('[class$="graph-row"] [data-ref-menu]')]
    .find(chip => JSON.parse(chip.getAttribute("data-ref-menu")).ref === "refs/tags/v1").click();
    [...document.querySelectorAll("[data-ref-action-menu] button")]
      .find(item => item.textContent === "View This Tag").click(); true`);
  await chrome.waitFor(
    `window.METABROWSER_SOURCE_PIN?.ref === "refs/tags/v1" && ${MOUNTED}`,
    30000,
  );
  result.tagFromHistory = await chrome.evaluate(PAGE);

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

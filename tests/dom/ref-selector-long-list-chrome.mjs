// The branch chooser over thousands of branches in a real engine (mb-dcp2): every branch
// in the list, newest first, with only the rows near the view in the document.
//
// The listing's order and the window's range are browserless (tests/test_source_refs.py,
// tests/dom/source-ref-selector-session.js). What needs a browser is layout: how tall a
// row is, which rows a scroll position puts in view, and whether a key that jumps past
// every drawn row brings its row into view. So this serves the test's checkout with
// `metab`, as a reader does, and in one headless Chrome:
//
//   1. opens the chooser and reads the list: how many rows it says it has, the names
//      drawn, the note, the list's and a row's height, and how many rows are drawn;
//   2. scrolls the list to its middle and reads which row is under the list's center;
//   3. focuses the first row and presses End, then Home;
//   4. types a filter and reads the narrowed list.
//
// It times opening, from the click to the frame after the rows; End, from the key to the
// frame after; and the filter, from its last key to the frame after the narrowed rows.
//
// Usage: node ref-selector-long-list-chrome.mjs METAB CHECKOUT PORT STATE, with CHROME_BIN
// set and CHROME_PROFILES naming where Chrome's profile goes (tests/dom/chrome-session.mjs).
// SHOT, when set, names a PNG that gets the open list, for a person to look at.
// tests/test_ref_selector_long_list_chrome.py owns the directories, builds the checkout,
// and runs this in a process group of its own, which Chrome and the server join. This
// script starts `metab` and Chrome and builds no repository
// (tests/test_git_hook_environment.py).
import { spawn } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { launchChrome } from "./chrome-session.mjs";

const [metab, checkout, port, state] = process.argv.slice(2);
const profiles = process.env.CHROME_PROFILES;
if (!process.env.CHROME_BIN || !profiles || !state) {
  throw new Error("CHROME_BIN, CHROME_PROFILES, and four arguments are required");
}
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
// The server's first line names the port it took, which a port in use moves.
const SERVING = /Serving .* at http:\/\/127\.0\.0\.1:(\d+)\/view\//;
// The filter typed in step 4, a key at a time, as a reader types.
const FILTER = "b-19";

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

const ROOT = `document.getElementById("source-ref-selector")`;
const LIST = `${ROOT}.querySelector(".source-ref-selector-list")`;
const MOUNTED = `(${ROOT}?.querySelector(".source-ref-selector-panel") != null)`;
// Settled: no listing on its way and none waiting on the filter's pause.
const SETTLED = `(() => {
  const shown = window.MetabrowserSourceRefSelector.mounted().snapshot();
  return !shown.loading && !shown.filterPending &&
    ${LIST}.getAttribute("aria-busy") === "false";
})()`;
// Two frames and a task: whatever the last change drew has been laid out and painted.
const FRAMES = `new Promise((done) =>
  requestAnimationFrame(() => requestAnimationFrame(() => setTimeout(() => done(true), 0))))`;

/** The list as drawn: what it says it holds, and the rows in the document. */
const LISTED = `(() => {
  const root = ${ROOT};
  const list = ${LIST};
  const items = [...list.querySelectorAll(".source-ref-selector-item")];
  const focused = document.activeElement;
  const box = list.getBoundingClientRect();
  return {
    setSize: items.length > 0 ? Number(items[0].getAttribute("aria-setsize")) : 0,
    names: items.map((item) => item.querySelector(".source-ref-selector-name").textContent),
    positions: items.map((item) => Number(item.getAttribute("aria-posinset"))),
    note: root.querySelector(".source-ref-selector-note").textContent,
    listHeight: list.clientHeight,
    rowHeight: items.length > 0 ? items[0].getBoundingClientRect().height : 0,
    // Every row is as tall as the first, and each next row starts where the one before it
    // ends: rows placed at one row's height leave no gap and overlap none.
    heights: [...new Set(items.map((item) => item.getBoundingClientRect().height))],
    abutting: items.every((item, at) => {
      const next = items[at + 1];
      return next === undefined ||
        Number(next.getAttribute("aria-posinset")) !== Number(item.getAttribute("aria-posinset")) + 1 ||
        Math.abs(next.getBoundingClientRect().top - item.getBoundingClientRect().bottom) < 0.5;
    }),
    sizerHeight: list.firstElementChild.getBoundingClientRect().height,
    scrollTop: list.scrollTop,
    drawn: list.querySelectorAll("button").length,
    focusedIndex: list.contains(focused) && focused.dataset.index !== undefined
      ? Number(focused.parentElement.getAttribute("aria-posinset"))
      : null,
    focusedName: list.contains(focused)
      ? focused.querySelector(".source-ref-selector-name")?.textContent ?? null
      : null,
    inView: list.contains(focused)
      ? (() => {
          const row = focused.getBoundingClientRect();
          return row.top >= box.top - 0.5 && row.bottom <= box.bottom + 0.5;
        })()
      : null,
  };
})()`;

const server = await serve(checkout, Number(port), state);
const chrome = await launchChrome(process.env.CHROME_BIN, { profiles });

/** Press *key* as a keyboard does, and wait for the frame after. */
async function press(key, code, keyCode) {
  await chrome.send("Input.dispatchKeyEvent", {
    type: "rawKeyDown",
    key,
    code,
    windowsVirtualKeyCode: keyCode,
  });
  await chrome.send("Input.dispatchKeyEvent", {
    type: "keyUp",
    key,
    code,
    windowsVirtualKeyCode: keyCode,
  });
  await chrome.evaluate(FRAMES);
}

try {
  await chrome.send("Page.navigate", { url: `${server.base}/view/` });
  await chrome.waitFor(
    `${MOUNTED} && document.querySelectorAll("#tree-content .tree-item").length > 0`,
  );
  const result = {
    overscan: await chrome.evaluate("window.MetabrowserSourceRefSelector.ROWS_OVERSCAN"),
  };

  // 1. Open: from the click to the frame after the rows.
  let started = Date.now();
  await chrome.evaluate(`${ROOT}.querySelector(".source-ref-selector-toggle").click(); true`);
  await chrome.waitFor(`${SETTLED} && ${LIST}.querySelectorAll("button").length > 0`);
  await chrome.evaluate(FRAMES);
  result.openMs = Date.now() - started;
  result.opened = await chrome.evaluate(LISTED);
  if (process.env.SHOT) {
    const { data } = await chrome.send("Page.captureScreenshot", { format: "png" });
    fs.writeFileSync(process.env.SHOT, Buffer.from(data, "base64"));
  }

  // 2. The middle: the middle row is put at the list's center, and the row found there is
  // the one drawn at its index.
  result.middle = await chrome.evaluate(`(async () => {
    const list = ${LIST};
    const row = list.querySelector(".source-ref-selector-item").getBoundingClientRect().height;
    const count = Number(list.querySelector(".source-ref-selector-item").getAttribute("aria-setsize"));
    const middle = Math.floor(count / 2);
    list.scrollTop = Math.round(middle * row - (list.clientHeight - row) / 2);
    await ${FRAMES};
    const box = list.getBoundingClientRect();
    const under = document.elementFromPoint(
      box.left + box.width / 2,
      box.top + list.clientTop + list.clientHeight / 2,
    );
    const item = under?.closest(".source-ref-selector-item");
    return {
      expectedIndex: middle + 1,
      centerIndex: item ? Number(item.getAttribute("aria-posinset")) : null,
      drawn: list.querySelectorAll("button").length,
    };
  })()`);

  // 3. End and Home, from the first row: End's row was never drawn before the key.
  await chrome.evaluate(`(async () => {
    ${LIST}.scrollTop = 0;
    await ${FRAMES};
    ${LIST}.querySelector("button").focus();
    return true;
  })()`);
  started = Date.now();
  await press("End", "End", 35);
  result.endMs = Date.now() - started;
  result.end = await chrome.evaluate(LISTED);
  await press("Home", "Home", 36);
  result.home = await chrome.evaluate(LISTED);

  // 4. A filter, typed a key at a time, from its last key to the frame after its rows.
  await chrome.evaluate(`${ROOT}.querySelector(".source-ref-selector-filter").focus(), true`);
  for (const key of FILTER) {
    await chrome.send("Input.insertText", { text: key });
  }
  started = Date.now();
  await chrome.waitFor(
    `${SETTLED} && window.MetabrowserSourceRefSelector.mounted().snapshot().listing?.query === ${JSON.stringify(FILTER)}`,
  );
  await chrome.evaluate(FRAMES);
  result.filterMs = Date.now() - started;
  result.filtered = await chrome.evaluate(LISTED);
  console.log(JSON.stringify(result));
} finally {
  await chrome.close();
  await server.stop();
}

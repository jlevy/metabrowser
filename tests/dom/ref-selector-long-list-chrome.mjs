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
//   3. focuses the first row, draws the Files toolbar again around the list, as a tally
//      refresh does, and presses End; draws the toolbar again, and presses Home;
//   4. moves focus down to row KEPT, scrolls the list far from it, and reads that it
//      keeps focus, that Tab from the filter box reaches it, and that ArrowDown brings
//      the next row into view;
//   5. types a filter and reads the narrowed list;
//   6. switches to the oldest branch, and on its page opens the list, which shows the
//      served branch's row, at the foot of the list, rather than the newest.
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
// The filter typed in step 5, a key at a time, as a reader types.
const FILTER = "b-19";
// The row, by its index, that step 4 focuses and scrolls away from.
const KEPT = 5;
// The oldest branch, which step 6 switches to: the last row of every branch.
const OLDEST = "b-0000";

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
    role: list.getAttribute("role"),
    // The served ref's row, where the list says it is, and whether it is in view.
    served: (() => {
      const row = list.querySelector('button[aria-current="true"]');
      if (row === null) {
        return null;
      }
      const at = row.getBoundingClientRect();
      return {
        index: Number(row.parentElement.getAttribute("aria-posinset")),
        name: row.querySelector(".source-ref-selector-name").textContent,
        inView: at.top >= box.top - 0.5 && at.bottom <= box.bottom + 0.5,
      };
    })(),
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
  // A reader's page is focused. A headless one is not until its first key, so it fires no
  // focus events before then, and a redraw of the Files toolbar, which takes the selector
  // out of the page and puts it back (`keepAcrossRefills`), would not know which control
  // to give focus back to: one between step 3's focus and its first key puts focus in the
  // filter box, and End moves nothing, as it did in the pulls session (mb-nbyu, mb-gsz5).
  await chrome.send("Emulation.setFocusEmulationEnabled", { enabled: true });
  await chrome.send("Page.navigate", { url: `${server.base}/view/` });
  await chrome.waitFor(
    `${MOUNTED} && document.querySelectorAll("#tree-content .tree-item").length > 0`,
  );
  const result = {
    overscan: await chrome.evaluate("window.MetabrowserSourceRefSelector.ROWS_OVERSCAN"),
    keptIndex: KEPT,
  };

  // 1. Open: from the click to the frame after the rows. The working tree's page opens
  // its list on the Working tree tab, so the press on Branches follows the click at once.
  let started = Date.now();
  await chrome.evaluate(
    `${ROOT}.querySelector(".source-ref-selector-toggle").click(); ${ROOT}.querySelector('.source-ref-selector-kinds button[data-chip-value="branch"]').click(); true`,
  );
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

  // 2b. A scroll the page makes, with the redraw of something else in the same task: no
  // scroll event has come for it yet, so nothing but the scroll position itself says where
  // the list is. The Files toolbar's redraw, which a tally arriving makes whenever the index
  // is still warming, takes the list out of the page and puts it back, and a redraw of the
  // list's own rows is anchored to where the reader is: neither may put the list anywhere
  // but where the scroll put it (the nightly soak's 6 for 1001, mb-tjbm).
  const SCROLL_THEN = (what, target) => `(async () => {
    const list = ${LIST};
    const row = list.querySelector(".source-ref-selector-item").getBoundingClientRect().height;
    list.scrollTop = 0;
    await ${FRAMES};
    const at = ${target};
    const want = Math.round(at * row - (list.clientHeight - row) / 2);
    list.scrollTop = want;
    ${what}
    await ${FRAMES};
    const box = list.getBoundingClientRect();
    const under = document.elementFromPoint(box.left + box.width / 2, box.top + list.clientTop + list.clientHeight / 2);
    const item = under?.closest(".source-ref-selector-item");
    return {
      want,
      got: list.scrollTop,
      expectedIndex: at + 1,
      centerIndex: item ? Number(item.getAttribute("aria-posinset")) : null,
      drawn: list.querySelectorAll("button").length,
    };
  })()`;
  result.scrollThenToolbar = await chrome.evaluate(SCROLL_THEN("renderNavFilterBar();", 700));
  result.scrollThenToolbarTwice = await chrome.evaluate(
    SCROLL_THEN("renderNavFilterBar(); renderNavFilterBar();", 1200),
  );
  // The list's own render, as a poll or a stale-page notice makes one, in the same task.
  result.scrollThenRender = await chrome.evaluate(
    SCROLL_THEN(
      `window.dispatchEvent(new CustomEvent("metabrowser:pin-changed", { detail: { pin: "x" } }));`,
      1500,
    ),
  );

  // 3. End and Home, from the first row: End's row was never drawn before the key.
  await chrome.evaluate(`(async () => {
    ${LIST}.scrollTop = 0;
    await ${FRAMES};
    ${LIST}.querySelector("button").focus();
    // A redraw of the toolbar before the key, as the index's tallies arriving makes one,
    // leaves focus on the row the key moves from.
    renderNavFilterBar();
    await ${FRAMES};
    return true;
  })()`);
  started = Date.now();
  await press("End", "End", 35);
  result.endMs = Date.now() - started;
  result.end = await chrome.evaluate(LISTED);
  // The Files toolbar is drawn again around the list whenever a filter or a tally
  // changes, and on its own while the index warms up, which under load came after End.
  // That redraw takes the list out of the page and puts it back, which once left it
  // scrolled to its top with only the foot's rows drawn (mb-y1k0).
  await chrome.evaluate(`(async () => {
    renderNavFilterBar();
    await ${FRAMES};
    return true;
  })()`);
  result.redrawn = await chrome.evaluate(LISTED);
  await press("Home", "Home", 36);
  result.home = await chrome.evaluate(LISTED);

  // 4. The row that has focus stays drawn, and keeps focus, however far the list
  // scrolls from it; Tab from the filter box goes back to it.
  for (let at = 0; at < KEPT; at += 1) {
    await press("ArrowDown", "ArrowDown", 40);
  }
  await chrome.evaluate(`(async () => {
    const list = ${LIST};
    list.scrollTop = list.scrollHeight / 2;
    await ${FRAMES};
    return true;
  })()`);
  result.kept = await chrome.evaluate(LISTED);
  await chrome.evaluate(`${ROOT}.querySelector(".source-ref-selector-filter").focus(), true`);
  await press("Tab", "Tab", 9);
  result.tabbed = await chrome.evaluate(LISTED);
  await press("ArrowDown", "ArrowDown", 40);
  result.next = await chrome.evaluate(LISTED);

  // 5. A filter, typed a key at a time, from its last key to the frame after its rows.
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

  // 6. The oldest branch, chosen from the filtered list; its page's list opens on its row.
  await chrome.evaluate(
    `(() => { const box = ${ROOT}.querySelector(".source-ref-selector-filter"); box.focus(); box.select(); return true; })()`,
  );
  await chrome.send("Input.insertText", { text: OLDEST });
  await chrome.waitFor(
    `${SETTLED} && window.MetabrowserSourceRefSelector.mounted().snapshot().listing?.query === ${JSON.stringify(OLDEST)}`,
  );
  await press("ArrowDown", "ArrowDown", 40);
  await chrome.evaluate("window.__left = true; document.activeElement.click(); true");
  await chrome.waitFor(
    `!window.__left && ${MOUNTED} && document.querySelectorAll("#tree-content .tree-item").length > 0`,
  );
  await chrome.evaluate(`${ROOT}.querySelector(".source-ref-selector-toggle").click(); true`);
  await chrome.waitFor(`${SETTLED} && ${LIST}.querySelectorAll("button").length > 0`);
  await chrome.evaluate(FRAMES);
  result.switched = await chrome.evaluate(LISTED);
  console.log(JSON.stringify(result));
} finally {
  await chrome.close();
  await server.stop();
}

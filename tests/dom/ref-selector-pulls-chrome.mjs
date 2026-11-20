// The branch chooser when branches are the heads of pull requests, in a real engine
// (mb-tjbm): a row with a pull request is two lines and a row without one is one, and the
// windowed list places every row by its own height.
//
// What a row says and which rows a filter finds are the server's and browserless
// (tests/test_github_ref_pulls.py, tests/dom/source-ref-selector-session.js), and so is the
// range of rows a scroll draws (`rowWindow`). What needs a browser is layout: how tall each
// kind of row is, that the rows abut at those heights, that the list's box is as tall as
// every row together, which row a scroll position puts at the list's center, that a key
// that jumps past every drawn row brings its row into view, and that a pull request's
// icon, number, and title are drawn, the title cut at the line's end. So this serves the
// test's checkout, whose `origin` is a GitHub repository with its pull requests cached,
// with `metab` as a reader does, and in one headless Chrome:
//
//   1. opens the chooser and waits for the pull requests, then reads the list: the rows'
//      heights, where they sit, the list's box, how many rows are drawn, and what a
//      pull request's line holds;
//   2. scrolls to the middle row and reads which row is under the list's center;
//   3. focuses the first row, presses End, which draws the last row, never drawn before,
//      and Home;
//   4. types `#12`, which finds branches by their pull requests' numbers, and a word of
//      a title that no branch's name has;
//   5. reads the same list with the Files toolbar drawn again around it.
//
// Usage: node ref-selector-pulls-chrome.mjs METAB CHECKOUT PORT STATE, with CHROME_BIN set
// and CHROME_PROFILES naming where Chrome's profile goes (tests/dom/chrome-session.mjs).
// SHOT, when set, names a PNG that gets the open list, for a person to look at.
// tests/test_ref_selector_pulls_chrome.py owns the directories, builds the checkout and the
// cache, and runs this in a process group of its own, which Chrome and the server join.
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
const SERVING = /Serving .* at http:\/\/127\.0\.0\.1:(\d+)\/view\//;
// Typed in step 4, a key at a time: the numbers that start with 12, and a word that is in
// two pull requests' titles and in no branch's name.
const NUMBER_FILTER = "#12";
const TITLE_FILTER = "needlework";

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
const SETTLED = `(() => {
  const shown = window.MetabrowserSourceRefSelector.mounted().snapshot();
  return !shown.loading && !shown.filterPending &&
    ${LIST}.getAttribute("aria-busy") === "false";
})()`;
const FRAMES = `new Promise((done) =>
  requestAnimationFrame(() => requestAnimationFrame(() => setTimeout(() => done(true), 0))))`;
// The pull requests arrived and the plugin that draws their icons loaded and drew them.
const DRAWN = `(() => {
  const shown = window.MetabrowserSourceRefSelector.mounted().snapshot();
  return shown.listing?.pull_requests?.state === "ready" &&
    ${LIST}.querySelector(".source-ref-selector-pull-icon svg") !== null;
})()`;

/**
 * The list as drawn: its rows, their heights, and what each pull request's line holds.
 * *heights* are the two row heights the page drew, which each row's place is compared with.
 */
const listedScript = (heights) => `(() => {
  const list = ${LIST};
  const items = [...list.querySelectorAll(".source-ref-selector-item")];
  const focused = document.activeElement;
  const box = list.getBoundingClientRect();
  const shown = window.MetabrowserSourceRefSelector.mounted().snapshot();
  const refs = shown.listing?.refs ?? [];
  const at = (item) => Number(item.getAttribute("aria-posinset")) - 1;
  const heightOf = (item) => item.getBoundingClientRect().height;
  const withPulls = (item) => item.querySelector(".source-ref-selector-pull") !== null;
  const tops = items.map((item) => item.getBoundingClientRect().top - box.top - list.clientTop + list.scrollTop);
  return {
    setSize: items.length > 0 ? Number(items[0].getAttribute("aria-setsize")) : 0,
    names: items.map((item) => item.querySelector(".source-ref-selector-name").textContent),
    positions: items.map((item) => Number(item.getAttribute("aria-posinset"))),
    listHeight: list.clientHeight,
    plainHeights: [...new Set(items.filter((item) => !withPulls(item)).map(heightOf))],
    tallHeights: [...new Set(items.filter(withPulls).map(heightOf))],
    // Each row is where the heights of the rows before it put it, as the model's own
    // rows have it, and the rows abut: no gap, no overlap.
    placed: items.every((item) => {
      const expected = refs.slice(0, at(item)).reduce(
        (sum, row) => sum + (row.pulls?.length ? ${heights.tall} : ${heights.plain}), 0);
      return Math.abs(tops[items.indexOf(item)] - expected) < 0.5;
    }),
    abutting: items.every((item, index) => {
      const next = items[index + 1];
      return next === undefined || at(next) !== at(item) + 1 ||
        Math.abs(tops[index + 1] - (tops[index] + heightOf(item))) < 0.5;
    }),
    sizerHeight: list.firstElementChild.getBoundingClientRect().height,
    rowsWithPulls: refs.filter((row) => row.pulls?.length).length,
    rowsWithout: refs.filter((row) => !row.pulls?.length).length,
    scrollTop: list.scrollTop,
    drawn: list.querySelectorAll("button").length,
    focusedIndex: list.contains(focused) && focused.dataset.index !== undefined
      ? Number(focused.parentElement.getAttribute("aria-posinset"))
      : null,
    inView: list.contains(focused)
      ? (() => {
          const row = focused.getBoundingClientRect();
          return row.top >= box.top - 0.5 && row.bottom <= box.bottom + 0.5;
        })()
      : null,
    // What a drawn pull request's line holds, for the first few rows that have one: its
    // icon (drawn by the GitHub plugin, in the state's own hue), its number, and its
    // title, and whether the title is cut at the line's end.
    lines: items.filter(withPulls).slice(0, 12).map((item) => {
      const pull = refs[at(item)].pulls[0];
      const line = item.querySelector(".source-ref-selector-pull");
      const title = line.querySelector(".source-ref-selector-pull-title");
      const icon = line.querySelector(".github-pull-state-icon");
      const more = line.querySelector(".source-ref-selector-pull-more");
      const number = line.querySelector(".source-ref-selector-pull-number");
      return {
        number: number.textContent,
        state: pull.state,
        iconState: icon?.dataset.state ?? null,
        iconDrawn: icon?.querySelector("svg") !== null && icon?.querySelector("svg") !== undefined,
        text: title.textContent,
        cut: title.scrollWidth > title.clientWidth,
        fits: line.getBoundingClientRect().right <= item.getBoundingClientRect().right + 0.5,
        more: more?.textContent ?? null,
        numberWeight: getComputedStyle(number).fontWeight,
        titleWeight: getComputedStyle(title).fontWeight,
      };
    }),
  };
})()`;

const server = await serve(checkout, Number(port), state);
const chrome = await launchChrome(process.env.CHROME_BIN, { profiles });

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

const listed = (heights) => chrome.evaluate(listedScript(heights));

try {
  await chrome.send("Page.navigate", { url: `${server.base}/view/` });
  await chrome.waitFor(
    `${MOUNTED} && document.querySelectorAll("#tree-content .tree-item").length > 0`,
  );
  const result = {
    overscan: await chrome.evaluate("window.MetabrowserSourceRefSelector.ROWS_OVERSCAN"),
  };

  // 1. Open, and wait for the pull requests and their icons.
  await chrome.evaluate(`${ROOT}.querySelector(".source-ref-selector-toggle").click(); true`);
  await chrome.waitFor(`${SETTLED} && ${DRAWN}`);
  await chrome.evaluate(FRAMES);
  // The two heights, read from the first row of each kind.
  const heights = await chrome.evaluate(`(() => {
    const items = [...${LIST}.querySelectorAll(".source-ref-selector-item")];
    const of = (item) => item?.getBoundingClientRect().height ?? 0;
    return {
      plain: of(items.find((item) => item.querySelector(".source-ref-selector-pull") === null)),
      tall: of(items.find((item) => item.querySelector(".source-ref-selector-pull") !== null)),
    };
  })()`);
  result.heights = heights;
  result.opened = await listed(heights);
  result.placeholder = await chrome.evaluate(
    `${ROOT}.querySelector(".source-ref-selector-filter").placeholder`,
  );
  if (process.env.SHOT) {
    const { data } = await chrome.send("Page.captureScreenshot", { format: "png" });
    fs.writeFileSync(process.env.SHOT, Buffer.from(data, "base64"));
  }

  // 2. The middle row, put at the list's center; the row found there is the one drawn at
  // its index, whatever heights the rows before it have.
  result.middle = await chrome.evaluate(`(async () => {
    const list = ${LIST};
    const refs = window.MetabrowserSourceRefSelector.mounted().snapshot().listing.refs;
    const tall = ${heights.tall};
    const plain = ${heights.plain};
    const middle = Math.floor(refs.length / 2);
    const top = refs.slice(0, middle).reduce((sum, row) => sum + (row.pulls?.length ? tall : plain), 0);
    const own = refs[middle].pulls?.length ? tall : plain;
    list.scrollTop = Math.round(top - (list.clientHeight - own) / 2);
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
  await press("End", "End", 35);
  result.end = await listed(heights);
  await chrome.evaluate(`(async () => {
    renderNavFilterBar();
    await ${FRAMES};
    return true;
  })()`);
  result.redrawn = await listed(heights);
  await press("Home", "Home", 36);
  result.home = await listed(heights);

  // 4. The filter finds a branch by its pull request's number, and by a word of its title.
  for (const [name, text] of [
    ["byNumber", NUMBER_FILTER],
    ["byTitle", TITLE_FILTER],
  ]) {
    await chrome.evaluate(
      `(() => { const box = ${ROOT}.querySelector(".source-ref-selector-filter"); box.focus(); box.select(); return true; })()`,
    );
    await chrome.send("Input.insertText", { text });
    await chrome.waitFor(
      `${SETTLED} && window.MetabrowserSourceRefSelector.mounted().snapshot().listing?.query === ${JSON.stringify(text)}`,
    );
    await chrome.evaluate(FRAMES);
    result[name] = await listed(heights);
  }
  console.log(JSON.stringify(result));
} finally {
  await chrome.close();
  await server.stop();
}

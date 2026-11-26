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
// icon, title, and number are drawn, the title cut at the line's end. So this serves the
// test's checkout, whose `origin` is a GitHub repository with its pull requests cached,
// with `metab` as a reader does, and in one headless Chrome:
//
//   1. opens the chooser and waits for the pull requests, then reads the list: the rows'
//      heights, where they sit, the list's box, how many rows are drawn, and what a
//      pull request's line holds;
//   2. scrolls to the middle row and reads which row is under the list's center;
//   3. focuses the first row, draws the Files toolbar again, and presses End, which draws
//      the last row, never drawn before, and Home;
//   4. types `#12`, which finds branches by their pull requests' numbers, and a word of
//      a title that no branch's name has;
//   5. reads the same list with the Files toolbar drawn again around it;
//   6. loads the page again with the server saying it is still filling its pull requests,
//      and none yet for the first 300 rows, scrolls to the middle and focuses a row, and
//      reads that an ask that finds nothing new changes nothing in the document (no
//      mutation, the same focused element), and that when the pull requests arrive for the
//      rows above, which makes them taller, the row at the top of the view stays where it
//      was, the focused element is the same one and still in view (mb-tjbm review A1, A2);
//   7. the same, with the list at its foot after End: it is at its foot after, with its last
//      row focused and in view.
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

// The refs route as a server still filling its pull requests answers it: `phase` is "bare"
// while the first ABOVE rows have none, and "arrived" once they have them and the server is
// done. Each ask is counted. Installed in the page, over its own `fetch`.
const ABOVE = 300;
const OVERRIDE = `(() => {
  const real = window.fetch.bind(window);
  window.__phase = "bare";
  window.__asks = 0;
  window.fetch = async (input, init) => {
    const response = await real(input, init);
    const url = typeof input === "string" ? input : input.url;
    if (!url.includes("/api/source/refs") || window.__phase === "real") {
      return response;
    }
    window.__asks += 1;
    const body = await response.clone().json();
    if (window.__phase === "bare") {
      body.refs.slice(0, ${ABOVE}).forEach((row) => {
        delete row.pulls;
        delete row.pulls_total;
      });
      body.pull_requests = { state: "ready", complete: false, refreshing: true };
    }
    return new Response(JSON.stringify(body), { status: 200, headers: response.headers });
  };
  return true;
})()`;
// The index and offset in the list's view of the row at its top: the first row that ends
// below the view's top edge.
const TOP_ROW = `(() => {
  const list = ${LIST};
  const edge = list.getBoundingClientRect().top + list.clientTop;
  const item = [...list.querySelectorAll(".source-ref-selector-item")].find(
    (row) => row.getBoundingClientRect().bottom > edge + 0.5,
  );
  return item ? {
    index: Number(item.getAttribute("aria-posinset")),
    offset: Math.round((item.getBoundingClientRect().top - edge) * 10) / 10,
  } : null;
})()`;
const VIEW_STATE = `(() => {
  const list = ${LIST};
  const box = list.getBoundingClientRect();
  const focused = document.activeElement;
  const mine = list.contains(focused);
  const row = mine ? focused.getBoundingClientRect() : null;
  return {
    top: ${TOP_ROW},
    scrollTop: list.scrollTop,
    scrollHeight: list.scrollHeight,
    clientHeight: list.clientHeight,
    sameFocus: mine && focused === window.__focused && focused.isConnected,
    focusedInView: row !== null && row.top >= box.top - 0.5 && row.bottom <= box.bottom + 0.5,
    focusedIndex: mine ? Number(focused.parentElement.getAttribute("aria-posinset")) : null,
    withPulls: ${LIST}.querySelectorAll(".source-ref-selector-pull").length,
    asks: window.__asks,
    mutations: window.__mutations,
  };
})()`;
const WATCH = `(() => {
  window.__mutations = 0;
  window.__watcher?.disconnect();
  window.__watcher = new MutationObserver((records) => { window.__mutations += records.length; });
  window.__watcher.observe(${LIST}, { subtree: true, childList: true, attributes: true, characterData: true });
  return true;
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
  // A reader's page is focused. A headless one is not until its first key, so it fires no
  // focus events before then, and a redraw of the Files toolbar, which takes the selector
  // out of the page and puts it back (`keepAcrossRefills`), would not know which control
  // to give focus back to. Such a redraw comes whenever the index's tallies change, at any
  // step: one between step 3's focus and its first key put focus in the filter box, so
  // End moved nothing (mb-nbyu).
  await chrome.send("Emulation.setFocusEmulationEnabled", { enabled: true });
  await chrome.send("Page.navigate", { url: `${server.base}/view/` });
  await chrome.waitFor(
    `${MOUNTED} && document.querySelectorAll("#tree-content .tree-item").length > 0`,
  );
  const result = {
    overscan: await chrome.evaluate("window.MetabrowserSourceRefSelector.ROWS_OVERSCAN"),
  };

  // 1. Open, and wait for the pull requests and their icons. The list's rows are drawn
  // when its answer is, and the icons when the GitHub plugin has loaded, which the Pulls
  // tab's idle prefetch has usually done: `coldOpen` says whether the click came first,
  // and how long each took (mb-tjbm review A6).
  await chrome.evaluate(`(() => {
    const t = performance.now();
    const plugin = performance.getEntriesByType("resource").some((e) => e.name.includes("/plugin-static/github/") && e.name.endsWith("/index.js"));
    window.__opened = { at: t, plugin };
    // The working tree's page opens its list on the Working tree tab; Branches is a press on.
    ${ROOT}.querySelector(".source-ref-selector-toggle").click();
    ${ROOT}.querySelector('.source-ref-selector-kinds button[data-chip-value="branch"]').click();
    return true;
  })()`);
  await chrome.waitFor(`${SETTLED}`);
  result.rowsMs = await chrome.evaluate(`Math.round(performance.now() - window.__opened.at)`);
  await chrome.waitFor(`${DRAWN}`);
  result.iconsMs = await chrome.evaluate(`Math.round(performance.now() - window.__opened.at)`);
  result.pluginLoadedAtOpen = await chrome.evaluate(`window.__opened.plugin`);
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
    // A redraw of the toolbar before the key, as the index's tallies arriving makes one,
    // leaves focus on the row the key moves from.
    renderNavFilterBar();
    await ${FRAMES};
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
  // 6. Pull requests that arrive for rows above a list scrolled to its middle.
  /** Load the page again, and open the list with the server still filling its pull requests. */
  const openFilling = async () => {
    await chrome.send("Page.navigate", { url: `${server.base}/view/` });
    await chrome.waitFor(
      `${MOUNTED} && document.querySelectorAll("#tree-content .tree-item").length > 0`,
    );
    await chrome.evaluate(OVERRIDE);
    await chrome.evaluate(
      `${ROOT}.querySelector(".source-ref-selector-toggle").click(); ${ROOT}.querySelector('.source-ref-selector-kinds button[data-chip-value="branch"]').click(); true`,
    );
    await chrome.waitFor(
      `${SETTLED} && window.MetabrowserSourceRefSelector.mounted().snapshot().listing?.pull_requests?.refreshing === true`,
    );
    await chrome.evaluate(FRAMES);
  };
  /** Wait for the list to ask again once more, and for what it draws to settle. */
  const nextAsk = async () => {
    const asks = await chrome.evaluate("window.__asks");
    await chrome.waitFor(`window.__asks > ${asks} && ${SETTLED}`, 15000);
    await chrome.evaluate(FRAMES);
  };
  await openFilling();
  result.fillingBefore = await chrome.evaluate(VIEW_STATE);
  await chrome.evaluate(`(async () => {
    const list = ${LIST};
    const rows = [...list.querySelectorAll(".source-ref-selector-item")];
    list.scrollTop = ${ABOVE} * ${heights.plain} + 100;
    await ${FRAMES};
    const row = [...list.querySelectorAll("button")].find((button) => {
      const box = button.getBoundingClientRect();
      const edge = list.getBoundingClientRect();
      return box.top >= edge.top + 60 && box.bottom <= edge.bottom - 60;
    });
    row.focus();
    window.__focused = document.activeElement;
    return rows.length;
  })()`);
  await chrome.evaluate(WATCH);
  result.scrolled = await chrome.evaluate(VIEW_STATE);
  // An ask that finds nothing new: nothing in the list's document changes.
  await nextAsk();
  result.unchanged = await chrome.evaluate(VIEW_STATE);
  // The pull requests arrive for the rows above the view, and the server is done.
  await chrome.evaluate(`window.__phase = "arrived"; true`);
  await nextAsk();
  result.arrived = await chrome.evaluate(VIEW_STATE);

  // 7. The same at the foot, where End left the list.
  await openFilling();
  await chrome.evaluate(`(async () => {
    ${LIST}.querySelector("button").focus();
    return true;
  })()`);
  await press("End", "End", 35);
  await chrome.evaluate(`window.__focused = document.activeElement; true`);
  await chrome.evaluate(WATCH);
  result.footBefore = await chrome.evaluate(VIEW_STATE);
  await chrome.evaluate(`window.__phase = "arrived"; true`);
  await nextAsk();
  result.footAfter = await chrome.evaluate(VIEW_STATE);
  console.log(JSON.stringify(result));
} finally {
  await chrome.close();
  await server.stop();
}

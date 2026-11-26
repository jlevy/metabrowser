// Every route to an item reveals it in the navigation pane, in headless Chrome against live
// `metab` servers: the GitHub stand-in's checkout with two native stacks, and a repository
// with a long history.
//
//   CHROME_BIN=... CHROME_PROFILES=<dir> [SHOTS_DIR=<dir>] \
//     node tests/dom/nav-reveal-chrome.mjs <checkout URL> <history URL> <deep commit>
//
// tests/test_nav_reveal_chrome.py serves both and owns the profile directory, and stops this
// process's whole group, Chrome included, however the run ends (tests/process_group.py).
//
// After each route it reads the navigation pane as a reader sees it: which tab is in front,
// which row is selected, whether that row lies inside the pane's scroller with nothing
// between them clipping it and no folder above it still travelling, what a panel says of
// an item it cannot show, and where focus is
// (docs/design-system.md, "Navigation Reveals the Item"). The decisions behind them run
// browserlessly in tests/dom/nav-reveal-session.js.
//
// Each step writes `phase <name> <ms since start>` to stderr, so a slow run says where.
import fs from "node:fs";
import path from "node:path";
import { launchChrome } from "./chrome-session.mjs";

const [base, historyBase, deepCommit] = process.argv.slice(2);
if (!base || !historyBase || !deepCommit || !process.env.CHROME_BIN) {
  throw new Error("usage: CHROME_BIN CHROME_PROFILES nav-reveal-chrome.mjs <URL> <URL> <commit>");
}
const SHOTS = process.env.SHOTS_DIR ?? null;
const started = Date.now();
const phase = (name) => process.stderr.write(`phase ${name} ${Date.now() - started}\n`);
// Each wait's bound: a page load, a search, or the fake gh's refresh of the stand-in's list
// or stacks, which takes a second or two on a loaded machine.
const STEP_MS = 30000;

const failures = [];
let checks = 0;
const check = (label, ok, detail = "") => {
  checks += 1;
  if (!ok) {
    const failure = `${label}${detail ? `: ${detail}` : ""}`;
    failures.push(failure);
    // As it happens, so a run that stops later still says what failed before.
    process.stderr.write(`failed ${failure}\n`);
  }
};

// In the page: the box between *element* and the pane's scroller that clips away any of its
// *rect*, as a class name, or null. A folder's body clips its rows while it opens, and it
// can scroll, so a row scrolled into view while its folder opened was scrolled within that
// body and lay inside the pane's bounds, seen by no reader, until the folder was open and
// the row far below the pane (app.js, folderTravelAbove; mb-551m).
const CLIPPED_BY = `((element, rect, scroller) => {
  for (let box = element.parentElement; box && box !== scroller; box = box.parentElement) {
    if (getComputedStyle(box).overflowY !== "visible") {
      const clip = box.getBoundingClientRect();
      if (rect.top < clip.top - 1 || rect.bottom > clip.bottom + 1) {
        return box.className;
      }
    }
  }
  return null;
})`;

// In the page: whether a folder body above *element* still travels, opening or closing. A
// row is read in view only once they stand still: in the first frame of the travel, a row
// scrolled within the opening body sat at that body's top, unclipped and inside the pane,
// and the next frame carried it far below the pane (app.js, folderTravelAbove; mb-551m).
// Each body's own animations, not the document's: others keep running after a landing.
const TRAVELLING = `((element) => {
  for (let body = element.parentElement?.closest(".tree-children"); body; body = body.parentElement?.closest(".tree-children")) {
    if (body.getAnimations().some((animation) => animation.playState === "running")) {
      return true;
    }
  }
  return false;
})`;

// In the page: the navigation pane as a reader sees it, for the row *selector* names.
const PANE = (selector) => `(() => {
  const scroller = document.getElementById("tree-content");
  const view = scroller.getBoundingClientRect();
  const row = document.querySelector(${JSON.stringify(selector)});
  const box = row?.getBoundingClientRect();
  const clip = row ? ${CLIPPED_BY}(row, box, scroller) : null;
  const travelling = row ? ${TRAVELLING}(row) : false;
  const active = document.activeElement;
  const notes = [...document.querySelectorAll(".tree-selection-note, .github-pulls-outside")]
    .filter((note) => note.offsetParent !== null)
    .map((note) => note.textContent);
  return {
    tab: document.querySelector(".nav-tab-bar .tab-btn.active")?.dataset.tab ?? null,
    address: location.pathname,
    row: row ? {
      selected: row.classList.contains("selected") || row.getAttribute("aria-current") === "page",
      inView: row.offsetParent !== null && box.height > 0 && box.top >= view.top - 1 && box.bottom <= view.bottom + 1 && clip === null && !travelling,
      at: [Math.round(box.top), Math.round(box.bottom), Math.round(view.top), Math.round(view.bottom), scroller.scrollTop],
      clip,
      travelling,
    } : null,
    selectedFiles: [...document.querySelectorAll("#tab-files .tree-item.selected")].map((r) => r.dataset.path),
    notes,
    focusInNav: active instanceof Element && active.closest(".tree-pane") !== null,
  };
})()`;

const chrome = await launchChrome(process.env.CHROME_BIN, {
  profiles: process.env.CHROME_PROFILES,
  width: 1280,
  height: 800,
});
try {
  phase("chrome");
  const { evaluate, send } = chrome;
  const pageErrors = [];
  chrome.on("Runtime.exceptionThrown", ({ exceptionDetails }) =>
    pageErrors.push(exceptionDetails.exception?.description ?? exceptionDetails.text),
  );
  await send("Runtime.enable");
  await send("Page.enable");
  // Step 9 presses Control-N and Control-P, which are bound only where Control reaches the
  // page, macOS and iOS, as its navigator says (`controlReachesPage` in
  // static/keyboard-shortcuts.js). So every page here has a Mac's navigator, on every host,
  // CI's Linux runners included, as tests/dom/control-chords-chrome.mjs sets one; the key
  // events are still this Chrome's own.
  await send("Emulation.setUserAgentOverride", {
    userAgent: "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    platform: "MacIntel",
    userAgentMetadata: {
      brands: [],
      platform: "macOS",
      platformVersion: "",
      architecture: "x86",
      model: "",
      mobile: false,
    },
  });
  const waitFor = async (expression, what) => {
    try {
      return await chrome.waitFor(expression, STEP_MS);
    } catch (error) {
      const pane = await evaluate(PANE("body")).catch(() => null);
      throw new Error(
        `${what}: ${error.message}\npane: ${JSON.stringify(pane)}\npage errors: ${pageErrors.join("\n")}`,
      );
    }
  };
  const frames = () =>
    evaluate("new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)))");
  const load = async (url) => {
    const loaded = new Promise((resolve) => chrome.on("Page.loadEventFired", resolve));
    await send("Page.navigate", { url });
    await loaded;
  };
  const shot = async (name) => {
    if (SHOTS === null) {
      return;
    }
    await frames();
    const { data } = await send("Page.captureScreenshot", { format: "png" });
    fs.mkdirSync(SHOTS, { recursive: true });
    fs.writeFileSync(path.join(SHOTS, `${name}.png`), Buffer.from(data, "base64"));
  };
  /** A real key, as the keyboard sends it, to the focused element. */
  const press = async (key, { code = key, keyCode = 0, modifiers = 0, text } = {}) => {
    // A chord types no character, and is sent as one.
    await send("Input.dispatchKeyEvent", {
      type: text === undefined && modifiers !== 0 ? "rawKeyDown" : "keyDown",
      key,
      code,
      modifiers,
      windowsVirtualKeyCode: keyCode,
      ...(text === undefined ? {} : { text }),
    });
    await send("Input.dispatchKeyEvent", {
      type: "keyUp",
      key,
      code,
      modifiers,
      windowsVirtualKeyCode: keyCode,
    });
    await frames();
  };
  /** Quick Search: its key, the query, the first result, and Enter. */
  const quickSearch = async (query, expect) => {
    // Slash, which no view's tabs take: T is a folder's Treemap tab too. Its key is bound
    // once the shell's tools have loaded after the first tree, so a key pressed before then
    // is pressed again.
    const open = `document.activeElement?.matches?.(".search-palette-input") === true`;
    const deadline = Date.now() + STEP_MS;
    while (!(await evaluate(open))) {
      if (Date.now() > deadline) {
        await waitFor(open, "Quick Search opens");
      }
      await evaluate("document.activeElement?.blur?.()");
      await press("/", { code: "Slash", keyCode: 191, text: "/" });
      await chrome.waitFor(open, 1000).catch(() => {});
    }
    // The query as typed, and its own results: a list still showing an earlier query's
    // results is not this query's.
    await evaluate(`(() => {
      const input = document.activeElement;
      input.value = "";
      input.dispatchEvent(new Event("input", { bubbles: true }));
    })()`);
    await send("Input.insertText", { text: query });
    await waitFor(
      `document.activeElement?.value === ${JSON.stringify(query)} && document.querySelector('[role="option"][aria-selected="true"]')?.textContent.includes(${JSON.stringify(expect)}) === true`,
      `Quick Search finds ${expect}`,
    );
    await frames();
    await press("Enter", { code: "Enter", keyCode: 13, text: "\r" });
    await waitFor(
      `document.activeElement?.matches?.(".search-palette-input") !== true`,
      "Quick Search opens its result",
    );
  };
  /** Wait for a route's row, selected and in view, then record what the pane shows. */
  const revealed = async (label, selector, tab) => {
    const ready = `(() => { const p = ${PANE(selector)}; return p.tab === ${JSON.stringify(tab)} && p.row?.selected && p.row.inView; })()`;
    await chrome.waitFor(ready, STEP_MS).catch(() => {});
    const pane = await evaluate(PANE(selector));
    check(`${label}: ${tab} is in front`, pane.tab === tab, JSON.stringify(pane));
    check(`${label}: the row is selected`, pane.row?.selected === true, JSON.stringify(pane));
    check(`${label}: the row is in view`, pane.row?.inView === true, JSON.stringify(pane));
    check(`${label}: focus is not moved to the nav`, !pane.focusInNav, JSON.stringify(pane));
    check(`${label}: nothing is noted`, pane.notes.length === 0, JSON.stringify(pane));
    return pane;
  };
  /**
   * Hold the page's reads of its stacks at their answers until the returned function lets
   * them go, so they arrive after the Pulls list's first window.
   */
  const pausedStacks = [];
  chrome.on("Fetch.requestPaused", ({ requestId }) => pausedStacks.push(requestId));
  const holdStacks = async () => {
    await send("Fetch.enable", {
      patterns: [{ urlPattern: "*/api/plugin/github/stacks*", requestStage: "Response" }],
    });
    return async () => {
      for (const requestId of pausedStacks.splice(0)) {
        // A read the page has since stopped, as hiding the Pulls tab stops it, is not paused.
        await send("Fetch.continueRequest", { requestId }).catch((error) => {
          if (!error.message.includes("Invalid InterceptionId")) {
            throw error;
          }
        });
      }
      await send("Fetch.disable");
    };
  };
  const fileRow = (filePath) => `#tab-files .tree-item[data-path="${filePath}"]`;
  const pullRow = (number) => `#tab-pulls .github-pulls-row[data-number="${number}"]`;

  // 1. The address: a page that loads at a file three folders down.
  await load(`${base}/view/docs/deep/deeper/leaf.md`);
  phase("address");
  await revealed("the address", fileRow("docs/deep/deeper/leaf.md"), "files");
  await shot("address");

  // 2. A link in a document, to a file in folders the tree has closed.
  await load(`${base}/view/docs/links.md`);
  await waitFor(`document.querySelector('#preview-pane a[href*="leaf"]') !== null`, "the link");
  check(
    "a link: the leaf's folders start closed",
    await evaluate(`(() => {
      const folder = document.querySelector('#tab-files .tree-folder[data-path="docs/deep"]');
      return folder?.nextElementSibling?.classList.contains("tree-children-collapsed") ?? true;
    })()`),
  );
  await evaluate(`document.querySelector('#preview-pane a[href*="leaf"]').click()`);
  phase("link");
  await revealed("a link", fileRow("docs/deep/deeper/leaf.md"), "files");

  // 3. Quick Search, to a file in the fourth page of a 1,000-file folder. Only that page
  // is drawn: the pages before it stay behind a "more" row above it, and the last page
  // behind the row that ends the folder.
  await quickSearch("f605", "f605");
  phase("quick search: a long folder");
  await revealed("Quick Search, a long folder", fileRow("long/f605.txt"), "files");
  await shot("long-folder");
  // The long folder as drawn, in order: each run of consecutive rows, and each "more" row.
  const LONG = `(() => {
    const children = document.querySelector('#tab-files .tree-folder[data-path="long"]').nextElementSibling;
    const parts = [];
    let last = null;
    for (const item of children.children) {
      if (item.classList.contains("tree-page-more")) {
        last = null;
        parts.push(item.textContent);
        continue;
      }
      const name = item.dataset.path.slice("long/".length, -".txt".length);
      const number = Number(name.slice(1));
      if (last !== null && number === last + 1) {
        parts[parts.length - 1] = parts[parts.length - 1].split("–")[0] + "–" + name;
      } else {
        parts.push(name);
      }
      last = number;
    }
    return parts;
  })()`;
  const longIs = async (label, expected) => {
    const parts = await evaluate(LONG);
    check(label, JSON.stringify(parts) === JSON.stringify(expected), JSON.stringify(parts));
  };
  await longIs("Quick Search, a long folder: only the page that holds the row is drawn", [
    "f000–f199",
    "Show 400 more (1000 total)",
    "f600–f799",
    "Show 200 more (1000 total)",
  ]);
  // The "more" row above the revealed page draws the page before it there: the revealed
  // row stays where it is, in view and selected, and the folder reads in order.
  const MORE_ABOVE = `document.querySelector('#tab-files .tree-item[data-path="long/f600.txt"]').previousElementSibling`;
  for (const [press, drawn, expected] of [
    [
      1,
      "f399",
      ["f000–f399", "Show 200 more (1000 total)", "f600–f799", "Show 200 more (1000 total)"],
    ],
    [2, "f599", ["f000–f799", "Show 200 more (1000 total)"]],
  ]) {
    await evaluate(`${MORE_ABOVE}.scrollIntoView({ block: "nearest" })`);
    await frames();
    const before = await evaluate(PANE(fileRow("long/f605.txt")));
    check(
      `the "more" row above the revealed page, press ${press}: the revealed row is in view first`,
      before.row?.inView === true,
      JSON.stringify(before),
    );
    await evaluate(`${MORE_ABOVE}.click()`);
    await waitFor(
      `document.querySelector(${JSON.stringify(fileRow(`long/${drawn}.txt`))}) !== null`,
      `press ${press} draws the page before the revealed one`,
    );
    await frames();
    const after = await evaluate(PANE(fileRow("long/f605.txt")));
    check(
      `the "more" row above the revealed page, press ${press}: the revealed row stays in view`,
      after.row?.inView === true && after.row?.selected === true,
      JSON.stringify({ before: before.row, after: after.row }),
    );
    await longIs(`the "more" row above the revealed page, press ${press}: in order`, expected);
  }
  phase("the rows a reveal left behind");

  // 4. Quick Search to the file shown, after the reader closed its folder: opening it
  // again reveals it. The folder closes as its chevron's toggle does, without opening it.
  await evaluate(
    `toggleTreeFolder(document.querySelector('#tab-files .tree-folder[data-path="long"]'))`,
  );
  // Closed, and done travelling, as a reader sees it before reaching for Quick Search: the
  // close travels about 140 ms, and the tree's scroll shrinks with it, so the step waits
  // until no animation runs and the scroll has held still for three frames.
  await waitFor(
    `new Promise((resolve) => {
      const children = document.querySelector('#tab-files .tree-folder[data-path="long"]').nextElementSibling;
      const scroller = document.getElementById("tree-content");
      let still = 0;
      let last = scroller.scrollTop;
      const tick = () => {
        const settled = children.classList.contains("tree-children-collapsed") && children.getAnimations({ subtree: true }).length === 0 && scroller.scrollTop === last;
        still = settled ? still + 1 : 0;
        last = scroller.scrollTop;
        if (still >= 3) { resolve(true); } else { requestAnimationFrame(tick); }
      };
      requestAnimationFrame(tick);
    })`,
    "the long folder closes",
  );
  await quickSearch("f605", "f605");
  phase("quick search: the file shown");
  await revealed("Quick Search, the file shown", fileRow("long/f605.txt"), "files");

  // The reader scrolls the tree away from that row before leaving Files.
  await evaluate(`document.getElementById("tree-content").scrollTop = 0`);
  await frames();

  // 5. Quick Search to a pull request in a stack the reader closed, from the Pulls tab
  // scrolled away from it.
  await evaluate(`document.querySelector('.nav-tab-bar .tab-btn[data-tab="pulls"]').click()`);
  await waitFor(
    `document.querySelector('#tab-pulls .github-pulls-stack-row[data-stack="286"]') !== null`,
    "Stack #286 in the Pulls tab",
  );
  await evaluate(
    `document.querySelector('#tab-pulls .github-pulls-stack-row[data-stack="286"]').click()`,
  );
  await waitFor(
    `document.querySelector('#tab-pulls .github-pulls-stack-row[data-stack="286"]').getAttribute("aria-expanded") === "false"`,
    "Stack #286 closes",
  );
  await evaluate(`document.getElementById("tree-content").scrollTop = 1e6`);
  await frames();
  await quickSearch("#7", "#7");
  phase("quick search: a pull request");
  await revealed("Quick Search, a pull request in a closed stack", pullRow(7), "pulls");
  check(
    "Quick Search, a pull request: its stack opened",
    (await evaluate(
      `document.querySelector('#tab-pulls .github-pulls-stack-row[data-stack="286"]').getAttribute("aria-expanded")`,
    )) === "true",
  );
  await shot("pull-in-stack");

  // 6. Back, twice: to the list, then to the file the reader left scrolled away.
  await evaluate("history.back()");
  await waitFor(`location.pathname === "/pulls"`, "Back to the list");
  await evaluate("history.back()");
  await waitFor(`location.pathname === "/view/long/f605.txt"`, "Back to the file");
  phase("back");
  await revealed("Back", fileRow("long/f605.txt"), "files");

  // 7. Forward, twice: to the pull request.
  await evaluate("history.forward()");
  await waitFor(`location.pathname === "/pulls"`, "Forward to the list");
  await evaluate("history.forward()");
  await waitFor(`location.pathname === "/pull/7"`, "Forward to the pull request");
  phase("forward");
  await revealed("Forward", pullRow(7), "pulls");

  // 8. The address of a pull request: a page that loads at #7.
  await load(`${base}/pull/7`);
  phase("a pull request's address");
  await revealed("a pull request's address", pullRow(7), "pulls");
  // Again, with the stacks read after the list's first window, as a loaded machine can read
  // them: the first window reveals #7 far down the flat list, and the regroup that the
  // stacks bring leaves it in view. A paint that kept the first row in view instead moved
  // #7 into its stack, out of view.
  const release = await holdStacks();
  await load(`${base}/pull/7`);
  await revealed("a pull request's address, before its stacks", pullRow(7), "pulls");
  const flat = await evaluate(PANE(pullRow(7)));
  const level = `document.querySelector(${JSON.stringify(pullRow(7))})?.getAttribute("aria-level")`;
  check(
    "a pull request's address, before its stacks: the list is flat",
    (await evaluate(level)) === "1",
    JSON.stringify(flat),
  );
  await release();
  await waitFor(`${level} === "2"`, "#7 is grouped under its stack");
  await frames();
  phase("a pull request's address, stacks after the first window");
  const grouped = await evaluate(PANE(pullRow(7)));
  check(
    "a pull request's address, stacks after the first window: the row stays in view",
    grouped.row?.inView === true && grouped.row?.selected === true,
    JSON.stringify({ flat: flat.row, grouped: grouped.row }),
  );

  // 9. A key that opens an item: Control-N or Control-P walks the stack from #7 to its
  // neighbour, which the Pulls tab reveals, under All when its filter leaves it out. #7
  // ends its stack, so one of the two goes nowhere. On a page that reached #7 by Forward on
  // a server that had just started, neither chord walked, with or without this change
  // (2026-11-15), so the walk starts from the page's own address. The chords are bound
  // because the page's navigator names a Mac (above); under Linux's neither walks.
  await evaluate("document.activeElement?.blur?.()");
  await waitFor(
    `typeof window.metabrowser?.debug?.pullPage()?.hasStack === "function" && window.metabrowser.debug.pullPage().hasStack()`,
    "the page knows its stack",
  );
  // The page's stack walk answers once its stack is read, so a chord that came first is
  // pressed again.
  const walkedAway = `location.pathname !== "/pull/7"`;
  const walkDeadline = Date.now() + STEP_MS;
  for (let turn = 0; !(await evaluate(walkedAway)); turn += 1) {
    if (Date.now() > walkDeadline) {
      const diag = await evaluate(
        `JSON.stringify({keys: window.__keys, stack: window.metabrowser.debug.pullPage()?.hasStack?.(), active: document.activeElement?.tagName, tab: document.querySelector('.nav-tab-bar .tab-btn.active')?.dataset.tab})`,
      );
      await waitFor(walkedAway, `Control-N or Control-P walks the stack ${diag}`);
    }
    if (turn === 0) {
      await evaluate(
        `window.__keys = []; addEventListener("keydown", (e) => window.__keys.push(e.key + (e.ctrlKey ? "+ctrl" : "") + (e.defaultPrevented ? "!" : "")), true)`,
      );
    }
    await evaluate("document.activeElement?.blur?.()");
    await press(turn % 2 === 0 ? "n" : "p", {
      code: turn % 2 === 0 ? "KeyN" : "KeyP",
      keyCode: turn % 2 === 0 ? 78 : 80,
      modifiers: 2,
    });
    await chrome.waitFor(walkedAway, 1000).catch(() => {});
  }
  const walked = Number((await evaluate("location.pathname")).split("/")[2]);
  phase("stack walk");
  // #7's one neighbour in its stack is #8, which the stand-in has merged
  // (tests/github_pull_fixture.py), and the list opens under Open, which leaves it out: the
  // list moves to All, which reveals it like any other row, with nothing noted.
  check("a stack key from #7 walks to merged #8", walked === 8, JSON.stringify({ walked }));
  await revealed(`a stack key to #${walked}`, pullRow(walked), "pulls");
  const LIST_FILTER = `document.querySelector("#tab-pulls .github-pulls-list")?.dataset.filter ?? null`;
  const listFilter = await evaluate(LIST_FILTER);
  check(
    `a stack key to #${walked}: the list moves to All`,
    listFilter === "all",
    JSON.stringify({ walked, listFilter }),
  );
  await shot("control-n");

  // 9b. The same walk from #7's row with focus on it, as J and K leave it. The move to All
  // draws the list again, so the row that had focus goes; #8's row takes focus in its place,
  // rather than focus falling to the page's body.
  await load(`${base}/pull/7`);
  await revealed("a pull request's address, before a walk from its row", pullRow(7), "pulls");
  await waitFor(
    `typeof window.metabrowser?.debug?.pullPage()?.hasStack === "function" && window.metabrowser.debug.pullPage().hasStack()`,
    "the page knows its stack, for a walk from its row",
  );
  const focusSeven = `(() => { const row = document.querySelector(${JSON.stringify(pullRow(7))}); row?.focus(); return row !== null && document.activeElement === row; })()`;
  const focusedDeadline = Date.now() + STEP_MS;
  for (let turn = 0; !(await evaluate(walkedAway)); turn += 1) {
    if (Date.now() > focusedDeadline) {
      await waitFor(walkedAway, "Control-N or Control-P walks the stack from #7's focused row");
    }
    check(`#7's row takes focus before a walk (turn ${turn})`, await evaluate(focusSeven));
    await press(turn % 2 === 0 ? "n" : "p", {
      code: turn % 2 === 0 ? "KeyN" : "KeyP",
      keyCode: turn % 2 === 0 ? 78 : 80,
      modifiers: 2,
    });
    await chrome.waitFor(walkedAway, 1000).catch(() => {});
  }
  phase("stack walk from a focused row");
  const eightFocused = `(() => { const row = document.querySelector(${JSON.stringify(pullRow(8))}); return row !== null && document.activeElement === row; })()`;
  await chrome.waitFor(eightFocused, STEP_MS).catch(() => {});
  const fromRow = await evaluate(PANE(pullRow(8)));
  const fromRowDetail = JSON.stringify({
    ...fromRow,
    path: await evaluate("location.pathname"),
    filter: await evaluate(LIST_FILTER),
    active: await evaluate(
      "document.activeElement?.className + ' ' + (document.activeElement?.dataset?.number ?? '')",
    ),
  });
  check(
    "a stack key from #7's focused row: the list moves to All",
    (await evaluate(LIST_FILTER)) === "all",
    fromRowDetail,
  );
  check(
    "a stack key from #7's focused row: #8 is selected and in view",
    fromRow.row?.selected === true && fromRow.row?.inView === true,
    fromRowDetail,
  );
  check(
    "a stack key from #7's focused row: #8's row has focus",
    await evaluate(eightFocused),
    fromRowDetail,
  );
  check(
    "a stack key from #7's focused row: nothing is noted",
    fromRow.notes.length === 0,
    fromRowDetail,
  );

  const STACK = `#tab-pulls .github-pulls-stack-row[data-stack="286"]`;
  const stackState = () =>
    evaluate(
      `document.querySelector(${JSON.stringify(STACK)})?.getAttribute("aria-expanded") ?? null`,
    );
  const closeStack = async () => {
    await waitFor(`document.querySelector(${JSON.stringify(STACK)}) !== null`, "Stack #286");
    if ((await stackState()) !== "false") {
      await evaluate(`document.querySelector(${JSON.stringify(STACK)}).click()`);
    }
    await waitFor(
      `document.querySelector(${JSON.stringify(STACK)}).getAttribute("aria-expanded") === "false"`,
      "Stack #286 closes",
    );
  };
  const scrollTop = () => evaluate(`document.getElementById("tree-content").scrollTop`);
  const scrollAway = async () => {
    await evaluate(`document.getElementById("tree-content").scrollTop = 1e6`);
    await frames();
    return scrollTop();
  };
  // A step that moves nothing has had the time a reveal takes to move something.
  const settled = async () => {
    await evaluate("new Promise((resolve) => setTimeout(resolve, 400))");
    await frames();
  };
  const tabButton = (tab) => `document.querySelector('.nav-tab-bar .tab-btn[data-tab="${tab}"]')`;
  const activeIs = (tab) =>
    `document.querySelector(".nav-tab-bar .tab-btn.active")?.dataset.tab === "${tab}"`;

  // 10. Quick Search for the pull request shown, after the Pulls tab's button returned to it
  // with the list as the reader left it: the reveal ends that kept place, and opens the
  // stack the reader closed since. The page's stacks are held past the list's first window
  // until the reader is on Files, as a loaded machine can read them: the regroup they bring
  // while the reader is away, or as the list returns, leaves #7 where its reveal put it,
  // under its stack's row. A list that forgot that place on the way came back where #7 had
  // stood in the flat list, with #7 regrouped far above the pane and its stack's row
  // undrawn (CI on main at 5b1d2b055).
  const releaseAway = await holdStacks();
  await load(`${base}/pull/7`);
  await revealed("a pull request's address, before its tab's button", pullRow(7), "pulls");
  await evaluate(`${tabButton("files")}.click()`);
  await waitFor(activeIs("files"), "the Files tab's button");
  await releaseAway();
  await evaluate(`${tabButton("pulls")}.click()`);
  await waitFor(
    `${activeIs("pulls")} && location.pathname === "/pull/7"`,
    "the Pulls tab's button returns to #7",
  );
  await waitFor(`${level} === "2"`, "#7 is grouped under its stack after the tab's button");
  await frames();
  const returned = await evaluate(PANE(pullRow(7)));
  check(
    "the Pulls tab's button, stacks after the first window: #7 stays in view",
    returned.row?.inView === true && returned.row?.selected === true,
    JSON.stringify(returned),
  );
  await closeStack();
  await scrollAway();
  await quickSearch("#7", "#7");
  phase("quick search: the pull request shown, after its tab's button");
  await revealed(
    "Quick Search, the pull request shown after its tab's button",
    pullRow(7),
    "pulls",
  );
  check(
    "Quick Search, the pull request shown after its tab's button: its stack opened",
    (await stackState()) === "true",
  );

  // 11. Another tab of the pull request shown is a step within it: the page's Changes tab
  // leaves the stack the reader closed closed, and the list where the reader scrolled it.
  await closeStack();
  const beforeTab = await scrollAway();
  await evaluate(`document.activeElement?.blur?.()`);
  await evaluate(
    `document.querySelector('#preview-pane a.tab-btn[role="tab"][href="/pull/7/files"]').click()`,
  );
  await waitFor(`location.pathname === "/pull/7/files"`, "the page's Changes tab");
  await settled();
  phase("the page's tab");
  const afterTab = { stack: await stackState(), scrollTop: await scrollTop(), before: beforeTab };
  check(
    "the page's Changes tab: the closed stack stays closed",
    afterTab.stack === "false",
    JSON.stringify(afterTab),
  );
  check(
    "the page's Changes tab: the list stays where the reader scrolled it",
    Math.abs(afterTab.scrollTop - beforeTab) <= 1,
    JSON.stringify(afterTab),
  );

  // 12. A changed file of the pull request shown, clicked in the Pulls tab or walked with J,
  // is a step within it: the list stays on the reader's row, well below the pull request's
  // own, rather than jumping back to it. #106 has 250 changed files.
  await load(`${base}/pull/106`);
  await revealed("a pull request with 250 changed files", pullRow(106), "pulls");
  await evaluate(`document.querySelector(${JSON.stringify(pullRow(106))}).focus()`);
  // Right on the row opens its changed files, as on a folder's, and focus stays on the row: a
  // pull request's three lines are one item and one stop (mb-1z7j).
  await press("ArrowRight", { code: "ArrowRight", keyCode: 39 });
  await waitFor(
    `document.querySelector(${JSON.stringify(pullRow(106))})?.getAttribute("aria-expanded") === "true"`,
    "Right opens #106's changed files",
  );
  const FILE_ROW = (name) =>
    `#tab-pulls a.github-pull-file-row[href="/pull/106/files/src/app/plugins/github/${name}"]`;
  const clicked = FILE_ROW("mod_040.py");
  await waitFor(
    `document.querySelector('#tab-pulls .github-pulls-item[data-number="106"] .github-pull-file-row') !== null`,
    "#106's changed files are read",
  );
  // The file tree draws the rows near the view, so the list is scrolled down to the file.
  await waitFor(
    `(async () => {
      const scroller = document.getElementById("tree-content");
      for (let turn = 0; turn < 40 && document.querySelector(${JSON.stringify(clicked)}) === null; turn += 1) {
        scroller.scrollTop += 300;
        await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
      }
      return document.querySelector(${JSON.stringify(clicked)}) !== null;
    })()`,
    "#106's mod_040.py is drawn",
  );
  await evaluate(
    `document.querySelector(${JSON.stringify(clicked)}).scrollIntoView({ block: "center" })`,
  );
  await frames();
  const beforeClick = await scrollTop();
  await evaluate(`document.querySelector(${JSON.stringify(clicked)}).click()`);
  await waitFor(
    `location.pathname === "/pull/106/files/src/app/plugins/github/mod_040.py"`,
    "the clicked file's address",
  );
  await settled();
  phase("a changed file clicked");
  const afterClick = await evaluate(PANE(clicked));
  check(
    "a changed file clicked: the list stays where the reader scrolled it",
    Math.abs(afterClick.row?.at?.[4] - beforeClick) <= 1,
    JSON.stringify({ beforeClick, afterClick }),
  );
  check(
    "a changed file clicked: its row stays in view",
    afterClick.row?.inView === true,
    JSON.stringify(afterClick),
  );
  // J from mod_044.py, three times: each opens the next file, and the row J moved to,
  // which has focus, stays in view.
  await evaluate(`document.querySelector(${JSON.stringify(FILE_ROW("mod_044.py"))}).focus()`);
  const FOCUSED = `(() => {
    const scroller = document.getElementById("tree-content");
    const view = scroller.getBoundingClientRect();
    const row = document.activeElement;
    const box = row?.getBoundingClientRect?.();
    return {
      address: location.pathname,
      row: row?.getAttribute?.("href") ?? null,
      inView: Boolean(box) && row.offsetParent !== null && box.height > 0 && box.top >= view.top - 1 && box.bottom <= view.bottom + 1 && ${CLIPPED_BY}(row, box, scroller) === null && !${TRAVELLING}(row),
      scrollTop: scroller.scrollTop,
    };
  })()`;
  for (let walk = 1; walk <= 3; walk += 1) {
    const from = await evaluate("location.pathname");
    await press("j", { code: "KeyJ", keyCode: 74, text: "j" });
    await waitFor(`location.pathname !== ${JSON.stringify(from)}`, `J ${walk} opens the next file`);
    await settled();
    const walked = await evaluate(FOCUSED);
    check(
      `J ${walk} through #106's files: the row J moved to has focus and stays in view`,
      walked.inView && walked.row === walked.address,
      JSON.stringify(walked),
    );
  }
  phase("J through a pull request's files");

  // 13. Two reveals in one long folder, the second above the first: the "more" row below
  // the second's page, pressed by a reader reading down to it, draws its page down from
  // there, with its first row in view and focused, and the row the reader left in view.
  await load(`${base}/view/long/f905.txt`);
  await revealed("a long folder's fifth page by its address", fileRow("long/f905.txt"), "files");
  await quickSearch("f405", "f405");
  phase("quick search: a second page of a long folder");
  await revealed("Quick Search, a second page of a long folder", fileRow("long/f405.txt"), "files");
  await longIs("two reveals in one long folder: each draws only its page", [
    "f000–f199",
    "Show 200 more (1000 total)",
    "f400–f599",
    "Show 200 more (1000 total)",
    "f800–f999",
  ]);
  const MORE_BELOW = `document.querySelector('#tab-files .tree-item[data-path="long/f599.txt"]').nextElementSibling`;
  await evaluate(`${MORE_BELOW}.scrollIntoView({ block: "nearest" })`);
  await frames();
  await evaluate(`${MORE_BELOW}.click()`);
  await waitFor(
    `document.querySelector(${JSON.stringify(fileRow("long/f600.txt"))}) !== null`,
    `the "more" row below the reader's draws its page`,
  );
  await frames();
  const below = await evaluate(PANE(fileRow("long/f600.txt")));
  const left = await evaluate(PANE(fileRow("long/f599.txt")));
  const focusedRow = await evaluate(`document.activeElement?.dataset?.path ?? null`);
  const pressedBelow = JSON.stringify({ f600: below.row, f599: left.row, focusedRow });
  check(
    `the "more" row below the reader's: its first row is in view`,
    below.row?.inView === true,
    pressedBelow,
  );
  check(
    `the "more" row below the reader's: its first row has focus`,
    focusedRow === "long/f600.txt",
    pressedBelow,
  );
  check(
    `the "more" row below the reader's: the row above it stays in view`,
    left.row?.inView === true,
    pressedBelow,
  );
  await longIs(`the "more" row below the reader's: in order`, [
    "f000–f199",
    "Show 200 more (1000 total)",
    "f400–f999",
  ]);
  phase("the row below a second reveal");

  // 14. A file a filter hides: the tree selects nothing else and says why.
  await load(`${base}/view/README.md`);
  await revealed("before the filter", fileRow("README.md"), "files");
  await evaluate(`window.metabrowser.filterState.set({ types: [".md"] })`);
  await waitFor(
    `document.querySelector(${JSON.stringify(fileRow("src"))}) === null`,
    "the filter hides src",
  );
  await quickSearch("app.txt", "app.txt");
  await waitFor(`location.pathname === "/view/src/app.txt"`, "the hidden file opens");
  await waitFor(
    `[...document.querySelectorAll(".tree-selection-note")].some((n) => n.textContent === "src/app.txt is outside this filter.")`,
    "the tree names the hidden file",
  );
  phase("filtered");
  const filtered = await evaluate(PANE(fileRow("src/app.txt")));
  check("a filtered file: Files is in front", filtered.tab === "files", JSON.stringify(filtered));
  check(
    "a filtered file: no other row stays selected",
    filtered.selectedFiles.length === 0,
    JSON.stringify(filtered),
  );
  await shot("filtered");
  await evaluate(`window.metabrowser.filterState.set({ types: null })`);

  // 15. A commit's address, halfway down a 300-commit history.
  await load(`${historyBase}/commit/${deepCommit}`);
  phase("commit");
  await revealed(
    "a commit's address",
    `#tab-git .git-graph-row[data-revision="${deepCommit}"]`,
    "git",
  );
  await shot("commit");

  // 16. A document's links to a commit, a pull request, and the list open each in place
  // (mb-0uzt): its tab comes to the front and its panel reveals it, and the page is not
  // loaded again, so a mark set on its window before the click is still there after.
  const routeLink = async (label, href, tab, row) => {
    await load(`${base}/view/docs/links.md`);
    const link = `document.querySelector('#preview-pane a[href=${JSON.stringify(href)}]')`;
    // Its click is the tab controller's once the shell tools and the Pulls tab's routes
    // have loaded; until then the browser follows it, as a link it is.
    await waitFor(
      `${link} !== null && document.documentElement.dataset.shellToolsReady === "true" && window.MetabrowserPullRoute !== undefined`,
      `${label}: the link`,
    );
    await evaluate(`(() => { window.metabrowserStayed = true; ${link}.click(); })()`);
    phase(label);
    if (row !== null) {
      await revealed(label, row, tab);
    }
    await waitFor(
      `location.pathname === ${JSON.stringify(href)} && document.querySelector(".nav-tab-bar .tab-btn.active")?.dataset.tab === ${JSON.stringify(tab)}`,
      `${label}: the address and its tab`,
    );
    check(
      `${label}: opened in place`,
      (await evaluate("window.metabrowserStayed === true")) === true,
    );
  };
  const headLink = await (async () => {
    await load(`${base}/view/docs/links.md`);
    await waitFor(
      `document.querySelector('#preview-pane a[href^="/commit/"]') !== null`,
      "a document's commit link",
    );
    return evaluate(
      `document.querySelector('#preview-pane a[href^="/commit/"]').getAttribute("href")`,
    );
  })();
  await routeLink(
    "a document's link to a commit",
    headLink,
    "git",
    `#tab-git .git-graph-row[data-revision="${headLink.slice("/commit/".length)}"]`,
  );
  await routeLink("a document's link to a pull request", "/pull/8", "pulls", pullRow(8));
  await routeLink("a document's link to the list", "/pulls", "pulls", null);
  await shot("route-links");

  check("no script error on the page", pageErrors.length === 0, pageErrors.join("\n"));
} finally {
  await chrome.close();
}
if (failures.length > 0) {
  process.stderr.write(`${failures.join("\n")}\n`);
  process.exit(1);
}
process.stdout.write(`nav reveal in Chrome: ${checks} checks passed\n`);

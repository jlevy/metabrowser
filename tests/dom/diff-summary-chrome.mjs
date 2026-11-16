// A multi-file diff's Diff summary in the running app, laid out by headless Chrome: a served
// folder of patches, the shell's own page, and the diff plugin's header and tree.
//
//   CHROME_BIN=/path/to/chrome CHROME_PROFILES=/dir/the/caller/removes \
//     node tests/dom/diff-summary-chrome.mjs METAB ROOT PORT STATE_DIR COMMIT
//
// tests/test_changed_file_rows_chrome.py writes the folder, a Git repository whose COMMIT
// changes several files, owns the profile and STATE_DIR, runs this in a process group of its
// own, which Chrome and the server join, and judges the one JSON line it prints.
//
// What it measures is layout, which no browserless DOM computes (docs/design-system.md,
// "Diff Summary"; mb-hi4l): where the header's chevron and words start, and where each row
// of the opened tree starts at every depth, so its first level is one indentation step in
// from the header and each level one more; that the opened tree has no scroll bar of its own
// and is as tall as its rows, in the page's flow; that on a long change set only the rows in
// the window's view of the tree and its overscan are in the document, as the page scrolls;
// that the header starts collapsed with no tree; and that the keys and the focus ring are
// the tree's. This is the summary in a patch's toolbar; under a commit's identity and in a
// pull request's header, the commit summary and pull request header Chrome sessions
// measure its indentation.
//
// It also reads the chrome around the diff (`CHROME` below), on the patch and on COMMIT's
// page, where the toolbar holds the layout control alone: that the toolbar draws no rule
// and the first file card starts the cards' gap below it ("Diff Layout Control"; mb-a073),
// and the computed weight of every run of text in the count summaries the page shows, the
// Diff summary's header, the Files totals, and the Commits tally, so a number reads bold
// and a word regular ("Count Summaries Bold Their Numbers"; mb-roa9).
import { spawn } from "node:child_process";
import path from "node:path";
import { launchChrome } from "./chrome-session.mjs";

const [metab, root, port, state, commit] = process.argv.slice(2);
const base = `http://127.0.0.1:${port}`;
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
const started = Date.now();
const phase = (name) => process.stderr.write(`phase ${name} ${Date.now() - started}\n`);

async function serve() {
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
      }
    },
  };
}

const frames =
  "new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(() => resolve(true))))";

// In the page: the header, and the opened tree's box and rows, in client pixels.
const LAYOUT = `(() => {
  const round = (value) => Math.round(value * 100) / 100;
  const toggle = document.querySelector(".diff-summary-toggle");
  const body = document.querySelector(".diff-summary-body");
  const list = body?.querySelector(".diff-summary-rows");
  const left = (node) => node.getBoundingClientRect().left;
  const rows = body ? [...body.querySelectorAll('[role="treeitem"]')] : [];
  const bodyStyle = body ? getComputedStyle(body) : null;
  return {
    expanded: toggle.getAttribute("aria-expanded"),
    mounted: body !== null,
    step: parseFloat(getComputedStyle(document.documentElement).getPropertyValue("--tree-indent")),
    rowHeight: parseFloat(getComputedStyle(document.documentElement).getPropertyValue("--ui-row-height")),
    viewHeight: innerHeight,
    header: {
      chevron: round(left(toggle.querySelector(".diff-summary-chevron"))),
      words: round(left(toggle.querySelector(".diff-summary-files"))),
    },
    body: body === null ? null : {
      overflowY: bodyStyle.overflowY,
      height: round(body.getBoundingClientRect().height),
      listHeight: round(list.getBoundingClientRect().height),
      ownScroll: body.scrollHeight - body.clientHeight,
      scrollBar: body.offsetWidth - body.clientWidth,
      rowCount: Math.round(list.getBoundingClientRect().height / parseFloat(getComputedStyle(document.documentElement).getPropertyValue("--ui-row-height"))),
    },
    drawn: rows.length,
    rows: rows.slice(0, 12).map((row) => ({
      id: row.dataset.id,
      level: Number(row.getAttribute("aria-level")),
      lead: round(left(row.children[0])),
      name: round(left(row.children[1])),
    })),
  };
})()`;

// The Commits tally, named by its place: the one metadata line that stands in a toolbar's
// slot (static/styles.css, `.nav-toolbar > .nav-metadata`). Its own classes begin with a
// word that tests/test_git_hook_environment.py, reading this file's child_process, takes
// for a script that starts Git.
const COMMITS_TALLY = ".nav-toolbar > .nav-metadata";
// An age, by the age primitive's tier classes (docs/design-system.md, "Age").
const AGE = ".age-live, .age-sec, .age-min, .age-hr, .age-day, .age-wk, .age-old";

// In the page: the diff's toolbar against the first file card, and each count summary's runs
// of text, each with its computed weight and whether it is a bold number (`.summary-number`),
// a change stat, or an age, which carry weights of their own.
const CHROME = `(() => {
  const round = (value) => Math.round(value * 100) / 100;
  const toolbar = document.querySelector(".metabrowser-diff-host .diff-toolbar");
  const card = document.querySelector(".metabrowser-diff-host .diff-file");
  const style = getComputedStyle(toolbar);
  const runs = (selector) => {
    const line = document.querySelector(selector);
    if (line === null) {
      return null;
    }
    const found = [];
    const walker = document.createTreeWalker(line, NodeFilter.SHOW_TEXT);
    for (let node = walker.nextNode(); node; node = walker.nextNode()) {
      if (node.textContent.trim() === "") {
        continue;
      }
      const parent = node.parentElement;
      const number = parent.classList.contains("summary-number");
      found.push({
        text: node.textContent,
        weight: getComputedStyle(parent).fontWeight,
        number,
        // What holds a bold number: inline with its words, never a flex or grid line, where
        // it would be an item of its own.
        within: number ? getComputedStyle(parent.parentElement).display : null,
        own: parent.closest(".change-line-stats, ${AGE}") !== null,
      });
    }
    return found;
  };
  return {
    toolbar: {
      holds: [...toolbar.children].map((child) => child.classList[0]),
      rule: [style.borderBottomStyle, style.borderBottomWidth].join(" "),
      position: style.position,
      paddingBottom: style.paddingBottom,
      gapToCard: round(card.getBoundingClientRect().top - toolbar.getBoundingClientRect().bottom),
      cardMarginTop: getComputedStyle(card).marginTop,
      cardRule: getComputedStyle(card).borderTopWidth,
    },
    counts: {
      summary: runs(".diff-summary"),
      files: runs(".tree-summary.nav-metadata"),
      commits: runs("${COMMITS_TALLY}"),
    },
  };
})()`;

// In the page, in *theme*: the ink of every part of the Diff summary's header, against the
// tokens it is drawn from, each read from a probe that takes the token (mb-vb51). Each
// status's letter takes its status's ink (`.file-change-status`, `--git-status-*`), each
// dot and comma the muted punctuation (`.summary-punctuation`, `--muted`), and the file
// count and its words the line's own ink (`--text`).
const PAINT = `async (theme) => {
  document.documentElement.dataset.theme = theme;
  await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
  const header = document.querySelector(".diff-summary");
  const ink = (node) => getComputedStyle(node).color;
  const token = (name) => {
    const probe = document.createElement("span");
    probe.style.color = "var(" + name + ")";
    header.parentElement.append(probe);
    const color = ink(probe);
    probe.remove();
    return color;
  };
  const tokens = {};
  for (const name of ["--text", "--muted", "--git-status-added", "--git-status-deleted", "--git-status-modified", "--git-status-renamed"]) {
    tokens[name] = token(name);
  }
  const files = header.querySelector(".diff-summary-files");
  const painted = {
    theme,
    tokens,
    words: files ? ink(files) : null,
    numbers: [...header.querySelectorAll(".summary-number")].map((node) => [node.textContent, ink(node)]),
    letters: [...header.querySelectorAll(".file-change-status")].map((node) => [node.textContent, node.dataset.fileStatus, ink(node)]),
    marks: [...header.querySelectorAll(".summary-punctuation")].map((node) => [node.textContent, node.getAttribute("aria-hidden"), ink(node)]),
    text: header.textContent,
    label: header.getAttribute("aria-label"),
  };
  delete document.documentElement.dataset.theme;
  return painted;
}`;

/** Open *patch*, then its Diff summary, and read it once its travel is over. */
async function openSummary(browser, patch) {
  await browser.send("Page.navigate", { url: `${base}/view/${patch}` });
  await browser.waitFor(
    `document.querySelector(".diff-summary-toggle") !== null && document.querySelector(".diff-file-bar") !== null`,
    30000,
  );
  // The Files totals, once counted.
  await browser.waitFor(
    `document.querySelector(".tree-summary.nav-metadata") !== null && document.querySelector(".tree-summary.nav-metadata .tally-pending") === null`,
    30000,
  );
  await browser.evaluate(frames);
  const collapsed = await browser.evaluate(LAYOUT);
  collapsed.chrome = await browser.evaluate(CHROME);
  await browser.evaluate(`document.querySelector(".diff-summary-toggle").click(), true`);
  await browser.waitFor(
    `document.querySelector('.diff-summary-body [role="treeitem"]') !== null`,
    30000,
  );
  // The box travels open in --transition-fast; read it once that travel, and any that
  // replaced it, is over.
  await browser.evaluate(`(async () => {
    const travels = () => document.querySelector(".diff-summary-body").getAnimations();
    const deadline = performance.now() + 10000;
    while (travels().length > 0 && performance.now() < deadline) {
      await Promise.allSettled(travels().map((travel) => travel.finished));
    }
    return true;
  })()`);
  await browser.evaluate(frames);
  return { collapsed, open: await browser.evaluate(LAYOUT) };
}

const profiles = process.env.CHROME_PROFILES;
if (!process.env.CHROME_BIN || !profiles) {
  throw new Error("CHROME_BIN and CHROME_PROFILES are required");
}
const server = await serve();
phase("served");
const result = {};
let chrome = null;
try {
  chrome = await launchChrome(process.env.CHROME_BIN, { profiles, width: 1280, height: 900 });
  const browser = chrome;
  const errors = [];
  browser.on("Runtime.exceptionThrown", ({ exceptionDetails }) =>
    errors.push(exceptionDetails.exception?.description ?? exceptionDetails.text),
  );
  await browser.send("Runtime.enable");
  await browser.send("Page.enable");
  await browser.send("Page.navigate", { url: `${base}/view/` });
  await browser.waitFor(`document.readyState === "complete"`, 30000);
  phase("chrome");

  // A tree five levels deep: where each level starts against the header.
  result.nested = await openSummary(browser, "nested.patch");
  phase("nested");

  // The keys are the tree's: the row that takes Tab, then Down three times, with the ring a
  // focused row takes. A key first, so Chrome draws focus as the keyboard's.
  await browser.send("Input.dispatchKeyEvent", {
    type: "keyDown",
    key: "Shift",
    code: "ShiftLeft",
  });
  await browser.send("Input.dispatchKeyEvent", { type: "keyUp", key: "Shift", code: "ShiftLeft" });
  await browser.evaluate(
    `document.querySelector('.diff-summary-body [role="treeitem"][tabindex="0"]').focus(), true`,
  );
  const FOCUS = `(() => {
    const row = document.activeElement;
    const s = getComputedStyle(row);
    return { id: row.dataset.id ?? null, ring: [s.outlineStyle, s.outlineWidth, s.outlineOffset].join(" "), focusVisible: row.matches(":focus-visible") };
  })()`;
  const keys = [await browser.evaluate(FOCUS)];
  for (let at = 0; at < 3; at += 1) {
    await browser.send("Input.dispatchKeyEvent", {
      type: "keyDown",
      key: "ArrowDown",
      code: "ArrowDown",
      windowsVirtualKeyCode: 40,
    });
    await browser.send("Input.dispatchKeyEvent", {
      type: "keyUp",
      key: "ArrowDown",
      code: "ArrowDown",
      windowsVirtualKeyCode: 40,
    });
    await browser.evaluate(frames);
    keys.push(await browser.evaluate(FOCUS));
  }
  result.keys = keys;
  phase("keys");

  // A long change set: the window's view of the tree and the overscan are in the document,
  // at the top and with the page scrolled to the tree's middle, where the rows in view are
  // drawn.
  result.long = await openSummary(browser, "long.patch");
  result.long.scrolled = await browser.evaluate(`(async () => {
    const body = document.querySelector(".diff-summary-body");
    let scroller = body.parentElement;
    while (scroller && !/^(auto|scroll)$/.test(getComputedStyle(scroller).overflowY)) {
      scroller = scroller.parentElement;
    }
    const middle = body.getBoundingClientRect().top + body.getBoundingClientRect().height / 2;
    scroller.scrollTop += middle - scroller.getBoundingClientRect().top;
    const frame = () => new Promise((resolve) => requestAnimationFrame(resolve));
    await frame();
    await frame();
    await frame();
    const view = scroller.getBoundingClientRect();
    const rows = [...body.querySelectorAll('[role="treeitem"]')];
    const inView = rows.filter((row) => {
      const box = row.getBoundingClientRect();
      return box.bottom > view.top && box.top < view.bottom;
    });
    const list = body.querySelector(".diff-summary-rows").getBoundingClientRect();
    const height = parseFloat(getComputedStyle(document.documentElement).getPropertyValue("--ui-row-height"));
    // Every row index the view covers has its row drawn.
    const first = Math.max(0, Math.floor((view.top - list.top) / height));
    const last = Math.floor((view.bottom - list.top) / height);
    const tops = new Set(rows.map((row) => Math.round((row.getBoundingClientRect().top - list.top) / height)));
    let missing = 0;
    for (let at = first; at <= last; at += 1) {
      if (!tops.has(at)) missing += 1;
    }
    return { drawn: rows.length, inView: inView.length, missing, viewRows: last - first + 1 };
  })()`);
  phase("long");

  // A commit's page: the Diff summary at its top, the toolbar holding the layout control
  // alone, and the Commits tally beside it, once counted.
  await browser.send("Page.navigate", { url: `${base}/commit/${commit}` });
  await browser.waitFor(
    `document.querySelector(".metabrowser-diff-host .diff-file") !== null && document.querySelector(".diff-summary-toggle") !== null && document.querySelector("${COMMITS_TALLY} .summary-number") !== null && document.querySelector("${COMMITS_TALLY} .tally-pending") === null`,
    30000,
  );
  await browser.evaluate(frames);
  result.commit = await browser.evaluate(CHROME);
  // The header's inks, in each theme: its letters, its marks, and its words.
  result.commit.paint = [];
  for (const theme of ["light", "dark"]) {
    result.commit.paint.push(await browser.evaluate(`(${PAINT})(${JSON.stringify(theme)})`));
  }
  phase("commit");
  result.errors = errors;
} finally {
  await chrome?.close();
  await server.stop();
  phase("closed");
}
process.stdout.write(`${JSON.stringify(result)}\n`);

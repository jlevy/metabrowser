// A pull request's description never shows as Markdown source, in headless Chrome against a
// live `metab` server whose cache holds the cores of pull requests 7 and 10 and no record.
//
//   CHROME_BIN=... CHROME_PROFILES=<dir> RECORD_RELEASE=<dir> \
//     node tests/dom/github-pull-core-markdown-chrome.mjs <base URL>
//
// tests/test_github_pull_core_markdown_chrome.py serves a checkout of the GitHub stand-in with a
// fake `gh`, prepares the two cores without starting the Markdown child, holds each pull request's
// record fetch until this script writes a file named for its number in the directory
// RECORD_RELEASE names, owns the profile directory, and stops this process's whole group, Chrome
// included, however the run ends (tests/process_group.py).
//
// A sampler reads every animation frame from navigation start: the description's state, which is
// `source` while its Markdown source is on screen, `quiet` while its source is out of sight for a
// render on its way (`.github-pull-plain-pending`) and the loading period's quiet start has not
// passed, `placeholder` once its gray rows show, `rendered` once its Markdown is in, and `hidden`
// while the page holds its first paint out of sight. Four steps, in one document:
//
// 1. Pull request 7 by its address, the core preview, with the Markdown child cold: the page's
//    own first read starts it.
// 2. Its record, released once its core has been judged, with the description unchanged.
// 3. Pull request 10 from its row in the Pulls tab, the core preview, with the child warm and the
//    description's render held past the page's first-paint hold (`LATE_RENDER_MS`), so the page
//    shows with the placeholder in its place.
// 4. 10's record, released once its core has been judged.
//
// On each, no frame shows the description's source, and it renders within the Markdown route's
// own bound. Each page's timeline goes to stderr.
import { writeFileSync } from "node:fs";
import { join } from "node:path";
import { launchChrome } from "./chrome-session.mjs";

const [base] = process.argv.slice(2);
const release = process.env.RECORD_RELEASE;
if (!base || !process.env.CHROME_BIN || !process.env.CHROME_PROFILES || !release) {
  throw new Error(
    "usage: CHROME_BIN CHROME_PROFILES RECORD_RELEASE github-pull-core-markdown-chrome.mjs <base>",
  );
}
// One page load or fake gh fetch; a loaded machine has needed several seconds for one.
const STEP_MS = 30000;
// The longest an honest render may take to answer: the Markdown child's start wait and its render
// deadline, each INERT_RENDER_DEADLINE_MS (diff/markdown_projection_worker.py), past which the
// route refuses the text and the page shows its source with the line that says why.
const ROUTE_BOUND_MS = 10000;
// How long step 3 holds its description's render: past the page's first-paint hold,
// DESCRIPTION_HOLD_MS (200 ms in pull-page.js), and the loading period's quiet start,
// --loading-state-delay (50 ms in static/styles.css), with room for frames on a loaded runner,
// so the placeholder's rows show for a while before the render replaces them.
const LATE_RENDER_MS = 1500;

const failures = [];
let checks = 0;
const check = (label, ok, detail = "") => {
  checks += 1;
  if (!ok) {
    failures.push(`${label}${detail ? `: ${detail}` : ""}`);
  }
};

// Every frame, the description's state when it changes, in ms from the document's time origin,
// with whether the page shows a core and which page it is: a page the shell swaps in is another
// element, numbered as the sampler first sees it.
const SAMPLER = `(() => {
  const S = { trail: [], pages: 0 };
  window.__description = S;
  const visible = (element) => {
    for (let node = element; node && node.nodeType === 1; node = node.parentElement) {
      const style = getComputedStyle(node);
      if (style.visibility !== "visible" || style.display === "none") return false;
    }
    const box = element.getBoundingClientRect();
    return box.width > 0 && box.height > 0 && box.bottom > 0 && box.top < innerHeight;
  };
  const state = (page) => {
    const text = page?.querySelector('.github-pull-text[data-part="body"]');
    if (!text) return "none";
    const plain = text.querySelector(":scope > .github-pull-plain");
    const rendered = text.querySelector(":scope > .metabrowser-kpress-host");
    if (plain && visible(plain)) return "source";
    if (rendered && visible(rendered)) return "rendered";
    if (plain && plain.classList.contains("github-pull-plain-pending") && visible(text)) {
      return getComputedStyle(plain, "::after").visibility === "visible" ? "placeholder" : "quiet";
    }
    return "hidden";
  };
  const frame = () => {
    const now = Math.round(performance.now());
    const page = document.querySelector(".github-pull");
    if (page && !page.__sampled) page.__sampled = ++S.pages;
    const shows = state(page);
    const core = page?.dataset.corePreview === "true";
    const id = page?.__sampled ?? 0;
    const last = S.trail[S.trail.length - 1];
    if (!last || last[1] !== shows || last[2] !== core || last[3] !== id) {
      S.trail.push([now, shows, core, id]);
    }
    requestAnimationFrame(frame);
  };
  requestAnimationFrame(frame);
})();`;

const chrome = await launchChrome(process.env.CHROME_BIN, {
  profiles: process.env.CHROME_PROFILES,
});
try {
  const { evaluate } = chrome;
  const rendered = `document.querySelector('.github-pull-text[data-part="body"] > .metabrowser-kpress-host') !== null`;
  const waitFor = (expression) => chrome.waitFor(expression, STEP_MS);
  /** Wait for the description's render, and judge the frames either way: a description that
   * never renders is a failed check with its timeline, not a script that stops. */
  const settle = async () => {
    try {
      await chrome.waitFor(rendered, STEP_MS);
    } catch (error) {
      if (!String(error?.message).startsWith("timed out")) {
        throw error;
      }
    }
  };
  await chrome.send("Page.enable");
  await chrome.send("Page.addScriptToEvaluateOnNewDocument", { source: SAMPLER });
  const now = async () => Math.floor(await evaluate("performance.now()"));
  const shownPage = () => evaluate(`document.querySelector(".github-pull")?.__sampled ?? 0`);

  /**
   * Hold one page's frames from *since* to the rule, and say them on stderr: the state in effect
   * at *since*, then each change, of the page numbered *page* alone. With *late*, the render was
   * held past the first-paint hold, so the placeholder's rows must show before it.
   */
  const judge = async (name, since, { core, page, late = false }) => {
    // A frame past the render, so the sampler has seen it.
    await evaluate("new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)))");
    const all = JSON.parse(await evaluate("JSON.stringify(window.__description.trail)")).filter(
      ([, , , id]) => id === page,
    );
    const before = all.filter(([at]) => at < since).at(-1);
    const seen = [
      ...(before === undefined ? [] : [[since, ...before.slice(1)]]),
      ...all.filter(([at]) => at >= since),
    ];
    process.stderr.write(
      `${name}: ${seen.map(([at, shows, isCore]) => `${at - since} ms ${shows}${isCore ? " (core)" : ""}`).join(", ")}\n`,
    );
    const shown = seen.filter(
      ([, shows]) => shows !== "none" && shows !== "hidden" && shows !== "quiet",
    );
    check(
      `${name}: the description never shows its Markdown source`,
      shown.every(([, shows]) => shows !== "source"),
      JSON.stringify(seen),
    );
    const first = shown[0];
    const done = shown.find(([, shows]) => shows === "rendered");
    check(`${name}: the description renders`, done !== undefined, JSON.stringify(seen));
    if (first !== undefined && done !== undefined) {
      check(
        `${name}: it renders within the route's bound of its first sight`,
        done[0] - first[0] <= ROUTE_BOUND_MS,
        `${done[0] - first[0]} ms`,
      );
    }
    if (late) {
      const placeholder = shown.findIndex(([, shows]) => shows === "placeholder");
      check(
        `${name}: the placeholder's rows show while its render is held`,
        placeholder >= 0 && shown.findIndex(([, shows]) => shows === "rendered") > placeholder,
        JSON.stringify(seen),
      );
    }
    if (core) {
      check(
        `${name}: it renders while the page shows the core`,
        seen.some(([, shows, isCore]) => shows === "rendered" && isCore),
        JSON.stringify(seen),
      );
    }
  };

  // 1. Pull request 7's core, by its address: the first page of the document.
  await chrome.send("Page.navigate", { url: `${base}/pull/7` });
  await waitFor(`document.querySelector(".github-pull") !== null`);
  await settle();
  const seven = await shownPage();
  await judge("7 by its address", 0, { core: true, page: seven });

  // 2. The record follows the core, fetched as the page opened and let through now, its
  // description the same text.
  const opened = await now();
  writeFileSync(join(release, "7"), "");
  await waitFor(`document.querySelector(".github-pull")?.dataset.corePreview === "false"`);
  await settle();
  check("7's record replaces its core in place", (await shownPage()) === seven);
  await judge("7's record", opened, { core: false, page: seven });

  // 3. Pull request 10's core, from its row in the Pulls tab, as the owner opens one, its
  // description's render held past the first-paint hold.
  await chrome.send("Fetch.enable", {
    patterns: [{ urlPattern: "*/pull-markdown*number=10*part=body*", requestStage: "Request" }],
  });
  chrome.on("Fetch.requestPaused", ({ requestId }) => {
    setTimeout(() => {
      chrome.send("Fetch.continueRequest", { requestId }).catch(() => {});
    }, LATE_RENDER_MS);
  });
  const row10 = `document.querySelector('#tab-pulls .github-pulls-row[data-number="10"]')`;
  await waitFor(`${row10} !== null`);
  const followed = await evaluate(`(() => {
    ${row10}.scrollIntoView({ block: "center" });
    ${row10}.click();
    return Math.floor(performance.now());
  })()`);
  // A page replacing another keeps that one on screen until it is ready.
  await waitFor(
    `location.pathname === "/pull/10" && (document.querySelector(".github-pull")?.__sampled ?? ${seven}) !== ${seven}`,
  );
  await settle();
  const ten = await shownPage();
  await judge("10 from its row", followed, { core: true, page: ten, late: true });
  await chrome.send("Fetch.disable");

  // 4. 10's record, let through now, follows its core.
  const released = await now();
  writeFileSync(join(release, "10"), "");
  await waitFor(`document.querySelector(".github-pull")?.dataset.corePreview === "false"`);
  await settle();
  check("10's record replaces its core in place", (await shownPage()) === ten);
  await judge("10's record", released, { core: false, page: ten });
} finally {
  await chrome.close();
}

if (failures.length > 0) {
  process.stderr.write(`${failures.join("\n")}\n`);
  process.exit(1);
}
process.stdout.write(`core description in Chrome: ${checks} checks passed\n`);

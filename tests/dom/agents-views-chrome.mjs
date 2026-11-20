// The agents views in headless Chrome, against a live `metab` serving synthetic homes.
//
//   CHROME_BIN=/path/to/chrome CHROME_PROFILES=/dir/the/caller/removes \
//     node tests/dom/agents-views-chrome.mjs <server base URL> <expectations JSON>
//
// tests/test_agents_views_chrome.py writes the homes, serves them, owns the profile
// directory, and stops this process's whole group, Chrome included, however the run ends.
// The expectations are what the homes hold: how many sessions the list shows, how many of
// them are Codex's, and the paths of the files the pages open.
//
// What no browserless session can say, because it is the browser's: that a folder holding
// a home opens on its home and a plain folder does not, that the views' stylesheet is not in a
// plain folder's load, that the list pages, sorts, and filters through real clicks, that a
// session page and a compressed rollout render with the kind colors in both themes, that
// leaving the home stops its poll, and what a plain folder pays for the plugin's assets.
// The state machines are pinned browserlessly in tests/dom/agents-views-session.js.
//
// Prints one line of checks, and `measure` lines on stderr for what the views cost.
import { launchChrome } from "./chrome-session.mjs";

const [base, expectationsJson] = process.argv.slice(2);
const profiles = process.env.CHROME_PROFILES;
if (!base || !expectationsJson || !process.env.CHROME_BIN || !profiles) {
  throw new Error("usage: CHROME_BIN CHROME_PROFILES agents-views-chrome.mjs <URL> <expectations>");
}
const expected = JSON.parse(expectationsJson);
const failures = [];
let checks = 0;
const check = (label, ok, detail = "") => {
  checks += 1;
  if (!ok) {
    failures.push(
      `${label}${detail ? `: ${typeof detail === "string" ? detail : JSON.stringify(detail)}` : ""}`,
    );
  }
};
const began = Date.now();
const step = (name) =>
  process.stderr.write(`${((Date.now() - began) / 1000).toFixed(1)} s ${name}\n`);
const measure = (name, value) => process.stderr.write(`measure ${name} ${JSON.stringify(value)}\n`);

// The view the reader sees: no stage pending, and the active tab naming the view in the pane.
const SHOWN = `(() => {
  const pane = document.querySelector(".preview-pane");
  if (!pane || pane.querySelector(":scope > .preview-file-stage")) {
    return null;
  }
  const tab = pane.querySelector(":scope > .tab-bar > .tab-btn.active");
  const view = pane.querySelector(':scope > [data-active-view="true"]');
  return tab && view && tab.dataset.tab === view.dataset.tabContent ? { pane, tab, view } : null;
})()`;
const TABS = `(() => {
  const shown = ${SHOWN};
  return shown
    ? {
        tabs: [...shown.pane.querySelectorAll(":scope > .tab-bar > .tab-btn")].map((b) => b.dataset.tab),
        active: shown.tab.dataset.tab,
      }
    : null;
})()`;
const RESOURCES = `performance.getEntriesByType("resource")`;
const COUNT_REQUESTS = (needle) =>
  `${RESOURCES}.filter((entry) => entry.name.includes(${JSON.stringify(needle)})).length`;

async function until(chrome, expression, ms = 20000) {
  try {
    await chrome.waitFor(expression, ms);
    return true;
  } catch {
    return false;
  }
}

async function open(chrome, url) {
  await chrome.send("Page.navigate", { url });
  await until(chrome, "Boolean(window.metabrowser?.registerView)");
  await until(chrome, `Boolean(${SHOWN})`);
}

// Every anchor the shown view renders, and a bare `<a href>` put in it, as a link reads in
// the theme the page is in: the design's `--link`, never the user agent's blue (`-webkit-link`)
// or its visited purple, and no underline at rest. The bare anchor is what a new view that
// styles nothing gets, which the shell's base rule (styles.css, `:where(a:any-link)`) colors.
const LINKS = `(() => {
  const probe = (token) => {
    const span = document.createElement("span");
    span.style.color = "var(" + token + ")";
    document.body.append(span);
    const color = getComputedStyle(span).color;
    span.remove();
    return color;
  };
  const view = ${SHOWN}.view;
  const link = probe("--link");
  const anchors = [...view.querySelectorAll("a[href]")];
  const bare = document.createElement("a");
  bare.href = "#bare";
  bare.textContent = "bare";
  view.append(bare);
  const bareColor = getComputedStyle(bare).color;
  bare.remove();
  return {
    link,
    count: anchors.length,
    wrong: anchors
      .filter((a) => getComputedStyle(a).color !== link)
      .map((a) => [a.className, getComputedStyle(a).color]),
    underlined: anchors
      .filter((a) => getComputedStyle(a).textDecorationLine !== "none")
      .map((a) => a.className),
    bare: bareColor,
  };
})()`;

/** Check `LINKS` in both themes; *label* names the view. */
async function checkLinks(chrome, label, minimum = 1) {
  for (const theme of ["light", "dark"]) {
    await chrome.evaluate(`document.documentElement.setAttribute("data-theme", "${theme}")`);
    const seen = await chrome.evaluate(LINKS);
    check(`${label} draws links to check in the ${theme} theme`, seen.count >= minimum, seen);
    check(`every ${label} anchor is --link in the ${theme} theme`, seen.wrong.length === 0, seen);
    check(
      `none underlined at rest in the ${theme} theme (${label})`,
      seen.underlined.length === 0,
      seen,
    );
    check(
      `a bare link in the ${label} is --link, not the user agent's, in the ${theme} theme`,
      seen.bare === seen.link && seen.bare !== "rgb(0, 0, 238)" && seen.bare !== "rgb(85, 26, 139)",
      seen,
    );
  }
}

const clickTab = (chrome, tab) =>
  chrome.evaluate(
    `document.querySelector('.preview-pane > .tab-bar > .tab-btn[data-tab="${tab}"]').click()`,
  );

const chrome = await launchChrome(process.env.CHROME_BIN, { profiles, width: 1280, height: 900 });
step("launched");
try {
  await chrome.send("Page.enable");

  // -- a plain folder offers nothing of the agents' ------------------------------------
  await open(chrome, `${base}/view/${expected.plain}/`);
  const plain = await chrome.evaluate(TABS);
  check("a plain folder has no agents views", plain?.tabs.join() === "overview,treemap", plain);
  check("and opens on its Overview", plain?.active === "overview", plain);
  const plainAssets = await chrome.evaluate(
    `${RESOURCES}.filter((e) => e.name.includes("/plugin-static/agents/")).map((e) => [e.name.split("/").pop(), e.encodedBodySize])`,
  );
  check(
    "the views' stylesheet is not in a plain folder's load",
    !plainAssets.some(([name]) => name.startsWith("agents-views")),
    plainAssets,
  );
  check(
    "nor are the home's, the list's, or the session page's modules",
    !plainAssets.some(([name]) => /^(home|session|session-list|session-rows)\.js/.test(name)),
    plainAssets,
  );
  check(
    "nor are the Log, Charts, and Raw renderers or the sheet they and the kind colors live in",
    !plainAssets.some(([name]) => /^agent-log\./.test(name)),
    plainAssets,
  );
  check(
    "the plugin's one eager asset is its registration stub",
    plainAssets.map(([name]) => name.replace(/\?.*$/, "")).join() === "index.js",
    plainAssets,
  );
  measure("a plain folder's agents plugin assets (name, encoded bytes)", plainAssets);
  step("plain folder");

  // -- the home -----------------------------------------------------------------------
  await open(chrome, `${base}/view/`);
  const home = await chrome.evaluate(TABS);
  check(
    "a folder holding homes offers the home and the list",
    home?.tabs.slice(0, 2).join() === "agents,agent-sessions",
    home,
  );
  check("and opens on the home", home?.active === "agents", home);
  check(
    "the home paints",
    await until(chrome, `Boolean(${SHOWN}?.view.querySelector(".agents-stat-value"))`),
  );
  check(
    "its summary pass completes and the page says so",
    await until(
      chrome,
      `${SHOWN}?.view.querySelector(".agents-progress")?.dataset.phase === "complete"`,
      30000,
    ),
  );
  const totals = await chrome.evaluate(`(() => {
    const view = ${SHOWN}.view;
    const stats = Object.fromEntries([...view.querySelectorAll(".agents-stat")].map((s) => [
      s.querySelector(".agents-stat-label").textContent,
      s.querySelector(".agents-stat-value").textContent,
    ]));
    return {
      stats,
      recent: view.querySelectorAll(".agents-recent .agents-session-row").length,
      homes: [...view.querySelectorAll(".agents-home-item")].map((li) => li.textContent.slice(0, 20)),
      live: view.querySelector(".agents-live")?.textContent ?? null,
      bars: view.querySelectorAll(".agents-histogram-row").length,
    };
  })()`);
  check(
    "the totals count every session",
    totals.stats.Sessions === String(expected.sessions),
    totals,
  );
  check("the recent table lists a page of sessions", totals.recent === 8, totals);
  check("both homes are listed", totals.homes.length === 2, totals);
  check("the size histogram has rows", totals.bars > 0, totals);
  check("the live strip answers", /Running now/.test(totals.live ?? ""), totals);
  check(
    "the stylesheet loaded once",
    (await chrome.evaluate(COUNT_REQUESTS("agents-views.css"))) === 1,
  );
  const homeAssets = await chrome.evaluate(
    `${RESOURCES}.filter((e) => e.name.includes("/plugin-static/agents/")).map((e) => [e.name.split("/").pop(), e.encodedBodySize])`,
  );
  measure("the home's agents assets (name, encoded bytes)", homeAssets);
  const liveFirst = await chrome.evaluate(COUNT_REQUESTS("/api/plugin/agents/live"));
  check("the live strip asked once", liveFirst === 1, liveFirst);
  await checkLinks(chrome, "home");
  // A row is two lines, and the age stays on the first however long the project path is:
  // that is the row's contract (docs/design-system.md, "Session Rows").
  const ROW_LAYOUT = `(() => {
    const view = ${SHOWN}.view;
    return [...view.querySelectorAll(".agents-session-row")].map((row) => {
      const line = row.querySelector(".agents-row-line").getBoundingClientRect();
      const meta = row.querySelector(".agents-row-meta").getBoundingClientRect();
      const age = row.querySelector(".agents-row-age").getBoundingClientRect();
      const title = row.querySelector(".agents-row-title").getBoundingClientRect();
      const box = row.getBoundingClientRect();
      return {
        height: Math.round(box.height),
        ageOnFirstLine: age.top >= line.top - 1 && age.bottom <= line.bottom + 1,
        ageAtEnd: Math.abs(age.right - line.right) < 1,
        metaBelow: meta.top >= line.bottom - 1,
        metaInside: meta.right <= box.right + 1,
        titleBeforeAge: title.right <= age.left + 1,
      };
    });
  })()`;
  const rowsBefore = await chrome.evaluate(ROW_LAYOUT);
  check("the home lists its recent sessions as rows", rowsBefore.length >= 8, rowsBefore.length);
  await chrome.evaluate(`(() => {
    const view = ${SHOWN}.view;
    for (const project of view.querySelectorAll(".agents-row-project")) {
      project.textContent = "/work/github/a-very-long-project-directory-name/nested/deeper/still-deeper/and-deeper-still";
    }
    for (const title of view.querySelectorAll(".agents-row-title")) {
      title.textContent = "A title long enough to run past the end of the line on a narrow page, ".repeat(3);
    }
  })()`);
  const rowsLong = await chrome.evaluate(ROW_LAYOUT);
  const keeps = (rows) =>
    rows.every(
      (r) => r.ageOnFirstLine && r.ageAtEnd && r.metaBelow && r.metaInside && r.titleBeforeAge,
    );
  check("a row's age is at the end of its first line", keeps(rowsBefore), rowsBefore[0]);
  check("and stays there under a long title and a long path", keeps(rowsLong), rowsLong[0]);
  check(
    "a long path and title do not make a row taller",
    rowsLong.every((r, i) => r.height === rowsBefore[i].height),
    { before: rowsBefore[0], after: rowsLong[0] },
  );
  step("home");

  // -- leaving the home stops its poll ------------------------------------------------
  await clickTab(chrome, "overview");
  await until(chrome, `${SHOWN}?.tab.dataset.tab === "overview"`);
  const leftAt = await chrome.evaluate(COUNT_REQUESTS("/api/plugin/agents/live"));
  await new Promise((resolve) => setTimeout(resolve, expected.livePollMs + 1500));
  const after = await chrome.evaluate(COUNT_REQUESTS("/api/plugin/agents/live"));
  check("a view that was left asks nothing more", after === leftAt, { leftAt, after });
  await clickTab(chrome, "agents");
  check(
    "coming back mounts a fresh home",
    await until(chrome, `Boolean(${SHOWN}?.view.querySelector(".agents-stat-value"))`),
  );
  step("left and returned");

  // -- the list pages, sorts, and filters ---------------------------------------------
  await clickTab(chrome, "agent-sessions");
  check(
    "the list paints a page",
    await until(
      chrome,
      `${SHOWN}?.view.querySelectorAll(".agents-table tbody tr").length === ${expected.pageSize}`,
    ),
    await chrome.evaluate(`${SHOWN}?.view.querySelector(".agents-list-summary")?.textContent`),
  );
  const SUMMARY = `${SHOWN}?.view.querySelector(".agents-list-summary")?.textContent ?? ""`;
  const ROWS = `${SHOWN}?.view.querySelectorAll(".agents-table tbody tr").length`;
  check(
    "the first page says its range",
    (await chrome.evaluate(SUMMARY)).startsWith(
      `1 to ${expected.pageSize} of ${expected.listed} sessions`,
    ),
    await chrome.evaluate(SUMMARY),
  );
  check(
    "Previous is off on the first page",
    await chrome.evaluate(`${SHOWN}.view.querySelector('[data-agents-page="previous"]').disabled`),
  );
  await chrome.evaluate(`${SHOWN}.view.querySelector('[data-agents-page="next"]').click()`);
  check(
    "Next shows the rest",
    await until(chrome, `${ROWS} === ${expected.listed - expected.pageSize}`),
    await chrome.evaluate(SUMMARY),
  );
  check(
    "and its range",
    (await chrome.evaluate(SUMMARY)).startsWith(
      `${expected.pageSize + 1} to ${expected.listed} of ${expected.listed} sessions`,
    ),
    await chrome.evaluate(SUMMARY),
  );
  check(
    "Next is off on the last",
    await chrome.evaluate(`${SHOWN}.view.querySelector('[data-agents-page="next"]').disabled`),
  );
  await chrome.evaluate(`${SHOWN}.view.querySelector('[data-agents-page="previous"]').click()`);
  check("Previous goes back", await until(chrome, `${ROWS} === ${expected.pageSize}`));

  await chrome.evaluate(`${SHOWN}.view.querySelector('[data-agents-sort="size"]').click()`);
  check(
    "a column sorts, and its header says so",
    await until(
      chrome,
      `${SHOWN}?.view.querySelector('th[aria-sort="descending"] [data-agents-sort="size"]') !== null`,
    ),
  );
  check(
    "the request named the sort",
    (await chrome.evaluate(COUNT_REQUESTS("sort=size&order=desc"))) >= 1,
  );

  await chrome.evaluate(
    `${SHOWN}.view.querySelector('[data-chip-key="agent"][data-chip-value="codex"]').click()`,
  );
  check(
    "an agent filter narrows the list",
    await until(chrome, `(${SUMMARY}).includes("of ${expected.codex} sessions")`),
    await chrome.evaluate(SUMMARY),
  );
  check(
    "and returns to the first page",
    (await chrome.evaluate(SUMMARY)).startsWith("1 to "),
    await chrome.evaluate(SUMMARY),
  );
  await chrome.evaluate(
    `${SHOWN}.view.querySelector('[data-chip-key="agent"][data-chip-value="all"]').click()`,
  );
  await until(chrome, `(${SUMMARY}).includes("of ${expected.listed} sessions")`);
  await chrome.evaluate(
    `${SHOWN}.view.querySelector('[data-chip-key="origin"][data-chip-value="review"]').click()`,
  );
  check(
    "showing automatic reviews adds them",
    await until(
      chrome,
      `(${SUMMARY}).includes("of ${expected.listed + expected.reviews} sessions")`,
    ),
    await chrome.evaluate(SUMMARY),
  );
  await checkLinks(chrome, "list");
  // The table is wider than the pane, so its wrap scrolls and takes the keyboard's focus;
  // scrolled to the end, its last column is whole inside it, so none is cut off for good.
  const reach = await chrome.evaluate(`(() => {
    const wrap = ${SHOWN}.view.querySelector(".agents-table-wrap");
    const heads = [...wrap.querySelectorAll("thead th")];
    const overflowing = wrap.scrollWidth > wrap.clientWidth;
    wrap.scrollLeft = 0;
    const first = heads[0].getBoundingClientRect();
    const edge = wrap.getBoundingClientRect();
    const startsInside = first.left >= edge.left - 1;
    wrap.scrollLeft = wrap.scrollWidth;
    const last = heads[heads.length - 1].getBoundingClientRect();
    return {
      overflowing,
      focusable: wrap.tabIndex === 0,
      scrolls: getComputedStyle(wrap).overflowX === "auto",
      startsInside,
      endsInside: last.right <= edge.right + 1 && last.left >= edge.left - 1,
      columns: heads.length,
      paneFits: edge.right <= document.documentElement.clientWidth + 1,
    };
  })()`);
  check(
    "every column of the list is reachable by scrolling its wrap",
    reach.endsInside && reach.startsInside,
    reach,
  );
  check(
    "the wrap is a keyboard stop, and the page itself does not overflow",
    reach.focusable && reach.paneFits,
    reach,
  );
  step("list");

  // -- a session page -----------------------------------------------------------------
  await open(chrome, `${base}/view/${expected.claude}`);
  const claudeTabs = await chrome.evaluate(TABS);
  check(
    "a transcript opens on its Session view",
    claudeTabs?.active === "session" && claudeTabs.tabs.includes("log"),
    claudeTabs,
  );
  check(
    "its events paint",
    await until(chrome, `${SHOWN}?.view.querySelectorAll(".agents-event").length >= 10`),
  );
  const page = await chrome.evaluate(`(() => {
    const view = ${SHOWN}.view;
    return {
      title: view.querySelector(".agents-title")?.textContent,
      replayed: view.querySelectorAll(".agents-event-replay").length,
      child: view.querySelector(".agents-children a")?.getAttribute("data-agents-open") ?? null,
      kinds: [...new Set([...view.querySelectorAll(".agents-event")].map((e) => e.dataset.kind))],
    };
  })()`);
  check("the header names the session", page.title === expected.claudeTitle, page);
  check("replayed events are shown apart", page.replayed === expected.claudeReplayed, page);
  check("a child is a link to its file", page.child === expected.claudeChild, page);
  check("events of several kinds", page.kinds.length >= 4, page);

  // The kind colors, in both themes: a badge is its kind's token, and the themes differ.
  const COLORS = `(() => {
    const probe = (token) => {
      const span = document.createElement("span");
      span.style.color = "var(" + token + ")";
      document.body.append(span);
      const color = getComputedStyle(span).color;
      span.remove();
      return color;
    };
    const view = ${SHOWN}.view;
    const result = {};
    for (const kind of ["prompt", "thinking", "tool-call"]) {
      const badge = view.querySelector(".kind-" + kind);
      if (badge) {
        const style = getComputedStyle(badge);
        result[kind] = {
          badge: style.color,
          ink: probe("--agent-kind-" + kind + "-text"),
          ground: style.backgroundColor,
          groundToken: probe("--agent-kind-" + kind + "-bg"),
        };
      }
    }
    return result;
  })()`;
  await chrome.evaluate(`document.documentElement.setAttribute("data-theme", "light")`);
  const light = await chrome.evaluate(COLORS);
  await chrome.evaluate(`document.documentElement.setAttribute("data-theme", "dark")`);
  const dark = await chrome.evaluate(COLORS);
  for (const kind of ["prompt", "thinking"]) {
    check(
      `the ${kind} badge is its token in the light theme`,
      light[kind]?.badge === light[kind]?.ink && light[kind]?.ground === light[kind]?.groundToken,
      light[kind],
    );
    check(
      `and in the dark theme`,
      dark[kind]?.badge === dark[kind]?.ink && dark[kind]?.ground === dark[kind]?.groundToken,
      dark[kind],
    );
    check(`the two themes color it differently`, light[kind]?.ground !== dark[kind]?.ground, {
      light: light[kind],
      dark: dark[kind],
    });
  }
  await checkLinks(chrome, "session page");
  step("session page");

  // -- a transcript outside a home falls back to its Log -------------------------------
  if (expected.loose) {
    await open(chrome, `${base}/view/${expected.loose}`);
    const looseTabs = await chrome.evaluate(TABS);
    check(
      "a transcript in no home still opens on Session",
      looseTabs?.active === "session",
      looseTabs,
    );
    check(
      "and shows the Log it always had",
      await until(chrome, `Boolean(${SHOWN}?.view.querySelector(".log-event"))`),
    );
    const logAssets = await chrome.evaluate(
      `${RESOURCES}.filter((e) => e.name.includes("/plugin-static/agents/") && /agent-log\\.(js|css)/.test(e.name)).map((e) => [e.name.split("/").pop().replace(/\\?.*$/, ""), e.encodedBodySize])`,
    );
    check(
      "the Log's renderers and sheet load when the Log is shown, once each",
      logAssets
        .map(([name]) => name)
        .sort()
        .join() === "agent-log.css,agent-log.js",
      logAssets,
    );
    measure("the Log's agents assets (name, encoded bytes)", logAssets);
    step("outside a home");
  }

  // -- a compressed rollout -----------------------------------------------------------
  await open(chrome, `${base}/view/${expected.rollout}`);
  const rolloutTabs = await chrome.evaluate(TABS);
  check(
    "a compressed rollout offers Session and Log",
    rolloutTabs?.tabs.join() === "session,log",
    rolloutTabs,
  );
  check("and opens on Session", rolloutTabs?.active === "session", rolloutTabs);
  check(
    "its events paint",
    await until(chrome, `${SHOWN}?.view.querySelectorAll(".agents-event").length >= 5`),
  );
  const rollout = await chrome.evaluate(`(() => {
    const view = ${SHOWN}.view;
    return {
      title: view.querySelector(".agents-title")?.textContent,
      tools: [...view.querySelectorAll(".agents-event .file-header-badge[class*='tool-']")].map((b) => b.className.match(/tool-(\\w+)/)[1]),
    };
  })()`);
  check("the header is the thread's", rollout.title === expected.rolloutTitle, rollout);
  check("its tool calls wear their family's color class", rollout.tools.includes("shell"), rollout);
  await clickTab(chrome, "log");
  check(
    "its Log view shows the events alone",
    await until(
      chrome,
      `Boolean(${SHOWN}?.view.querySelector(".agents-event")) && !${SHOWN}.view.querySelector(".agents-session-head h2")`,
    ),
  );
  step("rollout");
} finally {
  await chrome.close();
}
if (failures.length > 0) {
  process.stderr.write(`${failures.join("\n")}\n`);
  process.exitCode = 1;
} else {
  process.stdout.write(`agents views in Chrome: ${checks} checks passed\n`);
}

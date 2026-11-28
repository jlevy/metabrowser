// Text is sized by its role, and secondary metadata by the text it accompanies, laid out by
// headless Chrome against a live `metab` server.
//
//   CHROME_BIN=... CHROME_PROFILES=<dir> node tests/dom/type-scale-chrome.mjs <server base URL>
//
// tests/test_type_scale_chrome.py serves a checkout of the GitHub stand-in with a fake `gh`,
// owns the profile directory, and stops this process's whole group, Chrome included, however
// the run ends (tests/process_group.py).
//
// The owner found one kind of time at three sizes on one screen (mb-ctlu). The rule is in
// docs/design-system.md, "Type Scale": the main view's reading text is --body-font-size, the
// navigation column's list text --nav-font-size, the controls --ui-small-font-size, and
// metadata, an age, a size, a count, an update or fetch time, a row's second line, a note, has
// no size of its own but the text's it accompanies. This reads the computed size of one of
// each role on each surface, holds it to the table below, and holds each piece of metadata to
// its text: on the base, a Pulls row's author and age, a tree row's size, a commit row's author
// and age, the Commits tally's age, a file's and a folder's header metadata, a review
// comment's file, a pull request's Checks, a tooltip's detail, and Help's descriptions each
// read a step smaller than their text. A file's and a folder's header and a diff file bar are
// the main view's reading text, the navigation column's foot is its list text, and Quick
// Search's status reads at its results' size. A Pulls row's age column holds the longest
// compact age whole. In the narrowest pane, a commit row's author gives way and its age stays
// whole ("History Rows": never the age), where the column's clip cut it.
//
// Each step writes `phase <name> <ms since start>` to stderr, so a slow run says where.
import { launchChrome } from "./chrome-session.mjs";
import { NARROWEST } from "./nav-toolbar-wrap.mjs";

const [base] = process.argv.slice(2);
if (!base || !process.env.CHROME_BIN || !process.env.CHROME_PROFILES) {
  throw new Error("usage: CHROME_BIN CHROME_PROFILES type-scale-chrome.mjs <base URL>");
}
const started = Date.now();
const phase = (name) => process.stderr.write(`phase ${name} ${Date.now() - started}\n`);
// One page load or fake gh refresh; a loaded machine has needed several seconds for one.
const STEP_MS = 30000;

// The table in "Type Scale", in px at the default zoom.
const ROLE = {
  "page title": 24,
  "reading text": 14,
  tooltip: 14,
  "list text": 13,
  control: 12,
  label: 12,
  "hint strip": 12,
  mono: 12,
};

const failures = [];
let checks = 0;
const check = (label, ok, detail = "") => {
  checks += 1;
  if (!ok) {
    failures.push(`${label}${detail ? `: ${detail}` : ""}`);
  }
};

// The first visible element a selector matches: its computed size, and its text, so a
// failure says what it read.
const READ = `(selector) => {
  const element = [...document.querySelectorAll(selector)].find(
    (candidate) => candidate.getClientRects().length > 0,
  );
  if (!element) return null;
  return {
    size: Number.parseFloat(getComputedStyle(element).fontSize),
    text: element.textContent.replace(/\\s+/g, " ").trim().slice(0, 40),
  };
}`;

const chrome = await launchChrome(process.env.CHROME_BIN, {
  profiles: process.env.CHROME_PROFILES,
});
try {
  phase("chrome");
  const evaluate = chrome.evaluate;
  const waitFor = (expression) => chrome.waitFor(expression, STEP_MS);
  const frames = () =>
    evaluate("new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)))");
  const click = async (selector) => {
    await waitFor(`document.querySelector(${JSON.stringify(selector)}) !== null`);
    await evaluate(`document.querySelector(${JSON.stringify(selector)}).click()`);
    await frames();
  };
  const read = (selector) => evaluate(`(${READ})(${JSON.stringify(selector)})`);
  /** Hold one element of a role to the role's size. */
  const role = async (where, name, selector) => {
    const found = await read(selector);
    check(`${where}: ${selector} is drawn`, found !== null);
    if (found !== null) {
      check(
        `${where}: ${selector} is ${name}, ${ROLE[name]} px`,
        found.size === ROLE[name],
        `${found.size} px, "${found.text}"`,
      );
    }
  };
  /** Hold a piece of metadata to the size of the text it accompanies. */
  const accompanies = async (where, metadata, text) => {
    const [meta, beside] = [await read(metadata), await read(text)];
    check(`${where}: ${metadata} and ${text} are drawn`, meta !== null && beside !== null);
    if (meta !== null && beside !== null) {
      check(
        `${where}: ${metadata} reads at the size of ${text}`,
        meta.size === beside.size,
        `${meta.size} px "${meta.text}" against ${beside.size} px "${beside.text}"`,
      );
    }
  };
  const hover = async (selector) => {
    await chrome.send("Input.dispatchMouseEvent", { type: "mouseMoved", x: 1, y: 1 });
    const point = await evaluate(`(() => {
      const element = document.querySelector(${JSON.stringify(selector)});
      element.scrollIntoView({ block: "center" });
      const box = element.getBoundingClientRect();
      return { x: box.x + Math.min(box.width / 2, 8), y: box.y + box.height / 2 };
    })()`);
    await chrome.send("Input.dispatchMouseEvent", { type: "mouseMoved", ...point });
    await waitFor(
      "[...document.querySelectorAll('.custom-tooltip')].some((tip) => tip.classList.contains('visible') && tip.textContent.trim())",
    );
  };

  // A pull request's page, with the Pulls tab in front of the navigation column.
  await chrome.send("Page.navigate", { url: `${base}/pull/7` });
  await waitFor(
    "document.querySelector('.github-pull-header .page-header-line') !== null && document.querySelector('#tab-pulls .github-pulls-row') !== null",
  );
  // The list's count and the PR's settled author row have no routine freshness line.
  await waitFor(
    "document.querySelector('.github-pulls-status .github-pulls-total-line .summary-number') !== null && document.querySelector('.github-pull-header .github-pull-action')?.textContent && document.querySelector('.github-pull-note')?.hidden",
  );
  phase("pull request");
  const pulls = "the Pulls panel";
  await role(pulls, "list text", "#tab-pulls .github-pulls-title");
  await role(pulls, "list text", "#tab-pulls .github-pulls-number");
  await role(pulls, "list text", "#tab-pulls .github-pulls-age");
  await role(pulls, "list text", ".github-pulls-status");
  await role(pulls, "control", ".github-pulls-filters .chip");
  await role(pulls, "label", ".nav-tab-bar .tab-btn");
  await role(pulls, "hint strip", ".nav-shortcut-label");
  await accompanies(pulls, "#tab-pulls .github-pulls-age", "#tab-pulls .github-pulls-title");
  await accompanies(pulls, ".github-pulls-status", "#tab-pulls .github-pulls-title");
  // The longest compact age stays whole in the metadata line.
  const longestAge = await evaluate(`(async () => {
    const age = [...document.querySelectorAll("#tab-pulls .github-pulls-age")].find((e) => e.getClientRects().length);
    const saved = age.textContent;
    age.textContent = "12mo";
    await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));
    const row = age.closest(".github-pulls-tail").getBoundingClientRect();
    const box = age.getBoundingClientRect();
    const range = document.createRange();
    range.selectNodeContents(age);
    const text = range.getBoundingClientRect();
    const read = { text: Math.round(text.width * 100) / 100, box: Math.round(box.width * 100) / 100, cut: age.scrollWidth > age.clientWidth, inside: text.right <= row.right + 0.5 };
    age.textContent = saved;
    return read;
  })()`);
  check(
    `${pulls}: the longest age, "12mo", is whole beside the diff toggle`,
    !longestAge.cut && longestAge.inside && longestAge.text <= longestAge.box + 0.5,
    JSON.stringify(longestAge),
  );
  process.stderr.write(`measured 12mo ${JSON.stringify(longestAge)}\n`);
  // The navigation column's foot, in the markup the server and source-freshness.js write for
  // a served mirror, which a checkout has none of: its update time reads at the column's list
  // size.
  const foot = await evaluate(`(() => {
    const element = document.createElement("div");
    element.className = "source-freshness";
    document.getElementById("tree-pane").append(element);
    const label = document.createElement("span");
    label.className = "source-freshness-label";
    label.textContent = "Refreshing…";
    element.replaceChildren(label);
    const size = (node) => Number.parseFloat(getComputedStyle(node).fontSize);
    const row = [...document.querySelectorAll("#tab-pulls .github-pulls-title")].find((e) => e.getClientRects().length);
    const read = { foot: size(label), row: size(row) };
    element.remove();
    return read;
  })()`);
  check(
    "the navigation column's foot: its update time is list text, 13 px, the rows' size",
    foot.foot === ROLE["list text"] && foot.foot === foot.row,
    JSON.stringify(foot),
  );

  const header = "a pull request's header";
  await role(header, "page title", ".github-pull-header .github-pull-title-text");
  await role(header, "reading text", ".github-pull-header .github-pull-action");
  await role(header, "reading text", ".github-pull-opened .github-pull-age");
  await role(header, "control", ".github-pull-header .github-pull-state");
  await role(header, "control", ".github-pull-label");
  await role(header, "label", "#preview-pane .tab-bar .tab-btn");
  await accompanies(header, ".github-pull-opened .github-pull-quiet", ".github-pull-action");
  await waitFor(
    "/^(Refreshed|Last fetched) /.test(document.querySelector('#nav-refresh')?.getAttribute('aria-description') ?? '')",
  );
  await hover("#nav-refresh");
  await role("the Refresh receipt", "tooltip", ".custom-tooltip.visible");
  await chrome.send("Input.dispatchMouseEvent", { type: "mouseMoved", x: 1, y: 1 });
  await evaluate("window.MetabrowserTooltip.hide()");
  // The full record's conversation paints once its description's Markdown arrives, or its
  // hold's bound passes (DESCRIPTION_HOLD_MS in pull-page.js). Its review comment cards
  // are drawn then.
  await waitFor("document.querySelector('.github-pull-card-head .github-pull-file') !== null");
  const conversation = "a pull request's Conversation";
  await role(conversation, "reading text", ".github-pull-card-head");
  await role(conversation, "reading text", ".github-pull-card-head .github-pull-file");
  await role(conversation, "mono", ".github-pull-hunk");
  await accompanies(
    conversation,
    ".github-pull-card-head .github-pull-age",
    ".github-pull-card-head",
  );
  await accompanies(
    conversation,
    ".github-pull-card-head .github-pull-file",
    ".github-pull-card-head",
  );

  await hover(".github-pull-header .github-pull-age");
  await role("a tooltip", "tooltip", ".custom-tooltip.visible");
  await chrome.send("Input.dispatchMouseEvent", { type: "mouseMoved", x: 1, y: 1 });
  await evaluate("window.MetabrowserTooltip.hide()");
  phase("conversation");

  // Checks: its summary and each check are the main view's secondary text.
  await click("#preview-pane .tab-bar .tab-btn[href$='/checks']");
  await waitFor("document.querySelector('.github-pull-checks li') !== null");
  const checksTab = "a pull request's Checks";
  await role(checksTab, "reading text", ".github-pull-checks li");
  await role(checksTab, "reading text", ".github-pull-section > p.github-pull-quiet");
  await role(checksTab, "control", ".github-pull-checks .github-pull-badge");
  await accompanies(checksTab, ".github-pull-checks li", ".github-pull-merge, .section-heading");
  phase("checks");

  // Files: a tree row's size and age, the totals over it, and a tooltip's detail lines.
  await click(".nav-tab-bar .tab-btn:nth-child(1)");
  await waitFor("document.querySelector('#tab-files .tree-item-size') !== null");
  const files = "the Files panel";
  await role(files, "list text", "#tab-files .tree-item-name");
  await role(files, "list text", "#tab-files .tree-item-size");
  // The totals stand in the band over the panel (#nav-metadata-files), outside its scroller.
  await role(files, "list text", "#nav-metadata-files .tree-summary");
  await accompanies(files, "#tab-files .tree-item-size", "#tab-files .tree-item-name");
  if (await evaluate("document.querySelector('#tab-files .tree-item-age:not(:empty)') !== null")) {
    await accompanies(files, "#tab-files .tree-item-age:not(:empty)", "#tab-files .tree-item-name");
  }
  // A tree row's tooltip, in the markup the tree's tooltip writes (folderTooltipHtml in
  // app.js): its detail lines are the row's metadata, at the tooltip's size. Written into the
  // shell's one tooltip element rather than shown by hover: what is read is the cascade, and
  // a focus or a repaint under the pointer can take a hovered tooltip away mid-read.
  const tip = await evaluate(`(() => {
    const tooltip = document.querySelector(".custom-tooltip");
    const saved = [tooltip.innerHTML, tooltip.style.display];
    tooltip.innerHTML = '<div class="tip-detail"><span class="count">2 files</span></div>';
    tooltip.style.display = "block";
    const size = (element) => Number.parseFloat(getComputedStyle(element).fontSize);
    const sizes = { tooltip: size(tooltip), detail: size(tooltip.querySelector(".tip-detail")) };
    [tooltip.innerHTML, tooltip.style.display] = saved;
    return sizes;
  })()`);
  check(
    "a tooltip: it is the tooltip's size, 14 px",
    tip.tooltip === ROLE.tooltip,
    JSON.stringify(tip),
  );
  check(
    "a tooltip: its detail lines read at its size",
    tip.detail === tip.tooltip,
    JSON.stringify(tip),
  );
  phase("files");

  // A file's view header and a folder's: the title at the page title's size, the eyebrow's
  // address at the list size of the navigation's path row, its twin across the divider
  // (mb-ch82), and the metadata line at the main view's reading size, the line's values at
  // the size of the line they are on (docs/design-system.md, "View Headers").
  await evaluate(
    "[...document.querySelectorAll('#tab-files .tree-file')].find((row) => /README/.test(row.textContent)).click()",
  );
  await waitFor(
    "/README/.test(document.querySelector('.file-header .view-header-title')?.textContent ?? '')",
  );
  const fileHeader = "a file's header";
  await role(fileHeader, "page title", ".file-header .view-header-title");
  await role(fileHeader, "list text", ".file-header .folder-crumb-root");
  await role(fileHeader, "reading text", ".file-header .view-header-line");
  await role(fileHeader, "reading text", ".file-header .file-header-size");
  await accompanies(fileHeader, ".file-header .file-header-size", ".file-header .view-header-line");
  await click("#header-home");
  await waitFor("document.querySelector('.file-header .folder-header-count') !== null");
  const folderHeader = "a folder's header";
  await role(folderHeader, "page title", ".file-header .view-header-title");
  await role(folderHeader, "reading text", ".file-header .folder-header-count");
  await role(folderHeader, "reading text", ".file-header .file-header-size");
  await accompanies(
    folderHeader,
    ".file-header .folder-header-count",
    ".file-header .view-header-line",
  );
  if (await evaluate("document.querySelector('.view-header-age [class*=age-]') !== null")) {
    await accompanies(
      folderHeader,
      ".view-header-age [class*=age-]",
      ".file-header .view-header-line",
    );
  }
  phase("headers");

  // Commits: a row's author and age, the tally's age, and, in the narrowest pane, the age
  // whole while the author gives way.
  await click(".nav-tab-bar .tab-btn:nth-child(3)");
  await waitFor("document.querySelector('.git-graph-row .git-graph-age') !== null");
  const commits = "the Commits panel";
  await role(commits, "list text", ".git-graph-subject");
  await role(commits, "list text", ".git-graph-meta .actor-name");
  await role(commits, "list text", ".git-graph-age");
  await accompanies(commits, ".git-graph-age", ".git-graph-subject");
  await accompanies(commits, ".git-graph-meta .actor-name", ".git-graph-subject");
  await waitFor("document.querySelector('.git-history-summary-age') !== null");
  await accompanies(commits, ".git-history-summary-age", ".git-history-summary-count");
  const narrow = await evaluate(`(async () => {
    const pane = document.querySelector(".tree-pane");
    pane.style.width = "${NARROWEST + 1}px";
    await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));
    const rows = [...document.querySelectorAll(".git-graph-row")].filter((row) => row.getClientRects().length);
    const cut = rows.map((row) => {
      const age = row.querySelector(".git-graph-age").getBoundingClientRect();
      const meta = row.querySelector(".git-graph-meta").getBoundingClientRect();
      return Math.round((age.right - meta.right) * 100) / 100;
    });
    pane.style.width = "";
    await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));
    return { rows: rows.length, cut };
  })()`);
  check(
    `${commits}: at the narrowest pane, ${NARROWEST + 1} px, every row's age is whole`,
    narrow.rows > 0 && narrow.cut.every((px) => px <= 0.5),
    JSON.stringify(narrow),
  );
  phase("commits");

  // A commit's page: its header's lines at the body size, its revision among them.
  await click(".git-graph-row .git-graph-body");
  await waitFor("document.querySelector('#preview-pane .git-commit-ages') !== null");
  const commitPage = "a commit's page";
  await role(commitPage, "page title", "#preview-pane .git-commit-subject");
  await role(commitPage, "reading text", "#preview-pane .git-commit-ages");
  // A short commit ID is the size of its line, and its monospace face's x-height the sans's
  // (docs/design-system.md, "Short Commit IDs"): the width of 100ex in each, measured.
  await accompanies(
    commitPage,
    "#preview-pane .git-commit-sha",
    "#preview-pane .git-commit-revision-line",
  );
  const xHeights = await evaluate(`(() => {
    const ex = (host) => {
      const probe = document.createElement("span");
      probe.style.cssText = "display: inline-block; position: absolute; width: 100ex; height: 0";
      host.append(probe);
      const width = probe.getBoundingClientRect().width / 100;
      probe.remove();
      return width;
    };
    const id = document.querySelector("#preview-pane .git-commit-sha");
    return { id: ex(id), line: ex(id.closest(".git-commit-revision-line")) };
  })()`);
  check(
    `${commitPage}: its revision's x-height is its line's`,
    Math.abs(xHeights.id - xHeights.line) <= 0.01 * xHeights.line,
    JSON.stringify(xHeights),
  );
  await accompanies(commitPage, "#preview-pane .git-commit-age", "#preview-pane .git-commit-ages");
  // Its diff's file bars: a main-view path strip, at the body size, with its stats.
  await waitFor("document.querySelector('#preview-pane .diff-file-bar .diff-file-path') !== null");
  await role(commitPage, "reading text", "#preview-pane .diff-file-bar .diff-file-path");
  await accompanies(
    commitPage,
    "#preview-pane .diff-file-bar .diff-file-stats",
    "#preview-pane .diff-file-bar .diff-file-path",
  );
  // Its Diff summary's files, opened: a tree's rows, list text, with their line counts.
  await click("#preview-pane .git-commit-diff-summary .diff-summary-toggle");
  await waitFor("document.querySelector('#preview-pane .changed-file-stats') !== null");
  await role(commitPage, "list text", "#preview-pane .changed-file-name");
  await accompanies(
    commitPage,
    "#preview-pane .changed-file-stats",
    "#preview-pane .changed-file-name",
  );
  phase("commit");

  // The settings menu: a control. It hangs over the navigation column, so it comes after
  // every hover there, and Escape closes it.
  await click("#settings-btn");
  await role("the settings menu", "control", ".settings-menu .menu-row");
  const escapeKey = { key: "Escape", code: "Escape", windowsVirtualKeyCode: 27 };
  await chrome.send("Input.dispatchKeyEvent", { type: "keyDown", ...escapeKey });
  await chrome.send("Input.dispatchKeyEvent", { type: "keyUp", ...escapeKey });
  await frames();

  // Help: a list of commands, each described at its label's size.
  const question = { key: "?", text: "?", code: "Slash", windowsVirtualKeyCode: 191, modifiers: 8 };
  await chrome.send("Input.dispatchKeyEvent", { type: "keyDown", ...question });
  await chrome.send("Input.dispatchKeyEvent", { type: "keyUp", ...question });
  await waitFor("document.querySelector('.help-command-description') !== null");
  await role("Help", "list text", ".help-command-label");
  await role("Help", "list text", ".help-command-description");
  await role("Help", "label", ".modal-title");
  await accompanies("Help", ".help-command-description", ".help-command-label");
  await chrome.send("Input.dispatchKeyEvent", { type: "keyDown", ...escapeKey });
  await chrome.send("Input.dispatchKeyEvent", { type: "keyUp", ...escapeKey });
  await frames();
  phase("help");

  // Quick Search: its status counts the results above it, at their size.
  const search = { key: "t", text: "t", code: "KeyT", windowsVirtualKeyCode: 84 };
  await chrome.send("Input.dispatchKeyEvent", { type: "keyDown", ...search });
  await chrome.send("Input.dispatchKeyEvent", { type: "keyUp", ...search });
  await waitFor("document.querySelector('.search-palette-input') !== null");
  await chrome.send("Input.insertText", { text: "READ" });
  await waitFor(
    "document.querySelector('.search-palette-label') !== null && /match/i.test(document.querySelector('.search-palette-status')?.textContent ?? '')",
  );
  await role("Quick Search", "list text", ".search-palette-status");
  await role("Quick Search", "hint strip", ".search-palette-hint");
  await accompanies("Quick Search", ".search-palette-status", ".search-palette-label");
  phase("search");
} finally {
  await chrome.close();
}
if (failures.length > 0) {
  process.stderr.write(`${failures.join("\n")}\n`);
  process.exit(1);
}
process.stdout.write(`type scale in Chrome: ${checks} checks passed\n`);

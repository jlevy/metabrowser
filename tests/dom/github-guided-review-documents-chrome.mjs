// A guided-review step's rendered documents in headless Chrome, against a live `metab` server that
// serves the GitHub stand-in, whose pull request 7's guide ends on a step citing docs/new.md and
// config/settings.yaml whole.
//
//   CHROME_BIN=... CHROME_PROFILES=<dir> node tests/dom/github-guided-review-documents-chrome.mjs <base URL>
//
// tests/test_github_guided_review_chrome.py builds that server, owns the profile directory, and stops
// this process's whole group, Chrome included, however the run ends (tests/process_group.py).
//
// Browserless, github-guided-review-documents-behavior.js pins which references are documents,
// what a document's view is asked, and that a step change disposes it. What only a browser holds is
// the document itself: the real diff view and its rendered layer, over the server's projection.
//
// 1. A whole-file Markdown reference draws as the Docs tab draws that file: the diff view's file
//    bar with the file's path, its Rendered | Source chooser with Rendered chosen, Current, and the
//    same rendered Markdown, compared with the Docs tab's own drawing of the file.
// 2. A whole-file YAML reference draws as the Changes tab draws that file: its bar, its chooser,
//    Diff, and the same rendered tree, compared with Changes' own drawing of the file.
// 3. A ranged reference to the Markdown file draws its source rows, as before, and no document.
import { launchChrome } from "./chrome-session.mjs";

const [base] = process.argv.slice(2);
if (!base || !process.env.CHROME_BIN || !process.env.CHROME_PROFILES) {
  throw new Error(
    "usage: CHROME_BIN CHROME_PROFILES github-guided-review-documents-chrome.mjs <base>",
  );
}
// One page load or fake gh fetch; a loaded machine has needed several seconds for one.
const STEP_MS = 30000;

const failures = [];
let checks = 0;
const check = (label, ok, detail = "") => {
  checks += 1;
  if (!ok) {
    failures.push(`${label}${detail ? `: ${detail}` : ""}`);
  }
};
const same = (label, got, want) =>
  check(label, JSON.stringify(got) === JSON.stringify(want), `got ${JSON.stringify(got)}`);

/**
 * The file at *path* as the view *scope* finds draws it, once its rendered layer has drawn: a
 * Markdown file's rendered HTML, and a tree's text, whose element ids are the view's own.
 */
const DRAWN = (scope, path) => `(() => {
  const view = (${scope});
  const bar = [...(view?.querySelectorAll(".diff-file-bar") ?? [])].find(
    (node) => node.querySelector(".diff-file-path")?.textContent === ${JSON.stringify(path)},
  );
  const section = bar?.parentElement ?? null;
  const rendered = section?.querySelector(".diff-markdown, .diff-structured") ?? null;
  const shown = rendered !== null && rendered.getClientRects().length > 0;
  return {
    path: bar?.querySelector(".diff-file-path")?.textContent ?? null,
    chooser: [...(bar?.querySelectorAll(".diff-markdown-control [data-chip-value]") ?? [])].map(
      (chip) => chip.textContent + (chip.getAttribute("aria-checked") === "true" ? " (chosen)" : ""),
    ),
    shows: view?.querySelector(".diff-root")?.dataset.show ?? null,
    rendered: !shown
      ? null
      : rendered.classList.contains("diff-markdown")
        ? rendered.innerHTML
        : rendered.textContent,
  };
})()`;
const TAB = `document.querySelector(".github-pull")`;
/** The step's document whose bar names *path*. */
const DOCUMENT = (path) =>
  `[...document.querySelectorAll(".github-pull-guide-document")].find((section) => [...section.querySelectorAll(".diff-file-path")].some((name) => name.textContent === ${JSON.stringify(path)}))`;
const ROWS = `[...document.querySelectorAll(".github-pull-guide-excerpt .diff-line")].map((line) => {
  const op = ["add", "del", "context"].find((name) => line.classList.contains(\`diff-line-\${name}\`));
  return \`\${op} \${line.querySelector(".diff-line-text").textContent}\`;
})`;

const chrome = await launchChrome(process.env.CHROME_BIN, {
  profiles: process.env.CHROME_PROFILES,
});
try {
  const { evaluate } = chrome;
  const waitFor = (expression) => chrome.waitFor(expression, STEP_MS);
  const go = async (route) => {
    await chrome.send("Page.navigate", { url: `${base}${route}` });
    await waitFor(`location.pathname === ${JSON.stringify(route)}`);
  };
  // A step is composed out of sight (`.github-pull-guide-incoming`, guided-review.js) and
  // shows whole once what it draws is in, so a check reads only the step shown.
  const settled = (title) =>
    waitFor(
      `document.querySelector(".github-pull-guide-step:not(.github-pull-guide-incoming) .github-pull-guide-title")?.textContent === ${JSON.stringify(title)}`,
    );
  /** Open the step titled *title* from the guide's list of steps. */
  const open = async (title) => {
    const link = `[...document.querySelectorAll(".github-pull-guide-steps-link")].find((link) => link.querySelector(".github-pull-guide-steps-title")?.textContent === ${JSON.stringify(title)})`;
    await waitFor(`${link} !== undefined`);
    await evaluate(`${link}.click()`);
    await settled(title);
  };
  const drawn = async (scope, path) => {
    await waitFor(`${DRAWN(scope, path)}.rendered !== null`);
    return evaluate(DRAWN(scope, path));
  };
  await chrome.send("Page.enable");

  // The Docs tab's own drawing of the Markdown file, and Changes' of the YAML file, which the
  // step's documents must match.
  await go("/pull/7/docs");
  const docs = await drawn(TAB, "docs/new.md");
  same(
    "Docs draws the Markdown file in Full, under its chooser, on Current",
    [docs.path, docs.chooser, docs.shows],
    ["docs/new.md", ["Rendered (chosen)", "Source"], "full"],
  );
  check("and its rendered Markdown has the file's heading", /New/.test(docs.rendered ?? ""));
  await go("/pull/7/files");
  const changes = await drawn(TAB, "config/settings.yaml");
  same(
    "Changes draws the YAML file rendered, on Diff",
    [changes.path, changes.chooser[0], changes.shows],
    ["config/settings.yaml", "Rendered (chosen)", "diff"],
  );
  check("and its rendered tree has the file's keys", /count/.test(changes.rendered ?? ""));

  // 1 and 2. The whole-file references.
  await go("/pull/7");
  await open("Read the new guide whole");
  same(
    "the step draws two documents and no excerpt",
    await evaluate(`[
      document.querySelectorAll(".github-pull-guide-step:not(.github-pull-guide-incoming) .github-pull-guide-document").length,
      document.querySelectorAll(".github-pull-guide-step:not(.github-pull-guide-incoming) .github-pull-guide-excerpt").length,
    ]`),
    [2, 0],
  );
  same(
    "its Markdown document is Docs' drawing of the file",
    await drawn(DOCUMENT("docs/new.md"), "docs/new.md"),
    docs,
  );
  same(
    "its YAML document is Changes' drawing of the file",
    await drawn(DOCUMENT("config/settings.yaml"), "config/settings.yaml"),
    changes,
  );
  const block = ".github-pull-guide-references";
  const chooser = `${block} .diff-show-control`;
  same(
    "the block has one comparison chooser above both file cards",
    await evaluate(`document.querySelectorAll(${JSON.stringify(chooser)}).length`),
    1,
  );
  const choose = async (mode) =>
    evaluate(
      `document.querySelector(${JSON.stringify(`${chooser} [data-chip-value="${mode}"]`)}).click()`,
    );
  await choose("current");
  same(
    "Excerpt applies to both documents and is checked",
    await evaluate(`[
      ...[...document.querySelectorAll("${block} .diff-root")].map((root) => root.dataset.show),
      document.querySelector("${chooser} [aria-checked='true']")?.textContent,
    ]`),
    ["current", "current", "Excerpt"],
  );
  const markdownToggle = `${DOCUMENT("docs/new.md")}.querySelector(".diff-file-toggle")`;
  await evaluate(`${markdownToggle}.click()`);
  await choose("full");
  same(
    "Full preserves the collapsed file",
    await evaluate(`${markdownToggle}.getAttribute("aria-expanded")`),
    "false",
  );

  // 3. The ranged reference to the Markdown file, on the step before it.
  await open("Read the new guide");
  same(
    "a ranged reference to it draws no document",
    await evaluate(`document.querySelectorAll(".github-pull-guide-document").length`),
    0,
  );
  same(
    "and its source rows, then the whole diff of a file of no rendered format",
    await evaluate(ROWS),
    ["add # New", "context one", "add two"],
  );
  const excerptToggle = `document.querySelector("${block} .github-pull-guide-excerpt").closest("section").querySelector(".diff-file-toggle")`;
  await evaluate(`${excerptToggle}.click()`);
  same(
    "the cited source range has an accessible disclosure",
    await evaluate(`${excerptToggle}.getAttribute("aria-expanded")`),
    "false",
  );
} finally {
  await chrome.close();
}
if (failures.length > 0) {
  process.stderr.write(`${failures.join("\n")}\n`);
  process.exitCode = 1;
} else {
  process.stdout.write(`guided review documents in Chrome: ${checks} checks passed\n`);
}

// A guided-review step's rendered document in headless Chrome, against a live `metab` server that
// serves the GitHub stand-in, whose pull request 7's guide ends on a step citing docs/new.md whole.
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
//    bar with the file's path, its Rendered | Source chooser with Rendered chosen, and the same
//    rendered Markdown, compared with the Docs tab's own drawing of the file on the same page.
// 2. A ranged reference to the same file draws its source rows, as before, and no document.
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

/** docs/new.md as the view under *scope* draws it, once its rendered layer has drawn. */
const DRAWN = (scope) => `(() => {
  const view = document.querySelector(${JSON.stringify(scope)});
  const bar = [...(view?.querySelectorAll(".diff-file-bar") ?? [])].find(
    (node) => node.querySelector(".diff-file-path")?.textContent === "docs/new.md",
  );
  const section = bar?.parentElement ?? null;
  const rendered = section?.querySelector(".diff-markdown") ?? null;
  return {
    path: bar?.querySelector(".diff-file-path")?.textContent ?? null,
    chooser: [...(bar?.querySelectorAll(".diff-markdown-control [data-chip-value]") ?? [])].map(
      (chip) => chip.textContent + (chip.getAttribute("aria-checked") === "true" ? " (chosen)" : ""),
    ),
    shows: view?.querySelector(".diff-root")?.dataset.show ?? null,
    rendered: rendered !== null && rendered.getClientRects().length > 0 ? rendered.innerHTML : null,
  };
})()`;
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
  const settled = (title) =>
    waitFor(
      `document.querySelector(".github-pull-guide-step .github-pull-guide-title")?.textContent === ${JSON.stringify(title)}`,
    );
  /** Open the step titled *title* from the guide's list of steps. */
  const open = async (title) => {
    const link = `[...document.querySelectorAll(".github-pull-guide-steps-link")].find((link) => link.querySelector(".github-pull-guide-steps-title")?.textContent === ${JSON.stringify(title)})`;
    await waitFor(`${link} !== undefined`);
    await evaluate(`${link}.click()`);
    await settled(title);
  };
  const drawn = async (scope) => {
    await waitFor(`${DRAWN(scope)}.rendered !== null`);
    return evaluate(DRAWN(scope));
  };
  await chrome.send("Page.enable");

  // The Docs tab's own drawing of the file, which the step's document must match.
  await go("/pull/7/docs");
  const docs = await drawn(".github-pull");
  same(
    "Docs draws the file rendered, under its chooser",
    [docs.path, docs.chooser, docs.shows],
    ["docs/new.md", ["Rendered (chosen)", "Source"], "current"],
  );
  check("and its rendered Markdown has the file's heading", /New/.test(docs.rendered ?? ""));

  // 1. The whole-file reference.
  await go("/pull/7");
  await open("Read the new guide whole");
  same(
    "the step draws one document and no excerpt",
    await evaluate(`[
      document.querySelectorAll(".github-pull-guide-step .github-pull-guide-document").length,
      document.querySelectorAll(".github-pull-guide-step .github-pull-guide-excerpt").length,
    ]`),
    [1, 0],
  );
  const step = await drawn(".github-pull-guide-document");
  same("its document is Docs' drawing of the file", step, docs);

  // 2. The ranged reference to the same file, on the step before it.
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
} finally {
  await chrome.close();
}
if (failures.length > 0) {
  process.stderr.write(`${failures.join("\n")}\n`);
  process.exitCode = 1;
} else {
  process.stdout.write(`guided review documents in Chrome: ${checks} checks passed\n`);
}

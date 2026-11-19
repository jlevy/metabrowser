// Mermaid diagrams drawn in headless Chrome against a live `metab` (the Mermaid plan,
// docs/project/specs/active/plan-2026-08-21-mermaid-diagram-rendering.md).
//
// Usage: node markdown-diagrams-chrome.mjs METAB ROOT PORT STATE_DIR, with CHROME_BIN set,
// and CHROME_PROFILES naming where Chrome's profile goes (tests/dom/chrome-session.mjs).
// tests/test_markdown_diagrams_chrome.py writes ROOT: `diagrams.md` with a flowchart, a
// sequence diagram, and a broken diagram; `plain.md` with none; and `flow.mmd`. It owns the
// profile directory and runs this in a process group of its own, which Chrome and the
// servers join, stopped however the session ends.
//
// The folder is served trusted and `--untrusted`. Under each it checks:
//
// - a document with no diagram fetches no file of the vendored Mermaid;
// - the document's two good diagrams are drawn with a size, as SVG in the page when
//   trusted and as images that loaded when untrusted, and the broken one shows an error
//   with its source;
// - the expand button opens the dialog with the diagram drawn in it, and Escape closes it;
// - the `.mmd` file's Diagram view draws its diagram as an image that loaded;
// - no page throws.
//
// Each step writes `phase <name> <ms since start>` to stderr. It prints
// `markdown diagrams in Chrome: <n> checks passed`, or the failures and exits 1.
import { spawn } from "node:child_process";
import path from "node:path";
import { launchChrome } from "./chrome-session.mjs";

const [metab, root, port, state] = process.argv.slice(2);
if (!metab || !root || !port || !state || !process.env.CHROME_BIN) {
  throw new Error(
    "usage: CHROME_BIN CHROME_PROFILES markdown-diagrams-chrome.mjs METAB ROOT PORT STATE",
  );
}
const base = `http://127.0.0.1:${port}`;
const started = Date.now();
const phase = (name) => process.stderr.write(`phase ${name} ${Date.now() - started}\n`);
// The vendored library's files, which a page fetches only when it draws a diagram.
const MERMAID_FILES = "/static/vendor/mermaid/";

const failures = [];
let checks = 0;
const check = (label, ok, detail = "") => {
  checks += 1;
  if (!ok) {
    const failure = `${label}${detail ? `: ${JSON.stringify(detail)}` : ""}`;
    failures.push(failure);
    process.stderr.write(`failed ${failure}\n`);
  }
};

/** Start a server with *flags*, and resolve to its stop once it says where it serves. */
async function serve(flags) {
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
      ...flags,
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
  return async () => {
    server.kill();
    await exited;
  };
}

// The view the reader sees, once the shell has moved it from its hidden stage into the
// pane (as tests/dom/document-print-chrome.mjs reads it).
const VIEW = `(() => {
  const pane = document.querySelector(".preview-pane");
  if (!pane || pane.querySelector(":scope > .preview-file-stage")) {
    return null;
  }
  return pane.querySelector(':scope > [data-active-view="true"]');
})()`;
const FIGURES = `[...(${VIEW}?.querySelectorAll('[data-kpress-diagram="mermaid"]') ?? [])]`;
// Every figure settled: drawn, or showing its error.
const SETTLED = (count) =>
  `(() => {
    const figures = ${FIGURES};
    return figures.length === ${count} && figures.every((figure) =>
      ["rendered", "error"].includes(figure.dataset.kpressDiagramStatus));
  })()`;

// Each figure as the reader sees it: its state, the drawing's kind and box, whether an
// image loaded, and the error shown.
const DESCRIBE = `${FIGURES}.map((figure) => {
  const drawn = figure.querySelector(":scope > .kpress-diagram-rendered > svg, :scope > .kpress-diagram-rendered > img");
  const box = drawn?.getBoundingClientRect();
  const error = figure.querySelector(":scope > .metabrowser-diagram-error");
  const source = figure.querySelector(":scope > .kpress-diagram-source, :scope > pre");
  return {
    status: figure.dataset.kpressDiagramStatus,
    drawing: drawn ? drawn.tagName.toLowerCase() : null,
    width: box ? Math.round(box.width) : 0,
    height: box ? Math.round(box.height) : 0,
    loaded: drawn?.tagName === "IMG" ? drawn.complete && drawn.naturalWidth > 0 : null,
    error: error ? error.textContent.trim().slice(0, 80) : null,
    errorShown: error ? error.getBoundingClientRect().height > 0 : false,
    sourceShown: source ? source.getBoundingClientRect().height > 0 : false,
  };
})`;

const frames = () =>
  "new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(() => resolve(true))))";

async function checkProfile(profile) {
  const trusted = profile === "trusted";
  const page = await launchChrome(process.env.CHROME_BIN, {
    profiles: process.env.CHROME_PROFILES,
  });
  /** @type {string[]} */
  const requested = [];
  /** @type {string[]} */
  const thrown = [];
  page.on("Network.requestWillBeSent", ({ request }) => requested.push(request.url));
  page.on("Runtime.exceptionThrown", ({ exceptionDetails }) =>
    thrown.push(JSON.stringify(exceptionDetails).slice(0, 400)),
  );
  try {
    await page.send("Page.enable");
    await page.send("Runtime.enable");
    await page.send("Network.enable");
    // The browser's cache would hide a second page's requests from the count.
    await page.send("Network.setCacheDisabled", { cacheDisabled: true });

    // A document with no diagram asks for nothing of Mermaid's.
    requested.length = 0;
    await page.send("Page.navigate", { url: `${base}/view/plain.md` });
    await page.waitFor(`!!${VIEW}?.querySelector("article.kpress p")`);
    await page.evaluate(frames());
    check(
      `${profile} plain: no Mermaid file fetched`,
      !requested.some((url) => url.includes(MERMAID_FILES)),
      requested.filter((url) => url.includes(MERMAID_FILES)),
    );
    phase(`${profile} plain`);

    // The document: two diagrams and a broken one.
    requested.length = 0;
    await page.send("Page.navigate", { url: `${base}/view/diagrams.md` });
    await page.waitFor(SETTLED(3), 30000);
    await page.evaluate("document.fonts.ready.then(() => true)");
    await page.evaluate(frames());
    const figures = await page.evaluate(DESCRIBE);
    const drawing = trusted ? "svg" : "img";
    for (const [index, figure] of figures.slice(0, 2).entries()) {
      check(
        `${profile} diagram ${index + 1} drawn as ${drawing} with a size`,
        figure.status === "rendered" &&
          figure.drawing === drawing &&
          figure.width > 40 &&
          figure.height > 20 &&
          figure.loaded !== false &&
          !figure.sourceShown,
        figure,
      );
    }
    check(
      `${profile} the broken diagram shows its error and source`,
      figures[2]?.status === "error" &&
        figures[2].errorShown &&
        figures[2].sourceShown &&
        figures[2].drawing === null,
      figures[2],
    );
    check(
      `${profile} the document fetched Mermaid`,
      requested.some((url) => url.includes(MERMAID_FILES)),
    );
    phase(`${profile} document`);

    // The dialog: the expand button opens it with the diagram drawn in it.
    await page.evaluate(`${FIGURES}[0].querySelector(".metabrowser-diagram-expand").click(), true`);
    await page.waitFor(`!!document.querySelector("dialog.metabrowser-diagram-dialog[open]")`);
    await page.evaluate(frames());
    const dialog = await page.evaluate(`(() => {
      const dialog = document.querySelector("dialog.metabrowser-diagram-dialog[open]");
      const drawn = dialog.querySelector(".metabrowser-diagram-stage > svg, .metabrowser-diagram-stage > img");
      const box = drawn?.getBoundingClientRect();
      const viewport = dialog.querySelector(".metabrowser-diagram-viewport").getBoundingClientRect();
      return {
        modal: dialog.matches(":modal"),
        drawing: drawn ? drawn.tagName.toLowerCase() : null,
        width: box ? Math.round(box.width) : 0,
        height: box ? Math.round(box.height) : 0,
        viewport: { width: Math.round(viewport.width), height: Math.round(viewport.height) },
        transform: dialog.querySelector(".metabrowser-diagram-stage").style.transform,
      };
    })()`);
    check(
      `${profile} the dialog draws the diagram, fitted`,
      dialog.modal &&
        dialog.drawing === drawing &&
        dialog.width > 40 &&
        dialog.width <= dialog.viewport.width + 1 &&
        dialog.height <= dialog.viewport.height + 1 &&
        dialog.transform.includes("scale("),
      dialog,
    );
    await page.send("Input.dispatchKeyEvent", {
      type: "keyDown",
      key: "Escape",
      code: "Escape",
      windowsVirtualKeyCode: 27,
    });
    await page.send("Input.dispatchKeyEvent", {
      type: "keyUp",
      key: "Escape",
      code: "Escape",
      windowsVirtualKeyCode: 27,
    });
    await page.waitFor(`!document.querySelector("dialog.metabrowser-diagram-dialog")`);
    check(`${profile} Escape closes the dialog`, true);
    phase(`${profile} dialog`);

    // A `.mmd` file's Diagram view.
    await page.send("Page.navigate", { url: `${base}/view/flow.mmd` });
    await page.waitFor(SETTLED(1), 30000);
    await page.evaluate(frames());
    const [file] = await page.evaluate(DESCRIBE);
    check(
      `${profile} the .mmd file is drawn as an image that loaded`,
      file?.status === "rendered" && file.drawing === "img" && file.loaded && file.width > 40,
      file,
    );
    phase(`${profile} file`);
    check(`${profile} no page threw`, thrown.length === 0, thrown);
  } finally {
    await page.close();
  }
}

let stop = await serve([]);
phase("trusted server");
try {
  await checkProfile("trusted");
} finally {
  await stop();
}
stop = await serve(["--untrusted"]);
phase("untrusted server");
try {
  await checkProfile("untrusted");
} finally {
  await stop();
}
phase("closed");

if (failures.length) {
  process.stdout.write(`${failures.length} of ${checks} checks failed:\n${failures.join("\n")}\n`);
  process.exit(1);
}
process.stdout.write(`markdown diagrams in Chrome: ${checks} checks passed\n`);

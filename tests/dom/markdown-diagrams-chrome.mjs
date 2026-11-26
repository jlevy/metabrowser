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
// - a document with no diagram fetches no file of the vendored Mermaid, of KPress's
//   diagram modules, or of the Markdown plugin's diagram adapter;
// - the document's two good diagrams are drawn with a size, as SVG in the page when
//   trusted and as images that loaded when untrusted, and the broken one shows an error
//   with its source;
// - every toolbar and dialog button's glyph resolves to a KPress sprite symbol in the page,
//   which an untrusted render's allowlist drops and KPress's controls fetch again;
// - the expand button opens the dialog with the diagram drawn in it, fitted and centered,
//   and Escape closes it;
// - each copy button carries the app's tooltip and copies its own diagram's source;
// - the `.mmd` file's Diagram view draws its diagram as the document does;
// - untrusted text's diagrams drawn isolated (`drawDiagrams(root, {isolated: true})`, as a
//   pull request's page draws them) load nothing that their image shape, a `themeCSS`
//   directive or front matter, a `fontFamily` directive, a state diagram's `classDef`, or
//   a `block-beta` `style`, a `themeCSS` `cursor` or `@font-face`, or a class diagram's
//   `style` names, from a server that counts every request; the trusted page's control,
//   the same sources drawn as plain images in the page, does load them (the untrusted
//   page's `img-src` already refuses that server, so there the check is vacuous); the rest
//   are drawn as images at the size the page lays them out at, the image shape shows its
//   error and source, and disposing removes the frame;
// - a frame taken out of the page while it draws ends that draw with an error, and holds
//   up neither a document's diagrams drawn after it nor the next isolated draw;
// - no page throws, and the only content security policy violations are the expected
//   `style-src-elem` ones under `--untrusted`, from the `<style>` Mermaid measures with
//   (`untrusted_shell_csp` in capabilities.py says why they are harmless).
//
// Each step writes `phase <name> <ms since start>` to stderr. It prints
// `markdown diagrams in Chrome: <n> checks passed`, or the failures and exits 1.
import { spawn } from "node:child_process";
import http from "node:http";
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
// What a page fetches only when it draws a diagram: the vendored library, KPress's
// diagram modules, and the Markdown plugin's adapter.
const DIAGRAM_FILES = [
  "/static/vendor/mermaid/",
  "/js/diagrams.js",
  "/js/diagram-controls.js",
  "/markdown/diagrams.js",
];
const isDiagramFile = (url) => DIAGRAM_FILES.some((part) => new URL(url).pathname.includes(part));
const MERMAID_FILES = DIAGRAM_FILES[0];
// Every policy violation the page reports, from its first script on.
const RECORD_VIOLATIONS = `globalThis.__violations = [];
document.addEventListener("securitypolicyviolation", (event) => {
  globalThis.__violations.push(event.effectiveDirective + " " + (event.blockedURI || "inline"));
});`;

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
  const error = figure.querySelector(":scope > .kpress-diagram-error");
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

// Every button's glyph under *scope*: the sprite symbol its `<use>` names, and whether the
// page holds that symbol.
const GLYPHS = (
  scope,
) => `[...(${scope}).querySelectorAll(".kpress-diagram-button")].map((button) => {
  const href = button.querySelector("use")?.getAttribute("href") ?? "";
  return { label: button.getAttribute("aria-label"), href, found: !!href && !!document.querySelector(href) };
})`;

// A server on another port that counts every request a diagram makes, by the `from` its
// URL names; it answers each with a one-pixel image.
const pixelHits = [];
const pixels = http.createServer((request, response) => {
  pixelHits.push(new URL(request.url ?? "/", "http://pixel").searchParams.get("from"));
  response.writeHead(200, { "content-type": "image/svg+xml", "cache-control": "no-store" });
  response.end('<svg xmlns="http://www.w3.org/2000/svg" width="1" height="1"/>');
});
await new Promise((resolve) => pixels.listen(0, "127.0.0.1", resolve));
const PIXEL = `http://127.0.0.1:${/** @type {import("node:net").AddressInfo} */ (pixels.address()).port}/pixel.svg`;
// Untrusted text: each source but the last names the counting server's image in a way
// Mermaid loads while it lays the diagram out on a page with no policy (measured in
// builtin_plugins/markdown/diagram-frame.js), or a reviewer saw load (`fontFace`). Only
// the image shape cannot be drawn without its image.
const HOSTILE = {
  shape: `flowchart LR\n  A@{ img: "${PIXEL}?from=shape", label: "x", w: 60, h: 60 }\n  A --> B`,
  themeCSS: `%%{init: {"themeCSS": ".node rect { mask-image: url(${PIXEL}?from=themeCSS) }"}}%%\nflowchart LR\n  A --> B`,
  frontMatter: `---\nconfig:\n  themeCSS: ".node rect { mask-image: url(${PIXEL}?from=frontMatter) }"\n---\nflowchart LR\n  A --> B`,
  fontFamily: `%%{init: {"fontFamily": "zz; mask-image: url(${PIXEL}?from=fontFamily)"}}%%\nflowchart LR\n  A --> B`,
  classDef: `stateDiagram-v2\n  s1 --> s2\n  classDef x mask-image:url(${PIXEL}?from=classDef)\n  class s1 x`,
  blockStyle: `block-beta\n  a b\n  style a mask-image:url(${PIXEL}?from=blockStyle)`,
  cursor: `%%{init: {"themeCSS": ".node rect { cursor: url(${PIXEL}?from=cursor), auto }"}}%%\nflowchart LR\n  A --> B`,
  classStyle: `classDiagram\n  class A\n  A <|-- B\n  style A fill:url(${PIXEL}?from=classStyle)`,
  fontFace: `%%{init: {"themeCSS": "@font-face { font-family: zz; src: url(${PIXEL}?from=fontFace) } .label { font-family: zz }"}}%%\nflowchart LR\n  A --> B`,
  plain: "sequenceDiagram\n  Alice->>Bob: Hello, Bob",
};
// In the page: set the sources as an inert text's blocks, draw them through the Markdown
// plugin's exported host, and describe each figure, the frames, and disposal.
const DRAW_TEXT = (options) => `(async () => {
  const mb = window.metabrowser;
  const markdown = await mb.plugins.load("markdown");
  const root = document.createElement("article");
  root.className = "kpress kpress-inert";
  for (const source of ${JSON.stringify(Object.values(HOSTILE))}) {
    const pre = document.createElement("pre");
    pre.setAttribute("lang", "mermaid");
    const code = document.createElement("code");
    code.textContent = source;
    pre.append(code);
    root.append(pre);
  }
  document.body.append(root);
  const drawn = markdown.drawDiagrams(root, ${JSON.stringify(options)});
  await drawn.ready;
  await new Promise((resolve) => setTimeout(resolve, 500));
  const frames = () => document.querySelectorAll("iframe.metabrowser-diagram-frame").length;
  const framesWhileDrawn = frames();
  const figures = [...root.querySelectorAll('[data-kpress-diagram="mermaid"]')].map((figure) => {
    const image = figure.querySelector(":scope > .kpress-diagram-rendered > img");
    const source = figure.querySelector(":scope > .kpress-diagram-source, :scope > pre");
    return {
      status: figure.dataset.kpressDiagramStatus,
      loaded: image ? image.complete && image.naturalWidth > 0 : null,
      width: image ? Math.round(image.getBoundingClientRect().width) : 0,
      natural: image ? [image.naturalWidth, image.naturalHeight] : null,
      inPage: !!figure.querySelector(":scope > .kpress-diagram-rendered > svg"),
      sourceShown: source ? source.getBoundingClientRect().height > 0 : false,
    };
  });
  drawn.dispose();
  root.remove();
  return { framesWhileDrawn, framesAfter: frames(), figures };
})()`;

// A frame taken out of the page while Mermaid loads in it: the isolated draw settles with
// an error rather than holding KPress's page-wide queue of Mermaid calls, a document's draw
// after it is drawn, and the next isolated draw opens a new frame.
const REMOVE_MID_DRAW = `(async () => {
  const mb = window.metabrowser;
  const markdown = await mb.plugins.load("markdown");
  const text = (source) => {
    const root = document.createElement("article");
    root.className = "kpress kpress-inert";
    const pre = document.createElement("pre");
    pre.setAttribute("lang", "mermaid");
    const code = document.createElement("code");
    code.textContent = source;
    pre.append(code);
    root.append(pre);
    document.body.append(root);
    return root;
  };
  const within = (promise) =>
    Promise.race([promise.then(() => true), new Promise((resolve) => setTimeout(() => resolve(false), 10000))]);
  const status = (root) =>
    root.querySelector('[data-kpress-diagram="mermaid"]')?.dataset.kpressDiagramStatus ?? null;
  const frame = () => document.querySelector("iframe.metabrowser-diagram-frame");
  const lost = text("flowchart LR\\n  A --> B");
  const lostDraw = markdown.drawDiagrams(lost, { isolated: true });
  const started = Date.now();
  while (!frame()?.contentWindow?.metabrowserDiagramFrame && Date.now() - started < 10000) {
    await new Promise((resolve) => setTimeout(resolve, 2));
  }
  const removed = !!frame();
  frame()?.remove();
  const lostSettled = await within(lostDraw.ready);
  const later = text("flowchart LR\\n  C --> D");
  const laterDraw = markdown.drawDiagrams(later, { inert: true });
  const laterSettled = await within(laterDraw.ready);
  const again = text("flowchart LR\\n  E --> F");
  const againDraw = markdown.drawDiagrams(again, { isolated: true });
  const againSettled = await within(againDraw.ready);
  const result = {
    removed,
    lost: { settled: lostSettled, status: status(lost) },
    later: { settled: laterSettled, status: status(later) },
    again: { settled: againSettled, status: status(again) },
  };
  for (const [draw, root] of [[lostDraw, lost], [laterDraw, later], [againDraw, again]]) {
    draw.dispose();
    root.remove();
  }
  return { ...result, framesAfter: document.querySelectorAll("iframe.metabrowser-diagram-frame").length };
})()`;

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
  /** @type {string[]} */
  const violations = [];
  const collectViolations = async () => {
    violations.push(...((await page.evaluate("globalThis.__violations ?? []")) ?? []));
  };
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
    await page.send("Page.addScriptToEvaluateOnNewDocument", { source: RECORD_VIOLATIONS });

    // A document with no diagram asks for nothing of Mermaid's.
    requested.length = 0;
    await page.send("Page.navigate", { url: `${base}/view/plain.md` });
    await page.waitFor(`!!${VIEW}?.querySelector("article.kpress p")`);
    await page.evaluate(frames());
    check(
      `${profile} plain: no diagram file fetched`,
      !requested.some(isDiagramFile),
      requested.filter(isDiagramFile),
    );
    await collectViolations();
    phase(`${profile} plain`);

    // Untrusted text's diagrams, drawn isolated, load nothing they name.
    pixelHits.length = 0;
    const isolated = await page.evaluate(DRAW_TEXT({ isolated: true }));
    const isolatedHits = pixelHits.splice(0);
    const names = Object.keys(HOSTILE);
    const drawnFigures = isolated.figures.filter((_, index) => names[index] !== "shape");
    check(
      `${profile} isolated text diagrams load nothing they name`,
      isolatedHits.length === 0,
      isolatedHits,
    );
    check(
      `${profile} isolated text diagrams are drawn as images, in a frame disposal removes`,
      isolated.figures.length === names.length &&
        drawnFigures.every(
          (figure) =>
            figure.status === "rendered" && figure.loaded && figure.width > 20 && !figure.inPage,
        ) &&
        isolated.framesWhileDrawn === 1 &&
        isolated.framesAfter === 0,
      isolated,
    );
    check(
      `${profile} an image shape shows its error and source`,
      isolated.figures[names.indexOf("shape")]?.status === "error" &&
        isolated.figures[names.indexOf("shape")]?.sourceShown,
      isolated.figures[names.indexOf("shape")],
    );
    // The control: the same sources drawn as plain images, laid out in the page.
    const control = await page.evaluate(DRAW_TEXT({ inert: true }));
    const controlHits = new Set(pixelHits.splice(0));
    if (trusted) {
      // In a page with no policy they load what they name, so the counting server sees a
      // load when one is made. Under `--untrusted` the page's `img-src` already refuses the
      // counting server's origin, so there the isolation check above is vacuous and this
      // one is the meaningful run. A `block-beta` style loaded from this origin in the
      // measurement and not from the counting server's here, so the control names the
      // others.
      // An `@font-face` in a `themeCSS` was seen to load in the page by a reviewer, and
      // not here, so the control does not name it; the isolation check does.
      const loading = [
        "shape",
        "themeCSS",
        "frontMatter",
        "fontFamily",
        "classDef",
        "cursor",
        "classStyle",
      ];
      check(
        `${profile} the same sources laid out in the page load what they name`,
        loading.every((name) => controlHits.has(name)) && control.framesWhileDrawn === 0,
        { hits: [...controlHits], control },
      );
    }
    // The frame lays each diagram out at the size the page does: its labels' box model
    // is the page's, under either policy. Not the sequence diagram's (`plain`): Mermaid
    // measures its actor names in the document's body, which in the page has the app's
    // face and in the frame Mermaid's, the one the image draws them in (diagram-frame.js),
    // so there the frame's boxes are the closer fit.
    const sizes = names
      .map((name, index) => ({
        name,
        isolated: isolated.figures[index]?.natural,
        inPage: control.figures[index]?.natural,
      }))
      .filter((size) => size.name !== "shape" && size.name !== "plain");
    check(
      `${profile} isolated diagrams are laid out at the page's size`,
      sizes.every(
        (size) =>
          size.isolated &&
          size.inPage &&
          Math.abs(size.isolated[0] - size.inPage[0]) <= 1 &&
          Math.abs(size.isolated[1] - size.inPage[1]) <= 1,
      ),
      sizes,
    );
    const lost = await page.evaluate(REMOVE_MID_DRAW);
    check(
      `${profile} a frame taken out mid-draw holds up no later diagram`,
      lost.removed &&
        lost.lost.settled &&
        lost.lost.status === "error" &&
        lost.later.settled &&
        lost.later.status === "rendered" &&
        lost.again.settled &&
        lost.again.status === "rendered" &&
        lost.framesAfter === 0,
      lost,
    );
    pixelHits.length = 0;
    await collectViolations();
    phase(`${profile} isolated`);

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
    await page
      .waitFor(`${GLYPHS(`${FIGURES}[0]`)}.every((glyph) => glyph.found)`, 10000)
      .catch(() => {});
    const toolbar = await page.evaluate(GLYPHS(`${FIGURES}[0]`));
    check(
      `${profile} the toolbar's three glyphs are in the page`,
      toolbar.length === 3 && toolbar.every((glyph) => glyph.found),
      toolbar,
    );
    // Each copy button is the page's: its tooltip is the app's, and it copies its own
    // diagram's source.
    const copies = await page.evaluate(`${FIGURES}.map((figure) => {
      const button = figure.querySelector(".kpress-diagram-copy");
      return {
        tip: button?.getAttribute("data-tip-text") ?? null,
        copy: button?.getAttribute("data-mb-copy-text") ?? null,
      };
    })`);
    check(
      `${profile} each copy button carries the app's tooltip and its diagram's source`,
      copies.length === 3 &&
        copies.every((copy) => copy.tip === "Copy diagram source") &&
        copies[0].copy?.startsWith("flowchart LR\n  A[Start here]") &&
        copies[1].copy?.startsWith("sequenceDiagram\n  Alice->>Bob") &&
        copies[2].copy === "flowchart LR\n  A -->",
      copies,
    );
    phase(`${profile} document`);

    // The dialog: the expand button opens it with the diagram drawn in it.
    await page.evaluate(`${FIGURES}[0].querySelector(".kpress-diagram-expand").click(), true`);
    await page.waitFor(`!!document.querySelector("dialog.kpress-diagram-dialog[open]")`);
    await page.evaluate(frames());
    const dialog = await page.evaluate(`(() => {
      const dialog = document.querySelector("dialog.kpress-diagram-dialog[open]");
      const drawn = dialog.querySelector(".kpress-diagram-stage > svg, .kpress-diagram-stage > img");
      const box = drawn?.getBoundingClientRect();
      const viewport = dialog.querySelector(".kpress-diagram-viewport").getBoundingClientRect();
      return {
        glyphs: ${GLYPHS("dialog")},
        centered: !!box && Math.abs(box.left + box.width / 2 - (viewport.left + viewport.width / 2)) < 2 &&
          Math.abs(box.top + box.height / 2 - (viewport.top + viewport.height / 2)) < 2,
        modal: dialog.matches(":modal"),
        drawing: drawn ? drawn.tagName.toLowerCase() : null,
        width: box ? Math.round(box.width) : 0,
        height: box ? Math.round(box.height) : 0,
        viewport: { width: Math.round(viewport.width), height: Math.round(viewport.height) },
        transform: dialog.querySelector(".kpress-diagram-stage").style.transform,
      };
    })()`);
    check(
      `${profile} the dialog draws the diagram, fitted and centered`,
      dialog.modal &&
        dialog.centered &&
        dialog.drawing === drawing &&
        dialog.width > 40 &&
        dialog.width <= dialog.viewport.width + 1 &&
        dialog.height <= dialog.viewport.height + 1 &&
        dialog.transform.includes("scale("),
      dialog,
    );
    check(
      `${profile} the dialog's eight glyphs are in the page`,
      dialog.glyphs.length === 8 && dialog.glyphs.every((glyph) => glyph.found),
      dialog.glyphs,
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
    await page.waitFor(`!document.querySelector("dialog.kpress-diagram-dialog")`);
    check(`${profile} Escape closes the dialog`, true);
    await collectViolations();
    phase(`${profile} dialog`);

    // A `.mmd` file's Diagram view.
    await page.send("Page.navigate", { url: `${base}/view/flow.mmd` });
    await page.waitFor(SETTLED(1), 30000);
    await page.evaluate(frames());
    const [file] = await page.evaluate(DESCRIBE);
    check(
      `${profile} the .mmd file is drawn as ${drawing}`,
      file?.status === "rendered" &&
        file.drawing === drawing &&
        file.loaded !== false &&
        file.width > 40,
      file,
    );
    await collectViolations();
    phase(`${profile} file`);
    check(`${profile} no page threw`, thrown.length === 0, thrown);
    // Only Mermaid's measuring <style>, and the control's loads from the counting server,
    // and only where the untrusted policy blocks them.
    const unexpected = violations.filter(
      (violation) =>
        trusted ||
        !(
          violation.startsWith("style-src-elem inline") ||
          violation.startsWith(`img-src ${PIXEL}?from=`)
        ),
    );
    check(`${profile} no unexpected policy violation`, unexpected.length === 0, unexpected);
    if (!trusted) {
      check(
        `${profile} Mermaid's measuring style is the policy's one refusal`,
        violations.length > 0,
      );
    }
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
pixels.close();
phase("closed");

if (failures.length) {
  process.stdout.write(`${failures.length} of ${checks} checks failed:\n${failures.join("\n")}\n`);
  process.exit(1);
}
process.stdout.write(`markdown diagrams in Chrome: ${checks} checks passed\n`);

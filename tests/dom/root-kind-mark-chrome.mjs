// The mark before the root's name at the top of the navigation, drawn by headless Chrome
// against live `metab` servers: a plain folder, a Git checkout, and a mirror.
//
//   CHROME_BIN=/path/to/chrome CHROME_PROFILES=/dir/the/caller/removes \
//     node tests/dom/root-kind-mark-chrome.mjs '<{"folder": url, "git": url, "mirror": url}>' \
//       '<{"folder": elements, "git": elements, "mirror": elements}>' <screenshot dir>
//
// tests/test_root_kind_mark_chrome.py serves the three roots, owns the profile directory, and
// runs this in a process group of its own, which Chrome joins.
//
// Which kind a root is, the words for it, and the sentence its mark carries are `/api/identity`'s
// (`cli-api-shell.tryscript.md`), and the shell writing the same into its first paint is
// `tests/test_root_identity.py`'s. What only a browser can tell is held here
// (docs/design-system.md, "Source Kind Marks"):
//
// - the box is in the page from its markup, `--icon-glyph` square, before the name and
//   outside its link, centered on the name's line, and its glyph arrives in that box
//   without moving the name;
// - the glyph is the one the server wrote for the kind (static/source-kind-glyphs.json), drawn
//   in `--muted`, and the three kinds draw three shapes, none of them the ordinary folder's;
// - the main pane's header for the root leads with that same glyph, and the header of a folder
//   inside the root with the ordinary folder's, so a root is never drawn as an ordinary folder;
// - its tooltip shows over it, and is its accessible name; and
// - the adjacent disclosure opens details for the source and dismisses with Escape.
//
// It saves one screenshot of the navigation's top for each kind in each theme. Each step
// writes `phase <name> <ms since start>` to stderr, so a slow run says where.
import fs from "node:fs";
import path from "node:path";

import { launchChrome } from "./chrome-session.mjs";

const [pagesJson, glyphsJson, shots] = process.argv.slice(2);
if (
  !pagesJson ||
  !glyphsJson ||
  !shots ||
  !process.env.CHROME_BIN ||
  !process.env.CHROME_PROFILES
) {
  throw new Error(
    "usage: CHROME_BIN CHROME_PROFILES root-kind-mark-chrome.mjs <pages JSON> <glyphs JSON> <dir>",
  );
}
const pages = JSON.parse(pagesJson);
// Each kind's glyph elements, as the glyph file has them.
const glyphElements = JSON.parse(glyphsJson);
const started = Date.now();
const phase = (name) => process.stderr.write(`phase ${name} ${Date.now() - started}\n`);
// Layout places boxes in a 64th of a pixel; under half a pixel is not a different place.
const TOLERANCE_PX = 0.5;
const STEP_MS = 30000;
// The navigation heading, as the screenshots clip it: the header row and the room under it
// for a tooltip.
const CLIP = { x: 0, y: 0, width: 360, height: 110, scale: 2 };

let checks = 0;
const failures = [];
const check = (label, ok, detail = "") => {
  checks += 1;
  if (!ok) {
    failures.push(`${label}${detail ? `: ${detail}` : ""}`);
    process.stderr.write(`failed ${label}\n`);
  }
};

// In the page: the mark, as it stands, the name beside it, and the glyph file's glyph for each
// kind. A glyph is compared as the browser serializes it, not as the file spells it.
const READ = `(() => {
  const mark = document.getElementById("header-root-kind");
  const name = document.querySelector(".header-path");
  const rect = (element) => {
    const box = element.getBoundingClientRect();
    return { left: box.left, right: box.right, top: box.top, bottom: box.bottom, width: box.width, height: box.height };
  };
  const shape = (markup) => {
    const holder = document.createElement("template");
    // Elements alone are parsed inside an svg, as a self-closing circle only is in one.
    holder.innerHTML = markup.startsWith("<svg") ? markup : "<svg>" + markup + "</svg>";
    return [...holder.content.querySelectorAll("path, circle, rect")].map((each) => each.outerHTML).join("");
  };
  const svg = mark.querySelector("svg");
  const registry = window.MetabrowserIcons;
  const given = ${JSON.stringify(glyphElements)};
  const glyphs = Object.fromEntries(Object.entries(given).map(([kind, elements]) => [kind, shape(elements)]));
  const styles = getComputedStyle(mark);
  const root = getComputedStyle(document.documentElement);
  // The token's color as the engine computes it, by painting it on a probe.
  const probe = document.createElement("span");
  probe.style.color = "var(--muted)";
  document.body.append(probe);
  const muted = getComputedStyle(probe).color;
  probe.remove();
  return {
    kind: mark.dataset.rootKind,
    role: mark.getAttribute("role"),
    label: mark.getAttribute("aria-label"),
    tip: mark.dataset.tipText,
    focusable: mark.tabIndex >= 0,
    inLink: name.contains(mark),
    box: rect(mark),
    name: rect(name),
    glyphPx: parseFloat(root.getPropertyValue("--icon-glyph")),
    color: styles.color,
    muted,
    drawn: svg ? shape(svg.outerHTML) : "",
    glyphs,
    folderGlyph: shape(registry.folder),
    strokeColor: svg ? getComputedStyle(svg).stroke : "",
    svgBox: svg ? rect(svg) : null,
    nameText: name.textContent.trim(),
    // The glyph the main pane's header leads with, for the root or the folder it shows.
    headerGlyph: (() => {
      const icon = document.querySelector("#preview-pane .view-header-icon svg");
      return icon ? shape(icon.outerHTML) : "";
    })(),
  };
})()`;

const browser = await launchChrome(process.env.CHROME_BIN, {
  profiles: process.env.CHROME_PROFILES,
  width: 1280,
  height: 800,
});

async function open(url) {
  // Marked so a stale document's mark is never read for the new one.
  await browser.evaluate("window.__root_kind_page = 'old'");
  await browser.send("Page.navigate", { url });
  await browser.waitFor(
    "window.__root_kind_page !== 'old' && document.readyState === 'complete' && " +
      "document.querySelector('#header-root-kind svg') !== null && " +
      "document.querySelector('#preview-pane .view-header-icon svg') !== null && " +
      "document.querySelector('.header-path') !== null",
    STEP_MS,
  );
}

async function hover(selector) {
  const point = await browser.evaluate(`(() => {
    const box = document.querySelector(${JSON.stringify(selector)}).getBoundingClientRect();
    return { x: box.left + box.width / 2, y: box.top + box.height / 2 };
  })()`);
  await browser.send("Input.dispatchMouseEvent", { type: "mouseMoved", ...point });
}

const TOOLTIP = `(() => {
  const tip = document.querySelector(".custom-tooltip");
  return tip && tip.classList.contains("visible") ? tip.innerText.trim() : null;
})()`;

async function screenshot(file) {
  const { data } = await browser.send("Page.captureScreenshot", { format: "png", clip: CLIP });
  fs.writeFileSync(path.join(shots, file), Buffer.from(data, "base64"));
}

/** @type {Record<string, any>} */
const seen = {};
for (const theme of ["light", "dark"]) {
  await browser.send("Emulation.setEmulatedMedia", {
    features: [{ name: "prefers-color-scheme", value: theme }],
  });
  for (const [kind, url] of Object.entries(pages)) {
    const where = `${kind} in ${theme}`;
    await open(url);
    // A pointer left on the last page's mark would show its tooltip on this one.
    await browser.send("Input.dispatchMouseEvent", { type: "mouseMoved", x: 900, y: 400 });
    const at = await browser.evaluate(READ);
    phase(where);

    check(
      `${where}: the page is the ${kind} kind, and its mark says so`,
      at.kind === kind,
      at.kind,
    );
    check(
      `${where}: the mark is an image named by its sentence, no control`,
      at.role === "img" && at.label === at.tip && at.label.length > 0 && !at.focusable,
      JSON.stringify({ role: at.role, label: at.label, tip: at.tip, focusable: at.focusable }),
    );
    check(
      `${where}: the mark is a box of its own, not inside the name's link`,
      !at.inLink && at.box.right <= at.name.left + TOLERANCE_PX,
      JSON.stringify({ box: at.box, name: at.name }),
    );
    check(
      `${where}: the box and its glyph are --icon-glyph square`,
      Math.abs(at.box.width - at.glyphPx) <= TOLERANCE_PX &&
        Math.abs(at.box.height - at.glyphPx) <= TOLERANCE_PX &&
        at.svgBox !== null &&
        Math.abs(at.svgBox.width - at.glyphPx) <= TOLERANCE_PX &&
        Math.abs(at.svgBox.height - at.glyphPx) <= TOLERANCE_PX,
      JSON.stringify({ glyphPx: at.glyphPx, box: at.box, svg: at.svgBox }),
    );
    const markMiddle = (at.box.top + at.box.bottom) / 2;
    const nameMiddle = (at.name.top + at.name.bottom) / 2;
    check(
      `${where}: the mark is centered on the name's line`,
      Math.abs(markMiddle - nameMiddle) <= 1,
      JSON.stringify({ markMiddle, nameMiddle }),
    );
    check(
      `${where}: the glyph is the one the server wrote for the kind, in the muted ink`,
      at.drawn === at.glyphs[kind] &&
        at.drawn !== "" &&
        at.color === at.muted &&
        at.strokeColor === at.muted,
      JSON.stringify({
        drawn: at.drawn,
        expected: at.glyphs[kind],
        color: at.color,
        muted: at.muted,
      }),
    );
    check(
      `${where}: the glyph is not the ordinary folder's`,
      at.drawn !== at.folderGlyph,
      at.drawn,
    );
    check(
      `${where}: the root's header in the main pane leads with the same glyph`,
      at.headerGlyph === at.drawn,
      JSON.stringify({ header: at.headerGlyph, mark: at.drawn }),
    );
    if (theme === "light") {
      seen[kind] = at;
    }

    // The mark's own tooltip, over the mark.
    await hover("#header-root-kind");
    await browser.waitFor(`(${TOOLTIP}) !== null`, STEP_MS);
    const shown = await browser.evaluate(TOOLTIP);
    check(
      `${where}: the tooltip over the mark is its sentence`,
      shown === at.tip,
      `${shown} / ${at.tip}`,
    );
    await screenshot(`root-kind-${kind}-${theme}-tooltip.png`);

    await hover(".header-path");
    await browser.waitFor(`(${TOOLTIP}) === null`, STEP_MS);
    const details = await browser.evaluate(`(() => {
      const root = document.getElementById("root-details");
      const summary = root.querySelector("summary");
      summary.focus();
      summary.click();
      return {
        open: root.open,
        text: root.querySelector(".root-details-info").innerText,
        removed: document.querySelector(".header-copy") === null,
      };
    })()`);
    check(
      `${where}: the disclosure has checkout details and replaces the hover copy control`,
      details.open && details.removed && details.text.includes(at.label.split(" (")[0]),
      JSON.stringify(details),
    );
    if (kind === "git") {
      await browser.waitFor(
        'document.querySelector("#root-details a[data-web-view=external]") !== null',
        STEP_MS,
      );
      const links = await browser.evaluate(`(async () => {
        const panel = document.querySelector(".root-details-panel");
        const copy = panel.querySelector("button");
        const link = panel.querySelector("a");
        let copied;
        Object.defineProperty(navigator, "clipboard", {
          configurable: true,
          value: { writeText: async (text) => { copied = text; } },
        });
        copy.click();
        await Promise.resolve();
        delete navigator.clipboard;
        return {
          copied,
          href: link.href,
          labels: [copy.innerText, link.innerText],
          glyphs: [copy, link].map(item => item.querySelector(".menu-item-icon svg") !== null),
          owner: [copy, link].every(window.MetabrowserPluginHost.isOwnedDelegate),
          result: panel.querySelector('[role="status"]').textContent,
        };
      })()`);
      check(
        `${where}: both link actions use the repository URL and shared icons`,
        links.copied === "https://github.com/octo/demo" &&
          links.href === links.copied &&
          links.labels.join("|") === "Copy Link|Open in Browser" &&
          links.glyphs.every(Boolean) &&
          links.owner &&
          links.result === "Link copied",
        JSON.stringify(links),
      );
    } else {
      const hasActions = await browser.evaluate(
        'document.querySelector("#root-details").hasAttribute("data-repository-url")',
      );
      check(`${where}: a root with no hosted URL has no link actions`, !hasActions, details);
    }
    await screenshot(`root-kind-${kind}-${theme}-details.png`);
    const dismissed = await browser.evaluate(`(() => {
      const root = document.getElementById("root-details");
      const summary = root.querySelector("summary");
      summary.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
      return !root.open && document.activeElement === summary;
    })()`);
    check(`${where}: Escape closes the disclosure and returns focus`, dismissed, details);
    await browser.send("Input.dispatchMouseEvent", { type: "mouseMoved", x: 900, y: 400 });
    await screenshot(`root-kind-${kind}-${theme}.png`);
  }
}

// A folder inside the root is an ordinary folder: its header leads with the ordinary glyph,
// which is no kind's.
await open(`${pages.folder}docs`);
const inside = await browser.evaluate(READ);
check(
  "a folder inside the root leads its header with the ordinary folder's glyph",
  inside.headerGlyph === inside.folderGlyph && inside.headerGlyph !== inside.drawn,
  JSON.stringify({ header: inside.headerGlyph, ordinary: inside.folderGlyph }),
);

// The three kinds are three shapes, and none is the ordinary folder's.
const shapes = Object.values(seen).map((at) => at.drawn);
check(
  "the three kinds draw three different shapes",
  new Set(shapes).size === Object.keys(pages).length,
  JSON.stringify(shapes),
);
await browser.close();

if (failures.length > 0) {
  process.stderr.write(`${failures.join("\n")}\n`);
  process.exit(1);
}
process.stdout.write(`root kind marks in Chrome: ${checks} checks passed\n`);

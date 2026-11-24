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
//   in the same Home link, centered on the name's line, and its glyph arrives in that box
//   without moving the name;
// - the glyph is the one the server wrote for the kind (static/source-kind-glyphs.json), drawn
//   in `--muted`, and the three kinds draw three shapes, none of them the ordinary folder's;
// - the main pane's header for the root leads with that same glyph, and the header of a folder
//   inside the root with the ordinary folder's, so a root is never drawn as an ordinary folder;
// - its tooltip shows over it, and is its accessible name; and
// - the mark and name open Home; the adjacent Info button opens details and dismisses on a
//   repeated click, an outside click, or Escape.
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
  const name = document.querySelector(".header-home-name");
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
    inLink: name.closest("#header-home").contains(mark),
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

async function pointFor(selector) {
  return browser.evaluate(`(() => {
    const box = document.querySelector(${JSON.stringify(selector)}).getBoundingClientRect();
    return { x: box.left + box.width / 2, y: box.top + box.height / 2 };
  })()`);
}

async function hover(selector) {
  await browser.send("Input.dispatchMouseEvent", {
    type: "mouseMoved",
    ...(await pointFor(selector)),
  });
}

async function click(selector, button = "left") {
  const point = await pointFor(selector);
  await browser.send("Input.dispatchMouseEvent", {
    type: "mousePressed",
    ...point,
    button,
    clickCount: 1,
  });
  await browser.send("Input.dispatchMouseEvent", {
    type: "mouseReleased",
    ...point,
    button,
    clickCount: 1,
  });
}

const TRIGGER = "#root-details > summary";
const MENU_OPEN = 'document.getElementById("root-details").open';
const INFO_ICON = `(() => {
  const trigger = document.querySelector("${TRIGGER}");
  const glyph = trigger.querySelector("svg");
  const template = document.createElement("template");
  template.innerHTML = window.MetabrowserIcons.info;
  return glyph.outerHTML === template.content.firstElementChild.outerHTML &&
    getComputedStyle(glyph).rotate === "none";
})()`;

async function checkCheckoutDetails() {
  const chip = "#root-details .root-details-branch button";
  const revisionCopy = "#root-details .git-commit-revision-copy";
  const menu = "#root-details > [data-ref-action-menu]";
  const state = await browser.evaluate(`(() => {
    const chip = document.querySelector(${JSON.stringify(chip)});
    const id = document.querySelector("#root-details .git-commit-sha");
    const copy = document.querySelector(${JSON.stringify(revisionCopy)});
    const { branch, revision } = window.METABROWSER_REPOSITORY_CONTEXT;
    return {
      chip: chip.matches(".git-ref-local.git-ref-head"),
      branch, revision,
      text: id.textContent,
      shortRevision: window.metabrowser.shortCommit(revision),
      font: getComputedStyle(id).fontFamily,
      ariaLabel: copy.getAttribute("aria-label"),
      owned: window.MetabrowserPluginHost.isOwnedDelegate(copy),
    };
  })()`);
  check(
    "checkout details show the shared local branch chip and short monospace commit",
    state.chip &&
      state.text === state.shortRevision &&
      state.font.includes("monospace") &&
      state.ariaLabel === "Copy revision" &&
      state.owned,
    JSON.stringify(state),
  );
  const narrow = await browser.evaluate(`(() => {
    const pane = document.getElementById("tree-pane");
    const width = pane.style.width;
    pane.style.width = "180px";
    const chip = document.querySelector(${JSON.stringify(chip)});
    const label = chip.querySelector(".git-ref-label");
    const panel = chip.closest(".root-details-panel");
    const fits = chip.getBoundingClientRect().right <= panel.getBoundingClientRect().right;
    const clipped = label.scrollWidth > label.clientWidth;
    pane.style.width = width;
    return fits && clipped;
  })()`);
  check("a long branch stays inside the narrow folder details", narrow);
  await hover("#root-details .git-commit-sha");
  await browser.waitFor(
    `getComputedStyle(document.querySelector(${JSON.stringify(revisionCopy)})).opacity === "1"`,
    STEP_MS,
  );
  await browser.evaluate(`Object.defineProperty(navigator, "clipboard", {
    configurable: true,
    value: { writeText: async (text) => { window.rootDetailsClipboard = text; } },
  })`);
  await click(revisionCopy);
  check(
    "the commit copy button copies the full revision and leaves the menu open",
    (await browser.evaluate("window.rootDetailsClipboard")) === state.revision &&
      (await browser.evaluate(MENU_OPEN)),
  );
  await click(chip);
  await browser.waitFor(`document.querySelector(${JSON.stringify(menu)}) !== null`, STEP_MS);
  const menuState = await browser.evaluate(`(() => {
    const root = document.getElementById("root-details");
    const menu = document.querySelector(${JSON.stringify(menu)});
    return {
      open: root.open && menu.contains(document.activeElement),
      label: menu.getAttribute("aria-label"),
      labels: [...menu.querySelectorAll(".menu-item")].map(item => item.textContent),
      url: menu.querySelector("a")?.href,
    };
  })()`);
  check(
    "the nested branch menu has its context, focus, and shared actions",
    menuState.open &&
      menuState.label === `Local branch ${state.branch}` &&
      menuState.labels.join("|") === "Copy Branch Name|View This Branch|Open on GitHub" &&
      menuState.url === `https://github.com/Octo/Demo/tree/refs/heads/${state.branch}`,
    JSON.stringify(menuState),
  );
  await click(`${menu} button`);
  check(
    "copying the branch from the nested menu keeps the root details open",
    (await browser.evaluate("window.rootDetailsClipboard")) === state.branch &&
      (await browser.evaluate(MENU_OPEN)),
  );
  const escaped = await browser.evaluate(`(() => {
    document.activeElement.dispatchEvent(new KeyboardEvent("keydown", {
      key: "Escape", bubbles: true, cancelable: true,
    }));
    return ${MENU_OPEN} && document.activeElement.matches(${JSON.stringify(chip)}) &&
      document.querySelector(${JSON.stringify(menu)}) === null;
  })()`);
  check("the first Escape closes only the branch menu and restores chip focus", escaped);
  await click(chip);
  await click(chip);
  check(
    "clicking the same branch chip closes only its menu",
    await browser.evaluate(
      `${MENU_OPEN} && document.querySelector(${JSON.stringify(menu)}) === null`,
    ),
  );
  await click(chip);
  await click(TRIGGER);
  await browser.waitFor(`document.querySelector(${JSON.stringify(menu)}) === null`, STEP_MS);
  check(
    "closing folder details clears the nested menu and its expanded state",
    await browser.evaluate(`!(${MENU_OPEN}) &&
      document.querySelector(${JSON.stringify(chip)}).getAttribute("aria-expanded") === "false"`),
  );
  await browser.evaluate("delete navigator.clipboard");
  await click(TRIGGER);
}

const TOOLTIP = `(() => {
  const tip = document.querySelector(".custom-tooltip");
  return tip && tip.classList.contains("visible") ? tip.innerText.trim() : null;
})()`;

async function screenshot(file, height = CLIP.height) {
  const { data } = await browser.send("Page.captureScreenshot", {
    format: "png",
    clip: { ...CLIP, height },
  });
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
      `${where}: the mark is before the name in the same Home link`,
      at.inLink && at.box.right <= at.name.left + TOLERANCE_PX,
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

    await hover(".header-home-name");
    await browser.waitFor(`(${TOOLTIP}) === null`, STEP_MS);
    const closedInfoIcon = await browser.evaluate(INFO_ICON);
    await click(TRIGGER);
    if (kind === "folder" && theme === "light") {
      check("the Info button opens the menu", await browser.evaluate(MENU_OPEN));
      await click(TRIGGER);
      check("clicking the same Info button closes the menu", !(await browser.evaluate(MENU_OPEN)));
      await click(TRIGGER);
      await browser.evaluate(`(() => {
        const outside = document.getElementById("settings-btn");
        outside.addEventListener("pointerdown", (event) => {
          event.preventDefault();
          event.stopPropagation();
        }, { once: true });
        outside.addEventListener("click", (event) => event.stopPropagation(), { once: true });
      })()`);
      await click("#settings-btn");
      check(
        "a click on another control closes the menu despite stopped propagation",
        !(await browser.evaluate(MENU_OPEN)),
      );
      // Clear the newly opened Settings menu and return to the closed root menu.
      await click("#settings-btn");
      await browser.evaluate(`(() => {
        const outside = document.getElementById("settings-btn");
        outside.addEventListener("pointerdown", (event) => event.preventDefault());
        outside.addEventListener("contextmenu", (event) => event.preventDefault(), { once: true });
      })()`);
      for (const button of ["middle", "right"]) {
        await browser.evaluate(`document.getElementById("root-details").open = false`);
        await click(TRIGGER);
        check(
          `an outside ${button} click starts with the menu open`,
          await browser.evaluate(MENU_OPEN),
        );
        await click("#settings-btn", button);
        check(`an outside ${button} click closes the menu`, !(await browser.evaluate(MENU_OPEN)));
      }
      await browser.evaluate(`document.getElementById("root-details").open = false`);
      await click(TRIGGER);
    }
    const details = await browser.evaluate(`(() => {
      const root = document.getElementById("root-details");
      const summary = root.querySelector("summary");
      return {
        open: root.open,
        label: summary.getAttribute("aria-label"),
        local: root.querySelector(".root-details-local").innerText,
        source: root.querySelector(".root-details-source").innerText,
        text: root.querySelector(".root-details-info").innerText,
        removed: document.querySelector(".header-copy") === null,
      };
    })()`);
    check(
      `${where}: the disclosure has checkout details and replaces the hover copy control`,
      details.open && details.removed && details.text.includes(at.label.split(" (")[0]),
      JSON.stringify(details),
    );
    check(
      `${where}: the menu keeps its Info glyph, accessible name, and local path label`,
      closedInfoIcon &&
        (await browser.evaluate(INFO_ICON)) &&
        details.label === `${at.label.split(" (")[0]} details` &&
        details.local.startsWith("Local path"),
      JSON.stringify(details),
    );
    if (kind === "mirror") {
      check(
        `${where}: the source tip and the local mirror path are separate`,
        details.local.endsWith("/repository.git") &&
          details.source === "Bare Git mirror with no checked-out files.",
        JSON.stringify(details),
      );
    }
    if (kind === "git") {
      await browser.waitFor(
        'document.querySelector("#root-details a[data-web-view=external]") !== null',
        STEP_MS,
      );
      const links = await browser.evaluate(`(async () => {
        const panel = document.querySelector(".root-details-panel");
        const copy = panel.querySelector(".root-details-actions button");
        const link = panel.querySelector(".root-details-actions a");
        let copied;
        Object.defineProperty(navigator, "clipboard", {
          configurable: true,
          value: { writeText: async (text) => { copied = text; } },
        });
        copy.focus();
        copy.click();
        await Promise.resolve();
        delete navigator.clipboard;
        return {
          copied,
          href: link.href,
          destination: panel.querySelector(".menu-link-url").innerText,
          labels: [copy.innerText, link.innerText],
          glyphs: [copy, link].map(item => item.querySelector(".menu-item-icon svg") !== null),
          owner: [copy, link].every(window.MetabrowserPluginHost.isOwnedDelegate),
          focusedInside: panel.closest("details").open && document.activeElement === copy,
          result: panel.querySelector('[role="status"]').textContent,
        };
      })()`);
      check(
        `${where}: both link actions use the repository URL and shared icons`,
        links.copied === "https://github.com/octo/demo" &&
          links.href === links.copied &&
          links.destination === links.copied &&
          links.labels.join("|") === "Copy Link|Open in Browser" &&
          links.glyphs.every(Boolean) &&
          links.owner &&
          links.focusedInside &&
          links.result === "Link copied",
        JSON.stringify(links),
      );
      if (theme === "light") {
        await checkCheckoutDetails();
      }
    } else {
      const hasActions = await browser.evaluate(
        'document.querySelector("#root-details").hasAttribute("data-repository-url")',
      );
      check(`${where}: a root with no hosted URL has no link actions`, !hasActions, details);
    }
    await browser.waitFor(
      'document.querySelector(".custom-tooltip")?.style.display !== "block"',
      STEP_MS,
    );
    await screenshot(`root-kind-${kind}-${theme}-details.png`, 300);
    const dismissed = await browser.evaluate(`(() => {
      const root = document.getElementById("root-details");
      const summary = root.querySelector("summary");
      const chords = ["altKey", "ctrlKey", "metaKey"].every((modifier) => {
        const escape = new KeyboardEvent("keydown", {
          key: "Escape", bubbles: true, cancelable: true, [modifier]: true,
        });
        return summary.dispatchEvent(escape) && root.open;
      });
      summary.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
      return chords && !root.open && document.activeElement === summary;
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

for (const selector of ["#header-root-kind", ".header-home-name"]) {
  await open(`${pages.folder}docs`);
  const startingPath = await browser.evaluate("location.pathname");
  await click(TRIGGER);
  const afterMenu = await browser.evaluate(`({ path: location.pathname, open: ${MENU_OPEN} })`);
  check(
    `the Info button opens details without navigating before clicking ${selector}`,
    afterMenu.open && startingPath !== "/view/" && afterMenu.path === startingPath,
    JSON.stringify({ startingPath, afterMenu }),
  );
  await click(selector);
  await browser.waitFor('location.pathname === "/view/"', STEP_MS);
  check(`${selector} navigates Home and dismisses details`, !(await browser.evaluate(MENU_OPEN)));
}

// An HTML preview has its own browsing context and its clicks do not reach the shell.
await browser.send("Page.enable");
await browser.send("Page.addScriptToEvaluateOnNewDocument", {
  source: `window.addEventListener("message", (event) => {
    const frame = document.querySelector("iframe.file-html-preview");
    if (event.data === "root-kind-preview-ready" && event.source === frame?.contentWindow) {
      frame.dataset.loaded = "true";
    }
  });`,
});
await open(`${pages.folder}preview.html`);
await browser.waitFor(
  `(() => {
    const frame = document.querySelector("iframe.file-html-preview[data-loaded]");
    if (!frame) return false;
    const box = frame.getBoundingClientRect();
    return document.elementFromPoint(box.left + box.width / 2, box.top + box.height / 2) === frame;
  })()`,
  STEP_MS,
);
await click(TRIGGER);
check("the Info button opens beside a sandboxed HTML preview", await browser.evaluate(MENU_OPEN));
await click("iframe.file-html-preview");
await browser.waitFor('document.activeElement.matches("iframe.file-html-preview")', STEP_MS);
check(
  "a click in the preview dismisses the menu and leaves focus in the preview",
  !(await browser.evaluate(MENU_OPEN)),
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

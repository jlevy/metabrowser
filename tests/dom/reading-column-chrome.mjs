// A reading column centered while the navigation pane is hidden, laid out and animated by
// headless Chrome against a live `metab` server.
//
//   CHROME_BIN=/path/to/chrome CHROME_PROFILES=/dir/the/caller/removes \
//     node tests/dom/reading-column-chrome.mjs <server base URL>
//
// tests/test_reading_column_chrome.py serves a folder with a long document, a short one,
// and a source file, owns the profile directory, and runs this in a process group of its
// own, which Chrome joins.
//
// The glide's state machine, which way the content moves and from where a turned slide
// picks it up, is browserless (`cli-ui-nav-collapse.tryscript.md`). What only a browser can
// tell is held here (docs/design-system.md, "Hiding the Navigation Pane"):
//
// - with the pane hidden, a document's card and its table of contents, a short document's
//   card, and the folder's Overview sit in the middle of the pane's content box, the same
//   room before them as after, at 1920 and 2560 px windows;
// - the eyebrow's Up, the header's icon, the first tab, and the column share one edge, and
//   the header's corner stays at the frame's end;
// - with the pane shown, and in a window too narrow for the wide band, the column starts at
//   the gutter, as it always has, and a source file keeps the gutter with the pane hidden;
// - a real `\` and Shift-\ glide the column in every frame from where it was drawn to its
//   new place, never back, with nothing pushed past the pane's end; and
// - under reduced motion the column moves at once.
//
// Each step writes `phase <name> <ms since start>` to stderr, so a slow run says where.
import { launchChrome } from "./chrome-session.mjs";

const [base] = process.argv.slice(2);
if (!base || !process.env.CHROME_BIN || !process.env.CHROME_PROFILES) {
  throw new Error("usage: CHROME_BIN CHROME_PROFILES reading-column-chrome.mjs <base URL>");
}
const started = Date.now();
const phase = (name) => process.stderr.write(`phase ${name} ${Date.now() - started}\n`);
// Layout places boxes in a 64th of a pixel, and a centered unit splits an odd pixel.
const TOLERANCE_PX = 1;
// How long a toggle is sampled: --motion-reveal in static/styles.css, with room for frames a
// loaded machine drops.
const SAMPLE_MS = 900;
const STEP_MS = 30000;
// The DevTools input domain's Shift bit.
const SHIFT = 8;
// Windows in the wide band, where a column is centered, and one below it, where it is not
// (the band starts at a 75rem pane, `@container kpress-doc (min-width: 75rem)`).
const WIDE = [1920, 2560];
const NARROW = 1100;

let checks = 0;
const failures = [];
const check = (label, ok, detail = "") => {
  checks += 1;
  if (!ok) {
    failures.push(`${label}${detail ? `: ${detail}` : ""}`);
    process.stderr.write(`failed ${label}\n`);
  }
};
// The main frame's animations, the slide and the glides: the tree's spinners run on.
const FRAME_ANIMATIONS = `document.getAnimations().filter((each) => each.effect?.target?.closest?.(".preview-frame")).length`;
const SETTLED = `${FRAME_ANIMATIONS} === 0`;
const near = (a, b) => a !== null && b !== null && Math.abs(a - b) <= TOLERANCE_PX;

// In the page: where the main view's column, header, and tabs are, against the pane.
const READ = `(() => {
  const pane = document.getElementById("preview-pane");
  const live = (selector) =>
    [...pane.querySelectorAll(selector)].find(
      (each) =>
        !each.closest(".preview-file-stage") &&
        getComputedStyle(each).visibility === "visible" &&
        each.getBoundingClientRect().width > 0,
    ) ?? null;
  const box = (element) => {
    if (!element) {
      return null;
    }
    const rect = element.getBoundingClientRect();
    return { left: rect.left, right: rect.right };
  };
  const paneBox = pane.getBoundingClientRect();
  const card = live(".kpress-long-text") ?? live(".folder-overview-panel-heading");
  const toc = live(".kpress-toc");
  const code = live(".code-block");
  const column = box(card);
  const end = toc ? box(toc).right : column?.right ?? null;
  return {
    paneLeft: paneBox.left,
    contentRight: paneBox.left + pane.clientWidth,
    frameRight: document.querySelector(".preview-frame").getBoundingClientRect().right,
    padding: parseFloat(getComputedStyle(document.documentElement).getPropertyValue("--content-padding-x")),
    column,
    end,
    code: box(code),
    up: box(live(".view-header-eyebrow > .folder-up")),
    icon: box(live(".view-header-heading > .view-header-icon")),
    tab: box(live(".tab-bar > .tab-btn")),
    // Placed at the frame's end whether or not it holds a button yet.
    corner: box(pane.querySelector(":scope > .view-header > .view-header-end")),
    collapsed: document.querySelector(".container").hasAttribute("data-nav-collapsed"),
    animations: ${FRAME_ANIMATIONS},
  };
})()`;

// In the page: the column's left edge in every frame for SAMPLE_MS, and whether the pane
// could scroll sideways in any of them, from the next frame on.
const SAMPLE = `new Promise((done) => {
  const pane = document.getElementById("preview-pane");
  const column = [...pane.querySelectorAll(".kpress-long-text, .folder-overview-panel-heading")].find(
    (each) => !each.closest(".preview-file-stage") && each.getBoundingClientRect().width > 0,
  );
  const lefts = [];
  let overflow = false;
  const start = performance.now();
  const tick = () => {
    lefts.push(column.getBoundingClientRect().left);
    overflow ||= pane.scrollWidth > pane.clientWidth;
    if (performance.now() - start < ${SAMPLE_MS}) {
      requestAnimationFrame(tick);
    } else {
      done({ lefts, overflow });
    }
  };
  requestAnimationFrame(tick);
})`;

const chrome = await launchChrome(process.env.CHROME_BIN, {
  profiles: process.env.CHROME_PROFILES,
  width: WIDE[0],
  height: 1000,
});
phase("chrome");

/** @param {number} width */
async function resize(width) {
  await chrome.send("Emulation.setDeviceMetricsOverride", {
    width,
    height: 1000,
    deviceScaleFactor: 1,
    mobile: false,
  });
}

/** @param {string} path */
async function open(path) {
  await chrome.send("Page.navigate", { url: `${base}/${path}` });
  // The shell's tools, which bring `\` and the chevron, load after the view; a press before
  // them does nothing (nav-collapse-chrome.mjs waits the same way).
  await chrome.waitFor(
    `(() => {
      const pane = document.getElementById("preview-pane");
      return document.documentElement?.dataset.shellToolsReady === "true" &&
        !!pane && !pane.classList.contains("preview-navigation-pending") &&
        !!pane.querySelector(":scope > .content-body .kpress-long-text, :scope > .content-body .folder-overview-panel-heading, :scope > .content-body .code-block");
    })()`,
    STEP_MS,
  );
  // The view settles: the counterpart in the header's corner, and fonts.
  await chrome.evaluate("document.fonts.ready.then(() => true)");
  await chrome.waitFor(SETTLED, STEP_MS).catch(() => {});
}

/** Press `\` (hide) or Shift-\ (show) as a keyboard does. @param {boolean} shift */
async function press(shift) {
  const key = shift ? "|" : "\\";
  const modifiers = shift ? SHIFT : 0;
  const common = { key, code: "Backslash", windowsVirtualKeyCode: 220, modifiers };
  await chrome.send("Input.dispatchKeyEvent", { type: "keyDown", text: key, ...common });
  await chrome.send("Input.dispatchKeyEvent", { type: "keyUp", ...common });
}

/** A toggle, sampled in every frame, then the settled page. @param {boolean} shift */
async function toggle(shift) {
  const sampling = chrome.evaluate(SAMPLE);
  await press(shift);
  const frames = await sampling;
  await chrome.waitFor(SETTLED, STEP_MS).catch(() => {});
  return { frames, page: await chrome.evaluate(READ) };
}

/**
 * The glide in every frame: from where the column was drawn before the press, monotone,
 * to where it rests, and never wider than the pane.
 *
 * @param {string} label
 * @param {{ lefts: number[], overflow: boolean }} frames
 * @param {number} from
 * @param {number} to
 */
function checkGlide(label, frames, from, to) {
  const { lefts, overflow } = frames;
  // The first sampled frame can come before the press lands; the first one that moved
  // starts at most one frame's travel from where the column was.
  const moved = lefts.findIndex((left) => Math.abs(left - from) > TOLERANCE_PX);
  check(`${label}: the column moves`, moved >= 0, JSON.stringify(lefts));
  const direction = Math.sign(to - from);
  let backward = null;
  for (let index = 1; index < lefts.length; index += 1) {
    if ((lefts[index] - lefts[index - 1]) * direction < -TOLERANCE_PX) {
      backward = index;
      break;
    }
  }
  check(`${label}: the column never moves back`, backward === null, JSON.stringify(lefts));
  // No jump: no frame is further from its neighbor than the whole move would allow in one
  // frame at the easing's steepest, and the first move starts beside where it was.
  const largest = Math.max(...lefts.slice(1).map((left, index) => Math.abs(left - lefts[index])));
  check(
    `${label}: no frame jumps the whole way`,
    largest < Math.abs(to - from) * 0.75,
    `largest step ${largest} of ${Math.abs(to - from)}: ${JSON.stringify(lefts)}`,
  );
  check(`${label}: the column comes to rest`, near(lefts.at(-1), to), JSON.stringify(lefts));
  check(`${label}: nothing passes the pane's end`, !overflow);
}

/** Where a column starts and ends with the pane shown: at the gutter. */
function checkAtGutter(label, page) {
  check(
    `${label}: the column starts at the gutter`,
    near(page.column?.left ?? null, page.paneLeft + page.padding),
    JSON.stringify(page),
  );
}

/** Centered, with the header and tabs on its edge and the corner at the end. */
function checkCentered(label, page, shownCorner) {
  const before = page.column.left - page.paneLeft;
  const after = page.contentRight - page.end;
  check(
    `${label}: as much room before the column as after it`,
    near(before, after),
    `${before} before, ${after} after`,
  );
  check(`${label}: centered past the gutter`, before > page.padding + TOLERANCE_PX, `${before}`);
  for (const name of ["up", "icon", "tab"]) {
    check(
      `${label}: the ${name} starts on the column's edge`,
      near(page[name]?.left ?? null, page.column.left),
      JSON.stringify(page[name]),
    );
  }
  check(
    `${label}: the header's corner stays at the frame's end`,
    near(page.corner?.right ?? null, shownCorner),
    `${page.corner?.right} against ${shownCorner}`,
  );
}

try {
  for (const width of WIDE) {
    await resize(width);
    for (const path of ["view/guide.md", "view/short.md", ""]) {
      const label = `${width} px ${path || "folder"}`;
      await open(path);
      phase(`open ${label}`);
      const shown = await chrome.evaluate(READ);
      checkAtGutter(`${label} shown`, shown);
      const hiding = await toggle(false);
      phase(`hide ${label}`);
      check(`${label}: the pane is hidden`, hiding.page.collapsed);
      checkCentered(`${label} hidden`, hiding.page, shown.corner.right);
      checkGlide(`${label} hide`, hiding.frames, shown.column.left, hiding.page.column.left);
      const showing = await toggle(true);
      phase(`show ${label}`);
      check(`${label}: the pane is shown`, !showing.page.collapsed);
      checkAtGutter(`${label} shown again`, showing.page);
      checkGlide(
        `${label} show`,
        showing.frames,
        hiding.page.column.left,
        showing.page.column.left,
      );
    }
  }

  // An expanded README's rail forms part of the column. Once collapsed, it is still
  // mounted and hidden. The remaining visible headings center without the rail.
  await open("view/with-readme-toc/");
  const readme = 'document.querySelector(".folder-overview-panel-document")';
  const readmeToc = `${readme}?.querySelector(".kpress-toc")`;
  await chrome.waitFor(
    `${readmeToc} && getComputedStyle(${readmeToc}).visibility === "visible"`,
    STEP_MS,
  );
  await press(false);
  await chrome.waitFor(SETTLED, STEP_MS);
  const withRail = await chrome.evaluate(READ);
  check("expanded README: the pane is hidden", withRail.collapsed);
  checkCentered("expanded README with its rail", withRail, withRail.corner.right);
  await chrome.evaluate(`${readme}.querySelector(".folder-overview-panel-toggle").click()`);
  await chrome.waitFor(
    `${readmeToc} && getComputedStyle(${readmeToc}).visibility === "hidden"`,
    STEP_MS,
  );
  const withoutRail = await chrome.evaluate(READ);
  checkCentered("collapsed README without its rail", withoutRail, withRail.corner.right);
  await press(true);
  await chrome.waitFor(SETTLED, STEP_MS);
  phase("collapsed README");

  // A source file keeps the gutter with the pane hidden: it states no reading unit.
  await resize(WIDE[0]);
  await open("view/tool.py");
  await press(false);
  await chrome.waitFor(SETTLED, STEP_MS).catch(() => {});
  const source = await chrome.evaluate(READ);
  check(
    "source hidden: the code starts at the gutter",
    source.collapsed && near(source.code?.left ?? null, source.paneLeft + source.padding),
    JSON.stringify(source),
  );
  await press(true);
  await chrome.waitFor(SETTLED, STEP_MS).catch(() => {});
  phase("source");

  // Below the wide band the column keeps the gutter with the pane hidden.
  await resize(NARROW);
  await open("view/guide.md");
  await press(false);
  await chrome.waitFor(SETTLED, STEP_MS).catch(() => {});
  const narrow = await chrome.evaluate(READ);
  check("narrow hidden: the pane is hidden", narrow.collapsed);
  checkAtGutter("narrow hidden", narrow);
  await press(true);
  await chrome.waitFor(SETTLED, STEP_MS).catch(() => {});
  phase("narrow");

  // Under reduced motion the column is in its place as the press lands, with no glide.
  await resize(WIDE[0]);
  await chrome.send("Emulation.setEmulatedMedia", {
    features: [{ name: "prefers-reduced-motion", value: "reduce" }],
  });
  await open("view/guide.md");
  const still = await chrome.evaluate(READ);
  await press(false);
  const moved = await chrome.evaluate(READ);
  check("reduced motion: hidden at once", moved.collapsed);
  check("reduced motion: no glide", moved.animations === 0, `${moved.animations} animations`);
  checkCentered("reduced motion", moved, still.corner.right);
  phase("reduced motion");
} finally {
  await chrome.close();
}

if (failures.length > 0) {
  console.error(failures.join("\n"));
  process.exitCode = 1;
} else {
  console.log(`reading column in Chrome: ${checks} checks passed`);
}

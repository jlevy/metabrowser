// Hiding the navigation pane, laid out and animated by headless Chrome against a live
// `metab` server.
//
//   CHROME_BIN=/path/to/chrome CHROME_PROFILES=/dir/the/caller/removes \
//     node tests/dom/nav-collapse-chrome.mjs <server base URL>
//
// tests/test_nav_collapse_chrome.py serves a plain folder, owns the profile directory, and
// runs this in a process group of its own, which Chrome joins.
//
// What `\` and the chevron do to the page's state, and which keys stay live while the pane
// is hidden, are browserless (`cli-ui-nav-collapse.tryscript.md`). What only a browser can
// tell is held here (docs/design-system.md, "Hiding the Navigation Pane"):
//
// - the chevron sits at the start of the main page's foot, in the gutter before the
//   content's edge, centered on the shortcut strip's row across the divider (mb-yw18),
//   pointing left at the pane, with no plate of its own, and stays there with the pane
//   hidden, and when a row under the strip shows;
// - the main page's focus ring paints over a band of the page with a ground of its own,
//   as a pull request's tab bar is (mb-0rop);
// - holding Shift shows its `\` badge, painted over the button rather than under it;
// - a real `\`, sent through the DevTools input domain, slides the frame from the pane's
//   edge to the window's in every frame without moving back, at its full width throughout,
//   and leaves the pane covered and inert and the chevron pointing right, on the same row;
// - a real Shift-\, which types `|`, slides it back and gives the pane its place again;
// - a click on the chevron does what `\` does; and
// - under reduced motion the page moves at once, with no animation.
//
// Each step writes `phase <name> <ms since start>` to stderr, so a slow run says where.
import zlib from "node:zlib";

import { launchChrome } from "./chrome-session.mjs";

const [base] = process.argv.slice(2);
if (!base || !process.env.CHROME_BIN || !process.env.CHROME_PROFILES) {
  throw new Error("usage: CHROME_BIN CHROME_PROFILES nav-collapse-chrome.mjs <base URL>");
}
const started = Date.now();
const phase = (name) => process.stderr.write(`phase ${name} ${Date.now() - started}\n`);
// Layout places boxes in a 64th of a pixel; under half a pixel is not a different place.
const TOLERANCE_PX = 0.5;
// How long a slide is sampled: --motion-reveal in static/styles.css, with room for frames a
// loaded machine drops.
const SAMPLE_MS = 900;
const STEP_MS = 30000;
// The DevTools input domain's Shift bit.
const SHIFT = 8;

let checks = 0;
const failures = [];
const check = (label, ok, detail = "") => {
  checks += 1;
  if (!ok) {
    failures.push(`${label}${detail ? `: ${detail}` : ""}`);
    process.stderr.write(`failed ${label}\n`);
  }
};

// In the page: where the pane, the frame, the chevron, the shortcut strip, and Up are,
// and their states.
const READ = `(() => {
  const pane = document.getElementById("tree-pane");
  const frame = document.querySelector(".preview-frame");
  const strip = document.getElementById("nav-shortcut-hints");
  // The committed view's Up, never a staged view's copy, which takes no pointer.
  const up = [...document.querySelectorAll("#preview-pane .view-header-eyebrow > .folder-up")].find(
    (each) => !each.closest(".preview-file-stage"),
  ) ?? null;
  const button = document.getElementById("nav-collapse-toggle");
  const box = (element) => {
    const rect = element.getBoundingClientRect();
    return { left: rect.left, right: rect.right, top: rect.top, height: rect.height, width: rect.width };
  };
  const paneBox = box(pane);
  const covering = document.elementFromPoint(paneBox.left + paneBox.width / 2, paneBox.top + paneBox.height / 2);
  const turn = new DOMMatrixReadOnly(getComputedStyle(button.querySelector("svg")).transform);
  return {
    pane: paneBox,
    frame: box(frame),
    frameLayoutWidth: frame.offsetWidth,
    // The strip's row below its rule, the line its keys are on.
    row: (() => {
      const rect = strip.getBoundingClientRect();
      return { top: rect.top + strip.clientTop, height: strip.clientHeight };
    })(),
    padding: parseFloat(getComputedStyle(document.documentElement).getPropertyValue("--content-padding-x")),
    up: up ? box(up) : null,
    button: box(button),
    window: document.documentElement.clientWidth,
    collapsed: document.querySelector(".container").hasAttribute("data-nav-collapsed"),
    inert: pane.inert,
    covered: Boolean(covering && frame.contains(covering)),
    expanded: button.getAttribute("aria-expanded"),
    label: button.getAttribute("aria-label"),
    pointsLeft: Math.abs(turn.a + 1) < 0.01,
    pointsRight: Math.abs(turn.a - 1) < 0.01,
    animations: frame.getAnimations().length,
    buttonGround: getComputedStyle(button).backgroundColor,
    // Whether a press anywhere in each box, its corners and middle a pixel in, lands on it:
    // true, or each press that missed and what it landed on, so a failure names the cover.
    owns: (() => {
      const named = (node) =>
        node
          ? node.tagName.toLowerCase() +
            (node.id ? "#" + node.id : "") +
            [...node.classList].map((name) => "." + name).join("")
          : null;
      const owns = (element) => {
        if (!element) {
          return null;
        }
        const rect = element.getBoundingClientRect();
        const xs = [rect.left + 1, rect.left + rect.width / 2, rect.right - 1];
        const ys = [rect.top + 1, rect.top + rect.height / 2, rect.bottom - 1];
        const missed = [];
        for (const x of xs) {
          for (const y of ys) {
            const hit = document.elementFromPoint(x, y);
            if (!element.contains(hit)) {
              missed.push({ x, y, hit: named(hit) });
            }
          }
        }
        return missed.length === 0 || missed;
      };
      return { button: owns(button), up: owns(up) };
    })(),
  };
})()`;

// In the page: whether the chevron's badge is what a point on its center hits. A badge
// takes no pointer, so it takes one for the test; hit testing follows the paint order.
const BADGE_ON_TOP = `(() => {
  const badge = [...document.querySelectorAll(".preview-frame > .kbd-badge")].find(
    (each) => each.textContent === "\\\\",
  );
  if (!badge) {
    return null;
  }
  badge.style.pointerEvents = "auto";
  const box = badge.getBoundingClientRect();
  const hit = document.elementFromPoint(box.left + box.width / 2, box.top + box.height / 2);
  badge.style.pointerEvents = "";
  return hit === badge;
})()`;

// In the page: record the frame's left edge and layout width in every frame for a while.
const SAMPLE = `(() => {
  window.navSamples = [];
  window.navSampling = true;
  const frame = document.querySelector(".preview-frame");
  const start = performance.now();
  const tick = () => {
    window.navSamples.push([frame.getBoundingClientRect().left, frame.offsetWidth]);
    if (performance.now() - start < ${SAMPLE_MS}) {
      requestAnimationFrame(tick);
    } else {
      window.navSampling = false;
    }
  };
  requestAnimationFrame(tick);
  return true;
})()`;

const browser = await launchChrome(process.env.CHROME_BIN, {
  profiles: process.env.CHROME_PROFILES,
  width: 1280,
  height: 800,
});

/** Press `\`, or with Shift `|`, through the DevTools input domain: a real key event. */
async function pressBackslash(shift) {
  const key = {
    key: shift ? "|" : "\\",
    code: "Backslash",
    windowsVirtualKeyCode: 220,
    nativeVirtualKeyCode: 220,
    modifiers: shift ? SHIFT : 0,
  };
  await browser.send("Input.dispatchKeyEvent", { type: "keyDown", text: key.key, ...key });
  await browser.send("Input.dispatchKeyEvent", { type: "keyUp", ...key });
}

/** Press or release Shift through the DevTools input domain. */
async function shift(type) {
  await browser.send("Input.dispatchKeyEvent", {
    type,
    key: "Shift",
    code: "ShiftLeft",
    windowsVirtualKeyCode: 16,
    modifiers: type === "keyDown" ? SHIFT : 0,
  });
}

/** Run an action while sampling every frame, and return the samples once the slide ends. */
async function sampled(action) {
  await browser.evaluate(SAMPLE);
  await action();
  await browser.waitFor("window.navSampling === false", STEP_MS);
  return browser.evaluate("window.navSamples");
}

const read = () => browser.evaluate(READ);

/**
 * The color painted at one point of the page, from a one-pixel screenshot: a PNG whose one
 * row is a filter byte and the pixel, which no filter changes with nothing before it.
 */
async function pixel(x, y) {
  const { data } = await browser.send("Page.captureScreenshot", {
    format: "png",
    clip: { x, y, width: 1, height: 1, scale: 1 },
  });
  const png = Buffer.from(data, "base64");
  const idat = [];
  let colorType = 0;
  for (let at = 8; at < png.length; ) {
    const length = png.readUInt32BE(at);
    const type = png.toString("latin1", at + 4, at + 8);
    const body = png.subarray(at + 8, at + 8 + length);
    if (type === "IHDR") {
      colorType = body[9];
    } else if (type === "IDAT") {
      idat.push(body);
    }
    at += 12 + length;
  }
  const raw = zlib.inflateSync(Buffer.concat(idat));
  if (raw.length < 4 || (colorType !== 2 && colorType !== 6)) {
    throw new Error(`unexpected screenshot: color type ${colorType}, ${raw.length} bytes`);
  }
  return [raw[1], raw[2], raw[3]];
}

// In the page: a positioned band with a ground of its own at the top of the main page,
// as a pull request's tab bar on the file stage is, and where the focus ring's top edge
// and its color are. The pane's own inset outline painted under it (mb-0rop).
const RING_PROBE = `(() => {
  const pane = document.getElementById("preview-pane");
  const band = document.createElement("div");
  band.id = "ring-probe";
  // At the folder plugin's level, the highest a plugin's positioned ground takes.
  band.style.cssText =
    "position: absolute; inset: 0 0 auto; z-index: 3; height: 40px; background: rgb(255, 0, 0)";
  pane.prepend(band);
  pane.focus();
  const frame = document.querySelector(".preview-frame").getBoundingClientRect();
  // The ring's color as sRGB bytes, whatever color space the token is written in.
  const canvas = document.createElement("canvas");
  canvas.width = canvas.height = 1;
  const context = canvas.getContext("2d");
  context.fillStyle = getComputedStyle(document.documentElement).getPropertyValue("--link");
  context.fillRect(0, 0, 1, 1);
  return {
    focusVisible: pane.matches(":focus-visible"),
    x: frame.left + frame.width / 2,
    y: frame.top + 1,
    color: [...context.getImageData(0, 0, 1, 1).data.slice(0, 3)],
  };
})()`;

/**
 * The checks every resting state shares: the chevron at the main page's foot, centered on
 * the shortcut strip's row across the divider, and in the gutter before the content's edge
 * and the eyebrow's Up. The pane keeps its layout while hidden, so its strip is where it
 * was, under the page.
 */
function checkChevron(where, at) {
  const rowCenter = at.row.top + at.row.height / 2;
  const buttonCenter = at.button.top + at.button.height / 2;
  check(
    `${where}: the chevron is centered on the shortcut strip's row`,
    Math.abs(buttonCenter - rowCenter) <= TOLERANCE_PX,
    JSON.stringify({ rowCenter, buttonCenter }),
  );
  check(
    `${where}: the chevron sits in the main page's gutter, before the content's edge and Up`,
    at.up !== null &&
      at.button.left >= at.frame.left - TOLERANCE_PX &&
      at.button.right <= at.frame.left + at.padding + TOLERANCE_PX &&
      at.button.right <= at.up.left + TOLERANCE_PX,
    JSON.stringify({ button: at.button, frame: at.frame.left, up: at.up }),
  );
  // WCAG 2.2's minimum target, 2.5.8; the divider's resize reach took the chevron's first
  // 4 px once (review A on #608), so a press anywhere in it must land on it.
  const target = (rect) => rect.width >= 24 && rect.height >= 24;
  check(
    `${where}: the chevron and Up are each a 24 px target, and a press anywhere in either lands on it`,
    at.up !== null &&
      target(at.button) &&
      target(at.up) &&
      at.owns.button === true &&
      at.owns.up === true,
    JSON.stringify({ button: at.button, up: at.up, owns: at.owns }),
  );
  check(
    `${where}: the chevron has no plate at rest`,
    at.buttonGround === "rgba(0, 0, 0, 0)",
    at.buttonGround,
  );
}

function checkShown(where, at) {
  check(`${where}: the pane is in the layout`, !at.collapsed && !at.inert, JSON.stringify(at));
  check(
    `${where}: the page starts at the pane's edge`,
    Math.abs(at.frame.left - at.pane.right) <= 1,
    JSON.stringify({ frame: at.frame.left, pane: at.pane.right }),
  );
  check(
    `${where}: the chevron points left and says Hide`,
    at.pointsLeft && at.expanded === "true" && at.label === "Hide navigation",
    JSON.stringify(at),
  );
  checkChevron(where, at);
}

function checkHidden(where, at) {
  check(`${where}: the pane is hidden and inert`, at.collapsed && at.inert, JSON.stringify(at));
  check(
    `${where}: the page fills the window and covers the pane`,
    Math.abs(at.frame.left) < TOLERANCE_PX &&
      Math.abs(at.frame.width - at.window) <= 1 &&
      at.covered,
    JSON.stringify(at),
  );
  check(
    `${where}: the chevron points right and says Show`,
    at.pointsRight && at.expanded === "false" && at.label === "Show navigation",
    JSON.stringify(at),
  );
  checkChevron(where, at);
}

/**
 * A slide's samples at the frame's full width, the layout it slides at: monotonic, through
 * the space between the edges, and, for a hide, ending at the window's edge. A show's last
 * frames are at the narrower width it settles to, which `checkShown` reads.
 */
function checkSlide(where, all, from, to, width, ends) {
  const samples = all.filter(([, layoutWidth]) => layoutWidth === width);
  const lefts = samples.map(([left]) => left);
  check(`${where}: the page slides at its full width`, samples.length > 2, JSON.stringify(all));
  const direction = Math.sign(to - from);
  check(
    `${where}: the page moves only toward ${to}px`,
    lefts.every(
      (left, index) => index === 0 || (left - lefts[index - 1]) * direction >= -TOLERANCE_PX,
    ),
    JSON.stringify(lefts),
  );
  check(
    `${where}: the page passes through the space between`,
    lefts.some((left) => Math.min(from, to) + 10 < left && left < Math.max(from, to) - 10),
    JSON.stringify(lefts),
  );
  if (ends) {
    check(
      `${where}: the page ends at ${to}px, at its full width`,
      Math.abs(lefts.at(-1) - to) < TOLERANCE_PX && all.at(-1)[1] === width,
      JSON.stringify(all),
    );
  }
}

try {
  phase("before the shell's tools");
  // The chevron is on the strip's row from the first paint, before the bundle that runs
  // it loads: held off here, with the scan's progress showing under the strip, and the
  // divider's reach kept off it (review A on #609).
  await browser.send("Page.enable");
  await browser.send("Network.enable");
  await browser.send("Network.setBlockedURLs", { urls: ["*nav-collapse*.js*"] });
  await browser.send("Page.navigate", { url: `${base}/view/` });
  await browser.waitFor(
    `document.querySelector("#preview-pane > .preview-file-stage") === null &&
     document.querySelector("#preview-pane .view-header-eyebrow > .folder-up") !== null`,
    STEP_MS,
  );
  await browser.evaluate(`document.getElementById("index-progress").hidden = false, true`);
  await browser.evaluate(
    "new Promise((done) => requestAnimationFrame(() => requestAnimationFrame(done)))",
  );
  const early = await read();
  check(
    "before the shell's tools: the module that runs the chevron has not loaded",
    !(await browser.evaluate("Boolean(window.MetabrowserNavCollapse)")),
  );
  checkChevron("before the shell's tools, with the scan's progress showing", early);
  await browser.send("Network.setBlockedURLs", { urls: [] });

  phase("load");
  await browser.send("Page.navigate", { url: `${base}/view/` });
  // The shell's tools are ready before the folder's view is in the page: the view is built
  // in the pane's staging layer (`.preview-file-stage`, app.js), inert, unseen, and taking
  // no pointer, while the loading placeholder is what a press lands on, and is committed
  // after. Its Up is read once the view is committed and the layer gone (mb-hujg).
  await browser.waitFor(
    `document.documentElement?.dataset.shellToolsReady === "true" &&
     document.getElementById("nav-shortcut-hints")?.hidden === false &&
     document.querySelector("#preview-pane > .preview-file-stage") === null &&
     document.querySelector("#preview-pane .view-header-eyebrow > .folder-up") !== null`,
    STEP_MS,
  );
  // Focus on the main page, as a reader's would be, outside every text field.
  await browser.evaluate(`document.getElementById("preview-pane").focus(), true`);
  const shown = await read();
  checkShown("at load", shown);
  const paneWidth = shown.pane.width;

  phase("a row under the strip");
  await browser.evaluate(`document.getElementById("index-progress").hidden = false, true`);
  await browser.waitFor(
    `(() => {
       const strip = document.getElementById("nav-shortcut-hints").getBoundingClientRect();
       const button = document.getElementById("nav-collapse-toggle").getBoundingClientRect();
       return Math.abs(button.top + button.height / 2 - (strip.top + 1 + (strip.height - 1) / 2)) <= 0.5;
     })()`,
    STEP_MS,
  );
  checkChevron("with the scan's progress showing under the strip", await read());
  await browser.evaluate(`document.getElementById("index-progress").hidden = true, true`);

  phase("focus ring");
  // A key first, as a reader's would be: focus a script moves then shows its ring.
  await shift("keyDown");
  await shift("keyUp");
  const ring = await browser.evaluate(RING_PROBE);
  const painted = await pixel(ring.x, ring.y);
  check(
    "the main page's focus ring paints over a band with a ground of its own",
    ring.focusVisible &&
      ring.color.length === 3 &&
      painted.every((value, index) => Math.abs(value - ring.color[index]) <= 8),
    JSON.stringify({ ring, painted }),
  );
  await browser.evaluate(`document.getElementById("ring-probe").remove(), true`);

  phase("shift badges the chevron");
  await shift("keyDown");
  await browser.waitFor(
    `[...document.querySelectorAll(".preview-frame > .kbd-badge")].some(
       (each) => each.textContent === "\\\\")`,
    STEP_MS,
  );
  check(
    "holding Shift: the chevron's badge is painted over it",
    await browser.evaluate(BADGE_ON_TOP),
  );
  await shift("keyUp");

  phase("backslash hides");
  const hiding = await sampled(() => pressBackslash(false));
  const hidden = await read();
  checkHidden("after \\", hidden);
  checkSlide("hiding", hiding, paneWidth, 0, hidden.window, true);

  phase("shift-backslash shows");
  const showing = await sampled(() => pressBackslash(true));
  const back = await read();
  checkShown("after Shift-\\", back);
  checkSlide("showing", showing, 0, paneWidth, hidden.window, false);
  check(
    "after Shift-\\: the page is its own width beside the pane again",
    Math.abs(back.frame.width - (back.window - back.pane.width)) <= 1,
    JSON.stringify(back),
  );

  phase("click hides");
  const center = {
    x: back.button.left + back.button.width / 2,
    y: back.button.top + back.button.height / 2,
  };
  for (const type of ["mousePressed", "mouseReleased"]) {
    await browser.send("Input.dispatchMouseEvent", {
      type,
      ...center,
      button: "left",
      clickCount: 1,
    });
  }
  await browser.waitFor(
    `document.querySelector(".preview-frame").getAnimations().length === 0 &&
     document.querySelector(".preview-frame").getBoundingClientRect().left === 0`,
    STEP_MS,
  );
  // The pointer leaves the chevron, so it is at rest, without the hover surface.
  await browser.send("Input.dispatchMouseEvent", { type: "mouseMoved", x: 640, y: 400 });
  await browser.waitFor(
    `document.getElementById("nav-collapse-toggle").getAnimations().length === 0`,
    STEP_MS,
  );
  checkHidden("after a click on the chevron", await read());

  phase("reduced motion");
  await browser.send("Emulation.setEmulatedMedia", {
    features: [{ name: "prefers-reduced-motion", value: "reduce" }],
  });
  await pressBackslash(false);
  const instant = await read();
  check(
    "under reduced motion: \\ shows the pane at once, with no animation",
    !instant.collapsed &&
      instant.animations === 0 &&
      Math.abs(instant.frame.left - instant.pane.right) <= 1,
    JSON.stringify(instant),
  );
} finally {
  await browser.close();
}

if (failures.length > 0) {
  console.error(failures.slice(0, 20).join("\n"));
  process.exitCode = 1;
} else {
  console.log(`nav collapse in Chrome: ${checks} checks passed`);
}

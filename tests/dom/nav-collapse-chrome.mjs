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
// - the chevron sits on the main page's left edge, right of the pane's border, centered on
//   the shortcut strip's row, pointing left at the pane;
// - a real `\`, sent through the DevTools input domain, slides the frame from the pane's
//   edge to the window's in every frame without moving back, at its full width throughout,
//   and leaves the pane covered and inert and the chevron pointing right, on the same row;
// - a real Shift-\, which types `|`, slides it back and gives the pane its place again;
// - a click on the chevron does what `\` does; and
// - under reduced motion the page moves at once, with no animation.
//
// Each step writes `phase <name> <ms since start>` to stderr, so a slow run says where.
import { launchChrome } from "./chrome-session.mjs";

const [base] = process.argv.slice(2);
if (!base || !process.env.CHROME_BIN || !process.env.CHROME_PROFILES) {
  throw new Error("usage: CHROME_BIN CHROME_PROFILES nav-collapse-chrome.mjs <base URL>");
}
const started = Date.now();
const phase = (name) => process.stderr.write(`phase ${name} ${Date.now() - started}\n`);
// Layout places boxes in a 64th of a pixel; under half a pixel is not a different place.
const TOLERANCE_PX = 0.5;
// How long a slide is sampled: SLIDE_MS in static/nav-collapse.js, with room for frames a
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

// In the page: where the pane, the frame, the strip, and the chevron are, and their states.
const READ = `(() => {
  const pane = document.getElementById("tree-pane");
  const frame = document.querySelector(".preview-frame");
  const strip = document.getElementById("nav-shortcut-hints");
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
    strip: box(strip),
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
  };
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

/** Run an action while sampling every frame, and return the samples once the slide ends. */
async function sampled(action) {
  await browser.evaluate(SAMPLE);
  await action();
  await browser.waitFor("window.navSampling === false", STEP_MS);
  return browser.evaluate("window.navSamples");
}

const read = () => browser.evaluate(READ);

/** The checks every resting state shares: the chevron on the strip's row, beside the pane. */
function checkChevron(where, at) {
  const stripCenter = at.strip.top + at.strip.height / 2;
  const buttonCenter = at.button.top + at.button.height / 2;
  check(
    `${where}: the chevron is centered on the shortcut strip's row`,
    Math.abs(stripCenter - buttonCenter) <= 1,
    JSON.stringify({ stripCenter, buttonCenter }),
  );
  check(
    `${where}: the chevron sits just inside the main page's left edge`,
    at.button.left >= at.frame.left + 2 - TOLERANCE_PX && at.button.left <= at.frame.left + 8,
    JSON.stringify({ button: at.button.left, frame: at.frame.left }),
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
  phase("load");
  await browser.send("Page.enable");
  await browser.send("Page.navigate", { url: `${base}/view/` });
  await browser.waitFor(
    `document.documentElement?.dataset.shellToolsReady === "true" &&
     document.getElementById("nav-shortcut-hints")?.hidden === false`,
    STEP_MS,
  );
  // Focus on the main page, as a reader's would be, outside every text field.
  await browser.evaluate(`document.getElementById("preview-pane").focus(), true`);
  const shown = await read();
  checkShown("at load", shown);
  const paneWidth = shown.pane.width;

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

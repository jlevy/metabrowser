// The shortcut strip at the foot of the navigation pane, laid out by headless Chrome against
// a live `metab` server.
//
//   CHROME_BIN=/path/to/chrome CHROME_PROFILES=/dir/the/caller/removes \
//     node tests/dom/shortcut-strip-chrome.mjs <server base URL>
//
// tests/test_shortcut_strip_chrome.py serves a plain folder, owns the profile directory, and
// runs this in a process group of its own, which Chrome joins.
//
// The owner asked for the strip to lead with Shift, Reveal keys, ahead of `?` for Help, and
// for it to stay one row: where its items do not all fit, it drops them from the end, Quick
// Search first, then Help, and Shift always shows (mb-k8am). Which items show at a width is
// layout, which only a browser computes; keyboard-help.js (`keepStripOnOneRow`) measures it,
// and tests/dom/shortcut-strip-session.js runs that code browserlessly on injected widths. Here,
// at every pane width from the 180px minimum to the 300px default, in both interface font
// sets, the strip is held to the rule, judged from widths read here rather than from the
// production arithmetic:
//
// - Shift shows, first, and what shows is a prefix of Shift, Help, and Quick Search: the
//   longest whose widths and gaps fit the strip's content box, so an item drops only when
//   it must;
// - every item shown lies inside the content box, on one line, and a dropped one is not
//   drawn, so it is out of the tab order;
// - the strip is one row: as tall as the server's hidden slot that holds its place before
//   the shell's tools load.
//
// A font set changed in a pane that has dropped items measures them again, shown: at
// 190px the system font set shows Shift alone, and the default one, switched to
// there, shows Shift and Help (review A1 on #544). At the narrowest pane, holding Shift
// shows the revealed layer over the panel above the strip, listing Help and Quick Search,
// which the resting strip dropped there.
//
// Each step writes `phase <name> <ms since start>` to stderr, so a slow run says where.
import { launchChrome } from "./chrome-session.mjs";

const [base] = process.argv.slice(2);
if (!base || !process.env.CHROME_BIN || !process.env.CHROME_PROFILES) {
  throw new Error("usage: CHROME_BIN CHROME_PROFILES shortcut-strip-chrome.mjs <base URL>");
}
const started = Date.now();
const phase = (name) => process.stderr.write(`phase ${name} ${Date.now() - started}\n`);
// The pane's 180px minimum (initPaneResize in static/app.js and `.tree-pane` in
// static/styles.css), and the default, `--tree-pane-width`.
const NARROWEST = 180;
const DEFAULT = 300;
// A pane where the system font set shows Shift alone and the default one Shift and Help
// (Chrome 152 on macOS: Help shows from 198px in the one and 181px in the other).
const FONT_SWITCH_PX = 190;
// Wide enough that every item shows in either font set, to read their widths.
const WIDE = 420;
// The strip's items, in their order, by label.
const ORDER = ["Reveal keys", "Help", "Quick Search"];
// Layout places boxes in a 64th of a pixel; under half a pixel is not a different place.
const TOLERANCE_PX = 0.5;
// Whether the items fit is exact: their widths are read in layout's unit, so their sum is.
const FIT_EPSILON_PX = 0.001;
// The reveal's hold, REVEAL_HOLD_MS in static/key-reveal.js, with room for a frame.
const HOLD_MS = 400;
const STEP_MS = 30000;

let checks = 0;
const failures = [];
const check = (label, ok, detail = "") => {
  checks += 1;
  if (!ok) {
    failures.push(`${label}${detail ? `: ${detail}` : ""}`);
  }
};

// In the page: set the pane's width and font set, let the strip's observer run (it runs in
// the rendering step after layout, so a frame and a task after it), and read the strip.
const READ = `async ({ width, font, reserve }) => {
  const root = document.documentElement;
  if (font === "system") {
    root.dataset.appFont = "system";
  } else {
    delete root.dataset.appFont;
  }
  const pane = document.querySelector(".tree-pane");
  pane.style.width = width + "px";
  await new Promise((resolve) => requestAnimationFrame(() => setTimeout(resolve, 0)));
  const host = document.getElementById("nav-shortcut-hints");
  const style = getComputedStyle(host);
  const px = (value) => parseFloat(value) || 0;
  const box = host.getBoundingClientRect();
  const left = box.left + px(style.borderLeftWidth) + px(style.paddingLeft);
  const right = box.right - px(style.borderRightWidth) - px(style.paddingRight);
  const items = [...host.children]
    .filter((child) => !child.classList.contains("nav-shortcut-reveal"))
    .map((item) => {
      const rect = item.getBoundingClientRect();
      return {
        label: item.querySelector(".nav-shortcut-label")?.textContent ?? "",
        drawn: getComputedStyle(item).display !== "none",
        hidden: item.hidden,
        left: rect.left,
        right: rect.right,
        top: rect.top,
        width: rect.width,
      };
    });
  let reserved = null;
  if (reserve) {
    // The slot the server ships, hidden and empty of nothing but its height rule.
    host.hidden = true;
    reserved = host.getBoundingClientRect().height;
    host.hidden = false;
  }
  return {
    pane: pane.getBoundingClientRect().width,
    available: right - left,
    left,
    right,
    gap: px(style.columnGap),
    height: box.height,
    reserved,
    items,
  };
}`;

const browser = await launchChrome(process.env.CHROME_BIN, {
  profiles: process.env.CHROME_PROFILES,
  width: 1280,
  height: 800,
});
/** @type {Record<string, Array<[number, string]>>} */
const summary = {};
try {
  phase("load");
  await browser.send("Page.enable");
  await browser.send("Page.navigate", { url: `${base}/view/` });
  // While the navigation replaces the document, `documentElement` can be null
  // for a poll: read every step of the readiness check null-safely.
  await browser.waitFor(
    `document.documentElement?.dataset.shellToolsReady === "true" &&
     document.getElementById("nav-shortcut-hints")?.hidden === false`,
    STEP_MS,
  );
  const read = (spec) => browser.evaluate(`(${READ})(${JSON.stringify(spec)})`);

  for (const font of ["clean", "system"]) {
    phase(`sweep ${font}`);
    const wide = await read({ width: WIDE, font, reserve: false });
    check(
      `${font}: every item shows in a ${WIDE}px pane, Shift first`,
      JSON.stringify(wide.items.map((item) => [item.label, item.drawn])) ===
        JSON.stringify(ORDER.map((label) => [label, true])),
      JSON.stringify(wide.items.map((item) => [item.label, item.drawn])),
    );
    const widths = new Map(wide.items.map((item) => [item.label, item.width]));
    summary[font] = [];
    let previous = null;
    for (let width = NARROWEST; width <= DEFAULT; width += 1) {
      const at = await read({ width, font, reserve: width % 20 === 0 || width === NARROWEST });
      const where = `${font}, ${width}px pane`;
      check(`${where}: the pane is that wide`, Math.abs(at.pane - width) < TOLERANCE_PX, at.pane);
      // The longest prefix whose widths and gaps fit the content box; Shift whatever.
      let expected = 1;
      for (let count = ORDER.length; count > 1; count -= 1) {
        const total =
          ORDER.slice(0, count).reduce((sum, label) => sum + widths.get(label), 0) +
          at.gap * (count - 1);
        if (total <= at.available + FIT_EPSILON_PX) {
          expected = count;
          break;
        }
      }
      const drawn = at.items.filter((item) => item.drawn).map((item) => item.label);
      check(
        `${where}: shows ${ORDER.slice(0, expected).join(", ")}`,
        JSON.stringify(drawn) === JSON.stringify(ORDER.slice(0, expected)),
        JSON.stringify({ drawn, available: at.available, widths: Object.fromEntries(widths) }),
      );
      check(
        `${where}: an item is drawn exactly when it is not hidden`,
        at.items.every((item) => item.drawn === !item.hidden),
        JSON.stringify(at.items),
      );
      const shown = at.items.filter((item) => item.drawn);
      check(
        `${where}: every item shown lies inside the strip, on one line`,
        shown.every(
          (item) =>
            item.left >= at.left - TOLERANCE_PX &&
            item.right <= at.right + TOLERANCE_PX &&
            Math.abs(item.top - shown[0].top) < TOLERANCE_PX,
        ),
        JSON.stringify({ left: at.left, right: at.right, shown }),
      );
      check(
        `${where}: the strip is one row, as tall at every width`,
        previous === null || Math.abs(at.height - previous) < TOLERANCE_PX,
        JSON.stringify({ height: at.height, previous }),
      );
      previous ??= at.height;
      if (at.reserved !== null) {
        check(
          `${where}: the strip is as tall as the hidden slot the server ships`,
          Math.abs(at.height - at.reserved) < TOLERANCE_PX,
          JSON.stringify({ height: at.height, reserved: at.reserved }),
        );
      }
      const last = summary[font].at(-1);
      if (!last || last[1] !== drawn.join(" + ")) {
        summary[font].push([width, drawn.join(" + ")]);
      }
    }
  }

  // A font set changed where items are dropped: the default set's widths, read in the wide pane,
  // decide what it shows once it is drawn there.
  phase("font switch");
  const clean = await read({ width: WIDE, font: "clean", reserve: false });
  const cleanWidths = new Map(clean.items.map((item) => [item.label, item.width]));
  const system = await read({ width: FONT_SWITCH_PX, font: "system", reserve: false });
  const switched = await read({ width: FONT_SWITCH_PX, font: "clean", reserve: false });
  const fits = (count) =>
    ORDER.slice(0, count).reduce((sum, label) => sum + cleanWidths.get(label), 0) +
      switched.gap * (count - 1) <=
    switched.available + FIT_EPSILON_PX;
  const expectedSwitched = ORDER.filter((_label, index) => index === 0 || fits(index + 1));
  const drawnBy = (at) => at.items.filter((item) => item.drawn).map((item) => item.label);
  check(
    `the system font set at ${FONT_SWITCH_PX}px shows Shift alone`,
    JSON.stringify(drawnBy(system)) === JSON.stringify(ORDER.slice(0, 1)),
    JSON.stringify(drawnBy(system)),
  );
  check(
    `switched to the default font set at ${FONT_SWITCH_PX}px, the strip measures again and shows ${expectedSwitched.join(", ")}`,
    JSON.stringify(drawnBy(switched)) === JSON.stringify(expectedSwitched) &&
      expectedSwitched.length === 2,
    JSON.stringify({ drawn: drawnBy(switched), expected: expectedSwitched }),
  );

  // The narrowest pane, the default font set: hold Shift, and the revealed layer lists
  // what the resting strip dropped, over the panel above it.
  phase("reveal");
  await read({ width: NARROWEST, font: "clean", reserve: false });
  await browser.evaluate(`document.activeElement?.blur?.(), true`);
  const shift = { key: "Shift", code: "ShiftLeft", windowsVirtualKeyCode: 16 };
  await browser.send("Input.dispatchKeyEvent", { type: "keyDown", modifiers: 8, ...shift });
  await new Promise((resolve) => setTimeout(resolve, HOLD_MS));
  const revealed = await browser.evaluate(`(() => {
    const host = document.getElementById("nav-shortcut-hints");
    const layer = host.querySelector(".nav-shortcut-reveal");
    if (!layer) {
      return null;
    }
    const strip = host.getBoundingClientRect();
    const box = layer.getBoundingClientRect();
    const above = document.elementFromPoint(box.left + 20, box.top + 4);
    return {
      labels: [...layer.querySelectorAll(".nav-shortcut-label")].map((label) => label.textContent),
      above: Boolean(above && layer.contains(above)) || above === layer,
      overlaps: box.top < strip.top - 1,
    };
  })()`);
  await browser.send("Input.dispatchKeyEvent", { type: "keyUp", modifiers: 0, ...shift });
  check(
    "holding Shift in the narrowest pane lists Help and Quick Search on the revealed layer",
    Boolean(revealed?.labels.includes("Help") && revealed.labels.includes("Quick Search")),
    JSON.stringify(revealed),
  );
  check(
    "the revealed layer is drawn over the panel above the strip, not cut at the strip's top",
    Boolean(revealed?.overlaps && revealed.above),
    JSON.stringify(revealed),
  );
} finally {
  await browser.close();
}

process.stderr.write(`widths ${JSON.stringify(summary)}\n`);
if (failures.length > 0) {
  console.error(failures.slice(0, 20).join("\n"));
  process.exitCode = 1;
} else {
  console.log(`shortcut strip in Chrome: ${checks} checks passed`);
}

// A rendered document's print button in headless Chrome against a live `metab`
// (docs/design-system.md, "Print").
//
// Usage: node document-print-chrome.mjs METAB ROOT PORT STATE_DIR, with CHROME_BIN set, and
// CHROME_PROFILES naming where Chrome's profile goes (tests/dom/chrome-session.mjs).
// tests/test_document_print_chrome.py writes ROOT, a folder whose README is long enough for
// KPress's table of contents and whose note opens with a paragraph, owns the profile
// directory, and runs this in a process group of its own, which Chrome and the servers join,
// stopped however the session ends.
//
// The folder is served trusted and `--untrusted`, whose inert render is the page's own.
// Under each, at windows whose pane is in KPress's narrow band (1100 px, the card band's
// narrowest pane here, and 1280 px), its wide band (1920 px), and its phone band (900 px),
// it opens the README and the note as files, and the folder's Overview, whose README is the
// document, and checks:
//
// - the header has no print button, and in the card bands the document's card has one, in
//   the card's top and trailing padding, centred in its corner, the icon button's size;
// - nothing in the view moves when the button is taken out of the card and put back;
// - in the narrow band, where the floating table of contents toggle shows with the button
//   still on screen, the two are apart, and in the wide band the rail is beside the card;
// - a click prints once (the page's `beforeprint`), and the pointer shows its tooltip;
// - Command-P and Control-P reach the page and nothing in it takes them from the browser;
// - in print, the button is hidden and the document is what prints;
// - in the phone band, where KPress draws no card, there is no button.
//
// Each step writes `phase <name> <ms since start>` to stderr. It prints
// `document print in Chrome: <n> checks passed`, or the failures and exits 1.
import { spawn } from "node:child_process";
import path from "node:path";
import { launchChrome } from "./chrome-session.mjs";

const [metab, root, port, state] = process.argv.slice(2);
if (!metab || !root || !port || !state || !process.env.CHROME_BIN) {
  throw new Error(
    "usage: CHROME_BIN CHROME_PROFILES document-print-chrome.mjs METAB ROOT PORT STATE",
  );
}
const base = `http://127.0.0.1:${port}`;
const started = Date.now();
const phase = (name) => process.stderr.write(`phase ${name} ${Date.now() - started}\n`);
// Window widths beside the default navigation pane: the pane at 36.8 rem (phone band, no
// card), 49.3 rem and 60.6 rem (narrow band, the card drawn), and 100.6 rem (wide band).
const WIDTHS = [
  { width: 1100, band: "narrow" },
  { width: 1280, band: "narrow" },
  { width: 1920, band: "wide" },
  { width: 900, band: "phone" },
];
const HEIGHT = 900;
// KPress's toggle threshold (toc.js), which builtin_plugins/markdown/toc-toggle.js follows.
const THRESHOLD = 100;
// Lengths are fractional; a difference under half a pixel is not a different place.
const TOLERANCE_PX = 0.5;
// The least room between the button and the toggle beside it.
const MIN_GAP_PX = 8;

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

// The view the reader sees: the shell lays a page out in a hidden stage and moves it into
// the pane once its faces have loaded, so every read is of the committed pane, its active
// tab naming the view shown (as tests/dom/folder-overview-alignment-chrome.mjs reads it).
const COMMITTED = `(() => {
  const pane = document.querySelector(".preview-pane");
  if (!pane || pane.querySelector(":scope > .preview-file-stage")) {
    return null;
  }
  const tab = pane.querySelector(":scope > .tab-bar > .tab-btn.active");
  const view = pane.querySelector(':scope > [data-active-view="true"]');
  return tab && view && tab.dataset.tab === view.dataset.tabContent ? { pane, tab, view } : null;
})()`;

// The shown document's mount: the file's Document view itself, or the Overview's README
// panel body.
const HOST = `(() => {
  const view = ${COMMITTED}.view;
  return view.matches(".metabrowser-markdown-document")
    ? view
    : view.querySelector(".metabrowser-markdown-document");
})()`;
// The shown document's card.
const CARD = `${HOST}.querySelector(":scope > article.kpress > .kpress-doc-layout > .kpress-long-text")`;

// The document's parts, in client coordinates: the card's border box and the text's box
// inside its padding, the button, the toggle, and the rail.
const PARTS = `(() => {
  const shown = ${COMMITTED};
  const host = ${HOST};
  const card = host.querySelector(":scope > article.kpress > .kpress-doc-layout > .kpress-long-text");
  const style = getComputedStyle(card);
  const box = card.getBoundingClientRect();
  const px = (value) => Number.parseFloat(value);
  const rect = (element) => {
    if (!element) {
      return null;
    }
    const r = element.getBoundingClientRect();
    return { left: r.left, top: r.top, right: r.right, bottom: r.bottom, width: r.width, height: r.height };
  };
  const button = card.querySelector(":scope > .metabrowser-print-indicator");
  const toggle = host.querySelector(".kpress-toc-toggle");
  const rail = host.querySelector(".kpress-toc");
  const pane = shown.pane;
  return {
    paneTop: pane.getBoundingClientRect().top,
    paneRem: pane.clientWidth / px(getComputedStyle(document.documentElement).fontSize),
    scrollTop: pane.scrollTop,
    headerPrint: document.querySelectorAll(".file-header-print, .file-header .metabrowser-print-indicator").length,
    cardDrawn: getComputedStyle(card).boxShadow !== "none",
    card: rect(card),
    inner: {
      left: box.left + px(style.borderLeftWidth),
      top: box.top + px(style.borderTopWidth),
      right: box.right - px(style.borderRightWidth),
    },
    text: {
      left: box.left + px(style.borderLeftWidth) + px(style.paddingLeft),
      top: box.top + px(style.borderTopWidth) + px(style.paddingTop),
      right: box.right - px(style.borderRightWidth) - px(style.paddingRight),
    },
    buttons: card.querySelectorAll(".metabrowser-print-indicator").length,
    button: button && { ...rect(button), display: getComputedStyle(button).display, last: card.lastElementChild === button },
    iconSize: px(getComputedStyle(document.documentElement).getPropertyValue("--icon-btn-size")),
    toggle: toggle && { ...rect(toggle), display: getComputedStyle(toggle).display, shown: toggle.classList.contains("show-toggle"), opacity: getComputedStyle(toggle).opacity },
    rail: rail && { ...rect(rail), position: getComputedStyle(rail).position },
  };
})()`;

// Every box in the shown view but the button's, and how far the pane scrolls: with the
// button in the card, after it is taken out, and once it is back. Synchronous, so nothing
// else lays the page out in between.
const STILL = `(() => {
  const shown = ${COMMITTED};
  const card = ${CARD};
  const button = card.querySelector(":scope > .metabrowser-print-indicator");
  const boxes = () => {
    const all = [shown.view, ...shown.view.querySelectorAll("*")].filter((element) => !button.contains(element));
    return JSON.stringify([shown.pane.scrollHeight, ...all.map((element) => {
      const r = element.getBoundingClientRect();
      return [r.left, r.top, r.width, r.height];
    })]);
  };
  const with_ = boxes();
  button.remove();
  const without = boxes();
  card.append(button);
  const back = boxes();
  return { count: JSON.parse(with_).length - 1, same: with_ === without && without === back };
})()`;

/** Open *address* and wait for the committed view's document and its fonts. */
async function open(page, address, overview) {
  await page.send("Page.navigate", { url: `${base}${address}` });
  await page.waitFor(`!!${COMMITTED} && !!${CARD}?.querySelector(":scope > p")`, 20000);
  if (overview) {
    // File Overview's type breakdown waits for the rollup, and moves the README down when
    // it lands; the README's place is read after it.
    await page.waitFor(
      `!!${COMMITTED}?.view.querySelector(".file-type-summary-details-toggle")`,
      20000,
    );
  }
  await page.evaluate("document.fonts.ready.then(() => true)");
  await page.evaluate(
    "new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)))",
  );
  return page.evaluate(PARTS);
}

/** Scroll the pane to *scrollTop*, and read once a toggle's fade has ended. */
async function scrollTo(page, scrollTop) {
  await page.evaluate(`document.querySelector(".preview-pane").scrollTop = ${scrollTop}`);
  await page.evaluate(
    "new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)))",
  );
  const read = await page.evaluate(PARTS);
  if (read.toggle && read.toggle.display !== "none") {
    await page.waitFor(
      `getComputedStyle(${HOST}.querySelector(".kpress-toc-toggle")).opacity === "${read.toggle.shown ? "1" : "0"}"`,
      5000,
    );
    return page.evaluate(PARTS);
  }
  return read;
}

const apart = (a, b) =>
  a.right + MIN_GAP_PX <= b.left ||
  b.right + MIN_GAP_PX <= a.left ||
  a.bottom + MIN_GAP_PX <= b.top ||
  b.bottom + MIN_GAP_PX <= a.top;

/** The checks of one page at one width. */
async function checkPage(page, label, address, band, overview) {
  const parts = await open(page, address, overview);
  check(`${label}: the header has no print button`, parts.headerPrint === 0, parts.headerPrint);
  if (band === "phone") {
    check(`${label}: no card is drawn`, !parts.cardDrawn, parts);
    check(
      `${label}: the button is not shown without the card`,
      parts.buttons === 1 && parts.button.display === "none",
      parts.button,
    );
    return;
  }
  const { button, inner, text } = parts;
  check(`${label}: the card is drawn`, parts.cardDrawn, parts);
  check(
    `${label}: one button, shown, last in the card`,
    parts.buttons === 1 && button.display !== "none" && button.last,
    parts,
  );
  check(
    `${label}: the button is the icon button's size`,
    Math.abs(button.width - parts.iconSize) <= TOLERANCE_PX &&
      Math.abs(button.height - parts.iconSize) <= TOLERANCE_PX,
    button,
  );
  check(
    `${label}: the button is in the card's top padding, above the text`,
    button.top >= inner.top - TOLERANCE_PX && button.bottom <= text.top + TOLERANCE_PX,
    { button, inner, text },
  );
  check(
    `${label}: the button is in the card's trailing padding, past the text`,
    button.left >= text.right - TOLERANCE_PX && button.right <= inner.right + TOLERANCE_PX,
    { button, inner, text },
  );
  check(
    `${label}: the button is centred in the card's corner`,
    Math.abs(button.top - inner.top - (inner.right - button.right)) <= TOLERANCE_PX,
    { button, inner },
  );
  const still = await page.evaluate(STILL);
  check(`${label}: nothing moves when the button arrives`, still.same && still.count > 3, still);
  // The button is shown on a card KPress draws: a render without the card's mark has none.
  const unmarked = await page.evaluate(`(() => {
    const article = ${HOST}.querySelector(":scope > article.kpress");
    article.removeAttribute("data-kpress-card");
    const display = getComputedStyle(${CARD}.querySelector(":scope > .metabrowser-print-indicator")).display;
    article.setAttribute("data-kpress-card", "on");
    return display;
  })()`);
  check(`${label}: a render without the card has no button shown`, unmarked === "none", unmarked);

  if (band === "narrow" && parts.toggle) {
    // Where the toggle shows with the button still on screen: just past the threshold in a
    // file, and just past the README's beginning on the Overview.
    const documentTop = parts.card.top - parts.paneTop + parts.scrollTop;
    const scrollTop = overview ? Math.ceil(documentTop) + 5 : THRESHOLD + 5;
    const read = await scrollTo(page, scrollTop);
    const visible = read.button.bottom > read.paneTop;
    check(
      `${label}: the toggle shows with the button on screen`,
      read.toggle.shown && read.toggle.opacity === "1" && visible,
      { button: read.button, toggle: read.toggle, paneTop: read.paneTop, scrollTop },
    );
    check(`${label}: the toggle and the button are apart`, apart(read.button, read.toggle), {
      button: read.button,
      toggle: read.toggle,
    });
    await scrollTo(page, 0);
  }
  if (band === "wide" && parts.rail) {
    check(
      `${label}: the rail is beside the card, apart from the button`,
      parts.toggle?.display === "none" &&
        parts.rail.left >= parts.card.right - TOLERANCE_PX &&
        apart(button, parts.rail),
      { button, rail: parts.rail, toggle: parts.toggle },
    );
  }

  // The pointer over the button shows its tooltip, and a click prints, once.
  await page.evaluate(
    `window.__prints = 0; addEventListener("beforeprint", () => { window.__prints += 1; }); true`,
  );
  const at = await page.evaluate(`(() => {
    const r = ${CARD}.querySelector(":scope > .metabrowser-print-indicator").getBoundingClientRect();
    return { x: r.left + r.width / 2, y: r.top + r.height / 2 };
  })()`);
  await page.send("Input.dispatchMouseEvent", { type: "mouseMoved", x: at.x, y: at.y });
  await page.waitFor(
    `(() => { const tip = document.querySelector(".custom-tooltip.visible"); return !!tip && tip.textContent === "Print document"; })()`,
    5000,
  );
  for (const type of ["mousePressed", "mouseReleased"]) {
    await page.send("Input.dispatchMouseEvent", {
      type,
      x: at.x,
      y: at.y,
      button: "left",
      clickCount: 1,
    });
  }
  await page.waitFor("window.__prints >= 1", 5000);
  await new Promise((resolve) => setTimeout(resolve, 200));
  const prints = await page.evaluate("window.__prints");
  check(`${label}: a click prints once`, prints === 1, prints);
}

/** Command-P and Control-P reach the page, and nothing in it takes them from the browser. */
async function checkPrintKeys(page, label) {
  await page.evaluate(
    `window.__keys = []; addEventListener("keydown", (event) => window.__keys.push(event), true); true`,
  );
  // Command is modifier 4 and Control 2 in the protocol's input domain.
  for (const modifiers of [4, 2]) {
    for (const type of ["rawKeyDown", "keyUp"]) {
      await page.send("Input.dispatchKeyEvent", {
        type,
        key: "p",
        code: "KeyP",
        windowsVirtualKeyCode: 80,
        modifiers,
      });
    }
  }
  const keys = await page.evaluate(
    "window.__keys.map((event) => ({ key: event.key, meta: event.metaKey, ctrl: event.ctrlKey, prevented: event.defaultPrevented }))",
  );
  check(
    `${label}: Command-P and Control-P reach the page and are left to the browser`,
    keys.length === 2 &&
      keys[0].meta &&
      keys[1].ctrl &&
      keys.every((key) => key.key === "p" && !key.prevented),
    keys,
  );
}

/** In print, the document prints and the button and the shell's chrome do not. */
async function checkPrintMedia(page, label) {
  await page.send("Emulation.setEmulatedMedia", { media: "print" });
  const printed = await page.evaluate(`(() => {
    const shown = ${COMMITTED};
    const card = ${CARD};
    return {
      button: getComputedStyle(card.querySelector(".metabrowser-print-indicator")).display,
      header: getComputedStyle(document.querySelector(".file-header")).display,
      view: getComputedStyle(shown.view).display,
      card: card.getBoundingClientRect().height,
      printable: shown.pane.dataset.printable,
    };
  })()`);
  await page.send("Emulation.setEmulatedMedia", { media: "" });
  check(
    `${label}: in print the document prints, without the button or the header`,
    printed.button === "none" &&
      printed.header === "none" &&
      printed.view !== "none" &&
      printed.card > 0 &&
      printed.printable === "true",
    printed,
  );
}

async function checkProfile(profile) {
  const page = await launchChrome(process.env.CHROME_BIN, {
    profiles: process.env.CHROME_PROFILES,
    width: WIDTHS[0].width,
    height: HEIGHT,
  });
  try {
    await page.send("Page.enable");
    for (const { width, band } of WIDTHS) {
      await page.send("Emulation.setDeviceMetricsOverride", {
        width,
        height: HEIGHT,
        deviceScaleFactor: 1,
        mobile: false,
      });
      for (const [name, address, overview] of [
        ["README", "/view/README.md", false],
        ["note", "/view/note.md", false],
        ["Overview", "/view/", true],
      ]) {
        await checkPage(page, `${profile} ${width} ${name}`, address, band, overview);
      }
      phase(`${profile} ${width}`);
    }
    await open(page, "/view/README.md", false);
    await checkPrintKeys(page, `${profile} README`);
    await checkPrintMedia(page, `${profile} README`);
    await open(page, "/view/", true);
    await checkPrintMedia(page, `${profile} Overview`);
  } finally {
    await page.close();
  }
  phase(`${profile} keys and print`);
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
process.stdout.write(`document print in Chrome: ${checks} checks passed\n`);

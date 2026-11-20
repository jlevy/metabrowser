// A README laid out with the HTML attributes github.com keeps, drawn in headless Chrome
// against a live `metab`, trusted and `--untrusted`, as github.com draws it.
//
// Usage: node markdown-github-layout-chrome.mjs METAB ROOT PORT STATE_DIR, with CHROME_BIN
// set, and CHROME_PROFILES naming where Chrome's profile goes (tests/dom/chrome-session.mjs).
// tests/test_markdown_github_layout_chrome.py copies tests/fixtures/github-layout to ROOT:
// a README of those layouts and the 512-pixel square image they show. It owns the profile
// directory and runs this in a process group of its own, which Chrome and the servers
// join, stopped however the session ends.
//
// Under each profile it checks, in the document as the reader sees it:
//
// - Metabrowser's own README opening, `<p align="center"><img width="192">` and
//   `<h1 align="center">`: the image is 192 pixels square and centered over a centered
//   title (the allowlist of an untrusted render dropped both attributes, which drew it at
//   512 pixels against the left edge);
// - an image sized by its `height` alone, its `width` alone, or both, takes those sizes,
//   as github.com sets no rule over them (KPress's `height: auto` overrode a `height`);
// - an image floated by `align="right"` or `align="left"` is that wide, against its edge,
//   with github.com's 20 pixels of room outside its width;
// - a table cell takes its own `align`, or its row's, over KPress's own alignment, and a
//   cell with neither keeps KPress's;
// - a `<div align="right">` sets its text against its right edge.
//
// Each step writes `phase <name> <ms since start>` to stderr. It prints
// `markdown github layout in Chrome: <n> checks passed`, or the failures and exits 1.
import { spawn } from "node:child_process";
import path from "node:path";
import { launchChrome } from "./chrome-session.mjs";

const [metab, root, port, state] = process.argv.slice(2);
if (!metab || !root || !port || !state || !process.env.CHROME_BIN) {
  throw new Error(
    "usage: CHROME_BIN CHROME_PROFILES markdown-github-layout-chrome.mjs METAB ROOT PORT STATE",
  );
}
const base = `http://127.0.0.1:${port}`;
const started = Date.now();
const phase = (name) => process.stderr.write(`phase ${name} ${Date.now() - started}\n`);

const failures = [];
let checks = 0;
const check = (label, ok, detail = "") => {
  checks += 1;
  if (!ok) {
    const failure = `${label}${detail === "" ? "" : `: ${JSON.stringify(detail)}`}`;
    failures.push(failure);
    process.stderr.write(`failed ${failure}\n`);
  }
};
// A box's edge is a whole pixel at most from where it belongs: layout rounds to a
// fraction of a pixel, and a centered box of odd width sits half a pixel off.
const near = (a, b) => Math.abs(a - b) <= 1;

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
const PROSE = `${VIEW}?.querySelector(".kpress-prose")`;
// Drawn: all seven of the document's images loaded.
const DRAWN = `(() => {
  const images = [...(${PROSE}?.querySelectorAll("img") ?? [])];
  return images.length === 7 && images.every((image) => image.complete && image.naturalWidth > 0);
})()`;

// What the checks read: each image by its alt text, each table cell by its text, the
// title, and the right-aligned block, as boxes and the styles that place them.
const MEASURE = `(() => {
  const prose = ${PROSE};
  const box = (element) => {
    const rect = element.getBoundingClientRect();
    return { left: rect.left, right: rect.right, width: rect.width, height: rect.height };
  };
  // Where a child is laid out: inside the padding and border.
  const contentBox = (element) => {
    const rect = element.getBoundingClientRect();
    const style = getComputedStyle(element);
    const left = rect.left + parseFloat(style.borderLeftWidth) + parseFloat(style.paddingLeft);
    const right = rect.right - parseFloat(style.borderRightWidth) - parseFloat(style.paddingRight);
    return { left, right, width: right - left };
  };
  const textBox = (element) => {
    const range = document.createRange();
    range.selectNodeContents(element);
    return box(range);
  };
  const images = {};
  for (const image of prose.querySelectorAll("img")) {
    const style = getComputedStyle(image);
    images[image.alt] = {
      ...box(image),
      block: contentBox(image.parentElement),
      float: style.float,
      paddingLeft: style.paddingLeft,
      paddingRight: style.paddingRight,
    };
  }
  const cells = {};
  for (const cell of prose.querySelectorAll("td, th")) {
    cells[cell.textContent.trim()] = getComputedStyle(cell).textAlign;
  }
  const title = prose.querySelector("h1");
  const right = [...prose.querySelectorAll("div")].find((div) => div.getAttribute("align"));
  return {
    images,
    cells,
    title: { ...box(title), text: textBox(title), align: getComputedStyle(title).textAlign },
    right: right ? { ...box(right), text: textBox(right) } : null,
  };
})()`;

const frames = () =>
  "new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(() => resolve(true))))";

/** @param {string} profile @param {Awaited<ReturnType<typeof launchChrome>>} page */
async function checkProfile(profile, page) {
  await page.send("Page.navigate", { url: `${base}/view/README.md` });
  await page.waitFor(DRAWN, 30000);
  await page.evaluate("document.fonts.ready.then(() => true)");
  await page.evaluate(frames());
  const { images, cells, title, right } = await page.evaluate(MEASURE);
  const at = (name) => images[name] ?? {};

  const icon = at("Centered icon");
  check(
    `${profile} the README's icon is 192 pixels square`,
    near(icon.width, 192) && near(icon.height, 192),
    icon,
  );
  check(
    `${profile} the README's icon is centered in its block`,
    near(icon.left - icon.block?.left, icon.block?.right - icon.right),
    icon,
  );
  check(
    `${profile} the title is centered`,
    title.align === "center" && near(title.text.left - title.left, title.right - title.text.right),
    title,
  );

  const badge = at("Badge");
  check(
    `${profile} an image sized by height alone`,
    near(badge.height, 20) && near(badge.width, 20),
    badge,
  );
  const byHeight = at("By height");
  check(
    `${profile} another image sized by height alone`,
    near(byHeight.height, 48) && near(byHeight.width, 48),
    byHeight,
  );
  const byWidth = at("By width");
  check(
    `${profile} an image sized by width alone`,
    near(byWidth.width, 64) && near(byWidth.height, 64),
    byWidth,
  );
  const byBoth = at("By both");
  check(
    `${profile} an image sized by both`,
    near(byBoth.width, 80) && near(byBoth.height, 40),
    byBoth,
  );

  const floatedRight = at("Right icon");
  check(
    `${profile} align="right" floats the image to the right edge, 120 wide, with 20 pixels of room`,
    floatedRight.float === "right" &&
      floatedRight.paddingLeft === "20px" &&
      near(floatedRight.width, 140) &&
      near(floatedRight.height, 120) &&
      near(floatedRight.right, floatedRight.block?.right),
    floatedRight,
  );
  const floatedLeft = at("Left icon");
  check(
    `${profile} align="left" floats the image to the left edge, 96 wide, with 20 pixels of room`,
    floatedLeft.float === "left" &&
      floatedLeft.paddingRight === "20px" &&
      near(floatedLeft.width, 116) &&
      near(floatedLeft.height, 96) &&
      near(floatedLeft.left, floatedLeft.block?.left),
    floatedLeft,
  );

  // A cell's own align, then its row's, then KPress's: a header centered, a cell at start.
  const expected = {
    Left: "left",
    Header: "center",
    Right: "right",
    Centered: "center",
    Default: "start",
    "Row right": "right",
    "Cell left": "left",
  };
  for (const [text, align] of Object.entries(expected)) {
    check(`${profile} the cell "${text}" is aligned ${align}`, cells[text] === align, cells);
  }

  check(
    `${profile} a <div align="right"> sets its text against its right edge`,
    right !== null && near(right.text.right, right.right) && right.text.left > right.left + 1,
    right,
  );
}

// Tall enough that the whole document is in view: its images load lazily, as they near it.
const page = await launchChrome(process.env.CHROME_BIN, {
  profiles: process.env.CHROME_PROFILES,
  height: 2400,
});
try {
  await page.send("Page.enable");
  await page.send("Network.enable");
  // The second server's page must not come from the first's cache.
  await page.send("Network.setCacheDisabled", { cacheDisabled: true });
  for (const [profile, flags] of [
    ["trusted", []],
    ["untrusted", ["--untrusted"]],
  ]) {
    const stop = await serve(flags);
    phase(`${profile} server`);
    try {
      await checkProfile(profile, page);
    } finally {
      await stop();
    }
    phase(profile);
  }
} finally {
  await page.close();
}
phase("closed");

if (failures.length) {
  process.stdout.write(`${failures.length} of ${checks} checks failed:\n${failures.join("\n")}\n`);
  process.exit(1);
}
process.stdout.write(`markdown github layout in Chrome: ${checks} checks passed\n`);

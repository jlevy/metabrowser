// Headless Chrome over one live `metab` server: a file's and a folder's view header
// (docs/design-system.md, "View Headers") at several pane widths in both themes.
//
// For each page it reads the header's rows, its ground and rules, the title's and the
// metadata line's type, and each metadata item's box; then it changes the line's values in
// place, as the folder header's live refresh does (`folderHeaderSummaryHtml` in view-header.js),
// and reads every box again. The caller (tests/test_view_header_chrome.py) judges the
// record. Arguments: the `metab` executable, the served root, a port to start the server's
// search from, and a state directory for its cache and config.
//
// Prints one JSON line, `{"results": [...]}`; each step's time goes to stderr.
import { spawn } from "node:child_process";
import path from "node:path";
import { launchChrome } from "./chrome-session.mjs";

const [metab, root, port, state] = process.argv.slice(2);
const started = Date.now();
const phase = (name) => process.stderr.write(`phase ${name} ${Date.now() - started}\n`);
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
const SERVING = /Serving .* at http:\/\/127\.0\.0\.1:(\d+)\/view\//;
// The window is 1280 px wide and the navigation pane is set to 300 px, so these are the
// main view's widths: a wide pane, the default window's, a narrow one, and the narrowest
// a 620 px window gives at the narrowest navigation pane.
const PANES = [1180, 900, 480, 260];
// The pages: a file two folders down with a long name, its folder, and the served root.
const PAGES = [
  { kind: "file", href: "/view/docs/notes/a-long-name-for-a-view-header-title.md" },
  { kind: "folder", href: "/view/docs/notes/" },
  { kind: "root", href: "/view/" },
];

async function serve() {
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
    ],
    {
      stdio: ["ignore", "pipe", "pipe"],
      env: { ...process.env, METABROWSER_LOG_LEVEL: "WARNING" },
    },
  );
  const exited = new Promise((resolve) => server.once("exit", resolve));
  let output = "";
  const took = await new Promise((resolve, reject) => {
    const bound = setTimeout(() => reject(new Error(`no server: ${output}`)), 30000);
    const read = (chunk) => {
      output += chunk;
      const serving = SERVING.exec(output);
      if (serving) {
        clearTimeout(bound);
        resolve(Number(serving[1]));
      }
    };
    server.stdout.on("data", read);
    server.stderr.on("data", read);
    server.once("exit", () => reject(new Error(`server exited: ${output}`)));
  });
  return {
    base: `http://127.0.0.1:${took}`,
    async stop() {
      server.kill("SIGTERM");
      await Promise.race([exited, sleep(20000)]);
    },
  };
}

// Every box the header draws, its ground and rules, and its type.
const READ = `(() => {
  const header = document.querySelector('#preview-pane > .file-header');
  const bar = document.querySelector('#preview-pane > .tab-bar');
  const box = (el) => {
    if (!el) return null;
    const r = el.getBoundingClientRect();
    const round = (n) => Math.round(n * 100) / 100;
    return { left: round(r.left), top: round(r.top), right: round(r.right), bottom: round(r.bottom), width: round(r.width), height: round(r.height) };
  };
  const style = (el) => (el ? getComputedStyle(el) : null);
  const q = (sel) => header && header.querySelector(sel);
  const line = q('.view-header-line');
  const lineBox = box(line);
  const items = line ? [...line.querySelectorAll('.view-header-item')].map((item) => {
    const b = box(item);
    return {
      text: item.textContent.replace(/\\s+/g, ' ').trim(),
      box: b,
      // On the line's one visible row, or wrapped to the clipped row under it.
      shown: b.top < lineBox.bottom - 0.5,
      whole: b.right <= lineBox.right + 0.5 && b.bottom <= lineBox.bottom + 0.5,
    };
  }) : [];
  const title = q('.view-header-title');
  const pane = document.getElementById('preview-pane');
  const token = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  return {
    // The tokens the layout is held to, as the page resolves them.
    tokens: Object.fromEntries(
      ["--view-header-row-gap", "--view-header-eyebrow-height", "--view-header-line-height", "--page-title-font-size", "--body-font-size"].map((name) => [name, token(name)]),
    ),
    paneWidth: Math.round(pane.getBoundingClientRect().width),
    scheme: matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light',
    header: box(header),
    eyebrow: box(q('.view-header-eyebrow')),
    up: box(q('.view-header-eyebrow > .folder-up')),
    upDisabled: !!q('.view-header-eyebrow > .folder-up[disabled]'),
    address: q('.view-header-eyebrow .file-header-path') ? q('.view-header-eyebrow .file-header-path').textContent.replace(/\\s+/g, ' ').trim() : null,
    heading: box(q('.view-header-heading')),
    icon: box(q('.view-header-icon')),
    iconGlyph: box(q('.view-header-icon svg')),
    title: box(title),
    titleText: title ? title.textContent : null,
    titleCut: title ? title.scrollWidth > title.clientWidth + 0.5 : null,
    // Whether the shell's own rule would show the title's tooltip, and the heights it
    // reads, which a large font's glyphs can make disagree with the width.
    titleTip: title ? tipAddsInformation(title) : null,
    titleHeights: title ? { scroll: title.scrollHeight, client: title.clientHeight } : null,
    end: box(q('.view-header-end')),
    line: lineBox,
    items,
    bar: box(bar),
    type: {
      title: style(title) && style(title).fontSize,
      titleWeight: style(title) && style(title).fontWeight,
      eyebrow: style(q('.view-header-eyebrow .file-header-path')) && style(q('.view-header-eyebrow .file-header-path')).fontSize,
      line: style(line) && style(line).fontSize,
    },
    grounds: {
      body: style(document.body).backgroundColor,
      header: style(header).backgroundColor,
      bar: style(bar).backgroundColor,
      nav: style(document.querySelector('.app-header')).backgroundColor,
    },
    rules: {
      headerTop: style(header).borderTopWidth,
      headerBottom: style(header).borderBottomWidth,
      barBottom: style(bar).borderBottomWidth,
      barBottomColor: style(bar).borderBottomColor,
      barTop: style(bar).borderTopWidth,
    },
    line_ink: style(line) && style(line).color,
  };
})()`;

// Change the line's values in place, as the live refresh does: the folder's summary
// rewritten by the shell's own `folderHeaderSummaryHtml`, a file's age item by
// `viewHeaderAgeHtml`, both the page's own view-header.js builders (app.js's
// viewHeaderBuilders), at the age a just-written folder has, then an hour later.
const RELABEL = (kind, step) => `(() => {
  const now = Date.now() / 1000;
  const mtime = ${step === "pending" ? "null" : step === "fresh" ? "now" : "now - 59 * 60"};
  if ('${kind}' === 'file') {
    const age = document.querySelector('#preview-pane > .file-header .view-header-age');
    age.outerHTML = viewHeaderBuilders().viewHeaderAgeHtml(mtime);
    return true;
  }
  const summary = document.querySelector('#preview-pane > .file-header .folder-header-summary');
  summary.innerHTML = viewHeaderBuilders().folderHeaderSummaryHtml(${
    step === "pending"
      ? "{ total_size: null, total_files: null, mtime: null }"
      : "{ total_size: 1234567, total_files: 12345, mtime }"
  });
  return true;
})()`;

async function main() {
  const server = await serve();
  phase("server");
  const browser = await launchChrome(process.env.CHROME_BIN, {
    profiles: process.env.CHROME_PROFILES,
    width: 1280,
    height: 900,
  });
  const results = [];
  try {
    phase("chrome");
    await browser.send("Page.enable");
    for (const theme of ["light", "dark"]) {
      await browser.send("Emulation.setEmulatedMedia", {
        features: [{ name: "prefers-color-scheme", value: theme }],
      });
      for (const pane of PANES) {
        // A pane this narrow needs a narrower window: 300 px of navigation beside it.
        await browser.send("Emulation.setDeviceMetricsOverride", {
          width: pane + 300,
          height: 800,
          deviceScaleFactor: 1,
          mobile: false,
        });
        for (const page of PAGES) {
          await browser.send("Page.navigate", { url: `${server.base}${page.href}` });
          await browser.waitFor("document.readyState === 'complete'");
          await browser.evaluate(
            "document.documentElement.style.setProperty('--tree-pane-width', '300px'), true",
          );
          await browser.waitFor(
            "document.querySelector('#preview-pane > .file-header .view-header-age [class*=age-]') !== null && document.querySelector('#preview-pane > .tab-bar') !== null",
          );
          // Fonts, then two frames, so the boxes read are the painted ones.
          await browser.evaluate(
            "document.fonts.ready.then(() => new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)))).then(() => true)",
          );
          const settled = await browser.evaluate(READ);
          const relabeled = {};
          for (const step of ["fresh", "hour", "pending"]) {
            await browser.evaluate(RELABEL(page.kind, step));
            await browser.evaluate(
              "new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r))).then(() => true)",
            );
            relabeled[step] = await browser.evaluate(READ);
          }
          results.push({ ...page, theme, pane, settled, relabeled });
        }
      }
      phase(theme);
    }
  } finally {
    await browser.close();
    await server.stop();
  }
  process.stdout.write(`${JSON.stringify({ results })}\n`);
}

main().catch((error) => {
  process.stderr.write(`${error.stack || error}\n`);
  process.exit(1);
});

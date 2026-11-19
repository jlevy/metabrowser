// Headless Chrome over one live `metab` server: a file's and a folder's view header
// (docs/design-system.md, "View Headers") at several pane widths in both themes.
//
// For each page it reads the header's rows, its ground and rules, the title's and the
// metadata line's type, where the title's text and the line sit and their baselines, and
// each metadata item's box; then it changes the line's values in place, as the folder
// header's live refresh does (`folderHeaderSummaryHtml` in view-header.js), and reads every
// box again. The caller (tests/test_view_header_chrome.py) judges the
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
// The navigation pane is set to 300 px and the window sized to each, so these are the
// main view's widths: a wide pane, a middling one, a phone's, and the narrowest a 620 px
// window gives at the narrowest navigation pane.
const PANES = [1400, 800, 360, 260];
// The name no pane holds on one line (tests/test_view_header_chrome.py, `_WRAPPED`).
const WRAPPED =
  "a-file-name-so-long-that-no-pane-the-session-draws-holds-it-on-one-line-of-the-view-header-so-it-wraps-and-its-size-and-age-follow-its-last-line.md";
// The pages: a file two folders down with a long name, its folder, the served root, and a
// file whose name is too long for any pane's row.
const PAGES = [
  { kind: "file", href: "/view/docs/notes/a-long-name-for-a-view-header-title.md" },
  { kind: "folder", href: "/view/docs/notes/" },
  { kind: "root", href: "/view/" },
  { kind: "wrapped", href: `/view/docs/notes/${WRAPPED}` },
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

// Every box the header draws, its ground and rules, and its type. It reads the layout
// before this one too (a title cut to one row, the line on a row of its own under it), so
// the record says how that layout misses the design rather than failing to read it.
const READ = `(() => {
  const header = document.querySelector('#preview-pane > .file-header');
  const bar = document.querySelector('#preview-pane > .tab-bar');
  const round = (n) => Math.round(n * 100) / 100;
  const rect = (r) => ({ left: round(r.left), top: round(r.top), right: round(r.right), bottom: round(r.bottom), width: round(r.width), height: round(r.height) });
  const box = (el) => (el ? rect(el.getBoundingClientRect()) : null);
  const style = (el) => (el ? getComputedStyle(el) : null);
  const q = (sel) => header && header.querySelector(sel);
  // Where a box's text sits: a probe of no size at its end rests on the baseline of its
  // last line.
  const baseline = (el) => {
    if (!el) return null;
    const probe = document.createElement('span');
    probe.style.cssText = 'display:inline-block;width:0;height:0;vertical-align:baseline';
    el.append(probe);
    const y = probe.getBoundingClientRect().top;
    probe.remove();
    return round(y);
  };
  const title = q('.view-header-title');
  const group = title ? title.parentElement : null;
  const line = q('.view-header-line');
  // The title's text, a box per line it takes, as its glyphs lie, without its padding.
  const range = document.createRange();
  if (title) range.selectNodeContents(title);
  const textRects = title ? [...range.getClientRects()].filter((r) => r.width > 0).map(rect) : [];
  const textLines = [...new Set(textRects.map((r) => Math.round(r.top)))].length;
  const items = line ? [...line.querySelectorAll('.view-header-item')].map((item) => ({
    text: item.textContent.replace(/\\s+/g, ' ').trim(),
    box: box(item),
  })) : [];
  const pane = document.getElementById('preview-pane');
  const token = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  return {
    // The tokens the layout is held to, as the page resolves them.
    tokens: Object.fromEntries(
      ["--view-header-row-gap", "--view-header-eyebrow-height", "--view-header-line-height", "--view-header-padding-top", "--view-header-padding-bottom", "--view-header-title-gap", "--page-title-font-size", "--body-font-size", "--view-header-up-size", "--view-header-toggle-option-width", "--chip-border", "--icon-glyph", "--content-padding-x"].map((name) => [name, token(name)]),
    ),
    paneWidth: Math.round(pane.getBoundingClientRect().width),
    scheme: matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light',
    header: box(header),
    // Whether anything in the header runs past its box, as a name or a value pushed out of
    // the pane would.
    headerOverflows: header ? header.scrollWidth > header.clientWidth + 0.5 : null,
    eyebrow: box(q('.view-header-eyebrow')),
    up: box(q('.view-header-eyebrow > .folder-up')),
    upDisabled: !!q('.view-header-eyebrow > .folder-up[disabled]'),
    address: q('.view-header-eyebrow .file-header-path') ? q('.view-header-eyebrow .file-header-path').textContent.replace(/\\s+/g, ' ').trim() : null,
    heading: box(q('.view-header-heading')),
    icon: box(q('.view-header-icon')),
    iconGlyph: box(q('.view-header-icon svg')),
    group: box(group),
    title: box(title),
    titleText: title ? title.textContent : null,
    titleTextRects: textRects,
    titleLines: textLines,
    // The title's line height, which the heading row's first line is.
    titleLineHeight: title ? parseFloat(style(title).lineHeight) : null,
    // Cut short: an ellipsis, or a box whose text runs past it.
    titleCut: title ? style(title).textOverflow === 'ellipsis' && title.scrollWidth > title.clientWidth + 0.5 : null,
    titleClipped: title ? textRects.some((r) => r.right > box(group).right + 0.5 || r.left < box(group).left - 0.5) : null,
    // Whether the shell's own rule would show the title's tooltip.
    titleTip: title ? tipAddsInformation(title) : null,
    titleBaseline: baseline(title),
    lineBaseline: baseline(q('.view-header-line .file-header-size')),
    end: box(q('.view-header-end')),
    toggle: box(q('.view-header-toggle')),
    toggleCurrent: q('.view-header-toggle [aria-current=page]') ? q('.view-header-toggle [aria-current=page]').className : null,
    toggleHref: q('.view-header-toggle a') ? q('.view-header-toggle a').href : null,
    marks: [...(header ? header.querySelectorAll('.view-header-toggle-mark') : [])].map(box),
    line: box(line),
    items,
    bar: box(bar),
    type: {
      title: style(title) && style(title).fontSize,
      titleWeight: style(title) && style(title).fontWeight,
      eyebrow: style(q('.view-header-eyebrow .file-header-path')) && style(q('.view-header-eyebrow .file-header-path')).fontSize,
      line: style(line) && style(line).fontSize,
    },
    inks: {
      line: style(line) && style(line).color,
      muted: (() => { const probe = document.createElement('span'); probe.style.color = 'var(--muted)'; header.append(probe); const color = getComputedStyle(probe).color; probe.remove(); return color; })(),
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
  };
})()`;

// Change the line's values in place, as the live refresh does: the folder's summary
// rewritten by the shell's own `folderHeaderSummaryHtml`, a file's age item by
// `viewHeaderAgeHtml`, both the page's own view-header.js builders (app.js's
// viewHeaderBuilders), at the age a just-written folder has, then an hour later.
const RELABEL = (kind, step) => `(() => {
  const now = Date.now() / 1000;
  const mtime = ${step === "pending" ? "null" : step === "fresh" ? "now" : "now - 59 * 60"};
  if ('${kind}' === 'file' || '${kind}' === 'wrapped') {
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

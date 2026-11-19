// Headless Chrome over one live `metab` server: a file's and a folder's view header
// (docs/design-system.md, "View Headers") at several pane widths in both themes, with the
// View on GitHub button in its corner (docs/design-system.md, "View on GitHub").
//
// For each page it reads the header's rows, its ground and rules, the title's and the
// metadata line's type, where the title's text and the line sit and their baselines, each
// metadata item's box, and the button's; then it changes the line's values in place, as the
// folder header's live refresh does (`folderHeaderSummaryHtml` in view-header.js), and
// reads every box again. Then, in each theme: the button's menu opened with a click and
// walked with the keys, a page with no counterpart, and a commit's page at a wide and a
// narrow pane. The caller (tests/test_view_header_chrome.py) judges the record.
// Arguments: the `metab` executable, the served root, a port to start the server's search
// from, a state directory for its cache and config, and the commit the served checkout is
// at.
//
// Prints one JSON line, `{"results": [...], "menus": [...], "absent": [...],
// "commits": [...]}`; each step's time goes to stderr.
import { spawn } from "node:child_process";
import path from "node:path";
import { launchChrome } from "./chrome-session.mjs";

const [metab, root, port, state, commit] = process.argv.slice(2);
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
  "a-file-name-so-long-that-no-pane-the-session-draws-holds-it-on-one-line-3f9a0c5be1d2476a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a-of-the-view-header-so-it-wraps-and-its-size-and-age-follow-its-last-line.md";
// The pages: a file two folders down with a long name, its folder, the served root, and a
// file whose name is too long for any pane's row.
const PAGES = [
  { kind: "file", href: "/view/docs/notes/a-long-name-for-a-view-header-title.md" },
  { kind: "folder", href: "/view/docs/notes/" },
  { kind: "root", href: "/view/" },
  { kind: "wrapped", href: `/view/docs/notes/${WRAPPED}` },
];
// A file the checkout does not track, which has no counterpart on github.com.
const ABSENT = "/view/docs/notes/draft.txt";
// The commit's page at a pane where its reading column ends short of the corner, and one
// where it reaches it.
const COMMIT_PANES = [1180, 480];

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

// What a corner's View on GitHub button draws: its group's box, the hooks the macOS app reads
// (mb-4wqh), its mark's box, its label's size, the inks and fills of its link and chevron
// and its frame (`buttonInks`, apart from the header's own `inks`), and the tokens they
// should resolve to, read from a probe painted with each. As a function's source, so READ
// and COMMIT_READ share it in the page.
const BUTTON_SOURCE = `(corner) => {
  const button = corner ? corner.querySelector(':scope > .counterpart') : null;
  if (!button) return { button: null, hooks: null, buttonInks: null, want: null, markBox: null };
  const round = (n) => Math.round(n * 100) / 100;
  const box = (el) => {
    if (!el) return null;
    const r = el.getBoundingClientRect();
    return { left: round(r.left), top: round(r.top), right: round(r.right), bottom: round(r.bottom), width: round(r.width), height: round(r.height) };
  };
  const resolved = (property, value) => {
    const probe = document.createElement('span');
    probe.style.position = 'absolute';
    probe.style[property] = value;
    document.body.append(probe);
    const out = getComputedStyle(probe)[property];
    probe.remove();
    return out;
  };
  const group = button.querySelector('.counterpart-group');
  const open = button.querySelector('[data-web-view=open]');
  const external = button.querySelector('[data-web-view=external]');
  const more = button.querySelector('.counterpart-more');
  const paint = (el) => ({ ink: getComputedStyle(el).color, fill: getComputedStyle(el).backgroundColor });
  const frame = getComputedStyle(group);
  const label = button.querySelector('.counterpart-label');
  return {
    button: box(group),
    markBox: box(button.querySelector('.counterpart-mark svg')),
    buttonFont: label ? getComputedStyle(label).fontSize : null,
    hooks: {
      root: button.hasAttribute('data-view-on-github'),
      label: open ? open.textContent : null,
      open: open ? open.getAttribute('href') : null,
      openTarget: open ? open.getAttribute('target') : null,
      openRel: open ? open.getAttribute('rel') : null,
      external: external ? external.getAttribute('href') : null,
      externalTarget: external ? external.getAttribute('target') : null,
      externalRel: external ? external.getAttribute('rel') : null,
      items: [...button.querySelectorAll('.counterpart-menu .menu-item')].map((item) => item.textContent.trim()),
      expanded: more ? more.getAttribute('aria-expanded') : null,
      popup: more ? more.getAttribute('aria-haspopup') : null,
      menuHidden: button.querySelector('.counterpart-menu').hidden,
    },
    buttonInks: {
      open: paint(open),
      more: paint(more),
      frame: { border: frame.borderTopColor, ground: frame.backgroundColor, radius: frame.borderTopLeftRadius },
    },
    want: {
      text: resolved('color', 'var(--text)'),
      muted: resolved('color', 'var(--muted)'),
      border: resolved('borderTopColor', 'var(--viz-border)'),
      surface: resolved('backgroundColor', 'var(--viz-surface)'),
      radius: resolved('borderTopLeftRadius', 'var(--radius-pill)'),
      glyph: resolved('width', 'var(--icon-glyph)'),
      chipFont: resolved('fontSize', 'var(--ui-small-font-size)'),
    },
  };
}`;

// Every box the header draws, its ground and rules, and its type. It reads the layout
// before this one too (a title cut to one row, the line on a row of its own under it), so
// the record says how that layout misses the design rather than failing to read it.
const READ = `(() => {
  const BUTTON = ${BUTTON_SOURCE};
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
      ["--view-header-row-gap", "--view-header-eyebrow-height", "--view-header-line-height", "--view-header-padding-top", "--view-header-padding-bottom", "--view-header-title-gap", "--page-title-font-size", "--body-font-size", "--view-header-up-size", "--view-header-corner-inset-top", "--view-header-corner-inset-end", "--view-header-corner-height", "--view-header-corner-room", "--content-padding-x"].map((name) => [name, token(name)]),
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
    endMarked: q('.view-header-end') ? q('.view-header-end').hasAttribute('data-counterpart') : null,
    eyebrowRoom: q('.view-header-eyebrow') ? parseFloat(style(q('.view-header-eyebrow')).paddingInlineEnd) : null,
    addressBox: box(q('.view-header-eyebrow .file-header-path')),
    ...BUTTON(q('.view-header-end')),
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

// The button's menu, opened with a trusted click on the chevron and walked with the keys:
// where it opens, what it holds, whether each item is the element at its own center, which
// item has focus after each key, and where focus goes when it closes.
const MENU_OPEN = `(() => {
  const more = document.querySelector('#preview-pane > .file-header .counterpart-more');
  const r = more.getBoundingClientRect();
  return { x: r.left + r.width / 2, y: r.top + r.height / 2 };
})()`;
const MENU_READ = `(() => {
  const root = document.querySelector('#preview-pane > .file-header .counterpart');
  const menu = root.querySelector('.counterpart-menu');
  const more = root.querySelector('.counterpart-more');
  const round = (n) => Math.round(n * 100) / 100;
  const box = (el) => {
    const r = el.getBoundingClientRect();
    return { left: round(r.left), top: round(r.top), right: round(r.right), bottom: round(r.bottom), width: round(r.width), height: round(r.height) };
  };
  const items = [...menu.querySelectorAll('.menu-item')];
  const active = document.activeElement;
  return {
    hidden: menu.hidden,
    expanded: more.getAttribute('aria-expanded'),
    menu: menu.hidden ? null : box(menu),
    group: box(root.querySelector('.counterpart-group')),
    viewport: { width: innerWidth, height: innerHeight },
    items: items.map((item) => {
      const b = box(item);
      const hit = menu.hidden ? null : document.elementFromPoint(b.left + b.width / 2, b.top + b.height / 2);
      const look = getComputedStyle(item);
      return { text: item.textContent.trim(), role: item.getAttribute('role'), topmost: hit !== null && item.contains(hit), look: [look.color, look.textDecorationLine] };
    }),
    focus: active === more ? 'chevron' : items.includes(active) ? active.textContent.trim() : (active ? active.tagName : null),
  };
})()`;
// A page whose answer says it has no counterpart: the corner, whether the answer has come,
// and what it holds.
const ABSENT_READ = `(() => {
  const header = document.querySelector('#preview-pane > .file-header');
  const corner = header && header.querySelector('.view-header-end');
  const eyebrow = header && header.querySelector('.view-header-eyebrow');
  return {
    answered: performance.getEntriesByType('resource').some((entry) => entry.name.includes('/api/counterpart?')),
    marked: corner ? corner.hasAttribute('data-counterpart') : null,
    children: corner ? corner.children.length : null,
    eyebrowRoom: eyebrow ? parseFloat(getComputedStyle(eyebrow).paddingInlineEnd) : null,
  };
})()`;
// A commit's page: its corner's button placed in the page, the page's box, and the room its
// subject leaves the button, with where the subject's text ends. The page has one corner,
// and the box it is placed in is its offset parent, whose class the test names: this
// script names no commit view's class, since a script that spawns a process and names the
// version-control tool as a word fails tests/test_git_hook_environment.py.
const COMMIT_READ = `(() => {
  const BUTTON = ${BUTTON_SOURCE};
  const corners = document.querySelectorAll('#preview-pane .view-header-end');
  const corner = corners.length === 1 ? corners[0] : null;
  const view = corner && corner.offsetParent;
  const subject = corner && corner.parentElement.querySelector(':scope > .page-heading');
  const round = (n) => Math.round(n * 100) / 100;
  const box = (el) => {
    if (!el) return null;
    const r = el.getBoundingClientRect();
    return { left: round(r.left), top: round(r.top), right: round(r.right), bottom: round(r.bottom), width: round(r.width), height: round(r.height) };
  };
  const range = document.createRange();
  if (subject) range.selectNodeContents(subject);
  const pane = document.getElementById('preview-pane');
  return {
    corners: corners.length,
    viewClass: view ? view.className : null,
    view: box(view),
    marked: corner ? corner.hasAttribute('data-counterpart') : null,
    afterSubject: corner ? corner.previousElementSibling === subject : null,
    subjectRoom: subject ? parseFloat(getComputedStyle(subject).paddingInlineEnd) : null,
    subjectEnd: subject ? round(range.getBoundingClientRect().right) : null,
    paneScrolls: pane.scrollWidth > pane.clientWidth,
    ...BUTTON(corner),
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
  const menus = [];
  const absent = [];
  const commits = [];
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
            "document.querySelector('#preview-pane > .file-header .view-header-age [class*=age-]') !== null && document.querySelector('#preview-pane > .tab-bar') !== null && document.querySelector('#preview-pane > .file-header .view-header-end > .counterpart') !== null",
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
      phase(`${theme} pages`);
      await browser.send("Emulation.setDeviceMetricsOverride", {
        width: 1200,
        height: 800,
        deviceScaleFactor: 1,
        mobile: false,
      });
      // The menu: opened with a click on the chevron, then ArrowDown, End, Home, Escape,
      // and opened again from the keyboard with ArrowUp, then Tab.
      await browser.send("Page.navigate", { url: `${server.base}${PAGES[0].href}` });
      await browser.waitFor(
        "document.querySelector('#preview-pane > .file-header .view-header-end > .counterpart') !== null",
      );
      await browser.evaluate(
        "document.fonts.ready.then(() => new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)))).then(() => true)",
      );
      const frames =
        "new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r))).then(() => true)";
      const key = async (name, code, keyCode) => {
        for (const type of ["keyDown", "keyUp"]) {
          await browser.send("Input.dispatchKeyEvent", {
            type,
            key: name,
            code,
            windowsVirtualKeyCode: keyCode,
          });
        }
        await browser.evaluate(frames);
        return browser.evaluate(MENU_READ);
      };
      const menu = { theme, steps: {} };
      menu.steps.closed = await browser.evaluate(MENU_READ);
      const at = await browser.evaluate(MENU_OPEN);
      for (const type of ["mousePressed", "mouseReleased"]) {
        await browser.send("Input.dispatchMouseEvent", {
          type,
          x: at.x,
          y: at.y,
          button: "left",
          clickCount: 1,
        });
      }
      await browser.evaluate(frames);
      menu.steps.clicked = await browser.evaluate(MENU_READ);
      menu.steps.arrowDown = await key("ArrowDown", "ArrowDown", 40);
      menu.steps.arrowDownAgain = await key("ArrowDown", "ArrowDown", 40);
      menu.steps.end = await key("End", "End", 35);
      menu.steps.home = await key("Home", "Home", 36);
      menu.steps.escape = await key("Escape", "Escape", 27);
      menu.steps.arrowUp = await key("ArrowUp", "ArrowUp", 38);
      menu.steps.tab = await key("Tab", "Tab", 9);
      // Open again with a click, then a press outside the button closes it.
      for (const type of ["mousePressed", "mouseReleased"]) {
        await browser.send("Input.dispatchMouseEvent", {
          type,
          x: at.x,
          y: at.y,
          button: "left",
          clickCount: 1,
        });
      }
      await browser.evaluate(frames);
      menu.steps.reopened = await browser.evaluate(MENU_READ);
      for (const type of ["mousePressed", "mouseReleased"]) {
        await browser.send("Input.dispatchMouseEvent", {
          type,
          x: 700,
          y: 600,
          button: "left",
          clickCount: 1,
        });
      }
      await browser.evaluate(frames);
      menu.steps.outside = await browser.evaluate(MENU_READ);
      menus.push(menu);
      // A file the checkout does not track: its corner keeps the room and draws nothing.
      await browser.send("Page.navigate", { url: `${server.base}${ABSENT}` });
      await browser.waitFor(
        "document.querySelector('#preview-pane > .file-header .view-header-age [class*=age-]') !== null && performance.getEntriesByType('resource').some((entry) => entry.name.includes('/api/counterpart?'))",
      );
      await browser.evaluate(frames);
      absent.push({ theme, ...(await browser.evaluate(ABSENT_READ)) });
      // The commit's page, its button placed in the page as a view header's is.
      for (const pane of COMMIT_PANES) {
        await browser.send("Emulation.setDeviceMetricsOverride", {
          width: pane + 300,
          height: 800,
          deviceScaleFactor: 1,
          mobile: false,
        });
        await browser.send("Page.navigate", { url: `${server.base}/commit/${commit}` });
        await browser.waitFor("document.readyState === 'complete'");
        await browser.evaluate(
          "document.documentElement.style.setProperty('--tree-pane-width', '300px'), true",
        );
        await browser.waitFor(
          "document.querySelector('#preview-pane .view-header-end > .counterpart') !== null",
        );
        await browser.evaluate(
          "document.fonts.ready.then(() => new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)))).then(() => true)",
        );
        commits.push({ theme, pane, ...(await browser.evaluate(COMMIT_READ)) });
      }
      phase(theme);
    }
  } finally {
    await browser.close();
    await server.stop();
  }
  process.stdout.write(`${JSON.stringify({ results, menus, absent, commits })}\n`);
}

main().catch((error) => {
  process.stderr.write(`${error.stack || error}\n`);
  process.exit(1);
});

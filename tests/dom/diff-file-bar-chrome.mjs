// A diff's file bars laid out by headless Chrome at bar widths from 1,063 px down to 171 px,
// under the shell's and the diff plugin's stylesheets and KPress's faces.
//
//   CHROME_BIN=/path/to/chrome CHROME_PROFILES=/dir/the/caller/removes \
//     KPRESS_STATIC=/dir/with/kpress/css/and/fonts [BAR_SHOTS=/dir/for/screenshots] \
//     node tests/dom/diff-file-bar-chrome.mjs
//
// tests/test_diff_file_bar_chrome.py copies KPress's stylesheets and faces out of the
// installed package, owns the profile, and runs this in a process group of its own.
//
// Each bar is the markup `renderFileBar` (builtin_plugins/diff/diff-view.js) builds, with
// the shell's icons, and for a bar with a Full | Concise | Source chooser the markup
// diff-markdown.js's `add` puts at its end, through the production chip group
// (static/filter-controls.js). tests/dom/diff-view-behavior.js and
// tests/dom/diff-view-file-session.js hold the production bar to this structure: the
// name's group (the disclosure, Copy path, and the stats), then View file or View on
// branch, then the end group. Here the layout is held, at every width:
//
// - no part of a bar ends past its content edge, and no two parts cover each other;
// - a bar with a chooser cuts its name only on a line of its own: View on branch and the
//   chooser move to the next line first, so the name keeps what it had while View on
//   branch was in the end group (review A of #759, A1);
// - a bar without one cuts a long name on one line while its name's group keeps
//   `--diff-file-lead-basis`, the space before View file giving way first, and below that
//   moves View file to the next line;
// - the chooser ends the bar at its end pad, and View file follows the name's group;
// - at rest the stats are nearer the name than View file is to the stats, though Copy
//   path keeps its slot between them (A4);
// - nothing after a file that waits for its first drawing is seen or takes a press, and
//   all of it is once the wait is over, so a body that arrives late moves nothing a reader
//   sees (mb-ne65). The session in tests/dom/diff-markdown-session.js holds when a file
//   says it waits.
import fs from "node:fs";
import http from "node:http";
import path from "node:path";
import { launchChrome } from "./chrome-session.mjs";

const root = path.resolve(import.meta.dirname, "../..");
const STATIC = path.join(root, "src/metabrowser/static");
const DIFF = path.join(root, "src/metabrowser/builtin_plugins/diff");
const KPRESS = path.resolve(/** @type {string} */ (process.env.KPRESS_STATIC));
const SHOTS = process.env.BAR_SHOTS;
// Layout puts box edges on 1/64 px; half a pixel separates what text rendering rounds.
const TOLERANCE_PX = 0.5;
// The widths the review measured (A1), and the narrowest a bar can be with nothing cut,
// which a Markdown file's Full | Concise | Source chooser sets: 150.8 px in Chrome, inside
// the bar's 10 px pads (159 px held the two-chip Rendered | Source it replaced).
const BAR_WIDTHS = [1063, 499, 399, 299, 199, 171];
const failures = [];
let checks = 0;
const check = (label, ok, detail = "") => {
  checks += 1;
  if (!ok) {
    failures.push(`${label}${detail ? `: ${detail}` : ""}`);
  }
};

const PAGE = `<!doctype html><html><head><meta charset="utf-8"><title>diff file bar</title>
<link rel="stylesheet" href="/kpress/css/style-tokens.css">
<link rel="stylesheet" href="/static/styles.css">
<link rel="stylesheet" href="/diff/styles.css">
<script src="/static/icons.js"></script>
<script src="/static/formatters.js"></script>
<script>window.metabrowser = { icons: window.MetabrowserIcons };</script>
<script src="/static/filter-controls.js"></script>
</head><body><div id="preview-pane" class="preview-pane"><div id="host" class="metabrowser-diff-host"></div></div></body></html>`;

const TYPES = { ".css": "text/css", ".js": "text/javascript", ".woff2": "font/woff2" };
function serve() {
  const server = http.createServer((request, response) => {
    const url = new URL(request.url ?? "/", "http://localhost");
    let file = null;
    if (url.pathname === "/") {
      response.writeHead(200, { "content-type": "text/html" });
      response.end(PAGE);
      return;
    }
    if (url.pathname.startsWith("/static/")) {
      file = path.join(STATIC, url.pathname.slice(8));
    } else if (url.pathname.startsWith("/diff/")) {
      file = path.join(DIFF, url.pathname.slice(6));
    } else if (url.pathname.startsWith("/kpress/")) {
      file = path.join(KPRESS, url.pathname.slice(8));
    }
    const within = [root, KPRESS].some((dir) => file?.startsWith(dir + path.sep));
    if (!file || !within || !fs.existsSync(file)) {
      response.writeHead(404);
      response.end();
      return;
    }
    response.writeHead(200, { "content-type": TYPES[path.extname(file)] ?? "text/plain" });
    fs.createReadStream(file).pipe(response);
  });
  return new Promise((resolve) => server.listen(0, "127.0.0.1", () => resolve(server)));
}

const SHORT = "docs/new.md";
const LONG = "docs/project/architecture/arch-views-models-routes.md";
// Every bar the page draws: on a pull request's Docs and Changes a document's bar has the
// chooser and View on branch; a commit's bar has View file; a patch's has neither.
const BARS = [
  { id: "chooser-short", path: SHORT, chooser: true, view: "View on branch" },
  { id: "chooser-long", path: LONG, chooser: true, view: "View on branch" },
  { id: "plain-short", path: "src/app.txt", chooser: false, view: "View on branch" },
  { id: "plain-long", path: LONG, chooser: false, view: "View file" },
  { id: "patch-long", path: LONG, chooser: false, view: null },
  // Stats of five digits a side, which the name's group keeps whole beside a cut name.
  {
    id: "wide-stats",
    path: LONG,
    chooser: false,
    view: "View file",
    additions: 12345,
    deletions: 12345,
  },
];

// In the page: the bars, as renderFileBar and diff-markdown.js's `add` build them.
const MOUNT = `(bars) => {
  const icons = window.MetabrowserIcons;
  const controls = window.metabrowser.filterControls;
  const formatters = window.MetabrowserFormatters;
  const el = (tag, className, children = []) => {
    const node = document.createElement(tag);
    if (className) node.className = className;
    node.append(...children);
    return node;
  };
  const host = document.getElementById("host");
  host.replaceChildren();
  for (const spec of bars) {
    const chevron = el("span", "diff-file-chevron");
    chevron.innerHTML = icons.toggle;
    const kind = el("span", "diff-file-kind file-change-status", ["A"]);
    kind.dataset.fileStatus = "added";
    const name = el("span", "diff-file-path", [spec.path]);
    const toggle = el("button", "diff-file-toggle expanded", [chevron, kind, name]);
    toggle.type = "button";
    const copy = el("button", "icon-btn icon-btn-reveal diff-file-copy");
    copy.type = "button";
    copy.innerHTML = icons.copy;
    // Its lines through the shell's brief change line, as renderFileBar paints them.
    const line = formatters.changeLine(
      { statuses: [], additions: spec.additions ?? 1, deletions: spec.deletions ?? 0 },
      formatters.formatInteger,
    );
    const stats = el("span", "diff-file-stats", formatters.changeLineNodes(document, line));
    const facts = el("span", "diff-file-facts", [stats]);
    const lead = el("div", "diff-file-lead", [toggle, copy, facts]);
    const end = el("div", "diff-file-end");
    const parts = [lead];
    if (spec.view) {
      const view = el("a", "diff-file-view", [spec.view]);
      view.href = "#";
      parts.push(view);
    }
    const bar = el("div", "diff-file-bar disclosure-toggle", [...parts, end]);
    if (spec.chooser) {
      const progress = el("span", "diff-markdown-progress", [el("span", "spinner spinner-sm")]);
      const control = el("div", "diff-markdown-control");
      control.innerHTML = controls.groupHtml({
        key: spec.id,
        label: "Markdown diff format",
        layout: "joined",
        options: [
          { label: "Full", value: "full" },
          { label: "Concise", value: "concise" },
          { label: "Source", value: "source" },
        ],
        select: "one",
        value: "concise",
      });
      bar.classList.add("diff-file-bar-markdown");
      end.append(progress, control);
    }
    const section = el("section", "diff-file", [bar]);
    section.id = spec.id;
    host.append(section);
  }
  return host.querySelectorAll(".diff-file-bar").length;
}`;

// In the page: each bar's geometry at one width.
const MEASURE = `(width) => {
  const host = document.getElementById("host");
  host.style.inlineSize = width + 2 + "px";
  const box = (el) => (el ? el.getBoundingClientRect() : null);
  const text = (el) => {
    const range = document.createRange();
    range.selectNodeContents(el);
    const rects = [...range.getClientRects()].filter((r) => r.width > 0);
    return { left: Math.min(...rects.map((r) => r.left)), right: Math.max(...rects.map((r) => r.right)), top: Math.min(...rects.map((r) => r.top)) };
  };
  return [...host.querySelectorAll(".diff-file")].map((section) => {
    const bar = section.querySelector(".diff-file-bar");
    const style = getComputedStyle(bar);
    const b = box(bar);
    const lead = bar.querySelector(".diff-file-lead");
    const name = bar.querySelector(".diff-file-path");
    const stats = bar.querySelector(".diff-file-stats");
    const view = bar.querySelector(".diff-file-view");
    const chooser = bar.querySelector(".diff-markdown-control");
    const parts = [".diff-file-chevron", ".diff-file-kind", ".diff-file-path", ".diff-file-copy", ".diff-file-stats", ".diff-file-view", ".diff-markdown-control"]
      .map((selector) => [selector, box(bar.querySelector(selector))])
      .filter(([, rect]) => rect !== null && rect.width > 0)
      .map(([selector, rect]) => ({ selector, left: rect.left, right: rect.right, top: rect.top, bottom: rect.bottom }));
    // The group's own width, laid out alone: what a bar lays it out at before it wraps.
    const saved = lead.style.cssText;
    lead.style.cssText = "flex: none; width: max-content; max-width: none";
    const leadMax = box(lead).width;
    lead.style.cssText = saved;
    const nameText = text(name);
    const statsText = text(stats);
    const viewText = view ? text(view) : null;
    return {
      id: section.id,
      width: b.width,
      contentLeft: b.left + parseFloat(style.paddingLeft),
      contentRight: b.right - parseFloat(style.paddingRight),
      barRight: b.right,
      leadMax,
      lead: { left: box(lead).left, right: box(lead).right, top: box(lead).top, bottom: box(lead).bottom },
      cut: name.scrollWidth > name.clientWidth,
      nameShown: name.clientWidth,
      nameFull: name.scrollWidth,
      parts,
      view: view ? { left: box(view).left, right: box(view).right, top: box(view).top } : null,
      chooser: chooser ? { right: box(chooser).right, top: box(chooser).top } : null,
      nameToStats: statsText.left - nameText.right,
      statsToView: viewText && viewText.top === statsText.top ? viewText.left - statsText.right : null,
      basis: parseFloat(getComputedStyle(host).getPropertyValue("--diff-file-lead-basis")),
    };
  });
}`;

const server = /** @type {import("node:http").Server} */ (await serve());
const { port } = /** @type {import("node:net").AddressInfo} */ (server.address());
/** @type {Awaited<ReturnType<typeof launchChrome>> | undefined} */
let chrome;
// In the page: which files are seen, with the file at *index* waiting, or none (-1).
const SEEN = `(waiting, index) => {
  const files = [...document.querySelectorAll("#host .diff-file")];
  files.forEach((file, at) => file.classList.toggle(waiting, at === index));
  return files.map((file) => {
    const style = getComputedStyle(file);
    return style.visibility === "visible" && style.opacity !== "0";
  });
}`;
const { WAITING_CLASS } = await import(path.join(DIFF, "diff-markdown.js"));
const measured = [];
try {
  chrome = await launchChrome(/** @type {string} */ (process.env.CHROME_BIN), {
    profiles: /** @type {string} */ (process.env.CHROME_PROFILES),
    width: 1200,
    height: 1000,
  });
  await chrome.send("Page.enable");
  await chrome.send("Page.navigate", { url: `http://127.0.0.1:${port}/` });
  await chrome.waitFor(
    "document.readyState === 'complete' && !!window.metabrowser?.filterControls",
  );
  const mounted = await chrome.evaluate(`(${MOUNT})(${JSON.stringify(BARS)})`);
  check("every bar is drawn", mounted === BARS.length, String(mounted));
  await chrome.evaluate("document.fonts.ready.then(() => true)");
  const seen = (index) => chrome.evaluate(`(${SEEN})(${JSON.stringify(WAITING_CLASS)}, ${index})`);
  const waiting = 1;
  check(
    "a waiting file and the files before it are seen, and none after it",
    JSON.stringify(await seen(waiting)) === JSON.stringify(BARS.map((_bar, at) => at <= waiting)),
  );
  check("every file is seen once none waits", (await seen(-1)).every(Boolean));
  for (const width of BAR_WIDTHS) {
    const bars = await chrome.evaluate(`(${MEASURE})(${width})`);
    measured.push({ width, bars });
    if (SHOTS) {
      const shot = await chrome.send("Page.captureScreenshot", { format: "png" });
      fs.writeFileSync(path.join(SHOTS, `bars-${width}.png`), Buffer.from(shot.data, "base64"));
    }
    for (const bar of bars) {
      const at = `${bar.id} at ${width} px`;
      // Five-digit stats need more than the narrowest bar holds beside the name's other
      // parts, so that bar is held down to 199 px.
      if (bar.id === "wide-stats" && width < 199) {
        continue;
      }
      check(`${at}: the bar is the width asked`, Math.abs(bar.width - width) < TOLERANCE_PX);
      const outside = bar.parts.filter(
        (part) =>
          part.right > bar.contentRight + TOLERANCE_PX ||
          part.left < bar.contentLeft - TOLERANCE_PX,
      );
      check(
        `${at}: no part ends past the bar's content edge`,
        outside.length === 0,
        JSON.stringify(outside),
      );
      const covered = [];
      for (const [index, part] of bar.parts.entries()) {
        for (const other of bar.parts.slice(index + 1)) {
          const across = Math.min(part.right, other.right) - Math.max(part.left, other.left);
          const down = Math.min(part.bottom, other.bottom) - Math.max(part.top, other.top);
          if (across > TOLERANCE_PX && down > TOLERANCE_PX) {
            covered.push(`${part.selector}/${other.selector}`);
          }
        }
      }
      check(`${at}: no two parts cover each other`, covered.length === 0, covered.join(", "));
      const line = bar.contentRight - bar.contentLeft;
      if (bar.view) {
        const viewOnNameLine = bar.view.top < bar.lead.bottom - TOLERANCE_PX;
        check(
          `${at}: View file follows the name's group`,
          viewOnNameLine
            ? bar.view.left >= bar.lead.right - TOLERANCE_PX
            : bar.view.left <= bar.contentLeft + TOLERANCE_PX,
          JSON.stringify({ view: bar.view, lead: bar.lead }),
        );
        if (bar.chooser !== null) {
          // The name is cut only on a line of its own, the group as wide as the line.
          check(
            `${at}: a bar with a chooser cuts its name only on a line of its own`,
            !bar.cut || (!viewOnNameLine && Math.abs(bar.lead.right - bar.contentRight) < 1),
            JSON.stringify({ cut: bar.cut, viewOnNameLine, lead: bar.lead, line }),
          );
        } else if (viewOnNameLine && bar.cut) {
          // Beside View file the name is cut only once the space before View file is gone:
          // the bar's gap, the group's, and the control's pad are what is left of it.
          check(
            `${at}: the space before View file gives way before the name`,
            bar.statsToView !== null && bar.statsToView <= 12 + TOLERANCE_PX,
            String(bar.statsToView),
          );
        } else if (!viewOnNameLine) {
          // View file moves to the next line only where the group would keep less than its
          // basis, or its whole width where that is less, beside it, and the name then has
          // the first line.
          const kept = Math.min(bar.basis, bar.leadMax);
          check(
            `${at}: View file moves to the next line only below the group's basis`,
            bar.view.right - bar.view.left + kept + 4 > line - TOLERANCE_PX &&
              (!bar.cut || Math.abs(bar.lead.right - bar.contentRight) < 1),
            JSON.stringify({ kept, line, lead: bar.lead, view: bar.view }),
          );
        }
      }
      if (bar.chooser !== null) {
        check(
          `${at}: the chooser ends the bar at its end pad`,
          Math.abs(bar.chooser.right - bar.contentRight) < TOLERANCE_PX,
          `${bar.barRight - bar.chooser.right} px from the bar's edge`,
        );
      }
      if (width === 1063) {
        check(`${at}: the name is whole`, !bar.cut);
        if (bar.statsToView !== null) {
          // Copy path's slot keeps 28 px between the name and the stats; View file is
          // further from the stats than that, so the stats read with the name.
          check(
            `${at}: the stats are nearer the name than View file is to them`,
            bar.statsToView >= bar.nameToStats + 12,
            `${bar.nameToStats} px to the stats, ${bar.statsToView} px on to View file`,
          );
        }
      }
    }
  }
} finally {
  await chrome?.close();
  server.close();
}
// What was measured, for the case's output.
for (const { width, bars } of measured) {
  process.stderr.write(
    `${width} px: ${bars
      .map(
        (bar) =>
          `${bar.id} name ${bar.nameShown}/${bar.nameFull}` +
          ` gaps ${bar.nameToStats.toFixed(2)}/${bar.statsToView?.toFixed(2) ?? "-"}`,
      )
      .join("; ")}\n`,
  );
}
if (failures.length > 0) {
  process.stderr.write(`${failures.join("\n")}\n`);
  process.exit(1);
}
process.stdout.write(`diff file bar in Chrome: ${checks} checks passed\n`);

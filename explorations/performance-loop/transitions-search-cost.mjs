#!/usr/bin/env node
// The cost of one call of the transition recorder's content search (`hasUseful`), on
// synthetic documents in headless Chrome: four shapes of 10,000 and 40,000 lines, scrolled
// to their end, where the screen holds dense lines; or past them onto a tail that is
// sparse (a heading at the top of the screen, one line at its bottom, lines under
// `pointer-events: none`) or blank. It measures no product and takes no lock; it is how
// the search's bounds and its hit-test bound were set (README, "Transition Navigation
// Scenario", **How content is found**).
//
//   node explorations/performance-loop/transitions-search-cost.mjs [--recorder FILE]
//     [--calls 20] [--profile DIR]
//
// `--recorder` loads another copy of transitions-recorder.mjs, such as an older
// revision's from `git show`, so two searches can be read side by side. Each figure is the
// median of `--calls` calls, in ms; the machine's load moves the values, not the ratios.
// A cell says `miss` when the search did not find what is on screen, and `cut` when it
// stopped at its hit-test bound. Beside the time, the last call's counts, which load does
// not move: the walk's visits (v) and texts measured (t), the hit test's points (p) and
// its work (w, revision 6's bound), and the characters measured (c). An older recorder
// leaves out the counts it does not keep.
import http from "node:http";
import os from "node:os";
import path from "node:path";
import { parseArgs } from "node:util";

const { values } = parseArgs({
  options: {
    recorder: { type: "string" },
    calls: { type: "string", default: "20" },
    profile: { type: "string" },
  },
});
const recorderPath = path.resolve(
  values.recorder ?? path.join(import.meta.dirname, "transitions-recorder.mjs"),
);
const { launchBrowser, driver } = await import(recorderPath);
const calls = Number.parseInt(values.calls, 10);

const PAGE = `<!doctype html><html><head><meta charset="utf-8"><style>
body { margin: 0; font: 13px monospace; }
#preview-pane { min-height: 500px; }
td { padding: 0 4px; }
</style></head><body><div id="preview-pane"><div data-active-view="true" id="view"></div></div></body></html>`;

// Each shape builds `n` lines of text in the view.
const SHAPES = {
  div: "one <div> per line",
  spans: "lines of 8 highlighted spans",
  table: "table rows of 3 cells",
  sections: "sections of 50 lines",
};
// What follows the lines, scrolled to the end, and whether the screen then shows content.
const TAILS = {
  dense: ["", true],
  sparseTop: [
    '<div style="height:900px"><h1 style="margin:8px 40px;font-size:20px">A heading at the top</h1></div>',
    true,
  ],
  sparseBottom: [
    '<div style="height:900px;position:relative"><div style="position:absolute;bottom:20px;left:40px">the only line on screen</div></div>',
    true,
  ],
  pointerNone: [
    `<div style="pointer-events:none">${Array.from({ length: 60 }, (_, i) => `<div>tail ${i}</div>`).join("")}</div>`,
    true,
  ],
  blank: ['<div style="height:3000px"></div>', false],
};
const build = `(shape, n, tail) => {
  const view = document.getElementById("view");
  const f = document.createDocumentFragment();
  const line = (i) => {
    const d = document.createElement("div");
    if (shape === "spans") {
      for (let k = 0; k < 8; k++) { const s = document.createElement("span"); s.className = "hljs-k" + k; s.textContent = "tok" + k + "_" + i + " "; d.appendChild(s); }
    } else {
      d.textContent = "line " + i + " of the document";
    }
    return d;
  };
  if (shape === "table") {
    const t = document.createElement("table");
    for (let i = 0; i < n; i++) { const tr = t.insertRow(); for (let k = 0; k < 3; k++) { tr.insertCell().textContent = "cell " + k + " row " + i; } }
    f.appendChild(t);
  } else if (shape === "sections") {
    for (let i = 0; i < n; i += 50) { const s = document.createElement("section"); for (let k = i; k < Math.min(n, i + 50); k++) { s.appendChild(line(k)); } f.appendChild(s); }
  } else {
    for (let i = 0; i < n; i++) { f.appendChild(line(i)); }
  }
  const t = document.createElement("div"); t.innerHTML = tail; f.appendChild(t);
  view.replaceChildren(f);
}`;

const server = http.createServer((_req, res) => {
  res.writeHead(200, { "content-type": "text/html", "cache-control": "no-store" });
  res.end(PAGE);
});
await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
const profileDir = path.resolve(
  values.profile ?? path.join(os.tmpdir(), `transitions-search-cost-${process.pid}`),
);
const browser = await launchBrowser({
  profileDir,
  extraArgs: process.platform === "linux" ? ["--no-sandbox"] : [],
});
try {
  const d = driver(browser);
  await d.navigate(`http://127.0.0.1:${server.address().port}/`);
  await d.waitFor("!!window.__tr && !!document.getElementById('view')", 20000);
  console.log(
    `recorder ${path.relative(process.cwd(), recorderPath)}; median of ${calls} calls, ms`,
  );
  console.log(`| Document | Lines | ${Object.keys(TAILS).join(" | ")} |`);
  console.log(
    `| --- | ---: | ${Object.keys(TAILS)
      .map(() => "---:")
      .join(" | ")} |`,
  );
  for (const [shape, label] of Object.entries(SHAPES)) {
    for (const n of [10000, 40000]) {
      const cells = [];
      for (const [tail, shown] of Object.values(TAILS)) {
        const r = await d.evaluate(`(async () => {
          (${build})(${JSON.stringify(shape)}, ${n}, ${JSON.stringify(tail)});
          await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));
          const doc = document.scrollingElement;
          doc.scrollTop = doc.scrollHeight;
          await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));
          const view = document.getElementById("view");
          const times = [];
          let found = null;
          for (let i = 0; i < ${calls}; i++) { const t = performance.now(); found = window.__tr.hasUseful(view); times.push(performance.now() - t); }
          times.sort((a, b) => a - b);
          const s = window.__tr.lastSearch ?? {};
          return { ms: times[Math.floor(times.length / 2)], found, cut: s.truncated === true, s };
        })()`);
        const counts = [
          ["v", "visits"],
          ["t", "texts"],
          ["p", "points"],
          ["w", "work"],
          ["c", "chars"],
        ]
          .filter(([, k]) => typeof r.s[k] === "number")
          .map(([l, k]) => `${l}${r.s[k]}`)
          .join(" ");
        cells.push(
          `${r.ms.toFixed(1)}${r.found === shown ? "" : " miss"}${r.cut ? " cut" : ""}${counts ? ` (${counts})` : ""}`,
        );
      }
      console.log(`| ${label} | ${n} | ${cells.join(" | ")} |`);
    }
  }
} finally {
  await browser.close();
  server.close();
}

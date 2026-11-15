#!/usr/bin/env node
// The cost of one call of the transition recorder's content search (`hasUseful`), on
// synthetic documents in headless Chrome: four shapes of 2,000 to 40,000 lines, read at
// the top, scrolled to the end, and scrolled past every line onto blank space. It measures
// no product and takes no lock; it is how the search's bounds were set (README,
// "Transition Navigation Scenario", **How content is found**).
//
//   node explorations/performance-loop/transitions-search-cost.mjs [--recorder FILE]
//     [--calls 20] [--profile DIR]
//
// `--recorder` loads another copy of transitions-recorder.mjs, such as an older
// revision's from `git show`, so two searches can be read side by side. Each figure is the
// median of `--calls` calls, in ms; the machine's load moves the values, not the ratios.
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
  if (tail) { const blank = document.createElement("div"); blank.style.height = "3000px"; f.appendChild(blank); }
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
  console.log(
    "| Document | Lines | Top | End | Past the end | Found at the end | Search at the end |",
  );
  console.log("| --- | ---: | ---: | ---: | ---: | --- | --- |");
  for (const [shape, label] of Object.entries(SHAPES)) {
    for (const n of [2000, 10000, 40000]) {
      const cells = [];
      let found = null;
      let search = null;
      for (const where of ["top", "end", "past"]) {
        const r = await d.evaluate(`(async () => {
          (${build})(${JSON.stringify(shape)}, ${n}, ${where === "past"});
          await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));
          const doc = document.scrollingElement;
          doc.scrollTop = ${where === "top" ? 0 : where === "end" ? "doc.scrollHeight - innerHeight" : "doc.scrollHeight"};
          await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));
          const view = document.getElementById("view");
          const times = [];
          let found = null;
          for (let i = 0; i < ${calls}; i++) { const t = performance.now(); found = window.__tr.hasUseful(view); times.push(performance.now() - t); }
          times.sort((a, b) => a - b);
          return { ms: times[Math.floor(times.length / 2)], found, search: window.__tr.lastSearch ?? null };
        })()`);
        cells.push(r.ms.toFixed(2));
        if (where === "end") {
          found = r.found;
          search = r.search;
        }
      }
      const s = search
        ? `${search.visits} visits, ${search.texts} texts${search.bounded ? ", bounded" : ""}${search.points ? `, ${search.points} points` : ""}`
        : "n/a";
      console.log(`| ${label} | ${n} | ${cells.join(" | ")} | ${found} | ${s} |`);
    }
  }
} finally {
  await browser.close();
  server.close();
}

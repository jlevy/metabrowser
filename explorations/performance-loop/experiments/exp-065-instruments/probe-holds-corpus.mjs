// Probe: the PR page's holds in headless Chrome, read from the app's own perf spans.
import { launch } from "./cdp2.mjs";

const base = process.argv[2] ?? "http://127.0.0.1:8965";
const count = Number(process.argv[3] ?? 6);
const b = await launch();
const markdownUrls = new Set();
b.on((msg) => {
  if (msg.method === "Network.requestWillBeSent") {
    const url = msg.params.request.url;
    if (url.includes("/api/plugin/github/pull-markdown")) {
      markdownUrls.add(url.replace(base, ""));
    }
  }
});
await b.send("Network.enable");
await b.send("Page.enable");
await b.send("Page.navigate", { url: `${base}/pulls` });
for (let i = 0; i < 150; i += 1) {
  if ((await b.evaluate("document.querySelectorAll('a.github-pulls-row').length")) > count) {
    break;
  }
  await b.sleep(200);
}
await b.sleep(1500);
await b.evaluate(`(() => {
  window.__holds = []; const seen = new Set();
  const labels = new Set(["githubPull:firstPaintHold", "githubPull:changesHold", "githubPulls:openingHold", "githubPulls:lateRowsHold"]);
  setInterval(() => {
    for (const s of window.metabrowser.perf.snapshot().raw_measure) {
      const key = s.label + s.ts + JSON.stringify(s.meta);
      if (labels.has(s.label) && !seen.has(key)) { seen.add(key); window.__holds.push({ label: s.label, ...s.meta }); }
    }
  }, 50);
  return true;
})()`);
const chip = await b.evaluate(
  `(() => { const e = document.querySelector('.github-pulls-filters .chip[data-chip-value="closed"]'); const r = e.getBoundingClientRect(); return {x: r.left + r.width / 2, y: r.top + r.height / 2}; })()`,
);
await b.click(chip.x, chip.y);
for (let i = 0; i < 300; i += 1) {
  if (
    await b.evaluate(
      `!!document.querySelector('#tab-pulls ul.github-pulls-list[data-filter="closed"]') && !!document.querySelector('a.github-pulls-row[data-number="348"]')`,
    )
  ) {
    break;
  }
  await b.sleep(200);
}
await b.sleep(1500);
const numbers = (process.env.SUBJECTS ?? "353,351,349,348").split(",");
async function clickAt(selector) {
  await b.evaluate(
    `document.querySelector(${JSON.stringify(selector)})?.scrollIntoView({block: 'center'})`,
  );
  await b.sleep(300);
  const box = await b.evaluate(
    `(() => { const e = document.querySelector(${JSON.stringify(selector)}); if (!e) return null; const r = e.getBoundingClientRect(); return {x: r.left + Math.min(60, r.width / 2), y: r.top + r.height / 2}; })()`,
  );
  if (box) {
    await b.click(box.x, box.y);
  }
  return box !== null;
}
const scrolls = [];
for (const n of numbers) {
  await clickAt(`a.github-pulls-row[data-number="${n}"]`);
  await b.sleep(2500);
  const tab = await b.evaluate(
    `(() => { const t = [...document.querySelectorAll('.tab-btn')].find((a) => a.textContent === 'Changes'); if (!t) return null; const r = t.getBoundingClientRect(); return {x: r.left + r.width/2, y: r.top + r.height/2}; })()`,
  );
  if (tab) {
    await b.click(tab.x, tab.y);
    await b.sleep(2500);
  }
  const conv = await b.evaluate(
    `(() => { const t = [...document.querySelectorAll('.tab-btn')].find((a) => a.textContent === 'Conversation'); if (!t) return null; const r = t.getBoundingClientRect(); return {x: r.left + r.width/2, y: r.top + r.height/2}; })()`,
  );
  if (conv) {
    await b.click(conv.x, conv.y);
    await b.sleep(800);
  }
  // Read down the conversation before the next click: the next page replaces a scrolled one.
  scrolls.push(
    await b.evaluate(
      `(() => { const p = document.querySelector(".preview-pane"); p.scrollTop = Math.min(1500, p.scrollHeight - p.clientHeight); return Math.round(p.scrollTop); })()`,
    ),
  );
  await b.sleep(300);
}
for (const step of ["back", "back", "forward"]) {
  await b.evaluate(`history.${step}()`);
  await b.sleep(1500);
}
await b.sleep(500);
const holds = await b.evaluate("window.__holds");
const stuck = await b.evaluate(
  "document.querySelectorAll('.github-pull-body-holding, .github-pull-diff-holding').length",
);
console.error("STUCK", stuck);
console.log(JSON.stringify({ numbers, scrolls, holds, markdownUrls: [...markdownUrls] }));
b.close();

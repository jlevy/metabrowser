// The Folder Overview's left edge, measured in a real headless Chrome against a live
// `metab` server. tests/test_folder_overview_alignment.py starts the server, waits until
// it serves, owns the profile directory, and stops this process's whole group, Chrome
// included, however the run ends.
//
//   node tests/dom/folder-overview-alignment-chrome.mjs http://127.0.0.1:<port> <profile dir>
//
// Every label the Overview host draws — each panel heading's toggle and File Overview's
// Details toggle — starts on the active tab's label at every pane width, so the labels
// line up with each other and never step as the window widens. The section rules and the
// README card keep sharing one outer edge. The README's own prose keeps KPress's
// responsive inset inside the card, which this does not measure.
//
// Where text starts is layout, which only a browser computes: the column comes from
// container queries on the pane's width, a token, and KPress's stylesheet together.
import assert from "node:assert/strict";
import path from "node:path";

const HERE = import.meta.dirname;
const { launchBrowser, driver } = await import(
  path.resolve(HERE, "../../explorations/performance-loop/transitions-recorder.mjs")
);

const [base, profileDir] = process.argv.slice(2);
if (!base || !profileDir) {
  throw new Error("usage: folder-overview-alignment-chrome.mjs <server base URL> <profile dir>");
}

// Window widths that put the preview pane in each of the three KPress document bands,
// beside the navigation column: under 48 rem, 48 to 75 rem, and 75 rem or more. The
// labels drifted in the two wider bands, so each band is measured at least once and the
// run fails if a change to the navigation's width leaves one unmeasured.
const WIDTHS = [900, 1200, 1440, 1920, 2560];
const BANDS = ["narrow", "regular", "wide"];
// Text positions are fractional; a difference under half a pixel is not a different edge.
const TOLERANCE_PX = 0.5;

const READY = `(() => {
  const panels = [...document.querySelectorAll(".folder-overview-panel")].filter((p) => !p.hidden);
  return panels.length === 2
    && panels.every((p) => p.querySelector(".folder-overview-panel-toggle"))
    && !!document.querySelector(".folder-overview-panel-document .kpress-prose p")
    && !!document.querySelector(".file-type-summary-details-toggle");
})()`;

// The left edge of an element's first line of text, where a reader sees it start.
const MEASURE = `(() => {
  const textX = (element) => {
    const walker = document.createTreeWalker(element, NodeFilter.SHOW_TEXT, {
      acceptNode: (node) => (node.textContent.trim() ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_SKIP),
    });
    const text = walker.nextNode();
    if (!text) {
      return null;
    }
    const range = document.createRange();
    range.selectNodeContents(text);
    return range.getClientRects()[0]?.x ?? null;
  };
  const pane = document.querySelector(".preview-pane");
  const rem = Number.parseFloat(getComputedStyle(document.documentElement).fontSize);
  const paneRem = pane.clientWidth / rem;
  const tab = document.querySelector(".preview-pane > .tab-bar .tab-btn.active");
  const labels = [
    ...[...document.querySelectorAll(".folder-overview-panel")]
      .filter((panel) => !panel.hidden)
      .map((panel) => {
        const toggle = panel.querySelector(".folder-overview-panel-toggle");
        return { name: toggle.textContent.trim(), x: textX(toggle) };
      }),
    { name: "Details", x: textX(document.querySelector(".file-type-summary-details-toggle")) },
  ];
  const headings = [...document.querySelectorAll(".folder-overview-panel-heading")].map(
    (heading) => heading.getBoundingClientRect().x,
  );
  const card = document.querySelector(".folder-overview-panel-document .kpress-doc");
  return {
    paneX: pane.getBoundingClientRect().x,
    band: paneRem < 48 ? "narrow" : paneRem < 75 ? "regular" : "wide",
    tab: tab ? { name: tab.textContent.trim(), x: textX(tab) } : null,
    labels,
    headings,
    cardX: card.getBoundingClientRect().x,
  };
})()`;

let checks = 0;
const bands = new Set();
const offsets = [];
const browser = await launchBrowser({
  profileDir,
  width: WIDTHS[0],
  height: 900,
  extraArgs: process.platform === "linux" ? ["--no-sandbox"] : [],
});
const d = driver(browser);
try {
  await browser.page.send("Page.navigate", { url: `${base}/view/` });
  for (const width of WIDTHS) {
    await browser.page.send("Emulation.setDeviceMetricsOverride", {
      width,
      height: 900,
      deviceScaleFactor: 1,
      mobile: false,
    });
    assert.ok(await d.waitFor(READY, 20000), `${width}px: the Overview never finished mounting`);
    // Two frames, so layout reflects the new width before anything is read.
    assert.ok(await d.frames(2), `${width}px: two animation frames did not arrive`);
    const m = await d.evaluate(MEASURE);
    bands.add(m.band);
    assert.equal(m.tab?.name, "Overview", `${width}px: the active preview tab`);
    const at = `${width}px (${m.band} band)`;

    // Every label starts on the Overview tab's label.
    for (const label of m.labels) {
      assert.ok(
        label.x !== null && Math.abs(label.x - m.tab.x) < TOLERANCE_PX,
        `${at}: ${label.name} starts at ${label.x}, the Overview tab's label at ${m.tab.x}`,
      );
      checks += 1;
    }
    // The section rules and the README card share one outer edge.
    for (const x of m.headings) {
      assert.ok(
        Math.abs(x - m.cardX) < TOLERANCE_PX,
        `${at}: a section rule starts at ${x}, the README card at ${m.cardX}`,
      );
      checks += 1;
    }
    offsets.push({ at, offset: m.labels[0].x - m.paneX });
  }
  // The indent from the pane is one value at every width, not one per band.
  for (const band of BANDS) {
    assert.ok(bands.has(band), `no width put the pane in the ${band} band: ${[...bands]}`);
  }
  for (const { at, offset } of offsets) {
    assert.ok(
      Math.abs(offset - offsets[0].offset) < TOLERANCE_PX,
      `the labels sit ${offset}px into the pane at ${at}, ${offsets[0].offset}px at ${offsets[0].at}`,
    );
    checks += 1;
  }
} finally {
  // Stops every Chrome process of the profile, then removes the profile.
  await browser.close();
}
console.log(`folder overview alignment: ${checks} checks passed`);

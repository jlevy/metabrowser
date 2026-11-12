// The staged view's font wait in a real engine: a cold landing on a plain document, then,
// in the same page, a document set in faces the first did not use. Neither document's
// paragraphs may move once it is shown.
//
//   CHROME_BIN=/path/to/chrome node tests/dom/staged-fonts-chrome.mjs http://127.0.0.1:PORT
//
// tests/test_staged_fonts_chrome.py serves plain.md and italic.md from a fresh server.
// The HTTP cache is off and every request waits 40 ms, so each face arrives after the
// stage could have been shown. Remembering the first document's faces let the italic one
// swap faces after it was shown (layout shift 0.150); before that, reading the font set's
// status let the first document swap too. Whether the browserless DOM asks for the right
// faces is tests/dom/staged-fonts-behavior.js; this is whether nothing moves.
import { launchChrome } from "./chrome-session.mjs";

const base = process.argv[2];
const failures = [];
let checks = 0;
const check = (label, ok, detail = "") => {
  checks += 1;
  if (!ok) {
    failures.push(`${label}${detail ? `: ${detail}` : ""}`);
  }
};

// Layout shifts with no input, from the document's start.
const PROBE = `(() => {
  window.__shifts = [];
  new PerformanceObserver((list) => {
    for (const entry of list.getEntries()) {
      if (!entry.hadRecentInput) window.__shifts.push({ at: entry.startTime, value: entry.value });
    }
  }).observe({ type: "layout-shift", buffered: true });
})();`;

// In the page: wait until *marker*'s document is shown (out of the stage), then follow its
// paragraphs for *ms* and report how far each moved and the shifts since it was shown.
const FOLLOW = `async (marker, ms, navigate) => {
  if (navigate) {
    void navigateToPath(navigate);
  }
  const shownView = () => {
    const view = document.querySelector('#preview-pane [data-active-view="true"]');
    return view && !view.closest(".preview-file-stage") && view.textContent.includes(marker)
      ? view
      : null;
  };
  const deadline = performance.now() + 15000;
  while (!shownView() && performance.now() < deadline) {
    await new Promise((resolve) => requestAnimationFrame(resolve));
  }
  const view = shownView();
  if (!view) {
    return { shown: false };
  }
  const shownAt = performance.now();
  const paragraphs = [...view.querySelectorAll("p")].slice(0, 40);
  const lows = paragraphs.map(() => Infinity);
  const highs = paragraphs.map(() => -Infinity);
  while (performance.now() - shownAt < ms) {
    paragraphs.forEach((p, i) => {
      const top = p.getBoundingClientRect().top;
      lows[i] = Math.min(lows[i], top);
      highs[i] = Math.max(highs[i], top);
    });
    await new Promise((resolve) => requestAnimationFrame(resolve));
  }
  const moved = paragraphs.map((_, i) => highs[i] - lows[i]);
  return {
    shown: true,
    paragraphs: paragraphs.length,
    moved: Math.round(Math.max(0, ...moved) * 100) / 100,
    shift: Math.round(window.__shifts.filter((s) => s.at >= shownAt).reduce((sum, s) => sum + s.value, 0) * 10000) / 10000,
    faces: [...document.fonts].map((f) => f.family + " " + f.weight + " " + f.style + " " + f.status),
  };
}`;

async function main() {
  const bin = process.env.CHROME_BIN;
  if (!bin || !base) {
    throw new Error("CHROME_BIN and a server address are required");
  }
  const browser = await launchChrome(bin);
  try {
    await browser.send("Page.enable");
    await browser.send("Network.enable");
    await browser.send("Network.setCacheDisabled", { cacheDisabled: true });
    await browser.send("Network.emulateNetworkConditions", {
      offline: false,
      latency: 40,
      downloadThroughput: -1,
      uploadThroughput: -1,
    });
    await browser.send("Page.addScriptToEvaluateOnNewDocument", { source: PROBE });
    await browser.send("Page.navigate", { url: `${base}/view/plain.md` });
    const landing = await browser.evaluate(`(${FOLLOW})("PLAIN-DOCUMENT", 1500, null)`);
    check("the landing's document is shown", landing.shown, JSON.stringify(landing));
    check(
      "the landing's paragraphs do not move once it is shown",
      landing.shown && landing.moved <= 0.5 && landing.shift === 0,
      JSON.stringify(landing),
    );
    const italic = await browser.evaluate(`(${FOLLOW})("ITALIC-DOCUMENT", 1500, "italic.md")`);
    check("the second document is shown", italic.shown, JSON.stringify(italic));
    check(
      "a document set in faces the first did not use does not move once it is shown",
      italic.shown && italic.moved <= 0.5 && italic.shift === 0,
      JSON.stringify(italic),
    );
  } finally {
    await browser.close();
  }
}

main()
  .catch((error) => {
    failures.push(`staged fonts session threw: ${error?.stack || error}`);
  })
  .then(() => {
    if (failures.length > 0) {
      console.error(failures.join("\n"));
      process.exitCode = 1;
    } else {
      console.log(`staged fonts in Chrome: ${checks} checks passed`);
    }
  });

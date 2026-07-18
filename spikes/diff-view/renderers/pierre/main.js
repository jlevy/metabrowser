import { bench, countNodes, done, fail, fetchText, quietLongTasks } from "../common/bench.js";
import { FileDiff, processFile } from "./dist/bundle.js";

const BASE = "../../fixtures/out/";
const host = /** @type {HTMLElement} */ (document.querySelector("#host"));
const SCENARIOS = [
  ["small", "src/service.py"],
  ["medium", "src/big_refactor.py"],
  ["huge", "package-lock.json"],
];

function makeFileDiff() {
  return new FileDiff({
    themeType: "light",
    diffStyle: "unified",
    preferredHighlighter: "shiki-js",
  });
}

/** @param {string} label */
async function settle(label) {
  const settleMs = await quietLongTasks(600, 60000);
  window.__RESULTS.push({
    name: `${label}:settle`,
    renderMs: settleMs,
    domNodes: countNodes(document),
  });
}

try {
  const data = {};
  for (const [id] of SCENARIOS) {
    data[id] = {
      oldText: await fetchText(`${BASE}contents_${id}_old.txt`),
      newText: await fetchText(`${BASE}contents_${id}_new.txt`),
      patchText: await fetchText(`${BASE}unified_${id}.diff`),
    };
  }

  // Server-precomputed patch path (Metabrowser's architecture): no client diffing.
  for (const [id] of SCENARIOS) {
    await bench(`pierre:${id}:patch`, () => {
      host.textContent = "";
      const container = document.createElement("div");
      host.append(container);
      const metadata = processFile(data[id].patchText, { isGitDiff: true, throwOnError: true });
      makeFileDiff().render({ fileDiff: metadata, fileContainer: container });
    });
    await settle(`pierre:${id}:patch`);
  }

  // Contents path (library computes the diff with jsdiff client-side).
  for (const [id, path] of SCENARIOS.slice(0, 2)) {
    await bench(`pierre:${id}:contents`, () => {
      host.textContent = "";
      const container = document.createElement("div");
      host.append(container);
      makeFileDiff().render({
        oldFile: { name: path, contents: data[id].oldText },
        newFile: { name: path, contents: data[id].newText },
        fileContainer: container,
      });
    });
    await settle(`pierre:${id}:contents`);
  }

  // Huge with plain-text language: separates jsdiff cost from highlighting cost.
  await bench("pierre:huge:contents_plain", () => {
    host.textContent = "";
    const container = document.createElement("div");
    host.append(container);
    makeFileDiff().render({
      oldFile: { name: "package-lock.json", contents: data.huge.oldText, lang: "text" },
      newFile: { name: "package-lock.json", contents: data.huge.newText, lang: "text" },
      fileContainer: container,
    });
  });
  await settle("pierre:huge:contents_plain");

  done();
} catch (err) {
  fail(err);
}

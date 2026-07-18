// Hybrid approach: @git-diff-view/core computes the diff model; a small custom
// table builder owns the DOM (the library has no vanilla DOM renderer).
import { bench, done, fail, fetchText } from "../common/bench.js";
import { DiffFile } from "./dist/bundle.js";

const BASE = "../../fixtures/out/";
const host = /** @type {HTMLElement} */ (document.querySelector("#host"));
const SCENARIOS = [
  ["small", "src/service.py"],
  ["medium", "src/big_refactor.py"],
  ["huge", "package-lock.json"],
];

/**
 * @param {HTMLElement} container
 * @param {InstanceType<typeof DiffFile>} diffFile
 */
function renderTable(container, diffFile) {
  const table = document.createElement("table");
  table.className = "dv-table";
  const tbody = document.createElement("tbody");
  const total = diffFile.unifiedLineLength;
  for (let i = 0; i < total; i += 1) {
    const item = diffFile.getUnifiedLine(i);
    if (!item || item.isHidden) continue;
    const value = item.value ?? "";
    const tr = document.createElement("tr");
    if (item.oldLineNumber && item.newLineNumber) tr.className = "dv-ctx";
    else if (item.newLineNumber) tr.className = "dv-add";
    else tr.className = "dv-del";
    const a = document.createElement("td");
    a.className = "dv-num";
    a.textContent = item.oldLineNumber ? String(item.oldLineNumber) : "";
    const b = document.createElement("td");
    b.className = "dv-num";
    b.textContent = item.newLineNumber ? String(item.newLineNumber) : "";
    const s = document.createElement("td");
    s.className = "dv-sign";
    s.textContent = tr.className === "dv-add" ? "+" : tr.className === "dv-del" ? "-" : " ";
    const code = document.createElement("td");
    code.className = "dv-code";
    code.textContent = value.replace(/\n$/, "");
    tr.append(a, b, s, code);
    tbody.append(tr);
  }
  table.append(tbody);
  container.append(table);
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
  for (const [id, path] of SCENARIOS) {
    /** @type {InstanceType<typeof DiffFile>} */
    let diffFile;
    await bench(`gdv:${id}:core`, () => {
      diffFile = DiffFile.createInstance({
        oldFile: { fileName: path, content: data[id].oldText },
        newFile: { fileName: path, content: data[id].newText },
        hunks: [data[id].patchText],
      });
      diffFile.initTheme("light");
      diffFile.initRaw();
      diffFile.buildUnifiedDiffLines();
    });
    await bench(`gdv:${id}:dom`, () => {
      host.textContent = "";
      renderTable(host, diffFile);
    });
  }
  // Syntax model cost alone (lowlight/highlight.js path), medium fixture.
  await bench("gdv:medium:syntax_init", () => {
    const diffFile = DiffFile.createInstance({
      oldFile: { fileName: "src/big_refactor.py", content: data.medium.oldText },
      newFile: { fileName: "src/big_refactor.py", content: data.medium.newText },
      hunks: [data.medium.patchText],
    });
    diffFile.initTheme("light");
    diffFile.initSyntax();
    diffFile.buildUnifiedDiffLines();
  });
  done();
} catch (err) {
  fail(err);
}

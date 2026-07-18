import { bench, done, fail, fetchJson } from "../common/bench.js";
import { renderChangeset, renderFilePatch } from "./diff_render.js";

const BASE = "../../fixtures/out/";
const host = /** @type {HTMLElement} */ (document.querySelector("#host"));

try {
  const patches = {};
  for (const id of ["small", "medium", "huge"]) {
    patches[id] = await fetchJson(`${BASE}fp_${id}.json`);
  }
  for (const id of ["small", "medium", "huge"]) {
    await bench(`custom:${id}`, () => {
      host.textContent = "";
      renderFilePatch(host, patches[id], { maxRows: Infinity });
    });
  }
  await bench("custom:huge_gated", () => {
    host.textContent = "";
    renderFilePatch(host, patches.huge, { maxRows: 1500 });
  });
  const set = await fetchJson(`${BASE}set50.json`);
  await bench("custom:set50_initial", () => {
    host.textContent = "";
    renderChangeset(host, set.files, { eager: 8 });
  });
  await bench("custom:set50_all", () => {
    host.textContent = "";
    renderChangeset(host, set.files, { eager: Infinity });
  });
  done();
} catch (err) {
  fail(err);
}

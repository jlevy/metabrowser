import { bench, done, fail, fetchText } from "../common/bench.js";

const BASE = "../../fixtures/out/";
const host = /** @type {HTMLElement} */ (document.querySelector("#host"));

try {
  const markup = {};
  for (const id of ["small", "medium", "huge"]) {
    markup[id] = await fetchText(`${BASE}html_${id}.html`);
  }
  for (const id of ["small", "medium", "huge"]) {
    await bench(`server_html:${id}`, () => {
      host.textContent = "";
      host.insertAdjacentHTML("beforeend", markup[id]);
    });
  }
  done();
} catch (err) {
  fail(err);
}

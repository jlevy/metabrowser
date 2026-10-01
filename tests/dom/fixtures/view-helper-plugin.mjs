// A third-party plugin as an SDK 0.7 plugin may be written, for
// tests/dom/plugin-view-helpers-session.js: it calls a documented view helper while its
// module evaluates, from a view's render, and from a click handler. The session gives
// it `window.viewHelperFixtureLog` to say what each call produced.

const mb = window.metabrowser;
const log = window.viewHelperFixtureLog;

/** @param {string} when @param {{innerHTML: string}} host @param {string} content */
function drawSource(when, host, content) {
  mb.renderSourceView(host, { path: "notes.py", content });
  const lines = /aria-valuemax="(\d+)"/.exec(host.innerHTML)?.[1] ?? "no";
  log.push(`${when}: a Source view with a gutter of ${lines} lines`);
}

drawSource("module evaluation", window.document.createElement("div"), "one\n");

mb.registerView("fixture-kind", "fixture", {
  render(container) {
    drawSource("render", container, "one\ntwo\n");
    container.addEventListener("click", () => {
      drawSource("click handler", container, "one\ntwo\nthree\n");
    });
  },
});

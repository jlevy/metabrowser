// A third-party plugin as an SDK 0.7 plugin may be written, for
// tests/dom/plugin-view-helpers-session.js: it calls a documented view helper while its
// module evaluates, from a view's render, and from a click handler. The session gives
// it `window.viewHelperFixtureLog` to say what each call produced.

const mb = window.metabrowser;
const log = window.viewHelperFixtureLog;
if (
  !mb.refChipHtml("<topic>", { copy: false }).includes("&lt;topic&gt;") ||
  mb.ageBucket(0) !== null ||
  mb.ageLabelHtml(0) !== ""
) {
  throw new Error("view presentation helpers were unavailable during plugin evaluation");
}

/** @param {string} when @param {{innerHTML: string}} host @param {string} content */
function drawSource(when, host, content) {
  const template = mb.render("<p>{{title}}</p>{{#tags}}<b>{{.}}</b>{{/tags}}", {
    title: "<card> & text",
    tags: ["one", "<two>"],
  });
  if (template !== "<p>&lt;card&gt; &amp; text</p><b>one</b><b>&lt;two&gt;</b>") {
    throw new Error("the synchronous template helper lost escaping or sections");
  }
  window.viewHelperTemplateLog.push(`${when}: ${template}`);
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

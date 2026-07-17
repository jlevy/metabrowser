const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const repoRoot = path.resolve(process.argv[2]);
const validValues = [
  "0",
  "-45.1%",
  "−45.1%",
  "+12%",
  "1,234.56",
  "-1.234,56%",
  "1234,5",
  ".75",
  ",75%",
];
const invalidValues = [
  "",
  "+",
  "−",
  "%",
  "Q4 12%",
  "12% growth",
  "1,23,456",
  "1.2.3",
  "--12",
  "+-12",
  "12%%",
];

function makeCell(textContent) {
  const attributes = new Map();
  return {
    attributes,
    textContent,
    setAttribute: (name, value) => attributes.set(name, value),
  };
}

const cells = [...validValues, ...invalidValues].map(makeCell);
const container = {
  classList: { add: () => {} },
  innerHTML: "",
  prepend: () => {},
  querySelector: () => null,
  querySelectorAll: (selector) => (selector === ".kpress-table th, .kpress-table td" ? cells : []),
};
let renderedView = null;
const metabrowser = {
  builtins: {},
  escapeHtml: (value) => String(value),
  fetchKpressRender: async () => ({ diagnostics: [], html: "<table></table>" }),
  isLargeTextPreview: () => false,
  kpressInitToc: () => null,
  perf: { measure: (_name, fn) => fn() },
  registerView: (kind, view, renderer) => {
    if (kind === "markdown" && view === "rendered") {
      renderedView = renderer;
    }
  },
  renderTextTruncationWarning: () => "",
  wrapWithCopy: (value) => value,
};
const sandbox = {
  Map,
  Promise,
  console,
  document: { createElement: () => ({ innerHTML: "", firstElementChild: null }) },
  metabrowser,
};
sandbox.window = sandbox;
sandbox.globalThis = sandbox;

vm.createContext(sandbox);
const pluginPath = path.join(repoRoot, "src/metabrowser/builtin_plugins/markdown/index.js");
vm.runInContext(fs.readFileSync(pluginPath, "utf8"), sandbox, { filename: pluginPath });

if (!renderedView) {
  throw new Error("Markdown rendered view was not registered");
}

(async () => {
  await renderedView.render(container, { path: "numbers.md", raw: {} });
  process.stdout.write(
    JSON.stringify({
      invalid: cells
        .slice(validValues.length)
        .filter((cell) => cell.attributes.get("data-kpress-numeric") === "true")
        .map((cell) => cell.textContent),
      valid: cells
        .slice(0, validValues.length)
        .filter((cell) => cell.attributes.get("data-kpress-numeric") === "true")
        .map((cell) => cell.textContent),
    }),
  );
})().catch((error) => {
  process.stderr.write(String(error?.stack || error));
  process.exitCode = 1;
});

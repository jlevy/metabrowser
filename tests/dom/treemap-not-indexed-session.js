// Run the whole production Treemap module for folders the inventory excludes.
// Every rollup/resource boundary fails if called: these envelopes already explain
// why totals are unavailable. Parent navigation and disposal still run normally.
const assert = require("node:assert/strict");
const path = require("node:path");
const { pathToFileURL } = require("node:url");

const emitWarning = process.emitWarning;
process.emitWarning = (warning, ...rest) => {
  if (String(warning).includes("is not specified and it doesn't parse as CommonJS")) {
    return;
  }
  emitWarning.call(process, warning, ...rest);
};

async function main() {
  const { registerTreemap } = await import(
    pathToFileURL(
      path.resolve(__dirname, "../../src/metabrowser/builtin_plugins/folder/treemap.js"),
    )
  );
  const unexpected = (name) => () => {
    throw new Error(`A not-indexed folder must not acquire ${name}`);
  };
  global.window = {
    addEventListener: unexpected("window listeners"),
  };
  global.ResizeObserver = class {
    constructor() {
      unexpected("a resize observer")();
    }
  };
  global.setTimeout = unexpected("a timer");
  let render;
  let tooltipHides = 0;
  const navigation = [];
  const mb = new Proxy(
    {
      registerView(kind, id, view) {
        assert.equal(kind, "folder");
        assert.equal(id, "treemap");
        render = view.render;
      },
      sourceKind: () => "filesystem",
      escapeHtml: (value) =>
        String(value).replaceAll("&", "&amp;").replaceAll('"', "&quot;").replaceAll("<", "&lt;"),
      navigation: { open: (...args) => navigation.push(args) },
      tooltip: { hide: () => tooltipHides++ },
    },
    {
      get(target, name) {
        if (name in target) {
          return target[name];
        }
        return unexpected(String(name))();
      },
    },
  );
  const controls = {
    get: unexpected("rollup controls"),
    mount: unexpected("mounted controls"),
    subscribe: unexpected("a controls subscription"),
  };
  registerTreemap(mb, {}, controls);
  const output = [];
  for (const [reason, folder, expected, parentPath, parentLabel] of [
    [
      "hidden",
      ".hidden",
      "Metabrowser does not index hidden folders, so this one has no file totals.",
      "",
      "/",
    ],
    [
      "symlink",
      "link/nested",
      "Metabrowser does not follow symbolic links when it indexes, so this folder has no file totals here.",
      "link",
      "link/",
    ],
  ]) {
    for (let mount = 0; mount < 2; mount++) {
      const listeners = new Set();
      let removals = 0;
      const parent = {
        addEventListener(type, fn) {
          assert.equal(type, "click");
          listeners.add(fn);
        },
        removeEventListener(type, fn) {
          assert.equal(type, "click");
          assert.equal(listeners.delete(fn), true);
          removals++;
        },
      };
      const container = {
        innerHTML: "",
        querySelector(selector) {
          assert.equal(selector, ".tm-parent-nav");
          assert.ok(this.innerHTML.includes('class="btn parent-nav-btn tm-parent-nav"'));
          return parent;
        },
      };
      const beforeHides = tooltipHides;
      const shown = render(container, { path: folder, raw: { dir: { not_indexed: reason } } });
      const text = container.innerHTML
        .replace(/<[^>]*>/g, " ")
        .replace(/\s+/g, " ")
        .trim();
      assert.ok(text.includes(expected), text);
      assert.ok(container.innerHTML.includes(`aria-label="Zoom out to ${parentLabel}"`));
      assert.ok(!/tm-loading|tm-viewport|tm-rollup-controls/.test(container.innerHTML));
      assert.equal(listeners.size, 1);
      for (const click of listeners) {
        click();
      }
      assert.deepEqual(navigation.at(-1), [{ path: parentPath }, { viewId: "treemap" }]);
      shown.dispose();
      shown.dispose();
      assert.equal(listeners.size, 0);
      assert.equal(removals, 1);
      assert.equal(tooltipHides - beforeHides, 1);
      if (mount === 0) {
        output.push({ reason, text, parent: navigation.at(-1) });
      }
    }
  }
  console.log(
    JSON.stringify({ folders: output, repeatMounts: "clean", rollupResources: 0 }, null, 2),
  );
}
main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});

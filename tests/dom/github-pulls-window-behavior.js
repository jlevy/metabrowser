const assert = require("node:assert/strict");
const path = require("node:path");
const { pathToFileURL } = require("node:url");
(async () => {
  const { createPullsWindow } = await import(
    pathToFileURL(
      path.resolve(__dirname, "../../src/metabrowser/builtin_plugins/github/pulls-window.js"),
    ).href
  );
  const window = createPullsWindow({ estimate: 42, overscan: 40 });
  const rows = Array.from({ length: 5000 }, (_, index) => 5000 - index);
  window.setRows(rows);
  for (const height of [Number.NaN, Number.POSITIVE_INFINITY, 0, -42]) {
    assert.equal(
      window.measure(4950, height),
      false,
      "only finite positive measured heights become spacers",
    );
  }
  assert.equal(window.measure(4950, 1200), true);
  const height = 5000 * 42 + 1200 - 42;
  for (const top of [0, 20_000, height - 800]) {
    const view = window.range(top, top + 700, [5000, 1]);
    const mounted = view.filter((part) => part.kind === "row");
    assert(mounted.length <= 101, "catalog size must not determine mounted row count");
    assert(mounted.some((part) => part.number === 5000));
    assert(mounted.some((part) => part.number === 1));
    const sum = view.reduce(
      (total, part) =>
        total + (part.kind === "gap" ? part.height : part.number === 4950 ? 1200 : 42),
      0,
    );
    assert.equal(sum, height, "expanded rows keep their exact reserved space");
  }
  const oldOffset = window.offset(4000);
  window.setRows([5001, ...rows]);
  assert.equal(
    window.offset(4000),
    oldOffset + 42,
    "a prefix insertion moves a reading anchor by exactly one row",
  );
  assert.equal(window.measure(4950, 1200), false);
  window.setRows(rows.slice(0, 500));
  assert.equal(window.offset(1), null, "filter/window replacement drops absent anchors");
  assert.equal(window.range(0, 700).filter((part) => part.kind === "row").length, 57);
  console.log(
    JSON.stringify({
      catalogRows: 5000,
      mountedRowsBound: 101,
      expandedHeight: 1200,
      protectedAnchors: true,
      prefixAnchorPreserved: true,
    }),
  );
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});

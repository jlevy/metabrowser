// Metabrowser — the in-page half of one exploration run.
//
// devtools/bench_serving.py measures what an HTTP client can see. It cannot
// see the thing this loop is about: when the reader gets a usable tree. That
// is a browser fact, so it is read here, from the page, after a cold load.
//
// Evaluate in the page and hand the printed JSON to `explorations/run.py
// record`. Nothing here depends on a headless driver; see explorations/README.md
// for why the browser half is driven by hand.
//
//   1. explorations/run.py serve --files 100000   -> prints a URL on a fresh port
//   2. load that URL in a browser, wait for the tree
//   3. evaluate this file, copy the JSON
//   4. explorations/run.py record --label <name> --json '<paste>'
(() => {
  const origin = performance.timeOrigin;
  const nav = performance.getEntriesByType("navigation")[0] || {};
  const perf = window.metabrowserPerf ? window.metabrowserPerf.snapshot() : { raw_measure: [] };
  const spans = perf.raw_measure || [];
  const firstOf = (label) => spans.filter((s) => s.label === label)[0] || null;
  const at = (span) => (span ? Math.round(span.ts - origin) : null);
  const took = (span) => (span ? Math.round(span.duration_ms) : null);

  const resources = performance.getEntriesByType("resource");
  const kb = (list) =>
    Math.round(list.reduce((total, r) => total + (r.transferSize || 0), 0) / 1024);
  const vendor = resources.filter((r) => r.name.includes("/static/vendor/"));
  const subtree = resources.filter((r) => r.name.includes("/api/tree?path="));

  // Time to first row is wall clock until the tree has rows a reader can use.
  // Not `load`, which reports a painted shell, and not network idle, which
  // reports a finished scan. The app's own renderTreeNodes:root span is the
  // moment the rows entered the DOM, so it is read rather than re-derived.
  const firstRow = firstOf("renderTreeNodes:root");

  return JSON.stringify({
    dcl_ms: Math.round(nav.domContentLoadedEventEnd || 0),
    load_ms: Math.round(nav.loadEventEnd || 0),
    first_row_ms: at(firstRow),
    first_row_render_ms: took(firstRow),
    load_tree_ms: took(firstOf("loadTree")),
    tree_items: document.querySelectorAll('[role="treeitem"]').length,
    lazy_stubs: document.querySelectorAll("[data-tree-lazy-stub]").length,
    dom_nodes: document.getElementsByTagName("*").length,
    // The tail is the point on a large tree: the sweep that warms collapsed
    // folders keeps requesting long after the page looks finished.
    subtree_requests: subtree.length,
    last_resource_ms: Math.round(
      resources.reduce((latest, r) => Math.max(latest, r.responseEnd), 0),
    ),
    requests: resources.length,
    transferred_kb: kb(resources),
    vendor_kb: kb(vendor),
    vendor_first_start_ms: vendor.length
      ? Math.round(Math.min(...vendor.map((r) => r.startTime)))
      : null,
  });
})();

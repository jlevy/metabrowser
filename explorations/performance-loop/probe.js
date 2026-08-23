// Metabrowser — the in-page half of one exploration run.
//
// devtools/bench_serving.py measures what an HTTP client can see. It cannot
// see the thing this loop is about: when the reader gets a usable tree. That
// is a browser fact, so it is read here, from the page, after a cold load.
//
// Evaluate in the page and hand the printed JSON to `explorations/performance-loop/run.py
// record`. Nothing here depends on a headless driver; see explorations/performance-loop/README.md
// for why the browser half is driven by hand.
//
//   1. explorations/performance-loop/run.py serve --files 100000   -> prints a URL on a fresh port
//   2. load that URL in a browser, wait for the tree
//   3. evaluate this file, copy the JSON
//   4. explorations/performance-loop/run.py record --label <name> --json '<paste>'
(async () => {
  const origin = performance.timeOrigin;
  // Long tasks are buffered by the browser and delivered to an observer on a
  // later task, so collecting them needs an async beat. Chromium only; where
  // unsupported the fields are null rather than a misleading zero.
  let longTasks = null;
  try {
    /** @type {PerformanceEntry[]} */
    const collected = [];
    const observer = new PerformanceObserver((list) => collected.push(...list.getEntries()));
    observer.observe({ type: "longtask", buffered: true });
    await new Promise((resolve) => setTimeout(resolve, 80));
    collected.push(...observer.takeRecords());
    observer.disconnect();
    longTasks = collected;
  } catch (_unsupported) {
    longTasks = null;
  }

  // One live re-probe of the root tree route, so a run records what that
  // request costs in the regime the page actually met (H8's metric). The
  // Server-Timing header separates the server's own work from queueing.
  const reprobe = { ms: null, srv_ms: null, index_status: null };
  try {
    const t0 = performance.now();
    const response = await fetch("/api/tree?depth=1", { cache: "no-store" });
    reprobe.ms = Math.round(performance.now() - t0);
    const timing = response.headers.get("server-timing") || "";
    const match = timing.match(/srv;dur=([0-9.]+)/);
    reprobe.srv_ms = match ? Math.round(Number(match[1])) : null;
    const progress = await (await fetch("/api/index/progress")).json();
    reprobe.index_status = progress.status || null;
  } catch (_unreachable) {
    // Leave nulls: a probe that cannot reach the server still reports the page.
  }

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

  // The first /api/tree fetch, attributed: how much was the server's own work
  // (Server-Timing, same-origin so it is exposed), how much was wire and
  // queueing, and how big it was. load_tree_ms alone conflates all three, and
  // H27 is specifically about which one dominates during a scan.
  const treeEntry = resources.find(
    (r) => /\/api\/tree(\?|$)/.test(r.name) && !r.name.includes("path="),
  );
  const treeSrv = treeEntry?.serverTiming?.find((t) => t.name === "srv");

  // Render cost, from the app's own spans: what H11 (patch instead of
  // replace) and H7 (row windowing) would move.
  const renderSpans = spans.filter((s) => String(s.label).startsWith("renderTreeNodes"));
  const renderTotal = Math.round(renderSpans.reduce((t, s) => t + s.duration_ms, 0));

  const paints = {};
  for (const entry of performance.getEntriesByType("paint")) {
    paints[entry.name] = Math.round(entry.startTime);
  }

  // What the reader sees, as opposed to when the data arrived. Everything
  // above this point measures the second and none of it measures the first.
  //
  // Two of these need a *visible* page and will be null here: Chromium does
  // not compute largest-contentful-paint for a page that has never been
  // visible, and a layout-shift score means nothing in a pane with no layout.
  // They are recorded anyway, as null rather than zero, so the numbers exist
  // the moment someone runs this in a real window -- and so a zero can never
  // be mistaken for "measured, and fine".
  const lcpEntries = [];
  const shiftEntries = [];
  try {
    new PerformanceObserver((list) => lcpEntries.push(...list.getEntries())).observe({
      type: "largest-contentful-paint",
      buffered: true,
    });
    new PerformanceObserver((list) => shiftEntries.push(...list.getEntries())).observe({
      type: "layout-shift",
      buffered: true,
    });
    await new Promise((resolve) => setTimeout(resolve, 120));
  } catch (_unsupported) {
    // Left empty; the fields below report null.
  }
  const visible = document.visibilityState === "visible";
  const laidOut = window.innerHeight > 0 && window.innerWidth > 0;
  const unshifted = shiftEntries.filter((entry) => !entry.hadRecentInput);
  const cls = unshifted.reduce((total, entry) => total + entry.value, 0);

  // The skeleton measure, which does not need visibility and so is the one
  // that works here: every region a reader expects to see is present, sized,
  // and holding something. A region that is present but zero-height is a hole
  // in the page, and one holding a placeholder is not yet the page.
  const SKELETON_REGIONS = ["#nav-filter-bar", "#tree-content", "#preview-pane"];
  const regions = {};
  for (const selector of SKELETON_REGIONS) {
    const element = document.querySelector(selector);
    const box = element ? element.getBoundingClientRect() : null;
    regions[selector] = element
      ? { h: Math.round(box.height), chars: (element.textContent || "").trim().length }
      : null;
  }
  const skeletonComplete = SKELETON_REGIONS.every(
    (selector) => regions[selector] && regions[selector].h > 0 && regions[selector].chars > 0,
  );

  // How far the page moves under the reader, measured directly, because the two
  // metrics a browser would report for this -- largest-contentful-paint and
  // cumulative layout shift -- both need a visible window and this pane never
  // is one. A region drawn before it has content and grown when the content
  // arrives pushes everything below it down, and that jump is its populated
  // height minus the height it stands at while empty.
  //
  // Both heights are read in the same build, so the number is what a reader of
  // *this* build gets rather than a difference between two builds. The empty
  // state is reconstructed rather than caught mid-load: a clone carrying the
  // same classes -- so a reserved height still applies to it -- holding the
  // markup the pending render actually emits, inserted beside the real element
  // so it inherits the same width and wraps the same way.
  function emptyHeight(element, pendingHtml) {
    const stand_in = element.cloneNode(false);
    stand_in.removeAttribute("id");
    stand_in.innerHTML = pendingHtml;
    element.parentNode.insertBefore(stand_in, element);
    const height = Math.round(stand_in.getBoundingClientRect().height);
    stand_in.remove();
    return height;
  }
  function shiftOf(element, pendingHtml) {
    if (!element) {
      return null;
    }
    return Math.round(element.getBoundingClientRect().height) - emptyHeight(element, pendingHtml);
  }

  // The pending tally row is not the settled one: `treeSummaryHtml(null, ...)`
  // emits a plain `.tree-summary` holding two empty cells, while a row that has
  // its counts is `.tree-summary-split` and can wrap to a second line.
  const filterBarShift = shiftOf(document.getElementById("nav-filter-bar"), "");
  const summaryShift = shiftOf(
    document.querySelector(".tree-summary"),
    '<span class="tree-summary-count"></span><span class="tree-summary-size"></span>',
  );
  const totalShift =
    filterBarShift === null || summaryShift === null ? null : filterBarShift + summaryShift;

  return JSON.stringify({
    // Recorded, not assumed. A pane that never got a size still runs the app
    // and still produces plausible timings, while every layout-dependent
    // number — rendered rows, how many rows a page mounts, what counts as on
    // screen — is measured against nothing. A run whose viewport is 0 is not a
    // run; `record` refuses it.
    viewport_w: window.innerWidth,
    viewport_h: window.innerHeight,
    dcl_ms: Math.round(nav.domContentLoadedEventEnd || 0),
    load_ms: Math.round(nav.loadEventEnd || 0),
    first_row_ms: at(firstRow),
    first_row_render_ms: took(firstRow),
    load_tree_ms: took(firstOf("loadTree")),
    tree_fetch_srv_ms: treeSrv ? Math.round(treeSrv.duration) : null,
    tree_fetch_wait_ms: treeEntry
      ? Math.round(treeEntry.responseStart - treeEntry.requestStart)
      : null,
    tree_fetch_total_ms: treeEntry ? Math.round(treeEntry.duration) : null,
    tree_fetch_kb: treeEntry ? Math.round((treeEntry.transferSize || 0) / 1024) : null,
    // null, not 0, where the browser did not report paint entries — this
    // pane returns [] for them, which is what keeps H10 blocked.
    fcp_ms: paints["first-contentful-paint"] ?? null,
    // Null where the environment cannot answer, never 0.
    lcp_ms: lcpEntries.length ? Math.round(lcpEntries[lcpEntries.length - 1].startTime) : null,
    lcp_element: lcpEntries.length
      ? `${lcpEntries[lcpEntries.length - 1].element?.tagName ?? "?"}.${
          (lcpEntries[lcpEntries.length - 1].element?.className ?? "").split(" ")[0]
        }`
      : null,
    cls: laidOut && unshifted.length >= 0 ? Number(cls.toFixed(4)) : null,
    cls_shifts: unshifted.length,
    // Records why a visual number is missing, so an absent LCP reads as an
    // environment limit rather than as a good result.
    page_visible: visible,
    page_laid_out: laidOut,
    skeleton_complete: skeletonComplete,
    region_heights: Object.fromEntries(
      Object.entries(regions).map(([selector, box]) => [selector, box ? box.h : null]),
    ),
    // The reader-facing skeleton numbers: how far the page moves, and how
    // many times the tree region is painted to get there. A region can hold
    // still and still be assembled in front of the reader, so both are kept.
    filter_bar_shift_px: filterBarShift,
    summary_shift_px: summaryShift,
    reserved_region_shift_px: totalShift,
    tree_region_repaints: renderSpans.length,
    long_tasks: longTasks ? longTasks.length : null,
    long_task_ms_total: longTasks
      ? Math.round(longTasks.reduce((t, e) => t + e.duration, 0))
      : null,
    render_spans: renderSpans.length,
    render_ms_total: renderTotal,
    // The H8 dimension: the root tree route, asked again right now, with the
    // server's own share and the scan state it was measured in.
    tree_reprobe_ms: reprobe.ms,
    tree_reprobe_srv_ms: reprobe.srv_ms,
    index_status_at_probe: reprobe.index_status,
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

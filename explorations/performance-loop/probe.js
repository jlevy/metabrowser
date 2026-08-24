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
  // Freeze the navigation-time profile before this adapter runs its own
  // buffered-observer beat and diagnostic route requests. Those operations
  // explain the load; they are not product work and must not extend the
  // interaction-coverage or main-thread responsiveness window.
  const profiler = window.metabrowser?.perf;
  const perf = profiler ? profiler.snapshot() : { raw_measure: [], label_totals: [] };
  const supportsEntryType = (type) => {
    if (typeof PerformanceObserver === "undefined") {
      return false;
    }
    const supported = PerformanceObserver.supportedEntryTypes;
    return supported != null && Array.from(supported).includes(type);
  };
  // Long tasks are buffered by the browser and delivered to an observer on a
  // later task, so collecting them needs an async beat. Chromium only; where
  // unsupported the fields are null rather than a misleading zero.
  //
  // The browser's longtask buffer holds a bounded number of entries, and a bad
  // load overruns it. So treat every figure below as a FLOOR, not a total: a
  // run whose `long_tasks` count looks suspiciously round has lost the tail,
  // and the honest reading is "at least this much". Attaching an observer at
  // navigation instead of here is the only way to be sure, which is what a
  // round investigating H58 should do rather than trusting this paste.
  let longTasks = null;
  try {
    if (!supportsEntryType("longtask")) {
      throw new Error("longtask PerformanceObserver entries are unsupported");
    }
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
  const spans = perf.raw_measure || [];
  const labelTotals = perf.label_totals || [];
  const firstOf = (label) => spans.filter((s) => s.label === label)[0] || null;
  const totalFor = (label) => labelTotals.find((row) => row.label === label) || null;
  const at = (span) => (span ? Math.round(span.ts - origin) : null);
  const took = (span) => (span ? Math.round(span.duration_ms) : null);
  const firstAt = (label) => at(firstOf(label)) ?? totalFor(label)?.first_end_ms ?? null;
  const firstTook = (label) => took(firstOf(label)) ?? totalFor(label)?.first_duration_ms ?? null;

  const resources = /** @type {PerformanceResourceTiming[]} */ (
    performance.getEntriesByType("resource")
  );
  const memory = /** @type {{ usedJSHeapSize?: number }} */ (performance).memory;
  const kb = (list) =>
    Math.round(list.reduce((total, r) => total + (r.transferSize || 0), 0) / 1024);
  const vendor = resources.filter((r) => r.name.includes("/static/vendor/"));
  const subtree = resources.filter((r) => r.name.includes("/api/tree?path="));
  const scripts = resources.filter((r) => r.initiatorType === "script");
  const startupScripts = scripts.filter(
    (r) =>
      !r.name.includes("/static/vendor/") && r.startTime < Number(nav.domContentLoadedEventEnd),
  );
  const styles = resources.filter((r) => r.initiatorType === "link" || r.name.endsWith(".css"));
  const images = resources.filter((r) => r.initiatorType === "img");
  const apiResources = resources.filter((r) => r.name.includes("/api/"));

  // Time to first row is wall clock until the tree has rows a reader can use.
  // Not `load`, which reports a painted shell, and not network idle, which
  // reports a finished scan. The app's own renderTreeNodes:root span is the
  // moment the rows entered the DOM, so it is read rather than re-derived.
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
  const renderTotals = labelTotals.filter((row) => String(row.label).startsWith("renderTreeNodes"));
  const renderCount = renderTotals.length
    ? renderTotals.reduce((total, row) => total + row.count, 0)
    : renderSpans.length;
  const renderTotal = Math.round(
    renderTotals.length
      ? renderTotals.reduce((total, row) => total + row.total_ms, 0)
      : renderSpans.reduce((total, span) => total + span.duration_ms, 0),
  );
  // Of those, the ones that actually replace the region. `renderTreeNodes:root`
  // is the label on the only span that writes `#tab-files` wholesale, so one
  // such span is one repaint. The other three labels are not repaints:
  // `:subtree` and `:subtreeCache` patch rows into a tree already standing, and
  // `:inline` is an *outer* span around a call that emits its own `:root`, so
  // counting it would charge one paint twice. Counting all four is what made
  // this a second name for `render_spans` rather than a measurement.
  const regionRepaints =
    totalFor("renderTreeNodes:root")?.count ??
    renderSpans.filter((s) => String(s.label) === "renderTreeNodes:root").length;

  const navigationResponsiveness = perf.responsiveness || null;
  const navigationVitals = perf.vitals || null;
  const responsiveness = navigationResponsiveness
    ? {
        performance_profile_schema: perf.schema || null,
        responsiveness_source: "navigation-profiler",
        ...navigationResponsiveness,
        long_task_window_ms: navigationResponsiveness.window_ms,
      }
    : {
        performance_profile_schema: null,
        responsiveness_source: "late-buffer",
        visibility_state: document.visibilityState,
        ever_hidden: null,
        measurement_valid: false,
        long_task_window_ms: Math.round(performance.now()),
        long_task_max_ms: longTasks
          ? Math.round(longTasks.reduce((worst, entry) => Math.max(worst, entry.duration), 0))
          : null,
        long_tasks_over_200ms: longTasks
          ? longTasks.filter((entry) => entry.duration > 200).length
          : null,
        main_thread_blocked_pct: longTasks
          ? Math.round(
              (1000 * longTasks.reduce((total, entry) => total + entry.duration, 0)) /
                performance.now(),
            ) / 10
          : null,
        interactions: null,
        interaction_p50_ms: null,
        interaction_p95_ms: null,
        interaction_max_ms: null,
      };
  // The workload that triggered this investigation has its own bounded view:
  // a backend may emit any volume, but no one delivery callback may monopolize
  // a frame and the callbacks together may not consume a material share of the
  // measured window. Work-item totals preserve the event volume beside the
  // time, so a later optimization cannot look good merely by dropping updates.
  const inventoryDeliveryLabels = [
    "fileStoreApplySnapshot",
    "fileStoreApplyChange",
    "knownFileCatalog:applyBulkSnapshot",
    "knownFileCatalog:applyCatalogChange",
  ];
  const inventoryDeliveryRows = inventoryDeliveryLabels.map(totalFor).filter((row) => row !== null);
  const inventoryDeliveryWorkMs = inventoryDeliveryRows.reduce(
    (total, row) => total + row.total_ms,
    0,
  );
  const inventoryDeliveryWindowMs = Number(responsiveness.long_task_window_ms || 0);

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
  let lateLcpSupported = false;
  let lateShiftSupported = false;
  let lateLcpObserver = null;
  let lateShiftObserver = null;
  try {
    if (!supportsEntryType("largest-contentful-paint")) {
      throw new Error("largest-contentful-paint entries are unsupported");
    }
    lateLcpObserver = new PerformanceObserver((list) => lcpEntries.push(...list.getEntries()));
    lateLcpObserver.observe({
      type: "largest-contentful-paint",
      buffered: true,
    });
    lateLcpSupported = true;
  } catch (_unsupported) {
    lateLcpSupported = false;
  }
  try {
    if (!supportsEntryType("layout-shift")) {
      throw new Error("layout-shift entries are unsupported");
    }
    lateShiftObserver = new PerformanceObserver((list) => shiftEntries.push(...list.getEntries()));
    lateShiftObserver.observe({
      type: "layout-shift",
      buffered: true,
    });
    lateShiftSupported = true;
  } catch (_unsupported) {
    lateShiftSupported = false;
  }
  if (lateLcpObserver || lateShiftObserver) {
    await new Promise((resolve) => setTimeout(resolve, 120));
    if (lateLcpObserver) {
      lcpEntries.push(...lateLcpObserver.takeRecords());
      lateLcpObserver.disconnect();
    }
    if (lateShiftObserver) {
      shiftEntries.push(...lateShiftObserver.takeRecords());
      lateShiftObserver.disconnect();
    }
  }
  const visible = document.visibilityState === "visible";
  const laidOut = window.innerHeight > 0 && window.innerWidth > 0;
  const unshifted = shiftEntries.filter((entry) => !entry.hadRecentInput);
  const cls = unshifted.reduce((total, entry) => total + entry.value, 0);

  // The stand-in goes in flow, beside the real element, so the same container
  // lays it out: it inherits the width, it wraps the same way, and a region
  // whose height comes from its container rather than from its content is
  // stretched exactly as the real one is. `#preview-pane` is `flex: 1`, so its
  // shipped height equals its settled height and it contributes nothing to
  // `frame_missing_px`. That is the right answer rather than a blind spot --
  // the pane fills its frame from first paint and only its contents are a
  // placeholder -- so do not "fix" this by measuring out of flow, which would
  // report the whole pane as missing.
  function heightOfStandIn(reference, standIn) {
    reference.parentNode.insertBefore(standIn, reference);
    const height = Math.round(standIn.getBoundingClientRect().height);
    standIn.remove();
    return height;
  }
  function emptyHeight(element, pendingHtml) {
    const stand_in = element.cloneNode(false);
    stand_in.removeAttribute("id");
    stand_in.innerHTML = pendingHtml;
    return heightOfStandIn(element, stand_in);
  }
  // Every region a reader expects to see, against the markup the server ships
  // for it -- copied from `server.py`, not paraphrased. A paraphrase measures
  // the wrong thing here and always in the same direction: `#tab-files` ships
  // a spinner inside 32px of padding, and its label is `.sr-only`, which is
  // clipped to a pixel. Measured as the bare sentence it reads as one line of
  // body text, which understates the shipped height by most of its value and
  // overstates the gap by the same amount.
  //
  // Two numbers per region: the height it settles at, and the height it stands
  // at holding only what the shell shipped. The gap between them is how much
  // of the frame does not exist at first paint, which is the H52 question. It
  // is recorded per run rather than derived by hand, because the metric that
  // used to sit here -- `skeleton_complete` -- asked whether each region was
  // present, sized and non-empty *at probe time*, which is after settle. It
  // answered true on every run ever recorded, including every one carrying the
  // hole this now measures. A metric that cannot come out false is not
  // measuring anything.
  const SKELETON_REGIONS = [
    ["#nav-filter-bar", ""],
    [
      "#tab-files",
      '<div class="loading mb-delayed-loading"><div class="spinner"></div>' +
        '<span class="sr-only">Loading files…</span></div>',
    ],
    ["#preview-pane", '<div class="preview-empty">Select a file to preview.</div>'],
  ];
  const regions = {};
  for (const [selector, shippedHtml] of SKELETON_REGIONS) {
    const element = document.querySelector(selector);
    if (!element) {
      regions[selector] = null;
      continue;
    }
    regions[selector] = {
      h: Math.round(element.getBoundingClientRect().height),
      shipped_h: emptyHeight(element, shippedHtml),
    };
  }
  // How many pixels of the frame the shell does not ship. Sums the regions
  // above, so it is a page-level number in a way the shift metric is not.
  const frameMissingPx = Object.values(regions).reduce(
    (total, box) => (box ? total + Math.max(0, box.h - box.shipped_h) : total),
    0,
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
  // state is reconstructed rather than caught mid-load, and how it is
  // reconstructed depends on whether the pending state is the same element:
  // where it is, a clone carrying the same classes -- so a reserved height
  // still applies to it -- holds the markup the shell ships; where it is not,
  // the app builds its own pending element (see the tally row below).
  function shiftOf(element, pendingHtml) {
    if (!element) {
      return null;
    }
    return Math.round(element.getBoundingClientRect().height) - emptyHeight(element, pendingHtml);
  }

  // The filter bar's pending state is the shipped element itself, empty, so a
  // clone of it is exactly right.
  const filterBarShift = shiftOf(document.getElementById("nav-filter-bar"), "");

  // The tally row's is not: the pending row is a whole different element from
  // the settled one -- `treeSummaryHtml(null, null, null)` emits a plain
  // `.tree-summary` holding two `.tally-pending` cells, while a row that has
  // its counts is `.tree-summary-split` and can wrap to a second line. Cloning
  // the settled row would carry `tree-summary-split` into the stand-in, and
  // restating its markup here would be a copy of `app.js` that drifts the next
  // time that function changes. Ask the app for its own pending row instead.
  function pendingSummaryRow() {
    if (typeof treeSummaryHtml !== "function") {
      return null;
    }
    const holder = document.createElement("div");
    holder.innerHTML = treeSummaryHtml(null, null, null);
    return holder.firstElementChild;
  }
  const settledSummary = document.querySelector(".tree-summary");
  const pendingSummary = settledSummary ? pendingSummaryRow() : null;
  const summaryShift = pendingSummary
    ? Math.round(settledSummary.getBoundingClientRect().height) -
      heightOfStandIn(settledSummary, pendingSummary)
    : null;
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
    ttfb_ms: Math.round(nav.responseStart || 0),
    response_download_ms:
      nav.responseEnd && nav.responseStart ? Math.round(nav.responseEnd - nav.responseStart) : null,
    dom_interactive_ms: Math.round(nav.domInteractive || 0),
    dcl_ms: Math.round(nav.domContentLoadedEventEnd || 0),
    load_ms: Math.round(nav.loadEventEnd || 0),
    first_row_ms: firstAt("renderTreeNodes:root"),
    first_row_render_ms: firstTook("renderTreeNodes:root"),
    load_tree_ms: firstTook("loadTree"),
    tree_fetch_srv_ms: treeSrv ? Math.round(treeSrv.duration) : null,
    tree_fetch_wait_ms: treeEntry
      ? Math.round(treeEntry.responseStart - treeEntry.requestStart)
      : null,
    tree_fetch_total_ms: treeEntry ? Math.round(treeEntry.duration) : null,
    tree_fetch_kb: treeEntry ? Math.round((treeEntry.transferSize || 0) / 1024) : null,
    // null, not 0, where the browser did not report paint entries — this
    // pane returns [] for them, which is what keeps H10 blocked.
    fcp_ms: navigationVitals ? navigationVitals.fcp_ms : (paints["first-contentful-paint"] ?? null),
    vitals_source: navigationVitals ? "navigation-profiler" : "late-buffer",
    vitals_unsupported: navigationVitals?.unsupported ?? null,
    // Null where the environment cannot answer, never 0.
    lcp_ms: navigationVitals
      ? navigationVitals.lcp_ms
      : lateLcpSupported && lcpEntries.length
        ? Math.round(lcpEntries[lcpEntries.length - 1].startTime)
        : null,
    lcp_element: navigationVitals
      ? navigationVitals.lcp_element
      : lateLcpSupported && lcpEntries.length
        ? `${lcpEntries[lcpEntries.length - 1].element?.tagName ?? "?"}.${
            String(lcpEntries[lcpEntries.length - 1].element?.className ?? "").split(" ")[0]
          }`
        : null,
    // Gated on visibility, not on layout. A layout-shift observer in a page
    // that has never been visible reports no entries because it cannot see
    // any, not because none happened, so `laidOut` here returned a confident
    // 0 for every run in this pane -- the exact "measured, and fine" reading
    // these fields exist to prevent. The shift figures below are what this
    // environment can actually answer.
    cls: navigationVitals
      ? navigationVitals.cls
      : visible && lateShiftSupported
        ? Number(cls.toFixed(4))
        : null,
    cls_shifts: navigationVitals
      ? navigationVitals.cls_shifts
      : visible && lateShiftSupported
        ? unshifted.length
        : null,
    // Records why a visual number is missing, so an absent LCP reads as an
    // environment limit rather than as a good result.
    page_visible: visible,
    page_laid_out: laidOut,
    frame_missing_px: frameMissingPx,
    // Settled beside shipped, per region, so `frame_missing_px` can be read
    // back to the region that owns it rather than taken on faith.
    region_heights: Object.fromEntries(
      Object.entries(regions).map(([selector, box]) => [
        selector,
        box ? { settled: box.h, shipped: box.shipped_h } : null,
      ]),
    ),
    // The reader-facing skeleton numbers: how far the page moves, and how
    // many times the tree region is painted to get there. A region can hold
    // still and still be assembled in front of the reader, so both are kept.
    filter_bar_shift_px: filterBarShift,
    summary_shift_px: summaryShift,
    reserved_region_shift_px: totalShift,
    tree_region_repaints: regionRepaints,
    // The profiler is loaded with the document, so an end-of-run paste reads
    // exact whole-window aggregates instead of reconstructing a floor from the
    // browser's bounded historical buffer. The late buffer remains diagnostic
    // and is named as such; it never overwrites the admissible totals.
    ...responsiveness,
    inventory_delivery_attribution_missing: inventoryDeliveryRows.length === 0 ? 1 : 0,
    inventory_delivery_batches: inventoryDeliveryRows.reduce((total, row) => total + row.count, 0),
    inventory_delivery_items: inventoryDeliveryRows.reduce(
      (total, row) => total + (row.work_items_total || 0),
      0,
    ),
    inventory_delivery_batch_items_max: inventoryDeliveryRows.reduce(
      (largest, row) => Math.max(largest, row.work_items_max || 0),
      0,
    ),
    inventory_delivery_max_ms: Math.round(
      inventoryDeliveryRows.reduce((largest, row) => Math.max(largest, row.max_ms), 0),
    ),
    inventory_delivery_work_ms_total: Math.round(inventoryDeliveryWorkMs),
    inventory_delivery_work_pct:
      inventoryDeliveryWindowMs > 0
        ? Math.round((1000 * inventoryDeliveryWorkMs) / inventoryDeliveryWindowMs) / 10
        : null,
    late_buffer_long_tasks: longTasks ? longTasks.length : null,
    late_buffer_long_task_ms_total: longTasks
      ? Math.round(longTasks.reduce((t, e) => t + e.duration, 0))
      : null,
    render_spans: renderCount,
    render_ms_total: renderTotal,
    // Attribution: which labelled span burned the time, whole-session and
    // immune to the sample ring's eviction. `longtask` says the thread was
    // blocked; this says by what. Sorted worst-single-span first, so the top
    // row is the one to profile.
    label_totals: perf.label_totals || null,
    worst_animation_frames: perf.worst_animation_frames || null,
    fetch_samples_seen: perf.fetch_samples_seen ?? null,
    fetch_samples_retained: perf.fetch_samples_retained ?? null,
    fetches_in_flight: perf.fetches_in_flight ?? null,
    fetch_aborts: perf.fetch_aborts ?? null,
    fetch_http_4xx: perf.fetch_http_4xx ?? null,
    fetch_http_5xx: perf.fetch_http_5xx ?? null,
    fetch_network_errors: perf.fetch_network_errors ?? null,
    measure_samples_seen: perf.measure_samples_seen ?? null,
    measure_samples_retained: perf.measure_samples_retained ?? null,
    labels_retained: perf.labels_retained ?? null,
    labels_overflowed: perf.labels_overflowed ?? null,
    resource_timing_capacity: perf.resource_timing_capacity ?? null,
    resource_timing_buffer_full: perf.resource_timing_buffer_full ?? null,
    // The H8 dimension: the root tree route, asked again right now, with the
    // server's own share and the scan state it was measured in.
    tree_reprobe_ms: reprobe.ms,
    tree_reprobe_srv_ms: reprobe.srv_ms,
    index_status_at_probe: reprobe.index_status,
    tree_items: document.querySelectorAll('[role="treeitem"]').length,
    lazy_stubs: document.querySelectorAll("[data-tree-lazy-stub]").length,
    plugin_view_containers: document.querySelectorAll("[data-plugin-view]").length,
    plugin_view_nonempty: Array.from(document.querySelectorAll("[data-plugin-view]")).filter(
      (container) => container.childElementCount > 0 || container.textContent?.trim(),
    ).length,
    shell_tools_missing: document.documentElement.dataset.shellToolsReady === "true" ? 0 : 1,
    file_catalog_incomplete:
      window.metabrowser?.fileCatalog?.snapshot?.()?.complete === true ? 0 : 1,
    dom_nodes: document.getElementsByTagName("*").length,
    // The tail is the point on a large tree: the sweep that warms collapsed
    // folders keeps requesting long after the page looks finished.
    subtree_requests: subtree.length,
    last_resource_ms: Math.round(
      resources.reduce((latest, r) => Math.max(latest, r.responseEnd), 0),
    ),
    requests: resources.length,
    transferred_kb: kb(resources),
    script_transfer_kb: kb(scripts),
    startup_script_requests: startupScripts.length,
    startup_script_transfer_kb: kb(startupScripts),
    startup_script_last_response_ms: startupScripts.length
      ? Math.round(Math.max(...startupScripts.map((resource) => resource.responseEnd || 0)))
      : null,
    startup_script_duration_max_ms: startupScripts.length
      ? Math.round(Math.max(...startupScripts.map((resource) => resource.duration || 0)))
      : null,
    startup_scripts_slowest: startupScripts
      .slice()
      .sort((left, right) => right.duration - left.duration)
      .slice(0, 10)
      .map((resource) => ({
        path: new URL(resource.name).pathname,
        start_ms: Math.round(resource.startTime),
        response_end_ms: Math.round(resource.responseEnd),
        duration_ms: Math.round(resource.duration),
        transfer_kb: Math.round((resource.transferSize || 0) / 1024),
      })),
    startup_scripts_latest: startupScripts
      .slice()
      .sort((left, right) => right.responseEnd - left.responseEnd)
      .slice(0, 10)
      .map((resource) => ({
        path: new URL(resource.name).pathname,
        start_ms: Math.round(resource.startTime),
        response_end_ms: Math.round(resource.responseEnd),
        duration_ms: Math.round(resource.duration),
        transfer_kb: Math.round((resource.transferSize || 0) / 1024),
      })),
    style_transfer_kb: kb(styles),
    image_transfer_kb: kb(images),
    api_transfer_kb: kb(apiResources),
    largest_resource_kb: resources.length
      ? Math.round(Math.max(...resources.map((resource) => resource.transferSize || 0)) / 1024)
      : 0,
    resource_duration_max_ms: resources.length
      ? Math.round(Math.max(...resources.map((resource) => resource.duration || 0)))
      : 0,
    js_heap_mb:
      typeof memory?.usedJSHeapSize === "number"
        ? Math.round((10 * memory.usedJSHeapSize) / (1024 * 1024)) / 10
        : null,
    vendor_kb: kb(vendor),
    vendor_first_start_ms: vendor.length
      ? Math.round(Math.min(...vendor.map((r) => r.startTime)))
      : null,
  });
})();

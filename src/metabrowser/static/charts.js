// Shared chart and tally rendering for built-in and external plugins.

((global) => {
  var _perf = global.metabrowserPerf || {
    measure: (_label, fn) => fn(),
  };
  var ICONS = global.MetabrowserIcons || {};
  var esc = (value) => {
    if (global.metabrowser?.escapeHtml) {
      return global.metabrowser.escapeHtml(value);
    }
    return String(value);
  };
  var chartInstances = [];
  var activeChartRender = null;

  function destroyChartInstances() {
    for (var i = 0; i < chartInstances.length; i++) {
      chartInstances[i].destroy();
    }
    chartInstances = [];
  }

  function dispose() {
    destroyChartInstances();
    activeChartRender = null;
  }

  function cssVar(ref) {
    if (typeof ref !== "string") {
      return ref;
    }
    var m = ref.match(/^var\((--[^)]+)\)$/);
    var prop = m ? m[1] : ref.indexOf("--") === 0 ? ref : null;
    if (!prop) {
      return ref;
    }
    var v = getComputedStyle(document.documentElement).getPropertyValue(prop).trim();
    return v || ref;
  }

  // Apply alpha (0..1) to an hsl()/hex color. Works with the resolved
  // output of cssVar() or any concrete color string already in the spec.
  function colorWithAlpha(color, alpha) {
    if (typeof color !== "string" || alpha >= 1) {
      return color;
    }
    var c = cssVar(color);
    var m = c.match(/^hsla?\(([^/)]+?)(?:\s*\/\s*[^)]+)?\)$/i);
    if (m) {
      return `hsl(${m[1].trim()} / ${alpha})`;
    }
    if (/^#[0-9a-f]{6}([0-9a-f]{2})?$/i.test(c)) {
      var hex = Math.round(alpha * 255).toString(16);
      if (hex.length < 2) {
        hex = `0${hex}`;
      }
      return c.slice(0, 7) + hex;
    }
    return c;
  }

  function renderSummaryTree(container, counts, metadata) {
    return _perf.measure(
      "renderSummaryTree",
      () => {
        if (!counts || Object.keys(counts).length === 0) {
          return;
        }

        var treeDiv = document.createElement("div");
        treeDiv.className = "tally-tree";

        // Metadata line
        if (metadata && Object.keys(metadata).length > 0) {
          var metaHtml = '<div class="tally-metadata">';
          for (var key in metadata) {
            if (metadata[key] != null) {
              metaHtml +=
                "<span><strong>" +
                esc(key.replace(/_/g, " ")) +
                ":</strong> " +
                esc(String(metadata[key])) +
                "</span>";
            }
          }
          metaHtml += "</div>";
          treeDiv.innerHTML = metaHtml;
        }

        // Build tree from slash-delimited paths
        var tree = {};
        var total = 0;
        for (var path in counts) {
          var parts = path.split("/");
          var node = tree;
          for (var i = 0; i < parts.length; i++) {
            if (!node[parts[i]]) {
              node[parts[i]] = { _count: 0, _children: {} };
            }
            node[parts[i]]._count += counts[path];
            node = node[parts[i]]._children;
          }
          total += counts[path];
        }

        // Render tree recursively
        var treeHtml = renderTallyNode("All events", total, tree, 0, false);
        var treeContent = document.createElement("div");
        treeContent.innerHTML = treeHtml;
        treeDiv.appendChild(treeContent);

        // Add click handlers for expand/collapse
        treeDiv.addEventListener("click", (e) => {
          var node = /** @type {Element} */ (e.target).closest(".tally-node");
          if (!node) {
            return;
          }
          var children = node.nextElementSibling;
          if (!children?.classList.contains("tally-children")) {
            return;
          }
          if (children.classList.contains("collapsed")) {
            children.classList.remove("collapsed");
            node.classList.remove("collapsed");
            node.classList.add("expanded");
          } else {
            children.classList.add("collapsed");
            node.classList.remove("expanded");
            node.classList.add("collapsed");
          }
        });

        container.appendChild(treeDiv);
      },
      {
        count_keys: counts ? Object.keys(counts).length : 0,
        metadata_keys: metadata ? Object.keys(metadata).length : 0,
      },
    );
  }

  // Color hints for certain leaf labels
  var TALLY_COLORS = {
    success: "tally-color-success",
    failed: "tally-color-failed",
    error: "tally-color-error",
    critical: "tally-color-critical",
    high: "tally-color-high",
    elevated: "tally-color-elevated",
    kill: "tally-color-kill",
  };

  function renderTallyNode(label, count, children, depth, startCollapsed) {
    var childKeys = Object.keys(children);
    var hasChildren = childKeys.length > 0;
    var colorClass = TALLY_COLORS[label] || "";
    var countHtml = `<span class="tally-count ${colorClass}">${count}</span>`;

    if (!hasChildren) {
      return (
        '<div class="tally-node tally-leaf"><span class="tally-toggle"></span>' +
        '<span class="tally-label">' +
        esc(label) +
        "</span>" +
        countHtml +
        "</div>"
      );
    }

    var collapsedCls = startCollapsed ? " collapsed" : " expanded";
    var html =
      '<div class="tally-node' +
      collapsedCls +
      '"><span class="tally-toggle">' +
      ICONS.toggle +
      "</span>" +
      '<span class="tally-label">' +
      esc(label) +
      "</span>" +
      countHtml +
      "</div>";
    html += `<div class="tally-children${startCollapsed ? " collapsed" : ""}">`;
    for (var i = 0; i < childKeys.length; i++) {
      var k = childKeys[i];
      var child = children[k];
      // Top-level nodes start collapsed by default
      html += renderTallyNode(k, child._count, child._children, depth + 1, depth === 0);
    }
    html += "</div>";
    return html;
  }

  function renderChartSpecs(container, charts) {
    return _perf.measure(
      "renderChartSpecs",
      () => {
        if (typeof Chart === "undefined") {
          container.innerHTML += '<div class="preview-empty">Chart.js not loaded</div>';
          return;
        }

        var section = document.createElement("div");
        section.className = "charts-section";

        for (let chartIndex = 0; chartIndex < charts.length; chartIndex++) {
          var spec = charts[chartIndex];
          var titleEl = document.createElement("div");
          titleEl.className = "chart-title";
          titleEl.textContent = spec.title;
          section.appendChild(titleEl);

          var wrapper = document.createElement("div");
          wrapper.className = "chart-container";
          var canvas = document.createElement("canvas");
          wrapper.appendChild(canvas);
          section.appendChild(wrapper);

          var chart = createChart(canvas, spec);
          if (chart) {
            chartInstances.push(chart);
          }
        }
        container.appendChild(section);
      },
      {
        charts: charts ? charts.length : 0,
      },
    );
  }

  function createChart(canvas, spec) {
    // Resolve any var(--foo) color sentinels emitted by Python to concrete
    // colors without mutating the source spec. Theme repainting rebuilds from
    // these token-bearing specs after the root palette changes.
    var series = (spec.series || []).map((item) => ({
      ...item,
      color: item.color ? cssVar(item.color) : item.color,
    }));
    var thresholds = (spec.thresholds || []).map((item) => ({
      ...item,
      color: item.color ? cssVar(item.color) : item.color,
    }));
    var annotations = (spec.annotations || []).map((item) => ({
      ...item,
      color: item.color ? cssVar(item.color) : item.color,
    }));

    var datasets = [];
    // Build threshold color function for area charts.
    // Thresholds define boundary lines; the fill color is determined by the
    // lowest threshold the value falls BELOW (e.g. between the red/15 and
    // yellow/30 lines → below yellow → yellow).  Above all thresholds uses
    // the highest threshold's color.
    var thresholdColorFn = null;
    if (spec.type === "area" && thresholds.length > 0) {
      var ascTh = thresholds.slice().sort((a, b) => a.value - b.value);
      thresholdColorFn = (y) => {
        for (var t = 0; t < ascTh.length; t++) {
          if (y < ascTh[t].value) {
            return ascTh[t].color;
          }
        }
        return ascTh[ascTh.length - 1].color; // above all thresholds
      };
    }

    for (var i = 0; i < series.length; i++) {
      var s = series[i];
      var ds = {
        label: s.label,
        data: s.data,
        borderColor: s.color,
        backgroundColor:
          spec.type === "area" || spec.type === "stacked-bar"
            ? colorWithAlpha(s.color, 0.2)
            : colorWithAlpha(s.color, 0.13),
        borderWidth: 1.5,
        pointRadius: 0,
        tension: 0,
      };
      if (s.style === "dashed") {
        ds.borderDash = [5, 3];
      }
      if (spec.type === "area") {
        ds.fill = true;
        // Use threshold-based segment coloring for line and fill
        if (thresholdColorFn) {
          ds.segment = {
            backgroundColor: (ctx) => colorWithAlpha(thresholdColorFn(ctx.p0.parsed.y), 0.2),
          };
        }
      }
      if (spec.type === "step") {
        ds.stepped = true;
      }
      datasets.push(ds);
    }

    var chartType = "line";
    if (spec.type === "stacked-bar") {
      chartType = "bar";
    }

    var config = {
      type: chartType,
      data: { datasets: datasets },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: { duration: 300 },
        interaction: { mode: "index", intersect: false },
        plugins: {
          legend: {
            display: datasets.length > 1,
            position: "top",
            labels: { boxWidth: 10, font: { size: 10 } },
          },
          tooltip: { enabled: true, bodyFont: { size: 11 } },
        },
        scales: {
          x: {
            type: spec.x_type === "time" ? "time" : "linear",
            time: { tooltipFormat: "MMM d, HH:mm:ss" },
            ticks: { font: { size: 10 }, maxTicksLimit: 8 },
            grid: { display: false },
          },
          y: {
            min: spec.y_min,
            max: spec.y_max,
            title: { display: !!spec.y_label, text: spec.y_label || "", font: { size: 10 } },
            ticks: { font: { size: 10 } },
            grid: { color: cssVar("--chart-grid") },
          },
        },
      },
    };

    // Stacked bar config
    if (spec.type === "stacked-bar") {
      config.options.scales.x.stacked = true;
      config.options.scales.y.stacked = true;
    }

    // Threshold lines
    if (thresholds.length > 0) {
      config.options.plugins.annotation = { annotations: {} };
      for (var t = 0; t < thresholds.length; t++) {
        var th = thresholds[t];
        config.options.plugins.annotation.annotations[`th${t}`] = {
          type: "line",
          yMin: th.value,
          yMax: th.value,
          borderColor: colorWithAlpha(th.color, 0.53),
          borderWidth: 1,
          borderDash: [4, 4],
          label: {
            display: true,
            content: th.label,
            position: "end",
            font: { size: 9 },
            backgroundColor: colorWithAlpha(th.color, 0.13),
            color: th.color,
          },
        };
      }
    }

    // Vertical annotation lines (faint lines, label on hover)
    if (annotations.length > 0) {
      if (!config.options.plugins.annotation) {
        config.options.plugins.annotation = { annotations: {} };
      }
      for (var a = 0; a < annotations.length; a++) {
        var ann = annotations[a];
        var color = ann.color || cssVar("--chart-annotation-default");
        config.options.plugins.annotation.annotations[`ann${a}`] = {
          type: "line",
          xMin: ann.x,
          xMax: ann.x,
          borderColor: color,
          borderWidth: 1,
          enter: (ctx) => {
            ctx.element.options.borderWidth = 2;
            ctx.chart.draw();
          },
          leave: (ctx) => {
            ctx.element.options.borderWidth = 1;
            ctx.chart.draw();
          },
          label: {
            display: false,
            content: ann.label,
            position: "start",
            rotation: -90,
            font: { size: 9 },
            backgroundColor: colorWithAlpha(color, 0.13),
            color: cssVar("--chart-label-text"),
          },
        };
      }
      // Override enter/leave to show label on hover
      for (var key in config.options.plugins.annotation.annotations) {
        ((k) => {
          config.options.plugins.annotation.annotations[k].enter = (ctx) => {
            ctx.element.label.options.display = true;
            ctx.element.options.borderWidth = 2;
            ctx.chart.draw();
          };
          config.options.plugins.annotation.annotations[k].leave = (ctx) => {
            ctx.element.label.options.display = false;
            ctx.element.options.borderWidth = 1;
            ctx.chart.draw();
          };
        })(key);
      }
    }

    try {
      return new Chart(canvas, config);
    } catch (_e) {
      return null;
    }
  }

  function renderPayload(container, chartData) {
    return _perf.measure(
      "renderChartsPayload",
      () => {
        destroyChartInstances();
        activeChartRender =
          chartData.charts && chartData.charts.length > 0 ? { container, chartData } : null;
        container.innerHTML = "";
        if (chartData.summary) {
          renderSummaryTree(container, chartData.summary.counts, chartData.summary.metadata);
        }
        if (chartData.charts && chartData.charts.length > 0) {
          renderChartSpecs(container, chartData.charts);
        }
        if (!chartData.summary && (!chartData.charts || chartData.charts.length === 0)) {
          container.innerHTML = '<div class="preview-empty">No chart data available</div>';
        }
      },
      {
        charts: chartData?.charts ? chartData.charts.length : 0,
        has_summary: !!chartData?.summary,
      },
    );
  }

  function repaintForTheme() {
    if (!activeChartRender) {
      return;
    }
    var render = activeChartRender;
    if ("isConnected" in render.container && !render.container.isConnected) {
      dispose();
      return;
    }
    renderPayload(render.container, render.chartData);
  }

  global.MetabrowserTheme.subscribe(repaintForTheme);

  global.MetabrowserCharts = {
    dispose: dispose,
    renderPayload: renderPayload,
  };
})(window);

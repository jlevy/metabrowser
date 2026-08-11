// Commit-graph swimlane layout and per-row SVG rendering.
//
// Ported from VS Code's built-in Source Control Graph:
//   src/vs/workbench/contrib/scm/browser/scmHistory.ts
//   Copyright (c) Microsoft Corporation. Licensed under the MIT License.
//
// The port is deliberately faithful. Lane geometry, path commands, and
// assignment order match upstream so a future layout fix can be diffed
// against this file rather than reverse-engineered. Four changes were
// made, each noted at its site:
//
//   1. Colors are design tokens (`var(--git-lane-N)`) instead of VS Code
//      theme color identifiers, per the core styling rule.
//   2. Lane state is threaded explicitly through `priorSwimlanes` so a
//      page boundary is a parameter rather than an array VS Code happens
//      to hold in memory. This is what keeps lanes continuous across
//      `/api/git/log` pages.
//   3. Incoming/outgoing-change rows are not built (they are a non-goal
//      for this version), but the `kind` field and the renderer branch
//      that draws them are kept intact, so adding them later is a data
//      change rather than a renderer change.
//   4. Every commit marker uses one smaller outer radius. HEAD and merge
//      commits remain distinct through concentric shapes without taking
//      more visual weight than an ordinary vertex.
//
// This module is pure: it fetches nothing, owns no DOM beyond the SVG
// element it returns, and holds no state between calls. That is what
// makes it testable under a `vm` shim.

(() => {
  // Types live in static/types.d.ts as MetabrowserGitGraphLane,
  // MetabrowserGitCommit, MetabrowserGitGraphRow, and
  // MetabrowserGitSwimlaneResult — the same declarations the panel and
  // the Window surface use, so a shape can only be defined once. They
  // mirror the TypedDicts in metabrowser/git/wire.py.

  // Geometry, verbatim from scmHistory.ts. SWIMLANE_HEIGHT is also the
  // row height: the SVG is exactly one row tall, which is what lets the
  // graph ride along in an ordinary scrolling list instead of needing a
  // canvas sized to the whole history.
  const SWIMLANE_HEIGHT = 22;
  const SWIMLANE_WIDTH = 11;
  const SWIMLANE_CURVE_RADIUS = 5;
  // Marker geometry deliberately diverges from upstream: topology is
  // expressed by the lanes, while concentric shapes carry node state.
  const CIRCLE_RADIUS = 4;
  const CIRCLE_STROKE_WIDTH = 2;
  const CIRCLE_CENTER_RADIUS = 1;

  const SVG_NAMESPACE = "http://www.w3.org/2000/svg";

  // Branch lane palette. These are VS Code's five graph foreground
  // colors, chosen upstream to stay distinguishable under the common
  // forms of color vision deficiency. Referenced as tokens rather than
  // literals; the values live in styles.css.
  const LANE_COLORS = Object.freeze([
    "var(--git-lane-1)",
    "var(--git-lane-2)",
    "var(--git-lane-3)",
    "var(--git-lane-4)",
    "var(--git-lane-5)",
  ]);

  // The lane color for the branch HEAD is on. Upstream calls this
  // `historyItemRefColor`; it is also the fallback when a lane's color
  // cannot be determined.
  const HEAD_LANE_COLOR = "var(--git-ref-local)";

  /**
   * Positive modulo. `-1 % 5` is `-1` in JavaScript, which would index
   * off the front of the palette.
   *
   * @param {number} index
   * @param {number} modulo
   * @returns {number}
   */
  function rot(index, modulo) {
    return ((index % modulo) + modulo) % modulo;
  }

  /**
   * The color a commit's own lane should take, if any ref on it names one.
   *
   * Upstream's `getLabelColorIdentifier`. A commit carrying the current
   * branch keeps that branch's color instead of drawing a new palette
   * color, so the branch you are on stays one continuous color for its
   * whole length.
   *
   * @param {MetabrowserGitCommit} commit
   * @param {Map<string, string>} refColors Full refname to CSS color.
   * @returns {string | undefined}
   */
  function labelColor(commit, refColors) {
    for (const ref of commit.refs ?? []) {
      const color = refColors.get(ref.id);
      if (color !== undefined) {
        return color;
      }
    }
    return undefined;
  }

  /**
   * Build the color map the layout consults, from the refs the panel knows.
   *
   * Kept separate from `computeSwimlanes` so a caller can supply its own
   * mapping — the incoming/outgoing work will need to add the remote and
   * base refs here.
   *
   * @param {string | null} headRefId Full refname HEAD is on, if any.
   * @returns {Map<string, string>}
   */
  function buildRefColors(headRefId) {
    const colors = new Map();
    if (headRefId) {
      colors.set(headRefId, HEAD_LANE_COLOR);
    }
    return colors;
  }

  /**
   * Assign swimlanes to a run of commits.
   *
   * Port of `toISCMHistoryItemViewModelArray`. The invariant: a row's
   * input lanes are the previous row's output lanes. Walking a row
   * replaces the lane carrying that commit with its first parent, and
   * appends one new lane per additional parent — which is exactly why a
   * merge fans out downward and a branch point converges.
   *
   * Commits must arrive in `--topo-order`, the order `/api/git/log`
   * returns, or lanes will interleave and the graph becomes unreadable.
   *
   * @param {MetabrowserGitCommit[]} commits
   * @param {object} [options]
   * @param {MetabrowserGitGraphLane[]} [options.priorSwimlanes] Trailing lanes from the
   *   previous page. Omit for the first page.
   * @param {number} [options.colorIndex] Palette cursor from the previous
   *   page. Omit for the first page.
   * @param {string | null} [options.headRevision] Commit id HEAD resolves
   *   to; that row is drawn with the HEAD marker.
   * @param {Map<string, string>} [options.refColors]
   * @returns {MetabrowserGitSwimlaneResult}
   */
  function computeSwimlanes(commits, options = {}) {
    const refColors = options.refColors ?? new Map();
    const headRevision = options.headRevision ?? null;

    /** @type {MetabrowserGitGraphRow[]} */
    const rows = [];
    let colorIndex = typeof options.colorIndex === "number" ? options.colorIndex : -1;
    let previousOutput = cloneLanes(options.priorSwimlanes ?? []);

    for (const commit of commits) {
      const inputSwimlanes = cloneLanes(previousOutput);
      /** @type {MetabrowserGitGraphLane[]} */
      const outputSwimlanes = [];
      let firstParentAdded = false;

      // Carry every input lane forward, substituting this commit's
      // first parent for the lane that was leading to this commit. Only
      // the first such lane is substituted: if two lanes both lead here
      // (a branch point) the extras are dropped, which is the visual
      // convergence.
      if (commit.parent_ids.length > 0) {
        for (const lane of inputSwimlanes) {
          if (lane.id === commit.id) {
            if (!firstParentAdded) {
              outputSwimlanes.push({
                id: commit.parent_ids[0],
                color: labelColor(commit, refColors) ?? lane.color,
              });
              firstParentAdded = true;
            }
            continue;
          }
          outputSwimlanes.push({ id: lane.id, color: lane.color });
        }
      }

      // Parents with no lane yet get one appended: the commit's own lane
      // when it was not already in flight (index 0), then one per extra
      // merge parent.
      for (let i = firstParentAdded ? 1 : 0; i < commit.parent_ids.length; i += 1) {
        let color;
        if (i === 0) {
          color = labelColor(commit, refColors);
        } else {
          // Scoped to the commits in hand, matching upstream, which
          // searches only the history items it has loaded. A merge
          // parent that falls on a later page therefore takes a palette
          // color rather than its ref's color — the same behavior as the
          // editor, and self-correcting once that page loads.
          const parent = commits.find((candidate) => candidate.id === commit.parent_ids[i]);
          color = parent ? labelColor(parent, refColors) : undefined;
        }
        if (!color) {
          colorIndex = rot(colorIndex + 1, LANE_COLORS.length);
          color = LANE_COLORS[colorIndex];
        }
        outputSwimlanes.push({ id: commit.parent_ids[i], color });
      }

      rows.push({
        commit,
        inputSwimlanes,
        outputSwimlanes,
        kind: headRevision !== null && commit.id === headRevision ? "HEAD" : "node",
      });
      previousOutput = outputSwimlanes;
    }

    return { rows, trailingSwimlanes: cloneLanes(previousOutput), colorIndex };
  }

  /**
   * @param {MetabrowserGitGraphLane[]} lanes
   * @returns {MetabrowserGitGraphLane[]}
   */
  function cloneLanes(lanes) {
    return lanes.map((lane) => ({ id: lane.id, color: lane.color }));
  }

  /**
   * The lane index a row's commit node sits on.
   *
   * Upstream's `getHistoryItemIndex`. A commit already in flight keeps
   * its lane; a commit nothing points at yet (the tip of a branch) is
   * placed just past the last lane.
   *
   * @param {MetabrowserGitGraphRow} row
   * @returns {number}
   */
  function commitLaneIndex(row) {
    const inputIndex = row.inputSwimlanes.findIndex((lane) => lane.id === row.commit.id);
    return inputIndex !== -1 ? inputIndex : row.inputSwimlanes.length;
  }

  /**
   * @param {string} color
   * @param {number} [strokeWidth]
   * @returns {SVGPathElement}
   */
  function createPath(color, strokeWidth = 1) {
    const path = document.createElementNS(SVG_NAMESPACE, "path");
    path.setAttribute("fill", "none");
    path.setAttribute("stroke-width", `${strokeWidth}px`);
    path.setAttribute("stroke-linecap", "round");
    path.style.stroke = color;
    return path;
  }

  /**
   * @param {number} index Lane index.
   * @param {number} radius
   * @param {number} strokeWidth
   * @param {string} [color] Omitted for the hollow inner circle, whose
   *   fill comes from CSS so it matches the row background.
   * @returns {SVGCircleElement}
   */
  function drawCircle(index, radius, strokeWidth, color) {
    const circle = document.createElementNS(SVG_NAMESPACE, "circle");
    circle.setAttribute("cx", `${SWIMLANE_WIDTH * (index + 1)}`);
    circle.setAttribute("cy", `${SWIMLANE_WIDTH}`);
    circle.setAttribute("r", `${radius}`);
    circle.style.strokeWidth = `${strokeWidth}px`;
    if (color) {
      circle.style.fill = color;
    }
    return circle;
  }

  /**
   * @param {number} index
   * @param {number} strokeWidth
   * @param {string} color
   * @returns {SVGCircleElement}
   */
  function drawDashedCircle(index, strokeWidth, color) {
    const circle = document.createElementNS(SVG_NAMESPACE, "circle");
    circle.setAttribute("cx", `${SWIMLANE_WIDTH * (index + 1)}`);
    circle.setAttribute("cy", `${SWIMLANE_WIDTH}`);
    circle.setAttribute("r", `${CIRCLE_RADIUS - CIRCLE_CENTER_RADIUS}`);
    circle.style.stroke = color;
    circle.style.strokeWidth = `${strokeWidth}px`;
    circle.style.strokeDasharray = "4,2";
    return circle;
  }

  /**
   * @param {number} x
   * @param {number} y1
   * @param {number} y2
   * @param {string} color
   * @param {number} [strokeWidth]
   * @returns {SVGPathElement}
   */
  function drawVerticalLine(x, y1, y2, color, strokeWidth = 1) {
    const path = createPath(color, strokeWidth);
    path.setAttribute("d", `M ${x} ${y1} V ${y2}`);
    return path;
  }

  /**
   * Last index of a lane leading to `id`.
   *
   * Upstream searches backwards on purpose: when a merge brings in a
   * parent that already had a lane, the *newly appended* lane is the one
   * the merge curve should attach to.
   *
   * @param {MetabrowserGitGraphLane[]} lanes
   * @param {string} id
   * @returns {number}
   */
  function findLastLaneIndex(lanes, id) {
    for (let i = lanes.length - 1; i >= 0; i -= 1) {
      if (lanes[i].id === id) {
        return i;
      }
    }
    return -1;
  }

  /**
   * Render one row's gutter as a standalone SVG element.
   *
   * Port of `renderSCMHistoryItemGraph`. The element is exactly one row
   * tall and as wide as the row's lanes require, so rows can be created
   * and discarded as the list scrolls.
   *
   * @param {MetabrowserGitGraphRow} row
   * @returns {SVGSVGElement}
   */
  function renderCommitGraph(row) {
    const svg = document.createElementNS(SVG_NAMESPACE, "svg");
    svg.classList.add("git-graph-svg");

    const commit = row.commit;
    const inputSwimlanes = row.inputSwimlanes;
    const outputSwimlanes = row.outputSwimlanes;

    const inputIndex = inputSwimlanes.findIndex((lane) => lane.id === commit.id);
    const circleIndex = inputIndex !== -1 ? inputIndex : inputSwimlanes.length;

    // The node takes its color from the lane leaving it where possible,
    // so a commit and the history below it share one color.
    let circleColor;
    if (circleIndex < outputSwimlanes.length) {
      circleColor = outputSwimlanes[circleIndex].color;
    } else if (circleIndex < inputSwimlanes.length) {
      circleColor = inputSwimlanes[circleIndex].color;
    } else {
      circleColor = HEAD_LANE_COLOR;
    }

    let outputSwimlaneIndex = 0;
    for (let index = 0; index < inputSwimlanes.length; index += 1) {
      const color = inputSwimlanes[index].color;

      if (inputSwimlanes[index].id === commit.id) {
        // A second lane arriving at this commit: draw it curving in to
        // the node's lane. This is the branch-point convergence.
        if (index !== circleIndex) {
          const path = createPath(color);
          const d = [
            `M ${SWIMLANE_WIDTH * (index + 1)} 0`,
            `A ${SWIMLANE_WIDTH} ${SWIMLANE_WIDTH} 0 0 1 ${SWIMLANE_WIDTH * index} ${SWIMLANE_WIDTH}`,
            `H ${SWIMLANE_WIDTH * (circleIndex + 1)}`,
          ];
          path.setAttribute("d", d.join(" "));
          svg.append(path);
        } else {
          outputSwimlaneIndex += 1;
        }
        continue;
      }

      // A lane passing through this row. Straight down if it keeps its
      // index; otherwise an S-curve into its new index, which is how
      // lanes close up after a branch ends.
      if (
        outputSwimlaneIndex < outputSwimlanes.length &&
        inputSwimlanes[index].id === outputSwimlanes[outputSwimlaneIndex].id
      ) {
        if (index === outputSwimlaneIndex) {
          svg.append(drawVerticalLine(SWIMLANE_WIDTH * (index + 1), 0, SWIMLANE_HEIGHT, color));
        } else {
          const path = createPath(color);
          const d = [
            `M ${SWIMLANE_WIDTH * (index + 1)} 0`,
            "V 6",
            `A ${SWIMLANE_CURVE_RADIUS} ${SWIMLANE_CURVE_RADIUS} 0 0 1 ${
              SWIMLANE_WIDTH * (index + 1) - SWIMLANE_CURVE_RADIUS
            } ${SWIMLANE_HEIGHT / 2}`,
            `H ${SWIMLANE_WIDTH * (outputSwimlaneIndex + 1) + SWIMLANE_CURVE_RADIUS}`,
            `A ${SWIMLANE_CURVE_RADIUS} ${SWIMLANE_CURVE_RADIUS} 0 0 0 ${
              SWIMLANE_WIDTH * (outputSwimlaneIndex + 1)
            } ${SWIMLANE_HEIGHT / 2 + SWIMLANE_CURVE_RADIUS}`,
            `V ${SWIMLANE_HEIGHT}`,
          ];
          path.setAttribute("d", d.join(" "));
          svg.append(path);
        }
        outputSwimlaneIndex += 1;
      }
    }

    // Merge parents beyond the first: a curve from the node out to each
    // newly opened lane. This is the visible fan-out of a merge.
    for (let i = 1; i < commit.parent_ids.length; i += 1) {
      const parentOutputIndex = findLastLaneIndex(outputSwimlanes, commit.parent_ids[i]);
      if (parentOutputIndex === -1) {
        continue;
      }
      const path = createPath(outputSwimlanes[parentOutputIndex].color);
      const d = [
        `M ${SWIMLANE_WIDTH * parentOutputIndex} ${SWIMLANE_HEIGHT / 2}`,
        `A ${SWIMLANE_WIDTH} ${SWIMLANE_WIDTH} 0 0 1 ${
          SWIMLANE_WIDTH * (parentOutputIndex + 1)
        } ${SWIMLANE_HEIGHT}`,
        `M ${SWIMLANE_WIDTH * parentOutputIndex} ${SWIMLANE_HEIGHT / 2}`,
        `H ${SWIMLANE_WIDTH * (circleIndex + 1)} `,
      ];
      path.setAttribute("d", d.join(" "));
      svg.append(path);
    }

    // Stub above the node, drawn only when something above leads here.
    if (inputIndex !== -1) {
      svg.append(
        drawVerticalLine(
          SWIMLANE_WIDTH * (circleIndex + 1),
          0,
          SWIMLANE_HEIGHT / 2,
          inputSwimlanes[inputIndex].color,
        ),
      );
    }

    // Stub below the node, drawn only when the commit has a parent — so
    // a root commit's lane visibly ends.
    if (commit.parent_ids.length > 0) {
      svg.append(
        drawVerticalLine(
          SWIMLANE_WIDTH * (circleIndex + 1),
          SWIMLANE_HEIGHT / 2,
          SWIMLANE_HEIGHT,
          circleColor,
        ),
      );
    }

    appendCommitNode(svg, row, circleIndex, circleColor);

    svg.style.height = `${SWIMLANE_HEIGHT}px`;
    svg.style.width = `${
      SWIMLANE_WIDTH * (Math.max(inputSwimlanes.length, outputSwimlanes.length, 1) + 1)
    }px`;
    return svg;
  }

  /**
   * Draw the node itself. Four variants, each visually distinct at a
   * glance: HEAD, incoming/outgoing changes, a merge, and a plain commit.
   *
   * @param {SVGSVGElement} svg
   * @param {MetabrowserGitGraphRow} row
   * @param {number} circleIndex
   * @param {string} circleColor
   */
  function appendCommitNode(svg, row, circleIndex, circleColor) {
    if (row.kind === "HEAD") {
      svg.append(drawCircle(circleIndex, CIRCLE_RADIUS, CIRCLE_STROKE_WIDTH, circleColor));
      // The unfilled inner circle inherits the current row background,
      // leaving a hollow HEAD ring through hover and selection states.
      svg.append(drawCircle(circleIndex, CIRCLE_STROKE_WIDTH, CIRCLE_STROKE_WIDTH));
      return;
    }

    // Not produced yet — incoming/outgoing rows are a non-goal for this
    // version — but kept so adding them is a data change, not a
    // renderer change.
    if (row.kind === "incoming-changes" || row.kind === "outgoing-changes") {
      svg.append(drawCircle(circleIndex, CIRCLE_RADIUS, CIRCLE_STROKE_WIDTH, circleColor));
      svg.append(
        drawCircle(circleIndex, CIRCLE_RADIUS - CIRCLE_CENTER_RADIUS, CIRCLE_STROKE_WIDTH),
      );
      svg.append(
        drawDashedCircle(circleIndex, CIRCLE_STROKE_WIDTH - CIRCLE_CENTER_RADIUS, circleColor),
      );
      return;
    }

    if (row.commit.parent_ids.length > 1) {
      // Merge: a ring around a smaller filled dot, kept inside the same
      // outer radius as every other vertex.
      svg.append(drawCircle(circleIndex, CIRCLE_RADIUS, CIRCLE_STROKE_WIDTH, circleColor));
      svg.append(drawCircle(circleIndex, CIRCLE_STROKE_WIDTH, CIRCLE_STROKE_WIDTH));
      svg.append(drawCircle(circleIndex, CIRCLE_CENTER_RADIUS, CIRCLE_STROKE_WIDTH, circleColor));
      return;
    }

    svg.append(drawCircle(circleIndex, CIRCLE_RADIUS, CIRCLE_STROKE_WIDTH, circleColor));
  }

  /**
   * Width in pixels a row's gutter will occupy.
   *
   * The panel reserves one width for every row so the subjects line up
   * in a single column instead of stepping in and out as lanes open and
   * close. Callers take the max over the rows they have.
   *
   * @param {MetabrowserGitGraphRow} row
   * @returns {number}
   */
  function graphWidth(row) {
    const lanes = Math.max(row.inputSwimlanes.length, row.outputSwimlanes.length, 1);
    return SWIMLANE_WIDTH * (lanes + 1);
  }

  window.MetabrowserGitGraph = Object.freeze({
    CIRCLE_RADIUS,
    CIRCLE_STROKE_WIDTH,
    HEAD_LANE_COLOR,
    LANE_COLORS,
    SWIMLANE_CURVE_RADIUS,
    SWIMLANE_HEIGHT,
    SWIMLANE_WIDTH,
    buildRefColors,
    commitLaneIndex,
    computeSwimlanes,
    graphWidth,
    renderCommitGraph,
  });
})();

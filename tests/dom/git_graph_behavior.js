// Behavioral checks for the commit-graph swimlane layout and renderer.
//
// The layout is a pure function of commit ids and parent ids, so it is
// tested against hand-written histories rather than a real repository:
// the topologies that matter (octopus merges, a branch that ends
// mid-page, a page boundary) are tedious to construct with git and
// trivial to write here.
//
// Assertions are on lane assignment rather than incidental pixels. The
// one geometry contract pinned below is that every vertex has the same
// outer radius; changing that would reintroduce visual weight that is
// unrelated to the lane topology.

const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const repoRoot = path.resolve(__dirname, "../..");

// Minimal SVG-capable document. renderCommitGraph only ever creates
// namespaced elements, sets attributes and inline styles, and appends —
// so this is the whole surface it touches.
class FakeSvgElement {
  constructor(tagName) {
    this.tagName = tagName;
    this.attributes = new Map();
    this.children = [];
    this.style = {};
    this.classNames = new Set();
    this.classList = {
      add: (...names) => {
        for (const name of names) {
          this.classNames.add(name);
        }
      },
    };
  }

  setAttribute(name, value) {
    this.attributes.set(name, String(value));
  }

  getAttribute(name) {
    return this.attributes.has(name) ? this.attributes.get(name) : null;
  }

  append(...nodes) {
    this.children.push(...nodes);
  }
}

const sandbox = {};
sandbox.window = sandbox;
sandbox.globalThis = sandbox;
sandbox.document = {
  createElementNS: (_ns, tagName) => new FakeSvgElement(tagName),
};
vm.createContext(sandbox);

const source = fs.readFileSync(path.join(repoRoot, "src/metabrowser/static/git_graph.js"), "utf-8");
vm.runInContext(source, sandbox, { filename: "git_graph.js" });

const graph = sandbox.MetabrowserGitGraph;
const failures = [];

function assertEqual(label, actual, expected) {
  const a = JSON.stringify(actual);
  const b = JSON.stringify(expected);
  if (a !== b) {
    failures.push(`${label}: expected ${b} got ${a}`);
  }
}

function assertTrue(label, value) {
  if (!value) {
    failures.push(`${label}: expected true`);
  }
}

// Commit ids are full object ids on the wire; here they are short readable
// labels, since the layout only ever compares them for equality.
function commit(id, parents, refs) {
  const result = { id, parent_ids: parents };
  if (refs) {
    result.refs = refs;
  }
  return result;
}

function laneIds(lanes) {
  return lanes.map((lane) => lane.id);
}

function countTags(svg, tagName) {
  return svg.children.filter((child) => child.tagName === tagName).length;
}

// ── Linear history ───────────────────────────────────────────

{
  // c -> b -> a. One lane, carried the whole way down.
  const commits = [commit("c", ["b"]), commit("b", ["a"]), commit("a", [])];
  const { rows, trailingSwimlanes } = graph.computeSwimlanes(commits);

  assertEqual("linear: row count", rows.length, 3);
  assertEqual("linear: first row has no input lanes", laneIds(rows[0].inputSwimlanes), []);
  assertEqual("linear: first row outputs its parent", laneIds(rows[0].outputSwimlanes), ["b"]);
  assertEqual("linear: second row inherits", laneIds(rows[1].inputSwimlanes), ["b"]);
  assertEqual("linear: second row outputs", laneIds(rows[1].outputSwimlanes), ["a"]);
  // The root commit has no parent, so its lane closes rather than
  // continuing into nothing.
  assertEqual("linear: root closes the lane", laneIds(rows[2].outputSwimlanes), []);
  assertEqual("linear: trailing lanes empty", laneIds(trailingSwimlanes), []);

  assertEqual("linear: every commit sits on lane 0", rows.map(graph.commitLaneIndex), [0, 0, 0]);
}

// ── Merge ────────────────────────────────────────────────────

{
  //   m (merge of b and c)
  //   ├─ b
  //   └─ c
  //      a
  const commits = [
    commit("m", ["b", "c"]),
    commit("b", ["a"]),
    commit("c", ["a"]),
    commit("a", []),
  ];
  const { rows } = graph.computeSwimlanes(commits);

  // The merge opens a second lane: first parent keeps the merge's lane,
  // the second parent gets a new one beside it.
  assertEqual("merge: opens a second lane", laneIds(rows[0].outputSwimlanes), ["b", "c"]);
  assertEqual("merge: b row keeps both lanes in", laneIds(rows[1].inputSwimlanes), ["b", "c"]);
  assertEqual("merge: b resolves to a", laneIds(rows[1].outputSwimlanes), ["a", "c"]);
  assertEqual("merge: c row inputs", laneIds(rows[2].inputSwimlanes), ["a", "c"]);
  // Both lanes now lead to `a`. They are *not* collapsed here: the
  // convergence is drawn on the row that owns `a`, one row further down,
  // which is what makes the two strands visibly meet at the commit
  // rather than merging into empty space above it.
  assertEqual("merge: both lanes lead to a", laneIds(rows[2].outputSwimlanes), ["a", "a"]);
  assertEqual("merge: c sits on lane 1", graph.commitLaneIndex(rows[2]), 1);
  assertEqual("merge: a collapses both lanes", laneIds(rows[3].outputSwimlanes), []);
  assertEqual("merge: a sits on lane 0", graph.commitLaneIndex(rows[3]), 0);

  // The two merge lanes must be visually distinguishable, or a merge
  // reads as a single strand.
  const [first, second] = rows[0].outputSwimlanes;
  assertTrue("merge: lanes take different colors", first.color !== second.color);
}

// ── Octopus merge ────────────────────────────────────────────

{
  const commits = [
    commit("o", ["p1", "p2", "p3"]),
    commit("p1", []),
    commit("p2", []),
    commit("p3", []),
  ];
  const { rows } = graph.computeSwimlanes(commits);

  assertEqual("octopus: one lane per parent", laneIds(rows[0].outputSwimlanes), ["p1", "p2", "p3"]);
  const colors = new Set(rows[0].outputSwimlanes.map((lane) => lane.color));
  assertEqual("octopus: three distinct lane colors", colors.size, 3);
}

// ── A branch that ends mid-page ──────────────────────────────

{
  //  tip      (on the main lane)
  //  side     (a branch tip nothing else references)
  //  base
  const commits = [commit("tip", ["base"]), commit("side", ["base"]), commit("base", [])];
  const { rows } = graph.computeSwimlanes(commits);

  assertEqual("mid-page branch: tip outputs base", laneIds(rows[0].outputSwimlanes), ["base"]);
  // `side` is not in the incoming lanes, so it takes a lane past the end
  // rather than displacing the lane already leading to `base`.
  assertEqual("mid-page branch: side takes a new lane", graph.commitLaneIndex(rows[1]), 1);
  assertEqual("mid-page branch: both lanes lead to base", laneIds(rows[1].outputSwimlanes), [
    "base",
    "base",
  ]);
  assertEqual("mid-page branch: base collapses them", laneIds(rows[2].outputSwimlanes), []);
}

// ── A root commit reached while another lane is in flight ────

{
  //  m        merge of two unrelated histories
  //  a1
  //  a0       root of the first history — b1's lane is still in flight
  //  b1
  //  b0       root of the second
  //
  // Upstream emits no output lanes at all for a root commit, which drops
  // every unrelated lane with it. A single-root repository puts its root
  // last, where nothing is in flight, so the bug stays invisible there.
  const commits = [
    commit("m", ["a1", "b1"]),
    commit("a1", ["a0"]),
    commit("a0", []),
    commit("b1", ["b0"]),
    commit("b0", []),
  ];
  const { rows } = graph.computeSwimlanes(commits);

  assertEqual("multi-root: merge opens both lanes", laneIds(rows[0].outputSwimlanes), ["a1", "b1"]);
  assertEqual("multi-root: first root keeps the sibling lane", laneIds(rows[2].outputSwimlanes), [
    "b1",
  ]);
  // The surviving lane is what draws b1 as a continuation rather than as
  // a disconnected tip floating below the graph.
  assertEqual("multi-root: sibling stays connected", laneIds(rows[3].inputSwimlanes), ["b1"]);
  assertEqual("multi-root: sibling keeps its column", graph.commitLaneIndex(rows[3]), 0);
  assertEqual("multi-root: last root collapses", laneIds(rows[4].outputSwimlanes), []);
}

// ── Page boundary continuity ─────────────────────────────────

{
  const all = [commit("m", ["b", "c"]), commit("b", ["a"]), commit("c", ["a"]), commit("a", [])];
  const whole = graph.computeSwimlanes(all).rows;

  // Split at an index where two lanes are in flight — the case that
  // actually breaks if continuity is not threaded through.
  const firstPage = graph.computeSwimlanes(all.slice(0, 2));
  const secondPage = graph.computeSwimlanes(all.slice(2), {
    priorSwimlanes: firstPage.trailingSwimlanes,
    colorIndex: firstPage.colorIndex,
  });

  const paged = [...firstPage.rows, ...secondPage.rows];
  assertEqual("paging: same row count", paged.length, whole.length);
  for (let i = 0; i < whole.length; i += 1) {
    assertEqual(
      `paging: row ${i} input lanes`,
      laneIds(paged[i].inputSwimlanes),
      laneIds(whole[i].inputSwimlanes),
    );
    assertEqual(
      `paging: row ${i} output lanes`,
      laneIds(paged[i].outputSwimlanes),
      laneIds(whole[i].outputSwimlanes),
    );
    // Colors have to match too: restarting the palette cursor at a page
    // boundary would recolor lanes mid-scroll.
    assertEqual(
      `paging: row ${i} lane colors`,
      paged[i].outputSwimlanes.map((lane) => lane.color),
      whole[i].outputSwimlanes.map((lane) => lane.color),
    );
  }
}

// ── Ref colors ───────────────────────────────────────────────

{
  const refColors = graph.buildRefColors("refs/heads/main");
  const commits = [
    commit("c", ["b"], [{ id: "refs/heads/main", name: "main", kind: "branch", is_head: true }]),
    commit("b", ["a"]),
    commit("a", []),
  ];
  const { rows } = graph.computeSwimlanes(commits, { refColors, headRevision: "c" });

  // The branch HEAD is on keeps one color for its whole length instead
  // of drawing a rotating palette color.
  assertEqual(
    "ref colors: head lane uses the head token",
    rows[0].outputSwimlanes[0].color,
    graph.HEAD_LANE_COLOR,
  );
  assertEqual("ref colors: head row is marked", rows[0].kind, "HEAD");
  assertEqual("ref colors: other rows are plain", rows[1].kind, "node");
}

// ── Renderer structure ───────────────────────────────────────

{
  const commits = [
    commit("m", ["b", "c"]),
    commit("b", ["a"]),
    commit("c", ["a"]),
    commit("a", []),
  ];
  const { rows } = graph.computeSwimlanes(commits, { headRevision: "m" });

  const headSvg = graph.renderCommitGraph(rows[0]);
  // HEAD is a ring whose hole is a real hole — one evenodd path, no
  // background-coloured disc — so its shape cannot change with the row
  // state (hover, selection, or any state added later).
  const headRing = headSvg.children.find(
    (child) => child.tagName === "path" && child.getAttribute("fill-rule") === "evenodd",
  );
  assertTrue("render: HEAD draws a punched ring", Boolean(headRing));
  assertEqual("render: HEAD adds no filled centre", countTags(headSvg, "circle"), 0);
  assertEqual("render: row is one row tall", headSvg.style.height, "22px");
  assertTrue("render: svg is class-tagged", headSvg.classNames.has("git-graph-svg"));

  const mergeRows = graph.computeSwimlanes(commits).rows;
  const mergeSvg = graph.renderCommitGraph(mergeRows[0]);
  // A merge keeps its ring + dot distinction without growing beyond a
  // plain vertex: a punched ring plus one filled centre dot.
  const mergeRing = mergeSvg.children.find(
    (child) => child.tagName === "path" && child.getAttribute("fill-rule") === "evenodd",
  );
  assertTrue("render: merge draws a punched ring", Boolean(mergeRing));
  assertEqual("render: merge draws one centre dot", countTags(mergeSvg, "circle"), 1);
  // The merge fan-out is an arc; a merge drawn with only straight lines
  // would not read as a merge.
  const mergePaths = mergeSvg.children.filter((child) => child.tagName === "path");
  assertTrue(
    "render: merge draws an arc",
    mergePaths.some((p) => (p.getAttribute("d") ?? "").includes("A ")),
  );

  const plainSvg = graph.renderCommitGraph(mergeRows[1]);
  assertEqual("render: plain commit draws one circle", countTags(plainSvg, "circle"), 1);
  // Every vertex occupies the same outer radius, whether it is drawn as
  // a punched ring or a plain filled circle.
  const outerRadii = [headSvg, mergeSvg, plainSvg].map((svg) => {
    const ring = svg.children.find(
      (child) => child.tagName === "path" && child.getAttribute("fill-rule") === "evenodd",
    );
    if (ring) {
      // `M <cx - r> <cy> a <r> <r> ...` — the first arc radius is the outer one.
      return (ring.getAttribute("d") ?? "").split(" a ")[1]?.split(" ")[0];
    }
    return svg.children.find((child) => child.tagName === "circle")?.getAttribute("r");
  });
  assertEqual(
    "render: every vertex uses the same outer radius",
    outerRadii,
    outerRadii.map(() => `${graph.CIRCLE_RADIUS}`),
  );

  const rootSvg = graph.renderCommitGraph(mergeRows[3]);
  // A root commit has no parent, so nothing is drawn below its node.
  const rootPaths = rootSvg.children.filter((child) => child.tagName === "path");
  assertTrue(
    "render: root commit draws no line below the node",
    rootPaths.every((p) => !(p.getAttribute("d") ?? "").includes("M 11 11 V 22")),
  );
}

// ── Gutter width ─────────────────────────────────────────────

{
  const commits = [commit("m", ["b", "c"]), commit("b", ["a"]), commit("c", ["a"])];
  const { rows } = graph.computeSwimlanes(commits);
  // Two lanes in flight plus the trailing margin lane.
  assertEqual("width: two lanes", graph.graphWidth(rows[1]), graph.SWIMLANE_WIDTH * 3);
  const single = graph.computeSwimlanes([commit("x", [])]);
  // A single-lane row still reserves a lane, so an empty gutter does not
  // collapse to zero width and shift the subject column.
  assertEqual(
    "width: minimum one lane",
    graph.graphWidth(single.rows[0]),
    graph.SWIMLANE_WIDTH * 2,
  );
}

if (failures.length > 0) {
  console.error(`FAILURES (${failures.length}):`);
  for (const failure of failures) {
    console.error(`  - ${failure}`);
  }
  process.exit(1);
}

console.log(`OK ${"git graph layout and renderer"}`);

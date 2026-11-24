const fs = require("node:fs");
const path = require("node:path");
const { pathToFileURL } = require("node:url");

const repoRoot = path.resolve(process.argv[2]);

// The folder plugin's modules have no package.json saying they are modules, which the
// browser never asks about, and folder-totals.js imports the hover it draws, so it is
// loaded from its file. Node's warning names the process and the checkout.
const emitWarning = process.emitWarning;
process.emitWarning = (warning, ...rest) => {
  if (String(warning).includes("is not specified and it doesn't parse as CommonJS")) {
    return;
  }
  emitWarning.call(process, warning, ...rest);
};
const failures = [];

function check(name, condition, detail = "failed") {
  if (!condition) {
    failures.push(`${name}: ${detail}`);
  }
}

class Element {
  constructor(tag) {
    this.tagName = tag.toUpperCase();
    this.children = [];
    this.parentNode = null;
    this.className = "";
    this.dataset = {};
    this.style = {};
    this.attributes = {};
    this.listeners = {};
    this.classList = {
      add: (...names) => {
        this.className = [...new Set([...this.className.split(" "), ...names])]
          .filter(Boolean)
          .join(" ");
      },
      contains: (name) => this.className.split(" ").includes(name),
    };
    this.scope = "";
    this.textContent = "";
    this._innerHTML = "";
  }

  append(...children) {
    for (const child of children) {
      child.parentNode = this;
      this.children.push(child);
    }
  }

  replaceChildren(...children) {
    this.children = [];
    this._innerHTML = "";
    this.append(...children);
  }

  setAttribute(name, value) {
    this.attributes[name] = String(value);
  }

  addEventListener(type, listener) {
    this.listeners[type] = listener;
  }

  emit(type, event = {}) {
    this.listeners[type]?.(event);
  }

  set innerHTML(value) {
    this._innerHTML = value;
    this.children = [];
  }

  get innerHTML() {
    return this._innerHTML;
  }

  /** In the document: each parent up to its body still holds the element. */
  get isConnected() {
    let node = this;
    while (node.parentNode?.children.includes(node)) {
      node = node.parentNode;
    }
    return node === document.body;
  }

  /** Whether *other* is this element or inside it. */
  contains(other) {
    for (let node = other; node; node = node.parentNode) {
      if (node === this) {
        return true;
      }
      if (!node.parentNode?.children.includes(node)) {
        return false;
      }
    }
    return false;
  }
}

global.document = { createElement: (tag) => new Element(tag) };
document.body = new Element("body");

(async () => {
  const folder = (name) =>
    pathToFileURL(path.join(repoRoot, "src/metabrowser/builtin_plugins/folder", name)).href;
  const styles = fs.readFileSync(
    path.join(repoRoot, "src/metabrowser/builtin_plugins/folder/file_type_summary.css"),
    "utf8",
  );
  const sharedStyles = fs.readFileSync(
    path.join(repoRoot, "src/metabrowser/static/styles.css"),
    "utf8",
  );
  const module = await import(folder("folder-totals.js"));
  const { createDistributionHover } = await import(folder("distribution-hover.js"));
  const tooltipCalls = [];
  const mb = {
    countClass: () => "",
    escapeHtml: (value) => String(value).replaceAll("&", "&amp;").replaceAll("<", "&lt;"),
    formatFileCount: (value) => `${value} files`,
    formatSize: (value) => `${value} B`,
    // The icon registry by path, as the Details table's rows look a family's up.
    fileTypeIcon: (iconPath) =>
      iconPath === "x.py"
        ? { className: "ft-python", svg: "<svg>py</svg>" }
        : { className: "", svg: "" },
    sizeClass: () => "",
    tooltip: {
      hide: (within) => tooltipCalls.push({ action: "hide", within }),
      show: (html, anchor) => tooltipCalls.push({ action: "show", anchor, html }),
    },
  };
  const totals = module.normalizeFolderTotals({
    total_files: 100,
    total_size: 500,
    unignored_files: 80,
    unignored_size: 300,
  });
  const container = new Element("div");
  // Bars with a hover of their own, as every caller gives them one to share.
  const view = module.mountFolderTotalsView(
    container,
    totals,
    mb,
    "size",
    createDistributionHover(),
  );
  const table = container.children[0].children[0];
  const body = table.children[2];
  const filesRow = body.children[0];
  const ignoredRow = body.children[1];
  const filesContents = filesRow.children[1].children[0];
  const ignoredContents = ignoredRow.children[1].children[0];
  const filesTrack = filesContents.children[1];
  const ignoredTrack = ignoredContents.children[1];

  check(
    "population rows show only a tally and one full-width composition track",
    filesContents.children.length === 2 &&
      filesContents.children[0].textContent === "300 B" &&
      filesTrack.children.length === 1 &&
      filesTrack.children[0].style.width === "100%",
    `${filesContents.children.length} metric children`,
  );
  check(
    "ignored population starts as an independently full-width track",
    ignoredContents.children.length === 2 &&
      ignoredContents.children[0].textContent === "200 B" &&
      ignoredTrack.children[0].style.width === "100%",
    `${ignoredContents.children.length} metric children`,
  );

  const composition = {
    metric: "size",
    files: {
      value: 300,
      segments: [
        {
          key: "family:python",
          label: "Python",
          category: "Code",
          iconPath: "x.py",
          paletteKey: "family:python",
          files: 18,
          bytes: 180,
          value: 180,
          share: 60,
        },
        {
          key: "family:markdown",
          label: "Markdown",
          category: "",
          iconPath: null,
          paletteKey: "family:markdown",
          files: 12,
          bytes: 120,
          value: 120,
          share: 40,
        },
      ],
    },
    ignored: {
      value: 200,
      segments: [
        {
          key: "family:python",
          label: "Python",
          paletteKey: "family:python",
          files: 5,
          bytes: 50,
          value: 50,
          share: 25,
        },
        {
          key: "family:javascript",
          label: "JavaScript",
          paletteKey: "family:javascript",
          files: 15,
          bytes: 150,
          value: 150,
          share: 75,
        },
      ],
    },
  };
  view.updateComposition(composition, {
    classFor: (key) => `slot-${key.replace("family:", "")}`,
    styleFor: () => "",
    paint: (element, key) => {
      element.classList.add(`slot-${key.replace("family:", "")}`);
    },
  });
  check(
    "Files bar is segmented with shared file-type colors",
    filesTrack.children.length === 2 &&
      filesTrack.children[0].className.includes("slot-python") &&
      filesTrack.children[1].className.includes("slot-markdown") &&
      filesTrack.children[0].style.width === "60%" &&
      filesTrack.children[1].style.width === "40%",
    `${filesTrack.children.length} Files segments`,
  );
  check(
    "Ignored bar has its own independently normalized composition",
    ignoredTrack.children.length === 2 &&
      ignoredTrack.children[0].style.width === "25%" &&
      ignoredTrack.children[1].style.width === "75%",
    `${ignoredTrack.children.length} Ignored segments`,
  );
  tooltipCalls.length = 0;
  const hoverEvent = { clientX: 20, clientY: 30 };
  const segment = filesTrack.children[0];
  const hoveredSegments = () =>
    [filesTrack, ignoredTrack].flatMap((track) =>
      track.children.filter((child) => "hovered" in child.dataset),
    );
  segment.emit("mouseenter", hoverEvent);
  const markedWhileHovered = hoveredSegments();
  segment.emit("mousemove", hoverEvent);
  segment.emit("mouseleave", hoverEvent);
  check(
    "semantic family segments reuse the shared nav tooltip",
    tooltipCalls[0]?.action === "show" &&
      tooltipCalls[0]?.html ===
        '<div class="data-label">Code</div>' +
          '<div class="tip-name tm-tip-name"><span class="file-identity-icon tm-tip-icon ft-python" aria-hidden="true"><svg>py</svg></span><span>Python</span></div>' +
          '<div class="tip-detail">18 files · 180 B</div>' &&
      tooltipCalls[1]?.action === "hide",
    JSON.stringify(tooltipCalls.map((c) => c.action)),
  );
  // A family with no category or icon to name says only its name and counts.
  tooltipCalls.length = 0;
  filesTrack.children[1].emit("mouseenter", hoverEvent);
  filesTrack.children[1].emit("mouseleave", hoverEvent);
  check(
    "a segment with no category or icon names only its family",
    tooltipCalls[0]?.html ===
      '<div class="tip-name tm-tip-name"><span>Markdown</span></div><div class="tip-detail">12 files · 120 B</div>',
    String(tooltipCalls[0]?.html),
  );
  tooltipCalls.length = 0;
  segment.emit("mouseenter", hoverEvent);
  segment.emit("mouseleave", hoverEvent);
  // The hover is drawn on the segment by an attribute, not by :hover, so a legend entry
  // naming the segment can draw it too; it marks that segment alone, and leaving takes it
  // off along with the tooltip, put away where it was anchored, on the segment.
  check(
    "a hovered segment is marked, alone, until the pointer leaves it",
    markedWhileHovered.length === 1 &&
      markedWhileHovered[0] === segment &&
      hoveredSegments().length === 0 &&
      tooltipCalls[1]?.within === segment,
    JSON.stringify({ marked: markedWhileHovered.length, after: hoveredSegments().length }),
  );
  // A tooltip names the segment it is on, so it is anchored to the segment and
  // never to the pointer. Moving the mouse across a segment must produce no
  // call at all: a tooltip that repositions while it is up jitters, and one
  // placed where the pointer happened to be does not say which segment it is
  // about. See docs/design-system.md, "A Tooltip Holds Still".
  check(
    "the tooltip anchors to the segment and ignores pointer movement",
    tooltipCalls[0]?.anchor === segment &&
      tooltipCalls.length === 2 &&
      !tooltipCalls.some((call) => call.action === "move"),
    JSON.stringify(tooltipCalls.map((c) => c.action)),
  );
  // The hover shift runs opposite ways per theme (deepen on the light page,
  // lift on the dark one), so both declarations have to be present. Their
  // values stay free to be adjusted without editing this check.
  const darkStart = sharedStyles.indexOf('[data-theme="dark"] {');
  check(
    "tooltip-bearing segments reuse the shared data-mark hover treatment",
    styles.includes(".file-type-summary-fill[data-hovered]") &&
      // One source of the hover: :hover too would mark a segment the hover has put away.
      !styles.includes(".file-type-summary-fill[data-segment-key]:hover") &&
      styles.includes("filter: var(--viz-data-mark-hover-filter);") &&
      darkStart > 0 &&
      sharedStyles.indexOf("--viz-data-mark-hover-filter:") < darkStart &&
      sharedStyles.lastIndexOf("--viz-data-mark-hover-filter:") > darkStart,
    styles,
  );
  // Hover is drawn on the marks the hover names and nowhere else. Nothing may key
  // off the track to reach a segment's siblings, and no rule may dim one: that was
  // the old treatment, and it made pointing at one segment restyle fifty. Not
  // scoped to the tally rows: a legend entry's hover marks its family's row in
  // the Details table too.
  const flattened = styles.replace(/\s+/g, " ");
  check(
    "a hovered mark grows and lifts its colour, and takes no outline",
    flattened.includes(
      " .file-type-summary-fill[data-hovered] { " +
        "filter: var(--viz-data-mark-hover-filter); " +
        "transform: scaleY(var(--viz-hover-grow)); z-index: 1; }",
    ) &&
      !styles.includes("--viz-hover-outline") &&
      // scaleX is the bug this replaced: on a horizontal bar the width is the
      // value, so growing it states a share the family does not have. Matched
      // as a declaration, since the stylesheet's own comment names it.
      !flattened.includes("transform: scaleX("),
    flattened.slice(0, 240),
  );
  // A transform, never width: the widths are percentages summing to 100, so
  // growing one in layout pushes the last segment past the end of the track. The
  // lift and the growth ease in and out as one motion on the viz layout scale's
  // plain ease, which does not overshoot: a spring that flicked past its target
  // read as a snap (docs/design-system.md, "Hover Styles the Thing Under the
  // Pointer").
  const layoutEase = /--viz-layout-ease:\s*([^;]+);/.exec(sharedStyles)?.[1].trim();
  check(
    "the lift and the growth ease in and out together on the layout scale",
    flattened.includes(
      "filter var(--viz-hover-grow-duration) var(--viz-hover-grow-ease), " +
        "transform var(--viz-hover-grow-duration) var(--viz-hover-grow-ease)",
    ) &&
      /--viz-hover-grow-duration:\s*var\(--viz-layout-duration\);/.test(sharedStyles) &&
      /--viz-hover-grow-ease:\s*var\(--viz-layout-ease\);/.test(sharedStyles) &&
      ["ease", "ease-in-out"].includes(layoutEase ?? ""),
    `--viz-layout-ease is ${layoutEase}`,
  );
  // The shimmer: a sheen's opacity on a pseudo-element, so the compositor runs it, on
  // its own tokens and keyframes beside the progress pulse's, which it is a gentler,
  // slower sibling of. The marks and the legend entry's dot share it.
  const shimmerKeyframes = /@keyframes viz-hover-shimmer \{([\s\S]*?)\n\}/.exec(sharedStyles);
  check(
    "a hovered mark and its entry's dot shimmer by opacity alone, on the shimmer's tokens",
    flattened.includes(
      ".file-type-summary-fill[data-hovered]::after, " +
        ".file-type-summary-legend-item[data-hovered] .file-type-summary-legend-swatch::after { " +
        'content: ""; position: absolute; inset: 0; border-radius: inherit; ' +
        "background: var(--viz-hover-shimmer-sheen); opacity: 0; pointer-events: none; " +
        "animation: viz-hover-shimmer var(--viz-hover-shimmer-period) ease-in-out " +
        "var(--viz-hover-grow-duration) infinite; }",
    ) &&
      shimmerKeyframes !== null &&
      new Set(shimmerKeyframes[1].match(/[a-z-]+(?=:)/g)).size === 1 &&
      shimmerKeyframes[1].includes("opacity: var(--viz-hover-shimmer-strength);") &&
      sharedStyles.indexOf("\n@keyframes viz-hover-shimmer {") >
        sharedStyles.indexOf("\n@keyframes tally-pending-pulse {") &&
      ["--viz-hover-shimmer-period:", "--viz-hover-shimmer-sheen:"].every(
        (token) => sharedStyles.indexOf(token) > 0 && sharedStyles.indexOf(token) < darkStart,
      ) &&
      sharedStyles.indexOf("--viz-hover-shimmer-strength:") < darkStart &&
      sharedStyles.lastIndexOf("--viz-hover-shimmer-strength:") > darkStart,
    shimmerKeyframes?.[1] ?? "no viz-hover-shimmer keyframes",
  );
  // The legend entry naming the hovered family answers with its marks: its dot lifts
  // as they do, and its name takes the family's ink, kept at 4.5:1 by the share
  // (tests/test_design_vocabulary.py). Colour and a filter only, so nothing moves.
  check(
    "the hovered family's entry lifts its dot and inks its name",
    flattened.includes(
      ".file-type-summary-legend-item[data-hovered] .file-type-summary-legend-swatch { " +
        "filter: var(--viz-data-mark-hover-filter); }",
    ) &&
      flattened.includes(
        ".file-type-summary-legend-item[data-hovered] .file-type-summary-legend-label { " +
          "color: color-mix( in oklab, var(--mb-distribution-color) " +
          "var(--mb-distribution-ink-share), var(--text) ); }",
      ),
    flattened.slice(flattened.indexOf(".file-type-summary-legend-item[data-hovered]"), 400),
  );
  check(
    "no rule dims a segment to pick out one of its siblings",
    !styles.includes(":not(:hover)") &&
      !styles.includes(":not([data-hovered])") &&
      !sharedStyles.includes("--mb-distribution-segment-recede"),
    styles.slice(0, 200),
  );
  // Reduced motion drops the motion, the transitions and the shimmer, and keeps the
  // stronger, wider highlight, drawn at once: a darker, thicker mark is a state, not
  // a movement.
  const reduced = flattened.slice(flattened.lastIndexOf("@media (prefers-reduced-motion: reduce)"));
  check(
    "reduced motion drops the transitions and the shimmer, and keeps the lift and growth",
    reduced.includes(
      ".file-type-summary-fill, .file-type-summary-legend-swatch, " +
        ".file-type-summary-legend-label { transition: none; }",
    ) &&
      reduced.includes(
        ".file-type-summary-fill[data-hovered]::after, " +
          ".file-type-summary-legend-item[data-hovered] .file-type-summary-legend-swatch::after " +
          "{ content: none; }",
      ) &&
      !reduced.includes("transform: none"),
    reduced.slice(0, 600),
  );
  // Segment widths are percentages that sum to 100, so the hairline between
  // them cannot occupy layout or the last segment leaves the track.
  check(
    "segments are separated by an inset hairline of the page ground",
    styles.includes("box-shadow: inset calc(-1 * var(--mb-distribution-segment-gap)) 0 0") &&
      styles.includes(":not(:last-child)") &&
      sharedStyles.includes("--mb-distribution-segment-gap:"),
    styles,
  );
  // A draw puts away its own segments' tooltip and no other surface's: the page has one
  // tooltip, and an unscoped hide on every draw took a Files tree row's from under a
  // pointer that had not moved (mb-alff, docs/design-system.md, "A Surface Puts Away Only
  // Its Own Tooltip").
  const totalsRoot = container.children[0];
  tooltipCalls.length = 0;
  view.update(totals);
  check(
    "a draw hides only a tooltip anchored in the totals",
    tooltipCalls.length === 1 &&
      tooltipCalls[0].action === "hide" &&
      tooltipCalls[0].within === totalsRoot,
    JSON.stringify(tooltipCalls.map((call) => [call.action, call.within === totalsRoot])),
  );
  view.dispose();
  check(
    "disposing Files clears its own tooltip",
    tooltipCalls.at(-1)?.action === "hide" && tooltipCalls.at(-1)?.within === totalsRoot,
    JSON.stringify(tooltipCalls.map((call) => call.action)),
  );
  check(
    "ignored row reuses the shared dimmed-content token",
    ignoredRow.className.includes("file-type-summary-ignored-row") &&
      styles.includes("opacity: var(--dimmed-content-opacity);") &&
      sharedStyles.includes("--dimmed-content-opacity: 0.45;"),
    ignoredRow.className,
  );
  check(
    "folder totals reserve no percentage column",
    styles.includes(".folder-totals .file-type-summary-metric-content") &&
      styles.includes("var(--file-type-summary-value-width) minmax(40px, 1fr)") &&
      !filesContents.children.some((child) =>
        child.className.includes("file-type-summary-percent"),
      ),
    styles,
  );

  // Bars that share their hover, as File Overview's do with the legend under them. A
  // segment's hover marks that segment alone. A hover entered from an element outside
  // the bars, as a legend entry enters it, names a family and marks the family's segment
  // in every row drawn, and shows one tooltip, the file count and byte size of the
  // segment in the row it names, anchored on that element, which shows the name; its
  // leave puts away only the tooltip anchored there. A row with no such segment adds no
  // mark, and if it is the named row, no tooltip. A draw puts away a hover held from a
  // segment, which it replaces, and draws again one held from an element it outlives,
  // while that element is in the document. Disposal lets go of the hover and stops
  // listening.
  const shared = createDistributionHover();
  const sharedContainer = new Element("div");
  // A legend entry, beside the bars and outside them.
  const entry = new Element("li");
  document.body.append(sharedContainer, entry);
  const sharedView = module.mountFolderTotalsView(sharedContainer, totals, mb, "size", shared);
  sharedView.updateComposition(composition, {
    classFor: () => "",
    styleFor: () => "",
    paint: () => {},
  });
  const sharedRoot = sharedContainer.children[0];
  const sharedBody = () => sharedRoot.children[0].children[2];
  const sharedTrack = (row) => sharedBody().children[row].children[1].children[0].children[1];
  const sharedMarked = () =>
    [0, 1].flatMap((row) => sharedTrack(row).children.filter((fill) => "hovered" in fill.dataset));
  /** A tooltip call, with its anchor named rather than serialized. */
  const named = (call) =>
    call && {
      action: call.action,
      html: call.html,
      on: [call.anchor, call.within].includes(entry)
        ? "entry"
        : [call.anchor, call.within].includes(sharedRoot)
          ? "bars"
          : call.anchor || call.within
            ? "segment"
            : "nothing",
    };
  const markdown = sharedTrack(0).children[1];
  const filesPython = sharedTrack(0).children[0];
  const ignoredPython = sharedTrack(1).children[0];
  tooltipCalls.length = 0;
  markdown.emit("mouseenter", hoverEvent);
  const fromSegment = { ...tooltipCalls[0] };
  markdown.emit("mouseleave", hoverEvent);
  // Python has a segment in both rows; pointing at one marks it alone.
  filesPython.emit("mouseenter", hoverEvent);
  const segmentMarks = sharedMarked();
  filesPython.emit("mouseleave", hoverEvent);
  tooltipCalls.length = 0;
  const pythonFromEntry = {
    population: "files",
    key: "family:python",
    anchor: entry,
    marks: "family",
  };
  shared.enter(pythonFromEntry);
  const fromOutside = { ...tooltipCalls[0], marked: sharedMarked() };
  shared.leave(pythonFromEntry);
  check(
    "a segment marks itself; a hover from outside marks its family in every row, one tooltip",
    fromSegment.action === "show" &&
      fromSegment.html ===
        '<div class="tip-name tm-tip-name"><span>Markdown</span></div><div class="tip-detail">12 files · 120 B</div>' &&
      fromSegment.anchor === markdown &&
      segmentMarks.length === 1 &&
      segmentMarks[0] === filesPython &&
      fromOutside.action === "show" &&
      fromOutside.html === "18 files · 180 B" &&
      fromOutside.anchor === entry &&
      fromOutside.marked.length === 2 &&
      fromOutside.marked[0] === filesPython &&
      fromOutside.marked[1] === ignoredPython &&
      sharedMarked().length === 0 &&
      tooltipCalls.length === 2 &&
      tooltipCalls[1].action === "hide" &&
      tooltipCalls[1].within === entry,
    JSON.stringify({
      fromSegment: named(fromSegment),
      segmentMarks: segmentMarks.length,
      fromOutside: { ...named(fromOutside), marked: fromOutside.marked.length },
      calls: tooltipCalls.map(named),
    }),
  );
  // The Ignored row has no Markdown segment: the family's Files segment is marked, and the
  // row the hover names has no segment to give a tooltip.
  tooltipCalls.length = 0;
  const ignoredMarkdown = {
    population: "ignored",
    key: "family:markdown",
    anchor: entry,
    marks: "family",
  };
  shared.enter(ignoredMarkdown);
  check(
    "a family hover whose named row has no such segment marks the rest and shows no tooltip",
    !tooltipCalls.some((call) => call.action === "show") &&
      sharedMarked().length === 1 &&
      sharedMarked()[0] === markdown,
    JSON.stringify(tooltipCalls.map(named)),
  );
  shared.leave(ignoredMarkdown);
  // A handle that marks itself and is none of these segments, as a Treemap cell would
  // be, draws nothing in the bars: no mark and no tooltip.
  tooltipCalls.length = 0;
  const elsewhere = { population: "files", key: "family:python", anchor: entry, marks: "self" };
  shared.enter(elsewhere);
  check(
    "a hover marking a handle outside the bars draws nothing in them",
    tooltipCalls.length === 0 && sharedMarked().length === 0,
    JSON.stringify(tooltipCalls.map(named)),
  );
  shared.leave(elsewhere);

  // A draw replaces every segment. One the pointer is on is replaced under it, and the
  // browser enters the new one, so the hover it held goes.
  sharedTrack(0).children[0].emit("mouseenter", hoverEvent);
  tooltipCalls.length = 0;
  sharedView.update(totals);
  check(
    "a draw puts away a hover held from a segment it replaces, with its tooltip",
    shared.current() === null &&
      sharedMarked().length === 0 &&
      tooltipCalls.some((call) => call.action === "hide") &&
      !tooltipCalls.some((call) => call.action === "show"),
    JSON.stringify(tooltipCalls.map(named)),
  );
  // An element outside the bars outlives the draw and hears nothing, so the bars draw its
  // hover again on the new segments, with the tooltip on the same element.
  shared.enter(pythonFromEntry);
  tooltipCalls.length = 0;
  sharedView.update(totals);
  const redrawnPython = [sharedTrack(0).children[0], sharedTrack(1).children[0]];
  const lastCall = tooltipCalls.at(-1);
  check(
    "a draw draws again a hover held from an element it outlives",
    shared.current()?.anchor === entry &&
      shared.current()?.key === "family:python" &&
      sharedMarked().length === 2 &&
      sharedMarked()[0] === redrawnPython[0] &&
      sharedMarked()[1] === redrawnPython[1] &&
      redrawnPython[0] !== filesPython &&
      lastCall?.action === "show" &&
      lastCall.anchor === entry &&
      lastCall.html === "18 files · 180 B",
    JSON.stringify({ current: shared.current()?.key, calls: tooltipCalls.map(named) }),
  );
  // Not once that element has left the document, which never hears the pointer leave it.
  document.body.replaceChildren(sharedContainer);
  sharedView.update(totals);
  check(
    "a draw puts away a hover held from an element that has left the document",
    shared.current() === null && sharedMarked().length === 0,
    JSON.stringify(shared.current()?.key),
  );
  sharedView.dispose();
  tooltipCalls.length = 0;
  shared.enter(pythonFromEntry);
  check(
    "disposed bars stop drawing a hover they shared",
    tooltipCalls.length === 0,
    JSON.stringify(tooltipCalls.map(named)),
  );

  if (failures.length) {
    console.error(`folder totals view FAILURES:\n- ${failures.join("\n- ")}`);
    process.exitCode = 1;
  } else {
    console.log("folder totals view OK");
  }
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});

const fs = require("node:fs");
const path = require("node:path");

const repoRoot = path.resolve(process.argv[2]);
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
}

global.document = { createElement: (tag) => new Element(tag) };

(async () => {
  const source = fs.readFileSync(
    path.join(repoRoot, "src/metabrowser/builtin_plugins/folder/folder-totals.js"),
    "utf8",
  );
  const styles = fs.readFileSync(
    path.join(repoRoot, "src/metabrowser/builtin_plugins/folder/file_type_summary.css"),
    "utf8",
  );
  const sharedStyles = fs.readFileSync(
    path.join(repoRoot, "src/metabrowser/static/styles.css"),
    "utf8",
  );
  const module = await import(
    `data:text/javascript;base64,${Buffer.from(source).toString("base64")}`
  );
  const tooltipCalls = [];
  const mb = {
    countClass: () => "",
    escapeHtml: (value) => String(value).replaceAll("&", "&amp;").replaceAll("<", "&lt;"),
    formatFileCount: (value) => `${value} files`,
    formatSize: (value) => `${value} B`,
    sizeClass: () => "",
    tooltip: {
      hide: () => tooltipCalls.push({ action: "hide" }),
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
  const view = module.mountFolderTotalsView(container, totals, mb, "size");
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
          paletteKey: "family:python",
          files: 18,
          bytes: 180,
          value: 180,
          share: 60,
        },
        {
          key: "family:markdown",
          label: "Markdown",
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
  segment.emit("mouseover", hoverEvent);
  segment.emit("mousemove", hoverEvent);
  segment.emit("mouseout", hoverEvent);
  check(
    "semantic family segments reuse the shared nav tooltip",
    tooltipCalls[0]?.action === "show" &&
      tooltipCalls[0]?.html === "<strong>Python</strong><br>18 files · 180 B" &&
      tooltipCalls[1]?.action === "hide",
    JSON.stringify(tooltipCalls.map((c) => c.action)),
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
    styles.includes(".folder-totals .file-type-summary-fill[data-segment-key]:hover") &&
      styles.includes("filter: var(--viz-data-mark-hover-filter);") &&
      darkStart > 0 &&
      sharedStyles.indexOf("--viz-data-mark-hover-filter:") < darkStart &&
      sharedStyles.lastIndexOf("--viz-data-mark-hover-filter:") > darkStart,
    styles,
  );
  // Hover is drawn on the hovered segment and nowhere else. Nothing may key off
  // the track to reach a segment's siblings, and no rule may dim one: that was
  // the old treatment, and it made pointing at one segment restyle fifty.
  // A tally track is eight pixels tall, so the lift needs the outline beside it
  // to register at all — which is why both are asserted rather than either.
  const flattened = styles.replace(/\s+/g, " ");
  check(
    "the hovered segment grows and lifts its colour, and takes no outline",
    flattened.includes(
      ".folder-totals .file-type-summary-fill[data-segment-key]:hover { " +
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
  // growing one in layout pushes the last segment past the end of the track.
  // The overshoot is the point, so assert the property rather than the spelling:
  // a cubic-bezier overshoots exactly when a control point's y exceeds 1.
  const easing = /--viz-hover-grow-ease:\s*cubic-bezier\(([^)]*)\)/.exec(sharedStyles);
  const controlYs = easing
    ? easing[1]
        .split(",")
        .map(Number)
        .filter((_, i) => i % 2 === 1)
    : [];
  check(
    "growth is a transform on a curve that overshoots",
    flattened.includes("transform var(--viz-hover-grow-duration) var(--viz-hover-grow-ease)") &&
      controlYs.length === 2 &&
      Math.max(...controlYs) > 1,
    `--viz-hover-grow-ease must overshoot; control y values were ${controlYs.join(", ")}`,
  );
  check(
    "no rule dims a segment to pick out one of its siblings",
    !styles.includes(":not(:hover)") && !sharedStyles.includes("--mb-distribution-segment-recede"),
    styles.slice(0, 200),
  );
  // An instant jump is worse than no growth.
  check(
    "reduced motion drops the growth rather than making it instant",
    flattened.includes("prefers-reduced-motion") &&
      flattened.includes(
        ".folder-totals .file-type-summary-fill[data-segment-key]:hover { transform: none; }",
      ),
    flattened.slice(flattened.indexOf("prefers-reduced-motion"), 400),
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
  view.dispose();
  check(
    "disposing Files clears the shared tooltip",
    tooltipCalls.at(-1)?.action === "hide",
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

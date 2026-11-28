const fs = require("node:fs");
const path = require("node:path");
const { pathToFileURL } = require("node:url");
const { FakeElement } = require("./pulls-test-dom.js");
const { createSdkSandbox } = require("./sdk-sandbox.js");

// The folder plugin's modules have no package.json saying they are modules, which the
// browser never asks about, and distribution-view.js imports the legend it shows, so it is
// loaded from its file. Node's warning names the process and the checkout.
const emitWarning = process.emitWarning;
process.emitWarning = (warning, ...rest) => {
  if (String(warning).includes("is not specified and it doesn't parse as CommonJS")) {
    return;
  }
  emitWarning.call(process, warning, ...rest);
};

const repoRoot = path.resolve(process.argv[2]);
const failures = [];

function check(name, condition, detail = "failed") {
  if (!condition) {
    failures.push(`${name}: ${detail}`);
  }
}

class TextNode {
  constructor(text) {
    this.textContent = text;
    this.parentNode = null;
  }

  remove() {
    this.parentNode?.removeChild(this);
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
    this.hidden = false;
    this.open = false;
    this.scope = "";
    this.textContent = "";
  }

  append(...children) {
    for (const child of children) {
      child.parentNode?.removeChild(child);
      child.parentNode = this;
      this.children.push(child);
    }
  }

  prepend(...children) {
    for (const child of [...children].reverse()) {
      child.parentNode?.removeChild(child);
      child.parentNode = this;
      this.children.unshift(child);
    }
  }

  replaceChildren(...children) {
    for (const child of this.children) {
      child.parentNode = null;
    }
    this.children = [];
    this.append(...children);
  }

  removeChild(child) {
    this.children = this.children.filter((candidate) => candidate !== child);
    child.parentNode = null;
  }

  remove() {
    this.parentNode?.removeChild(this);
  }

  setAttribute(name, value) {
    this.attributes[name] = String(value);
  }

  removeAttribute(name) {
    delete this.attributes[name];
  }

  addEventListener(type, listener) {
    this.listeners[type] = listener;
  }

  removeEventListener(type, listener) {
    if (this.listeners[type] === listener) {
      delete this.listeners[type];
    }
  }

  querySelector(selector) {
    if (!selector.startsWith(".")) {
      return null;
    }
    const className = selector.slice(1);
    for (const child of this.children) {
      if (child instanceof Element && child.className.split(/\s+/).includes(className)) {
        return child;
      }
      if (child instanceof Element) {
        const nested = child.querySelector(selector);
        if (nested) {
          return nested;
        }
      }
    }
    return null;
  }

  get ownerDocument() {
    return global.document;
  }

  get classList() {
    const element = new FakeElement("div");
    element.className = this.className;
    const { classList } = element;
    const change = (method, ...args) => {
      classList[method](...args);
      this.className = element.className;
    };
    return {
      add: (...names) => change("add", ...names),
      remove: (...names) => change("remove", ...names),
      toggle: (name, force) => change("toggle", name, force),
    };
  }
}

global.document = {
  activeElement: null,
  createElement: (tag) => new Element(tag),
  createTextNode: (text) => new TextNode(text),
};
global.window = { metabrowser: createSdkSandbox().metabrowser };

function row(key, label, category, files, bytes, filePercent, bytePercent) {
  return {
    key,
    label,
    category,
    files,
    bytes,
    filesText: `${files} files`,
    bytesText: `${bytes} B`,
    filePercent,
    bytePercent,
    fileShare: files,
    byteShare: bytes,
  };
}

function familyRow() {
  return {
    ...row("family:javascript", "JavaScript", "code", 80, 50, "80%", "50%"),
    kind: "family",
    // The family's canonical extension, which is what the model derives from
    // the registry's first extension for the family.
    iconPath: "x.js",
    paletteKey: "family:javascript",
    disclosable: true,
    children: [
      {
        ...row("family:javascript/.js", ".js", "code", 70, 40, "70%", "40%"),
        kind: "extension",
        child: true,
        extension: ".js",
        paletteKey: "family:javascript",
      },
      {
        ...row("family:javascript/.mjs", ".mjs", "code", 10, 10, "10%", "10%"),
        kind: "extension",
        child: true,
        extension: ".mjs",
        paletteKey: "family:javascript",
      },
    ],
  };
}

(async () => {
  const styles = fs.readFileSync(
    path.join(repoRoot, "src/metabrowser/builtin_plugins/folder/file_type_summary.css"),
    "utf8",
  );
  // By their file URLs, so their own imports (distribution-legend.js) resolve beside them.
  const folder = (name) =>
    pathToFileURL(path.join(repoRoot, "src/metabrowser/builtin_plugins/folder", name)).href;
  const view = await import(folder("distribution-view.js"));
  const { createDistributionHover } = await import(folder("distribution-hover.js"));
  const palette = {
    classFor: (key) => (key ? `slot-${key.slice(1)}` : "slot-other"),
    styleFor: () => "",
    paint: (element, key) => {
      element.className = `${element.className} ${key ? `slot-${key.slice(1)}` : "slot-other"}`;
    },
  };
  const metricClasses = {
    countClass: (value) => (value >= 50 ? "count-large" : ""),
    sizeClass: (value) => (value > 50 ? "size-large" : ""),
  };
  const fileTypeIcon = (name) =>
    name === "file" || name === "x.bin"
      ? { className: "", svg: '<svg data-file-icon="generic"></svg>' }
      : {
          className: name === "x.md" ? "ft-md" : "ft-code",
          svg: `<svg data-file-icon="${name}"></svg>`,
        };
  const first = {
    state: "populated",
    metric: "files",
    files: 100,
    bytes: 100,
    filesText: "100 files",
    bytesText: "100 B",
    showIgnored: true,
    ignoredFiles: 70,
    ignoredBytes: 60,
    ignoredFilesText: "70 files",
    ignoredBytesText: "60 B",
    ignoredFilePercent: "70%",
    ignoredBytePercent: "60%",
    ignoredFileShare: 70,
    ignoredByteShare: 60,
    rows: [
      row(".md", ".md", "docs", 15, 40, "15%", "40%"),
      row(".py", ".py", "code", 60, 20, "60%", "20%"),
      row(".json", ".json", "data", 20, 30, "20%", "30%"),
      row(".bin", ".bin", "other", 5, 10, "5%", "10%"),
    ],
  };
  const container = new Element("div");
  const handle = view.mountDistributionView(
    container,
    first,
    palette,
    metricClasses,
    fileTypeIcon,
    createDistributionHover(),
    (name) => `<svg data-category-icon="${name}"></svg>`,
  );
  const originalBody = handle.body;
  const originalPyRow = handle.rows.get(".py").tr;
  const originalPyMetricFill = handle.rows.get(".py").metricFill;
  check("summary uses a flat section body", handle.root.tagName === "DIV");
  check(
    "summary has no standalone metadata row",
    handle.root.children.length === 1 && handle.root.children[0] === handle.body,
  );
  const share = handle.body.children[0];
  const details = handle.body.children[1];
  check(
    "the caption precedes the legend in the compact summary",
    share.className === "file-type-summary-share" &&
      share.children[0] === handle.caption &&
      share.children[1] === handle.legendView.list &&
      handle.legendView.list.tagName === "UL",
  );
  check(
    "the caption is for screen readers only",
    handle.caption.className.split(" ").includes("sr-only"),
    handle.caption.className,
  );
  check(
    "the caption names the population for the legend and the table alike",
    handle.caption.id === "file-type-summary-1-caption" &&
      handle.legendView.list.attributes["aria-labelledby"] === handle.caption.id &&
      handle.table.attributes["aria-labelledby"] === handle.caption.id,
  );
  check(
    "the table sits in Details behind a toggle",
    details.className === "file-type-summary-details" &&
      details.children[0] === handle.detailsToggle &&
      details.children[1] === handle.table &&
      handle.body.children[2] === handle.status,
  );
  check(
    "Details is the disclosure an N more row uses, closed on mount",
    handle.detailsToggle.tagName === "BUTTON" &&
      handle.detailsToggle.type === "button" &&
      handle.detailsToggle.className.split(" ").includes("file-type-summary-disclosure") &&
      handle.detailsToggle.className.split(" ").includes("section-disclosure-trigger") &&
      handle.detailsToggle.textContent === "Details" &&
      handle.detailsToggle.attributes["aria-expanded"] === "false" &&
      handle.detailsToggle.attributes["aria-controls"] === handle.table.id &&
      handle.table.hidden === true,
  );
  check(
    "a closed Details still holds current rows, so opening it builds nothing",
    handle.rows.size === 4 && handle.groups.size === 4,
  );
  check("visual table headers are removed", handle.table.children[1].className === "sr-only");
  check("summary has one selected metric column", handle.table.children[0].children.length === 2);
  check(
    "a model without a legend leaves the list empty and hidden",
    handle.legendView.list.children.length === 0 && handle.legendView.list.hidden === true,
  );
  check(
    "a hidden legend and a closed table are not displayed",
    styles.includes(".file-type-summary-legend[hidden]") &&
      styles.includes(".file-type-summary-details > [hidden]"),
  );
  check(
    "semantic metric header follows the selected measure",
    handle.metricHeader.textContent === "Files",
  );
  check("aggregate bars removed", handle.body.querySelector(".file-type-summary-bars") === null);
  check(
    "groups have a fixed order",
    [...handle.groups.keys()].join(",") === "docs,code,data,other",
  );
  check(
    "documentation row grouped",
    handle.groups.get("docs").body.children[1].dataset.typeKey === ".md",
  );
  check(
    "group headings are semantic",
    handle.groups.get("code").body.children[0].children[0].scope === "rowgroup",
  );
  check("code row grouped", handle.groups.get("code").body.children[1] === originalPyRow);
  check("data row grouped", handle.groups.get("data").body.children[1].dataset.typeKey === ".json");
  check(
    "other row grouped",
    handle.groups.get("other").body.children[1].dataset.typeKey === ".bin",
  );
  check("color circles removed", handle.body.querySelector(".file-type-summary-mark") === null);
  check(
    "exact extension rows use the shared file identity icon",
    handle.rows.get(".md").icon.className === "file-identity-icon ft-md" &&
      handle.rows.get(".md").icon.innerHTML === '<svg data-file-icon="x.md"></svg>' &&
      handle.rows.get(".md").icon.attributes["aria-hidden"] === "true",
  );
  check(
    "unknown extensions use the shared generic file icon",
    handle.rows.get(".bin").icon.className === "file-identity-icon" &&
      handle.rows.get(".bin").icon.innerHTML === '<svg data-file-icon="generic"></svg>',
  );
  check(
    "breakdown values use the selected metric emphasis",
    handle.rows.get(".py").metricValue.className ===
      "file-type-summary-value data-num count count-large" &&
      handle.rows.get(".md").metricValue.className === "file-type-summary-value data-num count",
  );
  check(
    "Files values have no unconditional bold override",
    !styles.includes(".file-type-summary-files-row .file-type-summary-value"),
  );
  check(
    "metric value columns keep count labels clear of bars at every breakpoint",
    (styles.match(/--file-type-summary-value-width: 76px;/g) ?? []).length === 2,
  );

  const updated = {
    ...first,
    files: 120,
    bytes: 200,
    filesText: "120 files",
    bytesText: "200 B",
    rows: [
      row(".md", ".md", "docs", 25, 75, "25%", "75%"),
      row(".py", ".py", "code", 75, 25, "75%", "25%"),
    ],
  };
  view.updateDistributionView(handle, updated);
  check("body retained for live update", handle.body === originalBody);
  check("row retained by key", handle.rows.get(".py").tr === originalPyRow);
  check("row bar retained by key", handle.rows.get(".py").metricFill === originalPyMetricFill);
  check(
    "rows stay in category groups",
    handle.groups.get("code").body.children[1].dataset.typeKey === ".py" &&
      handle.groups.get("docs").body.children[1].dataset.typeKey === ".md",
  );
  check("row values patched", handle.rows.get(".py").metricValue.textContent === "75 files");
  check("row Files bar scaled", handle.rows.get(".py").metricFill.style.width === "75%");
  check(
    "live updates replace metric emphasis classes",
    handle.rows.get(".md").metricValue.className === "file-type-summary-value data-num count" &&
      handle.rows.get(".py").metricValue.className ===
        "file-type-summary-value data-num count count-large",
  );
  const filesColorClass = handle.rows.get(".py").metricFill.className;
  view.updateDistributionView(handle, {
    ...updated,
    metric: "size",
    showIgnored: false,
  });
  check(
    "metric switch reuses the cell and changes every displayed measure atomically",
    handle.rows.get(".py").metricFill === originalPyMetricFill &&
      handle.rows.get(".py").metricValue.textContent === "25 B" &&
      handle.rows.get(".py").metricFill.style.width === "25%" &&
      handle.rows.get(".py").metricValue.className === "file-type-summary-value data-num size" &&
      handle.metricHeader.textContent === "Bytes" &&
      handle.rows.get(".py").metricFill.className === filesColorClass,
  );

  const legendModel = {
    ...updated,
    legend: [
      {
        key: "family:python",
        label: "Python",
        paletteKey: "family:python",
        kind: "family",
        value: 75,
        percent: "75%",
        share: 75,
      },
      {
        key: "legend:other",
        label: '<img src=x onerror="pwned">',
        paletteKey: "",
        kind: "other",
        value: 25,
        percent: "25%",
        share: 25,
      },
    ],
  };
  view.updateDistributionView(handle, legendModel);
  const [pythonItem, otherItem] = handle.legendView.list.children;
  check(
    "each legend entry is a dot, the type, and its share",
    handle.legendView.list.hidden === false &&
      handle.legendView.list.children.length === 2 &&
      pythonItem.tagName === "LI" &&
      pythonItem.dataset.legendKey === "family:python" &&
      pythonItem.children.map((child) => child.className).join(",") ===
        "file-type-summary-legend-swatch,file-type-summary-legend-label,file-type-summary-legend-percent" &&
      pythonItem.children[0].attributes["aria-hidden"] === "true" &&
      pythonItem.children[1].textContent === "Python" &&
      pythonItem.children[2].textContent === "75%",
    pythonItem.children.map((child) => `${child.className}=${child.textContent}`).join(" | "),
  );
  check(
    "an entry carries its family's color, which its dot inherits, Other the neutral, and labels are text",
    pythonItem.className === "file-type-summary-legend-item slot-amily:python" &&
      otherItem.className === "file-type-summary-legend-item slot-other" &&
      otherItem.children[1].textContent === '<img src=x onerror="pwned">',
  );
  check(
    "legend entries wrap whole, so a dot never ends a line without its name",
    /\.file-type-summary-legend-item \{[^}]*white-space: nowrap;/.test(styles) &&
      /\.file-type-summary-legend \{[^}]*flex-wrap: wrap;/.test(styles),
  );
  check(
    "the legend uses the distribution tokens, not local colors",
    /\.file-type-summary-legend-swatch \{[^}]*background: var\(--mb-distribution-color\);/.test(
      styles,
    ) && !/#[0-9a-f]{3,8}\b|rgb\(|oklch\(/i.test(styles),
  );

  // A family's entry is a handle on its family's marks: it says where the pointer is to
  // the hover the population bars draw, naming its family and the segment in the tally
  // row the shares are of (Total while Show ignored is on, Files while it is off), and the
  // hover marks the family's own row in Details while that is open, not its extensions'.
  // The entry is marked whichever handle holds its family's hover, itself or a segment, so
  // its dot and name answer with the marks; a segment marks no Details row. Other names no
  // one segment, says nothing, and is never marked. An entry rebuilt or disposed under the
  // pointer, which never hears it leave, lets go of the hover it entered
  // (docs/design-system.md, "Aggregate Distributions").
  const legendHover = createDistributionHover();
  // The store the view is given, the real one, counting the listeners it holds: a view
  // that stops drawing is one that has stopped listening.
  let viewListeners = 0;
  const countedHover = {
    ...legendHover,
    subscribe(listener) {
      viewListeners += 1;
      const unsubscribe = legendHover.subscribe(listener);
      let subscribed = true;
      return () => {
        if (subscribed) {
          subscribed = false;
          viewListeners -= 1;
          unsubscribe();
        }
      };
    },
  };
  const hoverCalls = [];
  legendHover.subscribe((current) =>
    hoverCalls.push(current ? `${current.marks} ${current.population} ${current.key}` : "none"),
  );
  const pythonFamily = {
    ...row("family:python", "Python", "code", 75, 75, "75%", "75%"),
    kind: "family",
    paletteKey: "family:python",
    disclosable: true,
    children: [
      {
        ...row("family:python/.py", ".py", "code", 75, 75, "75%", "75%"),
        kind: "extension",
        child: true,
        extension: ".py",
        paletteKey: "family:python",
      },
    ],
  };
  const hoverModel = { ...legendModel, rows: [pythonFamily, ...legendModel.rows] };
  const hoverHandle = view.mountDistributionView(
    new Element("div"),
    hoverModel,
    palette,
    metricClasses,
    fileTypeIcon,
    countedHover,
  );
  const [hoverPython, hoverOther] = hoverHandle.legendView.list.children;
  const pythonClassBefore = hoverPython.className;
  const marked = () =>
    [
      ...hoverHandle.legendView.list.children,
      ...[...hoverHandle.rows.values()].map((r) => r.metricFill),
    ]
      .filter((element) => "hovered" in element.dataset)
      .map((element) =>
        element.dataset.legendKey !== undefined
          ? `legend ${element.dataset.legendKey}`
          : `row ${[...hoverHandle.rows].find(([, r]) => r.metricFill === element)[0]}`,
      );
  hoverPython.listeners.mouseenter();
  const entered = marked();
  hoverPython.listeners.mouseleave();
  // It hears the pointer enter and leave it, and nothing more: moving within it changes
  // nothing, and a repaint of the bars draws its hover again without it (folder-totals.js).
  check(
    "a family's entry enters and leaves its family's hover, and is marked while it holds",
    JSON.stringify(hoverCalls) === JSON.stringify(["family all family:python", "none"]) &&
      JSON.stringify(entered) === JSON.stringify(["legend family:python"]) &&
      marked().length === 0 &&
      JSON.stringify(Object.keys(hoverPython.listeners)) ===
        JSON.stringify(["mouseenter", "mouseleave"]) &&
      hoverPython.className === pythonClassBefore &&
      Object.keys(hoverPython.attributes).length === 0,
    JSON.stringify({ hoverCalls, entered }),
  );
  check(
    "Other answers no hover and no entry is a tab stop",
    Object.keys(hoverOther.listeners).length === 0 &&
      hoverHandle.legendView.list.children.every((item) => item.attributes.tabindex === undefined),
    JSON.stringify(Object.keys(hoverOther.listeners)),
  );

  // Details opened and closed under a pointer still on the entry: the family's row is
  // marked as it appears, its extension's row never, and unmarked as Details closes.
  hoverPython.listeners.mouseenter();
  hoverHandle.detailsToggle.listeners.click();
  const detailsOpened = marked();
  hoverHandle.rows.get("family:python").disclosure.listeners.click();
  const familyExpanded = marked();
  hoverHandle.detailsToggle.listeners.click();
  const detailsClosed = marked();
  hoverHandle.detailsToggle.listeners.click();
  hoverPython.listeners.mouseleave();
  check(
    "an open Details marks the family's own row for its entry, and only while open",
    JSON.stringify(detailsOpened) ===
      JSON.stringify(["legend family:python", "row family:python"]) &&
      JSON.stringify(familyExpanded) === JSON.stringify(detailsOpened) &&
      hoverHandle.rows.has("family:python/.py") &&
      JSON.stringify(detailsClosed) === JSON.stringify(["legend family:python"]) &&
      marked().length === 0,
    JSON.stringify({ detailsOpened, familyExpanded, detailsClosed }),
  );

  // A segment's hover, here entered from an element standing in for one, marks its
  // family's entry and no row, with Details open; one whose family the legend does not
  // name marks nothing.
  const segmentStandIn = new Element("span");
  const fromSegment = {
    population: "files",
    key: "family:python",
    anchor: segmentStandIn,
    marks: "self",
  };
  legendHover.enter(fromSegment);
  const segmentMarks = marked();
  legendHover.leave(fromSegment);
  const unnamed = { ...fromSegment, key: "family:css" };
  legendHover.enter(unnamed);
  const unnamedMarks = marked();
  legendHover.leave(unnamed);
  check(
    "a segment's hover marks its family's entry and no Details row",
    JSON.stringify(segmentMarks) === JSON.stringify(["legend family:python"]) &&
      unnamedMarks.length === 0,
    JSON.stringify({ segmentMarks, unnamedMarks }),
  );

  hoverCalls.length = 0;
  view.updateDistributionView(hoverHandle, { ...hoverModel, showIgnored: false });
  hoverHandle.legendView.list.children[0].listeners.mouseenter();
  view.updateDistributionView(hoverHandle, { ...hoverModel, showIgnored: false });
  check(
    "without ignored files the entry names its Files segment, and a rebuild lets go of it",
    JSON.stringify(hoverCalls) === JSON.stringify(["family files family:python", "none"]) &&
      marked().length === 0,
    JSON.stringify(hoverCalls),
  );
  // A hover held from a segment outlives the legend, so the rebuilt entry is marked.
  legendHover.enter(fromSegment);
  view.updateDistributionView(hoverHandle, { ...hoverModel, showIgnored: false });
  const rebuiltUnderSegment = marked();
  legendHover.leave(fromSegment);
  check(
    "a legend rebuilt under a segment's hover marks the family's new entry",
    JSON.stringify(rebuiltUnderSegment) === JSON.stringify(["legend family:python"]) &&
      !("hovered" in hoverHandle.legendView.list.children[0].dataset),
    JSON.stringify(rebuiltUnderSegment),
  );
  hoverCalls.length = 0;
  hoverHandle.legendView.list.children[0].listeners.mouseenter();
  const heldEntry = hoverHandle.legendView.list.children[0];
  const listeningBefore = viewListeners;
  view.disposeDistributionView(hoverHandle);
  legendHover.enter(fromSegment);
  check(
    "disposal lets go of the hover an entry under the pointer entered, and stops listening",
    JSON.stringify(hoverCalls) ===
      JSON.stringify(["family files family:python", "none", "self files family:python"]) &&
      !("hovered" in heldEntry.dataset) &&
      hoverHandle.hovered.length === 0 &&
      listeningBefore > 0 &&
      viewListeners === 0,
    JSON.stringify({ hoverCalls, listeningBefore, viewListeners }),
  );
  legendHover.leave(fromSegment);

  const pyRowBeforeDetails = handle.rows.get(".py").tr;
  handle.detailsToggle.listeners.click();
  check(
    "opening Details shows the table it controls, with the rows it already held",
    handle.detailsToggle.attributes["aria-expanded"] === "true" &&
      handle.table.hidden === false &&
      handle.rows.get(".py").tr === pyRowBeforeDetails,
  );
  view.updateDistributionView(handle, { ...legendModel, metric: "files" });
  check(
    "an open Details survives an update",
    handle.detailsToggle.attributes["aria-expanded"] === "true" && handle.table.hidden === false,
  );
  const detailsToggleBeforeRescan = handle.detailsToggle;
  view.updateDistributionView(handle, { state: "pending", rows: [] });
  check(
    "a skeleton takes the legend and Details with the rest of the body",
    handle.legendView === null && handle.detailsToggle === null && handle.table === null,
  );
  view.updateDistributionView(handle, legendModel);
  check(
    "Details reopens as it was once the rescan answers",
    handle.detailsToggle !== detailsToggleBeforeRescan &&
      handle.detailsToggle.attributes["aria-expanded"] === "true" &&
      handle.table.hidden === false &&
      handle.legendView.list.children.length === 2,
  );
  handle.detailsToggle.listeners.click();
  check(
    "closing Details hides the table and keeps the compact summary",
    handle.detailsToggle.attributes["aria-expanded"] === "false" &&
      handle.table.hidden === true &&
      handle.legendView.list.hidden === false &&
      handle.legendView.list.children.length === 2,
  );
  handle.detailsToggle.listeners.click();

  view.updateDistributionView(handle, { ...updated, rows: [familyRow()] });
  const family = handle.rows.get("family:javascript");
  check(
    "family parent starts collapsed and carries the family's icon",
    family.icon.hidden === false &&
      family.icon.innerHTML === '<svg data-file-icon="x.js"></svg>' &&
      family.disclosure.hidden === false &&
      family.disclosure.className.includes("section-disclosure-trigger") &&
      family.disclosure.attributes["aria-expanded"] === "false" &&
      !handle.rows.has("family:javascript/.js"),
  );
  check(
    "family disclosure identifies stable controlled rows",
    family.disclosure.attributes["aria-controls"] ===
      "file-type-summary-1-family_3Ajavascript_2F.js file-type-summary-1-family_3Ajavascript_2F.mjs",
  );
  check(
    "summary styles preserve hidden labels, icons, and disclosures",
    styles.includes(".file-type-summary-type-content > [hidden]") &&
      styles.includes("display: none;"),
  );
  family.disclosure.listeners.click();
  const jsChild = handle.rows.get("family:javascript/.js");
  check(
    "family disclosure reveals canonical extension rows",
    family.disclosure.attributes["aria-expanded"] === "true" &&
      family.disclosure.attributes["aria-controls"].split(" ").includes(jsChild.tr.id) &&
      jsChild.label.textContent === ".js",
  );
  // One icon for the family, on the family, in the family's colour — and none
  // on the extensions inside it. Per-extension icons resolved through the old
  // extension table, so .js and .mjs came out as two different glyphs inside
  // one family while the family row itself had none.
  check(
    "the family carries the icon and its extensions carry none",
    family.icon.hidden === false &&
      family.icon.className.includes("file-identity-icon-family") &&
      jsChild.icon.hidden === true &&
      jsChild.icon.innerHTML === "",
  );
  check(
    "family parent and child share one palette identity",
    family.metricFill.className === jsChild.metricFill.className,
  );
  handle.detailsToggle.listeners.click();
  handle.detailsToggle.listeners.click();
  check(
    "a family opened inside Details stays open across closing and reopening Details",
    handle.detailsToggle.attributes["aria-expanded"] === "true" &&
      family.disclosure.attributes["aria-expanded"] === "true" &&
      handle.rows.get("family:javascript/.js") === jsChild,
  );

  const singleton = {
    ...row("family:images", "Images", "media", 40, 80, "40%", "80%"),
    kind: "family",
    paletteKey: "family:images",
    disclosable: true,
    children: [
      {
        ...row("family:images/.png", ".png", "media", 40, 80, "40%", "80%"),
        kind: "extension",
        child: true,
        extension: ".png",
        iconPath: "x.png",
        paletteKey: "family:images",
      },
    ],
  };
  const noExtension = {
    ...row("(none)", "No extension", "other", 60, 20, "60%", "20%"),
    kind: "special",
    iconPath: null,
    paletteKey: "",
    disclosable: true,
    children: [
      {
        ...row("no-extension/README", "README", "other", 50, 15, "50%", "15%"),
        kind: "filename",
        child: true,
        iconPath: "README",
        paletteKey: "",
      },
      {
        ...row("no-extension/others", "3 more", "other", 10, 5, "10%", "5%"),
        kind: "others",
        child: true,
        iconPath: null,
        paletteKey: "",
      },
    ],
  };
  const remainingTypes = {
    ...row("", "Other types", "other", 2, 10, "2%", "10%"),
    kind: "special",
    iconPath: null,
    paletteKey: "",
    disclosable: true,
    children: [
      {
        ...row("remaining-types/.bin", ".bin", "other", 2, 10, "2%", "10%"),
        kind: "extension",
        child: true,
        extension: ".bin",
        iconPath: "x.bin",
        paletteKey: ".bin",
      },
    ],
  };
  view.updateDistributionView(handle, {
    ...updated,
    groups: [
      { id: "media", label: "Media", icon: "monitor" },
      { id: "other", label: "Other", icon: null },
    ],
    rows: [singleton, noExtension, remainingTypes],
  });
  const groupHeading = (id) => handle.groups.get(id).body.children[0].children[0];
  check(
    "registry group order and labels drive the table",
    [...handle.groups.keys()].join(",") === "media,other" &&
      groupHeading("media").children.at(-1).textContent === "Media",
  );
  // A group's heading leads with its category's icon, from the shell's registry, and a
  // group that names none draws none (docs/design-system.md, "File-Type Category Icons").
  check(
    "a group's heading leads with its category icon",
    groupHeading("media").innerHTML === '<svg data-category-icon="monitor"></svg>' &&
      groupHeading("other").innerHTML === "" &&
      groupHeading("other").children.at(-1).textContent === "Other",
    `${groupHeading("media").innerHTML} | ${groupHeading("other").innerHTML}`,
  );
  const imageFamily = handle.rows.get("family:images");
  check(
    "singleton families retain a collapsed disclosure",
    imageFamily.disclosure.hidden === false &&
      imageFamily.disclosure.attributes["aria-expanded"] === "false",
  );
  const noExtensionParent = handle.rows.get("(none)");
  check(
    "special parents share the disclosure and remain iconless",
    noExtensionParent.disclosure.hidden === false &&
      noExtensionParent.icon.hidden === true &&
      noExtensionParent.icon.innerHTML === "",
  );
  noExtensionParent.disclosure.listeners.click();
  check(
    "exact filename children use icons while aggregate Others stays iconless",
    handle.rows.get("no-extension/README").icon.innerHTML ===
      '<svg data-file-icon="README"></svg>' &&
      handle.rows.get("no-extension/others").icon.hidden === true &&
      handle.rows.get("no-extension/others").icon.innerHTML === "",
  );
  const remainingTypesParent = handle.rows.get("");
  remainingTypesParent.disclosure.listeners.click();
  check(
    "empty-string Other types key remains a valid disclosure identity",
    remainingTypesParent.disclosure.attributes["aria-expanded"] === "true" &&
      handle.rows.get("remaining-types/.bin").icon.innerHTML ===
        '<svg data-file-icon="generic"></svg>',
  );

  view.updateDistributionView(handle, {
    ...updated,
    rows: [
      row(".bad", '<img src=x onerror="pwned">', "other", 100, 100, "100%", "100%"),
      row("(none)", "No extension", "other", 0, 0, "0%", "0%"),
      row("", "Other types", "other", 0, 0, "0%", "0%"),
    ],
  });
  check(
    "labels use text content",
    handle.rows.get(".bad").label.textContent === '<img src=x onerror="pwned">',
  );
  check(
    "non-extension aggregate rows remain iconless",
    handle.rows.get("(none)").icon.hidden === true &&
      handle.rows.get("(none)").icon.innerHTML === "" &&
      handle.rows.get("").icon.hidden === true &&
      handle.rows.get("").icon.innerHTML === "",
  );
  check(
    "removed rows leave the DOM map",
    !handle.rows.has(".py") &&
      !handle.rows.has(".md") &&
      !handle.rows.has(".json") &&
      !handle.rows.has(".bin"),
  );

  view.updateDistributionView(handle, {
    ...updated,
    indexFailed: true,
    scanning: false,
  });
  check(
    "failed index has terminal status copy",
    handle.status.textContent ===
      "Could not finish scanning this folder; percentages cover the files found before it stopped.",
    handle.status.textContent,
  );

  view.updateDistributionView(handle, {
    ...updated,
    indexFailed: false,
    scanning: true,
    indexedFiles: 1234,
    indexedFilesText: "1,234",
  });
  check(
    "a running scan shows the nav panel's spinner and count, not a sentence",
    handle.status.children.length === 2 &&
      handle.status.children[0].className === "index-progress-spinner" &&
      handle.status.children[1].className === "index-progress-text" &&
      handle.status.children[1].textContent === "~1,234 files scanned",
    handle.status.children.map((child) => `${child.className}=${child.textContent}`).join(" | "),
  );

  view.updateDistributionView(handle, {
    ...updated,
    indexFailed: false,
    scanning: true,
    indexedFiles: 0,
  });
  check(
    "a scan that has counted nothing yet holds the bare label",
    handle.status.children[1]?.textContent === "Scanning…",
    handle.status.children[1]?.textContent,
  );

  view.updateDistributionView(handle, {
    ...updated,
    indexFailed: false,
    scanning: false,
  });
  check(
    "the scan row clears once the index settles",
    handle.status.hidden === true && handle.status.children.length === 0,
    `hidden=${handle.status.hidden} children=${handle.status.children.length}`,
  );

  view.updateDistributionView(handle, {
    state: "failed",
    rows: [],
  });
  check(
    "failed index without totals replaces the loading skeleton",
    handle.body.children[0].textContent ===
      "Could not scan this folder; no file summary is available.",
  );

  view.updateDistributionView(handle, {
    state: "unavailable",
    rows: [],
  });
  check(
    "completed index miss replaces the loading skeleton",
    handle.body.children[0].textContent === "This folder is not in the current file index.",
  );

  view.updateDistributionView(handle, {
    state: "empty",
    rows: [],
    filesText: "0 files",
    bytesText: "0 B",
  });
  check(
    "empty state removes distributions",
    handle.rows.size === 0 && handle.groups.size === 0 && handle.table === null,
  );
  check("empty state copy", handle.body.children[0].textContent === "No files to summarize.");

  view.updateDistributionView(handle, {
    state: "ignored-only",
    rows: [],
    allFilesText: "4 files",
  });
  check(
    "ignored-only state stays quiet beside the existing Show ignored control",
    handle.rows.size === 0 &&
      handle.groups.size === 0 &&
      handle.table === null &&
      handle.body.children.length === 0,
    `children=${handle.body.children.length}`,
  );

  // Disposal releases the markup, the rows, and both kinds of disclosure state.
  const disposable = new Element("div");
  const disposed = view.mountDistributionView(
    disposable,
    { ...first, rows: [familyRow()] },
    palette,
    metricClasses,
    fileTypeIcon,
    createDistributionHover(),
  );
  disposed.detailsToggle.listeners.click();
  disposed.rows.get("family:javascript").disclosure.listeners.click();
  check(
    "a view about to be disposed holds open disclosures",
    disposed.detailsExpanded === true && disposed.expandedFamilies.size === 1,
  );
  view.disposeDistributionView(disposed);
  check(
    "disposal removes the view and releases its rows and disclosure state",
    disposable.children.length === 0 &&
      disposed.rows.size === 0 &&
      disposed.groups.size === 0 &&
      disposed.expandedFamilies.size === 0 &&
      disposed.detailsExpanded === false &&
      disposed.table === null &&
      disposed.legendView === null &&
      disposed.detailsToggle === null &&
      disposed.lastRows.length === 0,
  );

  if (failures.length) {
    console.error(`file type summary FAILURES:\n- ${failures.join("\n- ")}`);
    process.exit(1);
  }
  console.log("file type summary OK");
})();

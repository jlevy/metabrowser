const fs = require("node:fs");
const path = require("node:path");

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
}

global.document = {
  activeElement: null,
  createElement: (tag) => new Element(tag),
  createTextNode: (text) => new TextNode(text),
};

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

(async () => {
  const source = fs.readFileSync(
    path.join(repoRoot, "src/metabrowser/builtin_plugins/folder/distribution_view.js"),
    "utf8",
  );
  const styles = fs.readFileSync(
    path.join(repoRoot, "src/metabrowser/builtin_plugins/folder/file_type_summary.css"),
    "utf8",
  );
  const view = await import(
    `data:text/javascript;base64,${Buffer.from(source).toString("base64")}`
  );
  const palette = {
    classFor: (key) => (key ? `slot-${key.slice(1)}` : "slot-other"),
  };
  const metricClasses = {
    countClass: (value) => (value >= 50 ? "count-large" : ""),
    sizeClass: (value) => (value > 50 ? "size-large" : ""),
  };
  const fileTypeIcon = (name) => ({
    className: name === "x.md" ? "ft-md" : "ft-code",
    svg: `<svg data-file-icon="${name}"></svg>`,
  });
  const first = {
    state: "populated",
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
  const handle = view.mountDistributionView(container, first, palette, metricClasses, fileTypeIcon);
  const originalBody = handle.body;
  const originalPyRow = handle.rows.get(".py").tr;
  const originalPyFileFill = handle.rows.get(".py").fileFill;
  check("summary uses a flat section body", handle.root.tagName === "DIV");
  check(
    "summary has no standalone metadata row",
    handle.root.children.length === 1 && handle.root.children[0] === handle.body,
  );
  check("visual table headers are removed", handle.table.children[1].className === "sr-only");
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
    "aggregate rows remain text-only",
    handle.totalRow.label.children.length === 0 && handle.ignoredRow.label.children.length === 0,
  );
  check("Totals group precedes the breakdown", handle.table.children[2] === handle.totalRow.body);
  check(
    "Total precedes Ignored",
    handle.totalRow.body.children[1] === handle.totalRow.tr &&
      handle.totalRow.body.children[2] === handle.ignoredRow.tr,
  );
  check(
    "Totals group has a semantic heading",
    handle.totalRow.body.children[0].children[0].textContent === "Totals" &&
      handle.totalRow.body.children[0].children[0].scope === "rowgroup",
  );
  check("ignored row names the subset", handle.ignoredRow.label.textContent === "Ignored");
  check(
    "ignored row reports exact values and shares",
    handle.ignoredRow.fileValue.textContent === "70 files" &&
      handle.ignoredRow.byteValue.textContent === "60 B" &&
      handle.ignoredRow.fileFill.style.width === "70%" &&
      handle.ignoredRow.byteFill.style.width === "60%" &&
      handle.ignoredRow.filePercent.textContent === "70%" &&
      handle.ignoredRow.bytePercent.textContent === "60%" &&
      handle.ignoredRow.fileFill.className.includes("mb-distribution-other") &&
      handle.ignoredRow.byteFill.className.includes("mb-distribution-other"),
  );
  check("total row names the population", handle.totalRow.label.textContent === "Total");
  check(
    "total row has full neutral bars",
    handle.totalRow.fileFill.style.width === "100%" &&
      handle.totalRow.byteFill.style.width === "100%" &&
      handle.totalRow.fileFill.className.includes("mb-distribution-other") &&
      handle.totalRow.byteFill.className.includes("mb-distribution-other"),
  );
  check(
    "breakdown values use shared metric emphasis",
    handle.rows.get(".py").fileValue.className === "file-type-summary-value count count-large" &&
      handle.rows.get(".py").byteValue.className === "file-type-summary-value size" &&
      handle.rows.get(".md").fileValue.className === "file-type-summary-value count" &&
      handle.rows.get(".md").byteValue.className === "file-type-summary-value size",
  );
  check(
    "Total and Ignored use the same metric emphasis",
    handle.totalRow.fileValue.className === "file-type-summary-value count count-large" &&
      handle.totalRow.byteValue.className === "file-type-summary-value size size-large" &&
      handle.ignoredRow.fileValue.className === "file-type-summary-value count count-large" &&
      handle.ignoredRow.byteValue.className === "file-type-summary-value size size-large",
  );
  check(
    "Total values have no unconditional bold override",
    !styles.includes(".file-type-summary-total-row .file-type-summary-value"),
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
  check("row bar retained by key", handle.rows.get(".py").fileFill === originalPyFileFill);
  check(
    "rows stay in category groups",
    handle.groups.get("code").body.children[1].dataset.typeKey === ".py" &&
      handle.groups.get("docs").body.children[1].dataset.typeKey === ".md",
  );
  check("row values patched", handle.rows.get(".py").fileValue.textContent === "75 files");
  check("row Files bar scaled", handle.rows.get(".py").fileFill.style.width === "75%");
  check("row Size bar scaled", handle.rows.get(".py").byteFill.style.width === "25%");
  check(
    "live updates replace metric emphasis classes",
    handle.rows.get(".md").fileValue.className === "file-type-summary-value count" &&
      handle.rows.get(".md").byteValue.className === "file-type-summary-value size size-large" &&
      handle.rows.get(".py").fileValue.className === "file-type-summary-value count count-large" &&
      handle.rows.get(".py").byteValue.className === "file-type-summary-value size",
  );
  check(
    "top totals patched",
    handle.totalRow.fileValue.textContent === "120 files" &&
      handle.totalRow.byteValue.textContent === "200 B",
  );
  check(
    "ignored row is visible when ignored files are included",
    handle.ignoredRow.tr.hidden === false,
  );

  view.updateDistributionView(handle, {
    ...updated,
    showIgnored: false,
  });
  check("ignored row hides when ignored files are excluded", handle.ignoredRow.tr.hidden === true);
  check(
    "paired row bars share a color",
    handle.rows.get(".py").fileFill.className === handle.rows.get(".py").byteFill.className,
  );

  view.updateDistributionView(handle, {
    ...updated,
    rows: [
      row(".bad", '<img src=x onerror="pwned">', "other", 100, 100, "100%", "100%"),
      row("(none)", "No extension", "other", 0, 0, "0%", "0%"),
      row("", "Remaining types", "other", 0, 0, "0%", "0%"),
    ],
  });
  check(
    "labels use text content",
    handle.rows.get(".bad").label.textContent === '<img src=x onerror="pwned">',
  );
  check(
    "non-extension breakdown rows remain text-only",
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
    state: "zero-bytes",
    bytes: 0,
    bytesText: "0 B",
    rows: [row(".py", ".py", "code", 100, 0, "100%", "0%")],
  });
  check(
    "zero-byte total remains truthful",
    handle.totalRow.fileFill.style.width === "100%" &&
      handle.totalRow.byteFill.style.width === "0%" &&
      handle.totalRow.bytePercent.textContent === "0%",
  );
  check(
    "zero-byte total stays at normal size weight",
    handle.totalRow.byteValue.className === "file-type-summary-value size",
  );

  view.updateDistributionView(handle, {
    ...updated,
    indexFailed: true,
    scanning: false,
  });
  check(
    "failed index has terminal status copy",
    handle.status.textContent ===
      "Indexing failed; percentages cover files indexed before the failure.",
    handle.status.textContent,
  );

  view.updateDistributionView(handle, {
    state: "failed",
    rows: [],
  });
  check(
    "failed index without totals replaces the loading skeleton",
    handle.body.children[0].textContent === "Indexing failed; no file summary is available.",
  );

  view.updateDistributionView(handle, {
    state: "empty",
    rows: [],
    filesText: "0 files",
    bytesText: "0 B",
  });
  check(
    "empty state removes distributions",
    handle.rows.size === 0 &&
      handle.groups.size === 0 &&
      handle.ignoredRow === null &&
      handle.totalRow === null,
  );
  check("empty state copy", handle.body.children[0].textContent === "No files to summarize.");

  if (failures.length) {
    console.error(`file type summary FAILURES:\n- ${failures.join("\n- ")}`);
    process.exit(1);
  }
  console.log("file type summary OK");
})();

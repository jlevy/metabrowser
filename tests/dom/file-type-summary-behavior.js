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
  const source = fs.readFileSync(
    path.join(repoRoot, "src/metabrowser/builtin_plugins/folder/distribution-view.js"),
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
  const handle = view.mountDistributionView(container, first, palette, metricClasses, fileTypeIcon);
  const originalBody = handle.body;
  const originalPyRow = handle.rows.get(".py").tr;
  const originalPyMetricFill = handle.rows.get(".py").metricFill;
  check("summary uses a flat section body", handle.root.tagName === "DIV");
  check(
    "summary has no standalone metadata row",
    handle.root.children.length === 1 && handle.root.children[0] === handle.body,
  );
  check("visual table headers are removed", handle.table.children[1].className === "sr-only");
  check("summary has one selected metric column", handle.table.children[0].children.length === 2);
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
    handle.rows.get(".py").metricValue.className === "file-type-summary-value count count-large" &&
      handle.rows.get(".md").metricValue.className === "file-type-summary-value count",
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
    handle.rows.get(".md").metricValue.className === "file-type-summary-value count" &&
      handle.rows.get(".py").metricValue.className === "file-type-summary-value count count-large",
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
      handle.rows.get(".py").metricValue.className === "file-type-summary-value size" &&
      handle.metricHeader.textContent === "Bytes" &&
      handle.rows.get(".py").metricFill.className === filesColorClass,
  );

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
      { id: "media", label: "Media" },
      { id: "other", label: "Other" },
    ],
    rows: [singleton, noExtension, remainingTypes],
  });
  check(
    "registry group order and labels drive the table",
    [...handle.groups.keys()].join(",") === "media,other" &&
      handle.groups.get("media").body.children[0].children[0].textContent === "Media",
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
      "Indexing failed; percentages cover files indexed before the failure.",
    handle.status.textContent,
  );

  view.updateDistributionView(handle, {
    ...updated,
    indexFailed: false,
    scanning: true,
    indexedFiles: 1234,
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
    handle.body.children[0].textContent === "Indexing failed; no file summary is available.",
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

  if (failures.length) {
    console.error(`file type summary FAILURES:\n- ${failures.join("\n- ")}`);
    process.exit(1);
  }
  console.log("file type summary OK");
})();

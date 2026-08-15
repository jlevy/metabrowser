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
    path.join(repoRoot, "src/metabrowser/builtin_plugins/folder/folder_totals.js"),
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
  const mb = {
    countClass: () => "",
    formatFileCount: (value) => `${value} files`,
    formatSize: (value) => `${value} B`,
    sizeClass: () => "",
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
        { key: "family:python", paletteKey: "family:python", value: 180, share: 60 },
        { key: "family:markdown", paletteKey: "family:markdown", value: 120, share: 40 },
      ],
    },
    ignored: {
      value: 200,
      segments: [
        { key: "family:python", paletteKey: "family:python", value: 50, share: 25 },
        { key: "family:javascript", paletteKey: "family:javascript", value: 150, share: 75 },
      ],
    },
  };
  view.updateComposition(composition, {
    classFor: (key) => `slot-${key.replace("family:", "")}`,
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

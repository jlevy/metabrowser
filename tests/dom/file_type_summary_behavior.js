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
  const view = await import(
    `data:text/javascript;base64,${Buffer.from(source).toString("base64")}`
  );
  const palette = {
    classFor: (key) => (key ? `slot-${key.slice(1)}` : "slot-other"),
  };
  const first = {
    state: "populated",
    filesText: "10 files",
    bytesText: "100 B",
    rows: [
      row(".py", ".py", "code", 70, 20, "70%", "20%"),
      row(".json", ".json", "data", 20, 30, "20%", "30%"),
      row(".md", ".md", "other", 10, 50, "10%", "50%"),
    ],
  };
  const container = new Element("div");
  const handle = view.mountDistributionView(container, first, palette);
  const originalBody = handle.body;
  const originalPyRow = handle.rows.get(".py").tr;
  const originalPyFileFill = handle.rows.get(".py").fileFill;
  check("summary uses a flat section body", handle.root.tagName === "DIV");
  check("summary has a metadata row", handle.root.children[0] === handle.meta);
  check("summary body follows metadata", handle.root.children[1] === handle.body);
  check("aggregate bars removed", handle.body.querySelector(".file-type-summary-bars") === null);
  check("groups have a fixed order", [...handle.groups.keys()].join(",") === "code,data,other");
  check(
    "group headings are semantic",
    handle.groups.get("code").body.children[0].children[0].scope === "rowgroup",
  );
  check("code row grouped", handle.groups.get("code").body.children[1] === originalPyRow);
  check("data row grouped", handle.groups.get("data").body.children[1].dataset.typeKey === ".json");
  check("other row grouped", handle.groups.get("other").body.children[1].dataset.typeKey === ".md");
  check("color circles removed", handle.body.querySelector(".file-type-summary-mark") === null);

  const updated = {
    ...first,
    filesText: "100 files",
    bytesText: "100 B",
    rows: [
      row(".md", ".md", "other", 25, 75, "25%", "75%"),
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
      handle.groups.get("other").body.children[1].dataset.typeKey === ".md",
  );
  check("row values patched", handle.rows.get(".py").fileValue.textContent === "75 files");
  check("row Files bar scaled", handle.rows.get(".py").fileFill.style.width === "75%");
  check("row Size bar scaled", handle.rows.get(".py").byteFill.style.width === "25%");
  check("total metadata patched", handle.total.textContent === "100 files · 100 B");
  check(
    "paired row bars share a color",
    handle.rows.get(".py").fileFill.className === handle.rows.get(".py").byteFill.className,
  );

  view.updateDistributionView(handle, {
    ...updated,
    rows: [row(".bad", '<img src=x onerror="pwned">', "other", 100, 100, "100%", "100%")],
  });
  check(
    "labels use text content",
    handle.rows.get(".bad").label.textContent === '<img src=x onerror="pwned">',
  );
  check("removed rows leave the DOM map", !handle.rows.has(".py") && !handle.rows.has(".md"));

  view.updateDistributionView(handle, {
    state: "empty",
    rows: [],
    filesText: "0 files",
    bytesText: "0 B",
  });
  check("empty state removes distributions", handle.rows.size === 0 && handle.groups.size === 0);
  check("empty state copy", handle.body.children[0].textContent === "No files to summarize.");

  if (failures.length) {
    console.error(`file type summary FAILURES:\n- ${failures.join("\n- ")}`);
    process.exit(1);
  }
  console.log("file type summary OK");
})();

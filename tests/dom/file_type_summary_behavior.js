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

function row(key, label, files, bytes, filePercent, bytePercent) {
  return {
    key,
    label,
    files,
    bytes,
    filesText: `${files} files`,
    bytesText: `${bytes} B`,
    filePercent,
    bytePercent,
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
    rows: [row(".py", ".py", 7, 20, "70%", "20%"), row(".md", ".md", 3, 80, "30%", "80%")],
  };
  const container = new Element("div");
  const handle = view.mountDistributionView(container, first, palette);
  const originalBody = handle.body;
  const originalPyRow = handle.rows.get(".py").tr;
  const originalPySegment = handle.bars.get("files").segments.get(".py");
  global.document.activeElement = handle.summary;

  const updated = {
    ...first,
    filesText: "12 files",
    bytesText: "120 B",
    rows: [row(".md", ".md", 4, 90, "33.3%", "75%"), row(".py", ".py", 8, 30, "66.7%", "25%")],
  };
  view.updateDistributionView(handle, updated);
  check("body retained for live update", handle.body === originalBody);
  check("row retained by key", handle.rows.get(".py").tr === originalPyRow);
  check(
    "segment retained by key",
    handle.bars.get("files").segments.get(".py") === originalPySegment,
  );
  check(
    "rows reordered without replacement",
    handle.tableBody.children.map((child) => child.dataset.typeKey).join(",") === ".md,.py",
  );
  check("row values patched", handle.rows.get(".py").fileValue.textContent === "8 files");
  check("disclosure focus preserved", global.document.activeElement === handle.summary);
  check(
    "paired bars retain the same keys",
    [...handle.bars.get("files").segments.keys()].join(",") ===
      [...handle.bars.get("bytes").segments.keys()].join(","),
  );

  view.updateDistributionView(handle, {
    ...updated,
    rows: [row(".bad", '<img src=x onerror="pwned">', 12, 120, "100%", "100%")],
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
  check("empty state removes distributions", handle.rows.size === 0 && handle.bars.size === 0);
  check("empty state copy", handle.body.children[0].textContent === "No files to summarize.");

  if (failures.length) {
    console.error(`file type summary FAILURES:\n- ${failures.join("\n- ")}`);
    process.exit(1);
  }
  console.log("file type summary OK");
})();

// Render checks for the diff view, deliberately lighter than the model
// tests: the data plane is pinned by the corpus and the CLI goldens, so
// this only asserts the projection — line rows, numbering, availability
// states, metadata-only changes, the per-file disclosure bar, and
// disposal.

const fs = require("node:fs");
const path = require("node:path");
const { pathToFileURL } = require("node:url");

const repoRoot = path.resolve(process.argv[2]);
const failures = [];

class FakeClassList {
  /** @param {FakeElement} owner */
  constructor(owner) {
    this.owner = owner;
  }

  _set() {
    return new Set(this.owner.className.split(" ").filter(Boolean));
  }

  _write(set) {
    this.owner.className = [...set].join(" ");
  }

  toggle(name, force) {
    const set = this._set();
    const want = force === undefined ? !set.has(name) : force;
    if (want) {
      set.add(name);
    } else {
      set.delete(name);
    }
    this._write(set);
    return want;
  }

  contains(name) {
    return this._set().has(name);
  }
}

class FakeElement {
  constructor(tag) {
    this.tagName = tag.toUpperCase();
    this.className = "";
    this.textContent = "";
    this.innerHTML = "";
    this.title = "";
    this.children = [];
    this.parentNode = null;
    this.attributes = new Map();
    this.listeners = new Map();
    this.classList = new FakeClassList(this);
  }

  append(...nodes) {
    for (const node of nodes) {
      node.parentNode = this;
      this.children.push(node);
    }
  }

  remove() {
    if (this.parentNode) {
      this.parentNode.children = this.parentNode.children.filter((child) => child !== this);
      this.parentNode = null;
    }
  }

  setAttribute(name, value) {
    this.attributes.set(name, String(value));
  }

  getAttribute(name) {
    return this.attributes.has(name) ? this.attributes.get(name) : null;
  }

  addEventListener(type, handler) {
    const handlers = this.listeners.get(type) ?? [];
    handlers.push(handler);
    this.listeners.set(type, handlers);
  }

  click() {
    for (const handler of this.listeners.get("click") ?? []) {
      handler({ target: this });
    }
  }

  *walk() {
    yield this;
    for (const child of this.children) {
      yield* child.walk();
    }
  }

  find(className) {
    return [...this.walk()].filter((node) => node.classList.contains(className));
  }

  text() {
    return [...this.walk()]
      .map((node) => node.textContent)
      .filter(Boolean)
      .join("\n");
  }
}

function check(label, condition, detail = "") {
  if (!condition) {
    failures.push(`${label}${detail ? `: ${detail}` : ""}`);
  }
}

async function main() {
  global.document = { createElement: (tag) => new FakeElement(tag) };
  const viewPath = path.join(repoRoot, "src/metabrowser/builtin_plugins/diff/diff_view.js");
  const { mountDiffView } = await import(pathToFileURL(viewPath).href);
  const corpus = JSON.parse(
    fs.readFileSync(
      path.join(repoRoot, "src/metabrowser/data/file-diff-format/file-diff-conformance.json"),
      "utf-8",
    ),
  );
  const byName = new Map(corpus.cases.map((entry) => [entry.name, entry.document]));

  // A modified file renders numbered rows with the right ops.
  const container = new FakeElement("div");
  const handle = mountDiffView(container, byName.get("modified-with-heading"));
  const lines = container.find("diff-line");
  check("four line rows render", lines.length === 4, String(lines.length));
  const markers = lines.map((row) => row.find("diff-line-marker")[0].textContent);
  check("ops project to markers", JSON.stringify(markers) === JSON.stringify([" ", "-", "+", " "]));
  const firstNumbers = lines[0].find("diff-line-number").map((cell) => cell.textContent);
  check("context rows carry both numbers", JSON.stringify(firstNumbers) === '["3","3"]');
  check("hunk heading renders", container.text().includes("def f():"));

  // The per-file bar: a section-disclosure trigger plus a copy control.
  const toggle = container.find("diff-file-toggle")[0];
  check(
    "bar composes the disclosure primitive",
    toggle.classList.contains("section-disclosure-trigger"),
  );
  check("sections start expanded", toggle.getAttribute("aria-expanded") === "true");
  const body = container.find("diff-file-body")[0];
  check(
    "trigger controls the body",
    toggle.getAttribute("aria-controls") === body.getAttribute("id"),
  );
  const copy = container.find("diff-file-copy")[0];
  check("copy control rides the shell delegation", Boolean(copy.getAttribute("data-copy-path")));
  check("copy control is an icon button", copy.classList.contains("icon-btn"));
  const stats = container.find("diff-file-stats")[0];
  check(
    "stat pair renders add then del",
    stats.children[0].classList.contains("diff-stat-add") &&
      stats.children[1].classList.contains("diff-stat-del"),
  );

  // Toggling collapses without disposing, and toggling back restores.
  toggle.click();
  check("collapse hides the body", body.classList.contains("diff-file-body-collapsed"));
  check("collapse flips aria-expanded", toggle.getAttribute("aria-expanded") === "false");
  check("collapse keeps rows mounted", container.find("diff-line").length === 4);
  toggle.click();
  check("expand restores the body", !body.classList.contains("diff-file-body-collapsed"));

  // Disposal removes everything the mount added.
  handle.dispose();
  check("dispose removes the root", container.children.length === 0);

  // Every availability state renders one labeled explanation, never an
  // empty section.
  const binary = new FakeElement("div");
  mountDiffView(binary, byName.get("binary-added-elided"));
  check("binary state renders its copy", binary.text().includes("Binary file; no textual diff."));
  const deferred = new FakeElement("div");
  mountDiffView(deferred, byName.get("deferred-manifest-only"));
  check("deferred state renders its copy", deferred.text().includes("not been loaded yet"));

  // A metadata-only change (chmod) says so instead of showing nothing.
  const chmod = new FakeElement("div");
  mountDiffView(chmod, byName.get("mode-change-only"));
  check("mode change renders the note", chmod.text().includes("No content changes."));
  check("mode transition is visible", chmod.text().includes("100644→100755"));

  // The no-newline marker is visible, not silently dropped.
  const noNewline = new FakeElement("div");
  mountDiffView(noNewline, byName.get("no-newline-marker"));
  check("no-newline marker renders", noNewline.find("diff-line-no-newline").length === 2);

  if (failures.length > 0) {
    for (const failure of failures) {
      console.error(failure);
    }
    process.exit(1);
  }
  console.log("diff view OK");
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});

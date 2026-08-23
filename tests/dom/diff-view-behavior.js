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
    this.dataset = {};
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
    // Bubbles like the real event: handlers up the ancestor chain all
    // see the original target, and any of them can stop it.
    let stopped = false;
    const event = {
      target: this,
      stopPropagation() {
        stopped = true;
      },
    };
    for (let node = this; node && !stopped; node = node.parentNode) {
      for (const handler of node.listeners.get("click") ?? []) {
        handler(event);
      }
    }
  }

  closest(selector) {
    for (let node = this; node; node = node.parentNode) {
      if (selector.startsWith("[") && node.attributes.has(selector.slice(1, -1))) {
        return node;
      }
      if (selector.startsWith(".") && node.classList.contains(selector.slice(1))) {
        return node;
      }
    }
    return null;
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
  const viewPath = path.join(repoRoot, "src/metabrowser/builtin_plugins/diff/diff-view.js");
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

  // The per-file bar: the nav tree's own chevron mechanism (leading
  // glyph, expanded/collapsed classes) plus a copy control, with the
  // stat pair beside the filename.
  const toggle = container.find("diff-file-toggle")[0];
  check(
    "chevron leads, from the shared registry mechanism",
    toggle.children[0].classList.contains("diff-file-chevron"),
  );
  check("trigger starts in the expanded class", toggle.classList.contains("expanded"));
  check("sections start expanded", toggle.getAttribute("aria-expanded") === "true");
  const body = container.find("diff-file-body")[0];
  check(
    "trigger controls the body",
    toggle.getAttribute("aria-controls") === body.getAttribute("id"),
  );
  const copy = container.find("diff-file-copy")[0];
  check("copy control rides the shell delegation", Boolean(copy.getAttribute("data-copy-path")));
  check("copy control is an icon button", copy.classList.contains("icon-btn"));
  check(
    "stats sit beside the filename",
    toggle.children[2].classList.contains("diff-file-path") &&
      toggle.children[3].classList.contains("diff-file-stats"),
  );
  const stats = container.find("diff-file-stats")[0];
  check(
    "stat pair renders add then del",
    stats.children[0].classList.contains("diff-stat-add") &&
      stats.children[1].classList.contains("diff-stat-del"),
  );

  // The whole bar is one activation surface: bar clicks toggle, the
  // button's own (bubbled) click toggles, the copy control does not.
  const bar = container.find("diff-file-bar")[0];
  bar.click();
  check("bar click collapses the body", body.classList.contains("diff-file-body-collapsed"));
  check("collapse flips aria-expanded", toggle.getAttribute("aria-expanded") === "false");
  check(
    "collapse flips the rotation class the tree uses",
    toggle.classList.contains("collapsed") && !toggle.classList.contains("expanded"),
  );
  check(
    "collapse marks the section, so its bar drops the doubled border",
    bar.parentNode.classList.contains("diff-file-collapsed"),
  );
  check("collapse keeps rows mounted", container.find("diff-line").length === 4);
  toggle.click();
  check("trigger click restores the body", !body.classList.contains("diff-file-body-collapsed"));
  copy.click();
  check(
    "copy click does not toggle",
    !body.classList.contains("diff-file-body-collapsed") &&
      toggle.getAttribute("aria-expanded") === "true",
  );

  // Disposal removes everything the mount added.
  handle.dispose();
  check("dispose removes the root", container.children.length === 0);

  // Every availability state renders one labeled explanation, never an
  // empty section.
  const binary = new FakeElement("div");
  mountDiffView(binary, byName.get("binary-added-elided"));
  check("binary state renders its copy", binary.text().includes("Binary file; no textual diff."));
  // Deferred is progress, not prose: with no revision to load from, the
  // section states unavailability; the progress box and its fetch are
  // covered where a revision exists (the shell's comparison path).
  const deferred = new FakeElement("div");
  mountDiffView(deferred, byName.get("deferred-manifest-only"));
  check(
    "deferred state never renders loading prose",
    !deferred.text().includes("not been loaded yet") && !deferred.text().includes("Loading"),
  );
  check("deferred without a source states unavailability", deferred.text().includes("unavailable"));

  // A metadata-only change (chmod) says so instead of showing nothing.
  const chmod = new FakeElement("div");
  mountDiffView(chmod, byName.get("mode-change-only"));
  check("mode change renders the note", chmod.text().includes("No content changes."));
  check("mode transition is visible", chmod.text().includes("100644→100755"));

  // A single-file document (a container child) skips the summary: its
  // bar already carries the name and stats.
  const single = new FakeElement("div");
  mountDiffView(single, byName.get("modified-with-heading"));
  check("one-file documents omit the summary line", single.find("diff-summary").length === 0);
  check("one-file documents still render their bar", single.find("diff-file-bar").length === 1);
  const many = new FakeElement("div");
  const manyDoc = byName.get("modified-with-heading");
  const twoFiles = {
    ...manyDoc,
    manifest: {
      ...manyDoc.manifest,
      files: [manyDoc.manifest.files[0], { ...manyDoc.manifest.files[0], id: "f2" }],
      totals: { ...manyDoc.manifest.totals, files: 2 },
    },
  };
  mountDiffView(many, twoFiles);
  check("change sets keep the summary", many.find("diff-summary").length === 1);

  // A long contiguous run folds behind an expander; ordinary runs do not.
  const longDoc = JSON.parse(JSON.stringify(byName.get("modified-with-heading")));
  const longHunk = longDoc.patches.f1.hunks[0];
  const addedLines = [];
  for (let i = 0; i < 60; i += 1) {
    addedLines.push({ op: "add", text: `line ${i}` });
  }
  longHunk.lines = [{ op: "context", text: "keep" }, ...addedLines];
  longHunk.old_count = 1;
  longHunk.new_count = 61;
  const folded = new FakeElement("div");
  mountDiffView(folded, longDoc);
  const control = folded.find("diff-fold-control")[0];
  check("a long run renders one expander", folded.find("diff-fold-control").length === 1);
  check("the expander states the hidden count", control.text().includes("40 more changed lines"));
  const group = folded.find("diff-fold-group")[0];
  check("hidden lines start collapsed", group.classList.contains("diff-fold-collapsed"));
  check("the visible head stays outside the group", folded.find("diff-line").length === 61);
  check("the group holds exactly the surplus", group.find("diff-line").length === 40);
  const sectionBody = folded.find("diff-file-body")[0];
  control.click();
  check("expanding reveals the group", !group.classList.contains("diff-fold-collapsed"));
  check(
    "expanding does not also collapse the file",
    !sectionBody.classList.contains("diff-file-body-collapsed"),
  );
  control.click();
  check("collapsing hides it again", group.classList.contains("diff-fold-collapsed"));
  check("short runs do not fold", container.find("diff-fold-control").length === 0);

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

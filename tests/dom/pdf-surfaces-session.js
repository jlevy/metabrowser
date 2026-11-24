// Browserless session: what a reader sees of a PDF on every surface Metabrowser shows one,
// from what the server serves there, through the production browser code.
//
// Every answer here is one the in-process application gave, recorded in
// tests/fixtures/pdf-surfaces-responses.json by tests/test_pdf_surfaces_session.py, which
// fails when the server answers differently: for a trusted folder, an `--untrusted` folder,
// and a pinned revision (every GitHub repository and pull request is one), the trust block
// and the content policy of the shell at /view/, the kind and views /api/file answers for
// each PDF, and the answer at /raw for the address the view links to; and for the pin, the
// comparison its commit's diff draws.
//
// The PDF view runs as the shell runs it (tests/dom/pdf-view-harness.js): the production
// SDK and compositor, with the view's script loaded with its kind's assets, on the globals
// the recorded shell wrote, in a browser and in the macOS app, whose host descriptor is the
// only difference. builtin_plugins/diff/diff-view.js mounts the recorded comparison on a
// small element tree, as a pull request's Changes and a commit's diff mount it.
//
// For each surface and host it prints what each PDF shows: the browser's viewer inline
// (`viewer`) or the note (`note`), whether the page's policy admits the viewer the view
// drew, and each action with its address and what the server answered there. For each
// change of the comparison it prints the change, the server's word on its diff, and what
// the file's body says. The browser's painting of a PDF is Chrome's
// (tests/test_pdf_preview_chrome.py).

const fs = require("node:fs");
const path = require("node:path");
const { pathToFileURL } = require("node:url");
const { APP_HOST, createPage, describe, preparePdfView } = require("./pdf-view-harness.js");

const repoRoot = path.resolve(__dirname, "../..");
const recorded = JSON.parse(
  fs.readFileSync(path.join(repoRoot, "tests/fixtures/pdf-surfaces-responses.json"), "utf8"),
);

function assert(condition, message) {
  if (!condition) {
    throw new Error(message);
  }
}

/**
 * Whether a page served with *policy* may embed a same-origin address: its `object-src`,
 * or `default-src` when it names none, as a browser reads them. No policy admits anything.
 */
function admitsSameOriginObject(policy) {
  if (!policy) {
    return true;
  }
  const directives = new Map(
    policy
      .split(";")
      .map((part) => part.trim().split(/\s+/))
      .filter((words) => words[0])
      .map(([name, ...sources]) => [name.toLowerCase(), sources]),
  );
  const sources = directives.get("object-src") ?? directives.get("default-src");
  if (sources === undefined) {
    return true;
  }
  return sources.some((source) => source === "'self'" || source === "*");
}

/** The pieces of a recorded `/raw` answer a reader's browser acts on. */
function answerFor(files, href) {
  const raw = Object.values(files)
    .map((file) => file.raw)
    .find((answer) => answer.href === href);
  if (raw === undefined) {
    return null;
  }
  return { status: raw.status, type: raw["content-type"], head: raw.head };
}

async function fileViews() {
  const page = createPage();
  const view = await preparePdfView(page);
  assert(view.prepared.status === "ready", "the PDF view did not compose");
  const surfaces = [];
  for (const surface of ["folder", "folderUntrusted", "pin"]) {
    const served = recorded[surface];
    for (const [hostName, host] of [
      ["browser", null],
      ["app", APP_HOST],
    ]) {
      page.serve({
        capabilities: served.shell.capabilities,
        sourceKind: served.shell.source_kind,
        host,
      });
      const policy = served.shell["content-security-policy"];
      const files = {};
      for (const [name, file] of Object.entries(served.files)) {
        const answer = file.file;
        const chosen = answer.views.find((candidate) => candidate.default) ?? answer.views[0];
        if (answer.kind !== "pdf" || chosen?.id !== "preview") {
          files[name] = { kind: answer.kind, view: chosen?.id ?? null, shows: "another view" };
          continue;
        }
        const { container, status } = await view.mount(answer.path);
        assert(status === "mounted", `${surface}: the view did not mount ${name}`);
        const [bar, body] = container.children;
        const shows = body.tagName === "EMBED" ? "viewer" : "note";
        files[name] = {
          kind: answer.kind,
          view: chosen.id,
          shows,
          ...(shows === "viewer"
            ? { policyAdmitsViewer: admitsSameOriginObject(policy) }
            : { note: body.textContent }),
          actions: bar.children.map((link) => {
            const seen = describe(link).attributes;
            return {
              label: link.textContent,
              href: seen.href,
              ...(seen.target ? { target: seen.target } : {}),
              ...(seen.download ? { download: seen.download } : {}),
              ...(seen["data-metabrowser-open-file"]
                ? { opensInApp: seen["data-metabrowser-open-file"] }
                : {}),
              answer: answerFor(served.files, seen.href),
            };
          }),
        };
      }
      surfaces.push({
        surface,
        host: hostName,
        served: {
          sourceKind: served.shell.source_kind,
          activeContent: served.shell.capabilities?.active_content ?? null,
          objectPolicy: admitsSameOriginObject(policy) ? "admits /raw" : "blocks embedding",
        },
        files,
      });
    }
  }
  view.lifecycle.disposeActive();
  assert(page.innerHtmlWrites() === 0, "the PDF view built markup with innerHTML");
  return surfaces;
}

// ── The comparison, as the diff view draws it ─────────────────────────────────────────

class ClassList {
  constructor(owner) {
    this.owner = owner;
  }

  _set() {
    return new Set(this.owner.className.split(" ").filter(Boolean));
  }

  _write(set) {
    this.owner.className = [...set].join(" ");
  }

  add(...names) {
    const set = this._set();
    for (const name of names) {
      set.add(name);
    }
    this._write(set);
  }

  remove(...names) {
    const set = this._set();
    for (const name of names) {
      set.delete(name);
    }
    this._write(set);
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

class DiffElement {
  constructor(tag) {
    this.tagName = tag.toUpperCase();
    this.className = "";
    this.textContent = "";
    this.innerHTML = "";
    this.title = "";
    this.hidden = false;
    this.dataset = {};
    this.style = {
      setProperty(name, value) {
        this[name] = value;
      },
      removeProperty(name) {
        delete this[name];
      },
    };
    this.children = [];
    this.parentNode = null;
    this.attributes = new Map();
    this.listeners = new Map();
    this.classList = new ClassList(this);
  }

  append(...nodes) {
    for (const given of nodes) {
      let node = given;
      if (typeof given === "string") {
        node = new DiffElement("#text");
        node.textContent = given;
      }
      node.parentNode = this;
      this.children.push(node);
    }
  }

  prepend(...nodes) {
    const before = this.children;
    this.children = [];
    this.append(...nodes);
    this.children.push(...before);
  }

  replaceChildren(...nodes) {
    for (const child of this.children) {
      child.parentNode = null;
    }
    this.children = [];
    this.textContent = "";
    this.append(...nodes);
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

  hasAttribute(name) {
    return this.attributes.has(name);
  }

  removeAttribute(name) {
    this.attributes.delete(name);
  }

  addEventListener(type, handler) {
    const handlers = this.listeners.get(type) ?? [];
    handlers.push(handler);
    this.listeners.set(type, handlers);
  }

  removeEventListener(type, handler) {
    this.listeners.set(
      type,
      (this.listeners.get(type) ?? []).filter((candidate) => candidate !== handler),
    );
  }

  contains(candidate) {
    for (let node = candidate; node; node = node.parentNode) {
      if (node === this) {
        return true;
      }
    }
    return false;
  }

  closest(selector) {
    for (let node = this; node; node = node.parentNode) {
      if (selector.startsWith(".") && node.classList?.contains(selector.slice(1))) {
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
    return [...this.walk()].filter((node) => node.classList?.contains(className));
  }

  querySelector(selector) {
    return this.find(selector.slice(1)).find((node) => node !== this) ?? null;
  }

  querySelectorAll(selector) {
    return this.find(selector.slice(1)).filter((node) => node !== this);
  }

  getBoundingClientRect() {
    return { top: 0, bottom: 0, left: 0, right: 0, width: 0, height: 0 };
  }

  /** The element's text as a reader reads it: its leaves' text, in order, joined. */
  reads() {
    return this.children.length === 0
      ? this.textContent
      : this.children.map((child) => child.reads()).join("");
  }
}

async function comparison() {
  globalThis.document = {
    createElement: (tag) => new DiffElement(tag),
    addEventListener() {},
    removeEventListener() {},
  };
  globalThis.window = {
    requestAnimationFrame: () => 1,
    cancelAnimationFrame() {},
    addEventListener() {},
    removeEventListener() {},
  };
  globalThis.Element = DiffElement;
  globalThis.getComputedStyle = () => ({ getPropertyValue: () => "24px", fontSize: "14px" });
  globalThis.IntersectionObserver = class {
    observe() {}
    unobserve() {}
    disconnect() {}
  };
  const diffView = await import(
    pathToFileURL(path.join(repoRoot, "src/metabrowser/builtin_plugins/diff/diff-view.js")).href
  );
  const document_ = recorded.pinComparison;
  const host = new DiffElement("div");
  const handle = diffView.mountDiffView(
    host,
    document_,
    {
      formatInteger: (count) => count.toLocaleString("en-US"),
      // Syntax colouring decides nothing here: a text diff draws plain.
      highlightSyntax: async () => null,
      isLargeTextPreview: () => true,
      langForPath: () => "",
      ...require("./changed-files-tree-fixture.js").shellPainters(),
    },
    {},
  );
  const changes = [];
  for (const change of document_.manifest.files) {
    const filePath = (change.new ?? change.old).path;
    const section = host
      .find("diff-file")
      .find((candidate) => candidate.find("diff-file-path")[0]?.reads().endsWith(filePath));
    assert(section !== undefined, `the diff drew no section for ${filePath}`);
    const notice = section.find("diff-availability")[0];
    changes.push({
      path: filePath,
      change: change.kind,
      binary: change.binary,
      availability: change.availability,
      // A binary change carries no line counts, as the server says with null.
      lines: change.additions === null ? null : `+${change.additions} −${change.deletions}`,
      body: notice ? notice.reads() : "text diff",
    });
  }
  handle.dispose();
  return changes;
}

(async () => {
  const surfaces = await fileViews();
  const pinComparison = await comparison();
  // One line for each file on each surface, for a reader of the transcript: what it shows,
  // and what the server answers at each action's address.
  const seen = surfaces.flatMap((surface) =>
    Object.entries(surface.files).map(([name, file]) => {
      const actions = (file.actions ?? [])
        .map((action) => `${action.label} → ${action.answer?.status} ${action.answer?.type}`)
        .join("; ");
      return `${surface.surface} · ${surface.host} · ${name}: ${file.shows}. ${actions}`;
    }),
  );
  const changed = pinComparison.map(
    (change) => `diff · ${change.change} ${change.path}: ${change.body}`,
  );
  console.log(JSON.stringify({ seen: [...seen, ...changed], surfaces, pinComparison }, null, 2));
})().catch((error) => {
  console.error(error);
  process.exit(1);
});

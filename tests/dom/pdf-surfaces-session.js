// Browserless session: what a reader sees of a PDF on every surface Metabrowser shows one,
// from what the server serves there, through the production browser code.
//
// Every answer here is one the in-process application gave, recorded in
// tests/fixtures/pdf-surfaces-responses.json by tests/test_pdf_surfaces_session.py, which
// fails when the server answers differently: for a trusted folder, an `--untrusted` folder,
// and a pinned revision (every GitHub repository and pull request is one), the trust block
// and the content policy of the shell at /view/, the kind and views /api/file answers for
// each PDF, the answer at /raw for the address the view links to, and the PDF plugin's
// preview of the file; and for the pin, the comparison its commit's diff draws and the
// preview each of its PDF cards asks for, as on a platform without a sandbox and with one.
//
// The PDF view runs as the shell runs it (tests/dom/pdf-view-harness.js): the production
// SDK and compositor, with the view's script loaded with its kind's assets, on the globals
// the recorded shell wrote, in a browser and in the macOS app, whose host descriptor is the
// only difference. builtin_plugins/diff/diff-view.js mounts the recorded comparison on a
// small element tree, as a pull request's Changes and a commit's diff mount it.
//
// For each surface and host it prints what each PDF shows: the browser's viewer inline
// (`viewer`) or the note (`note`), whether the page's policy admits the viewer the view
// drew, the first page behind it or why there is none, and each action with its address
// and what the server answered there. For each change of the comparison it prints the
// change, the server's word on its diff, what the file's body says, and the PDF card a
// binary PDF's body holds, which is an image and never a viewer. The browser's painting of a PDF is Chrome's
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

// The origin the recorder's in-process client is served at (tests/test_pdf_surfaces_session.py).
const PAGE_ORIGIN = "http://testserver";

/**
 * The source list a page served with *policy* applies to a load: its first directive in
 * *chain* the policy names, as a browser falls back (`frame-src`, then `child-src`, then
 * `default-src`). Null when it names none, which admits anything.
 */
function sourcesFor(policy, chain) {
  const directives = new Map(
    policy
      .split(";")
      .map((part) => part.trim().split(/\s+/))
      .filter((words) => words[0])
      .map(([name, ...sources]) => [name.toLowerCase(), sources]),
  );
  for (const name of chain) {
    if (directives.has(name)) {
      return directives.get(name);
    }
  }
  return null;
}

/**
 * Whether *sources* admit *href*, a same-origin address: `'self'` and `*` do, and a
 * source with a path does when the path is the address's, exactly, or a prefix of it for
 * a path ending in `/` (CSP's path matching, which ignores the query).
 */
function sourcesAdmit(sources, href) {
  if (sources === null) {
    return true;
  }
  const target = new URL(href, PAGE_ORIGIN);
  return sources.some((source) => {
    if (source === "'self'" || source === "*") {
      return true;
    }
    if (!/^https?:\/\//.test(source)) {
      return false;
    }
    const allowed = new URL(source);
    if (allowed.origin !== target.origin) {
      return false;
    }
    return allowed.pathname.endsWith("/")
      ? target.pathname.startsWith(allowed.pathname)
      : target.pathname === allowed.pathname;
  });
}

/**
 * Whether a page served with *policy* lets an `<embed>` of *href* show the browser's PDF
 * viewer: the object itself under `object-src`, and, as Chrome draws the PDF in a frame
 * of that address, the frame under `frame-src` too. No policy admits anything.
 */
function admitsViewerAt(policy, href) {
  if (!policy) {
    return true;
  }
  return (
    sourcesAdmit(sourcesFor(policy, ["object-src", "default-src"]), href) &&
    sourcesAdmit(sourcesFor(policy, ["frame-src", "child-src", "default-src"]), href)
  );
}

/** Let every answer the page was given settle, and what it drew follow. */
function settled() {
  return new Promise((resolve) => setImmediate(resolve));
}

/** The preview route's recorded answers, by the address the file page asks. */
function previewAnswers(files) {
  return Object.fromEntries(
    Object.values(files).map((file) => [
      `/api/plugin/pdf/preview?path=${encodeURIComponent(file.file.path)}`,
      file.preview,
    ]),
  );
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
      page.servePreviews(previewAnswers(served.files));
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
        await settled();
        const [bar, body, backdrop] = container.children;
        const shows = body.tagName === "EMBED" ? "viewer" : "note";
        const preview = served.files[name].preview;
        files[name] = {
          kind: answer.kind,
          view: chosen.id,
          shows,
          ...(shows === "viewer"
            ? { policyAdmitsViewer: admitsViewerAt(policy, body.getAttribute("src")) }
            : { note: body.textContent }),
          firstPage: backdrop
            ? { behindViewer: describe(backdrop).attributes }
            : { none: preview.reason ?? preview.status },
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
          embedPolicy: admitsViewerAt(policy, "/raw?path=any.pdf")
            ? admitsViewerAt(policy, "/api/file?path=any.pdf")
              ? "admits this origin"
              : "admits /raw only"
            : "blocks embedding",
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
    // The document the element belongs to, as a plugin's code finds it (the PDF card).
    this.ownerDocument = globalThis.document;
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

/** A PDF card the diff drew, as a reader sees it: its state, its image, and its caption. */
function describeCard(slot) {
  const [card] = slot.children;
  if (card === undefined) {
    return null;
  }
  const [page, caption] = card.children;
  const attributes = Object.fromEntries(card.attributes);
  return {
    state: attributes["data-pdf-preview"],
    ...(attributes["data-pdf-preview-reason"]
      ? { reason: attributes["data-pdf-preview-reason"] }
      : {}),
    image: page.children[0] ? Object.fromEntries(page.children[0].attributes) : null,
    caption: caption.children.map((part) => part.reads()),
    controls: describeControls(card),
  };
}

/** The View file controls under *node*, as the bar and the card draw them. */
function describeControls(node) {
  return node.find("diff-file-view").map((control) => {
    const attributes = Object.fromEntries(control.attributes);
    return {
      tag: control.tagName.toLowerCase(),
      label: control.reads(),
      tip: attributes["data-tip-text"],
      ...(attributes.href ? { href: attributes.href } : {}),
    };
  });
}

// The page a pull request's Changes is: the server serves another commit than the pull
// request's head, which is the comparison's right side, and the head has a branch. So
// each changed file's control is View on branch, a switch, on its bar and on its card.
const PULL_REQUEST_PAGE = {
  kind: "pin",
  pin: "0".repeat(40),
  branch: "feature",
  href: (address) => `/view/${typeof address === "string" ? address : "bytes"}`,
  pinSwitch: { onReleased: () => () => {}, switchTo: async () => ({ kind: "busy" }) },
  navigate() {},
  onPinChanged: () => () => {},
};

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
    // What the View file controls' tooltips name a commit with: the shell's own.
    metabrowser: {
      shortCommit: require("./changed-files-tree-fixture.js").shellFormatters().shortCommit,
    },
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
  const viewFileModule = await import(
    pathToFileURL(path.join(repoRoot, "src/metabrowser/builtin_plugins/diff/diff-view-file.js"))
      .href
  );
  const document_ = recorded.pinComparison;
  // The PDF plugin's module, in the page the PDF view runs in, on the pin's globals: what
  // `mb.plugins.load("pdf")` returns the diff.
  const pdfPage = createPage();
  pdfPage.serve({
    capabilities: recorded.pin.shell.capabilities,
    sourceKind: recorded.pin.shell.source_kind,
  });
  const pdf = await pdfPage.importProduction("src/metabrowser/builtin_plugins/pdf/index.js");
  const loads = [];
  /** Mount the comparison with the preview route answering *answers*. */
  async function mount(answers) {
    const requests = pdfPage.servePreviews(answers);
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
        plugins: {
          load: async (name) => {
            loads.push(name);
            assert(name === "pdf", `the diff loaded a plugin it does not require: ${name}`);
            return pdf;
          },
        },
        ...require("./changed-files-tree-fixture.js").shellPainters(),
      },
      {
        viewFile: (callbacks) => viewFileModule.createViewFileOpener(PULL_REQUEST_PAGE, callbacks),
      },
    );
    await settled();
    return { host, handle, requests };
  }
  const cards = {};
  for (const [label, answers] of Object.entries(recorded.pinComparisonPreviews)) {
    const drawn = await mount(answers);
    const slots = drawn.host.find("diff-pdf-card");
    cards[label] = {
      requests: drawn.requests,
      cards: slots.map((slot) => describeCard(slot)),
    };
    drawn.handle.dispose();
    // Disposing the diff removes every card it drew.
    assert(
      slots.every((slot) => slot.parentNode === null && slot.children.length === 0),
      `${label}: a card outlived its diff`,
    );
  }
  const { host, handle } = await mount(recorded.pinComparisonPreviews.noSandbox);
  const changes = [];
  for (const change of document_.manifest.files) {
    const filePath = (change.new ?? change.old).path;
    const section = host
      .find("diff-file")
      .find((candidate) => candidate.find("diff-file-path")[0]?.reads().endsWith(filePath));
    assert(section !== undefined, `the diff drew no section for ${filePath}`);
    // The file's own line, not the empty notice a View file control says a refusal in.
    const notice = section
      .find("diff-availability")
      .find((node) => !node.className.split(" ").includes("diff-file-notice"));
    const slot = section.find("diff-pdf-card")[0];
    const bar = section.find("diff-file-bar")[0];
    changes.push({
      path: filePath,
      change: change.kind,
      binary: change.binary,
      availability: change.availability,
      // Its lines as its bar draws them, a total of zero left out (mb-ox6a); a binary change
      // carries no line counts, as the server says with null, and its bar draws none.
      lines: section.find("diff-file-stats")[0]?.reads() ?? null,
      body: notice ? notice.reads() : "text diff",
      card: slot ? describeCard(slot) : null,
      barControls: bar ? describeControls(bar) : [],
    });
    // The card's way to the PDF's page is its bar's: the same control, a press nearer.
    const card = changes.at(-1).card;
    if (card !== null) {
      assert(
        card.controls.length > 0 &&
          JSON.stringify(card.controls) === JSON.stringify(changes.at(-1).barControls),
        `${filePath}: the card's controls are not its bar's`,
      );
    }
  }
  // A heavy diff must not grow a PDF viewer per changed PDF: no element the diff drew,
  // and no markup it wrote, is an embed, object, or iframe.
  const viewers = [...host.walk()].filter(
    (node) =>
      ["EMBED", "OBJECT", "IFRAME"].includes(node.tagName) ||
      /<(embed|object|iframe)\b/i.test(node.innerHTML),
  );
  assert(viewers.length === 0, `the diff drew a viewer: ${viewers.map((node) => node.tagName)}`);
  handle.dispose();
  return { changes, cards, loads: [...new Set(loads)] };
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
      const after = file.actions ? `. ${actions}` : ` (${file.kind}, the ${file.view} view)`;
      const first = !file.firstPage
        ? ""
        : file.firstPage.behindViewer
          ? "; first page behind it"
          : `; no first page (${file.firstPage.none})`;
      return `${surface.surface} · ${surface.host} · ${name}: ${file.shows}${first}${after}`;
    }),
  );
  const changed = pinComparison.changes.map(
    (change) =>
      `diff · ${change.change} ${change.path}: ${change.body}` +
      (change.card
        ? ` Card: ${change.card.state}${change.card.reason ? ` (${change.card.reason})` : ""}` +
          `, with ${change.card.controls
            .map((control) => `${control.label} (${control.tag}: ${control.tip})`)
            .join(", ")}, as its bar has.`
        : ""),
  );
  const carded = Object.entries(pinComparison.cards).map(
    ([label, { cards }]) =>
      `diff, ${label === "sandbox" ? "with a sandbox" : "without a sandbox"} · ` +
      cards
        .map((card) => `${card.caption.join(" · ")} (${card.image ? "image" : "no image"})`)
        .join("; "),
  );
  const noViewer = "diff · draws no embed, object, or iframe";
  console.log(
    JSON.stringify(
      { seen: [...seen, ...changed, ...carded, noViewer], surfaces, pinComparison },
      null,
      2,
    ),
  );
})().catch((error) => {
  console.error(error);
  process.exit(1);
});

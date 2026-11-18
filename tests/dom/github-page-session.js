// Browserless session: the view header's GitHub toggle (static/github-page.js) on the
// repository contexts the server derives (tests/fixtures/github-page-shell.json, recorded
// by tests/test_github_page_session.py).
//
// The production module loads whole into a page of fakes: a main pane, and in it the view
// header app.js commits, naming its item in `data-path` and ending its heading row in
// `.view-header-end`. For each context, as the SDK normalizes it, and each item of a
// folder's or a pin's paths, the session records whether the toggle is drawn and, when it
// is, its two states: the Metabrowser mark, the view the page opens in and is shown in,
// and the GitHub mark, a link to the item's page on github.com; then it commits the next
// page's header and records that the toggle is drawn again, for the new item, and still
// shows the Metabrowser view.
//
// Prints the transcript; exits 1 on any failure.

const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const repoRoot = path.resolve(__dirname, "../..");
const staticDir = path.join(repoRoot, "src/metabrowser/static");
const recorded = JSON.parse(
  fs.readFileSync(path.join(repoRoot, "tests/fixtures/github-page-shell.json"), "utf8"),
);

// The items a page can be on: the served root, a folder, a file, and names that need
// escaping, as each subject's routes name them. A folder spells a literal percent `%25`
// and a byte that is not UTF-8 `%XX`; a pin spells each segment as a `g1-` atom.
const wire = (text) =>
  text
    .split("/")
    .map((segment) => `g1-${Buffer.from(segment, "utf8").toString("base64url")}`)
    .join("/");
const ITEMS = {
  filesystem: [
    { path: "", folder: true },
    { path: "docs", folder: true },
    { path: "docs/guide.md", folder: false },
    { path: "docs/a b/雪 (1).md", folder: false },
    { path: "50%25-off.md", folder: false },
    { path: "raw/%FF.bin", folder: false },
  ],
  git_revision: [
    { path: "", folder: true },
    { path: wire("docs"), folder: true },
    { path: wire("docs/guide.md"), folder: false },
    { path: wire("docs/a b/雪 (1).md"), folder: false },
  ],
};

class HTMLElement {
  constructor(tag) {
    this.tagName = tag.toUpperCase();
    this.className = "";
    this.attributes = new Map();
    this.dataset = {};
    this.children = [];
    this.parentElement = null;
    this.id = "";
  }
  get classList() {
    const classes = () => this.className.split(/\s+/).filter(Boolean);
    return { contains: (name) => classes().includes(name) };
  }
  setAttribute(name, value) {
    this.attributes.set(name, String(value));
  }
  getAttribute(name) {
    return this.attributes.has(name) ? this.attributes.get(name) : null;
  }
  append(...nodes) {
    for (const node of nodes) {
      node.parentElement = this;
      this.children.push(node);
    }
  }
  matches(selector) {
    if (selector.startsWith("#")) {
      return this.id === selector.slice(1);
    }
    return this.classList.contains(selector.slice(1));
  }
  /** The two shapes the module asks for: `.class` anywhere below, and `#id > .class`. */
  querySelector(selector) {
    const child = /^#([\w-]+) > \.([\w-]+)$/.exec(selector);
    for (const node of this.walk()) {
      if (child) {
        if (node.matches(`.${child[2]}`) && node.parentElement?.matches(`#${child[1]}`)) {
          return node;
        }
      } else if (node.matches(selector)) {
        return node;
      }
    }
    return null;
  }
  *walk() {
    for (const node of this.children) {
      yield node;
      yield* node.walk();
    }
  }
}

function element(tag, className = "") {
  const node = new HTMLElement(tag);
  node.className = className;
  return node;
}

/** A page: the main pane, the SDK's repository and source kind, and the module loaded. */
function page(context, sourceKind) {
  const pane = element("main", "preview-pane");
  pane.id = "preview-pane";
  const body = element("body");
  body.append(pane);
  const observers = [];
  const sandbox = {
    console,
    TextEncoder,
    atob,
    HTMLElement,
    MutationObserver: class {
      constructor(callback) {
        this.callback = callback;
        observers.push(this);
      }
      observe() {}
    },
    document: {
      readyState: "complete",
      getElementById: (id) => (id === "preview-pane" ? pane : null),
      querySelector: (selector) => body.querySelector(selector),
      createElement: (tag) => element(tag),
      addEventListener: () => {},
    },
  };
  sandbox.window = sandbox;
  vm.createContext(sandbox);
  // The SDK's normalized context, as plugin-sdk.js's normalizeRepositoryContext gives it.
  // The context as the server wrote it, and the SDK's copy of it, as plugin-sdk.js's
  // normalizeRepositoryContext keeps it: null for any host but github.com.
  sandbox.METABROWSER_REPOSITORY_CONTEXT = context;
  sandbox.metabrowser = {
    repository: context && context.host === "github.com" ? Object.freeze({ ...context }) : null,
    sourceKind: () => sourceKind,
  };
  const module = path.join(staticDir, "github-page.js");
  vm.runInContext(fs.readFileSync(module, "utf8"), sandbox, { filename: module });
  /** Commit a view header for *item*, as app.js does, and let the observer run. */
  const commit = (item) => {
    pane.children = [];
    const header = element("div", `file-header view-header${item.folder ? " folder-header" : ""}`);
    header.dataset.path = item.path;
    const end = element("span", "view-header-end");
    header.append(element("div", "view-header-heading"));
    header.children[0].append(end);
    pane.append(header);
    for (const observer of observers) {
      observer.callback([]);
    }
    return end.querySelector(".view-header-toggle");
  };
  return { sandbox, commit };
}

/** The toggle as a reader meets it: its two marks, in order. */
function describe(toggle) {
  if (toggle === null) {
    return null;
  }
  return {
    label: toggle.getAttribute("aria-label"),
    role: toggle.getAttribute("role"),
    options: toggle.children.map((option) => ({
      element: option.tagName.toLowerCase(),
      class: option.className,
      current: option.getAttribute("aria-current"),
      label: option.getAttribute("aria-label"),
      tip: option.dataset.tipText,
      ...(option.tagName === "A"
        ? { href: option.href, target: option.target, rel: option.rel }
        : {}),
    })),
  };
}

const failures = [];
const check = (name, ok) => {
  if (!ok) {
    failures.push(name);
  }
};

const transcript = [];
for (const [name, context] of Object.entries(recorded)) {
  const sourceKind = name.startsWith("mirror-") ? "git_revision" : "filesystem";
  const { commit } = page(context, sourceKind);
  const items = ITEMS[sourceKind];
  const pages = items.map((item) => {
    const toggle = commit(item);
    return { path: item.path, folder: item.folder, toggle: describe(toggle) };
  });
  const shown = pages.filter((each) => each.toggle !== null);
  check(
    `${name}: drawn on every page or on none`,
    shown.length === 0 || shown.length === pages.length,
  );
  for (const each of shown) {
    const [here, there] = each.toggle.options;
    check(`${name} ${each.path}: opens in the Metabrowser view`, here.current === "page");
    check(
      `${name} ${each.path}: GitHub is a link`,
      there.element === "a" && there.current === null,
    );
  }
  transcript.push({
    context: name,
    toggle: shown.length ? shown[0].toggle : null,
    // Each page committed after the first draws the toggle again, in the Metabrowser view.
    pagesShowingMetabrowser: shown.filter((each) => each.toggle.options[0].current === "page")
      .length,
    pages: pages.length,
    urls: Object.fromEntries(
      pages.map((each) => [each.path || "(root)", each.toggle?.options[1].href ?? null]),
    ),
  });
}

// The links, as written: at the branch origin has, or at the commit where origin has no
// branch of the page's, which the tooltip says.
const linkOf = (name, item) => transcript.find((entry) => entry.context === name).urls[item];
const tipOf = (name) => transcript.find((entry) => entry.context === name).toggle.options[1].tip;
check(
  "a pushed branch links at the branch",
  linkOf("github-https", "(root)") === "https://github.com/octo/demo/tree/main" &&
    linkOf("github-https", "docs/guide.md") ===
      "https://github.com/octo/demo/blob/main/docs/guide.md",
);
check(
  "a pushed branch with a slash in its name links at it, a segment for each part",
  linkOf("github-feature-pushed", "docs/guide.md") ===
    "https://github.com/octo/demo/blob/feature/x/docs/guide.md",
);
check(
  "an unpushed branch links at the commit, under the served subfolder",
  linkOf("github-subfolder-unpushed", "docs") ===
    "https://github.com/octo/demo/tree/0123456789abcdef0123456789abcdef01234567/docs/docs",
);
// The tooltip says what the last fetch saw, and writes the commit short so the item's
// path is in it; the link keeps the whole commit.
check(
  "an unpushed branch says origin had none at the last fetch, with the commit short",
  tipOf("github-subfolder-unpushed") ===
    "View on GitHub: github.com/octo/demo/tree/0123456789ab/docs. origin had no feature/x at your last fetch, so this commit may not be on github.com either",
);
check(
  "a detached checkout's tooltip writes its commit short",
  tipOf("github-ssh-detached") === "View on GitHub: github.com/octo/demo/tree/0123456789ab",
);
check(
  "a mirror's branch is the origin's",
  linkOf("mirror-github", "(root)") === "https://github.com/octo/demo/tree/main",
);

process.stdout.write(`${JSON.stringify(transcript, null, 2)}\n`);
if (failures.length) {
  process.stderr.write(`${failures.join("\n")}\n`);
  process.exit(1);
}

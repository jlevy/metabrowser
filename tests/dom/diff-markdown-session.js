// Browserless session: a pull request's rendered Markdown views, driven through the
// production browser code.
//
// builtin_plugins/diff/diff-markdown.js and static/inert-html.js load whole. The answers
// are the server's projections, recorded in tests/fixtures/diff-markdown-responses.json by
// tests/test_diff_markdown_session.py, which fails when the server answers differently;
// so is Python's HTML parse of every block, from which this builds the template a page
// parses a block into, so the page's own sanitizer runs on what the server sends. The
// shared chip family, the stylesheet loader and the diff's layout are stand-ins, the page
// is a small element tree that records what the production code builds, and time is a
// clock this advances by hand, so the loading delay and a refused request's wait are
// steps of the story rather than races.
//
// Each step prints the requests the page made, and for each file whose state the step
// changed: its chooser (`*` marks
// the chosen format, `-` one that cannot be chosen), what its body shows (`rendered`,
// `source`, or `nothing` while it waits within the loading delay), whether its progress
// mark is counting down to visible, any message under its bar, and the rendered rows:
// each block's kind and text, `[note]` when its source says more than its render, and
// a fold as `[N unchanged blocks]`, open or closed.

const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const { pathToFileURL } = require("node:url");

const repoRoot = path.resolve(__dirname, "../..");
const recorded = JSON.parse(
  fs.readFileSync(path.join(repoRoot, "tests/fixtures/diff-markdown-responses.json"), "utf8"),
);
const ORIGIN = "http://127.0.0.1:8123";

let finished = false;
process.on("exit", (code) => {
  if (!finished && code === 0) {
    process.stderr.write("Markdown session: ended before its last step\n");
    process.exitCode = 1;
  }
});

function assert(condition, message) {
  if (!condition) {
    throw new Error(message);
  }
}

// ── The page: elements that record what the production code builds ─────────

class ClassList {
  constructor(owner) {
    this.owner = owner;
  }

  get names() {
    return this.owner.className.split(" ").filter(Boolean);
  }

  add(...names) {
    this.owner.className = [...new Set([...this.names, ...names])].join(" ");
  }

  remove(name) {
    this.owner.className = this.names.filter((each) => each !== name).join(" ");
  }

  toggle(name, force) {
    const on = force ?? !this.names.includes(name);
    if (on) {
      this.add(name);
    } else {
      this.remove(name);
    }
    return on;
  }

  contains(name) {
    return this.names.includes(name);
  }
}

class PageElement {
  constructor(tag) {
    this.nodeType = tag === "#text" ? 3 : 1;
    this.tagName = tag.toUpperCase();
    this.className = "";
    this.classList = new ClassList(this);
    this.childNodes = [];
    this.parentElement = null;
    this.attributes = new Map();
    this.listeners = new Map();
    this.dataset = {};
    this.hidden = false;
    this.open = false;
    this.text = "";
    this.id = "";
  }

  get children() {
    return this.childNodes.filter((node) => node.nodeType === 1);
  }

  get textContent() {
    return this.nodeType === 3
      ? this.text
      : this.childNodes.map((node) => node.textContent).join("");
  }

  set textContent(value) {
    if (this.nodeType === 3) {
      this.text = String(value);
      return;
    }
    this.childNodes = [];
    if (value) {
      this.append(text(String(value)));
    }
  }

  get firstElementChild() {
    return this.children[0];
  }

  append(...nodes) {
    for (const node of nodes) {
      if (node.tagName === "#FRAGMENT") {
        this.append(...node.childNodes);
        continue;
      }
      node.parentElement = this;
      this.childNodes.push(node);
    }
  }

  prepend(node) {
    node.parentElement = this;
    this.childNodes.unshift(node);
  }

  replaceChildren(...nodes) {
    this.childNodes = [];
    this.append(...nodes);
  }

  #insert(offset, nodes) {
    const siblings = this.parentElement.childNodes;
    const at = siblings.indexOf(this) + offset;
    for (const node of nodes) {
      node.parentElement = this.parentElement;
    }
    siblings.splice(at, 0, ...nodes);
  }

  after(...nodes) {
    this.#insert(1, nodes);
  }

  before(...nodes) {
    this.#insert(0, nodes);
  }

  setAttribute(name, value) {
    this.attributes.set(name, String(value));
  }

  getAttribute(name) {
    return this.attributes.has(name) ? this.attributes.get(name) : null;
  }

  removeAttribute(name) {
    this.attributes.delete(name);
  }

  addEventListener(name, listener) {
    this.listeners.set(name, listener);
  }

  contains(node) {
    return this === node || this.childNodes.some((child) => child.contains?.(node));
  }

  focus() {
    page.activeElement = this;
  }

  // The chip family's markup, as the shared stand-in below spells it.
  set innerHTML(spec) {
    if (typeof spec !== "object") {
      throw new Error("only a chooser is written as markup here");
    }
    this.childNodes = [];
    for (const option of spec.options) {
      const chip = element("button");
      chip.dataset.chipValue = option.value;
      chip.textContent = option.label;
      chip.setAttribute("aria-checked", String(spec.value === option.value));
      this.append(chip);
    }
  }

  querySelectorAll(selector) {
    const found = [];
    const walk = (parent) => {
      for (const child of parent.children) {
        const tag = child.tagName;
        const wanted =
          selector === "button[data-chip-value]"
            ? tag === "BUTTON" && child.dataset.chipValue !== undefined
            : selector === "a[href], img[src]"
              ? (tag === "A" && child.getAttribute("href") !== null) ||
                (tag === "IMG" && child.getAttribute("src") !== null)
              : tag === selector.toUpperCase();
        if (wanted) {
          found.push(child);
        }
        walk(child);
      }
    };
    walk(this);
    return found;
  }
}

const element = (tag) => new PageElement(tag);
const text = (value) => {
  const node = new PageElement("#text");
  node.text = value;
  return node;
};

// The template a page parses a block into, built from the recorded parse of that block.
function parsed(nodes) {
  return nodes.map((node) => {
    if (typeof node === "string") {
      const built = text(node);
      built.nodeValue = node;
      return built;
    }
    const built = element(node.tag);
    for (const [name, value] of node.attrs) {
      built.setAttribute(name, value);
    }
    built.append(...parsed(node.children));
    return built;
  });
}

function template() {
  const made = element("template");
  Object.defineProperty(made, "innerHTML", {
    set(html) {
      assert(html in recorded.trees, `no recorded parse for ${html}`);
      const content = element("#fragment");
      content.append(...parsed(recorded.trees[html]));
      made.content = content;
    },
  });
  return made;
}

const page = {
  activeElement: null,
  createElement: (tag) => (tag === "template" ? template() : element(tag)),
  createTextNode: (value) => text(String(value)),
  createDocumentFragment: () => element("#fragment"),
  implementation: {
    createHTMLDocument: () => ({
      createElement: (tag) => element(tag),
      createTextNode: (value) => text(String(value)),
    }),
  },
};
globalThis.document = page;
globalThis.window = { location: { origin: ORIGIN } };

let observer;
globalThis.IntersectionObserver = class {
  constructor(notify, options) {
    observer = this;
    this.notify = notify;
    this.options = options;
    this.observed = [];
  }

  observe(target) {
    this.observed.push(target);
  }

  disconnect() {
    this.observed = [];
  }
};

// ── The clock and the server ────────────────────────────────────────────────

const clock = {
  time: 0,
  timers: new Map(),
  next: 1,
  now: () => clock.time,
  later(callback, ms) {
    const handle = clock.next++;
    clock.timers.set(handle, { at: clock.time + ms, callback });
    return handle;
  },
  cancel(handle) {
    clock.timers.delete(handle);
  },
  advance(ms) {
    clock.time += ms;
    for (const [handle, timer] of [...clock.timers].sort((a, b) => a[1].at - b[1].at)) {
      if (timer.at <= clock.time && clock.timers.has(handle)) {
        clock.timers.delete(handle);
        timer.callback();
      }
    }
  },
};

/** Requests the page made since the last step, and the ones still waiting for an answer. */
let requests = [];
const waiting = [];

async function settle() {
  for (let turn = 0; turn < 20; turn += 1) {
    await new Promise((resolve) => setImmediate(resolve));
  }
}

function answer(fileId, how = "recorded") {
  const index = waiting.findIndex((request) => request.fileId === fileId);
  assert(index >= 0, `no request waits for ${fileId}`);
  const [request] = waiting.splice(index, 1);
  if (how === "recorded") {
    request.resolve(structuredClone(recorded.answers[fileId]));
  } else if (how === "busy") {
    request.reject(Object.assign(new Error("rendered_diff_busy"), { status: 429 }));
  } else {
    request.reject(new TypeError("Failed to fetch"));
  }
}

// ── What a step prints ──────────────────────────────────────────────────────

function rows(article) {
  const shown = [];
  for (const node of article.childNodes) {
    if (node.tagName === "P") {
      shown.push(`notice: ${node.textContent}`);
    } else if (node.tagName === "DETAILS") {
      const [summary, ...inner] = node.childNodes;
      shown.push(`[${summary.textContent}${node.open ? ", open" : ""}]`);
      for (const row of inner) {
        shown.push(`  ${row_(row)}`);
      }
    } else {
      shown.push(row_(node));
    }
  }
  return shown;
}

function row_(row) {
  const kind = row.className.replace("diff-markdown-block diff-markdown-", "").split(" ")[0];
  const note = row.classList.contains("diff-markdown-source-only") ? " [note]" : "";
  const prose = row.childNodes.find((node) => node.className === "kpress-prose");
  return `${kind}${note}: ${serialize(prose?.childNodes ?? [])}`;
}

function serialize(nodes) {
  return nodes
    .map((node) => {
      if (node.nodeType === 3) {
        return node.textContent.replace(/\s+/g, " ");
      }
      const tag = node.tagName.toLowerCase();
      const attributes = [...node.attributes]
        .map(([name, value]) => ` ${name}="${value}"`)
        .join("");
      return ["img", "br", "hr"].includes(tag)
        ? `<${tag}${attributes}>`
        : `<${tag}${attributes}>${serialize(node.childNodes)}</${tag}>`;
    })
    .join("");
}

function describe(file) {
  const chips = file.control.children.map((chip) => {
    const chosen = chip.getAttribute("aria-checked") === "true" ? "*" : "";
    return `${chosen}${chip.disabled ? "-" : ""}${chip.textContent}`;
  });
  const shows = !file.rendered.hidden ? "rendered" : !file.source.hidden ? "source" : "nothing";
  return {
    chooser: chips.join(" | "),
    shows,
    ...(file.progress.classList.contains("mb-delayed-loading") ? { progress: "counting" } : {}),
    ...(file.fallback.textContent ? { message: file.fallback.textContent } : {}),
    ...(file.rendered.childNodes.length > 0 ? { rows: rows(file.rendered) } : {}),
  };
}

const steps = [];
/** What each file showed when last printed: a step prints only the files it changed. */
const shown = new Map();
function step(name, files) {
  const changed = [];
  for (const file of files) {
    const now = describe(file);
    const text = JSON.stringify(now);
    if (shown.get(file.name) !== text) {
      shown.set(file.name, text);
      changed.push([file.name, now]);
    }
  }
  steps.push({ step: name, requests, files: Object.fromEntries(changed) });
  requests = [];
}

// ── The story ───────────────────────────────────────────────────────────────

async function main() {
  const inertPath = path.join(repoRoot, "src/metabrowser/static/inert-html.js");
  const context = { window: {}, URL };
  vm.runInNewContext(fs.readFileSync(inertPath, "utf8"), context, { filename: inertPath });
  const inert = context.window.MetabrowserInertHtml;
  const markdown = await import(
    pathToFileURL(path.join(repoRoot, "src/metabrowser/builtin_plugins/diff/diff-markdown.js")).href
  );

  const supported = recorded.manifest.filter((entry) => markdown.supportsMarkdownChange(entry));
  const ahead = markdown.firstScreenMarkdown(recorded.manifest);
  const isSnapshotTarget = markdown.snapshotTargets(recorded.snapshot_route);
  const route = recorded.snapshot_route;
  const links = {
    route,
    opens: Object.fromEntries(
      [
        [`${route}&side=head&path=g1-ZG9jcw%2Fg1-c2V0dXAubWQ&mode=document`, false],
        [`${route}&side=head&path=g1-ZG9jcw%2Fg1-ZGlhZ3JhbS5wbmc&mode=image`, true],
        [`${route}&side=head&path=g1-ZG9jcw%2Fg1-ZGlhZ3JhbS5wbmc&mode=image`, false],
        [`${route}&side=head&path=g1-ZG9jcw%2Fg1-c2V0dXAubWQ&offset=4`, false],
        [route.replace("left=a", "left=0"), false],
        ["/api/tree?path=docs", false],
      ].map(([href, image]) => [
        `${image ? "image" : "link"} ${href}`,
        isSnapshotTarget(href, image),
      ]),
    ),
  };

  const root = element("div");
  const unbinds = [];
  let shared;
  const views = markdown.createMarkdownViews({
    controls: {
      groupHtml: (spec) => spec,
      bind(container, handlers) {
        assert(container === root, "the chooser is bound to the diff");
        shared = handlers.onChange;
        return () => unbinds.push("unbound");
      },
    },
    load(fileId, signal) {
      requests.push(fileId);
      return new Promise((resolve, reject) => {
        const request = { fileId, resolve, reject };
        waiting.push(request);
        signal.addEventListener("abort", () => {
          requests.push(`abort ${fileId}`);
          reject(new DOMException("aborted", "AbortError"));
        });
      });
    },
    ensureInert: async () => inert,
    loadStyles: async () => {},
    mutate: (change) => change(),
    isSnapshotTarget,
    now: clock.now,
    later: clock.later,
    cancel: clock.cancel,
  });

  const files = supported.map((entry) => {
    const section = element("section");
    const bar = element("div");
    bar.append(element("button"));
    const source = element("div");
    source.id = `diff-file-${entry.id}`;
    section.append(bar, source);
    root.append(section);
    const state = views.add({ section, bar, source, id: entry.id });
    const [, control, progress] = bar.childNodes;
    const [, fallback, rendered] = section.childNodes;
    return {
      name: `${entry.id} ${(entry.new ?? entry.old).path}`,
      id: entry.id,
      section,
      source,
      control,
      progress,
      fallback,
      rendered,
      state,
    };
  });
  const byId = Object.fromEntries(files.map((file) => [file.id, file]));
  const choose = async (file, value) => {
    shared(file.source.id, value, "one");
    await settle();
  };
  const near = (...ids) =>
    observer.notify(ids.map((id) => ({ target: byId[id].section, isIntersecting: true })));

  views.observe(root, null);
  steps.push({
    step: "the page asks for the first screen's projections ahead of Changes",
    asks: ahead,
    lookahead: observer.options.rootMargin,
  });
  step("mount: every Markdown file waits for Rendered with Source hidden", files);

  observer.notify(
    files.map((file) => ({
      target: file.section,
      isIntersecting: ["f1", "f2"].includes(file.id),
    })),
  );
  await settle();
  step("the first screen asks for its first file; a file away from it shows Source", files);

  answer("f1");
  await settle();
  step("an answer within the loading delay paints Rendered first", files);

  clock.advance(50);
  await settle();
  step("past the loading delay a waiting file shows Source", files);

  answer("f2");
  await settle();
  step("an unsupported file stays in Source and cannot choose Rendered", files);

  near("f3");
  await settle();
  answer("f3", "busy");
  await settle();
  step("a busy server keeps Rendered and asks again after a wait", files);

  clock.advance(100);
  await settle();
  step("the wait is over", files);

  answer("f3");
  await settle();
  near("f4");
  await settle();
  await choose(byId.f4, "source");
  step("a file over budget shows Source; Source chosen while a request runs", files);

  answer("f4");
  await settle();
  step("the answer is kept, not shown", files);

  await choose(byId.f4, "rendered");
  step("choosing Rendered again shows the kept answer without asking", files);

  const details = byId.f1.rendered.childNodes.find((node) => node.tagName === "DETAILS");
  details.open = true;
  details.listeners.get("toggle")();
  step("opening a fold builds its blocks", [byId.f1]);

  await choose(byId.f1, "source");
  await choose(byId.f1, "rendered");
  near("f1");
  step("switching formats asks for nothing", [byId.f1]);

  views.dispose();
  step("disposal unbinds the chooser and stops every timer", files);
  steps.push({ step: "after disposal", unbound: unbinds, timers: clock.timers.size });

  finished = true;
  process.stdout.write(`${JSON.stringify({ links, steps }, null, 2)}\n`);
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});

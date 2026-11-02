// Browserless session: which layout a diff draws as its width changes, through the
// production browser code.
//
// builtin_plugins/diff/diff-view.js loads whole, as the plugin loads it, and mounts a
// document of the conformance corpus into a small element tree that records what it builds.
// The width a browser would report and the diff's font size are given; what a browser
// lays out at each width is measured in Chrome and recorded beside SPLIT_MIN_WIDTH_EM. Each
// step prints the layout the root says it draws, the rows it holds of each layout, whether
// it has ever built a Split row, the layout control, and what was written to the preference.

const fs = require("node:fs");
const path = require("node:path");
const { pathToFileURL } = require("node:url");

const repoRoot = path.resolve(__dirname, "../..");

function assert(condition, message) {
  if (!condition) {
    throw new Error(message);
  }
}

let splitRowsBuilt = 0;

class PageElement {
  constructor(tag) {
    this.tagName = tag.toUpperCase();
    this.classes = "";
    this.textContent = "";
    this.innerHTML = "";
    this.dataset = {};
    this.children = [];
    this.parentNode = null;
    this.attributes = new Map();
    this.listeners = new Map();
    const owner = this;
    this.classList = {
      contains: (name) => owner.className.split(" ").includes(name),
      toggle(name, force) {
        const names = new Set(owner.className.split(" ").filter(Boolean));
        const want = force === undefined ? !names.has(name) : force;
        if (want) {
          names.add(name);
        } else {
          names.delete(name);
        }
        owner.className = [...names].join(" ");
        return want;
      },
    };
  }

  get className() {
    return this.classes;
  }

  set className(value) {
    this.classes = value;
    if (value.split(" ").includes("diff-split-row")) {
      splitRowsBuilt += 1;
    }
  }

  append(...nodes) {
    for (const node of nodes) {
      node.parentNode = this;
      this.children.push(node);
    }
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

  addEventListener(type, handler) {
    this.listeners.set(type, [...(this.listeners.get(type) ?? []), handler]);
  }

  removeEventListener(type, handler) {
    this.listeners.set(
      type,
      (this.listeners.get(type) ?? []).filter((candidate) => candidate !== handler),
    );
  }

  closest(selector) {
    for (let node = this; node; node = node.parentNode) {
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

  /** Everything the mount built, to compare two mounts node for node. */
  tree() {
    return {
      tag: this.tagName,
      className: this.className,
      textContent: this.textContent,
      innerHTML: this.innerHTML,
      dataset: this.dataset,
      attributes: [...this.attributes],
      children: this.children.map((child) => child.tree()),
    };
  }
}

/** The ResizeObserver a browser gives, driven by a step. */
class WidthObserver {
  static all = [];

  constructor(callback) {
    this.callback = callback;
    this.target = null;
    WidthObserver.all.push(this);
  }

  observe(target) {
    this.target = target;
  }

  disconnect() {
    this.target = null;
  }

  report(width) {
    if (this.target !== null) {
      this.callback([{ contentRect: { width } }], this);
    }
  }
}

const nextTask = () => new Promise((resolve) => setTimeout(resolve, 0));

/** Let the view's intraline work finish, which draws a file again when it refines one. */
async function settle() {
  for (let turn = 0; turn < 10; turn += 1) {
    await nextTask();
  }
}

async function main() {
  globalThis.document = {
    createElement: (tag) => new PageElement(tag),
    addEventListener() {},
    removeEventListener() {},
  };
  globalThis.getComputedStyle = () => ({ fontSize: "14px" });
  globalThis.ResizeObserver = WidthObserver;
  const view = await import(
    pathToFileURL(path.join(repoRoot, "src/metabrowser/builtin_plugins/diff/diff-view.js")).href
  );
  const corpus = JSON.parse(
    fs.readFileSync(
      path.join(repoRoot, "src/metabrowser/data/file-diff-format/file-diff-conformance.json"),
      "utf8",
    ),
  );
  const document_ = corpus.cases.find((entry) => entry.name === "modified-with-heading").document;

  /** A mount in a container this wide, under this preference. */
  function mount(clientWidth, preference) {
    const writes = [];
    let change = null;
    let spec = null;
    const api = {
      highlightSyntax: async () => null,
      isLargeTextPreview: () => true,
      langForPath: () => "",
      prefs: {
        get: (_key, fallback) => preference ?? fallback,
        set(key, value) {
          writes.push(`${key}=${value}`);
          return true;
        },
      },
      filterControls: {
        groupHtml(next) {
          spec = next;
          return "control";
        },
        bind(_root, handlers) {
          change = handlers.onChange;
          return () => {};
        },
      },
    };
    const host = new PageElement("div");
    host.clientWidth = clientWidth;
    const built = splitRowsBuilt;
    const handle = view.mountDiffView(host, document_, api);
    const observer = WidthObserver.all.at(-1);
    return {
      host,
      handle,
      observer,
      async width(width) {
        observer.report(width);
        await nextTask();
      },
      choose(value) {
        change("diff-layout", value, "one");
      },
      line() {
        const root = host.find("diff-root")[0];
        const tips = spec.options.flatMap((option) =>
          option.tip === undefined ? [] : [`${option.label}: ${option.tip}`],
        );
        return {
          draws: root?.dataset.layout ?? null,
          splitRows: host.find("diff-split-row").length,
          unifiedRows: host.find("diff-line").length,
          builtSplit: splitRowsBuilt > built,
          control: spec.value,
          tips,
          preference: [...writes],
        };
      },
    };
  }

  const steps = [];
  const say = (name, page) => steps.push({ step: name, ...page.line() });

  const wide = mount(1049);
  say("a wide pane draws Split, the default", wide);
  await wide.width(1049);
  say("its first report changes nothing", wide);
  await wide.width(618);
  say("618 px is what Split needs: it still fits", wide);
  await wide.width(617);
  say("a pixel short: Unified, and the choice is not written", wide);
  await wide.width(630);
  say("room again, but within what a scrollbar could take back: still Unified", wide);
  await wide.width(637);
  say("still a pixel short of coming back", wide);
  await wide.width(638);
  say("Split, the reader's choice, returns", wide);
  wide.observer.report(617);
  wide.observer.report(900);
  await nextTask();
  say("two reports in one task: the last decides, and nothing is drawn for the first", wide);
  await wide.width(0);
  say("a hidden pane has no width: nothing changes", wide);

  const narrow = mount(440);
  say("opened narrow: Unified from the first draw, with no Split to throw away", narrow);
  await narrow.width(440);
  say("its first report changes nothing", narrow);
  narrow.choose("unified");
  say("choosing what is drawn changes nothing, so Split stays the choice", narrow);
  narrow.choose("split");
  say("choosing Split where it does not fit gets it, with its sideways scroll", narrow);
  await narrow.width(500);
  say("narrower or wider, it stays while the pane stays narrow", narrow);
  await narrow.width(900);
  say("the pane has room", narrow);
  await narrow.width(440);
  say("narrow again: the fallback is back", narrow);
  narrow.choose("split");
  narrow.choose("unified");
  say("choosing Unified is a choice, and is written", narrow);
  await narrow.width(900);
  say("with room, Unified stays", narrow);

  const unified = mount(1049, "unified");
  say("a reader who chose Unified, wide", unified);
  await unified.width(440);
  say("narrow: nothing to do, and no tip", unified);
  await unified.width(1049);
  say("wide again: nothing done", unified);

  const unlaid = mount(0);
  say("a container not laid out yet: Split", unlaid);
  await unlaid.width(440);
  say("its first report is narrow: Unified", unlaid);

  // Height changes report too, and draw nothing: only a new width is looked at.
  const tall = mount(900);
  await tall.width(900);
  await settle();
  const built = splitRowsBuilt;
  await tall.width(900);
  await settle();
  assert(splitRowsBuilt === built, "a report of the same width drew again");

  // A wide pane builds what it built before this was added: the same mount with no observer
  // and no width, as a browserless caller has, matches node for node.
  const measured = mount(1049);
  await measured.width(1049);
  delete globalThis.ResizeObserver;
  delete globalThis.getComputedStyle;
  const bare = mount(undefined);
  await settle();
  globalThis.ResizeObserver = WidthObserver;
  globalThis.getComputedStyle = () => ({ fontSize: "14px" });
  const built_ = (page) => JSON.stringify(page.host.tree()).replace(/diff-file-\w+-\d+/g, "id");
  assert(built_(measured) === built_(bare), "a wide pane drew something a bare mount does not");

  // Disposal: the observer lets go, and a fit still waiting does nothing.
  const leaving = mount(900);
  leaving.observer.report(440);
  leaving.handle.dispose();
  await nextTask();
  assert(leaving.observer.target === null, "dispose left the width observer on");
  assert(leaving.host.find("diff-root").length === 0, "dispose left the root behind");
  const disposed = leaving.line();
  assert(disposed.draws === null && disposed.splitRows === 0, "a disposed view drew");

  const pure = [
    [617, false],
    [618, false],
    [617, true],
    [637, true],
    [638, true],
    [0, true],
    [0, false],
  ].map(
    ([width, was]) =>
      `${width} px, ${was ? "was narrow" : "had room"}: ${view.tooNarrowForSplit(width, 14, was) ? "too narrow" : "fits"}`,
  );
  const scale = [12, 14, 16, 20].map((font) => {
    let width = 1;
    while (view.tooNarrowForSplit(width, font, false)) {
      width += 1;
    }
    return `${font} px text: Split fits from ${width} px`;
  });

  console.log(
    JSON.stringify(
      {
        steps,
        limit: pure,
        byTextSize: scale,
        drawn: [
          ["split", false, false],
          ["split", true, false],
          ["split", true, true],
          ["unified", true, false],
        ].map(
          ([chosen, tight, insisted]) =>
            `${chosen}${tight ? ", narrow" : ""}${insisted ? ", insisted" : ""}: ${view.drawnLayout(chosen, tight, insisted)}`,
        ),
      },
      null,
      2,
    ),
  );
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});

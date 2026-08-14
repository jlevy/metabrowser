const fs = require("node:fs");
const path = require("node:path");

const repoRoot = path.resolve(process.argv[2]);
const failures = [];

function check(name, condition, detail = "failed") {
  if (!condition) {
    failures.push(`${name}: ${detail}`);
  }
}

class ElementShim {}
global.Element = ElementShim;

class FakeElement extends ElementShim {
  constructor(tagName, attributes = {}) {
    super();
    this.tagName = tagName.toUpperCase();
    this.parentElement = null;
    this.attributes = new Map(Object.entries(attributes));
    this.id = attributes.id || "";
    this.scrolled = false;
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

  setAttribute(name, value) {
    this.attributes.set(name, value);
  }

  scrollIntoView() {
    this.scrolled = true;
  }
}

class FakeContainer extends FakeElement {
  constructor(elements) {
    super("main");
    this.elements = elements;
    this.listeners = new Map();
    for (const element of elements) {
      element.parentElement = this;
    }
  }

  addEventListener(name, listener) {
    this.listeners.set(name, listener);
  }

  removeEventListener(name, listener) {
    if (this.listeners.get(name) === listener) {
      this.listeners.delete(name);
    }
  }

  querySelectorAll(selector) {
    if (selector === "a[href]") {
      return this.elements.filter(
        (element) => element.tagName === "A" && element.hasAttribute("href"),
      );
    }
    if (selector === "[id]") {
      return this.elements.filter((element) => element.id);
    }
    const match = /^(\w+)\[(\w+)]$/.exec(selector);
    return match
      ? this.elements.filter(
          (element) => element.tagName === match[1].toUpperCase() && element.hasAttribute(match[2]),
        )
      : [];
  }
}

class FakeEventTarget {
  constructor() {
    this.listeners = new Map();
  }

  addEventListener(name, listener) {
    this.listeners.set(name, listener);
  }

  removeEventListener(name, listener) {
    if (this.listeners.get(name) === listener) {
      this.listeners.delete(name);
    }
  }

  dispatch(name, detail) {
    this.listeners.get(name)?.({ detail });
  }
}

function click(target, overrides = {}) {
  const event = {
    altKey: false,
    button: 0,
    ctrlKey: false,
    defaultPrevented: false,
    metaKey: false,
    preventDefault() {
      this.defaultPrevented = true;
    },
    shiftKey: false,
    target,
    ...overrides,
  };
  return event;
}

async function loadModule() {
  const linksSource = fs.readFileSync(
    path.join(repoRoot, "src/metabrowser/builtin_plugins/markdown/links.js"),
    "utf8",
  );
  const linksUrl = `data:text/javascript;base64,${Buffer.from(linksSource).toString("base64")}`;
  const projectAdaptersSource = fs.readFileSync(
    path.join(repoRoot, "src/metabrowser/builtin_plugins/markdown/project_adapters.js"),
    "utf8",
  );
  const projectAdaptersUrl = `data:text/javascript;base64,${Buffer.from(projectAdaptersSource).toString("base64")}`;
  const wikiResolverSource = fs.readFileSync(
    path.join(repoRoot, "src/metabrowser/builtin_plugins/markdown/wiki_resolver.js"),
    "utf8",
  );
  const wikiResolverUrl = `data:text/javascript;base64,${Buffer.from(wikiResolverSource).toString("base64")}`;
  const wikiEnhancerSource = fs
    .readFileSync(
      path.join(repoRoot, "src/metabrowser/builtin_plugins/markdown/wiki_enhancer.js"),
      "utf8",
    )
    .replace('"./wiki_resolver.js"', JSON.stringify(wikiResolverUrl));
  const wikiEnhancerUrl = `data:text/javascript;base64,${Buffer.from(wikiEnhancerSource).toString("base64")}`;
  const enhancerSource = fs
    .readFileSync(
      path.join(repoRoot, "src/metabrowser/builtin_plugins/markdown/link_enhancer.js"),
      "utf8",
    )
    .replace('"./links.js"', JSON.stringify(linksUrl))
    .replace('"./project_adapters.js"', JSON.stringify(projectAdaptersUrl))
    .replace('"./wiki_enhancer.js"', JSON.stringify(wikiEnhancerUrl));
  return import(`data:text/javascript;base64,${Buffer.from(enhancerSource).toString("base64")}`);
}

(async () => {
  const module = await loadModule();
  const internal = new FakeElement("a", { href: "guide.md#Install" });
  const published = new FakeElement("a", { href: "/published/" });
  const external = new FakeElement("a", { href: "https://example.com/docs" });
  const unsafe = new FakeElement("a", { href: "javascript:alert(1)" });
  const download = new FakeElement("a", { download: "", href: "files/archive.zip" });
  const newTab = new FakeElement("a", { href: "other.md", target: "_blank" });
  const image = new FakeElement("img", { src: "../images/map 1.svg#layer" });
  const remoteImage = new FakeElement("img", { src: "https://example.com/map.svg" });
  const unsafeImage = new FakeElement("img", { src: "data:image/png;base64,AA" });
  const heading = new FakeElement("h2", { id: "Install" });
  const container = new FakeContainer([
    internal,
    published,
    external,
    unsafe,
    download,
    newTab,
    image,
    remoteImage,
    unsafeImage,
    heading,
  ]);
  const eventTarget = new FakeEventTarget();
  const frames = new Map();
  let frameSequence = 0;
  const opened = [];
  let current = { path: "docs/readme.md", fragment: "Install" };
  const mb = {
    fileCatalog: {
      snapshot: () => ({
        complete: true,
        files: [{ path: "mkdocs.yml" }, { path: "docs/published.md" }],
      }),
      subscribe: () => () => {},
    },
    navigation: {
      current: () => current,
      href: (target) => `/view/${target.path}${target.fragment ? `#${target.fragment}` : ""}`,
      open: async (target) => opened.push(target),
    },
  };
  const handle = module.enhanceRenderedLinks(container, "docs/readme.md", mb, {
    cancel: (id) => frames.delete(id),
    eventTarget,
    schedule: (callback) => {
      frameSequence += 1;
      frames.set(frameSequence, callback);
      return frameSequence;
    },
  });

  check("canonical internal href", internal.getAttribute("href") === "/view/docs/guide.md#Install");
  check(
    "configured published route href",
    published.getAttribute("href") === "/view/docs/published.md",
  );
  check(
    "configured adapter disclosed",
    published.getAttribute("data-metabrowser-link-adapter") === "mkdocs",
  );
  check("external href preserved", external.getAttribute("href") === "https://example.com/docs");
  check("unsafe href removed", !unsafe.hasAttribute("href"));
  check("unsafe link keyboard reachable", unsafe.getAttribute("tabindex") === "0");
  check("unsafe link explained", unsafe.getAttribute("aria-disabled") === "true");
  check(
    "local image raw URL",
    image.getAttribute("src") === "/raw?path=images%2Fmap%201.svg#layer",
  );
  check(
    "remote image preserved",
    remoteImage.getAttribute("src") === "https://example.com/map.svg",
  );
  check("unsafe image source removed", !unsafeImage.hasAttribute("src"));

  for (const callback of [...frames.values()]) {
    callback(0);
  }
  frames.clear();
  check("initial fragment after enhancement", heading.scrolled);

  const internalClick = click(internal);
  container.listeners.get("click")(internalClick);
  await new Promise((resolve) => setImmediate(resolve));
  check("plain click intercepted", internalClick.defaultPrevented);
  check("plain click opened once", opened.length === 1);
  check("resolved click target", opened[0].path === "docs/guide.md");

  for (const [name, anchor, overrides] of [
    ["modifier", internal, { metaKey: true }],
    ["middle", internal, { button: 1 }],
    ["download", download, {}],
    ["new browsing context", newTab, {}],
  ]) {
    const nativeClick = click(anchor, overrides);
    container.listeners.get("click")(nativeClick);
    check(`${name} click preserved`, !nativeClick.defaultPrevented);
  }
  check("native variants did not open", opened.length === 1);

  heading.scrolled = false;
  current = { path: "docs/readme.md", fragment: "Install" };
  eventTarget.dispatch("metabrowser:navigation-fragment", { target: current });
  handle.dispose();
  check("dispose removes click listener", !container.listeners.has("click"));
  check(
    "dispose removes fragment listener",
    !eventTarget.listeners.has("metabrowser:navigation-fragment"),
  );
  check("dispose cancels pending scroll", frames.size === 0);

  if (failures.length) {
    console.error(`markdown link enhancer FAILURES:\n- ${failures.join("\n- ")}`);
    process.exit(1);
  }
  console.log("markdown link enhancer OK");
})().catch((error) => {
  console.error(error);
  process.exit(1);
});

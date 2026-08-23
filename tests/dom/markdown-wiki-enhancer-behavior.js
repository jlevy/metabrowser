const fs = require("node:fs");
const path = require("node:path");

const repoRoot = path.resolve(process.argv[2]);
const failures = [];

function check(name, condition, detail = "failed") {
  if (!condition) {
    failures.push(`${name}: ${detail}`);
  }
}

class FakeElement {
  constructor(tagName, attributes = {}, textContent = "") {
    this.attributes = new Map(Object.entries(attributes));
    this.innerHTML = "";
    this.parentElement = null;
    this.tagName = tagName.toUpperCase();
    this.textContent = textContent;
  }

  getAttribute(name) {
    return this.attributes.has(name) ? this.attributes.get(name) : null;
  }

  hasAttribute(name) {
    return this.attributes.has(name);
  }

  setAttribute(name, value) {
    this.attributes.set(name, value);
  }

  replaceWith(replacement) {
    const index = this.parentElement.elements.indexOf(this);
    this.parentElement.elements[index] = replacement;
    replacement.parentElement = this.parentElement;
    this.parentElement = null;
  }
}

class FakeContainer extends FakeElement {
  constructor(elements) {
    super("main");
    this.elements = elements;
    this.ownerDocument = { createElement: (tagName) => new FakeElement(tagName) };
    for (const element of elements) {
      element.parentElement = this;
    }
  }

  querySelectorAll(selector) {
    return selector === "[data-mb-wiki-target]"
      ? this.elements.filter((element) => element.hasAttribute("data-mb-wiki-target"))
      : [];
  }
}

async function loadModule() {
  const parserSource = fs.readFileSync(
    path.join(repoRoot, "src/metabrowser/builtin_plugins/markdown/wiki-parser.js"),
    "utf8",
  );
  const parserUrl = `data:text/javascript;base64,${Buffer.from(parserSource).toString("base64")}`;
  const transclusionSource = fs
    .readFileSync(
      path.join(repoRoot, "src/metabrowser/builtin_plugins/markdown/transclusion.js"),
      "utf8",
    )
    .replace('"./wiki-parser.js"', JSON.stringify(parserUrl));
  const transclusionUrl = `data:text/javascript;base64,${Buffer.from(transclusionSource).toString("base64")}`;
  const resolverSource = fs.readFileSync(
    path.join(repoRoot, "src/metabrowser/builtin_plugins/markdown/wiki-resolver.js"),
    "utf8",
  );
  const resolverUrl = `data:text/javascript;base64,${Buffer.from(resolverSource).toString("base64")}`;
  const enhancerSource = fs
    .readFileSync(
      path.join(repoRoot, "src/metabrowser/builtin_plugins/markdown/wiki-enhancer.js"),
      "utf8",
    )
    .replace('"./transclusion.js"', JSON.stringify(transclusionUrl))
    .replace('"./wiki-resolver.js"', JSON.stringify(resolverUrl));
  return import(`data:text/javascript;base64,${Buffer.from(enhancerSource).toString("base64")}`);
}

(async () => {
  const module = await loadModule();
  const exact = new FakeElement(
    "span",
    { "data-mb-wiki-action": "navigate", "data-mb-wiki-target": "Exact" },
    "Exact label",
  );
  const unique = new FakeElement(
    "span",
    { "data-mb-wiki-action": "navigate", "data-mb-wiki-target": "Unique" },
    "Unique",
  );
  const ambiguous = new FakeElement(
    "span",
    { "data-mb-wiki-action": "navigate", "data-mb-wiki-target": "Duplicate" },
    "Duplicate",
  );
  const missing = new FakeElement(
    "span",
    { "data-mb-wiki-action": "navigate", "data-mb-wiki-target": "Missing" },
    "Missing",
  );
  const image = new FakeElement(
    "span",
    {
      "data-mb-wiki-action": "embed",
      "data-mb-wiki-height": "480",
      "data-mb-wiki-target": "image.png",
      "data-mb-wiki-width": "640",
    },
    "Diagram",
  );
  const noteEmbed = new FakeElement(
    "span",
    { "data-mb-wiki-action": "embed", "data-mb-wiki-target": "Exact" },
    "Exact embed",
  );
  const container = new FakeContainer([exact, unique, ambiguous, missing, image, noteEmbed]);
  const files = [
    { path: "docs/Exact.md" },
    { path: "docs/image.png" },
    { path: "else/Unique.md" },
    { path: "one/Duplicate.md" },
    { path: "two/Duplicate.md" },
  ];
  let complete = false;
  let catalogListener = null;
  let unsubscribeCount = 0;
  const registered = [];
  const mb = {
    fetchKpressRender: async () => ({ html: '<article class="kpress">Embedded</article>' }),
    fetchText: async () => "# Embedded note\n",
    fileCatalog: {
      snapshot: () => ({ complete, files }),
      subscribe: (listener) => {
        catalogListener = listener;
        return () => {
          catalogListener = null;
          unsubscribeCount += 1;
        };
      },
    },
    navigation: {
      href: (target) =>
        `/view/${target.path}${target.fragment ? `#${encodeURIComponent(target.fragment)}` : ""}`,
    },
  };

  const handle = module.enhanceWikiLinks(container, "docs/current.md", mb, (element, target) => {
    registered.push({ element, target });
  });
  check("exact link resolves before complete", container.elements[0].tagName === "A");
  check(
    "exact link canonical href",
    container.elements[0].getAttribute("href") === "/view/docs/Exact.md",
  );
  check("exact label preserved", container.elements[0].textContent === "Exact label");
  check(
    "unique link starts pending",
    unique.getAttribute("data-metabrowser-link-status") === "pending",
  );
  check("pending state visible", unique.textContent.includes("resolving link"));
  check("pending inventory subscription", typeof catalogListener === "function");
  const renderedImage = container.elements[4];
  check("image embed element", renderedImage.tagName === "IMG");
  check(
    "image embed safe raw source",
    renderedImage.getAttribute("src") === "/raw?path=docs%2Fimage.png",
  );
  check(
    "image embed dimensions",
    renderedImage.getAttribute("width") === "640" && renderedImage.getAttribute("height") === "480",
  );
  check("image accessible label", renderedImage.getAttribute("alt") === "Diagram");
  const noteTransclusion = container.elements[5];
  check("note transclusion region", noteTransclusion.tagName === "ASIDE");
  await new Promise((resolve) => setImmediate(resolve));
  check(
    "note transclusion rendered",
    noteTransclusion.getAttribute("data-metabrowser-transclusion-status") === "ready",
  );

  complete = true;
  catalogListener();
  check("unique link resolves after completion", container.elements[1].tagName === "A");
  check(
    "unique link target",
    container.elements[1].getAttribute("href") === "/view/else/Unique.md",
  );
  check("ambiguous remains visible", ambiguous.textContent.includes("ambiguous link"));
  check("ambiguous link semantics", ambiguous.getAttribute("role") === "link");
  check(
    "ambiguous candidates announced",
    ambiguous.getAttribute("aria-label").includes("one/Duplicate.md"),
  );
  check("missing remains visible", missing.textContent.includes("missing link"));
  check("subscription released after settling", catalogListener === null && unsubscribeCount === 1);
  check("navigation registrations", registered.length === 2);
  handle.dispose();
  check("settled disposal is idempotent", unsubscribeCount === 1);

  const pendingOnly = new FakeElement(
    "span",
    { "data-mb-wiki-action": "navigate", "data-mb-wiki-target": "Later" },
    "Later",
  );
  complete = false;
  const pendingHandle = module.enhanceWikiLinks(
    new FakeContainer([pendingOnly]),
    "docs/current.md",
    mb,
    () => {},
  );
  check("second mount subscribed", typeof catalogListener === "function");
  pendingHandle.dispose();
  check(
    "dispose releases pending subscription",
    catalogListener === null && unsubscribeCount === 2,
  );

  if (failures.length) {
    console.error(`markdown wiki enhancer FAILURES:\n- ${failures.join("\n- ")}`);
    process.exit(1);
  }
  console.log("markdown wiki enhancer OK");
})().catch((error) => {
  console.error(error);
  process.exit(1);
});

// stackMemberRow, the one builder of a pull request's fields (github/stack-member-row.js),
// run without a browser on the production module: what each layout shows for a pull request
// with and without a stack place and an author, and that a field that is absent draws neither
// itself nor the dot before it, however the row got there.
const assert = require("node:assert/strict");
const path = require("node:path");
const { pathToFileURL } = require("node:url");

class Element {
  constructor(tag) {
    this.tag = tag;
    this.attributes = new Map();
    this.children = [];
    this.parentNode = null;
    this.hidden = false;
    this.dataset = {};
    this.classList = {
      add: (name) => this.setAttribute("class", [this.className, name].filter(Boolean).join(" ")),
    };
  }
  get className() {
    return this.getAttribute("class") ?? "";
  }
  set className(value) {
    this.setAttribute("class", value);
  }
  getAttribute(name) {
    return this.attributes.get(name) ?? null;
  }
  setAttribute(name, value) {
    this.attributes.set(name, String(value));
  }
  removeAttribute(name) {
    this.attributes.delete(name);
  }
  append(...nodes) {
    for (const node of nodes) {
      if (typeof node !== "string") {
        node.remove();
        node.parentNode = this;
      }
      this.children.push(node);
    }
  }
  replaceChildren(...nodes) {
    for (const child of this.children) {
      if (typeof child !== "string") {
        child.parentNode = null;
      }
    }
    this.children = [];
    this.append(...nodes);
  }
  insertBefore(node, before) {
    node.remove();
    node.parentNode = this;
    this.children.splice(this.children.indexOf(before), 0, node);
  }
  remove() {
    if (this.parentNode !== null) {
      this.parentNode.children = this.parentNode.children.filter((child) => child !== this);
      this.parentNode = null;
    }
  }
  get textContent() {
    return this.children
      .map((child) => (typeof child === "string" ? child : child.textContent))
      .join("");
  }
  set textContent(value) {
    this.replaceChildren(...(value === "" ? [] : [String(value)]));
  }
}

globalThis.document = {
  createElement: (tag) => new Element(tag),
  importNode: (node) => node,
};
globalThis.DOMParser = class {
  parseFromString() {
    return { body: { firstElementChild: null } };
  }
};

// What a reader sees: the text of every node not hidden, its spaces collapsed.
const seen = (node) =>
  (typeof node === "string" ? node : node.hidden ? "" : node.children.map(seen).join("")).replace(
    /\s+/g,
    " ",
  );
// The classes of the parts after the icon, in order, so an empty part shows.
const parts = (link) => {
  const holder = link.children.find((child) => child.className.endsWith("-copy"));
  return (holder ?? link).children
    .filter((child) => typeof child !== "string" && !child.hidden)
    .map((child) => child.className);
};

(async () => {
  const module = await import(
    pathToFileURL(
      path.resolve(__dirname, "../../src/metabrowser/builtin_plugins/github/stack-member-row.js"),
    ).href
  );
  const { MEMBER_LINE, PULLS_RUN, stackMemberRow } = module;
  const titleNodes = (title) => [title];
  const identity = (login) => {
    const element = new Element("span");
    element.className = "actor-identity";
    element.textContent = login;
    return element;
  };
  const member = (place, author) => ({
    number: 455,
    place,
    title: "feat: one order",
    state: "open",
    author: author === null ? null : { login: author, avatar: null },
  });
  const draw = (layout, ...members) => {
    const link = new Element(layout.flow ? "span" : "a");
    const row = stackMemberRow(link, titleNodes, identity, layout);
    for (const line of members) {
      row.show(line);
    }
    return { seen: seen(link).trim(), parts: parts(link) };
  };

  const line = {
    placed: draw(MEMBER_LINE, member("14/15", "jlevy")),
    noPlace: draw(MEMBER_LINE, member(null, "jlevy")),
    noPlaceNoAuthor: draw(MEMBER_LINE, member(null, null)),
    placeLost: draw(MEMBER_LINE, member("14/15", "jlevy"), member(null, "jlevy")),
    placeFound: draw(MEMBER_LINE, member(null, "jlevy"), member("2/3", "jlevy")),
    placeMoved: draw(MEMBER_LINE, member("1/3", "jlevy"), member("2/3", "jlevy")),
  };
  const run = {
    placed: draw(PULLS_RUN, member("14/15", "jlevy")),
    noPlace: draw(PULLS_RUN, member(null, "jlevy")),
    noPlaceNoAuthor: draw(PULLS_RUN, member(null, null)),
    placeLost: draw(PULLS_RUN, member("14/15", "jlevy"), member(null, "jlevy")),
  };
  // A field that is absent draws no dot: no row's text starts or ends with one, or has two
  // with nothing between them.
  for (const drawn of [...Object.values(line), ...Object.values(run)]) {
    assert.doesNotMatch(drawn.seen, /^·|·$|·\s*·/, drawn.seen);
  }
  assert.deepEqual(line.placeLost, line.noPlace);
  assert.deepEqual(run.placeLost, run.noPlace);
  console.log(JSON.stringify({ line, run }));
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});

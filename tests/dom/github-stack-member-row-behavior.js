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

// The order the design sets (docs/design-system.md, "One Order for a Pull Request's Fields").
const ORDER = ["title", "place", "by", "number"];

// What a reader meets, in order: each field the row draws, by the layout's name for it, and
// each dot. A hidden node draws nothing; a field drawn empty still counts, as its element is
// on the line; a dot inside a field is met before the field's own words.
const tokens = (link, layout) => {
  const fieldOf = new Map(ORDER.map((name) => [layout[name], name]));
  const met = [];
  const walk = (node, pending) => {
    if (typeof node === "string") {
      const text = node.trim();
      if (text === "·") {
        met.push("·");
      } else if (text !== "" && pending.name !== null && !pending.met) {
        met.push(pending.name);
        pending.met = true;
      }
      return;
    }
    if (node.hidden || node.className.split(" ").includes("sr-only")) {
      return;
    }
    const name = fieldOf.get(node.className);
    const own = name === undefined ? pending : { name, met: false };
    for (const child of node.children) {
      walk(child, own);
    }
    if (own !== pending && !own.met) {
      met.push(own.name);
    }
  };
  walk(link, { name: null, met: true });
  return met;
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
  const given = (line) =>
    ORDER.filter(
      (name) => (name === "place" ? line.place : name === "by" ? line.author : 1) !== null,
    );
  // Each case: the members shown one after another; the row is read after the last.
  const cases = {
    placed: [member("14/15", "jlevy")],
    noPlace: [member(null, "jlevy")],
    noAuthor: [member("14/15", null)],
    neither: [member(null, null)],
    placeLost: [member("14/15", "jlevy"), member(null, "jlevy")],
    placeFound: [member(null, "jlevy"), member("2/3", "jlevy")],
    authorLost: [member("2/3", "jlevy"), member("2/3", null)],
  };
  const draw = (layout, members) => {
    const sidebar = layout === PULLS_RUN;
    const link = new Element(sidebar ? "span" : "a");
    const row = stackMemberRow(link, titleNodes, identity, layout);
    for (const line of members) {
      row.show(line);
    }
    if (sidebar) {
      assert.equal(row.end.parentNode, null, "the sidebar places the suffix on its summary line");
      link.append(row.end);
    }
    return tokens(link, layout);
  };
  let drawings = 0;
  for (const [name, members] of Object.entries(cases)) {
    const last = members.at(-1);
    const byLayout = [MEMBER_LINE, PULLS_RUN].map((layout) => {
      drawings += 1;
      const met = draw(layout, members);
      const said = `${name}: ${met.join(" ")}`;
      // A dot sits between two fields: none starts or ends the row, and no two meet.
      assert.ok(
        met[0] !== "·" &&
          met.at(-1) !== "·" &&
          met.every((token, at) => token !== "·" || met[at + 1] !== "·"),
        said,
      );
      // A run has a dot before each field after the title; a line none before the first of
      // them, which starts the group at the line's end, and one before each of the rest.
      const after = met.slice(met.indexOf("title") + 1);
      const dotted = after
        .map((token, at) => (token === "·" ? null : after[at - 1] === "·"))
        .filter((dot) => dot !== null);
      assert.deepEqual(
        dotted,
        dotted.map((_, at) => after.filter((token) => token !== "·")[at] !== "number"),
        said,
      );
      // An absent field draws nothing, not even an empty element, and the fields drawn keep
      // the one order.
      const shown = met.filter((token) => token !== "·");
      assert.deepEqual(
        shown,
        layout === PULLS_RUN ? given(last).filter((field) => field !== "place") : given(last),
        said,
      );
      // A row that got here by changing reads as one drawn so at once.
      assert.deepEqual(met, draw(layout, [last]), said);
      return shown;
    });
    // A line and a run show the same fields in the same order.
    assert.deepEqual(
      byLayout[0].filter((field) => field !== "place"),
      byLayout[1],
      name,
    );
  }
  console.log(
    JSON.stringify({
      cases: Object.keys(cases).length,
      drawings,
      dotsSitBetweenFields: true,
      absentFieldsDrawNothing: true,
      fieldsKeepTheOneOrder: true,
      changedRowsReadAsDrawn: true,
      layoutsAgree: true,
    }),
  );
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});

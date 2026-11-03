// Small shared DOM stand-in for Pulls session and variable-height mount behavior.
const assert = require("node:assert/strict");
class FakeNode {
  constructor(nodeName) {
    this.nodeName = nodeName;
    this.childNodes = [];
    this.parentNode = null;
  }
  get firstChild() {
    return this.childNodes[0] ?? null;
  }
  get nextSibling() {
    return this.parentNode?.childNodes[this.parentNode.childNodes.indexOf(this) + 1] ?? null;
  }
  insertBefore(node, before) {
    if (node === before) {
      return node;
    }
    node.parentNode?.drop(node);
    const index = before === null ? this.childNodes.length : this.childNodes.indexOf(before);
    assert(index >= 0, "insertBefore reference must be a child");
    node.parentNode = this;
    this.childNodes.splice(index, 0, node);
    return node;
  }
  append(...nodes) {
    for (const node of nodes) {
      this.adopt(typeof node === "string" ? new FakeText(node) : node);
    }
  }
  adopt(node) {
    if (node.nodeName === "#fragment") {
      for (const child of [...node.childNodes]) {
        this.adopt(child);
      }
      return;
    }
    node.parentNode?.drop(node);
    node.parentNode = this;
    this.childNodes.push(node);
  }
  drop(node) {
    this.childNodes.splice(this.childNodes.indexOf(node), 1);
    node.parentNode = null;
  }
  remove() {
    this.parentNode?.drop(this);
  }
  replaceChildren(...nodes) {
    for (const child of [...this.childNodes]) {
      this.drop(child);
    }
    this.append(...nodes);
  }
  contains(node) {
    for (let at = node; at; at = at.parentNode) {
      if (at === this) {
        return true;
      }
    }
    return false;
  }
  get textContent() {
    return this.childNodes.map((child) => child.textContent).join("");
  }
  set textContent(value) {
    this.replaceChildren(String(value));
  }
}

class FakeText extends FakeNode {
  constructor(data) {
    super("#text");
    this.data = data;
  }
  get textContent() {
    return this.data;
  }
  set textContent(value) {
    this.data = String(value);
  }
}

class FakeElement extends FakeNode {
  constructor(tag) {
    super(tag.toUpperCase());
    this.localName = tag;
    this.attributes = new Map();
    this.dataset = {};
    this.style = {
      setProperty(name, value) {
        this[name] = value;
      },
    };
    this.listeners = new Map();
    this.hidden = false;
    this.classes = new Set();
  }
  get classList() {
    const classes = this.classes;
    return {
      add(...names) {
        for (const name of names) {
          classes.add(name);
        }
      },
      remove(...names) {
        for (const name of names) {
          classes.delete(name);
        }
      },
      contains: (name) => classes.has(name),
      toggle(name, on) {
        const wanted = on ?? !classes.has(name);
        if (wanted) {
          classes.add(name);
        } else {
          classes.delete(name);
        }
        return wanted;
      },
    };
  }
  get className() {
    return [...this.classes].join(" ");
  }
  set className(value) {
    this.classes = new Set(String(value).split(/\s+/).filter(Boolean));
  }
  setAttribute(name, value) {
    if (name === "class") {
      this.className = value;
    } else if (name.startsWith("data-")) {
      this.dataset[name.slice(5).replace(/-([a-z])/g, (_, letter) => letter.toUpperCase())] =
        String(value);
    } else {
      this.attributes.set(name, String(value));
    }
  }
  getAttribute(name) {
    return name === "class" ? this.className : (this.attributes.get(name) ?? null);
  }
  toggleAttribute(name, on) {
    if (on ?? !this.attributes.has(name)) {
      this.setAttribute(name, "");
    } else {
      this.removeAttribute(name);
    }
  }
  removeAttribute(name) {
    this.attributes.delete(name);
  }
  get firstElementChild() {
    return this.childNodes.find((child) => child instanceof FakeElement) ?? null;
  }
  addEventListener(type, listener) {
    this.listeners.set(type, listener);
  }
  closest(selector) {
    const [tag, name] = selector.split(".");
    for (let node = this; node !== null; node = node.parentNode) {
      if ((!tag || node.localName === tag) && (!name || node.classList?.contains(name))) {
        return node;
      }
    }
    return null;
  }
  querySelectorAll() {
    return [];
  }
  focus() {
    if (globalThis.document) {
      globalThis.document.activeElement = this;
    }
  }
  get tagName() {
    return this.nodeName;
  }
  get nextElementSibling() {
    let node = this.nextSibling;
    while (node && !(node instanceof FakeElement)) {
      node = node.nextSibling;
    }
    return node;
  }
  get isConnected() {
    return globalThis.document?.body?.contains(this) ?? false;
  }
  getBoundingClientRect() {
    return this.bounds?.() ?? { top: 0, bottom: 0, height: 0, left: 0, right: 800, width: 800 };
  }
  scrollIntoView() {}
  set innerHTML(html) {
    this.childNodes = [];
    this.markup = html;
  }
}

module.exports = { FakeNode, FakeElement };

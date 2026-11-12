// A small stand-in for the DOM, for the key reveal's browserless tests.
//
// The registry reads a badge target's liveness from the tree itself: connected, not
// `disabled`, outside `inert`, and visible by computed style. So this stand-in keeps a
// real tree with document order, attributes that reflect (`id`, `class`, `hidden`,
// `inert`, `disabled`, `data-*`), inline styles the computed style reads, focus, event
// capture and bubbling, and the selectors the shell's modules query with: tags, ids,
// classes, attribute tests, `:not()`, and the descendant and child combinators, in comma
// lists. It renders nothing.
//
// The window is on every event's path, above the document, as in a browser: a capture
// listener on it hears every event in the page, including the `focus` and `blur` that do
// not bubble. Moving focus fires `blur` and `focusout` on the element losing it, then
// `focus` and `focusin` on the one gaining it, in a browser's order.
//
// `innerHTML` parses the markup the shell's string renderers write (elements, quoted and
// bare attributes, text, and the entities `esc()` produces), so a module that renders
// HTML, as static/filter-controls.js does, runs whole.

const DOCUMENT_POSITION_PRECEDING = 2;
const DOCUMENT_POSITION_FOLLOWING = 4;

/** Listeners, and dispatch along an event path of capture, target, and bubble. */
class FakeEventTarget {
  constructor() {
    this.listeners = [];
  }

  addEventListener(type, listener, options) {
    const capture = options === true || Boolean(options?.capture);
    if (
      !this.listeners.some(
        (entry) => entry.type === type && entry.listener === listener && entry.capture === capture,
      )
    ) {
      this.listeners.push({ type, listener, capture });
    }
  }

  removeEventListener(type, listener, options) {
    const capture = options === true || Boolean(options?.capture);
    this.listeners = this.listeners.filter(
      (entry) => !(entry.type === type && entry.listener === listener && entry.capture === capture),
    );
  }

  /** From the outermost target to this one; the window, a document's, comes first. */
  eventPath() {
    return [this];
  }

  /** Capture from the window down, the target itself, then bubble back up. */
  dispatchEvent(event) {
    event.target ??= this;
    event.defaultPrevented ??= false;
    event.preventDefault ??= function preventDefault() {
      this.defaultPrevented = true;
    };
    let stopped = false;
    event.stopPropagation = () => {
      stopped = true;
    };
    const path = this.eventPath();
    const run = (node, phase) => {
      for (const entry of [...node.listeners]) {
        if (entry.type !== event.type) {
          continue;
        }
        if (phase === "capture" && !entry.capture) {
          continue;
        }
        if (phase === "bubble" && entry.capture) {
          continue;
        }
        event.currentTarget = node;
        entry.listener(event);
      }
    };
    for (const node of path.slice(0, -1)) {
      run(node, "capture");
      if (stopped) {
        return !event.defaultPrevented;
      }
    }
    run(this, "target");
    if (event.bubbles !== false) {
      for (const node of path.slice(0, -1).reverse()) {
        if (stopped) {
          break;
        }
        run(node, "bubble");
      }
    }
    return !event.defaultPrevented;
  }
}

class FakeNode extends FakeEventTarget {
  constructor(document, nodeName) {
    super();
    this.ownerDocument = document;
    this.nodeName = nodeName;
    this.childNodes = [];
    this.parentNode = null;
  }

  get parentElement() {
    return this.parentNode instanceof FakeElement ? this.parentNode : null;
  }

  get children() {
    return this.childNodes.filter((node) => node instanceof FakeElement);
  }

  get firstElementChild() {
    return this.children[0] ?? null;
  }

  get nextElementSibling() {
    const siblings = this.parentNode?.children ?? [];
    return siblings[siblings.indexOf(this) + 1] ?? null;
  }

  get isConnected() {
    let node = this;
    while (node.parentNode) {
      node = node.parentNode;
    }
    return node === this.ownerDocument;
  }

  get textContent() {
    return this.childNodes.map((node) => node.textContent).join("");
  }

  set textContent(value) {
    this.replaceChildren();
    if (value !== "" && value !== null && value !== undefined) {
      this.append(this.ownerDocument.createTextNode(String(value)));
    }
  }

  append(...nodes) {
    for (const node of nodes) {
      this.insertBefore(
        typeof node === "string" ? this.ownerDocument.createTextNode(node) : node,
        null,
      );
    }
  }

  appendChild(node) {
    return this.insertBefore(node, null);
  }

  insertBefore(node, before) {
    node.remove();
    const index = before ? this.childNodes.indexOf(before) : this.childNodes.length;
    if (index < 0) {
      throw new Error("insertBefore: the reference node is not a child");
    }
    node.parentNode = this;
    this.childNodes.splice(index, 0, node);
    return node;
  }

  remove() {
    if (this.parentNode) {
      const siblings = this.parentNode.childNodes;
      siblings.splice(siblings.indexOf(this), 1);
      this.parentNode = null;
    }
  }

  replaceChildren(...nodes) {
    for (const node of [...this.childNodes]) {
      node.remove();
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

  compareDocumentPosition(other) {
    const order = this.ownerDocument.treeOrder();
    const here = order.indexOf(this);
    const there = order.indexOf(other);
    if (here < 0 || there < 0 || here === there) {
      return 0;
    }
    return there > here ? DOCUMENT_POSITION_FOLLOWING : DOCUMENT_POSITION_PRECEDING;
  }

  /** The node's ancestors, then the window of a connected node's document. */
  eventPath() {
    const path = [];
    for (let node = this; node; node = node.parentNode) {
      path.unshift(node);
    }
    if (path[0] instanceof FakeDocument && path[0].defaultView) {
      path.unshift(path[0].defaultView);
    }
    return path;
  }

  querySelectorAll(selector) {
    const groups = parseSelectorList(selector);
    const found = [];
    const visit = (node) => {
      for (const child of node.children) {
        if (groups.some((group) => matchesGroup(child, group, this))) {
          found.push(child);
        }
        visit(child);
      }
    };
    visit(this);
    return found;
  }

  querySelector(selector) {
    return this.querySelectorAll(selector)[0] ?? null;
  }
}

class FakeText extends FakeNode {
  constructor(document, data) {
    super(document, "#text");
    this.data = data;
  }

  get textContent() {
    return this.data;
  }

  set textContent(value) {
    this.data = String(value);
  }
}

const REFLECTED_BOOLEANS = new Set(["hidden", "inert", "disabled"]);

class FakeStyle {
  constructor() {
    this.properties = new Map();
  }

  setProperty(name, value) {
    this.properties.set(name, String(value));
  }

  getPropertyValue(name) {
    return this.properties.get(name) ?? "";
  }

  removeProperty(name) {
    this.properties.delete(name);
  }

  get display() {
    return this.getPropertyValue("display");
  }

  set display(value) {
    this.setProperty("display", value);
  }

  get visibility() {
    return this.getPropertyValue("visibility");
  }

  set visibility(value) {
    this.setProperty("visibility", value);
  }
}

class FakeElement extends FakeNode {
  constructor(document, tagName) {
    super(document, tagName.toUpperCase());
    this.tagName = tagName.toUpperCase();
    this.localName = tagName.toLowerCase();
    this.attributes = new Map();
    this.style = new FakeStyle();
    this.isContentEditable = false;
    this.value = "";
    this.rect = null;
    const element = this;
    this.dataset = new Proxy(
      {},
      {
        get(_target, name) {
          return typeof name === "string"
            ? (element.getAttribute(`data-${toKebab(name)}`) ?? undefined)
            : undefined;
        },
        set(_target, name, value) {
          element.setAttribute(`data-${toKebab(String(name))}`, value);
          return true;
        },
        deleteProperty(_target, name) {
          element.removeAttribute(`data-${toKebab(String(name))}`);
          return true;
        },
        has(_target, name) {
          return element.hasAttribute(`data-${toKebab(String(name))}`);
        },
        ownKeys() {
          return [...element.attributes.keys()]
            .filter((key) => key.startsWith("data-"))
            .map((key) =>
              key.slice(5).replace(/-([a-z])/g, (_match, letter) => letter.toUpperCase()),
            );
        },
        getOwnPropertyDescriptor(_target, name) {
          const value = element.getAttribute(`data-${toKebab(String(name))}`);
          return value === null ? undefined : { configurable: true, enumerable: true, value };
        },
      },
    );
  }

  get id() {
    return this.getAttribute("id") ?? "";
  }

  set id(value) {
    this.setAttribute("id", value);
  }

  get className() {
    return this.getAttribute("class") ?? "";
  }

  set className(value) {
    this.setAttribute("class", value);
  }

  get classList() {
    const names = () => this.className.split(/\s+/).filter(Boolean);
    const write = (values) => this.setAttribute("class", [...new Set(values)].join(" "));
    return {
      add: (...added) => write([...names(), ...added]),
      remove: (...removed) => write(names().filter((name) => !removed.includes(name))),
      contains: (name) => names().includes(name),
      toggle(name, force) {
        const on = force === undefined ? !names().includes(name) : Boolean(force);
        if (on) {
          write([...names(), name]);
        } else {
          write(names().filter((value) => value !== name));
        }
        return on;
      },
    };
  }

  get type() {
    return this.getAttribute("type") ?? "";
  }

  set type(value) {
    this.setAttribute("type", value);
  }

  get tabIndex() {
    const value = this.getAttribute("tabindex");
    if (value !== null) {
      return Number(value);
    }
    return ["a", "button", "input", "select", "textarea"].includes(this.localName) ? 0 : -1;
  }

  set tabIndex(value) {
    this.setAttribute("tabindex", value);
  }

  setAttribute(name, value) {
    this.attributes.set(name, String(value));
  }

  getAttribute(name) {
    return this.attributes.get(name) ?? null;
  }

  hasAttribute(name) {
    return this.attributes.has(name);
  }

  removeAttribute(name) {
    this.attributes.delete(name);
  }

  toggleAttribute(name, force) {
    const on = force === undefined ? !this.hasAttribute(name) : Boolean(force);
    if (on) {
      this.setAttribute(name, "");
    } else {
      this.removeAttribute(name);
    }
    return on;
  }

  matches(selector) {
    return parseSelectorList(selector).some((group) => matchesGroup(this, group, null));
  }

  closest(selector) {
    for (let node = this; node instanceof FakeElement; node = node.parentNode) {
      if (node.matches(selector)) {
        return node;
      }
    }
    return null;
  }

  getBoundingClientRect() {
    const rect = this.rect ?? { left: 0, top: 0, width: 0, height: 0 };
    return {
      ...rect,
      right: rect.left + rect.width,
      bottom: rect.top + rect.height,
    };
  }

  /** Move focus here: `blur` and `focusout` on the element losing it, then `focus` and
   * `focusin` here. `blur` and `focus` do not bubble, but a capture listener on the
   * window or the document still hears them. */
  focus() {
    const document = this.ownerDocument;
    const previous = document.activeElement;
    if (previous === this) {
      return;
    }
    document.activeElement = this;
    if (previous && previous !== document.body) {
      previous.dispatchEvent({
        bubbles: false,
        relatedTarget: this,
        target: previous,
        type: "blur",
      });
      previous.dispatchEvent({ relatedTarget: this, target: previous, type: "focusout" });
    }
    this.dispatchEvent({ bubbles: false, relatedTarget: previous, target: this, type: "focus" });
    this.dispatchEvent({ relatedTarget: previous, target: this, type: "focusin" });
  }

  blur() {
    const document = this.ownerDocument;
    if (document.activeElement === this) {
      document.activeElement = document.body;
      this.dispatchEvent({ bubbles: false, relatedTarget: null, target: this, type: "blur" });
      this.dispatchEvent({ relatedTarget: null, target: this, type: "focusout" });
    }
  }

  click() {
    this.dispatchEvent({ type: "click", target: this });
  }

  scrollIntoView() {}

  select() {}

  /** Replace the children with the elements and text `markup` describes. */
  set innerHTML(markup) {
    this.replaceChildren(...parseMarkup(this.ownerDocument, String(markup)));
  }
}

for (const name of REFLECTED_BOOLEANS) {
  Object.defineProperty(FakeElement.prototype, name, {
    get() {
      return this.hasAttribute(name);
    },
    set(value) {
      this.toggleAttribute(name, Boolean(value));
    },
  });
}

function toKebab(name) {
  return name.replace(/[A-Z]/g, (letter) => `-${letter.toLowerCase()}`);
}

// ── Markup ────────────────────────────────────────────────────────

const VOID_ELEMENTS = new Set(["br", "hr", "img", "input", "link", "meta", "wbr"]);
const ENTITIES = { amp: "&", apos: "'", gt: ">", lt: "<", quot: '"' };

/** Text with the named and numeric character references a string renderer writes. */
function decodeEntities(text) {
  return text.replace(/&(#x[\da-f]+|#\d+|[a-z]+);/gi, (reference, name) => {
    if (name[0] === "#") {
      const hex = name[1].toLowerCase() === "x";
      return String.fromCodePoint(Number.parseInt(name.slice(hex ? 2 : 1), hex ? 16 : 10));
    }
    return ENTITIES[name.toLowerCase()] ?? reference;
  });
}

/**
 * The nodes `markup` describes: start and end tags, attributes quoted either way or bare,
 * void elements, comments (dropped), and text. Not a general HTML parser: an end tag
 * that does not close an open element, or an element left open, is an error, so markup a
 * renderer gets wrong fails loudly rather than parsing into something else.
 */
function parseMarkup(document, markup) {
  const root = document.createElement("template");
  const open = [root];
  const token =
    /<!--[\s\S]*?-->|<\/([a-zA-Z][\w-]*)\s*>|<([a-zA-Z][\w-]*)((?:\s+[^\s=>/"']+(?:\s*=\s*(?:"[^"]*"|'[^']*'|[^\s"'=<>`]+))?)*)\s*(\/?)>|([^<]+)/g;
  const attribute = /([^\s=>/"']+)(?:\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s"'=<>`]+)))?/g;
  let consumed = 0;
  for (const match of markup.matchAll(token)) {
    if (match.index !== consumed) {
      throw new Error(`Unparsed markup at ${consumed}: ${markup.slice(consumed, consumed + 40)}`);
    }
    consumed = match.index + match[0].length;
    const [whole, endTag, startTag, attributes, selfClosing, text] = match;
    const parent = open.at(-1);
    if (text !== undefined) {
      parent.append(document.createTextNode(decodeEntities(text)));
    } else if (endTag !== undefined) {
      if (open.length < 2 || parent.localName !== endTag.toLowerCase()) {
        throw new Error(`Unexpected </${endTag}> inside <${parent.localName}>`);
      }
      open.pop();
    } else if (startTag !== undefined) {
      const node = document.createElement(startTag);
      for (const [, name, double, single, bare] of (attributes ?? "").matchAll(attribute)) {
        node.setAttribute(name.toLowerCase(), decodeEntities(double ?? single ?? bare ?? ""));
      }
      parent.append(node);
      if (!selfClosing && !VOID_ELEMENTS.has(node.localName)) {
        open.push(node);
      }
    } else if (!whole.startsWith("<!--")) {
      throw new Error(`Unparsed markup: ${whole}`);
    }
  }
  if (consumed !== markup.length || open.length !== 1) {
    throw new Error(`Unclosed or unparsed markup: <${open.at(-1).localName}>`);
  }
  return [...root.childNodes];
}

/** A document's window: on every event's path above the document, and its own target
 * for what happens to the window itself, such as `blur` when the page loses focus. */
class FakeWindow extends FakeEventTarget {
  constructor(document) {
    super();
    this.document = document;
  }

  getComputedStyle(element) {
    return {
      get display() {
        return element.hidden ? "none" : element.style.display || "block";
      },
      get visibility() {
        for (let node = element; node instanceof FakeElement; node = node.parentNode) {
          if (node.style.visibility) {
            return node.style.visibility;
          }
        }
        return "visible";
      },
      direction: "ltr",
    };
  }

  /** The page losing focus to another window: the focused element hears `blur` and
   * `focusout` and stays the active element, then the window itself hears `blur`. */
  loseFocus() {
    const active = this.document.activeElement;
    if (active && active !== this.document.body) {
      active.dispatchEvent({ bubbles: false, relatedTarget: null, target: active, type: "blur" });
      active.dispatchEvent({ relatedTarget: null, target: active, type: "focusout" });
    }
    this.dispatchEvent({ bubbles: false, target: this, type: "blur" });
  }

  /** The page getting focus back: the window hears `focus`, then the element that kept
   * focus hears `focus` and `focusin` again. */
  regainFocus() {
    this.dispatchEvent({ bubbles: false, target: this, type: "focus" });
    const active = this.document.activeElement;
    if (active && active !== this.document.body) {
      active.dispatchEvent({ bubbles: false, relatedTarget: null, target: active, type: "focus" });
      active.dispatchEvent({ relatedTarget: null, target: active, type: "focusin" });
    }
  }
}

class FakeDocument extends FakeNode {
  constructor() {
    super(null, "#document");
    this.ownerDocument = this;
    this.visibilityState = "visible";
    this.defaultView = new FakeWindow(this);
    this.documentElement = this.createElement("html");
    this.head = this.createElement("head");
    this.body = this.createElement("body");
    this.documentElement.append(this.head, this.body);
    this.append(this.documentElement);
    this.activeElement = this.body;
  }

  get isConnected() {
    return true;
  }

  createElement(tagName) {
    return new FakeElement(this, tagName);
  }

  createTextNode(data) {
    return new FakeText(this, data);
  }

  getElementById(id) {
    return this.querySelector(`#${id}`);
  }

  /** Every node in document order, for compareDocumentPosition. */
  treeOrder() {
    const order = [];
    const visit = (node) => {
      order.push(node);
      for (const child of node.childNodes) {
        visit(child);
      }
    };
    visit(this);
    return order;
  }
}

// ── Selectors ─────────────────────────────────────────────────────

/** Split on a separator outside brackets, parentheses, and quotes. */
function splitTopLevel(text, separator) {
  const parts = [];
  let depth = 0;
  let quote = null;
  let current = "";
  for (const character of text) {
    if (quote) {
      quote = character === quote ? null : quote;
    } else if (character === '"' || character === "'") {
      quote = character;
    } else if (character === "[" || character === "(") {
      depth += 1;
    } else if (character === "]" || character === ")") {
      depth -= 1;
    } else if (depth === 0 && separator.test(character)) {
      parts.push(current);
      current = "";
      continue;
    }
    current += character;
  }
  parts.push(current);
  return parts;
}

/** A selector list: each group is compounds joined by " " or ">", rightmost last. */
function parseSelectorList(selector) {
  return splitTopLevel(selector, /,/).map((group) => {
    const tokens = splitTopLevel(group.replace(/\s*>\s*/g, " > ").trim(), /\s/).filter(Boolean);
    const steps = [];
    let combinator = " ";
    for (const token of tokens) {
      if (token === ">") {
        combinator = ">";
        continue;
      }
      steps.push({ combinator, compound: parseCompound(token) });
      combinator = " ";
    }
    return steps;
  });
}

function parseCompound(token) {
  const tests = [];
  const pattern =
    /([a-zA-Z][\w-]*)|#([\w-]+)|\.([\w-]+)|\[([^\]]+)\]|:not\(((?:[^()]|\([^()]*\))*)\)|(\*)/g;
  for (const match of token.matchAll(pattern)) {
    const [, tag, id, className, attribute, negated] = match;
    if (tag) {
      tests.push((element) => element.localName === tag.toLowerCase());
    } else if (id) {
      tests.push((element) => element.id === id);
    } else if (className) {
      tests.push((element) => element.classList.contains(className));
    } else if (attribute) {
      const parsed = /^([\w-]+)(?:([~^$*|]?=)(?:"([^"]*)"|'([^']*)'|([^\]]*)))?$/.exec(
        attribute.trim(),
      );
      if (!parsed) {
        throw new Error(`Unsupported attribute selector: [${attribute}]`);
      }
      const [, name, operator, double, single, bare] = parsed;
      const expected = double ?? single ?? bare;
      tests.push((element) => {
        const value = element.getAttribute(name);
        if (value === null) {
          return false;
        }
        if (!operator) {
          return true;
        }
        if (operator === "=") {
          return value === expected;
        }
        if (operator === "~=") {
          return value.split(/\s+/).includes(expected);
        }
        if (operator === "^=") {
          return value.startsWith(expected);
        }
        if (operator === "*=") {
          return value.includes(expected);
        }
        return value.endsWith(expected);
      });
    } else if (negated !== undefined) {
      const inner = parseSelectorList(negated);
      tests.push((element) => !inner.some((group) => matchesGroup(element, group, null)));
    }
  }
  return (element) => tests.every((test) => test(element));
}

/** Whether `element` matches one selector group, staying inside `scope` when given. */
function matchesGroup(element, steps, scope) {
  const match = (candidate, index) => {
    if (!(candidate instanceof FakeElement) || !steps[index].compound(candidate)) {
      return false;
    }
    if (index === 0) {
      return true;
    }
    const inside = (node) => node instanceof FakeElement && (!scope || scope.contains(node));
    if (steps[index].combinator === ">") {
      return inside(candidate.parentNode) && match(candidate.parentNode, index - 1);
    }
    for (let node = candidate.parentNode; inside(node); node = node.parentNode) {
      if (match(node, index - 1)) {
        return true;
      }
    }
    return false;
  };
  return match(element, steps.length - 1);
}

/** A keyboard event the stand-in can dispatch, with what a browser would report. */
function keyEvent(type, key, init = {}) {
  return {
    altKey: false,
    code: "",
    ctrlKey: false,
    defaultPrevented: false,
    isComposing: false,
    key,
    metaKey: false,
    repeat: false,
    shiftKey: key === "Shift" && type === "keydown",
    type,
    ...init,
  };
}

/** Build an element with attributes and children in one call. */
function element(document, tagName, attributes = {}, ...children) {
  const node = document.createElement(tagName);
  for (const [name, value] of Object.entries(attributes)) {
    if (value === true) {
      node.setAttribute(name, "");
    } else if (value !== false && value !== null && value !== undefined) {
      node.setAttribute(name, value);
    }
  }
  node.append(...children);
  return node;
}

module.exports = { FakeDocument, FakeElement, FakeWindow, element, keyEvent };

// Browserless session: a commit's body shown as Markdown on its page.
//
// static/git-panel.js and static/inert-html.js load whole, as the shell loads them, with
// the modules the panel reads at load (formatters.js, git-graph.js, git-history-window.js).
// The commit page asks `GET /api/git/commit-markdown/{revision}` for a body and sets the
// answer as a pull request's page sets a description: through the inert allowlist into a
// KPress article, then the trailers as written (`placeCommitBody`, `fetchCommitBody`). The
// answers are the route's: the rendered one is what cli-api-git-commit-markdown.tryscript.md
// pins for its fixture commit, parsed here by a small reader of the hardened markup the
// route sends (tags, quoted attributes, text, and the five entities it writes), since a
// browser's template parse is not available to Node. The SDK's asset loads are stand-ins
// that record what was asked and can fail. A hover's preparation (`prepareRevision`) asks
// for a body once its detail comes, and the reader's open joins that request unless it
// ended in an answer the panel does not keep.
//
// Each step prints the requests it made, what the body's box holds, and what the panel
// keeps. Exits 1 on a failed invariant.

const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const repoRoot = path.resolve(__dirname, "../..");
const staticDir = path.join(repoRoot, "src/metabrowser/static");

function assert(condition, message) {
  if (!condition) {
    throw new Error(message);
  }
}

// ── A stand-in DOM ────────────────────────────────────────────

class StandInNode {}

class Text extends StandInNode {
  constructor(value) {
    super();
    this.nodeType = 3;
    this.nodeValue = String(value);
    this.parentNode = null;
  }
  get textContent() {
    return this.nodeValue;
  }
  remove() {
    detach(this);
  }
}

function detach(node) {
  const parent = node.parentNode;
  if (parent) {
    parent.childNodes.splice(parent.childNodes.indexOf(node), 1);
    node.parentNode = null;
  }
}

class HTMLElement extends StandInNode {
  constructor(tag, ownerDocument) {
    super();
    this.nodeType = 1;
    this.tagName = tag.toUpperCase();
    this.ownerDocument = ownerDocument;
    this.childNodes = [];
    this.parentNode = null;
    this.attributes = new Map();
    this.className = "";
    this.dataset = {};
  }
  get parentElement() {
    return this.parentNode instanceof HTMLElement ? this.parentNode : null;
  }
  get classList() {
    const names = () => this.className.split(/\s+/).filter(Boolean);
    return {
      add: (...added) => {
        this.className = [...new Set([...names(), ...added])].join(" ");
      },
      remove: (...removed) => {
        this.className = names()
          .filter((name) => !removed.includes(name))
          .join(" ");
      },
      contains: (name) => names().includes(name),
    };
  }
  setAttribute(name, value) {
    if (name === "class") {
      this.className = String(value);
    } else {
      this.attributes.set(name, String(value));
    }
  }
  getAttribute(name) {
    return name === "class" ? this.className || null : (this.attributes.get(name) ?? null);
  }
  removeAttribute(name) {
    this.attributes.delete(name);
  }
  // What static/repository-links.js gives a link it makes open in place.
  addEventListener(type, listener) {
    this.listeners ??= [];
    this.listeners.push({ type, listener });
  }
  // A primary click, plain or with *modifiers*: whether a listener kept the browser from
  // following the link.
  click(modifiers = {}) {
    const event = {
      altKey: false,
      button: 0,
      ctrlKey: false,
      defaultPrevented: false,
      metaKey: false,
      shiftKey: false,
      ...modifiers,
      preventDefault() {
        this.defaultPrevented = true;
      },
    };
    for (const { type, listener } of this.listeners ?? []) {
      if (type === "click") {
        listener(event);
      }
    }
    return event.defaultPrevented;
  }
  append(...nodes) {
    for (const given of nodes) {
      const node = typeof given === "string" ? new Text(given) : given;
      detach(node);
      node.parentNode = this;
      this.childNodes.push(node);
    }
  }
  replaceWith(...nodes) {
    const parent = this.parentNode;
    assert(parent, "replaceWith on a detached element");
    const at = parent.childNodes.indexOf(this);
    detach(this);
    for (const [offset, node] of nodes.entries()) {
      detach(node);
      node.parentNode = parent;
      parent.childNodes.splice(at + offset, 0, node);
    }
  }
  remove() {
    detach(this);
  }
  get textContent() {
    return this.childNodes.map((node) => node.textContent).join("");
  }
  set textContent(value) {
    for (const node of [...this.childNodes]) {
      detach(node);
    }
    this.append(new Text(value));
  }
  // Only the selectors the code under test asks: `.a`, `tag`, and `a[href]`.
  matches(selector) {
    if (selector.startsWith(".")) {
      return this.classList.contains(selector.slice(1));
    }
    const attribute = selector.match(/^([a-z]+)\[([a-z]+)\]$/);
    if (attribute) {
      return this.tagName === attribute[1].toUpperCase() && this.attributes.has(attribute[2]);
    }
    return this.tagName === selector.toUpperCase();
  }
  querySelectorAll(selector) {
    const found = [];
    const walk = (node) => {
      for (const child of node.childNodes) {
        if (child instanceof HTMLElement) {
          if (child.matches(selector)) {
            found.push(child);
          }
          walk(child);
        }
      }
    };
    walk(this);
    return found;
  }
  querySelector(selector) {
    return this.querySelectorAll(selector)[0] ?? null;
  }
}

const ENTITIES = { amp: "&", lt: "<", gt: ">", quot: '"', "#39": "'" };
const decode = (text) => text.replace(/&(amp|lt|gt|quot|#39);/g, (_all, name) => ENTITIES[name]);
const VOID = new Set(["br", "hr", "img"]);

// The hardened markup the route sends, read into stand-in nodes, as a template would hold it.
function parseMarkup(html, doc) {
  const root = new HTMLElement("template-content", doc);
  const stack = [root];
  const token = /<\/([a-z0-9]+)>|<([a-z0-9]+)((?:\s+[a-z-]+="[^"]*")*)\s*>|([^<]+)/g;
  for (const match of html.matchAll(token)) {
    const [, closing, opening, attributes, text] = match;
    const top = stack[stack.length - 1];
    if (closing) {
      assert(top.tagName === closing.toUpperCase(), `unbalanced </${closing}>`);
      stack.pop();
    } else if (opening) {
      const element = new HTMLElement(opening, doc);
      for (const [, name, value] of attributes.matchAll(/([a-z-]+)="([^"]*)"/g)) {
        element.setAttribute(name, decode(value));
      }
      top.append(element);
      if (!VOID.has(opening)) {
        stack.push(element);
      }
    } else {
      top.append(new Text(decode(text)));
    }
  }
  assert(stack.length === 1, "unclosed markup");
  return root;
}

class StandInDocument {
  createElement(tag) {
    const element = new HTMLElement(tag, this);
    if (tag === "template") {
      let content = new HTMLElement("template-content", this);
      Object.defineProperty(element, "content", { get: () => content });
      Object.defineProperty(element, "innerHTML", {
        set: (html) => {
          content = parseMarkup(String(html), this);
        },
      });
    }
    return element;
  }
  createTextNode(value) {
    return new Text(value);
  }
  get implementation() {
    return { createHTMLDocument: () => new StandInDocument() };
  }
}

// What a box shows: each element's tag and classes, its kept attributes, and its text.
function shape(node) {
  if (!(node instanceof HTMLElement)) {
    return node.nodeValue;
  }
  const name =
    node.tagName.toLowerCase() +
    node.className
      .split(/\s+/)
      .filter(Boolean)
      .map((c) => `.${c}`)
      .join("");
  const attributes = [
    ...[...node.attributes.entries()].map(([key, value]) => `${key}=${value}`),
    ...Object.entries(node.dataset).map(
      ([key, value]) => `data-${key.replace(/[A-Z]/g, (c) => `-${c.toLowerCase()}`)}=${value}`,
    ),
  ];
  const label = attributes.length ? `${name}[${attributes.join(" ")}]` : name;
  const children = node.childNodes
    .filter((child) => child instanceof HTMLElement || child.nodeValue.trim() !== "")
    .map(shape);
  return children.length === 1 && typeof children[0] === "string"
    ? { [label]: children[0] }
    : { [label]: children };
}

// ── The production modules ────────────────────────────────────

const document = new StandInDocument();
const requests = [];
const assetLoads = [];
const options = { inertFails: false, stylesFail: false };
// A route's answer, or its answers in turn, the last repeated.
/** @type {Map<string, {status: number, body: unknown} | Error | Array<{status: number, body: unknown}>>} */
const answers = new Map();
/** @type {Map<string, Promise<void>>} */
const held = new Map();

// What the panel warns of, kept for the transcript rather than written to standard error.
const warnings = [];
const sandbox = {
  console: { ...console, warn: (message) => warnings.push(String(message)) },
  document,
  HTMLElement,
  URL,
  URLSearchParams,
  AbortController,
  Promise,
  Map,
  Set,
  WeakMap,
  setTimeout,
  clearTimeout,
  fetch: async (url) => {
    const route = String(url);
    requests.push(route);
    await held.get(route);
    const listed = answers.get(route);
    const answer = Array.isArray(listed)
      ? listed.length > 1
        ? listed.shift()
        : listed[0]
      : listed;
    if (answer instanceof Error) {
      throw answer;
    }
    assert(answer, `no answer for ${route}`);
    return {
      ok: answer.status >= 200 && answer.status < 300,
      status: answer.status,
      json: async () => answer.body,
    };
  },
};
sandbox.window = sandbox;
sandbox.metabrowser = {
  ensureAsset: async (name) => {
    assetLoads.push(name);
    if (options.inertFails) {
      throw new Error("the allowlist did not load");
    }
  },
  loadKpressAssets: async (manifest) => {
    assetLoads.push(`kpress:${manifest.assets.length}`);
    if (options.stylesFail) {
      throw new Error("the stylesheets did not load");
    }
  },
  // The SDK marks an outside destination only, and an in-app link not at all.
  decorateExternalLink: (anchor) => {
    if (/^https?:\/\//.test(anchor.getAttribute("href") ?? "")) {
      anchor.dataset.decorated = "external";
    }
    return anchor;
  },
  // What a preparation asks of the SDK for the diff beside the body.
  ensureKindAssets: async () => {},
  // What renderCommitSummary reads of the SDK for the rest of the summary.
  delegateOwnerAttribute: () => "",
  actorIdentityHtml: (name) => `<span class="actor-identity">${name}</span>`,
  // The size line, the SDK's, which this session does not read.
  changeSizeLine: () => ({ parts: [], sizeParts: [], text: "", label: "", tooltip: null }),
  changeSizeLineHtml: () => '<span class="change-size-line"></span>',
  icons: { copy: "" },
};
vm.createContext(sandbox);
for (const file of [
  "formatters.js",
  "git-graph.js",
  "git-history-window.js",
  "inert-html.js",
  // What a body's links open, which the SDK's loader answers on a page with a repository
  // identity (`loadRepositoryLinks` below); the stand-in loads nothing, so it is here
  // from the start.
  "git-path.js",
  "repository-links.js",
  "git-panel.js",
]) {
  const filename = path.join(staticDir, file);
  vm.runInContext(fs.readFileSync(filename, "utf8"), sandbox, { filename });
}
const internals = sandbox.MetabrowserGitPanel._internals;

// ── Commits and answers ───────────────────────────────────────

const RENDERED = "a".repeat(40);
const TRAILERS_ONLY = "b".repeat(40);
const TOO_LARGE = "c".repeat(40);
const DEADLINE = "d".repeat(40);
const OFFLINE = "e".repeat(40);
const NO_BODY = "f".repeat(40);
const STYLES = "1".repeat(40);
const NO_ALLOWLIST = "2".repeat(40);
const SHARED = "3".repeat(40);
const PREFETCHED = "4".repeat(40);
const BUSY = "5".repeat(40);
const ABANDONED = "6".repeat(40);
const LINKED = "7".repeat(40);

const ASSETS = {
  schema_version: "kpress-asset-manifest-v2",
  assets: [{ id: "css/document.css", entry_point: true, loading: "stylesheet" }],
};
// The fixture commit's answer in cli-api-git-commit-markdown.tryscript.md.
const FIXTURE_HTML =
  '\n<div><div><p>The app counted to one. This change wraps its prose at seventy-two\ncolumns, as a commit body does, and the page reflows it.</p>\n<ul>\n<li>a bullet that wraps onto\na second line</li>\n<li>another, which fixes #12; see https://example.com/issue</li>\n</ul>\n<ul>\n<li>a star bullet with <b>bold</b> </li>\n</ul>\n<p>An example:</p>\n<pre><code>indented code stays code\n</code></pre>\n<p>A <a href="https://example.com/doc" target="_blank" rel="noopener noreferrer">link</a> and a <a>relative one</a>.</p></div></div>';
const FIXTURE_TRAILERS =
  "Signed-off-by: Test <test@example.com>\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>";
const FIXTURE_BODY = `The app counted to one. ...\n\n${FIXTURE_TRAILERS}`;

const rendered = (revision, html, trailers) => ({
  status: 200,
  body: {
    is_repo: true,
    revision,
    html,
    trailers,
    link_base: "about:blank",
    assets: ASSETS,
  },
});
const route = (revision) => `/api/git/commit-markdown/${revision}`;
answers.set(route(RENDERED), rendered(RENDERED, FIXTURE_HTML, FIXTURE_TRAILERS));
answers.set(route(STYLES), rendered(STYLES, "\n<div><div><p>styled</p></div></div>", ""));
answers.set(route(NO_ALLOWLIST), rendered(NO_ALLOWLIST, "\n<div><div><p>x</p></div></div>", ""));
answers.set(route(SHARED), rendered(SHARED, "\n<div><div><p>shared</p></div></div>", ""));
answers.set(
  route(TRAILERS_ONLY),
  rendered(TRAILERS_ONLY, "", "Signed-off-by: Test <test@example.com>"),
);
answers.set(route(TOO_LARGE), {
  status: 422,
  body: {
    error: "the body is 70000 bytes, more than the 65536 rendered as Markdown",
    code: "body_too_large",
    max_bytes: 65536,
    revision: TOO_LARGE,
  },
});
answers.set(route(DEADLINE), {
  status: 422,
  body: {
    code: "render_deadline",
    error: "Rendering took longer than 5 seconds, so it was stopped",
    deadline_ms: 5000,
    remembered: false,
    revision: DEADLINE,
  },
});
answers.set(route(OFFLINE), new TypeError("Failed to fetch"));
// A body with links into the served repository, `acme/widgets`, as the route sends them: a
// pull request's page, a commit's, the list of pull requests, a file on the served branch,
// a relative reference, which the route's `about:blank` base leaves with no address, and
// another site.
const LINKED_COMMIT = "9".repeat(40);
answers.set(
  route(LINKED),
  rendered(
    LINKED,
    `\n<div><div><p>See <a href="https://github.com/acme/widgets/pull/12" target="_blank" rel="noopener noreferrer">the pull request</a>, <a href="https://github.com/acme/widgets/commit/${LINKED_COMMIT}" target="_blank" rel="noopener noreferrer">a commit</a>, <a href="https://github.com/acme/widgets/pulls" target="_blank" rel="noopener noreferrer">the pull requests</a>, <a href="https://github.com/acme/widgets/blob/main/docs/guide.md" target="_blank" rel="noopener noreferrer">the guide</a>, <a>a relative one</a>, and <a href="https://example.com/doc" target="_blank" rel="noopener noreferrer">another site</a>.</p></div></div>`,
    "",
  ),
);
answers.set(
  route(PREFETCHED),
  rendered(PREFETCHED, "\n<div><div><p>prefetched</p></div></div>", ""),
);
// The renderer is busy for the hover's prefetch, and renders for the reader's request.
answers.set(route(BUSY), [
  {
    status: 503,
    body: {
      code: "renderer_busy",
      error: "The renderer is busy with other texts",
      revision: BUSY,
    },
  },
  rendered(BUSY, "\n<div><div><p>rendered on the reader's request</p></div></div>", ""),
]);

const detail = (revision, body) => ({
  is_repo: true,
  commit: {
    id: revision,
    short_id: revision.slice(0, 7),
    parent_ids: [],
    author: { name: "Author", email: "a@example.invalid" },
    authored_at: 1700000000,
    committed_at: 1700000000,
    subject: "feat: teach the app to count",
  },
  body,
  stats: { files_changed: 0, additions: 0, deletions: 0 },
  files: [],
  files_truncated: false,
});

// A commit page's summary as renderCommitSummary writes it: the body's box and the message
// as written in it.
function summary(revision, body) {
  const root = new HTMLElement("section", document);
  const html = internals.renderCommitSummary(detail(revision, body));
  if (!body) {
    assert(!html.includes("git-commit-body"), "a commit with no body has no body's box");
    return root;
  }
  const box = new HTMLElement("div", document);
  box.className = "git-commit-body page-card chrome-prose";
  const plain = new HTMLElement("div", document);
  plain.className = "git-commit-body-plain";
  plain.textContent = body;
  box.append(plain);
  root.append(box);
  assert(
    html.includes(
      '<div class="git-commit-body page-card chrome-prose"><div class="git-commit-body-plain">',
    ),
    "renderCommitSummary writes the body's box and the message as written in it",
  );
  return root;
}

const tick = () => new Promise((resolve) => setTimeout(resolve, 0));
for (const revision of [PREFETCHED, BUSY, ABANDONED]) {
  answers.set(`/api/git/commit/${revision}`, { status: 200, body: detail(revision, "body") });
}
const bodyRequests = () => requests.filter((request) => request.includes("/commit-markdown/"));
/** Turns of the event loop until *done*, at most 50. */
async function settle(done) {
  for (let turn = 0; turn < 50 && !done(); turn += 1) {
    await tick();
  }
}

/**
 * A hover prepares *revision* (`prepareRevision`), and then the reader opens it: the page
 * places its body (`placeCommitBody`) while the hover's request for it is on its way.
 */
async function hoverThenOpen(revision) {
  requests.length = 0;
  let release = () => {};
  held.set(route(revision), new Promise((resolve) => (release = resolve)));
  internals.prepareRevision(revision, true);
  await settle(() => bodyRequests().length > 0);
  const hovered = bodyRequests().length;
  const root = summary(revision, "body");
  const placed = internals.placeCommitBody(root, detail(revision, "body"));
  release();
  await placed;
  await tick();
  held.delete(route(revision));
  internals.cancelSpeculativePreparation();
  return {
    hovered,
    requests: [...requests],
    box: shape(root.querySelector(".git-commit-body")),
    kept: internals.keptCommitBodies().includes(revision),
  };
}

async function step(label, revision, body, before = null) {
  requests.length = 0;
  assetLoads.length = 0;
  warnings.length = 0;
  const root = summary(revision, body);
  const placed = internals.placeCommitBody(root, detail(revision, body));
  const box = root.querySelector(".git-commit-body");
  const waiting = box ? box.querySelector(".git-commit-body-plain-pending") !== null : false;
  await before?.();
  await placed;
  await tick();
  return {
    [label]: {
      waiting,
      requests: [...requests],
      assets: [...assetLoads],
      box: box ? shape(box) : null,
      warnings: [...warnings],
      kept: internals.keptCommitBodies().map((id) => id.slice(0, 7)),
    },
  };
}

(async () => {
  const transcript = {};
  // KPress's stylesheets fail to load for the first body: it stays as written, with no
  // notice, and is not kept, so the next body asks for them again.
  options.stylesFail = true;
  Object.assign(
    transcript,
    await step("stylesheets that fail leave the body as written", STYLES, "styled"),
  );
  options.stylesFail = false;
  assert(
    JSON.stringify(transcript["stylesheets that fail leave the body as written"].box) ===
      JSON.stringify({
        "div.git-commit-body.page-card.chrome-prose": [{ "div.git-commit-body-plain": "styled" }],
      }),
    "a body whose stylesheets did not load shows as written",
  );

  Object.assign(transcript, await step("a body opens as Markdown", RENDERED, FIXTURE_BODY));
  const first = transcript["a body opens as Markdown"];
  assert(first.waiting, "the message as written is held out of sight until its Markdown comes");
  assert(first.assets.includes("kpress:1"), "stylesheets that failed are asked for again");
  const shown = JSON.stringify(first.box);
  assert(!shown.includes("git-commit-body-plain"), "the plain text is gone");
  assert(shown.includes("pre.kpress-code"), "code is KPress's code block");
  assert(
    shown.includes(
      "a[href=https://example.com/doc target=_blank rel=noopener noreferrer data-decorated=external]",
    ),
    "an absolute link keeps its address and is decorated as an outside link",
  );
  assert(shown.includes('{"a":"relative one"}'), "a relative link keeps only its text");
  assert(
    shown.includes(`"div.git-commit-trailers":${JSON.stringify(FIXTURE_TRAILERS)}`),
    "trailers",
  );

  Object.assign(transcript, await step("a kept body opens at once", RENDERED, FIXTURE_BODY));
  const again = transcript["a kept body opens at once"];
  assert(!again.waiting && again.requests.length === 0, "a kept render is placed with no request");
  assert(JSON.stringify(again.box) === shown, "and is the same Markdown");

  // Two callers, as a hover's preparation and the page, share one request.
  requests.length = 0;
  let release = () => {};
  held.set(route(SHARED), new Promise((resolve) => (release = resolve)));
  const one = internals.fetchCommitBody(SHARED);
  const two = internals.fetchCommitBody(SHARED);
  release();
  const [left, right] = await Promise.all([one, two]);
  held.delete(route(SHARED));
  transcript["two callers share one request"] = {
    requests: [...requests],
    same: left === right,
    kind: left.kind,
  };
  assert(requests.length === 1 && left === right, "one request answers both callers");

  // A hover's preparation asks for the body once its detail says there is one, and the
  // reader's open joins that request rather than making its own.
  transcript["a hover prefetches, and the open joins it"] = await hoverThenOpen(PREFETCHED);
  {
    const joined = transcript["a hover prefetches, and the open joins it"];
    assert(joined.hovered === 1, "the hover asks for the body once");
    assert(
      bodyRequests().length === 1 && joined.kept,
      "the open joins the hover's request, and its render is kept",
    );
    assert(JSON.stringify(joined.box).includes("prefetched"), "the body opens as Markdown");
  }

  // The hover's request is refused by a busy renderer while the reader's open waits on it:
  // the refusal answered the hover, so the open asks again, and shows that answer.
  transcript["a hover's refusal is asked again by the open"] = await hoverThenOpen(BUSY);
  {
    const busy = transcript["a hover's refusal is asked again by the open"];
    assert(busy.hovered === 1, "the hover asks once");
    assert(bodyRequests().length === 2, "the open asks again after the hover's refusal");
    const box = JSON.stringify(busy.box);
    assert(box.includes("rendered on the reader") && !box.includes("notice"), "with no notice");
  }

  // A preparation given up before its detail comes asks for no body.
  requests.length = 0;
  {
    let release = () => {};
    const detailRoute = `/api/git/commit/${ABANDONED}`;
    held.set(detailRoute, new Promise((resolve) => (release = resolve)));
    internals.prepareRevision(ABANDONED, true);
    await settle(() => requests.includes(detailRoute));
    internals.cancelSpeculativePreparation();
    release();
    await settle(() => false);
    held.delete(detailRoute);
    transcript["a preparation given up asks for no body"] = { requests: [...requests] };
    assert(requests.includes(detailRoute) && bodyRequests().length === 0, "no body is asked for");
  }

  Object.assign(
    transcript,
    await step("a body of only trailers", TRAILERS_ONLY, "Signed-off-by: Test <test@example.com>"),
  );
  assert(
    !JSON.stringify(transcript["a body of only trailers"].box).includes("kpress"),
    "a body of only trailers has no article",
  );

  Object.assign(transcript, await step("a body too long to render", TOO_LARGE, "x".repeat(80)));
  Object.assign(transcript, await step("a body too long, again", TOO_LARGE, "x".repeat(80)));
  assert(
    transcript["a body too long, again"].requests.length === 0,
    "a body too long to render is not asked for again",
  );

  Object.assign(transcript, await step("a render past its deadline", DEADLINE, "slow"));
  Object.assign(transcript, await step("past its deadline, again", DEADLINE, "slow"));
  assert(
    transcript["past its deadline, again"].requests.length === 1,
    "a refusal the renderer may not repeat is asked again",
  );

  Object.assign(transcript, await step("a request that never arrives", OFFLINE, "offline"));
  assert(
    !JSON.stringify(transcript["a request that never arrives"].box).includes("notice"),
    "a request that never arrived owes no notice",
  );

  options.inertFails = true;
  Object.assign(transcript, await step("an allowlist that cannot load", NO_ALLOWLIST, "x"));
  options.inertFails = false;

  // On a page with the served repository's identity, a body's links into it open its pages
  // here (static/repository-links.js, run whole): a same-repository pull request's page, a
  // commit's, and the list are their routes, which a plain click has the shell open in
  // place (`navigation.openRoute`), and a file on the served branch its `/view/` address,
  // which a plain click opens through the navigation; a modified click on any of them is
  // the browser's. A relative reference stays text, as on github.com, where a commit's
  // message is not Markdown, and another site stays an outside link.
  const navigated = [];
  sandbox.metabrowser.repository = {
    host: "github.com",
    owner: "acme",
    name: "widgets",
    branch: "main",
    revision: "8".repeat(40),
    served_prefix: "",
  };
  sandbox.metabrowser.sourceKind = () => "filesystem";
  // As static/plugin-sdk-views.js answers it on a repository's page: the resolver, which
  // the transcript lists among what the panel asked for.
  sandbox.metabrowser.loadRepositoryLinks = async () => {
    assetLoads.push("repository-links");
    return sandbox.MetabrowserRepositoryLinks;
  };
  sandbox.metabrowser.navigation = {
    href: (target) => `/view/${target.path}`,
    open: async (target) => {
      navigated.push(`/view/${target.path}`);
    },
    openRoute(href) {
      navigated.push(`the shell opens ${href}`);
      return true;
    },
  };
  // The link cards (static/link-previews.js), which the bundle loads after the resolver: a
  // recording stand-in, which the panel reaches through the resolver's runtime. A card is
  // its link's, by identity, with its root and target; a disposal forgets its root's.
  const cards = new Map();
  sandbox.MetabrowserLinkPreviews = {
    register(root, anchor, target) {
      cards.set(anchor, { root, target });
      return true;
    },
    forget(anchor) {
      cards.delete(anchor);
    },
    dispose(root) {
      for (const [anchor, card] of cards) {
        if (card.root === root) {
          cards.delete(anchor);
        }
      }
    },
  };
  Object.assign(
    transcript,
    await step("a body's links into the served repository", LINKED, "linked"),
  );
  {
    const linked = transcript["a body's links into the served repository"];
    assert(linked.assets.includes("repository-links"), "the panel asks for what links open");
    const box = JSON.stringify(linked.box);
    assert(
      box.includes("a[href=/pull/12 data-metabrowser-github-localization=pull]"),
      "a same-repository pull request opens its page here, in this tab, unmarked",
    );
    assert(box.includes('{"a":"a relative one"}'), "a relative reference stays text");
    assert(
      box.includes(
        "a[href=https://example.com/doc target=_blank rel=noopener noreferrer data-decorated=external]",
      ),
      "another site stays an outside link",
    );
    // What a plain click on each link does: the page opens a `/view/` address itself, the
    // shell a route, and the browser follows another site, as it follows every modified
    // click.
    const placed = summary(LINKED, "linked");
    await internals.placeCommitBody(placed, detail(LINKED, "linked"));
    const clicked = (anchor, modifiers) => {
      const opened = anchor.click(modifiers);
      const said = navigated.splice(0);
      assert(opened === said.length > 0, "a click opens in place exactly when it says so");
      return `${anchor.textContent}: ${opened ? said.join(", ") : "the browser follows it"}`;
    };
    linked.clicks = [
      ...placed.querySelectorAll("a[href]").map((anchor) => clicked(anchor)),
      ...placed
        .querySelectorAll("a[href]")
        .map((anchor) => `Command-click ${clicked(anchor, { metaKey: true })}`),
    ];
    assert(
      JSON.stringify(linked.clicks) ===
        JSON.stringify([
          "the pull request: the shell opens /pull/12",
          `a commit: the shell opens /commit/${LINKED_COMMIT}`,
          "the pull requests: the shell opens /pulls",
          "the guide: /view/docs/guide.md",
          "another site: the browser follows it",
          "Command-click the pull request: the browser follows it",
          "Command-click a commit: the browser follows it",
          "Command-click the pull requests: the browser follows it",
          "Command-click the guide: the browser follows it",
          "Command-click another site: the browser follows it",
        ]),
      "a plain click opens an in-app page in place, and a modified click is the browser's",
    );
    // Each link has its card, for its own address, with the body's article as its root: one
    // that opens here says what it opens, and one to another site where it goes. No link has
    // a tooltip of its own; when another page has the pane, the panel puts the body's cards
    // away.
    const article = placed.querySelector(".kpress-inert");
    const bodyLinks = placed.querySelectorAll("a[href]");
    linked.cards = bodyLinks.map((anchor) => {
      assert(anchor.getAttribute("data-tip-text") === null, "a link has no tooltip of its own");
      const card = cards.get(anchor);
      if (card === undefined) {
        return `${anchor.textContent}: none`;
      }
      const { root, target } = card;
      assert(root === article, "a link's card has the body's article as its root");
      let opens = target.href;
      if (target.kind === "view") {
        opens = `/view/${target.target.path}`;
      } else if (target.kind === "external") {
        opens = target.url;
      }
      assert(opens === anchor.getAttribute("href"), "a link's card is for its own address");
      return `${anchor.textContent}: ${target.kind}${target.kind === "view" ? ` ${target.localization}` : ""}`;
    });
    sandbox.MetabrowserGitPanel.cancelPending();
    linked["cards left once another page has the pane"] = bodyLinks.filter((anchor) =>
      cards.has(anchor),
    ).length;
  }
  sandbox.MetabrowserSourcePinGuard = { hasChanged: () => true };
  const staleCommit = summary(LINKED, "linked");
  await internals.placeCommitBody(staleCommit, detail(LINKED, "linked"));
  const staleGuide = staleCommit
    .querySelectorAll("a[href]")
    .find((anchor) => anchor.textContent === "the guide");
  assert(
    staleGuide?.getAttribute("href") ===
      "https://github.com/acme/widgets/blob/main/docs/guide.md" && !staleGuide.click(),
    "commit prose in a stale shell keeps the authored GitHub document link",
  );
  delete sandbox.MetabrowserSourcePinGuard;
  delete sandbox.metabrowser.repository;
  delete sandbox.metabrowser.sourceKind;
  delete sandbox.metabrowser.loadRepositoryLinks;
  delete sandbox.metabrowser.navigation;

  Object.assign(transcript, await step("a commit with no body", NO_BODY, ""));
  assert(transcript["a commit with no body"].requests.length === 0, "no body, no request");

  transcript.notes = {
    body_too_large: internals.commitBodyNote({ code: "body_too_large", max_bytes: 65536 }),
    render_deadline: internals.commitBodyNote({ code: "render_deadline", deadline_ms: 1000 }),
    renderer_exited: internals.commitBodyNote({ code: "renderer_exited" }),
    renderer_unavailable: internals.commitBodyNote({ code: "renderer_unavailable" }),
    renderer_busy: internals.commitBodyNote({ code: "renderer_busy" }),
    render_failed: internals.commitBodyNote({ code: "render_failed" }),
    commit_not_found: internals.commitBodyNote({ code: "commit_not_found" }),
    none: internals.commitBodyNote(null),
  };
  process.stdout.write(`${JSON.stringify(transcript, null, 2)}\n`);
})().catch((error) => {
  process.stderr.write(`${error.stack}\n`);
  process.exit(1);
});

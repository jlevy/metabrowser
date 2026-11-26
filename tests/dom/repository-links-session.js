// Browserless session for what a link in rendered text opens (static/repository-links.js).
//
// The exact production module loads whole, as the shell loads it on demand, beside the
// GitPath codec (static/git-path.js) a pinned revision's shell loads first. `localize`, which
// the part `localized` prints, reads one table of URLs against the contexts a page can
// have: a checkout on a branch whose name holds a slash, the same checkout served from a
// subfolder, a mirror's pinned revision, and a pull request's text whose head is or is not
// the served commit. With no part named, `viewFileUrl` reads a rendered diff's links to
// files of the head, and `enhance` runs over a few links of an inert text, as a pull
// request's page and a commit's page call it, and a plain and a modified click on each: a
// `/view/` target opens through `navigation.open`, a route through the page's own `open`
// when it takes it and otherwise through the shell's `navigation.openRoute`, and the
// browser follows what neither opened, as it does every modified click.
// tests/test_repository_links_js.py holds its in-app addresses to the server's route
// grammar and its github.com addresses to the server's URL reducer.
//
// The link cards (static/link-previews.js), which the bundle loads after the resolver, are
// a recording stand-in here: each run prints what `enhance` gave a card, with which root and
// target, and took one from, and what the runtime's `disposePreviews` put away (`previews`).

const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const repoRoot = path.resolve(__dirname, "../..");
const sandbox = { Object, URL, TextEncoder, TextDecoder, btoa, atob, console };
sandbox.window = sandbox;
vm.createContext(sandbox);
for (const name of ["git-path.js", "repository-links.js"]) {
  const file = path.join(repoRoot, "src/metabrowser/static", name);
  vm.runInContext(fs.readFileSync(file, "utf8"), sandbox, { filename: file });
}
const links = sandbox.MetabrowserRepositoryLinks;

// What the stand-in for the link cards heard, one line a call, each element by its name.
const previews = [];
/** @type {Map<object, string>} */
const names = new Map();
const named = (element) => names.get(element) ?? "an element of no name";
const described = (target) => {
  if (target.kind === "view") {
    return `view ${target.localization} /view/${target.target.path}`;
  }
  return `${target.kind} ${target.kind === "external" ? target.url : target.href}`;
};
const cards = {
  register(root, anchor, target, _mb, options = {}) {
    const title = options.authorTitle ? ` titled ${JSON.stringify(options.authorTitle)}` : "";
    previews.push(`register ${named(anchor)} in ${named(root)}: ${described(target)}${title}`);
    return true;
  },
  forget: (anchor) => previews.push(`forget ${named(anchor)}`),
  dispose: (root) => previews.push(`dispose ${named(root)}`),
};

const SERVED = "a".repeat(40);
const OTHER = "b".repeat(40);
const PINNED = "c".repeat(40);
const ANCHOR = `diff-${"0".repeat(64)}`;

const contexts = {
  checkout: {
    context: {
      branch: "feature/navigation",
      host: "github.com",
      name: "docs",
      owner: "example",
      revision: SERVED,
      served_prefix: "",
    },
    options: { sourceKind: "filesystem" },
  },
  subfolder: {
    context: {
      branch: "feature/navigation",
      host: "github.com",
      name: "docs",
      owner: "example",
      revision: SERVED,
      served_prefix: "packages/handbook",
    },
    options: { sourceKind: "filesystem" },
  },
  pin: {
    context: {
      branch: "main",
      host: "github.com",
      name: "docs",
      owner: "example",
      revision: PINNED,
      served_prefix: "",
    },
    options: { sourceKind: "git_revision" },
  },
  "text at the served head": {
    context: {
      branch: null,
      host: "github.com",
      name: "docs",
      owner: "example",
      revision: SERVED,
      served_prefix: "",
    },
    options: { sourceKind: "git_revision", text: { head: SERVED } },
  },
  "text beside a checkout of its head": {
    context: {
      branch: "main",
      host: "github.com",
      name: "docs",
      owner: "example",
      revision: SERVED,
      served_prefix: "",
    },
    options: { sourceKind: "filesystem", text: { head: SERVED } },
  },
  "text away from its head": {
    context: {
      branch: "main",
      host: "github.com",
      name: "docs",
      owner: "example",
      revision: PINNED,
      served_prefix: "",
    },
    options: {
      sourceKind: "git_revision",
      text: {
        head: OTHER,
        // The files pull request 7's comparison changes, which its Changes tab shows.
        changes: { number: 7, stack: false, files: new Set(["docs/trade-runner/README.md"]) },
      },
    },
  },
  "a stack's note away from its head": {
    context: {
      branch: "main",
      host: "github.com",
      name: "docs",
      owner: "example",
      revision: PINNED,
      served_prefix: "",
    },
    options: {
      sourceKind: "git_revision",
      text: { head: OTHER, changes: { number: 3, stack: true, files: new Set(["src/app.py"]) } },
    },
  },
  "text at the served head, from a subfolder": {
    context: {
      branch: null,
      host: "github.com",
      name: "docs",
      owner: "example",
      revision: SERVED,
      served_prefix: "packages/handbook",
    },
    options: { sourceKind: "git_revision", text: { head: SERVED } },
  },
  "text with no head yet": {
    context: {
      branch: "main",
      host: "github.com",
      name: "docs",
      owner: "example",
      revision: PINNED,
      served_prefix: "",
    },
    options: { sourceKind: "git_revision", text: { head: null } },
  },
};

const repo = "https://github.com/example/docs";
const cases = {
  checkout: [
    ["the repository", repo],
    ["the repository, its README's heading, as GitHub spells it", `${repo}#install`],
    ["the repository, any case, .git, www", "https://www.github.com/Example/Docs.git/"],
    ["the repository with a query", `${repo}?tab=readme`],
    ["the repository's README, as its anchors copy", `${repo}?tab=readme-ov-file#install`],
    ["a file on the served branch", `${repo}/blob/feature/navigation/guide/intro.md#Setup`],
    ["a file shown as source", `${repo}/blob/feature/navigation/src/app.py?plain=1#L3-L5`],
    ["a folder on the served branch", `${repo}/tree/feature/navigation/guide`],
    ["the served branch's root", `${repo}/tree/feature/navigation`],
    ["a file at the served commit", `${repo}/blob/${SERVED.toUpperCase()}/guide/intro.md`],
    ["the served commit's root", `${repo}/tree/${SERVED}`],
    ["a name with a percent sign", `${repo}/blob/feature/navigation/100%25.md`],
    ["a file on another branch", `${repo}/blob/main/guide/intro.md`],
    ["a file at another commit", `${repo}/blob/${OTHER}/guide/intro.md`],
    ["a file at the served commit, abbreviated", `${repo}/blob/aaaaaaa/guide/intro.md`],
    ["a file at another commit, abbreviated", `${repo}/blob/bbbbbbb/guide/intro.md`],
    ["a file at a tag", `${repo}/blob/v1.2.3/guide/intro.md`],
    ["a blob naming only the branch", `${repo}/blob/feature/navigation`],
    ["a pull request", `${repo}/pull/12`],
    ["its Changes", `${repo}/pull/12/files`],
    ["its Changes, at one file and line", `${repo}/pull/12/changes#${ANCHOR}R3`],
    ["its Checks", `${repo}/pull/12/checks`],
    ["one of its commits", `${repo}/pull/12/commits/${OTHER}`],
    ["its commit list", `${repo}/pull/12/commits`],
    ["a comment on it", `${repo}/pull/12#issuecomment-7`],
    ["its Changes with a query", `${repo}/pull/12/files?w=1`],
    ["no pull request number", `${repo}/pull/docs/new.md`],
    ["a commit", `${repo}/commit/${OTHER.toUpperCase()}`],
    ["a commit, at one file", `${repo}/commit/${OTHER}#${ANCHOR}`],
    ["a commit comment", `${repo}/commit/${OTHER}#r123`],
    ["a commit's patch", `${repo}/commit/${OTHER}.patch`],
    ["an abbreviated commit", `${repo}/commit/bbbbbbb`],
    ["the pull request list", `${repo}/pulls`],
    ["a search of pull requests", `${repo}/pulls?q=is%3Aopen`],
    ["an issue", `${repo}/issues/3`],
    ["a comparison", `${repo}/compare/main...feature/navigation`],
    ["the commit list", `${repo}/commits/feature/navigation`],
    ["a raw file", `${repo}/raw/feature/navigation/guide/intro.md`],
    ["another repository", "https://github.com/example/other/blob/feature/navigation/a.md"],
    ["another host", "https://gitlab.com/example/docs/-/blob/main/a.md"],
    ["a host that only starts like GitHub's", "https://github.com.example.net/example/docs"],
    ["credentials", "https://reader@github.com/example/docs"],
    ["a port", "https://github.com:8443/example/docs"],
    ["a malformed escape", `${repo}/blob/feature/navigation/%zz.md`],
    ["a dot segment, escaped", `${repo}/blob/feature/navigation/%2e%2e/secret.md`],
    // A raw HTML link keeps its address byte for byte, and the navigation codec refuses a
    // `%` that starts no escape.
    ["a query with a stray percent sign", `${repo}/blob/feature/navigation/a.md?a=50%`],
    ["a query with a malformed escape", `${repo}/blob/feature/navigation/a.md?q=%zz`],
    [
      "an owner spelled with a sign that folds to a letter",
      "https://github.com/exampl%E2%84%AAe/docs",
    ],
    [
      "its Changes, at a file anchor in capitals",
      `${repo}/pull/12/files#${ANCHOR.toUpperCase().replace("DIFF-", "diff-")}`,
    ],
    ["not a URL", "docs/new.md"],
  ],
  subfolder: [
    ["a file inside the served folder", `${repo}/blob/feature/navigation/packages/handbook/a.md`],
    ["a permalink inside it", `${repo}/blob/${SERVED}/packages/handbook/guide.md#Install`],
    ["the served folder itself", `${repo}/tree/feature/navigation/packages/handbook`],
    ["a file outside it", `${repo}/blob/feature/navigation/README.md`],
    ["the repository", repo],
  ],
  pin: [
    ["a file on the pinned branch", `${repo}/blob/main/docs/雪.md`],
    ["a folder on the pinned branch", `${repo}/tree/main/docs`],
    ["the pinned branch's root", `${repo}/tree/main`],
    ["a file at the pinned commit", `${repo}/blob/${PINNED}/README.md`],
  ],
  "text beside a checkout of its head": [
    ["a head file uses GitHub even if checkout bytes differ", `${repo}/pull/docs/guide.md`],
  ],
  "text at the served head": [
    ["a path-relative reference", `${repo}/pull/docs/trade-runner/README.md`],
    ["a folder", `${repo}/pull/docs/`],
    ["the root", `${repo}/pull/`],
    ["with a query and fragment", `${repo}/pull/src/app.py?plain=1#L2`],
    ["a pull request's Changes, still", `${repo}/pull/7/files`],
    ["a number first, then a pull request's page", `${repo}/pull/7/commits`],
    ["a folder named with digits", `${repo}/pull/2024/notes.md`],
    ["a bare pull, which is no reference", `${repo}/pull`],
    ["GitHub's page that opens a pull request", `${repo}/pull/new/feature/navigation`],
    ["a stray percent sign", `${repo}/pull/docs/a.md?q=%zz`],
    ["a file on another branch, still external", `${repo}/blob/main/README.md`],
  ],
  "text away from its head": [
    ["a file the pull request changes, in its Changes", `${repo}/pull/docs/trade-runner/README.md`],
    ["an authored absolute patch URL", `${repo}/pull/7.patch`, false],
    ["the same resolution from an authored relative file", `${repo}/pull/7.patch`],
    ["an anchored changed file, on GitHub", `${repo}/pull/docs/trade-runner/README.md#install`],
    ["a file it does not change, on github.com", `${repo}/pull/docs/guide.md`],
    [
      "a changed file with a query, on github.com",
      `${repo}/pull/docs/trade-runner/README.md?plain=1`,
    ],
    ["a folder", `${repo}/pull/docs/`],
    ["the root", `${repo}/pull/`],
    ["with a query and fragment", `${repo}/pull/src/app.py?plain=1#L2`],
    ["a name that needs escaping", `${repo}/pull/docs/space%20name.md`],
    ["a file on the pinned branch, in place", `${repo}/blob/main/README.md`],
  ],
  "text at the served head, from a subfolder": [
    ["a file inside the served folder", `${repo}/pull/packages/handbook/a.md`],
    ["a file outside it, on github.com", `${repo}/pull/README.md`],
  ],
  "a stack's note away from its head": [
    ["a file the stack changes, in its Changes", `${repo}/pull/src/app.py`],
    ["a file it does not change, on github.com", `${repo}/pull/README.md`],
  ],
  "text with no head yet": [["a path-relative reference", `${repo}/pull/docs/new.md`]],
};

const localized = {};
for (const [name, rows] of Object.entries(cases)) {
  const { context, options } = contexts[name];
  localized[name] = rows.map(([label, url, pathRelative = Boolean(options.text)]) => ({
    label,
    url,
    result: links.localize(url, context, { ...options, pathRelative }),
  }));
}

// A link of an inert text, with the attributes and listeners enhance reads and writes.
function anchor(href, attributes = {}) {
  const values = new Map(Object.entries({ href, ...attributes }));
  const listeners = [];
  return {
    getAttribute: (key) => values.get(key) ?? null,
    hasAttribute: (key) => values.has(key),
    setAttribute: (key, value) => values.set(key, String(value)),
    removeAttribute: (key) => values.delete(key),
    addEventListener: (type, listener) => listeners.push({ type, listener }),
    attributes: () => Object.fromEntries([...values].sort(([a], [b]) => a.localeCompare(b))),
    listeners: () => listeners.filter(({ type }) => type === "click").length,
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
      for (const { type, listener } of listeners) {
        if (type === "click") {
          listener(event);
        }
      }
      return event.defaultPrevented;
    },
  };
}

function enhanced(context, sourceKind, options) {
  const opened = [];
  const routed = [];
  const asked = [];
  // Whether the shell opens a route in place: false before its tab controller has loaded.
  const shellOpens = options.shell !== false;
  const outside = { target: "_blank", rel: "noopener noreferrer" };
  const anchors = {
    file: anchor(`${repo}/pull/docs/new.md`, { ...outside, "data-metabrowser-path-relative": "" }),
    branch: anchor(`${repo}/blob/main/README.md`, outside),
    pull: anchor(`${repo}/pull/12/files`, outside),
    commit: anchor(`${repo}/commit/${OTHER}`, outside),
    list: anchor(`${repo}/pulls`, outside),
    other: anchor("https://example.com/", outside),
  };
  const root = { querySelectorAll: () => Object.values(anchors) };
  names.set(root, "the text");
  for (const [name, link] of Object.entries(anchors)) {
    names.set(link, name);
  }
  previews.length = 0;
  sandbox.MetabrowserLinkPreviews = options.cards === false ? undefined : cards;
  const mb = {
    repository: context,
    sourceKind: () => sourceKind,
    // The page's one tooltip, which draws a link's card.
    tooltip: { show() {}, hide() {} },
    navigation: {
      href: (target) =>
        `/view/${target.path}${target.query ? `?${target.query}` : ""}${target.fragment ? `#${target.fragment}` : ""}`,
      open: (target) => {
        opened.push(target);
        return Promise.resolve();
      },
      openRoute: (href) => asked.push(href) > 0 && shellOpens,
    },
  };
  // As a pull request's page does: another pull request opens in place, and a commit's
  // page or the list is the shell's to open.
  const open = options.routes
    ? (route) =>
        route.pull !== null && routed.push(`${route.href} ${JSON.stringify(route.pull)}`) > 0
    : undefined;
  const changed = [links.enhance(root, mb, { text: options.text, open })];
  // The same text, read again as the page learns more: the files its pull request changes,
  // or a head that moved past them, or, as a rendered diff away from its head is, with its
  // `/view/` targets left as the text wrote them.
  for (const later of options.later ?? []) {
    changed.push(links.enhance(root, mb, { text: options.text, ...later, open }));
  }
  const clicks = {};
  for (const [name, link] of Object.entries(anchors)) {
    clicks[name] = {
      plain: link.click(),
      withMeta: link.click({ metaKey: true }),
      listeners: link.listeners(),
    };
  }
  // The page lets the text go.
  links.disposePreviews(root);
  return {
    changed,
    anchors: Object.fromEntries(
      Object.entries(anchors).map(([name, link]) => [name, link.attributes()]),
    ),
    clicks,
    opened,
    routed,
    shell: { opens: shellOpens, asked },
    previews: [...previews],
  };
}

// A rendered diff's link to a file of the head, `/view/<GitPath wire>`, on github.com at the
// head, for a page that does not show it.
const head = contexts.pin.context;
const viewFiles = Object.fromEntries(
  [
    ["a file", `/view/${sandbox.MetabrowserGitPath.wire("docs/雪.md")}`],
    [
      "a file, at a heading",
      `/view/${sandbox.MetabrowserGitPath.wire("docs/setup.md")}#user-content-install`,
    ],
    [
      "a name with a leading byte-order mark",
      `/view/${sandbox.MetabrowserGitPath.wire("\uFEFFplan.md")}`,
    ],
    [
      "a name with a literal replacement character",
      `/view/${sandbox.MetabrowserGitPath.wire("docs/\uFFFD.md")}`,
    ],
    ["a name with a control character", `/view/${sandbox.MetabrowserGitPath.wire("a\u0007.md")}`],
    ["a name with a backslash", `/view/${sandbox.MetabrowserGitPath.wire("a\\b.md")}`],
    ["a name that is not text", "/view/g1-_w"],
    ["a partially encoded path", "/view/g1-ZG9jcw/setup.md"],
    ["not a pin's address", "/view/docs/setup.md"],
    ["not a view", "/pull/7/files/docs/setup.md"],
  ].map(([label, href]) => [label, { href, url: links.viewFileUrl(head, OTHER, href) }]),
);

const textContext = contexts["text at the served head"].context;
const runs = {
  "a text at its served head": enhanced(textContext, "git_revision", {
    text: { head: SERVED },
  }),
  "a text away from its head, with the page's own router": enhanced(
    contexts["text away from its head"].context,
    "git_revision",
    { text: { head: OTHER }, routes: true },
  ),
  "a text whose pull request's changed files arrive after it is drawn": enhanced(
    contexts["text away from its head"].context,
    "git_revision",
    {
      text: { head: OTHER },
      later: [
        {
          text: {
            head: OTHER,
            changes: { number: 7, stack: false, files: new Set(["docs/new.md"]) },
          },
        },
      ],
      routes: true,
    },
  ),
  "a text whose head moves past its files, and whose new files then arrive": enhanced(
    contexts["text away from its head"].context,
    "git_revision",
    {
      text: {
        head: OTHER,
        changes: { number: 7, stack: false, files: new Set(["docs/new.md"]) },
      },
      later: [
        { text: { head: PINNED.replace(/c/g, "d") } },
        {
          text: {
            head: PINNED.replace(/c/g, "d"),
            changes: { number: 7, stack: false, files: new Set(["docs/new.md"]) },
          },
        },
      ],
      routes: true,
    },
  ),
  "a rendered diff's text, read again once the served pin moves": enhanced(
    contexts["text away from its head"].context,
    "git_revision",
    { later: [{ views: false }] },
  ),
  "a commit's message, which has no text context": enhanced(textContext, "filesystem", {}),
  "a commit's message before the shell's tabs have loaded": enhanced(textContext, "filesystem", {
    shell: false,
  }),
  "a text on a page whose link cards have not loaded": enhanced(textContext, "filesystem", {
    cards: false,
  }),
  "a page with no repository": enhanced(null, "filesystem", { text: { head: SERVED } }),
};

// The part `localized` prints what `localize` answers for the table of URLs, and no part
// the rest, so each is one transcript block of a size tryscript reads.
const part = process.argv[2] ?? null;
if (part !== null && part !== "localized") {
  throw new Error(`Unknown part ${part}; the one part to name is localized`);
}
console.log(
  JSON.stringify(part === "localized" ? { localized } : { viewFiles, enhanced: runs }, null, 2),
);

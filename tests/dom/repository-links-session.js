// Browserless session for what a link in rendered text opens (static/repository-links.js).
//
// The exact production module loads whole, as the shell loads it on demand, beside the
// GitPath codec (static/git-path.js) a pinned revision's shell loads first. `localize` reads
// one table of URLs against the contexts a page can have: a checkout on a branch whose name
// holds a slash, the same checkout served from a subfolder, a mirror's pinned revision,
// and a pull request's text whose head is or is not the served commit. `enhance` then runs
// over a few links of an inert text, as a pull request's page and a commit's page call it,
// and a plain and a modified click on each. tests/test_repository_links_js.py holds its
// in-app addresses to the server's route grammar and its github.com addresses to the
// server's URL reducer.

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
    options: { sourceKind: "git_revision", text: { head: OTHER } },
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
    ["a file on the served branch", `${repo}/blob/feature/navigation/guide/intro.md#Setup`],
    ["a file shown as source", `${repo}/blob/feature/navigation/src/app.py?plain=1#L3-L5`],
    ["a folder on the served branch", `${repo}/tree/feature/navigation/guide`],
    ["the served branch's root", `${repo}/tree/feature/navigation`],
    ["a file at the served commit", `${repo}/blob/${SERVED.toUpperCase()}/guide/intro.md`],
    ["the served commit's root", `${repo}/tree/${SERVED}`],
    ["a name with a percent sign", `${repo}/blob/feature/navigation/100%25.md`],
    ["a file on another branch", `${repo}/blob/main/guide/intro.md`],
    ["a file at another commit", `${repo}/blob/${OTHER}/guide/intro.md`],
    ["a file at an abbreviated commit", `${repo}/blob/aaaaaaa/guide/intro.md`],
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
  "text at the served head": [
    ["a path-relative reference", `${repo}/pull/docs/trade-runner/README.md`],
    ["a folder", `${repo}/pull/docs/`],
    ["the root", `${repo}/pull/`],
    ["with a query and fragment", `${repo}/pull/src/app.py?plain=1#L2`],
    ["a pull request's Changes, still", `${repo}/pull/7/files`],
    ["a number first is a pull request's address", `${repo}/pull/2024/notes.md`],
    ["a file on another branch, still external", `${repo}/blob/main/README.md`],
  ],
  "text away from its head": [
    ["a path-relative reference", `${repo}/pull/docs/trade-runner/README.md`],
    ["a folder", `${repo}/pull/docs/`],
    ["the root", `${repo}/pull/`],
    ["with a query and fragment", `${repo}/pull/src/app.py?plain=1#L2`],
    ["a name that needs escaping", `${repo}/pull/docs/space%20name.md`],
    ["a file on the pinned branch, in place", `${repo}/blob/main/README.md`],
  ],
  "text with no head yet": [["a path-relative reference", `${repo}/pull/docs/new.md`]],
};

const localized = {};
for (const [name, rows] of Object.entries(cases)) {
  const { context, options } = contexts[name];
  localized[name] = rows.map(([label, url]) => ({
    label,
    url,
    result: links.localize(url, context, options),
  }));
}

// A link of an inert text, with the attributes and listeners enhance reads and writes.
function anchor(href, attributes = {}) {
  const values = new Map(Object.entries({ href, ...attributes }));
  const listeners = [];
  return {
    getAttribute: (key) => values.get(key) ?? null,
    setAttribute: (key, value) => values.set(key, String(value)),
    removeAttribute: (key) => values.delete(key),
    addEventListener: (type, listener) => listeners.push({ type, listener }),
    attributes: () => Object.fromEntries([...values].sort(([a], [b]) => a.localeCompare(b))),
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
  const outside = { target: "_blank", rel: "noopener noreferrer" };
  const anchors = {
    file: anchor(`${repo}/pull/docs/new.md`, outside),
    pull: anchor(`${repo}/pull/12/files`, outside),
    commit: anchor(`${repo}/commit/${OTHER}`, outside),
    other: anchor("https://example.com/", outside),
  };
  const root = { querySelectorAll: () => Object.values(anchors) };
  const mb = {
    repository: context,
    sourceKind: () => sourceKind,
    navigation: {
      href: (target) =>
        `/view/${target.path}${target.query ? `?${target.query}` : ""}${target.fragment ? `#${target.fragment}` : ""}`,
      open: (target) => {
        opened.push(target);
        return Promise.resolve();
      },
    },
  };
  const changed = links.enhance(root, mb, {
    ...options,
    // As a pull request's page does: another pull request opens in place, and a commit's
    // page is followed as a link.
    open: options.routes
      ? (route) =>
          route.pull !== null && routed.push(`${route.href} ${JSON.stringify(route.pull)}`) > 0
      : undefined,
  });
  const clicks = {};
  for (const [name, link] of Object.entries(anchors)) {
    clicks[name] = { plain: link.click(), withMeta: link.click({ metaKey: true }) };
  }
  return {
    changed,
    anchors: Object.fromEntries(
      Object.entries(anchors).map(([name, link]) => [name, link.attributes()]),
    ),
    clicks,
    opened,
    routed,
  };
}

const textContext = contexts["text at the served head"].context;
console.log(
  JSON.stringify(
    {
      localized,
      enhanced: {
        "a text at its served head": enhanced(textContext, "filesystem", {
          text: { head: SERVED },
        }),
        "a text away from its head, with the page's own router": enhanced(
          contexts["text away from its head"].context,
          "git_revision",
          { text: { head: OTHER }, routes: true },
        ),
        "a commit's message, which has no text context": enhanced(textContext, "filesystem", {}),
        "a page with no repository": enhanced(null, "filesystem", { text: { head: SERVED } }),
      },
    },
    null,
    2,
  ),
);

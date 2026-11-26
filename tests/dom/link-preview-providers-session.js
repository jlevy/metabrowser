// Browserless session for what a link card says of each kind of page, and what a rest on
// the link starts loading (static/link-preview-providers.js).
//
// The exact production module runs whole, with the exact modules it reads: the Commits
// panel (static/git-panel.js, over the graph and history window it needs to evaluate), whose
// commit summary and prefetch it calls; the shared formatters, whose age a commit's card
// tells; the file type registry, whose family names a file; and the GitPath codec, which
// spells a pin's paths. The card's registry is a stand-in that keeps what each provider
// registers, as static/link-previews.js keeps it, and the session calls each as the card
// does once the pointer rests on a link. Every read replays the server's own answer:
// tests/fixtures/link-preview-providers-responses.json, which
// tests/test_link_preview_providers_session.py records from the real routes, and the stacks
// snapshot the Pulls tab's session replays (github-stacks-responses.json). A read the
// recordings hold no answer for fails the session, so it can make no other.
//
// It prints each kind's summary, the reads each rest made, and what each prefetch loaded,
// then every request in order and how many were aborted.

const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const repoRoot = path.resolve(__dirname, "../..");
const fixture = (name) =>
  JSON.parse(fs.readFileSync(path.join(repoRoot, "tests/fixtures", name), "utf8"));
const recorded = fixture("link-preview-providers-responses.json");
const stackSnapshots = fixture("github-stacks-responses.json");
const fileTypeRegistry = JSON.parse(
  fs.readFileSync(
    path.join(repoRoot, "src/metabrowser/data/file-rollup-format/recommended-file-types.json"),
    "utf8",
  ),
);

// The time ages are told at: six days after the recording's one commit date.
let now = Date.parse("2026-11-26T12:00:00Z");
class SessionDate extends Date {
  static now() {
    return now;
  }
}

/**
 * Every request any module made, in order, and whether its signal aborted it before its
 * answer came: what the page's `fetch_aborts` budget counts. A signal aborted after its
 * answer, as a preparation's is when another replaces it, aborts nothing.
 */
const requests = [];
/** The requests one step made, by the line each is printed as. */
let asked = [];
/** @returns {() => void} what marks the request answered */
function request(method, url, signal) {
  const line = `${method} ${url}`;
  const entry = { line, answered: false, aborted: false };
  requests.push(entry);
  asked.push(line);
  entry.aborted = signal?.aborted === true;
  signal?.addEventListener("abort", () => {
    entry.aborted ||= !entry.answered;
  });
  return () => {
    entry.answered = true;
  };
}

// A read the session holds until it says so, to stand for an answer still on its way.
let holding = false;
const held = [];
function answerLater(answer) {
  if (!holding) {
    return answer;
  }
  return new Promise((resolve) => held.push(() => resolve(answer)));
}

// `GET /api/plugin/<plugin>/<route>`, as `metabrowser.fetchPluginData` asks for it.
const pluginAnswers = new Map([
  ...Object.entries(recorded)
    .filter(([name]) => name.startsWith("pulls?") || name.startsWith("pull?"))
    .map(([name, answer]) => [`/api/plugin/github/${name}`, answer]),
  ...[recorded["commit comparison"], recorded["first commit comparison"]].map((answer) => [
    `/api/plugin/diff/comparison?revision=${answer.revision}`,
    answer,
  ]),
]);
let stacksAnswer = stackSnapshots.shared;
// `GET /api/git/commit/<id>`, as the Commits panel asks for it.
const commitAnswers = new Map(
  [recorded.commit, recorded["first commit"], recorded["commit absent"]].map((answer) => [
    `/api/git/commit/${answer.revision}`,
    answer,
  ]),
);

const sandbox = {
  console,
  Date: SessionDate,
  AbortController,
  URL,
  URLSearchParams,
  TextEncoder,
  TextDecoder,
  btoa,
  atob,
  setTimeout,
  clearTimeout,
  METABROWSER_SETTINGS: { FILE_TYPE_REGISTRY: fileTypeRegistry },
  async fetch(url, options = {}) {
    const answered = request(options.method ?? "GET", url, options.signal);
    const answer = commitAnswers.get(url);
    if (answer === undefined) {
      throw new Error(`no recorded answer for ${url}`);
    }
    const settled = await answerLater(answer);
    answered();
    return {
      ok: settled.status >= 200 && settled.status < 300,
      status: settled.status,
      headers: { get: () => null },
      json: async () => settled.body,
    };
  },
};
sandbox.window = sandbox;

// What a page holds of its files: the catalog's snapshot and the tree's folder totals, by
// each path as the inventory spells it, `%` as `%25` in a folder's.
const servedFiles = ["README.md", "docs/guide.md", "notes/100%25.md", "notes/draft.zzz-unclaimed"];
const catalogOf = (paths) =>
  paths
    .map((file) => ({
      path: file,
      basename: file.slice(file.lastIndexOf("/") + 1),
      logicalExtension: null,
      source: "inventory",
    }))
    .sort((left, right) => (left.path < right.path ? -1 : left.path > right.path ? 1 : 0));
let knownFiles = catalogOf(servedFiles);
let catalogComplete = true;
const folderTotals = new Map([
  ["", { files: 3, bytes: 112 }],
  ["docs", { files: 1, bytes: 48 }],
]);

/** What each prefetch asked for beyond its reads. */
let assets = [];
let counterparts = [];
let sourceKind = "filesystem";
let repository = { host: "github.com", owner: "octo", name: "demo" };

const mb = {
  async fetchPluginData(plugin, route, params = {}, options = {}) {
    const query = new URLSearchParams(
      Object.entries(params).map(([name, value]) => [name, String(value)]),
    ).toString();
    const url = `/api/plugin/${plugin}/${route}${query ? `?${query}` : ""}`;
    const answered = request("GET", url, options.signal);
    const answer = url === "/api/plugin/github/stacks" ? stacksAnswer : pluginAnswers.get(url);
    if (answer === undefined) {
      throw new Error(`no recorded answer for ${url}`);
    }
    const settled = await answerLater(answer);
    answered();
    if (settled.status < 200 || settled.status >= 300) {
      throw Object.assign(new Error(`fetchPluginData ${plugin}/${route}: ${settled.status}`), {
        status: settled.status,
        payload: settled.body,
      });
    }
    return settled.body;
  },
  async ensureKindAssets(kind) {
    assets.push(kind);
  },
  prefetchCounterpart(page) {
    counterparts.push(page);
  },
  get repository() {
    return repository;
  },
  sourceKind: () => sourceKind,
  // The registry the shell carries, as static/file-type-taxonomy.js builds it from the
  // settings the server writes.
  get fileTypes() {
    return sandbox.MetabrowserFileTypeTaxonomy;
  },
  navigation: {
    href: (target) => `/view/${target.path}`,
  },
  fileCatalog: {
    snapshot: () => ({
      complete: catalogComplete,
      truncated: false,
      files: knownFiles,
      observedCount: knownFiles.length,
      revision: 1,
      sourceSummary: {},
    }),
  },
  directoryTotals: {
    get(folder) {
      const totals = folderTotals.get(folder);
      return totals === undefined
        ? null
        : {
            path: folder,
            revision: 1,
            state: "complete",
            totalFiles: totals.files,
            totalBytes: totals.bytes,
            unignoredFiles: totals.files,
            unignoredBytes: totals.bytes,
          };
    },
  },
  formatAge: (seconds, options) => sandbox.MetabrowserFormatters.age(Number(seconds) || 0, options),
  formatFileCount: (count) => sandbox.MetabrowserFormatters.formatFileCount(count),
  formatSize: (bytes) => sandbox.MetabrowserFormatters.formatBytes(bytes),
};
// The Commits panel reads the SDK from the page, as it does in the shell.
sandbox.metabrowser = mb;

// The card's registry, as static/link-previews.js keeps what each provider registers.
const providers = new Map();
const provided = [];
sandbox.MetabrowserLinkPreviews = {
  provide(kind, provider) {
    provided.push(kind);
    providers.set(kind, provider);
  },
};

vm.createContext(sandbox);
for (const name of [
  "formatters.js",
  "file-type-taxonomy.js",
  "git-path.js",
  "git-graph.js",
  "git-history-window.js",
  "git-panel.js",
  "repository-links.js",
  "link-preview-providers.js",
]) {
  const file = path.join(repoRoot, "src/metabrowser/static", name);
  vm.runInContext(fs.readFileSync(file, "utf8"), sandbox, { filename: file });
}
const panel = sandbox.MetabrowserGitPanel;

const settle = () => new Promise((resolve) => setTimeout(resolve, 0));

/** A rest on a link: its summary, and the reads that rest made. */
async function rest(subject, signal) {
  asked = [];
  let summary;
  try {
    summary = await providers.get(subject.kind).summary(subject, signal ? { mb, signal } : { mb });
  } catch (error) {
    summary = { rejected: error?.name ?? String(error) };
  }
  // What a file's or folder's card could know: whether the catalog covered the whole root.
  const held = subject.kind === "file" || subject.kind === "folder";
  return {
    subject,
    summary,
    asked,
    ...(held ? { catalog: catalogComplete ? "whole" : "filling" } : {}),
  };
}

/** A prefetch on a rest: the reads it made, the assets it loaded, and the answers it asked. */
async function prefetch(subject) {
  asked = [];
  assets = [];
  counterparts = [];
  await providers.get(subject.kind).prefetch(subject, { mb });
  await settle();
  return { subject, asked, assets, counterparts };
}

const commit = recorded.commit.revision;
const absent = recorded["commit absent"].revision;
const pull = (number, tab = "", file = "") => ({ kind: "pull", number, tab, file });
const stack = (number) => ({ kind: "stack", number, file: "" });
// A file's or folder's subject as the card makes one from the resolver's answer for a
// github.com link to it on the served branch (static/link-previews.js, `subject`): its target
// is the resolver's own, spelled for the page's source kind, and its path the one shown.
const viewTarget = (shown, directory) =>
  sandbox.MetabrowserRepositoryLinks.localize(
    `https://github.com/octo/demo/${directory ? "tree" : "blob"}/main/${encodeURI(shown)}`,
    // The repository the link names, whatever the page's own context says, so a page with
    // none still has the subject a page with one would give the link.
    {
      host: "github.com",
      owner: "octo",
      name: "demo",
      branch: "main",
      revision: "a".repeat(40),
      served_prefix: "",
    },
    { sourceKind },
  ).target;
const file = (shown, opens = "here") => ({
  kind: "file",
  path: shown,
  opens,
  target: viewTarget(shown, false),
});
const folder = (shown) => ({
  kind: "folder",
  path: shown,
  opens: "here",
  target: viewTarget(shown.replace(/\/$/, ""), true),
});

async function run() {
  const summaries = {};
  const prefetches = {};

  summaries["a pull request, open"] = await rest(pull(12));
  summaries["a draft"] = await rest(pull(13));
  // An answer still on its way when the caller stops waiting lands, and is kept.
  holding = true;
  const stopped = new AbortController();
  const waiting = rest(pull(14), stopped.signal);
  await settle();
  stopped.abort();
  summaries["a closed one, whose caller stops waiting"] = await waiting;
  holding = false;
  for (const answer of held.splice(0)) {
    answer();
  }
  await settle();
  summaries["the closed one, rested on again"] = await rest(pull(14));
  summaries["a merged one"] = await rest(pull(15));
  summaries["one the catalog does not hold"] = await rest(pull(99));
  summaries["the open one again"] = await rest(pull(12));
  summaries["a changed file in its Changes"] = await rest(pull(12, "files", "docs/guide.md"));

  summaries["a stack the snapshot holds"] = await rest(stack(286));
  summaries["another, from the same read"] = await rest(stack(290));
  summaries["one the snapshot does not hold"] = await rest(stack(300));
  now += 30_000;
  stacksAnswer = stackSnapshots.absent;
  summaries["a stack, once the read is too old to reuse"] = await rest(stack(286));

  summaries["a commit the repository has"] = await rest({ kind: "commit", revision: commit });
  summaries["a commit it lacks"] = await rest({ kind: "commit", revision: absent });
  summaries["the missing commit again"] = await rest({ kind: "commit", revision: absent });
  sandbox.MetabrowserGitPanel = undefined;
  summaries["a commit, before the Commits panel has loaded"] = await rest({
    kind: "commit",
    revision: commit,
  });
  sandbox.MetabrowserGitPanel = panel;

  summaries["a file the served tree holds"] = await rest(file("docs/guide.md"));
  summaries["the same file, opened in the served working tree"] = await rest(
    file("docs/guide.md", "working-tree"),
  );
  summaries["a file a whole catalog lacks"] = await rest(file("docs/old-guide.md"));
  catalogComplete = false;
  summaries["the same, while the catalog is still filling"] = await rest(file("docs/old-guide.md"));
  catalogComplete = true;
  summaries["a name with a percent sign"] = await rest(file("notes/100%.md"));
  summaries["a name no file type claims"] = await rest(file("notes/draft.zzz-unclaimed"));
  summaries["a folder the tree has totaled"] = await rest(folder("docs/"));
  summaries["the served root"] = await rest(folder(""));
  summaries["a folder it has not"] = await rest(folder("src/"));
  // A pin's inventory spells each path in the GitPath wire (static/git-path.js).
  sourceKind = "git_revision";
  knownFiles = catalogOf(["README.md", "docs/guide.md"].map(sandbox.MetabrowserGitPath.wire));
  summaries["a file of a pinned revision"] = await rest(file("docs/guide.md"));
  summaries["a file the pinned revision lacks"] = await rest(file("docs/old-guide.md"));
  knownFiles = catalogOf(servedFiles);
  sourceKind = "filesystem";

  summaries["the pull request list"] = await rest({ kind: "pulls" });

  prefetches["a pull request"] = await prefetch(pull(12));
  prefetches["the same pull request again"] = await prefetch(pull(12, "files", "docs/guide.md"));
  prefetches["a stack"] = await prefetch(stack(286));
  prefetches["a commit the repository has"] = await prefetch({ kind: "commit", revision: commit });
  prefetches["a commit it lacks"] = await prefetch({ kind: "commit", revision: absent });
  prefetches["a file"] = await prefetch(file("docs/guide.md"));
  prefetches["a folder"] = await prefetch(folder("docs/"));
  prefetches["the served root"] = await prefetch(folder(""));
  sourceKind = "git_revision";
  prefetches["a file of a pinned revision"] = await prefetch(file("docs/guide.md"));
  sourceKind = "filesystem";
  repository = null;
  prefetches["a file, on a page with no GitHub repository"] = await prefetch(file("README.md"));
  repository = { host: "github.com", owner: "octo", name: "demo" };
  prefetches["the pull request list"] = await prefetch({ kind: "pulls" });

  // A rest that starts a commit's card and its prefetch together reads its detail once.
  asked = [];
  assets = [];
  const together = { kind: "commit", revision: recorded["first commit"].revision };
  const [summary] = await Promise.all([
    providers.get("commit").summary(together, { mb }),
    providers.get("commit").prefetch(together, { mb }),
  ]);
  await settle();
  const sharedRest = { subject: together, summary, asked, assets };

  console.log(
    JSON.stringify(
      {
        provided,
        summaries,
        prefetches,
        "a commit's card and prefetch together": sharedRest,
        requests: requests.map((entry) => entry.line),
        aborted: requests.filter((entry) => entry.aborted).map((entry) => entry.line),
      },
      null,
      2,
    ),
  );
}

run().catch((error) => {
  console.error(error);
  process.exit(1);
});

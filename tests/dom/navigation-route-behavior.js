// Pure contracts for the canonical /view/ NavigationTarget URL codec.

const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const repoRoot = path.resolve(process.argv[2] || path.join(__dirname, "../.."));
const failures = [];
// What the production module answered for each scenario, in run order. The golden
// transcript, tests/golden/cli-ui-navigation.tryscript.md, is the one authority for
// these values: it pins every one, and an intended change is made there, once. This
// file does not repeat them as inline expectations, because a second copy would only
// make the session exit before it printed what changed.
const observed = [];

function observe(name, value) {
  if (observed.some(([seen]) => seen === name)) {
    failures.push(`${name}: recorded twice`);
  }
  observed.push([name, JSON.stringify(value)]);
}

// A relation between two answers of the module, which the transcript shows only as
// two values a reader would have to compare. These stay inline, and one that breaks
// names itself before the transcript is read.
function invariant(name, actual, expected) {
  const actualJson = JSON.stringify(actual);
  const expectedJson = JSON.stringify(expected);
  if (actualJson !== expectedJson) {
    failures.push(`${name}: expected ${expectedJson}, got ${actualJson}`);
  }
}

// What a call that must be refused did: the error it threw, or what it returned.
function refusal(call) {
  try {
    return { returned: call() };
  } catch (error) {
    return `${error.name}: ${error.message}`;
  }
}

const sandbox = {
  console,
  Object,
  Array,
  String,
  Error,
  TypeError,
  URIError,
  atob,
  btoa,
  TextDecoder,
  TextEncoder,
  Uint8Array,
};
sandbox.window = sandbox;
sandbox.globalThis = sandbox;
vm.createContext(sandbox);

const sourcePath = path.join(repoRoot, "src/metabrowser/static/navigation.js");
const source = fs.readFileSync(sourcePath, "utf8");
vm.runInContext(source, sandbox, { filename: sourcePath });

const route = sandbox.MetabrowserNavigationRoute;
// The pull-request page's routes: an on-demand module the shell fetches only for an
// address under /pull/.
const pullSourcePath = path.join(repoRoot, "src/metabrowser/static/pull-route.js");
vm.runInContext(fs.readFileSync(pullSourcePath, "utf8"), sandbox, { filename: pullSourcePath });
const pullRoute = sandbox.MetabrowserPullRoute;
// The GitPath wire codec, a startup script on a pinned revision's shell only. It is
// loaded here after navigation.js to show that the order does not matter: displayPath
// looks for it when it is called.
const gitPathSourcePath = path.join(repoRoot, "src/metabrowser/static/git-path.js");
observe(
  "without the codec a wire shows as written",
  route.displayPath("g1-UkVBRE1FLm1k", "git_revision"),
);
vm.runInContext(fs.readFileSync(gitPathSourcePath, "utf8"), sandbox, {
  filename: gitPathSourcePath,
});
const gitPath = sandbox.MetabrowserGitPath;

observe(
  "slash-bearing Git ref gets one encoded revision segment",
  route.commitHref("refs/heads/main"),
);
observe("slash-bearing Git ref parses", route.parseCommit("/commit/refs%2Fheads%2Fmain"));
observe(
  "slash-bearing Git ref and inner path parse independently",
  route.parseCommit("/commit/refs%2Fheads%2Ffeature/src/app.py"),
);
for (const pathname of [
  "/commit/main/src%2Fapp.py",
  "/commit/main/src%5Capp.py",
  "/commit/main/src%00app.py",
]) {
  observe(`reject encoded separator in commit inner path ${pathname}`, route.parseCommit(pathname));
}
for (const [label, revision] of [
  ["an empty", ""],
  ["a dot-leading", ".bad"],
  ["a spaced", "bad ref"],
  ["an over-long", "x".repeat(257)],
]) {
  observe(
    `reject ${label} commit revision`,
    refusal(() => route.commitHref(revision)),
  );
}

observe("pull-request page href", pullRoute.pullHref(7));
observe("pull-request Files changed href", pullRoute.pullHref(7, "files"));
observe("pull-request page parses", pullRoute.parsePull("/pull/7"));
observe("pull-request tab parses with a trailing slash", pullRoute.parsePull("/pull/7/files/"));
for (const pathname of ["/pull/0", "/pull/07", "/pull/7/commits", "/pull/7/files/x", "/pull/x"]) {
  observe(`reject pull-request route ${pathname}`, pullRoute.parsePull(pathname));
}
for (const [number, tab] of [
  [0, ""],
  [7, "commits"],
]) {
  observe(
    `reject invalid pull-request href ${number}/${tab}`,
    refusal(() => pullRoute.pullHref(number, tab)),
  );
}

// History landing on a pull-request route: the shown page switches its tab; a page a
// commit or file replaced in the meantime is mounted again; a landing the navigation
// controller applies itself, because it held a /view/ target, is left to it.
observe(
  "back between a page's tabs switches the tab",
  pullRoute.pullHistoryAction("/pull/7/files", 7, false),
);
observe(
  "back onto a page whose pane a commit took mounts it",
  pullRoute.pullHistoryAction("/pull/7", null, false),
);
observe(
  "back onto another pull request's page mounts it",
  pullRoute.pullHistoryAction("/pull/7/files", 8, false),
);
observe(
  "back from a file view is the controller's",
  pullRoute.pullHistoryAction("/pull/7", null, true),
);
observe("back onto a view route is not a page's", pullRoute.pullHistoryAction("/view/", 7, false));

observe("root href", route.href({ path: "" }));
observe("folder href keeps its slash", route.href({ path: "docs/" }));
observe("path segments encode independently", route.href({ path: "docs/a b/%25 notes/雪.md" }));
observe(
  "query and fragment stay outside path identity",
  route.href({ path: "docs/a.md", query: "plain=1&x=a b", fragment: "A/B #1" }),
);

observe("parse root", route.parse("/view/", "", ""));
observe("parse folder", route.parse("/view/docs/", "", ""));
observe(
  "parse encoded path once",
  route.parse("/view/a%20b/%25%20notes/%E9%9B%AA.md", "?plain=1&x=a%20b", "#A%2FB%20%231"),
);
observe(
  "query escapes remain data rather than delimiters",
  route.href({ path: "docs/a.md", query: "value=a%26b&literal=%25" }),
);

// The reserved-namespace seam. `_mb_` query keys belong to Metabrowser and every other
// key belongs to the document, but no presentation parameter exists yet, so the codec
// must still treat the whole query as opaque data. Implementing the split means changing
// these three observations deliberately rather than discovering the change downstream.
// See docs/architecture.md#browser-url-grammar.
observe(
  "reserved keys are carried, not yet interpreted",
  route.parse("/view/docs/a.md", "?_mb_view=source&plain=1", ""),
);
observe(
  "a query round-trips losslessly through parse and href",
  route.href(route.parse("/view/docs/a.md", "?_mb_view=source&plain=1", "#setup")),
);
// The seam's invariant: dropping reserved keys leaves the canonical content URL. It holds
// trivially while nothing is reserved, and must keep holding once parameters land.
observe(
  "stripping reserved keys yields the canonical content URL",
  route.href({ path: "docs/a.md" }),
);
observe("percent-looking data is not decoded twice", route.parse("/view/docs/a%252Fb.md", "", ""));

for (const [identity, url] of [
  ["100%25.md", "/view/100%25.md"],
  ["report%2520final.txt", "/view/report%2520final.txt"],
  ["d%251/雪.md", "/view/d%251/%E9%9B%AA.md"],
  ["bad%FF 雪%25.txt", "/view/bad%FF%20%E9%9B%AA%25.txt"],
  // A POSIX backslash is escaped `%5C` in the inventory; a literal `%5C` is `%255C`.
  ["a%5Cb.txt", "/view/a%5Cb.txt"],
  ["%255C.md", "/view/%255C.md"],
]) {
  observe(`native URL for ${identity}`, route.href({ path: identity }));
  observe(`identity from ${url}`, route.parse(url));
  invariant(`${identity} survives href and parse`, route.parse(route.href({ path: identity })), {
    path: identity,
  });
}
observe("display percent-looking filename literally", route.displayPath("a%2520%25.txt"));
observe("display a POSIX backslash name and a literal %5C", route.displayPath("a%5Cb/%255C.md"));
observe("display GitPath README wire", route.displayPath("g1-UkVBRE1FLm1k", "git_revision"));
observe(
  "display GitPath nested wire",
  route.displayPath("g1-ZG9jcw/g1-bm90ZS50eHQ", "git_revision"),
);
observe("display GitPath percent name", route.displayPath("g1-MTAwJS5odG1s", "git_revision"));
observe(
  "display GitPath nested percent name",
  route.displayPath("g1-ZG9jcw/g1-MTAwJS5tZA", "git_revision"),
);
observe("display GitPath one crumb of a wire", route.displayPath("g1-bm90ZS50eHQ", "git_revision"));
observe(
  "display GitPath patch container inner",
  route.displayPath("g1-Y2hhbmdlLnBhdGNo/src/app.py", "git_revision"),
);
observe(
  "display mixed filesystem path is not a GitPath wire",
  route.displayPath("docs/g1-UkVBRE1FLm1k"),
);
observe("display filesystem g1-looking filename literally", route.displayPath("g1-UkVBRE1FLm1k"));
// The encoder is the decoder's inverse, and the one place a page spells a wire.
for (const display of ["README.md", "docs/note.txt", "100%.html", "docs/雪.md", "a b/c?#.txt"]) {
  const shown = route.displayPath(gitPath.wire(display), "git_revision");
  observe(`GitPath wire of ${display} displays as it`, shown);
  invariant(`GitPath wire of ${display} displays as it`, shown, display);
}
observe("GitPath wire is one token per segment", gitPath.wire("src/app.py"));
observe("GitPath wire is unpadded base64url", gitPath.wire("a?>"));
observe(
  "GitPath wire of a name that is not UTF-8 is its bytes",
  gitPath.wire(Uint8Array.from([0x64, 0xe9, 0x2f, 0x66])),
);
for (const [label, bad] of [
  ["an empty path", ""],
  ["a leading slash", "/a"],
  ["a trailing slash", "a/"],
  ["an empty segment", "a//b"],
  ["no bytes", new Uint8Array(0)],
]) {
  observe(`${label} has no GitPath wire`, gitPath.wire(bad));
}
observe(
  "display filesystem g1-looking filename with explicit kind",
  route.displayPath("g1-UkVBRE1FLm1k", "filesystem"),
);
observe(
  "display invalid GitPath atom stays a wire token",
  route.displayPath("g1-!!!", "git_revision"),
);
observe(
  "display GitPath newline name replaces C0",
  route.displayPath("g1-bmV3CmxpbmUudHh0", "git_revision"),
);
observe("display GitPath invalid UTF-8 name", route.displayPath("g1-eP8udHh0", "git_revision"));
// A pin publishes node names already decoded, so `displayPath` is a codec for
// identities and not for names. Decoding a decoded name reads a tracked
// `g1-data` directory as a wire token, which is the trap the tree renderer
// steps around.
observe(
  "display a decoded Git name again is not idempotent",
  route.displayPath(route.displayPath("g1-ZzEtZGF0YQ", "git_revision"), "git_revision"),
);

sandbox.METABROWSER_PATH_ENCODING = "utf16";
for (const [identity, url] of [
  ["lone%D8%00.txt", "/view/lone%ED%A0%80.txt"],
  ["lone%DF%FF.txt", "/view/lone%ED%BF%BF.txt"],
  ["lone%D8%80.txt", "/view/lone%ED%A2%80.txt"],
  ["unicode\u0600.txt", "/view/unicode%D8%80.txt"],
]) {
  observe(`Windows native URL for ${identity}`, route.href({ path: identity }));
  invariant(
    `Windows ${identity} survives href and parse`,
    route.parse(route.href({ path: identity })),
    { path: identity },
  );
  observe(`Windows identity from ${url}`, route.parse(url));
}
// Windows reads a backslash as a separator, so no Windows identity holds one.
observe("Windows rejects an encoded backslash", route.parse("/view/a%5Cb.md"));
sandbox.METABROWSER_PATH_ENCODING = "bytes";
// A Git pin's wires and container inners never hold a backslash; only a served
// folder's inventory escapes one.
sandbox.METABROWSER_SOURCE_KIND = "git_revision";
observe(
  "a pin refuses an encoded backslash in a container inner",
  route.parse("/view/g1-YQ/x%5Cy"),
);
delete sandbox.METABROWSER_SOURCE_KIND;

for (const [name, pathname] of [
  ["unrelated route", "/api/tree"],
  ["missing canonical root slash", "/view"],
  ["malformed escape", "/view/a%2.md"],
  ["encoded slash", "/view/a%2Fb.md"],
  ["literal backslash", "/view/a\\b.md"],
  ["literal parent traversal", "/view/../secret.md"],
  ["encoded parent traversal", "/view/%2E%2E/secret.md"],
  ["encoded NUL", "/view/a%00b.md"],
  ["empty interior segment", "/view/docs//a.md"],
]) {
  observe(`reject ${name}`, route.parse(pathname, "", ""));
}

for (const [name, target] of [
  ["leading slash", { path: "/docs/a.md" }],
  ["dot segment", { path: "docs/./a.md" }],
  ["parent segment", { path: "docs/../a.md" }],
  ["backslash", { path: "docs\\a.md" }],
  ["NUL", { path: "docs/\0a.md" }],
]) {
  observe(
    `format rejects ${name}`,
    refusal(() => route.href(target)),
  );
}

function makeBrowser(pathname, search = "", hash = "") {
  const listeners = new Map();
  const writes = [];
  const location = { pathname, search, hash };
  function setUrl(value) {
    const parsed = new URL(value, "http://metabrowser.test");
    location.pathname = parsed.pathname;
    location.search = parsed.search;
    location.hash = parsed.hash;
  }
  const history = {
    pushState(_state, _unused, value) {
      writes.push(["push", value]);
      setUrl(value);
    },
    replaceState(_state, _unused, value) {
      writes.push(["replace", value]);
      setUrl(value);
    },
  };
  const eventTarget = {
    addEventListener(type, listener) {
      listeners.set(type, listener);
    },
    removeEventListener(type, listener) {
      if (listeners.get(type) === listener) {
        listeners.delete(type);
      }
    },
    dispatch(type) {
      listeners.get(type)?.({ type });
    },
  };
  return { eventTarget, history, listeners, location, setUrl, writes };
}

// The shell's pull-request page host, driven with the shell's own wiring: a claim of
// the pane disposes the page first (claimPreview), and a claim is current until the
// next one. Every pane, history, and page effect lands in one log.
function makePullShell(pathname) {
  const log = [];
  const location = { pathname };
  const mounts = [];
  let claims = 0;
  let host = null;
  function claimPane(owner) {
    host.dispose();
    claims += 1;
    log.push(`claim ${claims} (${owner})`);
    return claims;
  }
  host = pullRoute.createPullPageHost({
    claim: () => claimPane("pull-request"),
    isCurrent: (claim) => claim === claims,
    mount(claim, landing, open) {
      log.push(`mount /pull/${landing.number}${landing.tab ? `/${landing.tab}` : ""}`);
      let resolve;
      const rendered = new Promise((settle) => {
        resolve = settle;
      });
      mounts.push({ claim, open, resolve });
      return rendered;
    },
    pathname: () => location.pathname,
    pushHref(href) {
      location.pathname = href;
      log.push(`push ${href}`);
    },
  });
  const page = (number) => ({
    setTab: (tab) => log.push(`#${number} tab "${tab}"`),
    dispose: () => log.push(`#${number} disposed`),
  });
  const tick = () => new Promise((resolve) => setImmediate(resolve));
  return { claimPane, host, location, log, mounts, page, tick };
}

(async () => {
  {
    // A landing mounts the page; its tabs and back and forward switch the tab of the
    // page that holds the pane without claiming it again.
    const shell = makePullShell("/pull/7");
    const shown = shell.host.show({ number: 7, tab: "" });
    observe("a page is not shown while it mounts", shell.host.shown());
    shell.mounts[0].resolve(shell.page(7));
    observe("a mounted page opens", await shown);
    observe("the mounted page is shown", shell.host.shown());
    observe("a tab link opens the tab", await shell.mounts[0].open({ number: 7, tab: "files" }));
    observe(
      "the shown page's route opens without a push",
      await shell.host.open({ number: 7, tab: "files" }),
    );
    shell.location.pathname = "/pull/7";
    shell.host.onHistory("/pull/7", false);
    observe(
      "a landing the controller applies is left to it",
      shell.host.onHistory("/pull/7/files", true),
    );
    observe("a tab keeps the page and puts the tab in the URL", shell.log);
  }

  {
    // The page for a number the server does not serve links to the served one: opening
    // it puts that route in the URL and replaces the page.
    const shell = makePullShell("/pull/8/files");
    const first = shell.host.show({ number: 8, tab: "files" });
    shell.mounts[0].resolve(shell.page(8));
    await first;
    const served = shell.mounts[0].open({ number: 7, tab: "files" });
    shell.mounts[1].resolve(shell.page(7));
    observe("the served pull request's page opens", await served);
    observe("the served pull request's page replaces the other", shell.log);
    observe("the served pull request is shown", shell.host.shown());
  }

  {
    // A claim that lands while a page mounts supersedes it: the late page is disposed
    // and never shown. A second route while the first mounts claims again.
    const shell = makePullShell("/pull/7");
    const first = shell.host.show({ number: 7, tab: "" });
    const second = shell.host.show({ number: 7, tab: "files" });
    shell.mounts[0].resolve(shell.page(7));
    observe("a page a later route superseded is cancelled", await first);
    shell.claimPane("file");
    shell.mounts[1].resolve(shell.page(7));
    observe("a page a file claim superseded is cancelled", await second);
    observe("a superseded page is never shown", shell.host.shown());
    observe("superseded pages are disposed as they arrive", shell.log);
  }

  {
    // Once something else holds the pane, or no plugin mounted a page, the same route
    // mounts the page again instead of switching the tab of a page nobody sees.
    const shell = makePullShell("/pull/7");
    const shown = shell.host.show({ number: 7, tab: "" });
    shell.mounts[0].resolve(shell.page(7));
    await shown;
    shell.claimPane("commit");
    observe("a page another claim replaced is not shown", shell.host.shown());
    observe("back onto a replaced page mounts it", shell.host.onHistory("/pull/7", false));
    await shell.tick();
    shell.mounts[1].resolve(null);
    await shell.tick();
    observe("no plugin leaves no page shown", shell.host.shown());
    const again = shell.host.show({ number: 7, tab: "" });
    shell.mounts[2].resolve(shell.page(7));
    await again;
    observe("a replaced or unmounted page mounts again", shell.log);
  }

  {
    const browser = makeBrowser("/view/docs/start.md", "?plain=1", "#intro");
    const applied = [];
    const controller = route.createController({
      ...browser,
      apply(target, context) {
        applied.push([target, context]);
      },
    });
    const detachPublicNavigation = route.attachController(controller);
    observe(
      "public href uses the canonical codec",
      route.navigation.href({ path: "public path.md", fragment: "part" }),
    );
    await controller.start();
    observe("startup applies pathname route", applied[0][0]);
    observe("startup does not rewrite history", browser.writes);
    observe("public current reads controller state", route.navigation.current());

    await route.navigation.open({ path: "docs/next.md" });
    observe("user navigation pushes", browser.writes.at(-1));
    observe("path navigation reports a fetch boundary", applied.at(-1)[1].pathChanged);
    observe("latest navigation context is current", applied.at(-1)[1].isCurrent());

    controller.canonicalizePath("docs/next.md", true);
    observe("folder slash canonicalization replaces", browser.writes.at(-1));
    observe("canonical folder is current", controller.current());

    await controller.open({ path: "docs/next.md/", fragment: "details" });
    observe("same-file fragment gets a real URL", browser.writes.at(-1));
    observe("same-file fragment avoids a fetch boundary", applied.at(-1)[1].pathChanged);
    observe("superseded navigation context is stale", applied.at(-2)[1].isCurrent());

    browser.setUrl("/view/back.md#old");
    browser.eventTarget.dispatch("popstate");
    await new Promise((resolve) => setImmediate(resolve));
    observe("popstate restores from location", controller.current());

    browser.setUrl("/");
    browser.eventTarget.dispatch("popstate");
    await new Promise((resolve) => setImmediate(resolve));
    observe("back to landing clears target", controller.current());
    observe("landing callback receives null", applied.at(-1)[0]);

    controller.dispose();
    detachPublicNavigation();
    observe("dispose removes popstate", [...browser.listeners.keys()]);
  }

  {
    const browser = makeBrowser("/", "", "#README.md");
    const applied = [];
    const controller = route.createController({
      ...browser,
      apply(target) {
        applied.push(target);
      },
    });
    await controller.start();
    observe("a hash alone selects no file", controller.current());
    observe("a hash-only landing applies no target", applied);
    controller.dispose();
  }

  if (failures.length) {
    console.error(`navigation route FAILURES:\n- ${failures.join("\n- ")}`);
    process.exit(1);
  }
  // One observation a line, so a changed value is a one-line diff.
  const lines = observed.map(([name, value]) => `    ${JSON.stringify(name)}: ${value}`);
  console.log(`{\n  "observed": {\n${lines.join(",\n")}\n  }\n}`);
})().catch((error) => {
  console.error(error);
  process.exit(1);
});

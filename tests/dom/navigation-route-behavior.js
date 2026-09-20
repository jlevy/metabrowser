// Pure contracts for the canonical /view/ NavigationTarget URL codec.

const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const repoRoot = path.resolve(process.argv[2] || path.join(__dirname, "../.."));
const failures = [];
// Every distinct scenario this session verified, in first-run order. The
// golden pins the list, so removing a scenario changes the transcript.
const verified = [];

function check(name, condition, detail = "failed") {
  if (!verified.includes(name)) {
    verified.push(name);
  }
  if (!condition) {
    failures.push(`${name}: ${detail}`);
  }
}

function equal(name, actual, expected) {
  const actualJson = JSON.stringify(actual);
  const expectedJson = JSON.stringify(expected);
  check(name, actualJson === expectedJson, `expected ${expectedJson}, got ${actualJson}`);
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
  Uint8Array,
};
sandbox.window = sandbox;
sandbox.globalThis = sandbox;
vm.createContext(sandbox);

const sourcePath = path.join(repoRoot, "src/metabrowser/static/navigation.js");
const source = fs.readFileSync(sourcePath, "utf8");
vm.runInContext(source, sandbox, { filename: sourcePath });

const route = sandbox.MetabrowserNavigationRoute;

equal(
  "slash-bearing Git ref gets one encoded revision segment",
  route.commitHref("refs/heads/main"),
  "/commit/refs%2Fheads%2Fmain",
);
equal("slash-bearing Git ref parses", route.parseCommit("/commit/refs%2Fheads%2Fmain"), {
  revision: "refs/heads/main",
  file: "",
});
equal(
  "slash-bearing Git ref and inner path parse independently",
  route.parseCommit("/commit/refs%2Fheads%2Ffeature/src/app.py"),
  { revision: "refs/heads/feature", file: "src/app.py" },
);
for (const pathname of [
  "/commit/main/src%2Fapp.py",
  "/commit/main/src%5Capp.py",
  "/commit/main/src%00app.py",
]) {
  equal(
    `reject encoded separator in commit inner path ${pathname}`,
    route.parseCommit(pathname),
    null,
  );
}
for (const revision of ["", ".bad", "bad ref", "x".repeat(257)]) {
  let rejected = false;
  try {
    route.commitHref(revision);
  } catch (error) {
    rejected = error instanceof TypeError;
  }
  check(`reject invalid commit revision ${JSON.stringify(revision)}`, rejected);
}

equal("root href", route.href({ path: "" }), "/view/");
equal("folder href keeps its slash", route.href({ path: "docs/" }), "/view/docs/");
equal(
  "path segments encode independently",
  route.href({ path: "docs/a b/%25 notes/雪.md" }),
  "/view/docs/a%20b/%25%20notes/%E9%9B%AA.md",
);
equal(
  "query and fragment stay outside path identity",
  route.href({ path: "docs/a.md", query: "plain=1&x=a b", fragment: "A/B #1" }),
  "/view/docs/a.md?plain=1&x=a%20b#A%2FB%20%231",
);

equal("parse root", route.parse("/view/", "", ""), { path: "" });
equal("parse folder", route.parse("/view/docs/", "", ""), { path: "docs/" });
equal(
  "parse encoded path once",
  route.parse("/view/a%20b/%25%20notes/%E9%9B%AA.md", "?plain=1&x=a%20b", "#A%2FB%20%231"),
  { path: "a b/%25 notes/雪.md", query: "plain=1&x=a%20b", fragment: "A/B #1" },
);
equal(
  "query escapes remain data rather than delimiters",
  route.href({ path: "docs/a.md", query: "value=a%26b&literal=%25" }),
  "/view/docs/a.md?value=a%26b&literal=%25",
);

// The reserved-namespace seam. `_mb_` query keys belong to Metabrowser and every other
// key belongs to the document, but no presentation parameter exists yet, so the codec
// must still treat the whole query as opaque data. Implementing the split means changing
// these three assertions deliberately rather than discovering the change downstream.
// See docs/architecture.md#browser-url-grammar.
equal(
  "reserved keys are carried, not yet interpreted",
  route.parse("/view/docs/a.md", "?_mb_view=source&plain=1", ""),
  { path: "docs/a.md", query: "_mb_view=source&plain=1" },
);
equal(
  "a query round-trips losslessly through parse and href",
  route.href(route.parse("/view/docs/a.md", "?_mb_view=source&plain=1", "#setup")),
  "/view/docs/a.md?_mb_view=source&plain=1#setup",
);
// The seam's invariant: dropping reserved keys leaves the canonical content URL. It holds
// trivially while nothing is reserved, and must keep holding once parameters land.
equal(
  "stripping reserved keys yields the canonical content URL",
  route.href({ path: "docs/a.md" }),
  "/view/docs/a.md",
);
equal("percent-looking data is not decoded twice", route.parse("/view/docs/a%252Fb.md", "", ""), {
  path: "docs/a%252Fb.md",
});

for (const [identity, url] of [
  ["100%25.md", "/view/100%25.md"],
  ["report%2520final.txt", "/view/report%2520final.txt"],
  ["d%251/雪.md", "/view/d%251/%E9%9B%AA.md"],
  ["bad%FF 雪%25.txt", "/view/bad%FF%20%E9%9B%AA%25.txt"],
]) {
  equal(`native URL for ${identity}`, route.href({ path: identity }), url);
  equal(`identity from ${url}`, route.parse(url), { path: identity });
}
equal(
  "display percent-looking filename literally",
  route.displayPath("a%2520%25.txt"),
  "a%20%.txt",
);
equal(
  "display GitPath README wire",
  route.displayPath("g1-UkVBRE1FLm1k", "git_revision"),
  "README.md",
);
equal(
  "display GitPath nested wire",
  route.displayPath("g1-ZG9jcw/g1-bm90ZS50eHQ", "git_revision"),
  "docs/note.txt",
);
equal(
  "display GitPath percent name",
  route.displayPath("g1-MTAwJS5odG1s", "git_revision"),
  "100%.html",
);
equal(
  "display GitPath nested percent name",
  route.displayPath("g1-ZG9jcw/g1-MTAwJS5tZA", "git_revision"),
  "docs/100%.md",
);
equal(
  "display GitPath one crumb of a wire",
  route.displayPath("g1-bm90ZS50eHQ", "git_revision"),
  "note.txt",
);
equal(
  "display GitPath patch container inner",
  route.displayPath("g1-Y2hhbmdlLnBhdGNo/src/app.py", "git_revision"),
  "change.patch/src/app.py",
);
equal(
  "display mixed filesystem path is not a GitPath wire",
  route.displayPath("docs/g1-UkVBRE1FLm1k"),
  "docs/g1-UkVBRE1FLm1k",
);
equal(
  "display filesystem g1-looking filename literally",
  route.displayPath("g1-UkVBRE1FLm1k"),
  "g1-UkVBRE1FLm1k",
);
equal(
  "display filesystem g1-looking filename with explicit kind",
  route.displayPath("g1-UkVBRE1FLm1k", "filesystem"),
  "g1-UkVBRE1FLm1k",
);
equal(
  "display invalid GitPath atom stays a wire token",
  route.displayPath("g1-!!!", "git_revision"),
  "g1-!!!",
);
equal(
  "display GitPath newline name replaces C0",
  route.displayPath("g1-bmV3CmxpbmUudHh0", "git_revision"),
  "new\ufffdline.txt",
);
equal(
  "display GitPath invalid UTF-8 name",
  route.displayPath("g1-eP8udHh0", "git_revision"),
  "x\ufffd.txt",
);

sandbox.METABROWSER_PATH_ENCODING = "utf16";
for (const [identity, url] of [
  ["lone%D8%00.txt", "/view/lone%ED%A0%80.txt"],
  ["lone%DF%FF.txt", "/view/lone%ED%BF%BF.txt"],
  ["lone%D8%80.txt", "/view/lone%ED%A2%80.txt"],
  ["unicode\u0600.txt", "/view/unicode%D8%80.txt"],
]) {
  equal(`Windows native URL for ${identity}`, route.href({ path: identity }), url);
  equal(`Windows identity from ${url}`, route.parse(url), { path: identity });
}
sandbox.METABROWSER_PATH_ENCODING = "bytes";

for (const [name, pathname] of [
  ["unrelated route", "/api/tree"],
  ["missing canonical root slash", "/view"],
  ["malformed escape", "/view/a%2.md"],
  ["encoded slash", "/view/a%2Fb.md"],
  ["encoded backslash", "/view/a%5Cb.md"],
  ["literal backslash", "/view/a\\b.md"],
  ["literal parent traversal", "/view/../secret.md"],
  ["encoded parent traversal", "/view/%2E%2E/secret.md"],
  ["encoded NUL", "/view/a%00b.md"],
  ["empty interior segment", "/view/docs//a.md"],
]) {
  equal(`reject ${name}`, route.parse(pathname, "", ""), null);
}

for (const [name, target] of [
  ["leading slash", { path: "/docs/a.md" }],
  ["dot segment", { path: "docs/./a.md" }],
  ["parent segment", { path: "docs/../a.md" }],
  ["backslash", { path: "docs\\a.md" }],
  ["NUL", { path: "docs/\0a.md" }],
]) {
  let rejected = false;
  try {
    route.href(target);
  } catch (error) {
    rejected = error instanceof TypeError;
  }
  check(`format rejects ${name}`, rejected);
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

(async () => {
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
    equal(
      "public href uses the canonical codec",
      route.navigation.href({ path: "public path.md", fragment: "part" }),
      "/view/public%20path.md#part",
    );
    await controller.start();
    equal("startup applies pathname route", applied[0][0], {
      path: "docs/start.md",
      query: "plain=1",
      fragment: "intro",
    });
    equal("startup does not rewrite history", browser.writes, []);
    equal("public current reads controller state", route.navigation.current(), {
      path: "docs/start.md",
      query: "plain=1",
      fragment: "intro",
    });

    await route.navigation.open({ path: "docs/next.md" });
    equal("user navigation pushes", browser.writes.at(-1), ["push", "/view/docs/next.md"]);
    check("path navigation reports a fetch boundary", applied.at(-1)[1].pathChanged === true);
    check("latest navigation context is current", applied.at(-1)[1].isCurrent());

    controller.canonicalizePath("docs/next.md", true);
    equal("folder slash canonicalization replaces", browser.writes.at(-1), [
      "replace",
      "/view/docs/next.md/",
    ]);
    equal("canonical folder is current", controller.current(), { path: "docs/next.md/" });

    await controller.open({ path: "docs/next.md/", fragment: "details" });
    equal("same-file fragment gets a real URL", browser.writes.at(-1), [
      "push",
      "/view/docs/next.md/#details",
    ]);
    check("same-file fragment avoids a fetch boundary", applied.at(-1)[1].pathChanged === false);
    check("superseded navigation context is stale", applied.at(-2)[1].isCurrent() === false);

    browser.setUrl("/view/back.md#old");
    browser.eventTarget.dispatch("popstate");
    await new Promise((resolve) => setImmediate(resolve));
    equal("popstate restores from location", controller.current(), {
      path: "back.md",
      fragment: "old",
    });

    browser.setUrl("/");
    browser.eventTarget.dispatch("popstate");
    await new Promise((resolve) => setImmediate(resolve));
    equal("back to landing clears target", controller.current(), null);
    equal("landing callback receives null", applied.at(-1)[0], null);

    controller.dispose();
    detachPublicNavigation();
    check("dispose removes popstate", !browser.listeners.has("popstate"));
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
    equal("a hash alone selects no file", controller.current(), null);
    equal("a hash-only landing applies no target", applied, [null]);
    controller.dispose();
  }

  if (failures.length) {
    console.error(`navigation route FAILURES:\n- ${failures.join("\n- ")}`);
    process.exit(1);
  }
  console.log(JSON.stringify({ verified }, null, 2));
})().catch((error) => {
  console.error(error);
  process.exit(1);
});

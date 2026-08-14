// Pure contracts for the canonical /view/ NavigationTarget URL codec.

const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const repoRoot = path.resolve(process.argv[2]);
const failures = [];

function check(name, condition, detail = "failed") {
  if (!condition) {
    failures.push(`${name}: ${detail}`);
  }
}

function equal(name, actual, expected) {
  const actualJson = JSON.stringify(actual);
  const expectedJson = JSON.stringify(expected);
  check(name, actualJson === expectedJson, `expected ${expectedJson}, got ${actualJson}`);
}

const sandbox = { console, Object, Array, String, Error, TypeError, URIError };
sandbox.window = sandbox;
sandbox.globalThis = sandbox;
vm.createContext(sandbox);

const source = fs.readFileSync(path.join(repoRoot, "src/metabrowser/static/navigation.js"), "utf8");
vm.runInContext(source, sandbox, { filename: "navigation.js" });

const route = sandbox.MetabrowserNavigationRoute;

equal("root href", route.href({ path: "" }), "/view/");
equal("folder href keeps its slash", route.href({ path: "docs/" }), "/view/docs/");
equal(
  "path segments encode independently",
  route.href({ path: "docs/a b/% notes/雪.md" }),
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
  { path: "a b/% notes/雪.md", query: "plain=1&x=a%20b", fragment: "A/B #1" },
);
equal(
  "query escapes remain data rather than delimiters",
  route.href({ path: "docs/a.md", query: "value=a%26b&literal=%25" }),
  "/view/docs/a.md?value=a%26b&literal=%25",
);
equal("percent-looking data is not decoded twice", route.parse("/view/docs/a%252Fb.md", "", ""), {
  path: "docs/a%2Fb.md",
});

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

if (failures.length) {
  console.error(`navigation route FAILURES:\n- ${failures.join("\n- ")}`);
  process.exit(1);
}
console.log("navigation route OK");

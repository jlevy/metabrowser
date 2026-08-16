const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const repoRoot = path.resolve(process.argv[2]);
const fixture = JSON.parse(
  fs.readFileSync(path.join(repoRoot, "tests/fixtures/obsidian_wiki_resolution.json"), "utf8"),
);
const failures = [];

function equal(name, actual, expected) {
  const actualJson = JSON.stringify(actual);
  const expectedJson = JSON.stringify(expected);
  if (actualJson !== expectedJson) {
    failures.push(`${name}: expected ${expectedJson}, got ${actualJson}`);
  }
}

(async () => {
  const source = fs.readFileSync(
    path.join(repoRoot, "src/metabrowser/builtin_plugins/markdown/wiki_resolver.js"),
    "utf8",
  );
  const module = await import(
    `data:text/javascript;base64,${Buffer.from(source).toString("base64")}`
  );
  const navigationContext = {
    console,
    window: { location: { hash: "", pathname: "/view/", search: "" } },
  };
  vm.runInNewContext(
    fs.readFileSync(path.join(repoRoot, "src/metabrowser/static/navigation.js"), "utf8"),
    navigationContext,
  );

  equal("fixture schema", fixture.schema, "metabrowser-obsidian-wiki-resolution-v1");
  for (const testCase of fixture.cases) {
    const intent = { sourcePath: testCase.sourcePath || fixture.sourcePath, ...testCase.intent };
    const resolved = module.resolveWikiTarget(intent, fixture.completeSnapshot);
    equal(testCase.id, resolved, testCase.expected);
    if (testCase.canonicalUrl && resolved.status === "internal") {
      equal(
        `${testCase.id} canonical URL`,
        navigationContext.window.MetabrowserNavigationRoute.href(resolved),
        testCase.canonicalUrl,
      );
    }
  }

  const incomplete = { ...fixture.completeSnapshot, complete: false };
  equal(
    "incomplete unique basename stays pending",
    module.resolveWikiTarget(
      { sourcePath: "other/current.md", authoredTarget: "雪", action: "navigate" },
      incomplete,
    ),
    { status: "pending", reason: "catalog-incomplete" },
  );
  equal(
    "incomplete exact source-directory path resolves",
    module.resolveWikiTarget(
      { sourcePath: fixture.sourcePath, authoredTarget: "Note", action: "navigate" },
      incomplete,
    ),
    { status: "internal", path: "docs/Note.md" },
  );

  for (const [name, intent, snapshot] of [
    ["missing intent", null, fixture.completeSnapshot],
    [
      "invalid action",
      { sourcePath: fixture.sourcePath, authoredTarget: "Note", action: "launch" },
      fixture.completeSnapshot,
    ],
    [
      "unsafe source",
      { sourcePath: "../current.md", authoredTarget: "Note", action: "navigate" },
      fixture.completeSnapshot,
    ],
    [
      "invalid snapshot",
      { sourcePath: fixture.sourcePath, authoredTarget: "Note", action: "navigate" },
      null,
    ],
  ]) {
    let rejected = false;
    try {
      module.resolveWikiTarget(intent, snapshot);
    } catch (error) {
      rejected = error instanceof TypeError;
    }
    equal(`reject ${name}`, rejected, true);
  }

  if (failures.length) {
    console.error(`markdown wiki resolver FAILURES:\n- ${failures.join("\n- ")}`);
    process.exit(1);
  }
  console.log("markdown wiki resolver OK");
})().catch((error) => {
  console.error(error);
  process.exit(1);
});

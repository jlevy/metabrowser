const fs = require("node:fs");
const path = require("node:path");

const repoRoot = path.resolve(process.argv[2]);
const fixture = JSON.parse(
  fs.readFileSync(path.join(repoRoot, "tests/fixtures/markdown_link_targets.json"), "utf8"),
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
    path.join(repoRoot, "src/metabrowser/builtin_plugins/markdown/links.js"),
    "utf8",
  );
  const module = await import(
    `data:text/javascript;base64,${Buffer.from(source).toString("base64")}`
  );

  equal("fixture schema", fixture.schema, "metabrowser-markdown-link-targets-v1");
  for (const testCase of fixture.cases) {
    const intent = { sourcePath: fixture.sourcePath, ...testCase.intent };
    equal(testCase.id, module.resolveStandardTarget(intent), testCase.expected);
  }

  for (const [name, intent] of [
    ["missing intent", null],
    [
      "invalid syntax",
      { syntax: "wiki", sourcePath: "docs/a.md", authoredTarget: "b.md", action: "navigate" },
    ],
    [
      "invalid action",
      { syntax: "markdown", sourcePath: "docs/a.md", authoredTarget: "b.md", action: "launch" },
    ],
    [
      "unsafe source",
      { syntax: "markdown", sourcePath: "../a.md", authoredTarget: "b.md", action: "navigate" },
    ],
  ]) {
    let rejected = false;
    try {
      module.resolveStandardTarget(intent);
    } catch (error) {
      rejected = error instanceof TypeError;
    }
    equal(`reject ${name}`, rejected, true);
  }

  if (failures.length) {
    console.error(`markdown link resolver FAILURES:\n- ${failures.join("\n- ")}`);
    process.exit(1);
  }
  console.log("markdown link resolver OK");
})().catch((error) => {
  console.error(error);
  process.exit(1);
});

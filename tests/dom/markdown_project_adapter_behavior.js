const fs = require("node:fs");
const path = require("node:path");

const repoRoot = path.resolve(process.argv[2]);
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
    path.join(repoRoot, "src/metabrowser/builtin_plugins/markdown/project_adapters.js"),
    "utf8",
  );
  const module = await import(
    `data:text/javascript;base64,${Buffer.from(source).toString("base64")}`
  );

  const complete = (paths) => ({
    complete: true,
    files: paths.map((filePath) => ({ path: filePath })),
  });

  equal(
    "MkDocs published route",
    module.resolvePublishedRoute(
      { authoredTarget: "/guide/", resolvedPath: "guide/" },
      complete(["mkdocs.yml", "docs/guide.md"]),
    ),
    { adapter: "mkdocs", path: "docs/guide.md", status: "internal" },
  );
  equal(
    "Docusaurus docs route",
    module.resolvePublishedRoute(
      { authoredTarget: "/docs/setup", resolvedPath: "docs/setup" },
      complete(["docusaurus.config.ts", "docs/setup/index.md"]),
    ),
    { adapter: "docusaurus", path: "docs/setup/index.md", status: "internal" },
  );
  equal(
    "Jekyll published route",
    module.resolvePublishedRoute(
      { authoredTarget: "/about/", resolvedPath: "about/" },
      complete(["_config.yml", "_pages/about.md"]),
    ),
    { adapter: "jekyll", path: "_pages/about.md", status: "internal" },
  );
  equal(
    "exact repository target wins",
    module.resolvePublishedRoute(
      { authoredTarget: "/guide/", resolvedPath: "guide/" },
      complete(["mkdocs.yml", "guide/index.md", "docs/guide.md"]),
    ),
    null,
  );
  equal(
    "unconfigured repository does not adapt",
    module.resolvePublishedRoute(
      { authoredTarget: "/guide/", resolvedPath: "guide/" },
      complete(["docs/guide.md"]),
    ),
    null,
  );
  equal(
    "adapter collision is explicit",
    module.resolvePublishedRoute(
      { authoredTarget: "/guide/", resolvedPath: "guide/" },
      complete(["mkdocs.yml", "docs/guide.md", "docs/guide/index.md"]),
    ),
    {
      candidates: ["docs/guide.md", "docs/guide/index.md"],
      reason: "ambiguous-published-route",
      status: "ambiguous",
    },
  );
  equal(
    "configured incomplete catalog remains pending",
    module.resolvePublishedRoute(
      { authoredTarget: "/guide/", resolvedPath: "guide/" },
      { complete: false, files: [{ path: "mkdocs.yml" }] },
    ),
    { reason: "catalog-incomplete", status: "pending" },
  );
  equal(
    "ordinary relative link is not a published route",
    module.resolvePublishedRoute(
      { authoredTarget: "guide/", resolvedPath: "docs/guide/" },
      complete(["mkdocs.yml", "docs/guide.md"]),
    ),
    null,
  );

  if (failures.length) {
    console.error(`markdown project adapter FAILURES:\n- ${failures.join("\n- ")}`);
    process.exit(1);
  }
  console.log("markdown project adapter OK");
})().catch((error) => {
  console.error(error);
  process.exit(1);
});

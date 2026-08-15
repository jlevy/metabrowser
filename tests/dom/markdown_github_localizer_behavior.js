const fs = require("node:fs");
const path = require("node:path");

const repoRoot = path.resolve(process.argv[2]);
const failures = [];

function equal(name, actual, expected) {
  const actualJson = canonicalJson(actual);
  const expectedJson = canonicalJson(expected);
  if (actualJson !== expectedJson) {
    failures.push(`${name}: expected ${expectedJson}, got ${actualJson}`);
  }
}

function canonicalJson(value) {
  const keys = value && typeof value === "object" ? Object.keys(value).sort() : undefined;
  return JSON.stringify(value, keys);
}

(async () => {
  const source = fs.readFileSync(
    path.join(repoRoot, "src/metabrowser/builtin_plugins/markdown/github_localizer.js"),
    "utf8",
  );
  const module = await import(
    `data:text/javascript;base64,${Buffer.from(source).toString("base64")}`
  );
  const revision = "a".repeat(40);
  const context = {
    branch: "feature/navigation",
    host: "github.com",
    name: "docs",
    owner: "example",
    revision,
    served_prefix: "packages/handbook",
  };

  equal(
    "exact commit permalink",
    module.localizeGithubUrl(
      `https://github.com/example/docs/blob/${revision}/packages/handbook/guide.md#Install`,
      context,
    ),
    {
      fragment: "Install",
      localization: "revision",
      path: "guide.md",
      status: "internal",
    },
  );
  equal(
    "current branch with slash",
    module.localizeGithubUrl(
      "https://github.com/example/docs/tree/feature/navigation/packages/handbook/reference/?plain=1",
      context,
    ),
    {
      localization: "working-tree",
      path: "reference/",
      query: "plain=1",
      status: "internal",
    },
  );
  equal(
    "other commit remains external",
    module.localizeGithubUrl(
      `https://github.com/example/docs/blob/${"b".repeat(40)}/packages/handbook/guide.md`,
      context,
    ),
    null,
  );
  equal(
    "other repository remains external",
    module.localizeGithubUrl(
      `https://github.com/example/other/blob/${revision}/packages/handbook/guide.md`,
      context,
    ),
    null,
  );
  equal(
    "path outside served subdirectory remains external",
    module.localizeGithubUrl(`https://github.com/example/docs/blob/${revision}/README.md`, context),
    null,
  );
  equal(
    "tag-like reference remains external",
    module.localizeGithubUrl(
      "https://github.com/example/docs/blob/v1.2.3/packages/handbook/guide.md",
      context,
    ),
    null,
  );

  if (failures.length) {
    console.error(`markdown GitHub localizer FAILURES:\n- ${failures.join("\n- ")}`);
    process.exit(1);
  }
  console.log("markdown GitHub localizer OK");
})().catch((error) => {
  console.error(error);
  process.exit(1);
});

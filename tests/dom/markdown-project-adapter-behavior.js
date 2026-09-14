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

function throws(name, callback, message) {
  let error = null;
  try {
    callback();
  } catch (caught) {
    error = caught;
  }
  if (!(error instanceof TypeError) || !String(error.message).includes(message)) {
    failures.push(
      `${name}: expected TypeError containing ${JSON.stringify(message)}, got ${error}`,
    );
  }
}

(async () => {
  const source = fs.readFileSync(
    path.join(repoRoot, "src/metabrowser/builtin_plugins/markdown/project-adapters.js"),
    "utf8",
  );
  const module = await import(
    `data:text/javascript;base64,${Buffer.from(source).toString("base64")}`
  );
  const linksSource = fs.readFileSync(
    path.join(repoRoot, "src/metabrowser/builtin_plugins/markdown/links.js"),
    "utf8",
  );
  const links = await import(
    `data:text/javascript;base64,${Buffer.from(linksSource).toString("base64")}`
  );

  const complete = (paths) => ({
    complete: true,
    // Production catalog snapshots are canonical code-unit path order; keep
    // this direct resolver fixture on the same contract so binary lookups are
    // the behavior under test.
    files: [...paths].sort().map((filePath) => ({ path: filePath })),
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
    "incomplete catalog does not publish a currently unique derived route",
    module.resolvePublishedRoute(
      { authoredTarget: "/guide/", resolvedPath: "guide/" },
      {
        complete: false,
        files: complete(["mkdocs.yml", "docs/guide.md"]).files,
      },
    ),
    { reason: "catalog-incomplete", status: "pending" },
  );
  equal(
    "a truncated catalog settles an unproven derived route with an explanation",
    module.resolvePublishedRoute(
      { authoredTarget: "/guide/", resolvedPath: "guide/" },
      {
        complete: false,
        files: complete(["mkdocs.yml", "docs/guide.md"]).files,
        truncated: true,
      },
    ),
    { reason: "catalog-truncated", status: "unsupported" },
  );
  equal(
    "a truncated catalog keeps an exact target authoritative",
    module.resolvePublishedRoute(
      { authoredTarget: "/guide/", resolvedPath: "guide/" },
      {
        complete: false,
        files: complete(["guide/index.md", "mkdocs.yml"]).files,
        truncated: true,
      },
    ),
    null,
  );
  equal(
    "the later complete catalog can make that route ambiguous",
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
    "literal percent route keeps canonical inventory identity",
    module.resolvePublishedRoute(
      { authoredTarget: "/100%25/", resolvedPath: "100%25/" },
      complete(["mkdocs.yml", "docs/100%25.md"]),
    ),
    { adapter: "mkdocs", path: "docs/100%25.md", status: "internal" },
  );
  equal(
    "published route percent decoding happens exactly once",
    module.resolvePublishedRoute(
      { authoredTarget: "/100%252F/", resolvedPath: "100%252F/" },
      complete(["mkdocs.yml", "docs/100%252F.md", "docs/100%2F.md"]),
    ),
    { adapter: "mkdocs", path: "docs/100%252F.md", status: "internal" },
  );
  equal(
    "cross-adapter ambiguity uses raw UTF-16 code-unit order",
    module.resolvePublishedRoute(
      { authoredTarget: "/guide/", resolvedPath: "guide/" },
      complete(["mkdocs.yml", "_config.yml", "docs/guide.md", "_pages/guide.md"]),
    ),
    {
      candidates: ["_pages/guide.md", "docs/guide.md"],
      reason: "ambiguous-published-route",
      status: "ambiguous",
    },
  );
  equal(
    "dot segments in a published route resolve like the standard resolver",
    module.resolvePublishedRoute(
      { authoredTarget: "/a/../guide/", resolvedPath: "guide/" },
      complete(["mkdocs.yml", "docs/guide.md"]),
    ),
    { adapter: "mkdocs", path: "docs/guide.md", status: "internal" },
  );
  equal(
    "encoded dot segments resolve the same way",
    module.resolvePublishedRoute(
      { authoredTarget: "/./a/%2e%2e/guide/", resolvedPath: "guide/" },
      complete(["mkdocs.yml", "docs/guide.md"]),
    ),
    { adapter: "mkdocs", path: "docs/guide.md", status: "internal" },
  );
  equal(
    "ordinary relative link is not a published route",
    module.resolvePublishedRoute(
      { authoredTarget: "guide/", resolvedPath: "docs/guide/" },
      complete(["mkdocs.yml", "docs/guide.md"]),
    ),
    null,
  );
  const providerLongSource = `${"p".repeat(100_000)}.md`;
  const standardRoute = links
    .createTrustedStandardLinkResolutionContext(providerLongSource)
    .begin({
      action: "navigate",
      authoredTarget: "/guide/",
      sourcePath: providerLongSource,
      syntax: "markdown",
    })
    .step(1);
  equal("rooted standard resolution cannot inherit a provider-long source prefix", standardRoute, {
    done: true,
    pathVisits: 0,
    result: { status: "internal", path: "guide/" },
  });
  equal(
    "published adaptation accepts the exact bounded standard-resolution output",
    module.resolvePublishedRoute(
      { authoredTarget: "/guide/", resolvedPath: standardRoute.result.path },
      complete(["mkdocs.yml", "docs/guide.md"]),
    ),
    { adapter: "mkdocs", path: "docs/guide.md", status: "internal" },
  );
  equal(
    "non-published targets ignore provider-derived path shape",
    module.resolvePublishedRoute(
      { authoredTarget: "guide/", resolvedPath: { untrusted: true } },
      complete(["mkdocs.yml", "docs/guide.md"]),
    ),
    null,
  );

  let rejectedPathReads = 0;
  const unreadSnapshot = {
    complete: true,
    files: [
      Object.defineProperty({}, "path", {
        get() {
          rejectedPathReads += 1;
          return "mkdocs.yml";
        },
      }),
    ],
  };
  throws(
    "published adaptation rejects an unrelated provider-sized resolved path",
    () =>
      module.resolvePublishedRoute(
        { authoredTarget: "/guide/", resolvedPath: "p".repeat(16_384 * 3 + 1) },
        unreadSnapshot,
      ),
    "outside the authored-route envelope",
  );
  equal("rejected resolved paths perform no catalog reads", rejectedPathReads, 0);
  throws(
    "published adaptation rejects a bounded but mismatched resolved path",
    () =>
      module.resolvePublishedRoute(
        { authoredTarget: "/guide/", resolvedPath: "other/" },
        complete(["mkdocs.yml", "docs/guide.md"]),
      ),
    "does not match",
  );

  let largePathReads = 0;
  const largePaths = Array.from(
    { length: 300_000 },
    (_, index) => `generated/${String(index).padStart(6, "0")}.md`,
  );
  largePaths.push("docs/large-guide.md", "mkdocs.yml");
  largePaths.sort();
  const largeSnapshot = {
    complete: true,
    files: largePaths.map((filePath) =>
      Object.defineProperty({}, "path", {
        get() {
          largePathReads += 1;
          return filePath;
        },
      }),
    ),
  };
  equal(
    "300k catalog uses binary route lookup",
    module.resolvePublishedRoute(
      { authoredTarget: "/large-guide/", resolvedPath: "large-guide/" },
      largeSnapshot,
    ),
    { adapter: "mkdocs", path: "docs/large-guide.md", status: "internal" },
  );
  equal("300k route lookup path reads stay logarithmic", largePathReads < 256, true);

  const readsBeforeSharedContext = largePathReads;
  const sharedContext = module.createPublishedRouteResolutionContext(largeSnapshot);
  const readsAfterContextCreation = largePathReads;
  const sharedFirst = sharedContext.resolve({
    authoredTarget: "/large-guide/",
    resolvedPath: "large-guide/",
  });
  const readsAfterSharedFirst = largePathReads;
  for (let index = 0; index < 65; index += 1) {
    equal(
      `shared published context result ${index}`,
      sharedContext.resolve({
        authoredTarget: "/large-guide/",
        resolvedPath: "large-guide/",
      }),
      sharedFirst,
    );
  }
  equal(
    "snapshot context detects project configuration once with bounded lookup",
    readsAfterContextCreation - readsBeforeSharedContext < 256,
    true,
  );
  equal(
    "snapshot context memoizes route membership across repeated jobs",
    largePathReads,
    readsAfterSharedFirst,
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

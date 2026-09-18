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
    path.join(repoRoot, "src/metabrowser/builtin_plugins/markdown/wiki-resolver.js"),
    "utf8",
  );
  const module = await import(
    `data:text/javascript;base64,${Buffer.from(source).toString("base64")}`
  );
  const settle = (application, maxPathVisits = 256) => {
    let totalPathVisits = 0;
    while (true) {
      const step = application.step(maxPathVisits);
      totalPathVisits += step.pathVisits;
      equal("cooperative resolver step stays bounded", step.pathVisits <= maxPathVisits, true);
      if (step.done) {
        return { result: step.result, totalPathVisits };
      }
    }
  };
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

  const batchIntents = fixture.cases.map((testCase) => ({
    sourcePath: testCase.sourcePath || fixture.sourcePath,
    ...testCase.intent,
  }));
  const sharedFixtureContext = module.createWikiResolutionContext(fixture.completeSnapshot);
  const contextResults = batchIntents.map(
    (intent) => settle(sharedFixtureContext.begin(intent), 7).result,
  );
  const singleResults = batchIntents.map((intent) =>
    module.resolveWikiTarget(intent, fixture.completeSnapshot),
  );
  equal(
    "shared-context and single resolver results are byte-for-byte equal",
    contextResults,
    singleResults,
  );
  sharedFixtureContext.dispose();

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
  // A walk that stopped at the file cap is final, but files past the cap were
  // never indexed: a unique-looking fallback or an exact miss cannot be proven,
  // so the result is a terminal explanation instead of "Resolving…" forever.
  const truncated = { ...fixture.completeSnapshot, complete: false, truncated: true };
  equal(
    "truncated unique basename is final and explains the cap",
    module.resolveWikiTarget(
      { sourcePath: "other/current.md", authoredTarget: "雪", action: "navigate" },
      truncated,
    ),
    { status: "unsupported", reason: "catalog-truncated" },
  );
  equal(
    "truncated exact path still resolves",
    module.resolveWikiTarget(
      { sourcePath: fixture.sourcePath, authoredTarget: "Note", action: "navigate" },
      truncated,
    ),
    { status: "internal", path: "docs/Note.md" },
  );
  equal(
    "truncated explicit-path miss is not reported missing",
    module.resolveWikiTarget(
      { sourcePath: fixture.sourcePath, authoredTarget: "./Absent", action: "embed" },
      truncated,
    ),
    { status: "unsupported", reason: "catalog-truncated" },
  );
  // Files past the cap can only add candidates, so two indexed matches already
  // prove ambiguity; a truncated walk reports that instead of the cap.
  const truncatedAmbiguous = module.resolveWikiTarget(
    { sourcePath: "other/current.md", authoredTarget: "Duplicate", action: "navigate" },
    truncated,
  );
  const completeAmbiguous = module.resolveWikiTarget(
    { sourcePath: "other/current.md", authoredTarget: "Duplicate", action: "navigate" },
    fixture.completeSnapshot,
  );
  equal(
    "truncated fallback with several indexed candidates is already ambiguous",
    truncatedAmbiguous,
    completeAmbiguous,
  );
  equal("the ambiguous fixture has several candidates", completeAmbiguous.status, "ambiguous");
  let contradictoryCoverage = null;
  try {
    module.createWikiResolutionContext({ ...fixture.completeSnapshot, truncated: true });
  } catch (error) {
    contradictoryCoverage = error.name;
  }
  equal("a snapshot cannot be both complete and truncated", contradictoryCoverage, "TypeError");
  equal(
    "qualified target normalized to a leaf uses basename fallback",
    module.resolveWikiTarget(
      {
        action: "navigate",
        authoredTarget: "x/../Leaf",
        sourcePath: "docs/current.md",
      },
      {
        complete: true,
        files: [
          { basename: "Leaf.md", path: "a/Leaf.md" },
          { basename: "Leaf.md", path: "b/Leaf.md" },
        ],
      },
    ),
    {
      status: "ambiguous",
      reason: "ambiguous-target",
      candidateCount: 2,
      candidates: ["a/Leaf.md", "b/Leaf.md"],
    },
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

  let largePathReads = 0;
  const largePaths = Array.from(
    { length: 300_000 },
    (_, index) => `generated/${String(index).padStart(6, "0")}.md`,
  );
  largePaths.push("docs/Target.md", "else/UniqueTarget.md");
  largePaths.sort();
  const largeSnapshot = {
    complete: true,
    files: largePaths.map((filePath) =>
      Object.defineProperties(
        {},
        {
          basename: { value: filePath.slice(filePath.lastIndexOf("/") + 1) },
          path: {
            get() {
              largePathReads += 1;
              return filePath;
            },
          },
        },
      ),
    ),
  };
  equal(
    "300k exact wiki lookup",
    module.resolveWikiTarget(
      { sourcePath: "docs/current.md", authoredTarget: "./Target", action: "navigate" },
      largeSnapshot,
    ),
    { status: "internal", path: "docs/Target.md" },
  );
  equal("300k exact wiki path reads stay logarithmic", largePathReads < 64, true);

  const sharedPrefix = "p".repeat(15_000);
  const duplicateMembershipSnapshot = {
    complete: true,
    files: Array.from({ length: 1024 }, (_, index) => {
      const filePath = `${sharedPrefix}${String(index).padStart(4, "0")}.md`;
      return { basename: filePath, path: filePath };
    }),
  };
  const duplicateMembershipContext = module.createWikiResolutionContext(
    duplicateMembershipSnapshot,
  );
  const duplicateApplications = Array.from({ length: 100 }, () =>
    duplicateMembershipContext.begin({
      action: "navigate",
      authoredTarget: `/${sharedPrefix}missing`,
      sourcePath: "docs/current.md",
    }),
  );
  const duplicateDone = new Set();
  let duplicateMembershipWork = 0;
  while (duplicateDone.size < duplicateApplications.length) {
    for (const [index, application] of duplicateApplications.entries()) {
      if (duplicateDone.has(index)) {
        continue;
      }
      const step = application.step(4096);
      duplicateMembershipWork += step.pathVisits;
      equal("shared exact membership step stays bounded", step.pathVisits <= 4096, true);
      if (step.done) {
        duplicateDone.add(index);
        equal("shared exact membership result", step.result, {
          status: "missing",
          reason: "not-found",
        });
      }
    }
  }
  equal(
    "duplicate exact targets join one in-flight membership search",
    duplicateMembershipWork < 300_000,
    true,
  );
  duplicateMembershipContext.dispose();

  equal(
    "300k basename fallback",
    module.resolveWikiTarget(
      { sourcePath: "docs/current.md", authoredTarget: "UniqueTarget", action: "navigate" },
      largeSnapshot,
    ),
    { status: "internal", path: "else/UniqueTarget.md" },
  );
  const boundedContext = module.createWikiResolutionContext(largeSnapshot);
  const bounded = boundedContext.begin({
    sourcePath: "docs/current.md",
    authoredTarget: "NeverThere",
    action: "navigate",
  });
  let boundedStep = bounded.step(4096);
  equal("fallback step reports its exact path bound", boundedStep.pathVisits, 4096);
  equal("fallback remains pending between bounded steps", boundedStep.done, false);
  while (!boundedStep.done) {
    equal("fallback continuation honors path bound", boundedStep.pathVisits <= 4096, true);
    boundedStep = bounded.step(4096);
  }
  equal("bounded fallback result", boundedStep.result, {
    status: "missing",
    reason: "not-found",
  });
  equal("completed fallback step is terminal", bounded.step(4096), {
    done: true,
    pathVisits: 0,
    result: { status: "missing", reason: "not-found" },
  });
  boundedContext.dispose();

  const candidateOverflowContext = module.createWikiResolutionContext({
    complete: true,
    files: Array.from({ length: 4097 }, (_, index) => ({
      basename: "Same.md",
      path: `${String(index).padStart(4, "0")}/Same.md`,
    })),
  });
  const candidateOverflow = candidateOverflowContext.begin({
    sourcePath: "docs/current.md",
    authoredTarget: "Same",
    action: "navigate",
  });
  const overflowResult = candidateOverflow.step(500_000);
  equal("candidate overflow result", overflowResult.result, {
    status: "unsupported",
    reason: "too-many-candidates",
  });
  equal("candidate overflow remains terminal", candidateOverflow.step(1), {
    done: true,
    pathVisits: 0,
    result: { status: "unsupported", reason: "too-many-candidates" },
  });
  candidateOverflowContext.dispose();

  const disposableContext = module.createWikiResolutionContext(largeSnapshot);
  disposableContext.stepIndex(1);
  disposableContext.dispose();
  const readsAfterContextDispose = largePathReads;
  equal("disposed context index step is terminal", disposableContext.stepIndex(4096), {
    done: true,
    pathVisits: 0,
  });
  equal(
    "disposed context cannot rebuild retained index state",
    largePathReads,
    readsAfterContextDispose,
  );

  const previewPaths = Array.from(
    { length: 25 },
    (_, index) => `${String(index).padStart(2, "0")}/shared/Leaf.md`,
  ).sort();
  const previewResolution = module.resolveWikiTarget(
    { sourcePath: "docs/current.md", authoredTarget: "shared/Leaf", action: "navigate" },
    {
      complete: true,
      files: previewPaths.map((filePath) => ({ basename: "Leaf.md", path: filePath })),
    },
  );
  equal("qualified ambiguity reports exact candidate count", previewResolution.candidateCount, 25);
  equal(
    "qualified ambiguity retains only the ordered 20-item preview",
    previewResolution.candidates,
    previewPaths.slice(0, 20),
  );

  const hotPaths = Array.from(
    { length: 4096 },
    (_, index) => `vault/${String(index).padStart(4, "0")}/Leaf.md`,
  ).sort();
  const hotContext = module.createWikiResolutionContext({
    complete: true,
    files: hotPaths.map((filePath) => ({ basename: "Leaf.md", path: filePath })),
  });
  const firstHot = settle(
    hotContext.begin({
      action: "navigate",
      authoredTarget: "0000/Leaf",
      sourcePath: "docs/current.md",
    }),
  );
  equal("hot qualified bucket first lookup", firstHot.result, {
    status: "internal",
    path: "vault/0000/Leaf.md",
  });
  let promotionVisits = 0;
  let indexedHotVisits = 0;
  for (let index = 1; index <= 80; index += 1) {
    const settled = settle(
      hotContext.begin({
        action: "navigate",
        authoredTarget: `${String(index).padStart(4, "0")}/Leaf`,
        sourcePath: "docs/current.md",
      }),
    );
    if (index === 1) {
      promotionVisits = settled.totalPathVisits;
    } else {
      indexedHotVisits += settled.totalPathVisits;
    }
    equal(`hot qualified result ${index}`, settled.result, {
      status: "internal",
      path: `vault/${String(index).padStart(4, "0")}/Leaf.md`,
    });
  }
  equal(
    "second distinct target promotes with linear segment work",
    promotionVisits < 100_000,
    true,
  );
  equal(
    "later qualified targets reuse the segment trie instead of rescanning the bucket",
    indexedHotVisits < 5000,
    true,
  );
  const repeatedHot = settle(
    hotContext.begin({
      action: "navigate",
      authoredTarget: "0001/Leaf",
      sourcePath: "docs/current.md",
    }),
  );
  equal("repeated qualified target is memoized", repeatedHot.totalPathVisits, 0);
  hotContext.dispose();

  const smallBucketSegment = "s".repeat(15_000);
  const smallBucketPaths = Array.from(
    { length: 20 },
    (_, index) => `vault/${String(index).padStart(2, "0")}/${smallBucketSegment}/Leaf.md`,
  ).sort();
  const smallBucketContext = module.createWikiResolutionContext({
    complete: true,
    files: smallBucketPaths.map((filePath) => ({ basename: "Leaf.md", path: filePath })),
  });
  settle(
    smallBucketContext.begin({
      action: "navigate",
      authoredTarget: `00/${smallBucketSegment}/Leaf`,
      sourcePath: "docs/current.md",
    }),
  );
  const smallBucketPromotion = settle(
    smallBucketContext.begin({
      action: "navigate",
      authoredTarget: `01/${smallBucketSegment}/Leaf`,
      sourcePath: "docs/current.md",
    }),
  );
  equal("second distinct small-bucket target promotes", smallBucketPromotion.result, {
    status: "internal",
    path: smallBucketPaths[1],
  });
  let smallBucketIndexedWork = 0;
  for (let index = 2; index < smallBucketPaths.length; index += 1) {
    const resolved = settle(
      smallBucketContext.begin({
        action: "navigate",
        authoredTarget: `${String(index).padStart(2, "0")}/${smallBucketSegment}/Leaf`,
        sourcePath: "docs/current.md",
      }),
    );
    smallBucketIndexedWork += resolved.totalPathVisits;
    equal(`small-bucket indexed target ${index}`, resolved.result, {
      status: "internal",
      path: smallBucketPaths[index],
    });
  }
  equal(
    "small collision bucket avoids distinct-target times bucket rescans",
    // Each direct-ref verification walks the bounded query twice (trie descent
    // plus final boundary check), but never multiplies it by the 20 candidates.
    smallBucketIndexedWork < 600_000,
    true,
  );
  smallBucketContext.dispose();

  const providerOnlyPrefix = "a/".repeat(100_000);
  const providerDeepPaths = [
    `left/${providerOnlyPrefix}Leaf.md`,
    `right/${providerOnlyPrefix}Leaf.md`,
  ].sort();
  const providerDeepContext = module.createWikiResolutionContext({
    complete: true,
    files: providerDeepPaths.map((filePath) => ({ basename: "Leaf.md", path: filePath })),
  });
  settle(
    providerDeepContext.begin({
      action: "navigate",
      authoredTarget: "first-miss/Leaf",
      sourcePath: "docs/current.md",
    }),
    16_384,
  );
  const providerDeepPromotion = settle(
    providerDeepContext.begin({
      action: "navigate",
      authoredTarget: "second-miss/Leaf",
      sourcePath: "docs/current.md",
    }),
    16_384,
  );
  equal(
    "segment promotion ignores unreachable provider-only prefix depth",
    providerDeepPromotion.result,
    { status: "missing", reason: "not-found" },
  );
  equal(
    "provider-only prefix promotion stops at the authored-target envelope",
    // At most two candidate paths cross the reachable 3x-normalized target
    // window; the factor eight covers the charged scan, node, map, and summary
    // transitions without depending on the 200k provider-only prefix.
    providerDeepPromotion.totalPathVisits < (16_384 * 3 + 3) * 8,
    true,
  );
  providerDeepContext.dispose();

  const boundaryPaths = [
    ...Array.from(
      { length: 4096 },
      (_, index) => `vault/prefix${String(index).padStart(4, "0")}shared/Leaf.md`,
    ),
    "vault/good/shared/Leaf.md",
  ].sort();
  const boundaryContext = module.createWikiResolutionContext({
    complete: true,
    files: boundaryPaths.map((filePath) => ({ basename: "Leaf.md", path: filePath })),
  });
  settle(
    boundaryContext.begin({
      action: "navigate",
      authoredTarget: "prefix0000shared/Leaf",
      sourcePath: "docs/current.md",
    }),
  );
  const boundaryLookup = settle(
    boundaryContext.begin({
      action: "navigate",
      authoredTarget: "shared/Leaf",
      sourcePath: "docs/current.md",
    }),
  );
  equal("qualified suffix range enforces a segment boundary", boundaryLookup.result, {
    status: "internal",
    path: "vault/good/shared/Leaf.md",
  });
  equal(
    "segment-boundary promotion remains linear",
    boundaryLookup.totalPathVisits < 100_000,
    true,
  );
  const indexedBoundaryLookup = settle(
    boundaryContext.begin({
      action: "navigate",
      authoredTarget: "good/shared/Leaf",
      sourcePath: "docs/current.md",
    }),
  );
  equal("indexed qualified suffix preserves deeper segment lookup", indexedBoundaryLookup.result, {
    status: "internal",
    path: "vault/good/shared/Leaf.md",
  });
  equal(
    "indexed segment-boundary lookup is sublinear",
    indexedBoundaryLookup.totalPathVisits < 100,
    true,
  );
  boundaryContext.dispose();

  let maximumBucketReads = 0;
  const maximumBucketFiles = Array.from({ length: 500_000 }, (_, index) => {
    const filePath = `vault/${String(index).padStart(6, "0")}/Leaf.md`;
    return Object.defineProperties(
      {},
      {
        basename: { value: "Leaf.md" },
        path: {
          get() {
            maximumBucketReads += 1;
            return filePath;
          },
        },
      },
    );
  });
  const maximumBucketContext = module.createWikiResolutionContext({
    complete: true,
    files: maximumBucketFiles,
  });
  const maximumBucketLookup = maximumBucketContext.begin({
    action: "navigate",
    authoredTarget: "499999/Leaf",
    sourcePath: "docs/current.md",
  });
  let maximumBucketStep = maximumBucketLookup.step(16_384);
  let maximumBucketSteps = 1;
  let maximumBucketWork = maximumBucketStep.pathVisits;
  while (!maximumBucketStep.done) {
    equal("500k same-basename task is bounded", maximumBucketStep.pathVisits <= 16_384, true);
    maximumBucketStep = maximumBucketLookup.step(16_384);
    maximumBucketSteps += 1;
    maximumBucketWork += maximumBucketStep.pathVisits;
    // One entry read + seven basename code units + one bounded map operation is
    // 4.5M visits before the cold suffix comparison. The measured full shape is
    // 5,555,597 visits / 340 slices; keep a narrow structural allowance.
    if (maximumBucketSteps > 350) {
      throw new Error("500k same-basename lookup exceeded its linear work bound");
    }
  }
  equal("500k same-basename lookup completes correctly", maximumBucketStep.result, {
    status: "internal",
    path: "vault/499999/Leaf.md",
  });
  equal("500k same-basename lookup has bounded total work", maximumBucketWork < 5_600_000, true);
  equal("500k same-basename catalog reads remain one-pass", maximumBucketReads < 500_100, true);
  const maximumPromotion = maximumBucketContext.begin({
    action: "navigate",
    authoredTarget: "499998/Leaf",
    sourcePath: "docs/current.md",
  });
  let maximumPromotionStep = maximumPromotion.step(16_384);
  let maximumPromotionSteps = 1;
  let maximumPromotionWork = maximumPromotionStep.pathVisits;
  while (!maximumPromotionStep.done) {
    equal("500k promotion task is bounded", maximumPromotionStep.pathVisits <= 16_384, true);
    maximumPromotionStep = maximumPromotion.step(16_384);
    maximumPromotionSteps += 1;
    maximumPromotionWork += maximumPromotionStep.pathVisits;
    if (maximumPromotionSteps > 320) {
      throw new Error("500k segment-trie promotion exceeded its linear work bound");
    }
  }
  equal("500k segment-trie promotion completes correctly", maximumPromotionStep.result, {
    status: "internal",
    path: "vault/499998/Leaf.md",
  });
  equal(
    "500k segment-trie promotion has bounded total work",
    maximumPromotionWork < 5_100_000,
    true,
  );
  const maximumIndexed = settle(
    maximumBucketContext.begin({
      action: "navigate",
      authoredTarget: "499997/Leaf",
      sourcePath: "docs/current.md",
    }),
  );
  equal("500k promoted lookup is sublinear", maximumIndexed.totalPathVisits < 100, true);
  equal("500k promoted lookup remains correct", maximumIndexed.result, {
    status: "internal",
    path: "vault/499997/Leaf.md",
  });
  maximumBucketContext.dispose();

  const commonDirectory = Array.from({ length: 96 }, (_, index) => `shared-${index}`).join("/");
  const longSuffixPaths = Array.from(
    { length: 4096 },
    (_, index) => `${String(index).padStart(4, "0")}/${commonDirectory}/Leaf.md`,
  ).sort();
  const longSuffixContext = module.createWikiResolutionContext({
    complete: true,
    files: longSuffixPaths.map((filePath) => ({ basename: "Leaf.md", path: filePath })),
  });
  const longSuffixLookup = longSuffixContext.begin({
    action: "navigate",
    authoredTarget: `4095/${commonDirectory}/Leaf`,
    sourcePath: "docs/current.md",
  });
  let longSuffixStep = longSuffixLookup.step(16_384);
  let longSuffixWork = longSuffixStep.pathVisits;
  while (!longSuffixStep.done) {
    longSuffixStep = longSuffixLookup.step(16_384);
    longSuffixWork += longSuffixStep.pathVisits;
    equal(
      "long common suffix step charges code-unit work",
      longSuffixStep.pathVisits <= 16_384,
      true,
    );
  }
  equal("long common suffix resolves correctly", longSuffixStep.result, {
    status: "internal",
    path: `4095/${commonDirectory}/Leaf.md`,
  });
  equal(
    "long common suffix total work is linear in compared input",
    longSuffixWork < 5_000_000,
    true,
  );
  longSuffixContext.dispose();

  const longCatalogPath = `${"very-long-segment/".repeat(1200)}tail/Deep.md`;
  equal(
    "catalog identities have no consumer-imposed length ceiling",
    module.resolveWikiTarget(
      { sourcePath: "docs/current.md", authoredTarget: "tail/Deep", action: "navigate" },
      {
        complete: true,
        files: [{ basename: "Deep.md", path: longCatalogPath }],
      },
    ),
    { status: "internal", path: longCatalogPath },
  );

  const unicodeCandidatePaths = ["\uE000/Unicode.md", "😀/Unicode.md"].sort();
  equal(
    "resolver preserves the catalog's raw UTF-16 candidate order",
    module.resolveWikiTarget(
      { sourcePath: "docs/current.md", authoredTarget: "Unicode", action: "navigate" },
      {
        complete: true,
        files: unicodeCandidatePaths.map((filePath) => ({
          basename: "Unicode.md",
          path: filePath,
        })),
      },
    ),
    {
      status: "ambiguous",
      reason: "ambiguous-target",
      candidateCount: 2,
      candidates: unicodeCandidatePaths,
    },
  );

  const differentialPaths = Array.from(
    { length: 1000 },
    (_, index) =>
      `vault/${String(index).padStart(4, "0")}/section-${index % 17}/group-${index % 37}/Leaf.md`,
  ).sort();
  const differentialContext = module.createWikiResolutionContext({
    complete: true,
    files: differentialPaths.map((filePath) => ({ basename: "Leaf.md", path: filePath })),
  });
  const differentialTargets = [
    ...Array.from({ length: 37 }, (_, index) => `group-${index}/Leaf`),
    ...Array.from({ length: 51 }, (_, index) => `section-${index % 17}/group-${index % 37}/Leaf`),
    ...Array.from({ length: 12 }, (_, index) => `missing-${index}/Leaf`),
  ];
  for (const authoredTarget of differentialTargets) {
    const lookup = `${authoredTarget}.md`;
    const matches = differentialPaths.filter(
      (filePath) => filePath === lookup || filePath.endsWith(`/${lookup}`),
    );
    const expected =
      matches.length === 0
        ? { status: "missing", reason: "not-found" }
        : matches.length === 1
          ? { status: "internal", path: matches[0] }
          : {
              status: "ambiguous",
              reason: "ambiguous-target",
              candidateCount: matches.length,
              candidates: matches.slice(0, 20),
            };
    equal(
      `qualified suffix differential ${authoredTarget}`,
      settle(
        differentialContext.begin({
          action: "navigate",
          authoredTarget,
          sourcePath: "docs/current.md",
        }),
      ).result,
      expected,
    );
  }
  differentialContext.dispose();

  const gitCurrent = "g1-ZG9jcw/g1-Y3VycmVudC5tZA";
  const gitNote = "g1-ZG9jcw/g1-bm90ZS50eHQ";
  const gitReadme = "g1-UkVBRE1FLm1k";
  const gitPercent = "g1-MTAwJS5odG1s";
  const gitSnapshot = {
    complete: true,
    files: [
      { basename: "100%.html", path: gitPercent },
      { basename: "README.md", path: gitReadme },
      { basename: "current.md", path: gitCurrent },
      { basename: "note.txt", path: gitNote },
    ],
  };
  const gitWikiCases = [
    {
      id: "git-basename-note",
      intent: { authoredTarget: "note.txt", action: "navigate", sourcePath: gitCurrent },
      expected: { status: "internal", path: gitNote },
      canonicalUrl: `/view/${gitNote}`,
    },
    {
      id: "git-relative-note",
      intent: { authoredTarget: "./note.txt", action: "navigate", sourcePath: gitCurrent },
      expected: { status: "internal", path: gitNote },
      canonicalUrl: `/view/${gitNote}`,
    },
    {
      id: "git-qualified-note",
      intent: { authoredTarget: "docs/note.txt", action: "navigate", sourcePath: gitCurrent },
      expected: { status: "internal", path: gitNote },
      canonicalUrl: `/view/${gitNote}`,
    },
    {
      id: "git-rooted-readme",
      intent: { authoredTarget: "/README.md", action: "navigate", sourcePath: gitCurrent },
      expected: { status: "internal", path: gitReadme },
      canonicalUrl: `/view/${gitReadme}`,
    },
    {
      id: "git-percent-html",
      intent: { authoredTarget: "100%.html", action: "navigate", sourcePath: gitCurrent },
      expected: { status: "internal", path: gitPercent },
      canonicalUrl: `/view/${gitPercent}`,
    },
    {
      id: "git-qualified-miss",
      intent: { authoredTarget: "nested/note.txt", action: "navigate", sourcePath: gitCurrent },
      expected: { status: "missing", reason: "not-found" },
    },
  ];
  for (const testCase of gitWikiCases) {
    const resolved = module.resolveWikiTarget(testCase.intent, gitSnapshot);
    equal(testCase.id, resolved, testCase.expected);
    if (testCase.canonicalUrl && resolved.status === "internal") {
      equal(
        `${testCase.id} canonical URL`,
        navigationContext.window.MetabrowserNavigationRoute.href(resolved),
        testCase.canonicalUrl,
      );
    }
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

const path = require("node:path");
const { pathToFileURL } = require("node:url");

const repoRoot = path.resolve(process.argv[2]);
const failures = [];
function check(name, condition, detail = "failed") {
  if (!condition) {
    failures.push(`${name}: ${detail}`);
  }
}

(async () => {
  const module = await import(
    pathToFileURL(path.join(repoRoot, "src/metabrowser/builtin_plugins/markdown/dom-traversal.js"))
      .href
  );
  let nextCalls = 0;
  let selectorCalls = 0;
  let queryCalls = 0;
  let treeWalkerFilter = "not-called";
  const nodes = Array.from({ length: 100_000 }, () => ({
    matches: () => {
      selectorCalls += 1;
      return false;
    },
  }));
  const document = {
    createTreeWalker(_root, whatToShow, filter) {
      check("TreeWalker uses SHOW_ELEMENT", whatToShow === 1);
      treeWalkerFilter = filter;
      let index = 0;
      return {
        nextNode() {
          nextCalls += 1;
          const node = nodes[index] || null;
          index += 1;
          return node;
        },
      };
    },
  };
  const container = {
    ownerDocument: document,
    querySelectorAll() {
      queryCalls += 1;
      throw new Error("production traversal must not materialize a NodeList");
    },
  };
  const budget = module.createMarkdownDomTraversalBudget();
  const matches = [...module.matchingDescendants(container, "[data-link]", budget)];
  check("real DOM traversal does not use querySelectorAll", queryCalls === 0);
  check("zero-match traversal yields nothing", matches.length === 0);
  check(
    "zero-match traversal stops at the hard aggregate visit ceiling",
    budget.state.visits === 16_384 &&
      nextCalls === 16_385 &&
      selectorCalls === 16_384 &&
      treeWalkerFilter === undefined,
    JSON.stringify({ nextCalls, selectorCalls, treeWalkerFilter, visits: budget.state.visits }),
  );
  const before = nextCalls;
  check(
    "shared exhausted budget admits no later traversal",
    [...module.matchingDescendants(container, "[id]", budget)].length === 0 &&
      nextCalls === before + 1,
  );

  if (failures.length) {
    console.error(`markdown DOM traversal FAILURES:\n- ${failures.join("\n- ")}`);
    process.exit(1);
  }
  console.log("markdown DOM traversal OK");
})().catch((error) => {
  console.error(error);
  process.exit(1);
});

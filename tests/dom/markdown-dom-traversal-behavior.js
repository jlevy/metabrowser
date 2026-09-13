const path = require("node:path");
const { pathToFileURL } = require("node:url");

const repoRoot = path.resolve(process.argv[2]);
const failures = [];
function check(name, condition, detail = "failed") {
  if (!condition) {
    failures.push(`${name}: ${detail}`);
  }
}

// CSS string unescaping for the one selector shape production builds.
function unescapeCssString(value) {
  return value
    .replace(/\\([0-9a-fA-F]{1,6}) ?/g, (_match, hex) =>
      String.fromCodePoint(Number.parseInt(hex, 16)),
    )
    .replace(/\\(.)/g, "$1");
}

// A document-shaped container: every element exists, most do not match, and
// queries charge nothing between calls, as native selectors do.
function fakeContainer(elements) {
  const calls = { querySelector: [], querySelectorAll: 0 };
  return {
    calls,
    querySelector(selector) {
      calls.querySelector.push(selector);
      const match = /^\[id="((?:[^"\\]|\\.)*)"\]$/s.exec(selector);
      if (!match) {
        throw new Error(`unexpected selector ${selector}`);
      }
      const id = unescapeCssString(match[1]);
      return elements.find((element) => element.id === id) || null;
    },
    querySelectorAll(selector) {
      calls.querySelectorAll += 1;
      if (selector !== "[data-link]") {
        throw new Error(`unexpected selector ${selector}`);
      }
      return elements.filter((element) => element.link);
    },
  };
}

(async () => {
  const module = await import(
    pathToFileURL(path.join(repoRoot, "src/metabrowser/builtin_plugins/markdown/dom-traversal.js"))
      .href
  );

  // 18,000 elements with the anchors and ids at the end: the shape that
  // exhausted the former cumulative visit budget after a few lookups.
  const elements = Array.from({ length: 18_000 }, (_, index) => ({
    id: index === 17_990 ? "last-section" : "",
    link: index >= 17_000 && index % 100 === 0,
  }));
  const container = fakeContainer(elements);

  const lookups = Array.from({ length: 25 }, () =>
    module.findElementById(container, "last-section"),
  );
  check(
    "repeated fragment lookups in a large document all find the target",
    lookups.every((element) => element === elements[17_990]),
    String(lookups.filter(Boolean).length),
  );

  const first = module.matchingDescendants(container, "[data-link]");
  const second = module.matchingDescendants(container, "[data-link]");
  check(
    "admission lookups do not consume one another",
    first.length === 10 && second.length === 10 && first[9] === elements[17_900],
    `${first.length}/${second.length}`,
  );
  const limited = module.matchingDescendants(container, "[data-link]", 3);
  check(
    "a limit keeps the document-order prefix",
    limited.length === 3 && limited[0] === elements[17_000] && limited[2] === elements[17_200],
    String(limited.length),
  );

  const authoredIds = [
    'say-"hi"',
    "back\\slash",
    "line\nbreak",
    "tab\tand space",
    "\u{1f600}-emoji",
  ];
  const idElements = authoredIds.map((id) => ({ id, link: false }));
  const idContainer = fakeContainer(idElements);
  check(
    "ids that need quoting are found exactly",
    authoredIds.every((id, index) => module.findElementById(idContainer, id) === idElements[index]),
    JSON.stringify(idContainer.calls.querySelector),
  );
  check("an empty fragment finds nothing", module.findElementById(idContainer, "") === null);

  if (failures.length) {
    console.error(`markdown DOM traversal FAILURES:\n- ${failures.join("\n- ")}`);
    process.exit(1);
  }
  console.log("markdown DOM traversal OK");
})().catch((error) => {
  console.error(error);
  process.exit(1);
});

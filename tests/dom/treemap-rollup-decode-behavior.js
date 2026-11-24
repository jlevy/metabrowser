// The compact rollup decoder (treemap-rollup-decode.js) against the route.
//
// Given the same folder's rollup in both encodings, as the route answered them
// (tests/test_treemap_rollup_decode.py serves it), the decoded compact body is
// the ordinary body: every node, key, and value, with a folder's children in
// any order, since the layout orders them by value. Then the decoder refuses
// each malformed entry instead of drawing part of a tree, and leaves a body in
// the ordinary encoding as it is.
// Usage: node treemap-rollup-decode-behavior.js <repo> <ordinary.json> <compact.json>...
// with any number of ordinary and compact pairs. Prints one summary line; exits 1
// on a failed check.

const fs = require("node:fs");
const path = require("node:path");
const { isDeepStrictEqual } = require("node:util");
const { pathToFileURL } = require("node:url");

const emitWarning = process.emitWarning;
process.emitWarning = (warning, ...rest) => {
  if (String(warning).includes("is not specified and it doesn't parse as CommonJS")) {
    return;
  }
  emitWarning.call(process, warning, ...rest);
};

const [repoArg, ...pairArgs] = process.argv.slice(2);
const repoRoot = path.resolve(repoArg || ".");
const failures = [];

function check(name, cond, detail) {
  if (!cond) {
    failures.push(`${name}: ${detail || "failed"}`);
  }
}

/** The node with every folder's children ordered by path, so order cannot differ. */
function canonical(node) {
  if (!node || typeof node !== "object") {
    return node;
  }
  const copy = { ...node };
  if (Array.isArray(copy.children)) {
    copy.children = copy.children
      .map(canonical)
      .sort((a, b) => (a.path < b.path ? -1 : a.path > b.path ? 1 : 0));
  }
  return copy;
}

/** The first path at which two values differ, for a readable failure. */
function firstDifference(a, b, at = "") {
  if (isDeepStrictEqual(a, b)) {
    return null;
  }
  if (!a || !b || typeof a !== "object" || typeof b !== "object") {
    return `${at || "/"}: ${JSON.stringify(a)?.slice(0, 120)} != ${JSON.stringify(b)?.slice(0, 120)}`;
  }
  for (const key of new Set([...Object.keys(a), ...Object.keys(b)])) {
    const found = firstDifference(a[key], b[key], `${at}/${key}`);
    if (found) {
      return found;
    }
  }
  return `${at || "/"}: differ`;
}

/** Every node in a tree. */
function* nodes(node) {
  yield node;
  for (const child of node.children ?? []) {
    yield* nodes(child);
  }
}

(async () => {
  const { decodeRollupEnvelope, CompactRollupError } = await import(
    pathToFileURL(
      path.join(repoRoot, "src/metabrowser/builtin_plugins/folder/treemap-rollup-decode.js"),
    ).href
  );

  check("given pairs", pairArgs.length > 0 && pairArgs.length % 2 === 0, String(pairArgs.length));
  let filesDecoded = 0;
  for (let i = 0; i + 1 < pairArgs.length; i += 2) {
    const ordinary = JSON.parse(fs.readFileSync(pairArgs[i], "utf8"));
    const compact = JSON.parse(fs.readFileSync(pairArgs[i + 1], "utf8"));
    const name = path.basename(pairArgs[i + 1]);
    const frozen = JSON.stringify(compact);
    check(`${name}: is compact`, compact.encoding === "compact", String(compact.encoding));
    check(`${name}: the ordinary body names no encoding`, !("encoding" in ordinary));
    const decoded = decodeRollupEnvelope(compact);
    check(`${name}: decoding leaves its input as it was`, JSON.stringify(compact) === frozen);
    const difference = firstDifference(
      { ...decoded, node: canonical(decoded.node) },
      { ...ordinary, node: canonical(ordinary.node) },
    );
    check(`${name}: decodes to the ordinary body`, difference === null, difference);
    const files = [...nodes(decoded.node)].filter((node) => node.type === "file");
    filesDecoded += files.length;
    check(
      `${name}: an ordinary body comes back as it is`,
      decodeRollupEnvelope(ordinary) === ordinary,
    );
  }

  check("the bodies hold files to decode", filesDecoded > 0, "no file nodes");

  /** The error decoding a body whose root holds `files`, or null when it decodes. */
  function refusal(files) {
    try {
      decodeRollupEnvelope({
        encoding: "compact",
        node: { name: "", path: "", type: "dir", children: [], files },
      });
      return null;
    } catch (error) {
      return error;
    }
  }
  const malformed = {
    "not a list": "a.py",
    "four fields": [["a.py", 1, null, ".py"]],
    "six fields": [["a.py", 1, null, ".py", 0, 0]],
    "an empty name": [["", 1, null, ".py", 0]],
    "a string size": [["a.py", "1", null, ".py", 0]],
    "a string mtime": [["a.py", 1, "0", ".py", 0]],
    "a null extension": [["a.py", 1, null, null, 0]],
    "a boolean ignored flag": [["a.py", 1, null, ".py", true]],
  };
  for (const [what, files] of Object.entries(malformed)) {
    const error = refusal(files);
    check(`refuses ${what}`, error instanceof CompactRollupError, String(error));
  }
  const decoded = decodeRollupEnvelope({
    encoding: "compact",
    node: { name: "", path: "", type: "dir", files: [["a.py", 3, null, ".py", 1]] },
  });
  check(
    "a root file has its name for a path, and a null mtime no key",
    isDeepStrictEqual(decoded.node.children, [
      { name: "a.py", path: "a.py", type: "file", size: 3, ext: ".py", gitignored: true },
    ]),
    JSON.stringify(decoded.node.children),
  );

  const unexpanded = decodeRollupEnvelope({
    encoding: "compact",
    node: {
      name: "",
      path: "",
      type: "dir",
      children: [{ name: "d", path: "d", type: "dir", children: null }],
      files: [],
    },
  });
  check(
    "an unexpanded folder keeps children: null",
    unexpanded.node.children[0].children === null,
    JSON.stringify(unexpanded.node),
  );

  if (failures.length > 0) {
    console.error(`treemap rollup decode FAILURES:\n- ${failures.join("\n- ")}`);
    process.exit(1);
  }
  console.log(`treemap rollup decode OK (${filesDecoded} files decoded)`);
})();

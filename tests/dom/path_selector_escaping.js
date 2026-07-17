// Behavioral check for app.js escapePathForSelector.
//
// The escaper embeds filesystem paths inside double-quoted CSS attribute
// selectors. Rather than asserting on output strings alone, this test
// round-trips: escape the path, then decode it with an independent
// implementation of CSS string-literal semantics (a backslash escapes the
// following character). If decode(escape(p)) !== p for any tricky path,
// live insert/update/remove selectors would silently stop matching.
// It also guards that every dynamic data-path selector in app.js routes
// through the one helper.

const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const repoRoot = path.resolve(__dirname, "../..");
const appSource = fs.readFileSync(path.join(repoRoot, "src/metabrowser/static/app.js"), "utf-8");

const failures = [];

// Extract the helper's source and evaluate it in isolation.
const match = appSource.match(/function escapePathForSelector\(path\) \{[\s\S]*?\n\}/);
if (!match) {
  failures.push("escapePathForSelector not found in app.js");
} else {
  const sandbox = {};
  vm.createContext(sandbox);
  vm.runInContext(`${match[0]}; result = escapePathForSelector;`, sandbox, {
    filename: "escapePathForSelector.js",
  });
  const escapePathForSelector = sandbox.result;

  // Independent decoder for the CSS quoted-string grammar: a backslash
  // escapes the next character (the only escapes the helper may emit are
  // \\ and \", both of which decode by dropping the backslash).
  function decodeCssString(value) {
    let out = "";
    for (let i = 0; i < value.length; i += 1) {
      const ch = value[i];
      if (ch === "\\") {
        i += 1;
        if (i >= value.length) {
          return null; // dangling escape — invalid selector string
        }
        out += value[i];
      } else if (ch === '"') {
        return null; // unescaped quote terminates the string early
      } else {
        out += ch;
      }
    }
    return out;
  }

  const trickyPaths = [
    "plain/file.txt",
    "back\\slash.txt",
    'quo"tation.txt',
    'mix\\"ed\\\\name',
    "trailing\\",
    'a"b\\c"d',
    "emoji-📁/nested name.txt",
  ];
  for (const original of trickyPaths) {
    const escaped = escapePathForSelector(original);
    const decoded = decodeCssString(escaped);
    if (decoded !== original) {
      failures.push(
        `round-trip failed for ${JSON.stringify(original)}: escaped=${JSON.stringify(
          escaped,
        )} decoded=${JSON.stringify(decoded)}`,
      );
    }
  }
}

// Guard: no dynamic data-path selector may bypass the helper with a local
// quote-only .replace escape.
const strayEscapes = appSource.match(/data-path="\$\{[^}]*\.replace\([^}]*\}/g);
if (strayEscapes && strayEscapes.length > 0) {
  failures.push(`data-path selectors bypass escapePathForSelector: ${strayEscapes.join(" | ")}`);
}

if (failures.length > 0) {
  console.error(JSON.stringify({ failures }, null, 2));
  process.exit(1);
}
console.log("path selector escaping OK");

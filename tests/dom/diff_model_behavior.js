// The browser side of the File Diff Format conformance corpus.
//
// Every validation case must be accepted or rejected exactly as the
// corpus says — the same file the Python tests run, which is the whole
// agreement mechanism between the two implementations.

const fs = require("node:fs");
const path = require("node:path");
const { pathToFileURL } = require("node:url");

const repoRoot = path.resolve(process.argv[2]);
const failures = [];

async function main() {
  const modelPath = path.join(repoRoot, "src/metabrowser/builtin_plugins/diff/diff_model.js");
  const { validateDocument, fileChangeLabel } = await import(pathToFileURL(modelPath).href);
  const corpus = JSON.parse(
    fs.readFileSync(
      path.join(repoRoot, "src/metabrowser/data/file-diff-format/file-diff-conformance.json"),
      "utf-8",
    ),
  );

  for (const testCase of corpus.cases) {
    const result = validateDocument(testCase.document);
    const expected = testCase.expect === "valid";
    if (result.ok !== expected) {
      failures.push(
        `${testCase.name}: expected ${testCase.expect}, got ` +
          (result.ok ? "valid" : `invalid (${result.error})`),
      );
    }
  }

  // Apply-case documents are valid documents too; the browser model must
  // accept everything the oracle can apply.
  for (const applyCase of corpus.apply_cases) {
    const result = validateDocument(applyCase.document);
    if (!result.ok) {
      failures.push(`${applyCase.name}: apply document rejected (${result.error})`);
    }
  }

  // The indicator labels the tree and list rows are built from.
  const rename = corpus.cases.find((entry) => entry.name === "rename-with-edit");
  const renameLabel = fileChangeLabel(rename.document.manifest.files[0]);
  if (renameLabel.letter !== "R87" || !renameLabel.label.includes("→")) {
    failures.push(`rename label wrong: ${JSON.stringify(renameLabel)}`);
  }
  const typeChanged = corpus.cases.find((entry) => entry.name === "type-changed-file-to-symlink");
  const typeLabel = fileChangeLabel(typeChanged.document.manifest.files[0]);
  if (!typeLabel.notes.includes("file→symlink") || !typeLabel.notes.includes("100644→120000")) {
    failures.push(`type-change notes wrong: ${JSON.stringify(typeLabel)}`);
  }

  if (failures.length > 0) {
    for (const failure of failures) {
      console.error(failure);
    }
    process.exit(1);
  }
  console.log(
    `diff model OK (${corpus.cases.length} validation cases, ${corpus.apply_cases.length} apply cases)`,
  );
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});

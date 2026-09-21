const fs = require("node:fs");
const path = require("node:path");
const { pathToFileURL } = require("node:url");

const repoRoot = path.resolve(process.argv[2]);

async function main() {
  const modelPath = path.join(
    repoRoot,
    "src/metabrowser/builtin_plugins/hosted_review/hosted-review-model.js",
  );
  const { parseChangeRequest } = await import(pathToFileURL(modelPath).href);
  const corpus = JSON.parse(
    fs.readFileSync(
      path.join(
        repoRoot,
        "src/metabrowser/data/hosted-review-format/change-request-conformance.json",
      ),
      "utf-8",
    ),
  );
  const failures = [];

  for (const testCase of corpus.cases) {
    const document = structuredClone(corpus.base_document);
    for (const change of testCase.changes) {
      let target = document;
      for (const part of change.path.slice(0, -1)) {
        target = target[part];
      }
      target[change.path.at(-1)] = change.value;
    }
    const result = parseChangeRequest(document);
    const expected = testCase.expect === "valid";
    if (result.ok !== expected) {
      failures.push(
        `${testCase.name}: expected ${testCase.expect}, got ${result.ok ? "valid" : result.error}`,
      );
    }
  }

  const defectiveInput = new Proxy(
    {},
    {
      ownKeys() {
        throw new Error("synthetic programming defect");
      },
    },
  );
  try {
    parseChangeRequest(defectiveInput);
    failures.push("unexpected parser defects must not be reported as invalid data");
  } catch (error) {
    if (!(error instanceof Error) || error.message !== "synthetic programming defect") {
      failures.push(`unexpected parser defect changed identity: ${String(error)}`);
    }
  }

  if (failures.length > 0) {
    for (const failure of failures) {
      console.error(failure);
    }
    process.exit(1);
  }
  console.log(`hosted review model OK (${corpus.cases.length} cases)`);
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});

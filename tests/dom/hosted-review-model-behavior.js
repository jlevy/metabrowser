const fs = require("node:fs");
const path = require("node:path");
const { pathToFileURL } = require("node:url");

const descriptors = JSON.parse(process.argv[2]);

function loadCorpus(corpusPath) {
  return JSON.parse(fs.readFileSync(corpusPath, "utf-8"));
}

function changedRecord(baseRecord, changes) {
  const record = structuredClone(baseRecord);
  for (const change of changes) {
    let target = record;
    for (const part of change.path.slice(0, -1)) {
      target = target[part];
    }
    target[change.path.at(-1)] = change.value;
  }
  return record;
}

function runCases({ corpus, parser, records = null, failures }) {
  for (const testCase of corpus.cases) {
    if (records !== null && !records.has(testCase.record)) {
      continue;
    }
    const baseRecord =
      testCase.record === undefined ? corpus.base_document : corpus.base_records[testCase.record];
    const result = parser(changedRecord(baseRecord, testCase.changes));
    const expected = testCase.expect === "valid";
    if (result.ok !== expected) {
      failures.push(
        `${testCase.name}: expected ${testCase.expect}, got ${result.ok ? "valid" : result.error}`,
      );
    }
  }
}

async function main() {
  const failures = [];
  const modules = new Map();
  const families = [];

  for (const descriptor of descriptors) {
    const modulePath = path.resolve(descriptor.browser_module_path);
    let model = modules.get(modulePath);
    if (model === undefined) {
      model = await import(pathToFileURL(modulePath).href);
      modules.set(modulePath, model);
    }
    families.push({
      contractId: descriptor.contract_id,
      corpus: loadCorpus(descriptor.corpus_path),
      parser: model[descriptor.browser_parser_export],
      records:
        descriptor.corpus_record_selectors.length === 0
          ? null
          : new Set(descriptor.corpus_record_selectors),
      expectedCaseCount: descriptor.expected_case_count,
    });
  }

  for (const family of families) {
    const selectedCaseCount = family.corpus.cases.filter(
      (testCase) => family.records === null || family.records.has(testCase.record),
    ).length;
    if (selectedCaseCount !== family.expectedCaseCount) {
      failures.push(`${family.contractId}: resolved corpus case count changed`);
    }
  }

  for (const family of families) {
    if (typeof family.parser !== "function") {
      failures.push(`${family.contractId}: declared browser parser export is missing`);
      continue;
    }
    runCases({ ...family, failures });
  }

  const defectiveInput = new Proxy(
    {},
    {
      ownKeys() {
        throw new Error("synthetic programming defect");
      },
    },
  );
  for (const family of families) {
    if (typeof family.parser !== "function") {
      continue;
    }
    try {
      family.parser(defectiveInput);
      failures.push("unexpected parser defects must not be reported as invalid data");
    } catch (error) {
      if (!(error instanceof Error) || error.message !== "synthetic programming defect") {
        failures.push(`unexpected parser defect changed identity: ${String(error)}`);
      }
    }
  }

  if (failures.length > 0) {
    for (const failure of failures) {
      console.error(failure);
    }
    process.exit(1);
  }
  const caseCount = families.reduce(
    (count, family) =>
      count +
      family.corpus.cases.filter(
        (testCase) => family.records === null || family.records.has(testCase.record),
      ).length,
    0,
  );
  console.log(`hosted review model OK (${families.length} families, ${caseCount} cases)`);
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});

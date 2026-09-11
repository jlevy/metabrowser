// Browserless session for the document-width preference state machine.

const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const repoRoot = path.resolve(__dirname, "../..");
const settingsSource = fs.readFileSync(path.join(repoRoot, "src/metabrowser/settings.py"), "utf8");
const defaultMatch = settingsSource.match(/^DOC_MAX_CHARS_DEFAULT = (\d+)$/m);
if (!defaultMatch) {
  throw new Error("DOC_MAX_CHARS_DEFAULT is not a literal integer in settings.py");
}

const injectedDefault = Number(defaultMatch[1]);
const sandbox = {
  METABROWSER_SETTINGS: { DOC_MAX_CHARS_DEFAULT: injectedDefault },
  Number,
  Object,
};
sandbox.window = sandbox;
sandbox.globalThis = sandbox;
vm.createContext(sandbox);

const productionPath = path.join(repoRoot, "src/metabrowser/static/document-width.js");
vm.runInContext(fs.readFileSync(productionPath, "utf8"), sandbox, {
  filename: productionPath,
});

const width = sandbox.MetabrowserDocumentWidth;
const values = new Map();
const input = { value: "" };
const rootValues = new Map();
const root = {
  style: {
    setProperty(name, value) {
      rootValues.set(name, value);
    },
  },
};
const readPreference = (key) => values.get(key) ?? null;
const writes = [];
const writePreference = (key, value) => {
  values.set(key, value);
  writes.push({ key, value });
};

const freshProfile = width.readStored(readPreference);
values.set(width.KEY, "118");
const existingProfile = width.readStored(readPreference);
values.set(width.KEY, "not-a-number");
const malformedProfile = width.readStored(readPreference);

const liveValue = width.apply(87.6, true, { input, root, writePreference });
const liveState = {
  input: input.value,
  persisted: values.get(width.KEY),
  persistedWrites: writes.slice(),
  rootProperty: rootValues.get("--doc-max-chars"),
  value: liveValue,
};
const committedValue = width.apply(102, true, { input, root, writePreference });
const committedState = {
  input: input.value,
  persisted: values.get(width.KEY),
  persistedWrites: writes,
  rootProperty: rootValues.get("--doc-max-chars"),
  value: committedValue,
};

const result = {
  authority: {
    default: width.DEFAULT,
    injectedDefault,
    key: width.KEY,
    max: width.MAX,
    min: width.MIN,
  },
  bounds: {
    above: width.normalize(999),
    below: width.normalize(1),
    fractional: width.normalize(101.6),
  },
  storedProfiles: {
    existing: existingProfile,
    fresh: freshProfile,
    malformed: malformedProfile,
  },
  liveApply: liveState,
  committedApply: committedState,
};

const expected = {
  authority: {
    default: 102,
    injectedDefault: 102,
    key: "metabrowser.docMaxChars",
    max: 160,
    min: 40,
  },
  bounds: {
    above: 160,
    below: 40,
    fractional: 102,
  },
  storedProfiles: {
    existing: 118,
    fresh: 102,
    malformed: 102,
  },
  liveApply: {
    input: "88",
    persisted: "88",
    persistedWrites: [{ key: "metabrowser.docMaxChars", value: "88" }],
    rootProperty: "88",
    value: 88,
  },
  committedApply: {
    input: "102",
    persisted: "102",
    persistedWrites: [
      { key: "metabrowser.docMaxChars", value: "88" },
      { key: "metabrowser.docMaxChars", value: "102" },
    ],
    rootProperty: "102",
    value: 102,
  },
};

if (JSON.stringify(result) !== JSON.stringify(expected)) {
  throw new Error(`unexpected document-width session: ${JSON.stringify(result)}`);
}

console.log(JSON.stringify(result, null, 2));

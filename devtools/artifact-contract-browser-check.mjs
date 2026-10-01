import fs from "node:fs";
import { pathToFileURL } from "node:url";
import vm from "node:vm";

const descriptorPath = process.argv[2];
const descriptors = JSON.parse(fs.readFileSync(descriptorPath, "utf-8"));

const BROWSER_CAPABILITIES_SOURCE = String.raw`
(() => {
  "use strict";

  const BASE64_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";

  function utf8Bytes(value) {
    const text = String(value);
    const bytes = [];
    for (const symbol of text) {
      let codePoint = symbol.codePointAt(0);
      if (codePoint >= 0xd800 && codePoint <= 0xdfff) {
        codePoint = 0xfffd;
      }
      if (codePoint <= 0x7f) {
        bytes.push(codePoint);
      } else if (codePoint <= 0x7ff) {
        bytes.push(0xc0 | (codePoint >> 6), 0x80 | (codePoint & 0x3f));
      } else if (codePoint <= 0xffff) {
        bytes.push(
          0xe0 | (codePoint >> 12),
          0x80 | ((codePoint >> 6) & 0x3f),
          0x80 | (codePoint & 0x3f),
        );
      } else {
        bytes.push(
          0xf0 | (codePoint >> 18),
          0x80 | ((codePoint >> 12) & 0x3f),
          0x80 | ((codePoint >> 6) & 0x3f),
          0x80 | (codePoint & 0x3f),
        );
      }
    }
    return new Uint8Array(bytes);
  }

  class BrowserTextEncoder {
    get encoding() {
      return "utf-8";
    }

    encode(value = "") {
      return utf8Bytes(value);
    }

    encodeInto(value, destination) {
      if (!(destination instanceof Uint8Array)) {
        throw new TypeError("TextEncoder.encodeInto destination must be a Uint8Array");
      }
      const text = String(value);
      let read = 0;
      let written = 0;
      while (read < text.length) {
        const codePoint = text.codePointAt(read);
        const sourceWidth = codePoint > 0xffff ? 2 : 1;
        const bytes = utf8Bytes(text.slice(read, read + sourceWidth));
        if (written + bytes.length > destination.length) {
          break;
        }
        destination.set(bytes, written);
        read += sourceWidth;
        written += bytes.length;
      }
      return { read, written };
    }
  }

  function decodedInput(value) {
    if (value === undefined) {
      return new Uint8Array();
    }
    if (value instanceof ArrayBuffer) {
      return new Uint8Array(value);
    }
    if (ArrayBuffer.isView(value)) {
      return new Uint8Array(value.buffer, value.byteOffset, value.byteLength);
    }
    throw new TypeError("TextDecoder input must be an ArrayBuffer or an ArrayBuffer view");
  }

  function decodeUtf8(bytes, fatal) {
    let result = "";
    let offset = 0;
    let bytesNeeded = 0;
    let bytesSeen = 0;
    let codePoint = 0;
    let lowerBoundary = 0x80;
    let upperBoundary = 0xbf;
    const invalid = () => {
      if (fatal) {
        throw new TypeError("invalid UTF-8 input");
      }
      result += "\ufffd";
    };
    const reset = () => {
      bytesNeeded = 0;
      bytesSeen = 0;
      codePoint = 0;
      lowerBoundary = 0x80;
      upperBoundary = 0xbf;
    };
    while (offset <= bytes.length) {
      if (offset === bytes.length) {
        if (bytesNeeded !== 0) {
          invalid();
        }
        break;
      }
      const first = bytes[offset];
      if (bytesNeeded === 0) {
        if (first <= 0x7f) {
          result += String.fromCodePoint(first);
          offset += 1;
          continue;
        }
        if (first >= 0xc2 && first <= 0xdf) {
          bytesNeeded = 1;
          codePoint = first & 0x1f;
        } else if (first >= 0xe0 && first <= 0xef) {
          bytesNeeded = 2;
          codePoint = first & 0x0f;
          if (first === 0xe0) {
            lowerBoundary = 0xa0;
          } else if (first === 0xed) {
            upperBoundary = 0x9f;
          }
        } else if (first >= 0xf0 && first <= 0xf4) {
          bytesNeeded = 3;
          codePoint = first & 0x07;
          if (first === 0xf0) {
            lowerBoundary = 0x90;
          } else if (first === 0xf4) {
            upperBoundary = 0x8f;
          }
        } else {
          invalid();
        }
        offset += 1;
        continue;
      }
      if (first < lowerBoundary || first > upperBoundary) {
        invalid();
        reset();
        continue;
      }
      lowerBoundary = 0x80;
      upperBoundary = 0xbf;
      codePoint = (codePoint << 6) | (first & 0x3f);
      bytesSeen += 1;
      offset += 1;
      if (bytesSeen === bytesNeeded) {
        result += String.fromCodePoint(codePoint);
        reset();
      }
    }
    return result;
  }

  class BrowserTextDecoder {
    #fatal;
    #ignoreBOM;

    constructor(label = "utf-8", options = {}) {
      const normalized = String(label).trim().toLowerCase();
      if (!new Set(["utf-8", "utf8", "unicode-1-1-utf-8"]).has(normalized)) {
        throw new RangeError("browser evidence TextDecoder supports UTF-8 only");
      }
      this.#fatal = Boolean(options.fatal);
      this.#ignoreBOM = Boolean(options.ignoreBOM);
    }

    get encoding() {
      return "utf-8";
    }

    get fatal() {
      return this.#fatal;
    }

    get ignoreBOM() {
      return this.#ignoreBOM;
    }

    decode(value, options = {}) {
      if (options.stream) {
        throw new TypeError("browser evidence TextDecoder does not support streaming");
      }
      let decoded = decodeUtf8(decodedInput(value), this.#fatal);
      if (!this.#ignoreBOM && decoded.codePointAt(0) === 0xfeff) {
        decoded = decoded.slice(1);
      }
      return decoded;
    }
  }

  function browserAtob(value) {
    let input = String(value).replace(/[\t\n\f\r ]/g, "");
    if (input.length % 4 === 0) {
      input = input.replace(/==?$/, "");
    }
    if (input.length % 4 === 1 || /[^A-Za-z0-9+/]/.test(input)) {
      throw new TypeError("invalid base64 input");
    }
    let buffer = 0;
    let bitCount = 0;
    let output = "";
    for (const character of input) {
      buffer = (buffer << 6) | BASE64_ALPHABET.indexOf(character);
      bitCount += 6;
      while (bitCount >= 8) {
        bitCount -= 8;
        output += String.fromCharCode((buffer >> bitCount) & 0xff);
        buffer &= (1 << bitCount) - 1;
      }
    }
    return output;
  }

  function browserBtoa(value) {
    const input = String(value);
    let output = "";
    for (let offset = 0; offset < input.length; offset += 3) {
      const first = input.charCodeAt(offset);
      const second = offset + 1 < input.length ? input.charCodeAt(offset + 1) : 0;
      const third = offset + 2 < input.length ? input.charCodeAt(offset + 2) : 0;
      if (first > 0xff || second > 0xff || third > 0xff) {
        throw new TypeError("base64 input must contain only Latin-1 code units");
      }
      const group = (first << 16) | (second << 8) | third;
      output += BASE64_ALPHABET[(group >> 18) & 0x3f];
      output += BASE64_ALPHABET[(group >> 12) & 0x3f];
      output += offset + 1 < input.length ? BASE64_ALPHABET[(group >> 6) & 0x3f] : "=";
      output += offset + 2 < input.length ? BASE64_ALPHABET[group & 0x3f] : "=";
    }
    return output;
  }

  Object.defineProperties(globalThis, {
    TextEncoder: { value: BrowserTextEncoder },
    TextDecoder: { value: BrowserTextDecoder },
    atob: { value: browserAtob },
    btoa: { value: browserBtoa },
  });
  Object.freeze(BrowserTextEncoder.prototype);
  Object.freeze(BrowserTextEncoder);
  Object.freeze(BrowserTextDecoder.prototype);
  Object.freeze(BrowserTextDecoder);
  Object.freeze(browserAtob);
  Object.freeze(browserBtoa);
})();
`;

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

function selectedCases(corpus, selectors) {
  const selected = new Set(selectors);
  return corpus.cases.filter((testCase) =>
    selected.size === 0 ? !Object.hasOwn(testCase, "record") : selected.has(testCase.record),
  );
}

function parserResultProblem(result) {
  if (typeof result !== "object" || result === null || Array.isArray(result)) {
    return "parser result must be an object";
  }
  const keys = Reflect.ownKeys(result);
  if (keys.some((key) => typeof key !== "string")) {
    return "parser result has a non-string field";
  }
  if (result.ok === true) {
    if (keys.length !== 2 || !keys.includes("ok") || !keys.includes("value")) {
      return "successful parser result must contain exactly ok and value";
    }
    if (typeof result.value !== "object" || result.value === null || Array.isArray(result.value)) {
      return "successful parser result value must be an object";
    }
    return null;
  }
  if (result.ok === false) {
    if (keys.length !== 2 || !keys.includes("ok") || !keys.includes("error")) {
      return "failed parser result must contain exactly ok and error";
    }
    if (typeof result.error !== "string" || result.error.length === 0) {
      return "failed parser result error must be a nonempty string";
    }
    return null;
  }
  return "parser result ok must be true or false";
}

function sameJsonValue(left, right) {
  if (typeof left !== typeof right) {
    return false;
  }
  if (left === null || right === null || typeof left !== "object") {
    return Object.is(left, right);
  }
  if (Array.isArray(left) !== Array.isArray(right)) {
    return false;
  }
  const leftKeys = Reflect.ownKeys(left);
  const rightKeys = Reflect.ownKeys(right);
  if (
    leftKeys.length !== rightKeys.length ||
    leftKeys.some((key) => typeof key !== "string") ||
    rightKeys.some((key) => typeof key !== "string")
  ) {
    return false;
  }
  return leftKeys.every((key) => Object.hasOwn(right, key) && sameJsonValue(left[key], right[key]));
}

function contextJsonValue(context, value) {
  const json = JSON.stringify(value);
  return vm.runInContext(`JSON.parse(${JSON.stringify(json)})`, context, {
    filename: "metabrowser-browser-evidence-input.js",
  });
}

async function loadBrowserModule(descriptor) {
  const identifier = pathToFileURL(descriptor.module_path).href;
  const context = vm.createContext(vm.constants.DONT_CONTEXTIFY, {
    codeGeneration: { strings: false, wasm: false },
  });
  vm.runInContext(BROWSER_CAPABILITIES_SOURCE, context, {
    filename: "metabrowser-browser-capabilities.js",
  });
  const source = fs.readFileSync(descriptor.module_path, "utf-8");
  const module = new vm.SourceTextModule(source, {
    context,
    identifier,
  });
  await module.link((specifier) => {
    throw new Error(
      `browser parser module must be self-contained browser ESM; imports are forbidden: ${specifier}`,
    );
  });
  await module.evaluate();
  return { context, namespace: module.namespace };
}

async function main() {
  const failures = [];
  const modules = new Map();

  for (const descriptor of descriptors) {
    let loaded = modules.get(descriptor.module_path);
    if (loaded === undefined) {
      try {
        loaded = await loadBrowserModule(descriptor);
      } catch (error) {
        failures.push(`${descriptor.contract_id}: browser parser module failed: ${String(error)}`);
        continue;
      }
      modules.set(descriptor.module_path, loaded);
    }
    const parser = loaded.namespace[descriptor.export_name];
    if (typeof parser !== "function") {
      failures.push(
        `${descriptor.contract_id}: declared browser parser export ${descriptor.export_name} is missing`,
      );
      continue;
    }
    const corpus = JSON.parse(fs.readFileSync(descriptor.corpus_path, "utf-8"));
    const cases = selectedCases(corpus, descriptor.record_selectors);
    if (cases.length !== descriptor.expected_case_count) {
      failures.push(
        `${descriptor.contract_id}: expected ${descriptor.expected_case_count} selected cases, got ${cases.length}`,
      );
      continue;
    }
    for (const testCase of cases) {
      const baseRecord =
        testCase.record === undefined ? corpus.base_document : corpus.base_records[testCase.record];
      const expectedRecord = changedRecord(baseRecord, testCase.changes);
      const input = contextJsonValue(loaded.context, expectedRecord);
      let result;
      try {
        result = parser(input);
        if (!sameJsonValue(expectedRecord, input)) {
          failures.push(`${descriptor.contract_id}/${testCase.name}: parser mutated its input`);
        }
        const protocolProblem = parserResultProblem(result);
        if (protocolProblem !== null) {
          failures.push(`${descriptor.contract_id}/${testCase.name}: ${protocolProblem}`);
          continue;
        }
      } catch (error) {
        failures.push(`${descriptor.contract_id}/${testCase.name}: parser threw ${String(error)}`);
        continue;
      }
      const expected = testCase.expect === "valid";
      if (result.ok !== expected) {
        failures.push(
          `${descriptor.contract_id}/${testCase.name}: expected ${testCase.expect}, got ${result.ok ? "valid" : "invalid"}`,
        );
      }
      if (result.ok && !sameJsonValue(expectedRecord, result.value)) {
        failures.push(
          `${descriptor.contract_id}/${testCase.name}: successful parser result value must preserve its input record`,
        );
      }
    }
  }

  if (failures.length > 0) {
    for (const failure of failures) {
      console.error(failure);
    }
    process.exitCode = 1;
    return;
  }
  const caseCount = descriptors.reduce(
    (count, descriptor) => count + descriptor.expected_case_count,
    0,
  );
  console.log(`artifact browser evidence OK (${descriptors.length} parser(s), ${caseCount} cases)`);
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});

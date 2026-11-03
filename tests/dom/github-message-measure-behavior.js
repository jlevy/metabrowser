import assert from "node:assert/strict";
import { watchMessageMeasure } from "../../src/metabrowser/builtin_plugins/github/message-measure.js";

let fontSet = "clean";
let font = "system-ui";
let size = "15px";
let measurements = 0;
let disconnected = 0;
let callback;
const properties = new Map();
const root = { getAttribute: () => fontSet };
const host = {
  ownerDocument: {
    documentElement: root,
    createElement(kind) {
      assert.equal(kind, "canvas");
      return {
        getContext() {
          return {
            font: "",
            measureText(text) {
              measurements++;
              assert.match(this.font, /px system-ui/);
              return { width: text.length * Number.parseFloat(this.font) * 0.5 };
            },
          };
        },
      };
    },
  },
  style: {
    setProperty: (name, value) => properties.set(name, value),
    removeProperty: (name) => properties.delete(name),
  },
};
globalThis.getComputedStyle = (element) => {
  assert.equal(element, root);
  return { getPropertyValue: (name) => (name === "--prose-sans-font" ? font : size) };
};
globalThis.MutationObserver = class {
  constructor(update) {
    callback = update;
  }
  observe(element, options) {
    assert.equal(element, root);
    assert.deepEqual(options.attributeFilter, ["data-app-font", "style"]);
  }
  disconnect() {
    disconnected++;
  }
};
const dispose = watchMessageMeasure(host);
assert.equal(measurements, 0, "the calibrated clean font needs no canvas");
assert.equal(properties.size, 0);
fontSet = "system";
callback();
assert.equal(properties.get("--message-char-advance"), "0.5");
callback();
assert.equal(measurements, 1, "an unchanged font must reuse its measured advance");
fontSet = "clean";
callback();
assert.equal(properties.size, 0, "the clean font must recover its CSS calibration");
fontSet = "system";
callback();
assert.equal(properties.get("--message-char-advance"), "0.5");
assert.equal(measurements, 1);
font = "system-ui, sans-serif";
callback();
assert.equal(measurements, 2, "a changed font must be measured again");
size = "18px";
callback();
assert.equal(measurements, 3, "optical sizing requires measuring a changed prose size");
dispose();
assert.equal(disconnected, 1);
assert.equal(properties.size, 0);
console.log("clean calibration, system measurement, font changes, and disposal: pass");

import assert from "node:assert/strict";
import { createCopyButton } from "../../src/metabrowser/static/copy-button.js";
import dom from "./pulls-test-dom.js";
import sdk from "./sdk-sandbox.js";

const turn = () => new Promise(setImmediate);
for (const promised of [true, false]) {
  const writes = [];
  const feedbackTimers = [];
  let clicks = 0;
  const view = sdk.createSdkSandbox({ setTimeout: (callback) => feedbackTimers.push(callback) });
  view.navigator = {
    clipboard: {
      writeText(value) {
        writes.push(value);
        return Promise.resolve();
      },
    },
  };
  if (promised) {
    view.ClipboardItem = class {
      constructor(parts) {
        this.parts = parts;
      }
    };
    view.navigator.clipboard.write = async ([item]) => {
      clicks++;
      const blob = await item.parts["text/plain"];
      writes.push(await blob.text());
    };
  }

  const doc = { defaultView: view, createElement: (tag) => new dom.FakeElement(tag) };
  for (const cancel of [false, true]) {
    const lifetime = new AbortController();
    let resolve;
    const reading = new Promise((done) => {
      resolve = done;
    });
    let readCount = 0;
    const btn = createCopyButton(
      doc,
      "Copy field",
      async (signal) => {
        assert.equal(signal, lifetime.signal);
        readCount++;
        return reading;
      },
      lifetime.signal,
    );
    assert.equal(btn.getAttribute("aria-label"), "Copy field");
    const before = writes.length;
    const started = clicks;
    btn.listeners.get("click")();
    btn.listeners.get("click")();
    assert.equal(readCount, 1);
    if (promised) {
      assert.equal(clicks, started + 1, "Clipboard.write must start during the original click");
    }
    assert.equal(writes.length, before);
    if (cancel) {
      lifetime.abort();
    }
    resolve('{ "name": "Ada" }\r\n');
    await turn();
    assert.equal(writes.length, before + (cancel ? 0 : 1));
    if (!cancel) {
      assert.equal(writes.at(-1), '{ "name": "Ada" }\r\n');
    }
    assert.equal(btn.dataset.tipText, cancel ? "Copy failed" : "Copied");
    feedbackTimers.pop()();
    assert.equal(btn.dataset.tipText, "Copy field");
  }
}

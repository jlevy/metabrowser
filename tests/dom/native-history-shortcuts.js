const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const { FakeDocument, keyEvent } = require("./key-reveal-dom.js");

const staticDir = path.resolve(__dirname, "../../src/metabrowser/static");
const sources = ["keyboard-shortcuts.js", "shell-keymap.js", "key-reveal.js"].map((file) => {
  const filename = path.join(staticDir, file);
  return { filename, text: fs.readFileSync(filename, "utf8") };
});
const firstUrl = "http://127.0.0.1:8457/pull/927";
const nextUrl = "http://127.0.0.1:8457/view/README.md#readme";

function load({ advertised, installed }) {
  const document = new FakeDocument();
  const messages = [];
  const window = { document, location: { href: firstUrl } };
  window.window = window;
  if (advertised) {
    window.metabrowserHost = { actions: ["navigation-history"] };
  }
  if (installed) {
    window.webkit = {
      messageHandlers: {
        metabrowserNavigation: {
          postMessage: (message) => messages.push({ ...message }),
        },
      },
    };
  }
  vm.createContext(window);
  for (const { filename, text } of sources) {
    vm.runInContext(text, window, { filename });
  }
  const shortcuts = window.MetabrowserKeyboardShortcuts.create({ document });
  const build = () =>
    window.MetabrowserShellKeymap.createShellKeymap({
      shell: { navToggle: () => null },
      shortcuts,
    });
  const keymap = build();
  let timer;
  const reveal = window.MetabrowserKeyReveal.createKeyReveal({
    cancel: () => {
      timer = undefined;
    },
    document,
    schedule: (callback) => {
      timer = callback;
      return 1;
    },
    shortcuts,
  });
  function key(name, options, type = "keydown") {
    const event = keyEvent(type, name, options);
    document.activeElement.dispatchEvent(event);
    return event.defaultPrevented;
  }
  return {
    build,
    document,
    key,
    keymap,
    messages,
    reveal,
    showBadges: () => timer(),
    shortcuts,
    window,
  };
}

for (const page of [load({ installed: true }), load({ advertised: true }), load({})]) {
  assert.equal(page.window.MetabrowserNativeNavigation, undefined);
  assert.equal(page.shortcuts.present("shell.history-back"), null);
  assert.equal(page.key("["), false);
  assert.deepEqual(page.messages, []);
}

const page = load({ advertised: true, installed: true });
const { document, key, keymap, messages, reveal, shortcuts, window } = page;
const bridge = window.MetabrowserNativeNavigation;
const traffic = [];
function takeMessages() {
  const batch = messages.splice(0);
  traffic.push(...batch);
  return batch;
}
assert.deepEqual(takeMessages(), [{ kind: "state", url: firstUrl }]);
assert.equal(key("["), false);
bridge.setState({ back: true, forward: false });
assert.equal(key("["), true);
assert.equal(key("]"), false);
assert.deepEqual(takeMessages(), [{ kind: "history", direction: "back", url: firstUrl }]);

for (const guard of ["shiftKey", "ctrlKey", "metaKey", "altKey", "repeat", "isComposing"]) {
  assert.equal(key("[", { [guard]: true }), false, guard);
}
assert.equal(key("{", { code: "BracketLeft", shiftKey: true }), false);
key("[", { defaultPrevented: true });
const field = document.createElement("input");
document.body.append(field);
field.focus();
assert.equal(key("["), false);
document.body.focus();
const closeModal = shortcuts.activateScope("modal", { exclusive: true });
assert.equal(key("["), false);
closeModal();
assert.deepEqual(takeMessages(), []);

window.location.href = nextUrl;
bridge.setState({ back: false, forward: true });
assert.equal(key("["), false);
assert.equal(key("]"), true);
key("Shift");
assert.deepEqual(takeMessages(), [{ kind: "history", direction: "forward", url: nextUrl }]);
page.showBadges();
shortcuts.refreshBadges();
key("Shift", {}, "keyup");
assert.deepEqual(takeMessages(), [
  { kind: "reveal", visible: true, url: nextUrl },
  { kind: "reveal", visible: false, url: nextUrl },
]);

key("Shift");
page.showBadges();
reveal.dispose();
keymap.dispose();
assert.equal(window.MetabrowserNativeNavigation, undefined);
assert.equal(shortcuts.present("shell.history-forward"), null);
assert.equal(key("]"), false);
page.build();
assert.notEqual(window.MetabrowserNativeNavigation, bridge);
bridge.setState({ back: true, forward: true });
assert.equal(key("["), false);
assert.deepEqual(takeMessages(), [
  { kind: "reveal", visible: true, url: nextUrl },
  { kind: "reveal", visible: false, url: nextUrl },
  { kind: "state", url: nextUrl },
]);

console.log("OK native history keyboard bridge");
for (const message of traffic) {
  console.log(JSON.stringify(message));
}

// Browserless session for the "Block remote images" preference state machine.
//
// static/remote-images.js loads whole, as the shell loads it on demand when the menu opens.
// The session makes each choice from each state the page can be served under, and wires the
// menu's checkbox as the page does, and records what is written, whether the page loads
// again, which is how the server's policy follows the choice, and when the box, which the
// server draws disabled, is enabled. Only the server reads the cookie, so the key is the
// one src/metabrowser/settings.py names, and tests/test_remote_images_js.py holds the
// server's reading of its values to a table of its own.

const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const repoRoot = path.resolve(__dirname, "../..");
const settingsSource = fs.readFileSync(path.join(repoRoot, "src/metabrowser/settings.py"), "utf8");
const cookieMatch = settingsSource.match(/^BLOCK_REMOTE_IMAGES_COOKIE = "([^"]+)"$/m);
if (!cookieMatch) {
  throw new Error("BLOCK_REMOTE_IMAGES_COOKIE is not a literal string in settings.py");
}

const sandbox = { Object };
sandbox.window = sandbox;
sandbox.globalThis = sandbox;
vm.createContext(sandbox);
const productionPath = path.join(repoRoot, "src/metabrowser/static/remote-images.js");
vm.runInContext(fs.readFileSync(productionPath, "utf8"), sandbox, { filename: productionPath });
const remoteImages = sandbox.MetabrowserRemoteImages;

// One choice, from a page served under *applied*: what it wrote, and how often it reloaded.
function choice(blocked, applied) {
  const writes = [];
  let reloads = 0;
  const changed = remoteImages.choose(blocked, applied, {
    writePreference(key, value) {
      writes.push({ key, value });
    },
    reload() {
      reloads += 1;
    },
  });
  return { changed, writes, reloads };
}

// The menu's box, as the server draws it, wired as the page wires it once the menu opens:
// each change of the box is a choice from what the page was served under.
function box(served, drawn) {
  const writes = [];
  let reloads = 0;
  let change = null;
  // Drawn disabled, as the server draws it: a change before the box is wired is not made.
  const input = {
    checked: drawn,
    disabled: true,
    addEventListener(type, listener) {
      if (type === "change") {
        change = listener;
      }
    },
  };
  const disabledBefore = input.disabled;
  const mounted = remoteImages.mount(
    { getElementById: (id) => (id === remoteImages.INPUT_ID ? input : null) },
    {
      applied: () => served,
      writePreference: (key, value) => writes.push({ key, value }),
      reload: () => {
        reloads += 1;
      },
    },
  );
  return {
    mounted,
    disabledBefore,
    disabledAfter: input.disabled,
    tick(checked) {
      input.checked = checked;
      change();
      return { writes: writes.slice(), reloads };
    },
  };
}
const noBox = remoteImages.mount(
  { getElementById: () => null },
  { applied: () => false, writePreference() {}, reload() {} },
);
const fromOff = box(false, false);
const fromOn = box(true, true);

const diffSettingsPath = path.join(repoRoot, "src/metabrowser/static/diff-settings.js");
const diffSettings = fs.readFileSync(diffSettingsPath, "utf8");
function sourceLayout(stored) {
  const writes = [];
  const select = {
    disabled: true,
    value: "",
    addEventListener(_type, listener) {
      this.change = listener;
    },
  };
  vm.runInNewContext(
    diffSettings,
    {
      document: { getElementById: (id) => (id === "default-diff-layout" ? select : null) },
      window: {
        metabrowser: {
          prefs: {
            get: (_key, fallback) => stored ?? fallback,
            set: (key, value) => writes.push({ key, value }),
          },
        },
      },
    },
    { filename: diffSettingsPath },
  );
  const opened = { value: select.value, disabled: select.disabled, writes: [...writes] };
  select.value = select.value === "split" ? "unified" : "split";
  select.change();
  return { opened, writes };
}

console.log(
  JSON.stringify(
    {
      authority: {
        key: remoteImages.KEY,
        inputId: remoteImages.INPUT_ID,
        serverKey: cookieMatch[1],
        frozen: Object.isFrozen(remoteImages),
      },
      choices: {
        "off, stays off": choice(false, false),
        "off, turned on": choice(true, false),
        "on, stays on": choice(true, true),
        "on, turned off": choice(false, true),
      },
      checkbox: {
        "a page with no box": noBox,
        "served off, before and after wiring": {
          mounted: fromOff.mounted,
          disabledBefore: fromOff.disabledBefore,
          disabledAfter: fromOff.disabledAfter,
        },
        "served off, ticked": fromOff.tick(true),
        "served off, ticked and unticked": fromOff.tick(false),
        "served on, unticked": fromOn.tick(false),
      },
      sourceLayout: {
        unset: sourceLayout(),
        savedUnified: sourceLayout("unified"),
      },
    },
    null,
    2,
  ),
);

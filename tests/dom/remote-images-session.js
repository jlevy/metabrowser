// Browserless session for the "Block remote images" preference state machine.
//
// static/remote-images.js loads whole, as the shell loads it on demand when the menu's
// checkbox changes. The session reads the preference as every profile can hold it, makes
// each choice from each state the page can be served under, and records what is written
// and whether the page loads again, which is how the server's policy follows the choice.
// The cookie key is the one src/metabrowser/settings.py names, which the server reads.

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

// What each cookie value the reader's browser can hold reads as; the server reads the same.
const READS = [null, "1", "0", "", "true", "yes", "11", " 1"];
const stored = {};
for (const value of READS) {
  stored[JSON.stringify(value)] = remoteImages.readStored((key) => {
    if (key !== remoteImages.KEY) {
      throw new Error(`read ${key}`);
    }
    return value;
  });
}

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
  const input = {
    checked: drawn,
    addEventListener(type, listener) {
      if (type === "change") {
        change = listener;
      }
    },
  };
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

console.log(
  JSON.stringify(
    {
      authority: {
        key: remoteImages.KEY,
        inputId: remoteImages.INPUT_ID,
        serverKey: cookieMatch[1],
        frozen: Object.isFrozen(remoteImages),
      },
      stored,
      choices: {
        "off, stays off": choice(false, false),
        "off, turned on": choice(true, false),
        "on, stays on": choice(true, true),
        "on, turned off": choice(false, true),
      },
      checkbox: {
        "a page with no box": noBox,
        "served off, ticked": fromOff.tick(true),
        "served off, ticked and unticked": fromOff.tick(false),
        "served on, unticked": fromOn.tick(false),
      },
    },
    null,
    2,
  ),
);

// Control-N and Control-P in a real engine (mb-lnqj): how the platform's Chrome names the
// chord, and real key events through the registry's one document listener.
//
// The browserless sessions stub the navigator and build each key event by hand, so this
// loads the production registry (static/keyboard-shortcuts.js) and the Pulls tab's keys
// (static/pulls-nav.js) into a blank page, registers the production stack pair against a
// stand-in stack, and presses keys through the DevTools input domain, which delivers them
// to the page as real `keydown` events. It reports what each press did to the stack,
// whether the page cancelled it, and how Help writes the chord on this platform.
//
// The browser's own shortcuts are out of its reach: protocol input goes to the page
// without passing the browser's accelerators, so whether Chrome on Windows and Linux keeps
// Ctrl+N for a new window cannot be shown here (docs/design-system.md, "Control Chords").
//
// Usage: node control-chords-chrome.mjs, with CHROME_BIN set, and CHROME_PROFILES naming
// where Chrome's profile goes (tests/dom/chrome-session.mjs).
// tests/test_control_chords_chrome.py owns that directory and removes it, and runs this
// in a process group of its own, which Chrome joins.
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { launchChrome } from "./chrome-session.mjs";

const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const SOURCES = ["keyboard-shortcuts.js", "pulls-nav.js"].map((name) =>
  fs.readFileSync(path.join(repoRoot, "src/metabrowser/static", name), "utf8"),
);
// The DevTools input domain's modifier bits.
const ALT = 1;
const CONTROL = 2;
const META = 4;
const SHIFT = 8;

const profiles = process.env.CHROME_PROFILES;
if (!process.env.CHROME_BIN || !profiles) {
  throw new Error("CHROME_BIN and CHROME_PROFILES are required");
}
const chrome = await launchChrome(process.env.CHROME_BIN, { profiles });
try {
  await chrome.send("Page.enable");
  await chrome.send("Page.navigate", { url: "about:blank" });
  await chrome.waitFor("document.readyState === 'complete'");
  await chrome.evaluate(
    `document.body.innerHTML = '<input id="field"><textarea id="area"></textarea>'; true`,
  );
  for (const source of SOURCES) {
    await chrome.evaluate(`${source}\ntrue`);
  }
  await chrome.evaluate(`(() => {
    window.moves = [];
    window.lastKey = null;
    // Heard after the registry's capture listener has decided the key.
    window.addEventListener("keydown", (event) => {
      if (!["Alt", "Control", "Meta", "Shift"].includes(event.key)) {
        window.lastKey = {
          key: event.key,
          ctrlKey: event.ctrlKey,
          altKey: event.altKey,
          metaKey: event.metaKey,
          prevented: event.defaultPrevented,
        };
      }
    });
    const registry = window.MetabrowserKeyboardShortcuts.create({ document });
    const declined = () => false;
    const stack = {
      hasStack: () => true,
      moveStack(delta) {
        window.moves.push(delta);
        return true;
      },
    };
    for (const name of ["activateAnchor", "activateFile", "collapse", "expand", "fileLeft",
      "fileRight", "move", "moveFile", "toggleFiles", "toggleStack"]) {
      stack[name] = declined;
    }
    window.MetabrowserPullsNav.registerKeys(stack, registry);
    window.registry = registry;
    return true;
  })()`);

  /** Press one letter with `modifiers`, where `focus` says, and say what it did. */
  async function press(letter, modifiers, focus = null) {
    await chrome.evaluate(
      focus === null
        ? "document.activeElement?.blur(); true"
        : `document.getElementById(${JSON.stringify(focus)}).focus(); true`,
    );
    const before = await chrome.evaluate("window.moves.length");
    const shifted = (modifiers & SHIFT) !== 0;
    const key = shifted ? letter.toUpperCase() : letter;
    const code = `Key${letter.toUpperCase()}`;
    const windowsVirtualKeyCode = letter.toUpperCase().charCodeAt(0);
    // A plain letter types its character; a chord types none.
    const text = modifiers & (ALT | CONTROL | META) ? undefined : key;
    await chrome.send("Input.dispatchKeyEvent", {
      type: text === undefined ? "rawKeyDown" : "keyDown",
      modifiers,
      key,
      code,
      windowsVirtualKeyCode,
      ...(text === undefined ? {} : { text }),
    });
    await chrome.send("Input.dispatchKeyEvent", {
      type: "keyUp",
      modifiers,
      key,
      code,
      windowsVirtualKeyCode,
    });
    const after = await chrome.evaluate("window.moves.slice()");
    return {
      moved: after.slice(before),
      heard: await chrome.evaluate("window.lastKey"),
    };
  }

  const presses = {
    "Control-N": await press("n", CONTROL),
    "Control-P": await press("p", CONTROL),
    "Control-Shift-N": await press("n", CONTROL | SHIFT),
    "N alone": await press("n", 0),
    "P alone": await press("p", 0),
    "Control-Alt-N, as AltGr": await press("n", CONTROL | ALT),
    "Control-Command-P": await press("p", CONTROL | META),
    "Control-N in a field": await press("n", CONTROL, "field"),
    "Control-P in a text area": await press("p", CONTROL, "area"),
  };
  const written = await chrome.evaluate(`(() => {
    const presented = window.registry.present("pulls.stack.top").bindings;
    return {
      platform: navigator.userAgentData?.platform || navigator.platform,
      visible: presented.visible,
      spoken: presented.spoken,
      aria: presented.ariaKeyshortcuts,
    };
  })()`);
  console.log(JSON.stringify({ presses, written }));
} finally {
  await chrome.close();
}

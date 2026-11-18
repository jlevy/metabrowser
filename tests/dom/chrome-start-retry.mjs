// launchChrome's retry (tests/dom/chrome-session.mjs), against a stand-in for Chrome's
// binary that starts as one CASE says, with each start's bound cut to the case's BOUNDS_MS:
//
//   hang-once  the first start writes to stderr, leaves a helper naming its profile, and
//              never writes a DevTools port; the second is CHROME_BIN's
//   hang       every start does what hang-once's first does
//   exit       every start writes to stderr and exits 3 at once
//   missing    the binary is not there
//
//   CHROME_BIN=/path/to/chrome CHROME_PROFILES=/dir/the/caller/removes \
//     STAND_IN=/dir/for/the/stand-in node tests/dom/chrome-start-retry.mjs CASE
//
// tests/test_chrome_starts.py owns both directories and runs this in a process group
// of its own. It prints, as JSON, how the launch ended, each start's profile, and which of
// those profiles, or processes naming one, were left once the launch returned or threw.
import { execFileSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { launchChrome } from "./chrome-session.mjs";

// A hang lasts its whole bound, so the cases that only hang have a short one. A start that
// is Chrome's, or a stand-in's exit, has room: 30 warm starts in a row on a 10-core Mac
// at a load average of 10 to 17 took 0.5 to 1.2 s each.
const BOUNDS_MS = { "hang-once": 10000, hang: 1500, exit: 10000, missing: 1500 };
// How many of the starts hang, the rest being Chrome's.
const HANGS = { "hang-once": 1, hang: 1000, exit: 0, missing: 0 };
const [mode] = process.argv.slice(2);
if (!(mode in BOUNDS_MS)) {
  throw new Error(`unknown case ${mode}`);
}
const bound = BOUNDS_MS[/** @type {keyof typeof BOUNDS_MS} */ (mode)];
const hangs = HANGS[/** @type {keyof typeof HANGS} */ (mode)];
const profiles = /** @type {string} */ (process.env.CHROME_PROFILES);
const standIn = /** @type {string} */ (process.env.STAND_IN);

// Each start counts itself, records its profile, then hangs or exits, or runs Chrome.
const binary = path.join(standIn, "chrome");
if (mode !== "missing") {
  fs.writeFileSync(
    binary,
    `#!/bin/sh
state="$(dirname "$0")"
n=$(( $(cat "$state/starts" 2>/dev/null || echo 0) + 1 ))
echo "$n" > "$state/starts"
for arg in "$@"; do
  case "$arg" in --user-data-dir=*) echo "\${arg#--user-data-dir=}" >> "$state/profiles" ;; esac
done
if [ "${mode}" = exit ]; then
  echo "stand-in chrome: start $n exits" >&2
  exit 3
fi
if [ "$n" -le ${hangs} ]; then
  echo "stand-in chrome: start $n hangs" >&2
  "${process.execPath}" -e "setInterval(() => {}, 1000)" -- "$@" &
  exec sleep 600
fi
exec "${process.env.CHROME_BIN}" "$@"
`,
    { mode: 0o755 },
  );
}

const result = { mode, ok: false, error: null, value: null };
try {
  const chrome = await launchChrome(binary, { profiles, startBoundMs: bound });
  try {
    result.value = await chrome.evaluate("6 * 7");
    result.ok = true;
  } finally {
    await chrome.close();
  }
} catch (error) {
  result.error = String(/** @type {Error} */ (error).message);
}
const listed = fs.existsSync(path.join(standIn, "profiles"))
  ? fs.readFileSync(path.join(standIn, "profiles"), "utf8").split("\n").filter(Boolean)
  : [];
// The starts that failed: every one, or all but the last when the launch succeeded. A
// started session's own helpers may still be exiting after its close, so are not looked at.
const abandoned = result.ok ? listed.slice(0, -1) : listed;
const processes = execFileSync("ps", ["-A", "-ww", "-o", "pid=,args="], { encoding: "utf8" })
  .split("\n")
  .filter((line) => abandoned.some((profile) => line.includes(profile)));
console.log(
  JSON.stringify({
    ...result,
    starts: listed.length,
    abandoned,
    processesLeft: processes,
    profilesLeft: fs.readdirSync(profiles),
  }),
);

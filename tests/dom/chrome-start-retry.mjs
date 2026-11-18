// launchChrome's starts (tests/dom/chrome-session.mjs), against a stand-in for Chrome's
// binary that starts as one CASE says, with each start's bound cut to the case's BOUNDS_MS:
//
//   exit-once  the first start writes to stderr, leaves a helper naming its profile, and
//              exits 3; the second is CHROME_BIN's
//   exit       every start writes to stderr and exits 3 at once
//   signal     every start writes to stderr and kills itself with SIGSEGV
//   hang       the start writes to stderr, leaves a helper naming its profile, and never
//              writes a DevTools port
//   silent     the start writes DevToolsActivePort for a port that takes connections and
//              never answers, then hangs
//   socket     the start's port lists a page whose socket takes connections and never
//              answers, then hangs
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

// A hang lasts its whole bound, so the cases that hang have a short one. A start that is
// Chrome's, or a stand-in's exit, has room: 30 warm starts in a row on a 10-core Mac at a
// load average of 10 to 17 took 0.5 to 1.2 s each.
const BOUNDS_MS = {
  "exit-once": 10000,
  exit: 10000,
  signal: 10000,
  hang: 1500,
  silent: 3000,
  socket: 3000,
  missing: 1500,
};
const [mode] = process.argv.slice(2);
if (!(mode in BOUNDS_MS)) {
  throw new Error(`unknown case ${mode}`);
}
const bound = BOUNDS_MS[/** @type {keyof typeof BOUNDS_MS} */ (mode)];
const profiles = /** @type {string} */ (process.env.CHROME_PROFILES);
const standIn = /** @type {string} */ (process.env.STAND_IN);
const node = process.execPath;

// The silent and socket cases' DevTools port: it writes DevToolsActivePort into the
// profile it is given, as Chrome does, for a port that takes connections and never
// answers (silent), or that lists one page whose socket does the same (socket).
fs.writeFileSync(
  path.join(standIn, "port.cjs"),
  `const fs = require("node:fs");
const http = require("node:http");
const net = require("node:net");
const path = require("node:path");
const [mode, profile] = process.argv.slice(2);
const publish = (port) => {
  const file = path.join(profile, "DevToolsActivePort");
  fs.writeFileSync(file + ".part", port + "\\n/devtools/browser/stand-in");
  fs.renameSync(file + ".part", file);
};
const silent = net.createServer(() => {}).listen(0, "127.0.0.1", () => {
  const quiet = silent.address().port;
  if (mode === "silent") {
    publish(quiet);
    return;
  }
  const page = [{ type: "page", webSocketDebuggerUrl: "ws://127.0.0.1:" + quiet + "/page" }];
  const list = http.createServer((request, response) => response.end(JSON.stringify(page)));
  list.listen(0, "127.0.0.1", () => publish(list.address().port));
});
`,
);

// Each start counts itself, records its profile, then does as the case says.
const binary = path.join(standIn, "chrome");
if (mode !== "missing") {
  fs.writeFileSync(
    binary,
    `#!/bin/sh
state="$(dirname "$0")"
n=$(( $(cat "$state/starts" 2>/dev/null || echo 0) + 1 ))
echo "$n" > "$state/starts"
for arg in "$@"; do
  case "$arg" in --user-data-dir=*) profile="\${arg#--user-data-dir=}" ;; esac
done
echo "$profile" >> "$state/profiles"
case "${mode}" in
  exit-once)
    if [ "$n" -eq 1 ]; then
      echo "stand-in chrome: start $n exits" >&2
      "${node}" -e "setInterval(() => {}, 1000)" -- "$@" &
      exit 3
    fi
    exec "${process.env.CHROME_BIN}" "$@" ;;
  exit)
    echo "stand-in chrome: start $n exits" >&2
    exit 3 ;;
  signal)
    echo "stand-in chrome: start $n crashes" >&2
    kill -SEGV $$ ;;
  hang)
    echo "stand-in chrome: start $n hangs" >&2
    "${node}" -e "setInterval(() => {}, 1000)" -- "$@" &
    exec sleep 600 ;;
  silent|socket)
    echo "stand-in chrome: start $n answers nothing" >&2
    "${node}" "$state/port.cjs" "${mode}" "$profile" &
    exec sleep 600 ;;
esac
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
// started session's own helpers may still be exiting, and writing to its profile, after
// its close, so neither is looked at: on a CI runner its profile was there again after the
// close had removed it. The caller removes the whole directory (tests/process_group.py).
// Without a session, every profile made, the one a spawn failure never named included.
const abandoned = result.ok ? listed.slice(0, -1) : listed;
const processes = execFileSync("ps", ["-A", "-ww", "-o", "pid=,args="], { encoding: "utf8" })
  .split("\n")
  .filter((line) => abandoned.some((profile) => line.includes(profile)));
const profilesLeft = result.ok
  ? abandoned.filter((profile) => fs.existsSync(profile)).map((profile) => path.basename(profile))
  : fs.readdirSync(profiles);
console.log(
  JSON.stringify({
    ...result,
    starts: listed.length,
    abandoned,
    processesLeft: processes,
    profilesLeft,
  }),
);

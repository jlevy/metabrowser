// Where a headless Chrome's processes live. Chrome is started from this process the two
// ways the Chrome tests start it: through tests/dom/chrome-session.mjs, as the pull header
// and staged fonts sessions do, and through the performance loop's launchBrowser, as the
// recorder and the Overview alignment do (with --no-sandbox on Linux). Each loads a page
// with a dedicated worker and a frame, so Chrome starts its renderer, GPU, network, and
// storage helpers. While they run, this prints every process on the machine as JSON, with
// this process's ID, for tests/test_process_group.py to check that each process Chrome
// started is in this process's group, the group the caller stops.
//
//   CHROME_BIN=/path/to/chrome CHROME_PROFILES=/dir/the/caller/removes \
//     node tests/dom/chrome-group-probe.mjs
import { execFileSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { launchChrome } from "./chrome-session.mjs";

const { launchBrowser } = await import(
  path.resolve(import.meta.dirname, "../../explorations/performance-loop/transitions-recorder.mjs")
);

const bin = process.env.CHROME_BIN;
const profiles = process.env.CHROME_PROFILES;
if (!bin || !profiles) {
  throw new Error("CHROME_BIN and CHROME_PROFILES are required");
}
const PAGE = `data:text/html,${encodeURIComponent(`<p>probe</p><script>
  new Worker(URL.createObjectURL(new Blob(["setInterval(() => {}, 1000)"])));
</script><iframe src="data:text/html,<p>frame</p>"></iframe>`)}`;

function snapshot() {
  const listed = execFileSync("ps", ["-A", "-ww", "-o", "pid=,ppid=,pgid=,args="], {
    encoding: "utf8",
  });
  return listed
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => {
      const [pid, ppid, pgid, ...args] = line.split(/\s+/);
      return { pid: Number(pid), ppid: Number(ppid), pgid: Number(pgid), args: args.join(" ") };
    });
}

// Helpers start as the page needs them; give them a moment to.
const settle = () => new Promise((resolve) => setTimeout(resolve, 1500));
const snapshots = {};

const session = await launchChrome(bin, { profiles });
try {
  await session.send("Page.navigate", { url: PAGE });
  await session.waitFor(`document.readyState === "complete"`);
  await settle();
  snapshots["chrome-session"] = snapshot();
} finally {
  await session.close();
}

const recorderProfile = fs.mkdtempSync(path.join(profiles, "recorder-"));
const browser = await launchBrowser({
  profileDir: recorderProfile,
  extraArgs: process.platform === "linux" ? ["--no-sandbox"] : [],
});
try {
  await browser.page.send("Page.navigate", { url: PAGE });
  await settle();
  snapshots.launchBrowser = snapshot();
} finally {
  await browser.close();
}
process.stdout.write(`${JSON.stringify({ node: process.pid, snapshots })}\n`, () =>
  process.exit(0),
);

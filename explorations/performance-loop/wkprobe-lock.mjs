// The WKWebView probe's lock: one probe series or `clean` at a time per user, because
// both remove the probe's WebKit data under ~/Library and either would wipe a running
// series' store between its launches. It excludes nothing else: the transition harness
// and the other probes take no lock. No top-level effects, so
// tests/dom/wkprobe-run-behavior.mjs drives it.
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

// Beside the data it protects, keyed by the home directory as that data is, and not under
// the probe's bundle identifier, which cleanup removes.
export const DEFAULT_LOCK = path.join(
  os.homedir(),
  "Library",
  "Caches",
  "metabrowser-wkprobe.lock",
);

// The lock is a directory made with one atomic mkdir, with an `owner` file inside naming
// who holds it. Only the holder removes it. A lock whose owner's process is gone is
// reported as stale, never broken: the owner file may have been written some other way.
let held = null;

export const lockHeld = () => held !== null;

export function lockOwner(dir) {
  try {
    return fs.readFileSync(path.join(dir, "owner"), "utf8").trim();
  } catch (_error) {
    return null;
  }
}

export function pidAlive(pid) {
  try {
    process.kill(pid, 0);
    return true;
  } catch (error) {
    return error.code === "EPERM";
  }
}

/** The pid an owner file names: the whole file, or after `pid`. */
export function ownerPid(owner) {
  const m = (owner ?? "").match(/^(\d+)$|\bpid[=: ]+(\d+)/);
  const pid = Number(m?.[1] ?? m?.[2]);
  return pid > 0 ? pid : null;
}

export function takeLock(dir, what) {
  try {
    fs.mkdirSync(dir, { mode: 0o700 });
  } catch (error) {
    if (error.code !== "EEXIST") {
      throw error;
    }
    const owner = lockOwner(dir);
    const pid = ownerPid(owner);
    const stale =
      pid && !pidAlive(pid)
        ? `; its owner, pid ${pid}, is not running: if no probe series is running, remove ${dir}`
        : "";
    throw new Error(
      `the probe lock ${dir} is held${owner ? ` (${owner.split("\n")[0].slice(0, 200)})` : ""}${stale}; ${what} does not run beside another probe series or clean`,
    );
  }
  held = dir;
  fs.writeFileSync(
    path.join(dir, "owner"),
    `pid ${process.pid}: wkprobe.mjs ${what}, since ${new Date().toISOString()}\n`,
    { mode: 0o600 },
  );
}

export function releaseLock() {
  if (!held) {
    return;
  }
  const dir = held;
  held = null;
  if ((lockOwner(dir) ?? "").startsWith(`pid ${process.pid}:`)) {
    fs.rmSync(path.join(dir, "owner"), { force: true });
    try {
      fs.rmdirSync(dir);
    } catch (_error) {
      // Not empty: someone else's file; leave it.
    }
  }
}

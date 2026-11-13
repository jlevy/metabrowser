// Provenance shared by the performance loop's Node harnesses (transitions.mjs and
// wkprobe.mjs): which `metab` build, which corpus, which harness state, and what the
// server saw of the corpus. Read-only: nothing here writes to a checkout or its object
// store. A module of functions with no top-level effects, so both command lines and
// their tests import it.
import { execFileSync } from "node:child_process";
import { createHash } from "node:crypto";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

const REPO = path.resolve(import.meta.dirname, "../..");

export function git(cwd, ...args) {
  try {
    return execFileSync("git", ["-C", cwd, ...args], {
      encoding: "utf8",
      timeout: 20000,
      maxBuffer: 256 * 1024 * 1024,
      stdio: ["ignore", "pipe", "ignore"],
    }).trim();
  } catch (_error) {
    return null;
  }
}

/**
 * The content of a checkout's working tree beyond its commit: a hash of the diff against
 * HEAD and of every untracked, unignored file. Read-only: nothing is written to the
 * checkout or its object store.
 */
export function workingTreeContent(source) {
  const diff = git(source, "--no-optional-locks", "diff", "HEAD", "--binary");
  const untracked = git(
    source,
    "--no-optional-locks",
    "ls-files",
    "--others",
    "--exclude-standard",
    "-z",
  );
  if (diff === null || untracked === null) {
    return null;
  }
  const h = createHash("sha256").update(diff);
  for (const rel of untracked.split("\0").filter(Boolean).sort()) {
    h.update(`\0${rel}\0`);
    try {
      h.update(fs.readFileSync(path.join(source, rel)));
    } catch (_error) {
      h.update("unreadable");
    }
  }
  return `sha256:${h.digest("hex").slice(0, 16)}`;
}

/**
 * Identity of one `metab` build: its version line and, for an editable checkout, its
 * commit, whether it is dirty, and the content of a dirty tree, so two different
 * uncommitted states never pool as one build. A wheel install is identified by the hash
 * of its RECORD, which lists every installed file's own hash.
 */
export function buildProvenance(metab) {
  const version = execFileSync(metab, ["--version"], {
    encoding: "utf8",
    timeout: 60000,
    cwd: os.tmpdir(),
  }).trim();
  const venv = path.dirname(path.dirname(metab));
  let source = null;
  let editable = false;
  let record = null;
  const libs = path.join(venv, "lib");
  if (fs.existsSync(libs)) {
    for (const py of fs.readdirSync(libs)) {
      const site = path.join(libs, py, "site-packages");
      if (!fs.existsSync(site)) {
        continue;
      }
      for (const entry of fs.readdirSync(site)) {
        if (!/^metabrowser-.*\.dist-info$/.test(entry)) {
          continue;
        }
        const direct = path.join(site, entry, "direct_url.json");
        if (fs.existsSync(direct)) {
          const info = JSON.parse(fs.readFileSync(direct, "utf8"));
          editable = Boolean(info.dir_info?.editable);
          if (editable && String(info.url).startsWith("file://")) {
            source = decodeURIComponent(new URL(info.url).pathname);
          }
        }
        const recordFile = path.join(site, entry, "RECORD");
        if (fs.existsSync(recordFile)) {
          record = createHash("sha256")
            .update(fs.readFileSync(recordFile))
            .digest("hex")
            .slice(0, 16);
        }
      }
    }
  }
  const commit = source ? git(source, "rev-parse", "HEAD") : null;
  const status = source ? git(source, "--no-optional-locks", "status", "--porcelain") : null;
  const dirty = status === null ? null : status.length > 0;
  let content = null;
  if (dirty) {
    content = workingTreeContent(source);
  } else if (!editable && record) {
    content = `record:${record}`;
  }
  return { metab, version, editable, source, commit, dirty, content };
}

export function corpusProvenance(corpus) {
  const status = git(corpus, "--no-optional-locks", "status", "--porcelain");
  return {
    path: corpus,
    commit: git(corpus, "rev-parse", "HEAD"),
    dirty: status === null ? null : status.length > 0,
    // The Commits list walks HEAD and the trunk refs; a standalone clone keeps them still.
    trunk: git(corpus, "rev-parse", "--verify", "--quiet", "origin/main"),
    refs: (() => {
      const refs = git(corpus, "for-each-ref", "--format=%(objectname) %(refname)");
      return refs === null ? null : createHash("sha256").update(refs).digest("hex").slice(0, 16);
    })(),
  };
}

export function harnessProvenance() {
  const status = git(REPO, "--no-optional-locks", "status", "--porcelain");
  return {
    commit: git(REPO, "rev-parse", "HEAD"),
    dirty: status === null ? null : status.length > 0,
  };
}

/** Fields of a build whose change during a run refuses it (`build_changed`). */
export const BUILD_FIELDS = ["version", "commit", "dirty", "content"];
/** Fields of a corpus whose change during a run refuses it (`corpus_changed`). */
export const CORPUS_FIELDS = ["commit", "dirty", "trunk", "refs"];

/** The refusals a run owes when its build or corpus moved between its start and end. */
export function provenanceChanges(start, end) {
  const out = [];
  for (const k of BUILD_FIELDS) {
    if (end.build[k] !== start.build[k]) {
      out.push(["build_changed", `${k} was ${start.build[k]} at start, ${end.build[k]} at end`]);
    }
  }
  for (const k of CORPUS_FIELDS) {
    if (JSON.stringify(end.corpus[k]) !== JSON.stringify(start.corpus[k])) {
      out.push(["corpus_changed", `${k} was ${start.corpus[k]} at start, ${end.corpus[k]} at end`]);
    }
  }
  return out;
}

export async function getJson(url, timeoutMs = 30000) {
  const response = await fetch(url, { signal: AbortSignal.timeout(timeoutMs) });
  if (!response.ok) {
    throw new Error(`${url}: HTTP ${response.status}`);
  }
  return response.json();
}

/** Facts about the moving parts of the corpus, read from the server before measuring. */
export async function serverFacts(base) {
  const facts = {};
  try {
    const log = await getJson(`${base}/api/git/log?limit=1`);
    facts.git_log_head = log.commits?.[0]?.id ?? null;
  } catch (error) {
    facts.git_log_head = `error: ${error.message}`;
  }
  try {
    const closed = await getJson(`${base}/api/plugin/github/pulls?state=closed&limit=1`);
    facts.github = {
      state: closed.state,
      fetched_at: closed.fetched_at,
      filter_totals: closed.filter_totals,
      last_refresh: closed.last_refresh?.outcome ?? null,
    };
  } catch (error) {
    facts.github = `error: ${error.message}`;
  }
  return facts;
}

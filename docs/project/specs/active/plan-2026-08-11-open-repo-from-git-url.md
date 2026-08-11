# Feature: Open a Repo from a Git URL

**Date:** 2026-08-11

**Author:** Joshua Levy (with LLM assistance)

**Status:** Draft

## Overview

Accept a Git URL where `metab` currently accepts only a path:

```shell
metab https://github.com/pallets/flask
```

Metabrowser clones the repository into a purgeable cache under `~/.metabrowser/cache/`,
then serves it through the existing serve path.
A repo already in the cache opens immediately with no network access.

This is the smallest change that makes the capability work end to end.
It adds a fetch step in front of serve and changes nothing about how files are indexed
or rendered.

Rationale, benchmarks, and the prior-art survey are in
`research-2026-08-11-repo-cache-and-git-url-open.md`. This spec assumes those findings
rather than restating them.

## Goals

- `metab <git-url>` clones on first use, reuses the clone afterwards, and serves either
  way.
- First render happens as early as the clone allows, with remaining Git objects fetched
  in the background so history browsing works later without a stall.
- The cache is inspectable and removable, and never leaves a half-written clone behind.
- Failures name a cause the user can act on, and no invocation can hang waiting for a
  credential prompt.
- Metabrowser stores no credentials and never handles a token.

## Non-Goals

The following are deliberately deferred.
Each is independently useful and none blocks the others.

- **Deep links.** `…/tree/<ref>/<path>` and `…/blob/<ref>/<file>` are rejected in this
  phase. Stripping the query and fragment is in scope because Git rejects those and a
  pasted URL commonly carries them; splitting ref from path is not.
- **`owner/repo` shorthand.** Ambiguous with a relative directory, and worth its own
  decision.
- **Checking out a specific ref.** The clone serves its default branch.
- **Size-capped LRU eviction.** This phase ships manual purge only; an automatic policy
  needs data on real cache growth.
- **Fetching updates automatically.** Cached repos serve their cached state.
- **Non-Git version control**, and any hosted or multi-user deployment.

## Background

Metabrowser’s serve path takes a directory that already exists.
Reading an unfamiliar repository therefore means cloning it by hand first, which is the
workflow this repository’s own `tbd checkout-third-party-repo` shortcut encodes into an
`attic/` directory.

The research found no tool that joins the two halves: `ghq` manages a clone cache with
no viewer, `klaus` and `git instaweb` view local repos but cannot fetch.
It also found that Git accepts plain repository URLs directly, so the fetch step is
mostly cache bookkeeping rather than URL handling.

The `feat/git-graph-view` work (PR #24) has since landed a `metabrowser.git` package
with a bounded async subprocess runner, repository identity discovery, and a read-only
`/api/git/` collection.
That changes this plan: the Git plumbing this feature needs largely exists, and the job
is to reuse it rather than build a second path to the `git` executable.
Two of its properties are load-bearing here.

First, `metabrowser.git.repo` requires the served root to *be* the repository’s
working-tree root, on the grounds that history spans the whole working tree and exposing
it while serving a subdirectory would describe files outside the navigation boundary.
A URL-opened cache entry satisfies that by construction, so a repo opened from a URL
gets the Git panel with no URL-specific work — which is exactly the payoff the research
predicted from keeping a real clone.

Second, `metabrowser.git.__init__` states a deliberate contract: *“Everything here is
read-only. Nothing in this package stages, commits, checks out, fetches, or otherwise
mutates a repository.”* Cloning fetches.
That boundary decides where this feature’s code lives.

## Design

### Approach

Resolve the ROOT argument before serve begins.
If it is a URL, ensure a clone exists in the cache and substitute its path; otherwise
behave exactly as today.
Serve is unchanged and unaware that the directory came from a URL.

Clone with `--filter=blob:none`, which fetches the commits and trees the file tree needs
while deferring file contents.
Serve as soon as the checkout exists, then run `git backfill` in the background to pull
the deferred blobs in bulk.

The ordering is the whole point and it is a correctness requirement, not a refinement.
Backfill is equal to or more total work than a full clone; the benefit is that the user
is browsing while it runs.
If it cannot be backgrounded, a full clone is strictly better.

Fall back to a full clone when Git is older than 2.49, when `git backfill` fails, or
when the remote refuses a partial clone.
The result is correct in every case and only the timing differs.

### Components

**`metabrowser/repo_cache.py`** (new) owns the cache and nothing else:

- Cache root from `METABROWSER_CACHE_DIR`, else `~/.metabrowser/cache`.
- Path derivation to `repos/<host>/<owner>/<repo>` using `urlsplit` plus a small regex
  for the SCP-like `git@host:path` form.
  Segments are lowercased and sanitized; a short hash of the canonical URL is appended
  when sanitizing changed the name, so the mapping stays injective.
  Lowercasing matters because GitHub is case-insensitive and `PALLETS/FLASK` would
  otherwise occupy a second entry for the same repository.
- Publication by clone-to-temp then rename.
  The temp directory lives inside the cache root so the rename stays on one filesystem.
  A killed clone leaves a directory that looks like a repo to a naive existence check,
  so the final path must only ever appear as the result of a completed clone.
- An `fcntl.flock` lock file beside each repo directory, held for the clone and released
  before serving, so two concurrent invocations cannot both clone the same URL.
- A sidecar JSON beside the repo directory recording origin URL, clone strategy, Git
  version, timestamps, and head ref.
  Beside rather than inside, so it survives the rename and is never served.

**No new git wrapper.** An earlier draft of this spec proposed a `git_cmd.py`; that
would have duplicated `metabrowser.git.process`, which already provides fixed argument
vectors with no shell, a wall-clock timeout, incremental capped stdout reads, concurrent
stdout and stderr draining, child reaping on timeout and cancellation, scrubbing of the
repository-pinning `GIT_*` variables, `GIT_TERMINAL_PROMPT=0` with empty askpass
settings, and a typed `GitError` hierarchy.
Clone and backfill call `run_git` and inherit all of it.
`process.py` stays the only place that spawns `git`.

**`metabrowser/git/process.py`** needs three additions, each of which also improves the
existing read paths:

- **Version detection**, which the package currently has none of.
  An anchored regex on `git version ` taking at most three numeric components and
  ignoring vendor suffixes, since `2.39.5 (Apple Git-154)`, `2.44.0.windows.1`, and
  `2.55.GIT` all occur.
  Unparseable means unknown, which degrades to a full clone rather than failing.
  Cached for the process lifetime alongside `git_executable()`.
- **`stdin=DEVNULL` on spawn.** The runner currently passes no `stdin`, so children
  inherit the parent’s. `GIT_TERMINAL_PROMPT=0` covers Git’s own prompt, but a network
  operation can still reach an SSH or credential-manager prompt in ways the read paths
  never exercised.
- **Completing the non-interactive environment**: `SSH_ASKPASS_REQUIRE=never`,
  `GCM_INTERACTIVE=never`, and `GIT_SSH_COMMAND` carrying
  `-o BatchMode=yes -o ConnectTimeout=10`. The environment must keep being inherited and
  added to, never rebuilt — suppressing global or system config breaks the user’s
  credential helper, and on macOS breaks it outright because `osxkeychain` is configured
  in a packager-shipped system gitconfig.

**`metabrowser/repo_clone.py`** (new) holds the fetching operations, deliberately
outside the `metabrowser.git` package so that package’s read-only contract stays true:

- `clone` builds the argument vector and hardens through `-c` flags only:
  `core.symlinks=false` so a hostile symlink materializes as an inert text file,
  `core.hooksPath` pinned empty, `fetch.recurseSubmodules=false`, `protocol.allow=never`
  with explicit `https` and `ssh` allowances, `gc.auto=0`, `--no-recurse-submodules`,
  `--filter=blob:none`, and `--` before the URL. `transfer.fsckObjects` stays at its
  default, because enabling it fails to clone mainstream repositories including Flask.
- `backfill` runs `git backfill` when the detected version is at least 2.49.
- Both pass an explicit `timeout_s` far above `GIT_SUBPROCESS_TIMEOUT_S`, which is 15
  seconds because it bounds request-path reads.
  A large repository clones in well over that; two new settings constants cover clone
  and backfill separately.
- Both are async, because `run_git` is.
  The CLI clone happens before uvicorn starts, so it runs under `asyncio.run`; the
  background backfill is scheduled on the running loop once the server is up.

**`metabrowser/cli/main.py`** gains URL detection on ROOT. Because ROOT is typed as
`Path`, detection runs on the raw string before path resolution.
A value with a `scheme://` prefix or matching the SCP-like form is a URL; everything
else is a path, unchanged.
Query and fragment are stripped.
`/tree/` and `/blob/` URLs are rejected with a message naming the plain repository URL
to use instead.

**`metabrowser/errors.py`** needs no new type.
Clone failures surface as `CLIError`, which the entry point already renders as
`Error: <message>`.

### Error messages

Every Git failure exits 128, so the exit code carries no information and stderr must be
matched. `GitCommandError` already retains `stderr_summary`, so the classification has
what it needs; the CLI translates a `GitError` into a `CLIError` carrying an actionable
message. Four cases are worth distinguishing:

| Matched in stderr | Message |
| --- | --- |
| `could not read Username` | No Git credentials for the host; the repo may be private or may not exist. Suggest `gh auth login`. |
| `Repository not found` | Names both possibilities, because GitHub returns the same response for a missing repo and one the user cannot see. |
| `Invalid username or token` | Credentials are stale rather than insufficient. |
| `Permission denied (publickey)` | No usable SSH key; suggest checking the agent. |

Anything unmatched reports Git’s own stderr rather than guessing.

This is a deliberate divergence from the rule in `process.py`, which logs stderr and
never puts it in a response because Git writes absolute local paths into its error text.
That rule is right for an HTTP response crossing a trust boundary.
The CLI is the operator’s own terminal, where those paths are the user’s own and
withholding them would make a failed clone undiagnosable.
The divergence is confined to the CLI surface: nothing in `/api/git/` changes, and the
classification helper must not be reused by a route.

### CLI additions

```shell
metab https://github.com/owner/repo   # clone if needed, then serve
metab --cache                         # print the cache path and what is in it
metab --cache-purge                   # remove cached repos, reporting before removing
```

`--cache` and `--cache-purge` are modes in the existing `_MODE_OPTIONS` table, alongside
`--plugins` and `--doctor`, and take no ROOT. Adding two more modes strengthens the case
for `mb-1t99`, which would derive that table declaratively, but does not depend on it.

### Trust

A URL-opened repository is the first tree Metabrowser serves that a third party wrote
and that arrived automatically.
Rendering it under the default profile would put a stranger’s HTML and SVG in a tab
sharing an origin with the local API.

This feature therefore depends on `mb-vib1`, the capability set and `--untrusted`
profile, and URL-opened roots must serve under that profile.
The clone and cache work here is independent and can be built and reviewed first;
enabling the CLI path is what waits.

Symlink containment needs no new work.
`_safe_path` resolves and rejects anything outside the root using `relative_to`, every
walker scans with `follow_symlinks=False`, and the inventory rewalk refuses symlinked
directories. Cloning with `core.symlinks=false` is defense in depth on top of that.

## Implementation Plan

### Phase 1: Fetch, cache, and serve

- [ ] `git/process.py`: add version detection, `stdin=DEVNULL` on spawn, and the
  remaining non-interactive environment settings.
  No behavior change for existing callers beyond closing those gaps.
- [ ] `repo_clone.py`: hardened `clone` and `backfill` argument vectors over `run_git`
  with clone-scale timeouts, plus stderr classification into actionable CLI messages.
- [ ] `repo_cache.py`: cache root, path derivation and sanitization, lock,
  temp-and-rename publication, sidecar read and write.
- [ ] URL detection on ROOT in `main.py`, with query and fragment stripped and deep-link
  URLs rejected with a useful message.
- [ ] Wire resolution into `run_serve`: cached path substituted before the existing
  directory checks, and the served root reported as the URL it came from.
- [ ] Background backfill after the server is serving, with failure logged and never
  fatal.
- [ ] `--cache` and `--cache-purge` modes, with purge reporting before removing and
  tolerating `EACCES` on Git’s read-only object files.
- [ ] Serve URL-opened roots under the untrusted profile once `mb-vib1` lands.
- [ ] Docs: a routing line in the Metabrowser skill, and the cache path and purge
  command in the CLI docs.

## Testing Strategy

Network access must not be required to run the suite.
Tests clone from local `file://` fixture repositories built in a temp directory, which
exercises the same clone and rename machinery without a remote.

- **Path derivation** is table-driven over URL forms: `https`, `https` with `.git`,
  trailing slash, mixed case, SCP-like, query string, fragment, non-GitHub host, and
  nested GitLab groups.
  Assertions cover both the derived cache path and the URL handed to Git.
- **Version parsing** is table-driven over the real vendor strings, including the Apple,
  Windows, and untagged forms, plus unparseable input degrading to unknown.
- **Cache behavior**: a second open of a cached repo performs no clone; a lock held by
  another process is observed rather than raced; a temp directory left by an interrupted
  clone is never served, and the final path appears only after a completed clone.
- **Error classification** feeds captured stderr samples through the classifier and
  asserts the message, with no live network.
- **Non-interactive guarantee**: a clone against an unreachable local path returns
  rather than blocking, proving the environment and timeout are wired.
- **CLI surface** extends `tests/golden/cli-surface.tryscript.md` with the new modes and
  the deep-link rejection.
- **Git panel on a cached repo** asserts the payoff end to end: a repo opened from a
  `file://` URL satisfies the served-root-is-repo-root invariant, so `/api/git/log`
  answers for it. `tests/test_git_e2e.py` already builds fixture repositories and is the
  natural place to extend rather than duplicate.

## Rollout Plan

The feature is inert until a user passes a URL, so no existing invocation changes
behavior. It ships when `mb-vib1` allows URL-opened roots to serve under the untrusted
profile. The cache directory is created on first use and never written otherwise.

## Open Questions

- Should a small repository skip the partial clone?
  A full clone is simpler and, below some size, faster overall.
  Deciding needs a cheap size signal before cloning.
- Is `~/.metabrowser/cache` right, or should this follow the platform cache directory
  such as `~/Library/Caches` on macOS? The former is predictable across platforms and
  easier to document; the latter is better behaved.
- Should an existing `ghq` checkout be reused when one is present, given the layouts
  match?
- Should `repo_clone.py` live at the package top level, or as a `metabrowser.git`
  submodule with that package’s read-only claim narrowed to the panel surface?
  The former keeps the existing contract literally true and is the assumption here; the
  latter keeps all Git code in one package.
  This is worth settling with the author of `feat/git-graph-view` rather than
  unilaterally.
- Does the backfill’s long-running subprocess need a different cancellation story from
  request-scoped reads?
  `run_git` reaps children on cancellation, but a backfill outlives the request that
  started it and is owned by the server’s lifetime instead.

## References

- `research-2026-08-11-repo-cache-and-git-url-open.md` — benchmarks, prior art, and the
  reasoning behind blobless-plus-backfill
- `research-2026-07-17-web-diff-viewer-architecture.md` — the Git subprocess adapter
  discipline this reuses
- `metabrowser.git` (PR #24, `feat/git-graph-view`) — the bounded runner, repository
  identity, and read-only `/api/git/` collection this builds on
- `plan-2026-08-06-html-rendering-and-trust-model.md` — the trust profile this depends
  on
- `plan-2026-07-27-metab-flat-cli.md` — the mode and option table this extends

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->

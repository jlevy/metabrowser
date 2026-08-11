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

**`metabrowser/git_cmd.py`** (new) is a narrow wrapper over the `git` executable:

- Version detection with an anchored regex on `git version `, taking at most three
  numeric components and ignoring vendor suffixes, since `2.39.5 (Apple Git-154)`,
  `2.44.0.windows.1`, and `2.55.GIT` all occur.
  Unparseable means unknown, which degrades to a full clone rather than failing.
- A non-interactive environment on every invocation: `GIT_TERMINAL_PROMPT=0`,
  neutralized `GIT_ASKPASS` and `SSH_ASKPASS`, `SSH_ASKPASS_REQUIRE=never`,
  `GCM_INTERACTIVE=never`, `GIT_SSH_COMMAND` carrying
  `-o BatchMode=yes -o ConnectTimeout=10`, plus `stdin=DEVNULL` and a wall-clock
  timeout. The environment is inherited and added to, never rebuilt: suppressing global
  or system config breaks the user’s credential helper, and on macOS breaks it outright
  because `osxkeychain` is configured in a packager-shipped system gitconfig.
- Hardening through `-c` flags only: `core.symlinks=false` so a hostile symlink
  materializes as an inert text file, `core.hooksPath` pinned empty,
  `fetch.recurseSubmodules=false`, `protocol.allow=never` with explicit `https` and
  `ssh` allowances, `gc.auto=0`, `--no-recurse-submodules`, and `--` before the URL.
  `transfer.fsckObjects` stays at its default, because enabling it fails to clone
  mainstream repositories including Flask.
- Arguments always as a list, never through a shell.

**`metabrowser/cli/main.py`** gains URL detection on ROOT. Because ROOT is typed as
`Path`, detection runs on the raw string before path resolution.
A value with a `scheme://` prefix or matching the SCP-like form is a URL; everything
else is a path, unchanged.
Query and fragment are stripped.
`/tree/` and `/blob/` URLs are rejected with a message naming the plain repository URL
to use instead.

**`metabrowser/errors.py`** needs no new type.
Failures raise `CLIError`, which the entry point already renders as `Error: <message>`.

### Error messages

Every Git failure exits 128, so the exit code carries no information and stderr must be
matched. Four cases are worth distinguishing:

| Matched in stderr | Message |
| --- | --- |
| `could not read Username` | No Git credentials for the host; the repo may be private or may not exist. Suggest `gh auth login`. |
| `Repository not found` | Names both possibilities, because GitHub returns the same response for a missing repo and one the user cannot see. |
| `Invalid username or token` | Credentials are stale rather than insufficient. |
| `Permission denied (publickey)` | No usable SSH key; suggest checking the agent. |

Anything unmatched reports Git’s own stderr rather than guessing.

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

- [ ] `git_cmd.py`: version detection, non-interactive hardened environment, `clone`,
  `backfill`, and stderr classification.
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

## References

- `research-2026-08-11-repo-cache-and-git-url-open.md` — benchmarks, prior art, and the
  reasoning behind blobless-plus-backfill
- `research-2026-07-17-web-diff-viewer-architecture.md` — the Git subprocess adapter
  discipline this reuses
- `plan-2026-08-06-html-rendering-and-trust-model.md` — the trust profile this depends
  on
- `plan-2026-07-27-metab-flat-cli.md` — the mode and option table this extends

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->

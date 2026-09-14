---
type: is
id: is-01m2fafd1v8d5pakt6r7zxw5n8
title: Release Metabrowser v0.10.0
kind: task
status: open
priority: 1
version: 2
labels:
  - release
dependencies: []
created_at: 2026-09-14T06:43:05.914Z
updated_at: 2026-09-14T06:43:14.829Z
---
Release Metabrowser v0.10.0 following docs/publishing.md (agent-operated).

Version: v0.10.0, a minor bump because the release contains breaking changes for plugin authors (plugin SDK 0.6 refuses 0.5 manifests, API paths are escaped inventory identities, analyzeGraph() removed). The dev version string 0.9.2.devN only reflects the last tag.

Checklist state when this bead was created (main at f1e4669b):
1. main clean, CI green on f1e4669b: done.
2. make verify: passed on a tree identical to f1e4669b.
3. Previous-release performance comparison on the FINAL commit, quiet machine: NOT done (mb-afdb, includes the first-rows gate from mb-i2im).
4-10. Pending: CI on the exact tag commit, release notes, gh release create v0.10.0, publish workflow, PyPI metadata, uvx smoke tests, skill install check.

Pre-release fixes in flight: mb-7nij (installed env under a Git checkout annotated as a dev build), flaky load-sensitive tests (mb-087n, mb-7u5b, mb-rfot), PR #90 CLI golden cleanups (mb-teif, mb-nm3p, mb-meju, mb-xvza), nav row baseline (mb-khqn).

Release-preparation PR: rename CHANGELOG `## Unreleased` to `## 0.10.0` only after the performance comparison is accepted. A draft of the GitHub release notes is in the notes below.

## Notes

Draft GitHub release notes (refresh after the pre-release fixes merge):

Metabrowser 0.10.0 opens large repositories faster, reports loading and connection
problems clearly, and adds `metab --api` and `metab --show` for reading view data without a
browser. It is a breaking release for plugin authors: the plugin SDK is now 0.6.

## Breaking changes for plugin authors

- **Plugin SDK 0.6.** A plugin manifest must declare `sdk_version = "0.6"`.
  Manifests for 0.5 are refused at discovery and by `metab --doctor`.
- **API paths are escaped inventory identities.** Plugin readers, activity probes,
  Markdown links, browser URLs, and filename search now handle literal percent signs
  consistently. See [plugin path identity](https://github.com/jlevy/metabrowser/blob/v0.10.0/docs/plugins.md#path-identity).
- **`mb.builtins.markdown.analyzeGraph()` is removed**, with no replacement in this
  release.
- **`fileCatalog.snapshot()` adds `truncated`**, true when the inventory walk stopped at
  its file cap. A plugin waiting for a final catalog should stop on `complete` or
  `truncated`.

## Highlights

- **Fast first tree rows on large repositories.** The tree no longer waits for a scan of
  every nested `.gitignore` before indexing starts; on a large repository the top-level
  rows used to take 10-30 s. Nested `.gitignore` files now follow git's own rules.
- **J and K** move down and up in the file tree (Files and Recent) and the Git history,
  like the arrow keys.
- **Clear loading and connection states.** The preview pane shows a loading indicator
  instead of "Select a file to preview." while something loads. When the server has
  stopped, Metabrowser says it is not reachable and how to restart it, then retries the
  selection on its own when the server returns.
- **`metab --api <route>` and `metab --show <path>`** read the same data the browser
  reads, without a browser or a listening port. Every route the browser consumes and
  every built-in file kind is now reachable from `metab` and pinned by a golden
  transcript. See the [command-line guide](https://github.com/jlevy/metabrowser/blob/v0.10.0/docs/command-line.md).
- **A pluggable inventory engine.** Filesystem inventory now crosses one
  provider-neutral contract, with the Python implementation as the shipped provider.
  Snapshots, reconnects, refreshes, rollups, and shutdown are more consistent, including
  under free-threaded Python 3.14, which CI now tests.

## Fixes

- Markdown: embedded notes no longer time out before they start loading; wiki links in
  task-list items followed by an ordinary link now convert; and links in a tree larger
  than the file cap no longer say "Resolving link" forever.
- Opening a file or folder again after it failed to load now loads it again.
- Collapsed folders no longer disappear from Recent while the panel reports their files.
- Expanded folders keep their loaded children after a reconnect or stream resync.
- Filesystem changes refresh collapsed folders and cached previews correctly.
- Intermittent `/api/rollup` failures under concurrent discovery are gone.
- A `watchfiles` panic during free-threaded CLI teardown is fixed.
- <!-- TODO: add the version-annotation and nav-row baseline fixes if their PRs merge -->

## Other changes

- Rendered documents default to a **Max text width** of 102 characters, and inline and
  block code share one quiet border style.
- Image previews load their renderer on demand.
- One shared Markdown Worker serves every rendered document on a page.

The full list of changes is in the
[changelog](https://github.com/jlevy/metabrowser/blob/v0.10.0/CHANGELOG.md#0100).

**Full diff:** https://github.com/jlevy/metabrowser/compare/v0.9.1...v0.10.0

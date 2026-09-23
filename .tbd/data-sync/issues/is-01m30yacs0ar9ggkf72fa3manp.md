---
type: is
id: is-01m30yacs0ar9ggkf72fa3manp
title: Pin memoization and the 16 MiB classify-before-read ceiling on a Git pin
kind: task
status: in_progress
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-08-11-open-repo-from-git-url.md
delegate: claude-code@spud10
labels:
  - stack:pr216
  - release:v0.12.0
dependencies: []
parent_id: is-01m2yxd3tnr1s2zf0h0jat1ey2
hold: null
hold_until: null
created_at: 2026-09-21T02:56:58.655Z
updated_at: 2026-09-23T03:31:08.906Z
started_at: 2026-09-23T03:31:08.905Z
---
Two items the content-reader build (mb-0um4) deliberately left. (1) A blob over TEXT_PREVIEW_REQUEST_MAX_BYTES still 413s before classification on a pin, while the filesystem path serves the first window; this is S216-13's first item and needs streaming cat-file reads, but the port makes it a small change. (2) The port adds no blob memoization, so paging a binary view re-reads the whole blob per chunk on a pin, as before; GitTreeSource.derived() is sync-build-only so it does not fit. Measure before deciding whether (2) is worth a cache.

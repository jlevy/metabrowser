---
type: is
id: is-01kxgmnvg1heqtbjjc3bnz1pxk
title: Publish MetaBrowser v0.1.0 to PyPI
kind: task
status: open
priority: 2
version: 5
spec_path: docs/specs/metabrowser-v0.1.0.md
labels:
  - release
dependencies: []
parent_id: is-01kxgmkc6gb2e8s23jf409j4bv
created_at: 2026-07-14T15:42:08.385Z
updated_at: 2026-07-15T06:40:51.199Z
---
After review and merge, configure trusted publishing, create the v0.1.0 release, verify the published artifact, and confirm installation from PyPI.

## Notes

PR #1 is merged to origin/main at 5dfb02e with the complete standalone package and green release gates. KPress 0.2.2 is pinned and verified. Next steps are trusted-publisher configuration, v0.1.0 release/tag, PyPI artifact verification, and published uvx/metab smoke checks. Deferred compression/archive roadmap beads are non-blocking.

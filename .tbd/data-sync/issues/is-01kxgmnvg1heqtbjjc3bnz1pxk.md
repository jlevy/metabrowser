---
type: is
id: is-01kxgmnvg1heqtbjjc3bnz1pxk
title: Publish MetaBrowser v0.1.0 to PyPI
kind: task
status: open
priority: 2
version: 3
spec_path: docs/specs/metabrowser-v0.1.0.md
labels:
  - release
dependencies: []
parent_id: is-01kxgmkc6gb2e8s23jf409j4bv
created_at: 2026-07-14T15:42:08.385Z
updated_at: 2026-07-15T03:19:05.037Z
---
After review and merge, configure trusted publishing, create the v0.1.0 release, verify the published artifact, and confirm installation from PyPI.

## Notes

KPress 0.2.2 is published, pinned, and verified. Publication now waits for MetaBrowser PR #1 to merge and for bounded zlib artifact support to pass the full local and GitHub release gates; then configure trusted publishing, tag v0.1.0, and verify the PyPI artifacts.

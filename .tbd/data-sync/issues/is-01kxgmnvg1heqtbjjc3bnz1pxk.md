---
type: is
id: is-01kxgmnvg1heqtbjjc3bnz1pxk
title: Publish MetaBrowser v0.1.0 to PyPI
kind: task
status: open
priority: 2
version: 7
spec_path: docs/specs/metabrowser-v0.1.0.md
labels:
  - release
dependencies: []
parent_id: is-01kxgmkc6gb2e8s23jf409j4bv
created_at: 2026-07-14T15:42:08.385Z
updated_at: 2026-07-16T16:02:22.967Z
---
After review and merge, configure trusted publishing, create the v0.1.0 release, verify the published artifact, and confirm installation from PyPI.

## Notes

Release candidate review on codex/release-v0.1.0-readiness confirms the public repository, available PyPI project name, current simple-modern-uv/tbd baseline, 676-test release gate at 6156c65, and a clean synthetic v0.1.0 build/install smoke under Python 3.12. PR #3 is mergeable/clean with all five CI jobs green, zero formal reviews, and zero review threads. Remaining: configure the PyPI pending trusted publisher, merge PR #3, publish v0.1.0, and verify public uvx/tool/skill installation.

---
type: is
id: is-01kxh1b2g7ap0thk7xbtdp6ypw
title: Reject file paths in walk subtree mode
kind: bug
status: closed
priority: 2
version: 3
spec_path: docs/project/specs/done/plan-2026-07-14-metabrowser-v0.1.0-standalone-package.md
labels: []
dependencies: []
created_at: 2026-07-14T19:23:26.598Z
updated_at: 2026-07-17T21:16:44.257Z
closed_at: 2026-07-14T19:26:20.447Z
close_reason: Required directory targets for walk subtrees while preserving file deep links for serve, added regression coverage, and passed all 616 tests and package gates
---
Keep serve deep links file-capable but require walk --path subtree targets to be directories, matching the tree endpoint contract; add regression coverage.

---
type: is
id: is-01kxh1b2g7ap0thk7xbtdp6ypw
title: Reject file paths in walk subtree mode
kind: bug
status: closed
priority: 2
version: 2
spec_path: docs/specs/metabrowser-v0.1.0.md
labels: []
dependencies: []
created_at: 2026-07-14T19:23:26.598Z
updated_at: 2026-07-14T19:26:20.449Z
closed_at: 2026-07-14T19:26:20.447Z
close_reason: Required directory targets for walk subtrees while preserving file deep links for serve, added regression coverage, and passed all 616 tests and package gates
---
Keep serve deep links file-capable but require walk --path subtree targets to be directories, matching the tree endpoint contract; add regression coverage.

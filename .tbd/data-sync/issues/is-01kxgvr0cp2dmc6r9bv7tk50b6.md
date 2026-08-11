---
type: is
id: is-01kxgvr0cp2dmc6r9bv7tk50b6
title: Normalize and contain serve paths
kind: bug
status: closed
priority: 2
version: 3
spec_path: docs/project/specs/done/plan-2026-07-14-metabrowser-v0.1.0-standalone-package.md
labels: []
dependencies: []
created_at: 2026-07-14T17:45:38.966Z
updated_at: 2026-07-17T21:16:41.330Z
closed_at: 2026-07-14T17:48:05.367Z
close_reason: Expanded home-relative serve roots, rejected traversal and symlink deep links resolving outside the served root, added two CLI regressions, updated the extraction spec, and passed the full 601-test release gate plus clean npm audit.
---
Address PR #1 review findings: expand and canonicalize serve ROOT before file/directory handling, and reject --path targets whose resolved path escapes ROOT (including symlink escapes) before generating a broken deep link. Add CLI regressions and rerun the full release gate.

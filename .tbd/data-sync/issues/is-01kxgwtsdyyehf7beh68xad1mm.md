---
type: is
id: is-01kxgwtsdyyehf7beh68xad1mm
title: Contain walk paths and isolate test configuration
kind: bug
status: closed
priority: 2
version: 2
spec_path: docs/specs/metabrowser-v0.1.0.md
labels: []
dependencies: []
created_at: 2026-07-14T18:04:38.718Z
updated_at: 2026-07-14T18:08:59.929Z
closed_at: 2026-07-14T18:08:59.928Z
close_reason: Contained walk subpaths, isolated pytest collection from operator plugin env, and verified all 606 tests plus package gates
---
Address PR #1 review findings: share serve --path containment with walk --path, including traversal/symlink/absolute-path rejection and existence checks; and clear operator METABROWSER_PLUGINS_DIRS during pytest bootstrap so strict direct-import validation is hermetic. Add regressions and rerun the complete release gate.

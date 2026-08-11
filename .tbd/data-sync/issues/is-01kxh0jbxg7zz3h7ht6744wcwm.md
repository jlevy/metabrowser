---
type: is
id: is-01kxh0jbxg7zz3h7ht6744wcwm
title: Align plugin diagnostics and walk path semantics
kind: bug
status: closed
priority: 2
version: 3
spec_path: docs/project/specs/done/plan-2026-07-14-metabrowser-v0.1.0-standalone-package.md
labels: []
dependencies: []
created_at: 2026-07-14T19:09:57.039Z
updated_at: 2026-07-17T21:16:43.495Z
closed_at: 2026-07-14T19:12:34.211Z
close_reason: Reported effective local-plugin hooks, rejected unsupported walk path modes, and passed all 614 tests and package gates
---
Make plugins list/show report effective JavaScript-only capabilities for local plugins and reject walk --path with text or stream modes instead of silently ignoring it; add CLI regressions.

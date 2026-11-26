---
type: is
id: is-01m8bcdsa46tnvsehetymvxdc8
title: "Merge PR #871 and rebuild Metabrowser from main"
kind: task
status: closed
priority: 2
version: 4
spec_path: docs/project/specs/active/plan-2026-08-17-general-diff-rendering.md
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/871
    at: 2026-11-26T07:34:28.178Z
delegate: codex@macbookpro
labels: []
dependencies: []
parent_id: is-01kxse0d3sm8h0p1yh1mjwgbxz
hold: null
hold_until: null
created_at: 2026-11-26T07:34:23.296Z
updated_at: 2026-11-26T07:49:43.091Z
started_at: 2026-11-26T07:34:26.517Z
closed_at: 2026-11-26T07:49:43.087Z
close_reason: "PR #871 merged at c0ea08948. Rebuilt and verified both the macOS development app and metab runtime from that commit. Main CI passed on its one retry. Watcher flake tracked in mb-7j24."
resolution: null
duplicate_of: null
---
Merged as c0ea08948. Rebuild the local macOS development bundle and runtime, then verify the build and merge-triggered CI.

---
type: is
id: is-01m2zvdh0wgdt6c9qx38dz52xw
title: Acquire SSH Git URLs into the shared mirror
kind: task
status: deferred
priority: 1
version: 11
spec_path: docs/project/specs/active/plan-2026-08-11-open-repo-from-git-url.md
labels: []
dependencies: []
parent_id: is-01kzs5m38dz1egphfwf30c8h7n
child_order_hints:
  - is-01m3617625k6h6qq4dq2hyxytb
created_at: 2026-09-20T16:47:01.143Z
updated_at: 2026-11-14T18:44:05.220Z
---
Acquire SSH Git URLs into the shared worktree-free Git store, with prompt suppression, safe diagnostics, identity and credential isolation, and separate live and automated acceptance. file:// and https:// already acquire and serve (HTTPS in mb-bgs7, PR #231); ssh stays refused (src/metabrowser/cache/acquire.py:6). Deferred by the user's 2026-09-23 decision (thin-mirror plan, Decisions). This design predates the thin mirror, so re-plan against it before starting.

## Notes

2026-09-30: deferred by the user's 2026-09-23 decision (thin-mirror plan, Decisions). Not part of v0.12; does not gate mb-n2ro. The design text predates the thin mirror (provider store, auth contexts, leases and SDK panels are retired); re-plan against the thin-mirror plan before starting. HTTPS shipped in mb-bgs7 (PR #231); child mb-s1lt closed as superseded. No dependency edge to mb-n2ro exists.

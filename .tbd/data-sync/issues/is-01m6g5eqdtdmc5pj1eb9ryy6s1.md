---
type: is
id: is-01m6g5eqdtdmc5pj1eb9ryy6s1
title: "PR checkout design: review overlays and complete safe local-worktree path"
kind: task
status: in_progress
priority: 1
version: 8
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m6g59qm4ewjgek4vjmndcxrj
child_order_hints:
  - is-01m6g9jsp8gs0esdtpf4g7j2nw
  - is-01m6g9kpk69mz7175s26ngjp9y
  - is-01m6g9p42kam0bbtyv1svw9jhc
  - is-01m6gft617bv7et4xz31y4qgbn
  - is-01m6gft6cfr7b50arr0rpdk1by
hold: null
hold_until: null
created_at: 2026-11-03T07:37:22.617Z
updated_at: 2026-11-03T10:38:24.142Z
started_at: 2026-11-03T07:37:52.370Z
---
Checkout agent owns #283 correctness and #288 local-worktree design. Preserve no-write checkout guarantee; valid criss-cross merges; review current revert and integration gaps.

## Notes

2026-11-03 checkpoint0f5fc1ef in codex/checkout-files-01a1a051: explicit comparison Fetch acquires store beside folder; no source/pin mutation, cached healthy store read-only reuse, job upgrade retained, failed acquire preserves record. Targeted135backendtests passed; golden concurrency ordering stabilized+repeatedgreen; readonly main/linked worktrees and subdirectories4-way matrix passes with no Git process checkout path. Forwardmerged renderer persistedmanifests994b77a1 and #283 fixes c1a033fe. Checkout UI Fetch trigger+production recording in progress; fullvalidation resumes after rendering timing quietwindow. Self-review only, root independent review/fullverify/CI pending.

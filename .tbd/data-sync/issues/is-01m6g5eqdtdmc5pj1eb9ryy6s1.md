---
type: is
id: is-01m6g5eqdtdmc5pj1eb9ryy6s1
title: "PR checkout design: review overlays and complete safe local-worktree path"
kind: task
status: closed
priority: 1
version: 9
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
updated_at: 2026-11-03T20:17:10.128Z
started_at: 2026-11-03T07:37:52.370Z
closed_at: 2026-11-03T20:17:10.128Z
close_reason: "Completed by forward commits in the PR-support stack; independent reviews, rechecks and dispositions are published on the owning PRs. Final integration ea771741211193a387c1771e04df29b5a9698100 passed make verify (4712 Python, 9 expected skips, 373 transcripts), 8 public live tests, installed-wheel Chrome (22 actions, 25 unchanged checkout/Git fingerprints), and all 171 CI jobs across 19 current-head runs on 14 PRs. Final clean review: https://github.com/jlevy/metabrowser/pull/288#pullrequestreview-5758664799 . No PR merged."
resolution: null
duplicate_of: null
---
Checkout agent owns #283 correctness and #288 local-worktree design. Preserve no-write checkout guarantee; valid criss-cross merges; review current revert and integration gaps.

## Notes

2026-11-03 checkpoint0f5fc1ef in codex/checkout-files-01a1a051: explicit comparison Fetch acquires store beside folder; no source/pin mutation, cached healthy store read-only reuse, job upgrade retained, failed acquire preserves record. Targeted135backendtests passed; golden concurrency ordering stabilized+repeatedgreen; readonly main/linked worktrees and subdirectories4-way matrix passes with no Git process checkout path. Forwardmerged renderer persistedmanifests994b77a1 and #283 fixes c1a033fe. Checkout UI Fetch trigger+production recording in progress; fullvalidation resumes after rendering timing quietwindow. Self-review only, root independent review/fullverify/CI pending.

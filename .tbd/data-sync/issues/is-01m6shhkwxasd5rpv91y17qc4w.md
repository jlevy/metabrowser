---
type: is
id: is-01m6shhkwxasd5rpv91y17qc4w
title: Watch GitHub pull request activity and recover connection failures
kind: feature
status: closed
priority: 2
version: 12
spec_path: docs/project/specs/active/plan-2026-11-06-pr-watch-and-reconnect.md
delegate: codex@spud10.local
labels: []
dependencies:
  - type: blocks
    target: is-01m6sppcghnnagtzr2gs9ev631
  - type: blocks
    target: is-01m6sx3tjqbthwcgkd91tt9tkt
parent_id: is-01m6f3n89kn7ztmfhrzswxnsgz
child_order_hints:
  - is-01m6shhmmxtvf9wz92kd75eyz0
  - is-01m6shhnakxdd0zeetnvzjrnvx
  - is-01m6shhnvfvppa319j426d9cbg
  - is-01m6shhp93hj2aybfj68g5prxh
hold: null
hold_until: null
created_at: 2026-11-06T23:01:50.098Z
updated_at: 2026-11-07T04:26:49.512Z
started_at: 2026-11-06T23:03:25.346Z
closed_at: 2026-11-07T04:26:49.511Z
close_reason: "PR #312 at 67c27fdb is mergeable, exact-head CI is green and all review threads are resolved. Design, backend, UI and end-to-end child work is verified. Ready for owner merge in stack #302."
resolution: null
duplicate_of: null
---
Keep a visible Pulls list or PR page current with the shared incremental GitHub catalog. Preserve cached access during failures, resume after reconnect, and present one helpful connection status with a Reload action.

## Notes

Watch published as #312. Exact initial CI passed. Review identified address-driven filter priority, steady outage text through retries, and normalized rejected-credential instructions. Fixing those in the watch layer and merging forward through #315.

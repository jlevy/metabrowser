---
type: is
id: is-01m6f3a4ab0xx86kma2fv9t9cy
title: List refresh job
kind: task
status: closed
priority: 1
version: 5
spec_path: docs/project/specs/active/plan-2026-10-01-github-pulls-tab.md
delegate: claude-code@spud10
labels: []
dependencies:
  - type: blocks
    target: is-01m6f3a4rcc45rvvzgy17a392p
parent_id: is-01m2h7hrjfx06hzpr7ptz7k9wn
hold: null
hold_until: null
created_at: 2026-11-02T21:40:40.394Z
updated_at: 2026-11-04T17:14:29.920Z
started_at: 2026-11-02T22:28:26.088Z
closed_at: 2026-11-04T17:14:29.920Z
close_reason: "Scoped implementation independently reviewed and tested; owning feature PRs are actually merged. Final main https://github.com/jlevy/metabrowser/commit/db52ec09cf839269da3a56fd396e44f3092995a9 includes account fix https://github.com/jlevy/metabrowser/pull/297 and documentation https://github.com/jlevy/metabrowser/pull/298, with final manual acceptance and per-issue qualifications checked. Individual source, test, review and merge evidence: ACTION-PLAN.json SHA-256 d0867a696ee055cc27911e83c4f70744b419a3ca4a7a1218f0eeaf419dc37589. Future scope and historical dependency relationships remain open or preserved as recorded."
resolution: null
duplicate_of: null
---
Coordinator key per source and state, per-page conditional requests, the account read before and after, the reader rules, and waiting for reset_at, applied to ServedPull too.

## Notes

2026-11-02: refresh_pull_list in pull_list_refresh.py: key <slug>:pulls/<name>, per-page If-None-Match, account read before and after, more reads only the next page, reader rules. refresh_is_due waits a window and for reset_at. Followed the plan and left the same rule on ServedPull to step 2; this bead's text says here. PR 279.

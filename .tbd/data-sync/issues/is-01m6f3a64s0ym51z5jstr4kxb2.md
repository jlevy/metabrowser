---
type: is
id: is-01m6f3a64s0ym51z5jstr4kxb2
title: What starts a fetch, and the job bound
kind: task
status: closed
priority: 1
version: 5
spec_path: docs/project/specs/active/plan-2026-10-01-github-pulls-tab.md
delegate: claude-code@spud10
labels: []
dependencies:
  - type: blocks
    target: is-01m6f3a6sjp293xntwmfty69pn
parent_id: is-01m6f39wqb7nqd20w7z5vpw9vh
hold: null
hold_until: null
created_at: 2026-11-02T21:40:42.263Z
updated_at: 2026-11-04T17:14:29.794Z
started_at: 2026-11-02T23:07:55.425Z
closed_at: 2026-11-04T17:14:29.794Z
close_reason: "Scoped implementation independently reviewed and tested; owning feature PRs are actually merged. Final main https://github.com/jlevy/metabrowser/commit/db52ec09cf839269da3a56fd396e44f3092995a9 includes account fix https://github.com/jlevy/metabrowser/pull/297 and documentation https://github.com/jlevy/metabrowser/pull/298, with final manual acceptance and per-issue qualifications checked. Individual source, test, review and merge evidence: ACTION-PLAN.json SHA-256 d0867a696ee055cc27911e83c4f70744b419a3ca4a7a1218f0eeaf419dc37589. Future scope and historical dependency relationships remain open or preserved as recorded."
resolution: null
duplicate_of: null
---
No record is fetched except by a reader's action in the shell's chrome, with mutation checks. A bound on distinct pull-request jobs, set from a measured refresh, refusing with a typed state.

## Notes

Done, PR 281, commits e6cb1ef0 and d44412bd. Only "retry": true can add a pull request to the cache. An automatic request answers not_cached or not_due and starts nothing. MAX_PULL_JOBS = 8 from a measured refresh of 4.7 to 7.0 s on pallets/click, run one at a time; past it 429 too_many. A page asks by itself after REFRESH_ASK_MS, once per visible period. Mutation checks all caught, listed in the PR. Filed mb-rznj for a list's refresh waiting behind queued pull-request jobs.

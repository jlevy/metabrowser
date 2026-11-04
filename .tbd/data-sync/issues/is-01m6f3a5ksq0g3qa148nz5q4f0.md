---
type: is
id: is-01m6f3a5ksq0g3qa148nz5q4f0
title: Provider set and attended pull request
kind: task
status: closed
priority: 1
version: 5
spec_path: docs/project/specs/active/plan-2026-10-01-github-pulls-tab.md
delegate: claude-code@spud10
labels: []
dependencies:
  - type: blocks
    target: is-01m6f3a64s0ym51z5jstr4kxb2
parent_id: is-01m6f39wqb7nqd20w7z5vpw9vh
hold: null
hold_until: null
created_at: 2026-11-02T21:40:41.720Z
updated_at: 2026-11-04T17:14:29.665Z
started_at: 2026-11-02T22:48:22.493Z
closed_at: 2026-11-04T17:14:29.665Z
close_reason: "Scoped implementation independently reviewed and tested; owning feature PRs are actually merged. Final main https://github.com/jlevy/metabrowser/commit/db52ec09cf839269da3a56fd396e44f3092995a9 includes account fix https://github.com/jlevy/metabrowser/pull/297 and documentation https://github.com/jlevy/metabrowser/pull/298, with final manual acceptance and per-issue qualifications checked. Individual source, test, review and merge evidence: ACTION-PLAN.json SHA-256 d0867a696ee055cc27911e83c4f70744b419a3ca4a7a1218f0eeaf419dc37589. Future scope and historical dependency relationships remain open or preserved as recorded."
resolution: null
duplicate_of: null
---
A bounded set replaces the single companion in cache/providers.py and mirror_refresh.py, one attended number replaced by a pin switch, and each place in the plan's One Pull Request per Server changed or deliberately kept.

## Notes

Done, PR 281, commit 0c62aa2e. ServedPulls (a PullRequestSet) replaces the single companion for any GitHub mirror, with MAX_KEPT_PULLS in memory (64, measured: 1.1 KB each, 0.4 to 3 ms to read one again). It never drops the attended pull request or a running one. MirrorSession.attend keeps one number, replaced when a pin switch serves another's head. pull_host in pull_route.py is the seam for steps 4 and 5. ServedPull now obeys reset_at after rate_limited. Every row of One Pull Request per Server is in the PR body as changed or kept.

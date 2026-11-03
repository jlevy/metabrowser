---
type: is
id: is-01m6f3a5ksq0g3qa148nz5q4f0
title: Provider set and attended pull request
kind: task
status: in_progress
priority: 1
version: 4
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
updated_at: 2026-11-02T23:54:14.417Z
started_at: 2026-11-02T22:48:22.493Z
---
A bounded set replaces the single companion in cache/providers.py and mirror_refresh.py, one attended number replaced by a pin switch, and each place in the plan's One Pull Request per Server changed or deliberately kept.

## Notes

Done, PR 281, commit 0c62aa2e. ServedPulls (a PullRequestSet) replaces the single companion for any GitHub mirror, with MAX_KEPT_PULLS in memory (64, measured: 1.1 KB each, 0.4 to 3 ms to read one again). It never drops the attended pull request or a running one. MirrorSession.attend keeps one number, replaced when a pin switch serves another's head. pull_host in pull_route.py is the seam for steps 4 and 5. ServedPull now obeys reset_at after rate_limited. Every row of One Pull Request per Server is in the PR body as changed or kept.

---
type: is
id: is-01m6fpm3qetf6hcyn97cxv3e3n
title: "PR #283 D1: admitted Git 2.43 reads an unreadable merge-base walk as no common history"
kind: bug
status: closed
priority: 1
version: 3
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m6f60pqc21gnqnct2pdq16zb
hold: null
hold_until: null
created_at: 2026-11-03T03:18:10.414Z
updated_at: 2026-11-03T03:28:52.741Z
started_at: 2026-11-03T03:18:36.385Z
closed_at: 2026-11-03T03:28:52.740Z
close_reason: "fixed in 00c0f48b23dc41f71676f7edd24978fe9833d8ea on PR #283: D1 no-boundary exit 1 and non-tip merge bases confirmed by rev-list --count; admitted-git (2.43.7) green in run 41567778096"
resolution: null
duplicate_of: null
---
High. Review D (follow-up, round 2), PR #283, https://github.com/jlevy/metabrowser/pull/283#pullrequestreview-5746541377. src/metabrowser/git/shallow.py:146-150 and cache/pull_refs.py:470-490: Git before 2.45 exits 1 from merge-base when the walk meets an unreadable commit, so a collected ancestor was recorded as no_merge_base on admitted-git (2.43.7).

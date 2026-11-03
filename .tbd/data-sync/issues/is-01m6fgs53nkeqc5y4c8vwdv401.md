---
type: is
id: is-01m6fgs53nkeqc5y4c8vwdv401
title: "PR #281 C1: an absurd Retry-After or X-Ratelimit-Reset raises in rate_limit_reset"
kind: bug
status: closed
priority: 3
version: 2
spec_path: docs/project/specs/active/plan-2026-10-01-github-pulls-tab.md
labels: []
dependencies: []
parent_id: is-01m6fgs20qmf639pkqec7tzk5q
created_at: 2026-11-03T01:36:04.212Z
updated_at: 2026-11-03T02:16:39.174Z
closed_at: 2026-11-03T02:16:39.173Z
close_reason: "fixed in b416cb7c: rate_limit_reset answers unknown for a time no clock holds; test_a_rate_limit_time_no_clock_can_hold_says_a_limit_without_a_time"
resolution: null
duplicate_of: null
---
Low. gh.py:299-316. Review https://github.com/jlevy/metabrowser/pull/281#pullrequestreview-5745898115

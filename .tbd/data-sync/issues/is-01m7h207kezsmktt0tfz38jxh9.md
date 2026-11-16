---
type: is
id: is-01m7h207kezsmktt0tfz38jxh9
title: "PR #449 A3: on Git before 2.42 every comparison pays git var and git config and nothing is kept"
kind: bug
status: closed
priority: 2
version: 3
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m7h1z1rnzfafwf740k7yrzdh
hold: null
hold_until: null
created_at: 2026-11-16T02:11:58.189Z
updated_at: 2026-11-16T02:53:12.243Z
started_at: 2026-11-16T02:53:11.898Z
closed_at: 2026-11-16T02:53:12.242Z
close_reason: A3 fixed in ae27afdce (Git before 2.42 lists its system file alone; answers kept)
resolution: null
duplicate_of: null
---
Severity: Medium. PR #449 (https://github.com/jlevy/metabrowser/pull/449), review https://github.com/jlevy/metabrowser/pull/449#pullrequestreview-5913959566. References: src/metabrowser/diff/adapters/textconv.py:155-174, :243-250. See the review for the full finding and suggested fix.

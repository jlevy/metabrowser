---
type: is
id: is-01m7h20fx7jmrq1z7kjmg4gbyv
title: "PR #449 C4: on Git before 2.42 a false GIT_CONFIG_NOSYSTEM leaves the system file unstamped and a kept answer goes stale"
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
created_at: 2026-11-16T02:12:06.694Z
updated_at: 2026-11-16T02:53:23.357Z
started_at: 2026-11-16T02:53:23.014Z
closed_at: 2026-11-16T02:53:23.356Z
close_reason: C4 fixed in ae27afdce (GIT_CONFIG_NOSYSTEM read as Git reads a boolean)
resolution: null
duplicate_of: null
---
Severity: Low. PR #449 (https://github.com/jlevy/metabrowser/pull/449), review https://github.com/jlevy/metabrowser/pull/449#pullrequestreview-5914224032. References: src/metabrowser/diff/adapters/textconv.py:157, :167-171. See the review for the full finding and suggested fix.

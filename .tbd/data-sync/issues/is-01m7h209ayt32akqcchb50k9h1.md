---
type: is
id: is-01m7h209ayt32akqcchb50k9h1
title: "PR #449 A7: source and tests cite finding IDs of a review that was never published"
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
created_at: 2026-11-16T02:11:59.965Z
updated_at: 2026-11-16T02:53:15.181Z
started_at: 2026-11-16T02:53:14.834Z
closed_at: 2026-11-16T02:53:15.180Z
close_reason: A7 fixed in 12167dfe3 (no unpublished finding IDs)
resolution: null
duplicate_of: null
---
Severity: Low. PR #449 (https://github.com/jlevy/metabrowser/pull/449), review https://github.com/jlevy/metabrowser/pull/449#pullrequestreview-5913959566. References: textconv.py:8,:24; git/process.py:1346; server_timing.py:31; tests/test_diff_one_run.py:344,:395,:458,:506; tests/test_diff_textconv_cache.py:1. See the review for the full finding and suggested fix.

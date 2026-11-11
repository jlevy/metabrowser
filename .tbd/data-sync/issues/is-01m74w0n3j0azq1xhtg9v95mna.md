---
type: is
id: is-01m74w0n3j0azq1xhtg9v95mna
title: "PR #348 A2: Changes skips the metadata read for stale records"
kind: bug
status: closed
priority: 2
version: 3
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m74w003xk59spnxy95gr9dss
hold: null
hold_until: null
created_at: 2026-11-11T08:36:27.377Z
updated_at: 2026-11-11T10:57:50.328Z
started_at: 2026-11-11T09:24:55.855Z
closed_at: 2026-11-11T10:57:50.327Z
close_reason: "Fixed: c5fc056d. Changes uses the cached record only while cached_comparison_record admits it (current, observed reader, no failure since); otherwise it refreshes first. Test: test_changes_reads_github_first_unless_the_cached_record_is_current[stale, rate_limited, another_reader]. Route map: 9163be07."
resolution: null
duplicate_of: null
---
Medium. checkout.py:483-510; arch-views-models-routes.md:231-235. Review A https://github.com/jlevy/metabrowser/pull/348#pullrequestreview-5855514600

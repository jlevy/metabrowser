---
type: is
id: is-01m74w0mqb95qcdghys6w1hk2q
title: "PR #348 A1: comparison preparation overwrites the metadata refresh stamp"
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
created_at: 2026-11-11T08:36:26.986Z
updated_at: 2026-11-11T09:24:56.352Z
started_at: 2026-11-11T09:24:55.848Z
closed_at: 2026-11-11T09:24:56.351Z
close_reason: "Fixed in c5fc056d: comparison preparation writes no success stamp and idle work records nothing (failures kept in memory, revision not retried); only a reader's failed comparison request is kept beside the record. Tests: test_a_comparison_from_the_cached_record_keeps_the_metadata_stamp, test_a_failed_idle_comparison_reports_nothing_and_is_not_repeated, test_changes_reads_github_first_unless_the_cached_record_is_current[rate_limited]."
resolution: null
duplicate_of: null
---
Medium. checkout.py:415-450 (_comparison_outcome), :508, :518; served_pull.py:455. Review A https://github.com/jlevy/metabrowser/pull/348#pullrequestreview-5855514600

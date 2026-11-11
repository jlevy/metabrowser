---
type: is
id: is-01m7594qqjjb2akjehwy60jfjx
title: "PR #348 E2: a comparison of an older read discards another server's newer refresh"
kind: bug
status: closed
priority: 3
version: 3
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m7594pkfe0xdkwhjqrwwpxz2
hold: null
hold_until: null
created_at: 2026-11-11T12:25:52.625Z
updated_at: 2026-11-11T14:23:37.237Z
started_at: 2026-11-11T12:25:53.209Z
closed_at: 2026-11-11T14:23:37.236Z
close_reason: "Fixed: 31e6ba7f. same_observation: a record differing only in comparison and unavailable[comparison] is the same read, in write_pull_record and write_pull_refresh. Test: test_a_comparison_of_an_older_read_does_not_discard_a_newer_refresh (fails without the guard)."
resolution: null
duplicate_of: null
---
Low. pull_record.py:542-548; checkout.py:562, 636. Review E https://github.com/jlevy/metabrowser/pull/348#pullrequestreview-5858632040

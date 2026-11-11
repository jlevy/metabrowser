---
type: is
id: is-01m7594rdwsteb1g7f24yye29j
title: "PR #348 E3: a reader's failed Changes is dropped when the record changed under it"
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
created_at: 2026-11-11T12:25:53.339Z
updated_at: 2026-11-11T14:23:37.552Z
started_at: 2026-11-11T12:25:53.934Z
closed_at: 2026-11-11T14:23:37.551Z
close_reason: "Fixed: 31e6ba7f, f9f7b9c3. The in-memory outcome is set before the stamp write; the stamp against the request's own pending base_uncertain record is kept; after a failed acquisition the record is reread. Tests: test_a_failed_changes_is_reported_after_its_own_pending_write[git_unavailable, disk_full] (fails with the strict stamp guard), test_a_reader_s_failure_is_reported_even_when_its_stamp_is_refused (fails without setting the outcome first)."
resolution: null
duplicate_of: null
---
Low. checkout.py:503-510, 612-619, 636-641; pulls.py:1093. Review E https://github.com/jlevy/metabrowser/pull/348#pullrequestreview-5858632040

---
type: is
id: is-01m883w8hmjtyb0b410zwfcykw
title: "PR #801 A4: server reader sentences are never held to the text rules"
kind: bug
status: closed
priority: 2
version: 3
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m883v3q9d1nc4xypdrb2gbg1
hold: null
hold_until: null
created_at: 2026-11-25T01:07:17.072Z
updated_at: 2026-11-25T02:42:21.166Z
started_at: 2026-11-25T01:08:33.508Z
closed_at: 2026-11-25T02:42:21.166Z
close_reason: "Fixed in ea97d252d on PR #801 (review A dispositions: https://github.com/jlevy/metabrowser/pull/801#issuecomment-7151064403); A1's remaining shape is mb-q9ar, A6's Swift audit is mb-dhiw. CI run 45533955537 passed."
resolution: null
duplicate_of: null
---
Medium finding A4 of review A on PR #801 (https://github.com/jlevy/metabrowser/pull/801#pullrequestreview-6049962996). References: tests/test_reader_messages.py:615-663; docs/design-system-messages.md:166-170.

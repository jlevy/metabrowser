---
type: is
id: is-01m883vb7yx7wgyt3drr48wkcp
title: "PR #801 A1: the check misses common ways of writing what it forbids"
kind: bug
status: in_progress
priority: 2
version: 2
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m883v3q9d1nc4xypdrb2gbg1
hold: null
hold_until: null
created_at: 2026-11-25T01:06:47.153Z
updated_at: 2026-11-25T01:08:16.744Z
started_at: 2026-11-25T01:08:16.742Z
---
Medium finding A1 of review A on PR #801 (https://github.com/jlevy/metabrowser/pull/801#pullrequestreview-6049962996). References: tests/test_reader_messages.py:86-101, :172-192, :491-530, :626-638; tests/dom/reader-message-literals.mjs:57-67, :238-272.

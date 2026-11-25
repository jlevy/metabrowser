---
type: is
id: is-01m883vm08h7ryrkxcwd74013s
title: "PR #801 A2: the server rule exempts str() of Metabrowser errors that have a reader_message"
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
created_at: 2026-11-25T01:06:56.118Z
updated_at: 2026-11-25T01:08:21.703Z
started_at: 2026-11-25T01:08:21.698Z
---
Medium finding A2 of review A on PR #801 (https://github.com/jlevy/metabrowser/pull/801#pullrequestreview-6049962996). References: tests/test_reader_messages.py:564-568, :760-792; src/metabrowser/content_errors.py:29-32; source_routes.py:739-740, :1403-1404.

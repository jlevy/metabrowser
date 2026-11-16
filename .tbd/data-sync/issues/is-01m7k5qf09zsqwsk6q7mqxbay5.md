---
type: is
id: is-01m7k5qf09zsqwsk6q7mqxbay5
title: "PR #486 A5: the double-encoded UTF-8 check misses the cp1252 form"
kind: bug
status: closed
priority: 3
version: 3
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m7jz6wz5wjnb9thcvxybaek0
hold: null
hold_until: null
created_at: 2026-11-16T21:55:34.024Z
updated_at: 2026-11-16T22:03:51.339Z
started_at: 2026-11-16T21:55:40.378Z
closed_at: 2026-11-16T22:03:51.338Z
close_reason: "Fixed in 1c3ad35e5 on PR #486: cp1252 alternative with three test cases, which fail on the old check."
resolution: null
duplicate_of: null
---
Suggestion. devtools/public_hygiene.py:76-84. Add U+00E2 followed by a cp1252 0x80-0x9F character, with three cp1252 cases in test_double_encoded_utf8_is_rejected. Review A on PR #486: https://github.com/jlevy/metabrowser/pull/486#pullrequestreview-5928430110

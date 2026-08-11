---
type: is
id: is-01kzsgf1xeeqrkhzfssqa95qs6
title: Omit meaningless unknown JSONL record labels and filters
kind: bug
status: closed
priority: 2
version: 4
labels: []
dependencies: []
parent_id: is-01kzrtbtsh9k6p8x84rta84y4p
created_at: 2026-08-11T22:53:04.813Z
updated_at: 2026-08-11T23:01:25.712Z
closed_at: 2026-08-11T23:01:25.712Z
close_reason: Implemented and verified
---
For generic JSONL such as ~/.claude/history.jsonl, do not render an unknown [unknown] heading on each row. Show record-type controls only when there are at least two meaningful classified types; otherwise render the record values directly. Cover fallback, homogeneous, and heterogeneous JSONL behavior and verify the exact browser case.

## Notes

Generic JSONL rows now omit unclassified kind badges and generated [unknown] prefixes. Type controls render only for two or more meaningful kinds. Added DOM behavior coverage for unknown, single-known, and multi-kind logs; visually verified against ~/.claude/history.jsonl in dark mode. make verify passes: 890 pytest tests and 28 tryscript cases.

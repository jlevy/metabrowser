---
type: is
id: is-01m888ydptdse0gf8rrcm6vy5t
title: A list of records past the structured parse limit still offers a Table tab that only refuses
kind: bug
status: open
priority: 3
version: 1
spec_path: docs/project/specs/active/plan-2026-11-19-tabular-data-and-live-sqlite.md
labels: []
dependencies: []
parent_id: is-01m7tv7gz4yk6tygqfexgtw0s2
created_at: 2026-11-25T02:35:50.872Z
updated_at: 2026-11-25T02:35:50.872Z
---
Found reviewing #805 (2026-11-24): the Table offer decides from a file's leading bytes and is not given its size, so a JSON or YAML list of records larger than STRUCTURED_PARSE_MAX_BYTES (records.py) is offered the Table tab, which then shows only the size refusal. The owner's rule from mb-0w2c: do not show the Table view unless it applies. Decide whether the offer should also see the logical size (or the server leave the tab out past the limit), or whether a large list should be readable as a table another way.

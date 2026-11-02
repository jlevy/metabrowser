---
type: is
id: is-01m6f3a2xknb6bzh2m26w2zema
title: List bounds, measured
kind: task
status: in_progress
priority: 1
version: 4
spec_path: docs/project/specs/active/plan-2026-10-01-github-pulls-tab.md
delegate: claude-code@spud10
labels: []
dependencies:
  - type: blocks
    target: is-01m6f3a3c2fsrz21ph82xrc6yg
parent_id: is-01m2h7hrjfx06hzpr7ptz7k9wn
hold: null
hold_until: null
created_at: 2026-11-02T21:40:38.962Z
updated_at: 2026-11-02T22:34:15.386Z
started_at: 2026-11-02T21:48:18.897Z
---
Bytes and seconds of a list page, largest row and label count, open and closed counts, and file size at the cap, recorded beside each constant in pull_list.py.

## Notes

2026-11-02: measured with gh api on the seven repositories of the record's ten pull requests: 70 pages of state=all, 7,000 rows, load average 10 to 30. Page 1.41-2.85 MB and 1.44-2.81 s at per_page=100; a 304 1.18-1.37 s; largest row 1,152 bytes, 43 labels. Set MAX_LIST_PAGES 10, the row bounds, and MAX_PULL_LIST_BYTES 10 MiB (worst list 8.42 MB, read back by a test). Recorded beside the constants in pull_list.py. PR 279.

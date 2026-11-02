---
type: is
id: is-01m6f3a3v2ny6852knvbqn6pmt
title: PullList model, file, and refresh stamp
kind: task
status: in_progress
priority: 1
version: 4
spec_path: docs/project/specs/active/plan-2026-10-01-github-pulls-tab.md
delegate: claude-code@spud10
labels: []
dependencies:
  - type: blocks
    target: is-01m6f3a4ab0xx86kma2fv9t9cy
parent_id: is-01m2h7hrjfx06hzpr7ptz7k9wn
hold: null
hold_until: null
created_at: 2026-11-02T21:40:39.905Z
updated_at: 2026-11-02T22:34:16.277Z
started_at: 2026-11-02T21:58:20.146Z
---
Rows ordered and deduplicated by number, merged derived from merged_at, one file per state in cache/paths.py, read with a size bound, schema 1, written atomically and privately.

## Notes

2026-11-02: PullList, PullListRow, ListPageMark, ListedRepository in pull_list.py; files named in cache/paths.py; read_refresh_stamp and write_refresh_stamp split out of pull_record.py for step 4; PullRefreshStamp gains reader. Rows unique, highest number first; merged is read from merged_at and added by the route. PR 279.

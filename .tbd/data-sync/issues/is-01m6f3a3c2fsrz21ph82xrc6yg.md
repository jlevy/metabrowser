---
type: is
id: is-01m6f3a3c2fsrz21ph82xrc6yg
title: Shared paging helper with query parameters
kind: task
status: in_progress
priority: 1
version: 4
spec_path: docs/project/specs/active/plan-2026-10-01-github-pulls-tab.md
delegate: claude-code@spud10
labels: []
dependencies:
  - type: blocks
    target: is-01m6f3a3v2ny6852knvbqn6pmt
parent_id: is-01m2h7hrjfx06hzpr7ptz7k9wn
hold: null
hold_until: null
created_at: 2026-11-02T21:40:39.424Z
updated_at: 2026-11-02T22:34:15.834Z
started_at: 2026-11-02T21:55:04.872Z
---
Move _read_list to a shared module, moved and not copied, taking state, sort, and direction as parameters. Repository wording for a refused list, not pull-request wording.

## Notes

2026-11-02: read_list moved to gh_lists.py, not copied, with a query string, a first page, and the caller's clock; ListRead says apart left_out and more. PullDataError moved with it and pulls.py re-exports it. Repository wording for a refused list is in pull_list_refresh._read_page. Step 4 reuses read_list with no query. PR 279.

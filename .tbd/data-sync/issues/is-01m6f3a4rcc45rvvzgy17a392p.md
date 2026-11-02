---
type: is
id: is-01m6f3a4rcc45rvvzgy17a392p
title: List routes, goldens, and parity
kind: task
status: in_progress
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-10-01-github-pulls-tab.md
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m2h7hrjfx06hzpr7ptz7k9wn
hold: null
hold_until: null
created_at: 2026-11-02T21:40:40.843Z
updated_at: 2026-11-02T22:34:17.165Z
started_at: 2026-11-02T22:28:26.646Z
---
GET pulls with windows by limit and after, POST pulls-refresh with more, the fake gh pages, and a test that no written file carries a credential. Listing touches no Git.

## Notes

2026-11-02: GET pulls and POST pulls-refresh in sidekick.py and pull_list_route.py; goldens cli-github-pulls.tryscript.md, cli-github-pulls-refresh.txt, cli-github-pulls-failures.txt; parity rows; tests/test_github_pull_list.py including a source directory with no store and no written file carrying a credential. Ten mutation checks caught. PR 279.

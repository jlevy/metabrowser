---
type: is
id: is-01m6f3a4rcc45rvvzgy17a392p
title: List routes, goldens, and parity
kind: task
status: closed
priority: 1
version: 4
spec_path: docs/project/specs/active/plan-2026-10-01-github-pulls-tab.md
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m2h7hrjfx06hzpr7ptz7k9wn
hold: null
hold_until: null
created_at: 2026-11-02T21:40:40.843Z
updated_at: 2026-11-04T17:14:29.925Z
started_at: 2026-11-02T22:28:26.646Z
closed_at: 2026-11-04T17:14:29.925Z
close_reason: "Scoped implementation independently reviewed and tested; owning feature PRs are actually merged. Final main https://github.com/jlevy/metabrowser/commit/db52ec09cf839269da3a56fd396e44f3092995a9 includes account fix https://github.com/jlevy/metabrowser/pull/297 and documentation https://github.com/jlevy/metabrowser/pull/298, with final manual acceptance and per-issue qualifications checked. Individual source, test, review and merge evidence: ACTION-PLAN.json SHA-256 d0867a696ee055cc27911e83c4f70744b419a3ca4a7a1218f0eeaf419dc37589. Future scope and historical dependency relationships remain open or preserved as recorded."
resolution: null
duplicate_of: null
---
GET pulls with windows by limit and after, POST pulls-refresh with more, the fake gh pages, and a test that no written file carries a credential. Listing touches no Git.

## Notes

2026-11-02: GET pulls and POST pulls-refresh in sidekick.py and pull_list_route.py; goldens cli-github-pulls.tryscript.md, cli-github-pulls-refresh.txt, cli-github-pulls-failures.txt; parity rows; tests/test_github_pull_list.py including a source directory with no store and no written file carrying a credential. Ten mutation checks caught. PR 279.

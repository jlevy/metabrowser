---
type: is
id: is-01m6f3a84d9w0j3vvq3dx4w5h1
title: "Pulls panel: rows, filters, states, keyboard"
kind: task
status: in_progress
priority: 1
version: 6
spec_path: docs/project/specs/active/plan-2026-10-01-github-pulls-tab.md
delegate: claude-code@spud10
labels: []
dependencies:
  - type: blocks
    target: is-01m6f3a8hwmhajkj14c5528pc8
  - type: blocks
    target: is-01m6f3djrrnd70jq09ttmspt0j
parent_id: is-01m2h7jjgpzyfbf10238j32z6q
hold: null
hold_until: null
created_at: 2026-11-02T21:40:44.300Z
updated_at: 2026-11-03T04:35:54.203Z
started_at: 2026-11-03T00:48:46.428Z
---
pulls-panel.js with describe and a controller run browserlessly. All as default, reaching the end loads more, each gh state with what to do, roving focus, a live region, and the marked current row. Text only.

## Notes

2026-11-03, PR 285: builtin_plugins/github/pulls-panel.js, describePulls and createPullsController run browserlessly in tests/dom/github-pulls-panel-session.js on a recording of the real server (tests/test_github_pulls_panel_session.py), golden cli-ui-github-pulls-panel.tryscript.md. All default, windows, Load more and reaching the end, each typed gh state, polling only while shown, live region, current row, text only.

2026-11-03 (PR #285 addressing): rows are a tree's items (A5), the row follows the baseline recipe and is registered in _baseline_rows (A4), ages are told again in place (A6), an append builds only its rows (B2), a poll reads the top window (B3), /pulls with no rows says why (A10). The panel session's paint section builds the list in a stand-in DOM.

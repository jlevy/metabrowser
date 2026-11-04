---
type: is
id: is-01m6f3a84d9w0j3vvq3dx4w5h1
title: "Pulls panel: rows, filters, states, keyboard"
kind: task
status: closed
priority: 1
version: 7
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
updated_at: 2026-11-04T17:14:29.442Z
started_at: 2026-11-03T00:48:46.428Z
closed_at: 2026-11-04T17:14:29.442Z
close_reason: "Scoped implementation independently reviewed and tested; owning feature PRs are actually merged. Final main https://github.com/jlevy/metabrowser/commit/db52ec09cf839269da3a56fd396e44f3092995a9 includes account fix https://github.com/jlevy/metabrowser/pull/297 and documentation https://github.com/jlevy/metabrowser/pull/298, with final manual acceptance and per-issue qualifications checked. Individual source, test, review and merge evidence: ACTION-PLAN.json SHA-256 d0867a696ee055cc27911e83c4f70744b419a3ca4a7a1218f0eeaf419dc37589. Future scope and historical dependency relationships remain open or preserved as recorded."
resolution: null
duplicate_of: null
---
pulls-panel.js with describe and a controller run browserlessly. All as default, reaching the end loads more, each gh state with what to do, roving focus, a live region, and the marked current row. Text only.

## Notes

2026-11-03, PR 285: builtin_plugins/github/pulls-panel.js, describePulls and createPullsController run browserlessly in tests/dom/github-pulls-panel-session.js on a recording of the real server (tests/test_github_pulls_panel_session.py), golden cli-ui-github-pulls-panel.tryscript.md. All default, windows, Load more and reaching the end, each typed gh state, polling only while shown, live region, current row, text only.

2026-11-03 (PR #285 addressing): rows are a tree's items (A5), the row follows the baseline recipe and is registered in _baseline_rows (A4), ages are told again in place (A6), an append builds only its rows (B2), a poll reads the top window (B3), /pulls with no rows says why (A10). The panel session's paint section builds the list in a stand-in DOM.

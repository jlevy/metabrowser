---
type: is
id: is-01m0wrpxfbmxdjaew4e3v6w19s
title: Move the commit change summary into the Git metadata header
kind: task
status: closed
priority: 1
version: 6
spec_path: docs/project/specs/active/plan-2026-08-25-git-revision-navigation-performance.md
labels: []
dependencies:
  - type: blocks
    target: is-01m0w542g2gzak7th85hx2bdz8
parent_id: is-01m0w52mbqvhdj9r2et2eh9p55
created_at: 2026-08-25T15:30:36.138Z
updated_at: 2026-08-25T15:45:10.652Z
closed_at: 2026-08-25T15:45:10.651Z
close_reason: Aggregate change totals now live beside commit identity above the description; revision-hosted diffs omit only the duplicate summary. Focused, full, and visible-browser acceptance passed.
resolution: null
duplicate_of: null
---
Files/functions: src/metabrowser/static/git-panel.js renderCommitDetail and a focused renderCommitSummary helper; src/metabrowser/builtin_plugins/diff/index.js revision mount path; src/metabrowser/builtin_plugins/diff/diff-view.js mountDiffView/renderDiffToolbar; src/metabrowser/static/styles.css; tests/dom/git-panel-behavior.js; tests/dom/diff-view-behavior.js; CHANGELOG.md and the active spec. Behavior/invariants: show files changed and +N/−N beside revision, author, and age before the commit body; direct patch/diff views retain their toolbar summary; revision-hosted diffs omit the lower duplicate while retaining the layout control; exact/estimated semantics and empty/bounded states stay truthful. Acceptance: focused tests prove ordering and single-summary behavior, direct diff behavior remains covered, both themes/narrow layout are visually checked, make format and make verify pass.

## Notes

Implemented renderCommitSummary in git-panel.js and summary-free revision mounts through diff/index.js plus mountDiffView/renderDiffToolbar. Focused DOM tests, make format, make lint-check, and make verify pass (1,545 tests, 48 goldens). Visible-browser validation on the trading repository confirms one header summary before the description, no hosted diff duplicate, the layout toolbar remains, and semantic colors work in dark and light themes.

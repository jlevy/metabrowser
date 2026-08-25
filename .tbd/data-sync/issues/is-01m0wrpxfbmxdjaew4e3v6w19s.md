---
type: is
id: is-01m0wrpxfbmxdjaew4e3v6w19s
title: Move the commit change summary into the Git metadata header
kind: task
status: in_progress
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-08-25-git-revision-navigation-performance.md
labels: []
dependencies:
  - type: blocks
    target: is-01m0w542g2gzak7th85hx2bdz8
parent_id: is-01m0w52mbqvhdj9r2et2eh9p55
created_at: 2026-08-25T15:30:36.138Z
updated_at: 2026-08-25T15:30:43.396Z
---
Files/functions: src/metabrowser/static/git-panel.js renderCommitDetail and a focused renderCommitSummary helper; src/metabrowser/builtin_plugins/diff/index.js revision mount path; src/metabrowser/builtin_plugins/diff/diff-view.js mountDiffView/renderDiffToolbar; src/metabrowser/static/styles.css; tests/dom/git-panel-behavior.js; tests/dom/diff-view-behavior.js; CHANGELOG.md and the active spec. Behavior/invariants: show files changed and +N/−N beside revision, author, and age before the commit body; direct patch/diff views retain their toolbar summary; revision-hosted diffs omit the lower duplicate while retaining the layout control; exact/estimated semantics and empty/bounded states stay truthful. Acceptance: focused tests prove ordering and single-summary behavior, direct diff behavior remains covered, both themes/narrow layout are visually checked, make format and make verify pass.

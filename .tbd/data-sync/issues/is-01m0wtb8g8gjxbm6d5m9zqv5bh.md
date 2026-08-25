---
type: is
id: is-01m0wtb8g8gjxbm6d5m9zqv5bh
title: Consolidate the Git commit summary component
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
created_at: 2026-08-25T15:59:11.367Z
updated_at: 2026-08-25T15:59:16.435Z
---
Files/functions: src/metabrowser/static/git-panel.js renderCommitSummary, renderCommitChangeStats, and renderCommitDetail; src/metabrowser/static/styles.css component selectors; tests/dom/git-panel-behavior.js; tests/test_design_vocabulary.py; docs/design-system.md; active Git revision navigation plan; PR #82. Behavior/invariants: one named renderCommitSummary helper and one .git-commit-summary root own the subject, revision/copy affordance, author, age, aggregate change stats, refs, and optional description; renderCommitDetail composes that root with comparison and bounded-file surfaces rather than assembling summary fragments; change stats have a distinct child name; ordering, truthful unknown totals, semantic colors, escaped content, and exact copy payload remain unchanged. Acceptance: focused DOM tests pin one component root and its anatomy/order, a static design-system test ties the documented contract to renderer and CSS, make format and make verify pass, visible browser smoke remains clean, commit is pushed to PR #82, and the bead is closed and synced.

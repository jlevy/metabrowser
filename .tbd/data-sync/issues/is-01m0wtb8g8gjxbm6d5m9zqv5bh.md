---
type: is
id: is-01m0wtb8g8gjxbm6d5m9zqv5bh
title: Consolidate the Git commit summary component
kind: task
status: closed
priority: 1
version: 7
spec_path: docs/project/specs/active/plan-2026-08-25-git-revision-navigation-performance.md
labels: []
dependencies:
  - type: blocks
    target: is-01m0w542g2gzak7th85hx2bdz8
  - type: blocks
    target: is-01m0x2ayvesqex8163ch5n72s5
  - type: blocks
    target: is-01m0yh4s21r569a73k1kaz8p35
parent_id: is-01m0w52mbqvhdj9r2et2eh9p55
created_at: 2026-08-25T15:59:11.367Z
updated_at: 2026-08-26T07:56:50.610Z
closed_at: 2026-08-25T16:21:38.399Z
close_reason: "The Git commit summary now has one renderer, semantic root, named change-stats child, documented design-system contract, maintained tests, and green focused/full/browser acceptance. Commit 6edbb58 is pushed to PR #82."
resolution: null
duplicate_of: null
---
Files/functions: src/metabrowser/static/git-panel.js renderCommitSummary, renderCommitChangeStats, and renderCommitDetail; src/metabrowser/static/styles.css component selectors; tests/dom/git-panel-behavior.js; tests/test_design_vocabulary.py; docs/design-system.md; active Git revision navigation plan; PR #82. Behavior/invariants: one named renderCommitSummary helper and one .git-commit-summary root own the subject, revision/copy affordance, author, age, aggregate change stats, refs, and optional description; renderCommitDetail composes that root with comparison and bounded-file surfaces rather than assembling summary fragments; change stats have a distinct child name; ordering, truthful unknown totals, semantic colors, escaped content, and exact copy payload remain unchanged. Acceptance: focused DOM tests pin one component root and its anatomy/order, a static design-system test ties the documented contract to renderer and CSS, make format and make verify pass, visible browser smoke remains clean, commit is pushed to PR #82, and the bead is closed and synced.

## Notes

Implemented one pure renderCommitSummary component root for subject, metadata, change stats, refs, and optional body; renamed the aggregate child renderCommitChangeStats/.git-commit-change-stats; reduced renderCommitDetail to composition. The design system documents anatomy, ownership, unknown-total and hosted-diff rules; the static vocabulary registry prevents fragment drift. Focused tests, make format, make verify (1,546 tests, 48 goldens), precommit, prepush, a visible trading-repo smoke, copy feedback, and exact-head git-revisions validation pass at 6edbb58.

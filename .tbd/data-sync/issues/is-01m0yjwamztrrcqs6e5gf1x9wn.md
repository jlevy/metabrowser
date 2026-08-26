---
type: is
id: is-01m0yjwamztrrcqs6e5gf1x9wn
title: Render commit descriptions as standard prose
kind: feature
status: in_progress
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-08-25-git-revision-navigation-performance.md
labels: []
dependencies: []
parent_id: is-01m0w52mbqvhdj9r2et2eh9p55
created_at: 2026-08-26T08:27:10.868Z
updated_at: 2026-08-26T08:28:27.641Z
---
Files and interfaces: update .git-commit-body in src/metabrowser/static/styles.css; update the typography contract in tests/test_chrome_typography.py, the shared commit-summary contract in tests/test_design_vocabulary.py, docs/design-system.md, the active Git revision plan, and CHANGELOG.md. Behavior and invariants: a non-empty commit body remains an optional full-summary-only block, preserves authored newlines and wrapping, uses the normal application sans face and standard body size, remains escaped by renderCommitSummary, and does not appear for an empty body or in compact pointer tooltips. Acceptance: focused typography/design/DOM tests pass; headed real-browser validation uses a commit with a non-empty multiline body; make format and make verify pass.

---
type: is
id: is-01m0yjwamztrrcqs6e5gf1x9wn
title: Render commit descriptions as standard prose
kind: feature
status: closed
priority: 1
version: 5
spec_path: docs/project/specs/active/plan-2026-08-25-git-revision-navigation-performance.md
labels: []
dependencies:
  - type: blocks
    target: is-01m0w542g2gzak7th85hx2bdz8
parent_id: is-01m0w52mbqvhdj9r2et2eh9p55
created_at: 2026-08-26T08:27:10.868Z
updated_at: 2026-08-26T08:59:44.048Z
closed_at: 2026-08-26T08:46:48.087Z
close_reason: Commit descriptions render as standard-size sans-serif prose with preserved newlines; focused, browser, and full verification are green.
resolution: null
duplicate_of: null
---
Files and interfaces: update .git-commit-body in src/metabrowser/static/styles.css; update the typography contract in tests/test_chrome_typography.py, the shared commit-summary contract in tests/test_design_vocabulary.py, docs/design-system.md, the active Git revision plan, and CHANGELOG.md. Behavior and invariants: a non-empty commit body remains an optional full-summary-only block, preserves authored newlines and wrapping, uses the normal application sans face and standard body size, remains escaped by renderCommitSummary, and does not appear for an empty body or in compact pointer tooltips. Acceptance: focused typography/design/DOM tests pass; headed real-browser validation uses a commit with a non-empty multiline body; make format and make verify pass.

## Notes

Implemented the full-only commit body as standard sans-serif prose at --body-font-size while preserving exact authored newlines with pre-wrap. TDD changed the typography allowlist/design-vocabulary/DOM assertions before CSS. Focused typography, design, and DOM tests pass (35 tests). Headed real-browser validation on multiline commit 1d115a374fa47b6017bedad838e1fedb2e73930d confirms system-ui sans, 14px text, white-space: pre-wrap, and three preserved lines in light and dark. Palette validation on the same build confirms medium 9% pure rows; light 3% refined unchanged rows; darkest composite intraline spans in light/dark and Split/Unified. make format and make verify pass: 1,564 tests, 48 golden scenarios, locked Python/npm audits, distribution inspection, and isolated installed-wheel smoke tests. Two host-load timing flakes were diagnosed without threshold changes; after terminating ten obsolete local scan servers, both timing tests passed five consecutive isolated runs and the full gate passed.

---
type: is
id: is-01m0x2ayvesqex8163ch5n72s5
title: Render bounded commit-summary tooltips
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
created_at: 2026-08-25T18:18:50.093Z
updated_at: 2026-08-25T18:19:05.222Z
---
Files/functions: src/metabrowser/static/git-panel.js renderCommitSummary/renderCommitChangeStats plus a compact tooltip projection and scheduleHover/cancelHover; src/metabrowser/static/styles.css commit-summary tooltip modifier; tests/dom/git-panel-behavior.js; tests/test_design_vocabulary.py; docs/design-system.md; active plan; CHANGELOG.md. Behavior/invariants: hovering or focusing a Git history row presents one bounded rich tooltip that reuses the selected commit summary vocabulary for subject, author, short revision with a noninteractive copy glyph, age, changed-file count, additions, and deletions. The long commit body and refs do not enter the tooltip. The subject truncates to a small fixed line count, unknown totals remain unknown, content is escaped, and the tooltip stays supplementary and noninteractive under the shared tooltip lifecycle. The actual copy button remains in the selected summary. Pointer and keyboard intent share detail preparation without duplicate requests; leaving/blur hides the tooltip without canceling a still-active modality. Acceptance: focused tests fail before and pass after; design-system contract documents and enforces the compact variant and noninteractive copy glyph; make format and make verify pass; real-browser validation covers hover, focus, long messages, unknown totals, both themes, dismissal, and unchanged selection/copy behavior.

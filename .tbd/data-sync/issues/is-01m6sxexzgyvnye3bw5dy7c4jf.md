---
type: is
id: is-01m6sxexzgyvnye3bw5dy7c4jf
title: Keep PR rows collapsed during Up and Down navigation
kind: bug
status: in_progress
priority: 2
version: 4
spec_path: docs/project/specs/active/plan-2026-10-01-github-pulls-tab.md
labels: []
dependencies:
  - type: blocks
    target: is-01m6sxeyax9gqajg1b3csc9gmq
parent_id: is-01m6f3n89kn7ztmfhrzswxnsgz
created_at: 2026-11-07T02:30:05.039Z
updated_at: 2026-11-07T03:38:21.580Z
---
Match Files keyboard navigation. Up and Down change the active Pulls row without opening its changed-file tree or fetching its file list. A deliberate PR-row click or explicit tree expansion opens that tree. Retain explicit expansion state across selection and test held keys, click, and both source modes.

## Notes

Implemented in b80da2e0. Keyboard selection and Enter preserve reader disclosure. Click toggles the row tree, Right expands, and explicit file links reveal their owner. Browser Down steps through real PRs with no open file trees. Focus, history, and viewport regressions pass.

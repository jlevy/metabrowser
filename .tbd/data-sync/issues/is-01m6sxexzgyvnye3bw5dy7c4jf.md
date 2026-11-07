---
type: is
id: is-01m6sxexzgyvnye3bw5dy7c4jf
title: Keep PR rows collapsed during Up and Down navigation
kind: bug
status: closed
priority: 2
version: 6
spec_path: docs/project/specs/active/plan-2026-10-01-github-pulls-tab.md
labels: []
dependencies:
  - type: blocks
    target: is-01m6sxeyax9gqajg1b3csc9gmq
parent_id: is-01m6f3n89kn7ztmfhrzswxnsgz
created_at: 2026-11-07T02:30:05.039Z
updated_at: 2026-11-07T04:55:40.179Z
closed_at: 2026-11-07T04:55:40.178Z
close_reason: "PR #319 at f61dad59 is mergeable with green CI and all review threads resolved. Keyboard selection, explicit disclosure, same-PR file identity and history/focus regression sessions passed, with checkout and managed browser verification."
resolution: null
duplicate_of: null
---
Match Files keyboard navigation. Up and Down change the active Pulls row without opening its changed-file tree or fetching its file list. A deliberate PR-row click or explicit tree expansion opens that tree. Retain explicit expansion state across selection and test held keys, click, and both source modes.

## Notes

PR #319 distinguishes the actual changed-file path from duplicate route notices. A new same-PR file address reopens its owner, while repeated notices preserve manual collapse. Enter/Space and same-PR preview navigation preserve disclosure by design, recorded on the review thread. Targeted history/focus/disclosure regressions pass; final forward integration is ab905365.

---
type: is
id: is-01m6f3a9tmf2t5m4pcb97gfr0j
title: Changed-files tree model
kind: task
status: in_progress
priority: 1
version: 5
spec_path: docs/project/specs/active/plan-2026-10-01-github-pulls-tab.md
delegate: claude-code@spud10
labels: []
dependencies:
  - type: blocks
    target: is-01m6f3aa89emxbf0rwesa8gt7x
parent_id: is-01m6f39zpnk9rc3kjy552b88qj
hold: null
hold_until: null
created_at: 2026-11-02T21:40:46.035Z
updated_at: 2026-11-03T04:31:40.752Z
started_at: 2026-11-03T03:58:48.569Z
---
Browserless: a tree from a list, single-child folder chains as one row, renames, expansion state, the measured auto-expand rule, a cut list, and each gh state.

## Notes

2026-11-03: done on claude/pulls-4-files (78677a66, fixture chain renamed in a84968ab). builtin_plugins/github/pull-files-tree.js: buildFileTree, visibleRows (single-child folder chains as one row), initialExpansion (threshold is a parameter; judged by the Link page count while filling; folders a later page brings follow the same rule), toggleFolder per chain, revealPath and current, holdFileList (offset polling while one list fills, restart at 0 on another read), describeFileList (absent/pending/filling/stopped/stale/current, honest count, capped, truncated, failure). Session tests/dom/github-pull-files-tree-session.js on a recording of real route answers (tests/fixtures/github-pull-files-responses.json, a list caught between its pages), golden cli-ui-github-pull-files-tree.tryscript.md, parity row github.pull-files-tree. Build+flatten measured: 1.3 ms at 1,183 real files, 3.7 ms at 3,000 (Node 24.19, load 4.5). The auto-expand constant is mb-jagq's to measure in a real browser.

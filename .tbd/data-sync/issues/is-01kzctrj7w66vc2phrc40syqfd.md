---
type: is
id: is-01kzctrj7w66vc2phrc40syqfd
title: "git: log parsing, decorations, and paging cursor"
kind: task
status: closed
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-08-06-git-graph-view.md
labels: []
dependencies:
  - type: blocks
    target: is-01kzctrvcdztesz9gabmf7zfsn
parent_id: is-01kzctqt5s7te6w75jm5pvg6g7
created_at: 2026-08-07T00:42:54.587Z
updated_at: 2026-08-07T01:29:02.979Z
closed_at: 2026-08-07T01:29:02.979Z
close_reason: null
---
Add metabrowser/git/log.py: build the git log argv, parse NUL-delimited output into GitCommit records, parse %D decorations into GitRef with VS Code precedence ordering, and implement the opaque paging cursor over a stable ordering.

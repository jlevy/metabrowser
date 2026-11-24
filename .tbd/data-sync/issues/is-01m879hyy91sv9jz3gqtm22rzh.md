---
type: is
id: is-01m879hyy91sv9jz3gqtm22rzh
title: Let wide Markdown tables use surplus reading-pane width
kind: task
status: in_progress
priority: 2
version: 8
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/787
    at: 2026-11-24T17:37:41.870Z
delegate: codex@macbookpro
labels: []
dependencies: []
hold: null
hold_until: null
created_at: 2026-11-24T17:27:16.680Z
updated_at: 2026-11-24T19:12:00.947Z
started_at: 2026-11-24T19:12:00.946Z
---
A wide table in a standalone rendered Markdown document, including the three-column table in docs/project/architecture/arch-diff-pipeline.md, should grow beyond the prose measure when the reading pane has room. Preserve the existing display at medium and narrow pane widths, the prose measure, the TOC, and internal scrolling when a table is wider than the space available. Check the pinned KPress support first and verify actual layout across width bands.

## Notes

PR #787 integrated head e109fdcecbdbe3ce64b1930d4671b6f246808358 contains exact main 70fc5bc8ebca8eb4361b2f8a70a47c5febf026db and the independently verified tree 2b044f329ed7232bb4b8eb7e05a79408807a052d. Standard run 45456912631 passed the full matrix on all supported Python versions; ci-ok job 138672795894 issued main-red run=45454448848 head=70fc5bc8ebca8eb4361b2f8a70a47c5febf026db tested=yes. The exact hosted full verify 45456971323 is running. Prior pre-integration full verify 45451488482 passed. Main fixture timeouts are tracked separately in mb-7a2y.

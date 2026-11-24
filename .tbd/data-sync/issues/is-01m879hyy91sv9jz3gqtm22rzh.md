---
type: is
id: is-01m879hyy91sv9jz3gqtm22rzh
title: Let wide Markdown tables use surplus reading-pane width
kind: task
status: in_progress
priority: 2
version: 4
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/787
    at: 2026-11-24T17:37:41.870Z
labels: []
dependencies: []
created_at: 2026-11-24T17:27:16.680Z
updated_at: 2026-11-24T17:37:44.194Z
---
A wide table in a standalone rendered Markdown document, including the three-column table in docs/project/architecture/arch-diff-pipeline.md, should grow beyond the prose measure when the reading pane has room. Preserve the existing display at medium and narrow pane widths, the prose measure, the TOC, and internal scrolling when a table is wider than the space available. Check the pinned KPress support first and verify actual layout across width bands.

## Notes

PR #787 at 07b512e7bd306a49692fa520862eabafda19a794. Chrome regression passed for the real architecture table across wide/medium/narrow panes and a compact table at desktop width. Trusted and untrusted Chrome and native WKWebView draw the same responsive layout, up to small engine rounding. Standard CI and isolated full release verification are pending.

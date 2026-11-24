---
type: is
id: is-01m879hyy91sv9jz3gqtm22rzh
title: Let wide Markdown tables use surplus reading-pane width
kind: task
status: in_progress
priority: 2
version: 5
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/787
    at: 2026-11-24T17:37:41.870Z
labels: []
dependencies: []
created_at: 2026-11-24T17:27:16.680Z
updated_at: 2026-11-24T17:42:56.137Z
---
A wide table in a standalone rendered Markdown document, including the three-column table in docs/project/architecture/arch-diff-pipeline.md, should grow beyond the prose measure when the reading pane has room. Preserve the existing display at medium and narrow pane widths, the prose measure, the TOC, and internal scrolling when a table is wider than the space available. Check the pinned KPress support first and verify actual layout across width bands.

## Notes

PR #787 at 0c69c68d4c093268c17cf1d932d9608a340d37a2. Chrome regression and native WKWebView passed at desktop, medium, and narrow widths in both trust profiles. A follow-up updates the two static KPress layout assertions, with all 13 focused tests passing. Exact-head standard CI 45451456976 and full make verify 45451488482 are running.

---
type: is
id: is-01m879hyy91sv9jz3gqtm22rzh
title: Let wide Markdown tables use surplus reading-pane width
kind: task
status: in_progress
priority: 2
version: 2
labels: []
dependencies: []
created_at: 2026-11-24T17:27:16.680Z
updated_at: 2026-11-24T17:27:40.831Z
---
A wide table in a standalone rendered Markdown document, including the three-column table in docs/project/architecture/arch-diff-pipeline.md, should grow beyond the prose measure when the reading pane has room. Preserve the existing display at medium and narrow pane widths, the prose measure, the TOC, and internal scrolling when a table is wider than the space available. Check the pinned KPress support first and verify actual layout across width bands.

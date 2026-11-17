---
type: is
id: is-01m7hcgkr63xw09pjk9a49kj85
title: "Commit page and PR Changes: no rule under the Split/Unified chooser"
kind: task
status: closed
priority: 2
version: 3
spec_path: docs/project/specs/done/plan-2026-11-15-files-grouping-diff-summary-and-pull-stacks.md
labels: []
dependencies: []
parent_id: is-01m7dm3az28qmj39y5hmdq2k0v
created_at: 2026-11-16T05:15:40.677Z
updated_at: 2026-11-17T05:59:27.151Z
closed_at: 2026-11-16T06:21:26.325Z
close_reason: "Delivered in #474 (4b8edd731): no rule under the Split/Unified chooser on commit, PR Changes and patch views; measured."
resolution: null
duplicate_of: null
---
Owner, 2026-11-15: "also let's drop the extra horizontal rule below the unified | split chooser on commits or the changes tab on PRs". Measured on a commit page: .diff-toolbar has border-bottom 1px (y=248), then 12px, then the first .diff-file card's own top border. Since mb-pb35 moved the Diff summary to the page top, that toolbar holds only the chooser.

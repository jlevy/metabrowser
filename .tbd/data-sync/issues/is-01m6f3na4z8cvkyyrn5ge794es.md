---
type: is
id: is-01m6f3na4z8cvkyyrn5ge794es
title: Split diff in a narrow pane hides additions as blank space
kind: bug
status: in_progress
priority: 1
version: 3
delegate: claude-code@spud10
labels:
  - release:v0.12.0
dependencies: []
parent_id: is-01m6f3n89kn7ztmfhrzswxnsgz
hold: null
hold_until: null
created_at: 2026-11-02T21:46:46.813Z
updated_at: 2026-11-03T07:00:49.534Z
started_at: 2026-11-02T21:47:04.983Z
---
Fixed in 5a4881ec on claude/v012-pr-review-workflows: Unified below 618 px, Split returns at 638 px, the stored choice is untouched. Verified in the app's own pane at 313 px, and wide panes are byte-identical. It touches plain-folder commit diffs in narrow panes only. Close when it merges.

## Notes

2026-11-03: fixed on PR 280 (5a4881ec); review C1's first-layout flash fixed at ca450430, measured in Chrome as one layout per load. CI green. Closes when the stack merges.

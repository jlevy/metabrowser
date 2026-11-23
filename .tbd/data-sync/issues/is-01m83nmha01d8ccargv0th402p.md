---
type: is
id: is-01m83nmha01d8ccargv0th402p
title: "Diff file header: Rendered | Source right-aligned, copy-path on hover beside the name"
kind: task
status: in_progress
priority: 2
version: 3
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/748
    at: 2026-11-23T08:26:37.593Z
delegate: claude-code@spud10
labels: []
dependencies: []
hold: null
hold_until: null
created_at: 2026-11-23T07:41:26.206Z
updated_at: 2026-11-23T08:26:37.596Z
started_at: 2026-11-23T07:42:58.234Z
---
On the diff Changes view the Rendered | Source chooser sits next to the file name and the copy-path icon is right-aligned. Swap: the chooser aligns right on the file header bar, and the copy-path control appears on hover (and focus) immediately right of the file name. Keep keyboard reachability, design tokens, and the bar-as-activation-surface behaviour. Done: CSS and markup change in builtin_plugins/diff, verified in headless Chrome with screenshots, design-system doc updated.

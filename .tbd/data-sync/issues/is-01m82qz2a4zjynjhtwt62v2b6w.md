---
type: is
id: is-01m82qz2a4zjynjhtwt62v2b6w
title: Keep Command-L Open URL progress visible until a browsing window appears
kind: bug
status: in_progress
priority: 1
version: 3
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/712
    at: 2026-11-22T23:41:12.418Z
delegate: codex@spud10
labels: []
dependencies: []
parent_id: is-01m7hgpc9550w78kmwqsvv64xh
hold: null
hold_until: null
created_at: 2026-11-22T23:02:54.011Z
updated_at: 2026-11-22T23:41:12.431Z
started_at: 2026-11-22T23:04:29.222Z
---
Keep the native Open URL dialog open with progress after submitting a target. Close when its destination window is visible and can show server progress, or retain the field and display the recoverable error. Preserve accessibility, coherent repeated-submit and cancellation behavior, and flows that open a reused window.

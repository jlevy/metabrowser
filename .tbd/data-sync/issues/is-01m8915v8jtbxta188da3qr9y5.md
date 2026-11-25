---
type: is
id: is-01m8915v8jtbxta188da3qr9y5
title: "Hunk gap: one line past MAX_LINES_ANSWER_BYTES is drawn whole, up to MAX_LINES_SIDE_BYTES in one task"
kind: task
status: open
priority: 3
version: 1
labels: []
dependencies: []
created_at: 2026-11-25T09:39:19.948Z
updated_at: 2026-11-25T09:39:19.948Z
---
Follow-up from PR #830 review A2 (https://github.com/jlevy/metabrowser/pull/830#pullrequestreview-6054720489). side_lines keeps at least one line per answer so a reader is never stuck, so an unchanged line longer than MAX_LINES_ANSWER_BYTES (512 KiB, diff/side_lines.py) is answered and drawn whole, up to MAX_LINES_SIDE_BYTES (16 MiB). Measured 2026-11-25 in headless Chrome at load ~230: a 1 MiB line drew in 98-107 ms and a 4 MiB line in 424-487 ms, each in one task, so a 16 MiB line would be near 2 s. Options: refuse such a line with a 409 code the page shows as a plain bar for that gap only, or draw a long line's head with a way to show the rest. Needs a design decision; waits on PR #830 merging.

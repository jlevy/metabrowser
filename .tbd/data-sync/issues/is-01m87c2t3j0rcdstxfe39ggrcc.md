---
type: is
id: is-01m87c2t3j0rcdstxfe39ggrcc
title: "Give a diff file bar with a mode-change note a lead basis wide enough for its group (review B1 on #759)"
kind: bug
status: open
priority: 3
version: 1
labels: []
dependencies: []
created_at: 2026-11-24T18:11:25.930Z
updated_at: 2026-11-24T18:11:25.930Z
---
--diff-file-lead-basis (diff plugin styles.css) was set from a bar's stats alone. A name's group that also holds a mode-change note needs more, so View file stays on the line and squeezes the group: from 379 to 299 px the change letter falls under Copy path, and with wide stats the note under View file or View on branch, visible at rest. Not a regression (the merge base overlapped at the same widths). Fix: widen the basis for a bar with a note, and add that bar to tests/test_diff_file_bar_chrome.py.

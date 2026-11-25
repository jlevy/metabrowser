---
type: is
id: is-01m87c2t3j0rcdstxfe39ggrcc
title: "Give a diff file bar with a mode-change note a lead basis wide enough for its group (review B1 on #759)"
kind: bug
status: open
priority: 3
version: 2
spec_path: docs/project/specs/active/plan-2026-08-17-general-diff-rendering.md
labels: []
dependencies: []
parent_id: is-01kxse0d3sm8h0p1yh1mjwgbxz
created_at: 2026-11-24T18:11:25.930Z
updated_at: 2026-11-25T02:34:28.402Z
---
--diff-file-lead-basis (diff plugin styles.css) was set from a bar's stats alone. A name's group that also holds a mode-change note needs more, so View file stays on the line and squeezes the group: from 379 to 299 px the change letter falls under Copy path, and with wide stats the note under View file or View on branch, visible at rest. Not a regression (the merge base overlapped at the same widths). Fix: widen the basis for a bar with a note, and add that bar to tests/test_diff_file_bar_chrome.py.

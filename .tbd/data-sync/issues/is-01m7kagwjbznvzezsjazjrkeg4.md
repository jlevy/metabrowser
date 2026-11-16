---
type: is
id: is-01m7kagwjbznvzezsjazjrkeg4
title: "Font sizes follow one type scale by role: secondary metadata (ages, 'Updated just now', 'Fetched just now via GitHub CLI', counts) is one size everywhere unless a stated reason differs; main-view metadata at the body size"
kind: task
status: in_progress
priority: 1
version: 2
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m7dm3az28qmj39y5hmdq2k0v
hold: null
hold_until: null
created_at: 2026-11-16T23:19:21.413Z
updated_at: 2026-11-16T23:20:08.998Z
started_at: 2026-11-16T23:20:08.996Z
---
Owner, 2026-11-16: 'review font size for consistency in our design system. "Updated just now" on the nav panel in PR tab is larger than "Fetched just now via GitHub CLI" in the PR main body. Things like update time and less important metadata like that should all be the same size unless there's a specific reason to make it larger or smaller. Probably the small font size on the main view should actually be the regular body size. The diff summary text on the toggle is also too small, at least in the current version I'm seeing right now.' Stacked on #487 (header parity), which already moves the PR page's status line and the Diff summary to the body size.

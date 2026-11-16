---
type: is
id: is-01m7hh0vgfbenvcjgxf4q1cv0d
title: "PR #466 B4: keep less state per group in the pass"
kind: bug
status: closed
priority: 3
version: 3
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m7hcjpsxhfvt5ms7769smjwf
hold: null
hold_until: null
created_at: 2026-11-16T06:34:27.214Z
updated_at: 2026-11-16T07:26:37.173Z
started_at: 2026-11-16T06:34:37.922Z
closed_at: 2026-11-16T07:26:37.172Z
close_reason: "fixed in 9ae55a4 (adopted: pass 1.5-1.9x faster, peak 54.5 to 9.1 MB, differential identical); PR #466 review B"
resolution: null
duplicate_of: null
---
Suggestion. python_inventory.py:497-536. Review B https://github.com/jlevy/metabrowser/pull/466#pullrequestreview-5915875839. Adopt if the pass's time does not get worse, else defer under is-01m7dm3az28qmj39y5hmdq2k0v.

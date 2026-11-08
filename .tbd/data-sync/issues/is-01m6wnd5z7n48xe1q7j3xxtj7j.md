---
type: is
id: is-01m6wnd5z7n48xe1q7j3xxtj7j
title: Align Pulls Reload with the state filters and retain update status
kind: bug
status: in_progress
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-10-01-github-pulls-tab.md
delegate: codex@spud10
labels:
  - release:v0.12.0
dependencies:
  - type: blocks
    target: is-01m6wdjwawp9g1bvnefz2hxze3
parent_id: is-01m6f3n89kn7ztmfhrzswxnsgz
hold: null
hold_until: null
created_at: 2026-11-08T04:07:02.374Z
updated_at: 2026-11-08T04:10:49.661Z
started_at: 2026-11-08T04:10:49.373Z
---
User acceptance on November7: put the existing Reload button flush right on the same row as Open | Closed | All in the PR navigation panel. Keep the Updated just now status line in its existing location. Preserve one refresh action, spinner/error/reconnect semantics, filter tallies, sticky positioning and narrow-panel fit; verify the production controller/mount and real wide/narrow browser output. Include in the current UI follow-up stack, review, test and install.

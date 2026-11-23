---
type: is
id: is-01m8365jk440vdy3mjt5g8qft9
title: Center rendered diffs inside the full file card
kind: bug
status: closed
priority: 2
version: 5
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/728
    at: 2026-11-23T03:30:51.913Z
  - kind: other
    url: https://github.com/jlevy/metabrowser/actions/runs/45106819001
    at: 2026-11-23T03:43:31.931Z
delegate: codex@spud10
labels: []
dependencies: []
parent_id: is-01m7hgpc9550w78kmwqsvv64xh
hold: null
hold_until: null
created_at: 2026-11-23T03:11:07.354Z
updated_at: 2026-11-23T03:43:36.756Z
started_at: 2026-11-23T03:12:50.233Z
closed_at: 2026-11-23T03:43:36.745Z
close_reason: "Reviewed and merged in PR #728. Exact main CI passed. Chrome verified wide and narrow Markdown and structured layouts. The active macOS development app and folder server restarted on ed952387f and served the exact merged stylesheet."
resolution: null
duplicate_of: null
---
Center Markdown and structured content in each responsive Rendered diff. Keep each change gutter at the file card edge. Verify narrow and wide boxes, and keep Source governed by the existing split or unified layout.

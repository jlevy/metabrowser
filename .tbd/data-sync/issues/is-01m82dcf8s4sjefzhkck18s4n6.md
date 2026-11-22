---
type: is
id: is-01m82dcf8s4sjefzhkck18s4n6
title: Use the Files size style for PR overview diff sizes
kind: bug
status: in_progress
priority: 2
version: 3
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/695
    at: 2026-11-22T20:11:47.014Z
delegate: codex@spud10
labels: []
dependencies: []
parent_id: is-01m7hgpc9550w78kmwqsvv64xh
hold: null
hold_until: null
created_at: 2026-11-22T19:57:58.933Z
updated_at: 2026-11-22T20:11:47.051Z
started_at: 2026-11-22T20:01:36.681Z
---
Reuse the Files navigation byte formatter, blue size classes and shared emphasis threshold for compressed and raw diff sizes on the PR overview. Preserve line wording and separator accessibility, and verify the ink and formatting against real Files size cells.

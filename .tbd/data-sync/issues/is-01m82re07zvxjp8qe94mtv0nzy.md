---
type: is
id: is-01m82re07zvxjp8qe94mtv0nzy
title: Make the separate nav folder menu dismiss on repeat and outside clicks
kind: bug
status: in_progress
priority: 1
version: 5
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/713
    at: 2026-11-22T23:46:19.811Z
delegate: codex@spud10
labels: []
dependencies: []
parent_id: is-01m7hgpc9550w78kmwqsvv64xh
hold: null
hold_until: null
created_at: 2026-11-22T23:11:03.413Z
updated_at: 2026-11-23T00:02:34.067Z
started_at: 2026-11-22T23:12:01.412Z
---
Keep the navigation folder name and icon as Home, with the 0 shortcut, and keep the current separate details chevron and hover target. Clicking the separate trigger again closes the open menu. Clicking anywhere outside dismisses it. Preserve menu content, actions, and keyboard and screen-reader behavior.

## Notes

Production Chrome verified repeated chevron use, primary and auxiliary outside pointer clicks, stopped propagation, Escape, Home glyph and name, and outside dismissal with focus preserved in a sandboxed preview. The final #713 pinned-mirror fixture follows the new Home link semantics. All 143 related fixtures passed; current CI rerun 45086093814. Verified installed preview at 9c6e73b47.

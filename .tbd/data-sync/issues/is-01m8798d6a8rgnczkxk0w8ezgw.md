---
type: is
id: is-01m8798d6a8rgnczkxk0w8ezgw
title: Make the sidebar folder Info glyph easier to recognize
kind: bug
status: in_progress
priority: 2
version: 4
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/786
    at: 2026-11-24T18:30:59.039Z
delegate: codex@spud10.local
labels: []
dependencies: []
hold: null
hold_until: null
created_at: 2026-11-24T17:22:03.592Z
updated_at: 2026-11-24T18:30:59.042Z
started_at: 2026-11-24T17:22:28.092Z
---
Keep the circled Info convention and give the lowercase i a more distinct silhouette at sidebar scale. Verify the icon and existing menu behavior in both themes.

## Notes

Included in PR 786 at dc391a2f6ef6986e51209b16eab4ea3e7e4b6ae7, exact review 6044262407. Stronger lowercase i, same circle, kind-specific tooltip, and shared suppression while menu is open. The 202 focused checks passed. Standard CI 45449762455 and full verify 45449769481 running.

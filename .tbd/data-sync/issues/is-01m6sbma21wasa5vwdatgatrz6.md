---
type: is
id: is-01m6sbma21wasa5vwdatgatrz6
title: Add fixed keyboard shortcuts for the main tabs
kind: feature
status: in_progress
priority: 2
version: 3
delegate: codex@spud10.local
labels: []
dependencies: []
parent_id: is-01m6f3n89kn7ztmfhrzswxnsgz
hold: null
hold_until: null
created_at: 2026-11-06T21:18:26.870Z
updated_at: 2026-11-06T21:41:36.725Z
started_at: 2026-11-06T21:21:42.700Z
---
Order Files, Git, Pulls consistently and bind Command+1, Command+2, and Command+3. Preserve numbers when a tab is absent. Show the shortcuts in Help and document browser-reserved chords.

## Notes

Implemented at 8a3206fb above #307. Fixed Files/Git/Pulls order and Command-1/2/3 Help bindings, with plain-number fallback for browsers that reserve the Command chords. The production shell golden covers late and missing tabs. Built-in browser verified all chords, the fallback, and Help.

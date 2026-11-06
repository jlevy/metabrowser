---
type: is
id: is-01m6sbma21wasa5vwdatgatrz6
title: Add fixed keyboard shortcuts for the main tabs
kind: feature
status: closed
priority: 2
version: 5
delegate: codex@spud10.local
labels: []
dependencies: []
parent_id: is-01m6f3n89kn7ztmfhrzswxnsgz
hold: null
hold_until: null
created_at: 2026-11-06T21:18:26.870Z
updated_at: 2026-11-06T22:39:15.592Z
started_at: 2026-11-06T21:21:42.700Z
closed_at: 2026-11-06T22:39:15.591Z
close_reason: "Implemented, reviewed, installed, and verified in PR #308."
resolution: null
duplicate_of: null
---
Order Files, Git, Pulls consistently and bind Command+1, Command+2, and Command+3. Preserve numbers when a tab is absent. Show the shortcuts in Help and document browser-reserved chords.

## Notes

Completed in stacked PR #308 at 8a3206fb. The production session and built-in browser verified tab order, fixed Command numbers, fallbacks, and Help. Full local make verify and exact-head GitHub CI run 42304493081 passed, with no automated review findings. Installed in 0.11.1.dev1180+7b4b76ee.

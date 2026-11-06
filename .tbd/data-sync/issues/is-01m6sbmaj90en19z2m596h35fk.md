---
type: is
id: is-01m6sbmaj90en19z2m596h35fk
title: Include GitHub pull requests in Quick Search
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
created_at: 2026-11-06T21:18:27.400Z
updated_at: 2026-11-06T21:41:37.027Z
started_at: 2026-11-06T21:21:42.712Z
---
Rename Quick File to Quick Search and add lightweight PR completions by #number or title from the persisted catalog. Match existing navigation and accessibility behavior, keep network work bounded, and update the design and validation docs.

## Notes

Implemented above the shortcut layer through 983989a6. Plans, design, public guide, and parity map updated. Cache-only exact and title matches, mixed completions, one-entry PR navigation, shared cooldown, and refresh priority have focused coverage. Built-in browser verified a fresh checkout cache, the managed repository, an offline cached checkout, and plain-folder file search. Full gate is running.

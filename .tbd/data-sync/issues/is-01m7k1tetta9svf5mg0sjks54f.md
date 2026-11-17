---
type: is
id: is-01m7k1tetta9svf5mg0sjks54f
title: "The commit page's author reads as the pull request page's: one shared identity component (avatar slot then bold name), the same line order for shared parts"
kind: feature
status: closed
priority: 1
version: 3
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m7k1tdq21g63np2bkdr6fr29
hold: null
hold_until: null
created_at: 2026-11-16T20:47:17.850Z
updated_at: 2026-11-17T00:30:22.145Z
started_at: 2026-11-16T20:57:31.695Z
closed_at: 2026-11-17T00:30:22.144Z
close_reason: "Merged in #487 (6579c0d41)"
resolution: null
duplicate_of: null
---
Shared parts (author identity, age, Diff summary row, title treatment) take one shell component and one structure on both pages; commit-only parts (hash with copy, refs, body) and PR-only parts (state, branches, labels, stack chip) keep their own lines. The component lives in the shell so the core commit page can use it without reaching into the GitHub plugin.

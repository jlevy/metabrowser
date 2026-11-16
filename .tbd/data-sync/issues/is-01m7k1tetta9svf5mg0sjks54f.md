---
type: is
id: is-01m7k1tetta9svf5mg0sjks54f
title: "The commit page's author reads as the pull request page's: one shared identity component (avatar slot then bold name), the same line order for shared parts"
kind: feature
status: open
priority: 1
version: 1
labels: []
dependencies: []
parent_id: is-01m7k1tdq21g63np2bkdr6fr29
created_at: 2026-11-16T20:47:17.850Z
updated_at: 2026-11-16T20:47:17.850Z
---
Shared parts (author identity, age, Diff summary row, title treatment) take one shell component and one structure on both pages; commit-only parts (hash with copy, refs, body) and PR-only parts (state, branches, labels, stack chip) keep their own lines. The component lives in the shell so the core commit page can use it without reaching into the GitHub plugin.

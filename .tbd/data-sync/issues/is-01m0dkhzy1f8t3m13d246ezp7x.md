---
type: is
id: is-01m0dkhzy1f8t3m13d246ezp7x
title: "Patch and PR containers: file changes as tree entries"
kind: feature
status: open
priority: 1
version: 1
labels: []
dependencies: []
created_at: 2026-08-19T18:11:55.456Z
updated_at: 2026-08-19T18:11:55.456Z
---
Adopt the nav-container contract for comparisons: a .patch/.diff file (and later a PR mirror) is folder-like; its children are the manifest's file changes with the same change indicators GitHub uses (A/D/M/R with old path, mode, type, binary); outer selection opens today's whole-document diff view as the overview; inner selection opens a single file-change document whose default tab is Diff. Needs the single-file-change envelope (kind + views for one FileChange plus its patch) and container children fed from the manifest — the /api/diff manifest route (mb-27dr) or the plugin document hook. Blocked by the container contract bead.

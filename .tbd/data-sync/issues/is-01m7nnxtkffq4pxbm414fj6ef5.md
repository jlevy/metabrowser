---
type: is
id: is-01m7nnxtkffq4pxbm414fj6ef5
title: "App: saved tabs and a recents section for source roots"
kind: task
status: open
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-11-17-open-anything-from-cli-and-app.md
labels: []
dependencies: []
parent_id: is-01m7nnxhaqce1g2ewec3wbaf7e
created_at: 2026-11-17T21:17:08.591Z
updated_at: 2026-11-18T20:21:16.773Z
---
Phase 1, apps/macos. Saved session records URL plus pin; restore starts on tab show; Open Recent gets a section for source roots until the roots route (mb-a5ru).

## Notes

2026-11-18, checked against main a1100bca6. Recents landed in a different shape in jlevy/metabrowser#546: metab keeps recent-targets.yml (folders and mirrors, key (mode, root)) and the app's Open Recent and Dock menu draw it from metab --recent --json, mirror entries included (RecentTargetsMenu.swift, RecentTargets.swift); no separate section from the saved session. A mirror entry reopens its default branch; its target (web URL) is mb-8bds. Remaining: saved tabs for repository windows. #539 leaves repository tabs out of the saved session (FolderWindows.snapshot iterates only isLocal sessions) and SavedTab.root is a folder path; mb-oxy8 (SessionRoot) is closed, so this is unblocked.

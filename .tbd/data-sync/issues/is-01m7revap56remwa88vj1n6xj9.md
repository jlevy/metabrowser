---
type: is
id: is-01m7revap56remwa88vj1n6xj9
title: "macOS app: keep the open-folder order and recency across a relaunch"
kind: task
status: open
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-11-18-macos-folder-switching.md
labels: []
dependencies: []
parent_id: is-01m7r5cmz107gb7jxq0y6pp7fe
created_at: 2026-11-18T23:11:10.020Z
updated_at: 2026-11-20T17:08:04.921Z
---
From PR #568 Review A, suggestion A12 (deferred in review round 1). The saved session records windows front to back and, since round 1, background folders most recently shown first (SavedSession.background). A restore therefore opens the windows' folders, then the background ones, so OpenFolders.inOrderOpened, the order the folder chooser (#575) lists open folders in, changes across a relaunch, and recency beyond that order is lost (OpenFolders.byRecency after a launch is the front window's folder, then the rest in open order). Fix: save the open order (for example SavedSession.openOrder, read with decodeIfPresent), admit it with the roots in SavedSession.admitted, have the restore make sessions in that order (SavedSession.roots), and consider seeding OpenFolders recency from the saved order. Repositories stay out, as they are out of the saved session.

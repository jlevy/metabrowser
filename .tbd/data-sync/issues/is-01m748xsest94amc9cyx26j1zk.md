---
type: is
id: is-01m748xsest94amc9cyx26j1zk
title: Quick folder switcher over registered roots (Phase 4)
kind: feature
status: open
priority: 3
version: 4
spec_path: docs/project/specs/active/plan-2026-11-10-native-macos-app.md
labels: []
dependencies: []
parent_id: is-01m748xpx7bjg68tfaf3q4nxmj
created_at: 2026-11-11T03:02:50.584Z
updated_at: 2026-11-18T22:49:05.271Z
---
Phase 4. A searchable switcher over open, warm, and recent folders whose membership and order come from the roots route (mb-a5ru) and the live-server registry (mb-5xi4), with goldens; no shell-only exemption (AGENTS.md CLI parity). Dock and File menu recents, which macOS keeps, are a platform exemption and may ship earlier.

## Notes

2026-11-11 (review A2 on #357): Dock and File menu recents are now v1's mb-cqxd, an OS-owned list; this bead keeps the quick switcher over the roots route and the registry.

2026-11-18 (owner decision, review A5 on #578): the folder-switching stack (epic mb-32yq) ships the title's folder chooser and View > Switch Folder... before the registry. Their open rows are the app's own state, decided in ShellCore and pinned by its tests, under the paint-exempt parity row app.folder-chooser, which records this decision; their recent rows are metab --recent's, pinned by its golden. When mb-5xi4's registry lands, this bead moves the open rows' membership and order to it, with goldens, and narrows that exemption to drawing.

---
type: is
id: is-01m7dqrdwsgt9p47d19rs6349h
title: "Architecture: macOS app; cut the app README to build, test, release"
kind: task
status: closed
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-11-14-documentation-from-first-principles.md
labels: []
dependencies: []
parent_id: is-01m7dqmdjvjrgqd3vpqw3z3zdc
created_at: 2026-11-14T19:15:13.432Z
updated_at: 2026-11-15T08:17:03.800Z
closed_at: 2026-11-15T08:17:03.799Z
close_reason: Implemented on claude/docs-first-principles (one standalone PR)
resolution: null
duplicate_of: null
---
Phase 2, PR 5: the macOS app.

- New arch-macos-app.md (about 250 lines) from apps/macos/README.md :524-1246 and the WebKit gate log in docs/large-content-rendering.md :501-754 (copy; the map-and-entry PR deletes it there): server supervision and a server per folder, crash recovery, runtime discovery, first run, the version floor, windows, tabs, session restore, the title-bar accessory, and WebKit differences. docs/architecture.md mentions the app nowhere today.
- Measurement tables (README :1087-1120) move beside TabDiscardPolicy and RestoreBudget; pitfalls move into code comments.
- Cut apps/macos/README.md to build, test, and release (about 450 lines): remove bead IDs (:1286-1291), the "The spike today" column (:1276), dated gate results, history phrasing (:126, :342-352, :639-642, :941-942, :1151, :1167-1172, :1197-1199), and hard-coded versions and sizes (:47, :83, :456-479).
- Refresh plan-2026-11-10-native-macos-app.md: its spike branch and claude/macos-release-build are gone, the workflow is live (not "drafted"), and checkboxes for closed beads are unchecked.

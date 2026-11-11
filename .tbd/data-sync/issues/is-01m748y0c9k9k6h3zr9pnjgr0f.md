---
type: is
id: is-01m748y0c9k9k6h3zr9pnjgr0f
title: "App updates: cask upgrades and an in-app notice, Sparkle later"
kind: task
status: open
priority: 4
version: 2
spec_path: docs/project/specs/active/plan-2026-11-10-native-macos-app.md
labels: []
dependencies: []
parent_id: is-01m748xpx7bjg68tfaf3q4nxmj
created_at: 2026-11-11T03:02:57.672Z
updated_at: 2026-11-11T16:46:31.539Z
---
Phase 5. Start with Homebrew cask upgrades and an update-available notice; add Sparkle 2.10 or later when shell updates become routine.

## Notes

2026-11-11: From research-2026-11-11-uv-and-macos-app-install.md: each installed copy has one updater — Homebrew for a cask install, metab for its own install, and Sparkle for both once it ships, with the cask then declaring auto_updates true. An update replaces the bundle whole (stage a complete copy, rename into place), because app bundle protection blocks writes inside a launched app.

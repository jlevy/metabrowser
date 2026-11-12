---
type: is
id: is-01m78v6m8kedregewxys29enqs
title: Show the Metabrowser logo in the title bar instead of the folder icon
kind: feature
status: open
priority: 2
version: 1
spec_path: docs/project/specs/active/plan-2026-11-10-native-macos-app.md
labels: []
dependencies: []
parent_id: is-01m748xpx7bjg68tfaf3q4nxmj
created_at: 2026-11-12T21:39:12.274Z
updated_at: 2026-11-12T21:39:12.274Z
---
The user, 2026-11-12: the title bar shows a folder icon (TitleAccessory.swift's ProxyIconView, drawn because a leading accessory makes AppKit drop its proxy icon). Use the Metabrowser app logo instead, with its own background and a very slight drop shadow like the app icon, nestled just right of the window buttons, fitting the title bar cleanly and reading well in light and dark mode with appropriate contrast.

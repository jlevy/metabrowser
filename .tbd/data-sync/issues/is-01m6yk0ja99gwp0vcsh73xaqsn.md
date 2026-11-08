---
type: is
id: is-01m6yk0ja99gwp0vcsh73xaqsn
title: "Spike the native macOS app: a Swift WKWebView shell over a CLI install"
kind: task
status: open
priority: 2
version: 1
labels: []
dependencies: []
created_at: 2026-11-08T22:03:40.744Z
updated_at: 2026-11-08T22:03:40.744Z
---
Build step 1 of Option D from docs/project/research/research-2026-11-08-macos-app-packaging.md as a self-contained SwiftPM package under apps/macos: discover a CLI install of metab, spawn one server per folder in its own process group, parse its URL, load it in WKWebView with a native navigation policy, menus, folder open and drop, downloads, and clean shutdown. Include unit tests for the pure logic, a bundle-assembly script, a README with the placement decision and the host-protocol gaps, and repository integration (sdist exclude, distribution check). Stacked on claude/macos-metabrowser-native-app-4ba344 (jlevy/metabrowser#338).

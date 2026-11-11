---
type: is
id: is-01m6yk0ja99gwp0vcsh73xaqsn
title: "Spike the native macOS app: a Swift WKWebView shell over a CLI install"
kind: task
status: closed
priority: 2
version: 4
spec_path: docs/project/specs/active/plan-2026-11-10-native-macos-app.md
labels: []
dependencies: []
parent_id: is-01m748xpx7bjg68tfaf3q4nxmj
child_order_hints:
  - is-01m6ypmttbye21yk47qhr6h4mm
created_at: 2026-11-08T22:03:40.744Z
updated_at: 2026-11-11T03:03:09.874Z
closed_at: 2026-11-08T23:07:53.382Z
close_reason: "Delivered in jlevy/metabrowser#341: apps/macos SwiftPM app (AppKit + WKWebView) over a discovered CLI install, one supervised server per folder, native navigation policy, menus, folder open and drop, downloads, error and settings windows; review findings fixed with regression tests (85 tests). Placement: in this repo under apps/macos. Gaps tracked in apps/macos/README.md."
resolution: null
duplicate_of: null
---
Build step 1 of Option D from docs/project/research/research-2026-11-08-macos-app-packaging.md as a self-contained SwiftPM package under apps/macos: discover a CLI install of metab, spawn one server per folder in its own process group, parse its URL, load it in WKWebView with a native navigation policy, menus, folder open and drop, downloads, and clean shutdown. Include unit tests for the pure logic, a bundle-assembly script, a README with the placement decision and the host-protocol gaps, and repository integration (sdist exclude, distribution check). Stacked on claude/macos-metabrowser-native-app-4ba344 (jlevy/metabrowser#338).

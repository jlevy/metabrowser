---
type: is
id: is-01m776x4zyth962wxrtq5e1cxq
title: "Review A4 on #363: the gate's print check omits the app's print bridge"
kind: bug
status: closed
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-11-10-native-macos-app.md
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m748xpx7bjg68tfaf3q4nxmj
hold: null
hold_until: null
created_at: 2026-11-12T06:25:15.773Z
updated_at: 2026-11-12T06:58:53.500Z
started_at: 2026-11-12T06:25:21.943Z
closed_at: 2026-11-12T06:58:53.499Z
close_reason: "Fixed in 76c6f675 (#363): the driver installs PagePrintRequests with the app's allowsPagePrint policy; --checks recorded the page's request reaching the print path, 8 pages."
resolution: null
duplicate_of: null
---
WebKitDriver.swift built its configuration with WebConfiguration.make() without pagePrints, so --checks exercised the old no-op window.print(). Install PagePrintRequests with the app's policy and record that the page's request reaches the print path.

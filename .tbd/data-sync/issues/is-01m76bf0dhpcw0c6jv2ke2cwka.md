---
type: is
id: is-01m76bf0dhpcw0c6jv2ke2cwka
title: "PR #341 B2: javaScriptCanOpenWindowsAutomatically is never turned off"
kind: bug
status: closed
priority: 1
version: 3
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m76bebqayw0ze5xz60yhthtw
hold: null
hold_until: null
created_at: 2026-11-11T22:25:40.785Z
updated_at: 2026-11-12T00:14:52.251Z
started_at: 2026-11-11T22:34:26.986Z
closed_at: 2026-11-12T00:14:52.250Z
close_reason: "fixed in 2f802613 (B2): WebConfiguration turns javaScriptCanOpenWindowsAutomatically off, also on child configurations; WebConfigurationTests in a real WKWebView"
resolution: null
duplicate_of: null
---
High. apps/macos/Sources/Metabrowser/BrowserWindowController.swift:79 and ShellCore/Web/NavigationPolicy.swift:62: the macOS default is YES, so a preview can open same-origin tabs without a gesture. Review B2 https://github.com/jlevy/metabrowser/pull/341#pullrequestreview-5866036340.

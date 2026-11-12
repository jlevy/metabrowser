---
type: is
id: is-01m76qxjyje20eat6yeezzb1p3
title: "App: the page's Print button does nothing in WKWebView"
kind: bug
status: in_progress
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-11-10-native-macos-app.md
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m748xpx7bjg68tfaf3q4nxmj
hold: null
hold_until: null
created_at: 2026-11-12T02:03:21.425Z
updated_at: 2026-11-12T05:45:52.498Z
started_at: 2026-11-12T05:45:52.497Z
---
From the WebKit gate's checks: window.print() in the app does nothing, because WebKit asks the UI delegate for private _webView:printFrame: methods the app does not implement and no public method exists. File > Print works (8 pages). The page must not call a shell API (architecture rule), so the fix is in the app (for example the same path File > Print uses) or the page hides its Print control in the app.

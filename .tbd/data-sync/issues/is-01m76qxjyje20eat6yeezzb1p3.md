---
type: is
id: is-01m76qxjyje20eat6yeezzb1p3
title: "App: the page's Print button does nothing in WKWebView"
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
created_at: 2026-11-12T02:03:21.425Z
updated_at: 2026-11-12T05:52:11.856Z
started_at: 2026-11-12T05:45:52.497Z
closed_at: 2026-11-12T05:52:11.855Z
close_reason: "Fixed in 46a5c324: a user script replaces window.print in the page's main frame with a message to PagePrintRequests, answered through File > Print's printOperation path for the server's own page when no sheet is open; public API only. PagePrintTests (WebKit) and PagePrintPolicyTests; manual check 9 in the README."
resolution: null
duplicate_of: null
---
From the WebKit gate's checks: window.print() in the app does nothing, because WebKit asks the UI delegate for private _webView:printFrame: methods the app does not implement and no public method exists. File > Print works (8 pages). The page must not call a shell API (architecture rule), so the fix is in the app (for example the same path File > Print uses) or the page hides its Print control in the app.

---
type: is
id: is-01m8bb552zgwwv4gvyhq6epqyf
title: "WebKit: an automated check that presses menus in the app's web view"
kind: task
status: open
priority: 1
version: 1
labels: []
dependencies: []
created_at: 2026-11-26T07:12:11.862Z
updated_at: 2026-11-26T07:12:11.862Z
---
mb-iwfs (PR #873) shipped because nothing presses a menu in real WebKit: the menu session modelled WebKit's press wrongly and Chrome focuses the pressed button. Turn the WKWebView press harness (kept at attic/webkit-press-harness/ in the root checkout, main.swift and check.sh) into a check in the webkit gate or CI, pressing chip menus inside a view (diff File type, folder rollups, Agents, event log).

---
type: is
id: is-01m78fd794nz2vq9nffhswcjwb
title: Name the dev build's log folder Metabrowser, and decide where logs live
kind: task
status: in_progress
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-11-10-native-macos-app.md
labels: []
dependencies: []
parent_id: is-01m748xpx7bjg68tfaf3q4nxmj
created_at: 2026-11-12T18:13:05.443Z
updated_at: 2026-11-12T20:24:46.923Z
---
The user, 2026-11-12: the dev build's logs folder should not be 'Metabrowser Dev'; it should be 'Metabrowser', as both builds are named Metabrowser. The user also asked for logs in an Application Support folder like a normal macOS app; the coordinator noted that ~/Library/Logs/<App> is Apple's location for logs (Console.app lists it under Log Reports) and asked the user to choose. Today AppIdentity.logsDirectory gives ~/Library/Logs/Metabrowser Dev/ for dev and ~/Library/Logs/Metabrowser/ for release, and supportDirectory gives ~/Library/Application Support/<bundle identifier>/. Change logsDirectory (and supportDirectory if the user wants it named Metabrowser), the README variants table and server-log section, the plan's variants amendment, and their tests, on #377. Two copies serving one folder already get separate logs through ServerLogLease.

## Notes

2026-11-12, the user decided: server logs at ~/Library/Logs/Metabrowser/ for both builds (Apple's location, kept in Console.app), and the app's data folder at ~/Library/Application Support/Metabrowser/ for both builds instead of the bundle-identifier folder. Dev and release then share restored windows; settings and recents stay per bundle identifier in user defaults. No migration code for data saved by unreleased builds (AGENTS.md); this Mac's session.json is moved by hand at install.

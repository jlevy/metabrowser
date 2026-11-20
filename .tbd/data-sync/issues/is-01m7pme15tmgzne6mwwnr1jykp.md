---
type: is
id: is-01m7pme15tmgzne6mwwnr1jykp
title: "metab --present: hand off to the macOS app only when it passes a fast self-check: the bundle LaunchServices resolves for the bundle ID is /Applications/Metabrowser.app or ~/Applications/Metabrowser.app and carries MetabrowserOpensURLs; refuse otherwise, with a developer override"
kind: task
status: open
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-11-17-open-anything-from-cli-and-app.md
labels: []
dependencies: []
parent_id: is-01m7nnxhaqce1g2ewec3wbaf7e
created_at: 2026-11-18T06:10:16.889Z
updated_at: 2026-11-20T17:22:47.310Z
---
Owner, 2026-11-18 in chat: 'We should be able to tell if the macOS app can run safely Via some sort of self-check that is fast... as long as the app has that name and it's in the applications folder, it's likely the correct app.' 'We could validate that it's in an expected location, which would be the system application folder or the user's application folder. If it's not in an expected location, we probably shouldn't be running it.' Builds on #540 review B7 (bundle ID + marker now; release team ID later). Local build review's lane.

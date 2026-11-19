---
type: is
id: is-01m7tdr44212qz0xrah2we67pq
title: "Open URL: correct an obvious missing https:// instead of refusing it"
kind: bug
status: in_progress
priority: 2
version: 2
delegate: claude-code@spud10
labels: []
dependencies: []
hold: null
hold_until: null
created_at: 2026-11-19T17:30:25.279Z
updated_at: 2026-11-19T17:31:02.483Z
started_at: 2026-11-19T17:31:02.481Z
---
Owner, 2026-11-19, verbatim: "Fix obvious corrections when opening a URL. if a URL is missing the protocol add it, e.g. \"github.com/jlevy/kpress\" -> https://github.com/jlevy/kpress\"  Don't give a completely obvious error and make the user type all of that." Today File > Open URL… (apps/macos/Sources/ShellCore/Folders/OpenURLPanel.swift, OpenURLEntry.link) refuses any text without a scheme with .notAFullURL.

---
type: is
id: is-01m7tdr44212qz0xrah2we67pq
title: "Open URL: correct an obvious missing https:// instead of refusing it"
kind: bug
status: in_progress
priority: 2
version: 4
delegate: claude-code@spud10
labels: []
dependencies: []
hold: null
hold_until: null
created_at: 2026-11-19T17:30:25.279Z
updated_at: 2026-11-19T18:15:35.289Z
started_at: 2026-11-19T17:31:02.481Z
---
Owner, 2026-11-19, verbatim: "Fix obvious corrections when opening a URL. if a URL is missing the protocol add it, e.g. \"github.com/jlevy/kpress\" -> https://github.com/jlevy/kpress\"  Don't give a completely obvious error and make the user type all of that." Today File > Open URL… (apps/macos/Sources/ShellCore/Folders/OpenURLPanel.swift, OpenURLEntry.link) refuses any text without a scheme with .notAFullURL.

## Notes

PR #612 (claude/open-url-add-https, head 07f5c4547). Open URL… writes github.com/…, http://github.com/…, and //github.com/… in full (OpenURLEntry.corrected); field shows the full URL. metab writes https:// before a reducer-claimed host that names nothing on disk (_root_in_full in cli/main.py). owner/repo stays refused in the panel and a path in the CLI: review A (O1/A1) kept the owner's 2026-11-18 no-shorthand answer (mb-m4mg). Dispositions posted for review A.

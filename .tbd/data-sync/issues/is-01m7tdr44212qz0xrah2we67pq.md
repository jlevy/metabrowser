---
type: is
id: is-01m7tdr44212qz0xrah2we67pq
title: "Open URL: correct an obvious missing https:// instead of refusing it"
kind: bug
status: closed
priority: 2
version: 8
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/612
    at: 2026-11-20T17:01:36.059Z
delegate: claude-code@spud10
labels:
  - linear
dependencies: []
hold: null
hold_until: null
created_at: 2026-11-19T17:30:25.279Z
updated_at: 2026-11-20T18:01:39.878Z
started_at: 2026-11-19T17:31:02.481Z
closed_at: 2026-11-19T18:22:06.093Z
close_reason: "Landed in #612 (5055819d2): Open URL… adds https:// to a GitHub host typed without a scheme and upgrades http://; the CLI completes a scheme-less GitHub URL that names nothing on disk. owner/repo shorthand dropped per the owner's recorded answer."
resolution: null
duplicate_of: null
extensions:
  linear:
    id: b5fc8c83-3e70-456d-9e11-713ba32ea8e1
    linked_at: 2026-11-20T18:01:39.877Z
---
Owner, 2026-11-19, verbatim: "Fix obvious corrections when opening a URL. if a URL is missing the protocol add it, e.g. \"github.com/jlevy/kpress\" -> https://github.com/jlevy/kpress\"  Don't give a completely obvious error and make the user type all of that." Today File > Open URL… (apps/macos/Sources/ShellCore/Folders/OpenURLPanel.swift, OpenURLEntry.link) refuses any text without a scheme with .notAFullURL.

## Notes

PR #612 (claude/open-url-add-https, head 07f5c4547). Open URL… writes github.com/…, http://github.com/…, and //github.com/… in full (OpenURLEntry.corrected); field shows the full URL. metab writes https:// before a reducer-claimed host that names nothing on disk (_root_in_full in cli/main.py). owner/repo stays refused in the panel and a path in the CLI: review A (O1/A1) kept the owner's 2026-11-18 no-shorthand answer (mb-m4mg). Dispositions posted for review A.

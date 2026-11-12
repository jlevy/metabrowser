---
type: is
id: is-01m76r53kjsahny5r16m0b11p1
title: "PR #359 D3: collapsing .. in an unresolved protected suffix changes the served folder"
kind: bug
status: closed
priority: 2
version: 3
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m76r4r0pna9p2h3kncd2jp4q
hold: null
hold_until: null
created_at: 2026-11-12T02:07:27.851Z
updated_at: 2026-11-12T03:05:31.767Z
started_at: 2026-11-12T02:58:04.467Z
closed_at: 2026-11-12T03:05:31.766Z
close_reason: "Fixed in 353d3f5e: no lexical collapse; uncertain roots defer under the saved spelling. RootAdmissionTests.aLinkThroughAProtectedLocationKeepsTheSavedSpelling. Reply issuecomment-6813151545."
resolution: null
duplicate_of: null
---
High. apps/macos/Sources/ShellCore/Folders/RootAdmission.swift:73 and :96. Review https://github.com/jlevy/metabrowser/pull/359#pullrequestreview-5867869514.

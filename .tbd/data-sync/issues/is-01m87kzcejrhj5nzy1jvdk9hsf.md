---
type: is
id: is-01m87kzcejrhj5nzy1jvdk9hsf
title: "Guided review: the notice's bulleted list overlaps the panel's left border"
kind: bug
status: closed
priority: 2
version: 4
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/795
    at: 2026-11-24T21:25:19.356Z
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m87ky2a36j5yg4pf9827xxd6
hold: null
hold_until: null
created_at: 2026-11-24T20:29:22.207Z
updated_at: 2026-11-24T22:13:05.949Z
started_at: 2026-11-24T20:38:48.176Z
closed_at: 2026-11-24T22:13:05.949Z
close_reason: "Fixed in #795"
resolution: null
duplicate_of: null
---
The out-of-date notice's bullet list draws its bullets over the left border. Fix the list's inset in styles.css, or remove the list as part of the concise notice and check no other guide list has the same fault, measured in headless Chrome.

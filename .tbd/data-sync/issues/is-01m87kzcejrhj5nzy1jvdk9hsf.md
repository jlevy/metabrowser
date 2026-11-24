---
type: is
id: is-01m87kzcejrhj5nzy1jvdk9hsf
title: "Guided review: the notice's bulleted list overlaps the panel's left border"
kind: bug
status: in_progress
priority: 2
version: 2
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m87ky2a36j5yg4pf9827xxd6
hold: null
hold_until: null
created_at: 2026-11-24T20:29:22.207Z
updated_at: 2026-11-24T20:38:48.179Z
started_at: 2026-11-24T20:38:48.176Z
---
The out-of-date notice's bullet list draws its bullets over the left border. Fix the list's inset in styles.css, or remove the list as part of the concise notice and check no other guide list has the same fault, measured in headless Chrome.

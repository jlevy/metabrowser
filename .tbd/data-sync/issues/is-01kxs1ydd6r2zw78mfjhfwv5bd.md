---
type: is
id: is-01kxs1ydd6r2zw78mfjhfwv5bd
title: "R3: make SDK copy delegate fully SDK-owned (drop global.copyContent branch)"
kind: bug
status: open
priority: 2
version: 2
labels: []
dependencies:
  - type: blocks
    target: is-01kxs2bd3cgdpv7tka15ts9j99
created_at: 2026-07-17T22:07:55.814Z
updated_at: 2026-07-17T22:15:03.691Z
---
Delegate still prefers private app.js global; implement SDK-owned copy with feedback + rejected-promise handling; cover in Node DOM shim.

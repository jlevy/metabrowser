---
type: is
id: is-01kxs1ydd6r2zw78mfjhfwv5bd
title: "R3: make SDK copy delegate fully SDK-owned (drop global.copyContent branch)"
kind: bug
status: closed
priority: 2
version: 4
labels: []
dependencies:
  - type: blocks
    target: is-01kxs2bd3cgdpv7tka15ts9j99
parent_id: is-01kxs2b441234qwdrbz6zekv70
created_at: 2026-07-17T22:07:55.814Z
updated_at: 2026-07-17T22:15:28.589Z
closed_at: 2026-07-17T22:15:28.589Z
close_reason: Fixed and pushed; make verify green (723 tests incl. new host-validation CLI, selector round-trip, and copy-delegate behavioral suites).
---
Delegate still prefers private app.js global; implement SDK-owned copy with feedback + rejected-promise handling; cover in Node DOM shim.

---
type: is
id: is-01m0tyg13fa9h3pbfd26x9f1tg
title: "PR #76 review R1: use DOM-free syntax token data"
kind: bug
status: closed
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-08-24-diff-syntax-highlighting-and-layouts.md
labels:
  - diff
  - review
dependencies: []
parent_id: is-01m0txbdd0b5cyzcp64vsje7kp
created_at: 2026-08-24T22:33:13.070Z
updated_at: 2026-08-24T22:41:50.034Z
closed_at: 2026-08-24T22:41:50.030Z
close_reason: "Fixed in reviewed design revision 5604e04; disposition published on PR #76."
resolution: null
duplicate_of: null
---
PR #76 review R1 (High), plan lines 145-176 and testing lines 357-360. Replace the planned DocumentFragment/clonable-fragment intermediate form with DOM-free per-line token runs that preserve class stacks across newlines, round-trip exact text, avoid innerHTML, and run in the repository's jsdom-free Node harness. Pin the Highlight.js entity vocabulary with tests.

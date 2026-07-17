---
type: is
id: is-01kxs11kc55313h2t1fc2excpf
title: Vendor all browser third-party assets locally (offline-first, replaces CDN+SRI)
kind: feature
status: closed
priority: 1
version: 8
labels: []
dependencies: []
child_order_hints:
  - is-01kxs122frj7121dbm1sc4t92z
  - is-01kxs122tmpmhe5mevg39napdq
  - is-01kxs1234masbahg1swn7nxsm4
  - is-01kxs123ec78tz1662kkyz8w8e
  - is-01kxs123qnw86pfrfx4x4q6xpp
  - is-01kxs1243ym7qtkqqfe9b43qbr
created_at: 2026-07-17T21:52:11.653Z
updated_at: 2026-07-17T22:00:57.599Z
closed_at: 2026-07-17T22:00:57.599Z
close_reason: "Vendoring shipped: 8 assets served same-origin from the wheel (920KB wheel), offline-first enforcement + manifest parity tests, docs updated, make verify green (714 tests), pushed to the review-fixes branch. Supersedes the CDN+SRI approach."
---
User decision: serve mustache/hljs/chart.js/plugins/elk from the wheel via a manifest-driven vendoring script sourced from lockfile-verified node_modules; enforce no external asset origins in the served page (offline goal); size caps in the script.

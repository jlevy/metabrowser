---
type: is
id: is-01m8hj8h41e2h8xzznm95n3bpq
title: Unify page history and add native Back, Forward, and URL controls
kind: feature
status: in_progress
priority: 2
version: 11
spec_path: docs/project/specs/active/plan-2026-11-28-shared-navigation-history.md
delegate: codex@spud10.local
labels: []
dependencies:
  - type: blocks
    target: is-01m8hj8hnhgn8342g68ddfp1ra
child_order_hints:
  - is-01m8hp1wznsa5nmb52cyekcmb6
  - is-01m8hp1xrk0r5pt9a5dc0b8qef
  - is-01m8hp1yg64decx13svd9pde09
  - is-01m8hp1z3amzj1rf3m309t1hcc
hold: null
hold_until: null
created_at: 2026-11-28T17:11:49.109Z
updated_at: 2026-11-28T18:27:26.546Z
started_at: 2026-11-28T18:18:06.017Z
---
Implement phase 1 after the draft spec is reviewed. Preserve browser history and verify equivalent macOS buttons, menus, shortcuts, and link copying.

## Notes

Design and Astra review are in draft PR #927. Phase 1 implementation is on codex/native-navigation-history from main. The native controls use WebKit’s existing history with committed page labels, and real Chrome verified PR Checks → file → Back → Forward, including exact browser titles. The separate source-qualified Git routes and history are tracked in mb-flot.

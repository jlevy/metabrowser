---
type: is
id: is-01m8hj8h41e2h8xzznm95n3bpq
title: Unify page history and add native Back, Forward, and URL controls
kind: feature
status: in_progress
priority: 2
version: 12
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
updated_at: 2026-11-28T18:33:42.456Z
started_at: 2026-11-28T18:18:06.017Z
---
Implement phase 1 after the draft spec is reviewed. Preserve browser history and verify equivalent macOS buttons, menus, shortcuts, and link copying.

## Notes

Design and Astra review are in draft PR #927. Phase 1 is implemented in draft PR #930 on codex/native-navigation-history and has a guided review. Real Chrome verified exact PR and file restoration with their tab titles. Swift app and native regression type-check passed locally, and GitHub runs the native suite. The follow-up for source-qualified Git routes and history is mb-flot.

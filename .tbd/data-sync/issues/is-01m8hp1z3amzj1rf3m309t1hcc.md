---
type: is
id: is-01m8hp1z3amzj1rf3m309t1hcc
title: Verify the native and browser navigation trace end to end
kind: task
status: in_progress
priority: 2
version: 4
spec_path: docs/project/specs/active/plan-2026-11-28-shared-navigation-history.md
delegate: codex@spud10.local
labels: []
dependencies: []
parent_id: is-01m8hj8h41e2h8xzznm95n3bpq
hold: null
hold_until: null
created_at: 2026-11-28T18:18:08.361Z
updated_at: 2026-11-28T18:59:08.391Z
started_at: 2026-11-28T18:46:24.486Z
---

## Notes

Linux and macOS CI passed on PR #930 commit 112a60b6d. Real Chrome restored exact PR Checks and file addresses and titles, including file titles through Git source changes. The macOS suite verifies WebKit item identity, inactive-window rejection and an origin-changing restart. Remaining interactive checks follow the macOS app hand checks under Menu Actions and Closing a Window: arrow clicks and menus, Shift hints, exact clipboard contents, URL disclosure and the minimum-width title bar.

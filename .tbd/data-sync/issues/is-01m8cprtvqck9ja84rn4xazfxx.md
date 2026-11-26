---
type: is
id: is-01m8cprtvqck9ja84rn4xazfxx
title: "PR #888 Chrome: Preserve membership of stacks with equal update times"
kind: bug
status: in_progress
priority: 2
version: 2
delegate: codex@spud10.local
labels: []
dependencies: []
parent_id: is-01m8cn7g58hfbbdjx6x1ng7bbg
hold: null
hold_until: null
created_at: 2026-11-26T19:54:25.326Z
updated_at: 2026-11-26T19:54:38.314Z
started_at: 2026-11-26T19:54:38.297Z
---
The stack #70 Whole stack navigation row disappears when a stack that contains all its members wins an otherwise tied timestamp. Chrome test test_the_stack_page_is_a_pull_request_page_that_holds_still_in_chrome failed in CI run 45885861978. Keep snapshot order for ties on server and client.

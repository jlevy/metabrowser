---
type: is
id: is-01m8e7927wvgqsb5mz3wfzq15z
title: Main Chrome stack-groups fixture assigns shared PR to a different stack
kind: bug
status: open
priority: 1
version: 1
labels: []
dependencies: []
created_at: 2026-11-27T10:02:08.995Z
updated_at: 2026-11-27T10:02:08.995Z
---
Main run 45976882655 at 63a00c89e failed tests/test_github_pulls_stacks_chrome.py membership/order checks: PR 10 appeared under Stack 300 while the fixture expects it under Stack 286. Existing mb-v719 and mb-y7lw describe distinct timeout/tooltip failure modes and do not authorize a rerun of this assertion failure. Diagnose snapshot activity ranking and fixture consistency, reproduce on main, and fix the cause.

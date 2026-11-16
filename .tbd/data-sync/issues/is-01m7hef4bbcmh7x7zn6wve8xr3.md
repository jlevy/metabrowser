---
type: is
id: is-01m7hef4bbcmh7x7zn6wve8xr3
title: "PR #459 A4: keymap.py states shell letters mean the same everywhere, without the open-menu exception"
kind: bug
status: closed
priority: 3
version: 3
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m7hcjfyhee19b9jnbk7nvqfk
hold: null
hold_until: null
created_at: 2026-11-16T05:49:49.290Z
updated_at: 2026-11-16T05:51:15.528Z
started_at: 2026-11-16T05:49:56.261Z
closed_at: 2026-11-16T05:51:15.527Z
close_reason: "Fixed in 038b8706d: keymap.py docstring and two comments name the open-menu exception."
resolution: null
duplicate_of: null
---
Low suggestion. src/metabrowser/keymap.py:21, :45-47, :51-53 state absolutely that a shell letter never means one thing in one place and another elsewhere; an open Group by menu's T now chooses By file type. PR #459, review A: https://github.com/jlevy/metabrowser/pull/459#pullrequestreview-5915454708

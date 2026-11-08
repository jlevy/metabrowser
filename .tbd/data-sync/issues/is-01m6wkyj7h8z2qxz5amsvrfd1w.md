---
type: is
id: is-01m6wkyj7h8z2qxz5amsvrfd1w
title: Place stack positions beside list PR numbers and simplify stack-menu rows
kind: feature
status: in_progress
priority: 1
version: 4
spec_path: docs/project/specs/active/plan-2026-10-01-github-pulls-tab.md
delegate: codex@spud10
labels:
  - release:v0.12.0
dependencies:
  - type: blocks
    target: is-01m6wdjwawp9g1bvnefz2hxze3
parent_id: is-01m6f3n89kn7ztmfhrzswxnsgz
hold: null
hold_until: null
created_at: 2026-11-08T03:41:34.832Z
updated_at: 2026-11-08T03:54:42.546Z
started_at: 2026-11-08T03:41:47.870Z
---
User acceptance on November 7: show the stack icon and position such as6/6 on the left Pulls overview/list beside the PR number. Reuse cached optional native stack metadata and existing navigation/menu behavior; avoid per-row provider fetches. The popover row must read bold position, tiny middle dot, title, tiny middle dot, PR number: **1/6** · title · #123. Keep the position bold and place the PR number to the right of its title, preserving current item, keyboard and native-link behavior. Update the plan/design docs, focused session/golden evidence, review and install through a follow-up PR. Also place the PR-page stack trigger immediately to the right of its Open/Merged/Closed status badge. Keep the disclosure mounted across passive header updates, and keep its menu within narrow panes.

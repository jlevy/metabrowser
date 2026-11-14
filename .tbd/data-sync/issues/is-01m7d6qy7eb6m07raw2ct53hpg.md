---
type: is
id: is-01m7d6qy7eb6m07raw2ct53hpg
title: Prepare Changes' first screen before the click, so H92 (c)'s hold has nothing to wait for
kind: task
status: open
priority: 2
version: 1
spec_path: docs/project/specs/active/plan-2026-11-11-ui-apparent-performance.md
labels: []
dependencies: []
parent_id: is-01m774q0ep0jq6vhb790rart0v
created_at: 2026-11-14T14:17:51.597Z
updated_at: 2026-11-14T14:17:51.597Z
---
exp-079 accepted H92 (c) as the campaign's costliest trade: at final main Changes is ready at 79 to 102 ms against 43 to 45 ms in the control, the price of holding first paint until the first screen's diffs are rendered (CHANGES_FIRST_SCREEN_MS = 200). H106's Conversation hold costs pull request clicks similarly (44 to 112 ms against 28 to 62 ms). Register a hypothesis: preparing the first screen's diffs and description on selection or pointer intent makes the hold resolve at once, keeping zero movement and winning back the time. Guards: wasted prepare requests, the hold-span probe, and exp-079's PR transitions.

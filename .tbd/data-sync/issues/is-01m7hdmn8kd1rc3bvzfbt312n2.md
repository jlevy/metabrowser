---
type: is
id: is-01m7hdmn8kd1rc3bvzfbt312n2
title: "PR #458 A3: a stale Pulls Show group is fitted one frame late when Pulls is shown again"
kind: bug
status: closed
priority: 3
version: 3
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m7hcjeyyagvt3h7zcvvssfks
hold: null
hold_until: null
created_at: 2026-11-16T05:35:21.874Z
updated_at: 2026-11-16T06:16:20.757Z
started_at: 2026-11-16T05:35:29.232Z
closed_at: 2026-11-16T06:16:20.756Z
close_reason: "Fixed in 3ed205983 on PR #458; disposition reply https://github.com/jlevy/metabrowser/pull/458#issuecomment-6908956491"
resolution: null
duplicate_of: null
---
Low. Review A https://github.com/jlevy/metabrowser/pull/458#pullrequestreview-5915435915. src/metabrowser/static/filter-controls.js:462, :517-526, :552. The MutationObserver does not see the slot's hidden attribute, so a show after the pane crossed the break waits for the ResizeObserver frame: one frame clipped. Fix: observe the slot's hidden attribute (or fit in activateNavPanel), and add a switch, narrow, switch-back step to the Pulls session asserting data-fit at the first ResizeObserver delivery.

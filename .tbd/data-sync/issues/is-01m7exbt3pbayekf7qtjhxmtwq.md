---
type: is
id: is-01m7exbt3pbayekf7qtjhxmtwq
title: "Transition recorder revision 6: memory and dwell readings, time-to-highlighted, and the open recorder bugs, then an A/A on main"
kind: task
status: open
priority: 1
version: 9
spec_path: docs/project/specs/active/plan-2026-11-14-performance-campaigns.md
labels: []
dependencies:
  - type: blocks
    target: is-01m774r967jvcvcx4btkpyfzeg
  - type: blocks
    target: is-01m774ramhp4w2e08j3t30aw9g
  - type: blocks
    target: is-01m7ezshzwvgr17jz8fkawd3hz
  - type: blocks
    target: is-01m7h2bkwq2pzqp6q48zp3anhr
  - type: blocks
    target: is-01m7h2bmadaxhnfqxqqzv5m7b9
  - type: blocks
    target: is-01m7h2bmrej11b0jakgaws5a19
parent_id: is-01m774q0ep0jq6vhb790rart0v
created_at: 2026-11-15T06:12:25.845Z
updated_at: 2026-11-16T02:18:41.571Z
---
Lane 0 of the campaign plan. One scenario revision bump costs less than three: fix mb-86b9 (content under a zero-size ancestor; bound the search), mb-5xzz (hidden and parked retained surfaces read as hidden) and mb-s0e4 (the input's own frame before the input) together, and add the readings Phase 2–3 rows need: retained memory per surface (H95, H98, H99), a dwell journey that sweeps hover dwell instead of the fixed 400 ms (H94), and a time-to-highlighted milestone (H101). Freeze it as revision 6 and run compare --aa on main so later rounds judge against a measured floor.

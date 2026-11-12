---
type: is
id: is-01m780x8xv4jrks46ak99qs03h
title: "Transition recorder: find on-screen content under a zero-size ancestor, and bound the content search"
kind: bug
status: open
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-11-11-ui-apparent-performance.md
labels: []
dependencies:
  - type: blocks
    target: is-01m774rb30k3bd8ehwy6exbwq4
  - type: blocks
    target: is-01m774ramhp4w2e08j3t30aw9g
parent_id: is-01m774q0ep0jq6vhb790rart0v
created_at: 2026-11-12T13:59:42.777Z
updated_at: 2026-11-12T13:59:49.275Z
---
Deferred from review C (C1, Medium) on jlevy/metabrowser#373 at 5031dc16. The revision 4 content search rejects a subtree on its ancestor's own box (explorations/performance-loop/transitions-recorder.mjs:345-361): a windowed list (zero-height positioned anchor, absolutely positioned rows) scrolled after ready reads 26 blank frames with 45 rows on screen, and off-screen siblings are measured uncounted, so hasUseful at the end of 10,000 lines costs about 15 ms per frame (1.7 ms in revision 3). Not present on any surface the current journeys measure (52 readings of file and commit views, Files tree, Git panel). Fix before any round that measures a scrolled, windowed, or chunked preview: test a subtree by its descendants' boxes when the ancestor box is zero-size or positioned, bound the walk by nodes visited (counted or not), and record the read's cost per frame. Bump the scenario revision. Reproductions: review C's probe scripts.

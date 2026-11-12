---
type: is
id: is-01m780x9atzc6kmf59czjzhmnw
title: "Transition recorder: read hidden and parked retained surfaces as hidden; tidy compare reporting"
kind: bug
status: open
priority: 3
version: 4
spec_path: docs/project/specs/active/plan-2026-11-11-ui-apparent-performance.md
labels: []
dependencies:
  - type: blocks
    target: is-01m774rb30k3bd8ehwy6exbwq4
  - type: blocks
    target: is-01m774ramhp4w2e08j3t30aw9g
  - type: blocks
    target: is-01m774r967jvcvcx4btkpyfzeg
parent_id: is-01m774q0ep0jq6vhb790rart0v
created_at: 2026-11-12T13:59:43.193Z
updated_at: 2026-11-12T13:59:49.628Z
---
Deferred from review C (C2 and C3, Low) on jlevy/metabrowser#373 at 5031dc16. C2: content under visibility:hidden, opacity:0, or a collapsed block still counts toward the 400-node cap; a retained page collapsed to height:0 with overflow:hidden reads 0/0/0 for a 66 px move, and one parked off screen reads 10,000 px. C3: the B4 window mark is one-way (the mirror case is an unmarked wrong-way result); tied medians with one pair beyond each way print 'one pair of 3 is same beyond' and name one pair; blankFramesOriginPrompt stops at any change of state letter; a root placeholder with visible text reads UP. Fix C2 before any round that retains hidden surfaces (per-main-tab retention, detached LRU, laid-out hidden view tabs); bump the scenario revision.

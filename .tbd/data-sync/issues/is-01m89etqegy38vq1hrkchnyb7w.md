---
type: is
id: is-01m89etqegy38vq1hrkchnyb7w
title: "PR #838 B1: when the carrier moves, Guided Review cannot read a step at the drawn comparison"
kind: bug
status: closed
priority: 2
version: 3
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m89etpwgfvf29h3jtxjr4664
hold: null
hold_until: null
created_at: 2026-11-25T13:37:55.662Z
updated_at: 2026-11-25T14:05:22.503Z
started_at: 2026-11-25T13:37:59.965Z
closed_at: 2026-11-25T14:05:22.500Z
close_reason: "Fixed in 0cc825cec on #838: behind() in createGuideNavigation holds the stack page at the revision read at the drawn comparison, and _pinned_past makes the route answer stack_moved at a kept pair the guide is pinned past. Tested by the stack mount session's carrier_moved case, the navigation session's moved case, a _pinned_past unit test, and the stack guide golden. Disposition: https://github.com/jlevy/metabrowser/pull/838#issuecomment-7164728138"
resolution: null
duplicate_of: null
---
A step not read yet is refused as a new guide, and reopening reads the re-pinned guide at the old pair as history rewritten. Fix: a step answer naming another revision while the drawn comparison is not current is that step's stack_moved; the route answers stack_moved at a kept pair the guide's pins are past; session cases.

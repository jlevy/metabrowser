---
type: is
id: is-01m774qzdxvfrwsyzmx5dgtce1
title: Reserve toggling chrome and fix page header sections' boxes at first paint
kind: task
status: in_progress
priority: 1
version: 10
spec_path: docs/project/specs/active/plan-2026-11-11-ui-apparent-performance.md
delegate: claude-code@spud10
labels: []
dependencies:
  - type: blocks
    target: is-01m774r967jvcvcx4btkpyfzeg
  - type: blocks
    target: is-01m774rfn15h0t9ys9eg0nvgyx
parent_id: is-01m774q0ep0jq6vhb790rart0v
hold: null
hold_until: null
created_at: 2026-11-12T05:47:29.077Z
updated_at: 2026-11-12T16:41:38.311Z
started_at: 2026-11-12T06:11:46.298Z
---
Per the page-header audit in the research doc (Page Headers, Section by Section): filter bar slot on every main tab; Commits button in the shell; scrollbar-gutter on tree and preview panes; always-present view tab bar; print and badge slots kept; PR title reserved and clamped to two lines; one-line fixed 26 px state row with truncating branch chips and a reserved stack-chip slot; state badge min-width; labels in an always-present row; fixed 26 px status row with a permanent Refresh slot; loading skeleton at final heights; Pulls status and connection lines always present, counts with tabular numerals and min-width; folder Overview panel skeletons at final height. Measured as region movement per transition (0 px target) and shift.

## Notes

PR #370. Pilot (harness v2 patched selector): main-tab tree movement 37 to 0 px; view tab bar 30 to 0; scrollbar 11 to 0; PR tabs 8 to 0; landing Commits-tab shift gone; guards held. Round-1 reviews at 078c4c69: A senior (5876543600; 3 High: A1 deep landing truncation lost, A2 font wait skipped, A3 state badge sizer makes loaded header 5.6 px taller than the empty-record header; 6 Medium; 7 Low), B performance (5876543926; B1 inline landing cost unmeasured; 4 Low). Official rounds on 078c4c69 stopped; addressing first, then exp-059 and exp-064 on harness v4 at the addressed head.


Round-1 addressed at 666a066c (475e2327 fixes, dfb78106 test, 666a066c doc): A1 landing graft all-or-nothing under a rows budget; A2 font wait moved to settleFaces; A3 badge sizer order and quiet-row height, Chrome header check; A4-A9 fixed; A12 deferred mb-25o7, A13 remainder mb-fov8; non-inlined landing reveal regression found and fixed. Startup headroom 395 bytes. Follow-up review C (round 2) in progress. exp-059 and exp-064 queued behind the series lock at 666a066c.

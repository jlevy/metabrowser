---
type: is
id: is-01m774qzdxvfrwsyzmx5dgtce1
title: Reserve toggling chrome and fix page header sections' boxes at first paint
kind: task
status: in_progress
priority: 1
version: 13
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
updated_at: 2026-11-12T17:46:22.026Z
started_at: 2026-11-12T06:11:46.298Z
---
Per the page-header audit in the research doc (Page Headers, Section by Section): filter bar slot on every main tab; Commits button in the shell; scrollbar-gutter on tree and preview panes; always-present view tab bar; print and badge slots kept; PR title reserved and clamped to two lines; one-line fixed 26 px state row with truncating branch chips and a reserved stack-chip slot; state badge min-width; labels in an always-present row; fixed 26 px status row with a permanent Refresh slot; loading skeleton at final heights; Pulls status and connection lines always present, counts with tabular numerals and min-width; folder Overview panel skeletons at final height. Measured as region movement per transition (0 px target) and shift.

## Notes

PR #370. Pilot (harness v2 patched selector): main-tab tree movement 37 to 0 px; view tab bar 30 to 0; scrollbar 11 to 0; PR tabs 8 to 0; landing Commits-tab shift gone; guards held. Round-1 reviews at 078c4c69: A senior (5876543600; 3 High: A1 deep landing truncation lost, A2 font wait skipped, A3 state badge sizer makes loaded header 5.6 px taller than the empty-record header; 6 Medium; 7 Low), B performance (5876543926; B1 inline landing cost unmeasured; 4 Low). Official rounds on 078c4c69 stopped; addressing first, then exp-059 and exp-064 on harness v4 at the addressed head.


Round-1 addressed at 666a066c (475e2327 fixes, dfb78106 test, 666a066c doc): A1 landing graft all-or-nothing under a rows budget; A2 font wait moved to settleFaces; A3 badge sizer order and quiet-row height, Chrome header check; A4-A9 fixed; A12 deferred mb-25o7, A13 remainder mb-fov8; non-inlined landing reveal regression found and fixed. Startup headroom 395 bytes. Follow-up review C (round 2) in progress. exp-059 and exp-064 queued behind the series lock at 666a066c.
Follow-up review C (round 2, 666a066c, 5878884042): changes requested; 1 High (C1 lint fails on 'PR 370' references in comments), 4 Medium (C2 wrong empty graft during discovery; C3 font wait caches the first document's faces, later faces swap in with CLS up to 0.150; C4 status end group overflows at narrow panes; C5 non-inlined landing still moves the tree, bead mb-o1ba), 5 Low. Rounds held until fixed.
Review C addressed at 28e12fa2 (C2 graft only with complete coverage; C3 every staged document's faces waited for, all declared faces loaded at idle on first miss; C4 offers truncate, header check 360-980 px with offers; C5 docs; C6 rate-limit hold one line; C8-C10; C7 deferred note). Lint-check exits 0 at 28e12fa2 (437 bytes startup headroom). Dispositions 6828815634/6828816245/6831293140. Interim rev-4 series of 078c4c69 (diagnostic, no artifact): every declared deciding metric passed (H86(a) 28/28, H86(b) 8/8, H91(a)-(d)), no declared guard wrong-way. Coordinator check in progress; then exp-059/064 at 28e12fa2.
Coordinator check at 28e12fa2 (comment 6831369006): lint-check exit 0 with public hygiene passing, 437 bytes headroom; 19 tests (inline, header Chrome, staged fonts) pass. C7 filed as mb-qql1. Review rounds for #370 complete; exp-059 and exp-064 at 28e12fa2 queued behind the lock with the load gate.

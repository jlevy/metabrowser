---
type: is
id: is-01m774qzdxvfrwsyzmx5dgtce1
title: Reserve toggling chrome and fix page header sections' boxes at first paint
kind: task
status: in_progress
priority: 1
version: 6
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
updated_at: 2026-11-12T07:24:36.414Z
started_at: 2026-11-12T06:11:46.298Z
---
Per the page-header audit in the research doc (Page Headers, Section by Section): filter bar slot on every main tab; Commits button in the shell; scrollbar-gutter on tree and preview panes; always-present view tab bar; print and badge slots kept; PR title reserved and clamped to two lines; one-line fixed 26 px state row with truncating branch chips and a reserved stack-chip slot; state badge min-width; labels in an always-present row; fixed 26 px status row with a permanent Refresh slot; loading skeleton at final heights; Pulls status and connection lines always present, counts with tabular numerals and min-width; folder Overview panel skeletons at final height. Measured as region movement per transition (0 px target) and shift.

## Notes

Implemented on claude/perf-layout (0e53da60, 2d9d2960, 2538f270; commit-landing toolbar and failure state in progress). One 37 px toolbar slot per main tab; content top identical on all tabs in headless Chrome. Awaiting exp-059.

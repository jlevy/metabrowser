---
type: is
id: is-01m6j2pt25zs6m77svjkrkhk5y
title: Clear inactive PR file selection without losing its retained cursor
kind: bug
status: in_progress
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-10-01-github-pulls-tab.md
delegate: pulls_navigation
labels: []
dependencies: []
parent_id: is-01m6hx4w87z6r8ndnbt57avr53
hold: null
hold_until: null
created_at: 2026-11-04T01:27:50.591Z
updated_at: 2026-11-04T01:43:22.391Z
started_at: 2026-11-04T01:29:02.440Z
---
Whole-shell native Files navigation can leave an old manually expanded PR tree file blue/aria-selected after the page changes. Current file and roving keyboard anchor are separate: clear only the inactive page-selection mark, retain expansion/cursor. Reproduce exact installed7cabc native navigation, verify new active diff following and repeated-route/delayed-page ownership, then minimal panel fix with meaningful whole-route regression. Parent stopped publication; forward-only coordinator commit/gates/independent review required.

## Notes

Confirmed exact installed7cabc3a8 whole-shell native Next PR navigation7Files→8Files: manually retained old7 tree remained expanded with old aria-selected file while active8diff reporteddocs/guide.md. Roving anchor stayedseparate. Raw stale-selection-repro.json/screenshot under durable stack-info-7cabc3a8 evidence. Fix clears previous tree current in shared panel markCurrent boundary, leaving manual expansion/roving anchor. Real pagehost/history+mountedtree regression red oldselection1→green0 with newactive1, Back restores oldselection and ignoreslateothercallback. Source panelSHA256511ea82aa7596f607867d4a9627fdacf512dc1c924878d29cf1f896605ed599a independently reviewedclean.72focusedtests17.08s,bothbrowsertypes,UIgoldens/lint/parity pass. No writercommit/push; coordinator owns finalcommit/artifactgates/publication/closure. Old7cabacceptance explicitly superseded.

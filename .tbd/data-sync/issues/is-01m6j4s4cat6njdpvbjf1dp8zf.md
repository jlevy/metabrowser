---
type: is
id: is-01m6j4s4cat6njdpvbjf1dp8zf
title: Use ago for ages outside condensed navigation
kind: task
status: in_progress
priority: 1
version: 3
spec_path: docs/design-system.md
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m6j4m8h98qy2w5w5wj5d46gj
hold: null
hold_until: null
created_at: 2026-11-04T02:04:03.849Z
updated_at: 2026-11-04T02:28:29.849Z
started_at: 2026-11-04T02:28:29.849Z
---
Owner requests consistent age wording: include ago in normal PR/header/conversation and other noncondensed metadata; compact Git/nav log rows may retain short1d labels. Audit shared formatAge call sites and distinguish labels for just now, future, unknown/invalid and numericpast ages so ago is not duplicated or appended incorrectly. Keep exact timestamp tooltips and existing age color semantics; use shared formatting/context option rather than scattered string fixes.

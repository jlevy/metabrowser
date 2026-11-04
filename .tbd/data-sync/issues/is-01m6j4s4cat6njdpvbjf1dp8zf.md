---
type: is
id: is-01m6j4s4cat6njdpvbjf1dp8zf
title: Use ago for ages outside condensed navigation
kind: task
status: in_progress
priority: 1
version: 5
spec_path: docs/design-system.md
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m6j4m8h98qy2w5w5wj5d46gj
child_order_hints:
  - is-01m6jcdfek91r91prw434b0h3n
hold: null
hold_until: null
created_at: 2026-11-04T02:04:03.849Z
updated_at: 2026-11-04T04:17:30.574Z
started_at: 2026-11-04T02:28:29.849Z
---
Owner requests consistent age wording: include ago in normal PR/header/conversation and other noncondensed metadata; compact Git/nav log rows may retain short1d labels. Audit shared formatAge call sites and distinguish labels for just now, future, unknown/invalid and numericpast ages so ago is not duplicated or appended incorrectly. Keep exact timestamp tooltips and existing age color semantics; use shared formatting/context option rather than scattered string fixes.

## Notes

Shared age formatter and SDK accept relative style; normal PR/card, full Git summary and folder header use past ago/just now/future in while condensed navigation remains compact. Existing freshness sentences unchanged. Fixed-clock edge controls preserve freshness classes and numeric tiers.

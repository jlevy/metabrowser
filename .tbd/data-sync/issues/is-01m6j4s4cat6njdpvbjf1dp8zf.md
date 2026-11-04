---
type: is
id: is-01m6j4s4cat6njdpvbjf1dp8zf
title: Use ago for ages outside condensed navigation
kind: task
status: closed
priority: 1
version: 6
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
updated_at: 2026-11-04T17:14:30.885Z
started_at: 2026-11-04T02:28:29.849Z
closed_at: 2026-11-04T17:14:30.885Z
close_reason: "Scoped implementation independently reviewed and tested; owning feature PRs are actually merged. Final main https://github.com/jlevy/metabrowser/commit/db52ec09cf839269da3a56fd396e44f3092995a9 includes account fix https://github.com/jlevy/metabrowser/pull/297 and documentation https://github.com/jlevy/metabrowser/pull/298, with final manual acceptance and per-issue qualifications checked. Individual source, test, review and merge evidence: ACTION-PLAN.json SHA-256 d0867a696ee055cc27911e83c4f70744b419a3ca4a7a1218f0eeaf419dc37589. Future scope and historical dependency relationships remain open or preserved as recorded."
resolution: null
duplicate_of: null
---
Owner requests consistent age wording: include ago in normal PR/header/conversation and other noncondensed metadata; compact Git/nav log rows may retain short1d labels. Audit shared formatAge call sites and distinguish labels for just now, future, unknown/invalid and numericpast ages so ago is not duplicated or appended incorrectly. Keep exact timestamp tooltips and existing age color semantics; use shared formatting/context option rather than scattered string fixes.

## Notes

Shared age formatter and SDK accept relative style; normal PR/card, full Git summary and folder header use past ago/just now/future in while condensed navigation remains compact. Existing freshness sentences unchanged. Fixed-clock edge controls preserve freshness classes and numeric tiers.

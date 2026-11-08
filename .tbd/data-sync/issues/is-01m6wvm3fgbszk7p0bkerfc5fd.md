---
type: is
id: is-01m6wvm3fgbszk7p0bkerfc5fd
title: Restore missing audit-trace coverage in the release data comparison
kind: task
status: closed
priority: 1
version: 4
spec_path: docs/project/specs/active/plan-2026-09-23-v012-thin-mirror.md
delegate: codex@spud10
labels: []
dependencies:
  - type: blocks
    target: is-01m3wgefqnj91f8avyyv4x8t5w
parent_id: is-01m3wgefqnj91f8avyyv4x8t5w
hold: null
hold_until: null
created_at: 2026-11-08T05:55:40.655Z
updated_at: 2026-11-08T19:04:25.159Z
started_at: 2026-11-08T06:01:34.359Z
closed_at: 2026-11-08T19:04:25.158Z
close_reason: "Restored and verified the previously missing trace coverage in final-data426-20261108T155237Z: all 33 selected trace rows have real audit logs from both builds (66 healthy profiles), exact IDs/multiplicities and raw payload hashes verified. The completed selected DATA comparison contains 1,921 CLI cases, 53 HTTP groups and 47 special cases; all 20 capture-audit predicates pass and every selected outcome has a specific disposition. Sealed manifest c4db97b6b98d2ef1cc9d374f1d4da15606874b046b1971f862daaaffe0c286e2. Original missing-helper finding and old captures remain unchanged. This closes only the instrumentation coverage gap; release clearance remains false pending browser fixes, performance, final artifact qualification and owner approval."
resolution: null
duplicate_of: null
---
Release-gate preparation found trace/sitecustomize.py absent from both preserved original and copied data harness. Thirty fx:trace:* CLI comparisons and three fx:served-trace aggregates would compare empty logs; this is unavailable coverage, never a pass. The associated 63 HTTP comparisons still exercise real behavior. Preserve the missing-helper finding and original evidence. Investigate the expected trace schema and recover or build minimal observational test instrumentation only if it can be validated concisely without changing candidate code, compatibility gates, credentials or runtime policy. Prove trace events are actually emitted before claiming the audit rows. Existing focused Git environment/read-policy/checkout isolation tests strengthen but do not replace complete tracing. Keep the release data gate open until the gap is resolved or explicitly accepted.

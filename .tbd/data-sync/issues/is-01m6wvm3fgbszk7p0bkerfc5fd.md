---
type: is
id: is-01m6wvm3fgbszk7p0bkerfc5fd
title: Restore missing audit-trace coverage in the release data comparison
kind: task
status: in_progress
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-09-23-v012-thin-mirror.md
delegate: codex@spud10
labels: []
dependencies: []
parent_id: is-01m3wgefqnj91f8avyyv4x8t5w
hold: null
hold_until: null
created_at: 2026-11-08T05:55:40.655Z
updated_at: 2026-11-08T06:01:34.372Z
started_at: 2026-11-08T06:01:34.359Z
---
Release-gate preparation found trace/sitecustomize.py absent from both preserved original and copied data harness. Thirty fx:trace:* CLI comparisons and three fx:served-trace aggregates would compare empty logs; this is unavailable coverage, never a pass. The associated 63 HTTP comparisons still exercise real behavior. Preserve the missing-helper finding and original evidence. Investigate the expected trace schema and recover or build minimal observational test instrumentation only if it can be validated concisely without changing candidate code, compatibility gates, credentials or runtime policy. Prove trace events are actually emitted before claiming the audit rows. Existing focused Git environment/read-policy/checkout isolation tests strengthen but do not replace complete tracing. Keep the release data gate open until the gap is resolved or explicitly accepted.

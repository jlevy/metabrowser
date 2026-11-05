---
type: is
id: is-01m6ngsnrtagtxwew8t9nzwdmy
title: "PR #301 R2: Bound repeated visible core provider attempts"
kind: bug
status: closed
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-08-21-load-time-performance.md
delegate: codex@spud10
labels: []
dependencies: []
parent_id: is-01m6ngsms9m08a746a7fwhpprp
hold: null
hold_until: null
created_at: 2026-11-05T09:31:47.865Z
updated_at: 2026-11-05T10:57:38.260Z
started_at: 2026-11-05T09:31:49.308Z
closed_at: 2026-11-05T10:57:38.259Z
close_reason: Fixed per-row quota cooldown and overlapping readiness with original expiry; exact held/cooldown tests green. https://github.com/jlevy/metabrowser/pull/301#discussion_r4479561690.
resolution: null
duplicate_of: null
---
Medium review at https://github.com/jlevy/metabrowser/pull/301#discussion_r4478709998. A window token must not bypass the bounded cooldown for already attempted indexed rows.

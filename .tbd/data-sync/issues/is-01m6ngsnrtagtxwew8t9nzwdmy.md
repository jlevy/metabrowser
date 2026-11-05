---
type: is
id: is-01m6ngsnrtagtxwew8t9nzwdmy
title: "PR #301 R2: Bound repeated visible core provider attempts"
kind: bug
status: in_progress
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-08-21-load-time-performance.md
delegate: codex@spud10
labels: []
dependencies: []
parent_id: is-01m6ngsms9m08a746a7fwhpprp
hold: null
hold_until: null
created_at: 2026-11-05T09:31:47.865Z
updated_at: 2026-11-05T09:31:49.309Z
started_at: 2026-11-05T09:31:49.308Z
---
Medium review at https://github.com/jlevy/metabrowser/pull/301#discussion_r4478709998. A window token must not bypass the bounded cooldown for already attempted indexed rows.

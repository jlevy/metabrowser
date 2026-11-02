---
type: is
id: is-01m6f2kzc9kkhd609gy59jx1rc
title: "PR #276 A1: a command's printed output can supply route evidence in an in-process golden"
kind: bug
status: in_progress
priority: 2
version: 2
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m6f2kp2dkv14cykagykcmqet
hold: null
hold_until: null
created_at: 2026-11-02T21:28:34.440Z
updated_at: 2026-11-02T21:29:09.181Z
started_at: 2026-11-02T21:29:09.180Z
---
Low. devtools/check_parity.py:183-200 applies _IN_PROCESS_COMMAND to the whole .txt; tests/golden_harness.py:218-230 block writes streams raw. Fix: refuse the ambiguity at recording time. Review: https://github.com/jlevy/metabrowser/pull/276#pullrequestreview-5743224957

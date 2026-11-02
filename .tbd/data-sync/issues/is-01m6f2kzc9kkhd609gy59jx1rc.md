---
type: is
id: is-01m6f2kzc9kkhd609gy59jx1rc
title: "PR #276 A1: a command's printed output can supply route evidence in an in-process golden"
kind: bug
status: closed
priority: 2
version: 3
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m6f2kp2dkv14cykagykcmqet
hold: null
hold_until: null
created_at: 2026-11-02T21:28:34.440Z
updated_at: 2026-11-02T21:49:00.772Z
started_at: 2026-11-02T21:29:09.180Z
closed_at: 2026-11-02T21:49:00.771Z
close_reason: "Fixed in 282797c: block refuses a block without exactly one command header. CI run 41530107623 green at 5c6567e. Disposition: https://github.com/jlevy/metabrowser/pull/276#issuecomment-6589319967"
resolution: null
duplicate_of: null
---
Low. devtools/check_parity.py:183-200 applies _IN_PROCESS_COMMAND to the whole .txt; tests/golden_harness.py:218-230 block writes streams raw. Fix: refuse the ambiguity at recording time. Review: https://github.com/jlevy/metabrowser/pull/276#pullrequestreview-5743224957

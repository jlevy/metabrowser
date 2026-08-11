---
type: is
id: is-01kxj00a5zhd18jcbv8f5zmqxg
title: "PR #1 review A2: preserve byte cursors in SSE tail reads"
kind: bug
status: closed
priority: 1
version: 8
spec_path: docs/project/specs/done/plan-2026-07-14-metabrowser-v0.1.0-standalone-package.md
labels: []
dependencies: []
parent_id: is-01kxhztx5585r48tq7gja5refa
created_at: 2026-07-15T04:19:19.870Z
updated_at: 2026-07-17T21:16:36.085Z
closed_at: 2026-07-15T06:02:32.266Z
close_reason: Implemented or dispositioned with bead-specific evidence; post-fix make -j4 verify passes with 669 tests, all lint/type/Flowmark/audit/distribution gates clean, and the live manual browser checklist completed.
---
Top-level PR #1 review finding 2 and final tail audit: byte offsets were used with a text-mode file, partial EOF lines could be acknowledged prematurely across reconnects, and newline-free pending buffers were unbounded. Read exact bytes and decode after slicing; acknowledge only complete lines with resumable event IDs; rewind partial EOF state; bound and recover oversized pending lines; add UTF-8, reconnect, Last-Event-ID, and repeated-batch regressions.

## Notes

SSE now reads exact bytes, acknowledges complete lines with event IDs, honors Last-Event-ID, rewinds partial EOF state, and bounds oversized newline-free buffers. UTF-8, reconnect, and repeated-batch regressions pass.

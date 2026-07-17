---
type: is
id: is-01kxj00ada4vwea8smssvwh5dw
title: "PR #1 review A3: enforce streaming gzip output bounds"
kind: bug
status: closed
priority: 1
version: 8
spec_path: docs/project/specs/done/plan-2026-07-14-metabrowser-v0.1.0-standalone-package.md
labels: []
dependencies: []
parent_id: is-01kxhztx5585r48tq7gja5refa
created_at: 2026-07-15T04:19:20.105Z
updated_at: 2026-07-17T21:16:36.394Z
closed_at: 2026-07-15T06:02:32.295Z
close_reason: Implemented or dispositioned with bead-specific evidence; post-fix make -j4 verify passes with 669 tests, all lint/type/Flowmark/audit/distribution gates clean, and the live manual browser checklist completed.
---
Top-level PR #1 review finding 3 and final compression parity audit: gzip paths trusted forgeable ISIZE metadata and common readers lacked compressed-input, CPU, and concatenated-member logical-size parity. Enforce compressed-input, decoded-output, and CPU limits while streaming; normalize malformed streams behind ArtifactCompressionError; scan multi-member size safely; preserve caller-specific error contracts; cover forged-size and decompression-bomb behavior.

## Notes

Gzip now enforces compressed-input, decoded-output, and CPU bounds; validates multi-member sizes; normalizes malformed streams; preserves endpoint error contracts; and prevalidates raw identity responses before 200 headers. Compression regressions and full gate pass.

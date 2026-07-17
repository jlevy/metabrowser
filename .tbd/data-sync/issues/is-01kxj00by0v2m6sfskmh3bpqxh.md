---
type: is
id: is-01kxj00by0v2m6sfskmh3bpqxh
title: "PR #1 review A10: make verification ordering parallel-safe"
kind: bug
status: closed
priority: 2
version: 5
spec_path: docs/specs/metabrowser-v0.1.0.md
labels: []
dependencies: []
parent_id: is-01kxhztx5585r48tq7gja5refa
created_at: 2026-07-15T04:19:21.664Z
updated_at: 2026-07-15T06:02:32.599Z
closed_at: 2026-07-15T06:02:32.599Z
close_reason: Implemented or dispositioned with bead-specific evidence; post-fix make -j4 verify passes with 669 tests, all lint/type/Flowmark/audit/distribution gates clean, and the live manual browser checklist completed.
---
Top-level PR #1 review finding 7f: make -j verify can start validation targets before install completes. Encode install prerequisites/order so parallel invocation cannot race dependency setup; add a make-policy regression.

## Notes

All parallel quality targets wait for locked environment installation; the mutating default runs format, lint, and test serially. make -j4 verify completed cleanly.

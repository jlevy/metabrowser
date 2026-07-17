---
type: is
id: is-01kxj00e1td5kbef6dm2wjx42b
title: "PR #1 review S3: document the legacy TypeScript ratchet"
kind: bug
status: closed
priority: 2
version: 4
spec_path: docs/specs/metabrowser-v0.1.0.md
labels: []
dependencies: []
parent_id: is-01kxhztx5585r48tq7gja5refa
created_at: 2026-07-15T04:19:23.833Z
updated_at: 2026-07-15T06:02:32.730Z
closed_at: 2026-07-15T06:02:32.730Z
close_reason: Implemented or dispositioned with bead-specific evidence; post-fix make -j4 verify passes with 669 tests, all lint/type/Flowmark/audit/distribution gates clean, and the live manual browser checklist completed.
---
Top-level review finding 7i: verify that the broad legacy browser allowlist has a current rationale and a strict new-module ratchet. Improve documentation or configuration enforcement if the rationale is still implicit.

## Notes

Documented the strict-new-module TypeScript ratchet and bounded legacy allowlist. Strict and legacy check-JS configurations pass in the full gate.

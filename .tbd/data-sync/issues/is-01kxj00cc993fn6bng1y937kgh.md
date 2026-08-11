---
type: is
id: is-01kxj00cc993fn6bng1y937kgh
title: "PR #1 review A12: disposition pinned tbd bootstrap commands"
kind: bug
status: closed
priority: 2
version: 6
spec_path: docs/project/specs/done/plan-2026-07-14-metabrowser-v0.1.0-standalone-package.md
labels: []
dependencies: []
parent_id: is-01kxhztx5585r48tq7gja5refa
created_at: 2026-07-15T04:19:22.120Z
updated_at: 2026-07-17T21:16:46.799Z
closed_at: 2026-07-15T06:02:32.630Z
close_reason: Implemented or dispositioned with bead-specific evidence; post-fix make -j4 verify passes with 669 tests, all lint/type/Flowmark/audit/distribution gates clean, and the live manual browser checklist completed.
---
Top-level PR #1 review finding 7d: managed agent bootstrap hooks invoke exact get-tbd@0.4.0 with npx --yes. Verify whether this reviewed bootstrap fallback is intentional and policy-enforced; either harden it or document a technical rebuttal.

## Notes

Exact get-tbd@0.4.0 bootstrap remains intentional operator documentation; hooks never fetch it, package policy rejects moving or hook-time fetches, and installed tbd 0.4.0 manages the bead tree.

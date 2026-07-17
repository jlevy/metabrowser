---
type: is
id: is-01kxj00c4nt1fhk1p97mh936mz
title: "PR #1 review A11: catch terminal home paths in public hygiene"
kind: bug
status: closed
priority: 1
version: 6
spec_path: docs/project/specs/done/plan-2026-07-14-metabrowser-v0.1.0-standalone-package.md
labels: []
dependencies: []
parent_id: is-01kxhztx5585r48tq7gja5refa
created_at: 2026-07-15T04:19:21.877Z
updated_at: 2026-07-17T21:16:37.561Z
closed_at: 2026-07-15T06:02:32.428Z
close_reason: Implemented or dispositioned with bead-specific evidence; post-fix make -j4 verify passes with 669 tests, all lint/type/Flowmark/audit/distribution gates clean, and the live manual browser checklist completed.
---
Top-level PR #1 review finding 7g: the private-home-path regex requires a trailing slash, so /Users/name or /home/name at end of text is missed. Match both terminal and descendant paths and add focused source/archive regressions.

## Notes

Public hygiene now catches terminal and descendant /Users/name and /home/name paths in source and archives. Focused hygiene regressions and distribution gate pass.

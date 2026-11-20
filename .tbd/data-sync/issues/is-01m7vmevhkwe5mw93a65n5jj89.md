---
type: is
id: is-01m7vmevhkwe5mw93a65n5jj89
title: "PR #617 C4: a second hard link to a database whose checkpoint was interrupted reads as damaged"
kind: bug
status: closed
priority: 2
version: 3
delegate: claude-code@vm
labels: []
dependencies: []
parent_id: is-01m7vme8z9g4zntjqcdkt3y0pe
hold: null
hold_until: null
created_at: 2026-11-20T04:46:56.051Z
updated_at: 2026-11-20T05:15:04.709Z
started_at: 2026-11-20T04:47:06.853Z
closed_at: 2026-11-20T05:15:04.709Z
close_reason: "fixed: 12cc8813d maps corruption in the another-name state to its label; access.json private_copy_through_a_second_hard_link reproduces it; test list adds the case. Disposition reply: https://github.com/jlevy/metabrowser/pull/617#issuecomment-7031127972"
resolution: null
duplicate_of: null
---
docs/project/specs/active/plan-2026-11-19-tabular-data-and-live-sqlite.md:497,510-512,517-518. Map a corruption error in the another-name state to its label at any size; add the case to the nondestructive tests. Severity: Medium. PR #617, review C: https://github.com/jlevy/metabrowser/pull/617#pullrequestreview-5987608762

---
type: is
id: is-01m6f6mnkfn21bq57ye3fpqs31
title: Any PR that deletes an empty file has no Files changed
kind: bug
status: closed
priority: 0
version: 4
delegate: codex@spud10
labels:
  - release:v0.12.0
dependencies: []
parent_id: is-01m6f3ne8f25m4n06r3d09zw9d
hold: null
hold_until: null
created_at: 2026-11-02T22:38:51.502Z
updated_at: 2026-11-04T12:47:02.890Z
started_at: 2026-11-04T12:46:56.417Z
closed_at: 2026-11-04T12:47:02.889Z
close_reason: "Fixed by e50fee2e and independently verified with both exact deleted-empty-file regressions. Owning PR #284 merged in the normal atomic native-stack #278 merge at 8aae81d0dc98223f3b7b2e9b05dfd0084dfd9f35; actual main CI run 41828013066 passed all nine jobs. The implementation and current main tree are verified, so the landing condition is now satisfied."
resolution: null
duplicate_of: null
---
parse_unified_patch cannot model a deleted empty file, returns an empty document when any section fails, and the route answers 404 file f1 not found. Found by exp-040 on a 663-file PR and a public 301-file one; on main too, and shared with .patch files on plain folders. First commit on claude/v012-large-pr-perf.

## Notes

2026-11-04 reconciliation: already fixed in e50fee2e (fix(diff): model a deleted file with no hunks), retained by forward ancestry in owning PR284 head768a504d and final0487921d. Independent fresh immutable048 execution passed both exact regressions: test_a_deleted_empty_file_keeps_the_sections_beside_it and test_a_comparison_deleting_an_empty_file_keeps_its_files (2passed0.78s). The endpoint case uses real Git history deleting empty __init__.py alongside binary/modified neighbors and requires HTTP200/deletedready/nohunks/neighborhunks/no warnings. Evidence merge-gating-21-0487921d/empty-deletion-exact048.log. No further source fix needed. Keep open until actual feature landing; then close against the merge commit.

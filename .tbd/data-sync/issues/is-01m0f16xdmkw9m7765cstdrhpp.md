---
type: is
id: is-01m0f16xdmkw9m7765cstdrhpp
title: "Diff --diff-check: read blobs through one batched cat-file, not one process per blob"
kind: task
status: open
priority: 3
version: 5
spec_path: docs/project/specs/active/plan-2026-08-17-general-diff-rendering.md
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01kxse0d3sm8h0p1yh1mjwgbxz
hold: null
hold_until: null
created_at: 2026-08-20T07:29:46.931Z
updated_at: 2026-11-14T18:45:01.756Z
started_at: 2026-11-01T16:21:30.331Z
---
PR #58 review S3 (deferred). The shared-parser half landed in PR #276 (b73f5a62): cli/diff_cli._materialize and tests/diff_fixture_repo.materialize_tree both read ls-tree through git/tree_source.iter_ls_tree_records. Remaining: --diff-check still spawns one `git cat-file blob` per blob, both when it materializes each tree (src/metabrowser/cli/diff_cli.py:200) and when it prefetches content refs (:241). Read them through one `git cat-file --batch` process. git/tree_source.py already has a batch reader pooled per store (_BatchObjectReader, read_store_blob), and a local checkout would need a way to use it.

## Notes

2026-11-01: fixed in PR #276, open, CI green at its last read. Close when it merges; its required review has not run. Partly: the ls-tree half only; the cat-file --batch half stays open.

2026-11-04 final landing update: all 23 PRs in this delivery (21 feature PRs plus #297 and #298) are merged on main https://github.com/jlevy/metabrowser/commit/db52ec09cf839269da3a56fd396e44f3092995a9. Postlanding Review E: https://github.com/jlevy/metabrowser/pull/298#pullrequestreview-5772391263. Final-main CI passed all nine jobs: https://github.com/jlevy/metabrowser/actions/runs/41868009781. The verified global CLI is 0.11.1.dev1154+db52ec09; final installed-wheel, browser, coordinator manual and production-cache acceptance are complete. Current feature landing is fully accepted. Earlier pending-gate or no-merge statements are historical; preserve each original build, test and measurement provenance. This does not claim a v0.12.0 release, a quiet-host performance result or completion of separate future work.

PR #276 and its required reviews are complete and merged: the shared ls-tree materializer half is delivered. The cat-file --batch/batched-blob-read half remains unimplemented. Keep this partial-scope task open; the older open-PR/review-pending condition is historical.

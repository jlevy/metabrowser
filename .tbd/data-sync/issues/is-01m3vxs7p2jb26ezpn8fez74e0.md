---
type: is
id: is-01m3vxs7p2jb26ezpn8fez74e0
title: "Remove GitTreeSource.read_blob_oid: no caller in the product"
kind: task
status: closed
priority: 4
version: 4
spec_path: docs/project/specs/active/plan-2026-09-23-v012-thin-mirror.md
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m3te95dfdnc80j5xywqje9ke
hold: null
hold_until: null
created_at: 2026-10-01T14:27:06.050Z
updated_at: 2026-11-04T17:14:29.869Z
started_at: 2026-11-01T16:05:46.323Z
closed_at: 2026-11-04T17:14:29.869Z
close_reason: "Scoped implementation independently reviewed and tested; owning feature PRs are actually merged. Final main https://github.com/jlevy/metabrowser/commit/db52ec09cf839269da3a56fd396e44f3092995a9 includes account fix https://github.com/jlevy/metabrowser/pull/297 and documentation https://github.com/jlevy/metabrowser/pull/298, with final manual acceptance and per-issue qualifications checked. Individual source, test, review and merge evidence: ACTION-PLAN.json SHA-256 d0867a696ee055cc27911e83c4f70744b419a3ca4a7a1218f0eeaf419dc37589. Future scope and historical dependency relationships remain open or preserved as recorded."
resolution: null
duplicate_of: null
---
From PR #257 (mb-79t3): GitTreeSource.read_blob_oid in src/metabrowser/git/tree_source.py has no caller under src/; only three tests call it, and a mutation of it (reviewer's T11) is caught by nothing. Delete the method and its three test uses, or name the caller that needs it. Also from that review, equivalent mutants to note, not fix: the /raw route's own non-blob check duplicates read_blob's refusal (C01, C02), and the mailmap arguments change nothing for the history formats in use (%an/%ae are not mailmap-mapped; R04), so one of each pair could be removed as redundant. Not labelled v0.12.

## Notes

2026-11-01: fixed in PR #274, open, CI green at its last read. Close when it merges; its required review has not run.

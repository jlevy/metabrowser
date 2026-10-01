---
type: is
id: is-01m3vxs7p2jb26ezpn8fez74e0
title: "Remove GitTreeSource.read_blob_oid: no caller in the product"
kind: task
status: open
priority: 4
version: 1
spec_path: docs/project/specs/active/plan-2026-09-23-v012-thin-mirror.md
labels: []
dependencies: []
parent_id: is-01m3te95dfdnc80j5xywqje9ke
created_at: 2026-10-01T14:27:06.050Z
updated_at: 2026-10-01T14:27:06.050Z
---
From PR #257 (mb-79t3): GitTreeSource.read_blob_oid in src/metabrowser/git/tree_source.py has no caller under src/; only three tests call it, and a mutation of it (reviewer's T11) is caught by nothing. Delete the method and its three test uses, or name the caller that needs it. Also from that review, equivalent mutants to note, not fix: the /raw route's own non-blob check duplicates read_blob's refusal (C01, C02), and the mailmap arguments change nothing for the history formats in use (%an/%ae are not mailmap-mapped; R04), so one of each pair could be removed as redundant. Not labelled v0.12.

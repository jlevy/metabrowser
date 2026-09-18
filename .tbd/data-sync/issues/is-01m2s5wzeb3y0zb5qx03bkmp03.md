---
type: is
id: is-01m2s5wzeb3y0zb5qx03bkmp03
title: Prefetch default-revision blobs and pin crash recovery
kind: task
status: in_progress
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-08-11-open-repo-from-git-url.md
delegate: unknown@cursor
labels:
  - release:v0.11.0
dependencies: []
parent_id: is-01kzsb4jnyd56wy89xmztkmz2m
hold: null
hold_until: null
created_at: 2026-09-18T02:35:32.170Z
updated_at: 2026-09-18T02:35:36.190Z
started_at: 2026-09-18T02:35:36.190Z
---
After a blobless staging fetch, explicitly fetch the default revision's blob-mode tree entries (100644, 100755, 120000) by object ID: ls-tree -r -z --full-tree, then fetch --stdin with negotiation noop and the object-fetch low-speed bound. A prefetch transport failure still publishes with object_state converging. Pin crash recovery: a staging entry whose liveness lock is free is swept; a store published without an alias is reclaimed. No CLI wiring, no serving, no HTTPS.

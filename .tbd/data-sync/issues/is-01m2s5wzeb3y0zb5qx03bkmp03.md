---
type: is
id: is-01m2s5wzeb3y0zb5qx03bkmp03
title: Prefetch default-revision blobs and pin crash recovery
kind: task
status: closed
priority: 1
version: 5
spec_path: docs/project/specs/active/plan-2026-08-11-open-repo-from-git-url.md
delegate: unknown@cursor
labels:
  - release:v0.11.0
dependencies: []
parent_id: is-01kzsb4jnyd56wy89xmztkmz2m
hold: null
hold_until: null
created_at: 2026-09-18T02:35:32.170Z
updated_at: 2026-09-20T05:50:31.135Z
started_at: 2026-09-18T02:35:36.190Z
closed_at: 2026-09-20T05:50:31.135Z
close_reason: "Implemented on survivor draft #217 https://github.com/jlevy/metabrowser/pull/217 (file:// acquire, no serving). Review remains mb-k900. Nothing merged to main."
resolution: null
duplicate_of: null
---
After a blobless staging fetch, explicitly fetch the default revision's blob-mode tree entries (100644, 100755, 120000) by object ID: ls-tree -r -z --full-tree, then fetch --stdin with negotiation noop and the object-fetch low-speed bound. A prefetch transport failure still publishes with object_state converging. Pin crash recovery: a staging entry whose liveness lock is free is swept; a store published without an alias is reclaimed. No CLI wiring, no serving, no HTTPS.

## Notes

PR https://github.com/jlevy/metabrowser/pull/145 on cursor/v011-cache-prefetch-recover-bd04 HEAD f369c4cf, stacked on #144. All 7 CI checks green (lint, test 3.12/3.13/3.14/3.14t, distribution, stack-integration). Lands HEAD-tree blob prefetch after blobless fetch (ls-tree + fetch --stdin, FETCH_POLICY, low-speed bound) and crash sweep of a staging entry whose lock is free. Prefetch failure still validates staging. run_git accepts bounded stdin. CLI still fails closed; no serving. Do not close until review. Next: --no-serve (mb-1i98) and goldens (mb-dg00).

---
type: is
id: is-01m0h1njbgvyzhht9gn4y15z4d
title: "PR #59 review R9: architecture doc overclaims test coverage for invariant 2"
kind: bug
status: closed
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01m0h1neycr90x9zn2evw9vnjq
created_at: 2026-08-21T02:16:15.984Z
updated_at: 2026-08-21T02:28:33.562Z
closed_at: 2026-08-21T02:28:33.562Z
close_reason: "Fixed in 40df198 on PR #59. R2: revisions now come from a process-wide sequence and the ETag carries the served root; reproduced the cross-root body reuse first and it no longer occurs. R5: eviction-epoch map released once no rollup pass is in flight. R8: envelope totals seeded into the reconciler at mount. R9: added the source-scan guard enforcing invariant 2 and moved test_browser_recent.py onto the real write path. R3b: shared-build test now gates on events and asserts the build survives its starter's cancellation."
---

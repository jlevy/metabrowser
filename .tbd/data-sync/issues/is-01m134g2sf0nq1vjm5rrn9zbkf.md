---
type: is
id: is-01m134g2sf0nq1vjm5rrn9zbkf
title: "D2: blobless acquisition contradicts the offline guarantee"
kind: bug
status: closed
priority: 1
version: 2
spec_path: docs/project/reviews/review-2026-08-27-independent-design-review.md
labels: []
dependencies: []
parent_id: is-01m134g1jm1dr1xgfhct0ja3c7
created_at: 2026-08-28T02:52:01.710Z
updated_at: 2026-08-28T03:02:49.691Z
closed_at: 2026-08-28T03:02:49.690Z
close_reason: Fixed in dbd5521 (D2). See the commit message and the plan diff.
resolution: null
duplicate_of: null
---
The plan says a cache hit is an offline operation served without fetch, but a blobless clone lazily fetches blobs from the promisor remote when content is read. The project's own research observed exactly this: blame failed with 'could not fetch from promisor remote' under an intercepted network. No lazy-fetch policy, no mapping to deferred/unavailable, no acceptance case. Fix in Phase 0 beside the version gates: disable lazy fetch on read paths (--no-lazy-fetch / GIT_NO_LAZY_FETCH, needs its own floor row) and map misses to deferred/unavailable, or gate blobless on that floor, or accept lazy fetch and rewrite the guarantee to what is true.

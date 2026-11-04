---
type: is
id: is-01m6kb7886n3r5my9ygqn2r66y
title: Align the acquisition state table with current policies and records
kind: bug
status: closed
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01m6jhctf78vq1v7ndv43jzssy
created_at: 2026-11-04T13:15:52.453Z
updated_at: 2026-11-04T17:21:01.600Z
closed_at: 2026-11-04T17:21:01.600Z
close_reason: "All 17 accepted documentation findings corrected in reviewed/merged PR #298 and independently verified on its exact final-main tree. Completed against actual final main https://github.com/jlevy/metabrowser/commit/db52ec09cf839269da3a56fd396e44f3092995a9; final independent integration review and all nine main CI jobs passed. Original evidence retains its execution pins; genuine future and release scope remains separate."
resolution: null
duplicate_of: null
---
Documentation review D10: maintained repository-source state table denies a low-speed bound, assumes every staged object is locally owned, and names nonexistent strategy/object_state fields. Current origin/process policies bound transport and acquisition; admitted overlays can borrow objects; actual RepositoryStore and RepositoryStoreState use acquisition/lender and documented default-ref/time/operation fields. Correct current state rows against source while retaining clearly historical measurements. No runtime or schema change.

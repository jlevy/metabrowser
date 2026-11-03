---
type: is
id: is-01m6f60ncbgnmwgg9g07wcsj4t
title: "Overlay stores step 2: healing, commits_unavailable, and blob verification"
kind: feature
status: in_progress
priority: 1
version: 4
labels:
  - release:v0.12.0
dependencies: []
parent_id: is-01m6f3n89kn7ztmfhrzswxnsgz
created_at: 2026-11-02T22:27:55.913Z
updated_at: 2026-11-03T11:44:20.648Z
---
Plan step 2, needed for the owner's goal and proposed for 0.12.x: the healing job (sweep, by commit ID, then the ref), commits_unavailable, blob verification once measured, --checkout as repair, and the replica fixtures. After step 1 is reviewed.

## Notes

Taking over after #283 correctness and #288 completion checkpoint ef7045b9. Approved scope: explicit bounded missing-object recovery (displayed commit IDs before current PR ref), no implicit clone or checkout writes, and SHA1/SHA256 verification of completely consumed bounded blobs. Preserve existing partial-window semantics and public shapes; partial windows are not claimed authenticated. First prove exact object-ID fetch on replica and public GitHub, use gh blob API only if proven necessary. Measure hash/diff verification overhead, no full repository walks. Parent handles independent review/full verification/CI; no synchronization from this agent.

2026-11-03 independent-review integration at final tip 58270d69. Bounded object healing and authentication are complete across owning #283 3cb49015 and #288 58270d69, with independent F and D reviews/rechecks. Explicit Files Refresh uses the displayed pair and observed object IDs before current-ref refresh, without checkout writes or automatic clone; whole SHA1/SHA256 objects authenticate, partial windows retain their original bound. Persisted corrupt statistics and retained old pack readers are fixed. Replica, negative-control and actual Chrome success/failure/recovery checks pass; eight read-only live GitHub tests pass on58270d69. Limits are explicit: missing ancestry can prevent exact-ID fetch negotiation and yield commits_unavailable; origin may not serve an old object; a missing pinned tree may prevent startup before page repair. No speculative full clone or full-store object scan is claimed. Final full verification, publication and remote CI are coordinator gates still pending; no PR merged.

---
type: is
id: is-01m6f60ncbgnmwgg9g07wcsj4t
title: "Overlay stores step 2: healing, commits_unavailable, and blob verification"
kind: feature
status: in_progress
priority: 1
version: 2
labels:
  - release:v0.12.0
dependencies: []
parent_id: is-01m6f3n89kn7ztmfhrzswxnsgz
created_at: 2026-11-02T22:27:55.913Z
updated_at: 2026-11-03T08:43:03.076Z
---
Plan step 2, needed for the owner's goal and proposed for 0.12.x: the healing job (sweep, by commit ID, then the ref), commits_unavailable, blob verification once measured, --checkout as repair, and the replica fixtures. After step 1 is reviewed.

## Notes

Taking over after #283 correctness and #288 completion checkpoint ef7045b9. Approved scope: explicit bounded missing-object recovery (displayed commit IDs before current PR ref), no implicit clone or checkout writes, and SHA1/SHA256 verification of completely consumed bounded blobs. Preserve existing partial-window semantics and public shapes; partial windows are not claimed authenticated. First prove exact object-ID fetch on replica and public GitHub, use gh blob API only if proven necessary. Measure hash/diff verification overhead, no full repository walks. Parent handles independent review/full verification/CI; no synchronization from this agent.

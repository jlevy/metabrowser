---
type: is
id: is-01m6f60ncbgnmwgg9g07wcsj4t
title: "Overlay stores step 2: healing, commits_unavailable, and blob verification"
kind: feature
status: closed
priority: 1
version: 6
labels:
  - release:v0.12.0
dependencies: []
parent_id: is-01m6f3n89kn7ztmfhrzswxnsgz
created_at: 2026-11-02T22:27:55.913Z
updated_at: 2026-11-04T17:18:11.023Z
closed_at: 2026-11-03T20:17:10.189Z
close_reason: "Completed by forward commits in the PR-support stack; independent reviews, rechecks and dispositions are published on the owning PRs. Final integration ea771741211193a387c1771e04df29b5a9698100 passed make verify (4712 Python, 9 expected skips, 373 transcripts), 8 public live tests, installed-wheel Chrome (22 actions, 25 unchanged checkout/Git fingerprints), and all 171 CI jobs across 19 current-head runs on 14 PRs. Final clean review: https://github.com/jlevy/metabrowser/pull/288#pullrequestreview-5758664799 . No PR merged."
resolution: null
duplicate_of: null
---
Plan step 2, needed for the owner's goal and proposed for 0.12.x: the healing job (sweep, by commit ID, then the ref), commits_unavailable, blob verification once measured, --checkout as repair, and the replica fixtures. After step 1 is reviewed.

## Notes

Taking over after #283 correctness and #288 completion checkpoint ef7045b9. Approved scope: explicit bounded missing-object recovery (displayed commit IDs before current PR ref), no implicit clone or checkout writes, and SHA1/SHA256 verification of completely consumed bounded blobs. Preserve existing partial-window semantics and public shapes; partial windows are not claimed authenticated. First prove exact object-ID fetch on replica and public GitHub, use gh blob API only if proven necessary. Measure hash/diff verification overhead, no full repository walks. Parent handles independent review/full verification/CI; no synchronization from this agent.

2026-11-03 independent-review integration at final tip 58270d69. Bounded object healing and authentication are complete across owning #283 3cb49015 and #288 58270d69, with independent F and D reviews/rechecks. Explicit Files Refresh uses the displayed pair and observed object IDs before current-ref refresh, without checkout writes or automatic clone; whole SHA1/SHA256 objects authenticate, partial windows retain their original bound. Persisted corrupt statistics and retained old pack readers are fixed. Replica, negative-control and actual Chrome success/failure/recovery checks pass; eight read-only live GitHub tests pass on58270d69. Limits are explicit: missing ancestry can prevent exact-ID fetch negotiation and yield commits_unavailable; origin may not serve an old object; a missing pinned tree may prevent startup before page repair. No speculative full clone or full-store object scan is claimed. Final full verification, publication and remote CI are coordinator gates still pending; no PR merged.

2026-11-04 final landing update: all 23 PRs in this delivery (21 feature PRs plus #297 and #298) are merged on main https://github.com/jlevy/metabrowser/commit/db52ec09cf839269da3a56fd396e44f3092995a9. Postlanding Review E: https://github.com/jlevy/metabrowser/pull/298#pullrequestreview-5772391263. Final-main CI passed all nine jobs: https://github.com/jlevy/metabrowser/actions/runs/41868009781. The verified global CLI is 0.11.1.dev1154+db52ec09; final installed-wheel, browser, coordinator manual and production-cache acceptance are complete. Current feature landing is fully accepted. Earlier pending-gate or no-merge statements are historical; preserve each original build, test and measurement provenance. This does not claim a v0.12.0 release, a quiet-host performance result or completion of separate future work.

The reviewed bounded healing, displayed-endpoint refresh and whole-object authentication work landed through PRs #283 and #288. Preserve the stated commits_unavailable, origin-object-availability and missing-startup-tree limitations; no speculative full clone or full-store object walk is claimed. Keep this completed scope closed.

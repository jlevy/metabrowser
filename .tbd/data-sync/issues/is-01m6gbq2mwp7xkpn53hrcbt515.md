---
type: is
id: is-01m6gbq2mwp7xkpn53hrcbt515
title: "PR #284 F1: preserve the generic hydration-bound regression"
kind: bug
status: open
priority: 2
version: 3
labels: []
dependencies: []
parent_id: is-01m6g5eq1rdb9f15dx2kecf1p0
created_at: 2026-11-03T09:26:47.707Z
updated_at: 2026-11-03T11:44:10.214Z
---
Independent strong Review F at 0c37ce6c reproduced a required ordinary-folder test failure: comparison_at binds the old MAX_HYDRATED_FILES default, while the test injects a smaller current bound and validation rejects it. Fixed on the owning #284 branch in f5b8eec2 by explicitly forwarding the current generic bound. Production default stays fifty; PR policy stays eight. The unchanged failing test plus three policy/binary tests pass independently; five cache corruption/security probes also pass. Pending final forward propagation, remote publication and CI.

## Notes

2026-11-03 independent-review integration at final tip 58270d69. Review F1 is fixed by f5b8eec2 and independently rechecked. Retained at owning #284 a876c64b with unchanged product source. Generic hydration stays fifty and PR hydration eight; the original meaningful bound regression remains intact. Final full verification, publication and remote CI are coordinator gates still pending; no PR merged.

---
type: is
id: is-01m6gbq2mwp7xkpn53hrcbt515
title: "PR #284 F1: preserve the generic hydration-bound regression"
kind: bug
status: closed
priority: 2
version: 4
labels: []
dependencies: []
parent_id: is-01m6g5eq1rdb9f15dx2kecf1p0
created_at: 2026-11-03T09:26:47.707Z
updated_at: 2026-11-03T20:17:09.705Z
closed_at: 2026-11-03T20:17:09.705Z
close_reason: "Completed by forward commits in the PR-support stack; independent reviews, rechecks and dispositions are published on the owning PRs. Final integration ea771741211193a387c1771e04df29b5a9698100 passed make verify (4712 Python, 9 expected skips, 373 transcripts), 8 public live tests, installed-wheel Chrome (22 actions, 25 unchanged checkout/Git fingerprints), and all 171 CI jobs across 19 current-head runs on 14 PRs. Final clean review: https://github.com/jlevy/metabrowser/pull/288#pullrequestreview-5758664799 . No PR merged."
resolution: null
duplicate_of: null
---
Independent strong Review F at 0c37ce6c reproduced a required ordinary-folder test failure: comparison_at binds the old MAX_HYDRATED_FILES default, while the test injects a smaller current bound and validation rejects it. Fixed on the owning #284 branch in f5b8eec2 by explicitly forwarding the current generic bound. Production default stays fifty; PR policy stays eight. The unchanged failing test plus three policy/binary tests pass independently; five cache corruption/security probes also pass. Pending final forward propagation, remote publication and CI.

## Notes

2026-11-03 independent-review integration at final tip 58270d69. Review F1 is fixed by f5b8eec2 and independently rechecked. Retained at owning #284 a876c64b with unchanged product source. Generic hydration stays fifty and PR hydration eight; the original meaningful bound regression remains intact. Final full verification, publication and remote CI are coordinator gates still pending; no PR merged.

---
type: is
id: is-01m134g6t4q7dc1ywh2jtnhh6t
title: "D9: provider snapshot store has no reclamation rule"
kind: chore
status: closed
priority: 2
version: 2
spec_path: docs/project/reviews/review-2026-08-27-independent-design-review.md
labels: []
dependencies: []
parent_id: is-01m134g1jm1dr1xgfhct0ja3c7
created_at: 2026-08-28T02:52:05.826Z
updated_at: 2026-08-28T03:02:51.826Z
closed_at: 2026-08-28T03:02:51.825Z
close_reason: Fixed in dbd5521 (D9). See the commit message and the plan diff.
resolution: null
duplicate_of: null
---
The cache plan established that retention without a reclamation rule is how a cache becomes the largest directory in a home folder, and gave staging/trash/quarantine a rule each. The provider plan's immutable snapshots and superseded manifests have none. Add one: snapshots unreferenced by any retained manifest are collectable, the current manifest and its snapshots are never collected, and offline or deleted sources retain their last validated set.

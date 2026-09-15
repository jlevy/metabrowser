---
type: is
id: is-01m2h9a0yd9zfnhtewqm7kfkgq
title: "PR #125 review C-R6: key PR index pointers by canonical query"
kind: bug
status: closed
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
labels: []
dependencies: []
parent_id: is-01m2h984s9t8fhm2efg67nwmve
created_at: 2026-09-15T01:01:09.963Z
updated_at: 2026-09-15T01:38:10.155Z
closed_at: 2026-09-15T01:38:10.154Z
close_reason: "Fixed C-R6: added deterministic query-keyed current/last-complete index pointers plus a conventional default alias to an exact query."
resolution: null
duplicate_of: null
---
PR #125 contracts C-R6. Define canonical query descriptors and safe digests, store current pointers under index query keys with an optional default pointer, persist the full canonical query, and verify the digest on read.

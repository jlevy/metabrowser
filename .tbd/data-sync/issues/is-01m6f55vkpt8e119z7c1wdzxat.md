---
type: is
id: is-01m6f55vkpt8e119z7c1wdzxat
title: metab --api --format json still prints header lines on stdout
kind: bug
status: closed
priority: 3
version: 4
labels:
  - release:v0.12.0
dependencies: []
parent_id: is-01m6f3n89kn7ztmfhrzswxnsgz
created_at: 2026-11-02T22:13:17.556Z
updated_at: 2026-11-04T17:14:29.863Z
closed_at: 2026-11-04T17:14:29.863Z
close_reason: "Scoped implementation independently reviewed and tested; owning feature PRs are actually merged. Final main https://github.com/jlevy/metabrowser/commit/db52ec09cf839269da3a56fd396e44f3092995a9 includes account fix https://github.com/jlevy/metabrowser/pull/297 and documentation https://github.com/jlevy/metabrowser/pull/298, with final manual acceptance and per-issue qualifications checked. Individual source, test, review and merge evidence: ACTION-PLAN.json SHA-256 d0867a696ee055cc27911e83c4f70744b419a3ca4a7a1218f0eeaf419dc37589. Future scope and historical dependency relationships remain open or preserved as recorded."
resolution: null
duplicate_of: null
---
Found 2026-11-02. With --api, --format json prints api: and status: lines before the JSON, so stdout is not JSON and needs tail -n +3, which the docs currently show. Check whether the plain --api form is a golden contract before changing it; the json form should be parseable as it stands.

## Notes

2026-11-03: fixed on PR 280 (9ee1ab7f): --api with --format json or yaml prints the envelope alone. Review C4 (a 202 cut mid-response) fixed at f867425f. Closes when the stack merges.

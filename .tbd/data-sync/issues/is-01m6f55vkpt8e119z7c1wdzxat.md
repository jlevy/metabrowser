---
type: is
id: is-01m6f55vkpt8e119z7c1wdzxat
title: metab --api --format json still prints header lines on stdout
kind: bug
status: in_progress
priority: 3
version: 3
labels:
  - release:v0.12.0
dependencies: []
parent_id: is-01m6f3n89kn7ztmfhrzswxnsgz
created_at: 2026-11-02T22:13:17.556Z
updated_at: 2026-11-03T07:00:52.176Z
---
Found 2026-11-02. With --api, --format json prints api: and status: lines before the JSON, so stdout is not JSON and needs tail -n +3, which the docs currently show. Check whether the plain --api form is a golden contract before changing it; the json form should be parseable as it stands.

## Notes

2026-11-03: fixed on PR 280 (9ee1ab7f): --api with --format json or yaml prints the envelope alone. Review C4 (a 202 cut mid-response) fixed at f867425f. Closes when the stack merges.

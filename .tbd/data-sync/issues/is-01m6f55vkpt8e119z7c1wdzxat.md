---
type: is
id: is-01m6f55vkpt8e119z7c1wdzxat
title: metab --api --format json still prints header lines on stdout
kind: bug
status: open
priority: 3
version: 1
labels:
  - release:v0.12.0
dependencies: []
parent_id: is-01m6f3n89kn7ztmfhrzswxnsgz
created_at: 2026-11-02T22:13:17.556Z
updated_at: 2026-11-02T22:13:17.556Z
---
Found 2026-11-02. With --api, --format json prints api: and status: lines before the JSON, so stdout is not JSON and needs tail -n +3, which the docs currently show. Check whether the plain --api form is a golden contract before changing it; the json form should be parseable as it stands.

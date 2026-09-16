---
type: is
id: is-01m2ktr3rq01pq9w0dpbvm1vpy
title: "Hosted releases R2: direct release and asset cache"
kind: feature
status: open
priority: 2
version: 7
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
labels:
  - hosted-releases
dependencies:
  - type: blocks
    target: is-01m2ktsfdmrdehcpvg9kqsg6yb
parent_id: is-01m2ktnhjgw0bsgcaw6e8h9x2e
child_order_hints:
  - is-01m2ktrc9jfznq2b0kh57e4735
  - is-01m2ktrgz0vvvg0z0ggf17yjrb
created_at: 2026-09-16T00:44:26.260Z
updated_at: 2026-09-16T00:54:50.407Z
---
One formal PR stacked on green R1. Extend GitHub URL reduction for /releases/tag/<tag>, acquire one directly addressed release and bounded asset metadata, resolve its exact tag revision availability, and publish immutable detail/resource sets through the common auth-scoped provider store with current/last-complete/offline behavior. Absence from a list is never deletion proof; asset bytes remain on-demand content.

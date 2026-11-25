---
type: is
id: is-01m2ktr3rq01pq9w0dpbvm1vpy
title: "Hosted releases R2: direct release and asset cache"
kind: feature
status: closed
priority: 2
version: 9
spec_path: docs/project/specs/done/plan-2026-08-27-github-provider-and-pull-requests.md
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
updated_at: 2026-11-25T02:40:21.992Z
closed_at: 2026-11-14T18:43:56.446Z
close_reason: "Obsolete as written: R2 publishes through the auth-scoped provider store that the thin-mirror plan retired and #246 removed (kept only on draft #247); release browsing stays tracked by mb-7srn until re-planned."
resolution: canceled
duplicate_of: null
---
One formal PR stacked on green R1. Extend GitHub URL reduction for /releases/tag/<tag>, acquire one directly addressed release and bounded asset metadata, resolve its exact tag revision availability, and publish immutable detail/resource sets through the common auth-scoped provider store with current/last-complete/offline behavior. Absence from a list is never deletion proof; asset bytes remain on-demand content.

---
type: is
id: is-01m2ktprcgghmr7z8mpshmymcd
title: "Hosted releases R1: GitHub coverage oracle and gh mapping"
kind: feature
status: closed
priority: 2
version: 8
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
labels:
  - hosted-releases
dependencies:
  - type: blocks
    target: is-01m2ktrc9jfznq2b0kh57e4735
parent_id: is-01m2ktnhjgw0bsgcaw6e8h9x2e
child_order_hints:
  - is-01m2ktpzzzg5crhj0ggx8bbt1t
  - is-01m2ktq5v8236zvaxeyk7gzzhk
created_at: 2026-09-16T00:43:41.839Z
updated_at: 2026-11-14T18:44:33.797Z
closed_at: 2026-11-14T18:44:33.796Z
close_reason: "Obsolete as written: R1 maps into the retired R0 contracts and the GitHub coverage oracle that #246 removed (kept only on draft #247); release browsing stays tracked by mb-7srn until re-planned."
resolution: canceled
duplicate_of: null
---
One formal PR stacked on green R0. Record scrubbed public GitHub release and asset responses, prove every common field observed/derived/optional/unavailable, and implement fixed bounded gh api normalization into Release, ReleaseAsset, and ReleaseIndex records without using gh release presentation JSON or retaining raw responses.

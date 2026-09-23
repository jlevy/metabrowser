---
type: is
id: is-01m2kw2cra83fyszkrptvhfead
title: "Hosted review Phase 4A review: publish direct PR view PR"
kind: task
status: closed
priority: 1
version: 18
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
labels:
  - stack:publication
  - release:v0.12.0
dependencies:
  - type: blocks
    target: is-01m2zvffb1z2vsseb9d9nqcj6m
  - type: blocks
    target: is-01m35tapm6wjnn235hr3s669b7
parent_id: is-01m10vgwqwn8gjdv8fm183vztr
created_at: 2026-09-16T01:07:31.721Z
updated_at: 2026-09-23T07:37:19.396Z
closed_at: 2026-09-23T07:37:19.392Z
close_reason: "Superseded 2026-09-23 by the thin-mirror plan (docs/project/specs/active/plan-2026-09-23-v012-thin-mirror.md, PR #227; epic mb-hall), per the user's decisions. Replacement: mb-vrl7 (PR view), built as an internal page without the public router, address-space and resource-kind SDKs."
resolution: null
duplicate_of: null
---
Independently review mounted routes, canonical hosted address codec, route-backed resource kinds, direct PR rendering without an index, diff composition, CLI parity, browserless lifecycle, and hostile-content handling. Resolve findings through the review shortcut, run make verify, and publish one formal draft GitHub PR with gh stacked on the exact green Phase 3B head. Record the exact PR URL, base and head branches and OIDs, review record, final green CI, and registration with mb-n2ro. Do not merge.

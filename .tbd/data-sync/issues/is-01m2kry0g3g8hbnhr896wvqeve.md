---
type: is
id: is-01m2kry0g3g8hbnhr896wvqeve
title: "Hosted review Phase 0C.2b: review and publish the format-boundary phase"
kind: task
status: open
priority: 1
version: 4
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
labels:
  - release:v0.11.0
  - phase:hosted-review-0c2
dependencies:
  - type: blocks
    target: is-01m2k1jrywxceb6n3r0pbadegx
  - type: blocks
    target: is-01m2k713pxra1ns2fk3pcwrpb6
  - type: blocks
    target: is-01m2kwk6h6pzxanejy6c339r08
parent_id: is-01m2k1jrywxceb6n3r0pbadegx
created_at: 2026-09-16T00:12:42.370Z
updated_at: 2026-09-16T01:16:42.405Z
---
Run independent inventory, installed-wheel, parity, architecture, and delivery reviews; address every finding; run make verify; sync beads; and publish exactly one formal draft Phase 0C.2 PR with gh, based on the exact green Phase 0C.1 head. Record base/head OIDs and stack path, watch GitHub CI to a final green summary, and register the PR with mb-n2ro. Do not merge here; mb-n2ro alone owns explicit-approval landing and retargeting, and mb-63ym closes only after every Phase 0 PR is landed and revalidated.

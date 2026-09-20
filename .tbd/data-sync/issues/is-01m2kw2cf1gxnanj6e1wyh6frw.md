---
type: is
id: is-01m2kw2cf1gxnanj6e1wyh6frw
title: "GitHub Phase 3C review: publish bounded PR index PR"
kind: task
status: open
priority: 1
version: 18
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
labels:
  - release:v0.11.0
  - stack:publication
dependencies:
  - type: blocks
    target: is-01m2kw2d2arc9hn25pfsc4me50
  - type: blocks
    target: is-01kxry31tw40txkbzctzv1mtsd
  - type: blocks
    target: is-01m2h7jjgpzyfbf10238j32z6q
  - type: blocks
    target: is-01m2zvffb1z2vsseb9d9nqcj6m
parent_id: is-01m10xd666fefs5z7ft5m58zj0
created_at: 2026-09-16T01:07:31.424Z
updated_at: 2026-09-20T16:48:25.400Z
---
Independently review the bounded PR discovery index, query identity, pagination, completeness, no-ref-fetch, and offline cache behavior after the direct PR view works without discovery. Resolve findings through the review shortcut, run make verify, and publish one formal draft GitHub PR with gh stacked on the exact green Phase 4A direct-view head. Record the exact PR URL, base and head branches and OIDs, review record, final green CI, and registration with mb-n2ro. Do not merge.

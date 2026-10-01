---
type: is
id: is-01m2kw2cf1gxnanj6e1wyh6frw
title: "GitHub Phase 3C review: publish bounded PR index PR"
kind: task
status: closed
priority: 1
version: 21
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
labels:
  - stack:publication
  - release:v0.12.0
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
updated_at: 2026-10-01T00:13:18.403Z
closed_at: 2026-10-01T00:13:18.402Z
close_reason: "Superseded 2026-09-23 by the thin-mirror plan (docs/project/specs/active/plan-2026-09-23-v012-thin-mirror.md, PR #227; epic mb-hall), per the user's decisions. These publication beads belonged to the retired Phase 3C/4B/4C stack. The PR list, panel and review anchors are deferred (mb-lnkl, mb-iw1v, mb-rldc) and get new review beads when re-planned."
resolution: canceled
duplicate_of: null
---
Independently review the bounded PR discovery index, query identity, pagination, completeness, no-ref-fetch, and offline cache behavior after the direct PR view works without discovery. Resolve findings through the review shortcut, run make verify, and publish one formal draft GitHub PR with gh stacked on the exact green Phase 4A direct-view head. Record the exact PR URL, base and head branches and OIDs, review record, final green CI, and registration with mb-n2ro. Do not merge.

---
type: is
id: is-01m2ktp3wnzbzmr1cvb51qtptf
title: "Hosted releases R0 review: publish the contract PR"
kind: task
status: open
priority: 2
version: 5
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
labels:
  - hosted-releases
dependencies:
  - type: blocks
    target: is-01m2ktnpypp52bxemwarsz57j6
  - type: blocks
    target: is-01m2ktvrasq8fxf38pn3yf1p8j
parent_id: is-01m2ktnpypp52bxemwarsz57j6
created_at: 2026-09-16T00:43:20.851Z
updated_at: 2026-09-16T01:16:58.680Z
---
After independent architecture and contract reviews of Release R0, resolve every finding through the review shortcut, run make verify, sync beads, and create or update the formal draft PR with gh on the exact declared release-stack base. Before closing, record the exact PR URL, base/head branch names, immutable base/head OIDs, review record, final green CI, and registration with mb-kk47. Do not merge; mb-kk47 alone owns approval-gated landing.

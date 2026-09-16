---
type: is
id: is-01m2kw2b66x74xxjjtdp3wrsr4
title: "GitHub Phase 2A review: publish repository URL-open PR"
kind: task
status: open
priority: 1
version: 6
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
labels:
  - release:v0.11.0
  - stack:publication
dependencies:
  - type: blocks
    target: is-01m2kw2bht6rte4gtjdq39n1yt
  - type: blocks
    target: is-01m0dkj0gqvpzpxm7t1tpshf30
  - type: blocks
    target: is-01m2h7gjc36fqv8cv38qd9zynr
  - type: blocks
    target: is-01m2k713pxra1ns2fk3pcwrpb6
parent_id: is-01kzs5m38dz1egphfwf30c8h7n
created_at: 2026-09-16T01:07:30.107Z
updated_at: 2026-09-16T01:16:58.435Z
---
Independently review the repository URL reducer and URL-open slice, resolve all findings through the review shortcut, run make verify, and create or update one formal draft GitHub PR with gh based on the exact named convergence head recorded by mb-j439. Before closing, record the exact PR URL, base and head branch names, immutable base and head OIDs, review record, final green CI, and registration with mb-n2ro. Do not merge; the sole landing coordinator owns approval-gated landing.

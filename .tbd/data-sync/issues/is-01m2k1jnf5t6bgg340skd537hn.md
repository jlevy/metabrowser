---
type: is
id: is-01m2k1jnf5t6bgg340skd537hn
title: "Hosted review Phase 0B.3: add the scrubbed GitHub coverage oracle"
kind: task
status: open
priority: 1
version: 5
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
labels:
  - release:v0.11.0
  - stack:pr125
dependencies:
  - type: blocks
    target: is-01m2k1jq7ydswdag1x08n30hvn
parent_id: is-01m10vgw6vhq82cd495kvhh9gf
child_order_hints:
  - is-01m2krwcrtg8vx2cwqh4v8ddxj
  - is-01m2krwnemr6d0fht4kk7gsafx
created_at: 2026-09-15T17:24:33.379Z
updated_at: 2026-09-16T00:13:02.382Z
---
Coordinate one formal Phase 0B.3 pull request stacked on the exact green Phase 0B.2 head. mb-oc1h owns the scrubbed GitHub coverage oracle, mapping inventory, hostile fixtures, and common-model coverage tests; mb-e95m owns independent review, make verify, bead sync, gh publication, and final green CI. Close this phase only after both children are complete and its PR is registered with mb-n2ro.

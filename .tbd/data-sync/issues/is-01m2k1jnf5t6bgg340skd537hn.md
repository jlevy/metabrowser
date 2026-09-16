---
type: is
id: is-01m2k1jnf5t6bgg340skd537hn
title: "Hosted review Phase 0B.3: add the scrubbed GitHub coverage oracle"
kind: task
status: closed
priority: 1
version: 8
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
labels:
  - release:v0.11.0
  - stack:pr125
  - stack:pr134
dependencies:
  - type: blocks
    target: is-01m2k1jq7ydswdag1x08n30hvn
parent_id: is-01m10vgw6vhq82cd495kvhh9gf
child_order_hints:
  - is-01m2krwcrtg8vx2cwqh4v8ddxj
  - is-01m2krwnemr6d0fht4kk7gsafx
created_at: 2026-09-15T17:24:33.379Z
updated_at: 2026-09-16T05:10:56.431Z
closed_at: 2026-09-16T05:10:56.430Z
close_reason: "Phase 0B.3 implementation and publication are complete in green formal stacked draft PR #134 with documented review dispositions."
resolution: null
duplicate_of: null
---
Coordinate one formal Phase 0B.3 pull request stacked on the exact green Phase 0B.2 head. mb-oc1h owns the scrubbed GitHub coverage oracle, mapping inventory, hostile fixtures, and common-model coverage tests; mb-e95m owns independent review, make verify, bead sync, gh publication, and final green CI. Close this phase only after both children are complete and its PR is registered with mb-n2ro.

## Notes

Phase 0B.3 is complete as draft PR #134: https://github.com/jlevy/metabrowser/pull/134. Exact base is green PR #133 head 74dad3588d6de658ab2c56cf76711b39f0d3a496; exact Phase 0B.3 head is 18ef513adc9782554d456b3ef0fbc7d02e0d975f. The scrubbed no-network GitHub oracle, evidence-driven common-model reconciliation, durable docs, and all review dispositions are complete. Full local and pre-push gates plus all seven GitHub checks are green. No merge performed; next stack layer is Phase 0C.1.

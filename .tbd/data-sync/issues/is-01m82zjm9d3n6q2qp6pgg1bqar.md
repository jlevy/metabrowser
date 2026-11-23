---
type: is
id: is-01m82zjm9d3n6q2qp6pgg1bqar
title: "Bound paid probes: a key's probe interval doubles after consecutive 200s that changed nothing"
kind: task
status: open
priority: 2
version: 1
spec_path: docs/project/specs/active/plan-2026-11-22-pull-request-update-cadence.md
labels: []
dependencies: []
parent_id: is-01m82h0qrnw9vg6vrj597asgpv
created_at: 2026-11-23T01:15:55.043Z
updated_at: 2026-11-23T01:15:55.043Z
---
Phase 1 item from #696 review A2: a pull's REST representation embeds its base and head repository objects, whose pushed_at moves on every push to any branch, so a probe pays one core per push to the repository, per visible page, per server. After a few consecutive 200s that changed nothing, lengthen that key's probe interval (doubling, up to FULL_REFRESH_S); a 304 or a real change resets it. Measure the issue representation (mb-2ppr) first: if it holds, the bound may be unneeded.

---
type: is
id: is-01m82zjm9d3n6q2qp6pgg1bqar
title: "Bound paid probes: a key's probe interval doubles after consecutive 200s that changed nothing"
kind: task
status: closed
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-11-22-pull-request-update-cadence.md
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m82h0qrnw9vg6vrj597asgpv
hold: null
hold_until: null
created_at: 2026-11-23T01:15:55.043Z
updated_at: 2026-11-23T08:02:32.374Z
started_at: 2026-11-23T06:40:01.336Z
closed_at: 2026-11-23T08:02:32.371Z
close_reason: "No code: no key but the list's needs the bound, and the list has it. Evidence (cbe50a266; measured 2026-11-23 06:44-07:12 UTC, read-only, logs in attic/mb-y7ut): (1) issue issues/N: mb-2ppr, 304 in all 90 rounds where the pull's ETag moved. (2) checks, first pages of check-runs and status at CHECKS_PROBE_S: 504 conditional reads of six heads; all 56 200s after a page's first changed a field the record keeps (0 changed nothing); for four pulls with finished checks both pages answered 304 in all 96 reads while the pull's own ETag moved 7 times, so these ETags do not move with the repository. (3) pull pulls/N during the mergeability settle: can pay a 200 that still says null, but is bounded by MERGEABLE_SETTLE_S (renewed no sooner than FULL_REFRESH_S); 10 of 10 null pulls answered by the next read, 0 paid idle (32 of 32 with earlier measurements). (4) list probe: can, and has the doubling (MAX_PAID_PROBE_S, PAID_PROBES_BEFORE_SLOWING, tested in test_github_pull_list_probe.py). There is no pull-representation fallback. Numbers recorded beside CHECKS_PROBE_S and MERGEABLE_SETTLE_S and in the plan's Budget section."
resolution: null
duplicate_of: null
---
Phase 1 item from #696 review A2: a pull's REST representation embeds its base and head repository objects, whose pushed_at moves on every push to any branch, so a probe pays one core per push to the repository, per visible page, per server. After a few consecutive 200s that changed nothing, lengthen that key's probe interval (doubling, up to FULL_REFRESH_S); a 304 or a real change resets it. Measure the issue representation (mb-2ppr) first: if it holds, the bound may be unneeded.

---
type: is
id: is-01m82h0qrnw9vg6vrj597asgpv
title: "Live GitHub updates: what is on screen updates within seconds, everything else every minute or two, inside the rate limit"
kind: epic
status: in_progress
priority: 1
version: 15
spec_path: docs/project/specs/active/plan-2026-11-22-pull-request-update-cadence.md
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/696
    at: 2026-11-22T21:01:45.632Z
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/709
    at: 2026-11-22T22:59:19.912Z
labels:
  - linear
  - Feature
dependencies: []
child_order_hints:
  - is-01m82dqbcj0728gy8tb9xqewe4
  - is-01m82h15ejqn4675xxm6c4xaz8
  - is-01m82h16wc07dbhpd3msz6w8wj
  - is-01m82hx4dgadx9h9b789deab17
  - is-01m82jn9hd045gp3s3e24bygne
  - is-01m82szzfax1dcgyjtrbn87gcz
  - is-01m82t0689c2xsj5yqs9fryy3t
  - is-01m82s87jvewvbb1kp1a9kyt0k
  - is-01m82vvzskcz4ey2fk0nzbc47b
created_at: 2026-11-22T21:01:28.721Z
updated_at: 2026-11-23T00:11:07.439Z
extensions:
  linear:
    id: 0c7789d9-960d-4814-a23b-d2a26e474369
    linked_at: 2026-11-22T21:02:20.346Z
---
A merge on github.com took 48 s to show on an open pull request page (2026-11-22), since the page polled every 30 s and the server held a record fresh for 60 s. This effort gives every GitHub view one update policy: probe what the reader can see every few seconds with conditional requests, which GitHub answers 304 without spending rate limit; read everything in full every minute or two; and keep automatic work under a self-imposed share of the hourly budget.

Plan: docs/project/specs/active/plan-2026-11-22-pull-request-update-cadence.md (PR jlevy/metabrowser#696).

- Phase 1 (a): probes for the pull request on screen and its pending checks.
- Phase 1 (b): a conditional account check, so a probe or job spends no core call checking the sign-in.
- Phase 2: the Pulls list probe, full-read cadence for the catalog, files list, and stacks, and budget admission everywhere.
- Phase 3: Metabrowser's own stores are fetched as often as is useful, since a fetch into them is safe to repeat and spends no rate limit (owner, 2026-11-22): a visible mirror branch probed every few seconds (mb-6pzh), and a served store fetched every few minutes when no page is visible.

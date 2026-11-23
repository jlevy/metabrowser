---
type: is
id: is-01m82h0qrnw9vg6vrj597asgpv
title: "Live GitHub updates: what is on screen updates within seconds, everything else every minute or two, inside the rate limit"
kind: epic
status: closed
priority: 1
version: 35
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
  - is-01m82zjm9d3n6q2qp6pgg1bqar
  - is-01m834mxptcmj4fvcmktwhzq32
  - is-01m83859mjgnk7whvej489dvzc
  - is-01m83ae6tg4m1pqqdf3qwbc26g
  - is-01m83g988ce2e5294bf07rwpbn
  - is-01m83g98v4ar87x5d7q5yqmq6t
  - is-01m83g99cgya820tjjvtjny5ha
  - is-01m83g99y25eh6aegb8gpf5wnx
  - is-01m83g9aj1r65x7qjk68w971qf
  - is-01m83kesy0bwjqpe4nwf0ykpha
  - is-01m83kez288a4cxagyj1tyht3h
  - is-01m83kf3rsy7tc0g1tawd18a4v
  - is-01m83qna533s9rh2z5jh200yc1
  - is-01m83qnbdf3kswkegs0q63gtpm
  - is-01m83qnctc1z0ky04cxdjmr0md
  - is-01m83qnf0r556qas7pn6vwdfat
  - is-01m83qp8kr3hm0t08y7av1p56f
  - is-01m83z9hk4cvwb4vnnhkt17t1b
  - is-01m83zhd3kfcv0c4tgvgd43h4p
created_at: 2026-11-22T21:01:28.721Z
updated_at: 2026-11-23T13:47:01.557Z
closed_at: 2026-11-23T13:47:01.557Z
close_reason: "All agreed phases and follow-ups merged in stack #710 (PRs #696-#747, main b68cc9571). Open follow-ups: mb-pgru, mb-m3gp, mb-mg37."
resolution: null
duplicate_of: null
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

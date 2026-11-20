---
type: is
id: is-01m7wysgm9rg3fdch55nst1wrn
title: "CI speed: finish the Fast CI plan and verify its phases"
kind: epic
status: in_progress
priority: 2
version: 17
spec_path: docs/project/specs/active/plan-2026-11-16-fast-ci.md
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/496
    at: 2026-11-20T19:14:52.551Z
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/499
    at: 2026-11-20T19:14:52.552Z
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/504
    at: 2026-11-20T19:14:52.552Z
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/513
    at: 2026-11-20T19:14:52.552Z
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/514
    at: 2026-11-20T19:14:52.552Z
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/515
    at: 2026-11-20T19:14:52.552Z
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/554
    at: 2026-11-20T19:14:52.552Z
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/585
    at: 2026-11-20T19:14:52.552Z
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/669
    at: 2026-11-20T19:14:52.552Z
labels:
  - linear
  - Improvement
dependencies: []
child_order_hints:
  - is-01m7m3rn4x4ttt604xrtj32vff
  - is-01m7m5vfv9h31f3b6hha08r57z
  - is-01m7ks85cztbqgy4bw9ntv7c7s
  - is-01m7kpnfbtzejh3redbeppejmp
  - is-01m7kpnew2rrszv4ekchm6c75z
  - is-01m7pj8gve71bkvxyw96nqa4yn
  - is-01m7pjrkn0aprh3pz0m4ba5ff6
  - is-01m7wybwgt2zk3z9wgw4ge1kyg
  - is-01m7kh4k0qtd75277xcq14dt1b
  - is-01m7x3dt9bhf2vxgyng4cssa41
  - is-01m7pq9dk5hbfvrq38zv4v53zb
created_at: 2026-11-20T17:06:45.512Z
updated_at: 2026-11-20T19:16:55.199Z
extensions:
  linear:
    id: 1ece55fe-0ac1-49d4-bf60-5ea298d7306c
    linked_at: 2026-11-20T19:16:55.198Z
---
The owner asked on 2026-11-16 for a pull request's gate in 3 to 5 minutes at the same coverage. The assessment and plan merged in #496 (docs/project/specs/active/plan-2026-11-16-fast-ci.md); Phase 1 (#499, four processors) and Phase 2 (#504, parallel jobs with one ci-ok verdict) are merged, and the first measured pull requests took 4.7 to 5.5 minutes.

What remains: finish Phase 1's 10-run acceptance (mb-g0xx), verify Phase 2 after the merge (mb-ohsk), the owner's branch ruleset requiring ci-ok (mb-m4ct), and Phase 3 (path classes mb-pvyg, the serial tier's fixed waits mb-37dw, the Chrome start retry and per-test allowances mb-sicb and mb-bl54). Flaky tests are tracked under mb-1qsn.

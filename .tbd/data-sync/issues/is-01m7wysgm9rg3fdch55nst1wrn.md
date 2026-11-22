---
type: is
id: is-01m7wysgm9rg3fdch55nst1wrn
title: "CI speed: finish the Fast CI plan and verify its phases"
kind: epic
status: in_progress
priority: 2
version: 21
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
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/698
    at: 2026-11-22T21:09:43.748Z
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
  - is-01m82c8bd5hw5cyz98wty5qm63
created_at: 2026-11-20T17:06:45.512Z
updated_at: 2026-11-22T23:30:43.004Z
extensions:
  linear:
    id: 1ece55fe-0ac1-49d4-bf60-5ea298d7306c
    linked_at: 2026-11-20T19:16:55.198Z
---
The owner asked on 2026-11-16 for a pull request's gate in 3 to 5 minutes at the same coverage. The assessment and plan merged in #496 (docs/project/specs/active/plan-2026-11-16-fast-ci.md); Phase 1 (#499, four processors) and Phase 2 (#504, parallel jobs with one ci-ok verdict) are merged, and the first measured pull requests took 4.7 to 5.5 minutes.

What remains: finish Phase 1's 10-run acceptance (mb-g0xx), verify Phase 2 after the merge (mb-ohsk), the owner's branch ruleset requiring ci-ok (mb-m4ct), and Phase 3 (path classes mb-pvyg, the serial tier's fixed waits mb-37dw, the Chrome start retry and per-test allowances mb-sicb and mb-bl54). Flaky tests are tracked under mb-1qsn.

## Notes

2026-11-22 owner decisions in chat, verbatim: (1) "can you be sure these longer-lived tests are only run occasionally, not blocking CI on a routine basis?": slow Chrome tests (measured at 20 s or more) run on pushes to main, in the nightly soak and in the release gate, not on pull requests. (2) "We should aim to have a much faster routine CI cycle. 6 minutes is too long. It should be, ideally, more like 3. unless There's a really strong reason that that's difficult." (3) "we should not be paying Chrome testing costs on CI in terms of time if all we're changing is the CLI or backend things that may not need Chrome testing.": a PR that touches no browser-affecting path skips the Chrome tier, and main always runs the full tier. (4) The owner chose measured-weights shard balancing over a minimal split. Measured on PR run 45063672769: 7.0 min wall, set by chrome 1/4 at 6.2 min, then unit up to 5.3, goldens and serial up to 4.6, and admitted-git 2.8 to 4.2. Work: #698 (measured weights, mb-j5j2) plus a stacked PR for the fast PR path.


2026-11-22 landed: #698 (measured-seconds shard dealing, devtools/shard_weights.json) and #700 (PR path: one interpreter, slow Chrome tests skipped, Chrome only when BROWSER_PATHS change) merged as a stack into main fea5669; mb-j5j2 closed. The PR path now runs 18 checks and took about 3.5 min in its last measurement. The floor is tests/test_github_pulls.py (about 112 s on one worker) plus 45-60 s of setup and collection per job.

---
type: is
id: is-01kzrtbtsh9k6p8x84rta84y4p
title: Assess and publish Metabrowser v0.3.0 minor release
kind: task
status: in_progress
priority: 1
version: 31
labels: []
dependencies: []
child_order_hints:
  - is-01kzs1ky5mhg44p2n3tgv204sc
  - is-01kzs3c844hxhn5fmbxx8j5z1r
  - is-01kzs4vct70w4b81px21hj3dcn
  - is-01kzs5y3mbvz1151xyeg83znnj
  - is-01kzsbeh7nmvevgsmyr9w174d5
  - is-01kzsc71m2gs2sgsjheqemj7v2
  - is-01kzsd1epcab6ghygv2syte5he
  - is-01kzse0dcec8030qn0akzvar9w
  - is-01kzsgf1xeeqrkhzfssqa95qs6
  - is-01kzshazdfnw7wz3h768kgbfmg
  - is-01kzsrn1678d07r42wx26b1kwh
  - is-01kzst1xpjmy6yd8kw5gyekcz9
  - is-01kzthkwjct0arxn9pjyse720a
  - is-01kzthkwwj2ym3cfq756kms6zk
  - is-01kztjpwcq00gxd4p1s73zvbm9
  - is-01kztjypg3zzwf65tkc6m31nph
  - is-01kztk1re8jyap1fcn39p6w3nd
created_at: 2026-08-11T16:26:50.545Z
updated_at: 2026-08-12T09:10:10.444Z
---
Review all user-visible changes since v0.2.0, triage outstanding defects for release blockers, validate the filtering/search stabilization release, prepare accurate v0.3.0 notes, run the complete release gate, publish the GitHub release, verify PyPI artifacts and public smoke tests, and confirm CI.

## Notes

Final v0.3.0 readiness review covered the 93-commit delta from v0.2.0 through main, open issues and PRs, packaging/version metadata, supply-chain policy, runtime navigation/search behavior, and release documentation. Five release-review findings were fixed: Quick File reconnect convergence, tree and recent snapshot/status alignment, premature root-summary values, and stopped progress polling. Real-browser smoke passed on a 12,611-file inventory, Quick File performance stayed within bounds at 50,000 candidates, a temporary v0.3.0 tag build imported as 0.3.0, and full make verify passed on 2026-08-12 with 914 pytest cases and 30 golden scenarios plus lint, types, public hygiene, locked vulnerability audits, distributions, API check, and isolated-wheel smoke tests. Commit ded7925 is pushed in draft PR #34; all five GitHub Actions jobs (lint, distribution, Python 3.12, 3.13, and 3.14) passed, the PR is mergeable, and it has no review comments or unresolved threads. The release remains intentionally uncut pending PR merge and explicit publish authorization. Known mb-087n (timing-threshold flake reproduced at v0.2.0) and mb-pn95 (watchfiles kernel-overflow API limitation) remain deferred nonblockers.

---
type: is
id: is-01kzrtbtsh9k6p8x84rta84y4p
title: Assess and publish Metabrowser v0.3.0 minor release
kind: task
status: closed
priority: 1
version: 34
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
  - is-01kzvbhe5e49xmrq7kzjmykfjp
created_at: 2026-08-11T16:26:50.545Z
updated_at: 2026-08-12T16:28:49.947Z
closed_at: 2026-08-12T16:28:49.946Z
close_reason: Published and verified Metabrowser v0.3.0 end to end.
---
Review all user-visible changes since v0.2.0, triage outstanding defects for release blockers, validate the filtering/search stabilization release, prepare accurate v0.3.0 notes, run the complete release gate, publish the GitHub release, verify PyPI artifacts and public smoke tests, and confirm CI.

## Notes

Metabrowser v0.3.0 was published from merge commit 59eaf20dc15fc1326e8088ef4defad1e02872ed6 after the full review of the 93-commit delta since v0.2.0. PR #34 merged only after Cursor Bugbot identified a capped-inventory reconnect convergence defect; the fix added TDD coverage and the exact merge commit passed make verify with 915 pytest cases and 30 golden scenarios, plus formatting, lint, types, public hygiene, locked vulnerability audits, distribution inspection, API checks, and isolated-wheel smoke tests. Main CI run 31616943322 and publish run 31617191802 passed across Python 3.12, 3.13, and 3.14. GitHub release v0.3.0 targets the exact merge SHA and published through trusted publishing. PyPI metadata reports version 0.3.0, Python >=3.12,<4.0, AGPL-3.0-or-later, and the intended project URLs/classifiers. The wheel and sdist downloaded from PyPI matched SHA-256 digests 4139e2ff1b278e5f1392724dc986e95c7aab6f02f509c3b15361d667deb7c330 and 0da242e0dbf9f55b6a3218027a760b13142686ea84c1f19621c6e6cd8c490793. Fresh-cache public smoke tests passed for metabrowser@0.3.0, the metab entry point, and the metabrowser entry point. A clean npx skills install from jlevy/metabrowser produced the expected Metabrowser Agent Skill, and its uvx metabrowser@latest runner resolved publicly to 0.3.0. Known mb-087n and mb-pn95 remain deferred nonblocking follow-ups.

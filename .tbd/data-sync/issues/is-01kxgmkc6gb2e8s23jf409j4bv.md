---
type: is
id: is-01kxgmkc6gb2e8s23jf409j4bv
title: Prepare MetaBrowser v0.1.0 standalone package
kind: epic
status: in_progress
priority: 1
version: 42
labels:
  - release
dependencies: []
child_order_hints:
  - is-01kxgmnv21hb6wdegrj4xn8fac
  - is-01kxgmnv8fs9qcyahf2wm2s939
  - is-01kxgmnvg1heqtbjjc3bnz1pxk
  - is-01kxh3crhbe17w5ay4h4136h84
  - is-01kxh6nz7zzeerc5xgd3enrev2
  - is-01kxhn8vbqgh32vwnvv92brhkv
  - is-01kxhpk3s4ffm69y00gc20pccg
  - is-01kxhvy508zsg3zxbj2m5wptzd
  - is-01kxhw35zc74apb3vwkmn67xjs
  - is-01kxhx67bp2wc5zyqyzapnnb4c
  - is-01kxhxpvyky9jsxa3321hqsrj7
  - is-01kxhytdpkzawm7554krxgj6t5
  - is-01kxhztx5585r48tq7gja5refa
  - is-01kxj67pctmr4k4mdmvd45cnq5
  - is-01kxj67pty26s2j7bftahawv2a
  - is-01kxj6mq90b884fzynz50bjcbj
  - is-01kxj6mrvpkqnkn274rhy3mg2j
  - is-01kxj87a53xs0p7rnwecgdsfkj
  - is-01kxj9abcx9a5cp05zq9vakm8b
  - is-01kxj9pbx9h88k8m1fn1qrd1pq
  - is-01kxnvq16mbtsb3mqvbr7ch0a6
  - is-01kxnvq1ep0v3a635pawwsc8gs
  - is-01kxnvq1q524e5bh7nxjgbbf2j
  - is-01kxnvq1y0qwm9p57jcj37q09b
  - is-01kxnvq25p7jthk4c5q3y1wbg3
  - is-01kxnww26n70vegt5rxxnn2kca
  - is-01kxnww2f3ggbt0grdkf7spdt4
  - is-01kxnww2qv3mt7v5j17059bwpc
  - is-01kxrfjwe1hcx74kyp0xkdym4e
  - is-01kxrgmxr607dw8d5ygsjt2bva
  - is-01kxrhq8cs0hr2qxhc518vr5rd
created_at: 2026-07-14T15:40:47.183Z
updated_at: 2026-07-17T17:24:24.088Z
---
Create a public-safe, MIT-licensed standalone MetaBrowser package with exact KPress integration, modern Python tooling, release automation, and complete validation.

## Notes

Owner review comment 4994096399 is fully addressed in the local PR #3 working tree: public API/error contracts, uv/npm policy consistency, release checklist reconciliation, installed-wheel plugin diagnostics, and a common KPress/MetaBrowser tooling floor. The full make -j4 verify gate passes 686 tests plus Ruff, strict BasedPyright, Biome, both TypeScript projects, Flowmark, public hygiene, dependency audits, distributions, and metab plugins doctor from the installed wheel. Completed review beads are closed; CSP and measured Python/JavaScript/Biome ratchets remain explicit public follow-ups. Commit, push, published finding dispositions, and fresh GitHub Actions checks remain pending for the parent workflow.

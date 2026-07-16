---
type: is
id: is-01kxgmkc6gb2e8s23jf409j4bv
title: Prepare MetaBrowser v0.1.0 standalone package
kind: epic
status: in_progress
priority: 1
version: 30
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
created_at: 2026-07-14T15:40:47.183Z
updated_at: 2026-07-16T16:02:22.693Z
---
Create a public-safe, MIT-licensed standalone MetaBrowser package with exact KPress integration, modern Python tooling, release automation, and complete validation.

## Notes

Standalone extraction is merged. Release-readiness PR #3 is ready and mergeable at 6156c65 after the public Python sidekick API, Common Documentation Guidelines audit, and npm ambient-policy hardening. The final local gate passes 676 tests plus lint, strict types, Flowmark, public/document hygiene, dependency audits, distributions, and installed-wheel smoke tests. All five required GitHub jobs are green. Thread-aware inspection reports zero formal reviews, zero review threads, and only three non-actionable Cursor usage-limit notices. The epic remains in progress for PR #3 merge and PyPI publication under mb-xkcx.

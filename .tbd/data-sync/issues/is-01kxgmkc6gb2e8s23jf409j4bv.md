---
type: is
id: is-01kxgmkc6gb2e8s23jf409j4bv
title: Prepare MetaBrowser v0.1.0 standalone package
kind: epic
status: in_progress
priority: 1
version: 24
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
created_at: 2026-07-14T15:40:47.183Z
updated_at: 2026-07-15T06:40:50.961Z
---
Create a public-safe, MIT-licensed standalone MetaBrowser package with exact KPress integration, modern Python tooling, release automation, and complete validation.

## Notes

Standalone extraction and final PR reconciliation merged through MetaBrowser PR #1 at merge commit 5dfb02e; origin/main contains final head 42d5303. The 669-test local release gate and all latest-head GitHub checks were green, with 35/35 review threads resolved. Bounded gzip and zlib are core; .zst and other compression/archive work remain explicit non-blocking roadmap beads mb-epis, mb-min4, and mb-p7ts in TODO.md. The epic remains in progress only for PyPI publication mb-xkcx.

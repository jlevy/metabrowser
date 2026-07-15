---
type: is
id: is-01kxgmkc6gb2e8s23jf409j4bv
title: Prepare MetaBrowser v0.1.0 standalone package
kind: epic
status: in_progress
priority: 1
version: 13
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
created_at: 2026-07-14T15:40:47.183Z
updated_at: 2026-07-15T03:19:04.698Z
---
Create a public-safe, MIT-licensed standalone MetaBrowser package with exact KPress integration, modern Python tooling, release automation, and complete validation.

## Notes

Standalone PR #1 is clean and mergeable at 9226d5d with all GitHub Actions jobs passing. The core package no longer ships specialized database readers or their native dependencies. Bounded zlib artifact support remains the final core-format feature before release; publication stays blocked until that work and the PR merge are complete.

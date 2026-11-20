---
type: is
id: is-01m2hs64m7nfagfxyf7b0hxrhr
title: "[epic] Pay down the flat-tree delivery cost carried since v0.10.0"
kind: epic
status: open
priority: 1
version: 13
spec_path: docs/project/specs/active/plan-2026-09-15-flat-tree-delivery-cost.md
labels:
  - performance
dependencies: []
child_order_hints:
  - is-01m2gv1af5w404zxdq8vxedm86
  - is-01m2hrdm4kc5t3kvw1374e9tkj
  - is-01m2hrdmk40n34a85r702vwhxg
  - is-01m2hrcwzqe7r4pyd7bdfq474x
  - is-01m2hrcxgbcrrte71dn2abqyxx
  - is-01m2hrcxyxvjz4qr0bg13kzdqt
  - is-01m2h6bz9ehf0pba4zs1ehjvmw
  - is-01m1dt40nmqvb9k1dpewnyk06m
created_at: 2026-09-15T05:38:39.879Z
updated_at: 2026-11-20T17:16:51.404Z
---
v0.10.0 shipped a known regression on flat mega-trees (exp-035; the known-limitations entry in CHANGELOG.md's 0.10.0 section), and docs/project/specs/active/plan-2026-09-15-flat-tree-delivery-cost.md is the plan for paying it down. No 0.10.1 patch was released: tier 1's catalog content hash (mb-wpqq part 2) landed in #129 and shipped in 0.11.0, and the flat-stress budget check (mb-ma3x) is closed. Open: the walker emit batch, still 256 in settings.py (mb-nuhb); the 300k re-measurement the plan owes 0.11.0's evidence; and the structural tier-2 work, not building a per-entry contract object for entries the store already admitted (mb-kicj). The acceptance rows are mb-qvw4 (attached walk), mb-qtgj (catalog read) and mb-zc3p (Long Tasks). Done when the flat-shape walk under an attached browser is at parity with v0.9.1 or better over five back-to-back pairs on a quiet host, and the flat-stress ratchet is lowered to match.

## Notes

CORRECTION to the epic description: it says the tier-1 constants are "worth roughly 5%".
That added savings taken from different denominators. Measured properly:

  walker emit batch (mb-nuhb)   ~4% of the flat-shape walk it shortens
  catalog content hash (wpqq)   ~0.8% of the catalog read it shortens

There is no single combined percentage, and quoting one was the error. Neither closes a
1.65x gap; the structural work in tier 2 is what does.

Also corrected: the sort key is a TRADE, not a cliff. See mb-wpqq -- one non-ASCII file
costs 3 ms, not 41 ms; inverting the comparison needs a large share of the tree to be
non-ASCII. Decision unchanged (leave it alone), reasoning corrected.

2026-11-14 audit: no 0.10.1 was released; tier 1 shipped in 0.11.0 (plan-2026-09-15-flat-tree-delivery-cost.md:146-150). P1 untouched since 2026-09-15 with P1 children; priority left for the owner.

2026-11-20 audit: Flat-tree delivery regressions measured against v0.9.1 (walk, catalog read, tally, long tasks); every child is open.

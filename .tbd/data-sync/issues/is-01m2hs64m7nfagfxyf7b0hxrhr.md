---
type: is
id: is-01m2hs64m7nfagfxyf7b0hxrhr
title: "[epic] v0.10.1: pay down the flat-tree delivery cost"
kind: epic
status: open
priority: 1
version: 8
labels:
  - performance
  - release
dependencies: []
child_order_hints:
  - is-01m2gv1af5w404zxdq8vxedm86
  - is-01m2hrdm4kc5t3kvw1374e9tkj
  - is-01m2hrdmk40n34a85r702vwhxg
  - is-01m2hrcwzqe7r4pyd7bdfq474x
  - is-01m2hrcxgbcrrte71dn2abqyxx
  - is-01m2hrcxyxvjz4qr0bg13kzdqt
created_at: 2026-09-15T05:38:39.879Z
updated_at: 2026-09-15T05:51:25.015Z
---
v0.10.0 shipped a known regression on flat mega-trees, accepted deliberately in exp-035
and recorded in CHANGELOG.md's known-limitations entry and the load-time plan's "Debt
Carried into v0.10.0" section. This epic is the patch release that pays it down.

THE COST, AS MEASURED

A browser attached during a walk pays about 14 us per discovered entry on the delivery
path: an entry query, a contract entry, a projection, a decoration and a wire record,
plus three validations of the same path string (ChangeBatch -> EntryQuery ->
InventoryEntry). On a repository shape that buys content immediately and is worth it. At
300,000 flat entries it dominates, and there is no reader benefit to weigh against it,
because nobody reads 300,000 files.

Observed on the 300k flat corpus against v0.9.1: walk under an attached browser
1.62-1.78x, /api/catalog 663 ms -> 2,575 ms, Long Tasks of 98 ms and 75 ms where v0.9.1
had none.

WHAT IS PATCH-SAFE AND READY

  mb-wpqq part 2  catalog content hash, per-page join. Written, tested, measured at
                  62 ms -> 41 ms on 300k rows with a byte-identical digest. Held out of
                  v0.10.0 only because it touches a path exp-034's captures measured.
                  This is the first commit after the tag.
  mb-nuhb         walker emit batch 256 -> 1,024. Measured 1.2 s off an attached 300k
                  walk. Needs a browser check for first-row delay and client transient
                  heap before it is taken -- it was held back precisely because it
                  trades against the metric nearest its gate.
  mb-ma3x         make the flat-stress budget file's relationship to the release gate a
                  check rather than a sentence.

Those three together are worth roughly 5%. They are real and they are not the answer.

WHAT ACTUALLY FIXES IT

Not building a per-entry contract object for entries the store already admitted. That is
mb-kicj, and it is structural: skipping the redundant validations requires either global
mutable caches (unacceptable, particularly free-threaded) or not constructing the objects
at all. The repository's own stance, stated in the validator's comment, is "keep
validating, make it cheap." Whether that lands in 0.10.1 or a 0.11.0 depends on how the
first measurement of the object-free path comes out.

SEQUENCING

1. Land mb-wpqq part 2 immediately after the v0.10.0 tag, with its three tests.
2. Browser-check and decide mb-nuhb.
3. Add the mb-ma3x check.
4. Re-measure the 300k corpus against performance-budgets-flat-stress.toml. Lower the
   450 ms ratchet to whatever the new worst run supports. The ratchet only means
   something if it is lowered as the debt is paid.
5. Prototype the object-free delivery path and measure before designing it.

DONE WHEN

The flat-shape walk under an attached browser is at parity with v0.9.1 or better, over
five back-to-back pairs on a quiet host, and the flat-stress ratchet has been lowered to
match. Until then this epic stays open regardless of what ships.

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

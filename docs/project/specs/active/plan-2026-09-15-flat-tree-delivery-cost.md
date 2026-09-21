# Feature: Paying Down the Flat-Tree Delivery Cost

**Date:** 2026-09-15

**Author:** Metabrowser maintainers

**Status:** Draft

## Overview

v0.10.0 shipped a measured regression on one corpus shape, knowingly, and recorded it in
[exp-035](../../../../explorations/performance-loop/experiments/exp-035-scoping-the-first-row-gate-accepts-v0100.md),
in `CHANGELOG.md`’s known-limitations entry, and in the load-time plan’s
[Debt Carried into v0.10.0](plan-2026-08-21-load-time-performance.md#debt-carried-into-v0100)
section. This plan is how it gets paid down.

The release trades bulk indexing throughput for time to first content: it streams rows
to subscribers during the walk instead of completing the walk and then serving.
On a repository-shaped tree that is a large win at every size measured.
On a flat mega-tree — hundreds of files per directory — the per-entry cost dominates and
there is no reader benefit to weigh against it, because nobody reads 300,000 files.

Measured on the 300k flat corpus against v0.9.1, five back-to-back quiet-host pairs:

| What | v0.9.1 | v0.10.0 | Tracked as |
| --- | --- | --- | --- |
| Walk with a browser attached | 18.7 s | 31.3 s (1.62-1.78x) | `mb-qvw4` |
| `/api/catalog` on a settled index | 663 ms | 2,575 ms (3.9x) | `mb-qtgj` |
| Long Tasks | none | 98 ms and 75 ms in two of five runs | `mb-zc3p` |

## Goals

- Return the flat-shape walk under an attached browser to parity with v0.9.1 or better,
  measured as five back-to-back pairs on a quiet host.
- Lower the `performance-budgets-flat-stress.toml` ratchet to whatever the new behavior
  supports. A ratchet that is never lowered is just a weaker gate.
- Keep every repository-shaped gain from v0.10.0. This work may not buy flat-shape
  throughput back by giving up time to first row.

## Non-Goals

- Changing the delivery model.
  Streaming rows during the walk is the point of v0.10.0 and is not up for
  reconsideration here.
- Optimizing for corpora nobody has.
  The 300k flat corpus is a measuring instrument that isolates per-entry cost, not a
  target shape. It earns work because it isolates a cost that is also paid, in smaller
  absolute terms, on real trees.

## Background: where the 14 µs goes

A browser attached during a walk pays, per discovered entry: an entry query, a contract
entry, a projection, a decoration, a wire record, and a catalog upsert — plus three
validations of the same path string, at `ChangeBatch.__post_init__`, `EntryQuery` and
`InventoryEntry`.

Two measurements bound the problem from opposite ends.
Bare filesystem traversal of the corpus is 0.87 s warm against a 12.9-15.5 s detached
walk, so roughly 93% of the walk is Python above the filesystem.
And the delivery decomposition sums to 13.86 µs per entry, matching the ~14 µs observed.
This is not a syscall problem and it is not a mystery.

## Design

Three tiers, in the order their evidence supports.

### Tier 1: measured constants, patch-safe

Worth about 5% between them.
Real, small, and not the answer — stated plainly so nobody mistakes this tier for the
fix.

- **Catalog content hash, per-page join** (`mb-wpqq`). 62 ms → 41 ms at 300,000 rows,
  byte-identical digest, three tests.
  Written and tested during the v0.10.0 round and held back only because it touches a
  path exp-034’s captures measured.
  Lands first.
- **Walker emit batch 256 → 1,024** (`mb-nuhb`). 1.2 s off an attached 300k walk; 1,024
  is the contract ceiling, since `MAX_CHANGE_PATHS` is 1,024 and above it a change
  becomes `all_dirty` and forces a resync.
  Not taken yet: a larger batch delays the first emit, and `first_row_ms` on the flat
  corpus is the metric nearest its gate.
  Needs a browser check for first-row delay and client transient heap before it is
  taken.

Two candidates were measured and **rejected**, recorded so they are not proposed again:

- The catalog sort key’s per-row UTF-8 encode.
  Removing it is 34 ms faster on all-ASCII trees and 41 ms slower once one non-ASCII
  name takes CPython’s latin1 compare away from the whole sort — a cliff triggered by a
  single file.
- The `f"change-{index}"` query label.
  0.034 s over 300,000 entries, against a debugging-visible label change.

### Tier 2: stop paying for objects the store already admitted

This is the fix.
The entry query, contract entry and projection exist to carry a path the
provider just produced and already validated.
Skipping the redundant validations is not available on its own: it needs either global
mutable caches, which are unacceptable and especially so free-threaded, or not
constructing the objects at all.
The repository’s own stance, in the validator’s comment, is “keep validating, make it
cheap” — so the target is the construction, not the validation.

Measure before designing.
The first deliverable in this tier is a prototype of the object-free path priced against
the current one on the same corpus, not a design document.

### Tier 3: a non-Python provider

The `fdu` spike already measured client-side duplication on one eight-query read: 8,830
entries materialized, 412,836 path bytes, 470 child-bucket rebuilds, four full-result
sorts, four aggregate passes, ~852 ms and ~13 MB of Python allocation.
That is the ceiling on what tier 2 can win while the consumer side stays as it is.
Out of scope for a patch release; in scope for deciding whether tier 2 is worth its
complexity.

## Implementation Plan

1. Land the catalog content hash immediately after the v0.10.0 tag, with its three
   tests.
2. Browser-check the emit batch for first-row delay and transient heap; take it or
   reject it on that evidence, with the measurement recorded beside the constant.
3. Add the check that keeps `performance-budgets-flat-stress.toml` from drifting off the
   release gate (`mb-ma3x`).
4. Re-measure the 300k corpus, five back-to-back pairs, and lower the ratchet.
5. Prototype the object-free delivery path and price it before designing it.

## Testing Strategy

Counts before times, per the engine performance model.
A change that claims to remove per-entry work is pinned by a test that counts the work,
not one that times it — the wiki-resolver memo work-session test is the pattern to
follow.

Every claim in tiers 1 and 2 needs a deterministic test that fails on the old code, by
scratch copy or `PYTHONPATH` shadowing, before its number is believed.

## Rollout Plan

Tier 1 is patch-safe.
It was planned for 0.10.1 and in the event shipped in 0.11.0: the catalog content hash
landed in #129 and rode out with the content-trust work rather than on a patch of its
own. Tier 2 changes no contract but is large enough that it ships on its own measured
round, as 0.12.0 or later depending on what the prototype costs.
The flat-stress ratchet is lowered in the same change that earns it, never separately.

Shipping tier 1 inside a feature release carries a cost this plan should name.
`_catalog_content_identity` is on the path exp-034’s captures measured, and exp-035 set
the standard that a change touching a measured path “would need the captures taken
again”. The 300k re-measurement in step 4 above is therefore owed to 0.11.0’s evidence,
not only to the tier-1 work, and it remains outstanding.
[exp-036](../../../../explorations/performance-loop/experiments/exp-036-backend-only-partial-does-not-clear-v0110.md)
is the record of shipping without it: a backend-only comparison that found the candidate
equivalent and explicitly did not clear the release.

## Open Questions

- Does the emit batch’s first-row delay actually show up in a browser, or is the first
  row served from the initial `/api/tree` request before any batch lands?
  The 47 ms of additional fill time at 1,024 is arithmetic, not a measurement.
- Is the Long Task growth (`mb-zc3p`) the same delivery work surfacing as one long
  callback, or something separate?
  Assumed, not established.
- What does the object-free path cost in readability, and is that trade better than tier
  3?

## References

- [exp-034](../../../../explorations/performance-loop/experiments/exp-034-v0100-quiet-machine-rejects-the-candidate-on-300k.md)
  — the measurements
- [exp-035](../../../../explorations/performance-loop/experiments/exp-035-scoping-the-first-row-gate-accepts-v0100.md)
  — the disposition
- [Engine performance model](../../../engine-performance-model.md)
- [Load-time performance plan](plan-2026-08-21-load-time-performance.md)

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->

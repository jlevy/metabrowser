---
title: The walker builds each entry once instead of three times
softschema:
  contract: metabrowser.loadtime:Experiment/v1
  schema: experiment.schema.yaml
  envelope: experiment
  status: enforced
experiment:
  id: exp-022
  title: The walker builds each entry once instead of three times
  date: "2026-09-01"
  hypotheses: [H65, H66, H67]
  subject:
    corpus: build_corpus synthetic shape 2
    corpus_files: 60000
    host_system: Darwin 25.5.0
    browser: none; backend scan only
    cold: true
  method:
    runs_per_condition: 5
    interleaved: false
    control: the branch before this round, at fef9f6c6
    candidate: the same tree with H65 and H67 applied
    record: explorations/performance-loop/scan_bench.py inproc --files 60000 --runs 5
  results:
    - metric: walk_to_settled_ms_H65
      control_median: 1847.0
      candidate_median: 1652.6
      control_range: [1811.8, 2047.9]
      candidate_range: [1622.7, 1687.1]
      change_pct: -10.5
      overlapping: false
    - metric: walk_to_settled_ms_H66
      control_median: 1652.6
      candidate_median: 1645.4
      control_range: [1622.7, 1687.1]
      candidate_range: [1614.1, 1752.9]
      change_pct: -0.4
      overlapping: true
    - metric: walk_to_settled_ms_H67
      control_median: 1645.4
      candidate_median: 1277.4
      control_range: [1614.1, 1752.9]
      candidate_range: [1233.1, 1502.7]
      change_pct: -22.4
      overlapping: false
  complexity:
    lines_changed: 190
    new_dependencies: []
    new_failure_modes:
      - >-
        `with_write_token` and `with_empty` list every `FsEntry` field
        positionally, so a field added later is silently dropped from the copy.
        `test_fsentry_fast_copies_match_dataclasses_replace` compares them
        against the reflective `dataclasses.replace`, and was verified to fail
        when a field is removed from one of them.
    notes: >-
      The fast path duplicates the tail of `_store_walker_entry` for the
      add case. It is the walker's whole path, so the duplication buys the
      round's largest single win, but it is duplication and a change to either
      copy has to be made in both.
  verdict:
    decision: accepted
    primary_metric: walk_to_settled_ms
    reason: >-
      H65 and H67 each moved the median on disjoint ranges, together 1,847 ms to
      1,277 ms. H66 as first written did not: netting the aggregate deltas per
      parent and climbing the ancestor chain once was 1,645 ms against 1,653 on
      overlapping ranges, because the dict and closure it allocated per entry
      cost what the saved traversals returned. H67 is that same idea with the
      allocation removed from the path that never needs it.
    commit: d765421a
---
# exp-022: The walker builds each entry once instead of three times

## Why

The inventory-provider refactor was measured for behaviour and never for speed.
A full scan of a 60,000-file corpus ran 2.75x slower than `main`; two fixes recorded in
`mb-0y68` closed most of that, and left 28%.

The profile behind the residual pointed at `dataclasses.replace` — 64,420 calls and
1.28M `getattr` — and at the per-entry construction around it.

## What was built

**H65.** `dataclasses.replace` reads all twenty `FsEntry` fields back through
string-keyed `getattr` and then runs the generated `__init__` over them.
The walker calls it once per entry to stamp a write token.
`with_write_token` and `with_empty` build the copy positionally instead: the same
`__init__`, reached without the reflection.
3.5 us to 1.3 us in isolation.

Safe because `FsEntry` has no `__post_init__`, so nothing is being skipped except the
lookup of what to copy.

**H66.** Leaf, file, and tracked-file aggregates hang off the same ancestor chain, and
the ordinary walker event moves all three by the same parent, so adjusting them
separately climbed that chain three times — 180,000 climbs, splitting every path
component on the way up.
The change netted the deltas per parent and climbed once.

**H67.** The add path — no existing entry, which is every entry of a first walk — has
exactly one parent, so it skips the delta map entirely and calls the combined climb
directly.

## What the prediction got wrong

H66 was right about the redundant climbs and wrong about where the time was.
Merging three ancestor walks into one measured as nothing: 1,645 ms against 1,653 with
ranges overlapping. The traversals it saved were paid back by the `dict` and the closure
it allocated per entry to net the deltas in.

That is the whole reason H67 exists, and why it is 368 ms rather than the handful H66
returned. The lesson is narrow and reusable: on a path that runs once per entry, an
allocation costs about what four dictionary updates and four `rsplit` calls cost, so a
refactor that trades traversal for bookkeeping is not obviously a win at this scale.

Removing the map from the add path also made the general path’s `existing is None`
branches unreachable, which basedpyright caught.

## Limits

Measured in process, so the number excludes interpreter startup and HTTP. That is
deliberate — it is the instrument that can see a per-entry change — but it means these
figures are not what a user waits for.
The build-to-build comparison against `main` is exp-023.

One corpus, one shape, one host.
Synthetic shape 2 is shallow, roughly four components deep, which is exactly the regime
where H66’s traversal saving was small enough to be cancelled.
On a deep tree the ranking of H66 and H67 could differ.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->

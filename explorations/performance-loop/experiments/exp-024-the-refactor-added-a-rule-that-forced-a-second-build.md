---
title: The refactor added a rule that forced a second build of every entry
softschema:
  contract: metabrowser.loadtime:Experiment/v1
  schema: experiment.schema.yaml
  envelope: experiment
  status: enforced
experiment:
  id: exp-024
  title: The refactor added a rule that forced a second build of every entry
  date: "2026-09-03"
  hypotheses: [H72]
  subject:
    corpus: build_corpus synthetic shape 2
    corpus_files: 60000
    corpus_dirs: 1105
    host_system: Darwin 25.5.0
    browser: none; backend scan only
    cold: false
  method:
    runs_per_condition: 3
    interleaved: true
    control: main at 26b109eb, driven through its own InventoryIndex.start
    candidate: the stack with the walker building the retained record directly
    record: >-
      deterministic operation counts from a monkeypatched in-process walk, plus
      interleaved wall-clock on the identical corpus; the host carried a load
      average above 20 throughout, so the counts are the result and the times
      are corroboration
  results:
    - metric: inventory_entry_constructions_per_entry
      control_median: 0.0
      candidate_median: 0.0
      control_range: [0.0, 0.0]
      candidate_range: [0.0, 0.0]
      change_pct: 0.0
      overlapping: false
    - metric: require_canonical_inventory_path_calls_per_entry
      control_median: 0.0
      candidate_median: 2.04
      control_range: [2.04, 2.04]
      candidate_range: [2.04, 2.04]
      change_pct: 0.0
      overlapping: false
    - metric: walk_to_settled_ms
      control_median: 3970.0
      candidate_median: 4104.0
      control_range: [3768.0, 3975.0]
      candidate_range: [3962.0, 4176.0]
      change_pct: 3.4
      overlapping: true
  complexity:
    lines_changed: 95
    new_dependencies: []
    new_failure_modes:
      - >-
        `FsEntry` and `WriteToken` move to `metabrowser.fs_record`, and
        `metabrowser.events` re-exports them. An importer reaching for the
        record through `events` still works, so nothing forces the honest
        import; the module docstring states which one is which.
    notes: >-
      The remaining 2.04 validations per entry are the change pipeline's, not
      the walker's, and are recorded as their own item rather than fixed here.
  verdict:
    decision: accepted
    primary_metric: require_canonical_inventory_path_calls_per_entry
    reason: >-
      Entry construction and validation counts now match `main` exactly:
      125,525 `FsEntry` builds for 61,105 entries in both, and zero
      `InventoryEntry` builds where the stack previously did 62,210. The
      modelled saving, 6.25 us per entry, predicted a 382 ms improvement on
      this corpus; the interleaved medians moved 429 ms.
    commit: pending
---
# exp-024: The refactor added a rule that forced a second build of every entry

## Why

The stack was reported as 16% slower than `main` on a real tree.
That number does not survive inspection — the run behind it shared the host with an
`ffmpeg` at 636% CPU and another agent writing into the tree being walked, and the
harness that produced it could not tell a completed walk from one that hit its 60-second
index timeout partway through.
Both builds, re-run serially, timed out at about 178,000 of 299,810 entries.

So the question was reopened with an instrument that does not care about load: count the
operations. A count is the same under any amount of contention, and two builds walking
the same corpus should do the same work.

## What the counts said

The same 61,105-entry corpus, in process, per entry:

|  | `main` | the stack |
| --- | --- | --- |
| `os.scandir` | 2,210 | 2,210 |
| `os.lstat` | 1,111 | 1,139 |
| `FsEntry.__init__` | 125,525 | 125,525 |
| `InventoryEntry.__init__` | 0 | 62,210 |
| `_internal_entry` | 0 | 62,210 |
| `require_canonical_inventory_path` | 0 | 248,826 |

The filesystem work is identical.
Every difference is Python, on the per-entry path, and attributing the validator calls
to their callers splits them cleanly in half:

| caller | calls | per entry |
| --- | --- | --- |
| `InventoryEntry.for_observed_file` | 120,000 | 1.96 |
| `_record_provider_change` | 62,203 | 1.02 |
| `coordinator._merge_provider_batches` | 62,203 | 1.02 |
| `for_observed_dir`, `dataclasses._replace` | 4,420 | 0.08 |

Priced in isolation: a validation is 1.05 us, an `InventoryEntry` build 4.28 us, and
`_internal_entry` 1.85 us.
That models 8.7 us of overhead per entry, or 531 ms on this corpus against a measured
429 ms.

## The cause was a rule, not a design

`main`’s walker yields `FsEntry` — the record the inventory retains — and builds it
once.
The stack’s walker yields the contract’s `InventoryEntry`, which validates its path
and its parent on construction, and the provider then converts it to `FsEntry` anyway.

The reason it does that is `test_scanner_and_reducer_do_not_depend_on_browser_events`,
added by this stack, which forbids `walker.py` from importing `metabrowser.events`. That
rule is right about the dependency and wrong about the remedy available: `FsEntry` lives
in `events.py` for historical reasons, not because it is an event, and routing the
scanner through a validated contract type to avoid naming it cost a second construction
and two validations on the one path that runs once per file in the tree.

So the record moved to `metabrowser.fs_record`, which is neither the scanner nor the
browser layer, and `events.py` re-exports it.
The test still passes, and means what it says.
The walker builds each entry once, as it did before the refactor.

## What is left

`require_canonical_inventory_path` falls from 248,826 to 124,406. The remainder is the
change pipeline: `_record_provider_change` and `coordinator._merge_provider_batches`
each construct a validated contract object for every entry discovered, to publish
invalidations for entries no reader has seen.
`main` has no such pipeline during its boot walk.
That is about 2.1 us per entry and is the next item, recorded as its own bead rather
than folded in here, because skipping publication during discovery is a decision about
the change contract and not a local optimization.

The rule this round generalizes to is
[the engine performance model](../../../docs/engine-performance-model.md), and the
numbers it produced are kept in
[Python inventory cost](../../../docs/project/architecture/arch-python-inventory-cost.md).

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->

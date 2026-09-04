---
title: The instrument was measuring the order it ran in
softschema:
  contract: metabrowser.loadtime:Experiment/v1
  schema: experiment.schema.yaml
  envelope: experiment
  status: enforced
experiment:
  id: exp-023
  title: The instrument was measuring the order it ran in
  date: "2026-09-01"
  hypotheses: [H68, H69, H70, H71]
  subject:
    corpus: build_corpus synthetic shape 2
    corpus_files: 60000
    host_system: Darwin 25.5.0
    browser: none; backend scan only
    cold: true
  method:
    runs_per_condition: 9
    interleaved: true
    control: installed main build, metab 0.8.1.dev65+838459e
    candidate: this branch after exp-022, plus H71
    record: explorations/performance-loop/scan_bench.py binary --files 60000 --runs 9
  results:
    - metric: walk_to_settled_ms_H68_ancestor_memo
      control_median: 1203.1
      candidate_median: 1247.4
      control_range: [1181.0, 1387.2]
      candidate_range: [1233.8, 1298.1]
      change_pct: 3.7
      overlapping: true
    - metric: walk_to_settled_ms_H71
      control_median: 1203.1
      candidate_median: 1218.9
      control_range: [1181.0, 1387.2]
      candidate_range: [1099.3, 1565.9]
      change_pct: 1.3
      overlapping: true
    - metric: full_scan_ms_vs_main_sequential
      control_median: 1672.7
      candidate_median: 2000.2
      control_range: [1636.0, 1812.3]
      candidate_range: [1862.4, 2377.6]
      change_pct: 19.6
      overlapping: false
    - metric: full_scan_ms_vs_main_interleaved
      control_median: 1705.0
      candidate_median: 1844.9
      control_range: [1662.7, 1961.6]
      candidate_range: [1843.0, 2504.8]
      change_pct: 8.2
      overlapping: true
  complexity:
    lines_changed: 40
    new_dependencies: []
    new_failure_modes: []
    notes: >-
      H68 and H70 were reverted. H69 was refused before implementation on its
      microbenchmark. H71 is kept: it is measurable in isolation, not at walk
      scale, and one half of it removes a function-level import rather than
      adding anything.
  verdict:
    decision: rejected
    primary_metric: walk_to_settled_ms
    reason: >-
      Three of four hypotheses produced no detectable effect, and the fourth was
      refused on its microbenchmark. The round's actual result is about the
      instrument: running every trial of one build and then every trial of the
      other put all drift on whichever went second, which was always the
      candidate, and reported the gap against main as 19.6% on disjoint ranges.
      Interleaving the same comparison reports 8.2% on overlapping ranges. The
      earlier figure was partly an artifact of ordering.
    commit: d765421a
---
# exp-023: The instrument was measuring the order it ran in

## Why

exp-022 left the scan 1,203 ms in process and the gap against `main` unclosed.
Four more hypotheses came off the profile.

## What happened to each

**H68 — memoize the ancestor chain per parent.** Every file in a directory climbs the
same chain, so a 60,000-file tree re-derives a few thousand distinct chains once per
file. Caching them removes roughly 240,000 `rsplit` calls.

Rejected: 1,247 ms against 1,203, ranges overlapping, nominally *slower*. Shape 2 is
about four components deep, so a chain is four short strings; `str.rsplit` is C-speed
and a dict lookup plus tuple iteration costs about the same.
Reverted.

**H69 — allocation-free validation.** `require_canonical_inventory_path` runs 248,826
times per walk, half from `InventoryEntry.__post_init__` and half from
`ChangeBatch.__post_init__` validating dirty paths, and its `split("/")` allocates a
list per call. Substring scans decide the same thing without allocating.

Refused before implementation.
The microbenchmark says 1.05x on a deep path and 0.72x — slower — on a short one,
because a short path costs less to split than it costs to scan six times.
A mixed corpus is a wash.

The 124,406 calls from `ChangeBatch` are the coordinator validating every dirty path a
provider hands it. That guard is the boundary doing its job and is not a candidate for
removal.

**H70 — fast-path `derive_ext`.** It runs `replace("\\", "/")` and `rsplit("/")` on what
the walker passes as a bare filename, allocating twice before it starts.
Rejected on its microbenchmark: 1.11x, about 3 ms over 60,000 calls.

**H71 — hoist an import, construct positionally.** `for_observed_file` imported
`derive_ext` inside the function on every call, and `_internal_entry` bound twenty
keywords.
Together 34 ms in isolation, and no detectable effect at walk scale, exactly as
that number predicts against a ±50 ms spread.
Kept anyway: one half deletes a function-level import and the other matches the
positional construction exp-022 already introduced.

## What the round actually found

The profile had been overstating small functions badly.
`derive_ext` shows 3 us per call under cProfile and measures 0.575 us without it — the
per-call instrumentation is comparable to the work being instrumented at this call
count. Every remaining target on that profile was chosen partly on inflated numbers.

Worse, the build-to-build harness ran every trial of one binary and then every trial of
the other. Anything drifting over the measurement — another process starting, thermal
state, cache warmth — lands entirely on whichever went second, and the candidate always
did. That comparison reported the gap against `main` as 19.6% on disjoint ranges.

The same comparison, interleaved one run of each per pass, reports 8.2% on overlapping
ranges. `scan_bench.py` interleaves now.

## Where this leaves the gap

By median with overlapping ranges, there is no separable difference from `main` at n=5
or n=9. By minimum, which is the estimator noise cannot flatter because noise only adds
time, `main` is 1,662.7 ms and the candidate 1,843.0 — about 11%.

That is consistent with the pre-interleaving reading and is the honest figure.
It is also below what this host can resolve by median: candidate samples in the n=9 pass
reached 3,642 ms.

Further micro-optimization is not measurable here.
What remains is structural and is already tracked as `mb-kicj`: every entry is built as
a contract `InventoryEntry`, converted to `FsEntry`, and converted back on read.
Removing one of those constructions is worth about 190 ms by microbenchmark, which is
large enough to see, and it is a contract change rather than a local one.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->

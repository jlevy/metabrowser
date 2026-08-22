---
title: The gitignore pre-walk stops traversing what it cannot use
softschema:
  contract: metabrowser.loadtime:Experiment/v1
  schema: experiment.schema.yaml
  envelope: experiment
  status: enforced
experiment:
  id: exp-006
  title: The gitignore pre-walk stops traversing what it cannot use
  date: "2026-08-22"
  hypotheses:
    - H30
  subject:
    corpus: build_realistic_corpus at 150,000 files (36,552 directories, 104 nested .gitignore files), with two real working trees as sanity checks
    corpus_files: 150000
    corpus_dirs: 36552
    host_system: Darwin 25.5.0
    browser: n/a
    viewport: "n/a"
    cold: false
  method:
    runs_per_condition: 3
    interleaved: true
    control: load_gitignore walks the whole tree looking for nested .gitignore files
    candidate: the same walk, pruning ignored subtrees and hidden directories as patterns accumulate
    record: explorations/results/runs.jsonl
  results:
    - metric: gitignore_build_ms
      control_median: 1650
      candidate_median: 1250
      control_range: [1620, 3020]
      candidate_range: [1190, 1900]
      change_pct: -24.2
      overlapping: true
    - metric: gitignore_build_ms_real_tree_a
      control_median: 21370
      candidate_median: 2540
      control_range: [19740, 21590]
      candidate_range: [2530, 5750]
      change_pct: -88.1
      overlapping: false
    - metric: gitignore_build_ms_real_tree_b
      control_median: 750
      candidate_median: 0
      control_range: [740, 2320]
      candidate_range: [0, 10]
      change_pct: -100.0
      overlapping: false
    - metric: ignore_patterns_compiled
      control_median: 10668
      candidate_median: 327
      control_range: [10668, 10668]
      candidate_range: [327, 327]
      change_pct: -96.9
      overlapping: false
  complexity:
    lines_changed: 48
    new_dependencies: []
    new_failure_modes:
      - "A nested .gitignore inside an ignored or hidden directory is no longer read. That is what git does -- an ignored directory is excluded wholesale -- and the verdict for every visible path was compared against the unpruned filter on all three trees to confirm it."
    notes: One loop in load_gitignore. The accumulated spec is recompiled once per .gitignore found, not once per directory.
  verdict:
    decision: accepted
    primary_metric: gitignore_build_ms_real_tree_a
    reason: "21.4 s to 2.5 s on the real tree that motivated the hypothesis, and 0.75 s to effectively zero on the second, both on non-overlapping ranges. The reproducible corpus agrees in direction at 1.65 s to 1.25 s, with overlapping ranges because it is a fifth the size. Verified to change no answer: every visible path -- 341,872 of them on the largest tree -- gets the same verdict as the unpruned filter."
---
# The gitignore pre-walk stops traversing what it cannot use

## Hypothesis

**H30**, from exp-005: `build_gitignore_check` costs 19.4–23.3 s on a real 241,000-file
working tree, before the indexing walk starts and therefore before any row can exist.
It is larger than the 21 s walk it precedes.

The mechanism was in the code rather than in a measurement.
`load_gitignore` does a **full `os.walk` of the entire tree** to find nested
`.gitignore` files. So the tree is traversed twice — once to collect ignore patterns,
once to index — and the first pass prunes nothing.
It descends into every vendored, built, cached, and hidden directory looking for files
that cannot change any answer.

## What was tried

Two prunes in that loop, and both are semantics rather than shortcuts.

**A directory already ignored by accumulated patterns is not entered.** Git does not
read `.gitignore` files inside an ignored directory either — its contents are excluded
wholesale, so a nested pattern there could not change a verdict.
Patterns are hierarchical and `os.walk` is top-down, so everything governing a directory
has been collected before it is reached.

**A hidden directory is not entered.** A pattern found inside one could only govern
paths that are themselves never shown: `fs_paths.is_visible` already excludes them from
the indexing walk, so collecting ignore rules for them is work spent on rows nobody can
see.

The accumulated spec is recompiled once per `.gitignore` found — about a hundred times
on this corpus and five hundred on the real tree — rather than once per directory.

## What the numbers said

Interleaved, three repeats each, with the cache cleared between.

| tree | control | candidate |
| --- | ---: | ---: |
| **real tree A** (241,063 files, 222,819 dirs walked, 527 nested `.gitignore`) | 21.37 s (19.74–21.59) | **2.54 s (2.53–5.75)** |
| **real tree B** (320,064 files, 16,944 dirs, 88 nested `.gitignore`) | 0.75 s (0.74–2.32) | **0.00 s (0.00–0.01)** |
| reproducible corpus (150,000 files, 36,552 dirs, 104 nested `.gitignore`) | 1.65 s (1.62–3.02) | 1.25 s (1.19–1.90) |

The corpus agrees in direction and its ranges overlap, which is what a fifth the
directory count buys.
The real trees are where the effect is unambiguous, and tree A is the one the hypothesis
came from: **twenty seconds of dead time before the first row, gone.**

Patterns compiled fall with it, because the specs inside pruned subtrees are never read:
10,668 → 327 on tree A, 2,022 → 36 on tree B. That is a second-order win — every
per-entry ignore check during the indexing walk now matches against a smaller spec.

## Correctness, which mattered more than the speed

Changing what gets read changes what gets ignored, unless it does not.
Verified directly rather than argued: for every visible path in each tree, compare the
verdict from the pruned filter against the verdict from the unpruned one.

| tree | visible paths checked | verdicts that differ |
| --- | ---: | ---: |
| reproducible corpus | 158,750 | **0** |
| real tree B | 19,151 | **0** |
| real tree A | 341,872 | **0** |

## The corpus was wrong twice, and the second time was instructive

The first version of the reproducible corpus said this change was a **42% regression**
(1.73 s → 2.46 s) while both real trees said it was a large win.
The corpus was not wrong about files per directory or depth — it matched — but about the
*structure of what is ignored*. It scattered the ignored fraction across hundreds of
small directories.

Real trees do the opposite, and it is not close: one keeps **232,190 files under two
`target` directories**, the other **191,072 under seventeen `.venv` directories**.
Pruning one directory there skips a hundred thousand files.
Pruning one of my scattered directories skipped forty, while the matching cost was paid
on all 36,552.

The generator now plants a few enormous ignored subtrees instead of many small ones, and
the corpus agrees with the real trees.
The lesson generalizes past this round: a corpus can match every summary statistic and
still be wrong about the thing under test, and only a real tree finds that out.

## Limitations

The reproducible corpus is a fifth of the real tree’s directory count, so its effect
size is small enough that its ranges overlap; it is a regression check, not the
evidence. Three repeats each.
The real trees are not fixed fixtures — they are working directories that change — so
their numbers are a sanity check on direction and magnitude, not a baseline anything
later can be diffed against.

`gitignore_build_ms` is measured directly rather than through the browser, because it
happens before the server can answer anything.

## Verdict

**ACCEPTED.** 21.4 s → 2.5 s on the tree that motivated it, no verdict changed on
341,872 paths, and a 97% reduction in compiled patterns that every later ignore check
benefits from.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->

---
title: A real tree changes the priorities
softschema:
  contract: metabrowser.loadtime:Experiment/v1
  schema: experiment.schema.yaml
  envelope: experiment
  status: enforced
experiment:
  id: exp-005
  title: A real tree changes the priorities
  date: "2026-08-22"
  hypotheses:
    - H16
  subject:
    corpus: a real working tree, tree-a01f4187 (241,063 files, ~100,800 directories, 23 GB)
    corpus_files: 241063
    corpus_dirs: 100800
    host_system: Darwin 25.5.0
    browser: Chromium
    viewport: "1280x900"
    cold: true
  method:
    runs_per_condition: 1
    interleaved: false
    control: the same walk with nothing attached
    candidate: the same walk with one client polling /api/tree?depth=1 every 2 s
    record: explorations/results/runs.jsonl
  results:
    - metric: walk_elapsed_ms
      control_median: 21020
      candidate_median: 258268
      control_range: [21020, 21020]
      candidate_range: [258268, 258268]
      change_pct: 1128.6
      overlapping: false
    - metric: srv_scanning_ms
      control_median: 6
      candidate_median: 746
      control_range: [6, 6]
      candidate_range: [1, 1524]
      change_pct: 12333.0
      overlapping: false
  complexity:
    lines_changed: 0
    new_dependencies: []
    new_failure_modes: []
    notes: A characterization round. No production code changed; the harness gained `serve --tree` and `count`.
  verdict:
    decision: baseline
    primary_metric: walk_elapsed_ms
    reason: "Characterization, not a change. Three findings reorder the plan: watching a scan makes it 12x slower (21.0 s unattached against 258.3 s with one polling client, both warm), building the gitignore checks costs 19-23 s before any row can exist, and exp-004's inline does not fire on a first open because the index is empty when the page renders. The synthetic corpus was unrepresentative in the dimension that turned out to matter: 309 files per directory against 2.4."
---
# A real tree changes the priorities

## Why

Every browser number in this loop came from `build_corpus`: a root with thirteen
children, 309 files per directory, every file gitignored by the repository above it.
H16 said that was a validity risk.
This round replaces the guess with a tree someone actually uses — 241,063 files across
about 100,800 directories, 23 GB, 76 root entries — and it does not confirm the
priorities. It reorders them.

## The shape was wrong in the dimension that mattered

|  | `build_corpus` 300k | real tree |
| --- | ---: | ---: |
| files | 300,000 | 241,063 |
| directories | 972 | ~100,800 |
| **files per directory** | **309** | **2.4** |
| root entries | 13 | 76 |

Every per-directory cost in the walker was amortized across 309 files in the synthetic
corpus and is paid every 2.4 files here.
That is a 128× difference in how often the per-directory path runs, and no measurement
before this round could see it.

## Finding 1: watching the scan makes it twelve times slower

|  | walk elapsed |
| --- | ---: |
| nothing attached | **21.0 s** |
| one client polling `/api/tree?depth=1` every 2 s | **258.3 s** |

Both on a warm page cache, so this is contention and not disk.
The first measurement of this tree took 317.8 s on a cold cache with the same polling;
re-running warm removed the confound and left the amplification.

The mechanism is a feedback loop, and each part of it is already measured.
A nav request during a scan costs a tally pass.
On this tree that pass costs 0.75 s at 120,000 files indexed and 1.5 s at 241,000 — it
grows with the index, because it visits every entry:

| indexed | `/api/tree?depth=1` wall |
| ---: | ---: |
| 119,915 | 0.75 s |
| 146,852 | 0.91 s |
| 198,933 | 1.47 s |
| 241,063 (done) | 1.51 s |

That work competes with the walker for the GIL, so the walk slows down, so the scan
window lasts longer, so more polls land inside it, each more expensive than the last.
**One polling client is a lighter load than a real browser**, which polls progress every
second and refetches the tree on top of that.

This is the systemic reading of a number exp-003 already had.
That round bounded the repeat cost and called the remainder “the last second on the
critical path.” On this tree the remainder is the input to a loop that costs four
minutes.

## Finding 2: nothing can happen for the first twenty seconds

`build_gitignore_check` takes **19.4–23.3 s** on this tree, measured three times, before
the walk starts and therefore before any row can exist.
It is larger than the walk it precedes.

```
gitignore build   23.31 s   (before any row can exist)
walk              21.02 s   241,084 files / 201,604 dir yields
total             44.33 s
```

Nothing in the plan accounted for this.
It is not a scan cost, not a request cost, and not visible in any browser metric — the
page loads fine, it simply has nothing to show.

## Finding 3: exp-004’s inline does not fire on a first open

The probe recorded `inline_rows: null`. The shell inlines the root’s rows only when
`inventory_has_data()`, and on a first open of this tree the index is still empty at
page-render time — it is behind the twenty-second gitignore build.
So the change that took first row from 1,604 ms to 242 ms on the synthetic corpus does
nothing on the first open of a real one, which is exactly the case it was for.

It still helps every later load against a warm index, which is not nothing.
But the headline result of exp-004 is now known to be conditional in a way the artifact
did not say, and its own limitation section did not anticipate.

## What the reader actually got

First open, page rendered 32,196 files into the scan: `first_row_ms` 527 ms, 315 rows,
`load_tree_ms` 27 ms.
The page is *fast* — because the index was nearly empty, so there was almost nothing to
send. The tree then fills in over the next four minutes, and every interaction during
that window costs the better part of a second.

“Far from instant” is not first paint on this tree.
It is the four minutes afterward.

## Limitations

One tree, one machine, n=1 per condition — enough for a 12× effect and not enough for
anything subtle here.
The clean-walk figure comes from driving `walk_tree` directly rather than through the
server, so it excludes `_store_walker_entry` and the event emission the real walker also
does; it is a floor for the walk, not a full accounting.
Directory counts differ between measurement methods because the walker yields a
directory twice (placeholder, then finalized) and counts gitignored entries the
filesystem walk in `run.py count` skips.

## What this reorders

- **H27** (rows respond without the tally pass) moves to the front.
  It was ranked as the last second on the critical path; it is the input to a loop that
  costs four minutes.
- **H30** (the gitignore build) is new and is the largest single fixed cost measured
  anywhere in this plan.
- **H31** (the contention loop) is new and is the framing that explains why server-side
  cost matters more than its own duration suggests.
- **H32** (inline without a warm index) is new: exp-004’s win is conditional on state a
  first open does not have.
- **H21** (persist the index) gains: a 44 s cold open that a reader repeats every
  session is the case persistence exists for.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->

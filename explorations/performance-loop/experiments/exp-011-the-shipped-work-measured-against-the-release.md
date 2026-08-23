---
title: The shipped work, measured against the release
softschema:
  contract: metabrowser.loadtime:Experiment/v1
  schema: experiment.schema.yaml
  envelope: experiment
  status: enforced
experiment:
  id: exp-011
  title: The shipped work, measured against the release
  date: "2026-08-23"
  hypotheses:
    - H27
    - H30
    - H31
  subject:
    corpus: three shapes, counted by the harness walking them -- build_project_corpus at 10 projects (247,153 files, 31,201 directories, 251 nested .gitignore files), build_realistic_corpus (119,609 files, 30,080 directories, 83 nested .gitignore files, most of the tree under ignored subtrees), and build_corpus (120,001 files, 1,104 directories, no ignore files)
    corpus_files: 247153
    corpus_dirs: 31201
    host_system: Darwin 25.5.0
    browser: n/a
    viewport: "n/a"
    cold: false
  method:
    runs_per_condition: 5
    interleaved: true
    control: metab 0.6.0, installed from PyPI
    candidate: metab 0.6.1.dev41+66330af, main built to a wheel and installed into its own venv so both sides are console scripts
    record: devtools/compare_builds.py, with the medians reproduced in this document
  results:
    - metric: index_done_ms_project
      control_median: 29989
      candidate_median: 11928
      control_range: [25681, 34727]
      candidate_range: [11290, 12919]
      change_pct: -60.2
      overlapping: false
    - metric: index_done_ms_deep_and_narrow
      control_median: 33755
      candidate_median: 11693
      control_range: [27791, 35812]
      candidate_range: [11388, 11893]
      change_pct: -65.4
      overlapping: false
    - metric: index_done_ms_wide_and_shallow
      control_median: 6147
      candidate_median: 2666
      control_range: [5916, 6746]
      candidate_range: [2658, 2679]
      change_pct: -56.6
      overlapping: false
    - metric: gitignore_build_ms
      control_median: 1332
      candidate_median: 897
      control_range: [1332, 2527]
      candidate_range: [879, 897]
      change_pct: -32.7
      overlapping: false
      note: >-
        Two cold calls of each, taken hours apart. The candidate repeats itself
        and the control does not, which is the evidence for the page-cache
        reading below rather than an aside about it.
    - metric: peak_rss_mb_project
      control_median: 181.5
      candidate_median: 177.3
      control_range: [178.9, 182.8]
      candidate_range: [176.4, 177.9]
      change_pct: -2.3
      overlapping: false
    - metric: first_row_ms_project
      control_median: 1337
      candidate_median: 1171
      control_range: [1313, 1914]
      candidate_range: [876, 1233]
      change_pct: -12.4
      overlapping: true
  complexity:
    lines_changed: 0
    new_dependencies: []
    new_failure_modes: []
    notes: Measurement only. Nothing in the server changed for this round; the subject is what exp-006, exp-007 and exp-009 already landed.
  verdict:
    decision: accepted
    primary_metric: index_done_ms_project
    reason: "Accepted on the server half and CONTRADICTED on the browser half, and the second is why this verdict is qualified. A full index falls 30.0 s to 11.9 s on the corpus the earlier rounds used, with 33.8 s to 11.7 s deep and narrow and 6.1 s to 2.7 s wide and shallow, none of the ranges overlapping, both builds reporting identical rows, files and bytes, and peak memory lower everywhere. But a reader on a 241,063-file tree finds the candidate SERIOUSLY LESS RESPONSIVE than 0.6.0 for the whole crawl: 0.6.0 takes longer to paint its first rows and shows no counts for seconds, and is responsive once it does; the candidate paints sooner and then blocks the main thread 55% of the crawl, in blocks to 13.4 s, with interaction p95 at 3.1 s and a worst interaction of 13.5 s. This round could not see that because it measured the server, which is the limitation its own scope section states -- and that limitation turned out to be where the regression was. Tracked as mb-y2ft and H58."
---
# The shipped work, measured against the release

Rounds 001 through 010 each measured one change against the branch before it.
None of them measured what a reader installs.
This round does: the released `0.6.0` against `main`, on three tree shapes, asking two
questions in a fixed order.

**Does it still say the same thing?** First, because a performance change earns its
place by making the *same* answer arrive sooner, and a timing taken from a build that
answers differently is not a comparison of anything.

**Is it faster?** Only worth reading once the first question is settled.

Run twice: once against `8d78c29` and again against `66330af` after #72 merged.
Both rounds are reported, because two rounds a day apart on a machine doing other work
are worth more than one clean round.

## The answers are the same

On every shape both builds report **identical** row counts, file counts and byte totals.
On the tallies channel, `/api/tree?depth=0`, a full structural comparison after the
index settles finds **zero** differences.

One difference exists and is deliberate: a row request no longer computes navigation
tallies, because `depth=0` is now the channel that does.
That is exp-007’s mechanism, the client fetches both, and every tally field is nullable
and guarded field by field.
It is invisible in the browser and visible at the API, which is why it is now written
into the route documentation rather than left to be rediscovered.

## What the numbers said

Against `main` at `66330af`, medians with ranges:

| tree | directories | control | candidate |  |
| --- | ---: | ---: | ---: | ---: |
| **project** (247,153 files, 251 nested `.gitignore`) | 31,201 | 30.0 s (25.7–34.7) | **11.9 s (11.3–12.9)** | 2.51× |
| **deep and narrow** (119,609 files, 83 nested `.gitignore`) | 30,080 | 33.8 s (27.8–35.8) | **11.7 s (11.4–11.9)** | 2.89× |
| **wide and shallow** (120,001 files, no ignore files) | 1,104 | 6.1 s (5.9–6.7) | **2.7 s (2.66–2.68)** | 2.31× |

The earlier round, against `8d78c29`, agrees on all three: 28.2 → 12.2, 28.6 → 11.1, and
6.02 → 2.65.

Directory count is in the table because it is what orders the rows, and getting that
backwards is how the first write-up of this round was wrong.
Two shapes hold roughly the same number of files and differ by a factor of twenty-seven
in directories, and it is the directory-heavy one that costs five times as much.
That is exp-005’s finding arriving from a different direction: the per-directory cost
dominates, and a corpus that is wide and shallow is the easy case however many files it
holds.

Peak resident memory falls on every shape — 181.5 → 177.3 MB, 196.3 → 193.0 MB, 171.1 →
167.0 MB — so none of this is bought with memory.

**The gain is largest when a client is watching**, which is the point rather than a
footnote. Under a probe polling without backoff, `0.6.0` did not finish indexing the
project corpus within 240 seconds; the candidate finished in 28.9 seconds.
That is exp-005’s contention at full strength — a row request that computes tallies
takes CPU from the walker filling it — and exp-007 is what removes it.
The probe is not a realistic client and the margin it exposes is real.

The control is also the less predictable build.
Its range on the project corpus spans nine seconds against the candidate’s one and a
half, and that gap holds across both rounds and every shape.
A build whose worst case is close to its median is a different experience from one whose
worst case is a third worse again.

## What did not reproduce, which is also a result

exp-006 reports 13.36 s → 0.81 s for the gitignore pre-walk on this corpus shape.
Timed directly, cold, on a corpus rebuilt to the same shape:

|  | first measurement | hours later |
| --- | ---: | ---: |
| control `0.6.0` | 2.53 s | 1.33 s |
| candidate | 0.879 s | 0.897 s |

The candidate reproduces the reported 0.81 s and **repeats itself**. The control does
not reproduce the reported 13.36 s and **falls as the day goes on**.

That asymmetry is the finding, not an excuse for it.
The control walks the whole tree looking for nested `.gitignore` files, which is exactly
the work a warm page cache erases; the candidate prunes and barely walks, so there is
little for a cache to help with and its number holds still.
exp-006 cleared the cache between runs and this round could not, because dropping it
needs a privileged `purge` on this host.

So the direction holds, the candidate’s absolute number holds, and the control’s
magnitude is understated here by an amount that depends on how recently the tree was
touched. The honest reading is that the real win is **at least** the ratio measured here
and the reported 16× is not contradicted.
Settling it needs a host where the cache can be dropped.

**And one phrasing to fix.** exp-006 calls its figure “dead time before the first row”.
Over HTTP that does not describe what a reader sees: skeleton rows arrive at about 1.3 s
on *both* builds, because the server answers with placeholder rows while it works, and
the pre-walk cost lands in total index time instead.
The number is about a phase, not about first paint.
Tracked as mb-r29f.

## What this round did not cover, which is where the regression was

**Read this before the numbers above.** A reader using the candidate on a 241,063-file
tree reports it as seriously less responsive than `0.6.0` for the entire crawl, and
measurement in a visible browser agrees: the main thread is blocked 55.3% of a 107 s
window, in blocks reaching 13.4 s, with interaction latency at 32 ms median, 3.1 s at
p95, and 13.5 s at worst.

`0.6.0` behaves the other way round.
It is *slower* to paint the first rows and shows no file counts for several seconds —
and once the navigation renders, it stays responsive while it finishes crawling.

So the trade this campaign made is now visible: it bought earlier first paint and paid
for it in whether the page answers a click while the walk runs.
That is the failure `H56` predicted in the abstract — `first_row_ms` rewards painting
*something* early and says nothing about the states that follow — and the regime `H49`
named as unmeasured, interaction latency, is exactly the one that regressed.
None of this round’s measurements could see it, because they are all server-side.
Tracked as `mb-y2ft`; the invariant is `H58`.

The rest of this section is the scope note as originally written.

This is the server half only.
`reserved_region_shift_px` and `tree_region_repaints` — the two guards the loop’s README
names, because the campaign regressed both over nine rounds without noticing — are
browser facts and are not measured here.
exp-009 measured them for the change that moved them, with the instruments exp-010
corrected; nothing in this round touches the browser, and nothing here should be read as
covering them.

Also not covered: a cold page cache, which needs a host where dropping it is permitted;
any tree shape beyond these three; and a distribution rather than a direction, since
five runs establish the second and not the first.
`first_row_ms_project` is recorded as overlapping for exactly that reason and is not a
result on its own.

## Verdict

**ACCEPTED on `index_done_ms_project`**, 30.0 s → 11.9 s, with two other tree shapes
agreeing, two rounds against two commits agreeing, and no overlapping ranges — and, the
part that decides whether any of the timings mean anything, both builds reporting
identical rows, files and bytes on all three.

**And qualified.** The same candidate is markedly less responsive than `0.6.0` while it
crawls, which no measurement in this round could see.
A round that accepts on its own metric while a reader finds the build worse has not
measured the thing that matters, and saying so here is worth more than the acceptance
is.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->

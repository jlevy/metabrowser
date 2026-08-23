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
    corpus: three shapes -- build_project_corpus at 10 projects (247,153 files, 31,202 directories, 251 nested .gitignore files), build_realistic_corpus at 120,000 files (33,057 directories, 83 nested .gitignore files, 72,701 files under ignored subtrees), and build_corpus at 120,000 files (972 directories, no ignore files)
    corpus_files: 247153
    corpus_dirs: 31202
    host_system: Darwin 25.5.0
    browser: n/a
    viewport: "n/a"
    cold: false
  method:
    runs_per_condition: 5
    interleaved: true
    control: metab 0.6.0, installed from PyPI
    candidate: metab 0.6.1.dev30+8d78c29, built to a wheel and installed into its own venv so both sides are console scripts
    record: devtools/compare_builds.py, with the medians reproduced in this document
  results:
    - metric: index_done_ms_project
      control_median: 28223
      candidate_median: 12174
      control_range: [26567, 30666]
      candidate_range: [11776, 13704]
      change_pct: -56.9
      overlapping: false
    - metric: index_done_ms_deep_and_narrow
      control_median: 6020
      candidate_median: 2648
      control_range: [6018, 6022]
      candidate_range: [2639, 2655]
      change_pct: -56.0
      overlapping: false
    - metric: index_done_ms_wide_and_shallow
      control_median: 28560
      candidate_median: 11059
      control_range: [27094, 28694]
      candidate_range: [10806, 11310]
      change_pct: -61.3
      overlapping: false
    - metric: gitignore_build_ms
      control_median: 2527
      candidate_median: 879
      change_pct: -65.2
      overlapping: false
    - metric: peak_rss_mb_project
      control_median: 182.3
      candidate_median: 178.0
      control_range: [181.2, 183.5]
      candidate_range: [175.1, 178.8]
      change_pct: -2.4
      overlapping: false
    - metric: first_row_ms_project
      control_median: 1335
      candidate_median: 1169
      control_range: [1326, 3226]
      candidate_range: [1101, 1834]
      change_pct: -12.4
      overlapping: true
  complexity:
    lines_changed: 0
    new_dependencies: []
    new_failure_modes: []
    notes: Measurement only. Nothing in the server changed for this round; the subject is what exp-006 and exp-007 already landed.
  verdict:
    decision: accepted
    primary_metric: index_done_ms_project
    reason: "A full index falls 28.2 s to 12.2 s on the corpus the earlier rounds used, and two other tree shapes agree at 6.0 s to 2.6 s and 28.6 s to 11.1 s, none of the ranges overlapping. Both builds report identical rows, file counts and byte totals on every shape, so the speed is not bought with a different answer. Peak memory is unchanged to slightly lower. The claim that did not reproduce is exp-006's baseline magnitude -- 2.53 s measured against 13.36 s reported -- most likely because that round cleared the page cache and this one could not."
---
# The shipped work, measured against the release

Rounds 001 through 008 each measured one change against the branch before it.
None of them measured what a reader actually installs.
This round does: the released `0.6.0` against `main`, end to end, on three tree shapes,
asking two questions in a fixed order.

**Does it still say the same thing?** That comes first, because a performance change
earns its place by making the *same* answer arrive sooner, and a timing collected from a
build that answers differently is not a comparison of anything.

**Is it faster?** Only worth reading once the first question is settled.

## Method, and the four ways it went wrong first

Both builds run as installed console scripts.
The candidate is built to a wheel and installed into its own virtualenv, because a
candidate launched through `uv run` carries a resolver the baseline does not — about
half a second, which is harmless against a fifteen-second difference and decisive
against a one-second one.

Timings are measured from the moment the server accepted its first connection, never
from process spawn, so start-up is never charged to the code under test.

Every corpus is fingerprinted — file count, directory count, newest mtime — before the
first run and after the last.
The first attempt at this round used a working checkout, where the measurement’s own
`__pycache__` writes changed the tree between the two builds and filled the difference
report with `.pyc` counts belonging to neither.

Rows are polled from `/api/tree`, which is what the nav tree requests.
An earlier attempt polled `depth=0`, which returns no rows by design, and reported
first-row latency as null for every run.
A different attempt polled `depth=2` for tallies and read their absence as a regression,
which it is not: see below.

The two builds are asserted to report different versions before anything is measured.
That check exists because a previous comparison ran with both sides reporting `0.6.0`,
the candidate being a source checkout thirty commits past its tag whose recorded version
could not move.

`devtools/compare_builds.py` holds all four guards.

## The answers are the same

On the 247,153-file corpus both builds report **identical** row counts, file counts and
byte totals, and the same on the other two shapes.
On the tallies channel, `/api/tree?depth=0`, a full structural comparison after the
index settles finds **zero** differences.

One difference exists and is deliberate.
A row request no longer computes navigation tallies — `summary`, `extensions`,
`canonical_extensions`, `file_type_registry`, `type_families`, `type_presets`,
`recency_tallies` — because `depth=0` is now the channel that computes them.
That is exp-007’s mechanism, and the client fetches both.
It is invisible in the browser and visible at the API, which is why it is now written
into the route documentation rather than left to be rediscovered.

## What the numbers said

| tree | control | candidate |
| --- | ---: | ---: |
| **project** (247,153 files, 31,202 dirs, 251 nested `.gitignore`) | 28.2 s (26.6–30.7) | **12.2 s (11.8–13.7)** |
| **deep and narrow** (120,000 files, 33,057 dirs, 72,701 ignored) | 6.02 s (6.02–6.02) | **2.65 s (2.64–2.66)** |
| **wide and shallow** (120,000 files, 972 dirs, no ignore files) | 28.6 s (27.1–28.7) | **11.1 s (10.8–11.3)** |

Three shapes, no overlapping ranges, and the candidate’s spread is tighter in every one.
Peak resident memory moves 182.3 MB to 178.0 MB on the project corpus and the same
direction on the others, so none of this is bought with memory.

**The gain is largest when a client is watching**, which is the point rather than a
footnote. Under a probe polling without backoff, `0.6.0` did not finish indexing the
project corpus within 240 seconds; the candidate finished in 28.9 seconds.
That is exp-005’s contention at full strength — a row request that computes tallies
takes CPU from the walker filling it — and exp-007 is what removes it.
The probe is not a realistic client and the margin it exposes is real.

## What did not reproduce, which is also a result

exp-006 reports 13.36 s → 0.81 s for the gitignore pre-walk on this corpus shape.
Timed directly, on a corpus rebuilt to the same shape (251 nested `.gitignore` files,
31,202 directories):

- candidate **0.879 s**, against the 0.81 s reported — reproduced
- control **2.53 s**, against the 13.36 s reported — not reproduced

The likely reason is page-cache state.
exp-006 records `cold: false` but cleared the cache between runs; this round could not,
because doing so needs a privileged `purge` on this host.
The control’s cost is a metadata walk over the whole tree, which is exactly what a warm
cache erases, while the candidate barely walks — which is why the candidate’s figure is
cache-independent and lands on the reported value and the control’s does not.

So the direction holds, the candidate’s absolute number holds, and the control’s
magnitude is understated here.
The honest reading is that the real win is **at least** the 2.9× measured and the
reported 16× is not contradicted.
Settling it needs a host where the cache can be dropped.

**And one phrasing to fix.** exp-006 calls its figure “dead time before the first row”.
Over HTTP that does not describe what a reader sees: skeleton rows arrive at 1.3 s on
*both* builds, because the server answers with placeholder rows while it works, and the
pre-walk cost lands in total index time instead.
The number is about a phase, not about first paint.
Tracked as mb-r29f.

## Limits

Two runs establish a direction; five establish a little more.
Neither is a distribution, and `first_row_ms_project` is listed as overlapping for
exactly that reason — it is not a result on its own.

Not covered: a cold page cache, a browser-side measurement of what a reader perceives as
opposed to what the API reports, and any tree shape beyond these three.

## Verdict

**ACCEPTED on `index_done_ms_project`**, 28.2 s → 12.2 s, with two other tree shapes
agreeing and no overlapping ranges, and — the part that decides whether the timings mean
anything — both builds reporting identical rows, files and bytes on all three.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->

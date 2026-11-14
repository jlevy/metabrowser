---
title: Commit Comparison Cache and Git Route Memo, Confirmation
softschema:
  contract: metabrowser.loadtime:Experiment/v1
  schema: experiment.schema.yaml
  envelope: experiment
  status: enforced
experiment:
  id: exp-081
  title: Commit Comparison Cache and Git Route Memo, Confirmation
  date: "2026-11-13"
  hypotheses:
    - H88
  subject:
    corpus: Standalone clone of this repository at 7a02fed4 (corpus v2), clean, with the same refs at the start and end of every run and of the server half.
    corpus_files: 1286
    host_cpu: 10 CPUs
    host_system: Darwin 25.5.0 arm64, Node 24.19.0
    browser: Headless Chrome 152.0.7977.83 over the DevTools Protocol, a fresh profile per journey, trusted pointer and key input.
    viewport: 1440x900
    cold: false
  method:
    runs_per_condition: 3
    interleaved: true
    control: metab 0.12.1.dev165+9903292 (+165 commits, 099032928), the editable control checkout at origin/main 09903292, clean at the start and end of every run, a fresh server process per run.
    candidate: metab 0.12.1.dev165+9903292 (+179 commits, ed42364d4), the editable checkout of claude/perf-caches at ed42364d, clean at the start and end of every run, a fresh server process per run. It carries exp-061's candidate (4b0e1233), the render cache fix 2bb598b1, and two commits that change only records and exploration scripts.
    record: exp-081-transition-samples.jsonl
  results:
    - metric: requests_data.commits.revisit.1
      control_median: 1
      candidate_median: 0
      control_range: [1, 1]
      candidate_range: [0, 0]
      overlapping: false
    - metric: painted_ready_ms.commits.revisit.1
      control_median: 132.2
      candidate_median: 29.5
      control_range: [98.4, 147.7]
      candidate_range: [29.0, 30.3]
      overlapping: false
    - metric: requests_data.commits.revisit.2
      control_median: 1
      candidate_median: 0
      control_range: [1, 1]
      candidate_range: [0, 0]
      overlapping: false
    - metric: painted_ready_ms.commits.revisit.2
      control_median: 181.7
      candidate_median: 30.3
      control_range: [148.6, 197.8]
      candidate_range: [29.6, 30.4]
      overlapping: false
    - metric: painted_ready_ms.commits.hover_click
      control_median: 30.7
      candidate_median: 47.4
      control_range: [30.6, 30.7]
      candidate_range: [47.2, 48.4]
      overlapping: false
    - metric: painted_ready_ms.commits.cold.1
      control_median: 114.8
      candidate_median: 179.7
      control_range: [114.3, 131.4]
      candidate_range: [164.6, 179.8]
      overlapping: false
    - metric: painted_ready_ms.commits.first_show
      control_median: 264.7
      candidate_median: 80.9
      control_range: [263.2, 278.0]
      candidate_range: [80.3, 97.5]
      overlapping: false
    - metric: painted_ready_ms.main.files_to_commits.first
      control_median: 230.1
      candidate_median: 46.0
      control_range: [229.2, 246.3]
      candidate_range: [45.8, 47.5]
      overlapping: false
    - metric: client_ms.api_git_log_limit_250
      control_median: 144.5
      candidate_median: 5.9
      control_range: [140.76, 201.69]
      candidate_range: [5.53, 52.34]
      overlapping: false
    - metric: client_ms.api_git_summary
      control_median: 148.8
      candidate_median: 2.9
      control_range: [140.72, 202.27]
      candidate_range: [2.48, 52.37]
      overlapping: false
    - metric: client_ms.api_git_refs
      control_median: 22.1
      candidate_median: 3.1
      control_range: [20.07, 67.52]
      candidate_range: [1.47, 46.41]
      overlapping: true
    - metric: client_ms.api_git_refs, identity-refresh samples set aside
      control_median: 21.24
      candidate_median: 2.95
      control_range: [20.07, 24.62]
      candidate_range: [1.47, 4.11]
      overlapping: false
    - metric: comparison_ms with a concurrent catalog page, control (alone → concurrent)
      control_median: 93.6
      candidate_median: 93.8
      control_range: [71.05, 136.62]
      candidate_range: [83.06, 129.55]
      overlapping: true
    - metric: comparison_ms with a concurrent catalog page, candidate (alone → concurrent)
      control_median: 90.2
      candidate_median: 88.3
      control_range: [68.28, 131.93]
      candidate_range: [74.99, 94.59]
      overlapping: true
  complexity:
    lines_changed: 1007
    new_dependencies: []
    new_failure_modes:
      - A served folder's commit comparison kept by the page does not reflect an edit to the working tree's .gitattributes or Git configuration until Refresh, the same lifetime the page already gives commit detail.
      - The route memo does not notice Git configuration outside the repository, or an object lost from under a ref that still names it.
      - A repository with more than 16,384 entries under its ref directories gets no ref state and is answered uncached, as before.
    notes: The product code is exp-061's (1,007 changed lines, 821 of them the server half's); the commits since touch neither half.
  verdict:
    decision: rejected
    primary_metric: "H88(a): requests_data and painted_ready_ms on commits.revisit.1 and .2; H88(b): client ms of /api/git/log?limit=250, /api/git/summary, and /api/git/refs"
    reason: "H88(a), the comparison cache, is rejected: its four deciding metrics are met, but its declared guard has two wrong-way results with ranges apart and 3 of 3 pairs beyond 1.3x, commits.hover_click (30.7 to 47.4 ms) and commits.cold.1 (114.8 to 179.7 ms), and neither is explained; the catalog-contention account of the hover-click was tested and not shown. H88(b), the route memo, is unresolved: its three deciding routes meet the standard rule (the refs overlap is explained by identity-refresh samples, placed directly by their timestamps) and B8 was correct in 45 of 45 checks, but the round's Commits transitions carry those two unexplained wrong-way results, which it cannot attribute to either half."
    commit: ed42364d
---
**Status:** Confirmation round of
[exp-061](exp-061-commit-comparison-cache-and-git-route-memo.md), on harness revision 4.
H88(a), the comparison cache: **rejected**. H88(b), the route memo: **unresolved**.
Three pairs were kept under the load rule; nine were excluded; all 24 runs were valid.

## Why This Round

exp-061 left both halves of H88 unresolved, and the loop’s next step was to explain each
failed guard, fix what the candidate caused, and confirm under criteria declared first.

Since exp-061:

- the render cache’s store no longer walks the kept renders (`2bb598b1`, which is H90’s
  code, in [exp-082](exp-082-markdown-render-cache-and-kept-worker-confirmation.md));
- `git-route-pairs.mjs` records when each sample started, so the identity-period account
  of the refs overlap can be checked directly;
- `catalog-contention-pairs.mjs` tests exp-061’s account of `commits.hover_click`, that
  the background pull-request catalog walk’s page slows the hover’s comparison.

Neither half of H88 changed.
The accept rule is the runbook’s standard one, as restated for this round before it ran:

- ranges apart with two or more pairs beyond 1.3x is a result;
- two or more pairs beyond under overlapping ranges must be explained with evidence
  before accepting, and an explanation that rests only on inference does not count;
- a guard flag is resolved the same way.

## Protocol

Declared before the probe and the series, in a criteria file whose terms this section
restates. One amendment was written before any result (below).

**Order and lock.** The series lock was taken only after the one-minute load had been
under 12 for two minutes, and held through the probe, the series with its replacements,
and the server half.
It was taken at 10:49:54Z at a load of 2.80 and released at 12:35:29Z.

**The mechanism probe**
([catalog-contention-pairs.mjs](../catalog-contention-pairs.mjs)):

- Two servers on the corpus, control on 8920 and candidate on 8921. Each had a fresh
  copy of exp-061’s harness state for its condition, which holds the pull-request
  catalog.
- The hover-click’s commit, `dbfd82b9`, ten iterations, with the leading build and the
  order of the cells alternating.
- Two cells per build: the comparison alone, and the comparison with a catalog page
  started 10 ms after it (`pulls?state=all&limit=8&after=N`, then `pull-cores-prepare`,
  as the Pulls panel issues them).
- The account is shown if (a) on each build the concurrent cell is slower, with ranges
  apart or at least 2 of 10 per-iteration ratios beyond 1.3x, and (b) the per-iteration
  increase has overlapping ranges on the two builds.

**Amendment 1** (08:26:29Z, before anything ran): review E of #368 (E1) found that the
script at `ed42364d` shared one page counter across both builds, so they never met the
same page. The probe instead ran a fixed copy from outside the candidate checkout:

- iteration *i* uses page `pages[(i - 1) % pages.length]` on both builds;
- the warm-up runs each server on every page.

That kept the candidate at `ed42364d`. The copy is committed byte for byte as
`021f1f36`; its sha256 starts `3aca932c9d3375f1`, as the amendment declared.
In the run, both builds met the same page in all ten iterations, and each was warmed on
all four pages.

**The series**, from a frozen harness at `5031dc16`:

```shell
node explorations/performance-loop/transitions.mjs run --exp exp-081 \
  --corpus /path/to/corpus-v2 --runs 6 \
  --journeys files,keyboard,views,maintabs,commits \
  --out .bench/transitions/exp-081/runs.jsonl \
  --condition control=/path/to/control/.venv/bin/metab \
  --condition candidate=/path/to/candidate/.venv/bin/metab
```

- The journey subset holds every transition the deciding metrics and the guards name,
  the same on both builds; `compare` notes it as a non-standard regime.
- `compare` carried this round’s four `--expect` flags and exp-082’s nine.
- **Exclusion, decided from load fields only before any metric was read:** a pair is
  excluded if either run’s one-minute load was above 12 at its start or at the start of
  any measured transition.
  Each excluded pair was replaced by another `run`, until six pairs were kept or six
  replacements had been tried.

**The server half**, right after the series
([git-route-pairs.mjs](../git-route-pairs.mjs), with per-sample `at_ms`):

- Control on 8910 and candidate on 8911, serving the corpus, each with an empty cache.
- 15 pairs per route, with a B8 check between pairs.
  B8 used a scratch clone with 1,000 loose branches, served on 8912 and 8913.
- **Identity-refresh classification, mechanical:** on each timed server, the first
  request is a refresh, and so is each later request that starts at least 5,000 ms after
  the previous refresh started.
- A route’s overlap is explained if, with both builds’ refresh samples set aside, its
  ranges are apart with at least 2 pairs beyond 1.3x, and on both builds every refresh
  sample is above that build’s largest other sample.

**H88(a), deciding:** `commits.revisit.1` and `.2`, `requests_data` and
`painted_ready_ms`, lower.
Guards: no unexplained wrong-way result on any `commits.*` or `main_subject.*commits*`
transition; all runs valid.

**H88(b), deciding:** client time of the three routes, lower.
Guard: B8.

## Identities and Load

| Item | Value |
| --- | --- |
| Control | `metab 0.12.1.dev165+9903292 (+165 commits, 099032928)`, clean at every run’s start and end |
| Candidate | `metab 0.12.1.dev165+9903292 (+179 commits, ed42364d4)`, clean at every run’s start and end |
| Harness | `5031dc16`, scenario revision 4, clean |
| Corpus | `7a02fed4`, clean, 1,286 indexed files, trunk `083e78e4`; the same `for-each-ref` digest before and after the server half |
| Chrome | 152.0.7977.83, headless |
| Probe | 10:49:58Z to 10:50:23Z, one-minute load 2.98 to 2.65 |
| Kept pairs | series `2026-11-13T10-50-24-287Z` pairs 1 to 3, 10:50Z to 11:16Z; one-minute load 2.65 to 6.96 at run starts and at most 9.72 at a transition’s start (`compare` reports 2.65 to 6.96 and 4.1 to 6.96 at runs’ starts and ends) |
| Excluded pairs | 9: pairs 4 to 6 of that series and pairs 1 to 3 of `2026-11-13T11-42-10-407Z` and of `2026-11-13T12-08-36-221Z`, whose highest one-minute load at a run’s or a transition’s start was 14.1 to 22.15; recorded in [exp-081-transition-excluded-samples.jsonl](exp-081-transition-excluded-samples.jsonl) |
| Server half | 12:34:33Z to 12:35:28Z, one-minute load 6.11 to 5.04 |

Three kept pairs are the accept rule’s floor.
At three runs a side, two identical builds come apart on one comparison with probability
10%. `compare` counted 2,918 comparisons, 508 of which vary at all, so about 51 would
come apart by chance; 235 did.
A decision here that would rest on overlapping ranges is called “no detectable effect”.

## Results

Every number here is from `compare` over the kept samples
([exp-081-transition-samples.jsonl](exp-081-transition-samples.jsonl)), from the route
record ([exp-081-git-routes-samples.json](exp-081-git-routes-samples.json)), or from the
probe’s record ([exp-081-catalog-contention.json](exp-081-catalog-contention.json)).
Pair ratios from `compare` are candidate over control.

### H88(a): Commit Revisits

| Transition | Data requests | Painted ready ms, control → candidate | Pair ratios |
| --- | --- | --- | --- |
| `commits.revisit.1` | 1 → 0 | 132.2 (98.4–147.7) → 29.5 (29.0–30.3) | 0.22x (0.21–0.29), 3 of 3 beyond |
| `commits.revisit.2` | 1 → 0 | 181.7 (148.6–197.8) → 30.3 (29.6–30.4) | 0.17x (0.15–0.20), 3 of 3 beyond |

All four are results; `compare` met all of the round’s expectations.

### H88(a): The Guard

| Transition | Metric | Control → candidate | Pair ratios | Verdict |
| --- | --- | --- | --- | --- |
| `commits.hover_click` | painted ready ms | 30.7 (30.6–30.7) → 47.4 (47.2–48.4) | 1.54x (1.54–1.58), 3 of 3 beyond | higher, result |
| `commits.hover_click` | ready ms | 14.9 (14.7–16.4) → 34.5 (33.1–34.9) | 2.32x (2.02–2.37), 3 of 3 beyond | higher, result |
| `commits.hover_click` | frames to ready | 1 → 2 | 2.00x, 3 of 3 beyond | higher, result |
| `commits.cold.1` | painted ready ms | 114.8 (114.3–131.4) → 179.7 (164.6–179.8) | 1.43x (1.37–1.57), 3 of 3 beyond | higher, result |

`compare` also listed the hover-click’s settle time and ready after the last input, and
`commits.cold.1`’s ready and ready after the last input, all higher with ranges apart in
3 of 3 pairs.

### H88(b): Server Half

| Route | Control ms | Candidate ms | Pair ratios (control / candidate) | Apart |
| --- | --- | --- | --- | --- |
| `/api/git/log?limit=250` | 144.5 (140.76–201.69) | 5.9 (5.53–52.34) | 24.18x (3.81–28.04), 15 of 15 beyond | yes |
| `/api/git/summary` | 148.8 (140.72–202.27) | 2.9 (2.48–52.37) | 52.22x (3.45–67.88), 15 of 15 beyond | yes |
| `/api/git/refs` | 22.1 (20.07–67.52) | 3.1 (1.47–46.41) | 6.97x (1.35–16.75), 15 of 15 beyond | no |

Every status was 200, each route’s body had the same length on both builds, and every
candidate answer carried an entity tag.

**The refs overlap, explained.** By the declared classification, the refresh samples on
the refs route are pairs 4, 9, and 14 on both builds: 60.85 to 67.52 ms on the control
and 43.6 to 46.41 ms on the candidate.
Every one is above that build’s largest other refs sample (24.62 and 4.11 ms).
With them set aside, the control’s range is 20.07 to 24.62 ms and the candidate’s 1.47
to 4.11 ms: apart, with 12 of 12 pairs beyond 1.3x. The same holds on the log and
summary routes, whose refresh samples fall on pairs 5, 10, and 15 and on pairs 4
(control) or 5 (candidate), 9, and 14. The overlap is the five-second
repository-identity refresh, which both builds pay on the same requests, placed by each
sample’s own start time.
No sample is dropped from the ranges above.

**B8: correct.** The scratch clone had 1,000 loose branches and 1,019 refs.
It moved 45 times between timed pairs: 12 commits on HEAD, 11 loose branches moved, 11
tags added, and 11 loose branches deleted.
After each move, the candidate’s refs, summary in both scopes, and first log page
equaled the control’s in 45 of 45 checks per route, and its entity tag changed in 45 of
45\.

### The Hover-Click Account, Tested

| Build | Comparison alone, ms | With a catalog page, ms | Per-iteration ratio, median | Beyond 1.3x | Increase, ms |
| --- | --- | --- | --- | --- | --- |
| control | 93.6 (71.05–136.62) | 93.8 (83.06–129.55) | 0.97x | 3 of 10 | −2.4 (−35.2 to 58.5) |
| candidate | 90.2 (68.28–131.93) | 88.3 (74.99–94.59) | 0.96x | 0 of 10 | −3.2 (−44.4 to 15.9) |

Every catalog page returned 8 rows under a generation, every `pull-cores-prepare` was a
200, and in all 20 concurrent cells the prepare started before the comparison’s answer
was read.

Criterion (a) fails on the candidate: its concurrent cell is not slower, and no ratio
passes 1.3x. **The account is not shown.** A catalog page in flight does not measurably
slow the comparison on either build, so exp-061’s account of `commits.hover_click` does
not hold.

The walk’s phase at the hover was recorded per run as declared
([exp-081-hover-click-phase.jsonl](exp-081-hover-click-phase.jsonl)). It repeated
exp-061’s pattern in all 24 runs, kept and excluded:

- every control run had page `after=291` start before the hover’s comparison, and was
  ready in one frame (14.7 to 17.1 ms);
- every candidate run had no page before it, and was ready a frame later (33.1 to 35.5
  ms).

With the contention account not shown, the phase marks where each build is in the
journey, a page ahead or behind the walk, and does not explain the extra frame.

### `commits.cold.1`

`commits.cold.1` is the first commit opened after the Commits list.
The candidate made the same requests as the control: the diff plugin’s modules, the
comparison, the commit, and the background walk.
The application’s own `gitRevision:selectToReady` span was 117.8, 172.7, and 172.7 ms on
the control and 172.3, 164.8, and 171.6 ms on the candidate.
On two control runs, the scenario credited the commit as painted about 60 ms before that
span ended. In the excluded pairs, which are not judged, both builds were bimodal: about
114 or 165 to 181 ms, and the candidate was mostly in the upper mode.
The cause is not identified.

### Other Commits Transitions

| Transition | Painted ready ms, control → candidate | Pair ratios |
| --- | --- | --- |
| `commits.first_show` | 264.7 (263.2–278.0) → 80.9 (80.3–97.5) | 0.31x (0.30–0.35), 3 of 3 beyond |
| `main.files_to_commits.first` | 230.1 (229.2–246.3) → 46.0 (45.8–47.5) | 0.20x (0.19–0.20), 3 of 3 beyond |
| `main_subject.files_to_commits` | 213.7 (163.5–214.1) → 98.8 (97.2–113.2) | 0.53x (0.45–0.60), 3 of 3 beyond |
| `main_subject.pulls_to_commits` | 213.0 (180.1–229.3) → 112.2 (96.9–112.3) | 0.53x (0.49–0.54), 3 of 3 beyond |

All are lower, results.

### The Other Wrong-Way Results

`compare` listed 13 wrong-way results.
Eight are H88(a)’s guard above.
The other five belong to exp-082 or to neither round, and exp-082 gives each with its
evidence.

## Verdicts

**H88(a), the browser comparison cache: rejected.** Decided by the transition scenario.

1. Moved as predicted: yes, all four deciding metrics.
2. Ranges apart: yes, all four, each beyond 1.3x in 3 of 3 pairs.
3. Nothing else wrong-way unaccounted for: **no.**
   - The declared guard has two wrong-way results with ranges apart:
     `commits.hover_click`, a frame later in every run of the round, and
     `commits.cold.1`, about 65 ms later.
   - The one explanation offered for the first was tested here and not shown.
     The second has none.
   - The round does not show that the comparison cache causes either.
     The hover-click follows the candidate’s faster revisits, and `commits.cold.1` comes
     before any revisit. But a declared guard with established, unexplained wrong-way
     results fails.
4. Complexity judgment: 173 changed lines, no dependency, one stated staleness, for 1
   request and about 100 to 150 ms per revisit.
   Not worth it while a hover-click and the first cold commit paint later for reasons
   the round cannot name.

**H88(b), the server route memo: unresolved.** Decided by `git-route-pairs.mjs`.

1. Moved as predicted: yes, on all three routes.
2. Log and summary are apart with 15 of 15 pairs beyond 1.3x. Refs overlaps, explained
   with evidence: the declared refresh samples are the only slow ones, on the same pairs
   on both builds. Without them the refs ranges are apart with 12 of 12 pairs beyond.
3. Its guard, B8, was correct in 45 of 45 checks.
   - In the browser, the transitions the memo serves are lower: `commits.first_show` and
     `main.files_to_commits.first`, apart, 3 of 3 beyond.
   - **Not met in full:** the same table has the two unexplained wrong-way results
     above, on Commits transitions.
   - The memo’s routes are not among their requests, but the memo moves when the Commits
     panel is ready, and the round cannot rule out a timing effect on `commits.cold.1`.
4. Complexity judgment: 821 changed lines across six server modules, no dependency, and
   two stated limits. Worth it for about 139 ms on each log page and 146 ms on each
   summary, once the Commits regressions are explained.

**What would resolve them:**

- a trace of `commits.cold.1` and the hover-click on both builds, at the journey’s
  timing;
- then a declared round, either of each half alone against the control, or of the whole
  candidate with those two explained.

## Changes After the Measured Candidate

After `ed42364d`, the branch merged `main` (`6bff1e88`) and committed the probe script
that ran (`021f1f36`). Neither changes either half of H88.

## Limits

- Three kept pairs, the accept rule’s floor.
  At n = 3 a single comparison separates by chance 10% of the time.
  The two guard results are consistent in the excluded pairs too, which are not judged.
- Headless Chrome only.
- The series ran a journey subset, the same on both builds.
- The probe’s pages came from the catalog state exp-061 left.
  Its pages and their cores may differ from what a fresh run’s walk prepares.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->

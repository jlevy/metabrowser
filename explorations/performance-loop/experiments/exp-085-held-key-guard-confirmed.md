---
title: The Held Key's Guard, Confirmed
softschema:
  contract: metabrowser.loadtime:Experiment/v1
  schema: experiment.schema.yaml
  envelope: experiment
  status: enforced
experiment:
  id: exp-085
  title: The Held Key's Guard, Confirmed
  date: "2026-11-13"
  hypotheses:
    - H91
  subject:
    corpus: Standalone clone of this repository at 7a02fed4 with its own refs, clean; its commit, trunk, and refs did not move during the series.
    corpus_files: 1286
    host_cpu: 10 CPUs
    host_system: Darwin 25.5.0 arm64, Node 24.19.0
    browser: Headless Chrome 152.0.7977.83 over the DevTools Protocol, a fresh profile per journey, trusted key input.
    viewport: 1440x900
    cold: false
  method:
    runs_per_condition: 6
    interleaved: true
    control: metab 0.12.1.dev165+9903292 (+165 commits, 099032928), the editable control checkout at origin/main 09903292, clean at the start and end of every run.
    candidate: metab 0.12.1.dev176+28e12fa2 (+176 commits, 28e12fa28), the editable checkout of this branch at 28e12fa2, the candidate exp-064 measured, clean at the start and end of every run.
    record: exp-085-skim-samples.jsonl
  results:
    - metric: file_envelope_requests.skim.held_arrow_down
      control_median: 6
      candidate_median: 2
      control_range: [6, 6]
      candidate_range: [2, 2]
      overlapping: false
    - metric: requests_data.skim.held_arrow_down
      control_median: 6
      candidate_median: 2
      control_range: [6, 6]
      candidate_range: [2, 2]
      overlapping: false
    - metric: ready_after_last_input_ms.skim.held_arrow_down
      control_median: 47.7
      candidate_median: 52.85
      control_range: [44.1, 65.8]
      candidate_range: [39.3, 69.7]
      overlapping: true
    - metric: painted_ready_ms.skim.held_arrow_down
      control_median: 381.4
      candidate_median: 383.9
      control_range: [374.4, 395.6]
      candidate_range: [373.2, 406.4]
      overlapping: true
  complexity:
    lines_changed: 0
    new_dependencies: []
    notes: "No code changed for this round: it re-measures exp-064's candidate. The walk itself is part of the 315 source lines exp-064 counts for H91, plus a share of the review fixes (round 1's slow-repeat rule, review B2)."
  verdict:
    decision: accepted
    primary_metric: file_envelope_requests
    reason: "skim.held_arrow_down's file envelopes went 6 to 2, ranges apart, over 6 judged pairs. The guard ready_after_last_input_ms went 47.7 (44.1–65.8) to 52.85 (39.3–69.7) ms, pairs 1.09x (0.76–1.58), overlapping with two pairs beyond 1.3x; the pre-registered evidence holds (every candidate run under the walk's 120 ms settle, each pair beyond matched within a frame by its final row's select-to-ready span, no blank or placeholder frame), so the guard is explained and H91 (c) is accepted. Run with Low Power Mode on."
    commit: 28e12fa2
---
**Status:** Accepted: H91 (c), the held arrow key, is settled in the regime it ran in,
Low Power Mode on (lowpowermode 1) on AC power.
Its deciding metric moved as predicted, and its guard, wrong-way under the pair rule
with overlapping ranges, is explained by the evidence declared before measuring.

[exp-064](exp-064-four-movements-nobody-asked-for.md) left H91 (c), the held arrow key,
unresolved. Its deciding metric moved as predicted, but its declared guard,
`ready_after_last_input_ms` on the skim, was wrong-way under the pair rule with only
four pairs and overlapping ranges.
This round measures the same two builds again on that one journey, with six judged pairs
and the evidence that would explain the guard written down before any measurement.

## Protocol

Declared before any measurement, in the lane’s preregistration:

- Builds: the candidate exp-064 measured, `28e12fa2`, against origin/main `09903292`;
  the frozen revision-4 harness `5031dc16`; the same corpus.
- Journey: `skim` only, which carries the deciding metric.
  Six interleaved back-to-back pairs judged, at least five.
- Pacing, by amendment after the first attempt and before any further measurement (no
  result had been read): the first attempt ran its pairs back to back and every one was
  excluded by the load rule; the amendment ran one invocation per pair, each starting
  only once the one-minute load had stayed under 12 for 60 s, a pair’s two runs back to
  back in alternating order, at most 20 paced pairs attempted.
- Load: the series lock taken only after the one-minute load stayed under 12 for two
  minutes; a pair excluded, before any result is read, if either run started above 12,
  saw a transition start above it, or was refused.
- Decides H91 (c): `skim.held_arrow_down`’s `file_envelope_requests`, predicted lower, a
  result when the median is lower and the ranges are apart.
- Guard: `ready_after_last_input_ms` on the skim.
  Ranges apart and higher with two or more pairs beyond 1.3x is a result, and H91 (c) is
  rejected. Two or more pairs beyond 1.3x under overlapping ranges must be explained by
  the evidence below, or H91 (c) is not accepted.
  Fewer than two pairs beyond, and the guard holds.
- Evidence, from fields the harness records on each skim: E1, every candidate run’s
  ready after last input is under the walk’s settle, 120 ms, so the walk released on the
  key’s release and not its timer; E2, each pair beyond 1.3x has its candidate excess
  matched within a frame by the excess of its last select-to-ready span, the final row’s
  own navigation, or by that run’s long tasks and LoAF blocking; E3, no blank or
  placeholder frame in any candidate run.
  The guard is explained only if all three hold.

## Results

`compare`’s figures, lifted by script from its JSON:

| Metric | Role | Control | Candidate | Pair ratio | compare verdict |
| --- | --- | ---: | ---: | ---: | --- |
| file_envelope_requests | deciding | 6 | 2 | — | lower, ranges apart (result) |
| requests_data | shown beside it | 6 | 2 | — | lower, ranges apart (result) |
| ready_after_last_input_ms | guard | 47.7 (44.1–65.8) | 52.85 (39.3–69.7) | 1.09x (0.76–1.58) | ranges overlap, but 2 of 6 pairs are higher beyond the 1.3x tolerance: explain before accepting |
| painted_ready_ms | guard (exp-064) | 381.4 (374.4–395.6) | 383.9 (373.2–406.4) | 1.00x (0.94–1.09) | no detected difference |
| blank_frames | evidence E3 | 0 | 0 | 1.00x (1.00–1.00) | no detected difference |
| placeholder_visible_frames | evidence E3 | 0 | 0 | 1.00x (1.00–1.00) | no detected difference |

The guard’s evidence, pair by pair, from the recorded rows:

| Pair (series start, UTC) | Control ready after last input (ms) | Candidate (ms) | Ratio | Control last select-to-ready (ms) | Candidate (ms) | Candidate long tasks / LoAF blocking (ms) | Candidate blank / placeholder frames |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `19:41:47` | 65.8 | 50 | 0.76x | 50 | 46.3 | 0 / 0 | 0 / 0 |
| `19:45:12` | 50.8 | 39.3 | 0.77x | 50 | 37.3 | 0 / 0 | 0 / 0 |
| `19:46:53` | 45 | 46.2 | 1.03x | 44.5 | 44.3 | 0 / 0 | 0 / 0 |
| `19:48:35` | 44.1 | 69.7 | 1.58x (beyond) | 44.6 | 63.4 | 0 / 0 | 0 / 0 |
| `19:50:14` | 46.9 | 61.8 | 1.32x (beyond) | 47.2 | 56.8 | 0 / 0 | 0 / 0 |
| `19:51:54` | 48.5 | 55.7 | 1.15x | 49.1 | 51.7 | 0 / 0 | 0 / 0 |

E1 (every candidate run under 120 ms): holds.
E2 (each pair beyond 1.3x matched within a frame by its last select-to-ready span, or by
long tasks and LoAF blocking): holds.
E3 (no blank or placeholder frame in any candidate run): holds.

## Verdict

**H91 (c), the held key: accepted**, in the regime the round ran in: Low Power Mode on
(`lowpowermode 1`) and on AC power, at the start and end of every judged run.

- **Deciding:** `skim.held_arrow_down`’s file envelopes went 6 to 2 in every judged run,
  ranges apart, as predicted (the first row, opened by the plain press, and the row the
  walk stops on).
- **Guard:** `ready_after_last_input_ms` went 47.7 (44.1–65.8) to 52.85 (39.3–69.7) ms,
  pairs 1.09x (0.76–1.58): overlapping ranges with two pairs higher beyond 1.3x and one
  lower beyond it, so it had to be explained.
  The evidence declared before measuring holds.
  E1: every candidate run is under the walk’s 120 ms settle, so the walk released on the
  key’s release and never on its timer.
  E2: in each of the two pairs beyond 1.3x, the candidate’s excess is matched within a
  frame by the excess of its final row’s select-to-ready span, the final file’s own
  navigation, with no long task and no LoAF blocking in either.
  E3: no blank or placeholder frame in any candidate run.
  The skim’s painted ready went 381.4 (374.4–395.6) to 383.9 (373.2–406.4) ms, no
  detected difference.
- **What E2 does not separate:** the candidate’s final select-to-ready span starts at
  the last repeat’s selection and so includes the moment until the key’s release opens
  the row; the driver sends the release straight after the last repeat, and E1 bounds
  that moment far below the settle, but the span does not split it from the file’s
  render.

exp-064’s verdict for H91 as a whole stays as recorded there; its note points here for
(c).

## Identities and Load

| Item | Value |
| --- | --- |
| Control build | `metab 0.12.1.dev165+9903292 (+165 commits, 099032928)`, editable checkout at `09903292`, clean |
| Candidate build | `metab 0.12.1.dev176+28e12fa2 (+176 commits, 28e12fa28)`, editable checkout at `28e12fa2`, clean, the commit exp-064 measured; its install was rebuilt at that commit from the same lock since, so its version reads differently from exp-064’s rows |
| Corpus | Standalone clone at `7a02fed4`, refs hash `387f68dc4e8eb8e0`, 1,286 indexed files, unmoved in every run |
| Harness | `5031dc16`, clean; scenario revision 4; the skim journey alone |
| Chrome | 152.0.7977.83, headless, 1440x900 |
| Power | Low Power Mode on (lowpowermode 1) at the start and end of every judged run, on ‘AC Power’; modes seen during the series: lowpowermode 1 |

The runs went from 2026-11-13T19:41:47.602Z to 2026-11-13T19:52:31.119Z. The one-minute
load average was 3.31 to 7.92 at run starts and ends and 3.43 to 7.97 when the skim
started. The series held the shared series lock.
The first attempt, 12 pairs run back to back (series starting 18:50:52Z and 18:55:23Z),
was excluded entirely by the load rule: runs of about 22 s each, every one starting a
server, its index, and Chrome, drove the one-minute load from 11.24 when the lock was
taken to 38.82 within about 95 s. No result of it was read.
Its rows are kept in the excluded samples.

The load and power rules excluded 13 of 19 pairs before any result was read; their rows
are kept in [exp-085-excluded-samples.jsonl](exp-085-excluded-samples.jsonl):

- Pair `2026-11-13T18-50-52-836Z#1`: control run 1 saw load 13.75 at a transition start;
  candidate run 1 started at load 15.28; candidate run 1 saw load 18.74 at a transition
  start.
- Pair `2026-11-13T18-50-52-836Z#2`: candidate run 2 started at load 23.23; candidate
  run 2 saw load 35.9 at a transition start; control run 2 started at load 34.07;
  control run 2 saw load 35.95 at a transition start.
- Pair `2026-11-13T18-50-52-836Z#3`: control run 3 started at load 38.82; control run 3
  saw load 38.15 at a transition start; candidate run 3 started at load 37.1; candidate
  run 3 saw load 36.94 at a transition start.
- Pair `2026-11-13T18-50-52-836Z#4`: candidate run 4 started at load 36.7; candidate run
  4 saw load 35.18 at a transition start; control run 4 started at load 33.16; control
  run 4 saw load 32.26 at a transition start.
- Pair `2026-11-13T18-50-52-836Z#5`: control run 5 started at load 32.26; control run 5
  saw load 30.27 at a transition start; candidate run 5 started at load 29.6; candidate
  run 5 saw load 30.73 at a transition start.
- Pair `2026-11-13T18-50-52-836Z#6`: candidate run 6 started at load 29.55; candidate
  run 6 saw load 28.7 at a transition start; control run 6 started at load 27.85;
  control run 6 saw load 27.82 at a transition start.
- Pair `2026-11-13T18-55-23-776Z#1`: control run 7 started at load 26.63; control run 7
  saw load 31.52 at a transition start; candidate run 7 started at load 31.32; candidate
  run 7 saw load 27.12 at a transition start.
- Pair `2026-11-13T18-55-23-776Z#2`: candidate run 8 started at load 26.15; candidate
  run 8 saw load 24.64 at a transition start; control run 8 started at load 26.17;
  control run 8 saw load 25.11 at a transition start.
- Pair `2026-11-13T18-55-23-776Z#3`: control run 9 started at load 23.74; control run 9
  saw load 26.95 at a transition start; candidate run 9 started at load 27.07; candidate
  run 9 saw load 31.62 at a transition start.
- Pair `2026-11-13T18-55-23-776Z#4`: candidate run 10 started at load 30.69; candidate
  run 10 saw load 28.98 at a transition start; control run 10 started at load 28.1;
  control run 10 saw load 23.71 at a transition start.
- Pair `2026-11-13T18-55-23-776Z#5`: control run 11 started at load 22.37; control run
  11 saw load 20.36 at a transition start; candidate run 11 started at load 20.49;
  candidate run 11 saw load 17.91 at a transition start.
- Pair `2026-11-13T18-55-23-776Z#6`: candidate run 12 started at load 19.04; candidate
  run 12 saw load 17 at a transition start; control run 12 started at load 17; control
  run 12 saw load 17.16 at a transition start.
- Pair `2026-11-13T19-43-31-359Z#1`: candidate run 14 saw load 12.21 at a transition
  start.

6 pairs remain.

## Limits

- One journey, one machine, headless Chrome; WebKit is not measured.
- The guard’s evidence reads the harness’s own fields (ready after last input, the
  shell’s select-to-ready spans, long tasks, LoAF, frame counts); no second instrument
  was run.
- Everything the branch took after `28e12fa2` is post-round and unmeasured here, as in
  exp-064.

## Reproducing

```shell
# one invocation per pair, each after a quiet window, alternating which condition goes first
node explorations/performance-loop/transitions.mjs run --exp exp-085 \
  --corpus /path/to/standalone-clone --runs 1 --journeys skim \
  --out .bench/transitions/exp-085/runs.jsonl \
  --condition control=/path/to/control/.venv/bin/metab \
  --condition candidate=/path/to/this-branch-at-28e12fa2/.venv/bin/metab
node explorations/performance-loop/transitions.mjs compare \
  explorations/performance-loop/experiments/exp-085-skim-samples.jsonl \
  --control control --candidate candidate --format json \
  --expect skim.held_arrow_down:file_envelope_requests:lower
```

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->

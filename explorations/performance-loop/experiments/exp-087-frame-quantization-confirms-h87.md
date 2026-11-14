---
title: Frame Quantization Accounts for exp-083's Wrong-Way Frames
softschema:
  contract: metabrowser.loadtime:Experiment/v1
  schema: experiment.schema.yaml
  envelope: experiment
  status: enforced
experiment:
  id: exp-087
  title: Frame Quantization Accounts for exp-083's Wrong-Way Frames
  date: "2026-11-14"
  hypotheses:
    - H87
  subject:
    corpus: Standalone clone of this repository at 7a02fed4 with its own refs, clean; its commit, trunk, and refs were the same at the start and end of every run.
    corpus_files: 1286
    host_cpu: 10 CPUs
    host_system: Darwin 25.5.0 arm64, Node 24.19.0; Low Power Mode on and AC power for every pair
    browser: Headless Chrome 152.0.7977.83 over the DevTools Protocol, a fresh profile per journey, trusted pointer and key input.
    viewport: 1440x900
    cold: false
  method:
    runs_per_condition: 9
    interleaved: true
    control: metab 0.12.1.dev165+9903292 (+165 commits, 099032928), the editable control checkout at origin/main 09903292, clean.
    candidate: metab 0.12.1.dev692+91bf42b3 (+181 commits, 10d659aee), the editable checkout of claude/perf-delivery checked out at 10d659ae for the series, clean; the code and dependencies of exp-083's candidate, with venv metadata re-synced since.
    protocol:
      path: exp-087-protocol.txt
      sha256: 7afe7e112e9065e64b82f9d3091b2d47d85fe72a947003274c845a66cd86d2ff
    record: exp-087-files-samples.jsonl
  results:
    - metric: later_frame_share.files.cold.json
      control_median: 0.0
      candidate_median: 0.111
      overlapping: true
    - metric: later_frame_share.files.cold.image
      control_median: 0.0
      candidate_median: 0.111
      overlapping: true
    - metric: later_frame_share.files.revisit.markdown_large
      control_median: 0.0
      candidate_median: 0.0
      overlapping: true
    - metric: frames_to_ready.files.cold.json
      control_median: 3
      candidate_median: 3
      control_range: [2, 3]
      candidate_range: [2, 5]
      overlapping: true
    - metric: painted_ready_ms.files.cold.json
      control_median: 80.3
      candidate_median: 78.5
      control_range: [63.3, 81.2]
      candidate_range: [63.0, 109.8]
      overlapping: true
    - metric: frames_to_ready.files.cold.image
      control_median: 4
      candidate_median: 4
      control_range: [3, 4]
      candidate_range: [3, 5]
      overlapping: true
    - metric: painted_ready_ms.files.cold.image
      control_median: 80.8
      candidate_median: 75.4
      control_range: [64.0, 81.3]
      candidate_range: [63.7, 97.2]
      overlapping: true
    - metric: frames_to_ready.files.revisit.markdown_large
      control_median: 4
      candidate_median: 4
      control_range: [3, 4]
      candidate_range: [3, 4]
      overlapping: true
  complexity:
    lines_changed: 1056
    new_dependencies: []
    new_failure_modes:
      - As in exp-060 and exp-083.
    notes: H87's four commits, as in exp-083. This round adds no code.
  verdict:
    decision: accepted
    primary_metric: share of runs on the later frame (frames to ready above the pooled modal count) for files.cold.json, files.cold.image, and files.revisit.markdown_large, by a two-sided Fisher exact test
    reason: In 9 judged pairs, all with Low Power Mode on and on AC power, no view lands on the later frame more often in the candidate than in the control. files.cold.json is 1/9 against 0/9 (p=1.0), files.cold.image 1/9 against 0/9 (p=1.0), and files.revisit.markdown_large 0/9 against 0/9 (p=1.0). As pre-registered, exp-083's wrong-way results on these views (5, 4, and 1) are frame-quantization flips. exp-083's third clause is therefore met, and H87 is accepted on exp-083's metric and guard. Conditional requests per reload fell from 43 to 1, and reload painted-ready went from 158.1 to 124.7 ms.
    commit: 10d659ae
---
**Status:** Accepted.
Measured nine times a side, the cold JSON, cold image, and large Markdown revisit views
land on a later frame no more often with H87 than without it.
exp-083’s one-frame differences were the frame-quantization race that diag083 traced.

## Why This Round

exp-083 left H87 unresolved on ten wrong-way results: five on `files.cold.json` (one
frame later in every pair), four on `files.cold.image`, and one on
`files.revisit.markdown_large`. diag083, an unjudged diagnostic of 12 traced journeys in
three builds (control, candidate, and a candidate with Server-Timing off), found the
extra frame in all three builds.
Its cause is a race: the view’s render task (12–14 ms) must start about 27 ms after the
click to make the frame at about 64 ms.
A vsync frame task that runs between the data response and its body finishing, or a
server stall of a few milliseconds, pushes the paint to about 80 ms.
The per-request server time differed by 0.2–0.5 ms between the builds, and the client
work was identical. This round measures how often each build lands on the later frame.

## Protocol

> Correction, 2026-11-14: the pre-registration file below was kept in an agent’s
> temporary directory, which the 2026-11-14 restart emptied, and was rebuilt byte for
> byte from session transcripts.
> It is now committed as [exp-087-protocol.txt](exp-087-protocol.txt) and named in
> `method.protocol`, with the worktree parent directory written as `$WORKTREES`; writing
> that directory back reproduces the sha256 cited here.

Declared before any measurement, in a local pre-registration file (sha256
`68d473ccea6153b5d72806913965f475021ef932a6baa852b6fc3503fb199d1a`), which the
coordinator checked and approved as registered:

- **Series:** `transitions.mjs run --exp exp-087 --runs 1 --journeys files --out …`, one
  back-to-back pair per invocation, the leading condition alternating, with fresh state
  directories. A pair starts only after the one-minute load has stayed under 12 for 60 s
  with no other series running.
  The target was 10 judged pairs, with at most 24 attempts.
- **Load rule:** as in
  [exp-060](exp-060-immutable-stamped-assets-on-reload.md#load-rule-and-excluded-pairs)
  ([`exp-060-062-load-filter.mjs`](exp-060-062-load-filter.mjs)).
- **Power rule:** `pmset` lowpowermode and the power source are read before and after
  each pair ([power log](exp-087-power.jsonl)). A pair counts only if all four readings
  agree, and modes are never pooled.
  The judged mode is the first to reach 10 judged pairs.
  Failing that, it is the mode with the most, if that mode has at least 6.
- **Deciding question:** for each view, M(V) is the modal frames to ready over the
  judged runs of both builds, a tie taking the smaller count.
  A run lands on the later frame when its frames to ready exceed M(V). Each view gets a
  two-sided Fisher exact test on candidate against control, at p < 0.05, with no
  correction for testing three views.
  If no view differs, exp-083’s wrong-way results on these views are frame-quantization
  flips, and H87 is accepted on exp-083’s metric and guard.
  If any view differs, H87 stays unresolved.
- **Two choices beyond the request, approved before the run:**
  - M(V) is pooled over both builds.
    A per-build mode would hide exp-083’s pattern.
  - `files.revisit.markdown_large` is added so that all ten of exp-083’s wrong-way
    results are covered.

[`exp-087-analyze.mjs`](exp-087-analyze.mjs) applies the power rule and computes the
test. The committed copy differs from the one that ran only by Biome’s formatting and
lint fixes, which do not change behavior.
On the committed samples it gives the same output, byte for byte.

## Pairs

24 attempts ran from 19:54Z on November 13 to 00:37Z on November 14. Every power reading
was `lowpowermode 1` on AC power.
Background work from other sessions kept the load near 12 to 25, so most attempts were
excluded:

| Disposition | Pairs |
| --- | ---: |
| Judged (load 12 or less throughout, one power mode) | 9 |
| Excluded, a transition started above 12 | 5 |
| Excluded, stopped at a run start above 12 (incomplete) | 9 |
| Attempts with no row (stopped at the first run’s start) | 1 |

The highest loads in the judged pairs were 7.6, 10.76, 11.1, 11.14, 10.98, 9.37, 9.98,
11.05, and 8.32. No mode reached 10 judged pairs within 24 attempts.
The judged mode is therefore the one with the most, `lowpowermode=1 AC Power`, with 9
judged pairs, above the minimum of 6. The [samples](exp-087-files-samples.jsonl) hold
every recorded row, judged or not.

## Results

| View | M(V) | Frames to ready, all judged runs | Candidate later | Control later | Fisher p |
| --- | ---: | --- | ---: | ---: | ---: |
| `files.cold.json` | 3 | 2: 5, 3: 12, 5: 1 | 1/9 | 0/9 | 1.0 |
| `files.cold.image` | 4 | 3: 5, 4: 12, 5: 1 | 1/9 | 0/9 | 1.0 |
| `files.revisit.markdown_large` | 4 | 3: 3, 4: 15 | 0/9 | 0/9 | 1.0 |

No view differs beyond chance.
In this series both builds mostly land on what exp-083 saw as the later frame.
That is 3 frames for the cold JSON view in 6 of 9 control runs and 7 of 9 candidate
runs, and 4 frames for the cold image in 7 against 6. So the split in exp-083 (control
on 2 frames, candidate on 3) was where the race happened to fall in those four pairs,
not a property of the candidate.
Read that way, which was not pre-registered, the rates are 6/9 against 7/9 for JSON
above 2 frames and 7/9 against 6/9 for the image above 3 (Fisher p=1.0 each).

**Painted ready, not judged** (median and range; by frames to ready):

| View | Build | All runs | By frames to ready |
| --- | --- | --- | --- |
| `files.cold.json` | control | 80.3 (63.3–81.2) | 2: 64.1 (63.3–64.6), n=3; 3: 80.85 (79.8–81.2), n=6 |
|  | candidate | 78.5 (63.0–109.8) | 2: 63.9 (63.0–64.8), n=2; 3: 79.55 (75.3–81.0), n=6; 5: 109.8, n=1 |
| `files.cold.image` | control | 80.8 (64.0–81.3) | 3: 71.8 (64.0–79.6), n=2; 4: 81.0 (80.7–81.3), n=7 |
|  | candidate | 75.4 (63.7–97.2) | 3: 63.9 (63.7–64.1), n=3; 4: 80.1 (74.5–81.7), n=5; 5: 97.2, n=1 |
| `files.revisit.markdown_large` | control | 147.2 (130.5–163.7) | 3: 130.5, n=1; 4: 147.2 (145.5–163.7), n=8 |
|  | candidate | 147.0 (129.5–147.7) | 3: 129.5 (129.5–129.5), n=2; 4: 147.0 (144.5–147.7), n=7 |

`compare` on the judged pairs shows no detected difference in painted ready for any of
the three views: 1.00x (0.93–1.38), 0.93x (0.79–1.28), and 0.99x (0.89–1.00). It lists
11 results under overlapping ranges, each with two or three of nine pairs beyond the
tolerance. They are frame counts on several file views, the small source view’s times
(painted ready 63.2 against 64.0 ms), and two longest-task readings.
The only results with ranges apart are H87’s own: a Markdown revisit’s plugin assets
come from cache (3 revalidated to 0). It notes that at nine runs a side about none of
167 varying comparisons would come apart by chance, and two did, both of them that cache
result.

**Server time, restated from diag083 and not re-measured:** on the cold JSON chain, the
candidate’s `srv` was about 0.2–0.5 ms above the control’s per request.
The stamped plugin stylesheet took 1.0–1.2 against 0.6–0.8 ms, and `/api/file` 1.7–2.3
against 1.5–1.6 ms.

## Accept Rule, for H87

- exp-083’s first two clauses held: 43 to 1 conditional requests per reload, ranges
  apart, with the reload guard improved.
- Its third clause is now met.
  The ten wrong-way results it could not account for are frame-quantization flips by
  this round’s pre-registered test.
- The complexity judgment stands as in exp-083.

**Verdict:** H87 is accepted.

## Limits

- The judged pairs number 9, not the 10 targeted: 24 attempts were not enough under the
  background load. The pre-registered minimum was 6.
- Only Low Power Mode on was measured.
  Whether the race falls differently without it is not known.
- This round does not re-measure exp-083’s reload metric or guard, since the `files`
  journey has no reload.
- The WebKit relaunch limit recorded in exp-083 stands.
- Two follow-ups came out of diag083: `mb-n50b` (the JSON view’s render and layout sit
  on a frame boundary) and `mb-cgbo` (`/raw` gzips already-compressed media).

## Reproducing

From this directory, with `H` a checkout of the harness at `5031dc16`:

```shell
node exp-087-analyze.mjs exp-087-files-samples.jsonl exp-087-power.jsonl \
  exp-060-062-load-filter.mjs --out /tmp/judged-087.jsonl
node "$H/explorations/performance-loop/transitions.mjs" compare /tmp/judged-087.jsonl \
  --control control --candidate candidate
```

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->

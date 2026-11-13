---
title: Parallel Shell Tools and KPress Loading
softschema:
  contract: metabrowser.loadtime:Experiment/v1
  schema: experiment.schema.yaml
  envelope: experiment
  status: enforced
experiment:
  id: exp-062
  title: Parallel Shell Tools and KPress Loading
  date: "2026-11-13"
  hypotheses:
    - H89
  subject:
    corpus: Standalone clone of this repository at 7a02fed4 with its own refs, clean; nothing else commits to it, and its commit, trunk, and refs were the same at the start and end of every transition run.
    corpus_files: 1286
    host_cpu: 10 CPUs
    host_system: Darwin 25.5.0 arm64, Node 24.19.0
    browser: Headless Chrome 152.0.7977.83 over the DevTools Protocol, launched by the harness, a fresh profile per journey and per probe landing.
    viewport: 1440x900
    cold: false
  method:
    runs_per_condition: 4
    interleaved: true
    control: metab 0.12.1.dev165+9903292 (+165 commits, 099032928), the editable control checkout at origin/main 09903292, clean.
    candidate: metab 0.12.1.dev165+9903292 (+175 commits, d0fe9618e), the editable checkout of claude/perf-delivery at d0fe9618, clean. It carries H87, H89, and mb-rldd together.
    record: exp-062-levels-samples.jsonl
  results:
    - metric: levels_shell_tools.levels_probe
      control_median: 21
      candidate_median: 5
      control_range: [19, 23]
      candidate_range: [5, 5]
      overlapping: false
    - metric: levels_kpress.levels_probe
      control_median: 25
      candidate_median: 19.5
      control_range: [25, 28]
      candidate_range: [19, 20]
      overlapping: false
    - metric: shell_tools_ready_ms.landing.cold_markdown
      control_median: 357.8
      candidate_median: 324.5
      control_range: [310.5, 371.6]
      candidate_range: [302.8, 353.6]
      overlapping: true
    - metric: painted_ready_ms.landing.cold_markdown
      control_median: 311.0
      candidate_median: 362.3
      control_range: [293.8, 331.8]
      candidate_range: [343.7, 420.2]
      overlapping: false
    - metric: blank_frames.landing.cold_markdown
      control_median: 13
      candidate_median: 16.5
      control_range: [13, 13]
      candidate_range: [15, 17]
      overlapping: false
    - metric: placeholder_visible_frames.landing.cold_markdown
      control_median: 10
      candidate_median: 13.5
      control_range: [10, 10]
      candidate_range: [11, 14]
      overlapping: false
    - metric: shell_tools_end_ms.levels_probe
      control_median: 238.1
      candidate_median: 176.95
      control_range: [232, 242]
      candidate_range: [160.3, 201.3]
      overlapping: false
    - metric: kpress_end_ms.levels_probe
      control_median: 264.35
      candidate_median: 304
      control_range: [252.5, 284.3]
      candidate_range: [275.9, 337.1]
      overlapping: true
    - metric: levels_max.levels_probe
      control_median: 34.5
      candidate_median: 24.5
      control_range: [33, 36]
      candidate_range: [24, 25]
      overlapping: false
  complexity:
    lines_changed: 68
    new_dependencies: []
    new_failure_modes:
      - Every on-demand bundle's scripts are preloaded at once, so on a cold load they compete with the first view's KPress assets for the browser's connections; the last KPress asset ended later here, and the styled view painted later.
    notes: The source lines of c0c293bd, H89's own commit (44 added, 24 removed). 640e008d moved KPress loading from the eager SDK to the sdk-views tier to restore startup headroom (435 added, 372 removed); it is in this head too.
  verdict:
    decision: rejected
    primary_metric: dependent request levels to shell tools and to KPress, and shell_tools_ready_ms on landing.cold_markdown, all three lower with ranges apart
    reason: The two level criteria held. Shell tools went from 21 levels (19-23) to 5 (5-5), and KPress from 25 (25-28) to 19.5 (19-20), ranges apart. The third did not. Time to shell tools ready on the cold Markdown landing went from 357.8 ms (310.5-371.6) to 324.5 ms (302.8-353.6), with ranges overlapping, so no effect was detected. All three were required. The guard moved the wrong way. Cold Markdown painted ready went from 311.0 ms (293.8-331.8) to 362.3 ms (343.7-420.2), ranges apart, with every pair within 1.3x (1.16-1.27). The same transition's blank and placeholder frames are wrong-way results. The chain is shorter, but the styled view arrives later. As review B3 provided, a preload cap or a low preload priority is a follow-up candidate, not a re-score.
    commit: d0fe9618
---
**Status:** Rejected.
The request chain is shorter, as predicted.
Time to shell tools ready did not move detectably, and the cold Markdown view now paints
later.

## Why This Round

H89 says shell tools and KPress assets load one round trip at a time, and that fetching
them in parallel, in the same execution order, shortens the chain to tools ready and to
a styled Markdown view.
The plan names three readings: dependent request levels, time to shell tools ready, and
cold Markdown painted-ready.

The candidate’s H89 change (bead `mb-pdul`, commit `c0c293bd`) adds a preload for every
script of an on-demand bundle after the first, then executes them in order.
KPress stylesheets and scripts now load together.
The same head also holds `640e008d`, which moved KPress document loading from the eager
SDK to the `sdk-views` tier to restore startup headroom.

## Protocol

Declared before any measurement, at 2026-11-12T15:36:54Z, in a local pre-registration
file (sha256 `3d5afd678b01bc7d389cdecdb1d7ee5430a3d4ef994a0866bec0690772b8a6f0`). It was
amended once before any result was read; the sha256 after the amendment is
`2fbafb7594d3f848a90c24c7cb3feacfce0b57c5930667b6f75346c840f3899f`.
[exp-060](exp-060-immutable-stamped-assets-on-reload.md#protocol) gives the amendment,
the load rule, and the excluded pairs; this round shares its transition series.

All three criteria must move lower with ranges apart:

1. `levels_shell_tools`, from the levels probe: the dependent request level of the last
   shell-tools script.
2. `levels_kpress`, from the levels probe: the level of the last KPress stylesheet or
   script.
3. `shell_tools_ready_ms` on `landing.cold_markdown`, from the transition series, by
   `compare`’s expectation
   (`--expect landing.cold_markdown:shell_tools_ready_ms:lower`).

**Guard:** `painted_ready_ms` on `landing.cold_markdown`, by the pair rule at 1.3. If it
moves the wrong way, the record says so, and a preload cap or a low preload priority is
a follow-up, not a re-score (review B3).

## The Levels Probe

The transition scenario times shell tools and the first styled view, but it does not
count how many round trips deep they are.
[`exp-062-levels-probe.mjs`](exp-062-levels-probe.mjs) counts them.
It was written and smoke-tested on one diagnostic pair before the series.
Before its first timed run, it gained only a series id and a load reading at the
measured landing, so the load rule can apply to its rows.
The committed copy differs from the one that ran only in Biome’s formatting and import
order.

Each run starts a fresh server on port 8920 and waits for the inventory to complete.
An unrecorded landing in a throwaway profile warms the server.
The measured landing then loads `/view/README.md` in a fresh profile, a cold browser
against a warm server, the scenario’s own regime.
Chrome is launched with the harness’s `launchBrowser`, and requests are classed with its
`requestClass`.

A request’s level is 1 when it starts before any network request has ended.
Otherwise it is one more than the highest level among network requests that ended before
it started. Requests the browser answered from its cache, the event stream, and
background work take no part.
A level is an upper bound on the true dependency depth: two requests that only happened
in sequence count as a chain.

Four interleaved pairs ran, one per invocation, with the leading condition alternating.
Every pair was judged under the load rule; the highest loads were 6.39, 7.39, 6.48, and
8.25.

## Results

Medians and ranges over four runs a side; pair ratios are candidate over control.

**Levels probe** ([samples](exp-062-levels-samples.jsonl), figures from
[`exp-060-062-figures.mjs`](exp-060-062-figures.mjs)):

| Reading | Control | Candidate | Pair ratios |
| --- | ---: | ---: | --- |
| Levels to the last shell-tools script (criterion 1) | 21 (19–23) | 5 (5–5) | 0.217–0.263 |
| Levels to the last KPress asset (criterion 2) | 25 (25–28) | 19.5 (19–20) | 0.679–0.80 |
| Highest level | 34.5 (33–36) | 24.5 (24–25) | 0.667–0.758 |
| Last shell-tools script ends, ms from the document | 238.1 (232–242) | 176.95 (160.3–201.3) | 0.684–0.832 |
| Last KPress asset ends, ms from the document | 264.35 (252.5–284.3) | 304 (275.9–337.1) | 1.047–1.286 |
| Network requests | 112 | 111 | 0.991 |

All 14 shell-tools scripts were fetched in every run of both builds.
KPress stylesheets and scripts numbered 13 in the control and 12 in the candidate.

**Transition series** (`compare` on the judged `landing,files` rows, exp-060’s
[samples](exp-060-landing-files-samples.jsonl)):

| Reading on `landing.cold_markdown` | Control | Candidate | `compare` |
| --- | ---: | ---: | --- |
| Shell tools ready ms (criterion 3) | 357.8 (310.5–371.6) | 324.5 (302.8–353.6) | no detected difference; the expectation is not met |
| Painted ready ms (guard) | 311.0 (293.8–331.8) | 362.3 (343.7–420.2) | 1.17x (1.16–1.27), 0 of 4 beyond: higher, ranges apart, not a result |
| Styled Markdown ms | 311.0 (293.8–331.8) | 362.3 (343.7–420.2) | as painted ready |
| Ready ms | 305.3 (281.3–320.8) | 354.1 (331.2–408.5) | 1.18x (1.15–1.27), not a result |
| Frames to ready | 14 | 17.5 (16–18) | 1.25x (1.14–1.29), not a result |
| Blank frames | 13 | 16.5 (15–17) | 2 of 4 beyond: wrong way |
| Blank ms | 216.6 (216.6–216.7) | 275.0 (250.0–283.3) | 2 of 4 beyond: wrong way |
| Visible placeholder frames | 10 | 13.5 (11–14) | 3 of 4 beyond: wrong way |
| KPress requests | 18 | 17 | lower, ranges apart |

The four pair ratios for shell tools ready are 0.999, 0.966, 0.969, and 0.815.

## Accept Rule

1. **The medians moved in the predicted direction:** yes, for all three criteria.
2. **The ranges do not overlap, at four runs per condition:** yes for both level
   criteria. No for shell tools ready, whose ranges overlap.
   `compare`’s expectation is `NOT MET`, so the finding for criterion 3 is “no
   detectable effect”, not a small win.
3. **Nothing else moved the wrong way without being accounted for:** not met.
   The guard moved the wrong way under separated ranges, inside the tolerance.
   The cold landing’s blank and placeholder frames are wrong-way results.
   exp-060 lists the head’s other wrong-way results, including the unaccounted
   large-source long task.
4. **Complexity:** not worth it as measured.
   The change is small, 68 source lines.
   It shortens the chain to the shell tools, but it does not make the tools ready
   detectably sooner, and it delays the first styled view.

**Verdict:** rejected.

### Where the time went

These are inferences from the readings above, not separately measured:

- The shell-tools scripts now arrive about 61 ms sooner (median end 238.1 → 176.95 ms).
  The tools-ready milestone did not follow detectably.
  What else it waits for (the scripts running in order, the first view) was not
  measured.
- The last KPress asset ends about 40 ms later (264.35 → 304 ms, overlapping ranges)
  despite fewer levels, and the styled view paints about 51 ms later.
  Two mechanisms in this head fit that.
  The 14 parallel shell-tools fetches may hold the browser’s connections to the server
  while the stylesheets the first view needs wait.
  Or KPress loading, now in the `sdk-views` tier (`640e008d`), may start later.
  This round does not separate the two; a network waterfall of one cold landing per
  build would.
- B3’s follow-up targets the first mechanism: cap the preloads, or give them low
  priority, so the first view’s stylesheets go first.

## Known Side Effects and Readings Not Taken

- **`/raw` revalidates** (H87’s change, in this head): a revisited image costs one 304.
  Neither the probe nor the `files` journey revisits an image.
- **`raf_frame_gaps`** is off in Chrome and played no part; its readings are not
  comparable with those at `640e008d`.
- **WKWebView** readings were not taken.

## Reproducing

[exp-060’s commands](exp-060-immutable-stamped-assets-on-reload.md#reproducing) produce
both rounds’ figures.
The probe is run as:

```shell
node exp-062-levels-probe.mjs --harness "$H" --corpus /path/to/standalone-clone \
  --pairs 1 --out exp-062-levels-samples.jsonl --port 8920 \
  --condition control=/envs/control/.venv/bin/metab \
  --condition candidate=/envs/candidate/.venv/bin/metab
```

The order of the two `--condition` flags was swapped on every other invocation.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->

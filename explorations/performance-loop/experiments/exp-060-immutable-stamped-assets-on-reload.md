---
title: Immutable Stamped Assets on Reload
softschema:
  contract: metabrowser.loadtime:Experiment/v1
  schema: experiment.schema.yaml
  envelope: experiment
  status: enforced
experiment:
  id: exp-060
  title: Immutable Stamped Assets on Reload
  date: "2026-11-13"
  hypotheses:
    - H87
  subject:
    corpus: Standalone clone of this repository at 7a02fed4 with its own refs, clean; nothing else commits to it, and its commit, trunk, and refs were the same at the start and end of every run.
    corpus_files: 1286
    host_cpu: 10 CPUs
    host_system: Darwin 25.5.0 arm64, Node 24.19.0
    browser: Headless Chrome 152.0.7977.83 over the DevTools Protocol, a fresh profile per journey, trusted pointer and key input.
    viewport: 1440x900
    cold: false
  method:
    runs_per_condition: 4
    interleaved: true
    control: metab 0.12.1.dev165+9903292 (+165 commits, 099032928), the editable control checkout at origin/main 09903292, clean at the start and end of every run.
    candidate: metab 0.12.1.dev165+9903292 (+175 commits, d0fe9618e), the editable checkout of claude/perf-delivery at d0fe9618, clean at the start and end of every run. It carries H87, H89, and mb-rldd together.
    record: exp-060-landing-files-samples.jsonl
  results:
    - metric: revalidated_total.landing.reload
      control_median: 43
      candidate_median: 1
      control_range: [43, 43]
      candidate_range: [1, 1]
      change_pct: -97.7
      overlapping: false
    - metric: plugin_static_revalidated.landing.reload
      control_median: 29
      candidate_median: 0
      control_range: [29, 29]
      candidate_range: [0, 0]
      overlapping: false
    - metric: kpress_static_revalidated.landing.reload
      control_median: 13
      candidate_median: 0
      control_range: [13, 13]
      candidate_range: [0, 0]
      overlapping: false
    - metric: data_revalidated.landing.reload
      control_median: 1
      candidate_median: 1
      control_range: [1, 1]
      candidate_range: [1, 1]
      overlapping: true
    - metric: requests_total.landing.reload
      control_median: 109
      candidate_median: 108
      control_range: [106, 109]
      candidate_range: [105, 108]
      overlapping: true
    - metric: painted_ready_ms.landing.reload
      control_median: 175.8
      candidate_median: 140.8
      control_range: [173.5, 187.0]
      candidate_range: [116.0, 148.0]
      overlapping: false
    - metric: painted_ready_ms.landing.cold_markdown
      control_median: 311.0
      candidate_median: 362.3
      control_range: [293.8, 331.8]
      candidate_range: [343.7, 420.2]
      overlapping: false
    - metric: long_task_max_ms.files.revisit.source_large
      control_median: 121.0
      candidate_median: 147.0
      control_range: [109.0, 137.0]
      candidate_range: [147.0, 149.0]
      overlapping: false
  complexity:
    lines_changed: 1056
    new_dependencies: []
    new_failure_modes:
      - A file edited in place with its size, modification time, change time, and inode all unchanged would be served immutable under its old stamp.
      - A live tree (an editable install or an operator's plugin directory) is stamped again on every shell render, one stat per file; a tree past 2,000 files or 64 MiB is not stamped and its assets are revalidated as before.
    notes: The source and devtools lines of H87's four commits (191dd8a1, 1b30fa6f, e473fe46, d0fe9618), 817 added and 239 removed; tests and docs are not counted.
  verdict:
    decision: unresolved
    primary_metric: revalidated requests on landing.reload, all route families summed
    reason: H87's metric moved as predicted with ranges apart, 43 conditional requests per reload to 1, and its guard, reload painted-ready, moved the right way (175.8 to 140.8 ms, pairs 0.67-0.84). The accept rule's third clause is not met. The head this round measures, which also carries H89, has one wrong-way result that nothing here accounts for. On a revisit of a large source file, the longest task grew from 121 ms (109-137) to 147 ms (147-149), with 2 of 4 pairs beyond 1.3x. Its other four wrong-way results are accounted for below. Acceptance waits on that long task being explained, or on a round whose candidate holds H87 without H89 and mb-rldd.
    commit: d0fe9618
---
**Status:** Unresolved.
H87’s prediction held decisively and its guard improved; one unaccounted wrong-way
result in the same head keeps the accept rule’s third clause open.

## Why This Round

H87 says stamped assets carry no `Cache-Control`, and plugin and KPress assets are
`no-cache`, so every reload revalidates them.
Immutable headers on addresses that name their content would remove those requests.
The plan names conditional requests per reload in Chrome as the deciding metric, with
reload ready time as a guard.

The candidate (bead `mb-3m3l`, commits `191dd8a1`, `1b30fa6f`, `e473fe46`, and
`d0fe9618`) gives every static, plugin, and KPress asset an address that names its
content: `/static/<file>?v=<digest>`, `/plugin-static/<plugin>/@<digest>/…`, and
`/kpress-static/@<digest>/v<version>/…`. Such an answer is served
`max-age=31536000, immutable` only while the stamp is current and the file’s stat is the
one it was stamped with.
`/raw` answers are `no-cache` and revalidate under a tag that names the file, its
representation, the trust profile, and the sandbox policy.

## Protocol

Declared before any measurement, at 2026-11-12T15:36:54Z, in a local pre-registration
file (sha256 `3d5afd678b01bc7d389cdecdb1d7ee5430a3d4ef994a0866bec0690772b8a6f0`), and
amended once before any result was read (below; sha256 after the amendment
`2fbafb7594d3f848a90c24c7cb3feacfce0b57c5930667b6f75346c840f3899f`):

- **Decides:** revalidated (conditional) requests on `landing.reload`, all route
  families summed, as the harness’s cache disposition counts them.
  Predicted lower; a count, judged on its ranges.
- **Guard:** `painted_ready_ms` on `landing.reload`, by `compare`’s back-to-back pair
  rule at tolerance 1.3.
- **Also shown:** the revalidated count per family, and all requests, on
  `landing.reload`.
- **Series:** one transition series serves this round and
  [exp-062](exp-062-parallel-shell-tools-and-kpress-loading.md): four runs per
  condition, interleaved in back-to-back pairs, at scenario revision 4 of the harness at
  `5031dc16`. The candidate carries both hypotheses’ changes, so a movement here belongs
  to the head, not to H87 alone.
- **Accept rule:** the runbook’s, with the complexity judgment below.

**Amendment 1** (2026-11-12T21:34:53Z, before any result was read):

- The series runs `--journeys landing,files` for both builds, with `--out` naming its
  own rows file, so the rows are official.
  `landing` holds every criterion and guard of both rounds; `files` is kept to account
  for the `/raw` change and other file-view movement.
  The reason is machine time: two journeys take about two minutes a run instead of
  eight, so four pairs fit a 15–20 minute quiet window.
- The levels probe of exp-062 runs first.
- The load rule below, set by the coordinator at about 17:40Z on November 12, is part of
  the protocol.
- The full-scenario pairs recorded before the amendment stay recorded and are not
  judged. `compare` refuses to mix the two journey lists.

At 06:32Z on November 13 the coordinator moved the deadline for starting a pair 45
minutes later. Nothing else in the protocol changed.

## Load Rule and Excluded Pairs

The machine was shared with other sessions during this round.
From about 17:25Z on November 12, their disk work raised the one-minute load average to
245 at one run’s end.
From about 18:52Z another session’s CPU stress test (12 to 16 busy loops in cycles, with
headless Chrome checks) kept it between about 20 and 220 for hours.
After that, with Spotlight’s indexer the busiest process, it stayed between about 10 and
25 until about 06:05Z on November 13. Before any result of either round was read, the
coordinator set a load rule, applied by
[`exp-060-062-load-filter.mjs`](exp-060-062-load-filter.mjs):

- A back-to-back pair is excluded when any run in it saw a one-minute load above 12 at
  its start or at the start of any measured transition (for a levels-probe row, at its
  start or at its measured landing).
- A pair is excluded when it is incomplete: a run refused, or a condition missing.
- A replacement pair starts only after the load has been under 12 for 120 s, and the
  series lock is held throughout.
- Excluded rows stay in the samples as recorded and are not judged.

A pair that the rule had already excluded was stopped early to save machine time.
The decision to stop read only the load on the harness’s own run line.

**Full scenario, before the amendment** ([samples](exp-060-full-scenario-samples.jsonl),
11 rows, every journey):

| Pair (series#pair) | Runs | Highest load | Disposition |
| --- | --- | ---: | --- |
| `2026-11-12T16-48-55-703Z#1` | control 1, candidate 1 | 18.82 | Excluded |
| `2026-11-12T16-48-55-703Z#2` | candidate 2, control 2 | 23.09 | Excluded |
| `2026-11-12T16-48-55-703Z#3` | control 3, candidate 3 | 83.89 | Excluded; candidate 3 was refused in its warm-up (`journey_error: Runtime.evaluate: no reply in 20000 ms`) |
| `2026-11-12T16-48-55-703Z#4` | a candidate run that started at load 245.2 | 245.2 | Stopped at its start; no row |
| `2026-11-12T17-47-38-524Z#1` | control 4, candidate 4 | 17.96 | Excluded |
| `2026-11-12T18-06-16-055Z#1` | candidate 5; its control started at 20.52 and was stopped | 19.61 | Excluded, incomplete |
| `2026-11-12T18-19-29-062Z#1` | control 5; its candidate started at 26 and was stopped | 25.13 | Excluded, incomplete |
| `2026-11-12T18-41-24-158Z#1` | candidate 6; its control was stopped in its measured pass at 109.99 | 17.67 | Excluded, incomplete |

**`landing,files`, after the amendment**
([samples](exp-060-landing-files-samples.jsonl), 13 rows):

| Pair (series#pair) | Runs | Highest load | Disposition |
| --- | --- | ---: | --- |
| `2026-11-13T06-19-20-904Z#1` | control 1, candidate 1 | 8.07 | Judged |
| `2026-11-13T06-24-27-669Z#1` | candidate 2; its control started at 13.41 and was stopped | 12.4 | Excluded, incomplete |
| `2026-11-13T06-28-24-187Z#1` | control 2, candidate 3 | 9.58 | Judged |
| `2026-11-13T06-34-42-606Z#1` | control 3, candidate 4 | 8.57 | Judged |
| `2026-11-13T06-39-49-872Z#1` | candidate 5, control 4 | 18.96 | Excluded |
| `2026-11-13T06-50-22-024Z#1` | control 5, candidate 6 | 12.5 | Excluded |
| `2026-11-13T06-55-30-495Z#1` | candidate 7, control 6 | 9.85 | Judged |

Four pairs are judged, three of them led by the control: the deadline restart began a
new alternation, so the control led two pairs in a row.
`compare` reports a one-minute load of 5.73–8.88 and 6.96–9.14 at the judged runs’
starts and ends.

## Identities

| Item | Value |
| --- | --- |
| Control build | `metab 0.12.1.dev165+9903292 (+165 commits, 099032928)`, editable checkout at `09903292`, clean at the start and end of every run |
| Candidate build | `metab 0.12.1.dev165+9903292 (+175 commits, d0fe9618e)`, editable checkout at `d0fe9618`, clean at the start and end of every run |
| Corpus | Standalone clone at `7a02fed4` with its own refs, clean, 1,286 indexed files; server git log head `7a02fed4`, trunk `083e78e4` |
| Harness | `5031dc16`, clean; scenario revision 4; `--journeys landing,files` (`compare` notes the journey subset) |
| Chrome | 152.0.7977.83, headless |
| Pull request catalog | 360 to 367 in all; the totals each condition saw are in `compare`’s notes |

## Results

From `compare` on the judged rows, and from
[`exp-060-062-figures.mjs`](exp-060-062-figures.mjs) for the revalidated totals, which
`compare` shows but does not judge.
Medians and ranges over four runs a side; pair ratios are candidate over control.

| Metric on `landing.reload` | Control | Candidate | Pair ratios |
| --- | ---: | ---: | --- |
| Revalidated requests, all families (decides) | 43 (43–43) | 1 (1–1) | 0.023 in every pair |
| `plugin_static` revalidated | 29 | 0 | — |
| `kpress_static` revalidated | 13 | 0 | — |
| `data` revalidated | 1 | 1 | — |
| `plugin_static` from cache | 0 | 28 | — |
| `kpress_static` from cache | 4 | 16 | — |
| `static` from cache | 41 | 41 | — |
| KPress requests (`requests_kpress`) | 18 | 17 | — |
| All requests | 109 (106–109) | 108 (105–108) | 0.963–1.019 |
| Painted ready ms (guard) | 175.8 (173.5–187.0) | 140.8 (116.0–148.0) | 0.78x (0.67–0.84), 2 of 4 beyond |
| Ready ms | 170.9 (164.1–173.0) | 125.4 (113.3–145.1) | 0.73x (0.67–0.88), 3 of 4 beyond |
| Blank frames | 8 | 5 (4–5) | 0.63x (0.50–0.63), 4 of 4 beyond |

The one revalidation left is a data route, which H87 does not touch.
The candidate’s 29th `plugin_static` request was still pending when each reload’s window
closed, in all four runs.
`/static` assets never revalidated on reload in either build.
They already carried a `?v=` stamp with no `Cache-Control`, so Chrome kept them fresh by
its own heuristic. H87’s change makes that freshness explicit.
On the cold landing, the control revalidated one KPress asset and the candidate none.

## Accept Rule

1. **The median moved in the predicted direction:** yes, 43 to 1.
2. **The ranges do not overlap, at four runs per condition:** yes, 43–43 against 1–1.
3. **Nothing else moved the wrong way without being accounted for:** not met.
   `compare` (exit 1) lists five wrong-way results in this round’s table:
   - `landing.cold_markdown` blank frames 13 → 16.5 (15–17), blank ms 216.6 → 275.0, and
     visible placeholder frames 10 → 13.5 (11–14), with two to three pairs beyond each.
     These are the frames before a later ready frame.
     The cold Markdown landing is ready later in the candidate (painted ready 311.0 →
     362.3 ms, ranges apart, pairs 1.16–1.27, all within the tolerance).
     exp-062’s levels probe shows the last shell-tools script ending earlier and the
     last KPress asset ending later (264.35 → 304 ms).
     exp-062 traces the delay to the loading changes in this head: H89’s parallel
     fetches, or `640e008d`’s move of KPress loading.
     A cold landing starts with an empty browser cache, so H87’s headers do not apply to
     it. H87’s server-side stamp is also taken on every reload, and the reload painted
     sooner. Accounted for, by that attribution, which is an inference: this round does
     not separate the changes.
   - `files.cold.source_small` frames to ready, 2 (2–3) → 3 (2–3), under overlapping
     ranges, 2 of 4 pairs beyond.
     Its painted ready did not move (61.3 → 64.0 ms, pairs 1.00x). In both builds the
     per-run painted-ready values sit at about 48 and 64 ms, one frame apart, with one
     control run at 59 ms.
     Accounted for as frame quantization.
   - `files.revisit.source_large` longest task, 121 (109–137) → 147 (147–149) ms, 2 of 4
     pairs beyond. **Not accounted for.** Both builds made the same two background data
     requests and reached ready in one frame.
     The cold large-source view’s longest task moved the same way within the tolerance
     (116 → 128 ms, ranges apart).
     Something in the head lengthens the source view’s longest task.
     This round does not show whether it comes from H87, H89, or mb-rldd.
4. **Complexity:** worth it for H87 alone.
   About a thousand source lines and one new module remove 42 of 43 conditional requests
   per reload and make the reload paint sooner.
   The two new failure modes are bounded: tests cover an edit after the stamp, the
   re-stamp after a stat moved, and a tree past the bound
   (`tests/test_asset_stamps.py`).

**Verdict:** unresolved.
Clauses 1 and 2 hold and the guard improved.
Clause 3 waits on the large-source long task: explain it, or measure a candidate that
holds H87 without H89 and mb-rldd against the same control.

## What Did Not Move

- Requests per reload, 109 to 108: the reload still asks for every asset; it now finds
  them fresh.
- Every other file transition’s painted ready: no detected difference, except a single
  pair beyond the tolerance under overlapping ranges on `files.cold.source_small`,
  listed by `compare` but not a wrong-way result.

## Known Side Effects and Readings Not Taken

- **`/raw` revalidates.** A revisited image costs one 304 where the control served it
  without a request. The `files` journey visits its image only cold, so this round does
  not exercise that revisit: `files.cold.image` made the same requests in both builds.
- **`raf_frame_gaps`** (mb-rldd’s frame recorder) runs only where Long Tasks are
  unsupported, so it is off in Chrome and played no part here.
  Its readings are not comparable with those taken at `640e008d`.
- **WKWebView relaunch**, H87’s secondary reading, was not measured: it waits on `metab`
  host mode’s sticky port and the committed probe, and the screen was locked.

## Reproducing

From this directory, with `H` a checkout of the harness at `5031dc16`, writing the
judged rows somewhere outside the checkout:

```shell
node exp-060-062-load-filter.mjs exp-060-landing-files-samples.jsonl --out /tmp/judged.jsonl
node exp-060-062-load-filter.mjs exp-062-levels-samples.jsonl --out /tmp/judged-levels.jsonl
node "$H/explorations/performance-loop/transitions.mjs" compare /tmp/judged.jsonl \
  --control control --candidate candidate \
  --expect landing.cold_markdown:shell_tools_ready_ms:lower
node exp-060-062-figures.mjs "$H" /tmp/judged.jsonl /tmp/judged-levels.jsonl
```

The `--expect` is exp-062’s criterion; both rounds read the same `compare`. The samples
are `transitions.mjs samples` of the local rows.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->

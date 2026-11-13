---
title: Immutable Stamped Assets Without H89
softschema:
  contract: metabrowser.loadtime:Experiment/v1
  schema: experiment.schema.yaml
  envelope: experiment
  status: enforced
experiment:
  id: exp-083
  title: Immutable Stamped Assets Without H89
  date: "2026-11-13"
  hypotheses:
    - H87
  subject:
    corpus: Standalone clone of this repository at 7a02fed4 with its own refs, clean; its commit, trunk, and refs were the same at the start and end of every run.
    corpus_files: 1286
    host_cpu: 10 CPUs
    host_system: Darwin 25.5.0 arm64, Node 24.19.0, Low Power Mode set (checked after the runs)
    browser: Headless Chrome 152.0.7977.83 over the DevTools Protocol, a fresh profile per journey, trusted pointer and key input.
    viewport: 1440x900
    cold: false
  method:
    runs_per_condition: 4
    interleaved: true
    control: metab 0.12.1.dev165+9903292 (+165 commits, 099032928), the editable control checkout at origin/main 09903292, clean at the start and end of every run; the control of exp-060.
    candidate: metab 0.12.1.dev165+9903292 (+181 commits, 10d659aee), the editable checkout of claude/perf-delivery at 10d659ae, clean at the start and end of every run. It carries H87 and mb-rldd, with H89 reverted.
    record: exp-083-landing-files-samples.jsonl
  results:
    - metric: revalidated_total.landing.reload
      control_median: 43
      candidate_median: 1
      control_range: [43, 43]
      candidate_range: [1, 1]
      change_pct: -97.7
      overlapping: false
    - metric: painted_ready_ms.landing.reload
      control_median: 158.1
      candidate_median: 124.7
      control_range: [143.6, 224.4]
      candidate_range: [107.5, 125.7]
      overlapping: false
    - metric: long_task_max_ms.files.revisit.source_large
      control_median: 120
      candidate_median: 121
      control_range: [109, 143]
      candidate_range: [109, 135]
      overlapping: true
    - metric: painted_ready_ms.landing.cold_markdown
      control_median: 340.8
      candidate_median: 315.2
      control_range: [287.6, 411.3]
      candidate_range: [299.1, 346.1]
      overlapping: true
    - metric: painted_ready_ms.files.cold.json
      control_median: 63.4
      candidate_median: 80.9
      control_range: [63.0, 64.1]
      candidate_range: [79.6, 88.9]
      overlapping: false
    - metric: frames_to_ready.files.cold.json
      control_median: 2
      candidate_median: 3
      control_range: [2, 2]
      candidate_range: [3, 3]
      overlapping: false
    - metric: frames_to_ready.files.cold.image
      control_median: 3
      candidate_median: 4
      control_range: [3, 3]
      candidate_range: [3, 4]
      overlapping: true
  complexity:
    lines_changed: 1056
    new_dependencies: []
    new_failure_modes:
      - A file edited in place with its size, modification time, change time, and inode all unchanged would be served immutable under its old stamp.
      - A live tree is stamped again on every shell render, one stat per file; a tree past 2,000 files or 64 MiB is not stamped and its assets are revalidated as before.
    notes: H87's four commits, as in exp-060 (817 source lines added, 239 removed). The reverts of H89 do not touch them.
  verdict:
    decision: unresolved
    primary_metric: revalidated requests on landing.reload, all route families summed
    reason: With H89 reverted, H87's metric moved as predicted with ranges apart, 43 conditional requests per reload to 1. The guard improved, reload painted-ready 158.1 to 124.7 ms (pairs 0.56-0.87). The check declared for exp-060's open clause came back clean, and the cold Markdown landing is back at the control's level. The accept rule's third clause is still not met. compare lists ten wrong-way results that this round does not account for. The cold JSON view is one frame later in every pair, painted ready 63.4 to 80.9 ms with ranges apart, and the app's own select-to-ready span is 52-55 ms against 64-85 ms with the same requests. The cold image and the large Markdown revisit take one more frame under overlapping ranges. Acceptance waits on a diagnostic that splits that delay between H87's stamped handlers and mb-rldd's timing middleware.
    commit: 10d659ae
---
**Status:** Unresolved.
Without H89, H87’s prediction holds and its guard improves, and exp-060’s open long task
does not recur. A cold JSON view that paints one frame later in every pair now keeps the
third clause open.

## Why This Round

[exp-060](exp-060-immutable-stamped-assets-on-reload.md) measured H87 in a head that
also carried H89 and mb-rldd, and left one wrong-way result unaccounted for.
[exp-062](exp-062-parallel-shell-tools-and-kpress-loading.md) rejected H89, and #372
reverted it (`c30ee25c`, `add7edac`, `8ce4a224`, with docs in `372cbcec` and goldens in
`10d659ae`). This round measures H87, with mb-rldd, against the same control.

## Protocol

Declared before any exp-083 measurement, at 2026-11-13T07:25Z, in a local
pre-registration file (sha256
`426d68cde3dcd4652bfa5ccbbabf83f2bf634287517c3ce81cd5736b4f3f506d`):

- **Decides:** H87’s metric, as in exp-060: revalidated requests on `landing.reload`,
  all route families summed, predicted lower, judged on its ranges.
- **Guard:** `painted_ready_ms` on `landing.reload`, by the pair rule at 1.3.
- **Declared check for exp-060’s open clause:** `long_task_max_ms` on
  `files.revisit.source_large`, by the pair rule at 1.3. Had `compare` marked it
  wrong-way again, one unjudged DevTools trace per build would have split it between H87
  and mb-rldd.
- **Predicted:** the cold Markdown landing returns to the control’s level now that H89
  is gone, with no detected difference in painted-ready and no wrong-way blank or
  placeholder frames.
- **Everything else:** the third clause covers every wrong-way result `compare` lists
  for `landing` and `files`.
- **Series:** `--journeys landing,files` with `--out`, one back-to-back pair per
  invocation, the leading condition alternating, fresh state directories for exp-083.
  The target was four judged pairs.
- **Load rule, lock, and filter:** as in
  [exp-060](exp-060-immutable-stamped-assets-on-reload.md#load-rule-and-excluded-pairs),
  with [`exp-060-062-load-filter.mjs`](exp-060-062-load-filter.mjs).
  The lock was held from 16:52:34Z to 17:50:40Z.

`compare` was run with `--expect landing.reload:painted_ready_ms:lower`, which reads the
guard; the deciding count is not a metric `compare` judges.

## Pairs

| Pair (series#pair) | Runs | Highest load | Disposition |
| --- | --- | ---: | --- |
| `2026-11-13T16-58-45-642Z#1` | control 1, candidate 1 | 8.07 | Judged |
| `2026-11-13T17-03-49-545Z#1` | candidate 2, control 2 | 8.77 | Judged |
| `2026-11-13T17-08-52-940Z#1` | control 3, candidate 3 | 7.6 | Judged |
| `2026-11-13T17-14-06-134Z#1` | candidate 4, refused; its control started at 26.34 and was stopped | 6.04 | Excluded, incomplete |
| `2026-11-13T17-39-20-175Z#1` | control 4, refused; its candidate started at 190.91 and was stopped | 8.8 | Excluded, incomplete |
| `2026-11-13T17-47-34-937Z#1` | candidate 5, control 5 | 8.59 | Judged |

The machine was unplugged at 17:12:00Z and went into clamshell sleep at 17:12:04Z, ten
seconds after the third pair ended.
It woke in the dark several times before a full wake at 17:42:26Z. The fourth pair
started during those wakes.
The harness refused its candidate run (`frame_clock`: median frame step 200 ms on
`files.revisit.source_large`). The fifth pair started in a dark wake.
Its control was refused (`journey_error: Runtime.evaluate: no reply in 20000 ms`), and
the load on its candidate’s start line was 190.91. The three judged pairs before the
sleep ran on AC power, awake, and so did the one after the full wake.
`compare` reports a one-minute load of 2.95–7.28 and 3.85–7.58 at the judged runs’
starts and ends.

## Identities

| Item | Value |
| --- | --- |
| Control build | `metab 0.12.1.dev165+9903292 (+165 commits, 099032928)`, editable checkout at `09903292`, clean |
| Candidate build | `metab 0.12.1.dev165+9903292 (+181 commits, 10d659aee)`, editable checkout at `10d659ae`, clean |
| Corpus | Standalone clone at `7a02fed4`, clean, 1,286 indexed files; server git log head `7a02fed4`, trunk `083e78e4` |
| Harness | `5031dc16`, clean; scenario revision 4; `--journeys landing,files` |
| Chrome | 152.0.7977.83, headless |
| Pull request catalog | Absent at each condition’s first warm-up start, then 377 in all |

This record is committed on the branch after `main` was merged into it; the measured
candidate is `10d659ae`.

## Results

| Reading | Control | Candidate | `compare` or pair ratios |
| --- | ---: | ---: | --- |
| Revalidated requests on `landing.reload`, all families (decides) | 43 (43–43) | 1 (1–1) | 0.023 in every pair |
| `plugin_static` / `kpress_static` revalidated on reload | 29 / 13 | 0 / 0 | ranges apart |
| Reload painted ready ms (guard) | 158.1 (143.6–224.4) | 124.7 (107.5–125.7) | 0.73x (0.56–0.87), 2 of 4 beyond: lower, a result |
| Reload blank frames | 7 (6–11) | 5 (4–5) | 0.64x (0.45–0.83), 3 of 4 beyond: lower |
| Large-source revisit, longest task ms (declared check) | 120 (109–143) | 121 (109–135) | 0.944–1.015: no detected difference |
| Cold Markdown painted ready ms (predicted no difference) | 340.8 (287.6–411.3) | 315.2 (299.1–346.1) | 0.93x (0.84–1.04): no detected difference |
| Cold Markdown shell tools ready ms | 415.9 (320.9–511.4) | 357.0 (332.5–379.5) | 0.88x (0.74–1.04), 2 of 4 beyond, lower, ranges overlapping |
| Cold JSON painted ready ms | 63.4 (63.0–64.1) | 80.9 (79.6–88.9) | 1.27x (1.25–1.41), 1 of 4 beyond: higher, ranges apart |
| Cold JSON frames to ready | 2 | 3 | 1.50x, 4 of 4 beyond: wrong way |
| Cold image frames to ready | 3 | 4 (3–4) | 1.33x (1.00–1.33), 3 of 4 beyond, ranges overlapping: wrong way |

The one revalidation left on reload is a data route, as in exp-060. The cold Markdown
landing’s blank and placeholder frames are not wrong-way results.

## Accept Rule

1. **The median moved in the predicted direction:** yes, 43 to 1.
2. **The ranges do not overlap, at four runs per condition:** yes.
3. **Nothing else moved the wrong way without being accounted for:** not met.
   `compare` (exit 1) lists ten wrong-way results:
   - **`files.cold.json`, five:** painted ready, ready, ready after the last input,
     frames to ready (2 → 3 in all four pairs), and settled time.
     The view is one frame later in every pair.
     Both builds made the same requests: two data requests and the structured plugin’s
     four files. The app’s own `fileNavigation:selectToReady` span is 51.9, 53.8, 52.6,
     and 55.3 ms in the control against 85.4, 63.6, 70.4, and 65.7 ms in the candidate,
     so the time is spent before the app calls the view ready.
     exp-060’s candidate showed the same level (80.8 ms, 80.4–81.4), but its control
     ranged 64.8–80.8 then, so no result showed.
     **Not accounted for.**
   - **`files.cold.image`, four:** ready ms, frames to ready, blank frames, and blank
     ms, each one frame later in two or three pairs, under overlapping ranges.
     Its `selectToReady` span did not move (34.1–38.3 against 34.0–36.9 ms), so the
     frame is spent after the app is ready, on the image itself.
     **Not accounted for.**
   - **`files.revisit.markdown_large`, one:** frames to ready 3 (3–4) → 4 (3–5), 2 of 4
     pairs beyond, under overlapping ranges; painted ready shows no detected difference.
     **Not accounted for.**
4. **Complexity:** as in exp-060, worth it for what H87 buys on reload, if the cold-view
   frame belongs to something else or can be removed.

**Verdict:** unresolved, as exp-060 was.
The declared check and the prediction for the cold landing both came out as stated.
The third clause now waits on the cold JSON and image frame.
A diagnostic that reads each request’s server time on `files.cold.json` and
`files.cold.image` in both builds would split that frame between H87’s stamped handlers
and mb-rldd’s timing middleware.
Those are the candidate’s `Server-Timing` and the DevTools response timing.

## What Did Not Move

- exp-060’s open result: the large-source revisit’s longest task, 120 against 121 ms.
  Without H89 it shows no difference.
- The cold Markdown landing: painted ready, blank frames, and placeholder frames show no
  detected difference, as predicted.
- Requests per reload, 109 (106–110) against 108 (108–108); every other file
  transition’s painted ready.

## Limits

- **WebKit relaunch.** #378’s `WKWebView` probe found that, over three or more runs, the
  only regime a control can hold, judged by age, is “fresh”.
  In that regime stamped `/static/` assets come from cache at a relaunch.
  So in WebKit, H87’s saving on stamped assets reads 0 against 0 by construction, and
  only the families that were `no-cache` (plugin and KPress assets) can show a
  difference. #378’s `--stale-assets` flag gives a diagnostic stale control.
  This round did not take the WebKit reading.
- **Low Power Mode** was set for AC and battery alike when checked after this round
  (`pmset -g custom`), and the power log records no change to it.
  It was very probably on for exp-060 and exp-062 too.
  Both conditions shared it.
- **`/raw`** revalidates, so a revisited image costs one 304. These journeys do not
  revisit an image.
- **`raf_frame_gaps`** is off in Chrome and played no part.

## Reproducing

From this directory, with `H` a checkout of the harness at `5031dc16`:

```shell
node exp-060-062-load-filter.mjs exp-083-landing-files-samples.jsonl --out /tmp/judged-083.jsonl
node "$H/explorations/performance-loop/transitions.mjs" compare /tmp/judged-083.jsonl \
  --control control --candidate candidate --expect landing.reload:painted_ready_ms:lower
node exp-060-062-figures.mjs "$H" /tmp/judged-083.jsonl
```

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->

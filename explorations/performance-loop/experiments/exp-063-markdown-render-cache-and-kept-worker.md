---
title: Markdown Render Cache and Kept Worker
softschema:
  contract: metabrowser.loadtime:Experiment/v1
  schema: experiment.schema.yaml
  envelope: experiment
  status: enforced
experiment:
  id: exp-063
  title: Markdown Render Cache and Kept Worker
  date: "2026-11-12"
  hypotheses:
    - H90
  subject:
    corpus: Standalone clone of this repository at 7a02fed4 (corpus v2), clean; the same series as exp-061.
    corpus_files: 1286
    host_cpu: 10 CPUs
    host_system: Darwin 25.5.0 arm64, Node 24.19.0
    browser: Headless Chrome 152.0.7977.83 over the DevTools Protocol, a fresh profile per journey, trusted pointer and key input.
    viewport: 1440x900
    cold: false
  method:
    runs_per_condition: 6
    interleaved: true
    control: metab 0.12.1.dev165+9903292 (+165 commits, 099032928), the editable control checkout at origin/main 09903292, clean at the start and end of every run, a fresh server process per run.
    candidate: metab 0.12.1.dev165+9903292 (+174 commits, 4b0e12332), the editable checkout of claude/perf-caches at 4b0e1233, clean at the start and end of every run, a fresh server process per run. It carries this round's change and exp-061's, which touch disjoint code.
    record: exp-061-transition-samples.jsonl
  results:
    - metric: requests_kpress.files.revisit.markdown_small
      control_median: 1
      candidate_median: 0
      control_range: [1, 1]
      candidate_range: [0, 0]
      overlapping: false
    - metric: requests_kpress.files.revisit.markdown_large
      control_median: 1
      candidate_median: 0
      control_range: [1, 1]
      candidate_range: [0, 0]
      overlapping: false
    - metric: requests_kpress.files.history_back
      control_median: 1
      candidate_median: 0
      control_range: [1, 1]
      candidate_range: [0, 0]
      overlapping: false
    - metric: requests_kpress.files.history_forward
      control_median: 1
      candidate_median: 0
      control_range: [1, 1]
      candidate_range: [0, 0]
      overlapping: false
    - metric: post_body_bytes.files.revisit.markdown_small
      control_median: 19168
      candidate_median: 0
      control_range: [19168, 19168]
      candidate_range: [0, 0]
      overlapping: false
    - metric: post_body_bytes.files.revisit.markdown_large
      control_median: 191142
      candidate_median: 0
      control_range: [191142, 191142]
      candidate_range: [0, 0]
      overlapping: false
    - metric: post_body_bytes.files.history_back
      control_median: 19168
      candidate_median: 0
      control_range: [19168, 19168]
      candidate_range: [0, 0]
      overlapping: false
    - metric: post_body_bytes.files.history_forward
      control_median: 191142
      candidate_median: 0
      control_range: [191142, 191142]
      candidate_range: [0, 0]
      overlapping: false
    - metric: requests_plugin.files.revisit.markdown_small
      control_median: 3
      candidate_median: 0
      control_range: [3, 3]
      candidate_range: [0, 0]
      overlapping: false
    - metric: painted_ready_ms.files.revisit.markdown_small
      control_median: 62.7
      candidate_median: 45.2
      control_range: [62.0, 64.5]
      candidate_range: [44.4, 47.1]
      overlapping: false
    - metric: painted_ready_ms.files.revisit.markdown_large
      control_median: 145.9
      candidate_median: 114.2
      control_range: [130.6, 147.0]
      candidate_range: [111.9, 129.6]
      overlapping: false
    - metric: painted_ready_ms.files.history_back
      control_median: 40.1
      candidate_median: 29.8
      control_range: [37.2, 41.3]
      candidate_range: [23.8, 38.6]
      overlapping: true
    - metric: painted_ready_ms.files.history_forward
      control_median: 126.2
      candidate_median: 113.8
      control_range: [124.1, 142.6]
      candidate_range: [103.0, 120.9]
      overlapping: false
    - metric: long_task_max_ms.files.revisit.markdown_large
      control_median: 0
      candidate_median: 0
      control_range: [0, 0]
      candidate_range: [0, 0]
      overlapping: true
    - metric: long_task_max_ms.files.history_forward
      control_median: 0
      candidate_median: 0
      control_range: [0, 54]
      candidate_range: [0, 0]
      overlapping: true
    - metric: painted_ready_ms.keyboard.up_revisit.1
      control_median: 44.3
      candidate_median: 23.0
      control_range: [43.4, 55.2]
      candidate_range: [19.6, 27.2]
      overlapping: false
    - metric: ready_ms.keyboard.down_cold.1
      control_median: 35.0
      candidate_median: 41.7
      control_range: [28.3, 43.6]
      candidate_range: [27.9, 44.9]
      overlapping: true
    - metric: settled_ms.views.markdown.revisit_2
      control_median: 1.4
      candidate_median: 2.3
      control_range: [1.3, 3.0]
      candidate_range: [1.4, 2.5]
      overlapping: true
  complexity:
    lines_changed: 474
    new_dependencies: []
    new_failure_modes:
      - A render whose server inputs change while the page is open without changing the file's identity, such as a server restarted with other trust flags, is served from the page's copy until the shell drops the envelope.
      - A kept render over 52,335 characters is placed after the input's first paint, so the click's first frame shows the old document marked pending, as it did before the change.
    notes: 474 changed lines of product code (430 added, 44 removed) in builtin_plugins/markdown/rendered.js and markdown-worker-client.js, none in an eager startup script.
  verdict:
    decision: unresolved
    primary_metric: requests_kpress and post_body_bytes on files.revisit.markdown_small and .markdown_large and files.history_back and .history_forward, and requests_plugin on files.revisit.markdown_small
    reason: "All nine deciding metrics moved as predicted with ranges apart, painted ready on the four named transitions moved the right way or not at all, and the pilot's long tasks are gone (0 against 0). The declared guard fails: keyboard.down_cold.1 (ready and frames to ready), keyboard.down_cold.3 (frames to ready), and views.markdown.revisit_2 (settled) are each higher in 2 or 3 of 6 pairs under overlapping ranges, which compare counts as wrong-way and nothing here accounts for."
    commit: 4b0e1233
---
**Status:** Official round, on harness revision 4. H90: **unresolved**. Six interleaved
pairs, twelve valid runs, none refused: the series of
[exp-061](exp-061-commit-comparison-cache-and-git-route-memo.md).
Every deciding metric moved as predicted, and the declared guard did not hold; see
[Verdict](#verdict).

## Why This Round

H90, in the hypothesis registry of the research branch’s load-time plan (“Apparent Speed
and Layout Stability”), says two things are thrown away.
A Markdown revisit uploads its source and downloads its render again, and leaving
Markdown discards the preprocessing Worker.
A render cache keyed by content identity and a kept Worker would make revisits
request-free. The bead is `mb-mbd3`.

The change keeps each render, with its preparation’s diagnostics, on the file envelope
that the shell’s file cache holds.
It is keyed by path, `mtime_hash`, view, profile, table-of-contents option, and
preparation. A kept render of up to 52,335 characters is placed in the input’s own task,
and a larger one after the input’s first paint (`60a4e623`, and review round 1). The
Worker is kept for 60 s after its last reference, and page hide ends it early.

**One series measured two rounds.** The candidate carries this round’s change and
exp-061’s (H88). The two touch disjoint code, and this round reads the transitions with
a Markdown subject. Both artifacts read the same
[samples](exp-061-transition-samples.jsonl).
The regime, identities, load, and guards of the series are in exp-061 and are not
repeated here.

## Protocol

Declared before the series started, and not changed after.
Decided by the transition scenario.
All of the following must hold:

- `requests_kpress` lower on `files.revisit.markdown_small`,
  `files.revisit.markdown_large`, `files.history_back`, and `files.history_forward`
  (counts on their ranges: 1 to 0 expected);
- `post_body_bytes` lower on the same four (the upload);
- `requests_plugin` lower on `files.revisit.markdown_small` (no Worker preparation: 3 to
  0 expected).

Painted ready on the four was predicted to be no worse, with no wrong-way result; a
lower one was not required.
Guards:

- no wrong-way `long_task_max_ms` on `files.revisit.markdown_large` and
  `files.history_forward`, the pilot’s regression, which `60a4e623` addresses;
- no wrong-way result on any other `files.*`, `keyboard.*`, or `views.markdown.*`
  transition, or on `main.*_to_files`;
- every run valid.

The `compare` call, with this round’s nine expectations, is in exp-061’s protocol.

## Results

Every number here is from `compare` over the committed samples: times as median and
range over six runs, and pair ratios as candidate over control.

### Revisits and History Steps

| Transition | Subject | Painted ready ms, control → candidate | Pair ratios | KPress | POST bytes | Plugin modules |
| --- | --- | --- | --- | --- | --- | --- |
| `files.revisit.markdown_small` | `README.md` | 62.7 (62.0–64.5) → 45.2 (44.4–47.1) | 0.72x (0.71–0.74), 6 of 6 beyond | 1 → 0 | 19,168 → 0 | 3 → 0 |
| `files.revisit.markdown_large` | `docs/design-system.md` | 145.9 (130.6–147.0) → 114.2 (111.9–129.6) | 0.83x (0.77–0.89), 0 of 6 beyond | 1 → 0 | 191,142 → 0 | 0 → 0 |
| `files.history_back` | `README.md` | 40.1 (37.2–41.3) → 29.8 (23.8–38.6) | 0.74x (0.59–0.99), 3 of 6 beyond | 1 → 0 | 19,168 → 0 | 0 → 0 |
| `files.history_forward` | `docs/design-system.md` | 126.2 (124.1–142.6) → 113.8 (103.0–120.9) | 0.86x (0.76–0.97), 1 of 6 beyond | 1 → 0 | 191,142 → 0 | 0 → 0 |

Each count fell to zero in every candidate run, ranges apart.

- `files.revisit.markdown_small`’s painted ready is lower, apart, and beyond the
  tolerance in six of six pairs: a result.
- `files.revisit.markdown_large`’s is lower and apart with every pair within 1.3x, not a
  result.
- `files.history_back`’s ranges overlap with three pairs lower beyond the tolerance.
- `files.history_forward`’s is lower and apart with one pair beyond, a rerun owed in the
  right direction.

None is wrong-way.

Ready was lower and apart on all of these:

- `files.revisit.markdown_small`: 56.2 (52.5–58.2) → 32.3 (30.2–36.6) ms;
- `files.history_back`: 35.2 (31.8–35.4) → 22.9 (21.9–25.7) ms;
- `files.revisit.markdown_large`: 130.2 (124.3–140.1) → 103.8 (98.1–116.9) ms, with
  frames to ready 3 (3–4) → 2.

Blank and visible placeholder frames were 0 on both builds on all four.

### The Pilot’s Long Tasks

`long_task_max_ms` on `files.revisit.markdown_large` was 0 (0–0) on both builds, against
the pilot’s 0 → 84 ms.
On `files.history_forward` it was 0 (0–54) → 0 (0–0), with two pairs lower and none
higher. The kept large render no longer runs as one long task in the input’s turn.

### Other Markdown Transitions

| Transition | Painted ready ms, control → candidate | Pair ratios | Counts |
| --- | --- | --- | --- |
| `keyboard.up_revisit.1` | 44.3 (43.4–55.2) → 23.0 (19.6–27.2) | 0.49x (0.36–0.62), 6 of 6 beyond | KPress 1 → 0, plugin 3 → 0, POST 3,105 → 0 |
| `keyboard.up_revisit.2` | 44.0 (39.6–54.9) → 25.8 (25.4–29.3) | 0.59x (0.49–0.74), 6 of 6 beyond | KPress 1 → 0 |
| `main.pulls_to_files.first` | 63.4 (62.8–115.1) → 46.9 (42.6–48.4) | 0.74x (0.40–0.75), 6 of 6 beyond | KPress 1 → 0, plugin 3 → 0, POST 42,904 → 0, blank frames 2 (2–5) → 1 |
| `main.pulls_to_files.again` | 64.6 (62.5–79.2) → 46.0 (45.2–47.4) | 0.72x (0.58–0.73), 6 of 6 beyond | KPress 1 → 0, plugin 3 → 0, POST 42,904 → 0 |
| `main.commits_to_files.first` | 77.8 (62.8–80.4) → 54.2 (45.8–63.0) | 0.74x (0.61–0.80), 4 of 6 beyond | KPress 1 → 0, plugin 3 → 0, POST 42,904 → 0 |
| `main.commits_to_files.again` | 62.9 (61.7–94.8) → 46.3 (44.7–48.6) | 0.72x (0.50–0.79), 5 of 6 beyond | KPress 1 → 0, plugin 3 → 0, POST 42,904 → 0, blank frames 2 (2–4) → 1 |
| `main_subject.pulls_to_files` | 64.4 (63.4–191.7) → 47.7 (47.2–48.4) | 0.75x (0.25–0.76), 6 of 6 beyond | KPress 1 → 0, plugin 3 → 0, POST 42,904 → 0 |
| `main_subject.commits_to_files` | 65.3 (64.3–95.2) → 55.4 (47.6–63.0) | 0.85x (0.51–0.97), 3 of 6 beyond | KPress 1 → 0, plugin 3 → 0, POST 42,904 → 0 |
| `files.hover_click.markdown` | 64.0 (63.5–79.7) → 63.5 (63.3–65.5) | 1.00x (0.80–1.03), 0 of 6 beyond | KPress 1 → 1, POST 59,712 → 59,712 |
| `views.markdown.first`, `.revisit`, `.revisit_2` | 29.8, 30.0, 29.9 → 29.4, 29.9, 29.5 | 0.97x to 1.00x, 0 of 6 beyond | none on either build |
| `files.cold.markdown_large` | 187.3 (179.0–196.8) → 180.1 (162.1–197.6) | 0.96x (0.91–1.10), 0 of 6 beyond | no detected difference |

The plugin-module counts include both halves of the change: a revisit that finds its
render needs no Worker, and a Worker kept from the previous Markdown document needs no
modules. This series does not separate them.
`files.hover_click.markdown` opens a file not seen before, so it renders on both builds.

### The Guard’s Wrong-Way Flags

`compare` lists four wrong-way results in this round’s guard set.
In each the ranges overlap and two or three pairs are higher beyond 1.3x; none has its
ranges apart and none is on painted ready:

| Transition | Metric | Control → candidate | Pair ratios | Higher in pairs |
| --- | --- | --- | --- | --- |
| `keyboard.down_cold.1` | ready ms | 35.0 (28.3–43.6) → 41.7 (27.9–44.9) | 1.08x (0.93–1.40) | 5, 6 |
| `keyboard.down_cold.1` | frames to ready | 2 (2–3) → 2.5 (2–3) | 1.00x (0.67–1.50) | 4, 5 |
| `keyboard.down_cold.3` | frames to ready | 2 (2–3) → 2 (2–3) | 1.00x (0.67–1.50) | 2, 4 |
| `views.markdown.revisit_2` | settled ms | 1.4 (1.3–3.0) → 2.3 (1.4–2.5) | 1.38x (0.70–1.92) | 1, 5, 6 |

Painted ready on the same transitions showed no detected difference:

- `keyboard.down_cold.1`: 49.0 (42.7–56.4) → 55.9 (41.5–57.8);
- `keyboard.down_cold.3`: 44.0 (40.7–56.6) → 42.3 (40.3–56.9);
- `views.markdown.revisit_2`: 29.9 (25.7–30.2) → 29.5 (27.9–30.3).

On the journeys neither change addresses, `compare` lists flags of the same kind: 10
higher and 25 lower among 1,085 judged comparisons (exp-061 lists them).
That base rate suggests these four are noise under this load, but it is a suggestion and
not an account of any one of them.
The cold keyboard steps open files the page has not rendered, so the render cache cannot
answer them. The kept Worker and the new render path are on them, and nothing measured
here separates their cost.

## Verdict

**H90: unresolved.** Decided by the transition scenario under the accept rule:

1. Moved as predicted: yes, all nine deciding metrics.
   - KPress requests went 1 → 0 on each of the four transitions.
   - POST bytes went 19,168 → 0 and 191,142 → 0 on the README and design-system steps.
   - Plugin modules went 3 → 0 on `files.revisit.markdown_small`.

   Painted ready on the four moved the right way or did not move.

2. Ranges apart at six runs: yes, all nine.

3. Nothing else wrong-way unaccounted for: **no.** The long-task guard holds (0 against
   0, and 0 (0–54) against 0). The declared guard on `keyboard.*` and `views.markdown.*`
   has the four flags above, none accounted for.

4. Complexity judgment: 474 changed lines in two lazily loaded Markdown modules, no
   dependency, and one stated staleness, a server restarted with other trust flags.
   In return, a revisit or history step no longer uploads 19 to 191 KB or round-trips a
   render, and a small revisit paints in 45 instead of 63 ms.
   Worth it, if the guard’s flags are shown to be noise.

What would resolve it: a declared rerun of the flagged pairs, as the runbook prescribes,
or an A/A split at this n that sets the base rate for two-of-six flags.

## Pilot

The pilot ran on 2026-11-12 on harness revision 1 (`22af6103`), with five pairs.
Its candidate was `9e1630db`. That build placed every kept render in the input’s own
task, which on `docs/design-system.md` made an 84 ms long task and delayed the click’s
first paint to 96 ms.
`60a4e623` changed that, and this round shows the long task gone.
Its painted-ready times came from a harness revision whose crediting review A of the
harness found unsound, and are not evidence either way.
Its request counts agreed with this round’s. Its records are exp-061’s pilot files.

## Limits

- Headless Chrome only; the native app’s WebKit is not measured, and WebKit has no Long
  Tasks or Long Animation Frames API.
- `compare` does not judge Event Timing, so the click’s first-paint delay that the pilot
  found is judged here only through the long task.
- The Worker keep-alive’s own effect is inseparable from the render cache here.
  That effect is a Markdown file opened cold after a file of another kind, and the
  scenario has no such transition.
- The render cache’s memory was not measured in a browser; its bound is the render JSON
  measured over this repository’s 269 Markdown files.
- H90 is registered in the plan on the research branch, not yet in this branch’s plan.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->

---
title: Markdown Render Cache and Kept Worker, Confirmation
softschema:
  contract: metabrowser.loadtime:Experiment/v1
  schema: experiment.schema.yaml
  envelope: experiment
  status: enforced
experiment:
  id: exp-082
  title: Markdown Render Cache and Kept Worker, Confirmation
  date: "2026-11-13"
  hypotheses:
    - H90
  subject:
    corpus: Standalone clone of this repository at 7a02fed4 (corpus v2), clean; the same series as exp-081.
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
    candidate: metab 0.12.1.dev165+9903292 (+179 commits, ed42364d4), the editable checkout of claude/perf-caches at ed42364d, clean at the start and end of every run, a fresh server process per run. It carries exp-063's candidate and 2bb598b1, whose render cache store no longer walks every kept render.
    record: exp-081-transition-samples.jsonl
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
      control_median: 64.2
      candidate_median: 31.3
      control_range: [63.1, 65.4]
      candidate_range: [29.9, 45.8]
      overlapping: false
    - metric: painted_ready_ms.files.revisit.markdown_large
      control_median: 145.3
      candidate_median: 112.5
      control_range: [130.6, 145.5]
      candidate_range: [112.2, 129.6]
      overlapping: false
    - metric: painted_ready_ms.files.history_back
      control_median: 40.4
      candidate_median: 23.5
      control_range: [40.1, 52.1]
      candidate_range: [23.4, 25.2]
      overlapping: false
    - metric: painted_ready_ms.files.history_forward
      control_median: 124.3
      candidate_median: 91.0
      control_range: [120.7, 124.9]
      candidate_range: [90.2, 119.9]
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
      control_range: [0, 0]
      candidate_range: [0, 0]
      overlapping: true
    - metric: settled_ms.main.files_to_pulls.again
      control_median: 6.6
      candidate_median: 12.4
      control_range: [6.3, 6.7]
      candidate_range: [7.1, 13.7]
      overlapping: false
  complexity:
    lines_changed: 480
    new_dependencies: []
    new_failure_modes:
      - A render whose server inputs change while the page is open without changing the file's identity, such as a server restarted with other trust flags, is served from the page's copy until the shell drops the envelope.
      - A kept render over 52,335 characters is placed after the input's first paint, so the click's first frame shows the old document marked pending, as it did before the change.
    notes: 480 changed lines of product code against the base (436 added, 44 removed) in builtin_plugins/markdown/rendered.js and markdown-worker-client.js, none in an eager startup script.
  verdict:
    decision: unresolved
    primary_metric: requests_kpress and post_body_bytes on files.revisit.markdown_small and .markdown_large and files.history_back and .history_forward, and requests_plugin on files.revisit.markdown_small
    reason: "All nine deciding metrics moved as predicted with ranges apart; painted ready on the four named transitions is lower, three of them beyond 1.3x; no long task on either build; exp-063's guard flags did not recur, and this round's two in the declared guard are explained by their request lists. One wrong-way result is unaccounted for: main.files_to_pulls.again's settle time, 6.6 to 12.4 ms with ranges apart, on a transition outside the declared guard that leaves a Markdown document, where the round cannot show the Worker release or the render cache uninvolved."
    commit: ed42364d
---
**Status:** Confirmation round of
[exp-063](exp-063-markdown-render-cache-and-kept-worker.md), on harness revision 4. H90:
**unresolved.** It is the series of
[exp-081](exp-081-commit-comparison-cache-and-git-route-memo-confirmation.md): three
pairs kept under the load rule, nine excluded, all 24 runs valid.

## Why This Round

exp-063 met all nine deciding metrics and failed its guard on four two-of-six flags.
After it, the render cache’s store stopped walking every kept render (`2bb598b1`), which
this round measures.
exp-081 gives the shared protocol, the load rule and its exclusions, the identities, and
the load. This record gives H90’s criteria and its verdict.

## Protocol

Declared before the series, unchanged from exp-063 except for the accept rule, which is
the runbook’s standard one:

- ranges apart with two or more pairs beyond 1.3x is a result;
- two or more pairs beyond under overlapping ranges must be explained with evidence;
- a guard flag is resolved the same way.

**Deciding, all nine:**

- `requests_kpress` and `post_body_bytes` lower on `files.revisit.markdown_small`,
  `files.revisit.markdown_large`, `files.history_back`, and `files.history_forward`;
- `requests_plugin` lower on `files.revisit.markdown_small`.

**Painted ready on those four:** predicted no worse.

**Guards:**

- no unexplained wrong-way `long_task_max_ms` on `files.revisit.markdown_large` and
  `files.history_forward`;
- none on any other `files.*`, `keyboard.*`, `views.markdown.*`, or `main.*_to_files`
  transition;
- all runs valid.

Three kept pairs are the accept rule’s floor.
A decision that would rest on overlapping ranges is called “no detectable effect”.

## Results

Every number here is from `compare` over the kept samples
([exp-081-transition-samples.jsonl](exp-081-transition-samples.jsonl)), as candidate
over control, except the store benchmark’s.

### The Deciding Transitions

| Transition | Painted ready ms, control → candidate | Pair ratios | KPress | POST bytes | Plugin modules |
| --- | --- | --- | --- | --- | --- |
| `files.revisit.markdown_small` | 64.2 (63.1–65.4) → 31.3 (29.9–45.8) | 0.50x (0.46–0.71), 3 of 3 beyond | 1 → 0 | 19,168 → 0 | 3 → 0 |
| `files.revisit.markdown_large` | 145.3 (130.6–145.5) → 112.5 (112.2–129.6) | 0.86x (0.77–0.89), 0 of 3 beyond | 1 → 0 | 191,142 → 0 | 0 → 0 |
| `files.history_back` | 40.4 (40.1–52.1) → 23.5 (23.4–25.2) | 0.58x (0.48–0.59), 3 of 3 beyond | 1 → 0 | 19,168 → 0 | 0 → 0 |
| `files.history_forward` | 124.3 (120.7–124.9) → 91.0 (90.2–119.9) | 0.75x (0.73–0.96), 2 of 3 beyond | 1 → 0 | 191,142 → 0 | 0 → 0 |

- All nine counts fell to zero in every candidate run, ranges apart, and `compare` met
  each expectation.
- Painted ready is lower on all four: three are results, and `markdown_large` is apart
  with every pair within 1.3x.
- `long_task_max_ms` was 0 on both builds on all four.

### Other Markdown Transitions

| Transition | Painted ready ms, control → candidate | Pair ratios |
| --- | --- | --- |
| `keyboard.up_revisit.1` | 55.9 (55.6–56.6) → 22.5 (20.9–26.2) | 0.40x (0.37–0.47), 3 of 3 beyond |
| `keyboard.up_revisit.2` | 44.2 (43.3–44.7) → 25.9 (22.1–41.4) | 0.58x (0.51–0.94), 2 of 3 beyond |
| `main.pulls_to_files.first` | 63.1 (62.9–64.0) → 47.9 (47.7–48.3) | 0.76x (0.75–0.77), 3 of 3 beyond |

exp-063’s four guard flags did not recur:

- `keyboard.down_cold.1`’s painted ready showed no detected difference, 54.0 → 53.7 ms.
- `keyboard.down_cold.3`’s frames to ready went lower, 3 (2–3) → 2.
- `views.markdown.revisit_2`’s settle time came apart in one pair only, which `compare`
  lists without calling it wrong-way.

### Wrong-Way Results and Their Evidence

`compare` listed 13 wrong-way results.
Eight are exp-081’s, on the Commits transitions, and none of them is on a path this
round’s code runs: their requests include no KPress render and no Markdown module, and
the commit diff’s Markdown view is `diff-markdown.js`, which imports nothing of the
Markdown plugin. The other five:

**In the declared guard:**

- **`files.cold.image`, frames to ready 3 (3–4) → 4 (3–4).** Ranges overlap, with 2 of 3
  pairs beyond.
  - All six runs made the same requests on both builds: the file envelope, the image
    plugin’s two modules, the raw image, and the background catalog page.
  - The image plugin is not part of this change.
  - Painted ready shows no detected difference.
  - **Explained:** no changed code is on the path, and at three runs the frames are no
    detectable effect.
- **`main.commits_to_files.again`, network data requests 1 → 2.**
  - The control’s one is the KPress render of `docs/architecture.md`.
  - The candidate makes no render request: the render cache answers it.
  - The candidate’s two are the background walk’s catalog page (`github/pulls` and
    `pull-cores-prepare`, class background), which falls inside this transition’s
    window.
  - **Explained** by the request lists: the render request is gone, and the extra
    requests are the walk’s.

**Outside the declared guard:**

- **`views.json.revisit_2`, settle 2.9 (2.9–3.1) → 5.2 (1.9–5.3) ms.** Ranges overlap,
  with 2 of 3 pairs beyond.
  - It is a view switch on `package-lock.json`, with only background requests.
  - No Markdown code draws a JSON view.
  - No detectable effect.
- **`main.files_to_pulls.first`, settle 11.5 (9.2–21.2) → 17.0 (16.6–18.8) ms.** Ranges
  overlap, with 2 of 3 pairs beyond.
  No detectable effect, but not explained.
- **`main.files_to_pulls.again`, settle 6.6 (6.3–6.7) → 12.4 (7.1–13.7) ms.** Ranges
  apart, with 2 of 3 pairs beyond: a result, and **not explained.**
  - Both builds made the same requests, and painted ready shows no detected difference
    (30.5 → 30.9 ms).
  - The transition leaves `docs/architecture.md` for the Pulls tab.
    Whether the Markdown mount is disposed there, and so whether the Worker’s release
    runs, was not traced.
  - In the excluded pairs, which are not judged, the settle times were 7.0 to 14.7 ms on
    the control and 6.0 to 13.8 ms on the candidate.

### The Render Store

`2bb598b1`’s benchmark, cited by `rendered.js` beside its constant:

- **Method:** Node 24 on this machine, on 2026-11-12, at a one-minute load of 14 to 83.
  One lookup that misses and one store per step, 300 steps at each count of kept
  renders.
- **Before the change,** while each store checked every kept render for a collected
  envelope: 29 µs at 2 kept renders, 56 µs at 300, 1.7 ms at 1,000, and 2.3 ms at 4,000.
- **After it:** 1.5 to 7.6 µs at each of those counts, in two runs.

The benchmark was a scratch script and is not committed.
The mount behavior test holds the change: a store with 1,000 renders kept checks none of
them, 1,000 before the change.
The round’s journeys keep only a few renders, so the change does not show in the series.

## Verdict

**H90: unresolved.** Decided by the transition scenario under the standard rule.

1. Moved as predicted: yes, all nine deciding metrics.
2. Ranges apart: yes, all nine.
   Painted ready on the four named transitions is lower, three of them beyond the
   tolerance.
3. Nothing else wrong-way unaccounted for: **no, by one result.**
   - The declared guard holds: no long task on either build, and its two flags are
     explained by their request lists.
   - `main.files_to_pulls.again`’s settle time came apart.
     It is outside the declared guard, on a transition that leaves a Markdown document,
     and the round cannot show this change uninvolved.
4. Complexity judgment: 480 changed lines in two lazily loaded Markdown modules, no
   dependency, and one stated staleness.
   In return, every Markdown revisit and history step loses its 19 to 191 KB upload and
   its render round trip and paints sooner.
   Worth it, if that settle time is shown unrelated.

What would resolve it: trace whether leaving a Markdown document for the Pulls tab runs
the render cache or the Worker release, or rerun that transition under a declared rule.

## Changes After the Measured Candidate

After `ed42364d`, the branch merged `main` (`6bff1e88`) and committed exp-081’s probe
script (`021f1f36`). Neither changes the Markdown plugin.

## Limits

- Three kept pairs, the accept rule’s floor.
- Headless Chrome only.
  WebKit has no Long Tasks or Long Animation Frames API.
- The Worker keep-alive’s own effect, a Markdown file opened cold after a file of
  another kind, is not a transition the scenario has.
- The render cache’s memory was not measured in a browser.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->

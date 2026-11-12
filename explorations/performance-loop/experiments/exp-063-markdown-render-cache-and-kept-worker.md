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
    corpus: Detached checkout of this repository at 7a02fed4, frozen and clean; the same series as exp-061.
    corpus_files: 1286
    host_cpu: 10 CPUs
    host_system: Darwin 25.5.0 arm64, Node 24.19.0
    browser: Headless Chrome 152.0.7977.83 over the DevTools Protocol, a fresh profile per journey, trusted pointer and key input.
    viewport: 1440x900
    cold: false
  method:
    runs_per_condition: 5
    interleaved: true
    control: metab 0.12.1.dev165+9903292 (+165 commits, 099032928), the editable control checkout at origin/main 09903292, clean, one server process per run.
    candidate: metab 0.12.1.dev165+9903292 (+169 commits, 9e1630db7), the editable checkout of claude/perf-caches at 9e1630db, clean, one server process per run. It carries this round's commit (9e1630db) and exp-061's (3594c291, a627d915, 45f2b8d3), which touch disjoint code and metrics.
    record: exp-061-transition-samples.jsonl
  results:
    - metric: requests_kpress.files.revisit.markdown_large
      control_median: 1
      candidate_median: 0
      control_range: [1, 1]
      candidate_range: [0, 0]
      overlapping: false
    - metric: requests_kpress.files.revisit.markdown_small
      control_median: 1
      candidate_median: 0
      control_range: [1, 1]
      candidate_range: [0, 0]
      overlapping: false
    - metric: requests_plugin.files.revisit.markdown_small
      control_median: 3
      candidate_median: 0
      control_range: [3, 3]
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
    - metric: painted_ready_ms.files.revisit.markdown_large
      control_median: 128.9
      candidate_median: 114.7
      control_range: [113.3, 184.6]
      candidate_range: [113.4, 147.2]
      overlapping: true
    - metric: painted_ready_ms.files.revisit.markdown_small
      control_median: 62.5
      candidate_median: 63
      control_range: [46.4, 116.8]
      candidate_range: [38.6, 64.4]
      overlapping: true
    - metric: painted_ready_ms.files.history_back
      control_median: 41.6
      candidate_median: 58.9
      control_range: [41.1, 72.8]
      candidate_range: [41.7, 60.3]
      overlapping: true
    - metric: painted_ready_ms.files.history_forward
      control_median: 109.7
      candidate_median: 109.4
      control_range: [105.5, 155.6]
      candidate_range: [92.2, 125.1]
      overlapping: true
    - metric: painted_ready_ms.keyboard.up_revisit.1
      control_median: 44.4
      candidate_median: 28.4
      control_range: [40.7, 50.2]
      candidate_range: [27.4, 29.9]
      overlapping: false
    - metric: painted_ready_ms.keyboard.up_revisit.2
      control_median: 44.3
      candidate_median: 28.2
      control_range: [39.8, 59.9]
      candidate_range: [19.2, 28.3]
      overlapping: false
    - metric: painted_ready_ms.main.pulls_to_files.first
      control_median: 63.9
      candidate_median: 30.1
      control_range: [63.4, 65.2]
      candidate_range: [29.9, 30.6]
      overlapping: false
    - metric: blank_frames.main.pulls_to_files.first
      control_median: 2
      candidate_median: 0
      control_range: [2, 2]
      candidate_range: [0, 0]
      overlapping: false
    - metric: long_task_max_ms.files.revisit.markdown_large
      control_median: 0
      candidate_median: 84
      control_range: [0, 0]
      candidate_range: [83, 93]
      overlapping: false
    - metric: long_task_max_ms.files.history_forward
      control_median: 0
      candidate_median: 81
      control_range: [0, 0]
      candidate_range: [80, 84]
      overlapping: false
    - metric: event_timing_max_ms.files.revisit.markdown_large
      control_median: 16
      candidate_median: 96
      control_range: [16, 56]
      candidate_range: [96, 120]
      overlapping: false
  complexity:
    lines_changed: 400
    new_dependencies: []
    new_failure_modes:
      - A kept render is placed in the input's own task, so on a large document the first paint after the click is the finished document at about 96 ms rather than click feedback at 16 ms.
      - A render whose server inputs change while the page is open without changing the file's identity, such as a server restarted with other trust flags, is served from the page's copy until the shell drops the envelope.
    notes: 400 lines of product code in builtin_plugins/markdown/rendered.js and markdown-worker-client.js, none in an eager startup script; tests and documentation are another 648.
  verdict:
    decision: unresolved
    primary_metric: requests_kpress and requests_plugin on Markdown revisits and history steps
    reason: A pilot, not a verdict. It ran on harness revision 1 (22af6103), whose painted-ready measure and compare labels review A of the harness found unsound; its candidate was 9e1630db, which carries this round's and exp-061's changes in one build measured in one series against 09903292, and which places a large kept render in the input's task, as the head no longer does (60a4e623); and the corpus's refs moved during the series. Its request counts stand as pilot evidence; the official round on the fixed harness decides.
    commit: 9e1630db
---
**Status:** Pilot, not a verdict.
Five interleaved pairs, ten valid runs, none refused, on harness revision 1
(`22af6103`). The official round on the fixed harness will reuse this id and keep this
pilot as one of its sections.

Why this is a pilot:

- The harness revision the series ran on had unsound painted-ready crediting and
  `compare` labels, which review A of the harness found after the series; the times
  below are reported as the instrument gave them and are not a result.
- The candidate was `9e1630db`, one build carrying this round’s commit and exp-061’s,
  measured in one series against `09903292`.
- The candidate placed every kept render in the task of the input that found it.
  The responsiveness cost recorded below led to `60a4e623`, which places a large kept
  render after the input’s first paint, so the head does not behave as this candidate
  did.
- The corpus’s refs moved during the series (exp-061 says how).

What stands: the request counts, which do not depend on frame crediting.

## Why This Round

H90, in the hypothesis registry of the research branch’s load-time plan (“Apparent Speed
and Layout Stability”), says a Markdown revisit uploads its source and downloads its
render again, and leaving Markdown discards the preprocessing Worker; and that a render
cache keyed by content identity and a kept Worker make revisits request-free.
The exp-058 baseline recorded one KPress request on every Markdown revisit and history
step, and three plugin module requests (the Worker’s) when a Markdown revisit followed a
file of another kind.
The bead is `mb-mbd3`.

The change keeps each render, with its preparation’s diagnostics, on the file envelope
the shell’s file cache holds, keyed beside it by path, `mtime_hash`, view, profile,
table-of-contents option, and preparation; and it keeps the Worker for 60 s after its
last reference, ended early by page hide.

**One series measured two rounds.** This is the series of
[exp-061](exp-061-commit-comparison-cache-and-git-route-memo.md) (H88, the commit
comparison cache and the Git route memo).
The candidate build carries both changes; they touch disjoint code, and their metrics
are on disjoint transitions: this round reads the transitions with a Markdown subject.
Both artifacts read the same [samples](exp-061-transition-samples.jsonl).
The protocol, regime, identities, and guards are exp-061’s and are not repeated here.

## Protocol

Declared before the measured series:

- Named metrics: render requests and painted ready on a Markdown revisit and on history
  Back and Forward (`files.revisit.markdown_small`, `files.revisit.markdown_large`,
  `files.history_back`, `files.history_forward`). Prediction: no render request and no
  Worker preparation on a revisit.

- Guards: every other transition’s counts unchanged, no new blank frames or region
  movement, and every transition converged on the exact file.

The scenario’s request classes name the two effects separately: `kpress` counts the
render request and `plugin` counts module loads, which on a revisit are the Worker and
its imports. The scenario does not record a request’s body size, so the bytes a control
revisit uploaded are not measured here; the research that registered H90 measured 19 KB
for README.md and 190 KB for design-system.md.

The extra input-to-next-paint, long-animation-frame, and application-span columns below
are from [exp-061-transition-detail.jsonl](exp-061-transition-detail.jsonl), the same
runs’ fields for the named transitions, which `samples` does not keep.

## Results

Times are painted ready as median and range over five runs; counts are one value when
every run agreed and a range otherwise.

### Revisits and History Steps

| Transition | Subject | Painted ready ms, control → candidate | Ratio | KPress requests | Plugin requests |
| --- | --- | --- | ---: | --- | --- |
| `files.revisit.markdown_small` | `README.md` | 63 (46–117) → 63 (39–64) | 1.01x | 1 → 0 | 3 → 0 |
| `files.revisit.markdown_large` | `docs/design-system.md` | 129 (113–185) → 115 (113–147) | 0.89x | 1 → 0 | 0 → 0 |
| `files.history_back` | `README.md` | 42 (41–73) → 59 (42–60) | 1.42x | 1 → 0 | 0 → 0 |
| `files.history_forward` | `docs/design-system.md` | 110 (106–156) → 109 (92–125) | 1.00x | 1 → 0 | 0 → 0 |
| `keyboard.up_revisit.1` | `CONTRIBUTING.md` | 44 (41–50) → 28 (27–30) | 0.64x | 1 → 0 | 3 → 0 |
| `keyboard.up_revisit.2` | `CLAUDE.md` | 44 (40–60) → 28 (19–28) | 0.64x | 1 → 0 | 0 → 0 |
| `main.pulls_to_files.first` | `docs/architecture.md` | 64 (63–65) → 30 (30–31) | 0.47x | 1 → 0 | 3 → 0 |
| `main.pulls_to_files.again` | `docs/architecture.md` | 65 (62–65) → 31 (31–32) | 0.48x | 1 → 0 | 3 → 0 |
| `main.commits_to_files.first` | `docs/architecture.md` | 64 (64–79) → 64 (63–65) | 1.00x | 1 → 0 | 3 → 0 |
| `main.commits_to_files.again` | `docs/architecture.md` | 63 (62–75) → 64 (30–65) | 1.01x | 1 → 0 | 3 → 0 |
| `main_subject.pulls_to_files` | `docs/architecture.md` | 77 (64–96) → 64 (63–64) | 0.82x | 1 → 0 | 3 → 0 |
| `main_subject.commits_to_files` | `docs/architecture.md` | 64 (62–64) → 64 (63–65) | 1.01x | 1 → 0 | 3 → 0 |

Every nonzero control count above fell to zero in every candidate run, ranges apart: no
candidate run made a render request or loaded a Worker module on any of these
transitions.
The four click and history transitions the hypothesis named show no detected
difference in painted ready.
`keyboard.up_revisit.1` and `.2` and `main.pulls_to_files.first` and `.again` are lower,
apart, and beyond the 1.3x tolerance, and the main-tab returns from Pulls to Files lost
their 2 blank frames (2 → 0 in every run).
The plugin requests counted together the two halves of the change: a revisit that finds
its render needs no Worker, and a Worker kept from the previous Markdown document needs
no modules. This series does not separate them.

`files.history_back` was 41 to 43 ms in four control runs and 58 to 60 ms in four
candidate runs, a frame later, with one run each at the other’s level, so the ranges
overlap and it is not a result.
The candidate’s frames there are uncredited one more time than the control’s (2 against
1 in those runs): a DOM change followed the first frame that showed README.md, which the
scenario’s limits say can delay the credited frame by one.
The application’s own `fileNavigation:selectToReady` span on that step fell from 38
(27–80) to 24 (21–25) ms.

### Responsiveness

| Transition | Input to next paint ms, control → candidate | Longest task ms | Longest animation frame ms | Its blocking ms | `selectToReady` span ms |
| --- | --- | --- | --- | --- | --- |
| `files.revisit.markdown_large` | 16 (16–56) → 96 (96–120) | 0 → 84 (83–93) | 84 (80–102) → 87 (86–96) | 28 (26–41) → 36 (35–45) | 119 (116–181) → 82 (82–105) |
| `files.history_forward` | not recorded for `popstate` | 0 → 81 (80–84) | 86 (81–94) → 90 (88–92) | 30 (26–41) → 35 (35–38) | 116 (111–164) → 87 (86–89) |
| `files.revisit.markdown_small` | 16 (16–24) → 32 (32–40) | 0 → 0 | 0 → 0 | 0 → 0 | 52 (39–105) → 21 (21–30) |
| `main.pulls_to_files.first` | 16 (16–24) → 32 (32–32) | 0 → 0 | 0 → 0 | 0 → 0 | 61 (57–62) → 26 (25–27) |
| `keyboard.up_revisit.1` | 16 (16–16) → 16 (16–16) | 0 → 0 | 0 → 0 | 0 → 0 | 43 (41–51) → 27 (27–29) |

These moved the wrong way, and this is why.
On the control, a revisit’s click handler starts the Worker preparation and the render
request and returns, so the next paint, 16 ms after the input, shows the selected row
and the old document marked pending (the recorder’s `Ub` frames), and the document is
placed in a later task when the render arrives.
On the candidate, the render is found during the click’s own task and placed in it.
The next paint after the input is then the finished document: one frame later than the
feedback for a small one (32 ms), and 96 to 120 ms later for design-system.md, whose
placement is one 80 to 93 ms task.
The longest animation frame is about the same length on both builds (84 against 87 ms on
the revisit, 86 against 90 on Forward); what changed is that the click’s first paint
waits for it instead of preceding it.
On design-system.md’s revisit and Forward, every control run showed the old document
marked pending and no candidate run did, and painted ready shows no detected difference.

## What Did Not Move

`compare` found 37 metrics with ranges apart.
28 are on the transitions above: the request counts, the painted-ready and blank-frame
changes named above, and the two long tasks.
Nine belong to exp-061’s Git transitions.
No other transition’s request counts, blank frames, placeholder frames, preview
replacements, layout shifts, or region movement came apart, and views, tree, Pulls, and
cold file transitions are within their control ranges.

## What the Pilot Shows

No verdict: the accept rule is applied by the official round.
As pilot evidence:

- No candidate run made a render request, or loaded a Worker module, on any Markdown
  revisit, history step, keyboard revisit, or main-tab return to a Markdown file.
- The painted-ready times above came from the harness revision with the unsound
  crediting and are not evidence either way.
- The responsiveness cost on design-system.md was real enough to act on: `60a4e623`
  places a kept render over a measured size after the input’s first paint, and review
  round 1 of the change lowered that size to the largest one measured without a long
  task. The official round measures that code, not this candidate.

## Limits

- Headless Chrome only; the native app’s WebKit is not measured, and WebKit has no Long
  Tasks or Long Animation Frames API.
- The scenario does not record request body sizes, so uploaded bytes are inferred from
  the request count.
- The Worker keep-alive’s own effect, a Markdown file opened cold after a file of
  another kind, is not a transition this scenario has; here it is inseparable from the
  render cache.
- The render cache’s memory was not measured in a browser; its bound is the render JSON
  measured over this repository’s 269 Markdown files.
- H90 is registered in the plan on the research branch, not yet in this branch’s plan.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->

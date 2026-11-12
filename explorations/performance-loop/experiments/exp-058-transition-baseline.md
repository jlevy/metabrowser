---
title: Transition Navigation Baseline
softschema:
  contract: metabrowser.loadtime:Experiment/v1
  schema: experiment.schema.yaml
  envelope: experiment
  status: enforced
experiment:
  id: exp-058
  title: Transition Navigation Baseline
  date: "2026-11-11"
  hypotheses:
    - H86
    - H88
    - H90
    - H92
    - H94
    - H95
    - H98
    - H101
    - H105
  subject:
    corpus: Detached checkout of this repository at 7a02fed4, frozen and clean; its refs are shared with the main checkout, so the Commits list follows that checkout's trunk.
    corpus_files: 1286
    host_cpu: 10 CPUs
    host_system: Darwin 25.5.0 arm64, Node 24.19.0
    browser: Headless Chrome 152.0.7977.83 over the DevTools Protocol, a fresh profile per journey, trusted pointer and key input.
    viewport: 1440x900
    cold: false
  method:
    runs_per_condition: 6
    interleaved: false
    control: metab 0.12.1.dev165+9903292, the editable control checkout at origin/main 09903292, clean, one server process per run.
    candidate: No candidate. The results block is an A/A split of the same six runs, odd-numbered against even-numbered, which measures the instrument's resolution on this build.
    record: exp-058-transition-samples.jsonl
  results:
    - metric: painted_ready_ms.main.commits_to_files.again
      control_median: 78.8
      candidate_median: 63.7
      control_range: [63.2, 104.4]
      candidate_range: [58.5, 64.7]
      overlapping: true
    - metric: blank_frames.main.commits_to_files.again
      control_median: 3
      candidate_median: 2
      control_range: [2, 5]
      candidate_range: [2, 2]
      overlapping: true
    - metric: region_movement_px.main.files_to_commits.again
      control_median: 37
      candidate_median: 37
      control_range: [37, 37]
      candidate_range: [37, 37]
      overlapping: true
    - metric: painted_ready_ms.files.revisit.markdown_large
      control_median: 130.8
      candidate_median: 162.2
      control_range: [130.1, 131]
      candidate_range: [113.8, 163.6]
      overlapping: true
    - metric: requests_kpress.files.revisit.markdown_large
      control_median: 1
      candidate_median: 1
      control_range: [1, 1]
      candidate_range: [1, 1]
      overlapping: true
    - metric: painted_ready_ms.commits.revisit.1
      control_median: 131
      candidate_median: 163.7
      control_range: [130.4, 263.9]
      candidate_range: [131.3, 164.4]
      overlapping: true
    - metric: requests_data.commits.revisit.1
      control_median: 1
      candidate_median: 1
      control_range: [1, 1]
      candidate_range: [1, 1]
      overlapping: true
    - metric: subject_duplicates.pulls.list_to_pr.cold
      control_median: 2
      candidate_median: 2
      control_range: [2, 2]
      candidate_range: [2, 2]
      overlapping: true
    - metric: painted_ready_ms.pulls.pr_to_pr.revisit
      control_median: 28
      candidate_median: 24.7
      control_range: [26.5, 29.3]
      candidate_range: [24, 27.7]
      overlapping: true
    - metric: painted_ready_ms.keyboard.down_cold.1
      control_median: 43.3
      candidate_median: 51.9
      control_range: [41, 43.7]
      candidate_range: [43.3, 58.7]
      overlapping: true
  verdict:
    decision: baseline
    primary_metric: painted_ready_ms
    reason: Six valid runs of the control build pass every guard on all 73 transitions. The tables below are the control numbers each campaign round compares against. The A/A split found no time metric apart beyond the 1.3x tolerance; it is a baseline, not a result about the product.
---
**Status:** Baseline.
Six valid runs of the control build, none refused.

## Why This Round

The transition campaign (`mb-mpo0`) will land about twenty changes that make UI
transitions instant and remove layout shift, each measured as a round of this loop.
The committed `file-views` and `git-revisions` scenarios do not cover main-tab switches,
revisits, pull request pages, view-tab switches, or region movement.
This round adds the `transition-navigation/v1` scenario
([Transition Navigation Scenario](../README.md#transition-navigation-scenario)) and
records the numbers every later round compares against.
No product code changed.

## Protocol

Declared before the measured series:

- Scenario: every journey of `transitions.mjs`, 73 transitions per run.

- Series: five runs in one invocation, then a sixth so that `compare --aa` has three
  runs per half:

  ```shell
  node explorations/performance-loop/transitions.mjs run --exp exp-058 \
    --corpus /path/to/frozen-checkout --runs 5 \
    --condition control=/path/to/control/.venv/bin/metab
  node explorations/performance-loop/transitions.mjs run --exp exp-058 \
    --corpus /path/to/frozen-checkout --runs 1 \
    --condition control=/path/to/control/.venv/bin/metab
  node explorations/performance-loop/transitions.mjs samples \
    .bench/transitions/exp-058/runs.jsonl \
    --out explorations/performance-loop/experiments/exp-058-transition-samples.jsonl
  node explorations/performance-loop/transitions.mjs summarize \
    explorations/performance-loop/experiments/exp-058-transition-samples.jsonl
  node explorations/performance-loop/transitions.mjs compare \
    explorations/performance-loop/experiments/exp-058-transition-samples.jsonl --aa control
  ```

- Regime: the standard one in the scenario section.
  Each run started a fresh server on its own port (8890 to 8894, and 8890 again for the
  sixth), ran every journey once unrecorded, and then measured them, each journey in a
  fresh Chrome profile.
  All six runs shared one cache and configuration directory.
  Run 1 started it empty, so its warm-up pass fetched the pull request catalog from
  GitHub; the catalog was absent at run 1’s server start and `current` or `stale` at the
  other five.

- Load: the one-minute load average was 4.78 to 32.12 at run starts and ends; the
  five-minute average reached 43.88 at the end of run 4. Each run took 430 to 452 s.

The tables in this artifact are the output of `summarize` and the list in the A/A
section is the output of `compare --aa`, both run on the committed
[samples](exp-058-transition-samples.jsonl).
Running them on the full local rows gives the same output.

## Identities

| Item | Value |
| --- | --- |
| Control build | `metab 0.12.1.dev165+9903292 (+165 commits, 099032928)`, editable checkout at `09903292`, clean in every run |
| Corpus | Checkout at `7a02fed4`, clean, 1,286 indexed files |
| Trunk seen by Commits | `09903292` in all six runs, which was also the head of the first `git/log` page |
| Pull request catalog | 348 to 350 in all, 11 to 13 open, 337 closed, in runs 2 to 6 |
| Harness | `f571f0ea` for runs 1 to 5; `047a41d9` for run 6 |
| Chrome | 152.0.7977.83, headless |

Runs 2 to 5 record `harness.dirty: true`. While the series ran, the `samples` mode and
the `--aa` option were being written in the same worktree and were then committed as
`047a41d9`. Runs 1 to 5 were one process started at `f571f0ea`, so they all executed
that commit’s code. `047a41d9` changes only the README and `transitions.mjs` outside its
run path (`git diff --stat f571f0ea 047a41d9`).

The open pull request count moved from 11 to 13 during the series as other work opened
pull requests. That changes the list `pulls.first_show` and the main-tab Pulls rows land
on. The pull request subjects are merged and listed under the Closed filter, whose count
did not move.

## Guards

Every measured and warm-up pass of all six runs passed every guard.
Across the 438 measured transitions there were no page exceptions, no console errors,
and no rendered error.

During development each guard below refused at least once.
The first two refusals came from defects in the recorder itself; the rest are synthetic
checks run with scratch scripts that were not committed.

| Guard | What it refused |
| --- | --- |
| `page_exceptions` | The first recorder threw at document start, observing a document element that did not exist yet; both landing transitions refused. A product click handler made to throw also refused. |
| `converged` | The first landing arm ran before the recorder existed, so no landing became ready; both refused after 60 s. |
| `build_identity` | A wrapper `metab` that printed a different `--version` refused twice: once on the server’s version line and once on the page’s. |
| `viewport` | A 1280×800 browser refused. |
| `visibility` | A page whose `visibilityState` was forced to `hidden` refused, with 28 hidden frames. |
| `raf` | A page whose `requestAnimationFrame` was stubbed refused: two frames did not arrive within 3 s. |
| `hit_test` | An overlay over the tree refused the click before it was sent. |
| `rendered_errors` | A landing on a missing file refused on its `preview-error` alert. |
| `subject_missing` | Pull request #99999 refused: it is not listed under Closed. |

`input_observed`, `target_missing`, and `setup` did not trigger during development.

## Baseline

Times are painted ready, from the input event to the frame after the first frame that
showed the exact subject with useful content, as median and range over six runs.
Counts are a single value when every run agreed and a range otherwise.
Blank frames include frames that show a tab’s prompt by design: a main tab with nothing
selected lands on its prompt.

### Time and frames

| Transition | Painted ready ms, median (range) | Blank frames | Visible placeholder frames | Nav placeholder frames | Longest task ms, median (range) |
| --- | ---: | ---: | ---: | ---: | ---: |
| `landing.cold_markdown` | 378 (299–543) | 13–28 | 10–25 | 0–1 | 0 (0–0) |
| `landing.reload` | 182 (158–238) | 7–10 | 3–6 | 0 | 0 (0–0) |
| `files.cold.markdown_large` | 205 (181–264) | 0 | 0 | 0 | 70 (61–77) |
| `files.cold.markdown_mid` | 56 (47–76) | 0 | 0 | 0 | 0 (0–0) |
| `files.cold.source_large` | 114 (97–130) | 0 | 0 | 0 | 118 (113–156) |
| `files.cold.source_small` | 47 (46–64) | 0 | 0 | 0 | 0 (0–0) |
| `files.cold.json` | 79 (63–81) | 0 | 0 | 0 | 0 (0–0) |
| `files.cold.diff` | 130 (113–147) | 0 | 0 | 0 | 0 (0–0) |
| `files.cold.image` | 47 (46–49) | 0 | 0 | 0 | 0 (0–0) |
| `files.cold.binary` | 47 (46–64) | 0 | 0 | 0 | 0 (0–0) |
| `files.revisit.source_large` | 323 (314–362) | 0 | 0 | 0 | 126 (115–133) |
| `files.revisit.json` | 48 (48–64) | 0 | 0 | 0 | 0 (0–0) |
| `files.revisit.markdown_small` | 64 (48–64) | 0 | 0 | 0 | 0 (0–0) |
| `files.revisit.markdown_large` | 131 (114–164) | 0 | 0 | 0 | 0 (0–0) |
| `files.history_back` | 42 (40–71) | 0 | 0 | 0 | 0 (0–0) |
| `files.history_forward` | 110 (109–157) | 0 | 0 | 0 | 0 (0–0) |
| `files.hover_click.markdown` | 65 (48–77) | 0 | 0 | 0 | 0 (0–0) |
| `keyboard.down_cold.1` | 44 (41–59) | 0 | 0 | 0 | 0 (0–0) |
| `keyboard.down_cold.2` | 44 (43–60) | 0 | 0 | 0 | 0 (0–0) |
| `keyboard.down_cold.3` | 44 (42–159) | 0 | 0 | 0 | 0 (0–0) |
| `keyboard.up_revisit.1` | 45 (43–72) | 0 | 0 | 0 | 0 (0–0) |
| `keyboard.up_revisit.2` | 45 (41–47) | 0 | 0 | 0 | 0 (0–0) |
| `views.markdown.first` | 31 (30–32) | 0 | 0 | 0 | 0 (0–0) |
| `views.markdown.revisit` | 31 (26–32) | 0 | 0 | 0 | 0 (0–0) |
| `views.markdown.revisit_2` | 31 (30–32) | 0 | 0 | 0 | 0 (0–0) |
| `views.json.first` | 47 (30–48) | 0 | 0 | 0 | 0 (0–0) |
| `views.json.revisit` | 31 (30–32) | 0 | 0 | 0 | 0 (0–0) |
| `views.json.revisit_2` | 30 (29–31) | 0 | 0 | 0 | 0 (0–0) |
| `views.folder.first` | 47 (47–48) | 0 | 0 | 0 | 0 (0–0) |
| `views.folder.revisit` | 47 (46–49) | 0 | 0 | 0 | 0 (0–0) |
| `views.folder.revisit_2` | 64 (62–65) | 0 | 0 | 0 | 0 (0–0) |
| `main.files_to_commits.first` | 306 (264–364) | 15–21 | 0 | 0 | 0 (0–0) |
| `main.commits_to_files.first` | 65 (59–93) | 2–4 | 0 | 0 | 0 (0–0) |
| `main.files_to_commits.again` | 31 (25–32) | 1 | 0 | 0 | 0 (0–0) |
| `main.commits_to_files.again` | 64 (59–104) | 2–5 | 0 | 0 | 0 (0–0) |
| `main.files_to_pulls.first` | 65 (56–101) | 1 | 0 | 0 | 0 (0–0) |
| `main.pulls_to_files.first` | 70 (64–126) | 2–6 | 0 | 0 | 0 (0–0) |
| `main.files_to_pulls.again` | 64 (61–66) | 1 | 0 | 0 | 0 (0–0) |
| `main.pulls_to_commits` | 30 (26–31) | 1 | 0 | 0 | 0 (0–0) |
| `main.commits_to_pulls` | 64 (63–65) | 3 | 0 | 0 | 0 (0–0) |
| `main.pulls_to_files.again` | 64 (63–65) | 2 | 0 | 0 | 0 (0–0) |
| `main_subject.files_to_commits` | 240 (214–279) | 0 | 0 | 0 | 0 (0–0) |
| `main_subject.commits_to_pulls` | 65 (64–78) | 0 | 0 | 0 | 0 (0–0) |
| `main_subject.pulls_to_files` | 65 (62–112) | 0 | 0 | 0 | 0 (0–0) |
| `main_subject.files_to_pulls` | 64 (62–65) | 0 | 0 | 0 | 0 (0–0) |
| `main_subject.pulls_to_commits` | 220 (198–244) | 0 | 0 | 0 | 0 (0–0) |
| `main_subject.commits_to_files` | 64 (62–65) | 0 | 0 | 0 | 0 (0–0) |
| `commits.first_show` | 322 (281–430) | 16–25 | 0 | 0 | 0 (0–0) |
| `commits.cold.1` | 188 (164–298) | 5–14 | 2–11 | 0 | 54 (50–55) |
| `commits.cold.2` | 207 (197–230) | 0 | 0 | 0 | 0 (0–0) |
| `commits.cold.3` | 140 (130–182) | 0 | 0 | 0 | 0 (0–0) |
| `commits.revisit.1` | 148 (130–264) | 0 | 0 | 0 | 0 (0–0) |
| `commits.revisit.2` | 206 (148–295) | 0 | 0 | 0 | 0 (0–0) |
| `commits.hover_click` | 65 (65–80) | 0 | 0 | 0 | 0 (0–0) |
| `pulls.first_show` | 65 (63–77) | 1 | 0 | 0 | 0 (0–0) |
| `pulls.list_to_pr.cold` | 91 (59–102) | 1–5 | 0 | 0 | 0 (0–0) |
| `pulls.tab.changes_first` | 112 (79–128) | 0 | 0 | 0 | 0 (0–0) |
| `pulls.tab.checks_first` | 29 (26–46) | 0 | 0 | 0 | 0 (0–0) |
| `pulls.tab.conversation_revisit` | 29 (29–46) | 0 | 0 | 0 | 0 (0–0) |
| `pulls.tab.changes_revisit` | 46 (44–62) | 0 | 0 | 0 | 0 (0–0) |
| `pulls.tab.conversation_revisit_2` | 29 (26–57) | 0 | 0 | 0 | 0 (0–0) |
| `pulls.pr_to_pr.cold` | 79 (78–94) | 0 | 0 | 0 | 0 (0–0) |
| `pulls.pr_to_pr.revisit` | 27 (24–29) | 0 | 0 | 0 | 0 (0–0) |
| `pulls.pr_to_pr.hover_click` | 98 (64–115) | 0 | 0 | 0 | 0 (0–0) |
| `pulls.tab.changes_first_2` | 46 (44–51) | 0 | 0 | 0 | 0 (0–0) |
| `pulls.history_back` | 26 (24–28) | 0 | 0 | 0 | 0 (0–0) |
| `pulls.tab.changes_revisit_2` | 69 (45–156) | 0 | 0 | 0 | 0 (0–0) |
| `pulls.pr_changes_to_pr` | 105 (76–129) | 0 | 0 | 0 | 0 (0–0) |
| `tree.expand.docs` | 97 (81–130) | 0 | 0 | 0 | 0 (0–0) |
| `tree.expand.src` | 48 (48–77) | 0 | 0 | 0 | 0 (0–0) |
| `tree.collapse.src` | 31 (29–32) | 0 | 0 | 0 | 0 (0–0) |
| `tree.reexpand.src` | 31 (31–32) | 0 | 0 | 0 | 0 (0–0) |
| `tree.expand_nested.src_metabrowser` | 48 (46–59) | 0 | 0 | 0 | 0 (0–0) |

### Requests

| Transition | Data | Plugin modules | Static | KPress | Background | Subject duplicates |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `landing.cold_markdown` | 17–20 | 29 | 41 | 18 | 1–2 | 0 |
| `landing.reload` | 17–21 | 29 | 41 | 18 | 1–2 | 0 |
| `files.cold.markdown_large` | 1 | 0 | 0 | 3 | 2 | 0 |
| `files.cold.markdown_mid` | 1 | 0 | 0 | 1 | 0–2 | 0 |
| `files.cold.source_large` | 1 | 1 | 0 | 0 | 0–2 | 0 |
| `files.cold.source_small` | 1 | 0 | 0 | 0 | 2 | 0 |
| `files.cold.json` | 2 | 4 | 0 | 0 | 0 | 0 |
| `files.cold.diff` | 3 | 7 | 0 | 0 | 0–2 | 0 |
| `files.cold.image` | 1 | 2 | 0 | 0 | 1–2 | 0 |
| `files.cold.binary` | 1 | 0 | 0 | 0 | 0–2 | 0 |
| `files.revisit.source_large` | 0 | 0 | 0 | 0 | 0–2 | 0 |
| `files.revisit.json` | 1 | 0 | 0 | 0 | 0–2 | 0 |
| `files.revisit.markdown_small` | 0 | 3 | 0 | 1 | 0 | 0 |
| `files.revisit.markdown_large` | 0 | 0 | 0 | 1 | 0–2 | 0 |
| `files.history_back` | 0 | 0 | 0 | 1 | 2 | 0 |
| `files.history_forward` | 0 | 0 | 0 | 1 | 0–2 | 0 |
| `files.hover_click.markdown` | 1 | 0 | 0 | 1 | 0–2 | 0 |
| `keyboard.down_cold.1` | 1 | 0 | 0 | 1 | 0 | 0 |
| `keyboard.down_cold.2` | 1 | 0 | 0 | 1 | 0–2 | 0 |
| `keyboard.down_cold.3` | 1 | 1 | 0 | 0 | 2 | 0 |
| `keyboard.up_revisit.1` | 0 | 3 | 0 | 1 | 2 | 0 |
| `keyboard.up_revisit.2` | 0 | 0 | 0 | 1 | 0–2 | 0 |
| `views.markdown.first` | 0 | 0 | 0 | 0 | 2 | 0 |
| `views.markdown.revisit` | 0 | 0 | 0 | 0 | 0 | 0 |
| `views.markdown.revisit_2` | 0 | 0 | 0 | 0 | 0 | 0 |
| `views.json.first` | 0 | 0 | 0 | 0 | 2 | 0 |
| `views.json.revisit` | 0 | 0 | 0 | 0 | 0 | 0 |
| `views.json.revisit_2` | 0 | 0 | 0 | 0 | 0–2 | 0 |
| `views.folder.first` | 1 | 0 | 0 | 0 | 1–2 | 0 |
| `views.folder.revisit` | 0 | 0 | 0 | 0 | 0–2 | 0 |
| `views.folder.revisit_2` | 0 | 0 | 0 | 0 | 0 | 0 |
| `main.files_to_commits.first` | 4–5 | 0 | 0 | 0 | 1–2 | 0 |
| `main.commits_to_files.first` | 0–1 | 3 | 0 | 1 | 0–2 | 0 |
| `main.files_to_commits.again` | 1 | 0 | 0 | 0 | 2 | 0 |
| `main.commits_to_files.again` | 0 | 3 | 0 | 1 | 0 | 0 |
| `main.files_to_pulls.first` | 4–6 | 0 | 0 | 0 | 4 | 0 |
| `main.pulls_to_files.first` | 0 | 3 | 0 | 1 | 0 | 0 |
| `main.files_to_pulls.again` | 2 | 0 | 0 | 0 | 1 | 0 |
| `main.pulls_to_commits` | 1 | 0 | 0 | 0 | 0 | 0 |
| `main.commits_to_pulls` | 2 | 0 | 0 | 0 | 1 | 0 |
| `main.pulls_to_files.again` | 0 | 3 | 0 | 1 | 0 | 0 |
| `main_subject.files_to_commits` | 2 | 0 | 0 | 0 | 2 | 0 |
| `main_subject.commits_to_pulls` | 11–13 | 0 | 0 | 0 | 4–6 | 0 |
| `main_subject.pulls_to_files` | 0 | 3 | 0 | 1 | 0–2 | 0 |
| `main_subject.files_to_pulls` | 11–12 | 0 | 0 | 0 | 3 | 0–1 |
| `main_subject.pulls_to_commits` | 2 | 0 | 0 | 0 | 2–3 | 0 |
| `main_subject.commits_to_files` | 0 | 3 | 0 | 1 | 2 | 0 |
| `commits.first_show` | 4 | 0 | 0 | 0 | 2 | 0 |
| `commits.cold.1` | 2 | 7 | 0 | 0 | 2 | 0 |
| `commits.cold.2` | 2 | 0 | 0 | 0 | 2 | 0 |
| `commits.cold.3` | 2 | 0 | 0 | 0 | 2 | 0 |
| `commits.revisit.1` | 1 | 0 | 0 | 0 | 2 | 0 |
| `commits.revisit.2` | 1 | 0 | 0 | 0 | 2 | 0 |
| `commits.hover_click` | 2 | 0 | 0 | 0 | 2–4 | 0 |
| `pulls.first_show` | 4 | 0 | 0 | 0 | 2–4 | 0 |
| `pulls.list_to_pr.cold` | 14 | 8 | 1 | 1 | 5 | 2 |
| `pulls.tab.changes_first` | 4 | 1 | 1 | 0 | 6 | 0 |
| `pulls.tab.checks_first` | 0 | 0 | 0 | 0 | 2–4 | 0 |
| `pulls.tab.conversation_revisit` | 0 | 0 | 0 | 0 | 2–4 | 0 |
| `pulls.tab.changes_revisit` | 4–5 | 0 | 0 | 0 | 2–4 | 0 |
| `pulls.tab.conversation_revisit_2` | 0 | 0 | 0 | 0 | 2–4 | 0 |
| `pulls.pr_to_pr.cold` | 13–19 | 0 | 0 | 0 | 6 | 2–4 |
| `pulls.pr_to_pr.revisit` | 14–16 | 0 | 0 | 0 | 3–5 | 1–2 |
| `pulls.pr_to_pr.hover_click` | 14–16 | 0 | 0 | 0 | 5–7 | 1 |
| `pulls.tab.changes_first_2` | 3–5 | 0 | 0 | 0 | 4–7 | 0 |
| `pulls.history_back` | 0 | 0 | 0 | 0 | 3–5 | 0 |
| `pulls.tab.changes_revisit_2` | 3–6 | 0 | 0 | 0 | 2–5 | 0 |
| `pulls.pr_changes_to_pr` | 14–15 | 0 | 0 | 0 | 1–6 | 1–2 |
| `tree.expand.docs` | 5–7 | 19 | 0 | 1 | 2 | 0 |
| `tree.expand.src` | 2 | 0 | 0 | 0 | 0–2 | 0 |
| `tree.collapse.src` | 0 | 0 | 0 | 0 | 0–2 | 0 |
| `tree.reexpand.src` | 0 | 0 | 0 | 0 | 2 | 0 |
| `tree.expand_nested.src_metabrowser` | 12 | 0 | 0 | 0 | 2 | 0 |

### Stability and DOM

| Transition | Preview top nodes replaced | Layout shifts | Shift without input | Region movement px | DOM nodes after |
| --- | ---: | ---: | ---: | ---: | ---: |
| `landing.cold_markdown` | 4 | 2 | 0.0033–0.0034 | 0 | 2058–2126 |
| `landing.reload` | 4 | 1 | 0.0002 | 0 | 2058–2126 |
| `files.cold.markdown_large` | 5 | 0 | 0.0000 | 0 | 8399–8467 |
| `files.cold.markdown_mid` | 5 | 0 | 0.0000 | 0 | 6281–6349 |
| `files.cold.source_large` | 5 | 0 | 0.0000 | 30 | 18634–18702 |
| `files.cold.source_small` | 3 | 0 | 0.0000 | 0 | 5981–6049 |
| `files.cold.json` | 3 | 0 | 0.0000 | 30 | 10003–10071 |
| `files.cold.diff` | 5 | 7 | 0.0000 | 30 | 6381–6449 |
| `files.cold.image` | 3 | 0 | 0.0000 | 11 | 5715–5783 |
| `files.cold.binary` | 3 | 0 | 0.0000 | 11 | 5725–5793 |
| `files.revisit.source_large` | 3 | 0 | 0.0000 | 0 | 18657–18725 |
| `files.revisit.json` | 3 | 0 | 0.0000 | 30 | 10022–10090 |
| `files.revisit.markdown_small` | 5 | 0 | 0.0000 | 0 | 6181–6249 |
| `files.revisit.markdown_large` | 5 | 0 | 0.0000 | 0 | 8423–8491 |
| `files.history_back` | 5 | 0 | 0.0000 | 0 | 6181–6249 |
| `files.history_forward` | 5 | 0 | 0.0000 | 0 | 8423–8491 |
| `files.hover_click.markdown` | 5 | 0 | 0.0000 | 0 | 6819–6887 |
| `keyboard.down_cold.1` | 5 | 0 | 0.0000 | 11 | 1669–1737 |
| `keyboard.down_cold.2` | 5 | 0 | 0.0000 | 11 | 1715–1783 |
| `keyboard.down_cold.3` | 5 | 0 | 0.0000 | 30 | 1598–1666 |
| `keyboard.up_revisit.1` | 3 | 0 | 0.0000 | 30 | 1716–1784 |
| `keyboard.up_revisit.2` | 5 | 0 | 0.0000 | 11 | 1670–1738 |
| `views.markdown.first` | 0 | 0 | 0.0000 | 0 | 2280–2348 |
| `views.markdown.revisit` | 0 | 0 | 0.0000 | 0 | 2280–2348 |
| `views.markdown.revisit_2` | 0 | 0 | 0.0000 | 0 | 2280–2348 |
| `views.json.first` | 0 | 1 | 0.0000 | 0 | 9521–9589 |
| `views.json.revisit` | 0 | 1 | 0.0000 | 0 | 9521–9589 |
| `views.json.revisit_2` | 0 | 1 | 0.0000 | 0 | 9521–9589 |
| `views.folder.first` | 0 | 0 | 0.0000 | 0 | 2180–2248 |
| `views.folder.revisit` | 0 | 0 | 0.0000 | 0 | 1994–2062 |
| `views.folder.revisit_2` | 0 | 2 | 0.0000 | 0 | 2180–2248 |
| `main.files_to_commits.first` | 4 | 1 | 0.0000 | 37 | 3561–3663 |
| `main.commits_to_files.first` | 2 | 1 | 0.0000 | 37 | 4170–4272 |
| `main.files_to_commits.again` | 4 | 1 | 0.0000 | 37 | 3561–3663 |
| `main.commits_to_files.again` | 2 | 1 | 0.0000 | 37 | 4170–4272 |
| `main.files_to_pulls.first` | 4 | 2 | 0.0000 | 37 | 3597–3699 |
| `main.pulls_to_files.first` | 2 | 1 | 0.0000 | 37 | 4205–4307 |
| `main.files_to_pulls.again` | 4 | 1 | 0.0000 | 37 | 3597–3699 |
| `main.pulls_to_commits` | 1 | 0 | 0.0000 | 0 | 3596–3698 |
| `main.commits_to_pulls` | 1 | 0 | 0.0000 | 0 | 3597–3699 |
| `main.pulls_to_files.again` | 2 | 1 | 0.0000 | 37 | 4205–4307 |
| `main_subject.files_to_commits` | 5 | 1 | 0.0000 | 37 | 6244 |
| `main_subject.commits_to_pulls` | 2 | 0 | 0.0000 | 0 | 5400 |
| `main_subject.pulls_to_files` | 2 | 1 | 0.0000 | 37 | 5721 |
| `main_subject.files_to_pulls` | 5 | 1 | 0.0000 | 37 | 5400 |
| `main_subject.pulls_to_commits` | 2 | 0 | 0.0000 | 0 | 6244 |
| `main_subject.commits_to_files` | 2 | 1 | 0.0000 | 37 | 5721 |
| `commits.first_show` | 4 | 1 | 0.0000 | 37 | 3344–3446 |
| `commits.cold.1` | 3 | 0 | 0.0000 | 0 | 4500–4602 |
| `commits.cold.2` | 2 | 0 | 0.0000 | 0 | 4542–4644 |
| `commits.cold.3` | 2 | 0 | 0.0000 | 0 | 4948–5050 |
| `commits.revisit.1` | 2 | 0 | 0.0000 | 0 | 4500–4602 |
| `commits.revisit.2` | 2 | 0 | 0.0000 | 0 | 4542–4644 |
| `commits.hover_click` | 2 | 0 | 0.0000 | 0 | 3649–3751 |
| `pulls.first_show` | 4 | 2–3 | 0.0000 | 37 | 1609–1711 |
| `pulls.list_to_pr.cold` | 1 | 2 | 0.0000 | 0 | 3412 |
| `pulls.tab.changes_first` | 0 | 3–4 | 0.0000 | 8 | 5683–5848 |
| `pulls.tab.checks_first` | 0 | 1 | 0.0000 | 8 | 3236 |
| `pulls.tab.conversation_revisit` | 0 | 0 | 0.0000 | 0 | 3412 |
| `pulls.tab.changes_revisit` | 0 | 2–3 | 0.0000 | 8 | 5683–5848 |
| `pulls.tab.conversation_revisit_2` | 0 | 1 | 0.0000 | 8 | 3412 |
| `pulls.pr_to_pr.cold` | 2 | 0 | 0.0000 | 0 | 3967 |
| `pulls.pr_to_pr.revisit` | 2 | 8 | 0.0000 | 0 | 3713 |
| `pulls.pr_to_pr.hover_click` | 2 | 1 | 0.0000 | 0 | 4447 |
| `pulls.tab.changes_first_2` | 0 | 2 | 0.0000 | 8 | 5755 |
| `pulls.history_back` | 0 | 1 | 0.0000 | 8 | 4106 |
| `pulls.tab.changes_revisit_2` | 0 | 2–3 | 0.0000 | 8 | 5755–5756 |
| `pulls.pr_changes_to_pr` | 2 | 0 | 0.0000 | 8 | 4796 |
| `tree.expand.docs` | 5 | 8 | 0.0000 | 11 | 1939–2041 |
| `tree.expand.src` | 5 | 3 | 0.0000 | 0 | 2088–2190 |
| `tree.collapse.src` | 0 | 3 | 0.0000 | 0 | 2093–2195 |
| `tree.reexpand.src` | 0 | 3 | 0.0000 | 0 | 2093–2195 |
| `tree.expand_nested.src_metabrowser` | 5 | 1 | 0.0000 | 0 | 2886–2988 |

What the counts say, at this build:

- File-to-file, keyboard, history, and view-tab transitions had no blank frame and no
  visible placeholder in any run.
- Main-tab switches with nothing selected showed the tab’s prompt for 1 to 3 frames once
  the tab had been shown before (15 to 21 on the first Commits show), and the return to
  Files showed the prompt for 2 to 6 frames before the file came back.
  With a commit and a pull request selected, the same switches had no blank frame, but
  each still replaced two to five top-level preview nodes and issued requests.
- Every switch to or from Files moved the tree region by 37 px.
  Files that add or drop the view tab bar moved the content by 30 px, and files that add
  or drop the scrollbar changed its width by 11 px.
  Pull request tab switches moved the tab bar by 8 px.
- A commit revisit issued one data request, a Markdown revisit one KPress request, and a
  cold click on a pull request read its record three times (two duplicates).

## A/A Resolution

`compare --aa control` made 1,168 comparisons: 73 transitions and 16 metrics.
Ten had ranges that did not overlap:

- `files.cold.markdown_large` painted_ready_ms: 182 (181–197) → 215 (212–264) (1.18x);
  higher, ranges apart but within the 1.3x tolerance (not a result)
- `files.cold.markdown_large` long_task_max_ms: 67 (61–67) → 75 (72–77) (1.12x); higher,
  ranges apart but within the 1.3x tolerance (not a result)
- `keyboard.up_revisit.2` painted_ready_ms: 47 (45–47) → 42 (41–44) (0.90x); lower,
  ranges apart but within the 1.3x tolerance (not a result)
- `views.folder.revisit_2` painted_ready_ms: 64 (64–65) → 63 (62–64) (0.99x); lower,
  ranges apart but within the 1.3x tolerance (not a result)
- `main_subject.pulls_to_files` requests_background: 1–2 → 0; lower, ranges apart
- `commits.cold.2` painted_ready_ms: 198 (197–199) → 216 (215–230) (1.09x); higher,
  ranges apart but within the 1.3x tolerance (not a result)
- `commits.hover_click` painted_ready_ms: 65 (65–80) → 65 (65–65) (0.99x); lower, ranges
  apart but within the 1.3x tolerance (not a result)
- `pulls.list_to_pr.cold` painted_ready_ms: 90 (59–91) → 97 (92–102) (1.07x); higher,
  ranges apart but within the 1.3x tolerance (not a result)
- `pulls.pr_to_pr.hover_click` painted_ready_ms: 99 (98–115) → 98 (64–98) (0.99x);
  lower, ranges apart but within the 1.3x tolerance (not a result)
- `pulls.tab.changes_first_2` requests_background: 4–5 → 6–7; higher, ranges apart

No time metric came apart by more than the 1.3x tolerance; the largest ratio among the
separated times was 1.18x, on `files.cold.markdown_large`, at a load average that
reached 32 during the series.
Several separated by less than one frame, which is why a time needs the tolerance as
well as separate ranges.
The two background-request counts differ because the Pulls catalog walk runs on its own
timer; they are not a metric a round should name.

## Limits

- Headless Chrome only.
  The native app’s WebKit is not measured.
- The server is warm by design; a cold server render is not part of this regime.
- The corpus has no heavy view such as a multi-megabyte JSONL log, so heavy view-tab
  revisits (H99) are not covered.
- Painted ready is an upper bound quantized to one frame.
  A frame changed after its animation frame is not credited, which can add one frame.
- The command palette, filters, rapid repeated clicks, and held-key skims from the
  research inventory are not in these journeys.
- The hypothesis identifiers name the H86 to H106 registry proposed on the research
  branch, not yet in this branch’s plan.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->

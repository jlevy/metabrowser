---
title: One Read per Click, Trees That Open Once, and a Held Changes Paint
softschema:
  contract: metabrowser.loadtime:Experiment/v1
  schema: experiment.schema.yaml
  envelope: experiment
  status: enforced
experiment:
  id: exp-065
  title: One Read per Click, Trees That Open Once, and a Held Changes Paint
  date: "2026-11-13"
  hypotheses:
    - H92
  subject:
    corpus: Standalone clone of this repository at 7a02fed4 with its own refs, clean; its commit, cleanliness, trunk, and refs did not move during the series.
    corpus_files: 1286
    host_cpu: 10 CPUs
    host_system: Darwin 25.5.0 arm64, Node 24.19.0
    browser: Headless Chrome 152.0.7977.83 over the DevTools Protocol, a fresh profile per journey, trusted pointer and key input.
    viewport: 1440x900
    cold: false
  method:
    runs_per_condition: 3
    interleaved: true
    control: metab 0.12.1.dev165+9903292 (+165 commits, 099032928), the editable control checkout at 09903292, clean at the start and end of every run, one server process per run.
    candidate: metab 0.12.1.dev165+9903292 (+182 commits, 5a56f0a8f), the editable checkout of claude/perf-prpage at 5a56f0a8, clean at the start and end of every run, one server process per run. It carries H92's changes and H106's (exp-080), measured in one series.
    record: exp-065-transition-samples.jsonl
  results:
    - metric: subject_duplicates per run, the five pull request clicks of the pulls journey
      control_median: 6
      candidate_median: 0
      control_range: [6, 6]
      candidate_range: [0, 0]
      overlapping: false
    - metric: subject_duplicates.pulls.list_to_pr.cold
      control_median: 2
      candidate_median: 0
      control_range: [1, 2]
      candidate_range: [0, 0]
      overlapping: false
    - metric: subject_duplicates.pulls.pr_to_pr.cold
      control_median: 1
      candidate_median: 0
      control_range: [1, 1]
      candidate_range: [0, 0]
      overlapping: false
    - metric: subject_duplicates.pulls.pr_to_pr.revisit
      control_median: 0
      candidate_median: 0
      control_range: [0, 1]
      candidate_range: [0, 0]
      overlapping: true
    - metric: subject_duplicates.pulls.pr_to_pr.hover_click
      control_median: 1
      candidate_median: 0
      control_range: [1, 1]
      candidate_range: [0, 0]
      overlapping: false
    - metric: subject_duplicates.pulls.pr_changes_to_pr
      control_median: 2
      candidate_median: 0
      control_range: [2, 2]
      candidate_range: [0, 0]
      overlapping: false
    - metric: panel_shift_no_input, a selected row whose file list GitHub fills (pilot instrument)
      control_median: 0.05
      candidate_median: 0
      control_range: [0.05, 0.05]
      candidate_range: [0, 0]
      overlapping: false
    - metric: tree rows drawn with no input more than 500 ms after the click (pilot instrument)
      control_median: 43
      candidate_median: 0
      control_range: [43, 43]
      candidate_range: [0, 0]
      overlapping: false
    - metric: body layout shift after painted ready per run, the four Changes paints
      control_median: 1.0851
      candidate_median: 0
      control_range: [1.0851, 1.645]
      candidate_range: [0, 0]
      overlapping: false
    - metric: painted_ready_ms.pulls.tab.changes_first
      control_median: 46.4
      candidate_median: 110.3
      control_range: [45.2, 46.6]
      candidate_range: [95.3, 110.5]
      overlapping: false
    - metric: painted_ready_ms.pulls.tab.changes_revisit
      control_median: 45.0
      candidate_median: 78.3
      control_range: [44.6, 46.4]
      candidate_range: [75.3, 79.2]
      overlapping: false
    - metric: painted_ready_ms.pulls.tab.changes_first_2
      control_median: 46.1
      candidate_median: 96.0
      control_range: [44.2, 46.4]
      candidate_range: [96.0, 108.2]
      overlapping: false
    - metric: painted_ready_ms.pulls.tab.changes_revisit_2
      control_median: 43.7
      candidate_median: 95.4
      control_range: [42.7, 44.7]
      candidate_range: [93.3, 96.6]
      overlapping: false
    - metric: pr_description_shown_ms.pulls.pr_to_pr.cold
      control_median: 45.8
      candidate_median: 61.4
      control_range: [45.6, 46.3]
      candidate_range: [61.2, 62.6]
      overlapping: false
    - metric: pr_description_final_ms.pulls.pr_changes_to_pr
      control_median: 79.4
      candidate_median: 111.9
      control_range: [77.8, 79.5]
      candidate_range: [111.4, 112.7]
      overlapping: false
  complexity:
    lines_changed: 2006
    new_dependencies: []
    new_failure_modes:
      - A Changes paint with rendered Markdown waits out of sight for its first screen's Markdown files, up to CHANGES_FIRST_SCREEN_MS (200 ms), and a conversation's first paint for its first screen's texts, up to DESCRIPTION_HOLD_MS (200 ms); past either bound the page shows as it is.
      - A file tree whose list arrives late, or changes, after the tree is drawn shows an offer to draw it instead of drawing it; the reader presses it to see the new rows.
      - A selection's read is handed to the page that opens; if that page goes before the read answers, the read is aborted with it.
    notes: 1,715 lines added and 291 removed in product code (09903292..5a56f0a8) for H92 and H106 together, 1,173 and 242 of them in pull-page.js; tests, goldens, and documentation are another 2,291 and 68. H92's own code is mostly in pulls-panel.js (129, 36), pull-files-tree.js (191, 4), pull-files-view.js (46, 4), the diff plugin (57, 4), and the Changes hold in pull-page.js.
  verdict:
    decision: accepted
    primary_metric: (a) subject_duplicates on the pull request clicks; (b) no-input Pulls panel shift with a late file list; (c) body layout shift after painted ready on Changes
    reason: "Three parts, each decided on its named metric with three valid back-to-back pairs (six pairs excluded for load before any result was read). (a) accepted: duplicate reads of the selected record across the five clicks fell from 6 (6-6) to 0 (0-0), and no click got worse. (b) accepted on the pilot instrument: the late file list drew 43 rows with no input and a 0.05 panel shift in every control run, and none in any candidate run, which offered it instead. (c) accepted: body shift after painted ready over the four Changes paints fell from 1.0851 (1.0851-1.645) to 0 (0-0). The guards moved the wrong way and are accounted for by the holds: Changes paints 33 to 64 ms later (1.7x to 2.4x, every pair), and a cold click's description shows 16 to 49 ms later, because the page now waits out of sight for what it would otherwise replace. Judgment: worth it, given the owner's requirement that nothing moves or flashes as a page loads."
    commit: 5a56f0a8
---
**Status:** Accepted, all three parts.
Three valid interleaved pairs of the pulls and maintabs journeys, on harness revision 4
(`5031dc16`), and a pilot instrument for the file tree (part b), three more valid pairs.
Six of the nine transition pairs run, and none of the tree probe’s, were excluded by the
load rule before any result was read.
The candidate carries
[exp-080](exp-080-pull-request-conversation-final-at-first-paint.md)’s changes too: one
series measured both rounds, which read different metrics.

## Why This Round

H92 in the
[load-time plan](../../../docs/project/specs/active/plan-2026-08-21-load-time-performance.md)
says a pull request click reads the selected record two to four times, that a selected
row’s file tree grows seconds after the click, and that Changes paints before its
rendered diffs. It names three changes, each with its own metric: (a) an answer the
selection read less than one fast poll earlier counts as the page’s first read; (b) a
row’s file tree opens once at its full height; (c) Changes holds its first paint for the
diffs in flight. The bead is `mb-6chh`; the pull request is #369.

## Protocol

Declared before the measured series, with amendments timestamped before any timed run
or, for the last, during the series before any result was read:

- **Builds.** Control `09903292`; candidate `5a56f0a8`. The candidate was first declared
  at `3afd3131`; review D moved it to `5a56f0a8` before any timed run.

- **Series.** One series serves this round and exp-080, from the frozen harness checkout
  at `5031dc16`, scenario revision 4, unmodified:

  ```shell
  node explorations/performance-loop/transitions.mjs run --exp exp-065 \
    --corpus /path/to/standalone-clone --runs 3 --journeys pulls,maintabs \
    --out .bench/transitions/exp-065/runs-pulls.jsonl \
    --condition control=/path/to/control/.venv/bin/metab \
    --condition candidate=/path/to/candidate/.venv/bin/metab
  ```

  The journeys are the ones the criteria and guards name: `pulls` for every part here,
  and `maintabs` for its two Conversation transitions, which exp-080 counts.
  A journey subset is not the standard regime; both conditions ran the same one, and
  `--out` makes the rows the round’s.

- **Load rule.** The series lock was taken only after the one-minute load stayed under
  12 for two minutes (five samples 30 s apart).
  A pair is excluded, mechanically and before any result is read, when either run saw a
  one-minute load above 12 at its start (`load_start`) or at any measured transition’s
  start (`load1`). Pairs were added two at a time, each addition after the same quiet
  gate, until three were valid.
  The rule was applied by `exp-065-instruments/load-exclusions.mjs`, which reads only
  load fields.

- **Part (a).** Metric: per run, the scenario’s `subjectDuplicates` summed over the five
  pull request clicks (`pulls.list_to_pr.cold`, `pulls.pr_to_pr.cold`,
  `pulls.pr_to_pr.revisit`, `pulls.pr_to_pr.hover_click`, `pulls.pr_changes_to_pr`).
  Settlement reads after the page’s own `pull-refresh` are counted apart by the
  scenario. Predicted lower (candidate 0), judged on ranges; no click worse.
  Guards: `pr_description_shown_ms` and `pr_description_final_ms` on the four cold
  clicks, by compare’s pair rule, with exp-052’s 37–40 ms and exp-055’s 71–80 ms as
  context from other regimes.
  The page never treating a record older than one fast poll as its first read is the
  browserless selection session’s guard, not measured here.

- **Part (b).** The scenario’s warm server holds every subject’s file list, so it cannot
  produce a late tree.
  Pilot instrument `exp-065-instruments/probe-tree-late.mjs`: each run starts a fresh
  server on the corpus with empty cache and configuration directories, opens Pulls,
  switches to Closed, selects #353 with a trusted click, and watches the panel for 12 s.
  Metric: per run, the layout-shift sum with no recent input whose sources are in the
  Pulls panel; also the rows drawn into the selected tree more than 500 ms after the
  last input. Predicted lower (candidate 0), judged on ranges.
  Interleaved pairs on ports 8930 to 8936, the same load rule at each run’s start and
  click, and the same quiet gate before each pair.

- **Part (c).** Metric: per run, the layout-shift sum after painted ready whose sources
  are in the pull request body, over the four Changes paints of the pulls journey
  (`changes_first`, `changes_revisit`, `changes_first_2`, `changes_revisit_2`), derived
  from the scenario’s shift entries by `exp-065-instruments/derive-h92-h106.mjs`. All
  shifts count, since the control’s come within the click’s input window.
  Predicted lower (candidate 0), judged on ranges.
  The pilot showed `changes_first` alone rarely shifting in the control, so the metric
  covers every Changes paint.
  Guard: `painted_ready_ms` on the four, by compare’s pair rule.

- **Hold spans** (guard for both rounds): `exp-065-instruments/probe-holds-corpus.mjs`
  on the candidate after the series, using the series’ candidate state, three runs that
  click the four subjects in turn, each from the previous conversation scrolled by 1,500
  px. Bound-hit share under 10% of each kind’s holds, and each kind’s median under half
  its bound.

- **Accept rule.** The runbook’s: the named metric moves the predicted way, the ranges
  do not overlap at n ≥ 3, nothing else moved the wrong way without being accounted for,
  and the complexity is worth it.

Regime notes, true of the candidate measured:

- The conversation’s first-paint hold covers the comments and reviews on its first
  screen, measured from the page’s own top, with the next three texts asked for ahead.
- Over the loading page, the loading heading stays while the hold lasts, and the
  record’s header paints with the conversation at release.
- A slow landing keeps the loading blocks that had shown, in place, until the
  conversation shows.

## Identities

| Item | Value |
| --- | --- |
| Control build | `metab 0.12.1.dev165+9903292 (+165 commits, 099032928)`, editable checkout at `09903292`, clean at the start and end of every run |
| Candidate build | `metab 0.12.1.dev165+9903292 (+182 commits, 5a56f0a8f)`, editable checkout at `5a56f0a8`, clean at the start and end of every run |
| Corpus | Standalone clone at `7a02fed4`, trunk `083e78e4`, clean, 1,286 indexed files; refs unchanged in every run |
| Harness | `5031dc16`, clean, scenario revision 4, in every run |
| Chrome | 152.0.7977.83, headless |
| Pull request catalog | Absent at the first run’s start, 370 (15 open) and then 375 (12 open) as the series went on, in both conditions |

## Guards and Load

All 18 runs were valid, with 30 measured transitions each and no refusal.

| Pair | Order | Highest load at a run’s start | Highest load at a transition’s start | Status |
| --- | --- | ---: | ---: | --- |
| `06-59-22#1` | control, candidate | 7.87 | 7.14 | valid |
| `06-59-22#2` | candidate, control | 11.29 | 13.69 | excluded (load) |
| `06-59-22#3` | control, candidate | 13.04 | 20.10 | excluded (load) |
| `07-20-31#1` | control, candidate | 16.40 | 14.36 | excluded (load) |
| `07-20-31#2` | candidate, control | 11.80 | 13.10 | excluded (load) |
| `07-36-12#1` | control, candidate | 24.88 | 35.26 | excluded (load) |
| `07-36-12#2` | candidate, control | 36.52 | 75.79 | excluded (load) |
| `09-25-37#1` | control, candidate | 7.22 | 8.96 | valid |
| `09-25-37#2` | candidate, control | 5.74 | 7.46 | valid |

Six of nine pairs were excluded.
Their rows are kept, not judged, in
[exp-065-transition-excluded-samples.jsonl](exp-065-transition-excluded-samples.jsonl).
Each run took 201 to 225 s. The tree probe’s three pairs ran at a one-minute load of
5.20 to 10.45 at run starts and clicks, and none was excluded; the hold probe’s three
runs at 5.24 to 5.66.

## Results

The tables below are compare’s output on
[the kept samples](exp-065-transition-samples.jsonl)
(`compare --control control --candidate candidate`), `summarize` on the same file, the
derived readings in [exp-065-derived-samples.jsonl](exp-065-derived-samples.jsonl) (from
the kept full rows), the tree probe’s [samples](exp-065-tree-late-samples.jsonl), and
the hold [spans](exp-065-hold-spans.json).
Times are median (range) over three runs; pair ratios are candidate over control.

### Part (a): reads of the selected record per click

| Reading | Control | Candidate |
| --- | --- | --- |
| Duplicate reads, five clicks, per run | 6 (6–6) | 0 (0–0) |
| `pulls.list_to_pr.cold` | 2 (1–2) | 0 |
| `pulls.pr_to_pr.cold` | 1 | 0 |
| `pulls.pr_to_pr.revisit` | 0 (0–1) | 0 |
| `pulls.pr_to_pr.hover_click` | 1 | 0 |
| `pulls.pr_changes_to_pr` | 2 | 0 |
| Settlement reads, `pulls.pr_to_pr.cold` (shown, not judged) | 3 | 0–2 |

Every click reads its record once in the candidate.
The revisit’s ranges overlap, since the control read it twice in only one run.

### Part (b): a late file list

| Reading, per run | Control | Candidate |
| --- | --- | --- |
| No-input layout shift, Pulls panel | 0.05 (0.05–0.05) | 0 (0–0) |
| Rows drawn with no input past 500 ms | 43 (43–43) | 0 (0–0) |
| When the list arrived, after the click | 3,113 to 3,132 ms, drawn | 3,114 to 3,122 ms, offered as “Show 32 files” |

### Part (c): Changes first paint

| Transition | Control body shift after ready | Candidate | Control `shift_count` | Candidate |
| --- | --- | --- | --- | --- |
| `pulls.tab.changes_first` | 0.2188 (0.2188–0.2235) | 0 | 3–4 | 1 |
| `pulls.tab.changes_revisit` | 0.2204 (0.2157–0.4554) | 0 | 2–3 | 1 |
| `pulls.tab.changes_first_2` | 0.4854 (0.1605–0.4854) | 0 | 2 | 1 |
| `pulls.tab.changes_revisit_2` | 0.4854 (0.1605–0.4854) | 0 | 2 | 1 |
| Per run, the four | 1.0851 (1.0851–1.645) | 0 (0–0) |  |  |

The control’s shifts are the diff’s files moving as rendered Markdown arrives, within
the click’s input window, which is why `shift_sum_no_input` reads 0 on both sides.

### Guards

| Transition | Metric | Control | Candidate | Pairs |
| --- | --- | --- | --- | --- |
| `pulls.tab.changes_first` | painted ready | 46.4 (45.2–46.6) | 110.3 (95.3–110.5) | 2.38x, 3 of 3 beyond |
| `pulls.tab.changes_revisit` | painted ready | 45.0 (44.6–46.4) | 78.3 (75.3–79.2) | 1.74x, 3 of 3 beyond |
| `pulls.tab.changes_first_2` | painted ready | 46.1 (44.2–46.4) | 96.0 (96.0–108.2) | 2.08x, 3 of 3 beyond |
| `pulls.tab.changes_revisit_2` | painted ready | 43.7 (42.7–44.7) | 95.4 (93.3–96.6) | 2.19x, 3 of 3 beyond |
| `pulls.list_to_pr.cold` | description final | 74.7 (72.5–76.1) | 90.6 (90.4–100.8) | 1.25x, 1 of 3 beyond (a rerun, not a result) |
| `pulls.pr_to_pr.cold` | description shown | 45.8 (45.6–46.3) | 61.4 (61.2–62.6) | 1.34x, 3 of 3 beyond |
| `pulls.pr_to_pr.cold` | description final | 63 (62–63) | 61 (61–63) | no detected difference |
| `pulls.pr_to_pr.hover_click` | description shown | 30.9 (30.5–43.9) | 80.4 (80.2–81.5) | 2.60x, 3 of 3 beyond |
| `pulls.pr_to_pr.hover_click` | description final | 63.8 (60.7–64.1) | 80.4 (80.2–81.5) | 1.28x, 1 of 3 beyond (a rerun, not a result) |
| `pulls.pr_changes_to_pr` | description final | 79.4 (77.8–79.5) | 111.9 (111.4–112.7) | 1.42x, 3 of 3 beyond |

The description final times are the ones the reader sees as final in both builds; the
control’s description showed as plain text 17 to 33 ms before them on these transitions
(exp-080). Against exp-052 and exp-055’s prepared-click figures, measured in other
regimes, the candidate’s finals of 61 to 112 ms are within or above exp-055’s 71–80 ms,
and above exp-052’s 37–40 ms.

### Hold spans

| Span | n | Held, ms | Median | Bound | Outcomes |
| --- | ---: | --- | ---: | ---: | --- |
| `githubPull:firstPaintHold` (`hidden`) | 12 | 25 to 151 | 41.5 | 200 | 12 `met` |
| `githubPull:changesHold` | 18 | 31 to 74 | 58 | 200 | 18 `met` |
| `githubPulls:openingHold` | 12 | 34 to 68 | 40 | 150 | 12 `met` |
| `githubPulls:lateRowsHold` | 0 |  |  |  |  |

No hold reached its bound, and each median is under half its bound, so the guard holds.
Every first-paint hold waited for one text, the description, which fills these pull
requests’ first screens.
The 151, 98, and 95 ms holds are each run’s first pull request, which also loads
`inert-html` and KPress’s stylesheets.
The warm server holds every list, so no late rows were held.

### What moved the wrong way

Compare reports 62 wrong-way results.
All but two are on pull request transitions:

- **The holds.** `painted_ready_ms`, `ready_ms`, `frames_to_ready`,
  `ready_after_last_input_ms`, `pr_header_ms`, and `pr_description_shown_ms` rise on the
  cold clicks, the revisit, and the four Changes paints, by one to four frames.
  The page is not ready while its first paint waits out of sight, and the spans above
  are that wait.
- **`settled_ms` on the Changes revisits and the second Changes paint**, 70.8 to 222.2
  ms (`changes_first_2`) and 70.9 to 221.8 ms (`changes_revisit_2`), and on four
  Conversation clicks by 27 to 52 ms.
  With no shift in the window (one entry, the age line’s, as in the control), this is
  inferred to be the comparison’s Markdown files past its first screen still rendering
  after the first screen shows, and the conversation’s texts past the first screen
  arriving, both out of the reader’s first screen.
  Not measured further.
- **`dom_nodes_end`** higher by about 750 to 1,100 nodes on
  `pulls.pr_to_pr.hover_click`, `pulls.history_back`, and `pulls.pr_changes_to_pr`;
  **`data_network`** from 17–21 to 22–24 and from 19 to 20–23 on the first and last; and
  `requests_data` from 11 to 12 on `main_subject.commits_to_pulls`. The first-screen
  comments and the texts asked for ahead of them are asked for during the hold and
  rendered as Markdown, which is larger than plain text.
- **The two off pull requests.** `pulls.first_show` `settled_ms`, 9.9 (9.6–12.1) to 18.1
  (9.8–38.9), ranges overlapping with two of three pairs beyond; and
  `main_subject.files_to_commits` `ready_ms`, 204.4 (156.1–262.1) to 212.2
  (207.3–1069.7), ranges overlapping with two of three pairs beyond, one of them a
  1,069.7 ms candidate run whose painted ready (1,084.3 ms) compare lists as a rerun.
  The Pulls list and the Commits view run none of this round’s code except the diff
  plugin’s `checkFirstScreen`, which returns at once once its first screen has settled,
  so they are taken as noise on a loaded machine; compare owes both a rerun before a
  release.

### What did not move

`blank_frames`, placeholder frames, `preview_top_replaced`, and `shift_sum_no_input` on
every pull request transition; every `main.*` transition’s painted ready; and the Checks
tab. The pulls list’s own first show is within the tolerance in two of three pairs.

## Verdict

- **(a) Accepted.** The named metric fell from 6 to 0 with separated ranges, and no
  click read more. Its guard, description readiness on the cold clicks, moved the wrong
  way, and the read change cannot have caused it: the candidate reads less.
  It is the first- paint hold of part (c) and of exp-080, the spans above.
- **(b) Accepted, on the pilot instrument.** The scenario cannot exercise a late list.
  The probe shows the change the registry names: no growth with no input, and no shift.
- **(c) Accepted.** Every Changes paint’s shift after ready went to 0. Its guard is the
  cost: Changes is ready 33 to 64 ms later in every pair, at 78 to 110 ms.
- **Complexity, a judgment.** The hold costs one to four frames on these transitions,
  bounded at 200 ms, and removes shifts of 0.16 to 0.49 per Changes paint and the
  duplicate reads entirely.
  The owner’s stated requirement is that nothing shifts or flashes as a page loads, and
  every figure the reader waits for stays near 110 ms or under.
  Worth it.

Instruments: parts (a) and (c), and the guards, by the transition scenario; part (b) by
the tree probe; the hold spans by the hold probe.

## Changes After the Measured Candidate

These came after `5a56f0a8` and are off the paths this round measured, so they were not
measured again:

- `62ebfd75` (review E1, E2): a page that goes while its Changes hold waits keeps the
  diff out of sight and records the wait as `cancelled`; the tab keys’ wait under a held
  first paint is stated and tested.
  The series never cancels a page during a hold.

## Limits

- Three valid pairs per condition, the minimum, on a machine whose load ran from 5 to 76
  during the series; two identical builds separate on one comparison 10% of the time at
  this n (compare: 125 of 1,715 comparisons came apart, about 37 expected by chance).
- Headless Chrome only; WebKit, which the native app uses, is not measured.
- The tree probe is a pilot instrument, not the transition scenario: one subject, a cold
  server, 12 s windows.
- The milestones’ on-screen test does not read visibility, so on a transition whose page
  is installed straight into the pane, `pr_description_shown_ms` can fire on the held,
  hidden description (exp-080).
- The pilot instruments in [exp-065-instruments/](exp-065-instruments/) are committed as
  they ran, then formatted and lint-fixed with no change in behavior; the derivation and
  the exclusions give byte-identical output from them.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->

---
title: Every Region's Box at First Paint
softschema:
  contract: metabrowser.loadtime:Experiment/v1
  schema: experiment.schema.yaml
  envelope: experiment
  status: enforced
experiment:
  id: exp-059
  title: Every Region's Box at First Paint
  date: "2026-11-13"
  hypotheses:
    - H86
  subject:
    corpus: Standalone clone of this repository at 7a02fed4 with its own refs, clean; its commit, trunk, and refs did not move during the series.
    corpus_files: 1286
    host_cpu: 10 CPUs
    host_system: Darwin 25.5.0 arm64, Node 24.19.0
    browser: Headless Chrome 152.0.7977.83 over the DevTools Protocol, a fresh profile per journey, trusted pointer and key input.
    viewport: 1440x900
    cold: false
  method:
    runs_per_condition: 4
    interleaved: true
    control: metab 0.12.1.dev165+9903292 (+165 commits, 099032928), the editable control checkout at origin/main 09903292, clean at the start and end of every run, one server process per run.
    candidate: metab 0.12.1.dev165+9903292 (+176 commits, 28e12fa28), the editable checkout of this branch at 28e12fa2, clean at the start and end of every run, one server process per run, run back to back with the control in alternating order.
    record: exp-059-transition-samples.jsonl
  results:
    - metric: region_movement_px.files.cold.source_large
      control_median: 30
      candidate_median: 0
      control_range: [30, 30]
      candidate_range: [0, 0]
      overlapping: false
    - metric: region_movement_px.files.cold.json
      control_median: 30
      candidate_median: 0
      control_range: [30, 30]
      candidate_range: [0, 0]
      overlapping: false
    - metric: region_movement_px.files.cold.diff
      control_median: 30
      candidate_median: 0
      control_range: [30, 30]
      candidate_range: [0, 0]
      overlapping: false
    - metric: region_movement_px.files.cold.image
      control_median: 11
      candidate_median: 0
      control_range: [11, 11]
      candidate_range: [0, 0]
      overlapping: false
    - metric: region_movement_px.files.cold.binary
      control_median: 11
      candidate_median: 0
      control_range: [11, 11]
      candidate_range: [0, 0]
      overlapping: false
    - metric: region_movement_px.files.revisit.json
      control_median: 30
      candidate_median: 0
      control_range: [30, 30]
      candidate_range: [0, 0]
      overlapping: false
    - metric: region_movement_px.keyboard.down_cold.1
      control_median: 11
      candidate_median: 0
      control_range: [11, 11]
      candidate_range: [0, 0]
      overlapping: false
    - metric: region_movement_px.keyboard.down_cold.2
      control_median: 11
      candidate_median: 0
      control_range: [11, 11]
      candidate_range: [0, 0]
      overlapping: false
    - metric: region_movement_px.keyboard.down_cold.3
      control_median: 30
      candidate_median: 0
      control_range: [30, 30]
      candidate_range: [0, 0]
      overlapping: false
    - metric: region_movement_px.keyboard.up_revisit.1
      control_median: 30
      candidate_median: 0
      control_range: [30, 30]
      candidate_range: [0, 0]
      overlapping: false
    - metric: region_movement_px.keyboard.up_revisit.2
      control_median: 11
      candidate_median: 0
      control_range: [11, 11]
      candidate_range: [0, 0]
      overlapping: false
    - metric: region_movement_px.main.files_to_commits.first
      control_median: 37
      candidate_median: 0
      control_range: [37, 37]
      candidate_range: [0, 0]
      overlapping: false
    - metric: region_movement_px.main.commits_to_files.first
      control_median: 37
      candidate_median: 0
      control_range: [37, 37]
      candidate_range: [0, 0]
      overlapping: false
    - metric: region_movement_px.main.files_to_commits.again
      control_median: 37
      candidate_median: 0
      control_range: [37, 37]
      candidate_range: [0, 0]
      overlapping: false
    - metric: region_movement_px.main.commits_to_files.again
      control_median: 37
      candidate_median: 0
      control_range: [37, 37]
      candidate_range: [0, 0]
      overlapping: false
    - metric: region_movement_px.main.files_to_pulls.first
      control_median: 37
      candidate_median: 0
      control_range: [37, 37]
      candidate_range: [0, 0]
      overlapping: false
    - metric: region_movement_px.main.pulls_to_files.first
      control_median: 37
      candidate_median: 0
      control_range: [37, 37]
      candidate_range: [0, 0]
      overlapping: false
    - metric: region_movement_px.main.files_to_pulls.again
      control_median: 37
      candidate_median: 0
      control_range: [37, 37]
      candidate_range: [0, 0]
      overlapping: false
    - metric: region_movement_px.main.pulls_to_files.again
      control_median: 37
      candidate_median: 0
      control_range: [37, 37]
      candidate_range: [0, 0]
      overlapping: false
    - metric: region_movement_px.main_subject.files_to_commits
      control_median: 37
      candidate_median: 0
      control_range: [37, 37]
      candidate_range: [0, 0]
      overlapping: false
    - metric: region_movement_px.main_subject.pulls_to_files
      control_median: 37
      candidate_median: 0
      control_range: [37, 37]
      candidate_range: [0, 0]
      overlapping: false
    - metric: region_movement_px.main_subject.files_to_pulls
      control_median: 37
      candidate_median: 0
      control_range: [37, 37]
      candidate_range: [0, 0]
      overlapping: false
    - metric: region_movement_px.main_subject.commits_to_files
      control_median: 37
      candidate_median: 0
      control_range: [37, 37]
      candidate_range: [0, 0]
      overlapping: false
    - metric: region_movement_px.commits.first_show
      control_median: 37
      candidate_median: 0
      control_range: [37, 37]
      candidate_range: [0, 0]
      overlapping: false
    - metric: region_movement_px.pulls.first_show
      control_median: 37
      candidate_median: 0
      control_range: [37, 37]
      candidate_range: [0, 0]
      overlapping: false
    - metric: region_movement_px.tree.expand.docs
      control_median: 11
      candidate_median: 0
      control_range: [11, 11]
      candidate_range: [0, 0]
      overlapping: false
    - metric: region_movement_px.skim.held_arrow_down
      control_median: 30
      candidate_median: 0
      control_range: [30, 30]
      candidate_range: [0, 0]
      overlapping: false
    - metric: shift_sum_no_input.landing.reload
      control_median: 0.0002
      candidate_median: 0
      control_range: [0.0002, 0.0002]
      candidate_range: [0, 0]
      overlapping: false
    - metric: region_movement_px.pulls.tab.changes_first
      control_median: 8
      candidate_median: 0
      control_range: [8, 8]
      candidate_range: [0, 0]
      overlapping: false
    - metric: region_movement_px.pulls.tab.checks_first
      control_median: 8
      candidate_median: 0
      control_range: [8, 8]
      candidate_range: [0, 0]
      overlapping: false
    - metric: region_movement_px.pulls.tab.changes_revisit
      control_median: 8
      candidate_median: 0
      control_range: [8, 8]
      candidate_range: [0, 0]
      overlapping: false
    - metric: region_movement_px.pulls.tab.conversation_revisit_2
      control_median: 8
      candidate_median: 0
      control_range: [8, 8]
      candidate_range: [0, 0]
      overlapping: false
    - metric: region_movement_px.pulls.tab.changes_first_2
      control_median: 8
      candidate_median: 0
      control_range: [8, 8]
      candidate_range: [0, 0]
      overlapping: false
    - metric: region_movement_px.pulls.tab.changes_revisit_2
      control_median: 8
      candidate_median: 0
      control_range: [8, 8]
      candidate_range: [0, 0]
      overlapping: false
    - metric: region_movement_px.pulls.history_back
      control_median: 8
      candidate_median: 0
      control_range: [8, 8]
      candidate_range: [0, 0]
      overlapping: false
    - metric: region_movement_px.pulls.pr_changes_to_pr
      control_median: 8
      candidate_median: 0
      control_range: [8, 8]
      candidate_range: [0, 0]
      overlapping: false
  complexity:
    lines_changed: 653
    new_dependencies: []
    new_failure_modes:
      - "A row reserved at one line cuts long text short, with its whole text in a tooltip, and a toolbar wider than a narrowed pane scrolls along its row."
      - "A failure in the pull request status row wraps it and moves the tab bar, by design: it is the one state allowed to move."
    notes: "653 source lines changed in the four H86 commits (0e53da60, 2d9d2960, 2538f270, d074d681), plus a share of the 699 lines of review fixes (475e2327, 666a066c, 28e12fa2) that H86 and H91 have together. One judgment: worth it, because every box is decided by rules a reader can find (line units, struts, one toolbar slot, a Chrome check of the header) rather than by measured pixels, and the cost is that a reserved one-line row cuts long text short, with a tooltip, instead of wrapping."
  verdict:
    decision: accepted
    primary_metric: region_movement_px
    reason: "Every deciding result moved as predicted with ranges apart: region movement went to 0 in every candidate run on the 27 shell-chrome transitions and the 8 pull request header transitions, landing.reload's shift with no input went 0.0002 to 0, and no pull request switch rose. No declared guard moved the wrong way, and every other wrong-way result is accounted for."
    commit: 28e12fa2
---
**Status:** Accepted: (a) the shell’s chrome and (b) the pull request header both meet

## Note, 2026-11-13

After this round the branch changed the layout of paths this record measured, and none
of it is measured here: the verdict stands as recorded, for the candidate `28e12fa2`.
Review E’s fix (`6037a0a4`: no late stack chip or long login moves or hides the merge),
review F’s fixes (`29808715`: the Pulls stack column capped, the state badge sized to
its widest label, tab focus kept across the hold, and the retarget tests; `49d77cc2`: a
Pulls row’s title keeps 4ch beside its stack position), the run status badge sized to
its widest label from first paint (`ac190158`), and the merges of `main` through
`d36936c8` and after it.

the accept rule.

One interleaved series, four back-to-back pairs on scenario revision 4, measured this
branch after review rounds 1 and 2 against origin/main.
H86 says a region’s box can be decided at the first paint from what the first response
already knows, so that nothing under it moves when its content arrives: (a) the shell’s
chrome (the navigation’s toolbar slot, the Commits tab, scrollbar gutters, the view tab
bar, the file header’s slots) and (b) the pull request header’s rows.

## What Changed

(a) Shell chrome, `0e53da60`, `2538f270`, `d074d681`, and part of `475e2327`:

- One toolbar slot at the top of the navigation, filled on every main tab by that tab’s
  toolbar at one height (the Files filters, the Commits tally, the Pulls filters); the
  server draws the landing tab’s toolbar, and Commits in front on a commit’s address.
  A toolbar wider than a narrowed pane scrolls along its row.
- The Commits tab is drawn by the server at a repository’s root, before Git discovery; a
  press before discovery opens it on registration.
- Stable scrollbar gutters on the tree and the preview, the shortcut-hints row reserved,
  a view tab bar in every file, and the print button’s and run badge’s slots kept.
- The folder Overview holds the previous folder until its first rollup answers, at most
  100 ms.

(b) The pull request header, `2d9d2960` and part of `475e2327`:

- A title of two reserved lines, clamped there with its number outside the clamp; a
  one-line state row whose sentence gives way before its branch chips, with the stack
  chip’s slot held by a strut; the state badge as wide as the widest state, its label
  its first flex item; the quiet and label rows always present at one line; a status row
  with Refresh’s slot on every tab and the offers grouped with it, wrapping only for a
  failure.
- A cold page shows these rows, empty, with its tab bar over the body’s pulse, instead
  of the shell’s generic skeleton.

## Protocol

Declared before the measured series (the criteria were first declared for the revision 3
series and restated unchanged for each later one; metric names are identical in revision
4):

- (a) Deciding metric `region_movement_px`, lower to 0, on every transition where the
  exp-058 baseline moved shell chrome: the 28 listed in the first table below, plus
  `landing.reload`’s `shift_sum_no_input`, lower (the late Commits tab).
  Guards: `painted_ready_ms` and `blank_frames` on the cold, keyboard, and main-tab
  transitions in the guard table.
- (b) Deciding metric `region_movement_px`, lower to 0, on the eight pull request tab
  and history transitions in the second table; and no rise on `pulls.list_to_pr.cold`
  and the three `pulls.pr_to_pr.*` switches.
  Guards: `painted_ready_ms`, `pr_header_ms`, and `blank_frames` on the transitions in
  the guard table.
- Series: one invocation of `transitions.mjs run` at harness `5031dc16` (scenario
  revision 4, frozen), four runs per condition, control and candidate back to back in
  each pair and alternating which goes first, every journey once unrecorded and then
  measured, each journey in a fresh Chrome profile and each run on a fresh server.
  To use less machine time it ran the journeys the criteria and guards read, declared
  before the series: landing, files, keyboard, maintabs, commits, pulls, tree, palette,
  skim, and reveal, all but views.
- Load, declared before the series: the series lock was taken only after the one-minute
  load had stayed under 12 for two minutes, and a pair is excluded, before any result is
  read, if either of its runs saw a one-minute load above 12 at its start or at any
  measured transition’s start; excluded rows are kept and named, and pairs are added
  until at least three are valid.
- Conditions: the control is origin/main `09903292`; the candidate is this branch at
  `28e12fa2`, after review rounds 1 and 2 (reviews A, B, and C). The corpus is the
  standalone clone every round of this campaign uses.
- Earlier rows of this lane, at `078c4c69` before review round 1 (a revision 3 series
  and an interim revision 4 series), are diagnostics: they are cited here only as
  evidence about the instrument, never as a verdict.
- Accept rule, as declared: a deciding metric is a result when its median moved in the
  predicted direction and the two conditions’ ranges do not overlap, with at least three
  valid runs a side; a guard blocks a verdict when `compare` calls it wrong-way under
  the pair rule (the 1.3x tolerance); every other wrong-way result is listed and
  accounted for, or the verdict it touches is not accepted.
  A sub-claim that misses is rejected or unresolved and is not re-scored on another
  metric.
- One series serves exp-059 (H86) and exp-064 (H91). Their mechanisms and their deciding
  transitions do not overlap, so neither round’s change can produce the other’s result;
  both artifacts read the same [samples](exp-059-transition-samples.jsonl).

## Verdicts

- **(a) Shell chrome: accepted.** The 27 transitions where the exp-058 baseline moved
  shell chrome moved at the control and 0 in every candidate run, ranges apart: from 37
  to 0 px on a first switch to Commits and 30 to 0 px on a cold JSON file, for example.
  `landing.reload`’s layout shift with no input, the late Commits tab, went 0.0002 to 0.
  Neither guard, painted ready nor blank frames, moved the wrong way on any guarded
  transition.
- **(b) Pull request header: accepted.** The eight tab and history transitions moved 8
  px at the control and 0 in every candidate run, ranges apart.
  The four pull request switches stayed at 0 on both builds, so none rose.
  No guard (painted ready, the header’s time, blank frames) moved the wrong way.

## Complexity

653 source lines changed in the four H86 commits (0e53da60, 2d9d2960, 2538f270,
d074d681), plus a share of the 699 lines of review fixes (475e2327, 666a066c, 28e12fa2)
that H86 and H91 have together.
One judgment: worth it, because every box is decided by rules a reader can find (line
units, struts, one toolbar slot, a Chrome check of the header) rather than by measured
pixels, and the cost is that a reserved one-line row cuts long text short, with a
tooltip, instead of wrapping.

## Results

The deciding metric’s tables are `compare`’s, lifted by script from its JSON: each
median with its range, and the median of the back-to-back pair ratios.

### H86 (a) shell chrome

| Transition | Metric | Control | Candidate | Pair ratio | compare verdict |
| --- | --- | ---: | ---: | ---: | --- |
| `files.cold.source_large` | region_movement_px | 30 | 0 | — | lower, ranges apart (result) |
| `files.cold.json` | region_movement_px | 30 | 0 | — | lower, ranges apart (result) |
| `files.cold.diff` | region_movement_px | 30 | 0 | — | lower, ranges apart (result) |
| `files.cold.image` | region_movement_px | 11 | 0 | — | lower, ranges apart (result) |
| `files.cold.binary` | region_movement_px | 11 | 0 | — | lower, ranges apart (result) |
| `files.revisit.json` | region_movement_px | 30 | 0 | — | lower, ranges apart (result) |
| `keyboard.down_cold.1` | region_movement_px | 11 | 0 | — | lower, ranges apart (result) |
| `keyboard.down_cold.2` | region_movement_px | 11 | 0 | — | lower, ranges apart (result) |
| `keyboard.down_cold.3` | region_movement_px | 30 | 0 | — | lower, ranges apart (result) |
| `keyboard.up_revisit.1` | region_movement_px | 30 | 0 | — | lower, ranges apart (result) |
| `keyboard.up_revisit.2` | region_movement_px | 11 | 0 | — | lower, ranges apart (result) |
| `main.files_to_commits.first` | region_movement_px | 37 | 0 | — | lower, ranges apart (result) |
| `main.commits_to_files.first` | region_movement_px | 37 | 0 | — | lower, ranges apart (result) |
| `main.files_to_commits.again` | region_movement_px | 37 | 0 | — | lower, ranges apart (result) |
| `main.commits_to_files.again` | region_movement_px | 37 | 0 | — | lower, ranges apart (result) |
| `main.files_to_pulls.first` | region_movement_px | 37 | 0 | — | lower, ranges apart (result) |
| `main.pulls_to_files.first` | region_movement_px | 37 | 0 | — | lower, ranges apart (result) |
| `main.files_to_pulls.again` | region_movement_px | 37 | 0 | — | lower, ranges apart (result) |
| `main.pulls_to_files.again` | region_movement_px | 37 | 0 | — | lower, ranges apart (result) |
| `main_subject.files_to_commits` | region_movement_px | 37 | 0 | — | lower, ranges apart (result) |
| `main_subject.pulls_to_files` | region_movement_px | 37 | 0 | — | lower, ranges apart (result) |
| `main_subject.files_to_pulls` | region_movement_px | 37 | 0 | — | lower, ranges apart (result) |
| `main_subject.commits_to_files` | region_movement_px | 37 | 0 | — | lower, ranges apart (result) |
| `commits.first_show` | region_movement_px | 37 | 0 | — | lower, ranges apart (result) |
| `pulls.first_show` | region_movement_px | 37 | 0 | — | lower, ranges apart (result) |
| `tree.expand.docs` | region_movement_px | 11 | 0 | — | lower, ranges apart (result) |
| `skim.held_arrow_down` | region_movement_px | 30 | 0 | — | lower, ranges apart (result) |
| `landing.reload` | shift_sum_no_input | 0.0002 | 0 | — | lower, ranges apart (result) |

Guards:

| Transition | Metric | Control | Candidate | Pair ratio | compare verdict |
| --- | --- | ---: | ---: | ---: | --- |
| `files.cold.source_large` | painted_ready_ms | 113.2 (97.1–113.5) | 105.15 (96.5–114.6) | 1.00x (0.85–1.01) | no detected difference |
| `files.cold.source_large` | blank_frames | 0 | 0 | 1.00x (1.00–1.00) | no detected difference |
| `files.cold.json` | painted_ready_ms | 64.5 (63.7–80.3) | 64.15 (63.7–64.8) | 1.00x (0.80–1.00) | no detected difference |
| `files.cold.json` | blank_frames | 0 | 0 | 1.00x (1.00–1.00) | no detected difference |
| `keyboard.down_cold.1` | painted_ready_ms | 54.65 (53.1–57.7) | 53.05 (42.8–55.2) | 0.97x (0.74–1.03) | ranges overlap; one pair of 4 is lower beyond the 1.3x tolerance (2026-11-13T09-51-52-203Z#1): rerun that pair back to back before a release (listed, not a wrong-way result) |
| `keyboard.down_cold.1` | blank_frames | 0 | 0 | 1.00x (1.00–1.00) | no detected difference |
| `main.files_to_commits.again` | painted_ready_ms | 30.3 (27.2–30.8) | 29.1 (27.5–30.8) | 0.98x (0.95–1.01) | no detected difference |
| `main.files_to_commits.again` | blank_frames | 0 | 0 | 1.00x (1.00–1.00) | no detected difference |
| `main.commits_to_files.again` | painted_ready_ms | 63.5 (62.8–64.4) | 64.25 (63–77.4) | 1.01x (0.99–1.22) | no detected difference |
| `main.commits_to_files.again` | blank_frames | 2 | 2 | 1.00x (1.00–1.00) | no detected difference |
| `main.files_to_pulls.again` | painted_ready_ms | 29.9 (26.9–31) | 29.9 (24.7–31.8) | 1.00x (0.80–1.18) | no detected difference |
| `main.files_to_pulls.again` | blank_frames | 0 | 0 | 1.00x (1.00–1.00) | no detected difference |
| `main.pulls_to_files.again` | painted_ready_ms | 64.25 (62.8–65.1) | 63.65 (62.7–63.9) | 0.99x (0.98–1.00) | no detected difference |
| `main.pulls_to_files.again` | blank_frames | 2 | 2 | 1.00x (1.00–1.00) | no detected difference |
| `commits.first_show` | painted_ready_ms | 279.25 (263.5–280.2) | 279.3 (263.3–297.1) | 1.03x (0.94–1.06) | no detected difference |
| `commits.first_show` | blank_frames | 0 | 0 | 1.00x (1.00–1.00) | no detected difference |
| `pulls.first_show` | painted_ready_ms | 30.7 (28.7–31.9) | 29.5 (28.5–31.9) | 0.96x (0.90–1.11) | no detected difference |
| `pulls.first_show` | blank_frames | 0 | 0 | 1.00x (1.00–1.00) | no detected difference |

### H86 (b) pull request header

| Transition | Metric | Control | Candidate | Pair ratio | compare verdict |
| --- | --- | ---: | ---: | ---: | --- |
| `pulls.tab.changes_first` | region_movement_px | 8 | 0 | — | lower, ranges apart (result) |
| `pulls.tab.checks_first` | region_movement_px | 8 | 0 | — | lower, ranges apart (result) |
| `pulls.tab.changes_revisit` | region_movement_px | 8 | 0 | — | lower, ranges apart (result) |
| `pulls.tab.conversation_revisit_2` | region_movement_px | 8 | 0 | — | lower, ranges apart (result) |
| `pulls.tab.changes_first_2` | region_movement_px | 8 | 0 | — | lower, ranges apart (result) |
| `pulls.tab.changes_revisit_2` | region_movement_px | 8 | 0 | — | lower, ranges apart (result) |
| `pulls.history_back` | region_movement_px | 8 | 0 | — | lower, ranges apart (result) |
| `pulls.pr_changes_to_pr` | region_movement_px | 8 | 0 | — | lower, ranges apart (result) |

No rise on a pull request switch:

| Transition | Metric | Control | Candidate | Pair ratio | compare verdict |
| --- | --- | ---: | ---: | ---: | --- |
| `pulls.list_to_pr.cold` | region_movement_px | 0 | 0 | — | no detected difference |
| `pulls.pr_to_pr.cold` | region_movement_px | 0 | 0 | — | no detected difference |
| `pulls.pr_to_pr.revisit` | region_movement_px | 0 | 0 | — | no detected difference |
| `pulls.pr_to_pr.hover_click` | region_movement_px | 0 | 0 | — | no detected difference |

Guards:

| Transition | Metric | Control | Candidate | Pair ratio | compare verdict |
| --- | --- | ---: | ---: | ---: | --- |
| `pulls.list_to_pr.cold` | painted_ready_ms | 57.15 (57–58.1) | 56.85 (39.9–58.1) | 1.00x (0.69–1.02) | ranges overlap; one pair of 4 is lower beyond the 1.3x tolerance (2026-11-13T09-51-52-203Z#1): rerun that pair back to back before a release (listed, not a wrong-way result) |
| `pulls.list_to_pr.cold` | pr_header_ms | 57.15 (57–58.1) | 56.85 (39.9–58.1) | 1.00x (0.69–1.02) | ranges overlap; one pair of 4 is lower beyond the 1.3x tolerance (2026-11-13T09-51-52-203Z#1): rerun that pair back to back before a release (listed, not a wrong-way result) |
| `pulls.list_to_pr.cold` | blank_frames | 1 | 1 | 1.00x (1.00–1.00) | no detected difference |
| `pulls.tab.changes_first` | painted_ready_ms | 45.55 (44.6–45.8) | 45.8 (44.6–52.9) | 1.01x (0.97–1.19) | no detected difference |
| `pulls.tab.changes_first` | pr_header_ms | 28.9 (28–29.1) | 28.45 (19.6–29.2) | 0.98x (0.70–1.01) | ranges overlap; one pair of 4 is lower beyond the 1.3x tolerance (2026-11-13T09-51-52-203Z#4): rerun that pair back to back before a release (listed, not a wrong-way result) |
| `pulls.tab.changes_first` | blank_frames | 0 | 0 | 1.00x (1.00–1.00) | no detected difference |
| `pulls.tab.checks_first` | painted_ready_ms | 28.75 (26.2–29.6) | 28.55 (28.3–29.5) | 1.01x (0.96–1.08) | no detected difference |
| `pulls.tab.checks_first` | pr_header_ms | 28.75 (26.2–29.6) | 28.55 (28.3–29.5) | 1.01x (0.96–1.08) | no detected difference |
| `pulls.tab.checks_first` | blank_frames | 0 | 0 | 1.00x (1.00–1.00) | no detected difference |
| `pulls.pr_to_pr.cold` | painted_ready_ms | 45.4 (44.3–46) | 44.3 (43.8–46.2) | 0.99x (0.95–1.01) | no detected difference |
| `pulls.pr_to_pr.cold` | pr_header_ms | 45.4 (44.3–46) | 44.3 (43.8–46.2) | 0.99x (0.95–1.01) | no detected difference |
| `pulls.pr_to_pr.cold` | blank_frames | 0 | 0 | 1.00x (1.00–1.00) | no detected difference |
| `pulls.pr_to_pr.revisit` | painted_ready_ms | 26.05 (25.3–27.7) | 27.85 (26.3–28.3) | 1.04x (1.00–1.12) | no detected difference |
| `pulls.pr_to_pr.revisit` | pr_header_ms | 26.05 (25.3–27.7) | 27.85 (26.3–28.3) | 1.04x (1.00–1.12) | no detected difference |
| `pulls.pr_to_pr.revisit` | blank_frames | 0 | 0 | 1.00x (1.00–1.00) | no detected difference |
| `pulls.history_back` | painted_ready_ms | 45.15 (36.5–52.9) | 41.4 (38.8–52.1) | 0.96x (0.73–1.38) | ranges overlap; one pair of 4 is lower beyond the 1.3x tolerance (2026-11-13T09-51-52-203Z#4): rerun that pair back to back before a release (listed, not a wrong-way result) |
| `pulls.history_back` | pr_header_ms | 45.15 (36.5–52.9) | 41.4 (38.8–52.1) | 0.96x (0.73–1.38) | ranges overlap; one pair of 4 is lower beyond the 1.3x tolerance (2026-11-13T09-51-52-203Z#4): rerun that pair back to back before a release (listed, not a wrong-way result) |
| `pulls.history_back` | blank_frames | 0 | 0 | 1.00x (1.00–1.00) | no detected difference |

## Identities

| Item | Value |
| --- | --- |
| Control build | `metab 0.12.1.dev165+9903292 (+165 commits, 099032928)`, editable checkout at `09903292`, clean at the start and end of every run |
| Candidate build | `metab 0.12.1.dev165+9903292 (+176 commits, 28e12fa28)`, editable checkout of this branch at `28e12fa2`, clean at the start and end of every run |
| Corpus | Standalone clone at `7a02fed4` with its own refs (hash `387f68dc4e8eb8e0`), clean, 1,286 indexed files; commit, cleanliness, trunk, and refs the same at the start and end of every run |
| Harness | `5031dc16`, clean, in all 8 runs; scenario revision 4 |
| Chrome | 152.0.7977.83, headless, 1440x900 |
| Host | Darwin 25.5.0 arm64, 10 CPUs, Node 24.19.0 |

## Load and Refusals

Each run took 414 to 427 s, from 2026-11-13T09:51:52.205Z to 2026-11-13T10:47:34.608Z.
The one-minute load average was 3.76 to 6.97 at run starts and ends and 3.11 to 10.93
when each measured transition started (five-minute 4.25 to 6.05). The series held the
shared series lock throughout, so no other lane’s timed run overlapped it.
No run was refused.

The load rule, declared before the series, excluded none of the 4 pairs: no run started
above a one-minute load of 12, and no measured transition started above it.

## Every Other Wrong-Way Result

`compare` listed 59 wrong-way result(s) outside the deciding metrics; each is accounted
for below or the verdict it touches is not accepted.
Exit code 1, 0 gap(s).

| Metric | Transitions, control → candidate | compare outcome | Accounted for |
| --- | --- | --- | --- |
| requests_kpress | `landing.cold_markdown` 18 → 20; `landing.reload` 18 → 20; `reveal.deep_landing` 2.5 (2–3) → 7 | result | The font wait loads every declared face at idle once a staged view finds the page’s faces not all loaded (round 2’s review C3), so a page fetches, once, the reading faces no document has used yet: from the network on the two landings, and from the HTTP cache on reload. They are requested at idle after the stage is shown; neither landing’s painted-ready or blank-frame guard moved the wrong way. |
| dom_nodes_end | `landing.cold_markdown` 2061 → 2065; `landing.reload` 2061 → 2065; `files.cold.markdown_large` 8402 → 8406; `files.cold.markdown_mid` 6284 → 6288; `files.cold.source_large` 18637 → 18643; `files.cold.source_small` 5984 → 5990; `files.cold.json` 10006 → 10010; `files.cold.diff` 6384 → 6390; `files.cold.image` 5718 → 5724; `files.cold.binary` 5728 → 5734; `files.revisit.source_large` 18660 → 18666; `files.revisit.json` 10025 → 10029; `files.revisit.markdown_small` 6184 → 6188; `files.revisit.markdown_large` 8426 → 8430; `files.history_back` 6184 → 6188; `files.history_forward` 8426 → 8430; `files.hover_click.markdown` 6822 → 6826; `keyboard.down_cold.1` 1672 → 1676; `keyboard.down_cold.2` 1718 → 1722; `keyboard.down_cold.3` 1601 → 1607; `keyboard.up_revisit.1` 1719 → 1723; `keyboard.up_revisit.2` 1673 → 1677; `pulls.first_show` 1577 → 1581; `pulls.list_to_pr.cold` 4324 → 4335; `pulls.tab.changes_first` 6760 → 6770; `pulls.tab.checks_first` 4148 → 4159; `pulls.tab.conversation_revisit` 4324 → 4335; `pulls.tab.changes_revisit` 6595 → 6605; `pulls.tab.conversation_revisit_2` 4324 → 4335; `pulls.pr_to_pr.cold` 4897 → 4906; `pulls.tab.changes_first_2` 6685 → 6688; `pulls.history_back` 5036 → 5040; `pulls.tab.changes_revisit_2` 6685 → 6688; `tree.expand.docs` 1942 → 1946; `tree.expand.src` 2091 → 2095; `tree.collapse.src` 2096 → 2100; `tree.reexpand.src` 2096 → 2100; `tree.expand_nested.src_metabrowser` 2889 → 2893; `palette.open` 2076 → 2080; `skim.held_arrow_down` 2062 → 2065; `reveal.deep_landing` 3215 → 3221 | result | The reserved slots are nodes: the navigation’s per-tab toolbars, the view tab bar in every file, the print and badge slots, and the pull request header’s strut, label row, and status end. Drawn with the rest at first paint; region movement on these transitions is 0. |
| dom_nodes_end | `palette.query` 3278 → 3458 | result | Quick Search now keeps the whole file cap and draws up to 20 pull request rows after it (round 1’s review A4), so a query that matches both mounts more rows; list_row_replacements on this transition is 0, its deciding metric. |
| kpress_static_network | `landing.cold_markdown` 16 → 18; `reveal.deep_landing` 2.5 (2–3) → 7 | result | The same idle load of the declared faces as requests_kpress, counted by cache disposition. |
| preview_top_replaced | `files.cold.source_small` 3 → 4; `files.cold.json` 3 → 4; `files.cold.image` 3 → 4; `files.cold.binary` 3 → 4; `files.revisit.source_large` 3 → 4; `files.revisit.json` 3 → 4; `keyboard.up_revisit.1` 3 → 4 | result | A file with one view now draws the view tab bar too, one more top-level node in the preview; it arrives in the same commit as the rest of the view, and region movement here is 0. |
| settled_ms | `main.files_to_commits.again` 10.85 (9.7–17.9) → 13.85 (10–17.5) | explain | A settle time of a few milliseconds with overlapping ranges and some pairs beyond the tolerance; it is not a declared guard, and the instrument’s A/A baseline (exp-058) lists settle times under 25 ms among the differences one build shows against itself. |
| data_network | `commits.cold.1` 2 → 3.5 (3–4); `palette.open` 1 → 2 | result | Background requests of the pull request catalog’s warming (a further `/api/plugin/github/pulls` page and `POST pull-cores-prepare`) that finished inside the candidate’s window and were still pending at the end of the control’s; the transition’s own data requests are the same in both builds (the commit and its comparison on commits.cold.1, none on palette.open). |
| frames_to_ready | `tree.expand.docs` 3 (3–4) → 4 (3–4) | explain | Identical ranges in both builds, with some pairs a frame apart; the interim series of 078c4c69 listed the same transition the same way. |
| ready_after_last_input_ms | `skim.held_arrow_down` 47.85 (39.6–49.4) → 56.55 (46.4–71.3) | explain | A declared guard of H91 (c), and so not explained away: H91 (c) is not accepted (Verdicts). |

## Limits

- Revision 3 rows of this lane exist as a diagnostic, at `078c4c69` before review round
  1, and so does an interim revision 4 series of that commit; neither decides anything
  here. Between them, on the same build, the candidate’s region movement was identical on
  all 77 transitions (0 everywhere) and its blank frames differed on 6 of 77 transitions
  by at most a frame in the median (`files.cold.image` 1 to 2, `landing.cold_markdown`
  13.5 to 13; the other four within their ranges): revision 4’s reader moved no region
  result.
- Revision 3 read a dedicated worker’s 304 as network (review B2 of the instrument,
  #373); revision 4, which recorded these rows, reads it as revalidated.
  Either way it touches only the cache disposition fields (`requests.byFamily`,
  `plugin_static_network`, `plugin_static_revalidated`), which no criterion of H86 or
  H91 reads.
- The harness’s ports are fixed at 8890 to 8899 in revision 4, with no option to move
  them, so the series ran there and not on 8900 to 8909; the series lock kept every
  other lane’s timed run off the machine meanwhile.
- One machine, one Chrome, headless; WebKit, which the native shell uses, is not
  measured.
- The measured candidate is `28e12fa2`. Everything the branch took after it is
  post-round and unmeasured here: the merges of `main` (`8d382913`, with #373’s
  revision-4 instrument and #364 among others; `ed0c42a8`, #383’s keyboard stack, which
  resolved conflicts in `app.js`, `pull-page.js`, fixtures, and docs, so every file’s
  view tab bar is drawn with tablist roles and the pull request page’s tabs are live
  before its record arrives; `55bebbef`, #361 and #388; `55841fa9`, #390’s merge arrows;
  `e8c67338`, #391; `3d487119`, #394), review D’s fixes (`e9bea7c2`, tests and docs),
  and review E’s fixes for late stack badges and chips, which were in progress in
  another worktree when this was written.

## Reproducing

```shell
node explorations/performance-loop/transitions.mjs run --exp exp-059 \
  --corpus /path/to/standalone-clone --runs 4 \
  --journeys landing,files,keyboard,maintabs,commits,pulls,tree,palette,skim,reveal \
  --out .bench/transitions/exp-059/runs.jsonl \
  --condition control=/path/to/control/.venv/bin/metab \
  --condition candidate=/path/to/this-branch/.venv/bin/metab
node explorations/performance-loop/transitions.mjs samples \
  .bench/transitions/exp-059/runs.jsonl \
  --out explorations/performance-loop/experiments/exp-059-transition-samples.jsonl
node explorations/performance-loop/transitions.mjs compare \
  explorations/performance-loop/experiments/exp-059-transition-samples.jsonl \
  --control control --candidate candidate --format json --expect ID:region_movement_px:lower ...
```

The run is `transitions.mjs` at harness `5031dc16` (revision 4, frozen); the samples,
compare, and the tables here were produced from the committed samples.
`--expect` names each deciding metric in the Protocol below.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->

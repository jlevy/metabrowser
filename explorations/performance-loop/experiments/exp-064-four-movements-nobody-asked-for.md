---
title: Four Movements Nobody Asked For
softschema:
  contract: metabrowser.loadtime:Experiment/v1
  schema: experiment.schema.yaml
  envelope: experiment
  status: enforced
experiment:
  id: exp-064
  title: Four Movements Nobody Asked For
  date: "2026-11-13"
  hypotheses:
    - H91
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
    - metric: shift_sum_no_input.landing.cold_markdown
      control_median: 0.0033
      candidate_median: 0
      control_range: [0.0033, 0.0033]
      candidate_range: [0, 0]
      overlapping: false
    - metric: shift_sum_no_input.reveal.deep_landing
      control_median: 0.056999999999999995
      candidate_median: 0
      control_range: [0.0531, 0.0608]
      candidate_range: [0, 0]
      overlapping: false
    - metric: file_envelope_requests.skim.held_arrow_down
      control_median: 6
      candidate_median: 2
      control_range: [6, 6]
      candidate_range: [2, 2]
      overlapping: false
    - metric: requests_data.skim.held_arrow_down
      control_median: 6
      candidate_median: 2
      control_range: [6, 6]
      candidate_range: [2, 2]
      overlapping: false
    - metric: list_row_replacements.palette.query
      control_median: 11
      candidate_median: 0
      control_range: [11, 11]
      candidate_range: [0, 0]
      overlapping: false
    - metric: list_rows_replaced_below_selection.palette.query
      control_median: 11
      candidate_median: 0
      control_range: [11, 11]
      candidate_range: [0, 0]
      overlapping: false
  complexity:
    lines_changed: 315
    new_dependencies: []
    new_failure_modes:
      - "A landing outside the inline's bounds (a folder of over 200 entries, over 300 rows, over 8 folders, or discovery still running) reveals its path after the first paint and still moves the tree (bead mb-o1ba)."
      - "The font wait holds a staged view up to 100 ms for a face that stalls."
      - "The first staged view loads every declared face at idle, so a page fetches, once, faces no document has used yet."
      - "A held key whose repeat is slower than 120 ms opens rows as single presses do."
    notes: "315 source lines changed in the three H91 commits (d797b7b4, 936fbee7, 078c4c69), plus a share of the 699 lines of review fixes that H86 and H91 have together. One judgment: worth it for (a), (b), and (d), whose costs are bounded and stated beside their constants (a 100 ms cap, a 300-row inline, 20 pull request rows), and for (c) still to be settled, since what it saves (four of six reads on a skim) is clear and what it may cost is a guard this round could not tell from noise."
  verdict:
    decision: unresolved
    primary_metric: shift_sum_no_input
    reason: "(a) landing.cold_markdown's shift with no input went 0.0033 to 0, (b) reveal.deep_landing's 0.057 (0.0531–0.0608) to 0, and (d) palette.query's row replacements 11 to 0, each with ranges apart and no guard wrong-way: accepted. (c) skim.held_arrow_down's file envelopes went 6 to 2 as predicted, but its declared guard ready_after_last_input_ms was wrong-way under the pair rule, so (c) is not accepted."
    commit: 28e12fa2
---
**Status:** Unresolved as a whole: (a) fonts, (b) the deep landing, and (d) the
palette’s order are accepted; (c) the held key is unresolved on a guard.

One interleaved series, four back-to-back pairs on scenario revision 4, measured this
branch after review rounds 1 and 2 against origin/main.
H91 names four late movements that no input caused and says each can go: (a) the first
document’s body moving when PT Serif arrives, (b) a deep landing’s tree moving while its
folders open after first paint, (c) a held arrow key reading and rendering every file it
passes, and (d) Quick Search’s late pull request results replacing the file rows under
the selection.

## What Changed

- (a) Fonts, `d797b7b4` and `475e2327`: the staged view is shown once the faces its text
  is set in have landed, at most 100 ms later (`view-composition.js#settleFaces`). It
  asks for those faces by name with `document.fonts.load`, read from the staged prose’s
  computed font once per view; before review A2 it read `document.fonts.status`, which
  still read `loaded` when the renderer had not yielded a frame.
- (b) Deep landing, `936fbee7`, `078c4c69`, and `475e2327`: the shell inlines the
  landing path’s folders, expanded, each with its whole listing, within a measured
  budget of 300 rows, and names the path’s row, so the first tree paint shows the row
  selected; a path it cannot carry is revealed by the page as before, with its folders
  travelling.
- (c) Held key, `d797b7b4` and `475e2327`: a held arrow key moves the selection and the
  address on every repeat and opens only the row it stops on, on release or 120 ms after
  the last repeat; a single press opens at once, and a repeat slower than the settle
  opens each row as it reaches it.
- (d) Palette order, `d797b7b4` and `475e2327`: file results lead with the whole cap and
  pull requests follow as their own group of up to 20 rows, so their later answer is
  appended below the painted rows.

## Protocol

Declared before the measured series (first for revision 3 and restated unchanged since):

- (a) `landing.cold_markdown`’s `shift_sum_no_input`, lower (0.0033 to 0). Guards:
  `painted_ready_ms`, `styled_markdown_ms`, and `blank_frames` on that transition.
- (b) `reveal.deep_landing`’s `shift_sum_no_input`, lower (0.053 to 0). Guards:
  `painted_ready_ms` and `blank_frames` there.
- (c) `skim.held_arrow_down`’s `file_envelope_requests`, lower.
  The skim sends one plain key press and five repeats, and a plain press opens at once
  by design, so the predicted end value is 2 (the first row and the row the walk stops
  on). `requests_data` is shown beside it.
  Guards: `painted_ready_ms` and `ready_after_last_input_ms` on the skim, and
  `painted_ready_ms` on `keyboard.down_cold.{1,2,3}` (single presses).
- (d) `palette.query`’s `list_row_replacements`, lower (11 to 0), with
  `list_rows_replaced_below_selection` beside it.
  Guard: `painted_ready_ms` on `palette.query`.
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

- **(a) Fonts: accepted.** `landing.cold_markdown`’s layout shift with no input went
  0.0033 to 0, ranges apart.
  Its guards held: painted ready went 271.7 (264.2–285.7) to 288.35 (281.1–302.4) ms,
  pairs 1.06x (1.00–1.13), which compare calls no detected difference; that rise, about
  a frame, is the wait for the faces on the first document.
  Styled Markdown is the same figure, and blank frames did not move the wrong way.
- **(b) Deep landing: accepted.** `reveal.deep_landing`’s shift with no input went 0.057
  (0.0531–0.0608) to 0, ranges apart; painted ready went 193.7 (184.1–215.2) to 190
  (185.8–194.7) ms, no detected difference.
- **(c) Held key: unresolved.** The deciding metric moved as predicted:
  `skim.held_arrow_down`’s file envelopes went 6 to 2 in every run, ranges apart.
  But its declared guard `ready_after_last_input_ms` went 47.85 (39.6–49.4) to 56.55
  (46.4–71.3) ms, pairs 1.16x (0.98–1.80); compare’s verdict is “ranges overlap, but 2
  of 4 pairs are higher beyond the 1.3x tolerance: explain before accepting”, and it
  lists the guard as wrong-way.
  The rule declared before the series lets no wrong-way guard be explained away, so (c)
  is not accepted, and it is not re-scored on another metric.
  The skim’s painted ready went 380.2 (372.7–385.8) to 390.1 (374.7–407.8) ms, no
  detected difference, and the single presses’ guards held.
  The interim series of 078c4c69, a diagnostic, found this guard beyond the tolerance
  the other way, lower in 2 of its 6 pairs; a round with more pairs would settle it.
- **(d) Palette order: accepted.** `palette.query`’s row replacements went 11 to 0, and
  the replacements below the selection 11 to 0, ranges apart; painted ready went 190.25
  (188.3–191.9) to 190.95 (188.5–192.7) ms, no detected difference.

## Complexity

315 source lines changed in the three H91 commits (d797b7b4, 936fbee7, 078c4c69), plus a
share of the 699 lines of review fixes that H86 and H91 have together.
One judgment: worth it for (a), (b), and (d), whose costs are bounded and stated beside
their constants (a 100 ms cap, a 300-row inline, 20 pull request rows), and for (c)
still to be settled, since what it saves (four of six reads on a skim) is clear and what
it may cost is a guard this round could not tell from noise.

## Results

The tables are `compare`’s, lifted by script from its JSON: each median with its range,
and the median of the back-to-back pair ratios.

### H91 (a)

| Transition | Metric | Control | Candidate | Pair ratio | compare verdict |
| --- | --- | ---: | ---: | ---: | --- |
| `landing.cold_markdown` | shift_sum_no_input | 0.0033 | 0 | — | lower, ranges apart (result) |

Guards:

| Transition | Metric | Control | Candidate | Pair ratio | compare verdict |
| --- | --- | ---: | ---: | ---: | --- |
| `landing.cold_markdown` | painted_ready_ms | 271.7 (264.2–285.7) | 288.35 (281.1–302.4) | 1.06x (1.00–1.13) | no detected difference |
| `landing.cold_markdown` | styled_markdown_ms | 271.7 (264.2–285.7) | 288.35 (281.1–302.4) | 1.06x (1.00–1.13) | no detected difference |
| `landing.cold_markdown` | blank_frames | 11 (11–12) | 13 (13–14) | 1.18x (1.08–1.27) | higher, ranges apart but every pair within the 1.3x tolerance (not a result) |

### H91 (b)

| Transition | Metric | Control | Candidate | Pair ratio | compare verdict |
| --- | --- | ---: | ---: | ---: | --- |
| `reveal.deep_landing` | shift_sum_no_input | 0.057 (0.0531–0.0608) | 0 | — | lower, ranges apart (result) |

Guards:

| Transition | Metric | Control | Candidate | Pair ratio | compare verdict |
| --- | --- | ---: | ---: | ---: | --- |
| `reveal.deep_landing` | painted_ready_ms | 193.7 (184.1–215.2) | 190 (185.8–194.7) | 0.97x (0.89–1.04) | no detected difference |
| `reveal.deep_landing` | blank_frames | 8 (7–8) | 7 | 0.88x (0.88–1.00) | no detected difference |

### H91 (c)

| Transition | Metric | Control | Candidate | Pair ratio | compare verdict |
| --- | --- | ---: | ---: | ---: | --- |
| `skim.held_arrow_down` | file_envelope_requests | 6 | 2 | — | lower, ranges apart (result) |
| `skim.held_arrow_down` | requests_data | 6 | 2 | — | lower, ranges apart (result) |

Guards:

| Transition | Metric | Control | Candidate | Pair ratio | compare verdict |
| --- | --- | ---: | ---: | ---: | --- |
| `skim.held_arrow_down` | painted_ready_ms | 380.2 (372.7–385.8) | 390.1 (374.7–407.8) | 1.02x (0.98–1.09) | no detected difference |
| `skim.held_arrow_down` | ready_after_last_input_ms | 47.85 (39.6–49.4) | 56.55 (46.4–71.3) | 1.16x (0.98–1.80) | ranges overlap, but 2 of 4 pairs are higher beyond the 1.3x tolerance: explain before accepting |
| `keyboard.down_cold.1` | painted_ready_ms | 54.65 (53.1–57.7) | 53.05 (42.8–55.2) | 0.97x (0.74–1.03) | ranges overlap; one pair of 4 is lower beyond the 1.3x tolerance (2026-11-13T09-51-52-203Z#1): rerun that pair back to back before a release (listed, not a wrong-way result) |
| `keyboard.down_cold.2` | painted_ready_ms | 55.1 (43.1–57.4) | 43.8 (41.6–45.8) | 0.80x (0.75–1.01) | ranges overlap; one pair of 4 is lower beyond the 1.3x tolerance (2026-11-13T09-51-52-203Z#3): rerun that pair back to back before a release (listed, not a wrong-way result) |
| `keyboard.down_cold.3` | painted_ready_ms | 41.85 (40.5–53.9) | 43.4 (41.4–53.5) | 1.01x (0.99–1.07) | no detected difference |

### H91 (d)

| Transition | Metric | Control | Candidate | Pair ratio | compare verdict |
| --- | --- | ---: | ---: | ---: | --- |
| `palette.query` | list_row_replacements | 11 | 0 | — | lower, ranges apart (result) |
| `palette.query` | list_rows_replaced_below_selection | 11 | 0 | — | lower, ranges apart (result) |

Guards:

| Transition | Metric | Control | Candidate | Pair ratio | compare verdict |
| --- | --- | ---: | ---: | ---: | --- |
| `palette.query` | painted_ready_ms | 190.25 (188.3–191.9) | 190.95 (188.5–192.7) | 1.00x (0.99–1.02) | no detected difference |

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
  --control control --candidate candidate --format json --expect ID:METRIC:lower ...
```

The run is `transitions.mjs` at harness `5031dc16` (revision 4, frozen); the samples,
compare, and the tables here were produced from the committed samples.
`--expect` names each deciding metric in the Protocol below.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->

---
title: "The Campaign's Closing Round: Every Accepted Change at Final Main"
softschema:
  contract: metabrowser.loadtime:Experiment/v1
  schema: experiment.schema.yaml
  envelope: experiment
  status: enforced
experiment:
  id: exp-079
  title: "The Campaign's Closing Round: Every Accepted Change at Final Main"
  date: "2026-11-14"
  hypotheses:
    - H86
    - H87
    - H88
    - H91
    - H92
    - H106
  subject:
    corpus: "Standalone clone of this repository (corpus v2), as every judged run saw it: HEAD 7a02fed4 checked out and clean; trunk 083e78e4; server git log head 7a02fed4; refs digest 387f68dc4e8eb8e0, the state exp-058 through exp-085 and exp-087 recorded."
    corpus_files: 1286
    host_cpu: 10 CPUs
    host_system: Darwin 25.5.0 arm64, Node 24.19.0, Low Power Mode on, AC power
    browser: Headless Chrome 152.0.7977.83 over the DevTools Protocol, a fresh profile per journey, trusted pointer and key input.
    viewport: 1440x900
    cold: false
  method:
    runs_per_condition: 6
    interleaved: true
    control: metab 0.12.1.dev165+9903292 (+165 commits, 099032928), the campaign control and the build exp-058 measured, an editable checkout at 09903292, clean at the start and end of every run, a fresh server process per run.
    candidate: metab 0.12.1.dev991+c74d0ef3 (+991 commits, c74d0ef3d), main at #368's merge, an editable checkout at c74d0ef3, clean at the start and end of every run, a fresh server process per run. It carries every campaign lane (#370, #369, #372, #368) and 52 other merges since 09903292, among them the instrument changes.
    record: exp-079-transition-samples.jsonl, exp-079-power.jsonl, exp-079-power-samples.log, exp-079-derived-samples.jsonl, exp-079-skim-evidence.jsonl, exp-079-analysis.json, exp-079-exclude.mjs, exp-079-derive.mjs, exp-079-analyze.mjs
    protocol:
      path: exp-079-protocol.txt
      sha256: 8332a090ec67ea61b76a8c3f30339f8f3650ecc496c3154f1304d4076a204f71
  results:
    - metric: region_movement_px.files.cold.json
      control_median: 30
      candidate_median: 0
      control_range: [30, 30]
      candidate_range: [0, 0]
      overlapping: false
    - metric: region_movement_px.main.commits_to_files.first
      control_median: 37
      candidate_median: 0
      control_range: [37, 37]
      candidate_range: [0, 0]
      overlapping: false
    - metric: region_movement_px.pulls.tab.changes_first
      control_median: 8
      candidate_median: 0
      control_range: [8, 8]
      candidate_range: [0, 0]
      overlapping: false
    - metric: painted_ready_ms.pulls.tab.changes_first
      control_median: 42.8
      candidate_median: 102.15
      control_range: [40.3, 57.2]
      candidate_range: [92.4, 109.5]
      overlapping: false
    - metric: shift_sum_no_input.landing.cold_markdown
      control_median: 0.0033
      candidate_median: 0
      control_range: [0.0033, 0.0033]
      candidate_range: [0, 0]
      overlapping: false
    - metric: shift_sum_no_input.reveal.deep_landing
      control_median: 0.057
      candidate_median: 0
      control_range: [0.0531, 0.0608]
      candidate_range: [0, 0]
      overlapping: false
    - metric: list_row_replacements.palette.query
      control_median: 11
      candidate_median: 0
      control_range: [11, 11]
      candidate_range: [0, 0]
      overlapping: false
    - metric: file_envelope_requests.skim.held_arrow_down
      control_median: 6
      candidate_median: 2
      control_range: [6, 6]
      candidate_range: [2, 2]
      overlapping: false
    - metric: ready_after_last_input_ms.skim.held_arrow_down
      control_median: 46.15
      candidate_median: 65
      control_range: [42.9, 50.3]
      candidate_range: [56.8, 72.5]
      overlapping: false
    - metric: duplicate reads per run, the five pull request clicks
      control_median: 8
      candidate_median: 0
      control_range: [8, 8]
      candidate_range: [0, 0]
      overlapping: false
    - metric: body shift after ready per run, the four Changes paints
      control_median: 1.4889
      candidate_median: 0
      control_range: [0.9999, 1.6425]
      candidate_range: [0, 0]
      overlapping: false
    - metric: Conversation transitions per run whose description showed before its final form
      control_median: 6
      candidate_median: 1
      control_range: [5, 6]
      candidate_range: [1, 1]
      overlapping: false
    - metric: painted_ready_ms.main_subject.commits_to_pulls
      control_median: 79.4
      candidate_median: 112.1
      control_range: [63.6, 95.6]
      candidate_range: [80.5, 112.4]
      overlapping: true
    - metric: revalidated_total.landing.reload
      control_median: 43
      candidate_median: 1
      control_range: [43, 43]
      candidate_range: [1, 1]
      overlapping: false
    - metric: painted_ready_ms.landing.reload
      control_median: 166.45
      candidate_median: 106.7
      control_range: [156.9, 175.2]
      candidate_range: [105.9, 124.9]
      overlapping: false
    - metric: requests_data.commits.revisit.1
      control_median: 1
      candidate_median: 0
      control_range: [1, 1]
      candidate_range: [0, 0]
      overlapping: false
    - metric: painted_ready_ms.commits.revisit.1
      control_median: 122.5
      candidate_median: 30.4
      control_range: [97.4, 148.6]
      candidate_range: [29.3, 32.3]
      overlapping: false
    - metric: painted_ready_ms.commits.revisit.2
      control_median: 164.4
      candidate_median: 31.05
      control_range: [147.1, 181.6]
      candidate_range: [29.9, 31.7]
      overlapping: false
    - metric: painted_ready_ms.commits.cold.1
      control_median: 122.85
      candidate_median: 163.45
      control_range: [114.2, 180.3]
      candidate_range: [112.6, 164.8]
      overlapping: true
  complexity:
    lines_changed: 6066
    new_dependencies: []
    notes: "The campaign's four product lanes as shipped, each counted under src/ at its merge into main: #370 (H86, H91) 20 files, 1,285 lines added and 218 removed; #369 (H92, H106) 10 files, 1,718 and 291; #372 (H87; H89 reverted) 17 files, 1,083 and 218; #368 (H88; H90 removed) 11 files, 1,137 and 116. Clause 4 for each hypothesis that meets clauses 1 to 3 is in Complexity Judgments, below, resting on Facts for the Complexity Judgments."
  verdict:
    decision: unresolved
    primary_metric: "Per hypothesis, the deciding metrics of the record that accepted it: region movement (H86), revalidated requests per reload (H87), commit revisit requests and painted ready (H88 (a)), no-input shift, file envelopes, and row replacements (H91), duplicate reads and the Changes body shift (H92), and plain-first Conversation transitions (H106)"
    reason: "Judged mechanically at final main against the campaign control, six judged pairs, none excluded. Accepted, clauses 1 to 3 met and the coordinator's complexity judgment worth it: H86 (a); H91 (a), (b) and (d); H92 (a) and (c), each with exp-065's account of the first-paint hold, H92 (c) as the campaign's costliest accepted trade (Changes ready 79 to 102 ms against 43 to 45 ms, for a body shift of 1.49 per run removed). Unresolved: H86 (b), 13 wrong-way results on its guards over nine pull request transitions, the first-paint holds, which exp-059 does not account for; H87, 17 unaccounted wrong-way results on landing and files transitions; H88 (a), 12 on its commits and main_subject guard; H106, main_subject.commits_to_pulls painted ready, which exp-080 did not show higher; the analysis as amendment 3 hashed it accepts H106, on a broader reading the registration also states, and the coordinator ruled for the narrower one. Rejected: H91 (c), its guard ready_after_last_input_ms 46.2 to 65.0 ms, ranges apart with 3 of 6 pairs beyond 1.3x, which exp-085's rule rejects. Not measured: H88 (b), H92 (b), and WebKit. Not on main: H89 and H90."
    commit: c74d0ef3
---
**Status:** The campaign’s closing round (epic `mb-mpo0`). It compares final main, at
#368’s merge (`c74d0ef3`), with the campaign control (`09903292`). Each landed
hypothesis is judged mechanically on the criteria of the record that accepted it.
Six pairs were judged, none was excluded, and all 12 runs were valid.

Clauses 1 to 3 of the accept rule are judged by
[exp-079-analyze.mjs](exp-079-analyze.mjs).
Clause 4, the complexity judgment, is the coordinator’s, in **Complexity Judgments**,
below.

- **Accepted at final main:** H86 (a); H91 (a), (b) and (d); H92 (a) and (c). H92’s two
  parts rest on
  [exp-065](exp-065-one-read-per-click-trees-that-open-once-and-a-held-changes-paint.md)’s
  account of the first-paint hold.
- **Unresolved:** H86 (b), H87, H88 (a), and H106.
- **Rejected:** H91 (c), on its guard, by
  [exp-085](exp-085-held-key-guard-confirmed.md)’s declared rule.
- **Not measured:** H88 (b), H92 (b), and WebKit.
- **Not on main:** H89 and H90.

Every result belongs to final main as a whole, which carries the four campaign lanes and
52 other merges since `09903292`, not to one change alone.

The generated ledger shows exp-079 as `unresolved`, because the schema carries one
decision per record.
**Final Performance Update**, below, gives every hypothesis’s outcome.

## Why This Round

exp-058 measured the product at `09903292` on corpus v2, and every campaign round
measured its own lane against a control.
The plan reserves exp-079 to re-measure every accepted item together against that
control
([load-time plan](../../../docs/project/specs/active/plan-2026-08-21-load-time-performance.md#apparent-speed-and-layout-stability),
[UI plan](../../../docs/project/specs/active/plan-2026-11-11-ui-apparent-performance.md#testing-strategy)).
The round does that in Chrome, on scenario revision 5, with every journey.

## Protocol

The protocol is [exp-079-protocol.txt](exp-079-protocol.txt), sha256 `8332a090…`. It is
the registration and three amendments:

- **Registration** (2026-11-14): builds, the series, pacing, the lock, the load and
  power rules, six judged pairs, the Commits landings, and the per-hypothesis criteria.
- **Amendment 1** (12:05:00Z): the candidate, its version line and campaign pull
  requests; which hypotheses are on main, each checked by its merge and code; the corpus
  and the per-pair refs check; the harness, lock path and power mode; the operational
  stops.
- **Amendment 2** (committed 12:13:48Z, before any measurement): the corpus back on refs
  digest `387f68dc4e8eb8e0` after the coordinator removed `refs/remotes/origin/HEAD`;
  where H89’s and H90’s code lives; `report.md` regenerated and the registry updated by
  this pull request; WebKit and H88 (b) not measured; the exclusion script
  ([exp-079-exclude.mjs](exp-079-exclude.mjs)) by sha256.
- **Amendment 3** (written 12:25:00Z, committed 12:33:41Z): the analysis, by sha256, and
  its rules: what passes, what counts as wrong-way, which accounts are allowed, what
  each third clause sees, and the verdict labels.
  It was committed 20 s after the first pair finished (12:33:21Z in
  [exp-079-power.jsonl](exp-079-power.jsonl)) and before the second began.
  The operator states that no analysis had run on an exp-079 result and no judged result
  had been read, and that it had seen three log lines of `views.folder.*`, which nothing
  judges, as the amendment says.
  The committed files cannot show this.

**The accept rule** is the runbook’s. A deciding count or value passes when its median
moved the predicted way with ranges apart; a time or frame count, with ranges apart and
two or more pairs beyond 1.3x. A wrong-way result in a hypothesis’s table is a result,
or two or more pairs beyond 1.3x under overlapping ranges.
It blocks the verdict unless a rule its record declared, or that record’s own account of
the same metric on the same transition, accounts for it.

## Deviation from the Protocol

**The analysis script was corrected after the results were read.** Amendment 3 names
`exp-079-analyze.mjs` at sha256 `b09ab7c8…`, and its rule for a carried account is “the
record accepted the same metric on the same transitions moving the same way”.

That version carried exp-080’s account to every Conversation transition and cold click.
That is broader than the rule: in exp-080, `main_subject.commits_to_pulls` painted ready
went 64.9 to 64.7 ms, not higher.

**The registration is not consistent on this point.** The same amendment also says
exp-080 accounted for “H106’s description and painted-ready guards”, and defines H106’s
painted-ready guard as every Conversation transition.
That sentence backs the broad reading the hashed script took.

The committed version, sha256 `787bc624…`, names each record’s cells one by one, as its
own tables give them.
The correction only narrows what is accounted for: every cell set it names is a subset
of the hashed version’s. It changes one verdict: H106, accepted by the hashed version,
is unresolved here. No other verdict changes; the wording of the accounts on H92’s
entries also changes.
Both versions are in this branch’s history.

One comment in the committed version overstates its list.
It says exp-065’s cells come from that record’s guard table and its “What moved the
wrong way” section, but the list omits most of that section’s cells.
The list is narrower than the comment, which is again the conservative side.

**The coordinator’s ruling: the correction stands.** Where the registration gives two
readings, this round takes the one that accounts for less.
The general rule, the same metric moving the same way on the same transition, is the
condition for an account.
An account cannot cover a transition its record saw unchanged.
The correction cannot turn a failure into a pass, and it costs the campaign a verdict.
Under the hashed script, at `655a7bec`, H106 is accepted; no other verdict differs.

## Identities, Load, and Power

| Item | Value |
| --- | --- |
| Control | `metab 0.12.1.dev165+9903292 (+165 commits, 099032928)`, clean at every run’s start and end |
| Candidate | `metab 0.12.1.dev991+c74d0ef3 (+991 commits, c74d0ef3d)`, clean at every run’s start and end; its environment made like the control’s (`sync --frozen --all-groups`, CPython 3.14.7, the same third-party distributions) |
| Harness | `3a1ff25e`, scenario revision 5, clean, frozen for the round |
| Corpus | `7a02fed4` checked out, clean, 1,286 indexed files; trunk `083e78e4`; refs digest `387f68dc4e8eb8e0` before every pair and at every run’s start and end |
| Chrome | 152.0.7977.83, headless |
| Lock | taken 12:15:11Z at a one-minute load of 1.57, released 14:01:17Z, from the driver’s log (`attic/exp079/exp079-paced.log` in the round’s worktree), which is not committed because it holds a local path; the pairs’ own times, below, are in [exp-079-power.jsonl](exp-079-power.jsonl) |
| Pairs | six, 12:16:13Z to 14:01:16Z, the control first in odd attempts; all six judged, none excluded |
| Load | one-minute load 1.67 to 5.04 at run starts, at most 10.13 at a measured transition’s start |
| Power | Low Power Mode on and AC power before and after every pair ([exp-079-power.jsonl](exp-079-power.jsonl)) and in all 424 samples taken every 15 s ([exp-079-power-samples.log](exp-079-power-samples.log)); the judged mode is lowpowermode 1, AC Power |

Each run took 8.2 to 8.7 minutes.
At six runs a side, `compare` expects about 2.3 of its comparisons to come apart by
chance. The first run of each build saw the pull request catalog absent when the server
started. Each later run saw it at 409 (3 open, 406 closed), filled during the warm-up
pass.

## What Is Not Judged

**Commits landings.** Switching to Commits lands on the prompt in the control, which
predates `19a36c5b` (#395). In the candidate it lands on the newest commit, `7a02fed4`.
Six transitions record a different landing in every pair, and are reported and not
judged:

- `commits.first_show`
- `main.files_to_commits.first` and `main.files_to_commits.again`
- `main.pulls_to_commits`
- `main_subject.files_to_commits` and `main_subject.pulls_to_commits`

That removes four of H86 (a)'s 27 deciding transitions, and three of H88 (a)'s guard
transitions. `compare` ran with the Commits landings allowed to differ, and noted that
those switches measure a different subject on each side.

**Not measured by this series:**

- H92 (b), decided on the pilot tree probe;
- H88 (b), decided on `git-route-pairs.mjs`;
- the hold-span guard of exp-065 and exp-080, read by `probe-holds-corpus.mjs`;
- WebKit. The WKWebView probe needs a visible window and an unlocked screen with the user
  present. It is a follow-up and judges nothing here.

## Results

Every figure is from [exp-079-analysis.json](exp-079-analysis.json), which runs the
harness’s `compare` on the judged samples and reads the derived files:

- [exp-079-derived-samples.jsonl](exp-079-derived-samples.jsonl), from
  [derive-h92-h106.mjs](exp-065-instruments/derive-h92-h106.mjs);
- [exp-079-skim-evidence.jsonl](exp-079-skim-evidence.jsonl), from
  [exp-079-derive.mjs](exp-079-derive.mjs).

Times are milliseconds, median (range) over six runs a side.
Pairs beyond are against 1.3x.

### H86: Every Region’s Box at First Paint

**(a) Shell chrome.**

- **Deciding, met.** Every one of the 23 judged transitions moved shell chrome at the
  control and 0 px in every candidate run, ranges apart:
  - 30 px to 0 on the cold source, JSON and diff files, the JSON revisit,
    `keyboard.down_cold.3`, `keyboard.up_revisit.1` and the held skim;
  - 11 px to 0 on the cold image and binary, `keyboard.down_cold.1`,
    `keyboard.down_cold.2` and `keyboard.up_revisit.2`, and `tree.expand.docs`;
  - 37 px to 0 on every judged `main.*` and `main_subject.*` switch, and on
    `pulls.first_show`.
- **`landing.reload`.** Its no-input shift went 0.0002 to 0.
- **Guards held.** No wrong-way result on painted ready or blank frames.

**(b) The pull request header.**

- **Deciding, met.** The eight tab and history transitions went 8 px to 0, ranges apart.
  The four pull request switches stayed at 0 on both builds.
- **Guards not met.** Painted ready is later in final main on every Changes paint and
  every pull request click, and the header’s time on four of the clicks:

| Transition | Painted ready | compare |
| --- | --- | --- |
| `pulls.tab.changes_first` | 42.8 (40.3–57.2) → 102.2 (92.4–109.5) | ranges apart, 6 of 6 beyond |
| `pulls.tab.changes_revisit` | 45.1 (43.7–45.6) → 79.2 (74.1–86.0) | ranges apart, 6 of 6 beyond |
| `pulls.tab.changes_first_2` | 43.9 (42.2–58.0) → 95.1 (93.6–97.6) | ranges apart, 6 of 6 beyond |
| `pulls.tab.changes_revisit_2` | 42.5 (41.6–43.9) → 95.9 (93.9–96.7) | ranges apart, 6 of 6 beyond |
| `pulls.pr_changes_to_pr` | 62.2 (60.9–62.8) → 111.5 (94.5–112.6) | ranges apart, 6 of 6 beyond |
| `pulls.list_to_pr.cold` | 57.9 (56.9–75.8) → 90.5 (74.3–91.7) | ranges overlap, 4 of 6 beyond |
| `pulls.pr_to_pr.cold` | 45.5 (44.4–45.9) → 61.4 (59.0–62.7) | ranges apart, 6 of 6 beyond |
| `pulls.pr_to_pr.revisit` | 27.7 (25.0–41.8) → 44.2 (43.1–58.4) | ranges apart, 5 of 6 beyond |
| `pulls.pr_to_pr.hover_click` | 38.5 (30.2–48.1) → 96.4 (82.3–97.1) | ranges apart, 6 of 6 beyond |

`pr_header_ms` equals painted ready on the four clicks shown with it in
[exp-079-analysis.json](exp-079-analysis.json): 13 wrong-way results on nine
transitions. The nine painted-ready cells are ones exp-065 and exp-080 accounted for as
the first-paint hold, in which a pull request page waits out of sight until its body is
final.
The four header cells are in neither record’s tables; exp-065’s text describes the
header arriving later on the clicks.
exp-059 names no account for any of them.

### H87: Immutable Stamped Assets

- **Deciding, met.** Revalidated requests on `landing.reload`, over the five families,
  went 43 to 1 per run, ranges apart.
- **Guard held.** `landing.reload` painted ready went 166.5 (156.9–175.2) to 106.7
  (105.9–124.9), lower, ranges apart, 6 of 6 pairs beyond.
- **The declared check came out as stated.** `files.revisit.source_large`’s longest task
  went 119 (104–141) to 133 (114–139), ranges overlapping, one pair beyond, listed and
  not wrong-way.
- **The cold Markdown prediction came out as stated.** Painted ready on
  `landing.cold_markdown` went 273.4 to 290.2, no detected difference.
  Blank frames, blank time and placeholder frames are not wrong-way results.
- **exp-087’s later-frame test.** No view lands on a later frame more often:

| View | Candidate later | Control later | Fisher p |
| --- | --- | --- | --- |
| `files.cold.json` | 1 of 6 | 0 of 6 | 1.0 |
| `files.cold.image` | 1 of 6 | 4 of 6 | 0.2424 |
| `files.revisit.markdown_large` | 0 of 6 | 0 of 6 | 1.0 |

None of those views has a frame-level wrong-way result in this round.
The cold JSON and image views’ `preview_top_replaced` results are counted below.

**Third clause not met.** exp-083 covers every wrong-way result on `landing.*` and
`files.*`, and 17 are unaccounted for:

- **Static and KPress requests.** On `landing.cold_markdown` and `landing.reload`,
  `requests_static` went 41 to 44 and `requests_kpress` 18 to 19. On the cold landing,
  `static_network` went 41 to 44 and `kpress_static_network` 16 to 18.
- **The top of the preview, replaced once more.** `preview_top_replaced` went 3 to 4 on
  six `files.*` transitions.
- **Data requests.** `data_network` went 3.5 to 5 on `files.cold.diff`, 1 to 3 on
  `files.cold.binary`, and 1 to 3 on `files.revisit.markdown_small`.
- **Frames to ready.** On `files.cold.markdown_mid` and `files.cold.source_large`,
  frames to ready rose, ranges overlapping, with 2 and 3 of 6 pairs beyond.

This round has no evidence of its own that says which change in final main each belongs
to.
One has an earlier account: [exp-064](exp-064-four-movements-nobody-asked-for.md) saw
`requests_kpress` rise on both landings (18 to 20), and accounted for it as H91 (a)’s
font wait loading every declared face at idle.
The protocol limits H87’s accounts to exp-083’s, so that result stays unaccounted here.

### H88 (a): Commit Revisits

- **Deciding, met.** On both commit revisits, data requests went 1 to 0. Painted ready
  went 122.5 (97.4–148.6) to 30.4 (29.3–32.3) on `commits.revisit.1`, and 164.4
  (147.1–181.6) to 31.1 (29.9–31.7) on `commits.revisit.2`. Both are ranges apart, 6 of
  6 pairs beyond.
- **Guard not met.** With the three landing transitions not judged, 12 wrong-way results
  remain on `commits.*` and `main_subject.*commits*`:
  - **`main_subject.commits_to_pulls`, eight:** painted ready 79.4 (63.6–95.6) to 112.1
    (80.5–112.4), ranges overlapping, 3 of 6 pairs beyond, with ready, ready after the
    last input, and the header’s and the description’s times; data requests 12 to 13 and
    `data_network` 15 to 16; and 7,174 to 7,599 DOM nodes.
    It is a switch to a pull request page, but this round does not show why it is later:
    exp-080 measured it at 64.9 and 64.7 ms with the first-paint hold in place.
  - **`main_subject.commits_to_files`:** 6,045 to 6,129 DOM nodes.
  - **`commits.cold.1`:** painted ready 122.9 (114.2–180.3) to 163.5 (112.6–164.8), with
    ready and ready after the last input, ranges overlapping, 2 of 6 pairs beyond.
    That is the transition that failed exp-081.

### H91: Four Movements Nobody Asked For

- **(a) Fonts, met.** `landing.cold_markdown`’s no-input shift went 0.0033 to 0. Its
  guards (painted ready, styled Markdown, blank frames) have no wrong-way result.
  Blank frames went 11 (11–12) to 13 and blank time 183.4 (183.3–200.0) to 216.7
  (216.7–216.8) ms, ranges apart but every pair within 1.3x, as exp-064 also saw.
- **(b) Deep landing, met.** `reveal.deep_landing`’s shift went 0.057 (0.0531–0.0608) to
  0\. Its painted ready and blank frames have no wrong-way result.
- **(d) Palette order, met.** `palette.query`’s row replacements went 11 to 0, and those
  below the selection 11 to 0. Its painted ready has no wrong-way result.
- **(c) Held key: rejected by exp-085’s rule.**
  - The deciding metric moved as predicted: file envelopes went 6 to 2, ranges apart.
  - The guard, `ready_after_last_input_ms` on the skim, went 46.2 (42.9–50.3) to 65.0
    (56.8–72.5) ms: higher, ranges apart, 3 of 6 pairs beyond 1.3x.
  - exp-085 declared that case “a guard result; H91 (c) is rejected”.
    Its evidence E1 to E3 explains only overlapping ranges.
  - The evidence would hold if it applied.
    Every candidate run is under 120 ms (E1). No run has a blank or placeholder frame
    (E3).
  - In each pair beyond (1.43x, 1.69x, 1.62x), the candidate’s excess of 21.7, 29.6 and
    26.7 ms is matched within a frame by its last row’s select-to-ready span, 14.0, 22.1
    and 21.4 ms longer (E2). The time is the final row’s own render, slower in final
    main.
  - The skim’s painted ready went 380.2 to 411.0 ms, ranges apart, every pair within
    1.3x. The single presses’ painted ready has no wrong-way result.

### H92: One Read per Click, and a Held Changes Paint

- **(a), met, with exp-065’s account.**
  - Duplicate reads over the five pull request clicks went 8 (8–8) to 0 per run, ranges
    apart, and to 0 on each click.
  - Five guard cells rose: the description’s shown time on the cold, hover and
    from-Changes clicks, and its final time on the hover and from-Changes clicks.
  - exp-065 shows each of them higher, and accounted for each as the first-paint hold.
- **(c), met, with exp-065’s account.**
  - The body’s shift after ready over the four Changes paints went 1.4889
    (0.9999–1.6425) to 0 per run, ranges apart.
  - Its guard, painted ready on the four, is later: 42.5–45.1 to 79.2–102.2 ms, 6 of 6
    pairs beyond on each.
  - exp-065 recorded the same as the hold’s cost, bounded at 200 ms.

### H106: The Conversation Final at First Paint

- **Metric 1, met.** Conversation transitions whose description showed before its final
  form went 6 (5–6) to 1 per run, ranges apart.
  The remaining one is `pulls.list_to_pr.cold` in every candidate run, as in exp-080.
- **Metric 2, as predicted.** The body’s shift after ready stayed at 0 on both builds,
  and no pull request transition’s `preview_top_replaced` or no-input shift rose.
- **Guards: one unaccounted.** Ten of the eleven wrong-way guard cells are cells exp-080
  shows higher and accounted for as the first-paint hold.
  The eleventh is `main_subject.commits_to_pulls`’s painted ready: 79.4 (63.6–95.6) to
  112.1 (80.5–112.4), ranges overlapping, 3 of 6 pairs beyond.
  In exp-080 it went 64.9 to 64.7. H106 is unresolved.

## Verdicts

Clauses 1 to 3 are the analysis’s; clause 4 is the coordinator’s, in **Complexity
Judgments**, below.

- **H86 (a): accepted.** All 23 judged deciding transitions moved shell chrome 0 px,
  ranges apart; `landing.reload`’s shift went 0.0002 to 0. No guard moved the wrong way.
- **H86 (b): unresolved.** Its deciding metric is met, but its guards have 13
  unaccounted wrong-way results, the pull request page’s first-paint holds.
- **H87: unresolved.** Its deciding metric (43 to 1), its guard and its declared check
  are met. Its third clause has 17 unaccounted wrong-way results on `landing.*` and
  `files.*`.
- **H88 (a): unresolved.** Its four deciding metrics are met.
  Its guard has 12 unaccounted wrong-way results, on `main_subject.commits_to_pulls`,
  `main_subject.commits_to_files`, and `commits.cold.1`.
- **H88 (b): not measured.**
- **H91 (a), (b), (d): accepted.**
- **H91 (c): rejected** by exp-085’s guard rule.
  Its deciding metric is met.
- **H92 (a), (c): accepted,** each with exp-065’s account of the first-paint hold.
- **H92 (b): not measured.**
- **H106: unresolved,** on `main_subject.commits_to_pulls`’s painted ready.

## Final Performance Update

Every campaign hypothesis, with its deciding record, and its numbers at final main
against the campaign control in this round.

| Hypothesis | Its record | Final main against the control (exp-079) | Numbers, control → final main |
| --- | --- | --- | --- |
| H86 (a), shell chrome | accepted, [exp-059](exp-059-every-region-box-at-first-paint.md) | accepted | region movement 11–37 px → 0 on 23 transitions; reload no-input shift 0.0002 → 0; four Commits-switch transitions not judged |
| H86 (b), pull request header | accepted, exp-059 | unresolved | header movement 8 px → 0 on eight transitions; 13 wrong-way results on its guards over nine pull request transitions, painted ready and header time (`changes_first` 42.8 → 102.2 ms) |
| H87, immutable stamped assets | accepted, [exp-083](exp-083-immutable-stamped-assets-without-h89.md) and [exp-087](exp-087-frame-quantization-confirms-h87.md) | unresolved | revalidated requests per reload 43 → 1; reload painted ready 166.5 → 106.7 ms; 17 unaccounted wrong-way results on `landing.*` and `files.*` |
| H88 (a), comparison cache | accepted, [exp-086](exp-086-comparison-cache-route-memo-and-markdown-render-cache-confirmation.md) | unresolved | revisit data requests 1 → 0; revisit painted ready 122.5 → 30.4 and 164.4 → 31.1 ms; 12 unaccounted guard results |
| H88 (b), route memo | accepted, exp-086 | not measured | decided on the server half, `git-route-pairs.mjs`, which this series does not run |
| H89, parallel shell tools and KPress loading | rejected, [exp-062](exp-062-parallel-shell-tools-and-kpress-loading.md) | not on main | #372 reverted it; its code is at `14150b84` |
| H90, render cache and kept Worker | unresolved, exp-086 (after [exp-063](exp-063-markdown-render-cache-and-kept-worker.md) and [exp-082](exp-082-markdown-render-cache-and-kept-worker-confirmation.md)) | not on main | #368 took it out (`bd971661`); its code is at `6b876c54` |
| H91 (a), fonts | accepted, [exp-064](exp-064-four-movements-nobody-asked-for.md) | accepted | first-document no-input shift 0.0033 → 0 |
| H91 (b), deep landing | accepted, exp-064 | accepted | deep-landing no-input shift 0.057 → 0 |
| H91 (c), held key | accepted, [exp-085](exp-085-held-key-guard-confirmed.md) | rejected, by exp-085’s guard rule | file envelopes per skim 6 → 2; ready after the last input 46.2 → 65.0 ms, ranges apart, 3 of 6 pairs beyond |
| H91 (d), palette order | accepted, exp-064 | accepted | row replacements 11 → 0 |
| H92 (a), one read per click | accepted, [exp-065](exp-065-one-read-per-click-trees-that-open-once-and-a-held-changes-paint.md) | accepted, with exp-065’s account | duplicate reads per run 8 → 0 |
| H92 (b), trees that open once | accepted, exp-065 | not measured | decided on the pilot tree probe; the scenario’s warm server cannot produce a late file list |
| H92 (c), a held Changes paint | accepted, exp-065 | accepted, with exp-065’s account | Changes body shift after ready per run 1.4889 → 0; Changes painted ready 42.5–45.1 → 79.2–102.2 ms |
| H106, the Conversation final at first paint | accepted, [exp-080](exp-080-pull-request-conversation-final-at-first-paint.md) | unresolved; accepted by the analysis as hashed, on a broader reading of its accounts | plain-first Conversation transitions per run 6 → 1; `main_subject.commits_to_pulls` painted ready 79.4 → 112.1 ms |

WebKit is not measured; it is a follow-up.

**What final main costs.** No judged transition moves at final main, and the commit
revisits and the reload are ready in 0.19x to 0.67x of the control’s time.
Pull request pages pay for that stillness, by the first-paint holds of H92 (c) and H106
(**The Campaign Summary**, below):

- Changes is ready at 79 to 102 ms, against 43 to 45 ms.
- A pull request click is ready at 44 to 112 ms, against 28 to 62 ms.

The held-key skim’s last row is ready 19 ms later, which rejects H91 (c).

## Facts for the Complexity Judgments

For each hypothesis that meets clauses 1 to 3. The diff sizes are product code under
`src/`, from the records and from each lane’s merge into main.

- **H86 (a).**
  - **Size:** 653 lines in H86’s four commits, plus a share of the 699 lines of review
    fixes it shares with H91 (exp-059). #370 as merged is 20 files, 1,285 lines added
    and 218 removed, H86 and H91 together.
  - **Mechanism:** one toolbar slot at the top of the navigation on every main tab;
    stable scrollbar gutters on the tree and the preview; the shortcut-hints row, the
    view tab bar, and the print and run-badge slots kept; the Commits tab drawn by the
    server; the folder Overview holds the previous folder until its first rollup, at
    most 100 ms.
  - **Failure modes (exp-059):** a row reserved at one line cuts long text short, with
    the whole text in a tooltip; a toolbar wider than a narrowed pane scrolls along its
    row.
- **H91 (a), (b), (d).**
  - **Size:** 315 lines in H91’s three commits, plus that share of review fixes
    (exp-064).
  - **Mechanisms:** (a) a staged view waits for its faces, at most `FACE_WAIT_MS` = 100
    ms; (b) the server inlines a landing path’s folders, expanded, within
    `_INLINE_LANDING_ROWS` = 300 rows and `_INLINE_LANDING_DEPTH` = 8; (d) file results
    lead, with up to `PULL_RESULT_LIMIT` = 20 pull request rows as their own group
    below.
  - **Failure modes (exp-064):**
    - a landing outside the inline’s bounds still moves the tree;
    - the font wait holds a view up to 100 ms for a face that stalls;
    - the first staged view loads every declared face at idle.
- **H92 (a), (c).**
  - **Size:** 1,715 lines added and 291 removed in product code at the measured head,
    shared with H106 (exp-065). #369 as merged is 10 files, 1,718 and 291. H92’s own
    code is mostly in `pulls-panel.js`, `pull-files-tree.js`, `pull-files-view.js`, the
    diff plugin, and the Changes hold in `pull-page.js`.
  - **Mechanisms:** (a) the selection’s answer is handed to the page as its first read;
    (c) Changes holds its first paint for its first screen’s Markdown, at most
    `CHANGES_FIRST_SCREEN_MS` = 200 ms.
  - **Cost at final main:** Changes painted ready 79.2 to 102.2 ms where the control’s
    is 42.5 to 45.1 ms.
  - **Failure modes (exp-065):** a Changes paint waits out of sight up to 200 ms; if the
    page goes before the selection’s read answers, the read is aborted with it.

## Complexity Judgments

Clause 4, the coordinator’s, for each hypothesis that meets clauses 1 to 3, on the facts
above. Each is worth its complexity, so each is accepted at final main.

- **H86 (a): worth it.** Its mechanism is reserved boxes: slots, stable gutters, and a
  tab the server draws.
  No guard in exp-059’s table moved on any of its 23 transitions.
  `compare` lists 22 other wrong-way results on them, outside that table, such as frames
  to ready on `keyboard.down_cold.1`; this round does not say which change in final main
  they belong to. Its one wait, the Overview’s hold of the previous folder, is bounded at
  100 ms. Its failure modes are cosmetic: a row cut short with its text in a tooltip, and
  a toolbar that scrolls.
- **H91 (a): worth it.** A wait of at most 100 ms, for faces the page loads anyway,
  removes the first document’s reflow, and cold Markdown’s painted ready did not move.
- **H91 (b): worth it.** A bounded server inline (300 rows, 8 levels) removes the deep
  landing’s shift, and its painted ready did not move.
  A landing beyond the bounds keeps the control’s movement, no worse than before.
- **H91 (d): worth it.** A fixed group order removes all 11 row replacements, at no
  measured cost.
- **H92 (a): worth it.** It removes work: the page takes the read the selection already
  made, and duplicate reads went 8 to 0. The guard cells that rose are the first-paint
  hold’s, which (a) does not add.
- **H92 (c): worth it, and the campaign’s costliest accepted trade.**
  - The hold removes a body shift of 1.49 per run: content that moved under the reader
    after it painted. The control’s 43 ms is the time to a view that then rearranged
    itself.
  - It costs 34 to 59 ms on every Changes paint.
    Final main is ready at 79 to 102 ms, inside the 78 to 110 ms exp-065 recorded when
    it accepted the hold, so the cost has not grown.
  - The owner asked that nothing on the pull request page move, and the hold is how
    final main meets that.
  - It leaves Changes at about 100 ms, the edge of a switch that feels instant.
    The way to keep the stillness and win back the time is a hold with nothing to wait
    for: the first screen’s diffs prepared before the click.
    No registered hypothesis covers that yet.

## The Campaign Summary

Reported, not judged.
For every transition, from `compare` on the judged pairs:

- painted ready, median (range), with pair ratios, candidate over control;
- the no-input layout shift;
- the net region movement.

| Transition | Painted ready ms, control → candidate | Pair ratio | Verdict | No-input shift | Net region movement px |
| --- | --- | --- | --- | --- | --- |
| `landing.cold_markdown` | 273.4 (271.1–287.9) → 290.2 (287.6–294.1) | 1.05x (1.01–1.08) | no detected difference | 0.0033 → 0 | 0 → 0 |
| `landing.reload` | 166.5 (156.9–175.2) → 106.7 (105.9–124.9) | 0.67x (0.61–0.72) | lower, ranges apart, 6 of 6 pairs beyond | 0.0002 → 0 | 0 → 0 |
| `files.cold.markdown_large` | 180.5 (179.6–195.6) → 180.8 (180.3–197.5) | 1.00x (0.93–1.01) | no detected difference | 0 → 0 | 0 → 0 |
| `files.cold.markdown_mid` | 64.4 (62.1–65.2) → 64.4 (62.9–78.9) | 1.00x (0.96–1.25) | no detected difference | 0 → 0 | 0 → 0 |
| `files.cold.source_large` | 105.2 (95.7–128.5) → 114.2 (111.9–114.6) | 1.09x (0.89–1.20) | no detected difference | 0 → 0 | 30 → 0 |
| `files.cold.source_small` | 47.3 (46.8–48.8) → 47.0 (46.8–47.5) | 1.00x (0.96–1.01) | no detected difference | 0 → 0 | 0 → 0 |
| `files.cold.json` | 64.0 (63.4–65.6) → 64.4 (63.4–80.5) | 1.01x (0.97–1.27) | no detected difference | 0 → 0 | 30 → 0 |
| `files.cold.diff` | 80.2 (79.1–81.1) → 80.6 (78.8–95.9) | 1.00x (0.98–1.20) | no detected difference | 0 → 0 | 30 → 0 |
| `files.cold.image` | 79.1 (64.5–81.1) → 72.1 (62.8–81.1) | 0.99x (0.79–1.25) | no detected difference | 0 → 0 | 11 → 0 |
| `files.cold.binary` | 64.6 (63.9–64.9) → 63.2 (62.4–80.0) | 0.98x (0.97–1.24) | no detected difference | 0 → 0 | 11 → 0 |
| `files.revisit.source_large` | 79.9 (79.1–95.7) → 95.9 (80.0–96.4) | 1.19x (0.84–1.21) | no detected difference | 0 → 0 | 0 → 0 |
| `files.revisit.json` | 64.7 (63.6–65.0) → 64.4 (63.5–80.0) | 1.00x (0.99–1.24) | no detected difference | 0 → 0 | 30 → 0 |
| `files.revisit.markdown_small` | 63.6 (48.4–65.3) → 63.3 (62.7–79.1) | 1.00x (0.96–1.31) | no detected difference | 0 → 0 | 0 → 0 |
| `files.revisit.markdown_large` | 146.0 (130.8–147.9) → 145.8 (130.9–145.9) | 0.99x (0.90–1.11) | no detected difference | 0 → 0 | 0 → 0 |
| `files.history_back` | 38.5 (37.2–40.1) → 40.0 (39.1–41.1) | 1.05x (0.99–1.09) | no detected difference | 0 → 0 | 0 → 0 |
| `files.history_forward` | 123.1 (108.0–135.6) → 122.8 (119.6–138.0) | 1.00x (0.88–1.28) | no detected difference | 0 → 0 | 0 → 0 |
| `files.hover_click.markdown` | 71.6 (62.9–80.0) → 64.3 (63.6–65.7) | 0.91x (0.80–1.02) | no detected difference | 0 → 0 | 0 → 0 |
| `keyboard.down_cold.1` | 51.7 (41.5–54.5) → 53.0 (51.7–54.0) | 1.02x (0.99–1.28) | no detected difference | 0 → 0 | 11 → 0 |
| `keyboard.down_cold.2` | 54.5 (40.2–55.7) → 54.6 (43.0–55.2) | 1.01x (0.97–1.27) | no detected difference | 0 → 0 | 11 → 0 |
| `keyboard.down_cold.3` | 54.4 (43.4–55.7) → 42.9 (39.6–55.6) | 0.84x (0.76–1.02) | ranges overlap, one pair beyond | 0 → 0 | 30 → 0 |
| `keyboard.up_revisit.1` | 54.0 (42.5–58.3) → 54.3 (42.2–70.1) | 1.02x (0.77–1.31) | ranges overlap, one pair beyond | 0 → 0 | 30 → 0 |
| `keyboard.up_revisit.2` | 43.6 (42.3–44.9) → 41.7 (40.7–57.1) | 0.97x (0.92–1.33) | no detected difference | 0 → 0 | 11 → 0 |
| `views.markdown.first` | 29.9 (28.7–30.3) → 29.5 (28.8–30.7) | 1.00x (0.96–1.06) | no detected difference | 0 → 0 | 0 → 0 |
| `views.markdown.revisit` | 30.2 (29.0–31.5) → 29.7 (28.5–30.8) | 0.99x (0.95–1.02) | no detected difference | 0 → 0 | 0 → 0 |
| `views.markdown.revisit_2` | 30.3 (29.5–31.0) → 29.5 (29.0–31.0) | 0.98x (0.95–1.02) | no detected difference | 0 → 0 | 0 → 0 |
| `views.json.first` | 29.1 (28.2–30.2) → 29.4 (28.3–30.5) | 1.00x (0.95–1.06) | no detected difference | 0 → 0 | 0 → 0 |
| `views.json.revisit` | 31.6 (29.6–46.1) → 31.3 (29.4–46.2) | 0.99x (0.98–1.01) | no detected difference | 0 → 0 | 0 → 0 |
| `views.json.revisit_2` | 30.7 (29.1–31.9) → 30.8 (29.6–31.7) | 1.00x (0.97–1.05) | no detected difference | 0 → 0 | 0 → 0 |
| `views.folder.first` | 47.3 (45.6–48.2) → 46.9 (46.0–47.8) | 0.99x (0.96–1.05) | no detected difference | 0 → 0 | 0 → 0 |
| `views.folder.revisit` | 30.2 (29.4–31.1) → 30.9 (29.6–31.8) | 1.03x (0.98–1.04) | no detected difference | 0 → 0 | 0 → 0 |
| `views.folder.revisit_2` | 31.0 (30.0–32.2) → 30.8 (29.6–32.0) | 0.98x (0.95–1.07) | no detected difference | 0 → 0 | 0 → 0 |
| `main.files_to_commits.first` (landing differs, not judged) | 237.4 (229.1–262.5) → 195.3 (179.0–195.7) | 0.82x (0.72–0.85) | lower, ranges apart, 2 of 6 pairs beyond | 0 → 0 | 37 → 0 |
| `main.commits_to_files.first` | 79.0 (62.8–80.7) → 79.0 (63.7–80.9) | 1.00x (0.79–1.26) | no detected difference | 0 → 0 | 37 → 0 |
| `main.files_to_commits.again` (landing differs, not judged) | 29.1 (28.7–30.3) → 63.0 (61.9–79.0) | 2.19x (2.04–2.71) | higher, ranges apart, 6 of 6 pairs beyond | 0 → 0 | 37 → 0 |
| `main.commits_to_files.again` | 63.1 (62.7–64.6) → 78.1 (62.3–80.1) | 1.22x (0.98–1.27) | no detected difference | 0 → 0 | 37 → 0 |
| `main.files_to_pulls.first` | 29.9 (29.0–30.4) → 29.1 (28.8–30.5) | 0.98x (0.96–1.05) | no detected difference | 0 → 0 | 37 → 0 |
| `main.pulls_to_files.first` | 62.5 (62.3–63.8) → 62.8 (60.5–63.2) | 1.00x (0.97–1.01) | no detected difference | 0 → 0 | 37 → 0 |
| `main.files_to_pulls.again` | 29.7 (26.0–30.9) → 30.0 (28.8–30.7) | 1.02x (0.93–1.18) | no detected difference | 0 → 0 | 37 → 0 |
| `main.pulls_to_commits` (landing differs, not judged) | 30.9 (30.0–31.6) → 63.6 (63.5–65.0) | 2.06x (2.01–2.12) | higher, ranges apart, 6 of 6 pairs beyond | 0 → 0 | 0 → 0 |
| `main.commits_to_pulls` | 30.1 (29.0–30.6) → 29.9 (28.9–31.1) | 0.99x (0.98–1.06) | no detected difference | 0 → 0 | 0 → 0 |
| `main.pulls_to_files.again` | 63.3 (62.5–65.2) → 63.8 (62.8–64.7) | 1.00x (0.97–1.03) | no detected difference | 0 → 0 | 37 → 0 |
| `main_subject.files_to_commits` (landing differs, not judged) | 213.9 (213.3–231.5) → 63.6 (62.6–78.1) | 0.30x (0.27–0.36) | lower, ranges apart, 6 of 6 pairs beyond | 0 → 0 | 37 → 0 |
| `main_subject.commits_to_pulls` | 79.4 (63.6–95.6) → 112.1 (80.5–112.4) | 1.32x (1.18–1.42) | ranges overlap, 3 of 6 pairs higher beyond | 0 → 0 | 0 → 0 |
| `main_subject.pulls_to_files` | 64.3 (63.5–80.1) → 79.6 (63.5–80.5) | 1.23x (0.79–1.27) | no detected difference | 0 → 0 | 37 → 0 |
| `main_subject.files_to_pulls` | 80.3 (78.8–81.2) → 79.8 (78.9–96.3) | 1.01x (0.97–1.20) | no detected difference | 0 → 0 | 37 → 0 |
| `main_subject.pulls_to_commits` (landing differs, not judged) | 228.9 (180.4–232.0) → 79.4 (78.7–80.8) | 0.35x (0.34–0.45) | lower, ranges apart, 6 of 6 pairs beyond | 0 → 0 | 0 → 0 |
| `main_subject.commits_to_files` | 71.8 (62.4–79.7) → 63.6 (62.1–64.1) | 0.90x (0.79–1.00) | no detected difference | 0 → 0 | 37 → 0 |
| `commits.first_show` (landing differs, not judged) | 278.8 (264.3–280.0) → 197.9 (180.3–212.0) | 0.71x (0.68–0.76) | lower, ranges apart, 6 of 6 pairs beyond | 0 → 0 | 37 → 0 |
| `commits.cold.1` | 122.9 (114.2–180.3) → 163.5 (112.6–164.8) | 1.12x (0.69–1.43) | ranges overlap, 2 of 6 pairs higher beyond | 0 → 0 | 0 → 0 |
| `commits.cold.2` | 164.4 (162.6–197.6) → 159.5 (113.8–163.3) | 0.94x (0.69–0.98) | ranges overlap, one pair beyond | 0 → 0 | 0 → 0 |
| `commits.cold.3` | 146.9 (113.1–163.0) → 145.8 (113.7–163.0) | 1.00x (0.90–1.28) | no detected difference | 0 → 0 | 0 → 0 |
| `commits.revisit.1` | 122.5 (97.4–148.6) → 30.4 (29.3–32.3) | 0.26x (0.20–0.33) | lower, ranges apart, 6 of 6 pairs beyond | 0 → 0 | 0 → 0 |
| `commits.revisit.2` | 164.4 (147.1–181.6) → 31.1 (29.9–31.7) | 0.19x (0.17–0.21) | lower, ranges apart, 6 of 6 pairs beyond | 0 → 0 | 0 → 0 |
| `commits.hover_click` | 31.9 (31.5–32.5) → 30.7 (30.6–31.3) | 0.96x (0.96–0.98) | lower, ranges apart, every pair within 1.3x | 0 → 0 | 0 → 0 |
| `pulls.first_show` | 29.4 (28.9–31.0) → 29.8 (28.2–31.4) | 1.00x (0.98–1.05) | no detected difference | 0 → 0 | 37 → 0 |
| `pulls.list_to_pr.cold` | 57.9 (56.9–75.8) → 90.5 (74.3–91.7) | 1.55x (0.98–1.61) | ranges overlap, 4 of 6 pairs higher beyond | 0 → 0 | 0 → 0 |
| `pulls.tab.changes_first` | 42.8 (40.3–57.2) → 102.2 (92.4–109.5) | 2.30x (1.89–2.68) | higher, ranges apart, 6 of 6 pairs beyond | 0 → 0 | 8 → 0 |
| `pulls.tab.checks_first` | 29.1 (27.8–29.7) → 29.1 (27.4–29.9) | 1.01x (0.93–1.05) | no detected difference | 0 → 0 | 8 → 0 |
| `pulls.tab.conversation_revisit` | 29.0 (27.3–29.8) → 26.5 (24.7–28.6) | 0.91x (0.83–1.01) | no detected difference | 0 → 0 | 0 → 0 |
| `pulls.tab.changes_revisit` | 45.1 (43.7–45.6) → 79.2 (74.1–86.0) | 1.76x (1.63–1.91) | higher, ranges apart, 6 of 6 pairs beyond | 0 → 0 | 8 → 0 |
| `pulls.tab.conversation_revisit_2` | 28.1 (27.7–42.6) → 26.6 (25.1–43.3) | 0.96x (0.61–1.50) | ranges overlap, one pair beyond | 0 → 0 | 8 → 0 |
| `pulls.pr_to_pr.cold` | 45.5 (44.4–45.9) → 61.4 (59.0–62.7) | 1.36x (1.33–1.37) | higher, ranges apart, 6 of 6 pairs beyond | 0 → 0 | 0 → 0 |
| `pulls.pr_to_pr.revisit` | 27.7 (25.0–41.8) → 44.2 (43.1–58.4) | 1.72x (1.04–2.12) | higher, ranges apart, 5 of 6 pairs beyond | 0 → 0 | 0 → 0 |
| `pulls.pr_to_pr.hover_click` | 38.5 (30.2–48.1) → 96.4 (82.3–97.1) | 2.40x (2.01–3.18) | higher, ranges apart, 6 of 6 pairs beyond | 0 → 0 | 0 → 0 |
| `pulls.tab.changes_first_2` | 43.9 (42.2–58.0) → 95.1 (93.6–97.6) | 2.19x (1.64–2.25) | higher, ranges apart, 6 of 6 pairs beyond | 0 → 0 | 8 → 0 |
| `pulls.history_back` | 39.5 (37.2–55.6) → 41.3 (39.6–54.5) | 1.05x (0.75–1.46) | ranges overlap, one pair beyond | 0 → 0 | 8 → 0 |
| `pulls.tab.changes_revisit_2` | 42.5 (41.6–43.9) → 95.9 (93.9–96.7) | 2.23x (2.20–2.31) | higher, ranges apart, 6 of 6 pairs beyond | 0 → 0 | 8 → 0 |
| `pulls.pr_changes_to_pr` | 62.2 (60.9–62.8) → 111.5 (94.5–112.6) | 1.78x (1.52–1.84) | higher, ranges apart, 6 of 6 pairs beyond | 0 → 0 | 8 → 0 |
| `tree.expand.docs` | 63.9 (62.6–79.1) → 79.4 (78.5–80.1) | 1.24x (0.99–1.28) | no detected difference | 0 → 0 | 11 → 0 |
| `tree.expand.src` | 46.3 (45.8–46.7) → 46.8 (45.7–47.7) | 1.01x (0.98–1.04) | no detected difference | 0 → 0 | 0 → 0 |
| `tree.collapse.src` | 30.6 (30.1–32.1) → 29.3 (27.4–30.3) | 0.96x (0.91–1.00) | no detected difference | 0 → 0 | 0 → 0 |
| `tree.reexpand.src` | 30.2 (27.5–31.3) → 30.4 (29.8–31.1) | 1.01x (0.95–1.13) | no detected difference | 0 → 0 | 0 → 0 |
| `tree.expand_nested.src_metabrowser` | 47.1 (46.6–48.8) → 47.0 (46.5–47.8) | 1.00x (0.95–1.02) | no detected difference | 0 → 0 | 0 → 0 |
| `palette.open` | 29.1 (19.3–30.6) → 25.8 (23.4–33.9) | 0.99x (0.78–1.51) | no detected difference | 0 → 0 | 0 → 0 |
| `palette.query` | 189.2 (188.1–190.0) → 188.1 (175.0–189.6) | 1.00x (0.92–1.00) | no detected difference | 0 → 0 | 0 → 0 |
| `skim.held_arrow_down` | 380.2 (372.8–386.9) → 411.0 (401.3–419.3) | 1.07x (1.04–1.13) | higher, ranges apart, every pair within 1.3x | 0 → 0 | 0 → 0 |
| `reveal.deep_landing` | 185.9 (183.5–194.1) → 189.7 (181.6–201.4) | 1.01x (0.97–1.10) | no detected difference | 0.057 (0.0531–0.0608) → 0 | 0 → 0 |

## Every Wrong-Way Result

`compare` lists 167 wrong-way results, 139 of them results and 28 under overlapping
ranges with two or more pairs beyond, and no gap.
This table is the full list.
Only the ones inside a hypothesis’s own table count against it, and **Results** says
which those are.

| Transition | Metric | Control → candidate | compare |
| --- | --- | --- | --- |
| `landing.cold_markdown` | requests_static | 41 → 44 | higher, ranges apart |
| `landing.cold_markdown` | requests_kpress | 18 → 19 | higher, ranges apart |
| `landing.cold_markdown` | static_network | 41 → 44 | higher, ranges apart |
| `landing.cold_markdown` | kpress_static_network | 16 → 18 | higher, ranges apart |
| `landing.reload` | requests_static | 41 → 44 | higher, ranges apart |
| `landing.reload` | requests_kpress | 18 → 19 | higher, ranges apart |
| `files.cold.markdown_mid` | frames_to_ready | 2 (2–3) → 2.5 (2–3) | ranges overlap, 2 of 6 pairs higher beyond |
| `files.cold.source_large` | frames_to_ready | 2.5 (2–3) → 3 | ranges overlap, 3 of 6 pairs higher beyond |
| `files.cold.source_small` | preview_top_replaced | 3 → 4 | higher, ranges apart |
| `files.cold.json` | preview_top_replaced | 3 → 4 | higher, ranges apart |
| `files.cold.diff` | data_network | 3.5 (3–4) → 5 | higher, ranges apart |
| `files.cold.image` | preview_top_replaced | 3 → 4 | higher, ranges apart |
| `files.cold.binary` | preview_top_replaced | 3 → 4 | higher, ranges apart |
| `files.cold.binary` | data_network | 1 → 3 (2–3) | higher, ranges apart |
| `files.revisit.source_large` | preview_top_replaced | 3 → 4 | higher, ranges apart |
| `files.revisit.json` | preview_top_replaced | 3 → 4 | higher, ranges apart |
| `files.revisit.markdown_small` | data_network | 1 → 3 | higher, ranges apart |
| `keyboard.down_cold.1` | ready_ms | 38.6 (27.6–40.9) → 38.7 (37.7–39.7) | ranges overlap, 2 of 6 pairs higher beyond |
| `keyboard.down_cold.1` | frames_to_ready | 2 (2–3) → 3 | ranges overlap, 5 of 6 pairs higher beyond |
| `keyboard.down_cold.2` | frames_to_ready | 2.5 (2–3) → 3 (2–3) | ranges overlap, 2 of 6 pairs higher beyond |
| `keyboard.up_revisit.1` | ready_ms | 40.7 (27.8–44.1) → 41.3 (28.4–57.0) | ranges overlap, 2 of 6 pairs higher beyond |
| `keyboard.up_revisit.1` | preview_top_replaced | 3 → 4 | higher, ranges apart |
| `keyboard.up_revisit.2` | frames_to_ready | 2 → 2 (2–3) | ranges overlap, 2 of 6 pairs higher beyond |
| `views.markdown.revisit` | settled_ms | 2.3 (1.6–2.5) → 3.1 (3.0–3.4) | higher, ranges apart, 4 of 6 pairs beyond |
| `views.markdown.revisit_2` | settled_ms | 2.4 (1.3–3.1) → 3.1 (2.1–3.9) | ranges overlap, 3 of 6 pairs higher beyond |
| `views.json.revisit` | settled_ms | 4.6 (2.3–5.3) → 4.6 (3.6–5.4) | ranges overlap, 2 of 6 pairs higher beyond |
| `main.files_to_commits.first` | settled_ms | 10.6 (7.9–11.2) → 207.4 (196.4–208.0) | higher, ranges apart, 6 of 6 pairs beyond |
| `main.files_to_commits.first` | requests_data | 4 → 6 | higher, ranges apart |
| `main.files_to_commits.first` | requests_plugin | 0 → 7 | higher, ranges apart |
| `main.files_to_commits.first` | preview_top_replaced | 4 → 5 | higher, ranges apart |
| `main.files_to_commits.first` | dom_nodes_end | 3227 → 5144 | higher, ranges apart |
| `main.files_to_commits.first` | plugin_static_network | 0 → 7 | higher, ranges apart |
| `main.files_to_commits.first` | data_network | 6 → 8 | higher, ranges apart |
| `main.files_to_commits.again` | painted_ready_ms | 29.1 (28.7–30.3) → 63.0 (61.9–79.0) | higher, ranges apart, 6 of 6 pairs beyond |
| `main.files_to_commits.again` | ready_ms | 17.7 (13.4–20.5) → 56.5 (50.4–67.0) | higher, ranges apart, 6 of 6 pairs beyond |
| `main.files_to_commits.again` | frames_to_ready | 1 → 2 | higher, ranges apart, 6 of 6 pairs beyond |
| `main.files_to_commits.again` | settled_ms | 15.9 (9.4–18.6) → 73.4 (64.4–80.5) | higher, ranges apart, 6 of 6 pairs beyond |
| `main.files_to_commits.again` | ready_after_last_input_ms | 29.1 (28.7–30.3) → 63.0 (61.9–79.0) | higher, ranges apart, 6 of 6 pairs beyond |
| `main.files_to_commits.again` | preview_top_replaced | 4 → 5 | higher, ranges apart |
| `main.files_to_commits.again` | dom_nodes_end | 3227 → 5144 | higher, ranges apart |
| `main.files_to_pulls.first` | settled_ms | 15.5 (8.5–17.4) → 18.2 (15.7–20.3) | ranges overlap, 2 of 6 pairs higher beyond |
| `main.files_to_pulls.first` | requests_data | 4 → 5 | higher, ranges apart |
| `main.files_to_pulls.first` | post_body_bytes | 54 → 116 | higher, ranges apart |
| `main.pulls_to_commits` | painted_ready_ms | 30.9 (30.0–31.6) → 63.6 (63.5–65.0) | higher, ranges apart, 6 of 6 pairs beyond |
| `main.pulls_to_commits` | ready_ms | 16.4 (14.7–17.3) → 57.0 (52.9–57.9) | higher, ranges apart, 6 of 6 pairs beyond |
| `main.pulls_to_commits` | frames_to_ready | 1 → 2 | higher, ranges apart, 6 of 6 pairs beyond |
| `main.pulls_to_commits` | settled_ms | 8.2 (7.6–12.4) → 75.1 (73.6–76.2) | higher, ranges apart, 6 of 6 pairs beyond |
| `main.pulls_to_commits` | ready_after_last_input_ms | 30.9 (30.0–31.6) → 63.6 (63.5–65.0) | higher, ranges apart, 6 of 6 pairs beyond |
| `main.pulls_to_commits` | preview_top_replaced | 1 → 3 | higher, ranges apart |
| `main.pulls_to_commits` | dom_nodes_end | 3227 → 5144 | higher, ranges apart |
| `main.commits_to_pulls` | settled_ms | 9.6 (4.2–10.8) → 11.6 (6.7–14.7) | ranges overlap, 2 of 6 pairs higher beyond |
| `main_subject.files_to_commits` | dom_nodes_end | 6568 → 7697 | higher, ranges apart |
| `main_subject.commits_to_pulls` | painted_ready_ms | 79.4 (63.6–95.6) → 112.1 (80.5–112.4) | ranges overlap, 3 of 6 pairs higher beyond |
| `main_subject.commits_to_pulls` | ready_ms | 68.6 (51.0–81.8) → 96.4 (80.0–98.3) | ranges overlap, 4 of 6 pairs higher beyond |
| `main_subject.commits_to_pulls` | ready_after_last_input_ms | 79.4 (63.6–95.6) → 112.1 (80.5–112.4) | ranges overlap, 3 of 6 pairs higher beyond |
| `main_subject.commits_to_pulls` | pr_header_ms | 79.4 (63.6–95.6) → 112.1 (80.5–112.4) | ranges overlap, 3 of 6 pairs higher beyond |
| `main_subject.commits_to_pulls` | pr_description_shown_ms | 79.4 (63.6–95.6) → 112.1 (80.5–112.4) | ranges overlap, 3 of 6 pairs higher beyond |
| `main_subject.commits_to_pulls` | requests_data | 12 (11–12) → 13 | higher, ranges apart |
| `main_subject.commits_to_pulls` | dom_nodes_end | 7174 → 7599 | higher, ranges apart |
| `main_subject.commits_to_pulls` | data_network | 15 (12–15) → 16 | higher, ranges apart |
| `main_subject.pulls_to_files` | dom_nodes_end | 6045 → 6129 | higher, ranges apart |
| `main_subject.files_to_pulls` | dom_nodes_end | 7174 → 7599 | higher, ranges apart |
| `main_subject.pulls_to_commits` | dom_nodes_end | 6568 → 7697 | higher, ranges apart |
| `main_subject.commits_to_files` | dom_nodes_end | 6045 → 6129 | higher, ranges apart |
| `commits.first_show` | settled_ms | 10.4 (6.8–11.1) → 208.5 (198.3–210.4) | higher, ranges apart, 6 of 6 pairs beyond |
| `commits.first_show` | requests_data | 4 → 6 | higher, ranges apart |
| `commits.first_show` | requests_plugin | 0 → 7 | higher, ranges apart |
| `commits.first_show` | preview_top_replaced | 4 → 5 | higher, ranges apart |
| `commits.first_show` | dom_nodes_end | 3010 → 4927 | higher, ranges apart |
| `commits.first_show` | plugin_static_network | 0 → 7 | higher, ranges apart |
| `commits.first_show` | data_network | 6 → 8 | higher, ranges apart |
| `commits.cold.1` | painted_ready_ms | 122.9 (114.2–180.3) → 163.5 (112.6–164.8) | ranges overlap, 2 of 6 pairs higher beyond |
| `commits.cold.1` | ready_ms | 113.9 (109.0–174.0) → 150.5 (104.4–154.7) | ranges overlap, 2 of 6 pairs higher beyond |
| `commits.cold.1` | ready_after_last_input_ms | 122.9 (114.2–180.3) → 163.5 (112.6–164.8) | ranges overlap, 2 of 6 pairs higher beyond |
| `pulls.first_show` | post_body_bytes | 56 (54–56) → 117 (116–118) | higher, ranges apart |
| `pulls.list_to_pr.cold` | painted_ready_ms | 57.9 (56.9–75.8) → 90.5 (74.3–91.7) | ranges overlap, 4 of 6 pairs higher beyond |
| `pulls.list_to_pr.cold` | ready_ms | 44.4 (43.2–63.1) → 84.6 (66.4–85.8) | higher, ranges apart, 5 of 6 pairs beyond |
| `pulls.list_to_pr.cold` | frames_to_ready | 2 (2–3) → 4 | higher, ranges apart, 6 of 6 pairs beyond |
| `pulls.list_to_pr.cold` | settled_ms | 72.5 (71.5–92.7) → 104.7 (100.7–120.3) | higher, ranges apart, 5 of 6 pairs beyond |
| `pulls.list_to_pr.cold` | ready_after_last_input_ms | 57.9 (56.9–75.8) → 90.5 (74.3–91.7) | ranges overlap, 4 of 6 pairs higher beyond |
| `pulls.list_to_pr.cold` | requests_data | 14 → 16 (16–17) | higher, ranges apart |
| `pulls.list_to_pr.cold` | post_body_bytes | 178 → 360 | higher, ranges apart |
| `pulls.list_to_pr.cold` | dom_nodes_end | 5253 → 5670 | higher, ranges apart |
| `pulls.list_to_pr.cold` | data_network | 16 → 21 (19–21) | higher, ranges apart |
| `pulls.tab.changes_first` | painted_ready_ms | 42.8 (40.3–57.2) → 102.2 (92.4–109.5) | higher, ranges apart, 6 of 6 pairs beyond |
| `pulls.tab.changes_first` | ready_ms | 36.9 (34.7–50.8) → 89.1 (82.8–100.3) | higher, ranges apart, 6 of 6 pairs beyond |
| `pulls.tab.changes_first` | frames_to_ready | 2 (2–3) → 5.5 (5–6) | higher, ranges apart, 6 of 6 pairs beyond |
| `pulls.tab.changes_first` | ready_after_last_input_ms | 42.8 (40.3–57.2) → 102.2 (92.4–109.5) | higher, ranges apart, 6 of 6 pairs beyond |
| `pulls.tab.changes_first` | dom_nodes_end | 7689 → 7943 (7778–7943) | higher, ranges apart |
| `pulls.tab.checks_first` | dom_nodes_end | 5077 → 5340 | higher, ranges apart |
| `pulls.tab.conversation_revisit` | settled_ms | 12.8 (11.6–13.8) → 16.7 (13.3–21.1) | ranges overlap, 3 of 6 pairs higher beyond |
| `pulls.tab.conversation_revisit` | dom_nodes_end | 5253 → 5670 | higher, ranges apart |
| `pulls.tab.changes_revisit` | painted_ready_ms | 45.1 (43.7–45.6) → 79.2 (74.1–86.0) | higher, ranges apart, 6 of 6 pairs beyond |
| `pulls.tab.changes_revisit` | ready_ms | 34.5 (33.3–34.9) → 68.5 (62.5–75.3) | higher, ranges apart, 6 of 6 pairs beyond |
| `pulls.tab.changes_revisit` | frames_to_ready | 2 → 4 (4–5) | higher, ranges apart, 6 of 6 pairs beyond |
| `pulls.tab.changes_revisit` | ready_after_last_input_ms | 45.1 (43.7–45.6) → 79.2 (74.1–86.0) | higher, ranges apart, 6 of 6 pairs beyond |
| `pulls.tab.changes_revisit` | dom_nodes_end | 7524 → 7778 | higher, ranges apart |
| `pulls.tab.conversation_revisit_2` | ready_ms | 14.9 (12.0–27.5) → 22.2 (17.3–30.7) | ranges overlap, 3 of 6 pairs higher beyond |
| `pulls.tab.conversation_revisit_2` | settled_ms | 12.1 (9.3–17.5) → 21.2 (16.3–29.7) | ranges overlap, 5 of 6 pairs higher beyond |
| `pulls.tab.conversation_revisit_2` | dom_nodes_end | 5253 → 5670 | higher, ranges apart |
| `pulls.tab.conversation_revisit_2` | data_network | 2 (2–3) → 6 | higher, ranges apart |
| `pulls.pr_to_pr.cold` | painted_ready_ms | 45.5 (44.4–45.9) → 61.4 (59.0–62.7) | higher, ranges apart, 6 of 6 pairs beyond |
| `pulls.pr_to_pr.cold` | ready_ms | 36.6 (35.8–37.4) → 57.7 (54.6–59.1) | higher, ranges apart, 6 of 6 pairs beyond |
| `pulls.pr_to_pr.cold` | frames_to_ready | 2 → 3 | higher, ranges apart, 6 of 6 pairs beyond |
| `pulls.pr_to_pr.cold` | settled_ms | 75.5 (73.2–76.2) → 97.5 (93.0–145.1) | higher, ranges apart, 2 of 6 pairs beyond |
| `pulls.pr_to_pr.cold` | ready_after_last_input_ms | 45.5 (44.4–45.9) → 61.4 (59.0–62.7) | higher, ranges apart, 6 of 6 pairs beyond |
| `pulls.pr_to_pr.cold` | pr_header_ms | 45.5 (44.4–45.9) → 61.4 (59.0–62.7) | higher, ranges apart, 6 of 6 pairs beyond |
| `pulls.pr_to_pr.cold` | pr_description_shown_ms | 45.5 (44.4–45.9) → 61.4 (59.0–62.7) | higher, ranges apart, 6 of 6 pairs beyond |
| `pulls.pr_to_pr.cold` | requests_data | 13 → 14 | higher, ranges apart |
| `pulls.pr_to_pr.cold` | post_body_bytes | 178 → 264 | higher, ranges apart |
| `pulls.pr_to_pr.cold` | dom_nodes_end | 5250 → 5955 | higher, ranges apart |
| `pulls.pr_to_pr.cold` | data_network | 17 (17–18) → 19 | higher, ranges apart |
| `pulls.pr_to_pr.revisit` | painted_ready_ms | 27.7 (25.0–41.8) → 44.2 (43.1–58.4) | higher, ranges apart, 5 of 6 pairs beyond |
| `pulls.pr_to_pr.revisit` | ready_ms | 14.7 (11.5–28.7) → 42.3 (40.2–46.9) | higher, ranges apart, 6 of 6 pairs beyond |
| `pulls.pr_to_pr.revisit` | frames_to_ready | 1 (1–2) → 2 | ranges overlap, 5 of 6 pairs higher beyond |
| `pulls.pr_to_pr.revisit` | ready_after_last_input_ms | 27.7 (25.0–41.8) → 44.2 (43.1–58.4) | higher, ranges apart, 5 of 6 pairs beyond |
| `pulls.pr_to_pr.revisit` | pr_header_ms | 27.7 (25.0–41.8) → 44.2 (43.1–58.4) | higher, ranges apart, 5 of 6 pairs beyond |
| `pulls.pr_to_pr.revisit` | pr_description_shown_ms | 27.7 (25.0–41.8) → 44.2 (43.1–58.4) | higher, ranges apart, 5 of 6 pairs beyond |
| `pulls.pr_to_pr.revisit` | requests_data | 12 → 14 | higher, ranges apart |
| `pulls.pr_to_pr.revisit` | post_body_bytes | 178 → 352 | higher, ranges apart |
| `pulls.pr_to_pr.revisit` | dom_nodes_end | 5028 → 5387 | higher, ranges apart |
| `pulls.pr_to_pr.revisit` | data_network | 12 → 15 | higher, ranges apart |
| `pulls.pr_to_pr.hover_click` | painted_ready_ms | 38.5 (30.2–48.1) → 96.4 (82.3–97.1) | higher, ranges apart, 6 of 6 pairs beyond |
| `pulls.pr_to_pr.hover_click` | ready_ms | 30.5 (28.9–34.6) → 83.4 (75.4–89.3) | higher, ranges apart, 6 of 6 pairs beyond |
| `pulls.pr_to_pr.hover_click` | frames_to_ready | 1 → 3 (2–3) | higher, ranges apart, 6 of 6 pairs beyond |
| `pulls.pr_to_pr.hover_click` | settled_ms | 66.0 (62.2–68.3) → 96.7 (94.4–128.8) | higher, ranges apart, 6 of 6 pairs beyond |
| `pulls.pr_to_pr.hover_click` | ready_after_last_input_ms | 38.5 (30.2–48.1) → 96.4 (82.3–97.1) | higher, ranges apart, 6 of 6 pairs beyond |
| `pulls.pr_to_pr.hover_click` | pr_header_ms | 38.5 (30.2–48.1) → 96.4 (82.3–97.1) | higher, ranges apart, 6 of 6 pairs beyond |
| `pulls.pr_to_pr.hover_click` | pr_description_shown_ms | 38.5 (30.2–48.1) → 96.4 (82.3–97.1) | higher, ranges apart, 6 of 6 pairs beyond |
| `pulls.pr_to_pr.hover_click` | pr_description_final_ms | 63.7 (63.3–64.9) → 96.4 (82.3–97.1) | higher, ranges apart, 5 of 6 pairs beyond |
| `pulls.pr_to_pr.hover_click` | requests_data | 14 → 16 | higher, ranges apart |
| `pulls.pr_to_pr.hover_click` | post_body_bytes | 178 → 277 | higher, ranges apart |
| `pulls.pr_to_pr.hover_click` | dom_nodes_end | 5762 → 6714 | higher, ranges apart |
| `pulls.pr_to_pr.hover_click` | data_network | 19 (19–20) → 21 (21–25) | higher, ranges apart |
| `pulls.tab.changes_first_2` | painted_ready_ms | 43.9 (42.2–58.0) → 95.1 (93.6–97.6) | higher, ranges apart, 6 of 6 pairs beyond |
| `pulls.tab.changes_first_2` | ready_ms | 37.9 (36.7–53.3) → 81.9 (78.8–83.0) | higher, ranges apart, 6 of 6 pairs beyond |
| `pulls.tab.changes_first_2` | frames_to_ready | 2 (2–3) → 5 | higher, ranges apart, 6 of 6 pairs beyond |
| `pulls.tab.changes_first_2` | settled_ms | 76.4 (68.2–90.5) → 223.7 (222.0–227.1) | higher, ranges apart, 6 of 6 pairs beyond |
| `pulls.tab.changes_first_2` | ready_after_last_input_ms | 43.9 (42.2–58.0) → 95.1 (93.6–97.6) | higher, ranges apart, 6 of 6 pairs beyond |
| `pulls.tab.changes_first_2` | dom_nodes_end | 7070 → 7265 | higher, ranges apart |
| `pulls.history_back` | dom_nodes_end | 5421 → 6714 | higher, ranges apart |
| `pulls.tab.changes_revisit_2` | painted_ready_ms | 42.5 (41.6–43.9) → 95.9 (93.9–96.7) | higher, ranges apart, 6 of 6 pairs beyond |
| `pulls.tab.changes_revisit_2` | ready_ms | 38.1 (35.6–41.4) → 83.1 (79.7–86.2) | higher, ranges apart, 6 of 6 pairs beyond |
| `pulls.tab.changes_revisit_2` | frames_to_ready | 2 → 5 | higher, ranges apart, 6 of 6 pairs beyond |
| `pulls.tab.changes_revisit_2` | settled_ms | 81.3 (69.8–84.5) → 223.0 (220.2–224.5) | higher, ranges apart, 6 of 6 pairs beyond |
| `pulls.tab.changes_revisit_2` | ready_after_last_input_ms | 42.5 (41.6–43.9) → 95.9 (93.9–96.7) | higher, ranges apart, 6 of 6 pairs beyond |
| `pulls.tab.changes_revisit_2` | dom_nodes_end | 7070 → 7265 | higher, ranges apart |
| `pulls.pr_changes_to_pr` | painted_ready_ms | 62.2 (60.9–62.8) → 111.5 (94.5–112.6) | higher, ranges apart, 6 of 6 pairs beyond |
| `pulls.pr_changes_to_pr` | ready_ms | 55.7 (53.8–58.9) → 102.5 (94.4–107.9) | higher, ranges apart, 6 of 6 pairs beyond |
| `pulls.pr_changes_to_pr` | frames_to_ready | 2 → 4 (4–5) | higher, ranges apart, 6 of 6 pairs beyond |
| `pulls.pr_changes_to_pr` | settled_ms | 87.4 (72.9–105.6) → 173.9 (150.8–205.5) | higher, ranges apart, 6 of 6 pairs beyond |
| `pulls.pr_changes_to_pr` | ready_after_last_input_ms | 62.2 (60.9–62.8) → 111.5 (94.5–112.6) | higher, ranges apart, 6 of 6 pairs beyond |
| `pulls.pr_changes_to_pr` | pr_header_ms | 62.2 (60.9–62.8) → 111.5 (94.5–112.6) | higher, ranges apart, 6 of 6 pairs beyond |
| `pulls.pr_changes_to_pr` | pr_description_shown_ms | 62.2 (60.9–62.8) → 111.5 (94.5–112.6) | higher, ranges apart, 6 of 6 pairs beyond |
| `pulls.pr_changes_to_pr` | pr_description_final_ms | 79.2 (77.6–96.2) → 111.5 (94.5–112.6) | ranges overlap, 3 of 6 pairs higher beyond |
| `pulls.pr_changes_to_pr` | post_body_bytes | 179 (178–256) → 258 (257–259) | higher, ranges apart |
| `pulls.pr_changes_to_pr` | dom_nodes_end | 5983 → 7061 | higher, ranges apart |
| `tree.expand.docs` | frames_to_ready | 3 (3–4) → 4 | ranges overlap, 4 of 6 pairs higher beyond |
| `tree.collapse.src` | data_network | 0.5 (0–1) → 2 | higher, ranges apart |
| `palette.open` | data_network | 1 (0–1) → 2 | higher, ranges apart |
| `skim.held_arrow_down` | ready_after_last_input_ms | 46.2 (42.9–50.3) → 65.0 (56.8–72.5) | higher, ranges apart, 3 of 6 pairs beyond |
| `reveal.deep_landing` | placeholder_visible_frames | 4 (3–4) → 4 (3–5) | ranges overlap, 2 of 6 pairs higher beyond |
| `reveal.deep_landing` | settled_ms | 193.5 (191.1–200.0) → 261.3 (257.4–266.0) | higher, ranges apart, 6 of 6 pairs beyond |
| `reveal.deep_landing` | requests_static | 41 → 44 | higher, ranges apart |
| `reveal.deep_landing` | requests_kpress | 2.5 (2–3) → 7 | higher, ranges apart |
| `reveal.deep_landing` | static_network | 41 → 44 | higher, ranges apart |
| `reveal.deep_landing` | kpress_static_network | 2.5 (2–3) → 7 | higher, ranges apart |

## Limits

- **Final main is one build.** A result here belongs to the whole of it, not to the one
  change whose record names the metric:
  - the 52 merges since `09903292` outside the campaign lanes touch some of the same
    files;
  - one lane’s first-paint holds cost another’s guards (H86 (b));
  - `main_subject.commits_to_pulls`, which leaves H88 (a) and H106 unresolved, is later
    for a reason this round does not show.
- **The control is main from 2.5 days and 826 commits earlier.** Product behavior that
  changed since, such as the newest-commit landing, is not judged where it changes a
  transition’s subject.
- **Six pairs** resolve the large effects here.
  They do not resolve a one-frame difference, which is why exp-087’s later-frame test
  exists for H87.
- **Not measured:** WebKit; H92 (b)'s late file list; H88 (b)'s server routes; the hold
  spans.

## Reproducing

```shell
# $HARNESS, $CONTROL, $CANDIDATE and $CORPUS as in the protocol; the raw runs, which hold
# local paths, are $HARNESS/.bench/transitions/exp-079/runs.jsonl.
node $HARNESS/explorations/performance-loop/transitions.mjs samples \
  $HARNESS/.bench/transitions/exp-079/runs.jsonl --out exp-079-transition-samples.jsonl
node exp-079-exclude.mjs exp-079-transition-samples.jsonl exp-079-power.jsonl \
  --split /tmp/judged-samples.jsonl /tmp/exp079-other.jsonl
node exp-079-exclude.mjs $HARNESS/.bench/transitions/exp-079/runs.jsonl exp-079-power.jsonl \
  --split /tmp/exp079-judged-runs.jsonl /tmp/exp079-other-runs.jsonl
node exp-079-derive.mjs /tmp/exp079-judged-runs.jsonl exp-079-skim-evidence.jsonl
node exp-065-instruments/derive-h92-h106.mjs /tmp/exp079-judged-runs.jsonl \
  exp-079-derived-samples.jsonl
node exp-079-analyze.mjs $HARNESS /tmp/judged-samples.jsonl exp-079-derived-samples.jsonl \
  exp-079-skim-evidence.jsonl exp-079-analysis.json
node_modules/.bin/biome format --write exp-079-analysis.json   # the committed file is Biome's format
node $HARNESS/explorations/performance-loop/transitions.mjs compare /tmp/judged-samples.jsonl \
  --control control --candidate candidate --allow-mixed-landing
```

The judged samples are every row of
[exp-079-transition-samples.jsonl](exp-079-transition-samples.jsonl), since no pair was
excluded.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->

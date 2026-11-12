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
  date: "2026-11-12"
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
    corpus: Standalone clone of this repository at 7a02fed4 with its own refs, clean; nothing else commits to it, and its refs did not move during the series.
    corpus_files: 1286
    host_cpu: 10 CPUs
    host_system: Darwin 25.5.0 arm64, Node 24.19.0
    browser: Headless Chrome 152.0.7977.83 over the DevTools Protocol, a fresh profile per journey, trusted pointer and key input.
    viewport: 1440x900
    cold: false
  method:
    runs_per_condition: 6
    interleaved: false
    control: metab 0.12.1.dev165+9903292, the editable control checkout at origin/main 09903292, clean at the start and end of every run, one server process per run.
    candidate: No candidate. The results block is an A/A split of the same six runs, odd-numbered against even-numbered and paired in recorded order, which measures the instrument's resolution on this build.
    record: exp-058-transition-samples.jsonl
  results:
    - metric: painted_ready_ms.views.markdown.first
      control_median: 28.6
      candidate_median: 29.2
      control_range: [28.6, 30.5]
      candidate_range: [28.6, 30.6]
      overlapping: true
    - metric: painted_ready_ms.landing.reload
      control_median: 172.6
      candidate_median: 173.7
      control_range: [172.1, 172.6]
      candidate_range: [172.8, 174.6]
      overlapping: false
    - metric: painted_ready_ms.files.cold.image
      control_median: 77.8
      candidate_median: 79.9
      control_range: [63.4, 78.1]
      candidate_range: [78.9, 95.3]
      overlapping: false
    - metric: painted_ready_ms.commits.cold.1
      control_median: 113.2
      candidate_median: 163.5
      control_range: [112.8, 164.3]
      candidate_range: [113.4, 163.9]
      overlapping: true
    - metric: painted_ready_ms.main_subject.pulls_to_commits
      control_median: 229.6
      candidate_median: 212.2
      control_range: [229.1, 229.6]
      candidate_range: [178.8, 213.8]
      overlapping: false
    - metric: painted_ready_ms.files.revisit.source_large
      control_median: 92.9
      candidate_median: 80.4
      control_range: [79.8, 95.8]
      candidate_range: [79.6, 94.6]
      overlapping: true
    - metric: blank_frames.files.cold.image
      control_median: 1
      candidate_median: 2
      control_range: [1, 1]
      candidate_range: [2, 2]
      overlapping: false
    - metric: settled_ms.pulls.tab.checks_first
      control_median: 9.3
      candidate_median: 9.7
      control_range: [7.2, 9.6]
      candidate_range: [9.7, 24.4]
      overlapping: false
    - metric: region_movement_net_px.main.files_to_commits.again
      control_median: 37
      candidate_median: 37
      control_range: [37, 37]
      candidate_range: [37, 37]
      overlapping: true
    - metric: subject_duplicates.pulls.list_to_pr.cold
      control_median: 2
      candidate_median: 2
      control_range: [2, 2]
      candidate_range: [2, 2]
      overlapping: true
    - metric: subject_settlement_reads.pulls.pr_to_pr.revisit
      control_median: 2
      candidate_median: 2
      control_range: [2, 2]
      candidate_range: [2, 2]
      overlapping: true
  verdict:
    decision: baseline
    primary_metric: painted_ready_ms
    reason: Six valid runs of the control build on scenario revision 3 pass every guard on all 77 transitions. The tables below are the reference each campaign round and the campaign summary compare against. The A/A split found no painted-ready result; its five results are a one-frame difference in the image's blank frames, a settle time under 25 ms, and figures that are shown but not judged. It is a baseline, not a result about the product.
---
**Status:** Baseline, with one correction to its cache disposition counts (below).
Six valid runs of the control build on scenario revision 3, none refused.

## Correction, 2026-11-12

Review B on this round’s pull request found that revision 3, which recorded these rows,
read a 304 for a request a worker made as `network`. Chrome sends the raw status of a
dedicated worker’s request on the page’s session, and the recorder did not match it to
the worker’s request, so the request kept the cached 200 of its response event.
The record is corrected here, not rewritten: the samples, the tables, and the A/A
figures are left as recorded, since `byFamily` cannot be recomputed from the samples.

- In these six runs that is 108 requests: the Markdown worker’s two imports,
  `markdown-worker-operations.js` and `wiki-parser.js` (`plugin_static`), on nine
  transitions in every run.
  On `files.revisit.markdown_small`, `keyboard.up_revisit.1`,
  `main.commits_to_files.first` and `.again`, `main.pulls_to_files.first` and `.again`,
  `main_subject.pulls_to_files`, and `main_subject.commits_to_files` they are the whole
  `plugin_static` network count, 2 in every run, for requests that the server answered
  with 304 when review B reproduced the revisit on this build (the rows themselves do
  not hold the raw status); on `skim.held_arrow_down` they are 2 of its 3.
- `landing.reload`’s 2 `plugin_static` network requests in the Cache disposition table
  are very probably the same two; its request list is cut at 60 of 111 requests, so the
  rows cannot name them.
- The fields affected are `requests.byFamily.plugin_static` (`network` and
  `revalidated`), and through them the `plugin_static_network` and
  `plugin_static_revalidated` metrics.
  No other figure in this artifact reads them.

Revision 4 of the scenario reads these requests as `revalidated`. A round whose verdict
reads cache disposition uses that recorder with its own interleaved control, and does
not compare against these rows’ cache disposition counts.
`compare` refuses to mix revision 3 rows with revision 4 rows, so a later comparison
against this baseline as a whole needs it recorded again at revision 4. Revision 4 also
changes two readers that matter only for hidden or retained surfaces (a region’s first
rendered match, and the search for content past hidden text); their effect on these rows
was not measured.

The A/A figures below are `compare` at `5e368814`. At revision 4’s harness, on the same
samples, `compare` also lists 88 comparisons with one pair beyond the tolerance under
overlapping ranges, none a wrong-way result; the 33 separations, 5 results, 15 to
explain, 23 within the tolerance, and 5 reruns are unchanged, and it notes that the rows
are revision 3.

## Why This Round

The transition campaign (`mb-mpo0`) will land about twenty changes that make UI
transitions instant and remove layout shift, each measured as a round of this loop.
The committed `file-views` and `git-revisions` scenarios do not cover main-tab switches,
revisits, pull request pages, view-tab switches, or region movement.
This round adds the `transition-navigation/v1` scenario
([Transition Navigation Scenario](../README.md#transition-navigation-scenario)) and
records the numbers every later round compares against.
No product code changed.

## What Replaced the First Recording

The first recording of this baseline was scenario revision 1, from harness `f571f0ea`
and `047a41d9`, on a detached checkout that shared its refs with the main checkout.
Review A on its pull request found that its clocks and frame accounting decided verdicts
wrongly, and this recording replaces it entirely: none of its numbers compare with
these. Revision 3 changed what the numbers mean:

- Every frame is read after its own layout, so later DOM work no longer delays the
  credited frame. Painted ready is the ready frame’s presentation, the first frame
  boundary after its rendering ended, so a long task after the ready frame no longer
  counts; DOM work after it is settle time.
- Readiness counts only in a frame read after the input reached the page, and a ready
  predicate names the route, the active main tab, and a rendered surface.
- Useful content must be on screen: visible text, or an image once decoded.
- Blank and placeholder frames are counted over the whole window, and the prompt a main
  tab with nothing selected lands on is not blank.
- Region movement adds net displacement and path length, across replaced elements.
- A 304 the browser answered to its own cache is `revalidated`, not `network`.
- A read of a pull request that follows the page’s own refresh is a settlement read, not
  a duplicate.

`compare` now judges times on back-to-back pairs and reports every gap, and the series
refuses a moving corpus or build.

## Protocol

Declared before the measured series:

- Scenario: every journey of `transitions.mjs` at scenario revision 3, 11 journeys and
  77 transitions per run, from harness `dae89b6a`. Nothing on the run path (the
  recorder, the journeys, and `run`) changed after it.

- Series: six runs in one invocation, then the samples, the tables, and the A/A split:

  ```shell
  node explorations/performance-loop/transitions.mjs run --exp exp-058 \
    --corpus /path/to/standalone-clone --runs 6 \
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
  Each run started a fresh server on its own port (8890 to 8895), ran every journey once
  unrecorded, and then measured them, each journey in a fresh Chrome profile.
  All six runs shared one cache and configuration directory, which run 1 started empty,
  so its warm-up pass fetched the pull request catalog from GitHub.

- Load: no other measurement series was running when this one started.
  The one-minute load average was 3.23 to 6.67 at run starts and ends and 3.16 to 7.70
  when each transition started; the five-minute average was 4.17 to 5.59. Each run took
  457 to 480 s.

The tables in this artifact are the output of `summarize`, and the A/A figures the
output of `compare --aa`, both run on the committed
[samples](exp-058-transition-samples.jsonl).
Running them on the full local rows gives the same output, byte for byte.

## Identities

| Item | Value |
| --- | --- |
| Control build | `metab 0.12.1.dev165+9903292 (+165 commits, 099032928)`, editable checkout at `09903292`, clean at the start and end of every run |
| Corpus | Standalone clone at `7a02fed4` with its own refs, clean, 1,286 indexed files; commit, cleanliness, trunk, and the hash of every ref were the same at the start and end of every run |
| Trunk seen by Commits | `7a02fed4`, the head of the server’s first `git/log` page, in all six runs; the clone’s `origin/main` is `083e78e4`, an ancestor of it |
| Pull request catalog | Absent at run 1’s server start, before its warm-up fetched it; 358 in all, 18 open, 340 closed at runs 2 to 6 |
| Subjects in their lists | Every pull request and commit subject was mounted without scrolling, at the same offsets in every run: #353, #351, #349, and #348 at 344, 430, 473, and 516 px down the Closed list |
| Harness | `dae89b6a`, clean, in all six runs; scenario revision 3 |
| Chrome | 152.0.7977.83, headless |

## Guards

Every warm-up and measured pass of all six runs passed every guard, and no run’s build
or corpus moved between its start and its end.
Across the 462 measured transitions there were no page exceptions, no console errors,
and no rendered error, and none of their 26,421 frames went unread.

What makes each guard and definition fire is tested in
`tests/test_transitions_instrument.py`, on synthetic pages in headless Chrome and on
fixture rows, rather than by scratch scripts:

| Guard or definition | What the test does |
| --- | --- |
| `ready_before_input` | The subject is already on screen when the click is armed. |
| Settle time, not readiness | The page keeps changing the DOM for 600 ms after the subject shows, in a rAF loop and in a task loop. |
| Painted ready | A 300 ms task runs after the ready frame, and a ready frame takes hundreds of milliseconds to lay out; both are checked against Chrome’s Event Timing presentation time for the click. |
| Blank and placeholder frames | Content, then a visible placeholder, then content again, after ready; and a declared prompt. |
| Useful content | An image whose bytes arrive 700 ms later, and text at zero opacity, hidden, or clipped by a collapsed parent. |
| Region movement | A 37 px move over two frames, and a pull request page replaced after a gap by one whose header is 66 px taller. |
| `input_observed` | The page dispatches its own untrusted `pointerdown` first; a held key’s first `keyDown` is not a repeat. |
| Cache disposition | A server that logs its 304s answers a `no-cache` file, a `max-age` file, and the page’s own conditional request. |
| `compare` | Every refusal and verdict, on fixture rows. |
| Process cleanup | A stand-in server that fails after it starts, twice, and a Chrome that cannot start. |

## Baseline

Painted ready is measured from the input event to the ready frame’s presentation, the
first frame boundary after the main-thread rendering of the first frame that showed the
exact subject with useful content; ready read is that frame’s post-layout read.
Times are whole milliseconds, median and range over six runs.
Frame counts cover the whole window, from the input to the end of the transition’s
settle time; a count is one value when every run agreed, else median and range.
A main tab with nothing selected lands on its prompt by design, and its prompt frames
are not blank.

### Time and frames

| Transition | Painted ready ms, median (range) | Ready read ms | Blank frames | Blank after ready | Visible placeholder frames | Nav placeholder frames | Preview settled ms | Longest task ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `landing.cold_markdown` | 275 (266–281) | 267 (259–270) | 11.5 (11–12) | 0 | 8 (7–9) | 0 | 276 (269–277) | 0 (0–0) |
| `landing.reload` | 173 (172–175) | 160 (157–165) | 7.5 (7–8) | 0 | 3 (2–4) | 0 | 168 (160–177) | 0 (0–0) |
| `files.cold.markdown_large` | 180 (179–181) | 170 (165–173) | 0 | 0 | 0 | 0 | 182 (177–184) | 61 (59–63) |
| `files.cold.markdown_mid` | 64 (63–65) | 52 (51–54) | 0 | 0 | 0 | 0 | 57 (54–58) | 0 (0–0) |
| `files.cold.source_large` | 113 (112–114) | 97 (93–100) | 0 | 0 | 0 | 0 | 303 (294–306) | 116 (107–127) |
| `files.cold.source_small` | 48 (46–63) | 38 (36–51) | 0 | 0 | 0 | 0 | 53 (50–67) | 0 (0–0) |
| `files.cold.json` | 64 (63–81) | 58 (56–70) | 0 | 0 | 0 | 0 | 65 (62–77) | 0 (0–0) |
| `files.cold.diff` | 80 (77–95) | 73 (72–87) | 0 | 0 | 0 | 0 | 106 (98–114) | 0 (0–0) |
| `files.cold.image` | 79 (63–95) | 65 (49–82) | 1.5 (1–2) | 0 | 0 | 0 | 57 (46–64) | 0 (0–0) |
| `files.cold.binary` | 64 (63–65) | 55 (54–56) | 0 | 0 | 0 | 0 | 63 (62–64) | 0 (0–0) |
| `files.revisit.source_large` | 87 (80–96) | 72 (67–82) | 0 | 0 | 0 | 0 | 195 (187–206) | 127 (107–143) |
| `files.revisit.json` | 64 (63–65) | 57 (56–58) | 0 | 0 | 0 | 0 | 63 (62–64) | 0 (0–0) |
| `files.revisit.markdown_small` | 63 (60–78) | 56 (54–61) | 0 | 0 | 0 | 0 | 65 (61–67) | 0 (0–0) |
| `files.revisit.markdown_large` | 146 (144–147) | 136 (133–138) | 0 | 0 | 0 | 0 | 142 (139–143) | 0 (0–0) |
| `files.history_back` | 41 (37–42) | 35 (32–38) | 0 | 0 | 0 | 0 | 43 (39–44) | 0 (0–0) |
| `files.history_forward` | 122 (118–138) | 115 (113–123) | 0 | 0 | 0 | 0 | 120 (118–129) | 0 (0–0) |
| `files.hover_click.markdown` | 64 (63–65) | 59 (58–60) | 0 | 0 | 0 | 0 | 64 (63–65) | 0 (0–0) |
| `keyboard.down_cold.1` | 54 (53–55) | 41 (40–43) | 0 | 0 | 0 | 0 | 55 (54–57) | 0 (0–0) |
| `keyboard.down_cold.2` | 56 (50–58) | 41 (35–44) | 0 | 0 | 0 | 0 | 58 (51–59) | 0 (0–0) |
| `keyboard.down_cold.3` | 42 (41–54) | 33 (30–45) | 0 | 0 | 0 | 0 | 48 (46–58) | 0 (0–0) |
| `keyboard.up_revisit.1` | 48 (41–58) | 34 (27–43) | 0 | 0 | 0 | 0 | 50 (41–59) | 0 (0–0) |
| `keyboard.up_revisit.2` | 44 (42–46) | 29 (28–32) | 0 | 0 | 0 | 0 | 45 (44–47) | 0 (0–0) |
| `views.markdown.first` | 29 (29–31) | 15 (14–16) | 0 | 0 | 0 | 0 | 24 (22–25) | 0 (0–0) |
| `views.markdown.revisit` | 30 (28–32) | 15 (15–18) | 0 | 0 | 0 | 0 | 2 (2–3) | 0 (0–0) |
| `views.markdown.revisit_2` | 30 (29–31) | 15 (14–17) | 0 | 0 | 0 | 0 | 3 (2–3) | 0 (0–0) |
| `views.json.first` | 29 (28–30) | 21 (21–24) | 0 | 0 | 0 | 0 | 39 (36–42) | 0 (0–0) |
| `views.json.revisit` | 30 (30–45) | 28 (23–30) | 0 | 0 | 0 | 0 | 4 (3–5) | 0 (0–0) |
| `views.json.revisit_2` | 31 (29–32) | 18 (18–22) | 0 | 0 | 0 | 0 | 3 (3–4) | 0 (0–0) |
| `views.folder.first` | 47 (47–48) | 39 (38–40) | 0 | 0 | 0 | 0 | 20 (19–21) | 0 (0–0) |
| `views.folder.revisit` | 30 (29–31) | 15 (13–16) | 0 | 0 | 0 | 0 | 15 (13–16) | 0 (0–0) |
| `views.folder.revisit_2` | 31 (31–32) | 18 (16–19) | 0 | 0 | 0 | 0 | 20 (18–21) | 0 (0–0) |
| `main.files_to_commits.first` | 228 (227–245) | 224 (222–238) | 0 | 0 | 0 | 0 | 10 (7–10) | 0 (0–0) |
| `main.commits_to_files.first` | 78 (63–79) | 62 (57–64) | 2 | 0 | 0 | 0 | 64 (59–66) | 0 (0–0) |
| `main.files_to_commits.again` | 28 (28–30) | 19 (14–20) | 0 | 0 | 0 | 0 | 17 (12–18) | 0 (0–0) |
| `main.commits_to_files.again` | 62 (62–65) | 55 (55–60) | 2 | 0 | 0 | 0 | 58 (57–62) | 0 (0–0) |
| `main.files_to_pulls.first` | 29 (28–30) | 20 (15–21) | 0 | 0 | 0 | 0 | 18 (11–19) | 0 (0–0) |
| `main.pulls_to_files.first` | 63 (63–65) | 60 (55–60) | 2 | 0 | 0 | 0 | 62 (57–62) | 0 (0–0) |
| `main.files_to_pulls.again` | 30 (28–31) | 16 (14–17) | 0 | 0 | 0 | 0 | 8 (6–12) | 0 (0–0) |
| `main.pulls_to_commits` | 30 (28–32) | 15 (14–16) | 0 | 0 | 0 | 0 | 9 (8–10) | 0 (0–0) |
| `main.commits_to_pulls` | 30 (29–31) | 14 (14–16) | 0 | 0 | 0 | 0 | 9 (6–10) | 0 (0–0) |
| `main.pulls_to_files.again` | 64 (63–65) | 59 (57–60) | 2 | 0 | 0 | 0 | 61 (59–63) | 0 (0–0) |
| `main_subject.files_to_commits` | 214 (165–230) | 210 (159–215) | 0 | 0 | 0 | 0 | 215 (214–228) | 0 (0–0) |
| `main_subject.commits_to_pulls` | 78 (63–81) | 67 (49–71) | 0 | 0 | 0 | 0 | 565 (552–574) | 0 (0–0) |
| `main_subject.pulls_to_files` | 65 (63–65) | 59 (58–61) | 0 | 0 | 0 | 0 | 67 (64–67) | 0 (0–0) |
| `main_subject.files_to_pulls` | 64 (64–65) | 50 (48–54) | 0 | 0 | 0 | 0 | 72 (69–1044) | 0 (0–0) |
| `main_subject.pulls_to_commits` | 221 (179–230) | 213 (171–217) | 0 | 0 | 0 | 0 | 219 (205–222) | 0 (0–0) |
| `main_subject.commits_to_files` | 71 (62–80) | 61 (56–66) | 0 | 0 | 0 | 0 | 66 (64–68) | 0 (0–0) |
| `commits.first_show` | 269 (262–278) | 264 (257–271) | 0 | 0 | 0 | 0 | 6 (5–10) | 0 (0–0) |
| `commits.cold.1` | 138 (113–164) | 134 (109–162) | 5 | 0 | 2 | 0 | 169 (162–176) | 53 (0–56) |
| `commits.cold.2` | 180 (162–212) | 172 (156–205) | 0 | 0 | 0 | 0 | 206 (190–208) | 0 (0–0) |
| `commits.cold.3` | 145 (112–158) | 136 (108–146) | 0 | 0 | 0 | 0 | 149 (136–163) | 0 (0–0) |
| `commits.revisit.1` | 122 (97–148) | 111 (90–136) | 0 | 0 | 0 | 0 | 140 (135–142) | 0 (0–0) |
| `commits.revisit.2` | 164 (147–197) | 155 (137–183) | 0 | 0 | 0 | 0 | 185 (173–189) | 0 (0–0) |
| `commits.hover_click` | 31 (31–32) | 16 (15–18) | 0 | 0 | 0 | 0 | 34 (32–35) | 0 (0–0) |
| `pulls.first_show` | 29 (27–31) | 19 (14–22) | 0 | 0 | 0 | 0 | 17 (10–19) | 0 (0–0) |
| `pulls.list_to_pr.cold` | 65 (62–68) | 52 (50–58) | 1 (1–2) | 0 | 0 | 0 | 80 (77–90) | 0 (0–0) |
| `pulls.tab.changes_first` | 51 (42–58) | 42 (33–53) | 0 | 0 | 0 | 0 | 92 (83–100) | 0 (0–0) |
| `pulls.tab.checks_first` | 29 (28–47) | 14 (13–31) | 0 | 0 | 0 | 0 | 10 (7–24) | 0 (0–0) |
| `pulls.tab.conversation_revisit` | 29 (28–30) | 17 (15–19) | 0 | 0 | 0 | 0 | 11 (10–13) | 0 (0–0) |
| `pulls.tab.changes_revisit` | 43 (42–44) | 33 (32–34) | 0 | 0 | 0 | 0 | 58 (57–59) | 0 (0–0) |
| `pulls.tab.conversation_revisit_2` | 36 (26–44) | 27 (14–30) | 0 | 0 | 0 | 0 | 20 (11–23) | 0 (0–0) |
| `pulls.pr_to_pr.cold` | 43 (41–46) | 33 (29–35) | 0 | 0 | 0 | 0 | 71 (66–82) | 0 (0–0) |
| `pulls.pr_to_pr.revisit` | 27 (25–46) | 13 (12–32) | 0 | 0 | 0 | 0 | 1085 (1078–1098) | 0 (0–0) |
| `pulls.pr_to_pr.hover_click` | 47 (46–49) | 37 (35–40) | 0 | 0 | 0 | 0 | 64 (61–78) | 0 (0–0) |
| `pulls.tab.changes_first_2` | 42 (41–60) | 41 (38–55) | 0 | 0 | 0 | 0 | 82 (76–105) | 0 (0–0) |
| `pulls.history_back` | 47 (38–54) | 35 (30–43) | 0 | 0 | 0 | 0 | 32 (27–39) | 0 (0–0) |
| `pulls.tab.changes_revisit_2` | 45 (43–45) | 38 (37–43) | 0 | 0 | 0 | 0 | 74 (70–86) | 0 (0–0) |
| `pulls.pr_changes_to_pr` | 62 (58–62) | 54 (50–58) | 0 | 0 | 0 | 0 | 79 (74–93) | 0 (0–0) |
| `tree.expand.docs` | 78 (64–79) | 64 (54–65) | 0 | 0 | 0 | 0 | 64 (63–66) | 0 (0–0) |
| `tree.expand.src` | 46 (42–47) | 34 (30–34) | 0 | 0 | 0 | 0 | 47 (44–49) | 0 (0–0) |
| `tree.collapse.src` | 31 (30–32) | 16 (15–18) | 0 | 0 | 0 | 0 | 0 (0–0) | 0 (0–0) |
| `tree.reexpand.src` | 30 (29–31) | 15 (13–16) | 0 | 0 | 0 | 0 | 0 (0–0) | 0 (0–0) |
| `tree.expand_nested.src_metabrowser` | 47 (45–48) | 36 (33–36) | 0 | 0 | 0 | 0 | 48 (45–50) | 0 (0–0) |
| `palette.open` | 23 (19–33) | 16 (13–20) | 0 | 0 | 0 | 0 | 0 (0–0) | 0 (0–0) |
| `palette.query` | 190 (178–193) | 181 (175–185) | 0 | 0 | 0 | 0 | 0 (0–0) | 0 (0–0) |
| `skim.held_arrow_down` | 380 (373–389) | 376 (368–384) | 0 | 0 | 0 | 0 | 382 (374–390) | 0 (0–0) |
| `reveal.deep_landing` | 201 (184–203) | 192 (178–197) | 7.5 (7–9) | 0 | 4 (4–6) | 0 (0–1) | 200 (192–210) | 0 (0–0) |

### Requests

| Transition | Data | Plugin modules | Static | KPress | Background | Subject duplicates | Settlement reads |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `landing.cold_markdown` | 17 | 29 | 41 | 18 | 1 | 0 | 0 |
| `landing.reload` | 20 | 29 | 41 | 18 | 1 | 0 | 0 |
| `files.cold.markdown_large` | 1 | 0 | 0 | 3 | 2 | 0 | 0 |
| `files.cold.markdown_mid` | 1 | 0 | 0 | 1 | 0–2 | 0 | 0 |
| `files.cold.source_large` | 1 | 1 | 0 | 0 | 1–2 | 0 | 0 |
| `files.cold.source_small` | 1 | 0 | 0 | 0 | 2 | 0 | 0 |
| `files.cold.json` | 2 | 4 | 0 | 0 | 0 | 0 | 0 |
| `files.cold.diff` | 3 | 7 | 0 | 0 | 0–2 | 0 | 0 |
| `files.cold.image` | 1 | 2 | 0 | 0 | 2 | 0 | 0 |
| `files.cold.binary` | 1 | 0 | 0 | 0 | 0 | 0 | 0 |
| `files.revisit.source_large` | 0 | 0 | 0 | 0 | 2 | 0 | 0 |
| `files.revisit.json` | 1 | 0 | 0 | 0 | 1–2 | 0 | 0 |
| `files.revisit.markdown_small` | 0 | 3 | 0 | 1 | 0 | 0 | 0 |
| `files.revisit.markdown_large` | 0 | 0 | 0 | 1 | 2 | 0 | 0 |
| `files.history_back` | 0 | 0 | 0 | 1 | 2 | 0 | 0 |
| `files.history_forward` | 0 | 0 | 0 | 1 | 2 | 0 | 0 |
| `files.hover_click.markdown` | 1 | 0 | 0 | 1 | 2 | 0 | 0 |
| `keyboard.down_cold.1` | 1 | 0 | 0 | 1 | 0–2 | 0 | 0 |
| `keyboard.down_cold.2` | 1 | 0 | 0 | 1 | 2 | 0 | 0 |
| `keyboard.down_cold.3` | 1 | 1 | 0 | 0 | 2 | 0 | 0 |
| `keyboard.up_revisit.1` | 0 | 3 | 0 | 1 | 0–2 | 0 | 0 |
| `keyboard.up_revisit.2` | 0 | 0 | 0 | 1 | 0 | 0 | 0 |
| `views.markdown.first` | 0 | 0 | 0 | 0 | 1 | 0 | 0 |
| `views.markdown.revisit` | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `views.markdown.revisit_2` | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `views.json.first` | 0 | 0 | 0 | 0 | 2 | 0 | 0 |
| `views.json.revisit` | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `views.json.revisit_2` | 0 | 0 | 0 | 0 | 0–2 | 0 | 0 |
| `views.folder.first` | 1 | 0 | 0 | 0 | 2 | 0 | 0 |
| `views.folder.revisit` | 0 | 0 | 0 | 0 | 2 | 0 | 0 |
| `views.folder.revisit_2` | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `main.files_to_commits.first` | 4 | 0 | 0 | 0 | 1 | 0 | 0 |
| `main.commits_to_files.first` | 0–1 | 3 | 0 | 1 | 2 | 0 | 0 |
| `main.files_to_commits.again` | 1 | 0 | 0 | 0 | 2 | 0 | 0 |
| `main.commits_to_files.again` | 0 | 3 | 0 | 1 | 0 | 0 | 0 |
| `main.files_to_pulls.first` | 4–6 | 0 | 0 | 0 | 2 | 0 | 0 |
| `main.pulls_to_files.first` | 0 | 3 | 0 | 1 | 0 | 0 | 0 |
| `main.files_to_pulls.again` | 2 | 0 | 0 | 0 | 1 | 0 | 0 |
| `main.pulls_to_commits` | 1 | 0 | 0 | 0 | 0 | 0 | 0 |
| `main.commits_to_pulls` | 2 | 0 | 0 | 0 | 1 | 0 | 0 |
| `main.pulls_to_files.again` | 0 | 3 | 0 | 1 | 0 | 0 | 0 |
| `main_subject.files_to_commits` | 2 | 0 | 0 | 0 | 2 | 0 | 0 |
| `main_subject.commits_to_pulls` | 13 | 0 | 0 | 0 | 6 | 0 | 0 |
| `main_subject.pulls_to_files` | 0 | 3 | 0 | 1 | 0–2 | 0 | 0 |
| `main_subject.files_to_pulls` | 11–12 | 0 | 0 | 0 | 3 | 0–1 | 0 |
| `main_subject.pulls_to_commits` | 2 | 0 | 0 | 0 | 1–3 | 0 | 0 |
| `main_subject.commits_to_files` | 0 | 3 | 0 | 1 | 2 | 0 | 0 |
| `commits.first_show` | 4 | 0 | 0 | 0 | 1 | 0 | 0 |
| `commits.cold.1` | 2 | 7 | 0 | 0 | 0–2 | 0 | 0 |
| `commits.cold.2` | 2 | 0 | 0 | 0 | 2 | 0 | 0 |
| `commits.cold.3` | 2 | 0 | 0 | 0 | 2 | 0 | 0 |
| `commits.revisit.1` | 1 | 0 | 0 | 0 | 2 | 0 | 0 |
| `commits.revisit.2` | 1 | 0 | 0 | 0 | 2 | 0 | 0 |
| `commits.hover_click` | 2 | 0 | 0 | 0 | 4 | 0 | 0 |
| `pulls.first_show` | 4–6 | 0 | 0 | 0 | 2 | 0 | 0 |
| `pulls.list_to_pr.cold` | 14 | 8 | 1 | 1 | 5 | 2 | 0 |
| `pulls.tab.changes_first` | 4 | 1 | 1 | 0 | 5–6 | 0 | 0 |
| `pulls.tab.checks_first` | 0 | 0 | 0 | 0 | 2 | 0 | 0 |
| `pulls.tab.conversation_revisit` | 0 | 0 | 0 | 0 | 2 | 0 | 0 |
| `pulls.tab.changes_revisit` | 5 | 0 | 0 | 0 | 2 | 0 | 0 |
| `pulls.tab.conversation_revisit_2` | 0 | 0 | 0 | 0 | 2 | 0 | 0 |
| `pulls.pr_to_pr.cold` | 13–16 | 0 | 0 | 0 | 6 | 2 | 0 |
| `pulls.pr_to_pr.revisit` | 14 | 0 | 0 | 0 | 4 | 0 | 2 |
| `pulls.pr_to_pr.hover_click` | 14–15 | 0 | 0 | 0 | 5 | 1 | 0 |
| `pulls.tab.changes_first_2` | 3–6 | 0 | 0 | 0 | 6 | 0 | 0 |
| `pulls.history_back` | 0 | 0 | 0 | 0 | 4–5 | 0 | 0 |
| `pulls.tab.changes_revisit_2` | 6–7 | 0 | 0 | 0 | 3–4 | 0 | 0 |
| `pulls.pr_changes_to_pr` | 15 | 0 | 0 | 0 | 6–9 | 2 | 0 |
| `tree.expand.docs` | 5–6 | 19 | 0 | 1 | 1 | 0 | 0 |
| `tree.expand.src` | 2 | 0 | 0 | 0 | 2 | 0 | 0 |
| `tree.collapse.src` | 0 | 0 | 0 | 0 | 1–2 | 0 | 0 |
| `tree.reexpand.src` | 0 | 0 | 0 | 0 | 2 | 0 | 0 |
| `tree.expand_nested.src_metabrowser` | 12 | 0 | 0 | 0 | 2 | 0 | 0 |
| `palette.open` | 0 | 0 | 0 | 0 | 1–2 | 0 | 0 |
| `palette.query` | 1 | 0 | 0 | 0 | 4 | 0 | 0 |
| `skim.held_arrow_down` | 6 | 4 | 0 | 6 | 4 | 0 | 0 |
| `reveal.deep_landing` | 23–32 | 11 | 41 | 2–3 | 1 | 0 | 0 |

### Stability and DOM

| Transition | Preview top nodes replaced | Layout shifts | Shift without input | Largest step px | Net px | Path px | DOM nodes after |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `landing.cold_markdown` | 4 | 2 | 0.0033 | 0 | 0 | 0 | 2296 |
| `landing.reload` | 4 | 1 | 0.0002 | 0 | 0 | 0 | 2296 |
| `files.cold.markdown_large` | 5 | 0 | 0.0000 | 0 | 0 | 0 | 8637 |
| `files.cold.markdown_mid` | 5 | 0 | 0.0000 | 0 | 0 | 0 | 6519 |
| `files.cold.source_large` | 5 | 0 | 0.0000 | 30 | 30 | 30 | 18872 |
| `files.cold.source_small` | 3 | 0 | 0.0000 | 0 | 0 | 0 | 6219 |
| `files.cold.json` | 3 | 0 | 0.0000 | 30 | 30 | 30 | 10241 |
| `files.cold.diff` | 5 | 7 | 0.0000 | 30 | 30 | 30 | 6619 |
| `files.cold.image` | 3 | 0 | 0.0000 | 11 | 11 | 11 | 5953 |
| `files.cold.binary` | 3 | 0 | 0.0000 | 11 | 11 | 11 | 5963 |
| `files.revisit.source_large` | 3 | 0 | 0.0000 | 0 | 0 | 0 | 18895 |
| `files.revisit.json` | 3 | 0 | 0.0000 | 30 | 30 | 30 | 10260 |
| `files.revisit.markdown_small` | 5 | 0 | 0.0000 | 0 | 0 | 0 | 6419 |
| `files.revisit.markdown_large` | 5 | 0 | 0.0000 | 0 | 0 | 0 | 8661 |
| `files.history_back` | 5 | 0 | 0.0000 | 0 | 0 | 0 | 6419 |
| `files.history_forward` | 5 | 0 | 0.0000 | 0 | 0 | 0 | 8661 |
| `files.hover_click.markdown` | 5 | 0 | 0.0000 | 0 | 0 | 0 | 7057 |
| `keyboard.down_cold.1` | 5 | 0 | 0.0000 | 11 | 11 | 11 | 1907 |
| `keyboard.down_cold.2` | 5 | 0 | 0.0000 | 11 | 11 | 11 | 1953 |
| `keyboard.down_cold.3` | 5 | 0 | 0.0000 | 30 | 30 | 30 | 1836 |
| `keyboard.up_revisit.1` | 3 | 0 | 0.0000 | 30 | 30 | 30 | 1954 |
| `keyboard.up_revisit.2` | 5 | 0 | 0.0000 | 11 | 11 | 11 | 1908 |
| `views.markdown.first` | 0 | 0 | 0.0000 | 0 | 0 | 0 | 2518 |
| `views.markdown.revisit` | 0 | 0 | 0.0000 | 0 | 0 | 0 | 2518 |
| `views.markdown.revisit_2` | 0 | 0 | 0.0000 | 0 | 0 | 0 | 2518 |
| `views.json.first` | 0 | 1 | 0.0000 | 0 | 0 | 0 | 9759 |
| `views.json.revisit` | 0 | 1 | 0.0000 | 0 | 0 | 0 | 9759 |
| `views.json.revisit_2` | 0 | 1 | 0.0000 | 0 | 0 | 0 | 9759 |
| `views.folder.first` | 0 | 0 | 0.0000 | 0 | 0 | 0 | 2418 |
| `views.folder.revisit` | 0 | 0 | 0.0000 | 0 | 0 | 0 | 2232 |
| `views.folder.revisit_2` | 0 | 2 | 0.0000 | 0 | 0 | 0 | 2418 |
| `main.files_to_commits.first` | 4 | 1 | 0.0000 | 37 | 37 | 37 | 3732 |
| `main.commits_to_files.first` | 2 | 1 | 0.0000 | 37 | 37 | 37 | 4341 |
| `main.files_to_commits.again` | 4 | 1 | 0.0000 | 37 | 37 | 37 | 3732 |
| `main.commits_to_files.again` | 2 | 1 | 0.0000 | 37 | 37 | 37 | 4341 |
| `main.files_to_pulls.first` | 4 | 2 | 0.0000 | 37 | 37 | 37 | 3796 |
| `main.pulls_to_files.first` | 2 | 1 | 0.0000 | 37 | 37 | 37 | 4404 |
| `main.files_to_pulls.again` | 4 | 1 | 0.0000 | 37 | 37 | 37 | 3796 |
| `main.pulls_to_commits` | 1 | 0 | 0.0000 | 0 | 0 | 0 | 3795 |
| `main.commits_to_pulls` | 1 | 0 | 0.0000 | 0 | 0 | 0 | 3796 |
| `main.pulls_to_files.again` | 2 | 1 | 0.0000 | 37 | 37 | 37 | 4404 |
| `main_subject.files_to_commits` | 5 | 1 | 0.0000 | 37 | 37 | 37 | 6273 |
| `main_subject.commits_to_pulls` | 2 | 0 | 0.0000 | 0 | 0 | 0 | 5429 |
| `main_subject.pulls_to_files` | 2 | 1 | 0.0000 | 37 | 37 | 37 | 5750 |
| `main_subject.files_to_pulls` | 5 | 1 | 0.0000 | 37 | 37 | 37 | 5429 |
| `main_subject.pulls_to_commits` | 2 | 0 | 0.0000 | 0 | 0 | 0 | 6273 |
| `main_subject.commits_to_files` | 2 | 1 | 0.0000 | 37 | 37 | 37 | 5750 |
| `commits.first_show` | 4 | 1 | 0.0000 | 37 | 37 | 37 | 3515 |
| `commits.cold.1` | 3 | 0 | 0.0000 | 0 | 0 | 0 | 4671 |
| `commits.cold.2` | 2 | 0 | 0.0000 | 0 | 0 | 0 | 4713 |
| `commits.cold.3` | 2 | 0 | 0.0000 | 0 | 0 | 0 | 5119 |
| `commits.revisit.1` | 2 | 0 | 0.0000 | 0 | 0 | 0 | 4671 |
| `commits.revisit.2` | 2 | 0 | 0.0000 | 0 | 0 | 0 | 4713 |
| `commits.hover_click` | 2 | 0 | 0.0000 | 0 | 0 | 0 | 3820 |
| `pulls.first_show` | 4 | 2 | 0.0000 | 37 | 37 | 37 | 1875 |
| `pulls.list_to_pr.cold` | 1 | 2 | 0.0000 | 0 | 0 | 0 | 3508 |
| `pulls.tab.changes_first` | 0 | 3–4 | 0.0000 | 8 | 8 | 8 | 5944 |
| `pulls.tab.checks_first` | 0 | 1 | 0.0000 | 8 | 8 | 8 | 3332 |
| `pulls.tab.conversation_revisit` | 0 | 0 | 0.0000 | 0 | 0 | 0 | 3508 |
| `pulls.tab.changes_revisit` | 0 | 2 | 0.0000 | 8 | 8 | 8 | 5779 |
| `pulls.tab.conversation_revisit_2` | 0 | 1 | 0.0000 | 8 | 8 | 8 | 3508 |
| `pulls.pr_to_pr.cold` | 2 | 0 | 0.0000 | 0 | 0 | 0 | 4063 |
| `pulls.pr_to_pr.revisit` | 2 | 8 | 0.0000 | 0 | 0 | 0 | 3809 |
| `pulls.pr_to_pr.hover_click` | 2 | 1 | 0.0000 | 0 | 0 | 0 | 4543 |
| `pulls.tab.changes_first_2` | 0 | 2 | 0.0000 | 8 | 8 | 8 | 5851 |
| `pulls.history_back` | 0 | 1 | 0.0000 | 8 | 8 | 8 | 4202 |
| `pulls.tab.changes_revisit_2` | 0 | 2 | 0.0000 | 8 | 8 | 8 | 5851 |
| `pulls.pr_changes_to_pr` | 2 | 0 | 0.0000 | 8 | 8 | 8 | 4892 |
| `tree.expand.docs` | 5 | 8 | 0.0000 | 11 | 11 | 11 | 2177 |
| `tree.expand.src` | 5 | 3 | 0.0000 | 0 | 0 | 0 | 2326 |
| `tree.collapse.src` | 0 | 3 | 0.0000 | 0 | 0 | 0 | 2331 |
| `tree.reexpand.src` | 0 | 3 | 0.0000 | 0 | 0 | 0 | 2331 |
| `tree.expand_nested.src_metabrowser` | 5 | 1 | 0.0000 | 0 | 0 | 0 | 3124 |
| `palette.open` | 0 | 0 | 0.0000 | 0 | 0 | 0 | 2311 |
| `palette.query` | 0 | 1 | 0.0000 | 0 | 0 | 0 | 3513 |
| `skim.held_arrow_down` | 26 | 0 | 0.0000 | 30 | 0 | 60 | 2297 |
| `reveal.deep_landing` | 4 | 3–4 | 0.0530–0.0608 | 0 | 0 | 0 | 3450 |

### Milestones

| Transition | Shell tools ready ms | Styled Markdown ms | PR header ms | PR description shown ms | PR description final ms |
| --- | ---: | ---: | ---: | ---: | ---: |
| `landing.cold_markdown` | 257 (242–275) | 275 (266–281) | n/a | n/a | n/a |
| `landing.reload` | 149 (140–173) | 173 (172–175) | n/a | n/a | n/a |
| `main_subject.commits_to_pulls` | n/a | n/a | 78 (63–81) | 78 (63–81) | 79 (63–81) |
| `main_subject.files_to_pulls` | n/a | n/a | 64 (64–65) | 64 (64–65) | 73 (64–81) |
| `pulls.list_to_pr.cold` | n/a | n/a | 65 (62–68) | 65 (62–68) | 82 (79–84) |
| `pulls.tab.changes_first` | n/a | n/a | 26 (24–42) | n/a | n/a |
| `pulls.tab.checks_first` | n/a | n/a | 29 (28–30) | n/a | n/a |
| `pulls.tab.conversation_revisit` | n/a | n/a | 29 (28–30) | 29 (28–30) | 29 (28–30) |
| `pulls.tab.changes_revisit` | n/a | n/a | 27 (25–27) | n/a | n/a |
| `pulls.tab.conversation_revisit_2` | n/a | n/a | 36 (26–44) | 36 (26–44) | 36 (26–44) |
| `pulls.pr_to_pr.cold` | n/a | n/a | 43 (41–46) | 43 (41–46) | 60 (58–62) |
| `pulls.pr_to_pr.revisit` | n/a | n/a | 27 (25–46) | 27 (25–46) | 44 (42–63) |
| `pulls.pr_to_pr.hover_click` | n/a | n/a | 47 (46–49) | 47 (46–49) | 64 (63–65) |
| `pulls.tab.changes_first_2` | n/a | n/a | 25 (20–43) | n/a | n/a |
| `pulls.history_back` | n/a | n/a | 47 (38–54) | 47 (38–54) | 47 (38–54) |
| `pulls.tab.changes_revisit_2` | n/a | n/a | 28 (26–29) | n/a | n/a |
| `pulls.pr_changes_to_pr` | n/a | n/a | 62 (58–62) | 62 (58–62) | 85 (78–96) |

### Input, lists, and groups

| Transition | Input span ms | Ready after last input ms | File envelopes | POST body bytes | List rows replaced below selection | List row replacements | Tree step px | Tree net px | Tree path px | Tree movement frames | Palette step px |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `landing.cold_markdown` | 0 (0–0) | 275 (266–281) | 1 | 19168 | n/a | n/a | 0 | 0 | 0 | 0 | 0 |
| `landing.reload` | 0 (0–0) | 173 (172–175) | 1 | 19168 | n/a | n/a | 0 | 0 | 0 | 0 | 0 |
| `files.cold.markdown_large` | 0 (0–0) | 180 (179–181) | 1 | 191142 | n/a | n/a | 0 | 0 | 0 | 0 | 0 |
| `files.cold.markdown_mid` | 0 (0–0) | 64 (63–65) | 1 | 42904 | n/a | n/a | 0 | 0 | 0 | 0 | 0 |
| `files.revisit.markdown_small` | 0 (0–0) | 63 (60–78) | 0 | 19168 | n/a | n/a | 0 | 0 | 0 | 0 | 0 |
| `files.revisit.markdown_large` | 0 (0–0) | 146 (144–147) | 0 | 191142 | n/a | n/a | 0 | 0 | 0 | 0 | 0 |
| `files.history_back` | 0 (0–0) | 41 (37–42) | 0 | 19168 | n/a | n/a | 0 | 0 | 0 | 0 | 0 |
| `files.history_forward` | 0 (0–0) | 122 (118–138) | 0 | 191142 | n/a | n/a | 0 | 0 | 0 | 0 | 0 |
| `files.hover_click.markdown` | 0 (0–0) | 64 (63–65) | 1 | 59712 | n/a | n/a | 0 | 0 | 0 | 0 | 0 |
| `keyboard.down_cold.2` | 0 (0–0) | 56 (50–58) | 1 | 3105 | n/a | n/a | 0 | 0 | 0 | 0 | 0 |
| `keyboard.up_revisit.1` | 0 (0–0) | 48 (41–58) | 0 | 3105 | n/a | n/a | 0 | 0 | 0 | 0 | 0 |
| `main.commits_to_files.first` | 0 (0–0) | 78 (63–79) | 0–1 | 42904 | n/a | n/a | 0 | 0 | 0 | 0 | 0 |
| `main.commits_to_files.again` | 0 (0–0) | 62 (62–65) | 0 | 42904 | n/a | n/a | 0 | 0 | 0 | 0 | 0 |
| `main.files_to_pulls.first` | 0 (0–0) | 29 (28–30) | 0 | 62–64 | n/a | n/a | 0 | 0 | 0 | 0 | 0 |
| `main.pulls_to_files.first` | 0 (0–0) | 63 (63–65) | 0 | 42904 | n/a | n/a | 0 | 0 | 0 | 0 | 0 |
| `main.pulls_to_files.again` | 0 (0–0) | 64 (63–65) | 0 | 42904 | n/a | n/a | 0 | 0 | 0 | 0 | 0 |
| `main_subject.commits_to_pulls` | 0 (0–0) | 78 (63–81) | 0 | 132 | n/a | n/a | 0 | 0 | 0 | 0 | 0 |
| `main_subject.pulls_to_files` | 0 (0–0) | 65 (63–65) | 0 | 42904 | n/a | n/a | 0 | 0 | 0 | 0 | 0 |
| `main_subject.files_to_pulls` | 0 (0–0) | 64 (64–65) | 0 | 99–118 | n/a | n/a | 0 | 0 | 0 | 0 | 0 |
| `main_subject.commits_to_files` | 0 (0–0) | 71 (62–80) | 0 | 42904 | n/a | n/a | 0 | 0 | 0 | 0 | 0 |
| `pulls.first_show` | 0 (0–0) | 29 (27–31) | 0 | 62–64 | n/a | n/a | 0 | 0 | 0 | 0 | 0 |
| `pulls.list_to_pr.cold` | 0 (0–0) | 65 (62–68) | 0 | 178 | n/a | n/a | 0 | 0 | 0 | 0 | 0 |
| `pulls.pr_to_pr.cold` | 0 (0–0) | 43 (41–46) | 0 | 178–180 | n/a | n/a | 0 | 0 | 0 | 0 | 0 |
| `pulls.pr_to_pr.revisit` | 0 (0–0) | 27 (25–46) | 0 | 211 | n/a | n/a | 0 | 0 | 0 | 0 | 0 |
| `pulls.pr_to_pr.hover_click` | 0 (0–0) | 47 (46–49) | 0 | 178 | n/a | n/a | 0 | 0 | 0 | 0 | 0 |
| `pulls.pr_changes_to_pr` | 0 (0–0) | 62 (58–62) | 0 | 178 | n/a | n/a | 0 | 0 | 0 | 0 | 0 |
| `tree.expand.docs` | 0 (0–0) | 78 (64–79) | 1 | 0 | n/a | n/a | 89–90 | 384 | 384 | 9–10 | 0 |
| `tree.expand.src` | 0 (0–0) | 46 (42–47) | 1 | 0 | n/a | n/a | 6 | 24 | 24 | 8 | 0 |
| `tree.collapse.src` | 0 (0–0) | 31 (30–32) | 0 | 0 | n/a | n/a | 6 | 24 | 24 | 7 | 0 |
| `tree.reexpand.src` | 0 (0–0) | 30 (29–31) | 0 | 0 | n/a | n/a | 6 | 24 | 24 | 8 | 0 |
| `tree.expand_nested.src_metabrowser` | 0 (0–0) | 47 (45–48) | 1 | 0 | n/a | n/a | 373–377 | 1608 | 1608 | 9 | 0 |
| `palette.query` | 27 (23–29) | 163 (155–168) | 0 | 0 | 11 | 11 | 0 | 0 | 0 | 0 | 0 |
| `skim.held_arrow_down` | 333 (329–340) | 47 (42–52) | 6 | 27157 | n/a | n/a | 0 | 0 | 0 | 0 | 0 |
| `reveal.deep_landing` | 0 (0–0) | 201 (184–203) | 1 | 0 | n/a | n/a | 653–657 | 2808 | 2808 | 9–12 | 0 |

### Cache disposition (network / revalidated / cache)

| Transition | static | plugin-static | kpress-static | data | document |
| --- | ---: | ---: | ---: | ---: | ---: |
| `landing.cold_markdown` | 41 / 0 / 0 | 29 / 0 / 0 | 16 / 1 / 0 | 19 / 0 / 0 | 1 / 0 / 0 |
| `landing.reload` | 0 / 0 / 41 | 2 / 27 / 0 | 0 / 13 / 4 | 21 / 1 / 0 | 1 / 0 / 0 |
| `reveal.deep_landing` | 41 / 0 / 0 | 11 / 0 / 0 | 2–3 / 0 / 0 | 24–33 / 0 / 0 | 1 / 0 / 0 |

What the counts say, at this build:

- After the ready frame, no transition showed a blank or a placeholder frame in any run.
- Before it, the cold landing showed 11 or 12 blank frames, 7 to 9 of them with a
  visible placeholder, a reload 7 or 8, and the deep reveal landing 7 to 9. The first
  commit view (`commits.cold.1`, which loads the diff plugin’s seven modules) showed 5
  blank frames, 2 of them with a visible placeholder, the first image 1 or 2 while it
  decoded, and the first pull request opened from the list 1 or 2. Every other file,
  keyboard, history, view-tab, tree, palette, and pull request transition had no blank
  frame.
- A main tab with nothing selected landed on its prompt with no blank frame, and the
  return to Files showed 2 blank frames before the file came back, in every run.
  With a commit and a pull request selected, the same switches had no blank frame, but
  each still replaced two to five top-level preview nodes and issued requests.
- Every switch to or from Files moved the tree region by 37 px, in one step.
  Files that add or drop the view tab bar moved the content by 30 px, and files that add
  or drop the scrollbar changed its width by 11 px.
  Pull request tab switches moved the tab bar by 8 px, and so did #349’s Changes to
  #348, whose header is 8 px shorter; #353, #351, and #349 have headers of one height,
  so a switch among them moved nothing.
  Expanding `docs` pushed the rows below it 384 px over 9 or 10 frames, the nested
  expand 1,608 px, and the deep reveal 2,808 px.
- A cold click on a pull request read its record three times (two duplicates), as did a
  pull request to pull request click.
  A revisit read it once and then twice more after the page’s own refresh, which are
  settlement reads, not duplicates; its preview kept changing until about 1.08 s.
- A commit revisit issued one data request, and a Markdown revisit one KPress request,
  uploading the source again (19,168 bytes for `README.md`, 191,142 for
  `docs/design-system.md`).
- `files.revisit.source_large` painted in 80 to 96 ms, and a 107 to 143 ms task followed
  the ready frame. Revision 1 reported this transition at 314 to 362 ms, because its
  painted ready waited for that task.

## A/A Resolution

`compare --aa control` paired runs 1 and 2, 3 and 4, and 5 and 6, and made 4,199
comparisons: 77 transitions and every metric each applies to, with no gap.
609 of them vary at all; at three runs against three, two identical builds separate on
one comparison with probability 10% (2 / C(6, 3)), so chance alone predicts about 61
separations among them.
33 separated:

- Painted ready had no result.
  `files.cold.image` came apart with one pair of three beyond the tolerance, 77.8
  (63.4–78.1) → 79.9 (78.9–95.3), which the runbook answers with a rerun of that pair;
  `commits.cold.1` is bimodal, 113 or 164 ms, three frames apart, in both halves; three
  more separated with every pair within the tolerance.
- Five were results: `files.cold.image` blank frames, 1 in every odd run and 2 in every
  even one, and their milliseconds; `pulls.tab.checks_first` settle time, 9.3 (7.2–9.6)
  → 9.7 (9.7–24.4); and two figures that are shown but not judged.
- Fifteen had two pairs beyond the tolerance under overlapping ranges, which a round
  would have to explain: four are `commits.cold.1`’s bimodal times, and the rest are
  frame counts of 5 or fewer, settle times under 15 ms, the pull request revisit’s ready
  read (12 to 32 ms), and the navigation settle time the background catalog walk drives.

So on this build a round should not claim a one-frame change in the image’s blank
frames, or any settle time under about 25 ms, at three runs a side, and should read
`commits.cold.1` as two populations.
The full list is the output of the `compare --aa` command above.

## Limits

- Headless Chrome only.
  The native app’s WebKit is not measured.
- The server is warm by design; a cold server render is not part of this regime.
- The corpus has no heavy view such as a multi-megabyte JSONL log, so heavy view-tab
  revisits (H99) are not covered.
- Painted ready is read from the main thread: raster and GPU time are invisible to the
  page, and a headless Chrome presents earlier than a display would.
  A product ResizeObserver round after the first can change a frame after it was read.
- The pull request catalog is live: the open count moves the list that
  `pulls.first_show` and the main-tab Pulls rows land on, newer pull requests push the
  subjects down the Closed list, and the palette’s pull request results follow it.
  Each run records the totals and the subjects’ offsets.
- The hypothesis identifiers name the H86 to H106 rows of the load-time plan, merged to
  `main` with #364.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->

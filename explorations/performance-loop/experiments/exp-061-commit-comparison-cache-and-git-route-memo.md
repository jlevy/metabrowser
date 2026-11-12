---
title: Commit Comparison Cache and Git Route Memo
softschema:
  contract: metabrowser.loadtime:Experiment/v1
  schema: experiment.schema.yaml
  envelope: experiment
  status: enforced
experiment:
  id: exp-061
  title: Commit Comparison Cache and Git Route Memo
  date: "2026-11-12"
  hypotheses:
    - H88
  subject:
    corpus: Detached checkout of this repository at 7a02fed4, frozen and clean. It is a linked worktree, so its refs are the main checkout's, and they moved during the series.
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
    candidate: metab 0.12.1.dev165+9903292 (+169 commits, 9e1630db7), the editable checkout of claude/perf-caches at 9e1630db, clean, one server process per run. It carries this round's commits (3594c291, a627d915, 45f2b8d3) and exp-063's (9e1630db), which touch disjoint code and metrics.
    record: exp-061-transition-samples.jsonl
  results:
    - metric: requests_data.commits.revisit.1
      control_median: 1
      candidate_median: 0
      control_range: [1, 1]
      candidate_range: [0, 0]
      overlapping: false
    - metric: painted_ready_ms.commits.revisit.1
      control_median: 131.5
      candidate_median: 80.4
      control_range: [130.2, 161.7]
      candidate_range: [78.7, 81.4]
      overlapping: false
    - metric: requests_data.commits.revisit.2
      control_median: 1
      candidate_median: 0
      control_range: [1, 1]
      candidate_range: [0, 0]
      overlapping: false
    - metric: painted_ready_ms.commits.revisit.2
      control_median: 213.1
      candidate_median: 80.5
      control_range: [180.1, 294.9]
      candidate_range: [79.8, 81.8]
      overlapping: false
    - metric: requests_data.main_subject.files_to_commits
      control_median: 2
      candidate_median: 1
      control_range: [2, 2]
      candidate_range: [1, 1]
      overlapping: false
    - metric: painted_ready_ms.main_subject.files_to_commits
      control_median: 230.7
      candidate_median: 148.1
      control_range: [214.2, 311.7]
      candidate_range: [146.6, 197.7]
      overlapping: false
    - metric: painted_ready_ms.main_subject.pulls_to_commits
      control_median: 213.5
      candidate_median: 163.3
      control_range: [197.5, 291.9]
      candidate_range: [146.2, 180.1]
      overlapping: false
    - metric: painted_ready_ms.commits.first_show
      control_median: 298.6
      candidate_median: 97.8
      control_range: [297.6, 363.3]
      candidate_range: [96.1, 406.4]
      overlapping: true
    - metric: client_ms.api_git_log_limit_250
      control_median: 173.9
      candidate_median: 8.3
      control_range: [167.16, 182.34]
      candidate_range: [7.89, 9.2]
      overlapping: false
    - metric: client_ms.api_git_summary
      control_median: 172.4
      candidate_median: 4.4
      control_range: [165.71, 262.17]
      candidate_range: [3.18, 68.23]
      overlapping: false
    - metric: client_ms.api_git_refs
      control_median: 32
      candidate_median: 6.4
      control_range: [30.68, 37.85]
      candidate_range: [5.7, 7.05]
      overlapping: false
  complexity:
    lines_changed: 856
    new_dependencies: []
    new_failure_modes:
      - A served folder's commit comparison kept by the page does not reflect an edit to the working tree's .gitattributes or Git configuration until Refresh, the same lifetime the page already gives commit detail.
      - The route memo does not notice Git configuration outside the repository, or an object lost from under a ref that still names it.
      - A repository with more than 16,384 entries under its ref directories gets no ref state and is answered uncached, as before.
    notes: 856 lines of product code in git/ref_state.py, git/route_memo.py, git/history.py, git/routes.py, static/git-panel.js, settings.py, and types.d.ts; tests and documentation are another 708.
  verdict:
    decision: accepted
    primary_metric: requests_data and painted_ready_ms on commits.revisit
    reason: A commit revisit asked for no comparison in any candidate run and painted in 80 ms against 132 ms and 213 ms, ranges apart and beyond the 1.3x tolerance; the Git routes answered a repeat 5x to 39x faster, ranges apart; and nothing else moved the wrong way.
    commit: 45f2b8d3
---
**Status:** Accepted.
Five interleaved pairs, ten valid runs, none refused.

## Why This Round

H88, in the hypothesis registry of the research branch’s load-time plan (“Apparent Speed
and Layout Stability”), says a commit revisit fetches its comparison again and the Git
routes recompute on every call, and that a comparison cache by commit ID and a server
memo by a refs fingerprint make revisits and repeats cheap.
The exp-058 baseline measured 88 to 141 ms for each revisit’s comparison request, and
177 ms for `/api/git/log?limit=250` and 186 ms for a 67-byte `/api/git/summary`. The
bead is `mb-8a8g`.

The change has two halves.
In the browser, the Commits panel keeps an answered comparison, keyed by the request’s
own query, when its revision is a full commit ID, bounded at 16 MiB of JSON. On the
server, `git/ref_state.py` names the refs’ state with one `stat` per entry, and the refs
and summary bodies, the history scope, and the first log page’s session are kept under
that state, with an ETag.

**One series measured two rounds.** The candidate build carries this round’s commits and
those of [exp-063](exp-063-markdown-render-cache-and-kept-worker.md) (H90, the Markdown
render cache and the kept Worker).
The two changes touch disjoint code and their metrics are on disjoint transitions: this
round reads the transitions with a Git subject and exp-063 the ones with a Markdown
subject. Both artifacts read the same samples.

## Protocol

Declared before the measured series:

- Named metrics: requests and painted ready on a commit revisit (`commits.revisit.1` and
  `commits.revisit.2`). Prediction: no comparison request on a revisit, and a shorter
  painted ready. Server half: client time of repeated `/api/git/log?limit=250`,
  `/api/git/summary`, and `/api/git/refs`, at least ten each, control against candidate,
  back to back.

- Guards: every other transition’s counts unchanged, no new blank frames or region
  movement, and every transition converged on the exact commit.

- Series, from the frozen harness checkout at `22af6103`, the scenario of exp-058:

  ```shell
  node explorations/performance-loop/transitions.mjs run --exp exp-061 \
    --corpus /path/to/frozen-checkout --runs 5 \
    --condition control=/path/to/control/.venv/bin/metab \
    --condition candidate=/path/to/candidate/.venv/bin/metab
  node explorations/performance-loop/transitions.mjs samples \
    .bench/transitions/exp-061/runs.jsonl \
    --out explorations/performance-loop/experiments/exp-061-transition-samples.jsonl
  node explorations/performance-loop/transitions.mjs compare \
    explorations/performance-loop/experiments/exp-061-transition-samples.jsonl \
    --control control --candidate candidate
  ```

- Regime: the scenario’s standard one.
  Each run started a fresh server on its own port in 8890 to 8899, ran every journey
  once unrecorded, and then measured them, each journey in a fresh Chrome profile.
  The first `--condition` led odd pairs, so the order was control, candidate; candidate,
  control; and so on.

- Server half, after the series: one server per build on the same corpus, each with its
  own empty cache and configuration directory, both done indexing, then
  `node explorations/performance-loop/git-route-pairs.mjs --n 15`. For each route, one
  unrecorded warm-up request per server, then fifteen pairs, odd pairs control first.
  Each request sent `accept-encoding: gzip` and no `If-None-Match`, so a kept answer was
  a 200 with its body.
  The record is [exp-061-git-routes-samples.json](exp-061-git-routes-samples.json).

- Load: the one-minute load average was 7.4 to 13.17 at the control runs’ starts and
  ends and 8.02 to 18.47 at the candidate runs’, and the five-minute average reached
  16.12. Each run took 418 to 457 s. Another agent’s transition series (exp-059) shared
  the machine and the corpus for at least the last pair.
  The server half ran at a one-minute load of 7.09 to 7.45.

## Identities

| Item | Value |
| --- | --- |
| Control build | `metab 0.12.1.dev165+9903292 (+165 commits, 099032928)`, editable checkout at `09903292`, clean in every run |
| Candidate build | `metab 0.12.1.dev165+9903292 (+169 commits, 9e1630db7)`, editable checkout at `9e1630db`, clean in every run |
| Corpus | Checkout at `7a02fed4`, clean, 1,286 indexed files |
| Trunk seen by Commits | `09903292` in pairs 1 and 2, `9fad3080` in control run 3, `02db045a` from candidate run 3 on |
| Pull request catalog | Absent at run 1’s server start for each condition; 354 to 356 in all, 16 or 17 open, afterwards |
| Harness | `22af6103`, clean, in all ten runs |
| Chrome | 152.0.7977.83, headless |

The commit subjects are named by full ID, so the trunk moving changed only which commits
head the list.
It did change the ref state the candidate keeps its answers under; see the
first Commits show below.

## Guards

Every measured and warm-up pass of all ten runs passed every guard, including
`converged`: each commit transition ended on the requested commit with its route,
selected row, rendered subject, and owner in agreement.

## Results

Times are painted ready, from the input event to the frame after the first frame that
showed the exact subject, as median and range over five runs.
Counts are one value when every run agreed and a range otherwise.
Each number is from the committed samples, through `compare` and `summarize`, except the
input-to-next-paint column, which is from
[exp-061-transition-detail.jsonl](exp-061-transition-detail.jsonl), the same runs’ Event
Timing, Long Animation Frame, and request fields for the named transitions.

### Commit Revisits

| Transition | Painted ready ms, control | Painted ready ms, candidate | Ratio | Data requests | Input to next paint ms |
| --- | ---: | ---: | ---: | --- | --- |
| `commits.revisit.1` | 132 (130–162) | 80 (79–81) | 0.61x | 1 → 0 | 16 (16–16) → 24 (16–24) |
| `commits.revisit.2` | 213 (180–295) | 81 (80–82) | 0.38x | 1 → 0 | 16 (16–16) → 24 (16–24) |

Both are apart and beyond the 1.3x tolerance.
The one data request each control revisit made was `/api/plugin/diff/comparison`; the
candidate made none, and its blank frames, placeholder frames, preview replacements, and
region movement were the control’s (0, 0, 2, 0). The application’s own
`gitRevision:selectToReady` span fell from 141 (136–163) and 197 (185–310) ms to 65
(64–66) and 66 (65–67) ms.

### Other Transitions With a Git Subject

| Transition | Control | Candidate | Ratio | Verdict |
| --- | ---: | ---: | ---: | --- |
| `main_subject.files_to_commits` | 231 (214–312) | 148 (147–198) | 0.64x | lower, beyond the tolerance; data requests 2 → 1 |
| `main_subject.pulls_to_commits` | 214 (198–292) | 163 (146–180) | 0.76x | lower, beyond the tolerance; data requests 2 → 1 |
| `commits.first_show` | 299 (298–363) | 98 (96–406) | 0.33x | no detected difference |
| `main.files_to_commits.first` | 298 (262–394) | 249 (247–265) | 0.83x | no detected difference |
| `commits.hover_click` | 65 (64–66) | 49 (47–114) | 0.75x | no detected difference |
| `commits.cold.1` to `.3` | 181, 197, 130 | 180, 198, 131 | 0.99x to 1.01x | no detected difference |

Returning to the Commits tab with a commit selected remounts that commit, which is a
revisit: its comparison came from the kept answer.

The first Commits show reads `git/repo`, `git/refs`, `git/log`, and `git/summary`, all
of which the warm-up pass had asked for.
In three candidate runs it painted in 96 to 98 ms with 5 blank frames, against 298 to
363 ms and 17 to 21 in every control run.
In candidate runs 3 and 4 it took 296.5 and 406.4 ms with 17 and 24 blank frames, as the
control does: the warm-up pass’s answers no longer applied.
The trunk moved to `02db045a` just before candidate run 3, other agents commit to this
repository’s branches continually, and a change to any ref in the repository moves the
state. Which ref moved during each run was not recorded.
The ranges overlap, so this is not a result.

### Server Half

| Route | Control ms | Candidate ms | Ratio | Server-Timing `srv` ms, control → candidate | Body bytes |
| --- | ---: | ---: | ---: | --- | ---: |
| `/api/git/log?limit=250` | 173.9 (167.2–182.3) | 8.3 (7.9–9.2) | 21x | 171.1 → 5.4 | 90,487 |
| `/api/git/summary` | 172.4 (165.7–262.2) | 4.4 (3.2–68.2) | 39x | 170.0 → 2.4 | 67 |
| `/api/git/refs` | 32.0 (30.7–37.9) | 6.4 (5.7–7.1) | 5.0x | 29.5 → 3.8 | 80,805 |

Fifteen pairs per route; client time is the whole request, body included.
Every range is apart and every ratio is beyond the tolerance.
Each route’s body had the same length on both builds in every sample, and every
candidate answer carried an ETag.
The candidate’s one 68 ms summary (66 ms at the server) is probably a
repository-identity rediscovery, which the five-second identity cache causes on both
builds; the control’s three slowest summaries, 242 to 262 ms, fell in the same pairs.
That reading is not verified.
The refs did not move during the half: `git for-each-ref` hashed the same before and
after.

### What Did Not Move

`compare` found 37 metrics with ranges apart.
Eight are the four commit transitions above, painted ready and data requests each.
One is `main_subject.commits_to_pulls` painted ready, 81 (66–127) to 64 (63–65), apart
and within the tolerance, so not a result.
The other 28 are on transitions with a Markdown subject and belong to exp-063. No other
transition’s request counts, blank frames, placeholder frames, preview replacements,
layout shifts, or region movement came apart.

## Verdict

The accept rule, applied:

- The named metrics moved as predicted: a commit revisit made no comparison request (1 →
  0 in every run) and painted sooner (0.61x and 0.38x).
- Their ranges do not overlap, at five runs per condition, and both times are beyond the
  1.3x tolerance. The server half’s three routes are apart at 5x to 39x.
- Nothing else moved the wrong way: the input-to-next-paint of a revisit rose from 16 to
  24 ms in some runs, with ranges overlapping, and no guard count changed.
- **Judgment:** worth it, because a commit revisit now paints in about 80 ms with no
  request and the Git routes answer a repeat in 4 to 8 ms, for a stat walk per request
  and memory bounded at 16 MiB in the page and 8 MiB plus 32 scopes on the server.

## Limits

- Headless Chrome only; the native app’s WebKit is not measured.
- The corpus shares its refs with an active repository, so the memo’s hit rate here
  depends on how often other worktrees commit.
  A served repository that nobody else writes to keeps its state longer.
- The browser cache’s cost in memory was not measured in a browser; its bound is the
  JSON length measured over this repository’s last 200 commits (V8 heap 1.0 to 1.5 times
  that, in Node).
- A served folder’s comparison also reads its working tree’s `.gitattributes`; the page
  asks again only on Refresh.
- H88 is registered in the plan on the research branch, not yet in this branch’s plan.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->

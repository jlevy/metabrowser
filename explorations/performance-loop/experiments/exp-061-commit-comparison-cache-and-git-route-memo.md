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
    corpus: Standalone clone of this repository at 7a02fed4 (corpus v2), clean, with the same refs at the start and end of every run.
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
    candidate: metab 0.12.1.dev165+9903292 (+174 commits, 4b0e12332), the editable checkout of claude/perf-caches at 4b0e1233, clean at the start and end of every run, a fresh server process per run. It carries this round's change and exp-063's, which touch disjoint code.
    record: exp-061-transition-samples.jsonl
  results:
    - metric: requests_data.commits.revisit.1
      control_median: 1
      candidate_median: 0
      control_range: [1, 1]
      candidate_range: [0, 0]
      overlapping: false
    - metric: painted_ready_ms.commits.revisit.1
      control_median: 146.8
      candidate_median: 31.0
      control_range: [97.4, 349.2]
      candidate_range: [29.8, 31.6]
      overlapping: false
    - metric: requests_data.commits.revisit.2
      control_median: 1
      candidate_median: 0
      control_range: [1, 1]
      candidate_range: [0, 0]
      overlapping: false
    - metric: painted_ready_ms.commits.revisit.2
      control_median: 188.9
      candidate_median: 29.6
      control_range: [146.9, 198.0]
      candidate_range: [28.5, 30.8]
      overlapping: false
    - metric: painted_ready_ms.commits.hover_click
      control_median: 30.8
      candidate_median: 47.8
      control_range: [30.7, 94.0]
      candidate_range: [47.0, 49.1]
      overlapping: true
    - metric: painted_ready_ms.commits.cold.1
      control_median: 114.2
      candidate_median: 147.8
      control_range: [113.3, 231.3]
      candidate_range: [114.2, 196.1]
      overlapping: true
    - metric: painted_ready_ms.commits.first_show
      control_median: 280.4
      candidate_median: 95.8
      control_range: [263.8, 295.9]
      candidate_range: [93.3, 97.3]
      overlapping: false
    - metric: painted_ready_ms.main.files_to_commits.first
      control_median: 238.0
      candidate_median: 45.3
      control_range: [229.1, 388.3]
      candidate_range: [44.1, 46.9]
      overlapping: false
    - metric: requests_data.main_subject.files_to_commits
      control_median: 2
      candidate_median: 1
      control_range: [2, 2]
      candidate_range: [1, 1]
      overlapping: false
    - metric: painted_ready_ms.main_subject.files_to_commits
      control_median: 213.1
      candidate_median: 96.8
      control_range: [182.1, 297.4]
      candidate_range: [96.5, 98.4]
      overlapping: false
    - metric: painted_ready_ms.main_subject.pulls_to_commits
      control_median: 213.9
      candidate_median: 105.3
      control_range: [181.5, 284.8]
      candidate_range: [96.4, 114.2]
      overlapping: false
    - metric: client_ms.api_git_log_limit_250
      control_median: 182
      candidate_median: 6.8
      control_range: [174.57, 238.86]
      candidate_range: [6.21, 65.54]
      overlapping: false
    - metric: client_ms.api_git_summary
      control_median: 184.1
      candidate_median: 3.4
      control_range: [171.5, 279.4]
      candidate_range: [2.96, 53.49]
      overlapping: false
    - metric: client_ms.api_git_refs
      control_median: 28.4
      candidate_median: 3.6
      control_range: [23.49, 86.31]
      candidate_range: [3.02, 71.96]
      overlapping: true
  complexity:
    lines_changed: 1007
    new_dependencies: []
    new_failure_modes:
      - A served folder's commit comparison kept by the page does not reflect an edit to the working tree's .gitattributes or Git configuration until Refresh, the same lifetime the page already gives commit detail.
      - The route memo does not notice Git configuration outside the repository, or an object lost from under a ref that still names it.
      - A repository with more than 16,384 entries under its ref directories gets no ref state and is answered uncached, as before.
    notes: 1,007 changed lines of product code (914 added, 93 removed) in git/ref_state.py, git/route_memo.py, git/history.py, git/routes.py, git/log.py, git/process.py, static/git-panel.js, settings.py, and types.d.ts; 821 of them are the server half's.
  verdict:
    decision: unresolved
    primary_metric: "H88(a): requests_data and painted_ready_ms on commits.revisit.1 and .2; H88(b): client ms of /api/git/log?limit=250, /api/git/summary, and /api/git/refs"
    reason: "Neither half meets the accept rule. H88(a), the comparison cache, meets its four deciding metrics, but its declared guard fails: commits.hover_click is higher in 5 of 6 pairs (30.8 to 47.8 ms, ranges overlapping through one control run), and commits.cold.1 and commits.first_show's settle time are higher in 2 of 6, none of them accounted for. H88(b), the route memo, meets its criterion for the log page and the summary, but the refs route's ranges overlap (23.49 to 86.31 against 3.02 to 71.96 ms), so it does not meet the criterion it declared for all three routes. Its guard, B8, was correct in 45 of 45 checks."
    commit: 4b0e1233
---
**Status:** Official round, on harness revision 4. H88(a), the comparison cache:
**unresolved**. H88(b), the route memo: **unresolved**. Six interleaved pairs, twelve
valid runs, none refused.
Both halves moved their deciding metrics in the predicted direction, and neither met the
accept rule; see [Verdicts](#verdicts).

## Why This Round

H88, in the hypothesis registry of the research branch’s load-time plan (“Apparent Speed
and Layout Stability”), says a commit revisit fetches its comparison again and the Git
routes recompute on every call, and that a comparison cache by commit ID and a server
memo by a refs fingerprint make revisits and repeats cheap.
The bead is `mb-8a8g`.

The change has two halves, judged separately:

- **(a) In the browser,** the Commits panel keeps an answered comparison, keyed by the
  request’s own query, when its revision is a full commit ID, bounded at 16 MiB of JSON.
- **(b) On the server,** `git/ref_state.py` names the refs’ state with one `stat` per
  entry, and the refs and summary bodies, the history scope, and the first log page’s
  session are kept under that state, with an entity tag.

**One series measured two rounds.** The candidate carries this round’s change and
[exp-063](exp-063-markdown-render-cache-and-kept-worker.md)’s (H90, the Markdown render
cache and the kept Worker).
The two touch disjoint code, and each round reads its own transitions from the same
[samples](exp-061-transition-samples.jsonl): this one the transitions with a Git
subject, exp-063 those with a Markdown subject.

## Protocol

Declared before the series started, and not changed after:

- **H88(a)**, decided by the transition scenario.
  All four must hold: `commits.revisit.1` and `.2` `requests_data` lower (a count,
  judged on its ranges: 1 to 0 expected) and `painted_ready_ms` lower (the pair rule:
  ranges apart and at least two pairs beyond 1.3x). Guards: no wrong-way result on any
  `commits.*` or `main_subject.*commits*` transition, and every run valid.

- **H88(b)**, decided by [git-route-pairs.mjs](../git-route-pairs.mjs), the pilot’s
  instrument with the B8 check added.
  All three must hold, each by the same pair rule: the client time of
  `GET /api/git/log?limit=250`, `GET /api/git/summary`, and `GET /api/git/refs` lower.
  Guard (B8): between timed pairs a ref moves in a scratch clone with about 1,000 loose
  refs, and the candidate’s refs, summary in both scopes, and first log page must equal
  the control’s. It is reported as correct or wrong, not timed.

- Series, from a frozen harness checkout at `5031dc16` (scenario revision 4):

  ```shell
  node explorations/performance-loop/transitions.mjs run --exp exp-061 \
    --corpus /path/to/corpus-v2 --runs 6 \
    --condition control=/path/to/control/.venv/bin/metab \
    --condition candidate=/path/to/candidate/.venv/bin/metab
  node explorations/performance-loop/transitions.mjs samples \
    .bench/transitions/exp-061/runs.jsonl \
    --out explorations/performance-loop/experiments/exp-061-transition-samples.jsonl
  node explorations/performance-loop/transitions.mjs compare \
    explorations/performance-loop/experiments/exp-061-transition-samples.jsonl \
    --control control --candidate candidate \
    --expect commits.revisit.1:requests_data:lower \
    --expect commits.revisit.2:requests_data:lower \
    --expect commits.revisit.1:painted_ready_ms:lower \
    --expect commits.revisit.2:painted_ready_ms:lower
  ```

  The one `compare` call also carried exp-063’s nine `--expect` flags.
  Regime: the scenario’s standard one, a fresh server per run on a port in 8890 to 8899
  (fixed by the harness), one unrecorded warm-up pass of every journey, then the
  measured pass, each journey in a fresh Chrome profile.
  The first `--condition` led odd pairs.

- Server half, right after the series, with no other series on the machine: four
  servers, each with its own empty cache and configuration directory, all done indexing.
  Control and candidate served the corpus on ports 8910 and 8911, and served the B8
  scratch clone on 8912 and 8913. Then:

  ```shell
  node explorations/performance-loop/git-route-pairs.mjs \
    --control http://127.0.0.1:8910 --candidate http://127.0.0.1:8911 --n 15 \
    --out exp-061-git-routes-samples.json --check-repo /path/to/scratch-clone \
    --check-control http://127.0.0.1:8912 --check-candidate http://127.0.0.1:8913
  ```

  Per route, one unrecorded warm-up request per server, then fifteen pairs, odd pairs
  control first, with a B8 check after each pair.
  Each timed request sent `accept-encoding: gzip` and no `If-None-Match`, so a kept
  answer was a 200 with its body.
  The record is [exp-061-git-routes-samples.json](exp-061-git-routes-samples.json).

## Identities and Load

| Item | Value |
| --- | --- |
| Control build | `metab 0.12.1.dev165+9903292 (+165 commits, 099032928)`, editable checkout at `09903292`, clean at the start and end of every run and of the server half |
| Candidate build | `metab 0.12.1.dev165+9903292 (+174 commits, 4b0e12332)`, editable checkout at `4b0e1233`, clean at the start and end of every run and of the server half |
| Harness | `5031dc16`, scenario revision 4, clean in all twelve runs |
| Corpus | Standalone clone at `7a02fed4`, clean, 1,286 indexed files; trunk `083e78e4` and server log head `7a02fed4` in every run; the same refs fingerprint at every run’s start and end, and the same `for-each-ref` digest before and after the server half |
| Chrome | 152.0.7977.83, headless |
| Series | `2026-11-12T15-12-37-832Z`, 15:12 to 16:45 UTC; 455 to 487 s a run |
| Load, series | One-minute load 4.3 to 9.14 at the control runs’ starts and ends and 4.3 to 6.82 at the candidate runs’ (from `compare`); the five-minute load reached 8.94. Other agents’ processes raised it during the last control run, which ended at 9.14 |
| Load, server half | One-minute load 8.51 at its start and 11.27 at its end, 16:45 to 16:47 UTC |

## Guards

Every measured and warm-up pass of all twelve runs passed every guard of the scenario,
including `converged`. `compare` found no gap and no refusal.

**B8: correct.** The scratch clone was a clone of the corpus with 1,000 loose branches
(`refs/heads/loose/b0` to `b999`, at HEAD’s last 1,000 commits), 19 packed refs, 1,019
refs in all, and a detached HEAD. The timed servers never served it.
Between timed pairs it moved 45 times in turn: 12 commits on the detached HEAD, 11 loose
branches moved, 11 tags added, and 11 loose branches deleted.
Before each move the candidate was asked twice, so a kept answer existed.
After each move, for `/api/git/refs`, `/api/git/summary`, `/api/git/summary?scope=all`,
and `/api/git/log?limit=50`:

- the candidate’s answer equaled the control’s in 45 of 45 checks on each route, the
  refs and summaries byte for byte and the log page in every field but its cursors;
- the candidate’s entity tag changed in 45 of 45 checks on each route.

## Results

Times are painted ready, from the input event to the frame after the first frame that
showed the exact subject, as median and range over six runs.
Every number in this section and the next is from `compare` over the committed samples,
except the server half’s, which are from the instrument’s record.

### H88(a): Commit Revisits

| Transition | Painted ready ms, control → candidate | Pair ratios | Data requests | Verdict |
| --- | --- | --- | --- | --- |
| `commits.revisit.1` | 146.8 (97.4–349.2) → 31.0 (29.8–31.6) | 0.21x (0.09–0.32), 6 of 6 beyond | 1 → 0 | lower, apart, result |
| `commits.revisit.2` | 188.9 (146.9–198.0) → 29.6 (28.5–30.8) | 0.16x (0.14–0.21), 6 of 6 beyond | 1 → 0 | lower, apart, result |

Blank frames, visible placeholder frames, and region movement were 0 on both builds, and
both replaced the preview’s top nodes twice.

### H88(b): Server Half

| Route | Control ms | Candidate ms | Pair ratios | Apart | Body bytes |
| --- | --- | --- | --- | --- | ---: |
| `/api/git/log?limit=250` | 182 (174.57–238.86) | 6.8 (6.21–65.54) | 26.06x (3.47–29.02), 15 of 15 beyond | yes | 87,303 |
| `/api/git/summary` | 184.1 (171.5–279.4) | 3.4 (2.96–53.49) | 51.79x (4.17–63.4), 15 of 15 beyond | yes | 67 |
| `/api/git/refs` | 28.4 (23.49–86.31) | 3.6 (3.02–71.96) | 7.48x (1.2–11.7), 13 of 15 beyond | no | 2,311 |

Pair ratios here are control over candidate, so above 1 favors the candidate.
Each route’s body had the same length on both builds in every sample, every status was
200, and every candidate answer carried an entity tag.

The candidate’s slow samples fell every fourth pair: log pairs 4, 8, and 12 (56 to 66
ms), summary pairs 5, 9, and 13 (51 to 53 ms), and refs pairs 2, 6, 10, and 14 (51 to 72
ms). On the refs pairs the control was slow too (74 to 86 ms against 23 to 39 ms on its
other pairs).
This fits the repository identity’s five-second lifetime, which both builds
have: with a B8 check after each pair, four pairs take about five seconds.
That reading is not verified, and it does not change the verdict.

### Other Transitions With a Git Subject

| Transition | Painted ready ms, control → candidate | Pair ratios | Verdict |
| --- | --- | --- | --- |
| `commits.first_show` | 280.4 (263.8–295.9) → 95.8 (93.3–97.3) | 0.34x (0.32–0.37), 6 of 6 beyond | lower, result |
| `main.files_to_commits.first` | 238.0 (229.1–388.3) → 45.3 (44.1–46.9) | 0.19x (0.11–0.20), 6 of 6 beyond | lower, result |
| `main_subject.files_to_commits` | 213.1 (182.1–297.4) → 96.8 (96.5–98.4) | 0.45x (0.33–0.54), 6 of 6 beyond | lower, result; data requests 2 → 1 |
| `main_subject.pulls_to_commits` | 213.9 (181.5–284.8) → 105.3 (96.4–114.2) | 0.51x (0.34–0.53), 6 of 6 beyond | lower, result; data requests 2 → 1 |
| `commits.cold.2` | 205.7 (161.5–266.1) → 195.9 (148.7–228.5) | 0.96x (0.61–1.21), 1 of 6 beyond | no detected difference |
| `commits.cold.3` | 154.7 (146.5–195.7) → 146.1 (98.5–148.0) | 0.83x (0.61–0.99), 3 of 6 beyond | overlap, lower, to explain |
| `commits.cold.1` | 114.2 (113.3–231.3) → 147.8 (114.2–196.1) | 1.07x (0.70–1.58), 2 of 6 beyond | overlap, higher, to explain |
| `commits.hover_click` | 30.8 (30.7–94.0) → 47.8 (47.0–49.1) | 1.55x (0.50–1.60), 5 of 6 beyond | overlap, higher, to explain |

The first Commits show and the first switch to Commits read `git/refs`, `git/log`, and
`git/summary`, which the warm-up pass had asked for, so the candidate answered them from
the memo. They are the server half’s effect, seen in the browser; the round did not
declare them as deciding metrics.
Returning to a selected commit through a main tab made one data request instead of two:
the comparison came from the page’s keep.

### Wrong-Way Flags

`compare` exited 1 with 31 wrong-way results and no gap: in each, the ranges overlap and
two or more pairs are higher beyond 1.3x (“explain before accepting”). None has its
ranges apart. By the round each falls in:

- **H88’s guard, 10:**
  - `commits.hover_click`: painted ready, ready, frames to ready (1 (1–5) → 2), settled,
    and ready after the last input, each higher in pairs 1 to 5. Ready went from 15.8
    (14.6–79.9) to 35.2 (33.1–36.4) ms.
  - `commits.cold.1`: painted ready, ready, visible placeholder frames, and ready after
    the last input, each higher in two pairs.
  - `commits.first_show` settled, 5.0 (4.5–10.1) → 6.8 (4.9–9.4) ms, higher in pairs 1
    and 2.
- **Other Git transitions, 2:** `main.files_to_commits.first` settled, 9.2 (4.8–20.3) →
  9.7 (4.9–10.0) ms, and `main.commits_to_pulls` settled, 6.3 (6.0–6.9) → 7.1 (5.5–9.6)
  ms.
- **H90’s guard, 4:** see exp-063.
- **Neither round’s transitions, 15:**
  - `views.json.revisit`: painted ready, ready, settled, and ready after the last input.
  - `main_subject.files_to_pulls` settled, 606.6 (67.0–1064.1) → 1053.3 (1044.7–1071.5)
    ms.
  - `pulls.tab.changes_revisit`, 4 metrics.
  - `pulls.pr_to_pr.revisit` ready.
  - `pulls.history_back`, 5 metrics.

On the journeys that neither change addresses (landing, Pulls, tree, palette, skim, and
reveal), `compare` lists 10 flags of this kind higher and 25 lower among 1,085 judged
comparisons. So two-of-six flags under overlapping ranges occur on this machine where no
code changed. That base rate does not account for `commits.hover_click`, which is higher
in five of six pairs.
The application’s own `gitRevision:selectToReady` span in the raw runs agrees with it.
[Explanations After the Round](#explanations-after-the-round) gives what was found.

## Explanations After the Round

Written after the verdicts, from the round’s own records and short probes.
They change no verdict, and they decide nothing; exp-081 is the declared confirmation
round.

### `commits.hover_click` Is a Race the Background Catalog Walk Decides

The hover starts the commit’s detail and comparison requests 300 ms after the pointer
arrives, and the scenario clicks at 400 ms.
The comparison takes about as long as the gap between the two, so the transition is a
race:

- if the answer lands before the click, the commit is ready in the click’s first frame
  (the application’s `gitRevision:selectToReady` about 31 ms);
- if it lands after, it is ready one frame later (about 47 ms).

The candidate’s code on that path is a lookup that misses and, after the answer arrives,
a deferred keep that sizes it.
That answer is about 5.7 KB as `metab --api` prints it, so its sizing costs well under a
millisecond.
No H90 code runs there: the diff’s Markdown view is `diff-markdown.js`, with
its own route.

Short probes on this corpus did not show the candidate slower.
They ran while another lane’s series ran, at one-minute loads of 13.8 to 55 where
recorded:

- Hover-clicks on both builds, in four invocations, replaying the journey’s cold visits
  and revisits first: each build won and lost the race, and the comparison took 79 to
  287 ms.
- Eight interleaved requests per build of the comparison route: 83 to 125 ms on the
  control and 82 to 157 ms on the candidate, with no difference between the builds.
- The same for the commit route: 21 to 36 ms on both.

What the series rows show instead
([exp-061-hover-click-requests.jsonl](exp-061-hover-click-requests.jsonl)): during the
commits journey a background walk of the pull-request catalog
(`/api/plugin/github/pulls?...&after=N`, each page followed by `pull-cores-prepare`)
runs on its own clock.
The candidate meets it at a different point:

- At `commits.revisit.2`, every candidate run was on page `after=299` and every control
  run on `after=290`, because the candidate’s revisits skip the comparison request.
- At the hover-click, in control pairs 2 to 5 page `after=280` started before the
  hover’s comparison request, and each was ready in one frame.
- In all six candidate runs, that page started after the comparison request, and each
  was ready one frame later.
- Control pairs 1 and 6 had no catalog page before the comparison either.
  Pair 1 was ready in one frame; pair 6, at a load of 10.9, took 79.9 ms.

In the 4 runs where a catalog page started before the hover’s comparison, none was late.
In the 8 where none did, 7 were.

So the extra frame follows the walk’s phase, which the candidate’s faster revisits move,
not work the candidate adds on the hover-click.
That the catalog page’s server work slows the comparison is inferred, not shown: the
requests carry no timings, and the one probe run with the harness’s catalog state did
not place a page inside the hover window.

### The Refs Overlap Is the Repository-Identity Period, on Both Builds

Numbering the 45 pairs in the order they ran (log 1 to 15, summary 16 to 30, refs 31 to
45), the slow samples fall on pairs 4, 8, 12, 20, 24, 28, 32, 36, 40, and 44. That is
every fourth pair, and both builds are slow on the same pairs:

- control: 39 to 95 ms over its median on each;
- candidate: 48 to 68 ms over its median.

Pair 16 is the summary’s first, which follows that route’s unrecorded warm-up requests.
The half took 69.5 s for 45 pairs, so four pairs are about 6 s: the 5 s
`GIT_REPO_INFO_TTL_S` during which both builds keep a repository’s identity, plus the
wait for the next request.
The instrument records no timestamp per sample, so the pair index is the clock.
On the refs route, where the candidate otherwise answers in about 3 ms, those shared
pairs put the candidate’s maximum (71.96 ms) above the control’s minimum (23.49 ms).
The memo does not avoid the identity rediscovery, and the control pays it on the same
requests.

### The Other Flags

- **Outside both rounds, 15:**
  - The flagged views and Pulls transitions request no Git route and no Markdown render
    on either build.
  - Their requests are GitHub plugin routes, in the same counts on both builds, one
    background request aside.
  - The changed modules are not on those paths: only the Markdown plugin imports
    `rendered.js`, and the comparison keep runs only in the Commits panel.
  - They are context, beside the untouched-journey rate above.
- **`commits.cold.1`’s and `commits.first_show`’s flags**, each two of six pairs: the
  same kind as that rate.
  The cold visits fetch their comparison on both builds.

## Verdicts

The accept rule: the named metric moved as predicted; the ranges do not overlap at three
or more runs; nothing else moved the wrong way unaccounted for; and the complexity is
worth it.

**H88(a), the browser comparison cache: unresolved.** Decided by the transition
scenario.

1. Moved as predicted: yes.
   `commits.revisit.1` data requests went 1 → 0 and painted ready 146.8 (97.4–349.2) →
   31.0 (29.8–31.6) ms.
   `commits.revisit.2` went 1 → 0 and 188.9 (146.9–198.0) → 29.6 (28.5–30.8) ms.
2. Ranges apart at six runs: yes, all four.
   Both times were beyond 1.3x in 6 of 6 pairs, with pair ratios 0.21x (0.09–0.32) and
   0.16x (0.14–0.21).
3. Nothing else wrong-way unaccounted for: **no.** The declared guard names every
   `commits.*` transition.
   `commits.hover_click` is a frame later in five of six pairs, and `commits.cold.1` and
   `commits.first_show`’s settle time are flagged in two.
   None is accounted for.
4. Complexity judgment: 173 changed lines in `git-panel.js`, `settings.py`, and
   `types.d.ts`, no dependency, and one stated staleness (`.gitattributes` until
   Refresh) for 1 request and about 115 to 160 ms per revisit.
   Worth it if the hover-click frame is explained or removed; not on this evidence.

What would resolve it: an explanation of `commits.hover_click`, from a trace of the
hover and the click on both builds, then a declared rerun.

**H88(b), the server route memo: unresolved.** Decided by `git-route-pairs.mjs`, fifteen
interleaved pairs per route.

1. Moved as predicted: yes, on all three routes.
   Log 182 → 6.8 ms, summary 184.1 → 3.4 ms, refs 28.4 → 3.6 ms.
2. Ranges apart: log and summary yes, **refs no**. Refs’ control range was 23.49 to
   86.31 ms and its candidate range 3.02 to 71.96 ms, with 13 of 15 pairs beyond 1.3x
   and the lowest pair ratio 1.2x. The criterion named all three routes, so it is not
   met.
3. Guard: B8 correct in 45 of 45 checks.
   In the browser, the transitions the memo serves came out lower: `commits.first_show`
   and `main.files_to_commits.first`, apart and beyond the tolerance.
4. Complexity judgment: 821 changed lines across six server modules, no dependency, and
   two stated limits (outside configuration, lost objects).
   Worth it for the log page and the summary, about 175 and 181 ms per repeat; refs
   alone, about 25 ms here, would not carry it.

What would resolve it: a declared rerun of the server half that times the refs route
apart from the B8 checks, or one that names the identity period as a separate sample
class.

## Pilot

The pilot ran on 2026-11-12 on harness revision 1 (`22af6103`), with five pairs.
Its candidate was `9e1630db`, both rounds’ code before review round 1, and its corpus
was a linked worktree of an active repository, whose refs moved during it.
Its painted-ready times came from a harness revision whose crediting review A of the
harness found unsound, and its candidate predates the review-round-1 fixes.
It is not evidence either way.
Its request counts agreed with this round’s: 1 → 0 on each revisit, 2 → 1 on a main-tab
return to a selected commit.
Its server half measured 5x to 39x faster repeats, with ranges apart, on a corpus whose
refs body was 80,805 bytes.
Its records: [samples](exp-061-pilot-transition-samples.jsonl),
[detail](exp-061-pilot-transition-detail.jsonl), and
[route timings](exp-061-pilot-git-routes-samples.json).

## Limits

- Headless Chrome only; the native app’s WebKit is not measured.
- One candidate carried both rounds’ changes.
  That H90’s code is not on the commit path is inferred from reading it: the diff’s
  Markdown view uses `diff-markdown.js` and its own route, not `rendered.js`. It was not
  measured.
- The harness fixes its own ports at 8890 to 8899; only the server half used 8910 to
  8913\.
- The corpus’s refs body is 2,311 bytes (20 refs), smaller than an active repository’s,
  so the refs route’s saving here is smaller than in the pilot.
- The browser keep’s memory was not measured in a browser.
  Its bound is the JSON length measured over this repository’s last 200 commits; the
  parsed answers held 0.97 to 1.66 times that in V8’s heap, in Node, over five answers.
- H88 is registered in the plan on the research branch, not yet in this branch’s plan.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->

---
title: Comparison Cache, Route Memo, and Markdown Render Cache, Confirmation on Revision 5
softschema:
  contract: metabrowser.loadtime:Experiment/v1
  schema: experiment.schema.yaml
  envelope: experiment
  status: enforced
experiment:
  id: exp-086
  title: Comparison Cache, Route Memo, and Markdown Render Cache, Confirmation on Revision 5
  date: "2026-11-14"
  hypotheses:
    - H88
    - H90
  subject:
    corpus: "Standalone clone of this repository (corpus v2), as every judged run saw it: HEAD 7a02fed4 checked out and clean; trunk and server git log head 115068f5; refs digest 0ee6df52c12d13da. Its refs/remotes/origin/main was fetched from 083e78e4 to 115068f5 at 09:09:50Z, between amendment 3's check (09:01:26Z) and the first pair (09:25:03Z); see Deviation from the Protocol."
    corpus_files: 1286
    host_cpu: 10 CPUs
    host_system: Darwin 25.5.0 arm64, Node 24.19.0, Low Power Mode on, AC power
    browser: Headless Chrome 152.0.7977.83 over the DevTools Protocol, a fresh profile per journey, trusted pointer and key input.
    viewport: 1440x900
    cold: false
  method:
    runs_per_condition: 6
    interleaved: true
    control: metab 0.12.1.dev705+67dbbe6e (+710 commits, bfca78d44), an editable checkout at bfca78d4 (main with #400, as merged into the candidate), clean at the start and end of every run, a fresh server process per run.
    candidate: metab 0.12.1.dev734+dfe7dfaf (+742 commits, fc2a6d84a), an editable checkout of claude/perf-caches at fc2a6d84, clean at the start and end of every run, a fresh server process per run. It differs from the control by #368 alone (13 files under src/), the repository-identity fix and review F's fixes included.
    record: exp-086-transition-samples.jsonl, exp-086-git-routes-samples.json, exp-086-server-half.json, exp-086-identity-check.json
    protocol:
      path: exp-086-protocol.txt
      sha256: e05220652d4698c51dbd7c031f8735b01f2f3ac1bddc2c3583f2c6116c85579f
  results:
    - metric: requests_data.commits.revisit.1
      control_median: 1
      candidate_median: 0
      control_range: [1, 1]
      candidate_range: [0, 0]
      overlapping: false
    - metric: painted_ready_ms.commits.revisit.1
      control_median: 196.6
      candidate_median: 30.6
      control_range: [147.8, 198.5]
      candidate_range: [29.5, 32.1]
      overlapping: false
    - metric: requests_data.commits.revisit.2
      control_median: 1
      candidate_median: 0
      control_range: [1, 1]
      candidate_range: [0, 0]
      overlapping: false
    - metric: painted_ready_ms.commits.revisit.2
      control_median: 129.9
      candidate_median: 30.5
      control_range: [96.6, 148.4]
      candidate_range: [30.1, 32.0]
      overlapping: false
    - metric: painted_ready_ms.commits.hover_click
      control_median: 31.9
      candidate_median: 31.5
      control_range: [30.7, 32.7]
      candidate_range: [31.0, 32.5]
      overlapping: true
    - metric: painted_ready_ms.commits.cold.1
      control_median: 196.8
      candidate_median: 163.8
      control_range: [147.3, 213.6]
      candidate_range: [98.7, 165.0]
      overlapping: true
    - metric: client_ms.api_git_log_limit_250
      control_median: 144.36
      candidate_median: 6.04
      control_range: [136.92, 188.07]
      candidate_range: [5.62, 6.74]
      overlapping: false
    - metric: client_ms.api_git_summary
      control_median: 164.36
      candidate_median: 2.91
      control_range: [145.98, 240.99]
      candidate_range: [2.0, 3.39]
      overlapping: false
    - metric: client_ms.api_git_refs
      control_median: 20.95
      candidate_median: 2.95
      control_range: [20.46, 59.52]
      candidate_range: [1.54, 3.46]
      overlapping: false
    - metric: requests_kpress.files.revisit.markdown_small
      control_median: 1
      candidate_median: 0
      control_range: [1, 1]
      candidate_range: [0, 0]
      overlapping: false
    - metric: post_body_bytes.files.revisit.markdown_large
      control_median: 191142
      candidate_median: 0
      control_range: [191142, 191142]
      candidate_range: [0, 0]
      overlapping: false
    - metric: painted_ready_ms.files.revisit.markdown_small
      control_median: 63.8
      candidate_median: 31.0
      control_range: [62.6, 65.0]
      candidate_range: [30.0, 45.3]
      overlapping: false
    - metric: ready_ms.files.cold.image
      control_median: 50.8
      candidate_median: 66.4
      control_range: [50.2, 65.9]
      candidate_range: [50.2, 67.5]
      overlapping: true
  complexity:
    lines_changed: 1733
    new_dependencies: []
    new_failure_modes:
      - A served folder's commit comparison kept by the page does not reflect an edit to the working tree's .gitattributes or Git configuration until Refresh, the same lifetime the page already gives commit detail.
      - The route memo does not notice Git configuration outside the repository, or an object lost from under a ref that still names it.
      - For a repository the reader owns, uninstalling or replacing Git, or editing the global or system Git configuration, can take about a minute to show in the Git tab, where it took five seconds.
      - A kept Markdown render is placed without preprocessing while its file is unchanged; the Worker outlives the last open document by a minute.
    notes: "#368's product code against main at bfca78d4: 13 files under src/, 1,573 insertions and 160 deletions."
  verdict:
    decision: unresolved
    primary_metric: "H88(a): requests_data and painted_ready_ms on commits.revisit.1 and .2; H88(b): client ms of /api/git/log?limit=250, /api/git/summary, and /api/git/refs; H90: requests_kpress and post_body_bytes on four Markdown transitions, and requests_plugin on one"
    reason: "Judged mechanically under the registered rule. H88(a), the comparison cache, meets all four deciding metrics with ranges apart and 6 of 6 pairs beyond 1.3x, and its guard holds: no wrong-way result on any commits.* or main_subject.*commits* transition (commits.hover_click 31.9 to 31.5 ms, no difference; commits.cold.1 lower), all 12 runs valid. H88(b), the route memo, meets its three routes with ranges apart and 15 of 15 pairs beyond (log 144.4 to 6.0 ms, summary 164.4 to 2.9, refs 21.0 to 3.0), B8 correct in 45 of 45 checks, and no wrong-way result on the two transitions that request those routes. H90, the render cache and kept Worker, meets its nine deciding metrics, and painted ready is lower on its four transitions, but its guard on other files.* transitions carries seven wrong-way flags under overlapping ranges, 2 to 4 of 6 pairs beyond (frame counts on four cold files, and files.cold.image's ready time, 50.8 to 66.4 ms, and blank frames), which nothing explains yet. The corpus's remote-tracking ref moved after the protocol's last amendment (Deviation from the Protocol); the round is recorded as run, with H88(a)'s displacement guard weaker than registered."
    commit: fc2a6d84
---
**Status:** The confirmation round of
[exp-081](exp-081-commit-comparison-cache-and-git-route-memo-confirmation.md) and
[exp-082](exp-082-markdown-render-cache-and-kept-worker-confirmation.md), on harness
revision 5, judged mechanically under the registered rule:

- H88(a), the comparison cache: **accepted**.
- H88(b), the route memo: **accepted**.
- H90, the render cache and kept Worker: **unresolved**.

Six pairs were judged and none excluded; all 12 runs were valid.
The corpus’s remote-tracking ref moved after the protocol’s last amendment, so the round
ran on a corpus state the protocol does not describe.
It is recorded as run, and **Deviation from the Protocol**, below, says what that
changes.

## Why This Round

exp-081 rejected H88(a) on two wrong-way guard results, `commits.hover_click` and
`commits.cold.1`, and left H88(b) unresolved on the same two.
A contention sweep after it showed their mechanism: the repository identity was
discovered again by the first Git request after five quiet seconds, about 55 ms at the
server, and a page that asked the server less often moved that cost onto the hover and
the first cold commit.
#368 now keeps the identity while the refs’ state is unchanged (`36d3e325`, with review
F’s fixes in `fc2a6d84`). This round confirms H88 and H90 at that head.

## Protocol

The protocol is [exp-086-protocol.txt](exp-086-protocol.txt), sha256 `e0522065…` as
committed before the first judged pair.
It is registration 2 and three amendments:

- **Registration 2** (2026-11-13T19:52:02Z) set the builds, the journeys
  (`files,maintabs,commits`), paced pairs, the load and power rules, the accept rule,
  the per-hypothesis verdicts, and an identity-period explanation check.
- **Amendment 1** (20:31:00Z) moved the candidate to `fc2a6d84` and added the 60-minute
  stop.
- **Amendment 2** (2026-11-14T09:02:17Z) committed the protocol, with placeholders for
  machine paths and the analysis scripts by sha256.
- **Amendment 3** (09:02:17Z; the harness commit filled in at 09:21:20Z) moved the
  harness to scenario revision 5 at #417’s merge, `3a1ff25e`, and recorded that every
  switch to Commits lands on the newest commit on both builds.

The analysis is committed beside this record:
[exp-086-exclude.mjs](exp-086-exclude.mjs),
[exp-086-identity-check.mjs](exp-086-identity-check.mjs), and
[exp-086-refresh-classify.mjs](exp-086-refresh-classify.mjs).

**The accept rule** is the runbook’s standard one.
Ranges apart with two or more pairs beyond 1.3x is a result; counts are judged on their
ranges.
Two or more pairs beyond under overlapping ranges must be explained with evidence
before accepting, and an explanation that rests only on inference does not count.
A guard flag is resolved the same way, and every guard is judged on all judged pairs.

## Identities, Load, and Power

| Item | Value |
| --- | --- |
| Control | `metab 0.12.1.dev705+67dbbe6e (+710 commits, bfca78d44)`, clean at every run’s start and end |
| Candidate | `metab 0.12.1.dev734+dfe7dfaf (+742 commits, fc2a6d84a)`, clean at every run’s start and end |
| Harness | `3a1ff25e`, scenario revision 5, clean, frozen for the round |
| Corpus | `7a02fed4` checked out, clean, 1,286 indexed files; git log head and trunk `115068f5` in all 12 runs |
| Chrome | 152.0.7977.83, headless |
| Lock | taken 09:24:02Z at a one-minute load of 2.08, released 10:42:22Z |
| Paced pairs | six, 09:25:03Z to 10:40:59Z, the control first in odd pairs; all six judged, none excluded; one-minute load 1.76 to 5.42 at run starts and ends |
| Power | Low Power Mode on and AC power in all 313 samples (every 15 s); the judged mode is 1 |
| Server half | 10:41:03Z to 10:41:57Z, one-minute load 3.16 to 3.03 |

Before this round, one paced pair under amendment 1 (series `2026-11-14T00-46-24-933Z`)
ran on harness revision 4 and was refused on both runs in its warm-up pass.
It was also over the load rule.
No metric of it was read, and it is not judged.

At six runs a side, two identical builds come apart on one comparison with probability 2
in 924, and `compare` expects about one comparison in this round (0.94) to come apart by
chance.

## Deviation from the Protocol

**What happened.** At 09:09:50Z, `git fetch --quiet origin` ran in the corpus clone.
That was after amendment 3’s check (09:01:26Z) and before the first pair (09:25:03Z). It
fast-forwarded `refs/remotes/origin/main` from `083e78e4` to `115068f5`, main’s #425
merge.

**What amendment 3 said, and what held at run time.**

|  | Amendment 3, and the 08:48Z diagnostic it cites | Every judged run |
| --- | --- | --- |
| Checkout | `7a02fed4`, clean | `7a02fed4`, clean |
| Trunk and server git log head | `083e78e4` and `7a02fed4` | both `115068f5` |
| Refs digest (the harness’s) | `387f68dc4e8eb8e0` | `0ee6df52c12d13da` |
| The newest commit a switch to Commits lands on | `7a02fed4`, a merge whose first-parent diff is 32 files (+1098/−119) | `115068f5`, a merge whose first-parent diff is 1 file (+46/−13) |
| Commits above `7a02fed4` in the list | none | 698 |

All 12 runs saw this one corpus state, so `compare`’s sameness checks passed and the
builds were compared like for like.
The registered metrics, their directions, and the guards are unchanged.
Revision 5 names the newest commit by the server’s log head, so every landing still
reads `newest`. The commit subjects of the `commits` and `maintabs` journeys are named
by identity and sat 698 rows further down the list; each journey records where it found
them.

**The cause is not identified.** The product’s own fetches go to a mirror store, with
`--porcelain` and `--no-write-fetch-head` (`cache/origin.py`, `cache/pull_refs.py`).
This one wrote the corpus’s `FETCH_HEAD` and its reflog names `fetch --quiet origin`. No
session transcript records the command.

**What it changes for H88(a).** Amendment 3 argued that the revisits could not hide a
displacement: the newest commit’s comparison, a 32-file merge, would be one more entry
in the candidate’s kept comparisons, and a revisited comparison it displaced would be
fetched again and counted in `requests_data`. In this round `commits.first_show` opened
a 1-file diff instead, so the kept comparisons held a smaller entry than amendment 3
assumed. That guard was weaker than registered: the round shows the revisits kept their
comparisons with a small newest entry beside them, not with the 32-file one amendment 3
named. The Commits-switch transitions (`commits.first_show`, `main.*_to_commits`, and
`main_subject.*_to_commits`) timed a landing on that smaller commit.

## Results

Every number here is from `compare` over the judged samples
([exp-086-transition-samples.jsonl](exp-086-transition-samples.jsonl)), from the route
record ([exp-086-git-routes-samples.json](exp-086-git-routes-samples.json)) and its
classification ([exp-086-server-half.json](exp-086-server-half.json)), or from the
identity-period check ([exp-086-identity-check.json](exp-086-identity-check.json)).
`compare` met all 13 expectations and exits 1 on 7 wrong-way results, with no gaps.

### H88(a): Commit Revisits

| Transition | Data requests | Painted ready ms, control → candidate | Verdict |
| --- | --- | --- | --- |
| `commits.revisit.1` | 1 → 0 | 196.6 (147.8–198.5) → 30.6 (29.5–32.1) | ranges apart, 6 of 6 pairs beyond |
| `commits.revisit.2` | 1 → 0 | 129.9 (96.6–148.4) → 30.5 (30.1–32.0) | ranges apart, 6 of 6 pairs beyond |

**The guard holds.** No `commits.*` or `main_subject.*commits*` transition moved the
wrong way, and all 12 runs were valid.
The two that failed exp-081 are no longer flagged:

| Transition | Painted ready ms, control → candidate | Verdict |
| --- | --- | --- |
| `commits.hover_click` | 31.9 (30.7–32.7) → 31.5 (31.0–32.5) | no detected difference |
| `commits.cold.1` | 196.8 (147.3–213.6) → 163.8 (98.7–165.0) | lower; ranges overlap, 2 of 6 pairs beyond |
| `commits.cold.2` | 146.9 (97.1–148.9) → 130.6 (97.2–147.8) | lower; ranges overlap, 2 of 6 pairs beyond |
| `commits.cold.3` | 147.1 (130.0–148.6) → 122.2 (97.1–147.7) | lower; ranges overlap, 3 of 6 pairs beyond |
| `commits.first_show` | 413.7 (362.7–430.2) → 178.9 (146.4–180.1) | lower, ranges apart, 6 of 6 pairs beyond |
| `main.files_to_commits.first` | 362.6 (313.8–365.0) → 178.8 (145.5–181.5) | lower, ranges apart, 6 of 6 pairs beyond |
| `main.files_to_commits.again` | 196.5 (195.5–198.8) → 63.2 (62.2–64.7) | lower, ranges apart, 6 of 6 pairs beyond |
| `main.pulls_to_commits` | 196.5 (180.2–197.2) → 64.7 (63.9–64.9) | lower, ranges apart, 6 of 6 pairs beyond |
| `main_subject.files_to_commits` | 197.6 (195.8–213.8) → 63.4 (62.8–79.9) | lower, ranges apart, 6 of 6 pairs beyond |
| `main_subject.pulls_to_commits` | 205.2 (179.7–246.7) → 64.5 (63.3–79.6) | lower, ranges apart, 6 of 6 pairs beyond |

H88(a) is **accepted**.

### H88(b): Server Half

| Route | Control ms | Candidate ms | Pair ratios (control / candidate) | Apart |
| --- | --- | --- | --- | --- |
| `/api/git/log?limit=250` | 144.36 (136.92–188.07) | 6.04 (5.62–6.74) | 24.15x (21.81–32.28), 15 of 15 beyond | yes |
| `/api/git/summary` | 164.36 (145.98–240.99) | 2.91 (2.00–3.39) | 55.96x (50.70–79.72), 15 of 15 beyond | yes |
| `/api/git/refs` | 20.95 (20.46–59.52) | 2.95 (1.54–3.46) | 7.24x (5.96–18.66), 15 of 15 beyond | yes |

- Every status was 200.
- Each route’s bodies had the same length on both builds.
- Every candidate answer carried an entity tag.
- B8 was correct in 45 of 45 checks.
- No route overlaps, so exp-081’s identity-refresh rule has nothing to explain.
  On both builds, its refresh pairs are 5, 10, and 15 on the log, 5, 9, and 14 on the
  summary, and 3, 8, and 13 on the refs.
- **The guard holds.** The only transitions whose requests include these routes are
  `main.files_to_commits.first` and `commits.first_show`, both lower with ranges apart.

H88(b) is **accepted**.

### H90: Markdown Revisits

All nine deciding metrics are met:

- `requests_kpress` goes 1 → 0 on all four transitions.
- `post_body_bytes` goes 19,168 → 0 on `files.revisit.markdown_small` and
  `files.history_back`, and 191,142 → 0 on `files.revisit.markdown_large` and
  `files.history_forward`.
- `requests_plugin` goes 3 → 0 on `files.revisit.markdown_small`.

Each is ranges apart.
Painted ready is lower on all four:

| Transition | Painted ready ms, control → candidate | Verdict |
| --- | --- | --- |
| `files.revisit.markdown_small` | 63.8 (62.6–65.0) → 31.0 (30.0–45.3) | ranges apart, 6 of 6 pairs beyond |
| `files.revisit.markdown_large` | 138.1 (129.7–146.1) → 104.7 (96.8–113.4) | ranges apart, 4 of 6 pairs beyond |
| `files.history_back` | 41.3 (39.7–41.9) → 24.3 (23.5–37.4) | ranges apart, 4 of 6 pairs beyond |
| `files.history_forward` | 121.1 (109.6–124.8) → 106.0 (92.4–110.1) | ranges overlap, 1 of 6 pairs beyond |

The guard’s other clauses hold:

- no long task on `files.revisit.markdown_large` or `files.history_forward` on either
  build;
- `main.files_to_pulls.first` settles at 18.0 → 11.1 ms, lower, ranges overlapping;
- `main.files_to_pulls.again` settles at 8.9 → 8.2 ms.

**The guard on other `files.*` transitions has seven wrong-way flags,** each under
overlapping ranges:

| Transition | Metric | Control → candidate | Pairs beyond |
| --- | --- | --- | --- |
| `files.cold.image` | ready ms | 50.8 (50.2–65.9) → 66.4 (50.2–67.5) | 4 of 6 |
| `files.cold.image` | frames to ready | 3 → 3.5 (3–4) | 3 of 6 |
| `files.cold.image` | blank frames | 1 → 1.5 (1–2) | 3 of 6 |
| `files.cold.image` | blank ms | 16.6 → 25.0 (16.6–33.4) | 3 of 6 |
| `files.cold.markdown_mid` | frames to ready | 2 (2–3) → 2 (2–3) | 2 of 6 |
| `files.cold.json` | frames to ready | 2 → 2 (2–3) | 2 of 6 |
| `files.cold.diff` | frames to ready | 3.5 (3–4) → 4 (3–4) | 3 of 6 |

The protocol names no accounting for these flags.
It does not name exp-087’s later-frame test for frame counts, and it has nothing for the
image’s ready and blank times.
The rule asks that such a flag be explained with evidence before accepting, and this
round has none. H90 is **unresolved**.

**Observation, not an account:** every flagged pair differs by exactly one frame at the
16.6 ms frame interval, the candidate a frame later.
Some unflagged pairs differ by one frame the other way: `files.cold.image`’s ready time
is 64.6 → 50.2 ms in one pair, and `files.cold.markdown_mid` has one pair and
`files.cold.diff` two pairs one frame earlier on the candidate.
The round has no trace, and no request list that separates the flagged pairs from the
rest.

### The Identity-Period Explanation Check

The check is declared, not accounting, and decides no verdict.
It **does not fit** the identity account as registered:

- **The comparison route fits.** The median server time of requests on a TTL boundary
  over those within it is 1.59 on the control (121 over 76 ms; 36 and 132 requests) and
  1.00 on the candidate (78 over 78 ms; 31 and 53 requests).
- **The commit route** has no boundary request on the control: in every control run the
  comparison request arrived first.
  So its ratio cannot be formed, and the registered rule reads that as not fitting.
  On the candidate it is 1.04 (28 over 27 ms; 5 and 79 requests).
- **Per run, `commits.hover_click`’s comparison** was a boundary request in 6 of 6
  candidate runs (73 to 90 ms) and in none of the control’s (70 to 82 ms).
- **Per run, `commits.cold.1`’s comparison** was a boundary request in all 6 control
  runs (117 to 143 ms) and in 3 of 6 candidate runs (77 to 84 ms).

## Reproducing

```shell
# The frozen harness at 3a1ff25e; $HARNESS, $CONTROL, $CANDIDATE, $CORPUS as in the protocol.
node $HARNESS/explorations/performance-loop/transitions.mjs compare \
  exp-086-transition-samples.jsonl --control control --candidate candidate \
  --expect commits.revisit.1:requests_data:lower  # ...the 13 --expect flags of exp-081
node exp-086-refresh-classify.mjs exp-086-git-routes-samples.json server-half.json
```

The identity-period check reads the runs’ server logs, which hold local paths and stay
in the attic. Its result is [exp-086-identity-check.json](exp-086-identity-check.json).

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
